# Petehub 專案新對話交接文件

更新日期：2026-09-02
專案根目錄：`C:\intern\project_transfer`

> 新對話開始時，請先完整閱讀本文件，將它視為目前專案的主要前情。不要重新驗證「最近已完成並確認」的項目。

## 建議貼到新對話的第一句

```text
請先完整閱讀 C:\intern\project_transfer\docs\NEXT_CHAT_HANDOFF.md，將它視為目前專案的權威前情。
不要重做文件中標記為已完成、已驗證的修改。
回答使用繁體中文，先簡短說明要改哪些檔案，再直接執行；修改後只回報異動檔案與必要驗證結果。
若會修改全域共用元件、共用 CSS、共用資料 schema 或模型契約，必須先明確提醒。
```

---

## 一、使用者工作習慣與重要規則

- 使用繁體中文。
- 可以直接做，不要反覆問已能從程式或資料判斷的問題。
- 修改前簡短說要改哪裡；修改後說明異動檔案與驗證結果。
- 小修改不要過度驗證。通常前端 typecheck 加一項精準測試就足夠。
- 不要反覆啟動瀏覽器或等待瀏覽器工具；使用者可協助肉眼確認畫面。
- 不要重新測試本文件已標記完成且使用者已確認正常的項目。
- 若要改全域共用元件、全域 CSS、共用變數、API schema 或模型契約，必須先提醒。
- 不可修改舊 Streamlit 專案，除非使用者明確要求。
- 舊專案只供參考和舊資料產線使用；正式功能全部放在新專案。
- 優先考慮可維護性、模組化、前後端分離、API schema、產品流程與多頁共用。
- 工作樹可能已有使用者修改，不可覆蓋或回復不相關內容。
- 搜尋優先用 `rg` / `rg --files`，編輯優先用 `apply_patch`。
- 使用者說「開起來」通常代表啟動網站並打開首頁；可先檢查 `open-homepage.cmd`。
- 進入任何現有頁面修改前，先檢查實際 DOM／元件結構與資料回傳，不可只看截圖猜配置。
- 新增或修改 dashboard panel 時使用直角邊框；不要再新增圓角 panel／圓角外框。資料點、百分位軌道等視覺編碼不受此限制。
- `StrikeZoneScatter.vue`、`HeatmapBlendControl.vue` 與 discipline filters 已被投手／打者頁共用；修改前必須確認兩邊，不可刪除或讓任一側好球帶變成空圖。

### 最近一次效率問題

前一輪約 26 行修改耗時接近 50 分鐘，主因是過度驗證及瀏覽器輸出卡住。使用者已明確要求停止重複測試。後續應採用：

1. 先讀精準相關檔案。
2. 做局部修改。
3. 執行 typecheck 或 targeted test。
4. 立即交付，不再為已通過項目反覆開瀏覽器。

---

## 二、專案位置與技術架構

### 正式專案

- 根目錄：`C:\intern\project_transfer`
- 前端：`C:\intern\project_transfer\frontend`
- 後端：`C:\intern\project_transfer\backend`
- 資料：`C:\intern\project_transfer\data`

### 舊 Streamlit 專案（只讀參考）

- 舊程式：`C:\Users\郭睿承\Desktop\實習個案\abs2025\claude`
- 舊資料：`C:\Users\郭睿承\Desktop\實習個案\abs2025\data`

### 技術

- 前端：Nuxt 3、Vue 3、TypeScript
- 後端：FastAPI、Python
- 資料：DuckDB、CSV、Parquet
- 方向：前端負責 UI、圖表、互動與狀態；後端負責資料查詢、計算、模型與更新工作。

---

## 三、目前主要頁面

- `/`：Petehub 首頁、球隊入口、球員／影片搜尋、推薦影片。
- `/pitchers`：投手站與 selector。
- `/pitcher-personal`：Overview、Rotation、Outing Report、Stuff、Sequence、Discipline。
- `/comparison/pitcher`：兩位投手比較。
- `/comparison/period`：同投手不同期間比較。
- `/rotation/starter`、`/rotation/bullpen`：先發與牛棚工作量／疲勞。
- `/games/today`：每日比賽與 pitching lines。
- `/teams/[teamId]` 或現有球隊路由：各隊主頁。
- `/batters` 與打者個人頁：打者 leaderboard、趨勢、discipline/location。
- `/fielders/catchers/sequence`：捕手與搭配投手 sequence。
- `/lab/stuff`：Stuff+ Lab。
- `/lab/location`：Location+ Lab。
- `/lab/pitching`：Pitching+ Lab，目前仍屬持續開發區。
- 後台 Data Operations：由首頁 `per aspera ad astra` 入口進入。

