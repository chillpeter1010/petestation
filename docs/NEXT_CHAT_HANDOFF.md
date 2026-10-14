# Petehub 專案新對話交接文件

更新日期：2026-10-08
專案根目錄：`C:\intern\project_transfer`

> **編碼警告：本文件與專案內含繁體中文。新對話必須以 UTF-8 讀取檔案，例如 PowerShell 使用 `Get-Content -Raw -Encoding UTF8`；不可依賴系統預設編碼，避免中文亂碼或誤寫回檔案。**
>
> 新對話開始時，請先完整閱讀本文件，將它視為目前專案的主要前情。不要重新驗證「最近已完成並確認」的項目。
>
> 專案／Slice 進度另以 `docs/PROJECT_TRACKER.json` 為權威來源；`docs/PROJECT_TRACKER.md` 是其產生的人類可讀版本。新對話必須一併閱讀，並在工作實際完成、阻塞、延期或新增 Slice 時同步更新 tracker。

## 建議貼到新對話的第一句

```text
請用 UTF-8 完整閱讀 C:\intern\project_transfer\docs\NEXT_CHAT_HANDOFF.md 與 docs\PROJECT_TRACKER.json，將它們視為目前專案的權威前情；PowerShell 請明確使用 Get-Content -Raw -Encoding UTF8。
不要重做文件中標記為已完成、已驗證的修改。
Stamina主線已完成至Slice 19；先檢查git status，不要重跑Slice 0–19。2026 adjusted observed-season leaderboard保持凍結；Quality、Physical與Command必須分開呈現，因Slice 18增量RMSE門檻未通過。
Performance State v1已完成Slice 0–11，獨立v2已完成Slice 11A–15；不要重跑或把研究榜接正式排行榜。Shadow ledger目前只有2026 historical backfill、尚無真正prospective列；Slice 15 readiness已完成，但2027資料尚未存在，仍保留為untouched prospective validation。
回答使用繁體中文，先簡短說明要改哪些檔案，再直接執行；修改後只回報異動檔案與必要驗證結果。
若會修改全域共用元件、共用 CSS、共用資料 schema 或模型契約，必須先明確提醒。
```

---

## 2026-10-02 目前任務

### 2026-10-05 Pitcher Performance State Slice 0–3A

- 新增獨立research-only管線`pitcher_performance_state_contract_v1`，不改寫Observed Stamina+、Quality、Physical、Command或正式排行榜。四個預測目標為process collapse、result collapse、combined collapse與崩盤後return-to-baseline／strong rebound；SP／RP從資料、個人基準、標籤到模型全程分開，雙重身分保留兩條歷史。
- Slice 0以2025凍結角色內5%門檻。Stuff+／Location+、RE24/PA與WPA/LI/PA都先扣除只使用當時以前登板的pitcher×role empirical-Bayes基準；不可退回聯盟原始z-score，否則會把長期球員能力誤當短期狀態。2026固定門檻下SP process-collapse率9.99%（2025為5%，+4.99pp）觸發跨季漂移警告；RP為6.48%（+1.48pp）未超過2pp門檻。這是分布／模型校準漂移，不是生理結論。
- Slice 1建立2025共20,868次登板（4,860 SP／16,008 RP）與2026共20,793次（4,857／15,936）的唯一pitcher-game-role warehouse。Stuff+／Location+ coverage兩季近100%，PA-boundary RE24/WPA結果coverage近100%；Quality／Physical／Command約21–23%是既有starter-oriented來源邊界，RP不補值。Game Score因2025缺完整官方逐場line，固定標為starter-only Bill James-style runs-allowed proxy，不冒充官方值。
- Slice 2所有predictor皆shift到目標登板之前。2026 process-score RMSE：last 0.8421、MA5 0.6762、EWMA5 0.6729；lagged logistic的collapse AP 0.2047、Brier 0.0609、log loss 0.2390，相對2025 prevalence baseline AP 0.0698、Brier 0.0656、log loss 0.2596。反彈目前只有prevalence baseline，保留給Slice 8整合。
- Slice 3A修正原Slice 3的時間契約：不再把缺少`days_rest`補成4天，而是直接由同一pitcher×role相鄰`game_date`計算日曆間隔；固定登板策略及明示reset策略遇到至少60天都重置。2025內部逐次前瞻比較固定登板、日曆衰減與日曆衰減＋60天reset；沒有使用2026選策略。2026首場回歸者實際gap完整覆蓋SP 243條、RP 456條，中位數196／202.5天；舊欄位缺值179／411條均未再補4天。
- State-Space升版為`hierarchical_diagonal_ar1_state_space_v1_1`，phi網格加入0／0.10／0.25。2026 Stuff state相對zero-state RMSE改善SP 13.80%、RP 11.57%，仍是唯一明確有用的persistent state；Command改善1.87%／0.40%，只列exploratory；Result兩角色phi皆為0、改善0%，視為white noise／無增量預測力。Stuff phi皆0.85，half-life正確單位為4.265個5日單位＝21.33日，換算約SP 3.55次、RP 7.11次登板；換算登板數只是角色中位間隔近似，不是球員個別恢復承諾。
- 2026因Slice 3A是在首次診斷後修訂協議，正式狀態改為`test_with_documented_slice3a_amendment`，不可再稱pristine untouched test；2027保留為真正prospective untouched validation。
- Artifacts：`performance_state_contract.json`、`performance_state_appearances_<2025|2026>.parquet`、`performance_state_filtered_<2025|2026>.parquet`、`performance_state_slice0_3.json`。重建：`python backend/scripts/build_performance_state.py`。API：`/api/performance-state/overview`、`/api/performance-state/player`。HTTP只讀快照、不訓練。
- 驗證：真實兩季v1.1完整重建、Pydantic overview/player smoke、跨季calendar-gap／60日reset、causal history與future-observation invariance tests通過。Slice 4後續已使用此v1.1 filtered states完成，未重新調State-Space或拿2026選模型。

### 2026-10-05 Pitcher Performance State Slice 4–6

- Slice 4使用`hmmlearn 0.3.3`的role-specific diagonal-Gaussian HMM；特徵為filtered Stuff state、同場state change與5場innovation volatility。候選2–5 states只用2025 fit／時間後段validation，最低occupancy門檻2%，多起點後再用pitcher bootstrap檢查emission與transition穩定性；正式推論只用filtered probabilities，不使用smoothed future information。實際選出SP 2 states（Stable／Collapse）、RP 3 states（Stable／Collapse／High-volatility）；4–5 states的held-out likelihood明顯惡化，因此沒有硬造Declining／Recovering。Bootstrap中位emission similarity SP 0.721／RP 0.693、transition similarity 0.979／0.870；2026 process-collapse AP 0.102／0.098，仍屬research-only。
- HMM基礎transition由2025估計，推論時依實際gap對transition matrix做時間次方；至少60天改用2025 stationary prior，避免跨季承接。狀態名稱由標準化emission prototype做一對一post-fit assignment，控制label switching；名稱不是生理階段。
- Slice 5完成`student_t_gas_har_panel_v1`。以Stuff standardized innovation為波動訊號，GAS採Student-t score更新；HAR correction只用目標登板以前的lag-1、MA5、MA15、7／28日用量與calendar gap。log variance轉回level時使用只由2025 residual估計的Duan smearing factor。2026 GAS+HAR NLL SP 1.6044／RP 1.6089，優於EWMA 1.6067／1.6150；QLIKE 1.3935／1.4477，優於1.3992／1.4555。改善很小，不得包裝為重大突破；80%／95% coverage約SP 81.1%／95.6%、RP 81.2%／95.6%，squared-standardized residual lag-1 autocorrelation 0.041／0.045。
- Slice 6完成`student_t_gjr_garch_panel_v1`。使用`arch 8.0.0`的Student-t likelihood與SciPy constrained optimizer；SP／RP pooled參數但每個pitcher×role及至少60天gap都重置，不把不同投手串成假序列，也不做樣本不足的逐投手GARCH。兩角色皆收斂，persistence SP 0.991／RP 0.987，但negative-shock gamma皆為0；目前沒有證據支持負面shock比正面shock額外放大未來波動。GJR 2026 NLL 1.6059／1.6130，未勝過GAS+HAR。
- 新runtime artifacts：`performance_state_slice4_6.json`、`performance_state_advanced_<2025|2026>.parquet`。重建：`python backend/scripts/build_performance_state.py --slice4-6-only`；無參數則先重建Slice 0–3A再接4–6。Overview／player API已向後相容加入Slice 4–6 audit、regime probabilities與四種variance forecast。依賴已加入`hmmlearn==0.3.3`、`arch==8.0.0`；本機Python 3.14的hmmlearn需`C:\BuildTools`編譯。
- 驗證：真實2025／2026完整重建，advanced row key唯一，Pydantic overview/player smoke、calendar-gap transition與GAS future-invariance測試通過；Performance State＋WPA targeted tests共11 passed。下一步Slice 7不得回頭用2026重調Slice 4–6。

### 2026-10-05 Pitcher Performance State Slice 7

- 完成`pot_evt_caviar_panel_v1`，輸入固定為Slice 5的pregame GAS＋HAR variance與Stuff standardized innovation；尾端loss定義為負向innovation除以預測標準差。POT threshold只在2025 chronological fit／validation比較90%／92.5%／95%，declustering run length比較0／1／2；沒有使用2026選threshold、declustering或CAViaR規格。
- Threshold候選改以全validation censored likelihood同尺度比較：未超標使用`log(1-q)`、超標使用`log(q)+GPD density`。SP選q95／run0，共236個development clusters；GPD shape ξ=0.023，100次bootstrap 95% CI -0.088至0.129，KS p=0.926，接近exponential且無法確認heavy／bounded方向。RP亦選q95／run0，共758 clusters；ξ=0.343，CI 0.276至0.446，KS p=0.390，顯示RP的標準化負向innovation尾端明顯較重。run0勝出代表額外合併相鄰exceedances沒有改善2025 validation，不代表事件完全獨立。
- 2026 raw extreme rate為SP 4.43%／RP 5.10%；固定standardized POT threshold exceedance為4.69%／5.30%。EVT對raw extreme的AP為0.076／0.101；以2025 risk top-decile作alert，alert rate 9.78%／8.60%、recall 20.93%／19.95%、false-alert rate 9.26%／7.99%。辨識力有限，不能直接當高可信度警報。
- EVT在raw threshold映射仍位於POT tail時才使用GPD survival並提供expected severity；否則以凍結的2025 empirical survival補完整probability，但`evt_tail_supported=false`且severity保持null。2026 strict EVT support為SP 57.83%、RP 66.24%，前端未來必須揭露這個差異。
- CAViaR的SAV與Asymmetric Slope只用2025 validation選模，兩角色皆選Asymmetric Slope。2026 SP 95% VaR violation 5.09%、Kupiec p=0.785，coverage通過；RP violation 5.74%、p=0.000031，明確失敗，不得將RP CAViaR稱為已校準。CAViaR alert AP為0.076／0.097，沒有明顯勝過EVT。
- 新artifacts：`performance_state_slice7.json`、`performance_state_tail_<2025|2026>.parquet`；重建：`python backend/scripts/build_performance_state.py --slice7-only`。Overview與player API已加入Slice 7 audit、EVT probability／supported severity、CAViaR VaR與alert欄位。驗證包含缺值shock不污染後續CAViaR recursion、artifact唯一鍵、API schema、UTF-8與targeted tests。下一步Slice 8只能整合凍結features，不得拿2026重新調Slice 7。

### 2026-10-05 Pitcher Performance State Slice 8–9

- 完成`collapse_rebound_forecast_v1`與`performance_state_external_diagnostic_v1`。四個目標維持獨立：process collapse、result collapse、return-to-baseline、strong rebound；SP／RP分開訓練，沒有產生綜合risk score。崩盤預測只用目標登板前可知欄位；反彈預測只在上一場同角色process collapse後啟用。任何current-appearance filtered state或innovation都禁止當predictor並有測試鎖定。
- 2025按時間固定切60% training／20% calibration／20% validation；依序比較A lagged baseline、B state forecast、C regime prior、D GAS+HAR、E EVT五層penalized logistic，另以含GJR／CAViaR的XGBoost作challenger。沒有拿2026選feature layer、校準或alert threshold；HMM未實際存在的角色狀態欄位直接排除，不補0、不硬造regime。
- 2026 amended external diagnostic：process-collapse AP為SP 0.185（prevalence 0.100）、RP 0.183（0.065），兩者均通過AP至少+0.01且Brier/log-loss不惡化門檻；SP result-collapse AP 0.063（0.047）也窄幅通過；RP return-to-baseline AP 0.716（0.569）通過。SP return-to-baseline、SP/RP strong rebound及RP result-collapse未通過完整門檻。RP process-collapse的XGBoost AP 0.235高於primary 0.183，但仍只列challenger，未用2026回頭換模。
- 固定false-alert threshold、calibration bins、pitcher-cluster bootstrap 95% interval、dominant arsenal subgroup、feature importance與扣除2025角色平均均值回歸後的`excess_recovery`診斷均寫入audit。SP兩個rebound機率與excess recovery呈負相關，進一步支持不發布；RP return-to-baseline呈正相關0.203。整體決策固定`keep_research_only`，因不是所有role×target通過，且2026不是pristine test；不得接正式排行榜、Pitcher Personal或下一場先發卡。2027仍是untouched prospective validation。
- 新artifacts：`performance_state_slice8_9.json`、`performance_state_forecasts_<2025|2026>.parquet`；重建：`python backend/scripts/build_performance_state.py --slice8-9-only`。Overview／player API已加入Slice 8–9 audit及四組probability／alert。真實2026產物20,793列且pitcher-role-game key唯一；Performance State＋WPA targeted tests共15 passed。下一步Slice 10只做large-type research Lab，必須清楚顯示哪些模型通過／失敗與校準限制。

### 2026-10-06 Pitcher Performance State Slice 10

- 新增`/lab/performance-state`與Pitcher Lab入口。頁面以大字級、直角panel呈現SP／RP與process collapse、result collapse、return-to-baseline、strong rebound四個獨立目標；顯示amended-2026 AP／Brier／log-loss／alert指標、通過／失敗gate、2025 feature-layer ablation、logistic feature influence及限制說明。未通過模型固定顯示`NOT RELEASED`，不產生綜合分數。
- 新增`GET /api/performance-state/leaderboard`。研究榜只讀既有Parquet，不在HTTP訓練；每位pitcher-role顯示最近一筆已完成登板的pregame probability、球季平均機率、事件數／率與日期。這是completed-appearance retrospective board，不是下一場預測；下一場roll-forward仍保留給Slice 11。
- 排行榜點選投手會載入既有player API的逐場時間線，顯示預測機率、實際事件、process/result score、filtered regime、GAS+HAR variance及EVT risk；球員姓名另可前往Pitcher Personal，但本輪沒有把研究模型接進正式個人頁。
- 2026 minimum_forecasts=5的真實smoke：process/result榜SP 243人、RP 500人；conditional rebound榜SP 18人、RP 51人。缺少上一場collapse機會的投手不補0、不列入反彈榜。8組role×target response及player schema均通過。
- 驗證：Performance State＋WPA targeted tests共15 passed、UTF-8與Nuxt typecheck通過；沒有執行Nuxt build。Computer Use工作階段沒有browser surface，因此未完成實際瀏覽器視覺QA，後續若有browser可用應優先檢查桌面／窄螢幕布局。下一步Slice 11只做frozen-model shadow monitoring與atomic prospective error log，不得因Slice 10頁面完成就接正式排行榜或next-start卡。

### 2026-10-07 Pitcher Performance State Slice 11

