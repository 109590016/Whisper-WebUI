from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.recordtrans.contracts import JobStatus, Segment, SourceKind
from modules.recordtrans.media import MediaInfo
from modules.recordtrans.repository import RecordTransRepository
from modules.recordtrans.service import RecordTransService
from modules.recordtrans.storage import DataPaths, LocalMediaStorage
from modules.recordtrans.transcription import TranscriptionResult


class FakeAdapter:
    def transcribe(self, source: str | Path) -> TranscriptionResult:
        return TranscriptionResult(
            (Segment(0.0, 1.25, "测试 RecordTrans 123"),),
            "zh",
            {"fixture": True},
        )


class FakeProbe:
    def inspect(self, path: str | Path) -> MediaInfo:
        candidate = Path(path)
        return MediaInfo(candidate, ".wav", frozenset({"wav"}), candidate.stat().st_size, 1.25, "pcm_s16le")


class ServiceTests(unittest.TestCase):
    def test_upload_runs_through_queue_and_persists_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = DataPaths.from_root(root / "資料")
            storage = LocalMediaStorage(paths)
            repository = RecordTransRepository(paths.state / "recordtrans.sqlite3")
            source = root / "sample.wav"
            source.write_bytes(b"RIFF fixture")
            service = RecordTransService(
                paths, repository, storage, FakeAdapter(), FakeProbe(),
                converter=lambda text: text.replace("测试", "測試"),
            )
            try:
                submitted = service.submit_upload(source)
                service.queue.wait_until_idle()
                view = service.present(submitted.job_id)
                self.assertIsNotNone(view)
                assert view is not None
                self.assertEqual(view["status"], JobStatus.COMPLETED)
                self.assertIn("測試 RecordTrans 123", view["text"])
                self.assertEqual(len(view["downloads"]), 3)
                self.assertTrue(all(Path(path).is_file() for path in view["downloads"]))
            finally:
                service.queue.close()

    def test_repository_can_read_source_and_recent_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = DataPaths.from_root(Path(directory))
            storage = LocalMediaStorage(paths)
            repository = RecordTransRepository(paths.state / "recordtrans.sqlite3")
            media = Path(directory) / "voice.webm"
            media.write_bytes(b"audio")
            stored = storage.store_path(media, kind=SourceKind.UPLOAD)
            repository.add_source(stored)
            job_id = repository.create_job(stored.identifier)
            self.assertEqual(repository.get_source(stored.identifier)["id"], stored.identifier)
            self.assertEqual(repository.list_jobs(1)[0]["id"], job_id)
            with self.assertRaises(ValueError):
                repository.list_jobs(0)


if __name__ == "__main__":
    unittest.main()