---

## 四、資料來源與更新產線

### 主要資料

- 逐球資料庫：`data/MLB{year}/mlb_{year}.duckdb`
- 影片 lookup：`pitch_play_lookup`
- 官方投手單場 line cache：`pitcher_game_lines`
- 2026 line CSV：`data/MLB2026/mlb_2026_pitcher_game_lines.csv.gz`

### Derived export

舊站的衍生產線包含：

- `derived_data_exports.py`
- `export_derived_outing_reports.py`
- 輸出到 `data/derived`
- `outing_reports_{year}`
- `outing_pitch_type_metrics_{year}`
- `outing_usage_splits_{year}`
- `outing_location_points_{year}`
- `model_scores_pitcher_{year}`
- `model_scores_pitch_type_{year}`
- `derived_manifest`

### 已知更新風險

- DuckDB 可能因其他 Python 程序而 lock。
- 曾出現不同 connection configuration 無法同時開同一資料庫。
- 呼叫舊站 script 時可能發生 `No module named 'claude'`，需正確設定 root／`PYTHONPATH`。
- 不要假設網頁顯示的最新日期等於資料庫最新日期；需要時應分別查 pitch、video、official lines、derived scores。
- 更新逐球後，Stuff+、Location+、Pitching+ 與 game lines 的推論／聚合也必須串入自動流程。

---

## 五、視覺與棒球定義

### 好球帶

- 紅色框才是 Zone% 使用的 strike zone。
- 紫色框是 heart zone，不是 Zone%。
- `STRIKE_ZONE_BOX = (-0.83, 1.5, 1.66, 2.0)`
- `EXPANDED_SHADOW_BOX = (-1.33, 1.17, 2.66, 2.66)`
- `EXPANDED_CHASE_BOX = (-2.0, 0.5, 4.0, 4.0)`
- `EXPANDED_HEART_X = (-0.67, 0.67)`
- `EXPANDED_SHADOW_VERTICAL_EXTENSION = 0.33`

### 球種正規化與配色

- Four-Seam：紅
- Changeup：綠
- Sinker：橘
- Cutter：棕
- Sweeper：棕金
- Slider：黃
- Curveball：藍
- Splitter：青綠
- `4-Seam Fastball`、`Four-Seam`、`four-seam fastball` 必須正規化為同一球種。
- Outing Report 中 Sweeper 顯示為 `ST`。
- plate location 視角有時需要 `plate_x * -1`，改圖前必須確認捕手／投手視角。

---

## 六、Plus 模型目前的正式契約

詳細文件：`docs/PLUS_METRICS_CONTRACT.md`

### Stuff+

- 公開模型為 Peter Stuff+。
- 以球速、轉速、轉軸、水平／垂直位移、出手點、Extension、Arm Angle、球種、投手左右等球質特徵建模。
- 目標為 12 類 outcome 的預測機率，再轉換為預期 Run Value。
- 正式評分時以共同情境降低實際落點、球數和局面差異。
- Lance Brodowski 版本只保留為互動式 calculator／研究對照，不應成為第二套全域輸出。

### Location+

- 與 Stuff+ 分開建模。
- 只使用實際進壘位置、球種、球數、投打左右、出局數、壘包狀況、個人好球帶高度等位置／情境資訊。
- 不輸入球速、轉速、位移等球質資訊。
- Location+ 不是 `Pitching+ - Stuff+` 的殘差。

### 逐球與聚合

- 逐球 tooltip／圖表和單場、球種、球季彙總使用同一個底層 xRV 定義。
- 聚合頁面可為了小樣本穩定性加入 shrinkage，但不可另造不相容算法。
- 目前 aggregate contract 為 `location_plus_aggregate_v2`。
- Location+ 聚合資料：`data/derived/location_plus_scores.duckdb`。
- 先驗強度目前包含 season 50、side 25、season-pitch-type 50、outing 15、outing-pitch-type 15。

