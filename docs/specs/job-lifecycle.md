# Job Lifecycle Feature Spec

## 目標

完成 RT-07：以單 worker 處理排隊任務，持久保存狀態、elapsed time、錯誤、中斷與 retry attempt。

## 分支與檔案所有權

- 分支／工作樹：`feat/job-lifecycle`／`job-lifecycle`
- 可新增或修改：`modules/recordtrans/jobs.py`、`modules/recordtrans/ui/jobs.py`
- 測試：`tests/recordtrans/test_jobs.py`
- 不修改：`app.py`、依賴／Compose、共用 contracts／storage／repository、套件 `__init__.py`

## 共用介面

- queue 接受 job ID 與 `Callable[[str], None]` processor，worker 同時只處理一件。
- 所有狀態變更透過 `RecordTransRepository.transition_job()`；啟動呼叫 `mark_processing_interrupted()`。
- retry 使用 `retry_job()` 建立新 attempt，來源可用性由整合層在排隊前檢查。

## 驗收

依 OpenSpec `transcription-jobs` capability 與 tasks 6.1～6.3；測試必須證明兩件工作不會同時執行。

