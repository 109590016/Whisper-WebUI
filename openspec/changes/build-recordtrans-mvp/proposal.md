# Proposal

## Why

目前上游 Whisper-WebUI 雖支援檔案與麥克風轉錄，但來源錄音主要經過 Gradio 暫存路徑，缺少適合研究訪談使用的永久保存、可恢復任務狀態與本機交付流程。RecordTrans MVP 要讓單一使用者在 Windows 本機可靠地保存錄音或上傳媒體，使用 GPU 轉錄並取得繁體中文逐字稿。

## What Changes

- 建立僅供 localhost 使用的精簡繁體中文介面，保留錄音、媒體上傳、任務與結果頁面。
- 將錄音與上傳來源永久保存至可設定的本機資料目錄，避免因 Gradio 暫存清除而遺失。
- 建立持久化的轉錄任務生命週期、單 GPU 排隊、失敗重試與重啟中斷處理。
- 使用 faster-whisper 產生結構化 segments，輸出一致的 UTF-8 TXT、SRT 與 VTT，並提供確定性的繁體中文轉換。
- 建立可重現的 Docker Compose GPU 執行環境、模型快取、資料備份還原與驗收文件。
- 移除 MVP 不需要的 YouTube、翻譯、講者辨識與音源分離入口及必要依賴。
- **BREAKING**：既有完整 Whisper-WebUI 介面將縮減為 RecordTrans MVP；被排除的功能不再從主要容器提供。

## Capabilities

### New Capabilities

- `local-media-storage`：錄音與上傳來源的永久保存、資料目錄驗證、唯一命名及重啟後存取。
- `media-transcription`：支援的音訊／影片驗證、faster-whisper 轉錄、繁體轉換與 TXT／SRT／VTT 結果。
- `recording-capture`：瀏覽器麥克風錄製、回聽、保存及提交轉錄。
- `transcription-jobs`：轉錄任務排隊、狀態、重試、單 GPU 併發限制及重啟中斷恢復。
- `local-docker-runtime`：只綁定 localhost 的 Docker GPU 執行、模型快取、資料持久化與備份還原。

### Modified Capabilities

目前沒有既有 OpenSpec capability。

## Impact

- 主要受影響區域為 `app.py`、`modules/`、`configs/`、`Dockerfile`、`docker-compose.yaml`、依賴清單與測試。
- 新增 SQLite 狀態資料、可設定的資料根目錄、RecordTrans 專用模組與整合測試。
- 需要相容 NVIDIA GPU 的 Windows 驅動、Docker Desktop WSL 2 與首次模型下載網路。
- GitHub 將保留 `upstream` 指向 `jhj0517/Whisper-WebUI`，`origin` 指向使用者 fork；錄音、影片、逐字稿、模型、資料庫與機密不提交。