### Plus 分數轉換

```text
raw_plus = 100 + 10 × (league_mean_xrv - observed_xrv) / league_sd_xrv
reliability = pitches / (pitches + prior_pitches)
reported_plus = 100 + reliability × (raw_plus - 100)
```

- 100 為聯盟平均。
- 分數越高代表預期失分越低、對投手越有利。

### Pitching+

詳細規劃：`docs/PITCHING_PLUS_DESIGN.md`

- 應是獨立的「完整投球」第三模型，而非 Stuff+ 與 Location+ 的簡單相加或殘差。
- 使用球質、實際位置與投球前情境，預測相同 12 類 outcome。
- 訓練年度：2021–2024；驗證：2025；測試：2026。
- 基礎版不應直接加入實際 outcome、Run Value、打球結果或投手姓名等洩漏欄位。
- 球序／時間序列建議作 challenger model，加入前一球球種、球速／位置差、PA 中第幾球等，再與 base model 比較。
- `/lab/pitching` 的 UI 與資料仍可能有未完成或回歸問題，進入時先做精準檢查，不要假設目前完全正常。

---

## 七、最近已完成且禁止重做的修改

### 1. Zack Littell 跳錯球員

檔案：`frontend/pages/pitcher-personal.vue`

- 修正只變更 query 時，頁面仍使用舊 pitcher state，導致 Zack Littell 跳成 Adrian Del Castillo。
- 加入 personal／outing fetch request version guard，舊 request 不可覆蓋新 request。
- route watcher 現在同步：`year`、`role`、`team`、`pitcher_id`、`game_pk`、`tab`。
- Zack Littell ID：`641793`。
- 測試使用的 `game_pk=825048` 能回到正確投手與報告。

### 2. Batter 15-game AVG 起點

檔案：`frontend/components/batter/BatterTrendChart.vue`

- 第 1–14 場不畫 AVG15。
- 從第 15 場才開始顯示。
- x 軸改用實際可見點，避免從 0 或空值瞬間跳高。

### 3. Rotation／Fatigue MA5 起點

檔案：`backend/app/services/rotation_service.py`

- 同球種 `MA5` 改為 `rolling(5, min_periods=5)`。
- 前四顆同球種有效資料保持空值，第五顆才開始畫。

### 已完成驗證

- `npm --prefix frontend run typecheck` 已通過。
- `backend/tests/test_rotation_service.py`：7 passed。
- Zack Littell API 與 outing 已確認正確。
- 使用者已肉眼確認正常。

**不得在新對話重新跑以上瀏覽器驗證或重做修改。**

---

## 八、Batter Lab 狀態與下一階段

`/batters/lab/stuff-attack` 的第一版已完成，包含多球種群組篩選、投手左右手、Stuff+ band、可選 X/Y 指標、球員頭像散點圖、按需回歸與 Rules 說明。不要依照本節舊文字重做 Stuff Attack MVP。

Batter Swing Timing / Miss Distance V1 已於 2026-08-22 完成。權威規劃文件：`docs/BATTER_SWING_TIMING_ROADMAP.md`；該文件包含 Statcast 定義、V2–V3、Batter Personal／Team page 回接方式，以及棒次、守位、platoon 與打序預測 backlog。

### Swing Timing V1 已完成範圍

- 新頁面 `/batters/lab/swing-timing`，並已接入 Batter Lab hub。
- 新 API `/api/batters/lab/swing-timing`，讀取獨立的 batter timing summary cache，不覆蓋 pitcher timing 檔。
- 支援年度、球種群組、單一球種、投手左右手、打者左右打與最低揮棒數。
- 核心 leaderboard 與 Horizontal／Timing／Vertical 三維欄位切換。
- 球員列可展開三維 summary bars，並連回 Batter Personal；沒有逐次 bins 時不畫偽造 KDE。
- 2023–2026、All/L/R cache 已建立；targeted backend tests 與 Nuxt typecheck 已通過。

### Swing Timing V2.1–V2.6 已完成範圍（2026-08-22）

