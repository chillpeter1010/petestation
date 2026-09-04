# Batter Swing Timing / Miss Distance Roadmap

更新日期：2026-09-02
狀態：V1、V2.1–V2.6、V3、Batter Comparison Slice 0–8 已完成至目前可驗證的本機資料邊界；exact X/Y/Z distributions 與真實 batting stance 仍因來源缺失維持 unavailable

## 一、已確認的 Statcast 定義

所有比例均以符合追蹤條件、排除短打嘗試後的揮棒為基礎；實作前仍需以 Savant 匯出結果確認實際 denominator 與 contact event taxonomy。

- `Centered`：球棒 barrel 在水平方向距離球 `±4 inches` 內。
- `On Time`：球棒相對完美 timing 在 `±7 ms` 內。
- `Lined Up`：球棒在垂直方向距離球 `±2 inches` 內。
- `Flawed Swing %`：所有揮棒中，打者揮空，且該揮棒不屬於 `Lined Up`、`Centered`、`On Time` 任一類的比例。也就是三項均未達標的揮空；不是 `Perfect Contact %` 的補集。
- `Perfect Contact %`：所有揮棒中，打者有碰到球，且該揮棒同時為 `Lined Up`、`Centered`、`On Time` 的比例。
- `Competitive Rate`：打者最快 90% 的揮棒，加上棒速至少 60 mph 且造成至少 90 mph 擊球初速的揮棒，占全部揮棒的比例。此類資料自 2023 All-Star break 起提供。
- `Miss Distance`：球棒遠離雙手的 barrel half 與球在最接近瞬間的距離，單位 inches；短打嘗試排除。

### 實作前仍需確認

1. `Perfect Contact` 的 contact 是否包含 foul、foul tip 與所有 in-play contact，或另有排除條件。
2. `Competitive Rate` 的個人最快 90% 門檻是固定使用球員整季基準，或會隨頁面篩選重算。
3. `miss_distance` 排行榜平均值的實際樣本是否只包含有追蹤的 whiff；目前本機逐球欄位幾乎只在 whiff 有值。
4. X/Y/Z 正負號、左右打鏡像與 Savant 顯示用絕對值的規則。
5. Savant `Visual` 的 bins、平滑方式與是否另有逐揮棒／分箱 payload；只有 summary CSV 不足以精確重建平滑分布。
6. 排行榜資格、最小 swings、四捨五入與同名次規則。

## 二、資料線界線

### A. Savant batter summary

用途：復刻 Timing / Miss Distance 排行榜與打者三維 timing profile。

目前已確認 `type=batter` 可取得：

- 球員、球隊、球季、打擊側、球種、揮棒數
- Miss Distance、Whiff Rate、Competitive Rate
- Flawed Swing、Perfect Contact
- Tied Up / Centered / Flail 與條件平均距離
- Late / On Time / Early 與條件平均毫秒
- Over / Lined Up / Under 與條件平均距離

限制：資料已按打者與篩選條件彙總，不能事後和本機逐球 Stuff+ 精確 join。

### B. 本機 Statcast pitch-level data

用途：研究每次揮棒的 bat speed、swing length、attack metrics、Miss Distance、球種、球速、位置、球數、投手左右手、Stuff+ 與結果。

可回答：

- 面對特定球種／Stuff+ band，棒速比球員本人基準快慢多少。
- 高 Stuff+ 是否改變棒速、Swing Length、Whiff、Miss Distance、Contact 與 Run Value。
- 左右投、球數、位置與球速調整後的 `Adjusted Bat-Speed Delta`。

限制：目前沒有逐揮棒 X/Y/Z swing timing offset，因此不能把 Early / Late / Over / Under 精確接到 Stuff+。

## 三、三版本規劃

## V1 — Savant-compatible Batter Timing Leaderboard

完成日期：2026-08-22

實際交付：年度／球種群組／單一球種／投手左右手／打者左右打／打者球隊／投手球隊／最低揮棒數／賽季 PA 門檻篩選、核心排行榜、Horizontal／Timing／Vertical 三維切換、球員列展開摘要、中文 Rules 與打者個人頁連結。PA 拉條為 5–700、每格 5、預設 100。Pitcher Team 採本機逐球精確篩選；選擇球隊後切到 `matchup_event` 模式，不偽造該資料線缺少的 X／Y／Z timing 欄位。排行榜支援實際數據／PR 切換與可關閉的紅藍 heatmap；PR 以當前篩選後全體合格打者計算，並統一為越高越好，Swings 則保留為不染色的實際樣本數。表頭支援中文定義提示與升冪／降冪排序；首批渲染 200 位並可逐批展開。後端改用向量化加權聚合與依來源檔修改時間失效的選擇快取。V1 使用 Savant summary cache 呈現真實彙總值，不偽造逐次揮棒或 KDE 分布。

