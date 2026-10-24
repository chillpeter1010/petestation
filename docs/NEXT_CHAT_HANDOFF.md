# Petehub 新對話交接

更新日期：2026-10-24
專案根目錄：`C:\intern\project_transfer`

本文件只保存「接手下一個對話所需」的短摘要。專案完整歷史已移至 `docs/archive/PROJECT_HISTORY.md`，不得在每次開新對話時整份載入。

## 1. 開始順序與權威來源

開始工作前：

1. 用 UTF-8 完整閱讀`docs/NEXT_CHAT_HANDOFF.md`：目前跨對話限制、近期修改與接手注意事項。
2. 用`Get-Content -Raw -Encoding UTF8`解析完整`docs/PROJECT_TRACKER.json`，但先只輸出專案摘要與本次相關project；它是專案、Slice、狀態與下一步的唯一權威來源，不必把整份JSON印進對話。
3. 用 UTF-8 完整閱讀`docs/AGENT_WORKFLOW.md`：前後端、文件生命週期與更新規則。
4. 只讀本次工作直接相關的契約或專案主文件；不要預載全部 `docs/` 或歷史封存。

`docs/PROJECT_TRACKER.md`由 JSON 自動生成，不可單獨手改。若摘要、舊報告或歷史紀錄與 tracker／現行契約衝突，以 tracker 與現行契約為準。

開始前一律執行唯讀 `git status --short`。工作樹可能有未提交修改；不得 reset、checkout、restore、clean 或覆寫不相關內容。所有中文 Markdown／JSON 使用 UTF-8；PowerShell 讀取時明確使用 `Get-Content -Raw -Encoding UTF8`。

`C:\Users\郭睿承\Desktop\實習個案\abs2025\claude`與`C:\轉移\mlbpython`只可唯讀參考，除非使用者明確授權修改。

## 2. 當前進度（由 tracker 自動同步）

<!-- PROJECT_PROGRESS:START -->
Tracker updated: 2026-10-24

| Project | Status | Slices | Current direction |
| --- | --- | ---: | --- |
| Batter Comparison & Research | done | 10/10 | Only reopen when a verified exact timing, stance, roster or injury source becomes available. |
| Pitch Quality Leaderboards | in_progress | 12/13 | Keep Stuff+ v2/v5 research-only; allow Location+ v2 to enter shadow monitoring, then proceed to Slice 11 historical backfill/release gate only after prospective checks. |
| RE24 & Leverage Lab | done | 4/5 | Automate or explicitly version the collected reliever reference cutoff. |
| Daily Data Reliability | done | 7/7 | Observe the next full scheduled run. Use --retry-failed or one or more --step arguments when a source or downstream stage fails; do not rerun completed heavy stages unnecessarily. |
| Project & Slice Tracker | done | 4/4 | For future material work, update the project document and tracker JSON, run the sync script, then keep only recent cross-project changes or live blockers in the concise handoff. |
| Stamina+ Research & Lab | done | 24/24 | Treat Slice 0–19 as complete. Reopen only for a genuinely untouched season validation, or begin the separate Player Health & Availability research with its event-source audit. |
| Pitcher Metric Explorer | done | 1/3 | Slice 2 can add a separate pitcher-game explorer for Game Score, WPA, pitch count and the aligned Quality／Physical／Command game states; it must not mix game rows into the season-level regression. |
| Pitcher Performance State, Collapse & Rebound | active | 28/28 | Keep the strict 2026 replay locked and wait for untouched 2027 prospective rows; compare the frozen Primary and shadow candidates append-only before any production integration. Upgrade the Lab player timeline only after a point-in-time v2 artifact is specified. |
| Player Archetypes & Pitch Strategy | done | 12/12 | Treat Slice 0–6D as complete. If this research continues, either expose only the aggregate threshold-labeled entropy/supported-deviation panels in the Lab, or open a separately scoped batter-response slice with chronological validation before using true exploitability language. |
| Pitch Strategy Simulation & Game Theory | planned | 0/8 | Begin Slice 0 by freezing the completed Slice 4–6D inputs, chronology, pre/post-pitch boundary and replay vocabulary before adding any new location, transition or simulation model. |
| Catcher Descriptive Metrics | done | 9/9 | No required catcher-descriptive Slice remains. Reopen only if the park-factor source URL/methodology and an exposure-weighted adjustment formula are frozen, or if a separately validated batter-response layer changes the strategy release boundary; otherwise preserve the current no-composite, no-causal-value contract. |
| Player Health & Availability Research | planned | 0/7 | Begin with Slice 0: audit and, if the official source is stable, backfill immutable year-scoped transaction/IL event caches before fitting any alert model. |
| Player Salary & Value | idea | 0/0 | Define trusted salary sources, the value model and slices before implementation. |
<!-- PROJECT_PROGRESS:END -->

上表只作快速導航；完整 Slice deliverable、verification與next step仍以`PROJECT_TRACKER.json`為準。已完成專案不得因新對話自動重跑；新需求若是不同研究問題，先在tracker建立獨立Slice或專案。

## 3. 前端規定

