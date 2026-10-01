# Spec Delta

## Purpose

讓 RecordTrans 在 Windows Docker Desktop 與 WSL 2 上以本機 GPU 可重現啟動，並保障服務與使用者資料只在預期範圍內暴露。

## ADDED Requirements

### Requirement: 本機限定服務
系統 MUST 預設只將 Web UI 發布至 127.0.0.1，不得啟用公開分享連結。

#### Scenario: 啟動服務
- **WHEN** 使用者執行文件所列的 Docker Compose 啟動指令
- **THEN** UI 可由本機瀏覽器開啟且不綁定所有主機網路介面

### Requirement: GPU 執行驗證
系統 MUST 記錄並驗證驅動、CUDA、推論套件與模型組合；只有實際短音檔 GPU 推論成功才算通過。

#### Scenario: GPU 相容
- **WHEN** 容器能辨識 GPU 且短音檔推論完成
- **THEN** 系統記錄版本與資源使用並允許進入功能驗收

#### Scenario: GPU 不相容
- **WHEN** 驅動或 CUDA 不符合執行需求
- **THEN** 啟動或健康檢查顯示相容性錯誤，不得宣稱 GPU 驗證成功

### Requirement: 持久化與備份
系統 SHALL 將模型快取與使用者資料置於不同持久化位置，並提供經實測的資料備份與還原步驟。

#### Scenario: 重建容器
- **WHEN** 使用者重建應用容器
- **THEN** 模型快取與使用者資料仍存在且可再次使用

#### Scenario: 還原備份
- **WHEN** 使用者依文件將備份還原至空資料目錄
- **THEN** 系統可查詢已備份的來源、任務與結果

