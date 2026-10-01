from __future__ import annotations

import argparse
import os

import gradio as gr

from modules.recordtrans.recording import RecordingController
from modules.recordtrans.service import RecordTransService
from modules.recordtrans.ui.jobs import STATUS_LABELS
from modules.recordtrans.ui.recording import build_recording_panel
from modules.recordtrans.ui.theme import APP_CSS, recordtrans_theme


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
    def submit_file(path: str | None) -> tuple[str, str]:
        if not path:
            return "請先選擇檔案。", ""
        try:
            submitted = service.submit_upload(path)
            return "來源已永久保存，任務已加入等待佇列。", submitted.job_id
        except Exception as exc:
            return f"無法提交：{exc}", ""

    def retry_job(value: str | None) -> tuple[str, str, list[str]]:
        if not value:
            return "請輸入任務 ID。", "", []
        try:
            attempt = service.retry(value)
            return f"已建立第 {attempt} 次嘗試並加入佇列。", "", []
        except Exception as exc:
            return f"無法重試：{exc}", "", []

    with gr.Blocks(
        title="RecordTrans｜本機影音逐字稿",
        theme=recordtrans_theme(),
        css=APP_CSS,
    ) as app:
        with gr.Column(elem_id="recordtrans-shell"):
            gr.HTML(
                """
                <header id="recordtrans-hero">
                  <span class="rt-eyebrow">LOCAL AI TRANSCRIPTION</span>
                  <h1 class="rt-hero-title">RecordTrans</h1>
                  <p class="rt-hero-copy">
                    錄下訪談，或上傳既有音訊與影片，在本機完成繁體中文逐字稿。
                    來源、任務與結果只會保存在你設定的資料夾。
                  </p>
                </header>
                """
            )
            if service.interrupted_on_start:
                gr.HTML(
                    '<div id="recordtrans-notice"><strong>偵測到未完成任務</strong><br>'
                    f"上次關閉時有 {service.interrupted_on_start} 件任務處理中，"
                    "已標記為已中斷，可在「任務與結果」中重試。</div>"
                )

            with gr.Group(elem_id="recordtrans-workspace"):
                with gr.Tabs(elem_id="recordtrans-tabs"):
                    with gr.Tab("上傳媒體"):
                        with gr.Column(elem_classes=["rt-panel"]):
                            gr.HTML(
                                """
                                <div class="rt-section-heading">
                                  <p class="rt-section-kicker">UPLOAD</p>
                                  <h2 class="rt-section-title">從檔案建立逐字稿</h2>
                                  <p class="rt-section-copy">支援 MP3、WAV、M4A、MP4、MOV 與 WebM；單檔上限 1 GiB、60 分鐘。</p>
                                </div>
                                """
                            )
                            upload = gr.File(
                                label="選擇音檔或影片",
                                type="filepath",
                                file_types=[".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm"],
                                elem_classes=["rt-upload"],
                            )
                            upload_button = gr.Button(
                                "保存並開始轉錄", variant="primary"
                            )
                            upload_status = gr.Textbox(
                                label="上傳狀態",
                                interactive=False,
                                elem_classes=["rt-status"],
                            )
                            upload_job_id = gr.Textbox(
                                label="任務 ID", interactive=False
                            )
                            upload_button.click(
                                submit_file,
                                inputs=[upload],
                                outputs=[upload_status, upload_job_id],
                            )

                    with gr.Tab("麥克風錄音"):
                        build_recording_panel(
                            RecordingController(
                                service.storage, service.repository, service
                            )
                        )

                    with gr.Tab("任務與結果"):
                        with gr.Column(elem_classes=["rt-panel"]):
                            gr.HTML(
                                """
                                <div class="rt-section-heading">
                                  <p class="rt-section-kicker">RESULTS</p>
                                  <h2 class="rt-section-title">查看任務與下載結果</h2>
                                  <p class="rt-section-copy">貼上建立任務後取得的 ID，即可重新整理狀態、閱讀逐字稿或下載字幕。</p>
                                </div>
                                """
                            )
                            job_id = gr.Textbox(
                                label="任務 ID", placeholder="例如：c61e…"
                            )
                            with gr.Row():
                                refresh = gr.Button(
                                    "重新整理狀態", variant="primary"
                                )
                                retry = gr.Button("重試失敗／中斷任務")
                            job_status = gr.Textbox(
                                label="任務狀態",
                                interactive=False,
                                elem_classes=["rt-status"],
                            )
                            transcript = gr.Textbox(
                                label="繁體中文逐字稿",
                                lines=14,
                                interactive=False,
                                placeholder="任務完成後，逐字稿會顯示在這裡。",
                            )
                            downloads = gr.File(
                                label="下載 TXT／SRT／VTT", file_count="multiple"
                            )

                            refresh.click(
                                lambda value: _job_view(service, value),
                                inputs=[job_id],
                                outputs=[job_status, transcript, downloads],
                            )
                            retry.click(
                                retry_job,
                                inputs=[job_id],
                                outputs=[job_status, transcript, downloads],
                            )

            gr.HTML(
                """
                <aside id="recordtrans-notice">
                  <strong>請保留原始錄音</strong><br>
                  逐字稿為自動辨識結果；姓名、數字與重要內容請回聽原始錄音確認。
                </aside>
                """
            )
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
