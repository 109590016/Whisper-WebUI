from __future__ import annotations

import argparse
import os

import gradio as gr

from modules.recordtrans.recording import RecordingController
from modules.recordtrans.service import RecordTransService
from modules.recordtrans.ui.jobs import STATUS_LABELS
from modules.recordtrans.ui.recording import build_recording_panel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RecordTrans local transcription MVP")
    parser.add_argument("--server_name", default="0.0.0.0")
    parser.add_argument("--server_port", type=int, default=7860)
    parser.add_argument("--output_dir", default=None)
    return parser.parse_args()


def _job_view(service: RecordTransService, job_id: str | None):
    if not job_id:
        return "尚未選擇任務。", "", []
    view = service.present(job_id)
    if view is None:
        return "找不到任務。", "", []
    label = STATUS_LABELS[view["status"]]  # type: ignore[index]
    elapsed = float(view["elapsed_seconds"])
    message = f"{label}｜已經過 {elapsed:.3f} 秒"
    if view["error"]:
        message += f"｜{view['error']}"
    return message, str(view["text"]), view["downloads"]


def build_app(service: RecordTransService) -> gr.Blocks:
    with gr.Blocks(title="RecordTrans", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            "# RecordTrans\n"
            "本機錄音與影音逐字稿。來源、任務與結果只保存在你設定的資料夾。"
        )
        if service.interrupted_on_start:
            gr.Markdown(
                f"上次關閉時有 {service.interrupted_on_start} 件任務處理中，已標記為已中斷。"
            )

        with gr.Tabs():
            with gr.Tab("上傳音檔或影片"):
                upload = gr.File(
                    label="選擇 MP3、WAV、M4A、MP4、MOV 或 WebM",
                    type="filepath",
                    file_types=[".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm"],
                )
                upload_button = gr.Button("保存並開始轉錄", variant="primary")
                upload_status = gr.Textbox(label="上傳狀態", interactive=False)
                upload_job_id = gr.Textbox(label="任務 ID", interactive=False)

                def submit_file(path: str | None) -> tuple[str, str]:
                    if not path:
                        return "請先選擇檔案。", ""
                    try:
                        submitted = service.submit_upload(path)
                        return "來源已永久保存，任務已加入等待佇列。", submitted.job_id
                    except Exception as exc:
                        return f"無法提交：{exc}", ""

                upload_button.click(
                    submit_file, inputs=[upload], outputs=[upload_status, upload_job_id]
                )

            with gr.Tab("麥克風錄音"):
                build_recording_panel(
                    RecordingController(service.storage, service.repository, service)
                )

            with gr.Tab("任務與結果"):
                job_id = gr.Textbox(label="任務 ID")
                with gr.Row():
                    refresh = gr.Button("重新整理狀態", variant="primary")
                    retry = gr.Button("重試失敗／中斷任務")
                job_status = gr.Textbox(label="任務狀態", interactive=False)
                transcript = gr.Textbox(label="繁體中文逐字稿", lines=14, interactive=False)
                downloads = gr.File(label="下載 TXT／SRT／VTT", file_count="multiple")

                refresh.click(
                    lambda value: _job_view(service, value),
                    inputs=[job_id], outputs=[job_status, transcript, downloads]
                )

                def retry_job(value: str | None) -> tuple[str, str, list[str]]:
                    if not value:
                        return "請輸入任務 ID。", "", []
                    try:
                        attempt = service.retry(value)
                        return f"已建立第 {attempt} 次嘗試並加入佇列。", "", []
                    except Exception as exc:
                        return f"無法重試：{exc}", "", []

                retry.click(
                    retry_job, inputs=[job_id], outputs=[job_status, transcript, downloads]
                )

        gr.Markdown("逐字稿為自動辨識結果，重要內容請回聽原始錄音確認。")
    return app


def main() -> None:
    args = parse_args()
    data_dir = os.environ.get("DATA_DIR", args.output_dir or "./data")
    service = RecordTransService.create(
        data_dir,
        os.environ.get("RECORDTRANS_MODEL_DIR", "/Whisper-WebUI/models"),
        model_size=os.environ.get("RECORDTRANS_MODEL", "small"),
        device=os.environ.get("RECORDTRANS_DEVICE", "cuda"),
        compute_type=os.environ.get("RECORDTRANS_COMPUTE_TYPE", "float16"),
    )
    build_app(service).queue(default_concurrency_limit=4).launch(
        server_name=args.server_name, server_port=args.server_port, show_error=True
    )


if __name__ == "__main__":
    main()