- Pitcher Team 已啟用，使用本機 DuckDB 精確逐球 matchup；不會假裝 Savant batter summary 能按對手球隊切分。
- `All pitcher teams` 為 Savant summary mode；選定球隊則為 `matchup_event`，頁面會明確標示模式與不可用欄位。
- 球員列採 lazy load 呼叫 `/api/batters/lab/swing-timing/player`。
- V2.2：球員與聯盟的 Horizontal／Timing／Vertical summary comparison。
- V2.3：球種弱點矩陣。
- V2.4：條件 competitive swing 棒速相對球員整季基準的 Gear Change。
- V2.5：Batter Personal Overview 已嵌入精簡 Timing Fingerprint，顯示球員值、聯盟值與差距；timing 請求不阻塞原 Overview。
- V2.6：Batter Personal 已新增完整 Swing Timing tab，重用三維 summary、球種矩陣與 Gear Change，並支援球種群組、單一球種、投手左右手以及保留條件的 Lab 深連結。
- Batter Personal 的 location pitch points 已保留 `play_id`／`video_url`，點球可開啟 Savant 影片；同時接入逐球 `pitch_stuff_plus` 與 `location_plus_pitch`。目前 2026 兩項 Plus cache 完整，舊年份沒有本機分數 cache 時顯示缺值，不可假造。
- Timing leaderboard 使用固定 `colgroup` 控制欄寬與換行；個人頁 Pitch Matrix 字體與外層表格一致，Gear Change 由三欄改為四欄，卡片寬度約為原本 75%。
- 2023 下半季至 2026 可做 summary 與 Bat Tracking；現有逐球 `miss_distance` 只有 2026。2023–2025 的 matchup mode 仍可做棒速、Whiff、Competitive Rate、Swing Length 與 attack metrics。
- 尚未完成的是月度趨勢與 exact Savant distribution payload；只有 summary 時仍不可宣稱為完整分布。

### V3 Team Hitting Intelligence 已完成範圍（2026-08-22）

- Team page 已新增獨立 Hitting intelligence 區塊與 sticky-nav 入口，既有投手內容保留。
- 新 compact API：`/api/teams/{team_id}/hitting-intelligence`；由球隊頁另行 lazy fetch，不擴大原本 team dashboard payload。
- `Team Timing Map`：On Time × Perfect Contact 頭像散點、聯盟平均線、樣本外圈與 Batter Personal 深連結。
- `Team Miss Profile`：Horizontal／Timing／Vertical 球隊組成與 MLB 基準。
- `Pitch-family Matchup Matrix`：Fastball／Breaking／Offspeed，支援 Perfect、On Time、Whiff、Miss、RV/100 切換與相對聯盟配色。
- `Lineup Skill Strip`：PA 前九名的 competitive swing 平均棒速、Swing Contact、On Time、Platoon edge；只是 PA-based nine，不是官方或模型預測打序。
- 球棒速度使用 Statcast competitive swing 定義；RV/100 是有 bat tracking 揮棒的描述性 run value，未做 park／pitch quality 等調整。
- 球隊頁 grid 已改為 `minmax(0, 1fr)`，避免矩陣或卡片把整頁撐寬。
- `backend/tests/test_team_hitting_intelligence_service.py`、UTF-8 檢查與 Nuxt typecheck 已通過；2026 AZ 球隊頁的實際渲染、矩陣切換和個人頁連結已由瀏覽器驗證。

### Stuff Attack 已完成範圍

- 逐球 Stuff+ join 與 `<95`、`95–104`、`105–114`、`>=115` 分層。
- 球種群組多選、投手左右手與最低看到球數篩選。
- Swing、Chase、Contact、Whiff、HardHit、Barrel、xwOBA、RV 與 Bat Tracking 指標。
- Raw／adjusted view、response curve、球員頭像散點與按需回歸。
- 中文 Rules、UTF-8 檢查與 targeted tests。

後續 Stuff Attack 擴充應服從 `docs/BATTER_SWING_TIMING_ROADMAP.md` 的資料線界線：目前只有逐球 Bat Speed 與 Miss Distance 能精確和 Stuff+ 交叉；不可把 Savant 已彙總的 X/Y/Z timing 假裝成逐球資料。

