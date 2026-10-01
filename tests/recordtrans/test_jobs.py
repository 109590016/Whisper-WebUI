from __future__ import annotations

import io
import threading
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from modules.recordtrans.contracts import JobStatus, Segment, SourceKind
from modules.recordtrans.jobs import JobStoreView, SingleWorkerJobQueue
from modules.recordtrans.repository import RecordTransRepository
from modules.recordtrans.storage import DataPaths, LocalMediaStorage
from modules.recordtrans.ui.jobs import STATUS_LABELS, downloadable_outputs, present_job


class JobLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.paths = DataPaths.from_root(Path(self.temporary_directory.name) / "data")
        self.storage = LocalMediaStorage(self.paths)
        self.repository = RecordTransRepository(
            self.paths.state / "recordtrans.sqlite3"
        )
        self.view = JobStoreView(self.repository.database_path)
        self.queues: list[SingleWorkerJobQueue] = []

    def tearDown(self) -> None:
        for job_queue in self.queues:
            job_queue.close()
        self.temporary_directory.cleanup()

    def _create_job(self, name: str = "sample.wav") -> str:
        source = self.storage.store_stream(
            io.BytesIO(b"audio"), name, SourceKind.UPLOAD
        )
        self.repository.add_source(source)
        return self.repository.create_job(source.identifier)

    def _queue(self) -> SingleWorkerJobQueue:
        job_queue = SingleWorkerJobQueue(self.repository)
        job_queue.start()
        self.queues.append(job_queue)
        return job_queue

    def test_single_worker_never_processes_two_jobs_at_once(self) -> None:
        first = self._create_job("first.wav")
        second = self._create_job("second.wav")
        first_entered = threading.Event()
        release_first = threading.Event()
        active = 0
        maximum_active = 0
        guard = threading.Lock()

        def processor(job_id: str) -> None:
            nonlocal active, maximum_active
            with guard:
                active += 1
                maximum_active = max(maximum_active, active)
            if job_id == first:
                first_entered.set()
                self.assertTrue(release_first.wait(2))
            with guard:
                active -= 1

        job_queue = self._queue()
        job_queue.submit(first, processor)
        job_queue.submit(second, processor)
        self.assertTrue(first_entered.wait(2))
        self.assertEqual(self.repository.get_job(first)["status"], "processing")
        self.assertEqual(self.repository.get_job(second)["status"], "queued")
        release_first.set()
        job_queue.wait_until_idle()

        self.assertEqual(maximum_active, 1)
        self.assertEqual(self.repository.get_job(first)["status"], "completed")
        self.assertEqual(self.repository.get_job(second)["status"], "completed")

    def test_failure_is_persisted_and_status_projection_has_no_percentage(self) -> None:
        job_id = self._create_job()

        def fail(_: str) -> None:
            raise RuntimeError("模型載入失敗")

        job_queue = self._queue()
        job_queue.submit(job_id, fail)
        job_queue.wait_until_idle()

        reopened = JobStoreView(self.repository.database_path)
        snapshot = reopened.get(job_id)
        self.assertIsNotNone(snapshot)
        model = present_job(snapshot)
        self.assertEqual(model["status_label"], "失敗")
        self.assertEqual(model["error"], "模型載入失敗")
        self.assertNotIn("percent", model)
        self.assertGreaterEqual(model["elapsed_seconds"], 0.0)

    def test_elapsed_time_uses_current_attempt_timestamps(self) -> None:
        job_id = self._create_job()
        self.repository.transition_job(job_id, JobStatus.PROCESSING)
        snapshot = self.view.get(job_id)
        self.assertIsNotNone(snapshot)
        now = snapshot.started_at + timedelta(seconds=12.3456)
        model = present_job(snapshot, now)
        self.assertEqual(model["elapsed_seconds"], 12.346)
        self.assertEqual(model["status_label"], "處理中")

    def test_every_persistent_status_has_a_clear_label(self) -> None:
        self.assertEqual(
            STATUS_LABELS,
            {
                JobStatus.QUEUED: "等待中",
                JobStatus.PROCESSING: "處理中",
                JobStatus.COMPLETED: "已完成",
                JobStatus.FAILED: "失敗",
                JobStatus.INTERRUPTED: "已中斷",
            },
        )

    def test_startup_interrupts_processing_and_retry_preserves_attempt(self) -> None:
        job_id = self._create_job()
        self.repository.transition_job(job_id, JobStatus.PROCESSING)
        job_queue = SingleWorkerJobQueue(self.repository)
        self.assertEqual(job_queue.start(), 1)
        self.queues.append(job_queue)
        self.assertEqual(self.view.get(job_id).status, JobStatus.INTERRUPTED)

        sequence = job_queue.retry(job_id, lambda _: None, lambda _: True)
        self.assertEqual(sequence, 2)
        job_queue.wait_until_idle()
        attempts = self.view.attempts(job_id)
        self.assertEqual([attempt["status"] for attempt in attempts], [
            "interrupted",
            "completed",
        ])
        self.assertEqual([attempt["sequence"] for attempt in attempts], [1, 2])

    def test_retry_rejects_missing_source_without_creating_attempt(self) -> None:
        job_id = self._create_job()
        self.repository.transition_job(job_id, JobStatus.PROCESSING)
        self.repository.transition_job(job_id, JobStatus.FAILED, "decode failed")
        job_queue = self._queue()

        with self.assertRaisesRegex(FileNotFoundError, "永久來源不存在"):
            job_queue.retry(job_id, lambda _: None, lambda _: False)

        self.assertEqual(len(self.view.attempts(job_id)), 1)
        self.assertEqual(self.view.get(job_id).status, JobStatus.FAILED)

    def test_downloads_are_hidden_until_completed_result_exists(self) -> None:
        job_id = self._create_job()
        self.repository.save_result(
            job_id,
            [Segment(0, 1, "測試")],
            {"txt": "outputs/result.txt"},
            "zh",
        )
        queued = self.view.get(job_id)
        self.assertEqual(downloadable_outputs(queued), {})

        self.repository.transition_job(job_id, JobStatus.PROCESSING)
        processing = self.view.get(job_id)
        self.assertEqual(downloadable_outputs(processing), {})
        self.repository.transition_job(job_id, JobStatus.COMPLETED)
        completed = self.view.get(job_id)
        self.assertEqual(
            downloadable_outputs(completed), {"txt": Path("outputs/result.txt")}
        )

    def test_duplicate_submission_is_rejected(self) -> None:
        job_id = self._create_job()
        entered = threading.Event()
        release = threading.Event()

        def processor(_: str) -> None:
            entered.set()
            release.wait(2)

        job_queue = self._queue()
        job_queue.submit(job_id, processor)
        self.assertTrue(entered.wait(2))
        with self.assertRaises(ValueError):
            job_queue.submit(job_id, processor)
        release.set()
        job_queue.wait_until_idle()


if __name__ == "__main__":
    unittest.main()
