# Petehub 新對話交接

## 2026-11-15：Swing Timing 字級、展開寬度與水平拖曳條

使用者回報排行榜／展開明細太小、右側裁切且沒有可見水平拉條。查得 `docs/RESEARCH_DISPLAY_CONTRACT.md:12` 已規定桌面正文 14px／表頭 12px、最低 12px，以及寬表水平捲動；本頁原 9–10px 表頭／明細不符。僅修改 `frontend/pages/batters/lab/swing-timing.vue`：主表數字／姓名 16px、表頭 12px、展開明細 14px／次要字 12px，增加欄寬及表格最小寬 2056px；標題操作列可換行。表格上方新增具 aria-label 的 range 拉條與原生 scrollLeft 雙向同步，底部原生 scrollbar 加粗上色。ResizeObserver 只供產品執行時量測容器寬度，限制展開面板為可視容器寬並 sticky left，避免跟著整張寬表撐大；三維卡片／matrix／gear 明細依容器與換行呈現。未改資料或模型，未做瀏覽器／DOM 視覺檢查或啟動 server；只一次 Vue template／TS syntax／scoped CSS compile 與 diff 檢查。人工入口 `/batters/lab/swing-timing`，待使用者核對字級、展開右側、頂部拖曳與底部水平捲動、窄窗換行。未宣稱畫面通過。

## 2026-11-15：Swing Timing 搬入 Stuff Attack 回歸功能

使用者要求保留 Stuff Attack 原可選欄位，再加入 Swing Timing 欄位。已於 `/batters/lab/swing-timing` 排行榜上方加入折疊回歸區，展開才用原 API 的 `include_regression=true` 載入，保留頁面全部條件與最低樣本限制。新 service `batter_swing_regression_service.py` 重用 Stuff Attack flags／同樣 Adjusted 公式，以向量化聚合提供原 20 軸＋21 個 K／BB／三維對位軸＋Age／Season PA／Filtered Swings／Filtered Terminal PA 共 45 選項；原 Stuff Attack 頁面不改。無 Stuff+ 門檻套到本區，缺值不填零；對位欄跟既有 summary／matchup_event 模式一致。距離／時間偏差用表格同樣的絕對幅度；負 RV／K−BB／有向角度不取絕對值。

新 `BatterTimingRegression.vue` 共用 `linearRegression.ts`，顯示散點、回歸線、N／Pearson／R²／斜率／p／雙尾檢定；用全部有 X／Y 的合格球員與姓名搜尋，實際值等權 OLS，不受 PR 模式影響、不截前 200 名。切軸／條件清舊結果，過期回應忽略；可點頭像開原球員展開資訊。`timingRegression.ts` 處理有限值完整樣本與軸範圍，JS 檢查涵蓋真零／負數／null／NaN／Infinity、無變異、少樣本、>200 人、不修改來源。16 項 regression／timing／matchup／Stuff Attack Python 測試通過，正式 2026 DB 第一次額外聚合約 2.575 秒、同條件快取 0.004 秒；不是 UI 時間。未操作瀏覽器／截圖／server，人工入口相同頁面，驗收展開載入、45 選項、執行／清除、樣本與缺值、原排行榜保持可用。其他 Slice 與 lineup 跑壘修正未開始。

## 2026-11-15：Swing Timing 主欄位新增五項條件統計

使用者要求在三維切頁 Swing 與 Avg Miss Distance 間加入 avg bat speed、ideal bat angle%、K%、BB%、K−BB%（口述四項但明列五項，已明示按五項實作）。`SwingTimingLeaderboardRow`／前端型別新增角度與 K／BB／差值、三個分母；`batter_swing_matchup_service.filtered_batting_metrics` 以正式逐球來源 SQL 精確篩選、去重與聚合，summary／matchup API 皆用 model_copy 合併，不污染 Savant cache。棒速 competitive 口徑、Ideal Attack Angle 5°–20°；K／BB 以條件內終結 PA 為分母，不從只有 bat tracking 的 swings 計算。既有整季 PA 欄／PA 門檻不變，新增欄位 tooltip 顯示各自分母；球種依終結球判定。三切頁共用五欄，支援排序、PR 與 Heatmap、mph／百分比單位，寬表填滿容器且保留水平捲動。

驗證含完整 DB 李灝宇全條件／FF＋R／FF＋R＋NYY（皆有隨條件改變）、9 項 timing／matchup 測試與一次 vue-tsc。人工入口 `/batters/lab/swing-timing`；核對三切頁五欄順序、切球種／左右手／球隊的數值、PR／排序／上色、缺值與橫向捲動。未操作瀏覽器／server／截圖，畫面待使用者驗收；未修前一輪另外發現的 lineup 跑壘邏輯，未恢復其他 Slice。

## 2026-11-15：打者期間比較篩選修正與影片／Plus 串接

使用者回報李灝宇 6/12 前 0-0 AVG=0 但 PA Hit 有球。核對 701678 正式 DB：0-0 共 87 球，終結球為 8 個 field_out、其餘 79 非終結，故 H/AB=0/8 正確；17 顆 0-0 屬最終安打 PA，這與終結球 AVG 不同。比較頁補口徑文字；修正 PA 結果篩選須先於球數／球種，並依使用者新增 `Pitch result=Hit`（只取安打終結球）。比較服務原未載入正式逐球分數，現在接既有 Stuff／Location 快取；該 87 球均有分數與影片映射。補 balls／strikes／is_swing／zone，Discipline 點擊逐層傳到既有 ComparisonPeriodVideos 的 A/B 影片視窗，切篩選清空選球；沒有把缺值顯示成零，沒有補造 Stamina。

減少每面板重算 flags，加入最多 8 組、來源版本與 120 秒時間桶失效的球員年度快取。服務量測原 1.713 秒，修後冷載 1.610、重複 0.703 秒；只量後端，不宣稱 UI／遠端影片驗收。16 項期間比較與 discipline 測試、一次 vue-tsc 通過。沒有啟動／操控瀏覽器、截圖或另開 server。人工入口 `/batters/comparison/period`，年度 2026、李灝宇、以 6/12 分窗，核對兩種 Hit、0-0、分數與點球影片、反覆篩選。其他模型／Slice 仍暫停。

2026-11-15 進站故障修復：使用者回報 Nuxt 500／`IPC connection closed`。僅核對並重啟原本 `C:/intern/project_transfer/frontend`、127.0.0.1:3000 的 Nuxt 程序及其同專案子程序，未另開驗收環境，也未動 3001 舊專案或後端。新日誌在 `frontend/.logs/nuxt-recovery-20261115.{out,err}.log`；啟動後對原投手網址的無登入 HTTP 請求回正常 302 登入轉址，未使用 cookie／fixture、瀏覽器或 DOM。此為服務恢復證據，登入後畫面及熱圖仍由使用者驗收，未推定通過；未修改模型或恢復其他 Slice。

## 2026-11-15：In game 直接共用 Batter Personal 逐球熱圖

使用者明確要求「照抄 batter personal 熱力圖，預設 Swing%／100%」，已以既有 `personal/discipline` 的逐球位置資料取代 Game／Pitcher Personal In game 的分區 PR 圖。`StrikeZoneScatter.vue` 原有 64×52 Gaussian 計算抽至 `frontend/utils/pitchLocationHeatmap.ts`，Personal 原數學與預設不改，In game 共用此函式且選 choice=Swing%、Blend=1；保留 Density／Bat speed／滑桿，預設所有球數、可選僅看目前球數。依當前投手手別及打擊側篩選，來源是所選年度完整賽季描述，不是 before-date 情蒐預測。

`batter_service._build_batter_location_points` 只新增 `p_throws`／`stand` 欄位供前端篩選；沒有新 API、沒有補抓或重建 PR。舊分區 API／快取仍保留，但此圖已不依賴。原始資料、球路及影片未修改；Personal 顯示 X=-plate_x 只反轉一次回 replay 實體座標，3D 保留好球帶邊界、去除內部九格線，貼圖涵蓋平滑資料的帶外範圍。既有 Pitch Scout 僅在使用者開啟面板時請求，仍用原 prior-date 契約，不與整季熱圖混稱。

共用熱圖與快取來源／數學檢查、一遍 direct vue-tsc、逐球來源手別／站側／Swing flags 與 UTF-8 檢查完成；未開瀏覽器、server、截圖、DOM 或宣稱畫面通過。人工檢查入口 `/pitcher-personal?tab=in-game` 與 Game Replay：預設 Swing%／100%、平滑無灰色九格、切球／打者／手別及滑桿更新。其他模型／Slice 與動作設計仍暫停，沒有開始 Slice 11。

## 2026-11-14：Slices 6–10 完成、UTF-8 修復、研究模型保留晉升門檻

使用者授權「可以 開始slice6-10」，網路中斷後要求接續並修復 Slice 1–5 的問號亂碼。本輪已完成 `pitcher-decision-support` P0／0–10，**12/24**；11–21 planned、22 deferred。亂碼來自先前寫入字元轉成問號，已依 evidence 重寫權威 `PROJECT_TRACKER.json`，再產生主文件、前端快照與進度表；本專案內容已檢查 UTF-8 與連續問號。不要只改產生的 Markdown。其他專案既有佔位字樣不在本次修正範圍。

研究產物在 `data/research/decision_support_temporal_20261114/`；小型證據 `data/sample/petehub_pitcher_decision_slice6_v1.json` 至 `slice10_v1.json`。`protocol.json` 在訓練前凍結，`models/` 保存各 fold 的 joblib／metadata，`validation.json` 與 **151 檔 SHA manifest** 保存來源檢查；正式 Stuff／Location metadata SHA 不變，既有正式 Stamina／Performance State 未替換。研究方法與正式分數不同，不得直接補進正式快取。

Slice 6–7：四個參考期，2021 H2 使用截至 2021-07-01、2022 使用截至 2021 年底、2023 使用截至 2022 年底、2024–2026 均凍結截至 2023 年底；訓練比賽必須在 cutoff 前已結束。主要速球只取此前已關閉登板的 FF／SI／FC，至少 20 球。以官方 eventIndex 逐球和 Statcast 速度／位置／球種驗證對位，歧義不硬配。研究 Location 預測位置／情境的投手正向 RE，研究 Stuff 預測扣除位置／情境後的物理殘差，並非正式 marginal-context Stuff+。2021 上半年 346,433 顆實投保留暖機；2022–2026 研究 Plus 覆蓋約 98–99%。100 是訓練參考中心，不保證當年中位數 100，也不以 110 解讀為好 10%。

Slice 8–9：SP 前 20＋至少 15 球、RP 前 5＋至少 5 球，分開 Quality／Physical／Command，保留同球種基準、支援比例、近似 80% 抽樣區間與 n/(n+20) 收縮權重（不是經校準的正確機率）。早段／晚段只納入來源可用且對位的實投；>8h 中斷重新暖機。Ridge 角色預期控制用球數、早段狀態、已關閉歷史及嚴格更早的打席邊界近期用球、休息、連續日、同日、過去角色／長局數與 PA-LI。候選僅附登板前已結束登板的最後觀測狀態，不用本場前五球，不是準備度預測；所有個別排名關閉。2024 SP 有 prefix 的登板 4,716、RP 13,529；短登板、支援不足與 2021 暖機保留缺值。

時間檢查曾抓到候選 ASOF 的同名欄位衝突，已改用唯一的 `completed_state_available_at`；不能把 prefix 自身的過去基準 `history_available_at` 當成該完整登板狀態可用時點。候選必須同時滿足 `max(prior_state_closed_at, prior_state_observed_at) = prior_state_available_at < cutoff`。另有 2026 一顆投球完成時間比換投事件晚 6.474 秒，歷史可用時點取兩者較晚；不得提早採用。最終候選與決策時間檢查皆為零違規。本版先發評到 100 球、牛棚評到 60 球，超出範圍決策狀態為 `outside_modeled_pitch_count` 並清空分數及區間，不把最後一次分數當作仍在更新。

Slice 10：歷史中性 WE、24-state／延長賽收縮 RE、預期絕對 WE 波動的研究 **PA-LI**；不是同年實際 WPA 平均，也不宣稱精確重製 FanGraphs LI。WE 參考期內按完成比賽時間 80/20 固定 Platt 校準；七局、終局、再見與延長賽跑者規則有測試。全部 1,099,754 個官方決策都有前置列，暖機／壘包或來源不可靠不填分，缺 LI 不補 1。2024 固定 WE Brier 0.157961、log loss 0.472171；中性 WE 不包含球隊強弱或換投效果。

**下游只用窄特徵契約**：`pitch_features_YEAR`、`decision_states_YEAR`、`context_features_YEAR`、`candidate_state_priors_YEAR`；`pitch_labels_YEAR`／`context_labels_YEAR` 是另存結果。`observations`／`features`／`scored` 是訓練與稽核倉儲，包含結果欄位，不得整列交給決策模型。模型參考下的實現 WPA／守方 RE24 不是換投因果歸屬，原始來源 WPA 仍保留在 play 表。