- 完成`performance_state_shadow_monitor_v1`與`GET /api/performance-state/shadow`。不可變帳本為`performance_state_shadow_ledger.parquet`，主鍵是year／pitcher／role／game／target；既有預測機率不覆寫，來源日後出現不同機率時保留帳本值並記錄conflict。`performance_state_slice11.json`保存role×target的calibration、AP／Brier／log-loss及hit／miss／false alert／correct negative。
- 首次初始化共44,384筆2026 target rows，資料截至2026-09-27，全部標記`historical_backfill`；再次執行`python backend/scripts/build_performance_state.py --slice11-only`為`no_new_rows`，新增0、衝突0。目前`prospective_rows=0`，不能把回填結果稱為前瞻驗證。日更只在freshness報告標示此資料，尚未自動重建Performance State全鏈；後續只能在新的completed appearance artifacts可用後明確重建，再把新主鍵列append為`prospective_append`。
- `/lab/performance-state`研究榜點選球員後顯示Rotation風格的逐場時間序列。Process Collapse／Return／Strong Rebound的實際值使用個人基準調整後Stuff+與Location+平均的`process_score`，預測值是登板前Stuff state與Command state forecast的可用值平均；Result Collapse的實際值使用個人基準調整後RE24/PA與WPA/LI/PA平均的`result_score`，預測值使用登板前`result_state_forecast`。紅色實線／圓點是實際表現，藍色虛線／菱形是預測表現，同場以淡色垂直虛線顯示預測誤差；這兩條都不是事件機率。
- 圖上每場有日期座標；hover／keyboard focus顯示用球數、WPA、RE24、WPA/LI、Stuff+、Location+、Process／Result Score、四個目標機率與hit／miss／false-alert狀態。Leaderboard及逐場明細每個顯示欄位均可升／降冪排序。事件alert仍使用2025凍結的role×target threshold，不使用任意50%；命中場的實際節點以紫色外框輔助辨識。2025頁面不顯示2026 shadow摘要，避免把開發季誤作監控季。
- Integration gate維持`CLOSED`：至少要有untouched 2027且每個role×target至少250筆真正prospective rows；目前不得接Pitcher Personal、下一場先發卡、正式排行榜或production alert。
- 驗證：Performance State／WPA／freshness targeted tests共19 passed、backend venv `pip check`、UTF-8與Nuxt typecheck通過；未執行Nuxt build。資料新鮮度報告新增`performance_state_shadow`，明示為manual frozen-model rebuild與immutable append ledger。

### 2026-10-07 Pitcher Performance State v2 Slice 11A–13

- 新建完全獨立的`performance_state_multiseason_v2`管線；沒有覆寫v1的appearance／forecast／leaderboard／shadow ledger，也沒有改動正式Observed Stamina+。重建入口為`python backend/scripts/build_performance_state.py --slice11a-13-only`，唯讀稽核API為`GET /api/performance-state/v2-audit`。
- Slice 11A新增逐登板資格與情境分類。球員當季若曾以fielder_2至fielder_9守位出現在Statcast即列為position-player pitching稽核候選；另把季內少於60球、最多4場且單場不超過40球者列為`low_volume_emergency`。後者是事後cohort filter，禁止當pregame predictor；若未來取得官方roster position，應優先取代守位proxy。先發拆成opener-like／short／traditional starter，後援拆成bulk／standard relief，並把process collapse拆成first onset與prior-collapse後的persistent collapse。
- 2023／2024／2025／2026共有20,629／20,693／20,868／20,793筆唯一pitcher-role-game；model-eligible率95.22%／95.46%／95.29%／94.71%。四季position-player pitching登板為115／88／131／142筆；2026另有316場opener-like、4,308場traditional starter與1,003場bulk relief。Plus與PA-result coverage接近100%。
- Slice 12建立`performance_state_v2_warehouse_<year>.parquet`，四季統一使用2023 leverage reference；歷史Stuff+／Location+是以目前凍結模型回算，因此後續forward folds只驗證Performance State層，不能宣稱同時完成Plus模型的純樣本外驗證。
- Slice 13固定三個expanding-window folds：2023→2024、2023–24→2025，以及只作diagnostic的2023–25→2026。每個fold的角色基準、標準差、5%門檻、imputation與logistic係數都只由train years估計；預測artifact為`performance_state_v2_predictions_<2024|2025|2026>.parquet`，同時保存raw與clean cohorts及六個互不混合的targets。
- 主要結論：SP／RP的onset process-collapse在三個fold都優於prevalence；return-to-baseline也持續有訊號。Persistent collapse與strong rebound有潛力，但部分SP條件樣本很小，Slice 14前必須補pitcher-cluster uncertainty／校準檢查。SP result-collapse在2026 diagnostic沒有改善，現階段不得升級。2027仍保持untouched，v2目前仍是research-only。
- 產物為`performance_state_v2_contract.json`、`performance_state_v2_slice11a_13.json`、四季warehouse及三個test-year prediction files。完整建置約84秒；Performance State／WPA／freshness targeted tests共23 passed，其中v2專屬tests 4 passed；backend venv `pip check`與UTF-8檢查通過。

### 2026-10-07 Pitcher Performance State v2 Slice 14A–14B

- Slice 14A完成`performance_state_cluster_calibration_audit_v1`。每個fold／role／target以pitcher_id為cluster做100次bootstrap，另外保存calibration slope、intercept、ECE與evidence status；不把逐登板列當作獨立樣本。`supported`要求AP gain的95% cluster interval下界大於0，且Brier 95% interval上界不惡化；否則只標`ranking_only_or_uncertain`。
- 14A三個fold的穩定訊號是：SP／RP onset process-collapse皆通過；RP return-to-baseline皆通過。2026 diagnostic中SP return-to-baseline與strong-rebound也通過區間篩選，但因2026不是untouched test仍不得發布。Persistent SP多數fold與大部分strong-rebound只具排序或不確定證據；SP result-collapse在2026 AP gain interval為-0.0048至+0.0078、Brier interval為0至+0.0002，明確不支持升級。
- Slice 14B完成`performance_state_multiseason_advanced_v1`。使用2023–2025固定訓練／模型選擇，2026只作一次diagnostic；產出`performance_state_v2_slice14_states_<2023|2024|2025|2026>.parquet`、`performance_state_v2_slice14_predictions_2026.parquet`及`performance_state_v2_slice14.json`，共61,398筆target prediction。唯讀API為`GET /api/performance-state/v2-slice14-audit`，重建為`python backend/scripts/build_performance_state.py --slice14-only`。
- State-space多年度診斷：2026 Stuff state相對zero-state RMSE改善SP 18.03%、RP 11.81%；Command SP改善5.31%但RP僅0.22%且列exploratory；Result state兩角色皆0%增量。這支持把Stuff當主要持續狀態，Command只在SP保留研究訊號，Result不應硬套persistent latent state。
- HMM在多年度資料選出5-state，但SP bootstrap emission similarity只有0.424、transition similarity 0.763，穩定度遠低於RP的0.792／0.927；因此5個 regime名稱只能視為診斷，不應接產品。GAS／HAR的改善很小：SP EWMA NLL 0.9215優於GAS 0.9226與GAS-HAR 0.9230；RP GAS NLL 0.6446略優EWMA 0.6458，但GAS-HAR反而0.6581。GJR兩角色negative-shock gamma皆0，未支持負向衝擊額外放大波動。
- 多年度 tail 診斷：SP／RP皆選q95、run0；GPD shape約-0.055，與前一版RP重尾結果不同，顯示尾端形狀對訓練窗口敏感。2026 EVT supported rate為SP 65.21%、RP 69.16%；CAViaR改選SAV且Kupiec p=.819／.720，兩角色通過coverage，但這只代表VaR覆蓋，不代表崩盤預測能力高。
- 2026固定診斷 forecast：SP／RP process-collapse通過；RP result-collapse與return-to-baseline通過；SP result-collapse、onset、return／strong-rebound，以及RP strong-rebound未通過完整Brier／log-loss gate。只有AP提升不能視為機率校準成功。2027仍 untouched，沒有接正式排行榜、Pitcher Personal、下一場卡或production alert。
- API schema、Slice 14A/B targeted tests 2 passed；Performance State／WPA／freshness回歸測試共25 passed，`pip check`與UTF-8檢查通過。Slice 15預定為固定模型的2027 prospective shadow，不得中途用2027重選HMM／GAS／EVT或threshold。

### 2026-10-07 Pitcher Performance State v2 Slice 15

- 完成`performance_state_2027_prospective_shadow_v1`的readiness／shadow contract與`GET /api/performance-state/v2-slice15-audit`。重建指令為`python backend/scripts/build_performance_state.py --slice15-only`，目前產物為`performance_state_v2_slice15.json`。
- Slice 15會對Slice 14 audit、四季advanced states、2026 predictions、Slice 11A–13 audit與四季warehouse做SHA-256 fingerprint；若任何凍結輸入事後改變，audit會標為`stale`，禁止追加觀測。`model_refit_allowed=false`、`thresholds_locked=true`、`calibration_locked=true`。
- 目前`data/MLB2027/mlb_2027.duckdb`不存在，因此真實狀態為`awaiting_untouched_2027_source`、prediction rows=0、observed rows=0、integration gate=`CLOSED`。這是外部資料尚未到位，不是模型錯誤；Slice 15的實際prospective evaluation不能在2027資料不存在時假造。
- 未來來源出現後仍須走append-only materialization與賽後 observation；每個role×target至少250筆前瞻列、校準與cluster uncertainty gate都通過前，不得接Pitcher Personal、下一場卡、正式排行榜或production alert。Slice 15 readiness本身不會在HTTP請求內訓練任何模型。
- Slice 15 schema／readiness tests 2 passed；加上本輪完整 Performance State／WPA／freshness regression 共27 passed，`pip check`與UTF-8檢查通過。

### 2026-10-08 Pitcher Performance State v2 Slice 16 optimization challenger

- 在不覆寫 Slice 14／15、v1 artifacts、shadow ledger 或正式產品資料的前提下，新增 `performance_state_v2_slice16_service.py` 與 `python backend/scripts/build_performance_state.py --slice16-only`。新產物為 `data/derived/performance_state_v2_slice16.json` 及 `performance_state_v2_slice16_predictions_2026.parquet`，目前 81,092 筆固定 2026 diagnostic predictions。
- 時間設計固定為 2023–2024 development、2025 model selection、2023–2025 refit、2026 fixed diagnostic；2027 仍 untouched。候選特徵分為 stable EWMA／MA5（lag process、MA5、EWMA、lag volatility）與 context／workload（再加 calendar gap、7／28 日用量與前一場球數）。
- gate 修正：prevalence baseline 的 AP 可能數值上不差，但零變異預測現在明確標記 `baseline_only_not_supported`，不再視為模型成功；正式 candidate 仍需 AP 增益 ≥0.01、Brier／log-loss 不劣、且 pitcher-cluster 95% interval 同時支持。
- Slice 16 2026 diagnostic 的 baseline gate：SP 通過 process-collapse、onset process-collapse、return-to-baseline、strong-rebound；SP result-collapse 與 persistent process-collapse 仍 research-only。RP 通過 process-collapse、result-collapse、onset process-collapse、return-to-baseline；RP persistent process-collapse 與 strong-rebound 仍 research-only。再和相同分母的 Slice 14 比較後，只有 SP strong_rebound 的 AP 增益達門檻且 Brier／log-loss 不劣；其餘可比目標都標 `keep_frozen`，不能因勝過 prevalence baseline 就升級。這些不是 2027 樣本外結論，也未接回正式排行榜／下一場預測／Pitcher Personal。
- Slice 16 API：`GET /api/performance-state/v2-slice16-audit`。`API_CONTRACTS.md`、`PROJECT_TRACKER.json`／`.md` 已同步；新增 Slice16 schema／gate 測試，Slice14／15 regression 4 passed，build、UTF-8與既有測試均通過。下一步應先檢視 Slice16 的校準（尤其 ECE 偏高的 rebound）與 workload selection bias，再決定是否另切 rolling calibration／hierarchical pooling challenger；不要把 Slice16 直接升 production。

### 2026-10-08 Pitcher Performance State v2 Slice 17 calibration challenger

- 新增 `performance_state_v2_slice17_service.py`、`python backend/scripts/build_performance_state.py --slice17-only`、`data/derived/performance_state_v2_slice17.json` 與 `performance_state_v2_slice17_predictions_2026.parquet`。Slice17 只校準 Slice16 challenger，不覆寫 Slice14／15。
- 時間順序固定為 2023–2024 fit、2025 calibration selection、2023–2025 refit、2026 fixed diagnostic。候選是 raw、Platt、isotonic；2025 只負責選擇，2026 只負責診斷。
- 2026 結果顯示大多數 collapse／rebound 目標應保留 raw 機率；SP return-to-baseline 與 RP persistent-collapse 的校準在 Brier／log-loss 同時改善，因此只列為 calibration-positive research diagnostic。SP strong-rebound 雖然 Slice16 曾勝過 Slice14，但 isotonic 在2026變差，Slice17保留raw，不能把選擇期結果當作樣本外成功。
- API：`GET /api/performance-state/v2-slice17-audit`。新增 Slice17 schema／校準測試；production integration 仍 `closed`，2027 仍 untouched。下一步應評估 hierarchical partial pooling、角色／球種分層校準與 workload selection bias，不應直接把任一 Slice17 結果接正式頁面。

### 2026-10-08 Pitcher Performance State v2 Slice 18–20

- 新增 `performance_state_v2_slice18_20_service.py`、`python backend/scripts/build_performance_state.py --slice18-20-only`、`data/derived/performance_state_v2_slice18_20.json`，以及獨立的 Slice18／Slice19 2026 prediction Parquets。三個 slice 共用 2023–2024 development、2025 selection、2026 fixed diagnostic，2027 untouched。
- Slice18 是 empirical-Bayes pitcher-role residual shrinkage，不是假設已完成正式 GLMM／Bayesian random-effects。2025 選擇後只有 SP strong-rebound 採 partial pooling；其餘目標保留 global-only。這顯示小樣本 rebound 有部分個人差異訊號，但不能直接視為正式提升。
- Slice19 是 workload selection-bias sensitivity：比較標準 workload/context 與以 2023–2024 投手歷史平均殘差化的 workload。只有 RP persistent-collapse 在 2025 選擇採 residualized workload，其餘仍保留 context。這不是因果 workload effect 校正，不能解讀成用球數造成崩盤。
- Slice20 對 Slice17 2026 probabilities 依 SP/RP、target、dominant Fastball／Breaking／Offspeed 分組計算 ECE、calibration slope／intercept；小樣本或 ECE>0.05 標 `monitor`，不自動重調機率。當前 SP 有10個、RP有8個 subgroup 被標為 monitor，後續需 rolling-origin 再確認。
- API：`GET /api/performance-state/v2-slice18-20-audit`。production integration 仍 `closed`；Slice14／15、正式排行榜、Pitcher Personal與下一場預測均未改動。下一步應做 Slice21 rolling-origin robustness，再決定是否保留任何 challenger。

### 2026-10-08 Pitcher Performance State v2 Slice 21–22

- 新增 `performance_state_v2_slice21_22_service.py`、`python backend/scripts/build_performance_state.py --slice21-22-only`、`data/derived/performance_state_v2_slice21_22.json`，以及 `GET /api/performance-state/v2-slice21-22-audit`。
- Slice21 使用嚴格 forward folds：2023→2024、2023–2024→2025、2023–2025→2026；每個 SP/RP × target 比較 global、partial pooling、residualized workload 的 AP、Brier、log-loss與非劣勢旗標。2026 fold仍是 fixed diagnostic，不是 untouched test。
- Slice22 的 research-only decision：SP persistent-collapse 的 residualized workload與 RP return-to-baseline 的 partial pooling各有至少2個forward folds同時達到「Brier／log-loss不劣且AP不負」；其他目標沒有足夠跨年一致性，決策為 keep Slice14。所有 retained challenger 仍是研究候選，`formal_model_replaced=false`、production gate `CLOSED`、2027 prospective仍必須驗證。
- Slice21／22 targeted tests、API schema smoke、tracker與UTF-8檢查需保持通過；下一步不是直接接頁面，而是等待2027資料並在 prospective shadow 中比較候選與Slice14。

### 2026-10-08 Strict 2026 replay lock

- 新增 `performance_state_v2_strict_replay_service.py`、`python backend/scripts/build_performance_state.py --strict-2026-replay-only`、`data/derived/performance_state_v2_strict_2026_replay.json`、`performance_state_v2_strict_2026_replay_predictions.parquet`，以及 `GET /api/performance-state/v2-strict-2026-replay`。
- Strict protocol 固定為 2023–2024 train、2025 calibration、2026 test-like replay；role-target layer map 直接在 service source 中鎖定，Platt calibration 與 2025 negative 90th-percentile alert threshold 也固定。程式先完成所有 2023–2025 fit／calibration與model fingerprint，再載入2026 state files只做一次 scoring。
- fingerprint：`bd7b04755f1d4de5608814b2c225feabf24d0fe65e547d99b2f8ce8830716a19`；依 Slice14 相同 target eligibility 產生 81,092 筆 2026 predictions。Artifact status 為 `retrospective_holdout_replay`、integration gate `CLOSED`。
- 重要限制：本專案過去已檢視2026，因此這不是 untouched test；它是防止再用2026調參的 pre-registered replay。上游 Plus／state artifact仍是 retrospective inputs，真正 untouched prospective validation仍是2027。

