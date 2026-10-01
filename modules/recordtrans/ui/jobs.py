from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..contracts import JobStatus
from ..jobs import JobSnapshot


STATUS_LABELS = {
    JobStatus.QUEUED: "等待中",
    JobStatus.PROCESSING: "處理中",
    JobStatus.COMPLETED: "已完成",
    JobStatus.FAILED: "失敗",
    JobStatus.INTERRUPTED: "已中斷",
}


def present_job(
    snapshot: JobSnapshot, now: datetime | None = None
) -> dict[str, object]:
    """Return a refresh-safe UI model without inventing progress percentages."""

    return {
        "job_id": snapshot.job_id,
        "status": snapshot.status.value,
        "status_label": STATUS_LABELS[snapshot.status],
        "attempt": snapshot.attempt_sequence,
        "elapsed_seconds": round(snapshot.elapsed_seconds(now or datetime.now(UTC)), 3),
        "error": snapshot.error,
        "downloads": downloadable_outputs(snapshot),
    }


def downloadable_outputs(snapshot: JobSnapshot) -> dict[str, Path]:
    if not snapshot.downloads_available or snapshot.output_paths is None:
        return {}
    return {name: Path(path) for name, path in snapshot.output_paths.items()}
