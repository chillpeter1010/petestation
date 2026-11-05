# Game Center Analysis Modules

> 狀態：In progress
> 更新：2026-11-06
> Tracker project：`game-center-analysis-modules`

## 2026-11-06 呈現方案否決與 F2 重建規劃

使用者否決整張照片平移／縮放、任意前景位移、固定 PNG 打者；11-06 新加的下移／白線框也沒有獲得接受。現行 `PitchReplayChart.vue` 仍有此候選實作，本輪只更新規劃，未撤接／回退或修改程式。停止生成更多 PNG 姿勢或疊加螢幕位移，不再請使用者核准被否決的方案。下節 11-05「新稿待驗」是歷史交付敘述，不代表現行設計被接受。

單一實作 owner 為 Ballpark **F2.1–F2.7，全部 Planned**，詳細表在 `PETEHUB_BALLPARK_GAME_SYSTEM.md` 最上方：保存契約／引擎決策 → 同世界場地／真相機／球路 → 可編輯 rig → 確定性動作 clock → 實測 swing 資料 adapter → 共用整合／gate → 原設施業務 parity。母站 Game 與 Pitcher Personal 消費同一按需載入元件，Ballpark 只沿既有 canonical 入口，不把 Phaser 園區改成三維。Three.js 是優先候選，尚未安裝／選定 production；原 G 動作 Lab 收斂為後期進階擴充，避免重複 renderer／rig／clock。

**保留而非重做：** 原 3H 已接受的選場／逐球／影片／16 項熱圖／PR／Outside、原球路公式與 source identity；最新 local 真名解析、姓名 Personal 連結、收合 guide、exact-count 投打 API／卡片。後一批 UI 尚無單獨明確驗收，F2.1 先封存行為與數據契約，不要求為即將替換的貼圖畫面重驗整套資料。12 項 focused backend tests 與 source/typecheck 是前批證據，不等同人工通過。

**出手／揮棒契約：** 球從每球 release_pos_x/y/z 開始，投手丘／踏板與模型同世界，手部對該點定位；不從丘中心地面發射，不為配合背景改球路。bat speed／length／attack angle／direction／tilt 與部分平均姿態不構成逐幀球棒路徑；generic 動畫、season average、measured swing 需分開標記，來源不足顯示 unavailable，未來有實測才畫相應軌跡。時間軸需含 pre-pitch／release／plate-or-contact／post-pitch，pause／seek／replay 可重現；沒有接觸資料不得為看起來打到而改結果。

**未收尾但非全數硬性前置：** 本專案 Location(1)／Sequence(2)／Tags(3)／Movement(3B) 仍 in_progress，原 verification 的人工缺口未被 3H 接受覆蓋；影片補抓按鈕已交付，這輪沒有全季補齊／播放證據。不要自行重跑其測試或補抓。重構前建議先保護 dirty worktree、建立經審閱 checkpoint，確認最新非 renderer UI；E6 的 2D runtime gate 與新 renderer F2.6 gate 分開，開發可先隔離原型，正式 release 不可跳過量測／使用者驗收。本輪沒有 engine install、資產生成、資料回填、瀏覽器或產品碼修改。

## 最新共用 In game 延伸（2026-11-05，新增畫面待驗）

原 3H 熱圖／PR／Outside 已由使用者接受，Done 不重開。這輪新增：投打姓名由本機 player lookup／master 補齊，姓名連至 Personal；熱圖說明與視角 guide 預設收合。捕手畫面下方並列投手／打者 exact pre-pitch count 季度卡片，投手看該側打者、打者看該側投手，按球種列樣本、Mix／球速／Swing／Contact／Whiff／AVG，展開可看 wOBA、HardHit 與分母。這是各自整季同側同球數，**不是兩人交手紀錄或本場累計**；缺資料不補零。新 API 契約見 `API_CONTRACTS.md`。

視覺使用 `catcher-stadium-v2.png` 及 `catcher-batters-v4.png`。打者依使用者最後提供的白色大學球衣照片之姿勢／肩線／手持棒位置製作通用右／左打獨立靜態素材；不代表真實球員身形或動作。v2 舊姿勢與生成但未接入的 v3 背向稿被使用者否決，保留來源，不當作核准。完整生成 prompt、來源路徑及 hash 記於 `petehub_in_game_catcher_redesign_v1.json`，使用內建 imagegen。

捕手視角改為**整幅畫面同層 pan／zoom**：背景、打者、本壘板、好球帶、熱圖、球路與球一起移動；不再只改前景 3D 距離。拖曳／方向鍵平移、滾輪共同縮放、Home／Reset view 復原；捕手不提供 Low angle，投手視角保留原 3D orbit。球路原始物理座標與重建公式不改。好球帶增加深底與青色虛線輔助外框（不是額外判決區或新的 shadow 分類），原 17 吋邊界不變。

資料來源檢查：前批 12 項 focused backend tests 通過；來源／編譯檢查不等於畫面驗收。這輪新姿勢、整體縮放、收合說明、姓名連結與兩張資料卡待使用者驗收，未開瀏覽器、截圖或執行代理操作測試。舊待驗／通過記錄僅對應各自當時版本。

## 1. 目標與邊界

本專案把既有研究與個人頁能力，以單場 `game_pk` 為邊界接回 Game Center。已確認的入口是：

1. 比分板下方的 Location 頂層頁籤
2. 比分板下方的 Sequence 頂層頁籤
3. 比分板下方的 Movement 頂層頁籤
4. Pitch Replay 頂層頁籤
5. 投手姓名 hover／focus 的 Tags 小卡
6. 尚待獨立 Slice 驗證的 Catcher Calling

Stamina 是第五個、必須先通過角色與覆蓋率 gate 的輔助模組。打者端保留一至兩個分析入口，但先在 Lab 驗證，再決定是否加入正式 Box Score。

所有模組遵守以下共通規則：

- Box Score 仍是單場事實入口；展開內容必須固定在同一個 `game_pk`，不能混入同日另一場或整季逐球。
- 過濾器與圖表優先重用既有元件與契約，不另造一套同名但定義不同的計算。
- 選定比賽與球員後才 lazy load，避免第一次載入整場時同時運算所有投手與打者。
- 整季或跨季資料必須標明 `season`、`role`、`as_of`、版本與樣本數；不可讓使用者誤認為是該場表現。
- 無資料維持 unavailable，不補零；小樣本顯示分母與限制，不用單場排名或強弱標籤。
- Pitch Out 延續既有規則，排除 Stuff+、Location+、Stamina 與相關圖表計分。
- Catcher 模組只能描述實際 pitcher-catcher pairing 與觀察到的選擇；`fielder_2` 不是「誰下暗號」的證據。
- 不輸出 individual best pitch、因果 catcher value 或真實 exploitability。

## 2. Pre-Slice 資料覆蓋稽核（2026-10-24）

本節是在 Slice 0 開始前完成的唯讀稽核；不代表任何 Slice 已開始或完成。

### 2.1 Game-scoped 原始欄位

排除 Pitch Out 且要求有效 `pitch_type` 後，Location／Sequence／Catcher pairing 的原始鍵值可用度很高：

| Year | Valid pitches | Location `plate_x/z` | Sequence identity/count | `fielder_2` | EV on BBE | Bat speed on swings | Miss distance on whiffs |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 709,452 | 99.97% | 100.0% | 100.0% | 99.73% | 0.0% | 0.0% |
| 2022 | 708,116 | 100.0% | 100.0% | 100.0% | 99.61% | 0.0% | 0.0% |
| 2023 | 717,627 | 100.0% | 100.0% | 100.0% | 99.75% | 42.32% | 0.0% |
| 2024 | 709,170 | 100.0% | 100.0% | 100.0% | 99.73% | 93.09% | 0.0% |
| 2025 | 709,855 | 100.0% | 100.0% | 100.0% | 99.67% | 97.12% | 0.0% |
| 2026 | 713,813 | 100.0% | 100.0% | 100.0% | 99.59% | 97.28% | 97.38% |

