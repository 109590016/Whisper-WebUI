from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..recording import RecordingController, RecordingError, RecordingView


@dataclass(slots=True)
class RecordingComponents:
    capture: Any
    playback: Any
    status: Any
    source_id: Any
    job_id: Any
    save_button: Any
    submit_button: Any
    state: Any


def _capture_changed(
    controller: RecordingController,
    temporary_path: str | None,
) -> tuple[str | None, str, RecordingView, Any, Any]:
    import gradio as gr

    view = controller.capture_ready(temporary_path)
    return (
        view.temporary_path,
        view.message,
        view,
        gr.update(interactive=view.can_save),
        gr.update(interactive=False),
    )


def _save_recording(
    controller: RecordingController,
    view: RecordingView | None,
) -> tuple[str | None, str, str, RecordingView | None, Any]:
    import gradio as gr

    if view is None:
        return None, "尚無可保存的錄音。", "", None, gr.update(interactive=False)
    try:
        saved_view = controller.save(view)
    except RecordingError as exc:
        return None, str(exc), "", view, gr.update(interactive=False)
    assert saved_view.saved is not None
    return (
        saved_view.saved.playback_path,
        saved_view.message,
        saved_view.saved.source_id,
        saved_view,
        gr.update(interactive=True),
    )


def _submit_recording(
    controller: RecordingController,
    view: RecordingView | None,
) -> tuple[str, str, RecordingView | None]:
    if view is None:
        return "錄音尚未永久保存，無法提交轉錄。", "", None
    try:
        submitted_view = controller.submit(view)
    except RecordingError as exc:
        return str(exc), "", view
    return submitted_view.message, submitted_view.job_id or "", submitted_view


def build_recording_panel(controller: RecordingController) -> RecordingComponents:
    """Build the recording panel for assembly by the application entry point."""
    import gradio as gr

    gr.Markdown(
        "使用瀏覽器的錄音按鈕開始與停止。若拒絕權限或沒有裝置，"
        "瀏覽器會顯示錯誤；請允許 localhost 使用麥克風後再試。"
    )
    capture = gr.Audio(
        label="麥克風錄音（停止後可回聽）",
        sources=["microphone"],
        type="filepath",
    )
    with gr.Row():
        save_button = gr.Button("永久保存錄音", interactive=False)
        submit_button = gr.Button("提交轉錄", variant="primary", interactive=False)
    playback = gr.Audio(label="已保存錄音回聽", interactive=False)
    status = gr.Textbox(label="錄音狀態", value="尚未錄音。", interactive=False)
    source_id = gr.Textbox(label="來源 ID", interactive=False)
    job_id = gr.Textbox(label="任務 ID", interactive=False)
    state = gr.State(None)

    capture.change(
        fn=lambda path: _capture_changed(controller, path),
        inputs=[capture],
        outputs=[playback, status, state, save_button, submit_button],
    )
    save_button.click(
        fn=lambda current: _save_recording(controller, current),
        inputs=[state],
        outputs=[playback, status, source_id, state, submit_button],
    )
    submit_button.click(
        fn=lambda current: _submit_recording(controller, current),
        inputs=[state],
        outputs=[status, job_id, state],
    )
    return RecordingComponents(
        capture=capture,
        playback=playback,
        status=status,
        source_id=source_id,
        job_id=job_id,
        save_button=save_button,
        submit_button=submit_button,
        state=state,
    )
