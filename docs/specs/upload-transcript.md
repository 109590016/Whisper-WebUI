# Upload Transcript Feature Spec

## 目標

完成 RT-04 與 RT-06：驗證並永久保存支援媒體，透過固定轉錄 adapter 產生 segments、繁體文字及 TXT／SRT／VTT。

## 分支與檔案所有權

- 分支／工作樹：`feat/upload-transcript`／`upload-transcript`
- 可新增或修改：`modules/recordtrans/media.py`、`transcription.py`、`exports.py`、`ui/upload.py`、`ui/results.py`
- 測試：`tests/recordtrans/test_media.py`、`test_transcription.py`、`test_exports.py`
- 不修改：`app.py`、`requirements.txt`、`docker-compose.yaml`、`modules/recordtrans/contracts.py`、`storage.py`、`repository.py`、套件 `__init__.py`

## 共用介面

- 使用 `LocalMediaStorage.store_path(..., SourceKind.UPLOAD)` 保存來源，再呼叫 `RecordTransRepository.add_source()` 與 `create_job()`。
- 轉錄 adapter 接受永久來源 `Path`，回傳 `Sequence[Segment]`、偵測語言與 metadata，不直接變更 job 狀態。
- exporter 接受同一組繁體 segments，輸出至 DATA_DIR 的 outputs，完成前使用暫存檔。

## 驗收

依 OpenSpec `media-transcription` capability 與 tasks 4.1～4.4；PR 必須附 fake adapter 測試及可用時的短音檔整合結果。

