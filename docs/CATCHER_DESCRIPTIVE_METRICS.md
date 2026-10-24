# Catcher Descriptive Metrics

更新日期：2026-10-20
狀態：Slice 0–8 完成

## 文件規則

這是 Catcher Descriptive Metrics 小專案唯一的人工可讀主文件。後續 Slice 直接更新本文件中的對應章節，不再於 `docs/` 根目錄建立 per-Slice Markdown。精確、可重建的執行結果仍以 `data/research/catcher_descriptive/` 下的 JSON、Parquet、manifest 與 immutable snapshots 為準；專案與 Slice 狀態仍以 `docs/PROJECT_TRACKER.json` 為準。

## 研究邊界與用語

- 本專案處理捕手在場結果、投捕搭配、投手組成基準、可靠度與呈現。
- 所有 c/t 差值是 observed association 或 runs versus pitcher mix，不是捕手因果價值。
- 捕手在場不代表能辨識實際叫球者；配球模擬與 best response 不在本專案內。
- 率統計一律保留分子、分母與 `outs`；只有顯示時才轉成棒球局數記法，禁止把 `6.1 IP` 當成十進位 6.1。
- 小樣本標示 limited／unavailable，不使用聯盟平均補成精確值，也不做誇張年化。

## Slice 狀態

| Slice | 狀態 | 內容 |
| --- | --- | --- |
| 0 | 完成 | 舊來源、公式、資料涵蓋與可重現性稽核 |
| 1 | 完成 | 2021–2026 canonical pitcher-catcher ledger |
| 2 | 完成 | cERA、cRA9、cFIP |
| 3 | 完成 | 完整投手球季率加權的 tERA、tRA9、tFIP；LCO 僅作敏感度 |
| 4 | 完成 | cSaveRun 跨年可靠度與 dominant-pair sensitivity；release gate 未通過 |
| 5 | 完成 | Petehub xERA v1、cxERA／txERA 與逐層 reconciliation |
| 6 | 完成 | Statcast FRV 來源 gate、Throwing／Blocking／Framing 獨立防守軸；park factor候選來源已正規化，但尚未選定調整公式或套用 |
| 7 | 完成 | Leaderboard、Catcher Lab、Paired Duo 與登入後 release audit |
| 8 | 完成 | 2026 model-consistent strategy bridge；research-only且不建立排行榜或綜合分數 |

## Slice 0：Legacy source and definition audit

### 舊成果

`C:\轉移\mlbpython\ERA\catcher2025_processed.xlsx` 的 `Sheet1!A1:M104` 有 103 筆捕手、13 欄且沒有 Excel 公式。欄位為 Name、Tm、Inn、SavRun、ERA、RA9、tERA、tRA9、Framing、FRV、SR/Yr、SRA、SRA/Yr；Framing 與 FRV 各缺 26 筆。

| 舊欄位 | 可驗證程度 | 結論 |
| --- | --- | --- |
| ERA／RA9／tERA／tRA9 | 不可完整驗證 | 缺原始 R、ER、outs、pair weights 與 baseline lineage，只能作 comparison target |
| SavRun | 部分可重建 | 非 TOT 列可由 `(tERA - ERA) × Inn / 9` 重建到顯示精度，但原始分子與 innings 缺陷仍存在 |
| SR/Yr | 公式可重建、語意停用 | `SavRun × 1200 / Inn`；小樣本被不合理放大 |
| SRA | 數值可重建、棒球語意不明 | 每列等於 `SavRun + 0.01792792792793`，沒有來源或合理定義 |
| SRA/Yr | 公式可重建、語意停用 | `SRA × 1200 / Inn` |

舊表 Ben Rortvedt `324.3` 與 Austin Wynns `252.4` 證明 TOT 局數曾把棒球記法當十進位加總。舊 `cera_utils.py` 只會由 Baseball Reference pitcher By Catcher split 加總 BF／ER／K／BB／H／HR 並用 outs 算 ERA；失敗會靜默跳過投手，沒有 raw snapshot 或 completeness gate，也不會產出 RA9、t 系列、SavRun 或 SRA。

舊 `build_estimated_xera.py` 是 714 列 2025 pitcher-season OLS proxy，只有 in-sample MAE 0.222、RMSE 0.379、R² 0.930，並混用 xwOBA、xBA、wOBA 與擊球品質等重疊特徵。它只保留作 Slice 5 baseline，不能直接當 cxERA。

