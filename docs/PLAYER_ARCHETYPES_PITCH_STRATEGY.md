# Player Archetypes & Pitch Strategy

更新日期：2026-10-26
狀態：Slice 0–6D 與 3B practical profiles 完成；研究成果可用於描述性 profile 與 aggregate strategy diagnostics，不支援單球 best-pitch、投球建議、biomechanics 或因果宣稱

## 文件規則

這是 Player Archetypes & Pitch Strategy 小專案唯一的人工可讀主文件。後續 Slice 直接更新本文件中的章節，不再於 `docs/` 根目錄建立 per-Slice Markdown、獨立 catcher calling prework 或 supporting backfill 報告。精確輸出仍由 `data/derived/` 的 JSON／Parquet 契約保存；專案與 Slice 狀態以 `docs/PROJECT_TRACKER.json` 為準。

## 研究邊界

- Archetype 是描述性 profile，不是天賦評分。
- 同季 full-season tags 不可作同季逐球 pre-pitch feature；決策模型只可使用嚴格先前資訊。
- `target_*` 是要預測的實際行動，不是可在投球前使用的 feature。
- `fielder_2` 只能辨識場上捕手，不是「誰選了這球」的證明。
- 已投球的觀察結果可用於 post-pitch explanation，不可反推未投球選項的事實結果。
- 支援不足時 back off 或標示 insufficient，不指派虛假的 Average tag。
- 所有 best-pitch、causal、true exploitability 與個人戰術建議維持關閉。

## Slice 狀態

| Slice | 狀態 | 內容 |
| --- | --- | --- |
| 0 | 完成 | 舊 3×3、欄位涵蓋、時間可用性與缺值稽核 |
| 1 | 完成 | 投手角色與打者球季 warehouse |
| 2 | 完成 | Learned challenger tags |
| 2A | 完成 | 透明 arm-slot、arsenal depth／concentration／primary-pair tags |
| 3 | 完成 | 跨年穩定度、retention、邊界敏感度與 release decision |
| 3B | 完成 | Lab-first Pronation／Supination 與左右打 pitch-family usage profiles |
| prework | 完成 | 捕手配球資料稀疏度與層級 backoff 契約 |
| 4 | 完成 | 逐球 pre-pitch decision-state warehouse |
| 5 | 完成 | Hierarchical belief update challenger |
| 5A | 完成 | Observed location 與 Meatball post-pitch 說明 |
| 6A–6B | 完成 | Pitcher weapon state 與 batter threat surface |
| 6C | 完成 | Supported observational strategy value |
| 6D | 完成 | Aggregate game-theory diagnostics |

## Slice 0：來源與舊成果稽核

舊 3×3 把 Stuff／Command／BIP 等低維切分當成玩家身分，缺少角色、樣本支持、跨年穩定度與嚴格時間語意。結論是保留為 prior work，不作正式 player identity。

## 年度與玩家覆蓋

| Year | Pitches | Pitchers | Starters | Relievers | Batters | Qualified batters | Arm-angle row coverage | Catcher coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 712,320 | 909 | 292 | 542 | 1,049 | 463 | 37.1% | 99.6% |
| 2022 | 710,210 | 871 | 284 | 516 | 693 | 469 | 0.0% | 99.7% |
| 2023 | 720,684 | 863 | 294 | 529 | 656 | 462 | 99.6% | 99.6% |
| 2024 | 711,898 | 855 | 302 | 489 | 651 | 455 | 99.6% | 99.6% |
| 2025 | 712,528 | 873 | 289 | 522 | 673 | 461 | 99.6% | 99.6% |
| 2026 | 716,544 | 868 | 275 | 557 | 662 | 465 | 原始 73.9% | 99.6% |

Raw-row coverage、qualified-player coverage 與 feature-specific denominators 必須分開解讀。缺失年代不補值成已觀察值。

### 2026 Arm Angle supporting repair