### 2026-10-08 Performance State Lab model synchronization

- `/lab/performance-state` 已新增研究版 `GET /api/performance-state/v2-lab`。2026 Lab board 現在以 Slice14 的 role-target-specific probabilities 作 Primary，並同列 Slice18 partial-pooling 與 Slice19 workload-bias challenger 的 latest／season-mean shadow delta；Slice20 subgroup calibration、Slice22 freeze decision 與 strict replay status 也會隨 payload 提供。
- 正式 `/leaderboards`、Pitcher Personal 與 production model contract 未改動；既有 `/api/performance-state/player` 逐場 timeline 暫保留為明確標示的 v1 fallback，等 point-in-time v2 player artifact 另行定義後才接入。
- 2026 是 retrospective diagnostic，不是 untouched prospective evidence；v2-lab 不在 HTTP request 內訓練模型。非2026年份若研究版 artifact不適用，前端會回退到原 v1 Lab endpoint。
- 新增 `performance_state_v2_lab_service.py`、schema、route、frontend type/API method、Lab synchronization panel 與 focused test。驗證：v2-lab tests 2 passed、Slice14/strict replay tests 6 passed、backend compileall、UTF-8 check、Nuxt typecheck 均通過。正式排行榜仍使用既有 Stuff+／Location+／Pitching+ contracts。

### 2026-10-08 Plus v2 re-cleaning roadmap

- 現行正式 Stuff+ `pete_stuff_outcome_probability_v3_312_contexts` 與 Location+ `location_plus_independent_v1` 保持不變；這次只開新的 Plus v2 research track，不直接覆蓋 leaderboard、個人頁或既有快取。
- 新增 tracker 的 Plus Leaderboards Slice 7–11：Slice 7 先重做 position-player pitching、low-volume emergency、opener／bulk、pitch taxonomy、tracking-field missingness 與 pre/post-Trackman comparability audit；Slice 8 做 Stuff+ true-support scale、稀有球種 family fallback 與 point-in-time fastball reference challenger；Slice 9 做 Location+ canonical pitch taxonomy 與 execution/context challenger；Slice 10 做 calibration、shrinkage prior、角色／球種／tracking era subgroup validation；Slice 11 才做全歷史回填與 release gate。
- 已知 2026 稽核：position-player pitching 為142場、56位球員、約占登板0.68%；對應逐球約2,167／716,544（0.30%）。Performance State 已排除，但目前 Plus 原始訓練 loader 尚未套用同一排除規則，因此 Slice 7 必須先量化其對全體、尾端分數與稀有球種 scale 的影響。
- 若日後接中職，Trackman 前後不可假設 Slider／Sweeper 可同尺度比較；pre-Trackman 應停在 Breaking／family-level，Trackman 後才開 exact-pitch 分數，並另做 era calibration。這是中職資料契約，不能直接套用 MLB 的 Statcast contract。
- Slice 7–9 已開始並產生可重跑研究產物：`data/derived/plus_v2_slice7.json`（清理與 taxonomy audit）、`plus_v2_slice8.json`（清理後 Stuff+ scale/recenter diagnostic）、`plus_v2_slice9.json`（Location+ canonical taxonomy／execution aggregate diagnostic）。三者都標記 research-only，沒有覆蓋正式模型、leaderboard 或 pitch cache。
- Slice 7 的六年稽核顯示 position-player pitching 逐球占比約 0.19%–1.36%（2021 年較高），Slider 與 Sweeper 皆映射到 SL；未映射列保留在 artifact 供後續決策，沒有默默歸零。2022 的 per-pitch Stuff+ cache 目前缺席，Slice 8 會顯示為資料覆蓋缺口，不會假裝完成。
- Slice 8/9 的正式 research challenger refit 已完成：Slice 8 產生 `data/models/stuff_plus_v2_research/pete_stuff_v2_point_in_time_pipeline.joblib` 與 metadata；Slice 9 產生 `data/models/location_plus_v2_research/location_plus_v2_canonical_pipeline.joblib` 與 metadata。兩者都是獨立 research artifacts，尚未接入排行榜或個人頁。
- Slice 8 challenger 使用清理後資料與 pitcher-season 內嚴格 prior 的 FF/SI/FC expanding reference；2026 test：log-loss 1.2817、Brier 0.5736、calibration error 0.0237、run-value correlation 0.1538、grouped correlation 0.1561。相較正式 v3 的 log-loss 1.2639、Brier 0.5677、run-value correlation 0.1578、grouped correlation 0.1941，尚未具備升版證據；calibration error 則略改善。
- Slice 9 challenger 使用 canonical pitch categories（Slider/Sweeper→SL，SV/CS/Slurve→BR，KN/EP→OS）並保留 count、handedness、base/out context；2026 test：log-loss 1.2792、Brier 0.5759、calibration error 0.0214、run-value correlation 0.1476，與正式 v1（1.2774／0.5750／0.0222／0.1481）接近但未全面勝出。下一步是 Slice 10 calibration、subgroup residual 與 release gate，不是直接替換 production。
- Slice 10 已完成：`data/derived/plus_v2_slice10.json` 對 2026 做固定 seed 的 2% paired test audit（baseline 與 challenger 逐球 key 對齊）。門檻為 log-loss delta ≤ +0.01、Brier delta ≤ +0.005、calibration-error delta ≤ +0.005、supported subgroup calibration delta ≤ +0.02，且不得有 material subgroup regression。
- Slice 10 結果：Location+ v2 通過所有 gate，決策為 `eligible_for_shadow`；Stuff+ v2 的 log-loss、Brier 與 subgroup calibration regression 未通過，決策為 `research_only`。整體決策仍為 `research_only`，所以正式合約完全不變；下一步是 Slice 11 的 shadow／歷史回填與 prospective release gate。
- 另做 Slice 8b Stuff+ v5 prior-carryover revision：`data/derived/plus_v2_slice8b.json` 與 `data/models/stuff_plus_v2_research_v5/`。它在每一季第一段投球使用前一季 pitcher fastball prior，並把訓練抽樣提高至 35%；2026 test 為 log-loss 1.2776、Brier 0.5731、calibration error 0.0268、run-value correlation 0.1529、grouped correlation 0.1684。v5 明顯優於 v4，但仍未勝過正式 v3（1.2639／0.5677／0.0245／0.1578／0.1941），所以維持 research-only。
- 目前稽核特別要注意：2026 arm-angle 原始覆蓋約 73.6%，其餘年份約 96.5%–99.5%；2021 per-pitch Stuff+ cache 僅覆蓋約 36.9%，2022 cache 尚無資料，而 2023–2026 約 99.3%（以清理後 raw pitch rows 為分母）。這些是研究版的明確缺口，不應被模型補值或誤報成完整覆蓋。

### 2026-10-07 Development server recovery

- 3000與8000曾同時監聽但完全不回應。根因是實際網站使用的`backend\.venv`缺少已列入`pyproject.toml`的`hmmlearn==0.3.3`與`arch==8.0.0`；Uvicorn reload載入Performance State route失敗，Nuxt SSR連帶等待8000。
- 兩個套件已安裝到正確的backend venv並只重啟佔用3000／8000的開發程序。恢復後`/api/health`、`/`、`/leaderboards`與`/lab/performance-state`均回200；開發日誌在`data/admin_job_logs/dev_backend_*.log`及`dev_frontend_*.log`。

### 2026-10-04 Pitcher Personal lazy loading

- `/pitcher-personal`初始載入已由8支API全頁並行改為只取Overview；Stuff、Sequence、Rotation、Outing Report與Discipline在第一次開啟分頁時才取資料，同一球員／年份再次切回會沿用已載結果，5分鐘auto-refresh只更新Overview與當下分頁。Stamina原本就是分頁懶載入，契約未改。
- Stuff分頁第一次開啟時才並行取得1000球sample、Movement與Stuff Score；Overview在Stuff Score尚未載入時保留overview來源的既有Stuff+，不再用null覆蓋。
- 預設Rotation場次與Outing場次的程式化選取不再觸發第二次相同請求；Outing loader只明確載入一次report，使用者之後自行換場仍照常更新。
- 效能診斷基準為2026 Dylan Cease：舊初始8支並行流程約36.3秒／18.93 MiB，其中Discipline 36.2秒、Movement 29.1秒、Sequence 26.6秒；新初始關鍵路徑只剩Overview，直接service基準約1.6秒。未做瀏覽器計時，因Computer Use目前沒有browser surface。
- 驗證：UTF-8與Nuxt typecheck通過；未更動任何後端資料、模型契約或API response schema。

### 2026-10-04 Pitcher Metric Explorer Slice 1

- 新增Pitcher Lab的`/lab/pitcher-metrics`球季層級研究頁與`GET /api/pitchers/metric-explorer?year=...`。一列固定是一位投手的一個球季，不混入單場、逐球或20球window資料。
- 2026真實payload有868位投手、35個固定指標鍵，分類為Results & workload、Standard advanced、Petehub Plus、Stamina & stability；basic／advanced／Plus／Stamina來源狀態分開揭露，缺值保持null、不補0。
- UI支援年份、SP／RP、球隊、最低IP、姓名篩選，分類X/Y軸選單、完整案例散點圖，以及與打者Stuff Attack一致的手動回歸入口；結果包含Pearson r、Spearman rho、OLS R²／斜率／p-value、雙尾顯著性判讀、回歸線與多重嘗試警語。散點頭像已放大並加入hover/focus強調；下方欄位表會隨X/Y分類同步更新，不同分類並排兩表、同分類合併一表，選中欄位高亮，表格數字使用14px。
- 2026覆蓋例：ERA 868、FIP 377、Stuff+ 863、正式Stamina+與Physical Stability+各149位。Stamina只在正式可發布年份接入；其他年份保持unavailable。
- 驗證：Pitcher Metric Explorer、Stuff leaderboard、Stamina targeted tests共23 passed；真實response schema smoke、UTF-8與Nuxt typecheck通過。動態分類表與頭像尺寸調整後再次通過UTF-8及Nuxt typecheck。未做瀏覽器視覺QA，因目前Computer Use沒有可用瀏覽器surface。
- 下一步Slice 2應另建pitcher-game explorer，才可比較Game Score、WPA、用球數與同場Quality／Physical／Command；不可把單場列直接混入現有球季回歸。

### 2026-10-03 Stamina Slice 15–16

- Slice 15完成`stamina_physical_signal_contract_v1`。2023–2026每顆第21–100球都和同場前20球、相同精確球種至少3球的基準比較；Velocity與Extension／Arm Angle用絕對偏移，Movement與Release Point用二維向量距離，Spin用轉速與圓形轉軸組成的spin-vector距離。缺值保持null。
- Slice 16完成研究版`physical_stability_challenger_v1`／`stamina_physical_stability_v1`。六分項固定權重為Velocity 25%、Spin 15%、Movement 20%、Release Point 20%、Extension 10%、Arm Angle 10%；2023 robust reference固定套用2024–2026，沒有使用Stuff+作訓練target。
- 缺少component時不重新正規化，也不補0；缺少的固定權重以聯盟中性貢獻保留並降低reliability。輸出20球window與game score、六分項Plus、80% interval與high/medium/low confidence。現行Observed Stamina+ v1.1與排行榜完全未改。
- 四年supported-late coverage為2023 80.7%、2024 79.5%、2025 78.0%、2026 76.6%；2026 Arm Angle在exact-type support後為56.8%，明顯反映既知date-batch missingness。
- 2026有17,167個window、4,749場有raw state，4,572場合格／303位SP；median reliability 0.905、median 80% width 7.754、21–40對61–80 split rho 0.553、velocity-only對Physical rho 0.564。P05／P50／P95為84.5／101.2／113.2。
- 2026同場Physical Stability+和Observed Game Stamina+的Spearman約-0.005（4,537場），顯示兩者幾乎正交：前者是追蹤物理穩定，後者是球質維持，現階段支持分開呈現而非直接合成。
- Dylan Cease合格29場平均Physical 91.5（Velocity 94.5、Spin 77.1、Movement 105.2、Release 87.6），但正式Overall Stamina+ 106.1；Shane Baz為Physical 101.9／Stamina 106.1；Kyle Leahy為Physical 99.1／Stamina 93.5。這三例清楚呈現補償、同步穩定與「機制穩定但球質未維持」三種型態。
- 新artifacts：`stamina_physical_contract_2026.json`、`stamina_physical_windows_<2023..2026>.parquet`、`stamina_physical_games_<2023..2026>.parquet`。新API `GET /api/stamina/physical-stability?year=2026&pitcher_id=...`，重建參數`--physical-stability-only`；Stamina Lab已加入四年audit、分項契約與球員／單場explorer。
- 驗證：Stamina tests 14 passed、真實overview/detail Pydantic schemas通過、UTF-8與Nuxt typecheck通過。下一步是Slice 17 Command Retention+；Slice 18前不得將Physical與Quality合成正式分數或做健康／傷病宣稱。

### 2026-10-03 Stamina Slice 17–18

- Slice 17完成`stamina_command_retention_contract_v1`／`command_retention_challenger_v1`。對同場前20球、同精確球種至少3球的Location+做shrinkage baseline，再用2023凍結的early-Location、pitch-count spline與pitch type Ridge估計後段合理期望；實際減期望才是Command residual。
- 第一輪的早段斜率曾被錯誤固定為1，導致early Location與分數rho約-0.54；已改成由2023模型學習回歸平均後重跑。正式2026結果early-Location rho為-0.008，不可回退到舊做法。
- 輸出21–40、41–60、61–80、81–100球window，Overall固定使用前20球family mix，不因後段改變配球而重新加權；缺少family不重正規化，而是降低fixed-mix coverage。最低window 5球、game 15球、Overall mix coverage 80%。
- 2026有4,392場合格Overall／303位SP；pitch model RMSE 10.179，naive early baseline 10.363，改善1.77%；21–40對61–80 split rho 0.085，median reliability 0.458，median 80% interval width 14.469，P05／P50／P95為90.9／98.7／105.3。這是單場command狀態，重複性偏弱，不是穩定trait。
- Slice 18凍結2025訓練→2026檢驗，用21–40球early Quality預測同場61–80球Quality retention；baseline只用early Quality，velocity comparator加velocity，challenger加Physical Stability+與Command Retention+。
- 2026配對4,206場、coverage 96.03%；challenger RMSE 3.6395，baseline 3.6387，velocity comparator 3.6347。增量改善為-0.022%，相對velocity為-0.132%，兩個增量門檻皆失敗；calibration slope 0.9568通過，三項訊號最大pairwise |rho|僅0.041，顯示它們不重複，但「不重複」不等於「能提升後段Quality預測」。
- `composite_release_eligible=false`；Slice 19應以三項分開的產品整合與代表性球員個案檢查為主，不得為了產出Composite而降低門檻。未來有新年份時才能做更強的untouched-season確認。
- Artifacts：`stamina_command_contract_2026.json`、`stamina_command_windows_<2023..2026>.parquet`、`stamina_command_games_<2023..2026>.parquet`、`stamina_incremental_validation_2026.json`。API：`/api/stamina/command-retention`、`/api/stamina/incremental-validation`；CLI：`--command-validation-only`。Stamina Lab已加入四年audit、單場explorer與Slice 18 gates。
- 驗證：Stamina tests 15 passed、overview與Dylan Cease detail Pydantic smoke通過、UTF-8 check與Nuxt typecheck通過。

### 2026-10-03 Stamina Slice 19

