from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from .contracts import Segment


class TranscriptionError(RuntimeError):
    """Raised when local speech recognition cannot produce a valid result."""


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    segments: tuple[Segment, ...]
    detected_language: str | None
    metadata: dict[str, object]

    @property
    def text(self) -> str:
        return "".join(segment.text for segment in self.segments).strip()


class TranscriptionAdapter(Protocol):
    def transcribe(self, source: str | Path) -> TranscriptionResult: ...


ModelFactory = Callable[..., Any]


class FasterWhisperAdapter:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cuda",
        compute_type: str = "float16",
        download_root: str | Path | None = None,
        language: str | None = "zh",
        model_factory: ModelFactory | None = None,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = str(download_root) if download_root is not None else None
        self.language = language
        self._model_factory = model_factory
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        factory = self._model_factory
        if factory is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise TranscriptionError("尚未安裝 faster-whisper") from exc
            factory = WhisperModel
        kwargs: dict[str, object] = {
            "device": self.device,
            "compute_type": self.compute_type,
        }
        if self.download_root is not None:
            kwargs["download_root"] = self.download_root
        try:
            self._model = factory(self.model_size, **kwargs)
        except Exception as exc:
            raise TranscriptionError(f"無法載入本機 Whisper 模型：{exc}") from exc
        return self._model

    def transcribe(self, source: str | Path) -> TranscriptionResult:
        source_path = Path(source)
        if not source_path.is_file():
            raise TranscriptionError(f"找不到永久來源：{source_path}")
        model = self._load_model()
        try:
            raw_segments, info = model.transcribe(
                str(source_path), language=self.language, vad_filter=True
            )
            segments = tuple(
                Segment(float(item.start), float(item.end), str(item.text))
                for item in raw_segments
                if str(item.text).strip()
            )
        except Exception as exc:
            raise TranscriptionError(f"本機轉錄失敗：{exc}") from exc
        if not segments:
            raise TranscriptionError("轉錄未產生任何文字")

        detected_language = getattr(info, "language", None)
        metadata: dict[str, object] = {
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "language_probability": getattr(info, "language_probability", None),
            "duration_seconds": getattr(info, "duration", None),
        }
        return TranscriptionResult(segments, detected_language, metadata)


Converter = Callable[[str], str]


def opencc_simplified_to_traditional() -> Converter:
    try:
        from opencc import OpenCC
    except ImportError as exc:
        raise TranscriptionError("尚未安裝 OpenCC，無法產生繁體中文結果") from exc
    converter = OpenCC("s2twp")
    return converter.convert


def convert_segments_to_traditional(
    segments: Sequence[Segment], converter: Converter | None = None
) -> tuple[Segment, ...]:
    convert = converter or opencc_simplified_to_traditional()
    return tuple(Segment(item.start, item.end, convert(item.text)) for item in segments)