事件身分修正：發現原 parser 將部分代跑當作當下打者替換；改為只倒推真正打者的替換鏈，僅改官方 events／decisions 的 `batter_id`，其餘欄位與投手／時間／實投／負荷／候選排除保持一致，保存 `before_identity_*`、`batter_identity_changes_*` 與 `batter_identity_repair.json`。剩餘 27 顆來源打者 ID 歧異另列 `batter_identity_disagreements_YEAR` 與 `source_batter_consistent`；後續對戰模型必須確認或排除。此錯誤 ID 未列入本輪模型輸入。修復腳本重跑只驗證，不覆寫原始修正證據。

2024 已觀測 prefix 路徑比較：SP Quality RMSE 2.2869 vs 近期負荷基準 2.4408，Command 2.0890 vs 2.9139；RP Quality 4.9598 vs 5.3614，Command 4.7608 vs 6.4539。另有純用球數基準及重疊 prefix 描述性持續度。這些不是下一段預測或決策因果驗證；Plus 的物理殘差增量很小（Location RMSE 0.244997，加入 Stuff 殘差 0.244993），不晉升正式模型。2025／2026 只評分與覆蓋，沒有檢視其結果指標來挑模型；2026 是歷史重播，不是前瞻部署。

重跑順序（backend .venv）：`freeze_decision_temporal_protocol.py` → `build_decision_temporal_observations.py --year YEAR` 六年 → `--references` → `train_decision_temporal_plus.py` → `build_decision_temporal_context.py` → `build_decision_prefix_states.py` → `repair_decision_batter_identity.py` → `finalize_decision_temporal_research.py` → `export_pitcher_decision_plan.py` → `sync_project_tracker.py`。prefix 支援 `--fit-only` 與不重訓的 `--publish-only`；不要無故重跑已完成訓練。正式 guard／協定不可默默重設。

已完成 22 個局部 pytest、一次直接 vue-tsc、UTF-8／權威與產生快照一致性及六年時間／鍵檢查；均為 source-only，沒有 browser／server／DOM／截圖或任何畫面驗收。`/lab/decision-support` 新增 Slice 6–10 結果區、覆蓋表與限制，**新增畫面仍待使用者人工驗收**。未開始 Slice 11、xWPA／xRE24 行動模型、Personal 電池條、In game 同步、換投燈號或任何 Ballpark Slice。

## 2026-11-14：授權 Slices 2–5，研究資料層交付、新結果待人工

使用者回覆「都可以 開始繼續slice2-5」，Slice 1 新報告區塊已人工接受。本輪 `pitcher-decision-support` P0／0／1／2／3／4／5 done，7/24，6–21 planned、22 deferred；未開始 Slice 6。`/lab/decision-support` 新增 Slices 2–5 摘要、逐年表與名單信心限制，舊 Slice 0／1 明示補齊前快照。僅新增結果區待使用者人工驗收，不撤銷既有 P0／Slice 1 驗收。沒有 browser／server／DOM／截圖。

Slice 2：兩場最新公開 Savant game CSV 精準修復，2024 game746731：319→320（PA68 第4球改回 blocked_ball、第5球 strikeout），2026 game823244：10→258；DB／年度 gzip CSV／本機 meta 已同步。`data/research/decision_support_slice2_20261114/` 保存原始 game／CSV／meta 備份與來源 URL／UTC／SHA。其他 game 的全列 hash 不變，CSV EXCEPT ALL round-trip 通過；既有 lookup 原已完整，不重建全季。正式 Plus／Stamina／Performance State 產物不重訓、不晉升；舊衍生快照不冒充新來源，後續依版本處理。

Slice 3：`data/research/decision_support_pipeline_20261114/` 保存六年 `events_YEAR`／`plays_YEAR`／`decisions_YEAR`／`appearances_YEAR`／`roster_YEAR`／`runners_YEAR`。共14,577場、4,866,152事件、4,270,416顆實投、1,099,754 play、125,429登板段（含21零球段／重新上丘，不是官方G）。唯一鍵與 BF 對既有官方帳本一致，結果只存 play 一次；386個 WE 邊界留 null 待 Slice10。代跑承接壘包、打席中換投、繼承跑者、零球、再見與2021七局已處理；121場七局依 linescore.scheduledInnings，不從缺欄的 gameData.game 猜9。未知壘包標記，3場來源時鐘問題／234個邊界另標，不強改時間；Statcast與官方逐球不能僅按pitch_number假定同鍵。

Slice 4：`workload_YEAR`／`workload_sessions`／`closed_role_history` 共125,412實投session（4個中斷重開session），依UTC嚴格 t'<t、跨隊／SP-RP累積1/3/7/14日滾動小時窗。紐約日期算連續登板，同日多場不依gameID；>8h切段是資料規則，不是恢復假設。封閉後才使用總用球／角色歷史，前2021／春訓／小聯盟未知，2021開頭13,187邊界標14日左截斷。200獨立邊界×4視窗 brute-force一致；所有決策時間違規／重複0。2021七局修正沒有改負荷輸入的實投key/actor/time指紋。

Slice 5：`bullpen_sets_YEAR`／`bullpen_candidates_YEAR` 是完整官方game-day玩家名單的**名義候選**，不是最終出賽者名單或已證實實際可用牛棚。72組指定日期active-roster公開快照保存在`dated_roster_probes/`：66一致、6衝突；大多數日期仍`official_game_roster_date_unverified`，另有不足／衝突標記。候選排除現任、已用、換下、位置切換不明與常規三打者門檻不支持者，附嚴格過去負荷、前次用球、連續日、同日、先發／長局數歷史；醫療／熱身 null、精確同日異動／停賽未知，所有 `individual_ranking_allowed=false`。不得宣稱全日期active驗證、完整當下可用或最佳人選；Slice6須先凍結這些信心／排除條件。

重跑命令（backend .venv）：`scripts/repair_pitcher_decision_sources.py` → `scripts/build_pitcher_decision_ledger.py --year YEAR` → `scripts/build_pitcher_decision_workload.py` → `scripts/build_pitcher_decision_candidates.py`（可 `--year`）→ `scripts/finalize_pitcher_decision_foundation.py` → `scripts/export_pitcher_decision_plan.py` → `scripts/sync_project_tracker.py`。源碼在新 service `app/services/pitcher_decision_ledger.py`，小型證據 `data/sample/petehub_pitcher_decision_slice2_v1.json` 至 slice5。14局部pytest、一次vue-tsc、六年key／時間／名義候選排除／null可用性及1,066,310列候選負荷對精確SQL四視窗一致性檢查通過；畫面仍待人工。未訓練xWPA／xRE24、未做Personal／In game電池／預警，也未開始任何Ballpark Slice。

## 2026-11-12：Pitcher Decision Lab 規劃頁通過、Slice 1 完成

使用者回覆「通過 開始slice1」，P0 規劃頁人工驗收完成。本輪 Slice 1 完成六年賽程／來源與缺漏核對，`pitcher-decision-support` 目前 P0／0／1 done，2–21 planned，22 deferred，3/24。主文件 `PITCHER_DECISION_SUPPORT.md` 與前端快照由 `backend/scripts/export_pitcher_decision_plan.py` 產生；`/lab/decision-support` 新增 Slice 1 結果區，僅此新增區待人工，不撤銷 P0 既有驗收。

Slice 1 只新取 6 份無 key／cookie 的公開 StatsAPI 賽程，沿用捕手研究 14,577 場既有官方 raw feed，讀取所有來源 DB 均 read_only 且 mtime／size 未變。唯一完成賽程／本機 IDs 均 14,577，缺整場與整日 0；2021／2024／2026 各 1 場 Cancelled 排除（abstractGameState=Final 也可能取消，須依 detailedState）。2026-03-25 game 823244 本機 10 球 vs feed 258 顆實投，缺 248；2024-04-06 game 746731 PA68/pitch5 另 1 顆需核對來源修訂。2022 game663053、2023 game716704／717170 的最後比分差異是再見 balk，不能當缺投球。另有 14,017 本機編號鍵不對應、262 官方完成 play 無本機列、598 本機序列無終結事件；多含自動球／零球／時鐘與編號語意，留 Slice 3 正規化，不直接刪資料。

完整 Slice 1 evidence 在 `data/research/decision_support_slice1_20261112/`（sources URL／UTC／SHA、逐年 games／issues／feed inventory、逐日 CSV、report）；小型版本化證據 `data/sample/petehub_pitcher_decision_slice1_audit_v1.json`。可重跑 `backend/scripts/audit_pitcher_decision_sources.py --year YEAR --fetch-schedule`、`--year YEAR`、最後 `--finalize`。3 局部 pytest、六年 source／hash／snapshot／UTF-8 與一次 vue-tsc 通過；未開 browser／server／截圖。資料核對完成不等於資料已修復或新增畫面通過。

下一步須使用者指示 Slice 2，僅對上述兩個 game IDs 核對／補抓 Statcast，官方 feed 估新增下載 0；不要重抓全季。**本輪未補寫來源、重訓、重建歷史指標、Personal／In game 或任何 Ballpark Slice。** 正式 Stamina／Performance State 版本及其 gate 保留；2026 僅回溯，2027+ 才前瞻。

更新日期：2026-11-14
專案根目錄：`C:\intern\project_transfer`

## 最新背景修正：全站純黑（2026-11-10，待人工）

使用者要求全域搜尋並修正母站／Game等仍非黑色的背景。全域background／surface／muted／plot-bg改為#000，移除body橘色漸層；首頁、Game、投打個人頁、Lab、比較、輪值、球隊、登入／註冊、管理頁及Ballpark等局部裝飾漸層與寫死面板底色同步改黑。基礎文字／邊界色適配黑底，Location Lab原淺色畫布的軸字／框線同步調整。保留資料色階、圖例、狀態／選取色、場景圖片及3D場景內容。只改CSS，播放／API／跳轉腳本未改；CSS與來源一致性檢查通過，不代表畫面驗收。未開瀏覽器／server／截圖，待使用者驗母站Game與其他頁；Slice狀態不變。

## 最新小修：全場景浮動提示移除、室內無 guide（待人工）

使用者指出前批只移除portal提示，室內物件／NPC提示仍在。現移除runtime整個浮動prompt文字物件及所有GUIDE · generic頭頂標籤；Campus guide人物保留但沒有浮動字。自動guide只建立Campus，室內／吸菸區generic guide不渲染也不出現在可互動目錄／nearest triggers，避免隱形guide。固定設施招牌／Coach-GM地面標示、Nearby HUD、E/Enter/R/C和實際物件入口保留。沒有新增球員NPC或動作。僅兩個runtime/catalog檔案局部修改，畫面／操作需使用者本人驗；不重跑build/typecheck或browser。

## 最新：DaPeter Logo／純黑 Ballpark，3I 逐球熱區＋Pitch scout 待人工

使用者提供 `C:\Users\郭睿承\Pictures\dapeter.png`，原檔複製為 `frontend/public/brand/dapeter-logo.png`（1672×941，SHA256 74687b57e6e98058d124837a001a8c57057943b82c14f3b540c32aaf0ac3ace5），無重畫／修圖。共用SiteBrandMark／PetehubLogo接Classic app header、首頁、投手首頁、登入／註冊、Ballpark與favicon；兩舊theme皆DaPeter，原首頁／登入目的地保留，球隊徽不改。Ballpark Walk及Static頁首／外圍改純黑；body attribute只在Ballpark生效，不改場景PNG。原圖與跳轉／底色由使用者人工驗。

使用者已接受上一批打者切換加速，再授權逐球情境熱區＋Pitch scout兩短批，現已接入共用Game／Personal。新增Game Center Slice3I in_progress，6/18；Ballpark仍40/66。預設逐球context，使用比賽當日以前資料，固定投手手別／打者側、count、前球type/result，30球門檻逐層回退；PA>30 prior gate、每格分母5、絕對率非PR，取消勾選保留整季PR。Scout按鍵顯示歷史Swing/Take／family／集中區與世界座標收縮環；不使用當球type／location／outcome、不宣稱意圖／預測／最佳球。冷取數等候再播、有限下一球預讀及late guard。五項backend tests、request／Vue cache／rate contour與renderer-free geometry source checks、一次vue-tsc及局部SFC compile通過，非人工驗收；source約414/196/0.3ms非UI延遲。詳見GAME_CENTER_ANALYSIS_MODULES.md／API_CONTRACTS.md。先請用戶驗新功能，不開browser／server／DOM／截圖，不恢復任何人物動作／節點／density。Batter scout未啟用，既有Sequence仍全季描述branch。

