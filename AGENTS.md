# Petehub Agent Rules

## Ballpark 畫面驗收（2026-11-02，最高優先）

- Petehub Ballpark 的所有畫面、瀏覽器、碰撞手感與互動驗收一律由使用者本人執行。
- 不得替使用者開啟或控制瀏覽器；不得使用 Playwright、playwright-interactive、CUA、computer-use 或其他瀏覽器自動化。
- 不得自行截圖、圖片比較、視覺回歸或 DOM 視覺檢查。
- 不得為畫面驗證另開 frontend server、登入 fixture、替代帳號環境或隔離 UI server。
- 不得代替使用者點擊、hover、滾動、調整視窗、改 browser zoom、走角色或測試場景碰撞。
- 不得自行宣稱畫面、碰撞、穿模、互動、響應式、路由切換或操作手感通過。只有使用者明確回報通過，才能記錄人工驗收完成。
- UI 修改完成後只回報：改了什麼、檢查網址、最多五項人工測試清單。
- TypeScript、JSON、schema、hash、syntax 或資料契約等 source-only 檢查不等於畫面驗收。
- 小型視覺修正不要反覆執行 typecheck、build 或完整 audit；只有實際涉及契約或編譯風險時才執行必要的單一檢查。
- 使用者表示驗證由他處理時，立即停止所有驗證流程並交回；不得自行開始其他 Slice。

## 工作樹與執行邊界

- 開始前唯讀執行 `git status --short`。既有 dirty worktree 不得 reset、checkout、restore、clean、刪除不相關檔案或覆寫其他修改。
- 修改要小而精準，只碰直接相關檔案；小於 100 行的 UI／碰撞資料修正不得展開大型流程。
- 單一工具超過 60 秒無結果時立即止損並回報。預估超過 10 分鐘時先拆分 Slice 並向使用者說明。
- 未經使用者指示，不得開始 D2.5、D2.6、Section E 或重新製作角色。
- 不得使用 subagent，除非使用者明確要求平行代理工作。
