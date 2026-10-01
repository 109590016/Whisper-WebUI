from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from .contracts import JobStatus, Segment


class ExportError(RuntimeError):
    """Raised when a transcript cannot be safely exported."""


@dataclass(frozen=True, slots=True)
class ExportedTranscript:
    txt: Path
    srt: Path
    vtt: Path

    def as_dict(self) -> dict[str, str]:
        return {"txt": str(self.txt), "srt": str(self.srt), "vtt": str(self.vtt)}


def downloadable_outputs(
    status: JobStatus, outputs: ExportedTranscript | None
) -> ExportedTranscript | None:
    return outputs if status is JobStatus.COMPLETED else None


def export_transcript(
    segments: Sequence[Segment], output_directory: str | Path, stem: str
) -> ExportedTranscript:
    normalized = _validate_segments(segments)
    safe_stem = Path(stem).name.strip() or str(uuid4())
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    txt = output_dir / f"{safe_stem}.txt"
    srt = output_dir / f"{safe_stem}.srt"
    vtt = output_dir / f"{safe_stem}.vtt"
    text_lines = [item.text.strip() for item in normalized]
    srt_blocks = [
        f"{index}\n{_timestamp(item.start, srt=True)} --> {_timestamp(item.end, srt=True)}\n{item.text.strip()}"
        for index, item in enumerate(normalized, start=1)
    ]
    vtt_blocks = [
        f"{_timestamp(item.start, srt=False)} --> {_timestamp(item.end, srt=False)}\n{item.text.strip()}"
        for item in normalized
    ]
    _atomic_write_many(
        {
            txt: "\n".join(text_lines) + "\n",
            srt: "\n\n".join(srt_blocks) + "\n",
            vtt: "WEBVTT\n\n" + "\n\n".join(vtt_blocks) + "\n",
        }
    )
    return ExportedTranscript(txt=txt, srt=srt, vtt=vtt)


def _validate_segments(segments: Sequence[Segment]) -> tuple[Segment, ...]:
    if not segments:
        raise ExportError("沒有可輸出的逐字稿內容")
    result = tuple(segments)
    previous_start = -1.0
    previous_end = -1.0
    for item in result:
        if item.end <= item.start:
            raise ExportError("字幕結束時間必須晚於開始時間")
        if item.start < previous_start or item.start < previous_end:
            raise ExportError("字幕時間必須依序遞增且不得重疊")
        previous_start = item.start
        previous_end = item.end
    return result


def _timestamp(seconds: float, *, srt: bool) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}{separator}{millis:03d}"


def _atomic_write_many(files: dict[Path, str]) -> None:
    temporary_files: dict[Path, Path] = {}
    try:
        for path, content in files.items():
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.partial")
            temporary_files[path] = temporary
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        for path, temporary in temporary_files.items():
            os.replace(temporary, path)
    except OSError as exc:
        for temporary in temporary_files.values():
            temporary.unlink(missing_ok=True)
        raise ExportError("無法完整輸出逐字稿") from exc