官方 backfill 把 2026 Arm Angle coverage 從 `73.580%` 提升到 `99.327%`，完整零覆蓋日期由 46 降到 0，共補入 184,493 個官方值。仍有七個日期低於 98%，因官方個別日期重抓沒有新增值而保持 null，未做 synthetic imputation。這是本專案的來源修復，不是另一個獨立研究專案。

## Slice 1：Warehouse

Warehouse 保存 pitcher-season-role 與 batter-season 兩種 grain；starter／reliever 身分依 appearance role 建立，hybrid pitcher 保留 SP、RP 兩列與 role pitch share。所有列均為 full-season descriptive，不能作同季 pre-pitch belief。

| Year | Pitcher role rows | Eligible | Hybrid | Batter rows | Eligible batters |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021 | 1,157 | 834 | 248 | 1,049 | 463 |
| 2022 | 1,074 | 800 | 203 | 693 | 469 |
| 2023 | 1,094 | 823 | 231 | 656 | 462 |
| 2024 | 1,039 | 791 | 184 | 651 | 455 |
| 2025 | 1,082 | 811 | 209 | 673 | 461 |
| 2026 | 1,118 | 832 | 250 | 662 | 465 |
| Total | 6,564 | 4,891 | — | 4,384 | 2,775 |

Pitcher role key 與 batter-season key 無重複。Season Plus 來源不是 role-specific，因此會在同投手 SP／RP 列重複，使用端必須保留 source flag。

## Slice 2／2A：Tags

Slice 2 以可驗證的 challenger clustering 建立多維 profile，保存 selected `k`、silhouette、membership、stability、rule/GMM agreement 與 minimum support；玩家可有多個 tag，沒有足夠證據時不勉強分類。

Slice 2A 增加透明、可手算的 arm-slot 與 arsenal tags，包括 arsenal depth、concentration、primary pair。這些 tag 用於說明 repertoire 形狀，不是成績評分，也不可拿同季完整資料洩漏到同季逐球預測。Primary Pair 仍保留在 frozen artifact 供研究追溯，但因產品解讀不直觀，已從 Pitcher Tag Lab、Game Center hover 與 read API distribution 隱藏。

## Slice 3：Validation

- Roster 共 10,948 列，duplicate keys 為 0。
- 具至少三個 core tags 的 player-season 共 7,477 列。
- 驗證涵蓋 same-role adjacent-year retention、跨角色比較、邊界擾動與 tag balance。
- Release decision 只允許達到樣本、穩定度與可解釋門檻的 profile；未通過者保持 research-only 或 withheld。

## Slice 3B：Practical profiles v1

這批標籤另存為 `player_archetype_practical_tags_v1`，只補充 Lab 與 Game Center 的完整球季描述，不覆寫 Slice 3 四個 core tags，也不回寫 Slice 4–6D 的既有研究資料。正式拼字使用 `Supination`；Pronation／Supination 在此只代表手別標準化後的橫向位移形狀，不是實際手腕動作、傷害風險或 mechanics 測量。

### Pronation／Supination 規則

- 橫向位移先轉成投手視角：RHP 使用 `-pfx_x × 12`、LHP 使用 `pfx_x × 12`，arm-side 為正、glove-side 為負。
- 每個球種至少 20 球、占該 role-season 至少 5%，並只和同年、同角色、同投球手、同一球種且至少 20 人的 cohort 比較。
- Pronation family 為 FF／FA／SI／CH／FS／FO；至少一個有支持球種達到 `+0.5 SD`，且該 family 依投球數加權後仍達 `+0.5 SD`，才成為 `Pronation` candidate。
- Supination family 為 SL／ST／CU／KC／SV；使用完全對稱的規則，至少一個有支持球種與加權 glove-side family profile 都達 `+0.5 SD`，才成為 `Supination` candidate。
- 若兩個 candidate 同時通過則依 XOR 規則全部隱藏；證據不足維持 unassigned／insufficient，不用 generic tag 補滿。這取代「每個 family 至少兩種強球」的不對稱規則，避免因常見 repertoire 結構讓 Pronation 被系統性放大。

