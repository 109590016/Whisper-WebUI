from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from modules.recordtrans.recording import (
    RecordingController,
    RecordingError,
)
from modules.recordtrans.repository import RecordTransRepository
from modules.recordtrans.storage import DataPaths, LocalMediaStorage, StorageError
from modules.recordtrans.ui.recording import (
    _capture_changed,
    _save_recording,
    _submit_recording,
)


class FakeSubmitter:
    def __init__(self) -> None:
        self.source_ids: list[str] = []

    def submit(self, source_id: str) -> str:
        self.source_ids.append(source_id)
        return "job-1"


class FailingStorage:
    def store_path(self, source: str, kind: object) -> object:
        raise StorageError("磁碟空間不足")


class FailingRepository:
    def add_source(self, source: object) -> str:
        raise sqlite3.OperationalError("database is locked")


class RecordingControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.paths = DataPaths.from_root(self.root / "資料 目錄")
        self.storage = LocalMediaStorage(self.paths)
        self.repository = RecordTransRepository(self.paths.state / "recordtrans.sqlite3")
        self.submitter = FakeSubmitter()
        self.controller = RecordingController(
            self.storage,
            self.repository,
            self.submitter,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _recording(self, name: str = "訪談.webm") -> Path:
        path = self.root / name
        path.write_bytes(b"recorded audio")
        return path

    def test_permission_denied_or_no_device_does_not_create_source(self) -> None:
        denied = self.controller.capture_ready(None)
        no_device = self.controller.capture_unavailable("找不到麥克風裝置。")

        self.assertFalse(denied.can_save)
        self.assertFalse(denied.can_submit)
        self.assertIn("權限", denied.message)
        self.assertIn("找不到", no_device.message)
        with closing(sqlite3.connect(self.repository.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0], 0)

    def test_capture_can_be_replayed_before_and_after_durable_save(self) -> None:
        temporary = self._recording()
        captured = self.controller.capture_ready(temporary)

        self.assertEqual(captured.temporary_path, str(temporary))
        self.assertTrue(captured.can_save)
        self.assertFalse(captured.can_submit)

        saved = self.controller.save(captured)
        self.assertTrue(saved.can_submit)
        self.assertIsNotNone(saved.saved)
        assert saved.saved is not None
        permanent = Path(saved.saved.playback_path)
        self.assertTrue(permanent.is_file())
        self.assertEqual(permanent.read_bytes(), b"recorded audio")
        self.assertNotEqual(permanent, temporary)

    def test_save_without_submit_survives_repository_reopen(self) -> None:
        saved = self.controller.save(self.controller.capture_ready(self._recording()))
        assert saved.saved is not None

        reopened = RecordTransRepository(self.repository.database_path)
        with closing(sqlite3.connect(reopened.database_path)) as connection:
            row = connection.execute(
                "SELECT id, relative_path FROM sources WHERE id = ?",
                (saved.saved.source_id,),
            ).fetchone()
            job_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

        self.assertEqual(row[0], saved.saved.source_id)
        self.assertTrue(self.storage.resolve(row[1]).is_file())
        self.assertEqual(job_count, 0)

    def test_save_failure_never_enables_submission(self) -> None:
        controller = RecordingController(
            FailingStorage(),  # type: ignore[arg-type]
            self.repository,
            self.submitter,
        )
        captured = controller.capture_ready(self._recording())

        with self.assertRaisesRegex(RecordingError, "保存失敗"):
            controller.save(captured)
        self.assertFalse(captured.can_submit)
        self.assertEqual(self.submitter.source_ids, [])

    def test_repository_failure_removes_untracked_permanent_file(self) -> None:
        controller = RecordingController(
            self.storage,
            FailingRepository(),
            self.submitter,
        )
        captured = controller.capture_ready(self._recording())

        with self.assertRaisesRegex(RecordingError, "來源尚未建立"):
            controller.save(captured)
        self.assertEqual(list(self.paths.recordings.iterdir()), [])

    def test_submit_requires_saved_recording_and_reuses_source_id(self) -> None:
        captured = self.controller.capture_ready(self._recording())
        with self.assertRaisesRegex(RecordingError, "尚未永久保存"):
            self.controller.submit(captured)

        saved = self.controller.save(captured)
        submitted = self.controller.submit(saved)

        assert saved.saved is not None
        self.assertEqual(self.submitter.source_ids, [saved.saved.source_id])
        self.assertEqual(submitted.saved, saved.saved)
        self.assertEqual(submitted.job_id, "job-1")

    def test_ui_callbacks_only_enable_submit_after_save(self) -> None:
        fake_gradio = SimpleNamespace(update=lambda **kwargs: kwargs)
        with patch.dict(sys.modules, {"gradio": fake_gradio}):
            playback, _, captured, save_update, submit_update = _capture_changed(
                self.controller,
                str(self._recording()),
            )
            self.assertEqual(playback, captured.temporary_path)
            self.assertEqual(save_update, {"interactive": True})
            self.assertEqual(submit_update, {"interactive": False})

            _, _, source_id, saved, submit_update = _save_recording(
                self.controller,
                captured,
            )
            self.assertEqual(source_id, saved.saved.source_id)
            self.assertEqual(submit_update, {"interactive": True})

        message, job_id, submitted = _submit_recording(self.controller, saved)
        self.assertEqual(job_id, "job-1")
        self.assertIn("已建立", message)
        self.assertEqual(submitted.saved.source_id, source_id)


if __name__ == "__main__":
    unittest.main()
