# RecordTrans 本機 Docker

## 已驗證前提

- Windows Docker Desktop 使用 WSL 2 Linux containers。
- NVIDIA GPU 已由 Docker runtime 辨識。
- 目前主機偵測為 RTX 3070 Ti Laptop 8 GB、NVIDIA driver 551.23；CUDA 12.6 測試 image 曾因 driver 條件不符而拒絕啟動，因此尚未通過 RecordTrans GPU 推論驗收。

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
docker compose run --rm whisper-webui python scripts/gpu_diagnostics.py
docker compose up -d
docker compose ps
```

瀏覽器開啟 `http://127.0.0.1:7860`。GPU 診斷成功只證明 runtime 可見；MVP 還須完成短音檔實際推論。第一次啟動會下載模型，第二次啟動應重用 named volume。

## 停止

```powershell
docker compose down
```

不要使用 `docker compose down -v`，該參數會刪除模型 volume。使用者資料位於設定的本機資料目錄，不由 GitHub 備份。
