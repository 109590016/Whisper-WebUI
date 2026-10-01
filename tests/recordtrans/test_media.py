from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from modules.recordtrans.media import (
    GIB,
    MediaProbe,
    MediaValidationError,
    accept_upload,
    submit_upload,
)
from modules.recordtrans.storage import DataPaths, LocalMediaStorage


def probe_result(
    *, format_name: str = "wav", duration: str = "2.5", streams=None, returncode: int = 0
):
    payload = {
        "format": {"format_name": format_name, "duration": duration},
        "streams": streams
        if streams is not None
        else [{"codec_type": "audio", "codec_name": "pcm_s16le"}],
    }
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=json.dumps(payload), stderr="bad media"
    )


class MediaProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def media(self, name: str = "訪談.wav", content: bytes = b"RIFFpayload") -> Path:
        path = self.root / name
        path.write_bytes(content)
        return path

    def test_accepts_supported_media_and_permanently_stores_same_named_files(self):
        source = self.media()
        probe = MediaProbe(runner=lambda *args, **kwargs: probe_result())
        storage = LocalMediaStorage(DataPaths.from_root(self.root / "資料 空白"))

        first = accept_upload(source, storage, probe)
        second = accept_upload(source, storage, probe)

        self.assertNotEqual(first.source.identifier, second.source.identifier)
        self.assertNotEqual(first.source.relative_path, second.source.relative_path)
        self.assertEqual(
            storage.resolve(first.source.relative_path).read_bytes(), b"RIFFpayload"
        )
        self.assertEqual(first.media.duration_seconds, 2.5)

    def test_submission_registers_saved_source_before_creating_job(self):
        source = self.media()
        probe = MediaProbe(runner=lambda *args, **kwargs: probe_result())
        storage = LocalMediaStorage(DataPaths.from_root(self.root / "data"))
        events = []

        class Repository:
            def add_source(self, stored):
                events.append(("source", stored.identifier))
                return stored.identifier

            def create_job(self, source_id):
                events.append(("job", source_id))
                return "job-1"

        submission = submit_upload(source, storage, Repository(), probe)

        self.assertEqual(submission.job_id, "job-1")
        self.assertEqual(events[0][0], "source")
        self.assertEqual(events[1], ("job", submission.source_id))

    def test_accepts_each_declared_container_when_content_matches(self):
        cases = {
            "sample.mp3": "mp3",
            "sample.wav": "wav",
            "sample.m4a": "mov,mp4,m4a,3gp,3g2,mj2",
            "sample.mp4": "mov,mp4,m4a,3gp,3g2,mj2",
            "sample.mov": "mov,mp4,m4a,3gp,3g2,mj2",
            "sample.webm": "matroska,webm",
        }
        for filename, format_name in cases.items():
            with self.subTest(filename=filename):
                source = self.media(filename)
                probe = MediaProbe(
                    runner=lambda *args, _format=format_name, **kwargs: probe_result(
                        format_name=_format
                    )
                )
                self.assertEqual(probe.inspect(source).extension, Path(filename).suffix)

    def test_rejects_corrupt_media(self):
        source = self.media()
        probe = MediaProbe(
            runner=lambda *args, **kwargs: probe_result(returncode=1)
        )
        with self.assertRaisesRegex(MediaValidationError, "損毀"):
            probe.inspect(source)

    def test_rejects_extension_content_mismatch(self):
        source = self.media("fake.mp3")
        probe = MediaProbe(runner=lambda *args, **kwargs: probe_result(format_name="wav"))
        with self.assertRaisesRegex(MediaValidationError, "內容與副檔名不符"):
            probe.inspect(source)

    def test_rejects_video_without_audio_track(self):
        source = self.media("silent.mp4")
        probe = MediaProbe(
            runner=lambda *args, **kwargs: probe_result(
                format_name="mov,mp4,m4a,3gp,3g2,mj2",
                streams=[{"codec_type": "video", "codec_name": "h264"}],
            )
        )
        with self.assertRaisesRegex(MediaValidationError, "沒有可用的音軌"):
            probe.inspect(source)

    def test_rejects_duration_over_sixty_minutes(self):
        source = self.media("long.webm")
        probe = MediaProbe(
            runner=lambda *args, **kwargs: probe_result(
                format_name="matroska,webm", duration="3600.001"
            )
        )
        with self.assertRaisesRegex(MediaValidationError, "超過 60 分鐘"):
            probe.inspect(source)

    def test_rejects_non_finite_duration(self):
        source = self.media()
        probe = MediaProbe(
            runner=lambda *args, **kwargs: probe_result(duration="NaN")
        )
        with self.assertRaisesRegex(MediaValidationError, "長度無效"):
            probe.inspect(source)

    def test_rejects_size_over_one_gib_before_invoking_probe(self):
        source = self.root / "huge.mov"
        with source.open("wb") as stream:
            stream.truncate(GIB + 1)
        invoked = False

        def runner(*args, **kwargs):
            nonlocal invoked
            invoked = True
            return probe_result()

        with self.assertRaisesRegex(MediaValidationError, "超過 1 GiB"):
            MediaProbe(runner=runner).inspect(source)
        self.assertFalse(invoked)


if __name__ == "__main__":
    unittest.main()