### 來源涵蓋與缺口

- 2021–2026 本機 Statcast 有 4,284,184 顆正規賽球與 1,098,891 筆 PA 終結事件；pitch／PA key 無重複，終結列的 `fielder_2`、`outs_when_up` 與比分欄完整。
- DuckDB 沒有 `outs_on_play`、`responsiblePitcher` 或 earned flag，所以不能用比分差假裝投手責任制 R／ER。
- 六場 official game-feed probe 的 591 個 PA 全部可用 `game_pk + atBatIndex + pitcher_id` 對齊；186 位得分跑者具有 earned 與 responsiblePitcher，316 個出局 movement 具有 outNumber。
- Slice 0 當時沒有已確認可直接使用的 catcher defense dataset，也沒有完整、明示來源的 park factor。後續 Slice 6 已稽核使用者提供的 2021–2026 DRS 與 Statcast FRV exports；產品主尺度採 FRV，DRS 只留 comparison audit。2026-10-20另收到兩個三年期park-factor表並正規化為可依球季／球隊join的候選來源；尚未取得原始URL、選定調整公式或回寫任何捕手指標。

### Slice 1 契約

唯一鍵：

- pitch：`season / game_pk / at_bat_number / pitch_number`
- PA：`season / game_pk / at_bat_number`
- pair：`season / pitching_team_id / pitcher_id / catcher_id`

來源優先序為 official MLB game feeds（責任投手、earned、out movement）→ official pitcher-game lines（控制總量）→ 本機 Statcast（`fielder_2` 與逐球欄位）。必須同時保存 current-pair runs 與 responsibility-based R／ER；不得把 automatic runner 或 inherited runner 強塞給錯誤捕手。

## Slice 1：Canonical pitcher-catcher ledger

流程下載並重用 immutable official snapshots，建立 PA、runner responsibility 與投捕 ledger，再對帳 official pitcher-game controls。瀏覽器可關閉或重新整理，但後端工作程序必須持續運行；中斷後由 manifest 恢復，合法 snapshot 不覆寫。

ledger 保存 outs、BF、R、ER、HR、BB、IBB、HBP、K、current-pair runs、pitcher-charged runs 與 responsible catcher。零出局 appearance 保留為明確零值，不製造 rate。

| Season | Games | Pitcher-game controls | Ledger rows | Season pairs | Catchers | Ranking eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 2,429 | 21,545 | 2,947 | 2,721 | 116 | 60 |
| 2022 | 2,430 | 20,883 | 2,932 | 2,714 | 120 | 59 |
| 2023 | 2,430 | 20,634 | 2,627 | 2,416 | 102 | 63 |
| 2024 | 2,429 | 20,695 | 2,586 | 2,369 | 100 | 56 |
| 2025 | 2,430 | 20,870 | 2,814 | 2,590 | 111 | 57 |
| 2026 | 2,429 | 20,802 | 3,049 | 2,823 | 111 | 57 |
| Total | 14,577 | 125,429 | 16,955 | 15,633 | 660 catcher-seasons | 352 |

每季 official、pitcher-team 與 team reconciliation 的 outs／BF／R／ER／HR／BB／IBB／HBP／K 差異都是 0；PA、out、ledger keys 與責任歸屬 hard gates 全部通過。Automatic extra-inning runner 沒有 reach-PA catcher 時保留 null catcher，但仍納入投手總量，絕不人工指派。

## Slice 2–3：公式與投手組成基準

### 指標

| 指標 | 公式／來源 |
| --- | --- |
| cERA | `27 × catcher ER / catcher outs` |
| cRA9 | `27 × catcher R / catcher outs` |
| cFIP | `27 × (13×HR + 3×(BB+HBP) - 2×K) / outs + season FIP constant` |
| tERA | 依實際 pair outs 加權各投手完整官方球季 ERA |
| tRA9 | 依實際 pair outs 加權各投手完整官方球季 RA9 |
| tFIP | 依實際 pair outs 加權各投手完整官方球季 FIP，與 cFIP 共用年度 constant |
| cSaveRun | `(tRA9 - cRA9) × catcher outs / 27` |
| cSaveRun/IP | `cSaveRun / (catcher outs / 3)`；不年化 |