`game_pk + at_bat_number + pitch_number` 在六季有效球中沒有重複鍵，pre-pitch balls／strikes 也沒有超出合法範圍。2021 只有 210 球缺 Location；其餘年份為零。

2026 的 Movement `pfx_x/z` 為 713,811／713,813（99.9997%），Release Point `release_pos_x/z` 為 713,812／713,813；20,788 個 pitcher-game 全部至少有一顆可畫，因此兩者不需要另建資料模型。

主要問題不是 Location／Sequence 原始資料缺失，而是不同衍生模組的年代不同：

- Stuff+／Location+ 的 `stamina_lab` cache：2022–2026 每季約 99.6–99.7%；2021 尚無對應 artifact，與歷史 Plus backfill 仍停在 2021 相符。
- Stamina trait／expected path：目前只有 2026 cache 有值；2022–2025 雖有逐球 Plus，兩欄仍全空。
- Catcher observed pairing：六季 raw `fielder_2` 都完整；player master 僅在 2021／2023–2025 有 20／29／21／41 球未命中，2026 全數命中。這不代表能辨識真正下暗號者。
- Catcher strategy bridge：只有 2026；713,853 個 model decisions 中，582,185（81.56%）通過預設 supported-choice gate，覆蓋 111 位 catcher contexts，但只能做 aggregate observed diagnostics。
- Pitcher tags：2026 有 tag 的 player-role 比例為 SP 275/377（72.9%）、RP 557/741（75.2%）；按投球數加權則為 98.8%／97.1%。未分配者主要是低量樣本，不應硬套 league tag。

### 2.2 打者單場樣本與年代限制

Contact 原始欄位 2021–2026 都接近完整，但單場 rate 的分母仍小。2026 共 49,604 個 batter-games：94.2% 至少有 1 顆 BBE、77.8% 至少 2 顆、只有 52.3% 至少 3 顆。因此 0–2 BBE 應優先顯示事件值與分母，不顯示成穩定 rate。

Swing tracking 的限制更明確：

- 2021–2022 沒有 bat tracking。
- 2023 從 07-14 才開始，僅 1,069/2,430 場有 bat speed，不能當完整球季。
- 2024／2025／2026 分別有 2,341／2,425／2,419 場有 tracking；2026 batter-games 中 90.8% 至少有 3 個 tracked swings。
- Miss Distance 只有 2026；71.2% 的 2026 batter-games 至少有 1 個 tracked whiff。
- 本地逐球目前沒有可用的 Squared-Up／Blast 欄位，既有 period service 也明確回傳 unavailable；不得把 season summary 冒充成該場逐球結果。

### 2.3 Artifact freshness

`mlb_2026.duckdb` 更新於 2026-10-24、`stamina_lab_2026.parquet` 更新於 10-16，但 Physical／Command game artifacts 仍停在 10-03。Physical 的舊 contract 因此仍寫 arm-angle supported coverage 56.8%。使用目前 Stamina source 做無寫入 dry-run 後，arm-angle supported coverage 為 76.3%，eligible games 仍為 4,572；代表重建可修正 component coverage，但不會消除短先發與 late-pitch 門檻。

開始 Slice 0 前應先正式重建並 fingerprint Stamina Physical／Command artifacts；若重建後主要驗證指標漂移，必須先重跑既有 validation gate，再談 Game Center 整合。

### 2.4 Pitch Replay 軌跡與身高稽核（2026-10-27）

Pitch Replay 不能只用 Movement 的 `pfx_x/z` 或 Release Point 的 `release_pos_x/z` 畫二次曲線。逐球至少需要以下三組欄位：

- 軌跡起點：`release_pos_x`、`release_pos_y`、`release_pos_z`
- 50 呎狀態：`vx0`、`vy0`、`vz0`、`ax`、`ay`、`az`
- 落點驗證：`plate_x`、`plate_z`；`sz_top`、`sz_bot` 用於顯示該打者好球帶

`release_speed`、`release_extension`、`pitch_type/name`、`p_throws`、`stand`、count／result、`game_pk + pitcher + at_bat_number + pitch_number + pitch_uid` 與 `play_id/video_url` 是顯示、篩選及影片互動欄位。`release_extension` 可做合理性檢查，但 `release_pos_y` 已存在時不是重建軌跡的必要欄位。

排除無有效 `pitch_type` 與 Pitch Out 後，實際 coverage 如下：

| Year | Replay-eligible pitches | 完整 release + velocity + acceleration | Coverage | Pitcher-games 至少一顆可重播 |
|---|---:|---:|---:|---:|
| 2021 | 709,452 | 709,242 | 99.9704% | 21,524 / 21,531 |
| 2022 | 708,116 | 708,077 | 99.9945% | 20,869 / 20,869 |
| 2023 | 717,627 | 717,626 | 99.9999% | 20,625 / 20,625 |
| 2024 | 709,170 | 709,170 | 100.0000% | 20,693 / 20,693 |
| 2025 | 709,855 | 709,852 | 99.9996% | 20,868 / 20,868 |
| 2026 | 713,813 | 713,812 | 99.9999% | 20,788 / 20,788 |

2026 唯一缺少完整軌跡的有效球，是 2026-09-05 game 823419 Martín Pérez 的一顆 CH；該球仍有 `plate_x/z`，但 Replay 必須顯示 unavailable 或靜態落點，不可插補假軌跡。代表場 2026-09-27 HOU–ATH 的 332 筆事件中有 328 顆有效 pitch，328／328 都有完整軌跡與影片 identity；其餘四筆是 Brady Basso 的 pitchless automatic balls／intentional-walk events，不應製造動畫。

座標契約必須特別處理 Statcast 的不同基準：`release_pos_*` 是實際出手點，`v*0/a*` 則以 50 呎狀態使用。先由 release point 回推 50 呎的 X/Z，再從 50 呎積分到本壘前緣 `y = 17/12 ft`；不能直接把 release position 與 `v*0/a*` 當成同一時間點。以 2026 全部 713,812 顆完整球驗證，回推後預測落點的 X／Z 同時在實際 `plate_x/z` 2 英吋內為 99.812%，3 英吋內為 99.947%。完整「實際出手點到本壘前緣」飛行時間中位數為 0.4151 秒，最大 1.4234 秒；eephus／position-player pitches 必須取二次方程式最小正根，不能用固定 `< 1 second` gate。超過 3 英吋的少數球逐球標記 `limited_trajectory`，不以人工拉線強制貼合落點。

本地所有 DuckDB 的 schema 都沒有 `height` 欄位；年度 `player_master` 也只有 ID、姓名、角色、球隊與出賽日期／事件欄位，現有 JSON cache 未找到球員身高。Pitch Replay MVP 不需要投手身高，因為球的實際三維起點已由 `release_pos_x/y/z` 決定。身高只有在畫出具比例的投手全身或骨架時才有幫助，但身高仍無法推回跨步、軀幹角度、手臂姿勢或真正投球動作。MVP 因此只畫球、出手點、軌跡、本壘與好球帶；若日後加入人物，需另建可追溯的 player bio cache，缺值使用明確標示的 generic silhouette，不得由 release height 反推身高。

## 3. Slice 狀態