目標：先建立定義正確、可驗證、可使用的打者版排行榜，不假造平滑分布。

### 頁面與功能

- 新增 `/batters/lab/swing-timing`，並由 Batter Lab hub 進入。
- 篩選：season、pitch group、pitch type、pitcher hand、batter side、minimum swings。
- 排行榜主欄位：Avg Miss Distance、Flawed Swing%、Perfect Contact%、Swings、Whiff Rate、Competitive Rate。
- 三組可切換欄位：
  - Horizontal：Tied Up%、Avg Tied-up Dist、Centered%、Flail%、Avg Flail Dist。
  - Timing：Late%、Avg Late ms、On Time%、Early%、Avg Early ms。
  - Vertical：Over%、Avg Over Dist、Lined Up%、Under%、Avg Under Dist。
- Rules 抽屜：使用本文件已確認的繁體中文定義與資料限制。
- 球員列可展開簡單三維 profile，以比例條、條件平均位置與聯盟基準呈現；V1 不畫偽造 KDE 曲線。
- 每列連回打者個人頁，保留 year、batter_id 與當前 pitch filter。

### 資料與 API

- 建立 batter 專用年度 CSV/cache 與 meta，不覆蓋既有 pitcher timing 檔。
- API：`GET /api/batters/lab/swing-timing`。
- 回傳來源、資料日期、filters、qualification、rows 與 league averages。
- 百分比統一在 API contract 指明是 `0–1` 或 `0–100`，前端不得猜測。

### 驗收條件

- 至少抽查 20 個打者 × 球種列，主要欄位與 Savant 顯示誤差只允許來自四捨五入。
- Flawed、Perfect、Competitive tooltip 與 Rules 定義一致。
- 空年份與小樣本顯示明確，不回傳假 0。
- UTF-8 檢查、targeted backend tests、frontend typecheck 通過。

## V2 — Exact Visuals + Batter Personal Integration

### 目前完成範圍（V2.1–V2.6，2026-08-22）

- V2.1：Pitcher Team 精確逐球對戰模式，支援 30 隊並保留打者球隊、球種、左右手與樣本門檻。
- V2.2：三維 alignment summary，以球員比例條和聯盟 marker 呈現；明確標為 summary，不假造 KDE。
- V2.3：球種矩陣，並列 Miss、Flawed、Perfect、Centered、On Time、Lined Up 與 Whiff。
- V2.4：Bat-Speed Gear Change，以符合當前條件的 competitive swing 平均棒速減去打者整季 competitive swing 平均棒速。
- V2.5：Batter Personal Overview 新增精簡 Timing Fingerprint，並列 On Time、Centered、Lined Up、Perfect 與 Miss Distance，顯示球員值、聯盟值與差距。
- V2.6：Batter Personal 新增完整 Swing Timing tab，支援球種群組、單一球種與投手左右手，並共用三維 summary、球種矩陣與 Gear Change 元件；可攜帶年度、球員與篩選條件往返 Lab。
- 球員詳細資料採點開列後才載入，避免增加排行榜第一次載入成本。
- Personal Overview 的 timing request 不阻塞原有首頁資料；完整 Timing tab 僅在使用者切入時載入。
- 尚未完成：月度趨勢，以及 Savant exact bins／逐揮棒 X／Y／Z payload。

資料年份：2023 下半季至 2026 都可使用 Savant summary 與 Bat Tracking；2023 為半季。現有本機逐球 cache 的 `miss_distance` 只有 2026，2023–2025 的精確投手球隊模式會顯示缺值提示，但棒速、揮棒長度、attack metrics、whiff 與 competitive rate 仍可計算。

目標：把 Timing 從排行榜提升為可解讀的球員技能輪廓，並回接打者個人頁。

### 視覺化

- 若取得 Savant bins／逐揮棒 visual payload，復刻三張分布圖：
  - Tied Up ↔ Centered ↔ Flail
  - Late ↔ On Time ↔ Early
  - Over ↔ Lined Up ↔ Under
- 若仍只有 summary，改採誠實的 diverging bars／lollipop，不使用推測的平滑曲線。
- 加入聯盟平均、樣本數、可靠度與 pitch-type small multiples。
- 加入 Bat-Speed Gear Change：條件棒速相對個人整季基準的 mph 差。

### 回接打者個人頁

目標頁：`frontend/pages/batter-personal.vue`。