本文件只保存「接手下一個對話所需」的短摘要。專案完整歷史已移至 `docs/archive/PROJECT_HISTORY.md`，不得在每次開新對話時整份載入。

## 2026-11-09 最新修正交付待人工

Game／Personal 同用 PitchReplayPanel：左側原寬、篩選右緣對齊回放，右欄上移、投打資訊卡下接 compact Sequence；點擊續播、一鍵收合與 PR 熱圖保留，density 已依用戶取消。中斷後已接續完成 This PA 排除未來球（只同 game／pitcher／PA、較小 pitch_number）、白球 hover／pick、可操作的球員／影片連結；Replay payload 沿用既有 Stuff／Location／Stamina 資料接線。Ballpark 建築入口浮動「Team Office · E / Enter」類提示移除，入口／R 等操作保留。前球／比較篩選 source checks、局部 backend replay payload pytest 1 passed、一次 vue-tsc 通過，均非畫面通過。下一步只請用戶驗 This PA 首球／換PA、白球資訊／連結／影片、Ballpark 提示移除；不開瀏覽器、不恢復動態重建、不開始新 Slice、不改 done。後續細節見 GAME_CENTER_ANALYSIS_MODULES.md 2026-11-09 段落。

## 2026-11-07 目前決策與下一步（下方為舊快照）

**最新掛載修正待人工：** 使用者截圖回報影片彈窗只有header/footer、沒有播放器，球場下方也沒有Sequence。元件內都有無條件heading/loading/error，故先處理新元件自動註冊／lazy掛載疑點；Game／Personal 明確 import `PitchVideoPlayer`，`PitchReplayPanel` 明確 import／直接使用 `InGameSequence`，移除 Lazy 名稱依賴。三處 SFC compiler binding 檢查確認 template 直接使用 `$setup` imported component，不經 resolveComponent；一次 vue-tsc PASS。這是 source 接線證據，不是執行中根因／播放／畫面通過。仍等用戶驗原頁刷新後彈窗原生影片、球場下方 `Sequence · Conditioned branch` 及切球同步；不再宣稱前次UI已成功。

**最新已接線待人工：** 使用者再要求移除 3D 投手、大張 Arm angle 圖與底部 Selected Pitch 表格，已移除；保留來源金點／數字／打者。熱圖 controls 與 View／Compare／Reset 同列對齊、按鍵框縮寬。投打卡改到 `PitchReplayPanel` 真正最右 sidebar，非場地內側欄，各六球種／More。下方 `InGameSequence` 改既有 **Conditioned branch**：條件是目前 balls-strikes＋打者L/R＋同PA相鄰前球；season anchors 匹配後保留同PA downstream／count descendants，不把前球 predicate 再篩後續。`/personal/sequence?previous_pitch=` 為向後相容新增，`__first__`／缺球界線明示。Game／Personal 影片彈窗共用 `PitchVideoPlayer`，既有 `teamDirectVideo` 解析 MP4→原生播放器，不嵌 Savant 整頁；保留來源連結／Retry／late-response guards。backend3局部 tests、frontend前球／影片source checks及一次vue-tsc PASS。無browser／DOM／截圖／新server。40／66不變，F2.4／F2.6／F2.7待人工，不進F3、不恢復動作。先驗五組：無投手與打叉區塊；按鍵與最右側卡片；Conditioned branch換球同步／首球缺球；影片only與關閉／錯誤；原熱圖與R返回。

**本日最新修正仍待用戶：** 使用者拒絕抱胸投手／球塊手套／熱圖透明洞與版面。3D 投手改逐球 arm-angle 固定伸臂示意（L/R、負值；腳/root不動，不動畫、不硬拉手去真實金點），手套為淺掌袋／拇指／指套並跟手朝向。熱圖低樣本／缺PR格改中性灰而非透明洞，不造PR。移除兩個 close-up 按鈕，exact-count 投打卡移側邊、主表各六球種，More pitch types 展開，窄版回下方。`check-static-pitcher-pose.mjs`／`check-batter-zone-contours.mjs` 與一次 vue-tsc PASS，無browser／DOM／截圖。40／66不變，F2.4／F2.6／F2.7繼續待人工，F2.5跳過，不恢復捕捉／動畫或自動進F3。先交這批給使用者驗。

**最新交付：使用者要求完成 F2.4／F2.6／F2.7、跳過 F2.5，不再動態重建。** 已實作共用 `PitchReleaseGuide` 逐球金色 release X／Z＋黑色 arm-angle 示意線／通用人形／正背切換，來源 XYZ／height／extension 分別保留；肩與2ft線長明示 schematic，負角度／缺值保留。圖卡不依賴 trajectory/WebGL。Game／Personal 共用，原熱圖／影片／靜態人物不改；3D 角色失敗狀態及 Retry 3D 已接。兩牛棚 canonical 直達母站 In game 新增 `bullpen=west|east`，官方 active-roster 手動選單含 freshness／retrieved/source-as-of，不替代名單、不覆蓋指定歷史投手，換人清場次、手動場次保留／最新預設，R 原房間不增加浮動按鈕。原比較／Lab／個人入口保留。局部數值／in-memory roster／lazy／cleanup source 檢查及一次 vue-tsc PASS，無 browser／DOM／截圖／server／build。證據 `petehub_static_release_delivery_v1.json`。**F2.4／F2.6／F2.7 已交付但仍 in_progress 等用戶人工回報；F2.6／E6 實測資源／裝置 gate 未完成，40／66不變；F2.5與G1–G6 deferred。** 下一步只收這批五組人工清單，不開始 F3、不恢復動畫／捕捉。完整最新紀錄在主文件頂部，下方舊「planning only」等文字已被覆蓋。

**最新靜態主線規劃：F2.4 改為 Static arm angle and release visualization；本輪只更新計畫，未改新 UI。** 使用者希望參考 Savant 正／背人形＋角度線呈現來源 arm_angle 與 release XYZ／height／extension。資料已存在：2026 正規賽 716,544 球，五欄合有 711,697、含負角度；沒有肩／肘／腕來源座標。原來源點為真實資料，示意肩點／線長／人形屬 generic；不能唯一還原身體、不能改球路配模型、不補45°、不把extension當跨步。先在母站共用 In game 做逐球靜態圖卡／線與正背視角，切球更新資料，播放只動球。

F2.1–F2.3 保留 Done；F2.5 與 G1–G6 全部 Deferred、不再阻擋當前 F2。當前剩 F2.4 → F2.6 靜態共用整合／release → F2.7 投打站功能／名單與場次選單，再 F3；F2.7 不要求動畫。總計仍40／66，F2現行必要六子項完成三個；暫緩不當完成，E6 效能／裝置仍未結案。F3–F6 業務與既有 Ballpark 2D 移動／NPC 互動方向保留。新靜態功能未實作／未人工驗，不能改 done。完整定義在主文件最上方；資料證據 `data/sample/petehub_static_release_plan_v1.json`。

**最高最新：使用者要求「暫停一切動作設計，就放個人在打擊區跟投手丘」。** 已停用動作研究入口、Perdomo 自動載入與套模，投打人物只顯示 ready 靜態站姿；Play／Timeline 仍是原來源球路，熱圖與出手資料保留。G5 改 Deferred，G3／G4 保持 Deferred，40／66 不變；不得因舊授權恢復動作、捕捉、訓練或下一批。歷史候選與素材留存，不是人工通過。本次不跑畫面／瀏覽器／測試流程，立即交回。

中斷前已修正熱圖第二個根因：建快取的全域 Python DuckDB 1.5.2 與運行後端 .venv 的 1.5.5 版本標籤不一致，實際投球指紋相同。移除版本標籤失效比較，以 .venv 核對內容後同步快取；兩手別 ready／Swing 九格有 PR，屬 source 回應核對，不是畫面驗收。後端現有 --reload 程序已載入新 worker，未另開環境。下方動作開工／待下一批敘述都被本段覆蓋。

**最新追加授權及交付：Perdomo B 接到主場景 3D 打者，分批完成，第一批待使用者。** 共用 Game／Personal In game 的 Scene playback 選「Perdomo · B swing reference」再 Play，L／R 可切，原 Pause／Replay／Speed／Timeline 驅動相同場景；可切回 Historical pitch。不是只有獨立標點面板。B body／影像平面 root＋通用握棒／ground clearance、neutral 腳向；雙腳 X／Z 可移動。缺失段留空，無實測 bat endpoints／contact；參考模式隱藏未同步歷史球路／出手數字，熱圖依 Perdomo＋來源投手手別保留。衣服鞋子資產不改，投手開關仍 false。

熱圖根因：DuckDB 整檔 stamp 因影片表更新而變，舊 PR 基準 stale，色值全 null。改以正規賽投球欄位內容 fingerprint，重建 2026 基準 571 合格／705 groups；Perdomo 兩手別 Swing／Whiff 九格有 PR。過期訊息移到收合外、有 Retry、不快取 stale。7 局部後端 tests、Vue 編譯與 rig source 數值檢查通過，不是畫面／自然度通過。G5 in_progress／40 of 66；入口同下方母站網址。先等用戶驗熱圖、左右打與來源、握棒／衣物／鞋子／腳步、播放／seek／切模式，再做下一批；不恢復投手模仿。

**最新 G5 局部授權：Perdomo 實際左右打各一支，先驗來源標點＋B 骨架，接在母站共用 Game／Personal In game 收合面板。** 入口 `http://127.0.0.1:3000/pitcher-personal?year=2026&role=SP&team=SD&pitcher_id=681190&game_pk=823246&tab=in-game`，展開「Geraldo Perdomo · 左右打揮棒標點試作」切換 L／R。`output/ballpark/perdomo-swing-v1/` 保存來源、manifest、raw-v2、兩側 review 與 rejected 首輪候選；API 沿既有登入保護 `/api/personal/motion-review/batter/672695/{L|R}/{data|video}`。

左／右明列分析窗口 1.05–4.1／0.05–4.1 秒，影片完整時間保留，切鏡前特寫不入模。人體觀測率 80.2／84.8%，雙肘雙腕同時信心達門檻僅 14.3／3.7%，遮擋不足以交付可靠完整揮棒。來源低信心點留空；B 對應估測骨段灰色虛線，短缺口僅供模型上下文、不顯示補點影格。非實測場地三維／步幅，未套人物、未訓練、未鏡射另一側、未造 bat endpoint／contact time。需使用者驗身份、準備至收棒與腳步、左右手／遮擋、播放／seek／相機及換側；尚未人工接受。

`data/sample/petehub_perdomo_swing_pilot_v1.json` 記來源契約／Vue 編譯檢查及外部 repo 檢視。`sernadesigns/baseball-game` 只有 console、隨機結果、局數／壘包／記分與事件拆分可參考，無動作素材／捕捉；未複製程式或安裝依賴。G5 in_progress、40／66 不變。**投手 G3／G4 仍 deferred，停用開關與原快取 SHA 保留，不因打者試作恢復投手模仿。** 下方「本輪不再辨識」限制指投手；這次僅使用者新授權的打者源影片研究，無 app 瀏覽器／截圖／DOM 畫面驗證。

**2026-11-07 最新：使用者拒絕 Burnes／Kelly 人物套模，指出腳位固定、缺少實際大跨步，決定停止投手動作模仿，改保留來源出手資訊。** B 的相機相對深度與影像平面 hip 位移沒有可靠的球場前後 root／步幅；extension 不能當作跨步距離。兩支 B 標點的接受不等於人物動作接受。

已撤下兩人人物動作預覽，關閉 B retarget、procedural delivery 與舊 video retarget，分析場景隱藏投手人物。共用 Game／Personal In game 僅播放原來源球路，獨立顯示 Release X／Y／Z（出手高度）、Arm angle、Extension；缺值 unavailable、不套 45°。保留金色真出手點／高度線，Release close-up 對焦來源點。標點研究區預設收合，來源資料保存，不再處理人物動畫。

缺失診斷／快取候選覆蓋率研究保存在 `data/sample/petehub_pitch_motion_quality_v1.json`，僅啟發式，不證明合理投球。`petehub_b_reference_retarget_v1.json` 已記使用者拒絕；骨長、finite、seek 與旋轉數值檢查不可當步幅或自然度通過。

40／66 不變。F2.4 改為來源出手資訊模式，待使用者驗新呈現；G3／G4 動作重構 deferred，未經新指示不再訓練、下載、辨識或套模。本次僅必要編譯檢查，無瀏覽器／截圖／DOM 畫面驗證。下方人物動作規劃為舊快照，本段優先。

**2026-11-07 最新：使用者接受 Thompson「B · MotionBERT-Lite · 側別修正」局部版本，並授權響尾蛇先發每人先做 1 支、標點與 B 骨架接入母站 In game。** 此接受只涵蓋原局部候選，不等於全球員／完整重構／角色 retarget 通過。原 Thompson raw 與 Yesavage ref5 SHA `f2b3a65fefd7a2ea6856bbfa230b66cf35fd981a85db5c9ab1130c05a0ad0fe2` 保留。

