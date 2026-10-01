"""Run one real faster-whisper inference and emit reproducible diagnostics."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: smoke_transcribe.py AUDIO_PATH")
    audio = Path(sys.argv[1])
    if not audio.is_file():
        raise SystemExit(f"missing audio: {audio}")
    model_name = os.environ.get("RECORDTRANS_SMOKE_MODEL", "tiny")
    model_dir = os.environ.get("RECORDTRANS_MODEL_DIR", "/Whisper-WebUI/models")
    started = time.perf_counter()
    model = WhisperModel(
        model_name,
        device="cuda",
        compute_type="float16",
        download_root=model_dir,
    )
    loaded_at = time.perf_counter()
    segments, info = model.transcribe(str(audio), language="en", vad_filter=True)
    text = "".join(segment.text for segment in segments).strip()
    finished = time.perf_counter()
    report = {
        "model": model_name,
        "device": "cuda",
        "compute_type": "float16",
        "detected_language": info.language,
        "text": text,
        "text_is_empty": not bool(text),
        "model_load_seconds": round(loaded_at - started, 3),
        "inference_seconds": round(finished - loaded_at, 3),
        "total_seconds": round(finished - started, 3),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
