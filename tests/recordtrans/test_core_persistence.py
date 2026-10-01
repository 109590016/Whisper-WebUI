from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from modules.recordtrans import (
    DataPaths,
    JobStatus,
    LocalMediaStorage,
    RecordTransRepository,
    Segment,
    SourceKind,
    StorageError,
)


class CorePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_data_paths_support_chinese_and_spaces(self) -> None:
        paths = DataPaths.from_root(self.root / "研究 錄音")
        paths.ensure_writable()
        self.assertTrue(paths.recordings.is_dir())
        self.assertTrue(paths.state.is_dir())

    def test_same_name_sources_never_overwrite(self) -> None:
        storage = LocalMediaStorage(DataPaths.from_root(self.root / "data"))
        first = storage.store_stream(
            io.BytesIO(b"first"), "訪談.webm", SourceKind.RECORDING
        )
        second = storage.store_stream(
            io.BytesIO(b"second"), "訪談.webm", SourceKind.RECORDING
        )
        self.assertNotEqual(first.identifier, second.identifier)
        self.assertEqual(storage.resolve(first.relative_path).read_bytes(), b"first")
        self.assertEqual(storage.resolve(second.relative_path).read_bytes(), b"second")

    def test_path_escape_is_rejected(self) -> None:
        storage = LocalMediaStorage(DataPaths.from_root(self.root / "data"))
        with self.assertRaises(StorageError):
            storage.resolve("../outside.wav")

    def test_repository_persists_and_enforces_transitions(self) -> None:
        paths = DataPaths.from_root(self.root / "data")
        storage = LocalMediaStorage(paths)
        source = storage.store_stream(
            io.BytesIO(b"audio"), "sample.wav", SourceKind.UPLOAD
        )
        repository = RecordTransRepository(paths.state / "recordtrans.sqlite3")
        repository.add_source(source)
        job_id = repository.create_job(source.identifier)
        repository.transition_job(job_id, JobStatus.PROCESSING)

        reopened = RecordTransRepository(paths.state / "recordtrans.sqlite3")
        self.assertEqual(reopened.get_job(job_id)["status"], JobStatus.PROCESSING.value)
        self.assertEqual(reopened.mark_processing_interrupted(), 1)
        self.assertEqual(reopened.get_job(job_id)["status"], JobStatus.INTERRUPTED.value)
        self.assertEqual(reopened.retry_job(job_id), 2)
        self.assertEqual(reopened.get_job(job_id)["status"], JobStatus.QUEUED.value)

        with self.assertRaises(ValueError):
            reopened.transition_job(job_id, JobStatus.COMPLETED)

        connection = sqlite3.connect(paths.state / "recordtrans.sqlite3")
        try:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        finally:
            connection.close()

    def test_segment_validation(self) -> None:
        self.assertEqual(Segment(0.0, 1.25, "測試").text, "測試")
        with self.assertRaises(ValueError):
            Segment(2.0, 1.0, "invalid")
