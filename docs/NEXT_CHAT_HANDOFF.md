# Petehub 新對話交接

更新日期：2026-11-03
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

對話中的「更新區」固定指首頁入口 **Per aspera ad astra** 對應的 `/admin/updates` 頁面；除非使用者另行指定，不要把它解讀為 tracker、交接文件或其他更新流程。

## 2. 當前進度（由 tracker 自動同步）

2026-11-03 最新通道修正：Coach 會議桌右緣與文件櫃之間原只餘 19px，桌椅右側碰撞外緣 x556→536 後改為 39px；角色 footprint 不變。右側繞至下方通道的來源幾何檢查完成，背景／入口／其他場景不動，`collision_overrides`／匯出／manifest 已同步，總量仍 135／82／16；人工手感待驗。D5 source gate v2 早於這次修正，不宣稱新增全 gate／browser PASS，不重跑完整 build/audit。D4 保持 done，D5 保持 in_progress。

2026-11-03 D5 收尾（優先於下方早期紀錄）：最新 **135 collision／82 foreground／16 portals** 已完成 D5 source-only 檢查，零 findings，證據 `petehub_ballpark_d5_source_gate_v2.json`；v1 保留歷史。代理程式／資料工作完成，D5 仍 in_progress／22 of 51，`production_ready=false`。使用者尚需回報 `petehub_ballpark_d5_manual_acceptance_v1.json` 的五項：Team Office 新碰撞、五場景載入／遮擋／邊緣、窄版／可用實機、reduced-motion、缺圖 neutral／silhouette／Static／Classic fallback。詳細網址／步驟見主文件 D5 章節及 JSON；缺圖由使用者 DevTools 暫時封鎖請求，不刪素材、不另開 server。已驗收的 D4／隊色／RLS／Campus 網子／頁寬不重測。未測實機不當作通過；不代驗畫面、不自動進 Section E。

2026-11-03 最新 D5 followup：Team Office Coach 看板／櫃體與 GM 螢幕／櫃體穿模已依使用者要求補兩個 rear-wall-equipment 碰撞。只改獨立碰撞及同步輸出，沒有新觸發功能；現行 **135 collision／82 foreground／16 portals**。已完成針對性 source geometry／入口／走道／匯出一致檢查，使用者人工驗收仍待回報；D5 不結案、D4 不重開。下段 11-02 的 133 數量及 source gate 證據是此次修正前紀錄，不覆蓋新碰撞；不重跑整套 audit/build，不代驗畫面。

2026-11-02 最新補充（優先於後方歷史摘要）：使用者已明確回報 D4 與全部 followup「都通過，進入 D5」。**D4 Done，22／51**；favorite-team 隊色、R／L／S、移除樣本按鈕、圍網與 70vw 頁寬不再待驗。現行 v3 **133 collision／82 foreground／16 portals**。D5 已授權並補齊角色／來源／組合／紋理 source-only gate，零 findings、十項 focused tests PASS，證據在 `data/sample/petehub_ballpark_d5_source_gate_v1.json`。PNG 12.44 MiB，單房＋User RGBA8 估算 18.70 MiB，不是實測 GPU／heap。D5 只剩載入／depth／邊緣、窄版／實機、reduced-motion、缺圖 fallback 的使用者結果；不可重問 D4 功能或同張素材。`production_ready=false`，D5 保持 in_progress，無代理瀏覽器／截圖／操作驗收。FPS／LCP／cleanup 的 E6 尚未開始，不自動進入 Section E。

<!-- PROJECT_PROGRESS:START -->
Tracker updated: 2026-11-03

