from __future__ import annotations

import queue
import sqlite3
import threading
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .contracts import JobStatus
from .repository import RecordTransRepository


JobProcessor = Callable[[str], None]


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    job_id: str
    source_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    error: str | None
    attempt_sequence: int
    started_at: datetime | None
    finished_at: datetime | None
    output_paths: dict[str, str] | None

    def elapsed_seconds(self, now: datetime | None = None) -> float:
        start = self.started_at or self.created_at
        end = self.finished_at or now or datetime.now(timezone.utc)
        return max(0.0, (end - start).total_seconds())

    @property
    def downloads_available(self) -> bool:
        return self.status is JobStatus.COMPLETED and bool(self.output_paths)


class JobStoreView:
    """Read-only projections over the persistent job repository."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def get(self, job_id: str) -> JobSnapshot | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT jobs.*, attempts.sequence, attempts.started_at,
                       attempts.finished_at, results.output_paths_json
                FROM jobs
                JOIN attempts ON attempts.job_id = jobs.id
                 AND attempts.sequence = (
                    SELECT MAX(latest.sequence)
                    FROM attempts AS latest
                    WHERE latest.job_id = jobs.id
                 )
                LEFT JOIN results ON results.job_id = jobs.id
                WHERE jobs.id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._snapshot(row) if row else None

    def attempts(self, job_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT sequence, status, started_at, finished_at, error
                   FROM attempts WHERE job_id = ? ORDER BY sequence""",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> JobSnapshot:
        import json

        output_paths = (
            json.loads(row["output_paths_json"])
            if row["output_paths_json"] is not None
            else None
        )
        return JobSnapshot(
            job_id=row["id"],
            source_id=row["source_id"],
            status=JobStatus(row["status"]),
            created_at=_parse_timestamp(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_timestamp(row["updated_at"]),  # type: ignore[arg-type]
            error=row["error"],
            attempt_sequence=int(row["sequence"]),
            started_at=_parse_timestamp(row["started_at"]),
            finished_at=_parse_timestamp(row["finished_at"]),
            output_paths=output_paths,
        )


@dataclass(frozen=True, slots=True)
class _WorkItem:
    job_id: str
    processor: JobProcessor


class SingleWorkerJobQueue:
    """A process-local queue that serializes all GPU-bound processors."""

    def __init__(self, repository: RecordTransRepository):
        self.repository = repository
        self._items: queue.Queue[_WorkItem | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._accepted: set[str] = set()
        self._started = False

    def start(self) -> int:
        with self._lock:
            if self._started:
                return 0
            interrupted = self.repository.mark_processing_interrupted()
            self._thread = threading.Thread(
                target=self._run,
                name="recordtrans-job-worker",
                daemon=True,
            )
            self._started = True
            self._thread.start()
            return interrupted

    def submit(self, job_id: str, processor: JobProcessor) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        if JobStatus(str(job["status"])) is not JobStatus.QUEUED:
            raise ValueError("only queued jobs can be submitted")
        with self._lock:
            if job_id in self._accepted:
                raise ValueError("job is already queued")
            self._accepted.add(job_id)
        self._items.put(_WorkItem(job_id, processor))

    def retry(
        self,
        job_id: str,
        processor: JobProcessor,
        source_available: Callable[[str], bool],
    ) -> int:
        if not source_available(job_id):
            raise FileNotFoundError("永久來源不存在，無法重試")
        sequence = self.repository.retry_job(job_id)
        self.submit(job_id, processor)
        return sequence

    def wait_until_idle(self) -> None:
        self._items.join()

    def close(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self._started:
                return
            thread = self._thread
            self._items.put(None)
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():
                raise TimeoutError("job worker did not stop")
        with self._lock:
            self._started = False
            self._thread = None

    def _run(self) -> None:
        while True:
            item = self._items.get()
            try:
                if item is None:
                    return
                self._process(item)
            finally:
                self._items.task_done()

    def _process(self, item: _WorkItem) -> None:
        try:
            self.repository.transition_job(item.job_id, JobStatus.PROCESSING)
            item.processor(item.job_id)
            self.repository.transition_job(item.job_id, JobStatus.COMPLETED)
        except Exception as exc:
            current = self.repository.get_job(item.job_id)
            if current and JobStatus(str(current["status"])) is JobStatus.PROCESSING:
                self.repository.transition_job(
                    item.job_id,
                    JobStatus.FAILED,
                    error=str(exc) or exc.__class__.__name__,
                )
        finally:
            with self._lock:
                self._accepted.discard(item.job_id)