主 t 系列使用投手完整官方球季率來回答「該捕手實際搭配的投手組合，其完整球季水準如何」。Leave-catcher-out（LCO）只作獨立敏感度：pair 至少 30 LCO outs，aggregate 至少 90 supported outs，95% coverage 只決定診斷標籤，不決定主排行榜資格，也不以聯盟平均補值。

所有正 outs pair 都有完整 ERA／RA9／FIP；每位捕手的 pair weights 和為 1；c/t 公式可由原始分子與 outs 獨立重建。主排行資格固定為 `catcher outs >= 900`（300 IP）。

Cal Raleigh 2024 是代表案例：全部 `1122.0 IP` 都用於主指標，`cERA/cRA9/cFIP = 3.2968/3.5134/3.5854`，完整球季投手組成 `tERA/tRA9/tFIP = 3.4127/3.7123/3.6378`，`cSaveRun = +24.8059`、`cSaveRun/IP = +0.022109`。只有 `732.0 IP` 可建立 LCO，coverage `65.24%`；舊式 LCO 的 `+122.4425 runs` 因樣本選擇而只顯示為診斷，不控制主榜。

## Slice 4：cSaveRun reliability

Slice 4 已完成。結果不支持把 cSaveRun 發布成穩定的跨年捕手能力指標，但不妨礙它作為有清楚樣本與限制的單季描述量。

- 跨年主檢驗使用兩季都至少 900 outs 的同一捕手，對 `cSaveRun/IP` 建立 216 個 adjacent-season pairs。
- Pooled Pearson 為 `-0.047704`、Spearman 為 `-0.051107`，同號率 `49.54%`，平均絕對跨年變動為 `0.035447 runs/IP`。Pearson 的 catcher-cluster bootstrap 95% CI 為 `[-0.208721, 0.115507]`。
- 五個年度配對 cohort 的 Pearson 依序為 `0.097163`、`0.038239`、`-0.061016`、`-0.132862`、`-0.112984`，沒有一致的正向穩定度。
- Dominant-pair test 對每個 catcher-season 移除 paired outs 最多的投手，再由其餘 pair 原始分子重算 cRA9、tRA9、cSaveRun 與 cSaveRun/IP。352 個 ranking-eligible catcher-seasons 中，316 個在至少 600 個 non-dominant outs 下變動不超過 `0.02 runs/IP`，36 個超過門檻，0 個無法計算。
- 若 tier 被解讀為「可跨年延續的個人能力」，最終為 352 個 `limited`、308 個 `unavailable`、0 個 `supported`。300 IP 以下直接 unavailable；達 300 IP 者仍因 project-wide cross-year gate 失敗而不得升為 supported。這個 tier 不表示單季 cSaveRun 沒有被計算；只表示不得把它升格為穩定 talent grade。沒有縮尾、補值或年化。

Cal Raleigh 2024 的最大搭配投手為 Logan Gilbert（`202.1 IP`，占 `18.03%`）。移除後仍有 `919.2 IP`，cSaveRun/IP 從 `0.022109` 變成 `0.027537`，差 `+0.005429`，dominant-pair test 為 stable；但他仍是 `limited`，因為單一案例穩定不能推翻整體跨年 gate 失敗。

結論：cSaveRun 可保留為單季描述性「相對投手組成少失多少分」，不得作跨年 catcher grade、因果 catcher runs saved 或薪資／人才評價。

## Slice 5：Petehub xERA／cxERA／txERA

Slice 5 已完成 `catcher_descriptive_slice5_xera_v1`。正式模型為 `petehub_xera_v1_statcast_xwoba_additive`；它是 Petehub 自己的 xERA 定義，不是 MLB 公布公式。上游接觸品質使用 Statcast `estimated_woba_using_speedangle`，Petehub 負責時間序校準、ERA 尺度與可加總聚合。

### Target、時間契約與模型