| Project | Status | Slices | Current direction |
| --- | --- | ---: | --- |
| Batter Comparison & Research | done | 10/10 | Only reopen when a verified exact timing, stance, roster or injury source becomes available. |
| Pitch Quality Leaderboards | in_progress | 12/13 | Keep Stuff+ v2/v5 research-only; allow Location+ v2 to enter shadow monitoring, then proceed to Slice 11 historical backfill/release gate only after prospective checks. |
| RE24 & Leverage Lab | done | 4/5 | Automate or explicitly version the collected reliever reference cutoff. |
| Daily Data Reliability | done | 7/7 | Observe the next 03:00 scheduled run in the selected mode. During the off-season, pause daily game refresh while leaving transactions enabled; use explicit --step or --retry-failed for manual recovery. |
| Project & Slice Tracker | done | 4/4 | For future material work, update the project document and tracker JSON, run the sync script, then keep only recent cross-project changes or live blockers in the concise handoff. |
| Stamina+ Research & Lab | done | 24/24 | Treat Slice 0–19 as complete. Reopen only for a genuinely untouched season validation, or begin the separate Player Health & Availability research with its event-source audit. |
| Pitcher Metric Explorer | done | 1/3 | Slice 2 can add a separate pitcher-game explorer for Game Score, WPA, pitch count and the aligned Quality／Physical／Command game states; it must not mix game rows into the season-level regression. |
| Pitcher Performance State, Collapse & Rebound | active | 28/28 | Keep the strict 2026 replay locked and wait for untouched 2027 prospective rows; compare the frozen Primary and shadow candidates append-only before any production integration. Upgrade the Lab player timeline only after a point-in-time v2 artifact is specified. |
| Player Archetypes & Pitch Strategy | done | 13/13 | Treat Slice 0–6D and 3B as complete. Keep practical_v1 at monitor status while reviewing false positives and adjacent-season stability in the Pitcher Tag Lab; keep Primary Pair hidden unless a later validated definition is easier to interpret. |
| Pitch Strategy Simulation & Game Theory | planned | 0/8 | Begin Slice 0 by freezing the completed Slice 4–6D inputs, chronology, pre/post-pitch boundary and replay vocabulary before adding any new location, transition or simulation model. |
| Catcher Descriptive Metrics | done | 9/9 | No required catcher-descriptive Slice remains. Reopen only if the park-factor source URL/methodology and an exposure-weighted adjustment formula are frozen, or if a separately validated batter-response layer changes the strategy release boundary; otherwise preserve the current no-composite, no-causal-value contract. |
| Game Center Analysis Modules | in_progress | 5/16 | Complete the remaining authenticated browser release gate for Location, Sequence, tags and Movement, including filters, pitcher switching and Savant video on desktop/narrow layouts; then proceed to Slice 4 Catcher Calling Context without reopening completed Replay 3D–3G. |
| Petehub Ballpark Game System | in_progress | 22/51 | User follows petehub_ballpark_d5_manual_acceptance_v1.json: (1) Team Office rear collision and clear front/entries/hall; (2) five-scene loading/depth/atlas edges; (3) narrow layout and available real-device coverage; (4) reduced-motion preview/runtime; (5) missing-character/background fallback via temporary browser request blocking, never deleting PNGs. Report each result and unavailable hardware separately. Do not repeat accepted D4/favorite-team/RLS/Campus net/width work. Only explicit user acceptance can close D5; E6 performance certification remains separate and Section E requires instruction. |
| Player Health & Availability Research | planned | 0/7 | Begin with Slice 0: audit and, if the official source is stable, backfill immutable year-scoped transaction/IL event caches before fitting any alert model. |
| Player Salary & Value | idea | 0/0 | Define trusted salary sources, the value model and slices before implementation. |
<!-- PROJECT_PROGRESS:END -->

上表只作快速導航；完整 Slice deliverable、verification與next step仍以`PROJECT_TRACKER.json`為準。已完成專案不得因新對話自動重跑；新需求若是不同研究問題，先在tracker建立獨立Slice或專案。

## 3. 前端規定

- 研究排行榜與Lab遵守`docs/RESEARCH_DISPLAY_CONTRACT.md`：固定合格母體、tie-aware PR、越高越有利方向、同一績效色階、缺值不補0，搜尋／隊伍篩選不得改變PR母體。
- 玩家列優先顯示正式姓名、頭像與可用的個人頁連結；不可在有既有player master／leaderboard resolver時退回`Player <id>`。
- 好球帶、影片modal、排行榜控制、球員連結等既有互動應重用共用元件；不得在新頁另畫語意較少的簡化版本。
- 每張資料表／面板必須有loading、empty、error狀態；可展開列需支援鍵盤與`aria-expanded`。Ballpark 畫面、瀏覽器、碰撞與互動驗收一律由使用者本人執行；代理不得開啟或控制瀏覽器、截圖、做 DOM 視覺檢查或宣稱人工驗收通過。
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

### 2026-11-02 Petehub Ballpark D2.1–D2.6

- 使用者已完成最新人工驗收：Clubhouse 中央通道不再被沙發／桌子阻擋、Team Office 顯示 `◀ COACH`／`GM ▶`，且 `0.8` camera zoom 與依 viewport 高度調整的頁面尺寸可接受。
- D1、D2.1–D2.6、D3、D4 為 Done；Ballpark 進度為 22／51。D5 source-only PASS、人工 gate 待驗。
- 現行 v2 為 66 collision polygons、36 foreground masks、12 portals；Clubhouse 使用 `clubhouse-corridor-v2.png`，Team Office 有地面方向標示。source-only 技術 PASS 與使用者人工畫面驗收分開記錄。
- 使用者已完成 D2.5 五項操作及 R 出口鍵驗收。D2.6 統一包 `d2-scenes-v3` 已完成：`scene-kit-v3.json`、`petehub_ballpark_scene_manifest_v3.json`、`output/ballpark/scenes-v3/`，共 132 collision／82 foreground／16 portals。runtime／inventory 改讀 v3，舊兩包保留；背景、碰撞、遮擋、spawn 與實際入口目標逐欄等價，沿用既有人工驗收。source-only 匯出可重現／五場景 hash 與 fallback／Nuxt typecheck PASS；沒有新 browser／performance PASS。v3 source 曾逐座標展開為 7,082 行，已改回 351 行且值不變。Section E 尚未開始。
- 使用者於 2026-11-02 指定角色標準：球員／NPC 採 V2（64×96）、User 採 V3（96×144 分件）；概念圖在 `output/ballpark/character-studies/`。D4 已授權並交付實作候選：`avatar-source-v1.json`／`build_ballpark_characters.py` 獨立編寫形狀與關節姿勢，不取概念圖像素作 atlas；兩角色各 48 格（四方向 idle 4@6fps／walk 8@10fps），User 四材質圖層、neutral atlas、0–99 背號及 Moreno 樣本。八張可編輯分件 SVG 在 `output/ballpark/characters-v1/`，hash／來源／匯出工具記於 `petehub_ballpark_character_manifest_v1.json`。User 不綁定 Moreno 外觀；世界高度候選 80、footprint 維持 18×10。
- D4：Character 已接四方向／Idle／Walk／Pause 預覽及 Moreno 樣本切換，現有 Save／Undo／Reset／Cancel／API 沿用；runtime 使用保存外觀與新 atlas，不再正常使用 player-v0，缺件顯示 neutral／silhouette 並保留原外觀。角色匯出可重現與 Nuxt typecheck PASS；外觀品質、手腳動作、比例、保存及桌面／窄版／reduced-motion 由使用者驗收，尚未回報，D4 維持 in_progress／21 of 51。下一步僅等待／修正 D4 回饋；不開始 D5、Section E 或 F4 roster NPC。D5 完整角色組合／紋理／裝置 release gate 尚未跑，`production_ready=false`。
- Ballpark 畫面測試完全由使用者執行；不得使用 Playwright、CUA、computer-use、截圖、另開 UI server、登入 fixture 或替代帳號環境。

