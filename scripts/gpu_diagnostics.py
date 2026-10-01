"""Fail-fast diagnostics for the RecordTrans GPU runtime."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version


def package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def main() -> int:
    report: dict[str, object] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: package_version(name)
            for name in ("ctranslate2", "faster-whisper", "torch", "torchaudio")
        },
    }
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
        )
        report["nvidia_smi"] = result.stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        report["nvidia_smi_error"] = str(exc)

    try:
        import ctranslate2

        report["cuda_device_count"] = ctranslate2.get_cuda_device_count()
    except Exception as exc:  # diagnostic output must preserve runtime error details
        report["ctranslate2_error"] = repr(exc)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("cuda_device_count", 0) else 1


if __name__ == "__main__":
    sys.exit(main())