- Benchmark 是使用者提供的 `data/pitcher_2021_2026_xStats.csv`，SHA-256 `538a48e179e70a23d6553266ac73af8e8b76ad7e3b8e128d5ab17c903f0b006c`。檔案為 FanGraphs-style、帶 Statcast xERA 的 season-pitcher export，共 5,159 個唯一 pitcher-seasons；原始下載 URL 未嵌在 CSV，因此 provenance 明確標為 `file_fingerprinted_source_url_not_embedded`，不冒充完整可追溯官方 snapshot。
- 2021–2026 各有 885／861／851／840／864／858 列；只有 2024 Tucker Barnhart 的 1 IP 列缺 xERA。以 `season + MLBAMID` 對齊，不使用 `Team`，因 641 列 `- - -` 是多隊合計。所有 IP 先按棒球記法轉成 outs；5,159 個 matching pitcher-seasons 與 canonical ledger 的 outs 完全相等，另有 80 個 ledger 投手球季不在 target，全部少於 1 IP。
- 凍結時間契約為 2021–2023 training、2024 selection、2025 final test、2026 external diagnostic。2026 已曾被舊模型與本專案查看，因此不稱為 pristine untouched test。
- 正式逐 PA 分子是 `0.6416147301907306 × expected_woba_sum - 0.09078536241180123 × BF`，再以 `xERA = 27 × expected_runs / outs` 聚合。線性權重允許個別 PA contribution 為負；只有聚合後的 rate 有棒球解讀。
- 未進 wOBA denominator 的事件 contribution 固定為 0；缺失 K／BB／HBP 使用 2021–2023 訓練期事件值；缺 tracking 的 BIP 使用凍結的訓練期 BIP mean expected-wOBA `0.371006598`。所有 fallback 類型與計數都保存，不用結果值或 catcher ID 補值。
- 曾比較加入 outs 的三特徵 additive 候選，但 canonical ledger 有一個 caught-stealing／mid-PA 換投案例，終結 PA 無法無歧義分配該 out。為維持逐 PA 分子可重建且不偽造 out ownership，正式模型選擇只含 expected-wOBA sum 與 BF；聚合分母直接使用已對帳 ledger outs。

### 驗證結果

| 時段 | Qualified pitcher-seasons | MAE | RMSE | Bias | Pearson | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021–2023 train | 1,663 | 0.167831 | 0.226041 | 0.027957 | 0.977737 | 0.982604 |
| 2024 selection | 541 | 0.176571 | 0.229049 | 0.107186 | 0.980029 | 0.982887 |
| 2025 final test | 542 | 0.159641 | 0.217482 | 0.046996 | 0.976579 | 0.978946 |
| 2026 external diagnostic | 539 | 0.152668 | 0.202850 | 0.010790 | 0.979958 | 0.980067 |

Qualified benchmark 固定至少 20 IP。2025 的 1,000 次 bootstrap MAE 95% CI 為 `[0.147257, 0.172340]`；所有 release gates（2024 MAE、2025 MAE／RMSE／bias／correlation、來源 coverage 與 reconciliation）通過。1,099,754 個 PA rows 中，source-supported BF 為 `99.710262%`；3,179 BF 使用明示 fallback，沒有把缺值偽裝為完整 tracking。

舊 xwOBA cubic 在 2025 MAE `0.715416`、bias `-0.715416`，排序相關雖高但絕對尺度系統性偏低。舊 expanded OLS 的 2025 MAE `0.138399`、2026 `0.118997`，但它用 2025 target 訓練：2025 是 in-sample、2021–2024 是把未來係數向後套用，不能作時間序 release comparison，因此只保留 diagnostic。

### 聚合定義與對帳

| 指標 | 定義 |
| --- | --- |
| xERA | `27 × Petehub PA expected-run components sum / pitcher outs` |
| cxERA | 同一 expected-run 分子聚合到捕手接捕的所有 PA，再除以 catcher outs |
| txERA | 每位實際搭配投手的 Petehub season xERA，依該 pair 的實際 outs 加權 |
| x Runs vs Mix | `pitcher-mix expected runs - catcher-PA expected runs`；正值代表 observed expected results 優於搭配投手基準 |

產物包含 1,099,754 PA、5,239 pitcher-seasons、15,633 pitcher-catcher pairs、660 catcher-seasons、180 team-seasons。PA／pitcher／pair／catcher／team 的總 outs 都是 774,146、BF 都是 1,097,198、expected-run numerator 都是 `121,756.737247976`（catcher 層只有 `1.5e-11` 浮點差）；pair 對 canonical ledger 的 outs 與 BF absolute difference 都是 0。

Leaderboard／Lab 已加入 cxERA、txERA、x Runs vs Mix、每局差值、來源 coverage 與 status；Paired Duo 加入 pair xERA、pitcher xERA 與同尺度差值。這些仍是 expected-results association，不是捕手因果價值。Slice 6 沒有改寫這些數值。