### Batter Personal 最新完成狀態（2026-09-02）

- 打者個人頁的 Overview、Swing Timing、Discipline & zones 本輪已告一段落，不要在下一對話重做版面。
- Discipline 只保留一個 `Swing map`；舊的 `Pitch map / Location profile / Batter-side view for the active filters.` 重複區塊已移除。
- Discipline 版型已依投手區配置：左側為共用 `HeatmapBlendControl` 與好球帶，右側為 summary cards 與垂直 filters。
- `Swing map` 可切換 `Bat speed`／`Choice`，共用 `StrikeZoneScatter`，球點可保留選取與影片連結。
- Overview 已完成左右對調：KPI、Timing Fingerprint 與 WPA／5-day wOBA 圖在左側，Percentile Rankings 在右側；兩欄底部對齊。
- Batter Personal 本輪涉及的 panel、tabs、filters、modal 與主要容器已改為直角邊框。
- 修正 discipline API 將 `All` 誤當成實際 CSV filter 的問題；測試投手 API 可回傳 1,675 個 pitch location points，不再是空白好球帶。
- 最近驗證：Nuxt typecheck 通過、production build 通過、相關 backend tests 32 passed、`git diff --check` 通過。
- 內建瀏覽器在最後一輪沒有可用 browser instance，因此沒有最後的像素級截圖驗證；程式、API 與 HTTP smoke check 已完成。

### 下一個明確任務：Batter Period Comparison Slice 0–3

使用者已要求下一輪直接完成 Slice 0–3。上一輪只建立工作計畫，**尚未開始撰寫 Batter Period Comparison 程式碼**，不要誤標為已完成。

#### Slice 0 — 封存與基線

- 先檢查目前 dirty worktree；近期修改橫跨 batter personal、共用好球帶、後台更新、catcher 與首頁，不可覆蓋或回復不相關內容。
- 更新本 handoff／`BATTER_SWING_TIMING_ROADMAP.md` 的實際狀態。
- 在確認 staged 檔案範圍後建立 Git checkpoint；不要盲目 `git add .`，也不要用 destructive reset／checkout。

#### Slice 1 — Batter Period Comparison 骨架

- 建立打者版 period comparison 頁面與入口。
- 呈現方式盡量沿用現有投手 `/comparison/period`：同一打者、Period A／Period B、兩組日期、共用情境篩選、A/B/delta 的閱讀順序。
- 不必強行抽成投打共用頁；可重用真正通用的 selector、好球帶、heatmap control 與格式化元件。
- 新增獨立 batter API schema／service／route，避免把投手 comparison service 塞入大量 batter-only 分支。

#### Slice 2 — 兩期間核心打擊指標

- 第一批至少涵蓋樣本與產出：PA、AB、OPS、wOBA、xwOBA、AVG、OBP、SLG。
- 擊球品質：Avg EV、Max EV、Barrel%、HardHit%、SweetSpot%（欄位存在才顯示）。
- 選球／接觸：Swing%、Chase%、Contact%、Whiff%、K%、BB%、K-BB%。
- 每項顯示 Period A、Period B、差值、樣本 denominator；百分點差要標為 `%`／`pp` 的正確語意，不可混用。
- 日期與篩選變更後由後端重算，前端不下載整季資料自行聚合。

#### Slice 3 — 雙好球帶 Heatmap

- Period A／Period B 並排，各只呈現一個相同規格的好球帶。
- 可透過按鈕切換 `Bat Speed` 與 `Choice`。
- `Choice` 是各位置的 Swing frequency；藍色代表較少出棒、紅色代表較常出棒，不表示好壞。
- `Bat Speed` 只使用有 bat tracking 的 competitive／tracked swings，低樣本區域保持淡色。
- 使用共用 `HeatmapBlendControl` 控制散點到 heatmap 的混合程度，A/B 必須使用同一色階 domain 才能直接比較。
- 盡量重用 `StrikeZoneScatter.vue`，但修改共用元件前必須同時 smoke check 投手與打者個人頁。

### 後續待辦：Batter Research Slice 4–8