首批依當次官方 AZ active roster 快照，交集本機 2026 至少 3 場第一局投球的先發候選：Eduardo Rodriguez、Merrill Kelly、Brandon Pfaadt、Ryne Nelson、Mitch Bratt、Kohl Drake、Jose Cabrera、Corbin Burnes，共 8 人；這是明示篩選規則，不宣稱球隊正式輪值或補入所有 2026 出賽者。每人選定 1 支 2026 官方逐球影片，失敗替代來源／狀態均保留於 `output/ballpark/team-motion-az-v1/manifest.json`。共 3,738 個完整來源時間軸影格，2,147 幀有部分候選骨架；缺失段留空，來源影片可播完。這些數量不是身分、接地或三維正確率。

`build_team_pitch_motion.py` 重用凍結 MotionBERT-Lite 權重，不訓練新模型、不碰原 5／10／20／holdout。逐片裁切與外觀／投手丘時間追蹤，短段不足的三人另保留原候選後改用 mound-crop-temporal-v1；身份仍需人工確認。沿每個連續有觀測且下肢信心足夠的區間，做兩狀態下肢標籤關聯；端點原解剖側別是待驗假設，不套 Thompson 的秒數、不搬動標點、不鎖腳、不跨缺失強補。原始／修正的二維與 B 三維可切換。

母站 Game 與 Personal 的共用 In game 內新增「來源標點 / B · MotionBERT-Lite · 響尾蛇先發投手」，按需載入每人的來源影片＋二維標點／B 三維骨架，同影片時鐘、暫停、變速、重播、拖軸、相機旋轉與八人姓名連結。來源日期／game／PA／pitch 獨立標示，**不是下方所選場次每球的個人動作或已接回人物網格**。檔案經現有登入保護的 `/api/personal/motion-review` 讀取，不另開 HTML／server。舊失敗角色 delivery／video retarget 仍停用。

依最新圖示移除共用 In game 的身高說明、Release／Plate、Character motion 控制與手動 2D schematic 按鈕；熱圖控制置左、View 置中、Compare／Reset view 置右並底部對齊，窄版換行。原 2D 失敗 fallback、來源球路／熱圖資料不改。此前工作使用者已明確回報通過；本批新排版與八人結果仍待用戶。

證據 `data/sample/petehub_team_pitch_motion_az_v1.json`；最窄 source 檢查核對 roster／球員鍵／完整時間／原始不變／標籤置換／有限數值／影片及模型 hash／檔案路由；Vue 編譯檢查另記。沒有瀏覽器、DOM 畫面檢查、截圖或代理操作驗收。40／66、G1／G3／F2.4 維持 in_progress；F2.5–F3 仍等動作 gate，不直接放行。

人工入口：`http://127.0.0.1:3000/pitcher-personal?year=2026&pitcher_id=593958&tab=in-game`；姓名列可換另外七人，Game 的 In game 選到同一批也可看。請驗：標點是否始終跟投手而非打者；遮擋時左右腳／真實離地是否保留；B 與來源放球／跨步的同步及缺失提示；播放／seek／變速／轉視角與換人清理；移除項目與控制列對齊。

最新中斷後用戶回報F2.4整段胸口朝本壘很不自然，要求參考影片，**未通過**。已實際分析Yesavage／Thompson兩支Savant逐球短片（playId／URL／hash／近似phase區間在`output/ballpark/f2-motion-reference-v1/`），未開browser或截app畫面。投手改側身set／lift、頭看本壘、髖先開肩後開、前腳先plant、放球後腿帶出，low-slot低抬腿／軀幹下沉、post-pitch不倒滑回踏板；保留source release／arm angle、打者與球路。這是影片觀察後的人工generic配方，不是ML／實測3D／個人mechanics。新的側身／髖肩時序／plant source檢查及既有出手／握點數值通過；vue-tsc另記結果。F2.4 in_progress、40/66，F2.5–F3暫緩等這項動作回報。中斷前尚缺的F2.4證據檔與manifest/交接收尾本輪補齊，不把舊「source PASS」當自然度驗收。

F2.4首動作批已接線待用戶：共用Chart全時間軸（pre1.2s／source flight／post0.8s）、Release／Plate seek、pause／speed／切球／hidden取消；逐球arm_angle與release XYZ／身高／手別驅動generic軀幹／手／跨步，源extension不當步幅。準備白球隨手、release後沿既有source path；左右打take／swing／unknown依description，generic收棒／recover，不造contact。修正數值發現的收棒副手脫棒（握點轉為chest frame）；左右投高矮高低slot的release與angle、重複seek、左右打61點握點與場景source檢查及一次vue-tsc PASS，無browser／畫面。40/66、F2.4 in_progress；請只交主文件最新五項人工清單，接受後依現有授權接F2.5→F2.6→F2.7→F3。此輪未動G、未全季影片抓取、不稱整段完成。證據`data/sample/petehub_replay_motion_f2_4_v1.json`；可動配方在TS，原10個ready/idle GLB clips未冒稱full-motion clip。

最新使用者授權調整計畫並開始F2.4至F3：F2.4 in_progress、40/66不變；先逐球release XYZ／arm_angle／extension／身高約束的通用投手與可seek時鐘，再左右打動作；依人工關卡接F2.5 source／adapter、F2.6整合但不假放行裝置／效能、F2.7官方名單牛棚／設施parity、F3 released Lab工具。extension不是步幅、arm_angle不是肩關節Euler角，不改真球路或把generic稱個人動作。影片學習流程已補G1資料／G3離線pose與retarget／G4個人範本與逐球約束，均planned、本輪不跑G或全季影片抓取。F2.3已接受不重問；所有新畫面仍只由用戶驗。

最新使用者明確表示這部分驗收完成：球衣／袖口／釘鞋與通用ready／idle外觀、上下鏡頭範圍小修已接受。**F2.3 Done，40/66**，不是代理畫面測試；不重問外觀。下一步F2.4投打動作與共用clock，尚未實作：先投手跨步／手對source release＋命名事件與可seek時鐘，再左右打load／stride／swing／follow-through／recover／take。來源球路、release與球速不改；無實測contact／bat path保持generic／unknown。全隊個人臉、精準edition、F2.5資料與F2.6／E6效能gate未因本次接受完成。下方in_progress／39/66／待驗均為舊快照。

最新袖口回報：釘鞋批後使用者指出隊色袖口突出，未回報F2.3通過。已移除剛性前臂圓環，袖口改用袖子原面與完全相同skin權重／POSITION／JOINTS，資產重烘焙 **4,107,456 B／13,864 tris**。只跑最窄角色source檢查，無browser／視覺驗證／重跑typecheck。白色是generic主場、客場隊色上衣灰褲，依當場攻守而非favorite team；非精準edition。僅待用戶驗左右側Ready／Idle袖口，F2.3 in_progress、F2.4 Planned，39/66不變。

最新F2.3仍未接受：使用者回報球衣不明顯與裸腳只塗色。本批加強寬鬆球衣胸腰／袖輪廓，加領袖口與開襟隊色滾邊，更新胸標／鈕扣；移除裸腳面，每腳新增獨立封閉鞋面／鞋底／四道鞋帶／八顆鞋釘，剛性蒙皮到各自foot joint，實際納入glTF／GLB。握棒、土丘、source球路與主客隊色規則不改。新GLB **4,107,044 B／13,864 tris／65 joints／10 clips**。角色source／衣服材質／釘鞋骨架數值及一次vue-tsc檢查，沒有browser／截圖／圖片比較。只等用戶在Game／Personal近看驗球衣、鞋型鞋釘、Ready／Idle接縫，F2.3 in_progress、F2.4 Planned、39/66。不要把下方舊塗色裸腳或先前候選當已接受。

最新第二輪F2.3仍被回報衣物／襪子斷裂、手腕反轉。已參考Epic官方持物two-bone IK與modular character（非宣稱MLB The Show內部程式）：改**主手palm socket帶動bat，副手IK追下握點；前臂twist與手腕分開，局部手腕偏轉≤.60rad，取消相反180度掌基底**。衣物從同一母網格重塑殼，完整原面集合分skin／cloth，接縫共用同POSITION／JOINTS／WEIGHTS與骨架，刪除圓管及最近頂點權重移植。GLB重烘焙 **4,052,180 B／14,318 tris／65 joints**；editable source／recipe／manifest更新。新手腕／掌心／接縫數值與vue-tsc PASS，無browser／截圖／圖片比較或視覺通過。只等用戶檢查肩袖／褲襪接縫、左右打正常握棒及idle拉裂；F2.3 in_progress、F2.4 Planned、39/66。土丘、extension及source球路不動；舊圓管方案是失敗候選，不再拿它當已修好。

最新F2.3人工指出握棒、裸身輪廓、雙圓土丘問題，**尚未通過**。已修：兩掌向與各節手指繞握把圓柱目標／拇指；隱藏被衣服覆蓋的解剖表面並新增獨立寬鬆skinned球衣／袖／領袖口／褲，非裸身上色，腰帶鈕扣隨之調整；遠端雙圓／截錐刪除，單一Lathe坡面土丘保留中央.254m及踏板；GLB重烘焙 **3,920,544 B／11,776 tris／65 joints**，source與manifest更新。骨架／手指距握把範圍／衣服skin、受影響scene幾何及vue-tsc PASS，無browser/畫面測試/build。只待用戶四項新修正，F2.3 in_progress、F2.4 Planned、39/66不變。

Extension答覆：有逐球release_extension與release XYZ，球路起點未改；現在顯示Source extension ft及缺值狀態。人物仍ready，與金色真release點未對齊，跨步／手部release對位是F2.4待作，不能把source起點吸附人物胸前／踏板來遮掩。舊「只有塗色衣服／14,318 tris／3,898,236 B／截錐丘」為舊候選記錄。

最高最新：使用者接受Game熱圖修正，並明確選擇「F2.3外觀批先交、接受後F2.4」。**F2.3 in_progress，F2.4 Planned，39/66不變**。已接Quaternius CC0 Standard免費Superhero Male（不是付費Regular／.blend），65 joints／14,318 tris、3,898,236 B GLB，可編輯glTF/bin/三色圖在`output/ballpark/f2-character-source-v1/`，原始source／授權與可重現Python+Node匯出保留；manifest `petehub_replay_actor_manifest_v1.json`。臉／眼是真3D網格但generic，未做個人臉／歷史背號；球衣是當場home/away與上下局推導的generic隊色款，非favorite/current team或精準edition。

共用Game／Personal新增Batter/Pitcher close-up、Show/Hide、Ready／Idle preview；列冊身高＋未知1.83m generic、左右打握點／腳位／視線、左右投對側手套、球棒／帽盔。10 clips含neutral ready/idle與八個烘焙完整左右姿勢；runtime明確正scale左右IK配方。Idle為獨立呼吸preview、Ready可停，非F2.4投打clock；金點仍真release，ready人物手尚未對release，不改source球路。缺資產保留定位guide與分析，timeout/abort/late disposal已寫；WebGL實機／perf未驗。純骨架數值＋受影響scene source＋兩replay測試＋修正後vue-tsc PASS，無browser/DOM畫面/截圖/server/build。**下一步只等用戶五項外觀清單（主文件最上方），不要直接做其餘clips或稱F2.3/F2.4 done**；外觀不喜歡就小批修，不重畫園區或回PNG人物。

最新人工回報：身高及其他項目通過，僅Game熱圖消失；使用者更正Personal熱圖正常。程式定位為共用Chart的Heatmap僅在activeView=catcher掛載，Game切Pitcher時卸載並清overlay。單行修正為3D各視角均保留Heatmap，2D仍沿catcher條件；未改統計／資料／貼圖材質，未執行瀏覽器、typecheck、build或舊audit。新修正待使用者僅驗Game三視角切換與Show heatmap／Metric，Personal原Catcher不重驗；39/66不變，不自動開始模型。

最高最新：使用者授權身高接線，已交付`player_bio_v1`（獨立schema／服務，People API依MLBAM ID按需批次，最多50人／7天TTL／失敗缺人15分鐘冷卻，raw身高＋英吋／公尺、體重／投打側、來源／時效，stale／unavailable，磁碟錯誤不擋replay）。Game／Personal共用replay帶兩人bio及nullable arm_angle；Chart顯示列冊身高，cyan線用打者height_m，缺值1.65m通用參考，不是正式模型／眼高。新服務三人live查詢成功；局部12後端測試＋3D數值身高fallback＋direct vue-tsc PASS，無browser／DOM畫面／截圖／server/build，新增畫面待使用者。F2.3／F2.4仍Planned，39/66；原2D／球路／PR／影片不改。