- 研究排行榜與Lab遵守`docs/RESEARCH_DISPLAY_CONTRACT.md`：固定合格母體、tie-aware PR、越高越有利方向、同一績效色階、缺值不補0，搜尋／隊伍篩選不得改變PR母體。
- 玩家列優先顯示正式姓名、頭像與可用的個人頁連結；不可在有既有player master／leaderboard resolver時退回`Player <id>`。
- 好球帶、影片modal、排行榜控制、球員連結等既有互動應重用共用元件；不得在新頁另畫語意較少的簡化版本。
- 每張資料表／面板必須有loading、empty、error狀態；可展開列需支援鍵盤與`aria-expanded`。桌面與窄版至少做一次實際頁面視覺檢查。
- 公開導覽、Lab入口與頁面歸屬以`frontend/config/siteArchitecture.ts`及現行router為準。Vue只負責UI狀態與呈現，棒球公式留在backend service／versioned artifact。

## 4. 後端、資料與模型規定

- API契約以`docs/API_CONTRACTS.md`為準；Stuff+／Location+以`docs/PLUS_METRICS_CONTRACT.md`為準；各研究線公式與限制以該專案唯一主文件為準。
- 計算需保留原始分子、分母、樣本數、coverage、資料版本與source fingerprint。局數一律用outs計算，只有顯示時轉成棒球局數記法。
- 長時間更新使用immutable／resumable cache、atomic replace、durable progress與可針對失敗步驟重試；不得因一次重按就覆寫有效完成品或重跑全部重型步驟。
- 缺資料要標示unavailable、limited或明確fallback；不得用補值製造不存在的精確度。回歸、模型與描述性統計不得混稱，未通過時間外驗證的結果不得包裝成因果價值或production score。
- 真實大型資料與runtime secrets只留本機忽略路徑。舊Streamlit與舊資料來源不是現況權威；使用前先核對現行service、artifact與測試。

## 5. 自動更新與文件維護

- 修改`docs/PROJECT_TRACKER.json`後執行：`python backend/scripts/sync_project_tracker.py`。它會重建`PROJECT_TRACKER.md`並只替換本文件第2節的marker區塊，不改寫人工維護規則與近期事項。
- 日常資料更新、retry、heartbeat、freshness與單年度歷史回填以tracker中的`daily-data-reliability`、`docs/API_CONTRACTS.md`的Data Operations章節及`/admin/updates`為準。後端工作可在頁面關閉後繼續，但backend process必須保持運行。
- 同一小專案只維護一份人工可讀主文件；Slice是主文件內章節，不建立新的頂層`SLICE*.md`。精確執行結果存JSON／Parquet／manifest／immutable snapshots。
- 完成實質工作時：更新專案主文件、tracker JSON、執行同步、補本文件的「近期修改／未解事項」。詳細舊紀錄只追加到`docs/archive/PROJECT_HISTORY.md`，不要再膨脹本文件。

## 6. 近期修改與未解事項

### 2026-10-24 文件生命週期整理

- 原本約213 KB的交接檔已封存為`docs/archive/PROJECT_HISTORY.md`；現行交接縮為約10 KB，歷史只在需要時搜尋局部內容。
- `PROJECT_STATUS.md`與`WORKBOARD.md`確認為2026-07過時快照，已移至`docs/archive/`並標示superseded；migration／legacy文件已標示reference，不再與current status混用。
- tracker同步腳本現在同時生成`PROJECT_TRACKER.md`與本文件第2節；marker以外的人工規則不會被覆寫。

### 2026-10-24 Game Center／Outing／Stuff

- Game Center名稱解析改用年度`player_master`fallback；Box Score／Feed的姓名、頭像與個人頁連結已接回既有球員呈現契約。
- Game Center與Outing Report改用共用`StrikeZoneScatter`，保留Stuff+、Location+、Stamina與影片identity；2026影片lookup損壞cache可重建，CSV輸出改atomic replace。2026-09-27 HOU–ATH實測332／332球有`video_url`。
- Pitcher Personal Stuff已重排資訊區；movement／outcome表按需展開，Stuff+ consistency移至圖下方，Pitch Out在後端計分、coverage、variability及前端圖表全部排除。
- 驗證已通過：相關backend tests 20 passed、Nuxt typecheck、UTF-8與`git diff --check`。尚未完成登入後的最終像素級browser視覺檢查。

### 接手限制

- Catcher Descriptive Metrics Slice 0–8已完成，主文件為`docs/CATCHER_DESCRIPTIVE_METRICS.md`。Park factor僅完成候選正規化；在來源URL、方法與exposure-weighted公式凍結前不得回寫指標。
- Player Archetypes & Pitch Strategy Slice 0–6D已完成，主文件為`docs/PLAYER_ARCHETYPES_PITCH_STRATEGY.md`。Pitch Strategy Simulation是獨立planned專案，不得因相關而直接重跑舊Slice。
- Pitcher Performance State維持research-only並等待真正未見的2027資料；不得用retrospective 2026結果開production gate。

## 7. 歷史與文件索引

- 完整過往進度、研究限制與事故：`docs/archive/PROJECT_HISTORY.md`（需要特定舊問題時才搜尋／局部讀取）。
- 2026-07舊產品盤點：`docs/archive/PROJECT_STATUS_2026-07.md`（已淘汰）。
- 2026-07 Pitcher Personal workboard：`docs/archive/WORKBOARD_2026-07.md`（已淘汰）。
- 文件分類、生命週期與過時稽核結果：`docs/AGENT_WORKFLOW.md`。