- Overview：放一張精簡 `Timing Fingerprint`，顯示 On Time、Centered、Lined Up、Perfect、Miss Distance。
- 新增 Timing 區段／tab：三維圖、球種矩陣、左右投 split、年度／月份趨勢。
- Stuff / Location 研究互通：由個人頁帶 batter_id 前往 Stuff Attack 或 Swing Timing Lab；Lab 可帶篩選回個人頁。
- 個人診斷文字只描述資料，例如「相對聯盟更常晚、主要垂直 miss 為 Under」，不宣稱因果。

### 共用元件候選

- `BatterTimingFingerprint.vue`
- `SwingTimingDimensionChart.vue`
- `BatterPitchTimingMatrix.vue`
- `BatSpeedGearChange.vue`

只有在 Lab 與 Personal 確實共用後才抽離元件，避免先做過度抽象。

### 驗收條件

- Lab 與 Personal 使用同一 API 定義與格式化規則。
- 任一圖都顯示 denominator、樣本數與資料起始限制。
- Summary 模式不宣稱為完整分布；Exact 模式必須能追溯 bins／原始 payload。

## V3 — Team Hitting Intelligence + Event-level Integration

完成日期：2026-08-22

### 目前完成範圍

- 新增獨立 compact API：`GET /api/teams/{team_id}/hitting-intelligence`，不把全聯盟完整 timing payload 併入既有 team dashboard。
- 球隊頁新增獨立 Hitting intelligence 導覽與區塊，原有 Rotation、Bullpen、Pitch arsenal 等投手內容保留。
- `Team Timing Map`：On Time × Perfect Contact 頭像散點，聯盟平均虛線，外圈以樣本穩定度呈現；球員可深連到 Batter Personal。
- `Team Miss Profile`：Horizontal、Timing、Vertical 三個方向的球隊組成與 MLB 平均 marker。
- `Pitch-family Matchup Matrix`：Fastball／Breaking Ball／Offspeed，支援 Perfect、On Time、Whiff、Miss Distance、RV/100 切換與相對聯盟的紅藍配色。
- `Lineup Skill Strip`：依賽季 PA 排列前九人，顯示 competitive swing 平均棒速、Swing Contact、On Time 與 Platoon contact edge；明確標示不是官方或預測先發打序。
- competitive swing 棒速依最快 90%，加回棒速至少 60 mph 且擊球初速至少 90 mph 的 Statcast 定義計算；RV/100 使用同批有 bat tracking 的實際揮棒，未做環境校正。
- 修正 team dashboard 單欄 grid 的 min-content 溢出，V3 矩陣不再把頁面撐出容器。
- 2026 AZ 實際頁面已完成 DOM、桌面版視覺、矩陣切換與深連結驗證；targeted backend tests、UTF-8 與 Nuxt typecheck 通過。

目標：讓球隊首頁同時具有投手與打者決策內容，並把研究轉成可快速閱讀的 roster 視覺化。

### 回接球隊首頁

目標頁：`frontend/pages/teams/[teamId].vue`。

- 新增 Hitting 區塊，不只增加另一張長表。
- `Team Timing Map`：隊內打者以 On Time × Perfect Contact 呈現，球員頭像為點、樣本大小為透明度／外圈。
- `Pitch-family Matchup Matrix`：打者 × Fastball / Breaking / Offspeed，顯示 timing edge、whiff 與 run value。
- `Lineup Skill Strip`：預計先發九人的棒速、Contact、On Time、Platoon edge 小型視覺卡。
- `Team Miss Profile`：全隊 Tied-up / Flail、Early / Late、Over / Under 組成，和聯盟平均比較。
- 圖上球員均連到 Batter Personal；標題連到完整 Batter Lab。
- Team dashboard API 只回傳該隊 compact summary，不把全聯盟完整 timing payload塞進球隊首頁。

### 進階研究

- 若未來取得逐揮棒三維 timing，加入 Stuff+ Timing Penalty：高 Stuff+ 對 On-time、Centered、Lined-up、Perfect 與 RV 的影響。
- 建立調整後個人基準，控制 pitch type、velocity、location、count、pitcher hand 與 batter identity。
- 對小樣本採 reliability／shrinkage，介面同時顯示原始樣本。

### 驗收條件

- 球隊首頁打者視覺與投手內容在資訊量上更平衡，但首頁只保留摘要。
- 所有 matchup／ranking 顯示資料日期、對手投手手別與可用球員範圍。
- 預測與描述性統計分開標示，不把 lineup ranking 當成官方先發名單。