- 完成`stamina_product_integration_v1`，決策固定為`keep_separate`，`composite_release_eligible=false`。現行Quality、Physical、Command不平均、不重新加權、不產生綜合排行。
- Pitcher Personal的Stamina分頁已改為三張同場對齊的small multiples：Quality Stamina+、Physical Stability+、Command Retention+。三圖共用場次x軸與70–130 Plus刻度，點選任一圖的場次後，其餘圖、80% interval、reliability與對齊表格同步切換。圖點支援滑鼠、Enter與Space。
- 個人頁並行取得三份現有API；任一份失敗時不會清空其餘兩項，缺值維持unavailable。Leaderboard的inline expansion也已同步為三圖compact模式，只有使用者展開該投手時才並行請求Quality／Physical／Command，不會在排行榜初次載入時發出數百個request。排名與現行排行榜契約沒有改變。
- Leaderboard正式`Stamina+`右側已加入`Q-Stm+`、`Phy-Stb+`、`Cmd-Ret+`：分別是合格單場Quality、Physical、Command分數的球季平均，各自至少需10場，不足維持null，不影響正式排名。真實2026前三名例：Sean Burke 107.2／107.7／92.4／98.9，Carlos Rodón 106.3／107.8／95.9／94.8，Dylan Cease 106.1／109.3／91.5／97.0（順序為正式Stamina／Q／Physical／Command）。
- `/leaderboards`所有頁籤的DataTable字體統一由12px提高到14px，table title／row count也各提高2px。頁首新增原生`details`「欄位說明」，會依Basic／Stuff+／Location+／Pitching+／Stamina+頁籤顯示繁體中文自定義指標定義與缺值規則。中文以UTF-8寫入，並已經`check_utf8.py`驗證；Windows單次smoke列印需設`PYTHONIOENCODING=utf-8`，避免CP950無法列印Rodón等字元，這不是artifact或API JSON的編碼錯誤。
- 2026有180位投手在三項都至少有10場。固定個案Cease／Baz／Leahy外，由資料自動選出Sean Burke（Quality明顯高於Physical）、Carlos Rodón（Quality高於Command）、Zack Littell（Physical高但Quality低）、Bryan Woo（相對均衡）。Stamina Lab已顯示這些代表個案與產品規則。
- Artifact：`stamina_product_integration_2026.json`；重建參數：`--product-integration-only`。驗證：Stamina tests 16 passed、Slice 19 overview Pydantic smoke通過、UTF-8與Nuxt typecheck通過。瀏覽器視覺QA因當前Computer Use沒有可用Chrome／Edge／內建瀏覽器而未能執行，不可誤寫成已目視驗收。
- Stamina Slice 0–19至此完成。只有新的untouched season可重開Composite驗證；其他後續應轉入獨立的Player Health & Availability資料來源稽核，不得將三項差異直接稱為傷病警報。

- 使用者已要求規劃下一階段的Physical／Mechanics Stability與球員健康管理研究。現行Observed Stamina+ v1.1及2026排行榜契約保持凍結，不得由新特徵原地覆寫。
- Stamina新增規劃Slice 15–19：先凍結物理訊號與缺值契約，再建立不以Stuff+為訓練目標的20球／單場Physical Stability+，另建Command Retention+，最後檢驗是否提供現行Quality Stamina+以外的增量資訊；未通過前只分開顯示，不發布綜合總分。
- 新增`Player Health & Availability Research` Slice 0–6。定位是非醫療的workload／availability／mechanics-change monitor；官方IL事件只作事件標籤，任何模型輸出不得稱為診斷、受傷原因或因果預測。
- 現有歷史球隊段可由2021–2026年度DuckDB的`player_team_stints`與逐球`pitcher_team`／`batter_team`重建；本機正式transactions／injury快取目前只有2026-08-01至2026-09-29的60日窗，2,800列，其中依description辨識約275列IL placement、194列IL activation、191列trade/acquired。開始健康模型前必須先做歷史事件來源稽核與不可覆寫的年度回填。

- Stamina目前主線已收斂為兩項：衡量每位先發投手單場內的球質維持狀態，以及把各場Overall／Fastball／Breaking／Offspeed Game Stamina+串成整季時間線。這是觀測狀態，不預測下一場，也不宣稱永久體能trait。
- 舊3×3分群與cold-start未來場次預測已從API、Lab、tracker與重建入口移除；不得重新接回主線。現行模型版本為`stamina_observed_game_state_v1_1`。
- Slice 7已將FF／FA／SI／FC歸Fastball，SL／ST／CU／KC／SV歸Breaking，CH／FS／FO歸Offspeed；FO明確屬於Offspeed。2026 SP分類覆蓋99.8%、分類後Stuff+覆蓋100%，未分類主要為CS 121球、KN 94球、PO 23球、UN 4球、EP 1球，維持unclassified，不猜測歸類。
- 234位SP的v1偏誤稽核顯示Stamina+與平均Stuff+ Spearman -0.353、平均球速 -0.280、early Stuff+ -0.446、early球速 -0.360；early Stuff+與naive late−early為-0.514。Q1至Q4 early Stuff+組的naive delta約0.00、-0.81、-1.07、-2.83，確認單純差值有明顯天花板／回歸平均風險。
- Bryan Woo兩季trait 89.3，但2025為81.9、2026為98.8；Jacob Misiorowski兩季80.6、2026為79.8。描述性family拆分顯示Woo主要是Fastball後段回落、Breaking大致穩定；Misiorowski的Fastball與Breaking均下降，但後段絕對球質仍高。這些尚未情境校正，不是v2正式結果。
- Slice 8已建立403,566列逐球family曲線與83,714列逐場family／Overall曲線；101+ Overall正確只保留438場／141位投手。Fastball的context-adjusted聯盟曲線由1–20球105.428降至61–80球103.340；Breaking與Offspeed後段上升仍可能含配球選擇，不可解讀成體力回升。
- Slice 9的2026 chronological 70/30 development test中，ANCOVA／spline mixed-effects approximation／可解釋ML相對early-quality baseline的RMSE improvement為+3.56%／+3.99%／+4.02%。ML優勢只有0.03pp，不能據此選黑箱；正式決策留給Slice 10跨季holdout。
- Slice 10已完成leakage-safe 2025→2026 holdout：2025有300,929個late pitches作train，2026有291,149球作test。三個逐球模型都通過RMSE、calibration與ceiling-neutrality gates；依0.25pp簡約規則選擇spline mixed-effects approximation，而不是RMSE僅多0.15pp的ML。
- 舊Slice 10的v2 trait候選scope全部未通過，仍維持`research_only`且candidate rows為0；這條路線沒有被重新發布。正式排行榜改用後續Observed Game／Season契約與Slice 13A校正，兩者不可混稱。
- 單場與整季時間線接Stamina Lab；Slice 14另將通過門檻的2026 adjusted observed-season summary接到`/leaderboards`。兩者都不得寫成下一場預測。

### 2026-10-01 Stamina v2 Slice 11

- Slice 11已完成，模型版本`stamina_research_slice11_v1`、契約`stamina_v2_slice11_multisignal_v1`。沒有改寫Slice 8–10 artifact；另建`stamina_v2_multisignal_2026.parquet`，共67,383列appearance×family×reached-window、377位SP、4,857場。
- 每個物理訊號都以同場前20球、相同精確球種至少3球為基準；缺少支持維持null。診斷分開保留context-adjusted Stuff+、球速、轉速、位移中心漂移、出手點漂移、延伸距離、Location+與family usage，不合成個人分數。
- 61–80球相對早段：Fastball Stuff+ -2.126、球速 -0.508 mph、使用率 -6.944pp；Breaking Stuff+ +1.015、球速 -0.392 mph、使用率 +3.611pp；Offspeed Stuff+ +1.746、球速 -0.493 mph、使用率 +3.333pp。三家族都掉速而Stuff+方向不同，支持「球種形狀／選擇補償」診斷，不支持把Stuff+單一斜率直接稱為體能。
- Fastball–Offspeed速度差在1–20至61–80球約7.151→7.206 mph，配對變化僅+0.002 mph；81–100為+0.060 mph。兩者大致同步掉速，沒有明顯證據顯示中段速度差崩解。101+只有149場雙family支持，結果不可外推。
- Fastball／Breaking／Offspeed的三球早段基準覆蓋約99.2%／74.2%／55.5%；Breaking與Offspeed缺值不得補0。位移與出手點drift是離開早段中心的距離，只表示改變幅度，不自動等於惡化或疲勞。
- 新API `GET /api/stamina/research-curves?year=2026&pitcher_id=...`供球員／場次selector；Stamina Lab顯示聯盟多訊號、coverage、跨family速度差和單場曲線，全部明確標成research-only，沒有排行榜、candidate rows或下游接線。
- Slice 11可獨立重建，不必重跑舊Slices：`python backend/scripts/build_stamina_lab.py --year 2026 --slice11-only`。
- 驗證：Pydantic overview/detail schema可解析；`test_stamina_lab_service.py` 9 passed；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-02 Observed Game Stamina+ v1.1

- 現行契約`stamina_observed_game_state_v1_1`只回答兩件事：一場比賽中球質如何隨球數維持，以及同一投手整季各場狀態如何變化。它不是下一場預測，也不是永久trait。
- 2025前20球精確球種基準依球數做empirical-Bayes收縮，再由精確球種×球數Spline、early Location+、early velocity及其球種關係估計第21–100球合理Stuff+；2026實際減預期為Retention。只要有1顆前段同球種即可進入收縮估計，低樣本會更靠近2025同球種先驗。
- Overall固定使用該場前20球family比例，至少15顆合格後段球且固定mix coverage需達80%；未觀測family保留原權重、使用聯盟family retention prior並增加不確定性，不重新正規化。Family至少5顆才給分。
- 單場誤差使用100次inning-cluster bootstrap並設analytic variance下限，再empirical-Bayes部分池化。Game Stamina+固定100為聯盟平均，每1個state SD為10分，輸出80% interval與high／medium／low confidence。
- 2026共4,563場／302位SP有Overall分數，涵蓋93.9%先發；Fastball／Breaking／Offspeed分別4,671／4,240／3,232場合格。相較v1，Breaking增加964場、Offspeed增加1,161場。
- v1.1預期曲線RMSE 9.597，較v1的10.115降低5.12%；相對更強的shrunken early-quality baseline 9.769仍改善+1.76%。Overall retention對early Stuff+／early velocity Spearman為0.070／0.097，均在|0.10|內；同場21–40與61–80 retention為0.423，高於v1的0.403。
- Overall median reliability 0.834、median 80% interval width 10.4分；分數第5／50／95百分位約85.9／99.6／114.2。這是堪用的描述性單場量尺，但不是精密生理測量。
- 新API `GET /api/stamina/game-states?year=2026&pitcher_id=...`回傳每場Overall與三family分數、80% interval、reliability、3／5場趨勢與各20球區間Retention。Lab加入整季折線、逐場表與選定場次分段解釋。
- 舊3×3分群與cold-start未來場次預測已從API、Lab、tracker和CLI移除。獨立重建使用`python backend/scripts/build_stamina_lab.py --year 2026 --game-state-only`。
- 驗證：真實overview與球員detail Pydantic schema通過；Stamina tests 9 passed；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-02 Stamina Slice 12 與單年度歷史回填

- Slice 12已完成，契約`stamina_observed_season_state_v1`、狀態`research_only`。它將單場Game Stamina+按reliability加權，合併單場測量誤差與場間波動，再作scope層級empirical-Bayes部分池化；仍只描述該球季已發生的狀態，不是永久trait或下一場預測。
- Overall排名資格為至少10場合格先發、150顆supported late pitches、平均game reliability至少0.70；Fastball／Breaking／Offspeed為至少8場、50球與相同reliability門檻。不合格列保留但`rank=null`。
- 2026產生`stamina_season_summaries_2026.parquet`共1,207列；Overall／Fastball／Breaking／Offspeed合格投手164／174／178／143位，median season reliability為0.895／0.893／0.933／0.917，median 80% interval width為3.5／3.5／3.5／3.8分。
- Reliability加權與普通單場平均的排名Spearman為0.998–0.999，顯示權重選擇沒有造成大幅名次翻轉。新API為`GET /api/stamina/season-summaries?year=2026`，獨立重建指令為`python backend/scripts/build_stamina_lab.py --year 2026 --season-summary-only`。
- Slice 13等待2024 backfill完成後，固定同一契約執行2024→2025外部驗證；通過後Slice 14才把Stamina+加入`/leaderboards`，不得提前把research-only球季排名當正式能力榜。
- Per aspera ad astra歷史Plus區已改為2021–2025各年份各自可點擊的按鈕；`POST /api/admin/jobs/backfill-historical-plus?year=<year>`只執行所選年度，前端不再送年份範圍。既有progress JSON與resume行為保留。
- 2024首次Stamina其實已成功寫出artifact，但child最後用Windows CP950輸出含`≤`的JSON時失敗，導致工作狀態誤記為failed。Admin child現在同時以`PYTHONIOENCODING=utf-8`與Python stream reconfigure固定UTF-8；resume也會跳過`completed`／`current`階段，只補失敗階段。
- 2024已安全續跑完成：Location+、per-pitch Stuff+、Pitching+、Plus leaderboard與Stamina均完成；Stamina為711,898列、855位投手，overview schema通過，沒有殘留2024 worker。
- 驗證：Stamina與Admin targeted tests 19 passed；真實Slice 12 artifact與2024／2026 schemas通過；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-02 Stamina Slice 13 外部驗證

- 2024回填完成後，以凍結的Game v1.1與Season v1契約重建2025。2025共有4,693場合格Overall、96.6%先發覆蓋，RMSE improvement +1.42%，early Stuff／velocity rho 0.049／0.080，場內21–40對61–80一致性0.426；單場層級全部通過。
- 2025 Season summary共1,240列；Overall／Fastball／Breaking／Offspeed合格投手170／180／189／134位，median reliability 0.911／0.924／0.947／0.923，weighted-vs-unweighted rank rho 0.998–0.999。
- Slice 13契約`stamina_observed_external_validation_v1`共9個release gates。Frozen contracts、coverage、RMSE gain、game ceiling-neutrality、within-game consistency、season support、precision與weighting sensitivity共8項通過。
- 唯一失敗為season leaderboard ceiling-neutrality：門檻為early Stuff+／velocity的max |Spearman|≤0.20；2025 Season Stamina+相關為0.314／0.167，2026為0.416／0.263，因此最大值0.416，`leaderboard_release_eligible=false`、維持`research_only`。
- 2025與2026共同合格投手112位，跨季Season Stamina+ rho 0.591；這只作描述，不是gate，因為目標是season state而非永久trait。分數與eligible games相關僅0.070／0.075，但與平均用球數為0.288／0.198，深度仍必須分欄呈現。
- 新artifact `stamina_external_validation_2026.json`、API `GET /api/stamina/external-validation?year=2026`、重建指令`python backend/scripts/build_stamina_lab.py --year 2026 --external-validation-only`。Slice 14排行榜不得發布；下一步Slice 13A只能用2024開發season-level ceiling修正，再鎖定套用2025／2026，且不得破壞其他8個已通過gate。
- 驗證：Stamina與Admin targeted tests 20 passed；真實2025／2026 external-validation與overview schema通過；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-02 Stamina Slice 13A season ceiling-bias repair

- 依使用者選擇不回填2023。Correction只用2025開發，2026維持唯一untouched external season；契約`stamina_observed_season_bias_repair_v1`。Overall／Fastball／Breaking／Offspeed各自使用early Stuff+與early velocity的3-knot degree-2 spline＋Ridge alpha 10，沒有使用2026選模或調參。
- 原始Slice 12 artifact完全保留；修正版另存`stamina_adjusted_season_summaries_2025.parquet`與`stamina_adjusted_season_summaries_2026.parquet`。100次development-pitcher bootstrap的prediction variance已加入80% interval，沒有把修正當成無誤差常數。
- 正式adjusted rank除原Slice 12資格外，再要求個別adjusted reliability≥0.70，避免高不確定性球員占據榜首。Untouched 2026各scope仍有Overall／Fastball／Breaking／Offspeed 140／145／163／122位合格投手。
- 在上述正式排名樣本中，Overall early Stuff／velocity rho由0.421／0.236降至0.181／0.105；Fastball為0.137／0.177、Breaking -0.023／0.077、Offspeed 0.045／-0.087，全部通過|rho|≤0.20。
- 其他gate也通過：最低median adjusted reliability 0.811、最大median 80% interval width 4.067、最低weighted-vs-unweighted rank rho 0.985；最低spread retention為Breaking 0.590，高於0.50，表示修正沒有把排行榜壓平成100。
- 正式決策：`leaderboard_release_eligible=true`、`publication_status=validated_observed_state`。這只允許發布清楚標示的observed-season leaderboard，不代表生理體能或next-start prediction；且correction v1目前只有2026一個untouched external season。
- 新API `GET /api/stamina/season-bias-repair?year=2026`、audit `stamina_season_bias_repair_2026.json`；重建指令`python backend/scripts/build_stamina_lab.py --year 2026 --season-bias-repair-only`。下一步Slice 14可接`/leaderboards`，但必須讀adjusted artifact並保留資格、CI、reliability與深度欄位。
- 驗證：Stamina與Admin targeted tests 21 passed；真實bias-repair與overview schema通過；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-02 Stamina Slice 14 leaderboard