球速原選單／readout已有mph；主客隊球衣與臉部原只有泛稱，已在Ballpark主文件明列：F2.3共用rig／列冊比例／home-away服裝材質／通用頭臉＋分批球員外觀及來源／LOD；F2.4來源時間／1×與慢放倍率不改真實release_speed；F2.6依歷史當場home/away與攻守／球員身份接衣服，不能用favorite team或current team。具體edition未知用明示generic，單張headshot不是3D掃描／可動人物；F4仍是2D roster NPC，完整全隊臉與G個人mechanics不自動完成。本批不製作球衣／臉部／動畫。

身高來源最新補查：本機pybaseball2.2.7的`people()`走Lahman，設定archive下載URL本次HTTP404；未升級／下載整包。MLB官方People API小樣本成功，5／5（Snell、Senzel、Moreno、Judge、Ohtani）有height／weight／batSide／pitchHand，證據 `data/sample/petehub_pitch_motion_bio_source_probe_v1.json`。缺的是本機bio契約／快取，不是外部來源不存在；小樣本不等於全聯盟覆蓋，current列冊bio不冒充逐年／當場實測。使用者提出只呈現release＋手臂方向＋arm angle的可選方案，已記主文件，未直接替換F2.3／F2.4或動工；arm_angle是肩至球連線與水平夾角，缺肩點／肘腕／臂長／深度不能唯一還原人體，示意須明標generic。下一步仍可選bio接線或較小分析示意批，本輪只有來源查詢／文件，無UI／API變更、補抓全隊或驗畫面，39/66不變。

最高最新：使用者明確接受最新F2.2（含遠端紅土半徑10/3m），**F2.2 Done，39/66**；F2父項in_progress，F2.3–F2.7仍Planned，E6/F2.6量測未完成。本輪要求先做資料初查，未開始模型／動畫。2021–2026本機DuckDB唯讀盤點與2026 roster／boxscore／Timing快取結果在 `data/sample/petehub_pitch_motion_data_audit_v1.json`，可重現程式 `backend/scripts/audit_pitch_motion_sources.py`。2026 716,544筆R：arm_angle711,723（99.33%，868位投手都有至少一筆），球路所需release/velocity/acceleration713,878（99.63%），手別100%；bat_speed等scalar在指定揮棒分母97.23%，不是逐幀bat path。六年度庫無height/weight或逐幀骨架；既有roster72筆、boxscore284位person也未保留身高／體重。arm_angle在Movement有用，但In game replay scalar未轉出，需nullable契約接線；身高不可由sz_top/release_z估。建議模型前先補有來源與時效的bio快取＋replay motion availability小批，不自行補抓或開模型。初查不等於F2.5 adapter完成；下方38/66及F2.2待驗為舊快照。

最高最新：使用者接受主隊預設選場，要求姓名白色後F1即結案，並授權F2及子項。白色link/visited已改，**F1 Done；F2 in_progress；F2.1 Done（資料／技術契約），F2.2 in_progress（新三維場地待用戶），38/66**。F2.3–F2.7依已排人工gates待執行，G/F4/H未開工。不要把舊「F2未授權」當現況，也不要直接宣稱F2全完成。

本批 Three.js/@types **0.187.0** 精確依賴與lockfile；Chart async client元件→mounted dynamic scene import，不進app shell。新場地同世界原值球路、丘／踏板／本壘／打擊框／zone，捕手／投手／側面preset與真orbit/dolly。金點是實際release，cyan僅站位/通用高度guide；正式可動模型下一批F2.3，不能把guide當球員。舊背景照片與PNG打者、任意前景translate撤接，原檔保留；2D schematic fallback不含這些圖，影片／白字姓名／PR／熱圖／exact-count兩卡／R保留。物理座標(X,Z,-Y)*.3048，source feet不變；API／backend公式未改。基準b7d720c加 `output/ballpark/f2-preflight-v1/f1-preserved-ui.patch`保留最新F1差異，這輪沒有commit/push。

`check-pitch-replay-3d.mjs`純數值/scene-graph/lazy source檢查＋一次direct vue-tsc PASS，無WebGL renderer／browser／DOM畫面／截圖／server/build；不代表新透視／GPU／手感通過，E6/F2.6仍待量測。契約／來源／hashes見 `petehub_pitch_replay_3d_f2_1_2_v1.json`及Ballpark主文件最上方，使用者只測新五項幾何／相機清單；不要重問F1或再產人物PNG。F2.2場地尺度接受後接F2.3可編輯rig與ready外觀，再F2.4動作／clock，遵守10分鐘拆批及用戶本人畫面驗收。

最新F1人工回報：使用者表示其他沒有問題，只要求Game預設在當日有主隊比賽時選主隊場。已小修：明確有效game_pk優先，其次favorite team的主／客場，最後首場；不為主隊跳日期或清除Viewing team篩選，主隊即時變更時有對應場可改選。既有F1來源檢查新增四種情況後PASS，沒跑browser/build/typecheck。原F1其餘交付接受，不重問整套；僅新主隊小修待確認，F1保持in_progress、36/66；F2未開工。以下五項全待驗文字為本次回報之前快照。

最高最新：使用者授權 git push → 收可保留 UI → F1。前段142檔 checkpoint **d25f602 已推 origin/main**；F1 source implementation 已交付，tracker 改 in_progress、仍36／66，等新五項人工清單；不把「開始」當驗收。Game 保留並同步 year/date/game_pk/pitcher_id/tab、歷史場日期還原／latest-request／empty-error-retry；Leaderboard 同步 year/team/tab/role 與 cutoff 限制；Campus GAME／三物件／記分板／DOM 連結沿用 canonical routes，球隊與年度保留。真名 Personal 連結／收合說明／exact-count 卡片與 API 沿用，逐球 details 也用姓名；無浮動R，鍵盤R及輸入／彈窗guard保留。F1純Node/Vue資料契約與一次vue-tsc PASS，無browser／DOM／HTTP／server／backend全測；證據 `petehub_ballpark_f1_source_gate_v1.json`，完整≤5項清單見Ballpark主文件最上方。F1待用戶，F2七子項全Planned，拒絕貼圖候選留待F2替換，不自動開工。下方「未提交checkpoint／F1尚planned」為本次交付前快照。

- 使用者否決母站 Catcher 的照片 pan／zoom、獨立前景 translate、固定 PNG 打者，以及最新下移／打擊框的整體呈現；停止微調／生成站姿貼圖，不記接受。現行候選碼仍在，本輪未回退或替換。已接受的 3H 資料／影片／PR 及 D、E1–E5 不重開。
- 已在 Ballpark tracker 新增 **F2.1–F2.7 全 Planned，36／66**（原 36／59 加七項，沒有扣除完成工作）：契約／安全點 → 三維場地／真相機／出手 → 通用可編輯 rig → 投打 clock → swing 資料 audit／adapter → 共用接線／release → 原設施 parity／兩牛棚 actors。詳細交付與人工 gates 只維護 Ballpark 主文件最上方；Game Center 主文件列消費／保留契約，不另建重複 Slice。G1–G6 保留 Planned，限後期專屬／進階 Motion Lab，重用 F2；F4 全隊 NPC、H simulation 未開工。
- 只獲授權規劃／工作盤點，**尚未獲 F2 實作開工指示**。Three.js 為優先候選，待 F2.1 來源／單位／載入／預算決策，不安裝引擎、不產模型、不把整個 2D 園區或 V2/V3 角色改成 3D。Nuxt 保持 UI／route／auth owner，母站兩頁共用 renderer。
- 開工前建議收尾：經審閱的 Git checkpoint（HEAD 3761955 與 upstream 當時 0/0，但新修改／素材仍大量未提交）；確認最新姓名／收合說明／exact-count 卡片與浮動 R 移除的有限 pending UI。舊功能入口與 R 返回先前已接受，不重問；圖片候選不再追求驗收。這輪不 stage／commit／push。
- E6 操作已接受，數值／裝置仍未量測；建議使用者保留現況基準，缺完整裝置矩陣不阻止另獲指示的隔離原型，但不能將 E6／F2.6 release 標通過。母站 Location／Sequence／Tags／Movement 仍 in_progress；影片全季補齊尚無本輪完成證據，皆分開列帳、不擅自重跑。
- source 球路已由 release_pos_x/y/z 重建；問題是照片／投影沒有同世界對齊，不能把球起點吸附丘中心或改 source 配動畫。逐球 scalar／整季平均不等於逐幀 bat path，generic／average／measured 分開。所有畫面／鏡頭／動作驗收仍由使用者本人，本輪沒有瀏覽器／截圖／server／測試／產品碼變更。

2026-11-05 最高最新（前段接受、母站新稿待驗）：使用者已明確接受「所有功能物件直接進母站」與 R 返回的前段修正；新要求移除浮動 R 提示，保留同帳號有效來源與輸入／彈窗防護下的鍵盤 R，已完成。下方單連結限定／保留中繼頁／R 待驗為舊快照。E5 done、36／59；E6 數值／裝置 gate 仍未量測，不自動開始 F。

母站共用 In game 新增投打真名 Personal 連結、收合熱圖說明與 Catcher guide、全季同側同 exact count 的投手／打者球種卡片；API `/api/games/matchup-context`，原始軌跡／影片與已接受的 PR 計算不改。新寫實背景 v2、打者 v4（依使用者最後的白色大學球衣照片姿勢，非真球員建模）；舊側向 v2 與未接入背向 v3 均被否決。捕手現在背景／打者／本壘板／好球帶／熱圖／球路共同 pan／zoom；投手保留 3D orbit。最新素材／縮放與新增 UI 仍待使用者，不能記 visual PASS。資料契約／來源證據見 Game Center 主文件與 `petehub_in_game_catcher_redesign_v1.json`。不得自行瀏覽器／截圖／操作驗證。

最高最新：使用者「都通過」接受直接跳過單連結中繼頁與放大提示文字；不再重問。本輪按要求在 BallparkClassicReturn.vue 加入母站 R 回來源房間，僅有效且屬目前帳號的來源 token 啟用；輸入／選單／可編輯／彈窗／IME／Ctrl-Meta-Alt／長按／已處理事件不觸發，卸載移除 listener，沿 E5 恢復位置。這項是使用者新授權，舊文件「Classic 不註冊 R」不得拿來否決，但仍不能搶表單輸入。R 小修待使用者驗收，沒跑瀏覽器/typecheck/build/audit；36／59不變。下一個未完成仍 E6 效能／裝置證據，之後 F1 Game/Leaderboard、F2 投打設施；真實球隊 NPC 是 F4，未自動開工。

最高最新：使用者回報 E5／E6「操作上都沒問題」，E5 依整體人工操作接受 Done，36／59；E6 操作接受但數值效能／裝置未量測，不放行、不捏造特定裝置 PASS。新要求已小修：只有一個 Classic 目的地的 links 物件直接導航（含 Coach workspace），不再中繼確認；多工具選擇及 Game／In game／選人／對話保留。保存 team／season／checkpoint／返回，admin 限制不變。Canvas 互動／guide／出口／方向文字分別放大至20／18／20／22px、粗體、高對比、雙倍文字解析度。新小修等使用者驗收，不重跑 typecheck／build／舊audit／瀏覽器。下方 E5 待驗及35／59 是歷史快照；F4 未開工。

2026-11-05 最高最新：使用者明確釐清 E3～E4「都通過」，E3／E3.1–E3.3／E4 全 Done，35／59；先前限縮成 Campus 兩項是代理誤讀，不重問舊清單。使用者接著授權 E5～E6，已交付 E5 versioned 本機帳號隔離位置／面向／房間／Viewing team 保存、refresh／relogin／Classic 返回、安全座標與壞版／壞檔 fallback；不做 server／跨裝置同步、不動 avatar profile。Portal spawn 只使用一次並清 query，C／R 與 Safe reset 保持指定入口。E6 新增手動 Record 20 seconds／JSON（dev 標示、raw frames／moving／p95／heap availability／owned runtime counters）、reduced motion／Canvas 切換保留 pose、context-loss 與清理。七組來源契約＋單次 direct vue-tsc PASS，完全沒開瀏覽器／截圖／操作／另開 server。E5／E6 in_progress 待新五項人工清單；正式部署 LCP／input／bundle、forced-GC retained heap／GPU／真低階裝置及多瀏覽器尚未量測，不可把 dev sample 當 release PASS。詳見主文件最上方 E5／E6 段與 `petehub_ballpark_e5_e6_source_gate_v1.json`、`petehub_ballpark_e5_e6_release_gate_v1.json`。F4 真實球隊 NPC／隨機刷新／個別美術未開始；核准背景／碰撞未改。下方所有 E3/E4 pending、30／59、局部接受是舊快照，本段與 tracker 優先。

