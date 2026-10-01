# RecordTrans MVP 拆單與驗收計畫

日期：2026-10-01。狀態：已確認；實作中。
方法：WWA（Why／What／Acceptance）。本文件為審閱用 backlog，並非已初始化或經 CLI 驗證的 OpenSpec change。

## 目標與邊界

單人於 Windows 本機開啟瀏覽器，錄製麥克風音訊或上傳音訊／影片，保存來源檔案，轉成可下載的逐字稿。以 jhj0517/Whisper-WebUI 為基底，沿用 Gradio 與 faster-whisper。

第一版：錄音停止後保存、檔案上傳、背景轉錄狀態、繁體中文結果、TXT／SRT／VTT、最近任務與重試、本機資料持久化、Docker 操作文件。
排除：即時轉錄、錄影／螢幕擷取、講者辨識、摘要、YouTube、翻譯、音源分離、帳號、LAN／公開服務。JSON 用作內部結果格式；不增加 JSON 下載 UI。
規劃假設：使用 Chrome／Edge 的 localhost；指定資料夾透過啟動設定掛載，第一版不做系統資料夾挑選器。支援 60 分鐘／1 GiB 以內上傳，30 分鐘連續錄音；這些是驗收目標，尚未實測。

## 證據與待驗證事項

- 本機尚無上游程式碼或 Git repository，既有 skills 必須保留。上游原始碼為線上 master 快照，實作前須固定 commit。
- 上游 app.py 已有上傳、麥克風、字幕輸出，也有 Gradio 暫存清除設定。錄音元件回傳暫存路徑不等於永久保存；必須新增明確保存流程。
- 上游 app.py 在啟動階段載入翻譯等功能，故不能只刪 requirements；須先解開匯入與初始化相依。
- 前一輪實測：Docker Desktop／WSL 2 可用，GPU 為 RTX 3070 Ti Laptop 8 GB；驅動 551.23，CUDA 12.6 測試容器遭版本條件拒絕。這不代表 PyTorch GPU 推論已通過。
- 上游 requirements 預設 cu128。優先由使用者完成相容驅動更新後驗證；不能只改 CUDA image 或單一套件便宣稱相容。
- Docker 當時可用 RAM 約 7.62 GiB；主機總 RAM 未取得，不先承諾調至 12／16 GB。autoMemoryReclaim 如需設定應置於 [experimental]；本規劃不修改全域 WSL 設定。
- Gradio 的長錄音可用性、繁體字輸出品質、GPU 推論與資源用量均待實測。

來源：
- https://github.com/jhj0517/Whisper-WebUI
- https://github.com/jhj0517/Whisper-WebUI/blob/master/app.py
- https://github.com/jhj0517/Whisper-WebUI/blob/master/modules/whisper/base_transcription_pipeline.py
- https://github.com/jhj0517/Whisper-WebUI/blob/master/requirements.txt
- https://github.com/jhj0517/Whisper-WebUI/blob/master/docker-compose.yaml

## 設計提案

一個 Docker Compose service 執行 Gradio 與 faster-whisper，沿用上游事件處理，不另建 React／FastAPI／Redis。所有轉錄共用一個 concurrency limit，GPU 同時一件。SQLite 記錄任務與來源／結果路徑；長任務不占用資料庫交易。重啟後將未完成任務標為「已中斷」，由使用者重試，不承諾自動續跑。

Windows 的 DATA_DIR 掛載至容器資料根目錄，其下 recordings、uploads、outputs、state 為永久資料；temp 為可清除資料。模型使用 Docker named volume；保留上游 configs 預設檔，避免空 bind mount 遮蔽設定。資料夾須通過可寫檢查後才接受錄音／上傳。正式保存使用唯一 ID 與原子完成標記，避免覆蓋同名來源。

只發布 127.0.0.1:7860，容器內仍監聽 0.0.0.0。不啟用 Gradio share；初次下載套件／模型需網路，模型備妥後以離線轉錄測試證明音訊不需送到雲端。

預設 small／float16／Chinese；可選自動辨識與 English。保留原始辨識文字，使用 OpenCC 類確定性轉換產生繁體版本，不以 LLM 改寫。繁簡轉換不等於辨識正確；時間戳從結構化 segments 產生，所有輸出共用同一份文字。

## 工作單

### RT-01：建立可追溯基底與正式規格（S）
**Why：** 保留上游更新來源與既有規劃，讓後續修改可追蹤。
**What：** 確認後建立 GitHub fork、整合至目前目錄，保留 skills 與本文件；記錄 upstream commit、授權與修改聲明。初始化 OpenSpec，將核定內容轉為 proposal／specs／design／tasks。
**Acceptance：** origin／upstream 指向正確；無遺失既有文件；上游 commit 可追溯；OpenSpec 驗證通過；錄音與模型不納入 Git。
**依賴：** 使用者確認本計畫；GitHub 帳號可建立 fork。無權限時只阻擋 fork／push，仍可完成本機規格。