- `/leaderboards`已加入Starter-only `Stamina+`頁籤，年份固定為2026；切入時角色固定SP。這不是RP缺資料的暗示，而是現行observed-season契約只對先發投手完成驗證。
- 新API `GET /api/stamina/leaderboard?year=2026`只讀`stamina_adjusted_season_summaries_2026.parquet`與通過的bias-repair audit；若年度不是audit的untouched test year或release gate失敗，服務會拒絕發布。
- 正式總榜只含`adjusted_qualified=true`的Overall列；Slice 14A後共149位。維持artifact內正式rank，不因前端隊伍、姓名或最低局數篩選而重排。
- 表格共14欄：rank、姓名、球隊、先發數、合格Stamina場數、局數、平均用球數、Fastball／Breaking／Offspeed Stamina+、80% interval上下界、adjusted reliability與Overall Stamina+。Family未通過自己的support／reliability門檻時顯示空白，不補0或借用Overall資格。
- 標示`validated_observed_state`與契約`stamina_observed_season_leaderboard_v1_1`，並明示2026是correction v1.1唯一untouched external season；排行榜描述該季球質維持狀態，不是生理體能、永久能力或下一場預測。
- 驗證：Slice 14A後真實artifact回傳149列且schema通過；Stamina service tests 13 passed；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-02 Stamina Slice 14A qualification repair

- Season／family上榜規則已由「平均單場reliability≥0.70」改成「整季reliability≥0.70」，最低支持仍為Overall 10場／150顆supported late pitches，family 8場／50球。平均單場reliability保留作診斷，不再一票否決大量場次已能提供精確整季估計的投手。
- 新契約為season state／external validation／bias repair／leaderboard各自的`v1_1`。校正模型仍只用2025 fit，2026仍是唯一untouched test，沒有為個別2026投手調參。
- 2026校正後正式人數更新為Overall／Fastball／Breaking／Offspeed 149／158／171／132。Dylan Cease Fastball有29場、932顆supported late pitches、整季reliability 0.866、adjusted reliability 0.823，現以107.4排名Fastball第1；其平均單場reliability 0.645仍如實保留。
- `/leaderboards`的Stamina頁籤以`Sean Burke`格式顯示姓名；欄位順序在IP後緊接Rel與Stamina+，Rel顯示三位小數。個人逐場圖位於`/lab/stamina`的Observed Game Stamina+／Season timeline，可切Overall與三個family。
- Slice 14B已把共用`StaminaTimeline`加入Pitcher Personal的Stamina分頁；從Stamina排行榜點姓名會直接開該分頁。排行榜其餘列區域可點擊或用Enter／Space展開同一份逐場圖與表格，再點一次收合；一次只展開一位，姓名連結不觸發展開。共用`DataTable`只新增opt-in expandable props／slot，其他表格預設行為不變。
- 新規則仍通過全部release gates：最大2026 ceiling |rho| 0.114、最低median adjusted reliability 0.814、最大median 80% interval width 4.052、最低scope support 132、最低weighting rho 0.983、最低spread retention 0.615。
- 驗證：2025／2026 Season Summary、external validation及bias repair已重建；Stamina tests 13 passed；UTF-8與Nuxt typecheck通過。

### 2026-09-30 Stamina v2 Slice 7

- Slice 7已完成，模型版本為`stamina_research_slice7_v1`，契約版本為`stamina_v2_slice7_preregistered_v1`；既有Slice 0–6演算法、v1 Stamina+分數與Pitcher Personal逐球state均未改寫。
- 2026 Stamina parquet的716,544球已加入`pitch_family`；Slice 7研究範圍固定為SP。三個family的球數／投手為Fastball 221,856／377、Breaking 117,182／374、Offspeed 64,528／335。
- Early→late usage為Fastball 59.6%→53.5%（-6.1pp）、Breaking 26.7%→29.8%（+3.1pp）、Offspeed 13.7%→16.7%（+3.0pp）；這只是pitch-selection診斷，v2 overall權重不得使用後段實際usage。
- v2 primary target已預先註冊為「late context-adjusted Stuff+ conditional on early quality」，必須先在精確球種內校正再聚合family；overall使用前一季repertoire，無前季時才用當場前20球權重。缺少family支持維持null，不補0。
- Release gates已鎖定：來源覆蓋、2025→2026共同SP樣本、rank與RMSE improvement、calibration、early Stuff+／球速殘餘相關的ceiling-neutrality，以及每個family的跨季支持與覆蓋。Slice 10通過前不得發布v2分數或接下游。
- 驗證：2026 artifact完整重建、Pydantic response schema可解析；`test_stamina_lab_service.py` 8 passed；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-09-30 Stamina v2 Slice 8–9

- Slice 8已完成，模型契約為`stamina_v2_slice8_curves_v1`。403,566列SP classified pitches先在精確球種內校正count、投打左右、TTO、局數、park與calendar trend，再產生family trailing MA5與20球區間曲線；context within-pitch-type R²為0.0703。
- 新runtime artifacts：`stamina_v2_pitch_curves_2026.parquet` 403,566列、`stamina_v2_appearance_curves_2026.parquet` 83,714列。MA5必須同一場、同family累積至第5球才開始；Fastball／Breaking／Offspeed MA5 coverage為91.2%／83.7%／73.8%。
- Overall曲線使用前一季repertoire固定權重；369位投手可使用2025權重，其他登板才使用當場前20球。沒有觀測到固定權重要求的family時保持null，不重新正規化來獎勵後段棄投；101+只保留實際到達的438場／141人。
- Slice 9已完成，契約為`stamina_v2_slice9_challengers_v1`。正式fit使用raw pitch與Slice 2式cross-fitted direct observation weights；MA5完全不進模型。2026切點為2026-08-03，train 204,003球／3,301場、test 87,146球／1,447場。
- Early-quality baseline RMSE 9.785；linear ANCOVA 9.437（+3.56%）、spline＋EB pitcher intercept 9.394（+3.99%）、shallow boosted tree 9.391（+4.02%）。三者差距小，boosted tree只作challenger；early Stuff+的permutation importance遠高於workload，再次證明必須做ceiling-neutral holdout audit。
- 階層式family slope共634列，另存`stamina_v2_hierarchical_2026.parquet`。Fastball 232位合格、league slope -0.648／20球、median reliability 0.807；Breaking 218位、+0.393、0.629；Offspeed 184位、+0.683、0.556。Breaking／Offspeed正值仍可能含time-varying pitch selection，不是因果體力回升或正式分數。
- 驗證：2026完整artifact重建、Pydantic overview schema與三份Parquet列數通過；`test_stamina_lab_service.py` 9 passed；UTF-8與Nuxt typecheck通過。未執行Nuxt build、未清`.nuxt`。

### 2026-10-01 Stamina v2 Slice 10

- Slice 10已完成，模型版本`stamina_research_slice10_v1`、契約`stamina_v2_slice10_holdout_v1`。為避免leakage，context adjustment的球種基準、類別欄位與係數只由2025估計，再固定套用2026；2026不參與fit或調參。
- 逐球holdout三模型全部通過：ANCOVA RMSE 9.659、改善+3.72%、calibration 0.997；spline mixed-effects RMSE 9.635、+3.96%、calibration 0.963；ML RMSE 9.620、+4.11%、calibration 1.015。三者殘餘對early Stuff+／early velocity的|Spearman|皆≤0.048。
- 依預先固定的簡約規則，只要較簡單模型距最佳RMSE improvement不超過0.25pp就優先選簡單者；因此選spline mixed-effects（距ML 0.15pp），ML維持challenger。
- 投手層級Overall與三個family都沒有完整通過release gates。Overall 121位共同投手、ρ=0.667、RMSE improvement +2.96%，但calibration 0.517且residual對early velocity ρ=0.157；Fastball 166位、ρ=0.613但RMSE -5.13%；Breaking 154位、ρ=0.314但RMSE -24.19%；Offspeed 124位、ρ=0.356但RMSE -35.42%。三family calibration slope僅0.468／0.291／0.220。
- 正式決策：`publication_status=research_only`、validated scopes為空、`stamina_v2_candidates_2026.parquet`為0列。這支持跨季逐球曲線建模，但不支持發布個人family／Overall Stamina+ v2；不得降低gate或用rank單獨包裝成正式分數。
- 此段是當時的Slice 10決策紀錄；現行產品已改為Observed Game Stamina+，不再嘗試發布跨場trait或next-start預測。
- 驗證：2025與2026 artifacts完整重建、Pydantic schema可解析、candidate artifact 0列符合gate、Stamina tests 9 passed、UTF-8與Nuxt typecheck通過；未執行Nuxt build、未清`.nuxt`。

---

## 2026-09-29 歷史完成紀錄：Stamina Lab Slice 0 與 Location Lab 字級

- 新增 `/lab/stamina` 與 Pitcher Lab 入口卡；當時定位為研究稽核台，後續 Slice 5 已在通過跨季 gate 後發布 v1 Stamina+。
- `backend/app/services/stamina_lab_service.py` 會從年度 DuckDB 建立 `data/derived/stamina_lab_<year>.parquet` 與同名 JSON audit。2026-09-29 重建結果為 716,544 顆唯一正規賽逐球、20,793 次登板、868 位投手；4,857 次 SP、15,936 次 RP，250 位雙重身分投手按登板角色分開保留，資料截至 2026-09-27。
- Slice 0 已準備登板內／單局球數、休息日、角色內賽季累積球數，並對齊逐球 Stuff+／Location+。Stuff+ 全部 eligible pitch 已完成快取；目前觀測覆蓋 SP 99.8%、RP 99.3%，Location+ 同為 SP 99.8%、RP 99.3%。剩餘缺值是上游缺少球種／追蹤欄位，保留為缺值，不補 0。
- Slice 0 頁面呈現每個清理步驟、SP/RP 樣本、球數區間、特徵覆蓋與 H1–H4 預分析契約；weather/travel 明確標示 missing。Slice 1–6 後續均已完成，本段只保留為資料基線紀錄。
- 新 API：`GET /api/stamina/overview?year=2026`。重建指令：`python backend/scripts/build_stamina_lab.py --year 2026`。
- Location Lab 的 leaderboard、控制項、明細、比較區與提示字級已提高至 Stuff Lab 同級，表格表頭 10px、內容 12px、Plus 14px，並增加列內距。
- 驗證：Stamina／Plus／Location targeted tests 9 passed、Nuxt typecheck 與 UTF-8 check 通過；未執行 Nuxt build、未清 `.nuxt`。

### 2026-09-29 Stamina Slice 1

- Slice 1 已完成聯盟層級 SP／RP 分開的登板內球數與角色內賽季累積用球曲線。模型以投手×球種與打者兩向固定效果控制個體差異，另控制 count、左右對戰、TTO、局數、主場與 calendar trend；95% CI 以 pitcher-game appearance clustered sandwich covariance 計算。
- 頁面可切 Stuff+／Location+，顯示 adjusted Plus-point delta、95% CI、精確樣本數與 raw mean。這仍不是正式 Stamina+；高用球數樣本的 informative removal／survivor bias 明確交由 Slice 2 校正。
- 2026 初步末端區間結果：SP 單場 Stuff+ +0.212（95% CI -0.567–0.991）、Location+ +0.280（-0.279–0.840）；SP 賽季 Stuff+ +0.149（-0.540–0.837）、Location+ -0.250（-0.554–0.054）；RP 單場 Stuff+ -0.063（-0.257–0.130）、Location+ +0.350（0.187–0.512）；RP 賽季 Stuff+ -0.092（-0.661–0.477）、Location+ -0.320（-0.648–0.008）。除 RP 單場 Location+ 外均為 inconclusive，不可宣稱整體疲勞已被證實或否定。
- Arm angle 73.6% 是 date-batch missingness：184 個比賽日中 46 天整日 0%，189,314 顆缺值中 185,974 顆仍具其他完整物理追蹤；不是特定投手沒有測量。重新抽抓 2026-09-24 已恢復 99.7%，代表歷史快取是在上游欄位暫時缺漏時保存。Slice 1 主模型排除 arm angle，頁面加入來源診斷；後續可另做歷史日期批次修復。

### 2026-09-29 Stamina Slice 2

- Slice 2 已完成：每個登板後段都和同場首段固定視窗配對，並以投手分組五折交叉驗證的留存機率模型，建立穩定化 inverse-probability-of-observation weights。每個目標視窗使用相對首段的直接留存機率，不跨門檻連乘。
- 先發 101+ 球 Stuff+ 的 Slice 1 adjusted delta 為 +0.212；同場 survivor-paired 為 -0.658，校正 observed selection 後為 -0.679（95% CI -1.866 至 +0.508，438 場、141 位投手）。因此原本尾段上升主要是留在場上的好投手／好狀態被選入，而不是可直接解讀的體力回升；極端尾段仍因樣本小而不顯著。
- 先發 Stuff+ 的 weighted paired delta：21–40 -0.486、41–60 -1.134、61–80 -1.735、81–100 -1.714，前四段的 95% CI 皆低於 0。101+ 因只占首段 cohort 9.0%，有效樣本約 298.5，必須維持 research-only 標示。
- Slice 2 另提供 TTO sensitivity、SP/RP 分開的固定 season-cohort 比較與留存模型 AUC／有效樣本／最大權重診斷。Location+ 與 RP 部分趨勢仍可能受未觀測的教練決策、健康、牛棚狀態及熱身影響，不能宣稱因果。
- `/lab/stamina` 已加入大型字級的 Slice 2 correction 區塊，可切 Stuff+／Location+，直接比較 Slice 1、同場配對、selection-weighted 結果，並展開完整 sensitivity tables。模型版本為 `stamina_research_slice2_v1`；資料截至 2026-09-27。
- 驗證：Stamina schema 可解析 18 筆 appearance corrections 與 9 個 selection models；Stamina／更新／freshness targeted tests 9 passed；Nuxt typecheck 與 UTF-8 check 通過。Slice 3 已於後續完成。

### 2026-09-29 Stamina Slice 3

- Slice 3 已完成 SP／RP 分開的投手個人 retention slope。每場先以相同球種配對首段與後段，降低 repertoire sequencing 偏誤；後段觀測沿用 Slice 2 的 cross-fitted stabilized observation weights，再按 matched-pitch precision 估計個人斜率。
- 個人斜率以 random-effects empirical Bayes 向角色聯盟平均部分池化；輸出 raw slope、posterior slope、95% CI、reliability、樣本場次、matched pitches 與 above／below／indistinguishable band。單位固定為 SP 每20球、RP每5球的 Plus-point 變化，仍不是正式 Stamina+。
- 2026 合格樣本：SP 203位（至少8場）、RP 364位（至少12場）。Stuff+ 聯盟 slope 為 SP -0.343／20球、RP +0.226／5球；Location+ 為 SP -0.048／20球、RP +0.047／5球。這些是 pitch-type-matched research estimates，不可直接宣稱因果。
- 時間前後半季驗證：SP Stuff+ 198位，Spearman ρ=0.571（stable）；RP Stuff+ 360位，ρ=0.399（partial）；SP Location+ ρ=0.075、RP Location+ ρ=0.019（皆 weak）。因此 Slice 3 支持繼續研究 Stuff+ 個人差異，但個人 Location+ 排名目前不可作正式指標。
- `/lab/stamina` 已加入 Slice 3 區塊：可切 SP／RP、共用 Stuff+／Location+ outcome switch、搜尋投手或球隊，顯示聯盟 prior、between-pitcher SD、split-half repeatability、頭像、個人頁連結、posterior CI 與 reliability。字級沿用 Stamina Lab 大字級，不把弱驗證結果包裝為正式分數。
- 模型版本 `stamina_research_slice3_v1`，資料截至 2026-09-27、狀態 current；API schema 可解析 1,134 筆 role×outcome 個人估計。Stamina／更新／freshness tests 9 passed，Nuxt typecheck、UTF-8 與 schema validation 通過。Slice 4A–E 已於後續完成。

### 2026-09-30 Stamina Slice 4A–E

