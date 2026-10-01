from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .contracts import SourceKind
from .storage import LocalMediaStorage, StorageError


class RecordingError(RuntimeError):
    """Raised when a recording cannot advance to the requested step."""


class SourceRepository(Protocol):
    def add_source(self, source: object) -> str: ...


class TranscriptionSubmitter(Protocol):
    def submit(self, source_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class SavedRecording:
    source_id: str
    playback_path: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class RecordingView:
    message: str
    temporary_path: str | None = None
    saved: SavedRecording | None = None
    job_id: str | None = None

    @property
    def can_save(self) -> bool:
        return self.temporary_path is not None

    @property
    def can_submit(self) -> bool:
        return self.saved is not None


class RecordingController:
    """Coordinates capture, durable storage, and transcription submission."""

    def __init__(
        self,
        storage: LocalMediaStorage,
        repository: SourceRepository,
        submitter: TranscriptionSubmitter,
    ) -> None:
        self.storage = storage
        self.repository = repository
        self.submitter = submitter

    def capture_ready(self, temporary_path: str | Path | None) -> RecordingView:
        if not temporary_path:
            return self.capture_unavailable("未收到錄音，請檢查麥克風權限或裝置。")

        candidate = Path(temporary_path)
        try:
            is_valid = candidate.is_file() and candidate.stat().st_size > 0
        except OSError:
            is_valid = False
        if not is_valid:
            return self.capture_unavailable("錄音內容不可用，請重新錄製。")

        return RecordingView(
            message="錄音完成，可先回聽；確認後請永久保存。",
            temporary_path=str(candidate),
        )

    def capture_unavailable(self, reason: str) -> RecordingView:
        message = reason.strip() or "麥克風不可用，請檢查瀏覽器權限或錄音裝置。"
        return RecordingView(message=message)

    def save(self, view: RecordingView) -> RecordingView:
        if not view.temporary_path:
            raise RecordingError("尚無可保存的錄音。")

        try:
            stored = self.storage.store_path(
                view.temporary_path,
                SourceKind.RECORDING,
            )
            try:
                source_id = self.repository.add_source(stored)
            except Exception:
                self.storage.resolve(stored.relative_path).unlink(missing_ok=True)
                raise
        except (OSError, StorageError, ValueError) as exc:
            raise RecordingError(f"錄音保存失敗：{exc}") from exc
        except Exception as exc:
            raise RecordingError("錄音保存失敗，來源尚未建立。") from exc

        permanent_path = self.storage.resolve(stored.relative_path)
        saved = SavedRecording(
            source_id=source_id,
            playback_path=str(permanent_path),
            relative_path=stored.relative_path,
        )
        return RecordingView(
            message="錄音已永久保存；現在可以提交轉錄。",
            temporary_path=view.temporary_path,
            saved=saved,
        )

    def submit(self, view: RecordingView) -> RecordingView:
        if view.saved is None:
            raise RecordingError("錄音尚未永久保存，無法提交轉錄。")

        job_id = self.submitter.submit(view.saved.source_id)
        return RecordingView(
            message=f"已建立轉錄任務：{job_id}",
            temporary_path=view.temporary_path,
            saved=view.saved,
            job_id=job_id,
        )
