from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

from modules.recordtrans.contracts import Segment
from modules.recordtrans.transcription import (
    FasterWhisperAdapter,
    TranscriptionError,
    convert_segments_to_traditional,
)


class FakeModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append((path, kwargs))
        segments = iter(
            [
                SimpleNamespace(start=0, end=1.2, text=" 简体中文 OpenAI 2026"),
                SimpleNamespace(start=1.2, end=2.5, text=" 第二段"),
            ]
        )
        info = SimpleNamespace(language="zh", language_probability=0.99, duration=2.5)
        return segments, info


class TranscriptionTests(unittest.TestCase):
    def test_faster_whisper_adapter_normalizes_lazy_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "saved.wav"
            with wave.open(str(source), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16_000)
                stream.writeframes(b"\x00\x00" * 1_600)
            model = FakeModel()
            factory_calls = []

            def factory(model_size, **kwargs):
                factory_calls.append((model_size, kwargs))
                return model

            adapter = FasterWhisperAdapter(model_factory=factory)
            result = adapter.transcribe(source)

        self.assertEqual(factory_calls[0][0], "small")
        self.assertEqual(factory_calls[0][1]["device"], "cuda")
        self.assertEqual(model.calls[0][1], {"language": "zh", "vad_filter": True})
        self.assertEqual(result.detected_language, "zh")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0], Segment(0.0, 1.2, " 简体中文 OpenAI 2026"))
        self.assertEqual(result.metadata["compute_type"], "float16")

    def test_adapter_requires_permanent_source_to_exist(self):
        adapter = FasterWhisperAdapter(model_factory=lambda *args, **kwargs: FakeModel())
        with self.assertRaisesRegex(TranscriptionError, "找不到永久來源"):
            adapter.transcribe("missing.wav")

    def test_deterministic_conversion_preserves_english_numbers_and_timing(self):
        original = (
            Segment(0, 1, "简体中文 OpenAI 2026"),
            Segment(1, 2, "软件和数据 API v2"),
        )
        mapping = str.maketrans({"简": "簡", "体": "體", "软": "軟", "数": "數", "据": "據"})
        converted = convert_segments_to_traditional(
            original, converter=lambda text: text.translate(mapping)
        )

        self.assertEqual(converted[0].text, "簡體中文 OpenAI 2026")
        self.assertIn("API v2", converted[1].text)
        self.assertEqual(
            [(item.start, item.end) for item in converted], [(0, 1), (1, 2)]
        )
        self.assertEqual(original[0].text, "简体中文 OpenAI 2026")


if __name__ == "__main__":
    unittest.main()
