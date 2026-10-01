from __future__ import annotations

import gradio as gr


def recordtrans_theme() -> gr.Theme:
    """Return the restrained Material-inspired theme used by RecordTrans."""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        font=[gr.themes.GoogleFont("Noto Sans TC"), "Inter", "sans-serif"],
    ).set(
        body_background_fill="#F3F6F8",
        body_background_fill_dark="#F3F6F8",
        body_text_color="#172B3A",
        body_text_color_dark="#172B3A",
        block_background_fill="#FFFFFF",
        block_background_fill_dark="#FFFFFF",
        block_border_color="#DCE4EA",
        block_border_color_dark="#DCE4EA",
        block_label_text_color="#496273",
        block_label_text_color_dark="#496273",
        input_background_fill="#F8FAFB",
        input_background_fill_dark="#F8FAFB",
        input_border_color="#D5E0E7",
        input_border_color_dark="#D5E0E7",
        button_primary_background_fill="#24658D",
        button_primary_background_fill_hover="#1D5273",
        button_primary_text_color="#FFFFFF",
        button_secondary_background_fill="#EEF3F6",
        button_secondary_background_fill_hover="#E2EAF0",
        button_secondary_text_color="#27495F",
        border_color_primary="#DCE4EA",
        border_color_primary_dark="#DCE4EA",
        shadow_drop="0 16px 40px rgba(31, 61, 81, 0.08)",
    )


APP_CSS = """
:root {
  --rt-ink: #172b3a;
  --rt-muted: #607889;
  --rt-blue: #24658d;
  --rt-blue-soft: #dcecf6;
  --rt-surface: #ffffff;
  --rt-line: #dce4ea;
  --rt-page: #f3f6f8;
  --rt-warning: #fff2cf;
  --rt-warning-ink: #7b5308;
}

body {
  background: var(--rt-page) !important;
}

body > gradio-app > .gradio-container {
  width: min(1180px, 100%) !important;
  flex: 0 1 1180px;
  margin-inline: auto !important;
}

.gradio-container {
  max-width: 1180px !important;
  padding: 34px 28px 48px !important;
  color: var(--rt-ink) !important;
}

#recordtrans-shell {
  gap: 22px;
  width: min(1120px, 100%) !important;
  max-width: 1120px !important;
  margin-inline: auto;
  align-self: stretch;
}

#recordtrans-hero {
  position: relative;
  overflow: hidden;
  padding: 34px 38px;
  border: 1px solid var(--rt-line);
  border-radius: 28px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fbfd 72%, #e5f0f6 100%);
  box-shadow: 0 18px 48px rgba(31, 61, 81, 0.08);
}

#recordtrans-hero::after {
  content: "";
  position: absolute;
  right: -56px;
  top: -70px;
  width: 210px;
  height: 210px;
  border-radius: 50%;
  background: rgba(36, 101, 141, 0.08);
}

.rt-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding: 7px 12px;
  border-radius: 999px;
  background: var(--rt-blue-soft);
  color: #1f5b80;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.rt-eyebrow::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3d86af;
}

.rt-hero-title {
  position: relative;
  z-index: 1;
  margin: 0;
  color: var(--rt-ink);
  font-size: clamp(38px, 5vw, 58px);
  font-weight: 760;
  letter-spacing: -0.045em;
  line-height: 1.05;
}

.rt-hero-copy {
  position: relative;
  z-index: 1;
  max-width: 650px;
  margin: 14px 0 0;
  color: var(--rt-muted);
  font-size: 16px;
  line-height: 1.75;
}

#recordtrans-workspace {
  padding: 8px;
  border: 1px solid var(--rt-line);
  border-radius: 28px;
  background: var(--rt-surface) !important;
  box-shadow: 0 18px 48px rgba(31, 61, 81, 0.08);
}

#recordtrans-tabs,
#recordtrans-tabs > .tab-wrapper,
#recordtrans-tabs .tabitem {
  background: var(--rt-surface) !important;
}

#recordtrans-tabs > .tab-wrapper > .tab-container:not(.visually-hidden) {
  gap: 6px;
  margin: 0;
  padding: 7px;
  border: 0;
  border-radius: 20px;
  background: #eaf0f3;
}

#recordtrans-tabs > .tab-wrapper > .tab-container:not(.visually-hidden) button {
  flex: 1 1 0;
  min-height: 58px;
  margin: 0;
  border: 0 !important;
  border-radius: 15px;
  color: #506879;
  font-size: 16px;
  font-weight: 700;
  transition: background 160ms ease, box-shadow 160ms ease, color 160ms ease;
}

#recordtrans-tabs > .tab-wrapper > .tab-container:not(.visually-hidden) button.selected,
#recordtrans-tabs > .tab-wrapper > .tab-container:not(.visually-hidden) button[aria-selected="true"] {
  background: #ffffff !important;
  color: #1f5b80 !important;
  box-shadow: 0 5px 14px rgba(31, 61, 81, 0.10);
}

#recordtrans-tabs .tabitem {
  padding: 30px 26px 24px;
  border: 0;
}

.rt-section-heading {
  margin-bottom: 18px;
}

.rt-section-kicker {
  margin: 0 0 7px;
  color: var(--rt-blue);
  font-size: 12px;
  font-weight: 750;
  letter-spacing: 0.08em;
}

.rt-section-title {
  margin: 0;
  color: var(--rt-ink);
  font-size: 25px;
  font-weight: 750;
  letter-spacing: -0.02em;
}

.rt-section-copy {
  margin: 8px 0 0;
  color: var(--rt-muted);
  font-size: 14px;
  line-height: 1.7;
}

.rt-panel {
  gap: 16px;
}

.rt-panel .block,
.rt-panel .form {
  border-radius: 16px !important;
}

.rt-panel button {
  min-height: 48px;
  border-radius: 14px !important;
  font-weight: 700 !important;
}

.rt-panel button.primary {
  box-shadow: 0 8px 20px rgba(36, 101, 141, 0.20);
}

.rt-upload .upload-container {
  min-height: 188px;
  border: 1.5px dashed #a9bfcc !important;
  background: #f7fafc !important;
}

.rt-status textarea,
.rt-status input {
  font-weight: 600;
}

#recordtrans-notice {
  padding: 18px 22px;
  border: 0;
  border-radius: 18px;
  background: var(--rt-warning);
  color: var(--rt-warning-ink);
  font-size: 14px;
  line-height: 1.65;
}

#recordtrans-notice strong {
  color: #654300;
}

@media (max-width: 700px) {
  #recordtrans-shell {
    width: calc(100% + 96px) !important;
    max-width: calc(100% + 96px) !important;
    margin-inline: -48px;
  }

  #recordtrans-hero {
    padding: 27px 23px;
    border-radius: 22px;
  }

  .rt-hero-title {
    overflow-wrap: anywhere;
    font-size: 34px;
  }

  #recordtrans-workspace {
    border-radius: 22px;
  }

  #recordtrans-tabs > .tab-wrapper > .tab-container:not(.visually-hidden) {
    overflow-x: auto;
  }

  #recordtrans-tabs > .tab-wrapper > .tab-container:not(.visually-hidden) button {
    min-width: 0;
    min-height: 52px;
    padding-inline: 5px;
    font-size: 12px;
  }

  #recordtrans-tabs .tabitem {
    padding: 24px 14px 18px;
  }

  .rt-action-row {
    flex-direction: column !important;
  }

  .rt-action-row > * {
    width: 100% !important;
    min-width: 100% !important;
  }
}
"""