- SP／RP 從 Slice 0 起就是分開估計：Slice 3 的 workload unit、minimum appearances、league prior、between-pitcher variance 與 empirical-Bayes shrinkage 都按角色獨立。SP reliability 普遍較高，主因是每場有更多同球種 matched pitches 與更長的觀測跨度，導致 sampling SE 較小；reliability 是角色內估計精度，不是跨角色能力分數。頁面已加入這段說明。
- Slice 4A 新增嚴格落後期且跨角色累積的 workload fields：全角色登板序號／賽季前累積球數、前場球數、前3／7／14／28日球數與登板數、back-to-back、long gap、前場角色切換。SP／RP outcome model 仍分開，但生理工作量不因角色切換歸零；測試確認當場最終球數不會洩漏進 predictor。
- Slice 4B readiness 定義為每場早段（SP前20球、RP前5球）相對該投手×角色×球種「此前至少20球」歷史基準的 Plus-point deviation。Pitcher fixed-effects 模型中，主要 Stuff+ 訊號為 RP 前場每多5球，下一場早段 -0.109（95% CI -0.217 至 -0.001）；RP 0休相對1休為 -0.548（-0.996 至 -0.100）。SP Stuff+ 沒有穩定 workload 係數。
- Slice 4C 以 Slice 2 selection-weighted、pitch-type-matched 單場 retention slope 為 outcome。SP 休7–13日相對正常4日為 -0.343（-0.570 至 -0.115），較像傷病／輪值中斷選擇，不能解讀成休息造成下降。其他正向 workload 訊號可能仍含 survivor／usage bias；Location+ 因 Slice 3 repeatability weak，維持 secondary endpoint。
- Slice 4D 同時放入跨角色賽季累積球數與線性／二次 calendar trend。每500球的 cumulative effect 在 SP/RP、Stuff+/Location+、readiness/retention 全部 95% CI 跨零；目前沒有證據顯示控制日期後仍有可辨識的整季累積衰退。Within-pitcher R² 僅 0.001–0.007。
- Slice 4E 完成2026 chronological 70/30 validation。SP Stuff+ readiness／retention 均 no_gain（RMSE improvement -2.58%／-0.66%）；RP Stuff+ 只有 +0.01%／+0.11%，correlation 0.031／0.075，實務上接近零。結論是公開的休息日與歷史用量目前無法可靠預測未見登板狀態。
- 2025 Location+ 已完整匯出709,876球；精確 Pete Stuff+ 歷史回填因每球展開312 contexts，停止於139,670／709,909 eligible pitches、144位投手、19.67%，狀態明確為 partial。2025 Stamina dataset 也標 partial。2025→2026管線已實跑，但僅23.7% dual-score coverage，四組 readiness 全為 `provisional_no_gain`，只作 smoke test、不納入研究結論。回填腳本新增 opt-in shard 參數；一般 daily update 預設行為不變。
- `/lab/stamina` 已加入4A audit、4B readiness、4C retention、4D chronic load、4E time/cross-season validation，沿用 SP/RP、Stuff+/Location+ 切換與大字級。模型版本 `stamina_research_slice4_v1`；2026資料截至2026-09-27且 current。

### 2026-09-30 Historical Plus 一鍵回填

- `/admin/updates`（Per aspera ad astra）新增 `Backfill 2021–2025 Plus data`。按一次會在本機後端依年份、依相依順序執行 Location+、逐球 Stuff+、Stuff leaderboard、Pitching+ 與 Stamina；不需要由對話逐年觸發，因此執行期間不消耗聊天 token，但會使用本機運算資源，且後端必須保持運行。
- 工作狀態原子寫入 `data/admin_job_logs/historical_plus_backfill.json`；頁面顯示各年份5階段狀態，逐球 Stuff+ 階段另外顯示 coverage 與已處理投手數。重新整理頁面會重新接回仍存活的工作；後端重啟後可以再按 Resume。
- 逐球 Stuff+ 沿用 pitcher-level SQLite cache，已完成投手不重算。若 Stuff+ 尚未達 `current`，該年份的 leaderboard／Pitching+／Stamina 不會在不完整來源上繼續重建；工作會標成 partial，下一次按鍵從快取續跑。
- API：`POST /api/admin/jobs/backfill-historical-plus`、`GET /api/admin/jobs/historical-plus-status`。歷史 Pitching+ 以各顯示賽季自身作為 centering reference，避免2021錯誤依賴不存在的2020資料。
- 依 Stamina Slice 5 的最低驗證需求，歷史回填優先順序調整為2025，再從2021依序續跑；2021已完成的 pitcher cache 保留，回到該年度時不重算。

### 2026-09-30 2025 Plus 完成與 Slice 5 決策

- 依使用者要求，2021與意外競態產生的2022工作均已停止；沒有其他歷史年份程序在跑，既有快取保留。`historical_plus_backfill.json` 明確標示2021／2022 paused、2025 completed。
- 2025逐球Stuff+已達709,909／709,909 eligible pitches、873投手、100%；Location+已完成709,876球；Pitching+完成704,958球、806投手、3,799投手×球種列；最終leaderboard有864投手且Stuff+/Location+/Pitching+皆current；Stamina dataset為current、712,528球、20,868登板、873投手。
- 歷史 leaderboard 原先在缺少 pitcher game-line 欄位時以 scalar `0 / 0` 觸發除零；`list_pitcher_leaderboard` 現在建立對齊列索引的缺值欄，並新增「整季無 game lines」回歸測試。歷史管線順序也修正為 Location+ → per-pitch Stuff+ → Pitching+ → leaderboard → Stamina，避免先封存缺少Pitching+的排行榜。
- 完整來源下的2025→2026 readiness 驗證仍沒有實務預測力：SP Stuff+ correlation 0.048、RMSE improvement -0.09%；SP Location+ 0.005／-0.24%；RP Stuff+ 0.033／+0.03%；RP Location+ 0.018／+0.01%。因此每日 readiness 不得包裝為 Stamina+。
- 相反地，pitch-type-matched、selection-weighted Stuff+ retention slope 具有跨季重複性：SP共同140人 posterior Spearman 0.617（raw 0.589；雙季 reliability≥0.35的134人 raw 0.640），RP共同222人 posterior 0.512（raw 0.491；可靠177人 raw 0.540）。Location+ retention仍弱：SP 0.196、RP 0.018。
- Slice 5 應改為「角色內 Stuff+ 維持能力 trait」：SP與RP分開、雙重身分雙分數、兩季partial pooling、100聯盟平均與CI；Location+只做診斷副指標，workload readiness留在research。Slice 6逐球hover應呈現固定trait、依當場用球位置推算的expected retention與實際Stuff+/Location+三者，不把單球雜訊偽裝成疲勞因果值。
- 本段是Slice 5發布前的決策門檻；2025完整回填後，retention trait已通過SP／RP跨季rank與RMSE improvement gate，正式結果以後續「Stamina Slice 5」段落為準。低解釋力workload readiness仍維持research-only。

### 2026-09-30 Stamina Slice 5

- Slice 5 已完成並將模型版本提升為 `stamina_research_slice5_v1`。正式 Stamina+ 定義為同角色、同季聯盟平均中心化後的 pitch-type-matched、selection-weighted Stuff+ retention trait；SP每20球、RP每5球，雙重身分保留兩個分數。
- 兩季估計先依 raw slope sampling variance 合併，再按角色進行 random-effects empirical-Bayes partial pooling；分數以角色平均100、投手間1 SD等於10分換算，並輸出95% CI、reliability、兩季數、登板數與matched pitches。
- 2025→2026 holdout的四道發布門檻為：Stuff+來源覆蓋至少95%、共同投手至少50人、Spearman至少0.40、相對角色平均baseline的RMSE improvement大於0。SP為140人、ρ=0.586、RMSE improvement +15.82%；RP為222人、ρ=0.491、+12.29%；最低來源覆蓋99.3%，兩角色皆validated。
- Qualified要求兩個單季reliability都至少0.35：SP 134人、RP 177人；兩季都有資料但任一季低於門檻者標Limited（SP 6、RP 45），只有一個合格球季者標Provisional（SP 130、RP 276）。低樣本分數仍可研究檢視，但不冒充合格排名。
- `/lab/stamina` 新增Slice 5研究版排行榜、SP/RP切換、姓名／球隊搜尋、Qualified-only篩選、四道gate、跨季rank與RMSE、Stamina+ CI和樣本標籤。Location+與workload readiness仍只屬診斷，不進Stamina+。
- Slice 6已於後續完成逐球expected retention state及hover接線；固定trait、expected path與實際Stuff+/Location+仍必須分開，不得把單球偏差標成因果疲勞。

### 2026-09-30 Stamina Slice 6

- Slice 6 已完成，模型版本為 `stamina_research_slice6_v1`。2026 Stamina parquet的716,544球已新增固定投手×角色trait、expected retention delta、同場同球種早段基準、expected Stuff+、reliability與sample label。
- expected retention在SP前20球／RP前5球reference window維持0，之後以2026同角色聯盟slope加上投手兩季retention advantage推進；expected Stuff+只在該場早段存在相同球種基準時提供，缺少時保留null。
- Trait可連結658,701球（91.9%）；expected Stuff+可計算597,825球（83.4%）。未覆蓋主要來自未達Slice 3最低登板門檻的投手或同場早段未投該球種，不以聯盟平均或0補值。
- Pitcher Personal的Movement與Location scatter現在共用逐球Stamina state；hover顯示Observed Stuff+、Location+、固定Stamina+ trait、Expected retention Δ與Expected Stuff+。Selected Pitch面板也顯示相同欄位，既有影片點擊與pitch identity不變。
- Movement／Location payload以game_pk＋at_bat_number＋pitch_number＋pitcher精確合併Stamina parquet。Shane Baz抽查2911球全部連到trait、2775球有expected Stuff+，兩張scatter的逐球欄位一致。
- 單球Observed Stuff+與Expected Stuff+的差距只代表高雜訊觀測，不是因果疲勞值；UI與Slice 6 audit均保留此警告。每日Stamina重建會自動重建逐球state，不在頁面request內重算模型。

### 2026-09-30 Stamina Lab 排序、單季榜與特徵影響力

- `/lab/stamina` 的研究內容已依 Slice 0 → 1 → 2 → 3 → 4A–E → 5 → 6 由上到下排列；標題、資料集控制與總覽維持在 Slice 0 前方。
- Slice 5 排行榜可切換 `2025–2026 Trait`、`2026 Season`、`2025 Season`。單季分數只使用該季 Slice 3 posterior Stuff+ retention slope，按 SP／RP 各自聯盟平均100、角色內1 SD等於10分縮放，不借用另一季，並明確標成 `season estimate`。目前共1,130筆：2025 SP 207／RP 356，2026 SP 203／RP 364。
- Slice 4B–C 新增 feature influence 表。`standardized Δ` 是同一投手內 predictor 增加1個標準差時的模型Plus-point變化；`relative strength` 只在目前角色×endpoint模型內以最大絕對值標為100，不能跨模型比較，也不是因果百分比。
- 正式 Stamina+ 仍只採用 pitch-type-matched、selection-weighted Stuff+ retention slope。Slice 4 的休息、近期負荷、賽季球數與月份等 predictor 只作研究診斷；高度相關特徵會共享訊號，不進正式分數。
- 驗證：Stamina與下游personal／freshness／admin targeted tests 23 passed、Nuxt typecheck、UTF-8與完整API schema validation通過；未執行Nuxt build。

### 2026-09-30 Stamina v2 Slice 7–12 行程

- 既有Slice 0–6維持為v1基準，不原地改寫已驗證分數。新研究從Slice 7開始；球種家族固定為Fastball、Breaking、Offspeed，且FO明確歸入Offspeed。
- Slice 7先做family coverage、開局Stuff+／球速與v1分數的負相關、回歸平均、天花板效應、球種使用選擇與缺值稽核，並預先註冊v2 target與release gate。
- Slice 8建立每位先發每場、先依精確球種與情境校正再聚合家族的衰退軌跡；trailing MA5只用於降噪、顯示與特徵提取，不把重疊視窗當獨立樣本推論。
- Slice 9平行比較ANCOVA/GAMM、家族層級random slopes與可解釋boosted-tree challenger；正式推論仍使用raw pitch／game clusters，避免以MA5虛增樣本數。
- Slice 10以2025訓練、2026 holdout，檢查RMSE、跨季rank、calibration、coverage、family reliability及新分數與early Stuff+／球速的殘餘相關；通過後才可產生Fastball／Breaking／Offspeed Stamina+與overall候選。
- Slice 11與Observed Game Stamina+只在Lab提供逐場多訊號曲線、單場分數與整季狀態；不得把歷史曲線包裝成下一場預測。
- Family契約：Fastball包含FF／FA、SI、FC等；Breaking包含SL、ST、CU、KC、SV等；Offspeed包含CH、FS、FO等。正式計算要先在精確球種內校正，再聚合family；缺少樣本維持null，不補0。
- Slice 8的MA5只作降噪、視覺與curve feature；重疊視窗不是獨立樣本，正式CI仍以raw pitch／appearance cluster或bootstrap估計。
- v2主要目標應比較ANCOVA或measurement-error-aware late-quality model，避免單純`late - early`的回歸平均。GAMM處理非線性pitch-count curve，hierarchical model處理pitcher-family小樣本，ML只作out-of-time challenger。
- Overall family權重必須預先固定（如前一季或每場前20球repertoire），不可使用後段實際usage，否則投手避開正在衰退的球種反而會提高分數。
- 主要研究風險包括informative removal、time-varying pitch selection、Stuff+特徵循環解釋、跨季arsenal改造、未觀測傷病／配速／教練決策、Offspeed稀疏樣本與multiple testing。所有結果先稱retention association，不稱因果疲勞。

## 2026-09-26 最新：Pitcher／Batter Period Comparison 共用化

- `/comparison/period` 與 `/batters/comparison/period` 現在共用 `ComparisonPeriodSetup`、`ComparisonTransferPanel`、`ComparisonCardsGrid`、`ComparisonMetricDetails` 與 `ComparisonPeriodWorkspace`；後續不要再各自複製 selector、period cards 或 filter rail。
- 打者版已補齊投手版的 Apply Periods 工作流、左右期間 percentile cards、完整 metric comparison、Period Snapshot、可收合右側 filters、轉隊 stint 一鍵前後比較，以及完整共用 Discipline boards。
- 左右 percentile 使用各自日期區間的實際打者數據，再對該季至少 50 PA 的打者母體分別計算；卡片會顯示各自日期、球隊與 pitch sample。不可退回只顯示兩張一般摘要卡。
- 原本左右完全相同的 `Season timing reference` 是全季摘要，不是 period 資料；容易誤導的 Timing Reference 與 Source Audit 已從 period response／頁面移除。
- 打者 date-range API 現在回傳 `current_team`、`transfer_count`、`team_stints`；stint 以連續球隊段落計算，因此 A → B → A 會保留為三段，不會錯誤合併。
- `ComparisonAdvantageSummary` 增加 display 模式，投手既有 percentile gap 顯示不變；打者使用實際 delta 單位，不把原始數據冒充百分位。
- 驗證：`npm run typecheck` 通過、`test_batter_period_comparison_service.py` 5/5、UTF-8 與 `git diff --check` 通過、`.nuxt/tsconfig.json` 存在、`/login` 與 `/api/health` 為 200。瀏覽器介面仍回報沒有可用 browser，因此本輪沒有截圖級視覺 QA。

---

## 2026-09-09 歷史工作樹提醒：品牌模式、導覽、Percentile 共用化與 Batter Leaderboard

本節不再是目前功能優先順序，但其dirty-worktree與防回歸規則仍有效。新對話第一步只執行 `git status --short` 辨識範圍，**不可 restore、reset、checkout、刪除或覆蓋這些未提交內容**。

### Peteclub／Petehub 品牌模式

- 新增 `frontend/composables/useSiteBrand.ts`，以 `site-brand-mode` cookie 保存 `peteclub | petehub`；目前預設為 Peteclub。
- `/admin/updates` 的 `Per aspera ad astra / Data operations` 頁已有 `Site identity` switch，可全域切換 Peteclub／Petehub。
- Peteclub 首頁使用單一字樣 `Peteclub`，採暖象牙至銅金色字標、charcoal 背景、低飽和琥珀光與淡化的棒球資料紋理；`Teams / Pitchers / Batters / Fielders` 和搜尋區已整組往右移。
- Petehub 首頁以 `.site-home--petehub` 保留原本橘黑背景、`Pete`＋橘色 `hub`、膠囊導覽與原搜尋框配置。後續修改 Peteclub 時不可再讓共用 selector 汙染 Petehub 原版。
- 登入、註冊、管理帳號、Lab 標題與首頁搜尋文案會依品牌模式切換名稱。
- 首頁右上角可見的 Light／Dark 切換按鈕已移除；底層既有 theme state 尚保留，不要誤認為整套 theme 系統已刪除。

### 全域 Home 與 Pitchers 首頁