2026-11-05 最新 E3／E4 交付待驗：使用者授權 E3＋E4（含 E3.1–E3.3），五項 source implementation 已完成但保持 in_progress，30／59 不變，等使用者五項人工驗收。44 個互動／guide 綁定、10 位虛構 stationary idle guide、物件 E-Enter／點擊／DOM 選單、mini-map／九場景 travel、Nuxt paused overlay／URL／focus／scroll／close-back 與 Classic 原設施返回連結。Game／左右牛棚重用母站 Vue/API，官方 roster freshness 保留；Shape 與 In game 分離。舊五場景業務物件為命名入口＋Classic equivalent，完整房內 F parity、真實球員／隨機巡遊／個別對話／活動動畫未完成且未開工。核准背景／collision／v4 環境 JSON 未改；app.vue 只加條件式返回連結，無全域引擎；PitcherInGameTab 只加 optional select-game event。來源證據 `petehub_ballpark_e3_e4_source_gate_v1.json`；互動契約與直接 vue-tsc PASS，不是畫面驗收，沒有 browser／截圖／DOM 視覺檢查／角色操作。完整五項清單見主文件最新 E3／E4 段，網址 `/ballpark/play`。不可提前 done 或自動開始 E5／E6／F；下方「E3 未開工」是歷史快照。

最新 NPC 需求釐清：使用者所指為「所屬隊的真實球員，隨機出現在園區與各房間」，不是 generic guide。現有正式素材僅 V3 User＋V2 Gabriel Moreno 樣本，未完成全隊球員。F4 需要官方 roster 身分、V2 代表素材、全園區／各房間生成與對話；數量／時機／去重／巡遊／活動規格仍待細化，不能把 Clubhouse 8–10 代表誤讀為只在該房間出現。本輪不開始建模／隨機球員實作。Campus guide 僅見標籤的回報，來源定位為 [770,811] 被 west-entry-fence depth815 蓋住，已把該 guide 獨立站位改 [850,745]，不抬高所有 NPC depth 或修改背景／遮罩／碰撞；修正待使用者人工確認。E3.3／E4 未驗收完成，不標 done。舊來源 gate 的 guide anchor/hash 是修正前快照，未為這項小修重跑 typecheck/build/audit。

## 1. 開始順序與權威來源

最新人工回報：使用者對 Campus guide 完整顯示及 E／Enter／點擊開啟對話兩項回覆「兩個都可以」，兩項已接受，不重問。其餘 E3／E4 完整清單尚未明確確認，五項 Slice 保持 in_progress，30／59；程式實作至 E4，E5／E6／F4 未開始。不能把本次局部回覆擴大成全部房間／Game／牛棚／Classic／travel／權限通過。上方 guide 修正待驗文字為本次回覆之前快照。

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

2026-11-05 最新聯盟PR／Outside修正待驗：使用者授權15–25分鐘兩批完整處理，選打者角度（低Whiff/SwStr等偏紅）與更鮮艷色盤。離線腳本 `build_batter_zone_baseline.py --year 2026`已完成唯一一次全季建置：716,544球／662打者、571名PA>30、705 hand/zone/metric reference groups；JSON在data/MLB2026/batter_zone_baseline_v1.json（4,130,003bytes）。共用原aggregate_zone_rates，格分母>=10、至少5peer才有PR；weighted league mean與equal-batter midrank PR分開，ties=50。AVG/wOBA/HH/Contact等高紅，Whiff/SwStr/CalledStrike/Strike/CSW/O-Swing反向，Swing/ZSwing/Foul/Inplay為頻率不評好壞。API附league avg／raw/colorPR／peerN／status；cache含DB/WAL與算法fingerprint，raw cache deepcopy，不在HTTP重建；先只有2026，其他年或stale無PR不得退回舊絕對值給色。前端顏色PR0藍#0050ff、50近白、100紅#ff142d／alpha.86，保留16metric原值／分母，平滑PR不是原百分比。16 targeted tests與PR source-contour／direct vue-tsc PASS；AJ Ewing805999 vsR中心Swing83.61 vsLG75.42 rawPR81.48、Whiff5.88 vsLG10.50 favorablePR76.01；數值不是實際畫面通過。

同批使用者指出Outside zones大矩形及橫向接縫：改白框外距離<.28的窄圓角halo、向外漸淡且上限低於內圈；同色alpha合compound path。只改顯示，不刪帶外球／不改表值或PR；帶外仍粗分組示意，非逐球KDE。最後一輪source-contour／vue-tsc通過，等使用者確認新配色、Ewing左右投／PR、Outside開關與旋轉縮放；未用browser／截圖／fixture／新server。證據petehub_batter_zone_pr_source_gate_v1.json，3H仍in_progress，Ballpark30／59、E3未開工不變。下方舊絕對色階／13項／初版hash皆為先前快照。

2026-11-05 最新熱圖等高線風格待驗：使用者要求如Personal等高線上色，已共用原Personal配色／八階至 `heatmapPalette.ts`（原Scatter數學及色值不變），Ingame用 `buildZoneRateContours` 對9/17個彙整區的分子／分母高斯插值，48×48採樣＋橫列合併減少polygons。不是逐球KDE或新增統計解析度，UI已提示表格為精確原值；缺樣本洞保留空白、真0冷色、Z/O不跨inside/outside混色。原白線／座標／16指標數據／球路及帶外開關保留，camera只重投影。新source-only數學檢查腳本PASS、一次direct vue-tsc PASS，無後端重跑／build／browser或畫面驗收。使用者可在Personal In game及Game Catcher檢查平滑樣式／比率切換／拖曳縮放，3H未done，BallparkE3仍未開工。舊hash／方塊色盤說明是前版快照。

2026-11-05 最新母站熱圖outcome extension：使用者要求AVG/wOBA/HardHit%，同選單已擴至16項。Service讀取launch_speed/woba_value/woba_denom，以完成PA最後pitch做唯一結果入格（不套每球）；AVG H/AB、wOBA有效原權重／正分母、HardHit>=95mph／有有效初速的場內BBE，缺值不補0。Schema numerator/denominator允許浮點，metric metadata新增format；前端AVG/wOBA三位小數、HardHit百分比，獨立圖例／色階不把wOBA當百分比或截斷實值。10項targeted測試、8個格式／色階assertions及一次direct vue-tsc PASS，無browser／畫面測試。實際2026 batter682998 vsR有位置結束球H84/AB400、wOBA144.35/455、HH140/300僅唯讀資料對照；source gate `petehub_batter_in_game_outcome_metrics_v1.json`。3H仍in_progress，請使用者重新整理Personal In game／Game Catcher，驗三項新指標、分母／缺資料、左右投與原熱圖比例／播放。Ballpark30／59及E3未開工不變；下方13項／初版hash屬舊快照。

2026-11-05 最新熱圖比例修正待驗：使用者提供catcher畫面指出好球帶視覺失衡，已僅改Chart通用人物catcher縮放0.95→0.76、人物定位與好球帶同深度；BatterInGameHeatmap帶外八區預設隱藏，新增Outside zones開關，選O比率自動顯示。白框17吋／原sz_bot/top、Statcast球路、率分母與全17區數值表不變。未重跑資料測試／typecheck/build或任何畫面測試；3H仍待用戶驗收。本次只小幅呈現修正，下方初版來源hash／測試屬之前快照，不當作本次畫面PASS。

2026-11-05 最新母站熱圖第一版：使用者授權完整可操作第一版，已新增 `GET /api/batters/personal/zone-rates`、schema/service、`BatterInGameHeatmap.vue` 與共用 chart catcher overlay，Game／Personal同步；Ballpark 30／59不變，E3未開工。整季唯一完成PA>30資格，從所選球 p_throws 預選左右投；手動L/R/All、13種比率、九格＋8帶外區、開關／圖例／數值分母表。事件flags與PA計數共用既有實作；率與分母逐格算，null不是0，低樣本淡色。每球sz高度正常化、17吋寬與原projection；舊Discipline固定框不同且未改，不能說Z/O逐格完全同值。新API唯讀必要欄位，不載入影片／Plus、不改軌跡；client latest-request／cache與server DB/WAL revision LRU隔離資料。七項targeted測試＋單次direct vue-tsc PASS，2026打者682998實際R/L樣本coverage相符；既有API未登入401，無替代帳號／fixture／browser或畫面測試。來源證據 `petehub_batter_in_game_heatmap_source_gate_v1.json`，五項人工清單在 GAME_CENTER_ANALYSIS_MODULES.md 6.1。3H仍in_progress，待用戶登入在Personal In game與Game Catcher視角驗收。下方「熱圖尚未接母站」屬本次之前規劃快照。E3框架及3.1舊五場景／3.2三新設施／3.3genericNPC對話travel只說明，未開工。

2026-11-05 最新 E2.5 通過與手別確認：使用者對 v4 五項人工清單回覆「都可以」，E2.5 Done，30／59，E2 原項及 E2.1–E2.5 全部完成。已同步 tracker／主文件／v4 acceptance metadata／manifest，來源檢查證據保留初次 hash 快照，不重跑 typecheck／匯出檢查／畫面測試；E3 尚未開工。使用者提醒投手手別已有欄位，已確認 replay 每球 scalar columns 包含 p_throws、summary 有 pitcher_hand，前端 Selected Pitch Throws 使用 p_throws；Batter Personal 原始 rows 及 pitcher_hand_split 也有它。熱圖後續可直接用選球的 p_throws 自動選左右投；需要補 Discipline 查詢參數與各格比率，不是新造或推測手別資料。詳見 GAME_CENTER_ANALYSIS_MODULES.md 6.1。本輪沒有母站功能修改。下方 E2.5 pending／29／59 屬歷史快照。

2026-11-05 最新 E2.5 開工／統一包交付：使用者明確要求 E2.5，現 in_progress，29／59 不變（人工待驗）。新增 `build_ballpark_scene_package.py` 組包 v3＋Game＋Batting/Pitcher＋annex，輸出 `scene-kit-v4.json` 628 行（每個座標記錄保持 compact，不是新加數千行邏輯）；原來源／背景留存。runtime 與 play fallback 改單一 v4，9 場景／59 物件 index、211 collision／147 foreground／21 portals／2 hotspots；manifest／九場景 SVG／compact JSON 在 scenes-v4。來源組合／實際 imports、59 refs、portal/spawn、尺寸／可重現匯出及單次直接 vue-tsc PASS；不重跑舊 BFS／build／完整 audit，無瀏覽器／畫面測試。下一步使用者驗統一包固定導覽、Campus 三新站、C-R、team與fallback，不重審畫風，不自行開始 E3。NPC：E3.3 通用角色／靠近對話基礎，F4 才所屬隊伍 8–10 名 V2 美術／真實名單／個別對話及吸菸聊天，F2 牛棚投手，正式 mechanics G3–G5。

同次使用者詢問共用 In game Catcher 視角打者九宮格，已明確選「整季總 PA > 30」資格（不是手別 PA）並要求自由切換各比率；依當前投手 p_throws 預選 vs LHP/RHP，允許切換、分母及空值／低樣本需正確。現有 Batter Discipline 有 pitcher_hand_split，但 route/useApi/service 沒有獨立 pitcher_hand filter，stand 是打者站位，不可混用；現有 heatmap 多為density不能冒充比率。具體需求／資料與cache／九宮格捕手projection／驗收方向已寫 `GAME_CENTER_ANALYSIS_MODULES.md` 6.1。熱圖未實作母站，3H仍in_progress；後續沿同共用面板做，不分裂新模組、不改軌跡。此規格不代表本輪已做 NPC 或熱區UI。

2026-11-05 最新人工通過：使用者對新增後門／吸菸區及五項清單（含物件盤點）回覆「都可以 通過」，E2.1 Done，29／59；E2 原項及 E2.1–E2.4 均完成，E2.5 仍 Planned，未開工。新門／C-R 往返／新區及盤點 acceptance metadata 已同步，不再重問。使用者接著詢問 User/NPC 走路、蹲、坐、抽菸、碰拳、臥推、傳接球、揮棒是否已規劃：現有正式素材只有 idle/walk；吸菸聊天 E3.3/F4、牛棚 generic 投球 F2、正式 pipeline/投球/揮棒 G3-G5 已有方向；其他日常／社交／訓練動作與 User 主動動作選單尚無完整 clip／接點／狀態／驗收規格。候選需求記於主文件最新動作盤點，尚未凍結新 Slice 或授權動畫開工；不重開 D4、不產角色、不自行開始 E2.5／E3／F／G。下方 E2.1 待驗與 28／59 屬歷史快照。