## Batter Comparison Slice 0–8（已完成至本機資料邊界）

完成日期：2026-09-03

- Slice 0：以明確 staged 檔案清單建立 `daeb568` checkpoint，封存既有 Batter Personal 與同批修改。
- Slice 1：建立 `/batters/comparison` → `/batters/comparison/period` 層級並由 `/batters` 進入；舊 `/comparison/batter-period` 相容導向新路徑。後端使用獨立 `/api/batter-comparison/period/*` schema、service 與 route。
- Slice 2：支援 PA、AB、OPS、wOBA、xwOBA、AVG、OBP、SLG、Avg/Max EV、Barrel%、HardHit%、SweetSpot%、Swing%、Chase%、Contact%、Whiff%、K%、BB%、K-BB%，每項均回傳 A、B、B−A 與兩側 denominator；百分率差明確使用 pp。
- Slice 3：Period A/B 共用 Bat Speed／Choice 切換、heatmap blend 與同一色階 domain。Choice 表示 swing frequency；Bat Speed 只納入依球員整季門檻判定的 competitive tracked swings，低樣本區保持淡色。
- 共用 `StrikeZoneScatter` 只新增可選 shared metric domain；未傳入時保留原本單圖自動 domain 行為。
- Slice 4：加入 Avg Bat Speed、Fast Swing%、Competitive%、Swing Length、Squared-Up% 與 Blast% 欄位，以及 pitch family／球種／投手左右手／打者左右打 split。Competitive threshold 固定使用球員整季基準；來源沒有 Squared-Up／Blast 時維持 unavailable。
- Slice 5：2026 `miss_distance` 可做真正 A/B；2023–2025 顯示 unavailable。Flawed／Perfect／Centered／On Time／Lined Up 與三方向組成只以獨立 season summary reference 呈現，不進任意日期 delta。
- Slice 6：完成 source audit。現有資料可呈現 intercept／attack geometry，但不可標成站位；exact X/Y/Z bins、腳印、stance depth、off-plate distance、stance angle 均因無可靠欄位維持 unavailable。
- Slice 7：新增 `/batters/comparison/team`，從逐場 PA sequence 重建 1–9 棒、從 fielder IDs 重建觀察到的守位，提供棒次產出、投手手別 split、樣本與 reliability。無法區分 DH／PH 時明確標記 unknown。
- Slice 8：新增 `/batters/comparison/lineup`，使用最近 20 場實際先發重建先發／棒次機率，提供 recent consensus、latest observed、run-expectancy candidate 三方案與 empirical PA-outcome simulation。沒有 active roster、傷兵與 probable starter 時不宣稱官方預測。
- 不可回頭重做已完成的 Batter Personal 或 Slice 0–8；後續若要解除 unavailable，必須先取得可驗證的新來源。

## 四、待完成清單：Team Batting / Lineup Research

以下項目先列入 backlog，不併入 Swing Timing V1：

| 項目 | 預計內容 | 主要風險／前置需求 | 狀態 |
| --- | --- | --- | --- |
| 棒次影響 | 依 1–9 棒拆分 PA、AVG、OBP、SLG、wOBA、K%、BB%，並比較球員本人基準 | 棒次是教練選擇結果，不能直接解讀為因果 | Completed（descriptive） |
| 守位／角色影響 | 重建觀察到的守位；無官方 lineup role 時不拆 DH／PH | fielder IDs 可驗證；DH／PH 缺來源 | Completed（source-gated） |
| Platoon matchup | 依使用者選擇的對手投手 L/R 顯示 observed split 與 reliability | 無 probable starter、active roster、傷兵 | Completed（manual hand） |
| 打序預測 | 最近 20 場先發與 1–9 棒位置機率、候選方案 | 不宣稱官方打序 | Completed（research mode） |
| 打序最佳化 | empirical PA-outcome simulation 比較候選打序 | 只使用觀察到的守位 coverage | Completed（scenario mode） |
| 球隊首頁 Hitting 區 | 將 Timing Map、Matchup Matrix、Lineup Skill Strip 接到 team dashboard | 已使用獨立 compact API，避免阻塞既有 team dashboard | Completed |

## 五、建議實作順序

1. 完成 V1 資料 cache、API、定義測試與排行榜。
2. 確認 Savant Visual payload；能取得才做 exact curves，否則使用 summary visual。
3. 抽出已被 Lab 與 Personal 共用的視覺元件，完成 V2。
4. 先把 compact hitter summary 接入 Team page，再進行 lineup／position 資料盤點。
5. 最後才做 lineup prediction 與 optimization，避免在 roster／position 資料未穩定前建立模型。
