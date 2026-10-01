# RecordTrans 本機 Docker

## 已驗證前提

- Windows Docker Desktop 使用 WSL 2 Linux containers。
- NVIDIA GPU 已由 Docker runtime 辨識。
- 目前主機已驗證 RTX 3070 Ti Laptop 8 GB、NVIDIA driver 551.23。
- 固定映像為 `nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04`，Python 3.10、CTranslate2 4.5.0、faster-whisper 1.1.1。
- CUDA 12.6 image 會因 driver 條件不符而拒絕啟動；不要把映像自行改回上游的 cu128 組合。

## 設定資料位置

複製 `.env.example` 為 `.env`，依需要修改 `RECORDTRANS_DATA_DIR`。資料目錄保存 recordings、uploads、outputs、state 與 temp；模型保存在 Docker named volume `recordtrans-models`。

## 驗證 Compose

```powershell
docker compose config
```

輸出必須只將 `7860` 發布至 `127.0.0.1`，並包含 `/data` 與模型 volume。

## 建置與啟動

```powershell
docker compose build
docker compose run --rm --entrypoint python whisper-webui scripts/gpu_diagnostics.py
docker compose up -d
docker compose ps
```

瀏覽器開啟 `http://127.0.0.1:7860`。狀態應顯示 `healthy`。第一次轉錄會下載模型，第二次啟動會重用 named volume。

## 已驗證 GPU 基線

2026-10-01 使用無私人內容的 3 秒合成 WAV 與 `tiny` 模型完成實際 CUDA 推論：首次模型載入 14.130 秒、推論 0.264 秒；快取後模型載入 1.942 秒、推論 0.065 秒。合成純音不含語音，因此空逐字稿是預期結果；此測試只驗證實際模型載入與 GPU inference path，內容品質另以真實語音驗收。

若要重跑相同技術驗收：

```powershell
docker compose run --rm --entrypoint ffmpeg whisper-webui -y -f lavfi -i "sine=frequency=440:duration=3" -ar 16000 -ac 1 /data/temp/gpu-tone.wav
docker compose run --rm --entrypoint python whisper-webui scripts/smoke_transcribe.py /data/temp/gpu-tone.wav
```

正式使用預設 `small` 模型。8 GB 顯存同時只執行一件工作；介面只顯示可證實的等待、處理、完成、失敗、已中斷狀態，不提供推測百分比。

## 停止

```powershell
docker compose down
```

不要使用 `docker compose down -v`，該參數會刪除模型 volume。使用者資料位於設定的本機資料目錄，不由 GitHub 備份。