| Slice | 狀態 | 交付內容 | 主要驗收 |
|---|---|---|---|
| 0 · Game-scoped contract and reuse audit | Planned | 凍結 `game_pk`、球員、角色、時間邊界、來源版本、lazy-load 與共用 filter schema；盤點可直接重用的 API／元件 | 雙重賽隔離、game row reconciliation、欄位來源表、錯誤／空資料狀態、代表比賽 fixtures |
| 1 · Pitcher Location | In progress | `Location` 是比分板下方的頂層頁籤；進入後以本場投手下拉選單切換，重用 `StrikeZoneScatter`、影片 identity、逐球 tooltip 與 Personal filters | game/pitcher filter、Pitch Out 排除與 payload tests 已通過；待登入後桌面／窄版互動與影片點擊驗證 |
| 2 · Pitcher Sequence | In progress | `Sequence` 是比分板下方的頂層頁籤；共用同一個投手下拉選單，並提供 count mix、follow-up 與 conditioned branch | PA／換投／跨場邊界與 payload tests 已通過；待登入後桌面／窄版互動驗證 |
| 3 · Pitcher Tags | In progress | 移除 `Tags` 頂層頁籤；滑鼠停留或鍵盤聚焦投手姓名時，以小卡顯示 released Slice 3 core tags，並追加 Lab-first Pronation／Supination 與左右打 family-usage profiles | Adapter tests 覆蓋 core／practical 合併、無標籤與過往同角色參考；必須標示 full-season snapshot 與 Lab-first，待登入後視覺驗證 |
| 3A · Shared Game Pitch Shape API | Completed | 一次回傳該投手該場的 Movement、release coordinates、篩選欄位、Plus/Stamina context 與影片 identity | Service/payload tests、代表場 824948 實際讀取與 Pitch Out 排除通過；Release Point UI 移除後仍保留相容 payload |
| 3B · Pitcher Movement | In progress | 新增 `Movement` 頂層頁籤，共用本場投手下拉選單與前端 filters，直接重用 `MovementChart` | API/service tests 與 Nuxt typecheck 通過；待登入後 Scatter/Average、Stuff+、投手切換、影片與窄版驗證 |
| 3D · Pitch Replay data and coordinate audit | Completed | 凍結重播必要欄位、50 呎座標轉換、落點 closure gate、慢速球與身高邊界 | 2021–2026 全量 coverage、2026 全量落點 closure、game 824948 與所有 DuckDB／player master schema 已核對 |
| 3E · Pitch Replay trajectory API | Completed | 新增 game/pitcher lazy replay payload，在後端以版本化公式輸出時間化 3D path、逐球狀態、filters 與影片 identity | game/pitcher scope、缺欄位、3 英吋 closure、30–40 mph 正根、Pitch Out／pitchless 排除與實際 HTTP response 均已驗證 |
| 3F · Pitch Replay SVG MVP | Completed | 新增 `Replay` 頂層頁籤，共用本場投手選單；單一透視場景可切換 Pitcher／Catcher、疊加該打席或全場其他球，並以拖曳或鍵盤微調鏡頭 | 播放／暫停／重播／scrub／速度、逐球選擇、local filters、影片、reduced-motion、視角方向、比較範圍、鏡頭控制與桌面／窄版均完成 |
| 3G · Pitch Replay validation and release gate | Completed | 對帳落點、飛行時間、方向與事件順序，正式釋出 SVG MVP；目前不升級 Canvas／3D | 速球／變化球／左右投／側投／32.3 mph／缺值案例、回應時間、零 severe console error及模擬邊界均通過 |
| 3H · Shared pitch panel and Personal In game | Done · 待使用者驗收 | Game Replay 與投手個人頁共用面板；Personal 新增 In game／場次選單，預設所選年度最近出賽 | 8 項來源／資料檢查及單次 Nuxt typecheck PASS；畫面／操作未由代理驗收，舊 3D–3G 不重開 |
| 4 · Catcher Calling Context | Planned | 顯示本場實際 catcher pairing、count/pitch mix、sequence context，並連到既有 Catcher Lab／Paired Duo；支援時才附整季 strategy bridge 摘要 | `fielder_2` pairing coverage、換捕手切分、pitcher-catcher-game reconciliation；無 caller attribution、無 leaderboard、無 best-pitch claim |
| 5 · Stamina Integration Gate | Planned | 把角色型 Stamina trait 與單場衰退訊號拆成兩層；決定 SP／RP 各自可顯示內容與 unavailable 規則 | 2026 role coverage 重算；單場 SP artifact 精確 join；RP 不誤顯 starter-only score；可靠度、CI、最低投球數與 Pitch Out 規則 |
| 6 · Batter Feature Coverage Lab | Planned | 以單場 batter-game 為粒度稽核 swing tracking 與 batted-ball 欄位、分母、年代與缺失模式 | 2023–2026 年度 coverage、2026 逐球 coverage、左右投與替補分層、極小樣本案例、官方事件 reconciliation |
| 7 · Batter Contact candidate | Planned | Lab 原型：EV／LA 分布、Avg/Max EV、HardHit、Barrel、Sweet Spot、xwOBA on contact；評估 `Contact` 按鍵 | BBE denominator、95 mph 與 barrel 定義、無 BBE 狀態、逐球影片、代表比賽及視覺驗證 |
| 8 · Batter Swing candidate | Planned | Lab 原型：competitive swing、Avg Bat Speed、Fast Swing%、Swing Length、Miss Distance；整季 timing fingerprint 與本場 tracking 分開，Squared-Up／Blast 維持 unavailable | bunt 排除、competitive denominator、exact timing 不可得聲明、樣本門檻、tracking missingness；決定是否釋出 `Swing` 按鍵 |
| 9 · Game Center integration and release audit | Planned | 將通過 gate 的模組整合成比分板下方頂層頁籤、共用本場球員選擇器與 lazy-load 策略 | backend tests、schema smoke、Nuxt typecheck、UTF-8、`git diff --check`、登入後桌面／窄版像素級 browser audit、效能預算 |

Slice 3D–3G 已完成並正式釋出 ball-only SVG Replay。Release Point 頂層頁籤與 Slice 3C 已依產品決定移除；現有 Slice 1–3B 的完整 browser release gate 仍獨立存在，之後才接 4 → 5 → 6。Slice 7 與 8 可在 Slice 6 後平行比較，但只有通過 gate 的候選才進 Slice 9。

### 3.1 Slice 1–3 實作與入口修正（2026-10-25）

Slice 1–3 的前後端與 API 已串接。後端保留 Location、Sequence、Tags 三條 game-scoped routes；Location／Sequence 由 `GamePitcherAnalysisPanel` 顯示，Tags route 改由投手姓名 hover/focus 小卡按需載入。加入 Pitch Shape 後，2026-10-26 的 targeted backend tests 為 30 passed、完整 backend suite 為 319 passed，Nuxt typecheck 與 UTF-8 檢查通過。

第一版誤把 `Location`、`Sequence`、`Tags` 做成每位投手列內的按鍵。Location／Sequence 的正確入口是比分板下方、與 `Feed`、`Box Score` 同層的頁籤；切入後再使用共用下拉選單選擇本場兩隊投手。Tags 不再占用頂層頁籤，而是在 Feed 對戰投手與 Box Score 投手姓名上 hover/focus 時顯示。Box Score 仍保留個人頁與 Outing Report 連結。小卡接既有 released Slice 3 roster，並追加獨立版本的 Lab-first practical profiles；完整球季 snapshot 仍可能包含所選歷史比賽之後的資料。當本季完全沒有 tag 時，只顯示最近一個過往同角色球季作為明確標記的 reference，不用聯盟平均或不同角色硬補。尚未完成的 release gate 是登入後實際點擊、影片 modal、桌面／窄版的 browser 像素級檢查，所以 Slice 1–3 維持 `in_progress`。