2026-11-05 接續中斷完成：使用者已接受 E2、E2.3，兩項 Done，總進度 28／59。新指示為 Clubhouse 餐飲區右牆黃框增小門，靠近 C 進吸菸庭院，南出口 R 回同門旁；之後由使用者盤點才可關 E2.1，不能提前記 done。新素材 `clubhouse-backdoor-v1.png`（實際寬 1670 明確映射世界 1672）及 `clubhouse-smoking-area-v1.png`，原圖／v3 source 保留不覆寫。獨立 `scene-kit-clubhouse-annex-v1.json` 包含 Clubhouse 背景 override／portal addition、吸菸庭院 17 collision／15 foreground／1 R 出口／5 物件候選；runtime 支援 C 門與固定導覽，保留 Nuxt URL／team／focus 與等價按鈕。盤點現在九場景／59 物件；新增長椅、煙灰缸、兩個未來球員抽菸／聊天站位及返回門。完整 prompt／來源 hash／縮放／檢查與五項人工清單在 `petehub_ballpark_clubhouse_annex_v1.json`。中斷前兩處 JSON tuple 型別錯誤已修正，直接 vue-tsc 重跑 PASS；資料／站位檢查 PASS，不代表畫面通過，未開瀏覽器／操作場景。新門／庭院／C-R 返回待使用者驗收，E2.1 等盤點；E2.5 改規劃九場景統一包，尚未開始。未來偶爾球員抽菸／聊天寫入 E3.3／F4，遊戲虛構情境不推論真人習慣，名單／頻率／動畫／對話待細化，本次未新增 NPC 或動畫。不重開已過 E2／E2.2–E2.4／D5／E1，也不自行開始 E2.5／E3 之後。下方舊進度與待驗文字以本段及 tracker 為準。

2026-11-04 最新驗收：使用者對 Pitcher In game v2 及三項人工清單回覆「都可以」，E2.4 Done，26／59；E2.2 Game、D5／E1 保持 done，不再要求重驗。已同步 Pitcher provenance／場景 acceptance metadata／manifest／盤點。尚未明確人工結案：E2 原輸入防護／失焦暫停表單／移動 Safe reset／可用 touch-gamepad；E2.1 52 物件盤點完整性及功能分配；E2.3 Batting 房間入口／走道圍網遮擋／R 出口／team與direct fallback。E2.5 尚未製作，不能當現成待驗或自行開工。隨機投手／投球／選單仍為 E3.2／E4／F2 future requirements，本次只記使用者人工通過，無瀏覽器／操作測試。下方 Pitcher 待驗與 25／59 文字皆為歷史快照。

2026-11-04 最新 Pitcher 配置變更：使用者要求兩牛棚改 In game、移除左台原 In game，並規劃未來隨機所屬投手投球與投手／場次選單。局部 image_gen 編修為 `pitcher-mound-v2.png`（原 v1 保留），runtime 改讀 v2；碰撞／遮擋／portal 不改。`scene-kit-e2-3-4-v1.json` 將舊 `bullpen-lanes` 拆為 `in-game-west`／`in-game-east`，左 `pitch-analysis` 僅 Shape，Pitcher 6 物件、全盤點 52。編修 prompt／hash 與 future contract 存 `petehub_ballpark_pitcher_in_game_layout_v2.json`，可編輯匯出／manifest／盤點同步。新圖／配置待使用者於 `/ballpark/play?room=pitcher-mound` 驗收；E2.4 仍 in_progress，25／59 不變，不假裝已接受 v2。F2 已補隨機投手／generic 投球（favorite team 預設、Viewing team 切換、官方 active-roster 候選、手動選擇優先、無資料狀態、分開歷史軌跡）；E3.2／E4 預留等價選單／共用 Personal In game 與面板返回。角色／刷新／動畫／選單尚未實作；道內 actor 需在 F2 拆前後網遮擋。舊 e2_3_4 source gate 保留原 hash／typecheck 歷史，不當成本次新圖 PASS，沒有瀏覽器或操作測試，不提前開始 E3／E4／F2。

2026-11-04 最新 Game 人工通過／Batting 與 Pitcher 交付（優先於下方舊待驗快照）：使用者明確回報 Game 介面通過，E2.2 Done，Ballpark 25／59；D5／E1 保持 done。按同次開工指示，兩張已核准原圖 byte-identical 複製為 `batting-cages-v1.png`／`pitcher-mound-v1.png`，新增獨立 `scene-kit-e2-3-4-v1.json`：Batting 16 collision／14 foreground，Pitcher 19 collision／17 foreground，各 1 R 出口／5 物件定位。runtime／play.vue 加兩房間固定導覽及 Campus batting／pitching portal overrides，R 回各自 Campus 到達點，保留 team query／Static／Classic。原五場景 v3 hash 不變，並非 E2.5 八場景統一包。可編輯 SVG／compact JSON、manifest、盤點與來源證據同步；只做新包數值幾何／匯出及一次直接 vue-tsc，無瀏覽器／操作驗收。人工網址 `/ballpark/play?room=batting-cages`、`?room=pitcher-mound`，依 `petehub_ballpark_e2_3_4_source_gate_v1.json` 五項檢查；E2.3／E2.4 保持 in_progress 等使用者回報。物件功能仍 E3.2／F2，投手 In game 共用母站模組尚未由場景物件啟動。不得重審已核准素材、重新開 D5／E1 或開始 E2.5／E3／E4／E5／F；E2／E2.1 仍待獨立明確結案。

2026-11-04 最新三圖核准／Game 製作：使用者明確回覆「三張都可以接受」，Game／Batting／Pitcher 設計已核准，不再要求同圖批准。按耗時限制先交 E2.2 短批 Game：`game-center-v1.png` 原圖 byte-identical，`scene-kit-e2-2-v1.json` 獨立追加 21 collision／19 foreground／1 return portal／3 未接線物件 bounds；可編輯 SVG／compact JSON 在 `output/ballpark/scenes-e2-2-v1/`，manifest 與來源證據 `petehub_ballpark_e2_2_source_gate_v1.json` 已保存。runtime 與 `/ballpark/play` 加 Game；只覆蓋 Campus GAME target，原 v3 五場景 hash 0bf16290… 不變。可由 Campus E/Enter 或固定 Game 按鍵進入，靠南側 CAMPUS 出口按 R 回 Campus GAME 到達點；Static／Classic／Viewing team 保留。數值幾何／物件站位、可重現匯出及單次直接 vue-tsc PASS，沒有 Nuxt prepare/build／瀏覽器／畫面／操作測試。Game URL `/ballpark/play?room=game-center` 及五項人工清單見來源證據；等使用者回報才可關 E2.2。Batting／Pitcher 美術已接受但未分層／接線，下一短批續做，不重新產圖；E2.1 不因藝術核准自動 done。24／59 不變，D5／E1 done 不重開，不開始 E2.5／E3／E4／E5／F；Schedule／Analysis／In game 仍未啟用，頁面有明確說明且保留 direct Game 入口。下段「候選待核准／未改 runtime」只屬核准前紀錄。

2026-11-04 最新 E2.2–E2.4：使用者重新要求開始三站製作，已沿用盤點配置、用內建 image_gen 以既有 Team Office clean v1 作畫風參考，產出三張 1672×941 候選，保存在 `output/ballpark/e2-facilities-v1/`（Game Center／Batting Cages／Pitcher Mound）。完整 prompt、原始輸出路徑、參考來源／hash、大小／PNG hash 記於 `petehub_ballpark_e2_facility_concepts_v1.json`，盤點表補候選參照及投手共用 Personal In game context。候選待使用者核准，未修改既有五場景／runtime，沒有新碰撞、foreground、portal／互動範圍，也沒有代理畫面／瀏覽器／圖片比較／操作驗收。新圖依素材規範停在 concept gate；確認後才製作可編輯包與接線。使用者的「E2.1盤點完的話 開始2.2-2.4」記為開工指示，不擅自當完整盤點／新圖人工通過；E2.1–E2.4 均維持 in_progress，24／59，D5／E1 done 不重開。下一步只請使用者確認這三張新圖或指出具體修改，不再要求同一 Campus GAME 門／既有背景核准；不開始 E2.5／E3／E4／E5／F。

2026-11-04 最新影片補抓方向（取代下段「需取得分批方向」）：使用者改要求在 Per aspera ad astra 的 `/admin/updates` 自行按鍵啟動，已新增 `AdminVideoBackfill.vue`「補齊缺漏影片」，沿用既有 video job／StatsAPI worker，只補所選年度未快取完整的場次，不跑全更新／模型。狀態每 5 秒讀取，顯示每 50 場保存後的覆蓋率、待補數、active／latest job、失敗及重試；同 backend 程序防重複排隊。關閉頁面仍執行，後端須保持運行；重啟會遺失記憶體工作狀態，使用者再按可跳過已保存場次，非 durable queue／自動續跑。server admin＋精確 peter1010 授權未改。6 項針對性後端測試、兩個 SFC／TypeScript 語法檢查 PASS，未做完整 typecheck/build／瀏覽器／播放驗收。代理沒有啟動全量補抓；985 場為先前單場補抓後的缺漏快照，應以面板即時統計為準。3H／Ballpark Slice 狀態不變；待使用者自行按鍵、離頁返回確認工作狀態，並在補後確認 Stuff／In game 影片，官方無影片者不得造鏈或當播放通過。

2026-11-04 最新首頁／影片事故：使用者回報首頁 index.vue dynamic import 失敗，HTTP 診斷定位到 reka-ui 舊 optimize hash 回 504 `Outdated Optimize Dep`。只重啟原 3000 前端程序（原 PID 10316→43976），未刪快取或新增平行 UI server，未改首頁碼；最佳化完成後首頁兩層依賴 33 個模組 HTTP 均 200（reka-ui／lucide hash cb5a93d4），不是瀏覽器畫面通過，仍請使用者自行重新整理確認。復原日誌在 `.runlogs/frontend-recovery-20261104-145057.*.log`。

影片診斷：2026 lookup 原有 424,030 rows／1,443 of 2,429 games，11-02 metadata 記 986 failures；8 月 joined video 為 0，9 月僅部分，因此 Stuff／In game 可同時缺影片，非所有資料消失。來源由 StatsAPI playByPlay 每球 playId→lookup→pitches_enriched 依 game/PA/pitch join；既有 service 的有效樣本 game 824948 pitcher 688297 仍 48／48 rows 有影片 identity。使用者已要求補齊；本短批先用原 backfill_video_lookup(max_games=1) 補 game 822708（2026-07-12），joined 281／281 rows 有影片，現 424,311 lookup rows／1,444 games，查詢剩 **985** 場不完整。此前先試讀的另一場 822678 為 308 playIds，但未宣稱已寫入。未做前端影片播放驗收。

寫入前原三份 lookup CSV／meta 備份在 `data/MLB2026/video_lookup_backups/before-single-game-20261104-145057/`；新 meta 的 failed_games=[] 只代表這一場批次無失敗，絕不是全季補齊。未啟動全量 985 場長跑；需依使用者時間止損規則取得分批方向（建議先 50 場，進度／錯誤可見、可續跑，無結果工具不超過 60 秒），不可盲重跑全季或清空既有 lookup。首頁驗收與影片補抓是獨立事項，不把任一 HTTP／資料結果記作 3H 人工通過。

2026-11-04 最新 In game 逐球 followup：使用者希望比照 Stuff 看每球資訊及開影片。共用圖表／面板已補詳細欄位、軌跡 hover／鍵盤聚焦資訊、點擊或 Enter／Space 選球並開影片；使用獨立 open-video 事件，不由下拉／自動換球觸發影片。保留 Open Video 與無映射說明，Game／Personal 兩端同步；只讀現有 payload，不新增 API／補造 Plus 或改軌跡。缺值／零值／影片 URL／資料不變與兩個 SFC 語法來源檢查 PASS，未重跑 typecheck/build／完整舊測試，也沒有 browser／圖片／實際互動驗收；3H 維持 in_progress，人工清單已補。前段初次 typecheck／v1 證據為先前快照，不能冒充本次新 hash 或互動通過。

2026-11-04 最新母站優先：使用者明確要求先把 Game 球路面板共用並接入投手個人頁，分頁叫 **In game**（不可叫 Replay）、預設所選年度最近一次出賽。新增 Game Center **3H in_progress**（5／17，3D–3G done 不重開）：共用 `PitchReplayPanel.vue`、`PitcherInGameTab.vue`、排序／篩選工具 `pitcherInGame.ts`；Game replay 分支改委派，Personal 新增 lazy 分頁，既有圖表僅加可自訂 title。沿用 personalOutings 與 game/pitcher replay API/cache，不改後端／座標公式或新增整季軌跡；有效 game_pk 深連結優先，無效退最近場。source-only 八項檢查＋單次 Nuxt typecheck PASS；證據 `petehub_pitcher_in_game_source_gate_v1.json`，五項人工清單在主文件 `GAME_CENTER_ANALYSIS_MODULES.md` 3.3。使用者驗收 `/pitcher-personal?tab=in-game` 與 `/games/today` 的原 Replay；代理未開瀏覽器、截圖或 server，不宣稱新 UI 通過。Ballpark 24／59 及 E2.1–E2.4 暫留原狀，本輪不做新圖／場景接線，未授權 E3／F。

