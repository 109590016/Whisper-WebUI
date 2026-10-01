from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .contracts import JobStatus
from .exports import export_transcript
from .jobs import JobStoreView, SingleWorkerJobQueue
from .media import MediaProbe, UploadSubmission, submit_upload
from .repository import RecordTransRepository
from .storage import DataPaths, LocalMediaStorage
from .transcription import FasterWhisperAdapter, TranscriptionAdapter, convert_segments_to_traditional


class RecordTransService:
    """Application service joining durable sources, one worker, and exports."""

    def __init__(self, paths: DataPaths, repository: RecordTransRepository,
                 storage: LocalMediaStorage, adapter: TranscriptionAdapter,
                 probe: MediaProbe | None = None,
                 converter: Callable[[str], str] | None = None) -> None:
        self.paths = paths
        self.repository = repository
        self.storage = storage
        self.adapter = adapter
        self.probe = probe or MediaProbe()
        self.converter = converter
        self.queue = SingleWorkerJobQueue(repository)
        self.interrupted_on_start = self.queue.start()
        self.jobs = JobStoreView(repository.database_path)

    @classmethod
    def create(cls, data_dir: str | Path, model_dir: str | Path, *,
               model_size: str = "small", device: str = "cuda",
               compute_type: str = "float16") -> "RecordTransService":
        paths = DataPaths.from_root(data_dir)
        storage = LocalMediaStorage(paths)
        repository = RecordTransRepository(paths.state / "recordtrans.sqlite3")
        adapter = FasterWhisperAdapter(model_size=model_size, device=device,
                                       compute_type=compute_type, download_root=model_dir)
        return cls(paths, repository, storage, adapter)

    def submit(self, source_id: str) -> str:
        if self.repository.get_source(source_id) is None:
            raise KeyError(source_id)
        job_id = self.repository.create_job(source_id)
        self.queue.submit(job_id, self.process)
        return job_id

    def submit_upload(self, path: str | Path) -> UploadSubmission:
        submission = submit_upload(path, self.storage, self.repository, self.probe)
        self.queue.submit(submission.job_id, self.process)
        return submission

    def process(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        source = self.repository.get_source(str(job["source_id"]))
        if source is None:
            raise FileNotFoundError("找不到任務的永久來源")
        source_path = self.storage.resolve(str(source["relative_path"]))
        if not source_path.is_file():
            raise FileNotFoundError("永久來源已不存在")
        raw = self.adapter.transcribe(source_path)
        traditional = convert_segments_to_traditional(raw.segments, self.converter)
        outputs = export_transcript(traditional, self.paths.outputs, job_id)
        self.repository.save_result(job_id, traditional, outputs.as_dict(), raw.detected_language)

    def retry(self, job_id: str) -> int:
        def source_available(candidate_job_id: str) -> bool:
            job = self.repository.get_job(candidate_job_id)
            if job is None:
                return False
            source = self.repository.get_source(str(job["source_id"]))
            return bool(source and self.storage.resolve(str(source["relative_path"])).is_file())
        return self.queue.retry(job_id, self.process, source_available)

    def present(self, job_id: str) -> dict[str, object] | None:
        snapshot = self.jobs.get(job_id)
        if snapshot is None:
            return None
        result = self.repository.get_result(job_id)
        text = ""
        if result is not None:
            segments = json.loads(str(result["segments_json"]))
            text = "".join(str(item["text"]) for item in segments).strip()
        return {
            "job_id": snapshot.job_id,
            "status": snapshot.status,
            "elapsed_seconds": snapshot.elapsed_seconds(),
            "error": snapshot.error,
            "text": text,
            "downloads": list((snapshot.output_paths or {}).values())
            if snapshot.status is JobStatus.COMPLETED else [],
        }