## Slice 6：Statcast FRV 來源 gate 與獨立防守軸

Slice 6 現行版本為 `catcher_descriptive_slice6_defense_v2`。產品主防守尺度由 DRS 改為 Statcast FRV，並顯示 Throwing、Blocking、Framing 三個捕手有效分項。DRS 仍保存在 artifact 作來源比較，但不再是 Leaderboard／Lab 主欄位。Park factor候選資料雖已於2026-10-20整理完成，仍沒有建立任何park-adjusted cERA、cSaveRun、xERA或綜合捕手分數。

### 2026-10-20 Park factor候選來源整理

- `data/park_factors_2021_2026.csv`是程式用canonical表，共177筆唯一`(season, team_code)`鍵。它把來源的59筆三年期venue-window列展開到各自涵蓋的三個球季，並保留`source_window`、起訖年與原始排行，因此不得把重複值誤稱為單季估計。
- 欄名改為snake_case；所有原始100基準值保存為`*_index`。`park_factor_multiplier = park_factor_index / 100`，`park_factor_delta_pct = (park_factor_index - 100) / 100`只為方便解讀，不代表已選定捕手調整公式。例如112同時表示1.12與相對中性+12%。
- 來源涵蓋2021–2023的30個venue rows及2024–2026的29個venue rows。使用者提供的後一窗口沒有Athletics，因此2024–2026保持unavailable，不補100或沿用Oakland。
- 尚未提供原始來源URL、下載日期與明確方法文件；`source_status`固定為`user_provided_no_url`。在來源血緣與調整方向確認前，它只是候選輸入，不會進入正式metrics artifact或Leaderboard。

### 來源、粒度與對帳

- 主來源為使用者提供的 `data/catcher_2021_2026_frv_statcast.csv`，SHA-256 `84ca9ccdf391f80419a7b3ab93a4e472dbd9978ae4ecc8361200c2c010c4a474`；comparison 來源仍是 `data/catcher_2021_2026_drs.csv`，SHA-256 `757de365cb71c8b0d277534e18430ac53e44d060e1568d51879403f91a4e2a1a`。
- 兩份檔案都是 FanGraphs-style season-team-catcher exports，皆未嵌入下載 URL，公開再散布權利尚未確認，因此目前只作內部研究資料。兩者各 731 列，2021–2026 逐年都是 126／135／112／106／121／131；key、姓名、來源 Inn 與 FRV 全部 731／731 精確相同。
- 唯一鍵為 `Season + Team + MLBAMID`。ARI／CHW／KCR／SDP／SFG／TBR／WSN 先正規化為專案 team code AZ／CWS／KC／SD／SF／TB／WSH；731 筆來源列全部對上 731 筆 canonical team-catcher rows，source-only 與 canonical-only 都是 0。
- 729／731 筆來源 innings 與 canonical outs 精確一致。兩個例外都是 2024 Danny Jansen：BOS 來源 `218.2 IP`、canonical `211.0 IP`，差 23 outs；TOR 來源 `444.1 IP`、canonical `443.1 IP`，差 3 outs。來源 `Inn` 只保留作稽核，所有資格與分母仍使用已經 official reconciliation 的 canonical outs，不為對齊外部表而改寫 ledger。
- FRV、Throwing、Blocking、Framing 在 731 列皆完整。Arm、Range、1B Rec 全列缺值，Inf DP 全列為 0；對捕手產品只發布三個有資訊的分項，不把空欄補成防守能力值。
- 494／731 筆 Throwing + Blocking + Framing 精確等於 FRV；其餘 237 筆只差 ±1。因來源分項已四捨五入，總 FRV 採來源欄位，不以顯示分項反算或覆寫。

### 發布欄位與整合邊界

| 欄位 | 工作定義與處理 |
| --- | --- |
| FRV | 來源提供的整季 Statcast Fielding Run Value，單位為相對來源所定平均基準的 runs above average；多隊捕手按 team rows 加總。正值是高於平均，不是絕對阻止的失分。 |
| Throwing | Statcast catcher throwing component，同樣是 runs above source-defined average。 |
| Blocking | Statcast catcher blocking component，同樣是 runs above source-defined average。 |
| Framing | Statcast catcher framing component，同樣是 runs above source-defined average。 |
| DRS | 另一套來源模型的 runs-above-average estimate，只留在 artifact 作比較，不與 FRV 混合或在主產品同列相加。 |

