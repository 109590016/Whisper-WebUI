---
name: execute-feature-spec
description: 在 ReMoney 的獨立 worktree 內執行已核定的 Feature Spec，並回報可整合的實作與測試結果。
---

讀取指定的 `docs/specs/*.md`、`AGENTS.md` 與共用 domain 契約。先確認目前 worktree 與 branch，再只修改 Spec 授權的檔案。共用契約需變動時先通知整合 Agent，不在其他分支同步修改。

完成實作與有意義的測試，執行 `npm.cmd run typecheck`、`npm.cmd run build` 和相關測試。回報修改檔案、驗收證據、限制、待整合事項。沒有單獨授權時，不推送、合併或部署。
