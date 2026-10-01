from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from .contracts import SourceKind


class StorageError(RuntimeError):
    """Raised when a media source cannot be durably stored."""


@dataclass(frozen=True, slots=True)
class DataPaths:
    root: Path
    recordings: Path
    uploads: Path
    outputs: Path
    state: Path
    temp: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "DataPaths":
        resolved = Path(root).expanduser().resolve()
        return cls(
            root=resolved,
            recordings=resolved / "recordings",
            uploads=resolved / "uploads",
            outputs=resolved / "outputs",
            state=resolved / "state",
            temp=resolved / "temp",
        )

    def ensure_writable(self) -> None:
        for directory in (
            self.root,
            self.recordings,
            self.uploads,
            self.outputs,
            self.state,
            self.temp,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            try:
                with tempfile.NamedTemporaryFile(dir=directory, delete=True):
                    pass
            except OSError as exc:
                raise StorageError(f"資料目錄不可寫入：{directory}") from exc


@dataclass(frozen=True, slots=True)
class StoredSource:
    identifier: str
    kind: SourceKind
    original_name: str
    relative_path: str
    size_bytes: int


class LocalMediaStorage:
    def __init__(self, paths: DataPaths):
        self.paths = paths
        self.paths.ensure_writable()

    def store_path(self, source: str | Path, kind: SourceKind) -> StoredSource:
        source_path = Path(source)
        if not source_path.is_file():
            raise StorageError(f"找不到來源檔案：{source_path}")
        with source_path.open("rb") as stream:
            return self.store_stream(stream, source_path.name, kind)

    def store_stream(
        self, stream: BinaryIO, original_name: str, kind: SourceKind
    ) -> StoredSource:
        identifier = str(uuid4())
        safe_name = Path(original_name).name or "media.bin"
        suffix = Path(safe_name).suffix.lower()
        directory = self.paths.recordings if kind is SourceKind.RECORDING else self.paths.uploads
        final_path = directory / f"{identifier}{suffix}"
        temporary_path = self.paths.temp / f"{identifier}.partial"

        try:
            with temporary_path.open("xb") as target:
                shutil.copyfileobj(stream, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary_path, final_path)
        except (OSError, ValueError) as exc:
            temporary_path.unlink(missing_ok=True)
            raise StorageError(f"無法完整保存來源：{safe_name}") from exc

        relative_path = final_path.relative_to(self.paths.root).as_posix()
        return StoredSource(
            identifier=identifier,
            kind=kind,
            original_name=safe_name,
            relative_path=relative_path,
            size_bytes=final_path.stat().st_size,
        )

    def resolve(self, relative_path: str) -> Path:
        candidate = (self.paths.root / relative_path).resolve()
        try:
            candidate.relative_to(self.paths.root)
        except ValueError as exc:
            raise StorageError("來源路徑超出資料目錄") from exc
        return candidate