Leaderboard 與 Catcher Lab 顯示 FRV、Throwing、Blocking、Framing。`outs >= 900` 的 352 個 catcher-seasons 標記 `available`，其餘標記 `limited`，不做年化。Paired Duo 不顯示 FRV，因整季來源不能合理分攤到 pitcher-catcher pair。

352 個 qualified rows 中，FRV 對 cSaveRun 的 Pearson／Spearman 為 `0.113730／0.107880`，對 x Runs vs Mix 為 `0.120144／0.127095`；相較之下 DRS 分別為 `0.526107／0.506699` 與 `0.400647／0.393714`。這是選擇較少重複投球結果訊號的產品尺度之一，但不是因果識別。FRV 與三個 components 不加入 cSaveRun／x Runs，也不建立 composite score；components 已包含在 FRV 中，不能再次相加。

### 跨年診斷與限制

相鄰兩季都至少 900 canonical outs 的樣本共 216 pairs。FRV 的 Pearson／Spearman 為 `0.603703／0.616207`；Throwing 為 `0.389092／0.370968`；Blocking 為 `0.461043／0.485057`；Framing 為 `0.598371／0.592886`。DRS comparison 為 `0.424827／0.434314`。這些只描述來源指標的跨年行為，不是因果驗證，也不會推翻 Slice 4 對 cSaveRun 的結論。

Slice 6 v2 release gates 全部通過：六季存在、FRV source key 唯一、兩來源 731 keys／Inn／FRV 全數一致、canonical key coverage 100%、必要 FRV fields 完整、canonical outs 保持為分母、既有指標未被 defense 調整。尚存限制是FRV原始下載URL／公開再散布權利未嵌入來源、FRV不能分配至Paired Duo，以及park factor候選來源尚缺URL與調整契約，故目前仍沒有park adjustment。

## Slice 7：Dashboard release audit

Slice 7 已完成。Catcher Leaderboard、Paired Duo與Catcher Lab通過登入後headless Chrome release audit：2026主榜載入57個ranking-eligible rows；排序、搜尋、Minimum IP下拉、實際數據／PR值、Heat map、捕手列展開、40 IP Paired Duo預設、捕手與投手個人頁連結、投手反向展開所有捕手、Lab投手連結及窄版表格內捲動均正常，browser console沒有severe error。

稽核發現Leaderboard雖產生`?year=2026`連結，初始化卻固定為2021；現已改為只接受2021–2026合法query並正確載入指定年度。測試用本機認證session在稽核後立即撤銷，沒有新增或修改帳號。

## Slice 8：Model-consistent strategy bridge

Slice 8 已完成`catcher_descriptive_slice8_strategy_bridge_v1`。它不重新訓練Player Archetypes & Pitch Strategy模型，而是先核對凍結的Slice 6C decision values與Slice 6D diagnostics SHA-256，再於預設propensity threshold `0.025`聚合到2026場上捕手情境。

- 來源總量為713,853個observed pitch decisions；其中582,185個decision具有至少兩個supported choices並進入strategy diagnostics。
- 共111個catcher contexts；103個至少有500 supported decisions而標示available，8個標示limited。
- Catcher Lab顯示supported-set coverage、normalized entropy、effective supported choices、top-choice probability、supported deviation、model-minimum-choice rate、chosen support與四個count-tier splits。
- 2021–2025沒有同版本凍結strategy artifact，正式回傳unavailable，不以2026、聯盟平均或Average補值。
- `catcher_id`只表示該球場上捕手，是predictive context，不證明實際由誰選球。Normalized entropy是可預測性描述量；supported deviation是一側observational model comparison，不是真正exploitability或捕手因果價值。
- 所有individual deviation均未超過`0.294617 runs/pitch`的單球noise floor。因此release gate明確關閉catcher strategy leaderboard、composite score、individual best-pitch advice與caller attribution。

產品只把策略診斷放在個別Catcher Lab，與c/t/xERA、FRV及cSaveRun分軸呈現，不加入主排行榜或Paired Duo。

## 產品呈現