Slice 4–8 仍是原定 roadmap 的一部分，只是不併入下一輪已指定的 Slice 0–3。完成 0–3 後應依序接續，不可遺漏。

#### Slice 4 — Bat Tracking 期間比較

- 在 Batter Period Comparison 加入 Avg Bat Speed、Fast Swing%、Competitive%、Swing Length、Squared-Up% 與 Blast%。
- 所有數值必須同時顯示 Period A、Period B、差值與有效 tracked swings；沒有該欄位時顯示 unavailable，不以 0 取代缺值。
- 棒速與 competitive swing 必須沿用 Statcast 定義；不能因日期篩選而偷偷改變球員整季 competitive threshold，除非來源明確就是動態重算。
- 加入 pitch family、單一球種、投手左右手、打者左右打等 split，但優先重用 Slice 1 已建立的篩選契約。
- 驗收重點：A/B denominator 一致可追溯、2023 半季限制有提示、無追蹤資料不參與平均。

#### Slice 5 — Timing／Miss Distance 期間比較

- 加入 Avg Miss Distance、Flawed Swing%、Perfect Contact%、Centered%、On Time%、Lined Up%，以及 Tied Up／Flail、Late／Early、Over／Under 組成。
- 2026 可使用本機逐球 `miss_distance` 做任意日期比較；其他年份缺逐球 coverage 時必須標示 unavailable／summary-only。
- X/Y/Z alignment 只有取得可按日期切割的 exact payload 才能做真正 Period A/B；現有 full-season summary 不可拆成任意期間。
- UI 必須把「真正的期間差」與「球季 summary 參考值」分開呈現，不能放在同一 delta 欄造成誤解。
- 驗收重點：分母、coverage、資料模式與方向定義清楚；不生成推測 KDE 或偽造逐揮棒分布。

#### Slice 6 — Exact Visual Payload 與 Batting Stance

- 先研究並保存 Savant Visual 使用的 bins／逐揮棒 X、Y、Z payload、平滑方式與正負號規則；來源不能驗證時維持現有 summary bars。
- 若取得 exact payload，再建立三張可追溯分布：Tied Up–Centered–Flail、Late–On Time–Early、Over–Lined Up–Under。
- 另行盤點 Batting Stance 所需資料：Depth in Box、Distance off Plate、Distance Between Feet、Stance Angle、左右腳位置、At Pitch Release、At Bat-Ball Intercept 與 Intercept Point。
- 兩組腳印必須依資料語意標示為 stance／release／intercept，不可自行猜成擊球前後。
- 站位頁先完成 source audit、欄位 coverage 與座標方向驗證，再製作動畫或腳印視覺；沒有可靠資料就停在資料盤點。
- 驗收重點：每張視覺可追溯原始 payload；左右打鏡像、座標與英吋單位經測試確認。

#### Slice 7 — Team Batting 描述性研究

- 建立逐場 lineup／batting order／defensive position／DH／PH 資料層，先驗證 game-level coverage。
- 棒次影響：依 1–9 棒比較 PA、AVG、OBP、SLG、wOBA、K%、BB%，並與球員本人基準比較。
- 守位／角色影響：比較同一打者擔任 C、其他守位、DH、PH 時的打擊表現，例如平常捕手改打 DH。
- Platoon matchup：依對手投手 L/R 顯示各打者的 observed split、樣本數與 reliability／shrinkage。
- 球隊首頁只放 compact 視覺摘要，完整研究放在 Batter Lab／Team Batting 子頁；不可再把長表直接塞滿首頁。
- 所有結果先定義為描述性關聯，不將棒次、守位或 DH 狀態解讀為因果。

#### Slice 8 — 打序預測與最佳化

- 前置資料：probable starter、active roster、傷兵／不可用狀態、近期實際打序、守位覆蓋、休息規則與 platoon 特徵。
- 第一階段做 lineup prediction：輸出每位球員先發機率、1–9 棒位置機率與 2–3 組候選打序；不得宣稱為官方先發名單。
- 第二階段才做 lineup optimization：在守位與可用球員限制下，以 run expectancy／模擬估計各候選打序的預期得分。
- 預測模型與最佳化器分開評估；描述性 leaderboard 不可直接當作 batting order model。
- 球隊頁呈現預測打序、platoon edge 與主要不確定性；正式打序公布後可比較預測誤差。
- 驗收重點：時間切分驗證、避免使用賽後資訊、顯示機率與不確定性、守位限制永遠有效。

