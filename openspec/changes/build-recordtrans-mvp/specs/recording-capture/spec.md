# Spec Delta

## Purpose

讓使用者直接在 localhost 瀏覽器錄製麥克風音訊，先確認並永久保存，再提交本機轉錄。

## ADDED Requirements

### Requirement: 麥克風錄製與回聽
系統 SHALL 在支援的 Chrome 或 Edge 中提供開始、停止與回聽錄音的操作及清楚狀態。

#### Scenario: 完成錄音
- **WHEN** 使用者允許麥克風並停止錄音
- **THEN** 系統提供回聽，並開始將錄音保存至伺服器資料目錄

#### Scenario: 麥克風不可用
- **WHEN** 使用者拒絕權限或沒有可用裝置
- **THEN** 系統顯示原因且不建立空白來源

### Requirement: 保存與轉錄分離
系統 MUST 在顯示保存成功後才允許提交轉錄，且未提交轉錄的錄音仍須保留。

#### Scenario: 只保存錄音
- **WHEN** 使用者完成錄音但不提交轉錄
- **THEN** 重新整理後該錄音仍可被查詢及回聽

#### Scenario: 保存失敗
- **WHEN** 錄音無法完整保存
- **THEN** 系統顯示失敗並禁止將該錄音提交轉錄

### Requirement: 長錄音驗收
系統 SHALL 支援至少 30 分鐘的連續錄音保存、回聽與後續轉錄。

#### Scenario: 三十分鐘錄音
- **WHEN** 使用者在支援瀏覽器完成 30 分鐘真實麥克風錄音
- **THEN** 錄音可完整保存、回聽並提交轉錄

