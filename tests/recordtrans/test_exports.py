from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.recordtrans.contracts import JobStatus, Segment
from modules.recordtrans.exports import (
    ExportError,
    downloadable_outputs,
    export_transcript,
)


class ExportTests(unittest.TestCase):
    def test_exports_utf8_txt_srt_and_vtt_from_same_segments(self):
        segments = (
            Segment(0, 1.234, "第一段 OpenAI 2026"),
            Segment(1.234, 65.5, "第二段文字"),
        )
        with tempfile.TemporaryDirectory() as directory:
            outputs = export_transcript(segments, directory, "job-1")
            txt = outputs.txt.read_text(encoding="utf-8")
            srt = outputs.srt.read_text(encoding="utf-8")
            vtt = outputs.vtt.read_text(encoding="utf-8")

        for text in ("第一段 OpenAI 2026", "第二段文字"):
            self.assertIn(text, txt)
            self.assertIn(text, srt)
            self.assertIn(text, vtt)
        self.assertIn("00:00:00,000 --> 00:00:01,234", srt)
        self.assertIn("00:00:01.234 --> 00:01:05.500", vtt)
        self.assertTrue(vtt.startswith("WEBVTT\n"))

    def test_rejects_overlapping_or_out_of_order_segments(self):
        segments = (Segment(0, 2, "one"), Segment(1, 3, "two"))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ExportError, "不得重疊"):
                export_transcript(segments, directory, "job")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_rejects_zero_duration_subtitle(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ExportError, "晚於開始時間"):
                export_transcript((Segment(1, 1, "instant"),), directory, "job")

    def test_only_completed_result_is_downloadable(self):
        segments = (Segment(0, 1, "done"),)
        with tempfile.TemporaryDirectory() as directory:
            outputs = export_transcript(segments, directory, "job")
            for status in (
                JobStatus.QUEUED,
                JobStatus.PROCESSING,
                JobStatus.FAILED,
                JobStatus.INTERRUPTED,
            ):
                self.assertIsNone(downloadable_outputs(status, outputs))
            self.assertIs(downloadable_outputs(JobStatus.COMPLETED, outputs), outputs)


if __name__ == "__main__":
    unittest.main()