- Catcher Leaderboard 顯示 c/t 指標、cSaveRun、cSaveRun/IP、資格與限制；為降低表格寬度，BF／R／ER／HR／BB／HBP／K 不在排行榜顯示，但 API 與 artifacts 仍完整保留供公式重建與對帳。率平均按 catcher outs 加權，平均 cSaveRun 為顯示列算術平均，pooled cSaveRun/IP 為總 cSaveRun 除以總 catcher innings。
- Catcher Leaderboard 同時顯示 Petehub cxERA／txERA 與 xR vs Mix；頁面明示這不是 MLB 公布的 xERA 公式。`xR vs Mix = pitcher-mix expected runs − catcher／pair expected runs`，正值代表低於投手組成基準的預期失分。主表隱藏 xERA coverage／status，但 API、artifact 與 Catcher Lab 保留來源稽核資訊。Paired Duo 顯示 pair xERA 與該投手球季 xERA。
- Catcher Leaderboard 與 Catcher Lab 另以獨立防守軸顯示 Statcast FRV、Throwing、Blocking、Framing；所有欄位都是相對來源平均基準的 runs above average，不是絕對失分。FRV 不加入 cSaveRun／x Runs，Paired Duo 因來源粒度不足而不顯示或分攤 FRV。
- Catcher Leaderboard 將 cSaveRun、cSaveRun/IP 緊接在 xR vs Mix 右側，便於比較實際失分與預期失分兩套 observed association。主表隱藏 Reliability tier；Catcher Lab 與 API 仍保留 tier，主表繼續顯示 non-dominant innings、dominant-pair cSaveRun/IP delta 與 sensitivity status，且頁面保留全體跨年 gate 說明。
- Catcher Leaderboard與Paired Duo沿用Swing Timing的`實際數據／PR值`及Heat map控制。捕手PR母體固定為同季至少900 outs，pair PR母體固定為同季至少120 shared outs；ties取平均名次，搜尋、隊伍與顯示門檻不改變母體。c／t／xERA類rate採低值方向反轉，xR vs Mix、cSaveRun與FRV components採高值方向；所有PR都只表示同季合格樣本內相對位置。IP、場次、coverage、status、reliability與sensitivity欄位不做PR或著色。
- 表頭可切換 `Catcher Leaderboard` 與 `Paired Duo`。
- Paired Duo 一列是一個 season-pitcher-catcher，預設至少 `40.0 IP = 120 outs`，排行榜顯示 shared games、IP、c/t、cSaveRun 與 LCO 診斷；原始分子仍留在 API／artifacts 而不佔用表格欄位。2021–2026 預設列數為 265／247／277／282／278／259。
- 捕手與投手皆有頭像與個人頁連結；點 pair row 非連結區可反向展開同季該投手搭配的所有捕手，包含低於 40 IP 的配對。
- Minimum IP 使用有界下拉選單；捕手主榜為 100 IP 級距，pair view 保留 40 IP 預設。桌面搜尋框限制寬度，避免 filter 重疊。
- Catcher Lab在2026顯示Slice 8 strategy bridge；其他年度明示unavailable。它沒有PR、Heat map、排名或composite，避免把不穩定entropy與one-sided supported deviation包裝成捕手能力。

## Artifacts 與重建入口

- Slice 0 audit：`data/derived/catcher_descriptive_slice0_audit.json`
- Slice 1 snapshots／manifests／ledger：`data/research/catcher_descriptive/slice1/`
- Slice 2–3 metrics：`data/research/catcher_descriptive/slice23_preview/`
- Slice 1–3 closeout：`data/derived/catcher_descriptive_slice123_closeout.json`
- Slice 4 reliability：`data/research/catcher_descriptive/slice4_reliability/`
- Slice 5 xERA：`data/research/catcher_descriptive/slice5_xera/`
- Slice 6 defense source gate：`data/research/catcher_descriptive/slice6_defense/`
- Slice 8 strategy bridge：`data/research/catcher_descriptive/slice8_strategy/`
- Commands：`backend/scripts/build_catcher_descriptive_slice0_audit.py`、`build_catcher_descriptive_slice1_ledger.py`、`build_catcher_descriptive_metrics.py`、`build_catcher_descriptive_slice123_closeout.py`、`build_catcher_descriptive_slice4_reliability.py`、`build_catcher_descriptive_slice5_xera.py`、`build_catcher_descriptive_slice6_defense.py`、`build_catcher_descriptive_slice8_strategy.py`

重建程式只更新機器可讀 artifacts；本文件由專案維護者在同一處更新，避免每個 Slice 重新產生頂層 Markdown。