### 2026-10-30 Petehub Ballpark A3–B2

- Ballpark 專案已完成 A3 四個 repo-local skills、A4 Classic UI baseline，以及 B1 journey／fallback 與 B2 zone IA contracts。
- `/` 在 H5 決策前維持 Classic 預設首頁；未來 `/ballpark` 是可選 lazy route。走路、fast travel、direct Classic URL 必須等價，Nuxt 保持唯一 auth／router／DOM owner。
- 現有 55 條 Nuxt page routes 已全數盤點：53 條 authenticated routes 分配到 owned zones，2 條 public auth routes 留在 world 外；Video Room 在 E4 前明示沒有 standalone route。
- Ballpark tracker 為 6/40；下一個允許開始的是 B3 visual art bible。尚未加入 Phaser、Babylon 或其他 runtime dependency。
- 主文件第 11 節已凍結版本生命週期：Classic 不追溯亂標 `v0`，Ballpark 正式發布前用 `0.x`、穩定版用 SemVer；產品／build／API／DB／save／simulation／asset 各自版本化，並區分 Classic fallback、artifact rollback 與資料 downgrade。
- B3 visual art bible 已完成；concept board 只作方向參考，正式資產仍由 D2 pipeline 生產。B4 本機互動原型已通過 desktop／narrow／reduced-motion／fallback／locked browser checks，目前版本建議 `0.1.0-design-preview`。
- B4 已由使用者核准並關閉；C1 也已完成註冊主隊、帳號 profile migration、default-avatar/skip bootstrap 與修改主隊流程。8 項 auth/schema/API 測試、Nuxt UTF-8/typecheck 與 Playwright NYY bootstrap 驗證通過；下一步為 C2，不加入 Phaser。
- `AGENT_WORKFLOW.md` 已加入 System Test Agent 契約：產品碼唯讀、隔離 DATA_DIR／DB／cache／ports／build/profile、只報告不自動修；現有前端 E2E／HTTP integration／CI 仍是明確測試缺口。

### 2026-10-24 文件生命週期整理

- 原本約213 KB的交接檔已封存為`docs/archive/PROJECT_HISTORY.md`；現行交接縮為約10 KB，歷史只在需要時搜尋局部內容。
- `PROJECT_STATUS.md`與`WORKBOARD.md`確認為2026-07過時快照，已移至`docs/archive/`並標示superseded；migration／legacy文件已標示reference，不再與current status混用。
- tracker同步腳本現在同時生成`PROJECT_TRACKER.md`與本文件第2節；marker以外的人工規則不會被覆寫。

### 2026-10-24 Game Center／Outing／Stuff

- Game Center名稱解析改用年度`player_master`fallback；Box Score／Feed的姓名、頭像與個人頁連結已接回既有球員呈現契約。
- Game Center已將原本獨立的Pitching頁籤併入Box Score；頂層只保留Feed與Box Score，Box Score內依序呈現Batting與Pitching。
- Batting box改以官方boxscore的`battingOrder`重建棒次與換人層級，保留0 PA守備替補；官方payload以年度／game_pk atomic cache，來源暫時不可用時才退回逐打席輪轉。2026-09-27 HOU–ATH已核對LaMonte Wade Jr.、Nick Allen、Raynel Delgado、Jorge Barrosa、Michael Stefanic、Tommy White與Denzel Clarke均掛回正確棒次。
- Game Center Box Score的AVG與ERA統一使用官方boxscore `seasonStats`，表示截至該場結束的球季累積；其餘PA／AB／H／HR等仍是單場數據。
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