### RT-02：本機 Docker 與 GPU 可重現啟動（M）
**Why：** 先排除驅動相容問題，避免功能開發建立在未驗證環境。
**What：** 確認驅動、固定上游依賴與映像版本，建立 localhost Compose、模型快取與資料掛載。先驗證上游基本轉錄。
**Acceptance：** 容器 GPU 檢查及實際短音檔推論皆成功；頁面由 localhost 開啟；只綁 loopback；第二次啟動重用模型；記錄安裝版本與資源用量。不得停掉其他既有容器。
**依賴：** RT-01；驅動更新可能需使用者操作及重啟。未通過不可宣稱 GPU MVP 完成。

### RT-03：來源檔與任務持久化（M）
**Why：** 錄音與逐字稿是使用者的成果，不能因清除暫存或重建容器而消失。
**What：** DATA_DIR 設定、啟動可寫檢查、永久來源保存、SQLite 任務 ID／狀態／路徑、內部 segments 結果結構。
**Acceptance：** 自訂含中文與空白的 Windows 路徑可用；同名檔案不覆蓋；只在完整寫入後回報保存成功；不可寫或磁碟不足時明確失敗；重建容器仍能讀回來源與已完成資料。
**依賴：** RT-02。此單先固定共用資料契約，再做 RT-04／05。

### RT-04：上傳音檔／影片並產生逐字稿（M）
**Why：** 先讓既有訪談與影片能轉成可用文字。
**What：** 串接 MP3、WAV、M4A、MP4、MOV、WebM 上傳、媒體檢查、永久保存及 faster-whisper。每次選一個檔案，多次提交可排隊。
**Acceptance：** 六種格式各以有效音軌樣本成功轉錄；60 分鐘／1 GiB 內樣本完成；超限檔案提前拒絕；無音軌影片、損毀檔與偽副檔名顯示可理解錯誤；失敗後來源仍保留。
**依賴：** RT-03。

### RT-05：錄音停止後永久保存（M）
**Why：** 使用者可以直接完成新訪談錄音，不必使用另一套錄音軟體。
**What：** 沿用 Gradio 麥克風元件，提供開始／停止、回聽、保存狀態與轉錄操作；停止後先完成伺服器保存再允許轉錄。
**Acceptance：** Chrome／Edge 麥克風授權、拒絕授權與無裝置狀態清楚；30 分鐘連續錄音可回聽、保存並轉錄；不轉錄也保留錄音；保存成功後重新整理不遺失。尚未保存時離頁提醒；瀏覽器崩潰的未保存錄音不承諾復原。
**依賴：** RT-03；與 RT-04 共用轉錄服務，不複製 pipeline。

### RT-06：繁體逐字稿與一致的下載格式（M）
**Why：** 結果可直接閱讀、交付與作為字幕使用。
**What：** 顯示逐字稿、下載 TXT／SRT／VTT，提供繁體轉換並保留原始辨識文字，明示逐字稿仍需校對。
**Acceptance：** 三格式文字一致；UTF-8 中文不亂碼；字幕時間有效且依序排列；英文字詞／數字不因繁簡轉換改寫；無語音樣本不造成程式錯誤，若模型仍產生文字則記錄為品質缺陷，不假裝正確。
**依賴：** RT-04；RT-05 接入後以錄音來源再驗收。

### RT-07：任務狀態、重試與中斷處理（M）
**Why：** 使用者知道長檔案是否還在處理，失敗時能重試而不用重錄。
**What：** 等待／處理／完成／失敗／已中斷狀態、最近任務列表、單 GPU 併發限制、從原始檔重試。沒有可靠比例時只顯示階段與已用時間。
**Acceptance：** 同時提交兩件只有一件進行 GPU 推論；錯誤包含可採取的下一步；刷新可查詢狀態與成果；重啟後原處理中任務標為中斷；重試新建 attempt 並保留既有結果；未完成輸出不顯示為可用成品。
**依賴：** RT-03、RT-04；涵蓋 RT-05／06 的整合流程。

### RT-08：精簡介面與必要依賴（M）
**Why：** 常用路徑易懂且安裝負擔可控制。
**What：** 繁體中文介面聚焦錄音、上傳、最近任務與結果；先去除無用功能的匯入／初始化，再移除對應依賴，保留 faster-whisper 與必要 VAD。
**Acceptance：** 無 YouTube、翻譯、語者辨識、音源分離入口；不需 DeepL／HF token；乾淨 image build 和錄音／上傳回歸通過；無新增時序錯誤。記錄 image 大小，不承諾固定縮減比例。
**依賴：** RT-04 至 RT-07。此單不重做前端框架。

