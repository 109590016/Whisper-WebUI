---
name: git-worktree-design
description: 在 ReMoney 有兩個以上可獨立實作的功能時，設計 Feature Spec、檔案所有權與 Git worktree 拆分方案。
---

先讀 `AGENTS.md`、`docs/STATUS.md` 與相關產品文件，再檢查 `git status --short --branch`、`git worktree list`、remote 與基準 commit。只有共同契約已固定、任務能獨立驗收，才建議平行。

為每個分支指定目標、可修改檔案、驗收條件、相依與合併順序。讓使用者看過拆分方案後建立 worktree；保留所有既有變更，不自動 stash、reset、強制移除或刪除分支。建立後逐一確認路徑、branch 與基準 commit。優先使用目前 Codex 環境提供的受管理 worktree 工具；無法使用時才考慮原生 Git 指令。

各分支從同一個已驗證的 `main` commit 開始。規格保存在 `docs/specs/`，避免每個分支都改同名根目錄文件。