Location／Sequence 首次開啟緩慢的主因，是 Catcher 選項曾在冷啟動時對整季捕手觸發外部姓名查詢，且 Location 同時建置畫面未使用的 movement／league tables。改用年度 `player_master`、Game Center Location 精簡 payload，再加上前端五分鐘 request deduplication/cache 與首位投手背景預載後，同一代表案例（2026-09-27 HOU–ATH，Tatsuya Imai）冷啟動 Location 由約 8.0 秒降到 0.26 秒，Sequence 約 0.44 秒。StrikeZoneScatter 另把可見球點與較大的透明 hit target 分離，tooltip 設為不接收 pointer events，修正球點 hover 閃爍及無法點擊。

2026-10-26 新增共用 Game Pitch Shape payload；目前只由 Movement 頂層頁籤使用，篩選在前端完成並沿用五分鐘 request cache。代表場 2026-09-27 HOU–ATH 的 686751 為 36／36 movement、36／36 release-coordinate、36／36 video identity，冷讀約 0.33 秒；669620 的四筆 pitchless automatic-ball／intentional-walk events 不製造球點，其餘 19／19 可顯示。後端 payload 仍保留 release coordinates 作相容資料，但 2026-10-27 已移除獨立 Release Point 頁籤與元件；登入後視覺驗證只剩 3B Movement release gate。

### 3.2 Slice 3E–3G Pitch Replay 實作與 release gate（2026-10-27）

新增 `GET /api/games/{game_pk}/pitchers/{pitcher_id}/replay` 與 `pitch_trajectory_statcast_v1`。後端只讀指定 game/pitcher 的有效球，排除 Pitch Out 與 pitchless events，以實際 release point 回推 Statcast 50 呎狀態，再輸出 31 個等 progress 的 release-to-plate 三維點、飛行時間、closure error、逐球 support state、filters 及影片 identity。缺核心欄位回傳 `unavailable` 且 path 為空；X 或 Z closure 超過 3 英吋回傳 `limited_trajectory`，不竄改終點。

Game Center 新增 `Replay` 頂層頁籤並沿用本場投手下拉選單。可重用 `PitchReplayChart` 以單一 SVG 透視場景呈現軌跡、出手點、投手丘、本壘板與逐球 `sz_bot/sz_top` 好球帶；Pitcher／Catcher 是同一場景的切換按鍵，不是兩圖並排。使用者可用滑鼠左鍵拖曳或方向鍵微調 yaw／pitch，俯仰最低約 −6°，`Low angle` 可直接切到約 −5°，Home 或 `Reset angle` 回到預設角度。好球帶外層另有 1.35× visibility guide，內層仍保留真實 1.66 ft 寬與逐球高度，視覺放大不改判定邊界。比較層可在同打席與該投手全場其他球之間切換，選定球維持高亮、其他球依球種著色並降低透明度。原有單球／單一 PA、播放／暫停／重播／scrub、0.25×／0.5×／1×、逐球選擇、local filters、Savant 影片與 reduced-motion 均保留。Replay 獨立 lazy load 並使用五分鐘 request cache，不增加 Movement payload。

2026-10-27 視覺複核後，Replay 的畫面 X 最終固定為捕手視角 `display_x = statcast_x`、投手視角 `display_x = -statcast_x`；兩個視角必須一起遵守這組相反方向，不在軌跡公式中二次翻轉。逐球好球帶真實邊界固定為 1.66 ft 寬並使用 `sz_bot/sz_top` 高度，Side View 與並排雙圖均已移除。單一 3D-to-2D perspective projection 讓兩種端點視角共用同一組實際三維軌跡與場地幾何，鏡頭旋轉只改投影、不改資料座標或軌跡公式。

release gate 結果：代表場 824948 的 13 位投手共 328 顆有效球全部 supported；Tatsuya Imai 實際 HTTP payload 為 10／10 supported、31 點／球、10／10 有影片 identity。Tyler Rogers 側投案例 game 823428 為 35／35 supported、最低 release Z 1.21 ft；左投案例 game 823743 為 97／97 supported。Zach McKinstry game 823663 的最慢 32.3 mph 球得到 1.304 秒路徑並正確標成 limited；Martín Pérez game 823419 為 83 supported／1 unavailable。實際 service 代表案例約 0.17–0.22 秒。登入後 Chrome 再以 2026-09-27 HOU–ATH 驗證單一場景、Pitcher／Catcher 投影切換、拖曳改角度、同打席 4 顆與全場 40 顆比較軌跡；窄版 document 水平溢位為 0 px，console 無 severe error，Nuxt typecheck 通過。SVG perspective 足以負擔每位投手數十球的互動重播；人物模型、自由移動鏡頭、深度遮擋或更高軌跡量出現前，仍不需要引入 WebGL engine。

### 3.3 Slice 3H · 共用面板與 Pitcher Personal In game（2026-11-04）

使用者授權先改母站，投手個人頁分頁必須叫 **In game**，不是 Replay；預設所選年度該投手最後一場出賽。Game 原有 Replay 入口保留。`PitchReplayPanel.vue` 抽出逐場資料載入、local filters、逐球選擇／播放、support state／closure／影片動作；兩入口共用它與既有 `PitchReplayChart`。圖表僅新增 title prop，座標／投影／播放公式未改。Game 原外層遇 replay mode 不再重複 fetch；Movement／Location／Sequence 保持原路徑。

`PitcherInGameTab.vue` 僅在進入分頁時 lazy 載入，以既有 `personalOutings(year,pitcherId)` 取得場次；`Date` 倒序、同日 `Game PK` 倒序、去重／排除無效 ID，預設第一場。網址若明確給出有效 `game_pk` 則優先該場，無效則退回最近場次；選單標示 Game PK 以區分雙重賽，不將 PK 排序說成精確開賽時間。先選比賽才請求原 `GET /api/games/{game_pk}/pitchers/{pitcher_id}/replay?year=...`，沿用五分鐘 game-analysis cache，不新增整季軌跡 endpoint 或重寫球路公式。

契約仍是 `pitch_trajectory_statcast_v1` historical reconstruction，game/pitcher/pitch identity、左右視角、support／limited／unavailable、Savant video 及 reduced-motion 沿用；Pitch Out／無投球事件排除，缺軌跡不補值。每顆有效資料球保留於逐球選單，沒有軌跡者顯示 unavailable 而不是假動畫。共用面板及場次載入用 request version／unmount 防過期回覆，切年／投手／場次清除前筆資料，圖表按 context key 重新建立，不跨場混播。loading／empty／error／Retry 具 DOM 狀態，影片沿用各母頁既有 modal；沒有改 API、帳號／權限、後端計算或 Ballpark 場景。

程式證據：`node frontend/scripts/check-pitcher-in-game.mjs --report data/sample/petehub_pitcher_in_game_source_gate_v1.json` 的 8 項純資料／來源契約檢查 PASS；單次 `npx nuxt typecheck` PASS，未跑完整 build／backend suite／瀏覽器。靜態 lifecycle guard 檢查不等於實際切換或清理通過，3H 保持 in_progress。3D–3G 舊已發布 gate 保留，不擴大成新入口人工通過。

2026-11-04 逐球資訊 followup：依使用者希望比照 Stuff，新增共用逐球詳細欄位（日期／game／PA／球序／球速／球數／結果／投打側／捕手／出手與進壘座標）及軌跡 hover title／鍵盤聚焦名稱。比較軌跡與選定軌跡可點擊或 Enter／Space 選球並開該球影片；按下軌跡不觸發 camera drag。`open-video` 與自動 `select-pitch` 分開，下拉選球／播放換球不自動彈影片。保留 Open Video 按鈕，無映射明示 unavailable；資料來源不含的 Plus 指標不補造。兩入口同步，無新 API／座標公式。新增欄位缺值／零值、影片 URL／play_id、資料不變及兩個 SFC 來源語法檢查 PASS；未重跑完整 typecheck/build／舊八項檢查。上述 v1 證據是初次交付快照，非此 followup 新 hash 或人工通過，3H 仍待使用者確認。

