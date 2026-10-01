from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .contracts import SourceKind
from .storage import LocalMediaStorage, StoredSource


GIB = 1024 * 1024 * 1024
MAX_MEDIA_BYTES = GIB
MAX_MEDIA_SECONDS = 60 * 60
SUPPORTED_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm"})

_EXPECTED_FORMATS: dict[str, frozenset[str]] = {
    ".mp3": frozenset({"mp3"}),
    ".wav": frozenset({"wav"}),
    ".m4a": frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}),
    ".mp4": frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}),
    ".mov": frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}),
    ".webm": frozenset({"matroska", "webm"}),
}


class MediaValidationError(ValueError):
    """Raised when an uploaded file is not safe to accept for transcription."""


@dataclass(frozen=True, slots=True)
class MediaInfo:
    path: Path
    extension: str
    format_names: frozenset[str]
    size_bytes: int
    duration_seconds: float
    audio_codec: str


@dataclass(frozen=True, slots=True)
class AcceptedUpload:
    source: StoredSource
    media: MediaInfo


@dataclass(frozen=True, slots=True)
class UploadSubmission:
    accepted: AcceptedUpload
    source_id: str
    job_id: str


class UploadRepository(Protocol):
    def add_source(self, source: StoredSource) -> str: ...

    def create_job(self, source_id: str) -> str: ...


ProbeRunner = Callable[..., subprocess.CompletedProcess[str]]


class MediaProbe:
    def __init__(self, executable: str = "ffprobe", runner: ProbeRunner = subprocess.run):
        self.executable = executable
        self._runner = runner

    def inspect(self, path: str | Path) -> MediaInfo:
        media_path = Path(path)
        if not media_path.is_file():
            raise MediaValidationError(f"找不到上傳檔案：{media_path}")

        extension = media_path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise MediaValidationError("不支援此格式；請上傳 MP3、WAV、M4A、MP4、MOV 或 WebM")

        size_bytes = media_path.stat().st_size
        if size_bytes <= 0:
            raise MediaValidationError("媒體檔案是空的")
        if size_bytes > MAX_MEDIA_BYTES:
            raise MediaValidationError("媒體檔案超過 1 GiB 上限")

        command = [
            self.executable,
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration:stream=codec_type,codec_name,duration",
            "-of",
            "json",
            str(media_path),
        ]
        try:
            completed = self._runner(
                command, capture_output=True, text=True, check=False, timeout=30
            )
        except FileNotFoundError as exc:
            raise MediaValidationError("找不到 ffprobe；請先安裝 FFmpeg") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaValidationError("媒體探測逾時，檔案可能已損毀") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip()
            suffix = f"：{detail}" if detail else ""
            raise MediaValidationError(f"無法讀取媒體，檔案可能已損毀{suffix}")

        try:
            payload = json.loads(completed.stdout)
            raw_formats = payload["format"]["format_name"]
            format_names = frozenset(item.strip().lower() for item in raw_formats.split(","))
            streams = payload.get("streams", [])
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            raise MediaValidationError("ffprobe 回傳無效的媒體資訊") from exc

        if not format_names.intersection(_EXPECTED_FORMATS[extension]):
            detected = ", ".join(sorted(format_names)) or "未知"
            raise MediaValidationError(
                f"檔案內容與副檔名不符；副檔名為 {extension}，實際格式為 {detected}"
            )
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
        if not audio_streams:
            raise MediaValidationError("媒體沒有可用的音軌")

        duration = self._duration(payload.get("format", {}), audio_streams)
        if duration <= 0:
            raise MediaValidationError("媒體長度無效")
        if duration > MAX_MEDIA_SECONDS:
            raise MediaValidationError("媒體長度超過 60 分鐘上限")

        codec = str(audio_streams[0].get("codec_name") or "unknown")
        return MediaInfo(
            path=media_path,
            extension=extension,
            format_names=format_names,
            size_bytes=size_bytes,
            duration_seconds=duration,
            audio_codec=codec,
        )

    @staticmethod
    def _duration(format_info: dict[str, object], audio_streams: list[dict[str, object]]) -> float:
        candidates = [format_info.get("duration")]
        candidates.extend(stream.get("duration") for stream in audio_streams)
        for candidate in candidates:
            try:
                value = float(candidate)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value > 0:
                return value
        return 0.0


def accept_upload(
    path: str | Path,
    storage: LocalMediaStorage,
    probe: MediaProbe | None = None,
) -> AcceptedUpload:
    """Validate before copying, then durably save the accepted upload."""

    media = (probe or MediaProbe()).inspect(path)
    stored = storage.store_path(media.path, SourceKind.UPLOAD)
    return AcceptedUpload(source=stored, media=media)


def submit_upload(
    path: str | Path,
    storage: LocalMediaStorage,
    repository: UploadRepository,
    probe: MediaProbe | None = None,
) -> UploadSubmission:
    accepted = accept_upload(path, storage, probe)
    source_id = repository.add_source(accepted.source)
    job_id = repository.create_job(source_id)
    return UploadSubmission(accepted=accepted, source_id=source_id, job_id=job_id)