### 完整 Slice 順序

1. Slice 0：封存與基線。
2. Slice 1：Batter Period Comparison 骨架。
3. Slice 2：兩期間核心打擊指標。
4. Slice 3：Bat Speed／Choice 雙好球帶 Heatmap。
5. Slice 4：Bat Tracking 期間比較。
6. Slice 5：Timing／Miss Distance 期間比較。
7. Slice 6：Exact visuals 與 Batting Stance 資料／視覺。
8. Slice 7：Team Batting 棒次、守位、角色與 Platoon 描述性研究。
9. Slice 8：打序預測與最佳化。

### Period Comparison 資料限制

- Bat Tracking 自 2023 All-Star break 後才可用；2023 是半季資料。
- 任意日期區間的逐球 `miss_distance` 目前本機只有 2026 可精確完成；這不在 Slice 0–3 的必交範圍。
- Centered／On Time／Lined Up 等 X/Y/Z 目前主要來自 Savant summary，不能假裝能按任意日期精確切割。
- Slice 0–3 不包含 exact Savant distributions、站位頁、棒次／守位研究或 lineup prediction。
- 所有新 panel 使用直角邊框；桌面版需在 100% 瀏覽器縮放下看見主要比較內容，窄螢幕再改為單欄。
- 驗收以 targeted backend tests、UTF-8 檢查、Nuxt typecheck、A/B API smoke check，以及投手／打者好球帶沒有回歸為準。

---

## 九、其他尚未完全收尾的區域

- Pitching+ Lab：曾出現 404、空資料、版面超寬、outings trend 空白與 leaderboard 欄位問題；進一步修改前要先確認目前實際程式狀態。
- 全域頁面寬度：使用者偏好 100% 瀏覽器縮放即可看見主要內容，不應靠把整頁做得更寬或讓右側被切掉。
- Petehub 全域首頁按鈕：曾多次與頁面標題重疊；若再修改，應檢查 layout 層級而非每頁各自補 margin。
- 後台網站結構圖：使用者希望 Data Operations 頁可看到全站路由、API、共用模組與依賴狀態，目前是否完成需先查程式。
- Games／Game Score／official lines：歷史上曾因 derived 或 pitcher lines 更新落後而出現空白或 0，更新流程要保持串接。
- Team payroll、transactions、injuries：FanGraphs 抓取易受動態頁面或表格結構影響，應保留快取、錯誤隔離與可重跑機制。

---

## 十、可參考的專案文件

- `docs/PLUS_METRICS_CONTRACT.md`：Plus 指標正式契約。
- `docs/PITCHING_PLUS_DESIGN.md`：Pitching+ 設計。
- `docs/API_CONTRACTS.md`：API 契約。
- `docs/ARCHITECTURE.md` 或根目錄 `ARCHITECTURE.md`：架構參考。
- `docs/AGENT_WORKFLOW.md`：協作流程。
- `docs/PROJECT_STATUS.md`：部分內容較舊，只可作歷史參考；本交接文件的最新狀態優先。

---

## 十一、新對話第一輪建議行動

不要先大範圍掃描或重做 Batter Personal。直接：

1. 完整閱讀本文件與 `docs/BATTER_SWING_TIMING_ROADMAP.md`。
2. 執行 `git status --short`，辨識目前未提交檔案；先完成上節 Slice 0 的安全 checkpoint。
3. 精準閱讀 `frontend/pages/comparison/period.vue`、`backend/app/services/comparison_service.py`、現有 comparison schemas／routes，以及共用 `StrikeZoneScatter.vue`／`HeatmapBlendControl.vue`。
4. 完成 Batter Period Comparison Slice 1–3；不要順手開始後續的 Slice 4–8。
5. 修改共用好球帶後，必須各驗證一次 pitcher period/personal 與 batter personal，不可只驗證新頁。
6. 最後只跑 UTF-8、targeted backend tests、frontend typecheck 與必要 smoke checks；不要再次用長時間瀏覽器等待拖慢交付。