2026-11-04 影片補抓後台 followup：依使用者改為自行按鍵補齊的要求，在 `/admin/updates` 新增所選年度「補齊缺漏影片」面板，沿用既有 background job／StatsAPI worker，不啟動全量補抓、不重算模型。新增狀態 API 的已保存／待補場次、全域執行中與年度最新工作；同程序防重複排隊，失敗可再按續補。每 50 場保存，面板每 5 秒讀取；關頁不取消，後端須保持運行，重啟後須再按一次且只接續已保存映射。場次完整定義為 pitch／player lookup 交集，不是逐球影片可播放保證；失敗／剩餘缺漏不宣稱全季完成。6 項隔離後端測試與兩個 Vue SFC／TypeScript 語法檢查 PASS（非完整 typecheck 或 UI 驗收），詳見 `API_CONTRACTS.md`。待使用者確認後台按鍵、重進頁狀態與補後影片播放；3H 保持 in_progress，不重開已完成 Slice。

使用者人工驗收（最多五項）：

1. `/pitcher-personal?tab=in-game` 選投手，看到 **In game**，場次預設該年最近一場；有日期／對手／Game PK。
2. 切換場次、投手、年份，逐球選單與球數跟著更新，不混入上一場或上一位投手；沒出賽時有空狀態。
3. 逐球／PA／This game、播放／暫停／速度／時間軸、視角與篩選／清除可用；詳細欄位跟隨選球，缺軌跡球誠實顯示 unavailable。
4. Hover／聚焦軌跡有該球資訊，點擊／Enter／Space 或 Open Video 開正確影片；自動換球不彈影片，無映射有說明。Game `/games/today` 的共用入口亦確認。
5. 窄版、鍵盤選單／按鈕及 reduced-motion 可用；未測的裝置或情境不可列通過。代理不開瀏覽器／截圖／另開 server。

## 4. 投手模組設計

### 4.1 Location

Location 固定為「該投手在該場比賽的逐球」。沿用 Personal 頁資訊，但移除已被 game context 固定的 Year／日期／投手選擇器。

保留的過濾器：

- Batter Side
- Count（exact count、Pitcher Ahead、Hitter Ahead、Two Strikes）
- Pitch
- Pitch Result
- In Play Result
- PA Result
- Paired Catcher（單場換捕手時仍有意義）

圖表保留 pitch type、velocity、result、Stuff+、Location+、Stamina 欄位、PA/pitch identity 與 Savant video modal。熱區混合可保留，但預設仍以實際 pitch dots 為主，避免小樣本熱圖看起來過度平滑。

### 4.2 Sequence

Sequence 固定在同一位投手、同一場比賽，不跨換投、跨 PA 或跨比賽串接。沿用：

- Batter Side、Count、Pitch、Pitch Result、Paired Catcher
- Count Detail
- Follow-up Pitch
- Conditioned Count／Pitch branch

單場樣本遠小於 Personal 全季頁，因此主畫面先顯示 count/pitch tree 與 immediate follow-up；Shallow／Two-Strike tables 只有在分母足夠時顯示，不做單場好壞結論。

### 4.3 Movement

Movement 固定為該投手該場的球路形狀，直接重用 `MovementChart`。Scatter 與 Average 都只以目前篩選後的本場球計算；不預設混入整季球點或聯盟平均。Pitch／Stuff+ 著色、逐球 tooltip、PA/pitch identity 與 Savant video 保留，Stuff+ cache 缺值時維持 unavailable。

### 4.4 Pitch Replay

Pitch Replay 是 game-scoped 的資料重播，不是投手動作捕捉或空氣動力學模擬。Game 入口與 Location／Movement 相同：比分板下方的頂層頁籤、共用本場投手下拉選單；2026-11-04 新增的投手個人頁 In game 則先選出賽場次後使用同一面板。兩邊都不能跨 game 或跨投手自動串接；新增入口人工 gate 見 3H。

MVP 使用 Vue／TypeScript 與可重用 SVG 元件，在單一場景中切換 catcher-view 與 pitcher-view。捕手畫面 X 使用 Statcast X，投手畫面 X 為其鏡像；後端依 `pitch_trajectory_statcast_v1` 契約計算固定時間間隔的路徑點與 flight time，前端只處理播放狀態與視覺投影，不自行重寫物理公式。必要互動為播放／暫停、重播、scrub、0.25×／0.5×／1×、逐球／單一 PA／目前所選投手本場全部有效球續播、同既有 filters、tooltip 與 Savant video。播放倍率只調整單顆球的飛行時間，連播球與球之間固定停留 0.7 秒。使用者開啟 Replay 才 lazy load，不把路徑點塞進 Movement 的既有 payload。

Replay 不直接用 `pfx_x/pfx_z`（HB／IVB）另畫一條人工曲線，而是使用 Statcast 的 `v*0/a*` 狀態重建完整三維路徑；因此 movement 已反映在軌跡中。若新增 tunneling／共軌分析，應以這些完整路徑計算共同出手窗口、早期分離量與晚期分岔點，並先定義是否正規化出手點或進壘點，不能只靠 HB／IVB 覆蓋目前的 replay path。

每顆球回傳 `supported`、`limited_trajectory` 或 `unavailable`。缺完整 release／velocity／acceleration 時不可插值；closure 超過 3 英吋仍可畫資料所描述的路徑，但需顯示 limited，不把終點硬拉到 `plate_x/z`。`prefers-reduced-motion` 下預設顯示靜態路徑並由使用者主動播放。第一版不畫實際投手身體、不用球員身高，也不宣稱 seam-shifted wake、風阻、旋轉軸演變或真實人體 mechanics。

### 4.6 Tags

Tags 是 season-role descriptive profile，不是單場評分或天賦結論。它不再是頂層頁籤；使用者 hover 投手姓名或以鍵盤聚焦姓名連結時顯示小卡，並附：

- SP／RP role
- support label／樣本數
- artifact version
- `as_of` 或明確的「完整球季 snapshot」標籤

核心來源是 `player_archetype_slice3_roster.parquet` 的 arsenal depth、arm slot、command tags；Primary Pair 仍留在 frozen artifact，但不再顯示於 Game Center 或 Pitcher Tag Lab。另追加獨立的 `player_archetype_practical_tags_v1.parquet`，包含 Pronation／Supination 與左右打 More Breaking Balls／More Offspeed profiles，並以 dashed outline 與 Lab-first 說明區隔。兩者都是 full-season descriptive snapshot，歷史比賽頁必須明示可能包含該場之後的資訊，不能宣稱 through-game-date。practical v1 不取代 core tags，也不影響任何 Slice 4–6D 研究 artifact。

本季沒有 tag 時，不用聯盟平均或不同角色的 generic label 補滿，因為那會讓平庸或低樣本投手看起來像已有個人型態結論。若 roster 中存在最近一個過往同角色、有正式 tag 的球季，小卡可顯示為 `reference only`，並同時明示目前球季仍是 unsupported；完全沒有同角色歷史時顯示 unavailable。

### 4.7 Catcher Calling Context

建議 UI 名稱保留使用者熟悉的 `Catcher Calling`，但副標固定寫成 `Observed pairing context`。內容分兩層：