### 左右打策略規則

- 左右打各至少 40 球；分別計算 Breaking Balls（SL／ST／CU／KC／SV）與 Offspeed（CH／FS／FO）的完整球季使用率。
- 某一打者側的 family usage 至少 25%，且比面對另一側高至少 12 個百分點，才標示 `LHB/RHB More Breaking Balls` 或 `LHB/RHB More Offspeed`；不再用單一 Slider／Changeup pair 描述整體策略。
- 同一投手可各有一個 LHB 與 RHB profile；它只描述球種 family 使用差異，不代表該配球有效、是捕手決策或應採取的策略。

### 實際覆蓋與穩定度

2021–2026 共 6,564 個 pitcher-role-season rows，Pronation 1,078、Supination 841；左右打策略有 2,445 列至少一個標籤。2026 的結果如下：

| Role | Movement eligible | Pronation | Supination | XOR suppressed | Movement tagged | Platoon eligible | Platoon tagged |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SP | 275 | 62 | 49 | 21 | 111（40.4%） | 271 | 122（45.0%） |
| RP | 555 | 119 | 103 | 36 | 222（40.0%） | 541 | 264（48.8%） |
| Total | 830 | 181 | 152 | 57 | 333（40.1%） | 812 | 386（47.5%） |

同角色相鄰球季 retention：Pronation 63.1%（648 pairs）、Supination 58.3%（489）；LHB More Breaking Balls 53.7%、LHB More Offspeed 54.9%、RHB More Breaking Balls 51.8%、RHB More Offspeed 68.8%。穩定度仍只屬中等，因此 release decision 為 `monitor`，不得升格成固定身分類型。

## Pitch-calling prework

### Coverage and sparsity

2021–2026 `fielder_2` 幾乎完整，因此可建立場上投捕 context，但稀疏的 pitcher-catcher-count-stand cell 不足以直接當可靠的配球偏好。必須使用 pitcher → pitcher-count-stand → pitcher-catcher-count-stand 的階層式 support 與 backoff，並保留樣本數。

### Strictly prior support

所有逐球 context 只可使用該球之前的紀錄；unseen 或 low-support state 必須 back off。捕手欄位是 predictive context，不是 who selected the pitch 的證明。

## Slice 4：Pitch-decision state warehouse

Integrity：passed；共 4,268,301 列。

### A–D deliverables

- 每顆可用 pitch 一列，保留唯一 decision key、當下 count／base-out／platoon／score context。
- `target_*` is the action to predict；target 與 pre-pitch feature 明確分離。
- 只合併 prior-season tags、嚴格 lagged support 與 hierarchy fallback。
- Same-season full-year tags are forbidden，避免未來資訊洩漏。

| Year | Rows | Duplicate keys | PA boundary errors | Map mismatch |
| --- | ---: | ---: | ---: | ---: |
| 2021 | 709,486 | 0 | 0 | 0 |
| 2022 | 708,156 | 0 | 0 | 0 |
| 2023 | 717,673 | 0 | 0 | 0 |
| 2024 | 709,224 | 0 | 0 | 0 |
| 2025 | 709,909 | 0 | 0 | 0 |
| 2026 | 713,853 | 0 | 0 | 0 |

## Slice 5：Belief update

模型使用 `2021–2024 train`、2025 前半 development、2025 後半 validation、2026 untouched test 的時間分離。選定 hierarchical challenger，並保留 frequency baseline、support tier、calibration、log loss、Brier、Top-1／Top-2、macro recall 與 ECE。

Cold-start 或低於 100 列的 subgroup 報 insufficient；它們 are never assigned an Average tag。捕手 context 可改善預測時仍只是 association，not proof of who called the pitch。

## Slice 5A：Observed location

