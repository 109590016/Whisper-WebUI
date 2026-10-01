---
name: git-smart-commit
description: 在 ReMoney 功能完成且要求提交時，檢查 diff，將同一功能的變更整理為可追溯的 Conventional Commits。
---

先檢查 `git status` 與完整 diff，區分本任務與使用者既有修改。只暫存本任務指定檔案。依可理解的功能邊界提交，例如 `feat(entry): add confirmation flow` 或 `test(rules): cover recorder access`。提交前執行相關驗證，提交後確認工作目錄與 commit 範圍。不得使用 `git add .` 混入無關內容，也不得繞過 hooks。
