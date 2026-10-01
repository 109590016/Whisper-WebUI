from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence
from uuid import uuid4

from .contracts import ALLOWED_TRANSITIONS, JobStatus, Segment, SourceKind
from .storage import StoredSource


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RecordTransRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    relative_path TEXT NOT NULL UNIQUE,
                    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(id),
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    sequence INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    UNIQUE(job_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS results (
                    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
                    detected_language TEXT,
                    segments_json TEXT NOT NULL,
                    output_paths_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def add_source(self, source: StoredSource) -> str:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO sources
                   (id, kind, original_name, relative_path, size_bytes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    source.identifier,
                    source.kind.value,
                    source.original_name,
                    source.relative_path,
                    source.size_bytes,
                    _now(),
                ),
            )
        return source.identifier

    def create_job(self, source_id: str) -> str:
        job_id = str(uuid4())
        timestamp = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO jobs (id, source_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, source_id, JobStatus.QUEUED.value, timestamp, timestamp),
            )
            connection.execute(
                """INSERT INTO attempts (id, job_id, sequence, status)
                   VALUES (?, ?, 1, ?)""",
                (str(uuid4()), job_id, JobStatus.QUEUED.value),
            )
        return job_id

    def get_job(self, job_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def get_source(self, source_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, object]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_result(self, job_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM results WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def transition_job(
        self, job_id: str, new_status: JobStatus, error: str | None = None
    ) -> None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            current = JobStatus(row["status"])
            if new_status not in ALLOWED_TRANSITIONS[current]:
                raise ValueError(f"illegal job transition: {current} -> {new_status}")
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, error = ? WHERE id = ?",
                (new_status.value, _now(), error, job_id),
            )
            started_at = _now() if new_status is JobStatus.PROCESSING else None
            finished_at = (
                _now()
                if new_status
                in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.INTERRUPTED}
                else None
            )
            connection.execute(
                """UPDATE attempts SET status = ?,
                   started_at = COALESCE(started_at, ?), finished_at = ?, error = ?
                   WHERE job_id = ? AND sequence = (
                       SELECT MAX(sequence) FROM attempts WHERE job_id = ?
                   )""",
                (new_status.value, started_at, finished_at, error, job_id, job_id),
            )

    def mark_processing_interrupted(self) -> int:
        timestamp = _now()
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id FROM jobs WHERE status = ?", (JobStatus.PROCESSING.value,)
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (JobStatus.INTERRUPTED.value, timestamp, row["id"]),
                )
                connection.execute(
                    """UPDATE attempts SET status = ?, finished_at = ?
                       WHERE job_id = ? AND sequence = (
                           SELECT MAX(sequence) FROM attempts WHERE job_id = ?
                       )""",
                    (JobStatus.INTERRUPTED.value, timestamp, row["id"], row["id"]),
                )
        return len(rows)

    def retry_job(self, job_id: str) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            current = JobStatus(row["status"])
            if current not in {JobStatus.FAILED, JobStatus.INTERRUPTED}:
                raise ValueError("only failed or interrupted jobs can be retried")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM attempts WHERE job_id = ?",
                (job_id,),
            ).fetchone()[0]
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, error = NULL WHERE id = ?",
                (JobStatus.QUEUED.value, _now(), job_id),
            )
            connection.execute(
                """INSERT INTO attempts (id, job_id, sequence, status)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid4()), job_id, sequence, JobStatus.QUEUED.value),
            )
        return int(sequence)

    def save_result(
        self,
        job_id: str,
        segments: Sequence[Segment],
        output_paths: dict[str, str],
        detected_language: str | None,
    ) -> None:
        segment_payload = [
            {"start": segment.start, "end": segment.end, "text": segment.text}
            for segment in segments
        ]
        with self._connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO results
                   (job_id, detected_language, segments_json, output_paths_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    job_id,
                    detected_language,
                    json.dumps(segment_payload, ensure_ascii=False),
                    json.dumps(output_paths, ensure_ascii=False),
                    _now(),
                ),
            )