- 非首頁、非登入／註冊頁通常由 `frontend/app.vue` 顯示全域回首頁入口：Peteclub 模式為一般 Home icon／文字，Petehub 模式為原 Petehub 標誌。
- `/pitchers` 是明確例外：不可使用 fixed global Home，也不可增加 `global-home-offset`。該頁在自己的 `top-bar` 內有無框、無底色的 Home 連結，與右側導覽位於同一內容邊界。
- `/pitchers` 原本的大型 `Pitcher station` 品牌字樣已移除。不要再把 Petehub 或有框 Home 浮在頁面左上外緣，也不要讓按鈕卡在內容容器一半的位置。
- `Pete` 與橘色 `hub` 的全域標誌必須保持緊密；`.global-home-link--brand` 已覆寫 `gap: 0`，避免一般 Home icon 的 gap 被品牌標誌繼承。

### Pitcher／Batter Overview Percentile 共用元件

- `frontend/components/comparison/PercentileMirrorCard.vue` 現在是投手與打者 Overview 共用的 percentile 呈現元件，沿用 Pitcher Period Comparison 的 right-side 配置。
- Batter Overview 的 `BatterPercentileProfile.vue` 已改為 adapter，將打者指標轉成 `ComparisonMetric` 後交給 `PercentileMirrorCard`；`BatterOverviewTab.vue` 會傳入球員 ID、姓名、球隊與年份。
- Pitcher Personal Overview 已新增同一個 `PercentileMirrorCard`；後端 `personal_service.py` 透過既有 comparison pool／metric card 建立 `charts.percentile_profile`，不可再建立第二套不一致的投手百分位算法。
- 百分位圓點在 40–60 區間使用深色字，其餘使用白字。打者端較低越好的 Chase%、Whiff%、K% 已保留 `higher_is_better=false` 語意。

### Batter League Leaderboard 最新配置

- 路由：`/batters/leaderboard`。
- 原本分離的 Standard／Discipline 已合併為 `Production & discipline`，目前只保留兩個 view：`Production & discipline`、`Contact`。
- 合併表欄位：PA、G、HR、AVG、OBP、SLG、OPS、BB、SO、BB%、K%、Whiff%；各欄仍可排序，合併表以較寬 table 搭配既有橫向捲動，Contact 表維持原寬度。
- 目前 tab 字級：標題 17px、說明 14px。
- 目前排行榜字級：`RANKED RESULTS` 13px、主標題 28px、qualified hitters 12px、表頭 12px、排名／數值 14px、球員姓名 16px、球隊／PA 11px。
- 排行榜已統一使用頁面無襯線字體；數值使用 `font-variant-numeric: tabular-nums` 對齊，不再整張表使用 Fira Code。

### 本輪驗證與操作限制

- 相關修改後多次執行 `frontend/node_modules/.bin/vue-tsc.cmd --noEmit -p frontend/.nuxt/tsconfig.json`，最近一次通過。
- 本機 `/`、`/login`、`/pitchers`、`/batters/leaderboard` 與後端 `/api/health` 在相關修改後皆曾回 HTTP 200。
- 未執行 Nuxt build，未清理 `.nuxt`，也未做 destructive Git 操作。
- 內建瀏覽器當時回報 `No browser is available`，所以最後幾輪以 typecheck、HTTP smoke 與使用者截圖確認為主。新對話不要為已通過項目反覆啟動瀏覽器。
- UI 修改必須非常局部。使用者已多次明確反對「要求調整 A 卻刪除／改壞 B」；尤其是 `frontend/app.vue`、`frontend/assets/css/main.css`、首頁品牌 selector 與共用 percentile 元件，動手前必須先列出影響頁面。

---

## 2026-09-04 嚴重事故：禁止在運行中的 Nuxt 上執行會清理 `.nuxt` 的驗證

### 事故經過與根因

- 使用者只要求全域檢查每日更新資料，代理卻超出範圍修改更新管線與管理頁。
- 在 Nuxt dev server 仍運行時執行 `npm run build`。Nuxt build 先清理了共用的 `frontend/.nuxt`，之後才因運行中程序鎖住 `codex-dev.stdout.log` 而以 `EBUSY` 失敗。
- 清理造成 `frontend/.nuxt/tsconfig.json` 消失；運行中的 Vite 隨後對所有頁面回報 `TSCONFIG_ERROR: Tsconfig not found`，本地端與 lhr 公開網站因此不可用。
- 之後曾建立 `.nuxt-verify` 嘗試繞過鎖，再清掉該暫存生成目錄。雖然它不是 Git 追蹤的原始碼，介面呈現為大量刪除，且這種未先說明的刪除行為不可接受。
- 事故當下 Git 追蹤的正式程式沒有 1,700 行刪除，實際 tracked diff 為新增 49 行、刪除 9 行；但這不減輕破壞運行環境的嚴重性。

### 已執行復原

- 只針對該輪變更執行精確 `git restore`，並移除該輪新增的稽核文件；先前已完成並推送的專案內容未回退。
- 停止故障的前端 PID 後執行 `npx nuxi prepare`，確認 `.nuxt/tsconfig.json` 已重新生成。
- 重新啟動 Nuxt 於 `127.0.0.1:3000`；FastAPI `127.0.0.1:8000/api/health`、本地首頁、登入頁與 Batters 頁皆回 HTTP 200。
- 原匿名 lhr tunnel 已死亡且無法取回同一 hostname；重新建立後的網址寫入 `.logs/private-site-url.txt`，不可把本文件內的某個 lhr URL 當永久網址。
- 復原完成時 `git status --short` 為空。

### 絕對禁止事項

1. **只被要求「檢查／盤點／說明」時，預設只能唯讀；未獲明確要求不得順手修改、重構、建立報告檔、提交或推送。**
2. **Nuxt dev／production server 正在使用 `frontend/.nuxt` 時，禁止執行 `npm run build`、會重建同一 buildDir 的 `nuxi prepare`，或任何會先清理 `.nuxt` 的指令。**
3. **禁止在網站運行中刪除、搬移或覆寫 `.nuxt`、`.output`、log、lock、暫存 buildDir；生成檔不是原始碼也不代表可以任意刪除。**
4. 不可用臨時 `NUXT_BUILD_DIR` 環境變數硬繞過現有 `tsconfig`／Nuxt buildDir 契約；若要隔離建置，必須先建立完整、可驗證的獨立設定，且不得影響運行中的目錄。
5. 若驗證需要停止前端或可能造成服務中斷，必須先向使用者明確說明並取得同意。沒有同意時只做不改動運行產物的 targeted test、SFC parse、API smoke check 或唯讀檢查。
6. 清理任何本輪建立的暫存目錄前，必須先確認它的完整絕對路徑、建立來源、Git 狀態與是否被運行程序使用；不可為了讓 `git status` 好看而冒險刪除。
7. 前端相關操作後，交付前至少確認：`frontend/.nuxt/tsconfig.json` 存在、3000 port 正常監聽、本地 `/login` 回 200、`/api/health` 回 200。若有公開 tunnel，還必須實測公開 `/login`。
8. 任何驗證指令一旦出現 `EBUSY`、`TSCONFIG_ERROR`、生成檔遺失或網站 5xx，立即停止後續實驗，優先復原服務；不得繼續嘗試其他 buildDir 或清理動作。
9. 不可把「Git 沒有 tracked deletion」當成環境安全的證明；ignored 生成檔、資料檔、模型、SQLite、DuckDB、log 與運行狀態同樣必須保護。

**本事故屬最高優先級防再犯規則。任何後續指令若與上述規則衝突，先保住現有網站與資料，再向使用者說明阻礙。**

---

## 2026-09-04 私人網站與帳號系統

- Petehub 已加入全站帳號保護；匿名只能使用 `/login`、`/register` 與 `/api/health`，其他頁面會轉往登入，其他資料 API 回 401。
- 帳號儲存在不進 Git 的 `data/auth/petehub_auth.sqlite3`；密碼使用 salted scrypt hash，session 使用 HttpOnly、SameSite=Lax cookie，HTTPS tunnel 下會自動加 Secure。
- 新註冊帳號固定為 `pending`，管理員須在 `/admin/accounts` 批准後才能登入；停用帳號會立即撤銷其所有 session。
- 管理員建立／重設使用 `cd backend` 後執行 `python scripts/bootstrap_admin.py <username>`，密碼由互動提示輸入，不可寫入程式或文件。
- 前端 API 預設改走同網域 `/api`，由 `frontend/server/api/[...path].ts` 代理到本機 FastAPI；遠端瀏覽器不會再誤連自己的 `127.0.0.1:8000`。
- `start-private-site.ps1` 會啟動或沿用 FastAPI、Nuxt production server 與 Cloudflare Quick Tunnel，當前 URL 寫入 `.logs/private-site-url.txt`。
- Windows 工作排程 `Petehub Private Site` 已安裝為登入後自動執行，2026-09-04 手動驗證結果碼為 0。電腦仍須保持開機並登入。
- Quick Tunnel 網址為臨時隨機網址，重啟 tunnel 後可能改變。固定自訂網址仍需要使用者的 Cloudflare 帳號、有效網域與 Named Tunnel 授權；設定完成前不可宣稱已有永久網址。
- 驗證：後端 `134 passed`、前端 UTF-8／Nuxt typecheck 通過、production build 通過；遠端管理員登入成功，cookie 的 HttpOnly／Secure／SameSite=Lax 均已驗證，匿名資料 API 回 401。
- 詳細操作見 `docs/PRIVATE_SITE.md`。

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

### 2026-09-04 Starter reference 與 Batter timing 更新修復

- `data/Starter/2026_starter_BR.csv` 與 `2021_2026_starter_dashboard.csv` 曾停在 2026-07-13，原因是正式每日管線只有讀取它們，沒有任何產生／更新步驟。
- FanGraphs legacy endpoint 目前會回 HTTP 403，因此新增 `starter_reference_service.py`：用 MLB 官方 Stats API 取得投手身份、球隊與官方賽季欄位，再以本機最新逐球資料及 official pitcher game lines 重建 GS、IP、ERA、K/9、BB/9、HR/9、QS、Game Score、IP/GS、Pit/GS 與 pitch-count bins。
- Starter 統計一律裁切到本機逐球／game-line coverage，不可混入 MLB API 已多出一天的場次。2026-09-04 實際更新為 353 位投手，資料截止 2026-09-02。
- 新增獨立 `data/Starter/2026_starter_dashboard.csv`，並原子更新 combined dashboard 的 2026 slice；歷史年度保留不變。無可靠即時來源的 WAR／LOB% 維持缺值，不沿用舊值假裝最新。
- Batter timing 原本已有 `refresh_batter_timing_cache`，但未接每日排程；現在 `run_pitcher_data_refresh` 會更新 2026 All／L／R 三份 Savant cache。2026-09-04 實際列數為 5,450／4,573／5,103。
- Starter reference 與 Batter timing 都採原子檔案替換；外部 MLB／Savant 暫時失敗時保留上一份 snapshot，回報 `status=stale`，不可讓它們拖垮其餘逐球、Plus 或 lineup 更新。
- 本修復只動後端資料產線與 targeted tests；禁止為此執行 Nuxt build 或清理 `.nuxt`。

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

## 八、Batter Lab 已完成狀態與保留資料邊界

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

### Batter Comparison Slice 0–9（已完成至本機資料邊界）

Slice 0–8的原始研究路線與後續Slice 9共用period workspace都已完成；不要在下一輪重做。既有dirty worktree曾以明確檔案清單建立`daeb568` checkpoint，未使用`git add .`。

- 新建構層級：`/batters` → `/batters/comparison` → `/batters/comparison/period`、`team`、`lineup`；舊 `/comparison/batter-period` 會導向新 period 路徑。
- 新 API：`/api/batter-comparison/period/options`、`date-range`、`overview`；使用獨立 schema、service 與 route，未把 batter-only 分支塞入投手 comparison service。
- 指標：PA、AB、OPS、wOBA、xwOBA、AVG、OBP、SLG、Avg EV、Max EV、Barrel%、HardHit%、SweetSpot%、Swing%、Chase%、Contact%、Whiff%、K%、BB%、K-BB%。每列均顯示 A、B、B−A 與兩側 denominator；百分率 delta 使用 pp。
- 雙好球帶：Period A/B 並排，共用 Bat Speed／Choice 切換、同一 heatmap blend 與同一色階 domain。Choice 是 swing frequency；Bat Speed 只使用 competitive tracked swings。
- 共用 `StrikeZoneScatter.vue` 只新增 optional shared metric domain，舊呼叫不傳時維持原行為。
- Slice 4：Bat Tracking A/B、固定整季 competitive threshold、pitch family 與既有情境 split；Squared-Up／Blast 缺來源時為 unavailable。
- Slice 5：2026 Miss Distance 做真正 A/B；X/Y/Z 只顯示 full-season summary reference，不混入任意日期 delta。
- Slice 6：exact distributions 與 batting stance 已完成 source audit；只有 intercept／attack geometry 可用，沒有腳印／stance 欄位時不生成視覺。
- Slice 7：Team Batting 依 PA sequence 與 fielder IDs 重建棒次／守位，提供 1–9 棒產出、platoon split、樣本與 reliability；DH／PH 無法可靠區分時標 unknown。
- Slice 8：最近 20 場先發／棒次機率與三組 lineup scenarios，使用 empirical PA-outcome simulation 比較 projected R/G；active roster、傷兵與 probable starter 缺來源，固定標為 research mode、不是官方預測。

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

### Batter Research Slice 4–8 完成契約

以下規格已依目前可驗證資料完成；標示 unavailable／summary-only 的項目是正式的 source gate，不可在後續對話改成推測值。

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
- 任意日期區間的逐球 `miss_distance` 目前本機只有 2026 可精確完成；Slice 5 已依年份回傳真實值或 unavailable。
- Centered／On Time／Lined Up 等 X/Y/Z 目前主要來自 Savant summary，不能假裝能按任意日期精確切割。
- exact Savant distributions 與真實 batting stance 仍缺來源；Slice 6 以 source audit 封鎖偽造輸出。棒次／守位研究與 lineup scenarios 已在 Slice 7–8 的獨立頁面完成。
- 所有新 panel 使用直角邊框；桌面版需在 100% 瀏覽器縮放下看見主要比較內容，窄螢幕再改為單欄。
- 驗收以 targeted backend tests、UTF-8 檢查、Nuxt typecheck、A/B API smoke check，以及投手／打者好球帶沒有回歸為準。

---

## 九、其他尚未完全收尾的區域

### 2026-09-03 Team Dashboard 後續調整

- `/batters/comparison/team` 已移除容易誤認成球員名單的 Batting-order results 彙總表。
- 三張打線情境卡位於 `/teams/:teamId`：Recent consensus、Latest observed、Run-expectancy candidate，可切換 vs RHP／vs LHP。它是 Team 頁的獨立區塊，不受 Team Hitting Intelligence API 的 loading/error 條件控制。頁面使用唯讀 `/api/batter-comparison/team-research/lineup-scenarios`，HTTP request 不重建守位、不執行模擬。
- Team Hitting Intelligence（lineup skill strip、timing map、miss profile）保留在 `/teams/:teamId`；Performance Board 下方保留可展開 Pitch-family Matchup Matrix。上述 team-only 區塊不可接到 `/batters` 總頁。
- `run_pitcher_data_refresh` 會在資料更新後，為全部球隊及左右投先算好打線情境，原子寫入 `data/derived/batter_lineup_scenarios_<year>.json`。API 以 `current|stale|unavailable` 回報快取狀態；資料較新或重建失敗時仍顯示上一份完成結果。
- `useAutoRefresh` 只在頁面保持可見時依間隔更新；不得監聽 window focus 或 visibilitychange 後立即整批刷新，避免使用者切離再返回時重載所有 dashboard request。
- Windows 工作排程 `Petehub Daily Data Update` 使用台灣本地時區，每天 03:00 執行根目錄 `daily-update.cmd`；安裝／更新腳本為 `install-daily-update.ps1`，並設定 StartWhenAvailable 與 IgnoreNew。
- Team Dashboard 指定內容順序：Rotation game lab → Previous outing arsenal → Bullpen availability → 三組 precomputed lineups → Recent starts → Team Hitting Intelligence；其餘區塊維持後續原順序。
- Pitch-family Matchup Matrix 已移到 Performance Board 下方，預設收合，點擊表頭才展開。
- Performance Board 已擴充：投手增加 G、WHIP、K%、BB%；打者增加 PA、AVG、OBP、SLG，同時保留 OPS、wOBA、HR。
- 績效型配色統一為「深紅 → 紅 → 淺紅 → 白 → 淺藍 → 藍 → 深藍」，好到壞依此排列；已套用 Matrix、共用 percentile table 與 Batter Percentile Profile。
- Team、Pitcher Personal、Batter Personal 會在頁面重新取得焦點或恢復可見時背景更新，頁面持續開啟時每五分鐘更新；相關 API request 使用 `no-store`。Batter Personal 同時補上同頁 route query 變更的反向同步。
- Teams 的 Rotation game lab 預設場次以 `Asia/Taipei` 當天往前一天為 cutoff，選該日或更早最近一場；例如台灣 2026-09-15 預設美國賽程日 2026-09-14，不再直接選清單最後、可能要到台灣隔天才進行的賽事。使用者用左右箭頭手動切換後不受影響。
- 2026-09-15 已手動完成 `daily_update.py --year 2026 --include-pitch-stuff`。Savant 可取得逐球至 2026-09-13，本機 2,245 場；官方已完成至 2026-09-14 共 2,255 場，但 9/14 的 10 場逐球尚未釋出，coverage 正確標為 `source_pending`。Stuff+／Location+ 到 9/13，Pitching+ 最新完整計算到 9/12；影片 lookup 與 pitcher game lines 各 2,245 場、failed 0。逐球 Stuff+ 全量掃描 854 位投手，326 位更新、寫入 13,226 筆、deferred 0，快取共 659,748 筆。流程狀態 `completed`，lock 已移除，下一次每日 03:00 排程會重試 9/14。