- Game layer：本場捕手、與該投手搭配的 pitches／PA、count/pitch mix、sequence branch、換捕手時間點。
- Season context：連到 Paired Duo／Catcher Lab；2026 且通過 support gate 時，才顯示 entropy、effective supported choices、top-choice probability、supported deviation、support coverage 等分離診斷。

不把 framing、blocking、throwing、cERA 或 cSaveRun 混成「配球分數」。既有 strategy bridge 仍不得推出 catcher strategy leaderboard、caller attribution、individual best pitch 或 causal value。

## 5. Stamina 現況與 Game Center 規則

### 5.1 2026 實際覆蓋

以 `data/derived/stamina_lab_2026.parquet` 重算：

| Role | Pitch rows | Pitchers | Stamina trait coverage | Expected Stuff+ path coverage |
|---|---:|---:|---:|---:|
| SP | 404,416 | 377 | 95.5% | 91.5% |
| RP | 312,128 | 741 | 87.3% | 73.0% |
| Total | 716,544 | 868 unique | 91.9% | 83.4% |

因此「後援投手完全沒有算」不正確：Slice 5 的 role-specific two-season retention trait 與 Slice 6 的逐球 trait／expected path 都有 RP。RP 的 expected path 覆蓋較低，Game Center 必須逐欄位顯示 unavailable，不能只用總覆蓋率掩蓋差異。

### 5.2 後援投手目前缺少的層級

下列較新的單場訊號在服務端明確以 `appearance_role = 'SP'` 建立，仍是 starter-only：

- Observed Game Stamina+：2026 Overall 4,563 個 eligible starts、302 位 pitchers。
- Physical Stability+：2026 4,572 個 eligible games、303 位 pitchers。
- Command Retention+：2026 Overall 4,392 個 eligible games、303 位 pitchers。

這表示 RP 尚未納入「單場衰退分數」的正式計算與評估。Game Center 規則如下：

- SP：可在完成門檻與可靠度 gate 後，顯示該場 Quality Stamina+、Physical Stability+、Command Retention+，三者維持分開。
- RP：只顯示有支援的 role-specific trait、expected path 與逐球觀察值；單場分數顯示 `Not evaluated for RP`，不可套用 SP 模型。
- 不重新合成 composite，也不因某投手缺資料而補 100 或零。
- 若未來要做 RP 單場 Stamina，必須另開研究 Slice，重新定義較短 appearance 的 early/late windows、最低投球數、槓桿與休息日影響，不能只放寬 SP 門檻。

另需注意：目前 2022–2025 的 `stamina_lab_*.parquet` 雖有逐球骨架，但這次稽核中 trait 與 expected path 欄位未填值；正式整合前必須決定只支援 2026，或先另行完成歷史 artifact backfill。

### 5.3 可擴大覆蓋的分級方案

既有門檻把「正式可比較」與「能否算出數值」綁在同一個 `eligible`。Game Center 可以拆成三層，但 limited 資料不得進排行榜、球季平均或跨球員比較：

| Signal | Supported | Existing raw/scored but ineligible | No state row | 建議 |
|---|---:|---:|---:|---|
| Quality Stamina+ | 4,563 starts | 185 starts | 109 starts | 185 場都有 raw retention／sampling variance，可用既有 EB prior 算 provisional score；標記 pitch-count／mix failure、CI 與 reliability |
| Physical Stability+ | 4,572 starts | 177 starts | 108 starts | 177 場已存完整 score；可顯示 limited，median reliability 0.586，但不得併入正式 season summary |
| Command Retention+ | 4,392 starts | 353 starts | 112 starts | 353 場已存完整 score；median reliability 僅 0.226，應採更嚴格的 low-confidence 標記或最低 reliability display gate |

Quality 的 185 場若沿用現有 prior 計算，provisional reliability 中位數約 0.573；150 場至少 0.40。這說明大多數確實「可算」，只是沒有通過正式 eligibility。建議狀態名稱：

- `supported`：通過既有門檻，可進既有 timeline／summary。
- `limited_observed`：有 raw state 或既有 score，但未通過 pitch count、fixed-mix 或 component coverage；只在該場顯示 score、CI、reliability、failure reasons。
- `insufficient_no_late_state`：沒有 late state row，不製造分數，只顯示缺少幾顆 supported pitches。

Trait 缺失也可再分級。2026 目前未取得 trait 的 player-role 中：

| Role | Missing player-roles | 3+ matched games | 1–2 matched games | No matched later window |
|---|---:|---:|---:|---:|
| SP | 142 | 45 | 76 | 21 |
| RP | 322 | 181 | 139 | 2 |

45 位 SP 與 181 位 RP 可以研究低樣本、強收縮的 `experimental_low_sample` posterior；但現有驗證門檻是 SP 8 場、RP 12 場，不能直接把它們升成正式 Stamina trait。1–2 場只應顯示 insufficient sample，不宜產生個人化分數。

Expected Stuff+ path 在已有 trait 的球員仍缺 16,399 顆 SP、44,477 顆 RP，主因是某球種在 baseline window 後才首次出現。嚴格使用賽前資料時可分層補回：

- 同角色／同球種的 earlier-2026 baseline：SP 14,654、RP 40,363（各約 89–91%）。
- 再退回 2025 同角色／同球種：SP 810、RP 1,423。
- 仍無個人歷史：SP 935、RP 2,691，只能用 role-pitch-type league prior，必須標記 `league_fallback` 與較低 reliability。

這是新的 baseline contract，必須 chronological backtest；不能在歷史比賽使用該場之後的球季平均。

RP 單場 Quality 並非資料上不可行。若使用既有 RP 1–5 球 baseline、6 球後評估，並要求至少 5 顆 supported late pitches、早期 family mix coverage ≥80%，2026 有 12,165/15,936 次 RP appearances（76.3%）、717 位 pitchers 可形成候選。Physical／Command 若維持同球種至少 3 顆 early baseline，具有至少 5 顆 supported late pitches 的上限約為 6,048／6,063 appearances（38.0%）；Command 尚須再套 fixed-mix gate。三者都必須另做 RP calibration、短登板 uncertainty 與 leverage/rest sensitivity，不能套用 SP 分布。

## 6. 打者候選功能

### 6.1 建議的兩個按鍵

1. `Contact`：優先正式候選。
   - 本場：Avg EV、Max EV、HardHit count/rate、Barrel count/rate、Sweet Spot%、Avg LA、xwOBA on contact、EV/LA 分布與 batted-ball 影片。
   - 原因：這些是實際擊球事件，適合單場回顧；只要清楚顯示 BBE 分母，就不會把一顆 105 mph 擊球過度包裝成穩定能力。
2. `Swing`：先留在 Lab。
   - 本場 tracking：competitive swings、Avg Bat Speed、Fast Swing%、Avg Swing Length、Miss Distance。
   - 整季 context：Timing Fingerprint 的 Competitive／Flawed／Perfect、Centered／On Time／Lined Up 等摘要。
   - 原因：本場 swing 樣本少，tracking 缺失不是零；既有 On Time 等欄位是 Savant summary，不是可回填到每一球的精確 timing label。Squared-Up／Blast 目前也沒有 local pitch-level 數值，維持 unavailable。

如果 Box Score 空間只允許一個入口，Slice 9 預設選 `Contact`，並把 Swing 留在 Lab／Batter Personal。若 Slice 6–8 證明兩者覆蓋與操作都穩定，再保留 `Contact`、`Swing` 兩個按鍵。

### 6.2 Lab 先行理由與 gate

打者原型先在 Lab 跑，不直接接正式 Game Center，因為需要先回答：

