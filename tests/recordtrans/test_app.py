from __future__ import annotations

import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace


@unittest.skipIf(find_spec("gradio") is None, "Gradio is not installed")
class AppLaunchTests(unittest.TestCase):
    def test_gradio_exposes_only_recordings_and_outputs(self) -> None:
        from app import _gradio_allowed_paths

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = SimpleNamespace(
                recordings=root / "recordings",
                outputs=root / "outputs",
                state=root / "state",
                uploads=root / "uploads",
            )
            service = SimpleNamespace(storage=SimpleNamespace(paths=paths))

            allowed = _gradio_allowed_paths(service)  # type: ignore[arg-type]

            self.assertEqual(
                allowed,
                [str(paths.recordings.resolve()), str(paths.outputs.resolve())],
            )
            self.assertNotIn(str(paths.state.resolve()), allowed)
            self.assertNotIn(str(paths.uploads.resolve()), allowed)


if __name__ == "__main__":
    unittest.main()