- Pitching+ Lab：曾出現 404、空資料、版面超寬、outings trend 空白與 leaderboard 欄位問題；進一步修改前要先確認目前實際程式狀態。
- 全域頁面寬度：使用者偏好 100% 瀏覽器縮放即可看見主要內容，不應靠把整頁做得更寬或讓右側被切掉。
- Petehub 全域首頁按鈕：曾多次與頁面標題重疊；若再修改，應檢查 layout 層級而非每頁各自補 margin。
- 後台網站結構圖：使用者希望 Data Operations 頁可看到全站路由、API、共用模組與依賴狀態，目前是否完成需先查程式。
- Games／Game Score／official lines：歷史上曾因 derived 或 pitcher lines 更新落後而出現空白或 0，更新流程要保持串接。
- Team payroll、transactions、injuries：FanGraphs 抓取易受動態頁面或表格結構影響，應保留快取、錯誤隔離與可重跑機制。

---

## 十、2026-09-10 Leaderboard Slice 0–4 與 Stuff+ 自動化

- `/leaderboards` 現有 Basic／Stuff+／Location+／Pitching+／Stamina+ 五個頁籤。前三個Plus頁籤各自顯示 FA/SI/FC/FS/SL/CU/CH/KC/FO 分球種欄位與整體分數；缺值顯示 `-`，不補 0，球員名連到 Pitcher Personal。Location+ 的 Slider／Sweeper 與 Pitching+ 的 SL／ST 都依球數加權合併為 SL，FF 顯示為 FA。Pitching+ 使用最新可完整計算的匯出，即使比主逐球來源慢也保留數值，同時以 `pitching_data_as_of`、stale 狀態與 warning 清楚標示獨立截止日。Stamina+則依本文件Slice 14契約只發布2026 Starter榜。
- 投手 leaderboard 的 Basic、Stuff+、Location+、Pitching+ 姓名前都使用與打者 leaderboard 相同的 `MlbPlayerHeadshot`；以既有 `player_id` 取 MLB 頭像，載入失敗時沿用元件的姓名縮寫 fallback。`DataTable` 只新增 opt-in 的 headshot props，不影響其他表格。
- `backend/app/services/stuff_leaderboard_service.py` 以 Pete Stuff+ v3 同一模型批次計算全聯盟、各球種與整體 Stuff+，合併當期 Location+／Pitching+ 的整體與分球種快取後原子寫入 `data/derived/stuff_leaderboard_<year>.json`。頁面與 `/api/stuff/leaderboard` 只讀快照，不在 request 內重算；API 支援 role、team、minimum_ip，並回傳 `data_as_of`、model version、`current|stale` 與 warnings。
- 2026-09-11 已重建四頁籤用快照：847 位 Stuff+ 投手中 826 位具 Location+ 分球種資料。Pitching+ 頁籤顯示最新完整匯出的整體與分球種值，並獨立標示其截止日。
- 2026-09-11 晚間已手動執行 `daily_update.py --include-pitch-stuff`：官方與本機都為 2,200 場、最新 2026-09-10、缺場 0；影片 lookup 與 pitcher game lines 也各完成 2,200 場且零失敗。逐球 Stuff+ 全量掃描 852 位投手，478 位更新、寫入 59,458 筆、deferred 0，快取共 646,522 筆。
- 同次更新後 Stuff+／Location+ 已到 2026-09-10；Pitching+ 從 2026-09-07 推進到 2026-09-09。2026-09-10 的 1,342 球仍全部缺上游 `arm_angle`，因此不得估補；combined leaderboard 顯示 2026-09-09 的最新完整 Pitching+，並維持 stale 與獨立截止日提醒。`backend/scripts/daily_update.py` 已將 stdout／stderr 固定為 UTF-8，避免所有步驟成功後因 Windows CP950 列印 JSON 反而回傳非零退出碼。
- 2026 第一份快照已建立：逐球來源截至 2026-09-08、847 位具有效 Stuff+ feature 的投手、模型 `pete_stuff_outcome_probability_v3_312_contexts`。Pitching+ 尚無可驗證的每日來源，欄位 source-gated 為空值。
- 每日 `run_pitcher_data_refresh` 在 Location+ 後自動重建 plus leaderboard；失敗時保留上一份原子快照並標 stale。admin status 會回報快照狀態、截止日、生成時間、模型版號與列數。
- 逐球 Stuff+ 快取只補缺少 pitch key；來源縮減／孤兒 key 才重建該投手。2026-09-29 起每日更新不再套用 75 位投手上限：Stuff+ 是必要步驟，必須完成所有 pending pitchers，並驗證 `cached_rows == eligible_rows` 才能回報 `current`；否則每日更新明確失敗，不可靜默保留 partial。完成後會依序重建 Plus leaderboard 與 Stamina Lab。
- 2026-09-29 全量回填與稽核完成：官方／本機皆為 2,429 場、最新 2026-09-27、缺場 0；來源 716,544 球，其中 713,853 球具 Stuff+ eligibility，713,853 球全部已快取，missing eligible 0、coverage 100%、868 位投手、deferred 0。本次補寫 41,973 球。Stamina 重建後 Stuff+ 覆蓋率 SP 99.8%、RP 99.3%；剩餘未覆蓋是上游無球種／追蹤資料，不是快取缺漏。
- Slice 5–6 已接線：每日 Location+ 後會用既有 `pete_pitching_complete_pitch_v1` artifact 刷新 Pitching+，再重建 combined Plus leaderboard；不重新訓練，也不把 Stuff+／Location+ 相加冒充 Pitching+。Pitching+ CSV／Parquet／metadata 改為 temporary-file replacement。
- 2026 Pitching+ 已實跑更新為 469,722 eligible pitches、777 pitchers、3,695 pitcher-pitch-type rows。原始來源截至 2026-09-08，但該日 4,472 球的 `arm_angle` 全部缺失，因此完整特徵匯出截至 2026-09-07；Pitching Lab 顯示 stale 與兩個截止日，combined leaderboard 依 strict cutoff gate 暫不顯示 Pitching+，後續來源補齊時每日工作會自動解除。
- Pitcher Personal → Movement scatter 已與同頁 Location scatter 共用 pitch identity／影片契約。Movement 圓點可用滑鼠、Enter 或 Space 選取；有 `video_url`／`play_id` 時直接開啟既有、相同位置的全頁影片 modal，沒有 mapping 時只更新 Selected Pitch 並保留 unavailable 提示。Movement 另有 `_movement_point_key` 單點索引 fallback，避免舊 response 缺 pitch identity 時一次圈選整個同球種。
- Windows task 已允許電池供電啟動、切到電池後不中止、WakeToRun，仍維持每天 03:00、StartWhenAvailable、IgnoreNew。
- 驗證：Stuff/cache/admin targeted tests 共 16 passed；UTF-8 check、Nuxt typecheck、`git diff --check` 通過。未執行 Nuxt build、未清 `.nuxt`。
- 2026-09-15 修正投手 Comparison 的轉隊球隊標籤：年度 comparison CSV 不再蓋過最新逐球球隊；例如 Dennis Santana（642701）現在顯示 AZ，而歷史隊段保留 PIT 3/26–7/20（711 球、44 場）→ AZ 8/17–9/13（149 球、10 場）。comparison pool 快取會隨 comparison CSV 或年度 DuckDB mtime 自動失效。
- `/comparison/period` 已加入轉隊偵測與一鍵區間：兩個連續隊段可直接比較轉隊前後；超過兩段可各自選 Period A／B 隊段。隊段按逐場 `pitcher_team` 的連續變化建立，因此 A→B→A 不會被錯誤合併成兩隊。Period 卡片的球隊也改由各自日期窗內逐球資料決定，跨多隊的手動日期窗顯示 `N Tms`。
- Comparison 的 SP／RP 不再信任年度 CSV 角色欄位，改用與投手 Leaderboard 相同的逐場 `GS / G > 0.3` 規則覆寫。Corbin Burnes（669203）的 2026 comparison／estimators CSV 雖錯寫 RP，但本機逐場為 G=1、GS=1，API 現固定回傳 `Corbin Burnes (AZ, SP)`；避免 daily update 中 comparison CSV 早於 Starter Dashboard 產生時短暫顯示錯誤角色。

---

## 十一、2026-09-20 RE24 & Leverage Lab 測試版

- 新增 `/lab/leverage`，由 Pitcher Lab 首頁的 `RE24 & Leverage Lab` 卡片進入。頁面包含 2025／2026 情境計算器、Local Estimate 對蒐集聯盟表的回歸診斷，以及可切換 Local Estimate／Collected Reference 的全聯盟後援 leaderboard。
- 情境輸入包含局數、上下半局、投球方／對手分數、出局數與壘包佔用；預設案例為 8 上 2:2、一出局一壘有人，退場 9 上 2:3、兩出局無人在壘。輸出 WPA、RE24、REW、gmLI、exLI、Span LI proxy、WPA/LI proxy 與 SD／MD；只有端點時不可可靠計算的 inLI、Clutch 明確顯示 unavailable。
- 後端 `leverage_lab_service.py` 從年度 DuckDB 正規賽逐打席建立經驗 LI state table，RE24 使用 `delta_pitcher_run_exp`，後援定義為該隊該場非第一位投手；HTTP request 使用依 DuckDB／reference mtime 失效的記憶體快取。WPA 已於後續全域稽核改為相鄰打席起點 WE 差，最後一個 PA 接到比賽終局 0／1，不再逐球累加 `delta_home_win_exp`。
- Reference 使用 `data/Reliever/2025_reliever_wpa.csv` 與 `2026_reliever_wpa.csv`，以 MLBAM ID 對齊 Local Estimate，檢驗 WPA、±WPA、RE24、pLI、inLI、gmLI、exLI、Pulls、WPA/LI、Clutch、SD、MD。回歸只作診斷，不會強制校正 leaderboard。
- 修正後以 2025 reference 固定校準 `+WPA × 0.936080`、`-WPA × 1.030875`，同一係數套用 2026；MLBAM ID 奇偶 holdout 的 WPA corr 約 0.975–0.977、MAE 約 0.104–0.111。2025 full smoke：WPA R² 0.953／MAE 0.107／bias -0.017（原錯誤逐球加總 R² 0.726／MAE 0.316／bias +0.307）、+WPA R² 0.996、-WPA R² 0.999、RE24 R² 0.795、pLI R² 0.976、gmLI R² 0.984、SD R² 0.994。2026 本機逐球截止 2026-09-13，reference 與本機可能不同截止日，因此計數型驗證標為 provisional。
- 全域 WPA 稽核同步修正 Starter Rotation、Pitcher Personal、Batter game log、Team Impact Plays、首頁高 WPA 影片與 Sequence downstream WPA。共用 `wpa_service.py` 以 PA boundary 產生唯一 WPA；影片只取 PA 終結球，Sequence 與 game totals 每個 PA 只計一次。
- 2026 蒐集 reference 含部分沒有本機後援出賽的先發投手。API 會排除這些 reference-only 球員並提出 warning；混合先發／後援球員的 reference 仍可能包含先發局數，不可把 2026 計數型誤差全解讀為模型誤差。
- API：`GET /api/leverage/overview?year=...`、`POST /api/leverage/calculator`。新 panel 全部使用直角邊框，leaderboard 姓名含頭像並連至 Pitcher Personal（RP）。

---

## 十二、可參考的專案文件

### 2026-09-26 Data Freshness 與 Project Tracker

- `/admin/updates`（Per aspera ad astra）已新增 `Freshness & page impact`：同時顯示 dataset 截止日、來源截止日、自動化方式、warning，以及每個頁面依賴哪些資料。
- `backend/app/services/data_freshness_service.py` 是資料新鮮度報告的單一產生器。每次完整 daily update 結束、或後台手動更新工作結束後，會產生 `data/admin_job_logs/data_freshness_latest.json`、`DATA_FRESHNESS.md` 與 timestamped history JSON。這些是 runtime artifact，不進 Git。
- 狀態語意固定為 `current | expected_lag | source_pending | partial | stale | manual | unverified | unavailable | live`；不可只用檔案修改時間冒充資料截止日。
- `/admin/updates` 已新增 `Plans, slices & completion`，資料源為 Git 追蹤的 `docs/PROJECT_TRACKER.json`；進度由 `done slices / scoped slices` 自動計算，沒有切 Slice 的構想顯示為 IDEA，不虛構完成百分比。
- `docs/PROJECT_TRACKER.md` 由 `backend/scripts/sync_project_tracker.py` 產生；JSON 必須先更新，再重建 Markdown。後台的 `Copy handoff summary` 可直接複製同一份摘要供新對話使用。
- 已收錄 Batter Comparison Slice 0–9、Plus Leaderboards Slice 0–6、RE24 & Leverage、Daily Data Reliability、Project Tracker、Stamina v2 Slice 7–12，以及尚未切 Slice 的 Player Salary & Value idea。
- 新 API：`GET /api/admin/data-freshness`、`POST /api/admin/data-freshness/refresh`、`GET /api/admin/project-tracker`。

- `docs/PLUS_METRICS_CONTRACT.md`：Plus 指標正式契約。
- `docs/PITCHING_PLUS_DESIGN.md`：Pitching+ 設計。
- `docs/API_CONTRACTS.md`：API 契約。
- `docs/ARCHITECTURE.md` 或根目錄 `ARCHITECTURE.md`：架構參考。
- `docs/AGENT_WORKFLOW.md`：協作流程。
- `docs/PROJECT_STATUS.md`：部分內容較舊，只可作歷史參考；本交接文件的最新狀態優先。

---

## 十三、新對話第一輪建議行動

不要重做Stamina既有資料基礎、Observed Game Stamina+、Batter Personal或Batter Comparison Slice 0–9。直接：

1. 以UTF-8完整閱讀本文件與`docs/PROJECT_TRACKER.json`；只有本輪涉及打者研究時才另外載入`docs/BATTER_SWING_TIMING_ROADMAP.md`。
2. 執行`git status --short`，辨識目前未提交檔案，不可覆蓋或回復不相關內容；並確認沒有歷史Plus backfill worker仍在背景執行。
3. Stamina現行契約是`stamina_observed_game_state_v1_1`。先閱讀`stamina_lab_service.py`的Slice 8–11與`_build_game_states`、Stamina schema及`stamina.vue`；不要恢復已移除的3×3或cold-start未來預測。
4. Game Stamina+只表示該場已觀測第21–100球相對2025條件預期的Stuff+維持狀態；100為聯盟平均，包含80% interval、reliability、family拆分與3／5場整季趨勢。不得解讀為下一場預測或直接生理量測。
5. 所有缺值維持null／unavailable，不補0；描述性family曲線不可冒充已校正或因果結果。
6. 修改後只跑UTF-8、targeted backend tests、frontend typecheck與必要smoke checks；不要再次用長時間瀏覽器等待拖慢交付，也不要在運行中的Nuxt上執行build。
7. 若本輪新增／完成／阻塞／延期任何計畫或Slice，更新`docs/PROJECT_TRACKER.json`，再執行`python backend/scripts/sync_project_tracker.py`；不可讓後台進度與實際工作分離。