- 每場每位打者有多少 tracked swings／BBE，替補或 0–1 PA 時如何呈現。
- bat speed、swing length、miss distance、launch speed／angle 各年度與不同裝置時期的缺失是否偏向特定球場、球員或結果。
- `competitive swing`、bunt 排除、HardHit、Barrel、Sweet Spot、xwOBA 的分母是否與既有 Personal／Comparison 完全一致。
- 是否需要最少 3 tracked swings、2 BBE 等顯示門檻；門檻在代表性比賽中會隱藏多少球員。
- 本場數據與整季 fingerprint 必須分欄顯示，不能合成一個未驗證的「打擊狀態」分數。

建議 filters 控制在 Pitcher Hand、Pitch、Count、Pitch Result／Swing Type；單場資料不要提供過多交叉篩選，避免每個格子只剩一球。

## 6.1 In game 捕手視角的打者九宮格（2026-11-05 第一版，人工待驗）

2026-11-05 聯盟／PR給色取代絕對值色盤：使用者選擇完成前處理/API/給色、並採打者角度反向。新增離線 `build_batter_zone_baseline.py --year 2026`，共用同一 `aggregate_zone_rates` 而非另寫聯盟公式；唯讀716,544 regular-season pitches／662打者，571名全季完成PA>30合格，產出705個hand/zone/metric群組，快取 `data/MLB2026/batter_zone_baseline_v1.json`（4,130,003 bytes）。每群只收該格分母>=10的合格打者；league_average為合併分子／合併分母，PR分布是每打者等權的原值，至少5名比較者。PR=100×(低於值的人數+0.5×同值人數)/N，全部同值為PR50；PR50是打者分布中位，並非加權聯盟平均。這是樣本描述PR，不是穩定能力認證。

打者方向：AVG/wOBA/HardHit/Contact/Z-Contact/O-Contact較高偏紅；Whiff/SwStr/CalledStrike/Strike/CSW/O-Swing較低偏紅（100−raw_PR）。Swing/Z-Swing/Foul/In-play屬頻率，維持raw_PR高紅低藍並明示不判斷能力好壞。新回應附league_average/raw_pr/color_pr/peer_count/benchmark_status及cohort門檻；原值與分母不變。前端改平滑同區基準PR、非繼續平滑原始百分比，色階PR0藍#0050ff／50近白／100紅#ff142d，較飽和且alpha .86。低樣本／少比較者無PR即不給色；基準缺失、來源變動或無效時不退回舊絕對值紅藍，表格仍可讀原值。原Personal palette不受此新Ingame PR色盤影響。

前處理僅先完成2026；其他年度須另執行相同腳本，HTTP不得偷偷掃全季。快取含DB/WAL revision與原始彙整程式／事件集合fingerprint，原始DB不寫入；完成時確認來源未變，原子發布。API以LRU讀JSON，enrich raw cached response時deep-copy避免PR污染原快取。2026來源與快取已對帳，無重複建置；`test_batter_zone_rates.py`＋`test_batter_zone_baseline.py` 共16項PASS，PR contour純來源檢查及direct vue-tsc PASS。A.J. Ewing id805999 vsR中間格：Swing83.61%、同格合格平均75.42%、rawPR81.48；Whiff5.88%、平均10.50%、反向colorPR76.01。九格Swing PR26.26–81.48、Whiff打者PR22.28–96.95，顯示舊全紅／全藍是絕對量尺／方向問題，不應為了讓畫面紅藍平均而對單一球員重縮放。證據 `petehub_batter_zone_pr_source_gate_v1.json`，本批仍待使用者畫面驗收。

同次使用者指出Outside zones呈大矩形與橫線，已改僅在白框外normalized距離<.28的圓角窄halo顯示，向外衰減（最高為內圈alpha的.55倍），同色/透明度用compound path合併繪製處理逐列接縫。帶外仍是8粗分組的示意，不是逐球密度，表格及PR不變、不剔除較遠的球；樣本不足區保留空白。純幾何檢查確認帶外範圍／衰減，畫面是否合適由使用者回報。此次未執行browser、截圖、另一個server或替代帳號。

2026-11-05 Personal式等高線上色：使用者希望套用Personal的等高線風格，已將其原heatColor／heatStroke／八階contourLevel抽為共用 `heatmapPalette.ts`，Personal原本計算／配色數值不變。In game改為對有樣本區的分子與分母做高斯顯示插值（normalized sigma .22，3sigma範圍），48×48採樣後按同色橫列合併，呈現同八階連續色帶；鏡頭改動只重投影色帶，不重做平滑。這是9／17區彙整值的顯示插值，非從原始逐球位置重新估計的KDE，不宣稱增加解析度或可靠性；UI已說明精確值見數值表。零值有冷色、零分母／缺樣本區不畫，Z/O不跨inside/outside插值；分母<10仍淡色。原16項數值、PA資格、座標及球路不動，帶外開關保留。`check-batter-zone-contours.mjs` 純來源／數學檢查PASS（空／零、分母加權、缺樣本洞、bounds、非修改資料、壓縮與wOBA尺度），一次direct vue-tsc PASS；未重跑後端測試／build／瀏覽器或畫面驗證，3H人工仍待回報。

2026-11-05 outcome metrics followup：使用者要求 AVG、wOBA、HardHit%，已加入同一共用熱圖選單，現16項。AVG為完成PA之H/AB，使用既有 NON_AB／HIT events；wOBA直接使用有效原始 woba_value 與正分母 woba_denom，缺值不補零、不另造年度權重。兩者只在該PA最後一球的有效位置入格，完成PA先按game/at-bat挑最後pitch去重，避免把結果重複套每球；無位置的結束球不轉嫁給前一球。HardHit%使用完成PA的場內擊球且有有限正值初速，>=95mph／有追蹤初速BBE，缺初速不當soft hit。AVG／wOBA為三位小數，HardHit%為百分比；numerator／denominator可為浮點權重。各格低樣本仍按自身分母淡色，資格仍整季PA>30。色階分別為百分比0–100、AVG0–1、wOBA0–2，上限顏色截頂且圖例有≥，原數值不截斷（wOBA可>1甚至>2）。來源檢查：10項targeted tests、8項格式／色階assertions、一次direct vue-tsc PASS；實際2026打者682998 vsR有位置結束球合計H84/AB400、wOBA144.35/455、HardHit140/300，僅資料對照，並非畫面／能力評價。證據 `petehub_batter_in_game_outcome_metrics_v1.json`，3H與最新比例／熱圖畫面仍待使用者驗收。

2026-11-05 比例 followup：使用者截圖指出好球帶視覺比例失衡。只調整 catcher 通用剪影為原顯示縮放的0.76/0.95，並與好球帶同一深度平面定位；不聲稱其為球員實際身高／動作。帶外八區預設不畫，可用 Outside zones 開關；選 O 系列時自動顯示，白色九宮格與17吋／sz_bot/top不變。數值表仍保留全17區，資料／分母／球路不動。本次只為呈現修正，不重跑先前資料測試／typecheck/build，也未由代理進行畫面測試；等待使用者回報。

使用者已授權完成可操作第一版（資料 API＋捕手熱圖＋比率切換）。Game／Pitcher Personal 共用 `PitchReplayPanel.vue` → `PitchReplayChart.vue` 的 Catcher 視角已接入 `BatterInGameHeatmap.vue`；依當前逐球 batter／pitcher／year／p_throws 取得資料，整季總 PA >30 才顯示。這是母站 3H 延伸，不是 Ballpark E3 開工。以下保留原需求，現況以本段及交付／驗收紀錄為準，舊「未實作」說明屬接線前快照。