### RT-09：完整驗收與本機交付（M）
**Why：** 能重複啟動並持續使用才算完成 MVP。
**What：** Docker 冷啟動、快取啟動、模型備妥後離線轉錄、完整流程與錯誤情境測試；提供啟動／停止／備份／還原／更新文件。
**Acceptance：** 下方完成清單全數通過並附證據；無未解決的資料遺失或主要流程阻斷；README 可依序操作；備份實際還原成功；不以自動化假錄音替代 30 分鐘麥克風實測。
**依賴：** RT-01 至 RT-08。

## 順序與規模

RT-01 → RT-02 → RT-03 → RT-04／RT-05 → RT-06／RT-07 → RT-08 → RT-09。
功能單盡量獨立驗收，但共用資料契約與環境有真實依賴，不宣稱全部能任意順序施工。S／M 是相對規模，不是工期承諾。RT-01～03 由整合 agent 依序完成；共用契約固定後，依下方分工啟動三個功能 agent 與獨立工作樹。

里程碑 A：RT-01～04，可上傳並 GPU 轉錄。
里程碑 B：RT-05～07，錄音、保存、逐字稿下載與重試形成完整使用流程。
里程碑 C：RT-08～09，精簡介面並完成交付驗收。

## Agent 與工作樹分工（待確認）

本次只更新計畫，不建立 fork、branch、worktree 或啟動實作 agent。確認後最多同時使用四個 agent：一個整合 agent 與三個功能 agent。採用工作樹分工原則：共同契約先固定、每個分支有檔案所有權與獨立驗收，再建立工作樹。

### 共用基底與啟動條件

整合 agent 先完成 RT-01～03，固定來源保存 API、任務 ID／狀態／attempt 結構、segments 格式、轉錄呼叫介面、錯誤格式與 UI 模組入口。實際函式名稱在檢查 fork 程式碼後寫入 Feature Spec。基底必須通過儲存與狀態測試及短音檔 GPU 轉錄，再推送並確認本機整合分支 HEAD 等於 origin 對應分支。

記錄基準 commit SHA，三個功能分支全部由此 SHA 建立；優先使用 Codex 受管理 worktree，各自驗證路徑、branch 與 SHA。整合分支沿用 fork 預設分支（預期 master，建立後核實），不為了命名任意改成 main。

| Agent | 建議分支／工作樹名稱 | 工作單 | 檔案所有權與交付 |
|---|---|---|---|
| 整合 agent | fork 預設分支；共用改動另開 chore/mvp-foundation、feat/mvp-integration | RT-01～03、RT-08～09 | app.py、Dockerfile、docker-compose.yaml、requirements.txt、configs/、共用儲存／資料庫／契約、README、主規格與整合測試 |
| 上傳轉錄 agent | feat/upload-transcript／upload-transcript | RT-04、RT-06 | 擬新增 modules/recordtrans/upload.py、transcription.py、exports.py、ui/upload.py、ui/results.py，及 tests/recordtrans/test_upload*、test_transcription*、test_exports* |
| 錄音 agent | feat/recording／recording | RT-05 | 擬新增 modules/recordtrans/recording.py、ui/recording.py，及 tests/recordtrans/test_recording* |
| 任務管理 agent | feat/job-lifecycle／job-lifecycle | RT-07 | 擬新增 modules/recordtrans/jobs.py、ui/jobs.py，及 tests/recordtrans/test_jobs* |

上述新增模組路徑是規劃，尚非已存在的上游檔案。RT-03 結束前由整合 agent 核對上游後固定，於 docs/specs/upload-transcript.md、recording.md、job-lifecycle.md 分別記錄目標、實際可修改檔案、介面、驗收及相依。套件 __init__.py 與其他共用檔案由整合 agent 擁有；功能 agent 不自行修改 app.py 或套件版本。

### 平行開發與相依處理

- 上傳／錄音模組共用基底的來源保存與任務提交介面；任務 agent 實作排隊執行與生命週期，轉錄 agent 提供實際推論 adapter。各分支先以固定介面的 fake adapter／測試替身驗收模組行為，不把替身測試當成完整流程通過。
- 錄音 agent 可以先完成錄音保存與回聽；錄音後實際轉錄待轉錄與任務模組整合後驗收。
- 共用契約需更動時，功能 agent 回報整合 agent，由整合 agent 更新基底與規格，再讓相關分支同步；不在各分支自行創造不同版本。
- 各工作樹使用獨立測試資料夾、SQLite 檔案與 Compose project name，瀏覽器測試使用不同 localhost port。只有一張 GPU，實機推論測試由整合 agent 排程，不能同時跑多個模型測試。
- 每個功能 agent 交付 commit SHA、修改檔案、驗收證據、限制與共用檔案整合需求；只更新自己的 Feature Spec／測試紀錄，主 backlog 與 OpenSpec tasks 由整合 agent 維護。

