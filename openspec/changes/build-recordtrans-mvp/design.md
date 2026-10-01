# Design

## Context

上游為 Gradio 單體應用，`app.py` 同時建立檔案、YouTube、麥克風、翻譯與音源分離介面，並於啟動時初始化多項非 MVP 依賴。上游已有 faster-whisper pipeline 與另一套 FastAPI backend，但目前 MVP 要優先交付單人本機介面，因此沿用 Gradio 路徑。現有 Docker Compose 掛載 models、outputs、configs 並向所有介面發布 7860；本機 GPU 驅動目前宣告 CUDA 12.4，相容版本仍需實際推論驗證。

## Goals / Non-Goals

**Goals:**

- 在上游架構內建立清楚分層的儲存、轉錄、任務與 UI 模組，使三個功能工作樹可在固定契約下開發。
- 所有來源先永久保存，所有轉錄經單一任務排隊與同一份結構化結果輸出。
- 容器重建後保留資料及模型，並提供可實測的離線轉錄與備份還原流程。

**Non-Goals:**

- 第一版不改寫成 React／FastAPI 多服務架構，不提供多使用者或遠端存取。
- 不保證瀏覽器崩潰前尚未傳至伺服器的錄音可以復原。
- 不以自動摘要、LLM 校稿或講者辨識改變原始逐字稿。

## Decisions

### 1. 沿用 Gradio，新增 RecordTrans 模組邊界

保留 `app.py` 作為組裝入口，把來源保存、轉錄 adapter、輸出、任務與各 UI 區塊放進 `modules/recordtrans/`。整合 agent 擁有入口與共用 `__init__.py`，功能分支只修改其 Feature Spec 授權的模組。替代方案是採用現有 FastAPI backend 或重做 SPA；兩者會增加 API、前端與部署範圍，無助於先驗證本機 MVP。

### 2. SQLite 作為狀態來源，檔案系統保存媒體與輸出

資料根目錄分為 `recordings/`、`uploads/`、`outputs/`、`state/` 與 `temp/`。SQLite 保存 source、job、attempt、狀態及相對路徑；媒體與大輸出不放入資料庫。使用 UUID、暫存檔與原子 rename 完成來源保存。替代方案是 Redis/Celery，但單機單 GPU 沒有額外服務的必要。

### 3. 程序內單 worker 排隊，重啟採明確中斷

所有來源提交同一個 queue，worker 同時只執行一項 GPU 推論。啟動時將遺留 processing job 標為 interrupted；重試建立新 attempt，不隱藏舊錯誤。這比假裝可從模型中段續傳更可預測，也避免在第一版引入分散式工作系統。

### 4. 轉錄 adapter 包裝上游 faster-whisper pipeline

adapter 接受永久來源，輸出統一的 segments、偵測語言與 metadata。預設 small／float16／Chinese，模型選項保持有限。上游輸出工具若符合契約則重用；否則以 adapter 正規化。GPU 驗收必須包含短音檔實際推論，單純 `nvidia-smi` 不足。

### 5. 原始與繁體結果分離

結構化結果保存原始辨識文字與確定性繁體轉換文字。TXT、SRT、VTT 從同一組轉換後 segments 產生，避免格式漂移；原始資料保留供追查。文字轉換使用 OpenCC 相容套件，不進行生成式重寫。

### 6. Compose 只綁 localhost 並分離資料與模型

Compose 使用 `127.0.0.1:7860:7860`，關閉 Gradio share。`DATA_DIR` bind mount 保存使用者資料，named volume 保存模型。configs 使用映像內預設加上明確 override，避免空目錄遮蔽。實作會固定 image 與 Python 依賴，不使用浮動 latest 作為可重現證據。

### 7. 先固定共用契約，再建立三個工作樹

RT-01～03 在整合分支完成後記錄基準 SHA，從同一 SHA 建立 upload-transcript、recording、job-lifecycle 工作樹。各分支以 fake adapter 驗證自身行為；GPU 與完整流程由整合分支串行驗證，避免單張 GPU 競爭。

## Risks / Trade-offs

- [Gradio 長錄音可能受瀏覽器記憶體與上傳行為限制] → 以 Chrome／Edge 30 分鐘真實錄音作為完成門檻；若失敗，縮小第一版承諾並記錄替代錄音方案，不能默默宣稱通過。
- [目前 NVIDIA 驅動與上游 cu128 不相容] → 先驗證可用的驅動／PyTorch 組合；需要系統更新時由使用者執行並重啟，程式提供明確版本文件。
- [程序內 queue 在非正常終止時不會續跑] → 任務與來源持久化，啟動時標為 interrupted 並允許重試。
- [SQLite 與多執行緒競爭] → 使用短交易、每操作獨立 connection、WAL 與狀態轉移條件；GPU 推論期間不持有交易。
- [精簡依賴可能觸發上游隱性匯入] → 先移除 UI 初始化路徑並跑乾淨 image build，再移除套件；每步執行錄音／上傳回歸。
- [公開 fork 誤收研究資料] → `.gitignore`、提交前 staged file 檢查與去識別測試素材；資料備份不使用 GitHub。

## Migration Plan

1. 以固定 upstream master commit 建立本機基底並初始化 OpenSpec。
2. 建立共用資料契約、忽略規則與 Docker GPU 基線；以短音檔驗證。
3. 提交並推送 foundation SHA，再由同一 SHA 建立三個功能工作樹。
4. 依序整合上傳轉錄、任務生命週期、錄音，最後精簡 UI／依賴。
5. 完成長檔、真實麥克風、重啟、離線與備份還原驗收後推送最終版本。

若 foundation 尚未被其他分支使用，可回退該分支；平行工作開始後，使用 revert commit 回復個別變更，不重寫共享歷史。使用者資料的 schema 變更須先備份 SQLite 與媒體目錄。
