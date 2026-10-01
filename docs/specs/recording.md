# Recording Feature Spec

## 目標

完成 RT-05：提供麥克風錄製、停止、回聽、永久保存與提交轉錄，且保存與轉錄是兩個可觀察步驟。

## 分支與檔案所有權

- 分支／工作樹：`feat/recording`／`recording`
- 可新增或修改：`modules/recordtrans/recording.py`、`modules/recordtrans/ui/recording.py`
- 測試：`tests/recordtrans/test_recording.py`
- 不修改：`app.py`、依賴／Compose、共用 contracts／storage／repository、套件 `__init__.py`

## 共用介面

- Gradio 暫存檔必須經 `LocalMediaStorage.store_path(..., SourceKind.RECORDING)` 保存並寫入 repository。
- UI 只有在保存成功後回傳可提交的 source ID；提交使用共用 job 建立介面。
- 功能分支可用 fake submitter 驗證流程，整合 agent 負責接入真實 queue 與 `app.py`。

## 驗收

依 OpenSpec `recording-capture` capability 與 tasks 5.1～5.4；30 分鐘真實瀏覽器錄音由整合環境執行。