### 整合順序與完成門檻

1. 三個功能 agent 完成各自模組測試後，推送功能分支並建立 PR；涉及其他分支時明確標記相依。
2. 整合 agent 依「上傳轉錄 → 任務管理 → 錄音」順序審查合併至整合分支；後續分支同步已合併內容並重新驗證受影響測試。
3. 整合 agent 統一接上 app.py 的 UI／事件與轉錄排隊，完成 RT-08；所有來源都經同一個 GPU 併發限制。
4. 在合併後版本執行 RT-09，含真實麥克風、長檔案、重啟與資料保留測試。個別 PR 通過不等於 MVP 通過。
5. 推送最終結果，確認本機 HEAD 等於 origin 整合分支且工作目錄乾淨；有無關使用者變更則列明保留，不為達成乾淨狀態而刪除。
6. 驗證分支成果已整合並可恢復後，封存受管理 worktree；不強制移除未保存變更。

## GitHub 同步與交付（待確認）

- 計畫確認後，於已登入的個人 GitHub 帳號建立 Whisper-WebUI fork；origin 指向個人 fork，upstream 指向 jhj0517/Whisper-WebUI。帳號或目標存在歧義時再確認精確 owner／repo，不覆寫既有倉庫。
- 上游為公開倉庫，採用 GitHub fork 時預期也是公開。若需要私人專案，須改採保留授權的獨立 repository，不能把公開 fork 當作私有備份。
- RT-01 同步核定計畫、skills、正式規格與上游基底；後續各里程碑同步已驗證的程式碼、測試及必要操作文件。功能透過 branch／PR 整合，保留 RT 編號與測試證據；建立的 PR 附加到本對話。
- 納入 Git：程式碼、Docker 設定、依賴版本、OpenSpec、Feature Specs、測試、去識別的驗收摘要與不含機密的 .env.example。
- 排除 Git：原始錄音／影片／上傳檔、逐字稿、models、SQLite 與 journal／WAL、暫存、實際 .env、token、私人驗收素材。GitHub 是程式碼同步，使用者資料另依 RT-09 本機備份還原流程處理。
- 每次推送前檢查暫存區內容與忽略規則；只提交此工作單範圍，不使用 blanket add 將未知檔案一起上傳。不強制推送或覆寫遠端歷史。
- 同步完成須有遠端分支／PR URL 與 commit SHA 證據；本機 commit 或測試成功不能替代 push 成功。若登入或網路阻擋，列出尚未推送的 commit，不宣稱已同步。

## MVP 完成清單

- [ ] 本機 GPU 實際推論成功，版本與 upstream commit 已記錄。
- [ ] 30 分鐘真實麥克風錄音，停止後保存、回聽、轉錄成功。
- [ ] 六種格式及 60 分鐘檔案轉錄成功，超過 1 GiB／60 分鐘明確拒絕。
- [ ] 原始檔、TXT／SRT／VTT 與任務資料在容器重建後仍可取得。
- [ ] 兩件排隊、GPU 記憶體不足、損毀檔、無音軌、不可寫路徑與重啟中斷皆有驗收證據。
- [ ] 模型備妥後離線轉錄成功；服務僅綁 localhost。
- [ ] 以固定短中文／中英夾雜樣本對照人工逐字稿，記錄錯字與漏字；不將模型正確率宣稱為保證。
- [ ] 逐字稿字幕人工抽查前、中、後段，記錄品質限制。
- [ ] README 與備份還原流程完成，阻斷性缺陷清零。
- [ ] 三個功能工作樹成果已審查整合，合併後完整驗收通過。
- [ ] GitHub fork、origin／upstream 與 PR 可追溯；最終本機與遠端 commit 一致，無私人資料或模型誤上傳。

自動測試涵蓋儲存、狀態轉移、輸出與錯誤處理；GPU／麥克風／瀏覽器權限使用實機驗收。品質不符實際使用需求時先調模型與設定後重測，不自行增加即時轉錄或摘要。

## 確認後的第一步

將本計畫核定版本轉入 OpenSpec，建立 fork 基底並執行 RT-01。驅動安裝與系統重啟另由使用者操作／明確授權；不將規格核定視為任意改動全域環境的授權。