**第一版交付：** 新增 `GET /api/batters/personal/zone-rates`、`batter_zone_rates_v1` schema／service，直接唯讀原 regular-season pitch table 的必要欄位；不載入／改寫影片、Plus cache 或軌跡資料。重用既有完成 PA 計數與 Discipline event flags；以 DB／WAL mtime/size 作 server LRU identity，client 在元件生命週期內以 year/batter/hand 快取最多32份、兩分鐘。回應一次含13種比率，換 metric 不重抓資料；latest-request guard 隔離換人／手別／卸載的過期回應。Game 與 Personal 均經同一共用元件，保留原 API／Batter Personal Discipline 頁面。

16項選單：Swing%、Contact%、Whiff%、SwStr%、Called Strike%、Strike%、CSW%、Z-Swing%、Z-Contact%、O-Swing%、O-Contact%、Foul%、In-play%、AVG、wOBA、HardHit%。每格回傳 numerator／denominator／value，真實0與null不混用，百分比與小數格式分開。九宮格＋八個帶外群組共17區；帶外矩形顯示範圍為示意，實際彙整包括更遠的球。Z/O 指標在不適用區域為 null。低於10個分母樣本用較淡顏色，並保留數值表；全季31 PA資格不代表每一格樣本足夠。各指標色階見最新followup，紅只表示較高數值。

**座標與相容性：** 熱圖每球以自己的 sz_bot/top 正規化，缺值／無效高度回退1.5–3.5ft並回報數量；水平為17吋本壘板。投到現有 replay 的當前好球帶 plane，同一個 `physicalPolygon` 隨捕手角度／縮放變換，不改球路。既有 Discipline 固定框 x±0.83ft、z1.5–3.5ft 未改；此圖的 Z/O 以正規化17吋框分區，不能假稱與舊固定框所有 Z/O 彙整值逐格一致。事件 flags／比率分母則沿用既有定義，包括 foul_tip 等既有分類，不用1−Whiff%推算Contact%。

**已完成來源檢查：** `test_batter_zone_rates.py` 七項測試（30/31 PA、唯一完成PA、左右手與分母、17區邊界／coverage、正常化／未知手別、DuckDB enriched/regular/batter選擇、nullable位置）PASS；單次直接 vue-tsc PASS。唯讀2026打者682998：全季671PA，vsR 1845球／1832有位置，vsL 800球／795有位置，17區合計相符；不是畫面或對該球員身分／能力的評價。未登入既有 API 回401，未建立其他帳號或 UI fixture，未做登入後播放／畫面測試。證據 `petehub_batter_in_game_heatmap_source_gate_v1.json`。3H仍 in_progress，等使用者人工驗收，不推定原影片播放與所有3H gate通過。

**本批人工清單（使用者執行）：**

1. `/pitcher-personal?tab=in-game` 選出賽場次、切 Catcher，確認顯示目前打者的整季PA／手別／熱圖；資料載入中及缺資料有說明。
2. 自動左右投與手動 L／R／All 正確；換打者／投手／年度／場次不殘留上一人的結果。
3. 切13種比率、展開數值表，確認0%／無分母區分、低樣本淡色，30PA以下不畫熱圖。
4. 拖曳／縮放時格子對齊；關閉熱圖或回 Pitcher 視角，原球路／選球／播放／影片操作維持正常。
5. 在 Game Center 相同共用面板確認同功能，並確認鍵盤選單、開關與窄版可用。

- 資格：使用所選年度 regular-season 全季唯一 PA（沿既有事件／game_pk＋at_bat_number 語意）計算，嚴格大於 30；不能用 pitch count、單場 PA 或對該手別 PA 代替。PA 門檻不隨目前顯示的左右投／球數等圖表 filters 改變。
- 手別：由目前選球的 `p_throws` 預選 vs LHP／RHP，與打者 `stand` 分開；允許手動切換且清楚標示篩選。換投／換打者／換年／換場時清除過期結果，未知手別不可默認右投。左右投兩份可快取，switch hitter 仍依投手手別取樣，不能鏡像混用。
- 比率選單：共用既有 discipline event flags／分母定義，提供 Swing%、Contact%、Whiff%、SwStr%、Called Strike%、Strike%、CSW% 及適用的 Z/O 系列等可計算選項；每格同時有 numerator、denominator、樣本與百分比。Contact%／Whiff% 以 swings，Swing%／SwStr%／CSW% 以 eligible pitches；不可同用球數當所有分母。AVG 等非比率百分比若加入，另用正確 AB/PA-end 及格式，不能與 Swing% 混算。
- 圖面：沿用 Discipline 的座標／區域語意及配色能力，但目前其 heatmap 主要是 density（另有 bat-speed／choice），不是所有比率皆已有 heatmap。新圖需計算各格分子／分母後著色；純 density 不可冒充揮棒／接觸率。好球帶以正規化高度及捕手視角對齊當前 replay 九宮格，視角旋轉需跟隨 projection，不改 Statcast 軌跡／左右側。O 系列須有帶外區呈現或在帶內格顯示不適用，不能把零母數塗成 0%。
- 範圍：打者全季對該投球手別樣本，非本場／對目前這一位投手的對戰成績；可先共用獨立 DOM 面板，再依接線規格呈現在 catcher 視角，保留圖例、開關、數值／鍵盤可讀表。低樣本顯示樣本提示，不推定個別格滿足全季 PA 門檻；缺座標／分母為零顯示無資料，不補造熱區。
- 現況證據：`batterPersonalDiscipline` 的 useApi／route／service 目前沒有 `pitcher_hand` 查詢參數，只有 `stand`；雖回應有 pitcher_hand_split，不能據此宣稱所有 location points 已依左右投篩選。需擴充共用資料契約、回應樣本／coverage 及 cache identity（year/batter/pitcher_hand/metric/filters/version），Game 與 Personal 使用相同模組，避免每換一球重抓整季資料。既有 endpoints／母站先保持現況。
- 手別欄位已確認（2026-11-05）：`game_pitcher_analysis_service.py` 的 replay scalar columns 已含 `p_throws`，回應每球保留；summary 另有 `pitcher_hand`。`pitcherInGame.ts` 將 `p_throws` 顯示為 Selected Pitch 的 Throws。`batter_service.py` 的正規化／欄位清單也保留 `p_throws`，且以它產生 pitcher_hand_split。因此直接讀目前選球 p_throws 可自動預選左右投；缺的是 Discipline 的獨立查詢參數及熱圖彙整，不是資料缺欄或需要推測／重抓手別。缺值仍明示未知，stand 始終為打者站位。
- 驗收方向：30/31 PA 邊界、左右投／switch hitter／換投換打者、各比率分母、空資料／缺位置／低樣本、捕手座標方向及關閉熱圖後原圖／影片不變；資料契約需 targeted tests，畫面一律由使用者驗收。仍待後續開工，不將本段當已完成 UI。

## 7. Slice 9 釋出標準

只有通過各 Slice gate 的模組才進正式 Box Score。最終需同時完成：

- API/schema 與代表 game fixtures：至少一般九局、雙重賽、延長賽、換投、換捕手、先發短局數、後援短 appearance、替補打者、無 BBE。
- Pitch Replay 另含一般速球、變化球、左右投、側投、30–40 mph 慢速球、缺完整軌跡與 closure limited fixtures；不得用固定小於一秒的 flight-time 假設。
- 與來源逐球／官方 boxscore 對帳，包含 lineup substitution 與 player identity。
- lazy-load、取消過期 request、cache key 包含 `year/game_pk/player/role/filters/version`。
- 桌面與窄版不產生整頁水平溢位；頂層頁籤、投手下拉選單與 modal 可用鍵盤操作。
- 登入後 browser 像素級檢查、零 severe console error。
- targeted backend tests、Nuxt typecheck、UTF-8 scan 與 `git diff --check` 全部通過。