Meatball 定義為 plate 的 `middle third horizontally and vertically`（zone 5 類型）。它只描述已發生投球位置，not a verified command miss；相關圖表與數值是 `post-pitch explanation only`，不可作投球前可用 feature 或未投球選項結果。

## Slice 6A–6B：Weapon 與 threat

Slice 6A 對每個 supported candidate 建立 exact-pitch pregame baseline 與嚴格 lagged 的同場 Stuff+／Location+ readiness。2026 的 713,853 個 decisions 產生 3,910,760 candidate rows，candidate state coverage 100%，future-count、duplicate 與 chosen-target mismatch 都是 0；同場狀態只使用 `earlier pitches in the same game`。

Slice 6B 只以 2021–2025 建立 batter × pitcher hand × count tier × pitch family × batter-relative location 的 Hunt+／Contact+／Damage+ surface，共 231,105 列，其中 230,785 batter cells、320 league fallback cells。2026 chosen pitch contexts 中 high support 67.31%、limited 14.79%、sparse 8.06%、league fallback 9.84%。這些狀態 do not yet identify a factual best unthrown pitch。

## Slice 6C：Supported strategy value

pre-pitch HistGradientBoosting challenger 以 2025 前半 development、後半 validation、2026 evaluation。所有 3,910,760 candidates 都能 scoring；在 2.5% propensity、20-pitch weapon、30-pitch threat gate 下，582,185 decisions（81.56%）至少有兩個 supported choices，556,315 observed choices（77.93%）受支援。

Validation RMSE 0.228234（threat-only 0.228442）；2026 RMSE 0.224830（baseline 0.225102）。然而單球 90% half-width 為 0.294617 runs，沒有 alternative interval 能分離。因此 Individual best-pitch labels remain disabled；single-pitch run value is noisy，只釋出 aggregate observational comparison。

## Slice 6D：Game-theory diagnostics

先驗證 frozen Slice 6C SHA-256，再於四個 propensity gates 產生 2,303,246 筆 threshold × decision diagnostics。2.5% gate 下：

- 582,185 decisions；normalized entropy 0.8571；effective supported choices 3.497；top-choice probability 46.83%。
- one-sided supported deviation 為 0.003188 runs/pitch；沒有 deviation 超過 0.294617-run noise floor。
- pitcher-cluster 90% intervals 涵蓋 Overall、role、count-tier 與 platoon，default subgroup 沒有低於 500 decisions。
- BatterAhead 的 entropy 跨 gate 最多變動 0.1051，因此不發布 entropy leaderboard。

這是 supported-deviation sensitivity，`not true exploitability`。現有不確定性 `cannot support a factual-best-pitch`、個人 advice 或因果結論。

## 產品位置

Player Archetype roster／Tag Lab 應位於 Pitcher Lab 研究區，而不是 Catcher 頁面或首頁獨立驗證卡。UI 必須顯示 sample support、cross-year checks、balance warnings 與「profiles, not talent grades」。

## Artifacts 與重建入口

- Slice 0–3 contracts：`data/derived/player_archetype_slice0_audit.json`、`player_archetype_slice1_warehouse.json`、`player_archetype_slice2_challenger.json`、`player_archetype_slice2a.json`、`player_archetype_slice3.json`
- Slice 3B practical profiles：`data/derived/player_archetype_practical_tags_v1.json`、`player_archetype_practical_tags_v1.parquet`、`player_archetype_practical_tag_distribution_v1.parquet`
- Pitch-calling prework：`data/derived/catcher_pitch_calling_prework.json`
- Slice 4–6D：`data/derived/player_archetype_slice4*` 至 `player_archetype_slice6d*`
- 2026 Arm Angle repair：`data/derived/arm_angle_backfill_2026*`
- Rebuild scripts：`backend/scripts/build_player_archetype_*.py`、`build_catcher_pitch_calling_prework.py`、`backfill_2026_arm_angle.py`

重建程式只更新機器可讀 artifacts；本文件由專案維護者在同一處更新，避免每個 Slice 重新產生頂層 Markdown。