2026-11-04 最新開工（優先於下方舊待驗／未授權文字）：使用者明確回報「E1可以，開始E2.1–2.4」，**E1 Done、24／59**，人工清單的 E1 兩項以整體接受同步，不推定裝置／GPU／效能；不再要求 E1 重驗。E2 維持正向回饋待明確結案。E2.1–E2.4 In progress 第一短批：新增 `petehub_ballpark_object_catalog_v1.json`、`build_ballpark_object_catalog.py` 與生成的 `output/ballpark/object-catalog-v1.md`，共 51 語意物件／候選＋現行全量 138 collision／82 foreground／16 portals／2 hotspots。source pin／ID／refs／來源覆蓋檢查 PASS，不是畫面完整性或互動 PASS；幾何列不是獨立物件數，未定位物件／背景裝飾群明列限制。

接續先讓使用者確認盤點表與三站 layout：Game 賽程／分析台／回放；Batting 名冊／個人分析／比較／Lab／練習網；Pitcher 名冊／球路／比較／工具／投球道；皆保留南側中央 R 出口與開放主走道。配置確認後才產三張新背景候選，每張經使用者核准才製作碰撞／foreground／portal 包。目前尚無新圖／新場景幾何，也沒有 runtime 修改或任何瀏覽器／圖片測試；既有五場景／D5 不重開。本輪授權只到 E2.1–E2.4，不自動做 E2.5／E3／E4／E5／F，也不重做角色。完整表由 JSON 生成，勿手改生成 MD 或將 planned intent 當既有功能。

2026-11-04 最新 Slice 重排（優先於後方歷史數量）：使用者要求把全部既有房間物件及三個新設施明確納入規劃。新增 E2.1 全場景物件／功能盤點、E2.2 Game、E2.3 Batting Cages、E2.4 Pitcher Mound、E2.5 八場景包；E3 收斂共用互動框架，新增 E3.1 既有五場景物件、E3.2 三新站物件、E3.3 generic NPC／對話／mini-map／fast travel。新增八個獨立 Planned 工作包，**23／59**，不是原有進度退回；D1–D5 不重開。僅文件規劃，沒有製作新圖／資料／程式，不等於授權開工；下一個建議為另獲指示後 E2.1。細節與依賴見主文件 Section E。

使用者回報「E2 目前測試沒大問題」，只記正向整體回饋，未補造個別輸入／硬體通過；E1／E2 保持 in_progress，E1 仍待快速切換／取消與 Classic 離開返回不重複畫布／角色／輸入的明確人工結案。使用者詢問 E1 能否 done 不視為已回報通過。三站目前直連 Classic，沒有 R 出口且 Back 可能回較舊的 Training URL；這是 E4 的來源設施／物件及關閉／history bridge、E5 的安全位置恢復範圍，不以重排宣稱已修復，也不拿精確位置恢復阻擋 E1 lifecycle 驗收。新背景先功能配置再新圖核准／分層製作；既有背景不重畫，E3 接線不代替 F 業務 parity。全部畫面由使用者驗收，無代理瀏覽器／測試 server／截圖／subagent。

2026-11-04 最新 E2 三處碰撞修正：Team Office 中央雙門／盆栽壁龕、右側入口盆栽櫃，以及 Clubhouse 左側電視上方櫃體已補獨立碰撞，現行 **138／82／16**。來源／匯出同步，針對性 numeric 阻擋／鄰近走道／出生點／入口／來源差異檢查 PASS；使用者畫面與手感尚未確認，不重開 D5、不開始 E3。此前 E1/E2「未改碰撞」僅指初次交付；本次三項為使用者後報的 E2 修正。沒有重跑 typecheck/build/完整 audit，既有 D5/E1-E2 證據是當時快照，不冒充新三處人工通過。

2026-11-04 最新 E1–E2：使用者同意先做這一批。已沿用 V0 補 AbortSignal／latest-load gate，取消過期載入並忽略過期回呼；錯誤／unmount 清理 observer／visibility／abort，舊 destroy 不會清空新 canvas。E2 補失焦／表單／暫停阻擋及輸入清除，手把須回中立／放開 A 後恢復，每次按下只互動一次。D5 圖片／碰撞／zoom／速度／入口不動；新增 `runtimeGuards.ts` 與純來源檢查 `check-ballpark-runtime.mjs`，五項契約檢查＋單次 Nuxt typecheck PASS。證據／五項人工清單為 `petehub_ballpark_e1_e2_source_gate_v1.json`／`petehub_ballpark_e1_e2_manual_acceptance_v1.json`。E1／E2 in_progress，23／51 不變，等使用者測快速切換／Classic 往返／失焦暫停表單／移動相機reset／可用touch-gamepad；不代測瀏覽器、不開始 E3。靜態 import 檢查不是正式 bundle graph，Phaser 次幀銷毀不是已量測 GPU／listener 零殘留，E6 保留。

2026-11-04 最新決策：使用者明確回報 D5 驗收通過，**Section D 完成，23／51**。人工清單、場景／角色 acceptance 及資產限定 readiness 已同步；最終 `petehub_ballpark_d5_release_gate_v1.json` asset gate PASS／零 findings，135 collision／82 foreground／16 portals 不變。`production_ready=true` 只指 D5 素材，不代表網站或 E6 runtime release；實機／瀏覽器型號與數值效能未提供，不自行補測或推定。Section E 尚未授權實作，接續應從 E1 開始而非直接跳 E5。背景可於後續版本修訂並局部重驗；E3／F4 已規劃通用 NPC 與主隊 8–10 名球員，但全園區／室內隨機出現及漫遊尚無凍結規格。E5 是安全場景／位置存檔與版本／壞檔復原，不是 NPC 生成。下列 11-03 待驗紀錄為歷史，不能重新打開已驗收 D5。

2026-11-03 最新通道修正：Coach 會議桌右緣與文件櫃之間原只餘 19px，桌椅右側碰撞外緣 x556→536 後改為 39px；角色 footprint 不變。右側繞至下方通道的來源幾何檢查完成，背景／入口／其他場景不動，`collision_overrides`／匯出／manifest 已同步，總量仍 135／82／16；人工手感待驗。D5 source gate v2 早於這次修正，不宣稱新增全 gate／browser PASS，不重跑完整 build/audit。D4 保持 done，D5 保持 in_progress。

2026-11-03 D5 收尾（優先於下方早期紀錄）：最新 **135 collision／82 foreground／16 portals** 已完成 D5 source-only 檢查，零 findings，證據 `petehub_ballpark_d5_source_gate_v2.json`；v1 保留歷史。代理程式／資料工作完成，D5 仍 in_progress／22 of 51，`production_ready=false`。使用者尚需回報 `petehub_ballpark_d5_manual_acceptance_v1.json` 的五項：Team Office 新碰撞、五場景載入／遮擋／邊緣、窄版／可用實機、reduced-motion、缺圖 neutral／silhouette／Static／Classic fallback。詳細網址／步驟見主文件 D5 章節及 JSON；缺圖由使用者 DevTools 暫時封鎖請求，不刪素材、不另開 server。已驗收的 D4／隊色／RLS／Campus 網子／頁寬不重測。未測實機不當作通過；不代驗畫面、不自動進 Section E。

2026-11-03 最新 D5 followup：Team Office Coach 看板／櫃體與 GM 螢幕／櫃體穿模已依使用者要求補兩個 rear-wall-equipment 碰撞。只改獨立碰撞及同步輸出，沒有新觸發功能；現行 **135 collision／82 foreground／16 portals**。已完成針對性 source geometry／入口／走道／匯出一致檢查，使用者人工驗收仍待回報；D5 不結案、D4 不重開。下段 11-02 的 133 數量及 source gate 證據是此次修正前紀錄，不覆蓋新碰撞；不重跑整套 audit/build，不代驗畫面。

2026-11-02 最新補充（優先於後方歷史摘要）：使用者已明確回報 D4 與全部 followup「都通過，進入 D5」。**D4 Done，22／51**；favorite-team 隊色、R／L／S、移除樣本按鈕、圍網與 70vw 頁寬不再待驗。現行 v3 **133 collision／82 foreground／16 portals**。D5 已授權並補齊角色／來源／組合／紋理 source-only gate，零 findings、十項 focused tests PASS，證據在 `data/sample/petehub_ballpark_d5_source_gate_v1.json`。PNG 12.44 MiB，單房＋User RGBA8 估算 18.70 MiB，不是實測 GPU／heap。D5 只剩載入／depth／邊緣、窄版／實機、reduced-motion、缺圖 fallback 的使用者結果；不可重問 D4 功能或同張素材。`production_ready=false`，D5 保持 in_progress，無代理瀏覽器／截圖／操作驗收。FPS／LCP／cleanup 的 E6 尚未開始，不自動進入 Section E。

<!-- PROJECT_PROGRESS:START -->
Tracker updated: 2026-11-14

| Project | Status | Slices | Current direction |
| --- | --- | ---: | --- |
| Batter Comparison & Research | done | 10/10 | Only reopen when a verified exact timing, stance, roster or injury source becomes available. |
| Pitch Quality Leaderboards | in_progress | 12/13 | Keep Stuff+ v2/v5 research-only; allow Location+ v2 to enter shadow monitoring, then proceed to Slice 11 historical backfill/release gate only after prospective checks. |
| 換投決策與預警研究 / Pitcher Decision Lab | in_progress | 12/24 | 新增 Slice 6–10 結果區待使用者人工驗收；下一階段為 Slice 11 決策樣本庫與探索分析，尚未開始，須使用者指示。 |
| RE24 & Leverage Lab | done | 4/5 | Automate or explicitly version the collected reliever reference cutoff. |
| Daily Data Reliability | done | 7/7 | Observe the next 03:00 scheduled run in the selected mode. During the off-season, pause daily game refresh while leaving transactions enabled; use explicit --step or --retry-failed for manual recovery. |
| Project & Slice Tracker | done | 4/4 | For future material work, update the project document and tracker JSON, run the sync script, then keep only recent cross-project changes or live blockers in the concise handoff. |
| Stamina+ Research & Lab | done | 24/24 | Treat Slice 0–19 as complete. Reopen only for a genuinely untouched season validation, or begin the separate Player Health & Availability research with its event-source audit. |
| Pitcher Metric Explorer | done | 1/3 | Slice 2 can add a separate pitcher-game explorer for Game Score, WPA, pitch count and the aligned Quality／Physical／Command game states; it must not mix game rows into the season-level regression. |
| Pitcher Performance State, Collapse & Rebound | active | 28/28 | Keep the strict 2026 replay locked and wait for untouched 2027 prospective rows; compare the frozen Primary and shadow candidates append-only before any production integration. Upgrade the Lab player timeline only after a point-in-time v2 artifact is specified. |
| Player Archetypes & Pitch Strategy | done | 13/13 | Treat Slice 0–6D and 3B as complete. Keep practical_v1 at monitor status while reviewing false positives and adjacent-season stability in the Pitcher Tag Lab; keep Primary Pair hidden unless a later validated definition is easier to interpret. |
| Pitch Strategy Simulation & Game Theory | planned | 0/8 | Begin Slice 0 by freezing the completed Slice 4–6D inputs, chronology, pre/post-pitch boundary and replay vocabulary before adding any new location, transition or simulation model. |
| Catcher Descriptive Metrics | done | 9/9 | No required catcher-descriptive Slice remains. Reopen only if the park-factor source URL/methodology and an exposure-weighted adjustment formula are frozen, or if a separately validated batter-response layer changes the strategy release boundary; otherwise preserve the current no-composite, no-causal-value contract. |
| Game Center Analysis Modules | in_progress | 6/18 | User validates 3I count/previous-pitch/hand context updates, season-PR toggle, empirical Scout target/probabilities, low-history fallback and pause/rapid selection. Keep 3I in_progress; no prediction-validation, visual/device PASS or resumed actor motion is implied. Existing full-season Sequence branch remains descriptive. |
| Petehub Ballpark Game System | in_progress | 40/66 | User acceptance only for latest F2 revision: pitcher/large diagram/Selected Pitch table removed; aligned heatmap/View/Compare controls and outer-right matchup sidebar; automatic Conditioned branch based on exact count/L-R batter/previous pitch, preserving PA descendants; native video-only popup in Game and Personal; original heatmap/R return. F2.4/F2.6/F2.7 still in_progress, F2.5/G motion deferred. Do not start F3 before this handoff/acceptance; E6/F2.6 performance/device release evidence remains outstanding. |
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
