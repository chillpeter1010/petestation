# API Contracts

## Decision Support16.1–16.3探索回測（2026-11-21，最新）

Build-time新增`exploratoryReplay`，來源`petehub_pitcher_decision_exploratory_v1.json`。不新增HTTP API。`replay`列2022–24同隊跨SP／RP冷卻回放、各角色提醒／早局／未知／同邊界與提前對應；不是正式多燈換投建議或正確率。`caseFlow`為固定MD5前32場全部共同截點，不依實際行動／收益挑場；`candidateCoverage`含名義人選列、自身歷史及逐欄coverage，當場候補live欄位NaN。`bridgeValidation/selection`六個共同截點actual-actor前推模型（base/rich），排序只2022/23，2024重用診斷。

`scenarios`下一完整organic PA／固定半局兩終點獨立：兩方案選定投手留半局、均勻名義RP池、256共同路徑、MAX32PA。`pa/half_supported`要求own-history／訓練人選群支持、無外推／截尾且最大缺轉移機率<=.01；灰點數值仍可診斷，不視為支持。第三出局後殘壘必須轉終止post_base=0。首PA可用現任live／自身候補近期閉合歷史，後續base清live，更新模擬球數及訓練局中休息；前三棒過去棒次預測後回過去聯盟先驗。未含IBB／獨立跑者事件／後續換投／長期成本，非原15.4後續行為策略。點`*_mc95_*`只含配對模擬誤差，`scenarios.*.wpa.interval`為支持案例均值的比賽群聚描述區間，不是因果收益。`sensitivity`在兩側共同支持案例計方向改變，分母不可混用或加總重疊點。

`timeline`32場沿官方歷史的凍結WE／WPA；`phase=anchor`為共同截點（重算WE、預定打者），`before/after`為事後實際局面。新增`shadowWarnings`與`scenarios`，舊`researchPoints`契約留版。黃色提醒與藍色實際換投分軌；提醒以decisionId選anchor，避免與上一PA after同x誤選。元件SVG clip／title ID每實例唯一，未知曲線保留缺口。

正式效益`formal_efficacy_passed=false`、`recommendation_allowed=false`、`individual_ranking_allowed=false`、`test2025_outcomes_examined=false`；原15.4資格與SMD未變、SNIPS／DR未估。進度51/58、16父項in_progress、16.1–3done、17–21planned。UI驗收使用者本人執行。

## Decision Support 15.5.1–15.5.4 PE與有限預測修訂（2026-11-21，最新）

新增build-time `peRevision`，來源`petehub_pitcher_decision_pe_revision_v1.json`，獨立於`entryReview`、`rpTargetResearch`及舊模型／燈號。`coverage`四年角色分母／欄位支持／打線預測身分吻合盤點，`folds`三年×兩角色的`pa/run/warnings/paired_binary_reference`，`selection`、`primary2024`、`balance_reference`及`methodNotes`留版。新增15.5.1–4四子項，完成48/55；16加15.5.4依賴但仍planned，2025封存。0正式推薦、未估策略收益、不新增HTTP API或線上訓練。

`decision_pe_features_v1`從原546880共同截點取得特徵。PA版PE代理採固定事件權重single-.88/double-1.25/triple-1.58/HR-2.03/walk-.69/HBP-.72，出局+.5（sac_fly例外），最後一球前count貢獻.5*sign(S-B)、已知EV≥95為-.5／≤80為+.5。揮空獨立特徵，不把逐球與打席分數重複加總；這是PA適配，不是論文精確重現或生理疲勞。無接觸EV貢獻0，接觸缺EV未知。最近1/2/3完整PA、3PA分數斜率，缺值打斷窗口；部分累積附known coverage。近期強擊球率以PA為分母、無接觸0／接觸缺EV未知；好球份額只計明列的strike/ball描述，不把fair inplay當好球。所有prefix嚴格早於anchor。

FF只取四縫線，最後已完成PA FF均值減已觀測prefix均值，未用全場最後平均。個人PE及FF參考各取同pitcher/role進場前最近50筆合格PA，至少10才有均值，保留entry reference time及支持量；新PE參考未宣稱為BF條件生理模型，既有球數／角色正常過程殘差仍在共同基準。

預定下一至三棒由全部已完成官方PA依九棒次循環、各slot最近已出現球員推估，零球及IBB同樣占棒次；首輪未看過的棒次身分未知。未讀事後首發表、實際下一PA打者或未來代打；forecast id只作歷史先驗查詢及事後吻合盤點，不直接作類別predictor、不按吻合篩樣本。打者九結果歷史只在anchor前ASOF，收縮20到前一UTC日已完成PA的聯盟先驗；沒有日參考時Laplace1均勻未資訊先驗，不能叫觀測值。未知身分／無自身歷史有獨立lineup_status。D是負荷／恢復，預定下一打者／相性另列，舊15.4字典錯誤不改其hash。

主要標籤`y_pa`為原投手下一完整自然PA的九類結果；輔助`y_run`為該PA開始到結束期間是否失分，不是anchor至半局終點。需要actual single physical actor=outgoing、未當下換投、PA start≥anchor、完整結束≤game close、organic及有效比分增量；當下換下／時鐘或actor不合仍NaN，不接接任結果。實際下一打者及future score只用於標籤／診斷，不入predictor。

`decision_pe_models_v1/protocol.json`在擬合前凍結資料hash、特徵群、五個主設定與兩個輔助設定、模型／切分／排名／提醒規則。每role/year都由全部共同邊界按整場game-close前80%／late20%切分，跨界場排除，再取有標籤的fit/cal；fit超過60000時固定自然抽樣，同fold所有設定／任務用相同fit。補值、缺值旗標及尺度只fit學習資料；HGB原生缺值。晚期校準只用disjoint observed cal的溫度[.5,3]，沒有oversampling。

固定模型：HGB 7葉60迭代minleaf200/L2=10/lr.05；正則化線性SGD log_loss/L2 alpha.001/100iter/average；RF100棵depth8/minleaf100/maxfeatures.7。主PA：hgb_base、hgb_pe、hgb_full、linear_full、rf_full；HGB為特徵消融，三種完整設定同完整特徵比較演算法。輔助run僅hgb_base/full。兩角色×三年×(5+2)=42個擬合，非42個獨立驗證。完整群同時增加個人參考與預定打線，無法只憑總增益歸因單一欄位。

主要驗證母體固定SP全部及RP局中short_profile。2022/23按預測失敗fold數→平均九類LL→固定設定順序排序，該fold條件為對hgb_base配對LL之game×pitcher300次探索性95%區間upper<0、非出局ECE≤.03且無fit警告；排名可有winner但沒有支持。selection/confirmation_guard凍結後才產生2024模型／機率。2024已用過，僅診斷，2025維持封存。區間條件於固定模型及已觀測結果，不含重訓、不解MNAR或反事實、不保多重比較。九類LL、非出局Brier／AUC與輔助run Brier／AP各用同任務比較，不能跨標籤評輸贏。

研究風險提醒只用輔助run模型：過去全部late-cal邊界（包括標籤未知者）的已校準風險90百分位當cut；同半局／同登板連續兩個完整PA邊界、一登板最多一次、角色流內同隊2PA冷卻。這是SP/RP各自回放，未整合跨角色全域策略。首三局保留盤點，不用最終登板長度或五局門檻篩掉早期案例。所有score先出再對actual change／future labels盤點；未知後續不算誤報。提醒母體為角色全部邊界，RP主要預測母體為局中短型，分母不同。配對只涵蓋既有合法母體的實際換投，same-boundary與提前1–2PA且600秒內分開，吻合不代表正確、全事件召回或策略收益。

RP`paired_binary_reference`另在新舊均有原投手標籤的同一paired monitoring案例，比較原15.3二元機率與新九類推導的非出局機率；驗證樣本相同，訓練樣本／任務不同，不是純learner消融。原十球任務保留原產物，不入新排名。沒有重訓行動傾向／重算權重，`balance_reference`逐值承接15.4，預測支持不代表SMD改善或取得16資格。

## Decision Support 15.4 凍結前推與16資格（2026-11-21，歷史版本）

欄位勘誤（競賽PDF參考評估時補記）：既有四群D是負荷／恢復壓力，並非下一打者；相性與預定下一打者為另一資訊群。以下及凍結15.4 source／protocol內「下一打者D」文字對應有誤，原研究產物留版不改hash。共同截點已有load_relative等負荷特徵，待補的是四群顏色／持續性／價值的整合覆核及獨立的下一打者時點安全重建；9項SMD未通過的固定數值結果不變。

新增build-time `entryReview`，來源`petehub_pitcher_decision_entry_review_v1.json`／`decision_entry_review_v1/`。包含flow、9個primary_folds、72個balance_results、6個targets、12個flows、qualifications、barriers、strategy_contract、methodNotes。72是固定3年×(SP兩phase×2scheme＋RP兩phase×5subset×2scheme)的診斷列，不是新模型；new_models=0。44/51研究交付，16–21仍planned，slice16_entry_allowed=false；2025封存，不改原PA／xWPA／候選／燈號／推薦，不新增API／線上訓練。

協定在本輪重算前凍結source與17個既有manifest，1546份既有產物核對保留。SP固定15.2 hgb_full、全部SP，局間／局中分開；RP固定15.3 history_enriched、主要局中short_profile，其他既定subset敏感度。主要overlap及次要IPW(.05,.95)分開，豐富平衡基準不刪欄；沿既有SMD≤.1、兩臂ESS≥500、ECE≤.03且無fit warning，各主要phase的2022/23開發與2024診斷都須過。9個主要phase/year門檻全未過SMD，不能按2024挑一個較好的subset救援。2024早已看過、15.3亦曾修正事件映射，這輪不是獨立確認。

review_ledger逐點保存決策身分、固定母體、past_cell_support、initial_support、annual/development comparison資格、review_eligible及互斥review_rejection。initial_support只用當時母體、過去分格及有效機率；實際行動、未來Y／是否觀測不入選取。年度資格與review_rejection是事後研究稽核，不能作歷史時點可知訊號、觸發器或宣稱歷史預警回放。414962個前推邊界有318669個初步支持，研究／實作資格通過0；不是318669個可用建議。

RP主要兩任務×三年，各自對同一已觀測案例與自己的過去訓練常數比較Brier差，300次獨立抽game與pitcher再相乘權重的pigeonhole探索性95%百分位區間。六個區間均跨0。僅條件於已觀測結果、固定模型，不含重訓不確定性、不解決MNAR或反事實識別，不作多重比較保證。缺失原因、覆蓋、g≥.1加權／最壞界限／odds情境另列，未知Y仍NaN。方法參考：[Owen, The pigeonhole bootstrap (2007)](https://arxiv.org/abs/0712.1111)；本專案使用比賽與投手作兩個重抽維度，是研究應用，非策略有效保證。

16五項barriers分別為comparison_balance、multilight_predictive_support、common_clock_four_reason_value_replay、candidate_joint_support_availability、aligned_half_endpoint_followup；未過及尚未就緒分開。共同截點僅重建A/B/C，未來打者D不能借用；原較晚時點四群／價值／人選行為與半局label未宣稱已對齊。名義池快照非active／熱身／醫療可用名單。完成15.4不代表實作已齊或可以估收益。

strategy_contract明定未執行的16候選研究：同一合法index boundary，reference續投；research在原四群兩紅含A/B、成熟度／fresh-block持續性、原14.2價值／合法／可用性／支持全過時換投。接任採當時確認可用且有自身歷史／joint支持的名義RP等機率抽樣，未知／無可用支持則abstain；屬時機與池層級，不作最佳人選排名。原.005 delta、unsupported mass≤.01、MC95 lower>0、model-bootstrap80 lower>0及冷卻／去重保留。兩臂後續使用相同版本調度策略，需在共同時點重建／凍結，原舊時點版本不可代入。

主要策略終點為守方WE(同當前／即將開始半局自然終點)−WE(common anchor)；次要RE(anchor)−中間失分−RE(同終點)。包括所有中間play／IBB／跑壘與吸收終局、同WE/RE模型版本。下一PA nonout及future_ten偏離不能替代WPA／RE24策略終點。16須在資格過後凍結direct／SNIPS／DR相同joint支持、群聚區間與敏感度及推論最小支持；本輪沒有估任何策略收益，也沒有執行候選策略。後續先另立修訂協定補拒絕清單，禁止放寬門檻／用2024重選母體或開封2025。

## Decision Support 15.3 RP目標與受限母體（2026-11-21，歷史版本）

新增build-time `rpTargetResearch`，來源`petehub_pitcher_decision_rp_targets_v1.json`及`decision_rp_targets_v1/`。`flow`、四年`preparation.coverage`、`primary2024`、120個`balance_results`、60個`task_results`、20個`sensitivity2024`、`fit_tasks`與`methodNotes`獨立保存；`balance_results`是3年×2phase×5subset×2模型×2權重，非120個獨立模型。30任務產物包含明示的HGB或稀少任務常數退路。43/51工作完成，15.4及16–21仍planned，2025封存；不新增API／線上訓練，不改原xWPA、燈號或推薦。

共同截點與原RP可比cohort沿15.1，不是部署全集。進場前最近10次已結束RP登板，至少5次，歷史BF中位≤4且球數中位≤20為`short_profile`，其餘`extended_profile`，不足`history_unknown`；個人參考必須嚴格早於進場。固定all、known_history、short_profile、extended_profile及short_load（短型且當前球數／歷史球數及BF／歷史BF皆≤1.5）五母體，主要局中short_profile擬合前指定，不能按2024或本場最後登板長度挑選。short_load排除高負荷局面，不代表全部疲勞情境。

`next_pa`是原投手下一完整自然PA的既有canonical「非K／非other_out」二元結果：strikeout／strikeout_double_play為0、安打／HR／walk／HBP為1，其餘若出局數增加為0，否則1；與preparation的eligible_history一致，不等同純OBP、安打率或xWPA。同單一實體投手、開始≥anchor且完整結束後才有標籤。`future_ten`取第一個完全在anchor後的固定十球塊，編號ceil(同session已投球數/10)，相同當前session、開始≤8h、三個研究殘差皆可量測；Stuff≤-5或速度≤-.5或Location≤-5為1。不能跳過壞塊選較晚好塊，也不能直接稱生理疲勞。當下換下者兩任務皆未知，不接接任投手的結果。未知Y保留NaN。

paired_monitoring為每個已知完成球塊的第一個決策機會，無完整球塊時每登板留一個起始機會，選取只用當時資訊；另報全部邊界覆蓋、登板及唯一未來球塊數，重複球塊／同場／同投手不是獨立樣本。固定HGB7葉60迭代minleaf200、L2=10及late-time Platt；整場80/20 fit/cal、跨界場排除，所有label早於次年前推anchor。action用全部RP邊界，observation用全部有／無標籤監測，outcome只用已觀測監測。fit<300／cal<100、fit任一類<20／cal任一類<5或單類時，保存training-only Laplace常數退路，不稱擬合改善。每任務僅與自身過去常數基準比較，不能跨目標Brier評輸贏。

新舊15.2行動機率在相同固定母體、同一豐富平衡基準含新增歷史欄位檢查，overlap主要、IPW(.05,.95)次要；過去cell兩行動各≥10、兩臂ESS≥500、maxSMD≤.1及ECE≤.03是診斷門檻。`primary2024`未取得策略資格，不能挑其他2024subset事後改主要目標。缺失敏感度報g≥.1的逆觀測加權及caps、最壞界限、未知者預測odds×.5／1／2之總體情境；這些是假設敏感度，不補Y、不回饋模型、不識別換下後反事實。caps≥10在g≥.1時相同是預期結果，不是額外穩健性證據。

revision2明示修正：首次將來源raw事件錯當分組名稱，已知nextPA標籤全為1；原source／protocol／資料／30任務產物及2024診斷完整封`attempt0_label_mapping`。新增原始事件映射測試後按既有preparation規則修正並全重跑，未改特徵、模型、母體或門檻。新protocol及內層產物guard在修正版2024前保存，但2024已看過，始終只稱診斷，非獨立確認。source audit及使用者畫面驗收分開。

## Decision Support 15.1–15.2 共同截點與平衡修訂（2026-11-19，歷史版本）

新增build-time `overlapRevision`，來源 `petehub_pitcher_decision_overlap_revision_v1.json`（`decision_balance_revision_v1`）。flow、foundation、clock2024、missing2024、selection、selected、primary2024、all_results與methodNotes獨立於原 `overlapResearch`；不改原快照／模型／xWPA／signalLights／alertResearch，不新增API或線上訓練。新增15.1–15.4四規劃子項，42/51工作完成，16增加15.4依賴；15.3–15.4與16–21仍planned。

15.1共同觀測截點＝前一個全場已完成play結束+1ms，嚴格早於原官方事件／第一球、現任已進場且局面可重建才納入。546930個原邊界排除50個不能嚴格確認者，留546880；2024留138074。原事件時鐘與完整audit保留。共同風險集仍繼承原回溯合法／身分／完整play篩選，不保證早於未記錄的教練意圖，非部署母體。

新特徵不沿用較晚row：以截點ASOF重取所有實投球數、BF、72/120h其他場用球、投手同角色歷史能力及原因區段；總／同場累積時鐘相減，量測可灰。個人負荷中位數固定進場前，避免現任出賽整段誤作已閉合歷史。局中取前play已知出局／壘包／比分，局間依已知例行賽規則重設出局及自動跑者壘包，不推斷跑者／下一打者身分；下一打者能力與舊時點WE/LI不回填。牛棚僅截點前名義RP快照，扣除已登板者，保留snapshot age與unknown，非完整active／熱身／健康可調度集合。

2024 RP局間舊時點落後共同截點中位續投132.6秒／換投91.9秒，局中27.9／61.5秒。差異方向依情境變動，不直接當作疲勞或估計其造成多少舊失衡。原15缺失原因屬事後標籤audit，永不入模型：RP缺16630中，當下換投4641、後續投球機會不足10553、量測／參考不足1267、支持範圍外142、區段／session缺口27。有量測2485。固定完整未來塊可能需要10–19球，機會不足包含後續換下；未觀測future_bad仍null。沒有開始15.3的新RP目標或觀測模型。

15.2預定4設定×2離場角色×2情境×3前推年度＝48模型。HGB固定7葉60迭代＋late-time Platt；核心／完整樣條logit固定C=.1、4節點二次曲線及onehot；矩條件平衡logit為固定受限研究實作，最小化IPW平衡矩與L2，150迭代及係數限制，非官方CBPS或精確平衡保證。數值中位補值／缺值旗標、尺度與曲線只fit學習分段；同phase整場80/20時間分學習／校準，跨界場剔除，所有label早於次年前驗證anchor。無class balancing或未來標籤特徵。

每模型都以相同豐富數值、缺值、類別基準檢查，核心消融不能省略移除欄位；兩組內常數但均值不同視完全分離並以有限尺度下限1e-8阻擋，不略過。過去cell兩行動各>=10為共同支持；主要overlap權重A=1用1-e、A=0用e，目標為可比較情境母體。次要IPW保留e∈[.05,.95]，權重1/e或1/(1-e)，不同目標分開，不依結果挑母體或直接與舊15點數／SMD宣稱改善百分比。門檻每role/phase兩組ESS>=500、最大絕對SMD<=.1、ECE<=.03、無收斂警告，僅研究診斷。

只讀2022/23前推排序：依失敗phase/year數、平均最大SMD、LL及固定次序，每角色一設定且兩情境共用。selection／confirmation_guard在2024輸出之前凍結；兩角色HGB最穩定，但內層4個phase/year完整門檻均未過，沒有晉升資格。2024主要overlap最大SMD為SP局間.195／局中.148、RP.255／.108，仍未過.1；部分2024 logit較好也不改選。2024已用診斷，不稱新獨立測試；2025結果封存。模型比較不估計疲勞／策略因果效應。

首次兩個2022 HGB fit後的IPW診斷遇pandas唯讀mask錯誤，原source/protocol/模型／機率／split封attempt0_readonly_mask；revision2只複製mask後篩選，不改模型、門檻、母體或排序，2024前完成修正。保留矩條件模型收斂警告，不反覆加迭代到2024過關。

完整 `decision_common_clock_v1/` 與 `decision_balance_revision_v1/` 各有protocol／manifest／source hashes、逐點重取特徵／時點排除／缺失原因、splits／48模型／機率／所有96個scheme結果及選擇guard。Lab#overlap-revision展示最新研究，原15收合保留#overlap-research；所有推薦／排名開關仍關閉，原11／0及多燈0有效研究候選未變。後續15.3→15.4→16，不能由研究工作完成宣稱可操作。source-only audit不等於平衡／策略或畫面通過，畫面使用者驗收。

## Decision Support Slice15 選擇偏差／重疊研究（2026-11-19）

build-time `overlapResearch` 讀 `petehub_pitcher_decision_overlap_v1.json`；版本 `decision_overlap_v1` 加顯式 `pool_probability_revision=explicit_outside_pool_mass_v2`。新增flow、逐年roles、weight_sensitivity、candidate_support、combination_observation_sensitivity2024及fixed32。完整balance欄位留研究檔，小型快照只留主要統計與最失衡欄位。這不新增HTTP API、不改原signalLights／alertResearch／xWPA，不觸發線上訓練。

546,930個2021–24回溯合法／身分／已完成play邊界、54,669換投，恢復38個原池外實際接替案例。仍有回溯cohort限制與強制換投排除，不是部署coverage。只用離場者／候選自己的決策前資訊；incoming ID、changed及chosen只當標籤；不依一般PA結果或轉移標籤可用性再選母體。game_closed_at作保守label available。2021→22、21–22→23、21–23→24，各學習段先80%整場時間fit、後段cal，跨界場剔除；所有訓練label均早於驗證首決策。2025結果不開啟。

調度e=P(change|X)、觀測g=P(全未來量測有效|X)用固定HGB7/60＋late-time Platt，分離場SP/RP。監測每完整block只取第一個合法邊界，目標anchor>=decision且編號最多來源+2，Stuff／球速／Location三量測全有才R=1；R=0為未觀測，future_bad仍null，不填正常。2021監測只有晚季凍結分塊分數，不以全年率直接比較年度。

候選池為nominal_eligible且previous_role=RP、過去relief>0；池內人選用固定L2條件softmax＋late-time溫度，僅採候選過去負荷／角色與出賽歷史，未涵蓋完整投打相性或真實熱身／健康。原二階段分數條件於RP池，原18模型／96檔core_manifest保存；診斷後另凍結pool_mass_v2加6模型估計s=P(in RP pool|change,X)。最終人選機率e*s*conditional_actor，池外e*(1-s)、續投1-e，總和1；RP池為空時s=0，不硬把池外動作攤入池內。這是顯式估計對象補正，非新的獨立2024驗證。

主要重疊e∈[.05,.95]且過去角色×局數×球數×LI分格兩行動各>=10；另列.01/.1與cap10/20/50。IP行動權重1/e或1/(1-e)，ESS=(sum w)^2/sum(w²)各行動另列，非比賽數。平衡含數值、缺值及類別均值，最大絕對SMD<=.1且每行動ESS>=500才過研究診斷。2024SP保留14691/96630（15.2%），ESS1943／8769、SMD.209；RP31196/41457（75.2%）、ESS4062／15948、SMD.296；兩角色均未過。AUC只衡量歷史選擇可預測性，不能當換投正確率或權重可用證據。

每候選初篩：條件機率>=.02、修正聯合機率>=.005、自身過去被選>=20、RP登板>=5及過去分格支持。`statistical_support` 只是初篩，不保證全域平衡或真實可調度；active／熱身／醫療／人工確認未知，operationally_available=0不表示實際無人可投。

觀測加權另以四群已知且g>=.1之母體作1/g。SP缺未來16828/38087，RP16630/19115；缺失不直接當疲勞或誤報。g>=.1使權重<=10，所以cap10/20/50相同屬範圍的必然，非穩健性證明。SP兩紅加權偏離率差29.1pp、比賽×投手200次重抽樣重算比率的描述95區間[-4.94,50.69]pp；RP此範圍無兩紅例，不硬算。`supported` 僅最低例數／有效draws門檻，非預測效度；稀疏例數不給區間。觀測權重依賴不可由資料證明的MAR／可交換條件，不能補出未觀測反事實或證明策略收益。

固定32場2376原始、1791有分數、633過初步重疊；1737可算值中604過初步重疊，但全域平衡仍未過，不能稱604則有效建議。原11／0、多燈0有效候選及recommendation_allowed=false／individual_ranking_allowed=false保留。40/47僅研究工作完成，下一步另立傾向平衡修訂或限定母體協定，過關後才安排16策略與終點；不自動進16或開封2025。

完整兩研究目錄 `decision_overlap_v1/`、`decision_overlap_pool_revision_v2/` 保存protocol／core_manifest／manifest、split、模型、機率、逐點／候選／monitoring、平衡與截斷敏感度。首次nullable dtype在transformer即拒、無模型／預測，原稿封存，revision2只修float/NaN後才擬合。來源／時鐘／機率質量audit另存；Lab#overlap-research畫面由使用者驗收，source檢查不等於模型效益或畫面通過。

## Decision Support 14.2.2–14.2.4 正常進程／分燈／事件契約（2026-11-19，現行研究版）

`signalLights` 優先讀 `petehub_pitcher_decision_signal_lights_v2.json`（`decision_signal_lights_calibrated_tails_v2`），缺新版才回v1。`calibrationSummary` 含 `blocks`、`actorRows`、`normal2024`、`outcomeModels`、`replay`，證據另存 `petehub_pitcher_decision_signal_calibration_v1.json`。仍是build-time研究快照，不新增HTTP API或線上預測。v1資料、969份先前凍結研究產物及原14.2的11預警／0配對保留；舊三份顯示源碼按原SHA存入新研究目錄 `previous_display_contract/`。

四季244,179個完整非重疊10球塊，545,204個有機PA actor特徵。球塊須10個有效且相鄰的session位置，移除身分衝突PA；個人參考以進場前同人／角色／球種／Plus模型版本至少20球為準。SP滿35球且本場<=100、RP滿10球且<=60，A需Stuff與球速各>=8筆、B位置>=8、C至少4次出棒且有接觸紀錄，混合量測版本灰。這是研究支持範圍，非疲勞門檻或全面OOD保證。

正常進程固定Ridge100＋球數／局間時間splines，控制累積／單局用球、局間時間、局數、球種配比、嚴格過去打者K能力及個人參考；C再條件於該已觀測塊球質／位置／球速，只作描述性殘差。4個時間窗各角色先80%已閉合比賽時鐘擬合、後段校準，跨界比賽剔除，所有label在評估窗前。正常MSE未勝個人參考者保留零預期差（C用fit均值）；保存預期差及額外殘差，非直接把正常下降當雜訊刪除。EWMA=.3只用已完成區段，缺區段重設濾波，跨局保留累積負荷。

A為Stuff／球速負向標準化殘差最大值（同群一票），B為位置負向、C為條件接觸率正向。分燈黃／紅以過去校準90／97.5百分位且超過半／完整實務幅度：Stuff及Location 5 Plus點、球速0.5mph、接觸率0.15。D對每方案自己的同角色最近10次已閉合登板中位用球（至少5次），由當日相對負荷、其他場72／120h負荷、進場連續登板與休息計算midrank CDF的聯合尾端，再用過去校準百分位及預先指定實務比值／連投日門檻。14日觀測不完整、個人參考不足則灰；跨局不抹掉D，D不等於疲勞真值。

當前A/B/C只連精確outgoing actor的已完成球塊，`available_at < decision_at`；incoming A/B/C未知，不繼承離場者狀態。個人參考 `personal_reference_at < entry_at`，D參考在現任進場或incoming假設決策前；資料年齡及缺值mask共同加入control／A／B／C／D／all，預處理只fit學習分段。先2022／2023前推固定排序，再2024同分母比較；SP92,013與RP45,686。所有新增方案均未通過相對共同control及實際保留模型的LL群聚區間／Brier／ECE／子群／穩定性門檻，因此保留SP原global與RP原rich tree+temperature，不改第一PA或原值模擬。不能稱疲勞特徵已提升換投效益。

區段末的平滑風險目標為「下一相鄰完整10球塊」超過實務幅度的額外偏離；無未來塊設限，非0。PA邊界的組合目標不同：下一編號塊可能已開始，必須ASOF FORWARD第一個 `target_anchor >= decision_at` 的全未來塊，最多比來源block晚兩個編號，A/B三項量測全有才給label。C當下代理不等於下個打者掌握度，後續真實球質／球種絕不回填成預測特徵。僅觀測續投者，仍有存活／缺失選擇偏差。2024六組平滑比較皆未通過同時勝不平滑與常數的群聚區間門檻。

多燈事件：四群皆支持、至少兩紅且含A或B，兩個新的相鄰10球block ID確認；重複PA讀同block不能當獨立證據。灰重設入場連續數、暫停活躍事件但不算恢復；兩個新塊A/B綠、C非紅才解除，D可仍高，解除後同登板可再成事件。session或登板結束仍活躍者設限，不稱已恢復。兩紅／三紅候選只用2022／23的全未來量測風險選支持（至少20旗標塊／10登板、正向群聚97.5區間與逐年非負提升），不依官方換投配對選參數；兩角色皆未通過，兩紅保留為探索狀態規則，三紅SP僅3例、RP0不能推論。

`SignalGates.validation?: unknown|pass|fail` 新增獨立預測支持條件，缺欄位視unknown，與 `value/legal/availability/statePersistence` 分開；實際資料validation=fail、availability=unknown。顏色的 `calibrated=true` 僅代表過去尾端校準，並非預測／生理／策略效度。0–8等權總分仍展示；任一灰使score=null，灰不補0。全部條件通過也僅是研究展示候選，`recommendationAllowed=false` 固定；demo手動假設通過須明示示範。

固定32場2,376邊界、1,737可算、842四群可判讀（SP591/1242、RP251/495），1次SP描述性持續事件、0觀測解除／新增研究候選／對應／操作推薦、208官方換投。新候選另外要求組合預測支持與原收益門檻、名義合法、每事件一次及同隊2已完成PA冷卻；可用性仍未知。官方匹配保留原同邊界或提前1–2守備PA且600秒、同場／隊／離場登板的一對一窗口，沒有為配對調寬。導航36例＝原11＋固定MD5前24＋明示狀態事件，不作統計分母；原11／0不能與新結果相加。本32場無觀測恢復，解除重啟只有規則測試，不能宣稱早期錯警降低已驗證。

39/47研究工作完成，15–20仍planned，2024已用診斷、2025結果封存；下一步15檢查調度／續投選擇偏差、重疊／有效樣本及稀疏區間，需另行開始。`data/research/decision_signal_calibration_v1/` 保留四份協定、fit/cal時鐘、模型、機率、逐塊／actor／事件與拒絕原因、manifest及audit。首次序列化guard在fit前失敗，原稿封存在attempt0，revision2才擬合；不得靜默修改凍結方法。畫面由使用者驗收，source檢查不等於畫面通過。

## Decision Support 14.2.1 多原因燈／景氣式綜合狀態展示契約（2026-11-19，歷史v1）

build-time `signalLights` 來自 `petehub_pitcher_decision_signal_lights_v1.json`，目前只是研究展示契約，不新增API、重訓、預警或正式推薦。A球質、B位置／控球代理、C對手掌握、D負荷／恢復每群一票；gmLI／相性另作脈絡，球速與Stuff等同群不重複加票。綠0、黃1、紅2，0–8分：0綠、1–2黃綠、3–4黃、5–6橙、7–8紅。分數與門檻尚未校準，不是官方景氣分數或風險機率。

任何灰、支持不足或真實未校準輸入都使該群灰，`score=null`／總燈灰；仍保留已知分數／異常群，不把灰補0或縮小分母。綠只指目前未見異常，不能當健康證明；紅不直接觸發換投。展示候選暫定四群皆可判讀、至少兩紅且含A或B、原因持續，並通過收益／名義合法／實際可用；高總分不能略過任何條件，`recommendationAllowed`永遠false。

原11則實際研究快照只讀來源轉接，A–D全部校準pending而維持灰，7則16–33球未達現行35球觀測支持。35是SP觀測支持門檻，不是疲勞切點；現任SP基準尚未採用已驗證的當日下滑特徵。實際收益通過原14.2門檻只顯示戰術比較，不能當原因持續；active／熱身／醫療未知，不能由名義合法推出可調度。`demo`模式允許手動指定燈與條件，須始終標記示範，不能混入實際研究結果或改寫模型。

14.2.1只完成顯示與規則契約；新增14.2.2正常進程／局間與去雜訊、14.2.3分燈／相關及SP／RP增益驗證、14.2.4解除／重啟與固定時序覆核。15新增14.2.4依賴，20消費已驗證契約作正式雙層燈號。新進度36/47，14.2.2–4及15–20尚未開始，2025封存；原14.2的11預警／0配對及969份舊凍結產物保留。畫面驗收由使用者執行。

## Decision Support Slice14.2 連續時序／研究預警／官方對應契約（2026-11-19）

版本 `decision_alerts_v1`；新增build-time `alertResearch`，小型完整摘要 `petehub_pitcher_decision_alert_research_v1.json`。不新增API、即時訓練或操作推薦。固定2024 prepared母體按MD5(game_pk)前32場，不按官方換投、模型收益或賽果選場；不作全季或獨立測試推論。原2,376個PA/play原始邊界全留，1,791個既有cohort邊界、1,737個具可算選項；既有cohort含回溯身分／實際接替者核對，不能當部署母體coverage。2025結果不開啟。

新core `build_decision_alert_research.py`／`decision_alert_rules.py`，protocol在正式模擬／配對前凍結自身源碼、規則、選場、原始時序／事件／輸入與模型SHA。沿14.1.1選定角色：SP無通過候選時為13.1修訂global，RP tree_rich_7＋溫度；僅第一PA使用新RP特徵，全部後續global／訓練期聯盟打者回退。角色名義池均勻抽人，不新增最佳類型或個別排名。原256路徑、8份共同比賽refit、轉移／WE／RE／用球參考不改；新時序每場SHA(seed:game)亂數在兩方案及9模型共用，沒有用原484點的亂數直接宣稱逐點版本差。

固定工程研究規則：中央ΔxWPA>=0.005（+0.5pp），配對MC95及模型中央80下界>0；全部9模型無截尾／外推，最差模型的平均缺轉移機率<=.01。RE24另報不作調參。這不是訓練出的最優門檻。相同登板、同守備半局、相鄰原始邊界連續2點成立才發，缺資料／不合法／支持不足都中斷；發出後同隊2個已完成守備PA冷卻、每登板最多1則。原始邊界序號用於相鄰／缺口；提前及冷卻用嚴格之前已完成且batter-faced的PA計數，零球IBB計PA、非打者／未完成play不增加PA。

純預警狀態機不接官方換投事件或未來結果；官方events只供後段回溯對應。同game／team／離場appearance；官方身分及event_index正好對上boundary prelude才稱同邊界，不冒充提前預測。另允許提前1–2個已完成守備PA、0<秒差<=600。依預警時序先同邊界、否則最早合格未用事件；每預警／事件最多一對，不事後挑最近或調窗口。

原始 `point_ledger` 保存全部邊界的cohort／選項／估值／模擬支持／門檻及run_length、冷卻、去重原因；`alerts`為實際發出的獨立研究預警，保留未配對；`matches`只有一對一成功對應；`event_ledger`保存32場全部官方pitching substitution，包括mid-PA／未知身分／不可算，另存同邊界與固定窗口的可算機會、matched alert及未配對原因。`flow`分開原始、prepared、modeled、simulation-supported、qualifying、persistent點、unique alert、官方event、同邊界／提前／未配對；persistent點數仍可能被去重／冷卻壓下，不等於預警數。

`recommendation_allowed=false`、`individual_ranking_allowed=false`、操作推薦數0。active／熱身／醫療／人工可用性、未觀測續投、後續打線時點及長期成本限制延續。對應率不代表合理率／因果收益，未配對預警不直接當錯誤；教練行動不是最優真值。點區間不是序列整體錯警控制。15–16才做選擇偏差／重疊與策略評估，17才開凍結後2025測試；本輪止於14.2，所有畫面由使用者本人驗收。

## Decision Support 13.6.1–13.6.3／14.1.1 補丁契約（2026-11-19）

此輪止於14.1.1；14.2／15仍待開始。新增build-time `modelPatchRevision`，由 `data/sample/petehub_pitcher_decision_model_patch_v3.json` 產生；不新增API或線上訓練。舊 `matchupRevision`、模型、協定及單場時間軸保留其版本，不將歷史頁面換成新版本卻沿用舊數字。

研究協定 `decision_model_diagnostics_v3`：2021→2022及2021–22→2023選設定，固定整場SHA pilot fit約30,000／cal至多約10,000，全年同分母驗證；線性四群×三L2及淺層HGB兩群×兩葉數，共16 learner設定／角色，每個比較raw／溫度模式。學習與校準依時間嚴格分開、跨界比賽排除；補值／尺度／編碼只fit學習段。每角色依內層log loss凍結六族候選，再移除pilot上限、用完整2021–23的時間切分fit／cal確認。2024已使用過，只能稱診斷；2025結果封存且沒有新調參回流。

`live_*_dev`為現任當場分數減100，替代者一律缺值；候補的同角色已閉合近期歷史保留在recent群，前次SP轉RP不當RP先驗。`option_plus_n`在現任是有效球數，在閉合歷史是有效登板數，禁止同單位收縮。current、recent、batter獨立加到共同基準；共同支持／年齡／scope控制相同，family高維分數不納入此精簡候選。這些界線不證明熱身或健康。

研究門檻同時要求相對舊角色基準的配對比賽×投手200次重抽樣、角色內多候選同時97.5%帶上界<0、Brier改善、ECE惡化<=.01、>=500列分群LL傷害<=.005、兩個內層年度相對同演算法基準傷害<=.005、無收斂警告。新增特徵另需勝過同演算法調整基準的LL同時帶及Brier，避免把更換演算法的增益歸給特徵。依凍結內層排序取第一個通過者，無通過則保留原版；這不是獨立最終確認。

訓練誤差為apparent error；逐類校準與年度／量測版本／scope分布只作診斷。固定模型群組置換在同月、現任／歷史及過去角色內聯合打亂，保留基準控制；是有限次模型依賴檢查，非條件重要性或疲勞／熟悉度因果。

14.1.1另版 `decision_action_sensitivity_v3` 僅對有通過候選的角色更動第一PA，後續維持原修訂global matchup。固定原484點、3880有支持選項、1556比較池、每方案256共同路徑及8個共同比賽重抽樣；沿原全訓練排序game的多項重抽樣計數，新增角色模型固定中央前處理／先驗，重訓learner，選用溫度時只在原校準段按同計數重校準。first PA預先快取並以重複列直接推論核對，原始與新產物各自manifest保存，不覆寫v2。原可用性／後續打線回退／狀態演化／長期成本限制繼續有效，支持範圍外與設限阻擋方向判定。`recommendationAllowed=false`、`individualRankingAllowed=false`；研究方向不等於預警數、正確率或實際換投配對。

本補丁僅建立2024診斷與敏感度；原2025／2026凍結機率檔仍屬v2，沒有冒充新候選已上線或完成最終測試。前端畫面由使用者本人驗收，source-only檢查不算畫面通過。

## Decision Support Slices 13.5／13.6／14.1 修訂契約（2026-11-18）

新增離線 `decision_batter_matchup_v1`（protocol revision2）、`decision_role_ablation_v2`（revision3）與 `decision_action_values_v2`，原v1及13.1–13.4不覆寫。`pitcherDecisionPlan.json.matchupRevision` 是build-time摘要：`coverage2024`、`roles`的同分母設定／LL／Brier／區間、`action`的484點方向對照、條件池、固定12例及用球；入口 `/lab/decision-support#matchup-revision`，無新增HTTP API、線上掃描／下載／訓練或正式推薦。

13.5 `observed_attack_YEAR` 以唯一 `request_id=decision_id` 對位實際被選actor；泛用 `attack_features` 亦可接 `decision_id:option_pitcher_id` 名義候選。只取已完成且 `available_at < decision_at` 的PA，零球IBB占PA窗、不製造投球。`game1/2/3`、`pair_game3`、`other_game3`、`team3` 與歷史pair／type／family分開；family收到占比的分母是收到球數，出棒率用該family有效描述球數，出棒組成用全部出棒，揮空／接觸／界外用出棒，EV／HardHit用有效場內EV，缺分母null。原始n、觀測時點、回退與粗類型支持保留。110個多打者或官方／實投身分衝突PA另存 `identity_exclusions_YEAR`，不進新歷史；來源未篩選初輪完整保留。

粗類型為過去同觀測角色last3閉合登板的手別×主導family×速球速度band，至少50球，無同季整季tag；這是廣義描述，不是已驗證最佳相性。BvP20PA→同打者type50PA→嚴格過去打者手別能力；family行為以有效分母20（EV10 BBE）收縮到過去手別／family聯盟參考。候選的過去SP球路描述可明示來源角色，但其SP三狀態／Plus不能冒充RP進場先驗。

13.5描述診斷獨立 `familiarity_identity_clean_v2` 協定，以原凍結curve cohort與乾淨PA統計的交集重算；保留初步描述。2021–2023 fit、2024驗證，接觸／揮空／EV對交手次數及此前實投曝光共12面板，200次比賽×投手重抽樣、面板內同時95%帶。反應期球數／位置／Plus／球類配比僅作描述調整，禁止當預測特徵；保留者選擇、多面板探索與心理鎖定／熟悉度因果限制。

13.6 `features_YEAR` 保留原 `option_role`（當時現任／候選過去觀測角色），新增 `forecast_role = is_current ? option_role : RP` 作本次角色分層。2024有285個接任者過去為SP；不能分到本次SP，跨角色三狀態／Plus及近期窗分數缺值。`observed_action`／PA結果不進設計矩陣；接任者不能使用被換下者prefix。前推risk以原決策cutoff重算，不能接較晚PA-anchor分數，候選entry risk仍缺值。原role分組／來源未清理的兩輪部分訓練、資料、源碼、協定另存，不依其分數調整門檻。

各角色25設定共用同一missing-aware有機PA／合法轉移分母；完整訊號baseline/all敏感度另報。共同基準控制支持n／年齡／scope；派生risk／交互項隨來源移除，去type時BvP先驗回打者能力。純負荷72／120小時、連投、季內序號對照不含後續複合risk。補值／尺度／編碼只fit2021–2023，固定L2=.001、能力收縮20。200次比賽×投手配對Poisson bootstrap，角色內全部設定LL同時97.5%帶及兩角色校正；晉級需上界<0、Brier改善、>=500PA分群無LL惡化>.005且無收斂警告。僅預定累加設定可選，all另須完整支持敏感度改善；2024是診斷選擇，2025仍是封存最終測試，2026僅評分。

14.1重跑原484研究點，角色池及至少兩位有支持的手別／粗類型池分開。已知第一打者使用選定角色模型（未通過則13.1修訂基準）；後續全部回修訂global matchup，不把未知未來狀態固定到半局末。事後存檔打序缺乏獨立的當時公開證明，後續全部明示原2023年底聯盟打者池回退，不讀實際未來打序／代打。game名單、active名單時點、名義法定合法、熱身／醫療／人工確認分列，不推出個別可調度。

九類PA結果接原合法runner轉移／凍結WE與RE，同一半局終點或再見，Δ為替代池減續投。每方案256共同亂數路徑、8次共同比賽分類器重訓；MC95與中央80模型範圍分開，後者固定前處理／轉移／WE／RE，無隱藏混雜校正。截尾、球數／首PA特徵外推阻擋方向，稀有轉移缺失機率另報。`old_new_comparison.parquet`保存逐點舊／新差值與區間；固定前12個decision ID呈現案例，不挑有利結果。預計新增用球／BF及剩餘名義RP另列；負荷在決策時鐘固定並累加新球，無投球時間長度或完整長期預算模型，不任意加扣WPA／RE。條件池多次探索沒有選最佳池；研究點不是去重預警或合理性驗證，14.2及15未開始。所有 `recommendation_allowed=false`、`individual_ranking_allowed=false`。

## Decision Support Slices 13.1–13.4 修訂觀測與條件下降（2026-11-18）

離線版本 `decision_role_observation_v2` 保留全部舊v1模型、協定與產物；新增四份 `data/sample/petehub_pitcher_decision_slice13_1_v2.json` 至 `slice13_4_v2.json`。`frontend/data/pitcherDecisionPlan.json.roleObservationRevision` 是小型 build-time 摘要，不新增HTTP路由、不在請求時掃描原始資料或訓練。Lab新增 `#role-revision`，兩幅SVG在 `/research/decision-role-observation-v2/decline_SP_2024.svg` 與 `decline_RP_2024.svg`。畫面與操作待使用者人工驗收。

13.1以完成時間嚴格早於決策重建24／72／120／168／336小時負荷；窗口不足／來源時鐘異常保留缺值及原始計數。`consecutive_days` 統一為實際現任／假定候選進場前的連續紐約登板日，不把當日或前次session的streak混入；決策日投球／登板streak、零球進場、同日其他登板、季內序號、本場／其他場負荷、進場休息與live idle分欄。824,462邊界的現任／候選合計10,415,470列；原固定白名單基準另版重訓，五日窗未提前加入選模。

13.2 `current_features_YEAR` 是原決策前現任actor；`pa_features_YEAR` 是實際單一actor首顆實投前的觀測，不能互換。prefix／最近十球球質、位置價值、物理量、CSW／揮空／接觸／界外／場內及有效擊球品質、已完成PA結果、同球種變化／個人歷史參考均附n與來源時間。三項狀態保存原35／10球暖機、100／60上限、>8h session重啟與模型相容限制，缺值不填正常。Location不是已知目標下的控球精準度。

13.3 `recent_history`、`recent_profiles_YEAR`、`recent_links_YEAR` 保存同角色已閉合登板，272,905去重profile連到全部選項。last1／3／5與近72／120小時「已閉合且可用」摘要和實投完成時間負荷窗不同；Plus／三狀態須版本相容。每指標保留有效登板n，原始有效球數在history，n<2不給均值描述性80%範圍；觀測時間是登板／狀態終點，不宣稱每項有效量測都在該瞬間。沒有近期資料不等於狀態正常或今日準備完成。

13.4曲線限2021–2023建立、2024驗證，SP／RP×7指標×4曝光軸共56面板，使用名冊投手、可確認actor／時間與實際slot。BF代理、打序slot交手、同打者交手及投球曝光分開；反應期球種配比僅作描述調整，禁止作風險預測特徵。200次比賽×投手重抽樣的面板內同時95%帶，附200PA／50登板／30投手支持門檻、實務下降幅度與相鄰兩區段及2024同區段重現要求；目前0面板重現。個人歷史曲線有部分收縮，尚無已驗證個人切點。

下一十球風險目標為同session未來十顆實投均值較前十顆下降至少5個研究Plus點，各窗至少8筆有效測量。時間前推L2模型只在訓練內末20%比賽校準；不足未來球／測量者為設限，不補負類。2024四項模型的Brier較球數基準改善，但目標含抽樣波動／回歸均值，僅適用已觀測續投，不是低於個人基準、疲勞、失分或換投價值。2025／2026只有凍結機率，未檢視結果。13.5／13.6／14.1／14.2未開始，舊半局55／12方向未重跑；`recommendation_allowed=false`、`individual_ranking_allowed=false`。

協定revision3、原序列化guard及漏名冊篩選的初輪模型／源碼另存；門檻與白名單未按2024調整。`data/research/decision_role_observation_v2/manifest.json` 遞迴保存263份產物SHA；兩個正式Plus metadata不改寫。完整重現步驟見主文件新增13.1–13.4節。

## Decision Support Slices 13–14 研究結果與時間軸（2026-11-18，原v1歷史）

`decision_ablation_v1` 保存 `features_YEAR`、完整支持 cohort 十個基準／Plus／三項狀態／leave-one-out 模型及全分母 missing-aware baseline/all。實際換投特徵對位接任者；Plus 必須為同 fold、嚴格早於決策的已結束登板摘要，現任才使用本次 prefix。各比較控制相同支持年齡、n、可靠度、scope、缺值及分母；僅 fit 2021–2023，2024 作設定診斷，2025／2026 僅保存預測。完整支持176,027／77,794：Plus小幅增益，三項單獨／合併未通過。全分母All對自身支持基準改善，不代表優於原Slice12的所有指標；正式模型不晉升。

`decision_action_values_v1` 在2024固定分層與兩場hash選取範例上建立 `cases`／`options`／`supported_cases`、訓練期打者／用球參考、8個比賽群聚分類器、9組情境結果及 `action_values_2024`。比較現任續投至半局結束 vs 從至少兩位有過去RP角色與足夠自身歷史的名義池均勻選一人投至半局結束。沒有後續換人，遵守最低打者與局末例外；熱身、醫療與精確當日異動未知。第一打者當時已知，後續以2023年底聯盟打者池的相同身分抽樣配對，不讀實際未來打序或投球。

每列提供 `wpa_continue/pool/delta`（勝率單位，顯示pp乘100）、`re24_continue/pool/delta`（分、守方正向）、差值的 `*_mc_se/mc95_low/mc95_high`、`*_bootstrap80_low/high`、`censored_paths`、`extrapolated_fraction`、`unsupported_mass`、`simulation_supported`、`research_direction`。256條配對模擬的MC95衡量抽樣誤差；8次分類器重抽樣的中央80%僅為固定前處理／轉移／WE／RE下的描述性範圍，沒有完整模型與隱藏混雜涵蓋。任何模型的路徑截尾或球數範圍外推均阻擋受支持方向；`research_direction=pool_higher|continue_higher|uncertain_or_unsupported` 是研究比較，`recommendation_allowed=false`／`individual_ranking_allowed=false`。499邊界中484個可建池，439個無截尾／外推，方向55／12／417；不可當作聯盟平均效果。

`traces.json` 與小型證據的 `timeline.games` 含兩場完整官方PA前／後研究WE點、官方換投事件及研究比較列。點以 `decisionId`、官方 `atBat`、`phase=before|after`、事件順序 `x`、`homeWe`、事後 `homeWpa`、比分／出局／壘包與投打身分對位。缺可靠局面留null斷線；不以平滑插值改寫WE。實際換投保存 `eventId`、事件時間、incoming/outgoing IDs與x；上軌實際事件、下軌決策前研究點。事後WPA／描述只作回溯展示，不進預測。只讀參考 `C:/intern/data_fixed/wpa_fixed__peter_0821/stats-master/frontend/src/components/GameWinProbabilityChart.tsx` 的Momentum結構，保存參考源碼SHA，未沿用CPBL WE表。

`frontend/data/pitcherDecisionPlan.json` 新增 build-time `signalAblation`／`actionResearch` 精簡摘要；Lab使用 `DecisionResearchTimeline.vue`，沒有新增API或線上訓練副作用。In game尚未接線：未來由year/game_pk、pitcher_id、decision_id與官方PA/event_id對位，pitch_uid須沿既有驗證映射，禁止直接把eventIndex當pitch_number。精確同步留Slice19，正式建議仍須15–18與20驗證。新圖、hover／點選／鍵盤與窄螢幕皆待使用者人工驗收。

## Decision Support Slices 12.5–12.7 候選與基準（2026-11-18）

離線研究版本 `decision_baseline_v1.2` 存於 `data/research/decision_baseline_v1/`。`option_features_YEAR` 主鍵為 `(decision_id, option_pitcher_id)`，包含現任與名義候選，統一投打歷史率／n／回退、角色與角色已知旗標、用球／休息、歷史可用時間、三項狀態與 scope。現任使用當次 prefix，候選使用此前已結束登板；後者不是準備度。候選角色為此前觀測角色，未知時 RP 參考回退；`warmup_available`／`body_available` 保留 null，`individual_ranking_allowed=false`。逐欄 coverage 按年度、現任／候選與角色提供非空分子及分母，決策層另提供至少一位／全部候選有能力或三項狀態的計數。能力率的非空涵蓋 frozen-reference 回退，不等於個人歷史充分。

`observed_features_YEAR` 依實際接任者 ID 對位當時可知的選項特徵。ID、觀測結果、後續實測球質及三項狀態不在本批三層基準白名單。局面 → 加用球／負荷 → 加投打能力，預測九類一般打席結果及合法 `(runs, final_outs, final_bases)` 聯合轉移；故意四壞另分流。補值、missing indicator、標準化、類別編碼與轉移參考僅 fit 2021–2023，2024 選 L2／收縮並列 log loss、Brier、逐類校準與按比賽群聚的不確定性。2025／2026 僅凍結評分，不檢視結果指標，最終測試仍在 Slice 17。

`validation_2024_LEVEL`／`predictions_YEAR_LEVEL` 保存原始九類機率、合法轉移預期失分、下一打席預期 WPA／RE24、未支持類別質量；機率和為 1，合法轉移內重新正規化，包含再見時非全壘打得分不得超過致勝分的約束。WPA 使用勝率單位，顯示百分點時乘 100；RE24 為守方正向的分數。未到 Slice 14 固定半局策略，不能作換投因果效益或個別候選排名。`protocol.json` 凍結白名單、時間切分與實作／輸入 SHA；`validation.json` 保存設定、收斂、有效分母及診斷。兩次中止的協定及部分模型保存在 `attempt1_nullable_category_failure/`、`attempt2_terminal_constraint_revision/`；v1.2 明列原協定 SHA，修正 nullable boolean 編碼及再見限制，未變更時間切分、特徵或選模規則。

`frontend/data/pitcherDecisionPlan.json.baselineResearch` 為 build-time 精簡摘要（逐年 coverage、樣本流向、三層驗證、保留層與協定 SHA）；頁面無新 HTTP API、下載或訓練副作用。完整證據為 `data/sample/petehub_pitcher_decision_slice12_5_v1.json` 至 `slice12_7_v1.json`；視覺驗收由使用者執行。

## Decision Support Slices 12.1–12.4 離線特徵（2026-11-18）

離線版本 `decision_preparation_v1` 保留原 Slice 11 資料，依 `decision_id` 新增 `boundary_review_YEAR`、`clean_labels_YEAR`、`decision_matchup_YEAR`、`player_ability_features_YEAR`、`signal_features_YEAR`、`prepared_features_YEAR` 及 `field_coverage_YEAR`。清洗後標籤保存一般打席適用旗標、從決策點起算的得分／出局／壘包及凍結研究 WE／RE 定價；故意四壞另有標記，缺可靠終點時保留空值。

投打能力分為投手 SP／RP 與打者 BAT，依此前已完成打席建立九類結果次數／比率。可用時間為打席完成與最後投球完成時間的較晚者，ASOF 使用嚴格小於決策點的歷史；同時刻資料先合併再累計。結果類別互斥且比率和為 1。先用自身手別拆分，再用自身 All，最後使用訓練參考期的整體分布。回退狀態、原始自身樣本、截止時間皆保存；2021 暖機內無歷史／參考者留空。中途換投、身分歧義、非名冊投手與故意四壞等排除原因逐列保存。

手別取已保存官方比賽快照，gameData 的列冊屬性可能事後修訂。左右開弓的預期站側採選項投手反側假設，原始 listed_bats 與歷史打席實際站側各自保存。當前決策不能讀稍後才投出的球；Stuff／Location 摘要只聚合該登板嚴格更早、通過來源對位的已完成投球，附有效 n、模型版本與 cutoff。三項狀態及原近似 80% 區間／收縮權重沿用已發布值。

Coverage 以年度×SP/RP×續投/換投及逐欄分母保存非空、有效支持、真零；候選另列決策×候選分母及至少一位有值的決策數。此段記錄準備階段契約，後續候選整合與前處理見上節。前端僅取得產生的精簡研究快照，無新增訓練／預警 HTTP API。

## RE24 Lab 球隊換投／代打觀測結果（2026-11-18）

`GET /api/leverage/overview?year=2025|2026` 增加球員 `entry_wpa_low/mid/high` 及 `team_pitching_rows`／`team_pinch_hit_rows`。球員新欄以每段後援接手第一筆可見投球的本機 gmLI 分為 <1、1 至 2（含端點）、>2；整段 WPA 按接手分組。原收集參考表只有球季統計，這三欄回 null。

球隊換投以同場實投投手身分切換辨識接手段，排除開場先發，按實際出賽隊伍加總接任段結果。每段 WPA 使用現有校正式；RE24 採逐球 `delta_pitcher_run_exp` 加總。指標缺局部來源時整段該指標留空；`wpa_n`／`re24_n` 是各指標分母。gmLI 分組不補缺值，來源為同季描述性 Leverage Lab 局面表。零球換投不在逐球辨識範圍。

代打只計官方事件明列的 pinch hitter 開始前換入且同一球員完成該打席；排除打席中換投及未完成／未對位的情形。WPA／RE24 取進攻方方向，公告數獨立揭露。資料來自 `export_leverage_pinch_hits.py` 產生的兩季離線快照，回應附 `pinch_hit_data_as_of`。每次平均各用自身有效數。這些是觀測結果，未校正教練選擇偏差；未來建模需另定固定範圍及時間切分。

## Pitcher Decision Slice 11 決策樣本（2026-11-18）

無新增 HTTP API。Lab 快照增加逐年續投／換投數、原始與納入分母及半局 WPA 覆蓋。離線 `pitcher_decision_sample_v1` 以 `decision_id` 對齊合法名義選擇邊界、前置特徵、候選和實際行動標籤。半局結果依官方事件順序取得最後可靠局面；終點時間異常或結果缺漏維持空值。原始排除原因保留，候選名義集合不視為已證實當場可用。

## Swing Timing 回歸研究區（2026-11-15）

既有 `GET /api/batters/lab/swing-timing` 新增可選 `include_regression=false`；一般排行榜不執行額外回歸軸聚合。使用者展開「指標散點圖與回歸分析」時才傳 true，原查詢條件與最低 PA／Swing 門檻完整保留。回應 leaderboard 新增 `axis_metrics`／`axis_samples`（一般查詢為空），filters 新增 `axis_options`：保留 Stuff Attack 原 20 軸，加 21 項 K／BB 與三維對位軸，再加 Age／Season PA／Filtered Swings／Filtered Terminal PA 共 45 個不重複選項。此區不套用 Stuff Attack 的 Stuff+ 分箱門檻，原 Stuff Attack 功能不改。

事件軸依同年度正式 regular-season DB 精確鍵去重、球種／左右投打／打者球隊／投手球隊篩選；competitive 棒速門檻來自全季，再於選定條件內聚合。共用原 `_add_metric_flags` 情境定義（球種、球數、站側、投手手別、粗位置）與相同 Adjusted 置中公式；以向量化群組統計避免逐球員重複掃描。對位、Whiff、棒速、Ideal、K／BB 等重疊軸直接沿用本排行榜數值；距離／時間偏差以表格相同的絕對幅度供回歸，Attack Angle／RV／K−BB 等有方向的值保留符號。無法取得的軸維持缺值，指定對方球隊時 X／Y／Z 對位仍依既有契約缺值。

前端共用 `linearRegression.ts` 之單變量 OLS／Pearson r／R²／斜率／Student-t 雙尾 p；使用實際值、所有符合條件與姓名搜尋且 X／Y 有限的球員，不截前 200 名、不以缺值填零、不按 PA 加權。顯示合格／有效／排除樣本數；同軸或少於三人停用、無變異提示不能估計。換條件或軸清除舊結果，使用 request ID 拒絕過期回應，關閉折疊區卸載。原排行榜 PR／上色不改回歸資料尺度。16 項相關 Python 測試與 JS 數學檢查完成；正式 DB 首次聚合約 2.575 秒、同條件快取約 0.004 秒，不含瀏覽器。無畫面驗收。

## Swing Timing 五項篩選統計（2026-11-15）

`/batters/lab/swing-timing` 的 Horizontal／Timing／Vertical 共用主欄位在 Swing 後、Avg Miss Dist. 前加入 Avg Bat Speed、Ideal Bat Angle%、K%、BB%、K−BB%。沿用實際值／PR／Heatmap 與欄頭排序，表格使用可水平捲動的 1572px 最小寬度並填滿較寬容器；畫面待使用者驗收。

既有 timing API 的 leaderboard 新增 nullable `ideal_attack_angle_pct`／`k_pct`／`bb_pct`／`k_bb_pct`，填入既有 `avg_bat_speed`，並提供 `context_pa`／`bat_speed_swings`／`attack_angle_swings`。資料來自正式球季逐球 DB，以球種群／球種、投手手別、打者站側、打者球隊、投手球隊精確篩選；不使用整季排行榜 K／BB 替代條件結果。原 PA 欄與最低 PA 篩選仍是整季樣本，欄位提示另顯示新增數據的實際分母。

Avg Bat Speed 沿用 competitive swings 棒速口徑：門檻為球員整季非觸擊揮棒棒速第 10 百分位，或棒速≥60 mph 且擊球初速≥90 mph，再於當前條件內取合格棒速平均。Ideal Bat Angle% 沿用專案 Stuff Attack 的 Attack Angle 5°–20°（含邊界），分母為條件內有該欄位的非觸擊揮棒，並非 launch angle 或整季比例。K／BB 分母為條件內終結 PA（球種依最後一球），保留沒有追蹤的 PA，排除 truncated_pa；BB 含 intent_walk、不含 HBP，K 含 strikeout_double_play，K−BB 為百分點差。精確投球鍵去重，未知來源／零分母留 null，不從 summary 對位比例推算。新增 SQL 聚合依來源 DB mtime／size／WAL 版本快取；summary model 用 copy 合併，避免污染 Savant 既有快取。

實際 DB 2026 李灝宇：全條件棒速 71.348、Ideal 51.033%、K 23.901%、BB 8.242%、K−BB 15.659%（364 PA）；FF＋R 棒速 70.450、Ideal 30.275%、K 27.119%、BB 22.034%、K−BB 5.085%（59 PA）。指定 NYY 同樣精確篩選，但原 X／Y／Z summary 指標仍遵循既有 event 模式缺值契約。

## Batter Period 篩選、逐球分數與影片（2026-11-15）

`pitch_result=Hit` 僅保留該球形成 single／double／triple／home_run 的終結球；`pa_result=Hit` 先依日期窗內終結結果選出安打 PA，再與球種／球數／左右手等逐球條件取交集，保留該 PA 中符合條件的球。AVG 仍僅由面板內終結打數 H／AB 計算，不能把最終 PA 結果回填到前面的每一球；無終結 AB 顯示缺值而非零。

比較頁讀取正式逐球 Stuff／Location 快取，依既有精確投球鍵對位，未覆蓋仍留缺值，不訓練或補造分數。Discipline rows 保留影片識別／URL、投球鍵、balls／strikes／is_swing／zone，點選事件由 ZonePanel → Section → Board 傳到 PeriodDiscipline，使用既有 ComparisonPeriodVideos 解析播放器；換篩選清空選球。這不代表遠端影片保證可播放。Null 進階分數不轉成 0。

同球員年度來源快取最多 8 組、120 秒時間桶，依來源 DB／WAL、分數快取／WAL 與 Stuff metadata 的路徑、mtime、size 失效；回傳 copy 防止篩選污染。面板 flags 每次資料集只計一次，不變更統計口徑。2026 李灝宇（701678）6/12 前 0-0：87 球，終結 AB 8／H 0；PA Hit 保留 17 顆 0-0 球，Pitch Hit 為 0。該 87 球皆有正式 Stuff／Location／影片映射。量測同一服務查詢原約 1.713 秒，修改後冷載 1.610 秒、重複 0.703 秒；不含 HTTP／瀏覽器渲染。人工畫面驗收待使用者。

## In game 熱圖改用 Batter Personal 逐球平滑（2026-11-15）

使用者指定直接共用 Batter Personal 熱圖，預設 Swing%／Heatmap Blend=100%。Game／Pitcher Personal In game 改讀既有 `GET /api/batters/personal/discipline` 的 `tables.location_points`；該表新增 `p_throws`／`stand` 供前端正確篩選，既有列與統計不變。使用所選年度整季打者資料，按投手手別及當前打擊側篩選，可選僅看當前球數；這是整季描述圖，不宣稱當時已知的情蒐預測。

`StrikeZoneScatter` 與 In game 共用 `pitchLocationHeatmap.ts` 的原有 64×52 逐球高斯平滑、bandwidth、密度淡出及 Personal 配色。Swing% 是局部加權揮棒比例，另可選 Density／Bat speed，不讀取舊九宮格／17 區 PR 基準。3D 依原 plate_x／plate_z 投影，僅反轉一次 Personal 的顯示 X，熱圖延伸範圍依實際平滑區域建立，保留真實好球帶邊界。原始投球、球路、影片與 Pitch Scout API 不變；舊分區 API 保留但不再供此圖上色。未做畫面／瀏覽器驗收。

## Pitcher Decision 歷史特徵 Slices 6–10（2026-11-14）

無新增 HTTP API。Lab 快照新增 `temporalResearch`，由 `data/sample/petehub_pitcher_decision_slice6_v1.json` 至 `slice10_v1.json` 摘要產生，包含凍結參考期、研究方法、各年覆蓋、2024 固定驗證與限制。頁面不執行補抓／訓練，不提供行動建議；新增畫面只由使用者驗收。

獨立離線研究根目錄為 `data/research/decision_support_temporal_20261114/`；正式 Plus／Stamina／Performance State 保留。`observations`、`features`、`scored` 是訓練／稽核用倉儲，含結果欄位，不可整列傳入決策模型。下游只能明列選用以下契約：

- `pitch_features_YEAR.parquet`：官方 event ID、投手／打者 ID、投球完成時間、物理／位置前置欄位、獨立研究 Plus、模型與 cutoff、來源／角色／打者身分一致性、暖機或缺值原因；不含全場結束、失分或下一狀態。
- `decision_states_YEAR.parquet`：每個決策僅接嚴格早於當下的已觀測 prefix；Quality／Physical／Command 各有分數、近似 80% 抽樣區間、收縮權重、模型與支援狀態。SP 至少 35 球、RP 至少 10 球，>8h 中斷須重新暖機；本版 SP 評到 100 球、RP 評到 60 球，超出範圍決策保留缺值。`reliability` 是 n/(n+20) 收縮權重，非校準正確機率。三項分開，沒有生理電量百分比。
- `context_features_YEAR.parquet`：每個官方決策一列，包括暖機列；研究中性 WE、收縮 RE、PA-LI、參考樣本／回退旗標及模型 cutoff。不可靠壘包或時間保留缺值，缺 LI 不補 1。研究 PA-LI 是過去完成打者轉移下的預期絕對 WE 波動，非 FanGraphs 精確復刻。
- `candidate_state_priors_YEAR.parquet`：候選在本次登板前已結束登板的最後觀測狀態；`prior_state_available_at=max(退出事件時間, 納入投球的完成時間)` 必須嚴格小於 cutoff。不是本場前五球、準備度預測或實際可用性證明；`individual_ranking_allowed=false`。
- `pitch_labels_YEAR.parquet`／`context_labels_YEAR.parquet`：另存實現結果及標籤可用時間。模型參考下的 WPA／守方 RE24 不等於換人因果效果；原始來源 WPA 保留在既有 play 表。

2021 上半年無可用研究 Plus／參考模型；prefix 模型另以 7–8 月暖機至 9 月。2024–2026 均使用截至 2023 年底的凍結模型，2025／2026 僅評分與覆蓋，未以其結果挑選模型。研究分數 100 是過去參考中心，當年中位數不保證 100；110 不代表改善 10%。狀態收縮後的當年標準差仍可不同。

`validation.json` 與 `manifest.json` 保存時間／唯一性／正式 metadata 保留檢查及產物 SHA。2024 驗證僅為參考模型與已觀測 prefix 的描述；下一段預測、xWPA／xRE24 行動模型、因果效果、個別牛棚排名與預警晉升仍關閉。Slice 6 另修正代跑誤改當下打者的 parser，僅更新事件／決策 `batter_id`；剩餘來源身分歧異另列，後續對戰研究須確認或排除。

## Pitcher Decision 資料層 Slices 2–5（2026-11-14）

無新增 HTTP API。Lab build-time 快照新增 `dataFoundation`，由 `data/sample/petehub_pitcher_decision_slice2_v1.json` 至 `slice5_v1.json` 產生；只包含修復摘要、逐年事件／負荷／名義候選覆蓋與限制，不載入大型 Parquet 或執行下載／訓練。

離線資料在 `data/research/decision_support_pipeline_20261114/`：`events_YEAR` 是官方 eventIndex 鍵（實投與非投球事件分開）；`plays_YEAR` 是單一結果歸屬；`decisions_YEAR` 是前置局面與規則狀態；`appearances_YEAR` 保留零球登板；`roster_YEAR` 是完整比賽名單，非事後出賽名單；`runners_YEAR` 保留官方 runner movement／responsible pitcher（僅結果用途）。結果 WPA／RE 不複製到每球或前置特徵；無法定價的相鄰 WE／RE 邊界保留 null。時鐘與來源修訂造成的 Statcast／官方逐球對位不得僅依 pitch_number 假定相同。

`workload_YEAR` 以 UTC 決策時點只計 t'<t 的全隊全角色實投；1／3／7／14 日為滾動小時窗。`workload_sessions`／`closed_role_history` 處理同日多場、>8h 中斷、連續日及封閉後才可知的登板總用球／角色歷史。早期資料、未知時間／壘包與 3 場來源時鐘異常保留旗標。

`bullpen_sets_YEAR`／`bullpen_candidates_YEAR` 是名義候選及其過去負荷。72 組 active-roster 指定日期來源覆核不等於全日期驗證；其餘為 `official_game_roster_date_unverified`，衝突／不足與非法／已使用／被換下者拒絕。熱身、醫療及精確同日異動均未知；`warmup_available`／`body_available` 保留 null，`individual_ranking_allowed=false`。這些資料不能宣稱完整的當下可用牛棚或最佳決策。

## Pitcher Decision Lab 規劃快照（2026-11-12）

Slice 1 更新：快照新增 `sourceAudit`，來源為版本化 `data/sample/petehub_pitcher_decision_slice1_audit_v1.json`，展示逐年完成賽程／本機 IDs／既有 feed／實投鍵差異／官方換投事件及兩場待查清單。此區是資料核對結果，不提供下載或修復動作；六份公開 schedule GET 不使用 API key／cookie。完整逐場問題、逐日覆蓋與來源 SHA 保存在 `data/research/decision_support_slice1_20261112/`，不由頁面讀取本機任意檔案。

`/lab/decision-support` 是研究規劃與離線結果摘要頁，由 `/lab?area=pitcher` 的 Pitcher Decision Lab 入口進入。頁面沒有新增 API、下載、模型訓練或預警執行功能；離線研究進度見上述 Slices 契約，不修改既有授權。

唯一 Slice 狀態來源為 `PROJECT_TRACKER.json` 的 `pitcher-decision-support`。執行 `backend/scripts/export_pitcher_decision_plan.py` 會驗證依賴順序，產生 `frontend/data/pitcherDecisionPlan.json` 的 build-time 規劃／覆蓋快照及 `docs/PITCHER_DECISION_SUPPORT.md`。資料是 2026-11-12 本機例行賽盤點；WPA／RE24／LI、逐球快取與合格先發場次有各自分母，不代表正式因果訓練資料。缺年度單場成績檔保留 null。未來模型 API 於相應 Slice 先定義契約再實作。

## In game prior-date context / Pitch scout v1（2026-11-09）

`GET /api/batters/personal/pitch-scout` 沿既有 batters API 授權。必要 query：`year,batter_id,pitcher_hand=L|R|All,stand=L|R,before_date=YYYY-MM-DD,balls=0..3,strikes=0..2`；選填 `previous_type,previous_result`，首球兩者為 `__first__`，相鄰前球不在未篩選來源中則 `__missing__`。**不接收當球球種、結果或落點。**

回應 `pitch_scout_context_v1`／`mode=historical_conditional_reference`，只讀所選年度正規賽、`game_date < before_date`（整個當日排除）。固定打者／投手手別／打者站側，先以 game／PA／pitcher／pitch_number 精確相鄰建立前球，缺號不跳接；排除 PO／IN、automatic penalties 與未知描述。打者過去完成 PA>30，採樣至少30球：exact count＋previous type/result → exact count＋previous family → exact count → broad count（兩好球優先、打者領先、投手領先、平手／淺球數）。每層樣本不足才退；全不足明示 insufficient_history，不補聯盟或假球員資料。

`heatmap` 只含 Swing／HardHit／Whiff／Contact／Called Strike 五率，沿原 Discipline flags／分母；HardHit只計有終局事件且有效EV的fair BBE。17區、17吋與逐球高度正規化、缺位置與高度fallback數保留。`benchmark_status=context_rates`：**絕對比率，不是PR**；每格分母至少5才上色，Whiff／Called Strike反向，缺格中性灰。原整季PR API不改，前端可切回。

Scout 回傳條件樣本數、Swing／Take百分比、歷史揮棒球種family分布、集中區標靶（該區至少3次揮棒及分母）。標靶是zone/group中心，非實測瞄準點；位置不隨當球落點移動，環的收縮僅由原球路progress驅動。未訓練或驗證預測模型，不輸出個人意圖、最佳配球、早晚／切球上下緣。回應包含 cutoff、tier、source_version；後端來源DB／WAL版本鍵LRU，前端64項／120秒、同請求合併、有限下一球預讀與late-response guard。冷情境未就緒時Play等待；Pause／切球／離頁取消待播，不修改歷史球路。原側欄Sequence仍是全季描述性branch，非此prior-date預測器。

## In game exact-count season context（2026-11-05）

`GET /api/games/matchup-context?year=2026&pitcher_id=...&batter_id=...&batter_side=L&pitcher_hand=R&balls=1&strikes=2` 沿用現有 API 授權。year 2021–2100、正球員 ID、side／hand `L|R|unknown`、balls 0–3、strikes 0–2；固定路徑先於 game_pk 動態路徑宣告。

回應 `in_game_count_matchup_v1`，scope 為 `regular_season_exact_pre_pitch_count`。包含年／投打 ID／本機解析姓名／手別／球數、source_status，以及 pitcher／batter 的 status、summary、pitch-type rows。投手統計為全季同球數對該側打者；打者為全季同球數對該手投手，不是 head-to-head，也不是目前比賽樣本。未知手別 `unknown_hand`，缺 split `no_data`，缺季資料 `unavailable`；零分母值 null，不偽造零。

每列有 pitches、usage_pct、有效球速均值、Strike／Zone／Swing／Contact／Whiff、AVG、wOBA、HardHit。AVG 使用唯一 PA 最後有結果球之 H/AB，先確定 terminal 再篩球數／手別，排除既有 NON_AB events；wOBA 只用來源 woba_value／正 woba_denom，無年度權重補值；HardHit 是 ≥95mph／有效初速 fair BBE。Contact／Whiff 分母為 swings；denominators 回 pitches、swings、ab、woba、tracked_bbe。列 pitches<30 標 limited，非可信度認證。非有限數值不入有效數據。

來源只讀 regular-season 必要欄位與本機 player lookup／master，姓名缺漏使用既有本機 timing map，不從網路批抓。Server LRU 128 以 DB／WAL mtime+size、季／球員／手別／球數失效；client 生命週期快取最多48組且 latest-request guard 防換球／換人舊回應覆蓋。既有 replay rows 同步補 batter_name／pitcher_name，不修改軌跡及影片契約。

## Shared Query Parameters

Most pitcher analysis endpoints should share these parameters where possible:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `team` | string | Optional team filter |
| `start_date` | string | ISO date |
| `end_date` | string | ISO date |
| `pitch_types` | string[] | Repeated query param |
| `stand` | string | `All`, `L`, `R` |
| `counts` | string[] | Count buckets or exact counts |
| `results` | string[] | Pitch or PA result buckets |

## Authentication and Ballpark profile

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `PATCH /api/auth/profile`

Registration accepts the existing `username` and `password` fields plus optional `favorite_team_id`. The value is either `null` or one of the 30 official MLB team IDs; unsupported IDs return validation error `422`. Authentication responses add `favorite_team_id`, derived `favorite_team_code`, and `avatar_setup_status` (`pending` or `default`).

`PATCH /api/auth/profile` is authenticated and partial. Sending `favorite_team_id: null` clears the home-team preference; omitting it preserves the current value. Sending `avatar_setup_status: "default"` records completion of the C1 neutral-avatar bootstrap, while omitting it preserves the current state. Full avatar appearance remains a D4 concern and is not stored by this contract.

## Official active roster

- `GET /api/teams/{team_code}/active-roster?year=2026`
- Optional `refresh=true` bypasses a fresh cache and attempts an official refresh.

Contract `official_active_roster_v1` reads only MLB StatsAPI `rosterType=active`; season participants, leaderboards and local pitch tables are never roster fallbacks. Each player exposes MLBAM ID, name, jersey number, position code/name/type and official status code/description. The response includes `retrieved_at`, nullable `source_as_of`, `cache_age_seconds`, a 30-minute `stale_after_seconds` threshold and explicit `fresh`, `stale` or `unavailable` freshness.

MLB StatsAPI does not publish a roster revision timestamp in this response, so `source_as_of` remains `null`; Petehub reports the honest retrieval time instead. A failed refresh returns a version-compatible disk cache as `stale` with a warning. With no valid cache it returns `unavailable` and an empty player list, never a reconstructed season roster.

## Recommended Endpoints

### Pitchers

- `GET /api/pitchers`
- `GET /api/pitchers/metric-explorer`
- `GET /api/pitchers/{pitcher_id}`

#### `GET /api/pitchers`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Defaults to `2026` |
| `role` | string | `SP` or `RP`; any non-`RP` value is treated as `SP` |

Response:

```json
[
  {
    "value": 650644,
    "label": "Aaron Civale (ATH)",
    "name": "Aaron Civale",
    "team": "ATH",
    "role": "SP",
    "games": 14,
    "starts": 14,
    "start_rate": 1.0
  }
]
```

#### `GET /api/pitchers/metric-explorer`

Returns one row per pitcher-season for the Pitcher Metric Explorer. Query parameter `year` selects the season. The response keeps only season-level fields and exposes a metric catalog with `key`, category, unit, direction and description so the client can safely populate arbitrary X/Y axes.

The first release joins traditional results/workload, standard estimator fields, season Stuff+／Location+／Pitching+, and the separately published 2026 Stamina signals by MLBAM ID. Missing joins remain `null`; they are never converted to zero. `source_status` reports whether the basic, Plus, advanced and Stamina sources were available. Regression is computed interactively by the client over the filtered complete-case pitcher sample and is descriptive rather than causal.

### Pitcher Personal

- `GET /api/personal/overview`
- `GET /api/personal/pitches`
- `GET /api/personal/discipline`
- `GET /api/personal/sequence`
- `GET /api/personal/movement`
- `GET /api/personal/rotation`
- `GET /api/personal/videos`
- `GET /api/personal/timing`

### Game Center

- `GET /api/games`
- `GET /api/games/{game_pk}/pitching`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/location`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/sequence`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/shape`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/replay`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/tags`

The game-detail response returns the line score, plate-appearance feed, batting box and pitching box for one local Statcast game. Batting rows use the official MLB boxscore `battingOrder` when available: the hundreds digit is the lineup slot and the remainder is the substitution sequence, so a `401` player is displayed under the `400` starter and a zero-PA defensive replacement is retained. `AVG` and `ERA` use the official boxscore `seasonStats` snapshot, which represents the cumulative season through that game; PA／AB／H／HR and the remaining box-score counting fields stay game-only. Official boxscores are cached atomically under the year-scoped local data directory. If that source is temporarily unavailable, the service falls back to completed-PA batting rotation and local through-date ERA; the batting fallback preserves lineup-slot grouping for players with a plate appearance but cannot invent a zero-PA substitute.

Location and Sequence are loaded from top-level Game Center tabs beside Feed and Box Score; both use a dropdown limited to pitchers who appeared in the selected game. They are restricted to the requested `game_pk` and pitcher and reuse the Personal analysis payload shapes and filters without allowing filtered rows to create artificial pitch adjacency. Requests are prefetched for the initially selected pitcher and deduplicated/cached briefly in the browser. The Tags endpoint is loaded only when a pitcher name receives hover or keyboard focus. It adapts the released Slice 3 season-role roster and may append versioned `practical_v1` Lab-first profiles (`Pronation`, `Supination`, and LHB/RHB More Breaking Balls or More Offspeed). Primary Pair remains in the frozen research artifact but is omitted from the read view and hover card. Every displayed item remains a full-season descriptive snapshot, not a through-game-date view; if the requested season has no assigned tag, the endpoint may return a separately labeled most-recent prior same-role reference and never presents that reference as current. Practical profiles do not alter the frozen Slice 3 data or downstream research artifacts. Pitch Out is excluded from Location and Sequence analysis.

`shape` is the lazy-loaded read path for the top-level Movement tab. One response contains game-only HB／IVB, compatible release X／Z fields, pitch/result/count/batter-side/catcher filter fields, Plus/Stamina context when cached, and the existing PA/pitch/video identity. The browser caches this unfiltered pitcher-game payload and applies Movement filters locally. Movement values are inches using the existing Petehub convention (`-pfx_x * 12`, `pfx_z * 12`); release position remains in the payload for compatibility, but Game Center no longer exposes a standalone Release Point tab. Pitch Out remains excluded.

`replay` is a separate lazy-loaded game/pitcher payload using contract `pitch_trajectory_statcast_v1`. It returns the same local filter fields and pitch/video identity plus a 31-point release-to-plate path for each valid pitch: `progress`, `time_seconds`, `x_ft`, `y_ft`, and `z_ft`. The backend first reconciles Statcast's actual `release_pos_*` with the velocity/acceleration state defined at 50 feet, then integrates to the front of home plate (`y = 17/12 ft`). Each pitch is explicitly labeled `supported`, `limited_trajectory`, or `unavailable`; a closure difference greater than three inches stays visible as limited data and is never pulled artificially to `plate_x/z`, while missing release/velocity/acceleration fields produce no path. Pitch Out and pitchless events are excluded. The browser caches the unfiltered response for five minutes and applies Replay filters locally. This is a ball-path reconstruction only—not body motion capture or full fluid-physics simulation.

### Batter Lab

- `GET /api/batters/lab/swing-timing`

#### `GET /api/batters/lab/swing-timing`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Available cached season; currently `2023`–`2026` |
| `pitch_group` | string | `all`, `fastball`, `breaking`, `offspeed`, `other` |
| `pitch_type` | string | Optional Statcast pitch code such as `FF`, `SL`, `CH` |
| `pitcher_hand` | string | `All`, `L`, `R` |
| `batter_side` | string | `All`, `L`, `R` |
| `batter_team` | string | Batter's season team code or `All` |
| `pitcher_team` | string | `All` 使用 Savant summary；球隊代碼使用本機精確逐球 matchup mode |
| `minimum_swings` | integer | Qualification threshold after filters |
| `minimum_plate_appearances` | integer | Season PA qualification threshold; `5`–`700`, normalized to steps of `5` |

Returns `league`, `leaderboard`, `data_mode`, filter options and sample metadata. All percentage fields use the `0–100` scale. Distances remain in inches and timing offsets in milliseconds. Rate fields are aggregated by swings; average miss distance is weighted by estimated whiffs, and conditional directional distances are weighted by their corresponding category counts.

The request path only reads local Savant summary caches under `data/MissDistance`; refreshing those caches is an explicit offline operation and does not occur during page requests.

`batter_team` is exact in summary mode. Selecting `pitcher_team` switches to exact local pitch-level matchups (`data_mode=matchup_event`). This mode returns exact tracked swings, Whiff, Competitive Rate, Bat Speed, Swing Length and attack metrics; X/Y/Z alignment and Flawed/Perfect remain null because those event-level fields are absent locally. Current pitch-level `miss_distance` coverage is 2026 only.

#### `GET /api/batters/lab/swing-timing/player`

Lazy-loaded V2 player detail endpoint. Accepts the same pitch, hand, side and pitcher-team filters plus `batter_id`. Returns player/league summary, pitch-type matrix and Bat-Speed Gear Change fields. The Lab calls it only when a leaderboard row is expanded.

#### `GET /api/personal/overview`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `role` | string | `SP` or `RP`; defaults to `SP` |
| `pitcher_id` | integer | MLBAM player id |

Response includes:

- `selected_pitcher`: pitcher option metadata from `/api/pitchers`
- `summary`: cards for `Team`, `GS`, `IP`, `ERA`, `Stuff+`, `WAR`
- `tables.dashboard`: the source dashboard row
- `tables.br`: the source BR / rotation row when available
- `tables.pitch_type_matrix`: pitch-level `Stuff+`, `Location+`, `Pitching+` matrix when available

#### `GET /api/personal/pitches`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `start_date` | string | Optional ISO date |
| `end_date` | string | Optional ISO date |
| `limit` | integer | Sample table row limit, capped at `1000` |

Response includes:

- `summary`: pitch count, game count, first game date, last game date
- `charts.pitch_type_distribution`: pitch type counts and rates
- `tables.sample_pitches`: limited pitch-level sample rows for debugging and downstream UI wiring

#### `GET /api/personal/movement`

Returns:

- `summary`: pitch count, pitcher hand, pitch type count
- `charts.movement_scatter`: horizontal/vertical break points for all valid filtered rows
- `tables.movement_summary`: pitch-level usage, movement, and velocity summary

#### `GET /api/personal/discipline`

Returns:

- `summary`: discipline metrics including swing, whiff, CSW, zone, chase, first-pitch strike
- `tables.discipline_summary`: one-row summary table
- `tables.stand_split`: L/R batter split table

#### `GET /api/personal/sequence`

2026-11-07: optional `previous_pitch` conditions anchor pitches on the immediately preceding `pitch_number` in the same game/PA, annotated before side/count/result filters. `__first__` selects pitch number 1 (no previous pitch); omitted/`All` preserves existing behavior. Gaps remain unavailable and do not borrow an earlier pitch. In game uses the pitcher's season scope plus current `stand`, exact `count` and this previous-pitch condition; `condition_count` is the current count and `condition_pitch=All`. `conditioned_count_pitch_mix` uses the existing Conditioned branch rule: retain matched anchors and their actual downstream PA rows/count descendants, without re-applying the previous-pitch predicate to those descendants. It does not filter on the currently selected pitch type or treat the distribution as a prediction.

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `start_date` | string | Optional ISO date |
| `end_date` | string | Optional ISO date |
| `current_pitch` | string | Optional pitch filter; defaults to `All` |

Returns:

- `summary`: filtered pitch snapshot
- `tables.shallow_sequences`: shallow-count sequence outcomes
- `tables.two_strike_sequences`: two-strike sequence outcomes

#### `GET /api/personal/rotation`

Returns:

- `summary`: game count, pitch count, total WPA
- `charts.wpa_games`: game-level WPA and cumulative WPA rows
- `tables.game_log`: game-level pitch/velo/spin/batter counts
- `tables.fatigue_by_inning`: inning-level fatigue proxy for selected or latest game

#### `GET /api/personal/videos`

Returns cached video links from DuckDB columns:

- `play_id`
- `video_url`

The endpoint does not call StatsAPI or Baseball Savant at request time.

#### Admin pitch-video backfill

- `POST /api/admin/jobs/backfill-video-lookup?year=2026&batch_size=50` queues the existing missing-game lookup worker only; it does not refresh pitches or recompute models. A queued/running video job is returned instead of queuing another (single backend process, including other seasons).
- `GET /api/admin/video-lookup-status?year=2026` adds `complete_games` / `missing_games` against that season's `games` table. A cached game counts as complete only when both pitch and player lookup rows exist, matching the worker's skip rule; this is not a per-pitch playback guarantee. `active_job` is global, `latest_job` is season-scoped, and `coverage_error` indicates a temporarily unreadable database, not zero coverage.
- `/admin/updates` exposes a dedicated start/resume button, persisted coverage refreshed every five seconds, partial-failure counts and retry guidance. Coverage updates after each 50-game save, not after every request. Job results remain available via `/api/admin/jobs/{job_id}` during the backend process lifetime.
- Closing/reloading the page does not cancel the backend job. The backend must stay running; after a restart the in-memory job status is lost, but saved CSV/DuckDB mappings are reused on the next explicit click. There is no automatic restart or durable queue claim.
- Both endpoints retain the router's server-side admin-role **and** exact `peter1010` username requirement. No backfill runs simply by opening the page. Play IDs/links come from official StatsAPI; missing or unplayable source videos are not fabricated.

#### `GET /api/personal/timing`

Returns Swing Timing / Miss Distance payloads when a yearly CSV exists under `data/MissDistance`.

- `summary`: swings, whiff rate, pitch type count
- `charts.x_timing_points`: tied-up / centered / flail points
- `charts.y_timing_points`: late / on-time / early points
- `charts.z_timing_points`: over / lined-up / under points
- `tables.timing_by_pitch`: pitch-level timing summary

### Starter Stuff

- `GET /api/stuff/leaderboard`
- `GET /api/stuff/pitch-shapes`
- `GET /api/stuff/pitcher-detail`

#### `GET /api/stuff/leaderboard`

Query parameters are `year`, `role=All|SP|RP`, `team`, and `minimum_ip`. The endpoint reads the atomic daily snapshot and never runs model inference during an HTTP request. It returns per-pitch-type Stuff+, Location+, and source-gated Pitching+ maps (`FA/SI/FC/FS/SL/CU/CH/KC/FO`), each season-level Plus score, `data_as_of`, model versions, warnings, and per-metric `source_status`.

Pitching+ overall and pitch-type values use the newest complete-feature export available. When its date trails the current pitch source, the response keeps the values, reports `source_status.pitching_plus=stale`, exposes `pitching_data_as_of`, and returns an explicit warning so the UI never implies that different metric cutoffs match.

### Pitching+ Lab

- `GET /api/pitching/overview`
- `GET /api/pitching/pitcher`

Both responses include `data_as_of`, `cache_status`, and warnings. The overview additionally reports `source_data_as_of`, so an incomplete newest tracking date is visible instead of silently presenting the export as current.

### RE24 & Leverage Lab

- `GET /api/leverage/overview?year=2025|2026`
- `POST /api/leverage/calculator`

The overview returns two explicitly separated reliever leaderboards: `estimated_rows` from the local regular-season pitch store and `reference_rows` from `data/Reliever/<year>_reliever_wpa.csv`. Local WPA is measured once per plate appearance from consecutive PA-boundary `home_win_exp` states; raw pitch-level `delta_home_win_exp` is never season-summed. A fixed 2025 component calibration (`+WPA × 0.936080`, `-WPA × 1.030875`) is applied to 2025 and 2026 and identified in `model_version`; it was stable under an MLBAM-ID parity holdout. Reference players without a local relief appearance are excluded, with a warning when mixed-role reference scope may still differ. The response also returns per-metric linear validation diagnostics (`correlation`, `r_squared`, `mae`, `rmse`, `bias`, `slope`, and `intercept`), local and reference timestamps, model version, warnings, and the empirically derived runs-per-win value.

The calculator accepts entry and exit inning, half, score, outs, and base occupancy. It estimates endpoint WPA, RE24, REW, gmLI, exLI, an endpoint span-LI proxy, WPA/LI proxy, and SD/MD result. `inLI` and Clutch remain unavailable because two endpoints do not contain the complete plate-appearance sequence required by those metrics. LI is an empirical Statcast state estimate and is not represented as an exact FanGraphs value.

### Stamina Lab

- `GET /api/stamina/overview?year=2026`
- `GET /api/stamina/research-curves?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/game-states?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/physical-stability?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/command-retention?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/incremental-validation?year=2026`
- `GET /api/stamina/season-summaries?year=2026`
- `GET /api/stamina/external-validation?year=2026`
- `GET /api/stamina/season-bias-repair?year=2026`
- `GET /api/stamina/leaderboard?year=2026`

The overview reads the generated `data/derived/stamina_lab_<year>.json` audit. Slice 11 retains league multi-signal family curves and exact-pitch-type early-reference diagnostics. `slice11_game_state` exposes observed-state v1.1: prior-season empirical-Bayes exact-type opening baselines, exact-pitch-type workload splines, fixed first-20-pitch family weights, inning-clustered uncertainty, single-game Overall/family Stamina+ and season-level diagnostics.

`research-curves` reads `stamina_v2_multisignal_<year>.parquet` and returns all game/window family rows for one starter so the client can select a game locally. Values are within-appearance deviations from at least three early pitches of the same exact pitch type; movement and release-point fields are unsigned distances from the early centroid. The response is descriptive, not a leaderboard or next-start forecast.

`game-states` reads `stamina_game_states_<year>.parquet` and `stamina_game_state_windows_<year>.parquet`. It returns each eligible start's Overall/Fastball/Breaking/Offspeed Game Stamina+, 80% interval, reliability, rolling 3/5-start state and 20-pitch-window retention. Overall requires 15 supported pitches after pitch 20 and at least 80% fixed opening-family coverage; each family requires 5 late pitches. An unobserved family keeps its opening weight, uses the league family-retention prior and adds uncertainty instead of being renormalized away. Unsupported values remain null.

`physical-stability` reads `stamina_physical_games_<year>.parquet` and `stamina_physical_windows_<year>.parquet`. Contract `stamina_physical_signal_contract_v1` compares every later pitch with at least three first-20 pitches of the same exact pitch type. Velocity, spin-vector, movement-vector, release-point, extension and arm-angle drift remain separate components; contract `stamina_physical_stability_v1` robustly standardizes them on 2023, uses fixed weights, partial pooling and an 80% interval. Missing fixed weight receives a league-neutral contribution and lowers reliability instead of becoming zero or being silently renormalized. The endpoint is research-only and describes public tracking stability, not injury risk, intent or physiology. Rebuild Slice 15–16 with `python backend/scripts/build_stamina_lab.py --year 2026 --physical-stability-only`.

`command-retention` reads `stamina_command_games_<year>.parquet` and `stamina_command_windows_<year>.parquet`. Contract `stamina_command_retention_contract_v1` uses at least three same-game first-20 exact-type pitches, a frozen 2023 early-Location/pitch-count/pitch-type Ridge expectation, and the fixed first-20 family mix. It returns Overall and family 20-pitch windows plus game-level Command Retention+, reliability and 80% intervals. Higher means Location+ held up better than expected; it is research-only and is not an injury, physiology or future-start prediction.

`incremental-validation` reads `stamina_incremental_validation_<year>.json`. Contract `stamina_incremental_validation_v1` fits on 2025 and evaluates on 2026: a 21–40 early-Quality baseline is compared with a challenger adding Physical Stability+ and Command Retention+ to explain 61–80 Quality retention. The response exposes matched coverage, RMSE, rank correlation, calibration, distinctness gates and `composite_release_eligible`. The current challenger did not improve RMSE, so no composite score is released.

The overview additionally exposes Slice 19 from `stamina_product_integration_<year>.json`. Contract `stamina_product_integration_v1` freezes the `keep_separate` product decision, representative-pitcher audit and personal-page rules. Pitcher Personal requests the existing game-state, physical-stability and command-retention endpoints in parallel, aligns them by game and preserves each signal's own interval and reliability. This does not create a new score or alter the leaderboard response.

`season-summaries` reads `stamina_season_summaries_<year>.parquet`. It reliability-weights the observed game scores, carries both measurement and between-game uncertainty into an 80% interval, and applies scope-level empirical-Bayes partial pooling. Contract `stamina_observed_season_state_v1_1` qualifies Overall with at least 10 eligible starts, 150 supported late pitches and season-level reliability of 0.70; family scopes require 8 eligible starts, 50 supported late pitches and the same season-level reliability floor. Mean single-game reliability remains diagnostic but is no longer a hard season-ranking veto because repeated starts can yield a precise season estimate even when individual games are noisy. Only qualified rows receive an unadjusted diagnostic rank.

`external-validation` reads the frozen game-state and season-summary artifacts for the requested year and its prior year. Contract `stamina_observed_external_validation_v1_1` checks coverage, pitch RMSE gain, game-level and season-level ceiling neutrality, within-game consistency, qualified support, season precision and weighting sensitivity under the v1.1 season gate. Cross-season pitcher rank is descriptive only and is not a release gate because the score measures season state rather than a permanent trait. The unadjusted season ceiling gate still fails as expected; the downstream frozen 2025 correction must pass its separate untouched-2026 audit before publication.

`season-bias-repair` exposes contract `stamina_observed_season_bias_repair_v1_1`. It fits separate Overall/Fastball/Breaking/Offspeed low-degree early-Stuff+/velocity splines with Ridge alpha 10 on v1.1-qualified 2025 summaries only, adds correction uncertainty from 100 bootstrap refits, and evaluates the frozen correction once on 2026. Adjusted rows are written to `stamina_adjusted_season_summaries_<year>.parquet`; official ranks additionally require row-level adjusted reliability of at least 0.70. The revised 2026 audit passed every gate: maximum ceiling correlation 0.114, minimum median reliability 0.814, maximum median 80% interval width 4.052, at least 132 qualified pitchers per scope, minimum weighted-vs-unweighted rho 0.983 and minimum retained score spread 0.615. Therefore `leaderboard_release_eligible=true`, with the explicit limitation that 2026 is the only untouched external season for this correction version.

`leaderboard` is the release-gated Slice 14 read path. It refuses a season unless its bias-repair audit is eligible and identifies that season as the untouched test year. Rows are Starter-only qualified Overall adjusted scores, ordered by the persisted official adjusted rank. The response also exposes starts, eligible Stamina games, average pitches, 80% interval, adjusted reliability, and separately qualified Fastball/Breaking/Offspeed scores; a family remains null when it fails its own support or adjusted-reliability gate. Research-only `quality_game_stamina_plus`, `physical_stability_plus` and `command_retention_plus` are separately calculated means that each require at least 10 eligible games; they remain null below that threshold and never change the official rank. Contract `stamina_observed_season_leaderboard_v1_1` currently publishes 149 Overall rows for 2026 and explicitly describes observed in-season retention rather than physiology or next-start prediction.

Game Stamina+ is an observed performance-retention index with league average 100. It describes only the pitches seen in that appearance, does not predict the next start, and is not presented as a permanent trait or direct physiological measurement. Depth and other physical signals remain separate explanatory fields.

The full artifact set is rebuilt outside HTTP requests with `python backend/scripts/build_stamina_lab.py --year <year>`. Slice 11 diagnostics use `--slice11-only`; the observed single-game and season timeline artifacts use `--game-state-only`; Slice 15–16 use `--physical-stability-only`; Slice 17–18 use `--command-validation-only`; Slice 19 uses `--product-integration-only`. If the season DuckDB changes after generation, the overview reports `dataset_status=stale` and warns that the research dataset must be rebuilt before modeling.

### Starter Discipline

- `GET /api/discipline/leaderboard`
- `GET /api/discipline/swing-map`
- `GET /api/discipline/pitcher-detail`

### Pitcher Similarity

- `GET /api/similarity/search`
- `POST /api/similarity/manual-shape`

### Pitcher Comparison

- `GET /api/comparison/period/options`
- `GET /api/comparison/period/date-range`
- `GET /api/comparison/period/overview`

Pitcher labels in `period/options` use the latest regular-season team found in the yearly pitch store; an older team value in the annual comparison CSV is only a fallback. Pitcher roles are also derived from regular-season appearances using the shared `GS / G > 0.3` rule, so a stale CSV role cannot classify a starter as a reliever. The cached comparison pool is keyed by both the comparison CSV and pitch-store modification times, so a daily data refresh invalidates stale team or role labels without requiring a service restart.

`period/date-range` additionally returns `current_team`, `transfer_count`, and chronological `team_stints`. A stint is a contiguous run of games for one team, so A → B → A is represented as three stints and two changes. Each stint includes `stint_index`, team, first/last appearance date, pitch count, game count, and a display label. The Period Comparison UI offers a one-click before/after comparison for two stints and explicit Period A／B stint selectors when more than two stints are detected.

Period overview player cards derive their team from pitches inside each requested window. A single-team window displays that team; a manual window spanning multiple teams displays `N Tms` and exposes the ordered team list in player metadata.

### Models

- `GET /api/models/movement`
- `GET /api/models/spin-breakdown`

### Pitcher Performance State Research

- `GET /api/performance-state/overview`
- `GET /api/performance-state/leaderboard?year=2026&role=SP|RP&target=process_collapse|result_collapse|return_to_baseline|strong_rebound&minimum_forecasts=5`
- `GET /api/performance-state/player?year=2026&pitcher_id=<id>&role=SP|RP`
- `GET /api/performance-state/shadow`
- `GET /api/performance-state/v2-audit`
- `GET /api/performance-state/v2-slice14-audit`
- `GET /api/performance-state/v2-slice15-audit`
- `GET /api/performance-state/v2-slice16-audit`
- `GET /api/performance-state/v2-slice17-audit`
- `GET /api/performance-state/v2-slice18-20-audit`
- `GET /api/performance-state/v2-slice21-22-audit`
- `GET /api/performance-state/v2-strict-2026-replay`
- `GET /api/performance-state/v2-lab?year=2026&role=SP|RP&target=process_collapse|result_collapse|return_to_baseline|strong_rebound&minimum_forecasts=5`

`overview` reads the precomputed Slices 0–9 audits. It exposes the frozen collapse/rebound label contract, appearance-level coverage, leakage-safe 2025 development, 2026 external diagnostics, role-pooled state-space diagnostics, Markov regimes, GAS+HAR volatility, the GJR-GARCH challenger, POT-EVT/CAViaR tail diagnostics, and separate collapse/rebound forecast validation. Slice 3A records actual pitcher-role calendar gaps, 2025-only timing-policy comparisons, explicit 60-day reset behavior, corrected five-day/calendar-day half-life units and the expanded low-persistence grid. HTTP requests never fit a model.

`player` returns the selected pitcher's role-specific appearance timeline with the actual days since the prior same-role appearance, observed process/result scores, single-game WPA／RE24／WPA-LI and per-PA forms, mean Stuff+／Location+, collapse/rebound labels, one-step state forecasts, filtered Stuff/Command/Result states, HMM prior/filtered regime probabilities, EWMA/GAS/GAS+HAR/GJR variance forecasts, EVT extreme probability/supported severity, CAViaR 95% loss quantile, and Slice 8 probabilities/alerts for each separate target. SP and RP histories remain separate for dual-role pitchers. These states are research-only performance estimates and do not overwrite Stamina+, diagnose fatigue or predict injury.

`leaderboard` is the Slice 10 research-board payload. It reads the frozen forecast and filtered-state Parquet files, never trains a model, and returns one row per pitcher-role with the latest evaluated pre-appearance probability, season mean probability, event count/rate and last evaluated date. It also returns the selected feature layer, amended-2026 validation metrics and release gate. The ranking is retrospective over completed appearances; it is explicitly not the next-game forecast planned for Slice 11. Conditional rebound boards contain only appearances following a same-role process collapse and do not pad missing opportunities.

`shadow` reads the Slice 11 immutable long-format ledger and monitoring audit. The ledger key is year／pitcher／role／game／target; an existing key's probability is never overwritten, and a later source mismatch is counted as a preserved conflict. The initial 2026 population is labeled `historical_backfill`; only newly observed keys in later rebuilds can be labeled `prospective_append`. Monitoring reports calibration and confusion counts separately for every role-target pair. The integration gate remains closed until untouched 2027 data and at least 250 truly prospective rows per role-target are available. This endpoint does not produce a scheduled-next-game forecast.

`v2-audit` reads the independent Slices 11A–13 audit. It exposes yearly eligibility/exclusion counts, opener／traditional-starter／bulk-reliever classifications, harmonized 2023–2026 warehouse coverage, and the strict expanding-window folds 2023→2024, 2023–24→2025 and diagnostic-only 2023–25→2026. Raw and cleaned cohorts remain separate; onset and persistent collapse are separate targets. Historical Plus values were retrospectively generated with the current frozen Plus models, so this endpoint validates the Performance State layer rather than claiming pristine out-of-sample Plus-model validation.

`v2-slice14-audit` reads the independent Slice 14A/B artifact. Slice 14A reports pitcher-cluster bootstrap intervals, calibration slope/intercept/ECE and evidence status for each fold, role and target. Slice 14B fits the advanced state/regime/volatility/tail/forecast stack on 2023–2025 and evaluates once on diagnostic-only 2026; it does not touch v1 artifacts or the 2027 prospective holdout.

`v2-slice15-audit` is the 2027 prospective-shadow readiness and monitoring contract. It fingerprints every Slice 14 input, locks training years/thresholds/calibration, reports whether an untouched 2027 source exists, and keeps the integration gate closed until append-only predictions and post-game observations reach at least 250 rows per role-target. When the source is absent it returns `awaiting_untouched_2027_source` with zero predictions; it never trains during an HTTP request.

`v2-slice16-audit` is a research-only optimization challenger. It develops on 2023–2024, selects between stable EWMA/MA5 and workload/context features on 2025, refits on 2023–2025, and evaluates once on the fixed 2026 diagnostic. It reports prevalence baselines, frozen Slice 14 metrics, pitcher-cluster bootstrap intervals, and a repaired release gate that explicitly rejects zero-variance baseline-only predictions. It never overwrites Slice 14/15 and keeps production integration closed.

`v2-slice17-audit` calibrates only the Slice 16 challenger. It selects raw, Platt or isotonic calibration on the 2025 window, applies the selected calibrator to a 2023–2025 refit, and reports raw-versus-calibrated Brier/log-loss on fixed 2026 diagnostics. A calibration is retained only when both Brier and log-loss are not worse; it does not replace Slice 14/15 automatically.

`v2-slice18-20-audit` contains three research-only diagnostics: Slice 18 empirical-Bayes pitcher partial pooling, Slice 19 residualized-workload selection-bias sensitivity, and Slice 20 SP/RP plus dominant-arsenal subgroup calibration. All use 2023–2024 development, 2025 selection and 2026 fixed diagnostics; none claims causal workload effects or retunes production probabilities.

`v2-slice21-22-audit` contains strict forward rolling-origin folds (2023→2024, 2023–2024→2025, 2023–2025→2026) for global, partial-pooling and residualized-workload challengers, followed by a research-only freeze decision. A retained challenger is never a formal model replacement; the response explicitly keeps production integration closed until untouched 2027 evidence exists.

`v2-strict-2026-replay` is a pre-registered retrospective holdout replay. Its role-target layer map, feature policy, 2025 Platt calibration rule and fixed false-alert threshold are fingerprinted before the 2026 state files are loaded for scoring. Because this project has previously inspected 2026, the response explicitly does not call it an untouched test; 2027 remains the only untouched prospective year.

`v2-lab` is the research-page synchronization contract. For the frozen 2026 diagnostic it aggregates Slice 14 role-target-specific probabilities as the Lab primary board, joins latest/season-mean deltas from Slice 18 partial-pooling and Slice 19 workload-bias challengers, and exposes the Slice 20 subgroup monitor, Slice 22 freeze decision and strict-replay status. It does not replace the formal `/leaderboards` model, overwrite v1 player timelines, or fit a model during an HTTP request; non-2026 requests should use the existing v1 Lab endpoint as fallback.

The Slice 10/11 player chart plots two same-scale performance series by appearance date, not a probability line. Process/rebound targets compare observed `process_score` (personal-baseline-adjusted Stuff+ and Location+ mean) with the mean of the available pre-appearance Stuff and Command state forecasts. Result collapse compares observed `result_score` (personal-baseline-adjusted RE24/PA and WPA/LI/PA mean) with the pre-appearance Result state forecast. Red solid circles/line are actual values, blue diamonds/dashed line are forecasts, and a light vertical dashed connector shows each game's forecast error; a purple ring marks a target event that was also alerted. Hover/focus exposes WPA, RE24, WPA/LI, Stuff+, Location+, both scores, all four target probabilities and the selected target's outcome. Forecast probabilities remain separate from forecast performance values.

Artifacts are rebuilt with `python backend/scripts/build_performance_state.py`; `--slice4-6-only` reuses the frozen v1.1 filtered states. Slice 4 compares 2–5 diagonal-Gaussian HMMs on 2025 and applies filtered, never smoothed, probabilities with elapsed-time transitions and 60-day stationary resets. Slice 5 fits Student-t GAS then a strictly lagged HAR correction with a 2025-only log-to-level smearing factor. Slice 6 uses `arch`'s Student-t likelihood with a constrained SciPy panel optimizer, resetting pitcher-role boundaries rather than concatenating unrelated players; per-pitcher GARCH fits are rejected for insufficient history. Outputs are `performance_state_slice4_6.json` and `performance_state_advanced_<year>.parquet`.

`--slice7-only` reads the frozen advanced artifacts and writes `performance_state_slice7.json` plus `performance_state_tail_<year>.parquet`. POT candidates compare 90%/92.5%/95% thresholds and declustering run lengths 0/1/2 using only the chronological 2025 fit/validation split; candidates use a comparable full-validation censored likelihood, with `log(1-q)` below the threshold and `log(q)+GPD density` above it. The final GPD is bootstrapped 100 times and audited with KS fit, support coverage, held-out alert recall and false-alert rate. EVT survival is used only when the requested raw extreme threshold lies above the fitted POT threshold; otherwise the frozen 2025 empirical survival is returned with `evt_tail_supported=false`, and expected severity remains null. CAViaR compares SAV and asymmetric-slope specifications on 2025 validation, then reports 2026 quantile loss and Kupiec unconditional coverage.

`--slice8-9-only` reads the frozen Slice 0–7 artifacts and writes `performance_state_slice8_9.json` plus `performance_state_forecasts_<year>.parquet`. For every SP/RP target, 2025 is divided chronologically into 60% training, 20% probability calibration and 20% validation. Five cumulative penalized-logistic layers are compared from lagged baseline through latent-state forecast, HMM prior, GAS+HAR and EVT; XGBoost with GJR/CAViaR is retained as a challenger. Current-appearance filtered states and innovations are forbidden predictors. Slice 9 applies the frozen choices to the amended 2026 external diagnostic and records PR-AUC, Brier/log loss, calibration bins, fixed false-alert metrics, pitcher-cluster bootstrap intervals, dominant-arsenal subgroups and explicit pass/fail gates. Targets remain separate and the overall decision is `keep_research_only`.

`--slice11-only` reads the existing frozen forecast and filtered-state artifacts; it does not refit any model. It atomically appends unseen keys to `performance_state_shadow_ledger.parquet` and writes `performance_state_slice11.json`. Performance State rebuilds are not currently part of the daily pipeline; the data-freshness report therefore labels this dataset `manual frozen-model rebuild · immutable append ledger` instead of implying automatic currency.

`--slice11a-13-only` builds only the independent v2 artifacts: `performance_state_v2_contract.json`, `performance_state_v2_slice11a_13.json`, `performance_state_v2_warehouse_<2023|2024|2025|2026>.parquet` and `performance_state_v2_predictions_<2024|2025|2026>.parquet`. It fixes the leverage reference to 2023, never rewrites v1 artifacts, and keeps 2027 untouched.

`--slice14-only` builds `performance_state_v2_slice14.json`, one advanced state Parquet per year, and `performance_state_v2_slice14_predictions_2026.parquet`. It requires the Slices 11A–13 warehouses and uses 2023–2025 for all fitting/model selection; 2026 is diagnostic-only.

`--slice15-only` writes the readiness artifact `performance_state_v2_slice15.json`. It fingerprints the frozen Slice 14 inputs and checks for `data/MLB2027/mlb_2027.duckdb`; it does not materialize, refit or retune a 2027 model. The source must be available before a future append-only materialization step can create prospective rows.

`--slice16-only` writes `performance_state_v2_slice16.json` and `performance_state_v2_slice16_predictions_2026.parquet`. It is a non-destructive challenger build using only frozen Slice 14 state inputs; 2026 remains diagnostic-only and no production artifact is changed.

`--slice17-only` writes `performance_state_v2_slice17.json` and `performance_state_v2_slice17_predictions_2026.parquet`. It calibrates the Slice 16 challenger using the temporally separate 2025 selection window; it never refits Slice 14/15 or opens production integration.

`--slice18-20-only` writes `performance_state_v2_slice18_20.json`, plus separate Slice 18 and Slice 19 2026 challenger prediction Parquets. It performs partial-pooling, workload-sensitivity and subgroup-calibration diagnostics without changing frozen production inputs.

`--slice21-22-only` writes `performance_state_v2_slice21_22.json` with forward-fold metrics and the non-production freeze decision. It does not rewrite Slice 14/15 or open any integration gate.

`--strict-2026-replay-only` writes `performance_state_v2_strict_2026_replay.json` and `performance_state_v2_strict_2026_replay_predictions.parquet`. It fits only on 2023–2024, calibrates on 2025, then loads 2026 after the model fingerprint is fixed; it does not tune on 2026 or open production integration.

The build uses 2025 to freeze empirical-Bayes personal baselines, thresholds, calendar-gap policy and all Slice 3A–6 parameters, then evaluates on 2026. Because Slice 3A was introduced after inspecting the first 2026 diagnostic, 2026 is labeled `test_with_documented_slice3a_amendment`, not pristine untouched validation; 2027 is reserved for prospective untouched validation. RE24 is pitcher-positive, WPA uses the shared plate-appearance boundary contract, and WPA/LI uses a shrunk 2025 empirical leverage table. `game_score_proxy` is explicitly a starter-only Bill James-style proxy, not an official earned-run Game Score.

### Catcher Descriptive Metrics

- `GET /api/catchers/descriptive/leaderboard?year&minimum_outs=0`
- `GET /api/catchers/descriptive/pairs/leaderboard?year&minimum_outs=120`
- `GET /api/catchers/descriptive/{catcher_id}?year`
- `GET /api/catchers/descriptive/{catcher_id}/strategy-bridge?year`

The catcher leaderboard returns the reconciled Slice 2–3 raw counts, cERA/cRA9/cFIP, full-season pitcher-mix tERA/tRA9/tFIP, cSaveRun and cSaveRun/IP. When the Slice 4 artifact is present, catcher rows also include adjacent-season support, a transparent reliability tier, and a dominant-pair sensitivity calculation that removes the pitcher with the most paired outs before recomputing cRA9, tRA9 and cSaveRun/IP. A stable dominant-pair row does not override a failed project-wide cross-year gate. Values remain observed associations and are never annualized or labeled causal catcher value.

When the passed Slice 5 artifact is present, catcher rows additionally expose `cxera`, `txera`, `x_runs_vs_mix`, `x_runs_vs_mix_per_ip`, `xera_expected_runs`, `pitcher_mix_expected_runs`, `xera_source_coverage_pct`, `xera_status` and `xera_model_version`. The response-level `xera` object carries model/contract versions, definitions, source coverage, evaluation periods and warnings. Petehub xERA v1 is a chronological additive calibration of Statcast `estimated_woba_using_speedangle`; it is explicitly not MLB's published xERA formula. `x_runs_vs_mix = pitcher_mix_expected_runs - xera_expected_runs` is an expected-results association, not causal catcher value.

When the passed Slice 6 v2 artifact is present, catcher-season rows additionally expose primary product fields `frv`, `throwing`, `blocking`, `framing`, `frv_status`, `source_innings_status`, `source_display_ip` and `outs_difference`. FRV and each component are source-provided runs above the source-defined average, not absolute runs prevented. Rounded components may differ from total FRV by one run, so `frv` remains authoritative and components must not be added to it again. Comparison-only DRS fields remain in the API/artifact for audit compatibility but are not displayed as the primary defense scale. The response-level `defense` object carries both source fingerprints, cross-source and canonical reconciliation, definitions, cross-year/overlap diagnostics and release-gate status. Canonical catcher outs remain the qualification denominator; source innings are audit-only. Defense fields are not added to cSaveRun or x Runs vs Mix. Park factor is `deferred_by_user`, so no park-adjusted metric is returned.

Paired Duo remains one season-pitcher-catcher row and defaults to 120 outs (40 IP). Its pair cSaveRun uses the pair's shared outs; Slice 4 reliability tiers apply only to the aggregate catcher-season view. Slice 5 adds pair `xera`, full-season `pitcher_xera`, `x_runs_vs_mix`, `x_runs_vs_mix_per_ip`, `xera_expected_runs`, source coverage and status. All expected-run numerators and outs reconcile through PA → pitcher → pair → catcher → team. Slice 6 FRV and components are intentionally unavailable on Paired Duo because a season-catcher total cannot be defensibly allocated to individual pitchers.

The Slice 8 strategy-bridge endpoint is research-only and currently returns model-consistent diagnostics for 2026. A row contains the on-field catcher context, total decisions, supported-set and chosen-support coverage, normalized entropy, effective supported choices, top-choice probability, supported deviation, model-minimum-choice rate, noise-floor count and count-tier splits. For 2021–2025 it returns `status=unavailable` and does not impute. The endpoint never returns a rank, composite catcher score, factual best pitch, true exploitability or causal caller attribution.

### Batter Comparison

- `GET /api/batter-comparison/period/options`
- `GET /api/batter-comparison/period/date-range`
- `GET /api/batter-comparison/period/overview`
- `GET /api/batter-comparison/team-research`
- `GET /api/batter-comparison/team-research/lineup-scenarios?year&team&opponent_hand=L|R`

`period/overview` returns Period A／B values, `delta = B - A`, and separate denominators for production, discipline, Bat Tracking and Miss Distance metrics. Percentage deltas use percentage points (`pp`). Both zone maps share one heatmap color domain.

Arbitrary-date X/Y/Z timing is not available locally. `timing_reference` therefore contains explicitly labeled full-season Savant summaries and never enters the period delta. `source_audit` records unavailable exact-distribution, Squared-Up／Blast and batting-stance fields rather than returning fabricated zeroes.

`team-research` uses `data_mode=recent_observed_research`. Batting order is reconstructed from team PA sequence and defensive positions from fielder IDs. It returns descriptive order splits, observed pitcher-hand splits, recent starter/order probabilities and three empirical run-expectancy scenarios. Active roster, injuries, official DH／PH roles and probable starters are not available from the local tables and are listed in `coverage`／`limitations`.

`team-research/lineup-scenarios` is the read-only Team Dashboard path for the three lineup cards: recent consensus, latest observed and run-expectancy candidate. It never reconstructs positions or runs simulations during an HTTP request. The data refresh pipeline computes both vs RHP and vs LHP results for every team, then atomically replaces `data/derived/batter_lineup_scenarios_<year>.json`. Responses expose `cache_status=current|stale|unavailable`; when newer pitch data exists or a rebuild fails, the endpoint continues serving the last completed entry with a warning.

### Data Operations Observability

- `GET /api/admin/data-freshness?year=2026` reads the latest generated freshness manifest. If no manifest exists for the requested year, it builds a non-persisted local snapshot without an external coverage request.
- `POST /api/admin/data-freshness/refresh?year=2026` rebuilds official coverage, dataset cutoffs, automation state and page-impact mappings, then writes the latest JSON, Markdown and timestamped history snapshot under `data/admin_job_logs`.
- `GET /api/admin/project-tracker` reads the Git-tracked `docs/PROJECT_TRACKER.json`, calculates project and portfolio progress from slice statuses, and returns handoff-ready Markdown.
- `GET /api/admin/daily-update-settings` reads the atomic daily scheduler settings.
- `PUT /api/admin/daily-update-settings?game_updates_enabled=false` pauses or enables the heavy game-data stages for future scheduled runs. It never disables the scheduled task itself: the transaction refresh and freshness report continue every day. Explicit `daily_update.py --step ...` commands remain available for manual maintenance even while the automatic game stages are paused.

The freshness manifest is the runtime authority for data cutoff reporting. `docs/PROJECT_TRACKER.json` is the planning authority for project, slice, verification and next-step status.

- `POST /api/admin/jobs/backfill-historical-plus?year=2024` starts the resumable local historical Plus pipeline for exactly one selected season. That season runs Location+, per-pitch Stuff+, Stuff leaderboard, Pitching+ and Stamina in dependency order; downstream stages do not run while per-pitch Stuff+ remains partial. A resumed season skips stages already marked `completed` or `current`. Admin child processes force UTF-8 on stdin/stdout/stderr so Windows legacy console encodings cannot turn a successfully written artifact into a failed job response.
- `GET /api/admin/jobs/historical-plus-status` returns the persisted season/stage status and, while Stuff+ is running, its cached-row and pitcher progress. Re-running the POST resumes the per-pitch cache instead of discarding completed pitchers.

## Standard Response Shape

```json
{
  "meta": {
    "year": 2026,
    "data_updated_at": "2026-07-02T00:00:00Z",
    "warnings": []
  },
  "summary": [],
  "charts": {},
  "tables": {}
}
```

## Versioning Rule

### Batter In game zone rates · 2026-11-05

`GET /api/batters/personal/zone-rates?year=2026&batter_id=682998&pitcher_hand=R` uses the existing API authentication; `batter_id` must be positive and `pitcher_hand` is exactly `All|L|R`. It returns `batter_zone_rates_v1`: year/batter/hand identity, status (`ready|insufficient_pa|no_data|unavailable`), whole-season completed unique `season_pa`, `eligible` (`PA>30`), split/located/missing-location/height-fallback pitch counts, metric definitions and 17 cells (9 normalized strike-zone + 8 outside groups). Each cell has stable id/label/region, `[u0,v0,u1,v1]` normalized bounds, pitches and all metric `{numerator,denominator,value}` records. Values are percentages; zero denominator/not-applicable is null, never zero. The eligibility count is computed before handedness filtering and is not pitch count or batter-vs-pitcher history. Regular-season PA excludes truncated PA and deduplicates by game/at-bat using the existing batter service definition.

Swing/strike/CSW and other pitch-based rates use cell pitches; Contact/Whiff use swings; Z/O variants are only applicable inside/outside respectively. Event flags reuse Discipline; coordinates use the replay's 17-inch zone and per-pitch recorded height (fallback 1.5–3.5ft, counted), distinct from the unchanged legacy Discipline fixed box. Missing/nonfinite locations do not enter cells. All finite outside locations are grouped even beyond their finite display bounds. Read-only season DB queries use enriched table first, select only necessary columns and exclude other batters/postseason; no video/Plus cache side effects. Server cache is bounded and keyed by year/batter/hand plus DB/WAL revision. Replay response and trajectory contract are unchanged. The old `/batters/personal/discipline` route still has its original arguments; new hand filtering is provided by this compact endpoint.

Outcome metric extension (additive, 2026-11-05): 16 metrics now include AVG, wOBA and HardHit%. Metric definitions expose `format=decimal|percent`; AVG/wOBA values are native decimal ratios, not percentages. Numerator/denominator support floating weights. AVG=H/AB on completed PA-ending rows with the shared non-AB exclusions. wOBA=sum(finite recorded woba_value)/sum(finite positive woba_denom) on PA-ending rows with both fields available; no missing-weight zero fill or generated coefficients. HardHit%=100*95+mph fair BBE/finite-positive-EV fair BBE, so missing EV is excluded. One completed PA outcome is chosen globally by game/at-bat/final pitch before hand/location filtering; only its final location receives the outcome. Nonterminal foul/stray EV and duplicated PA metadata do not create extra BBE/AB. Percentage metrics remain unchanged; missing/zero denominators are null. The client uses explicit separate color scales (percent0–100, AVG0–1, wOBA0–2), while actual values above the display ceiling remain unchanged in the numeric table.

League/PR extension (additive, 2026-11-05, supersedes absolute display coloring): root `benchmark_status/version/min_denominator/min_peers`; each rate adds `league_average`, `raw_pr`, `color_pr`, `peer_count`, `benchmark_status`; metric definitions add `direction=higher|lower|frequency`. Only same year/hand/cell/metric peers with full-season PA>30 and cell denominator>=10 enter the reference group; the weighted pooled league mean is separate from equal-batter midrank PR. At least5 peers and target denominator>=10 are required for color PR. Lower-is-favorable batter metrics reverse100−rawPR; frequency metrics retain rawPR with no quality claim. All ties yieldPR50. Raw AVG/wOBA/% and numerators/denominators remain unchanged. The client uses vivid0/50/100 PR colors and display-only PR interpolation; no missing/stale-reference absolute-color fallback. Outside groups render a narrow feathered halo, not actual pitch-density geometry.

Offline command: `python backend/scripts/build_batter_zone_baseline.py --year 2026`. Cache is per-year `MLB{year}/batter_zone_baseline_v1.json`, atomically published with DB/WAL stat plus aggregation/event-code fingerprint; same raw aggregator used for all peers. Only2026 is built initially. HTTP only reads/enriches and never scans/builds the league; source mismatch gives stale status and noPR until explicit preprocessing. Raw per-batter LRU results are deep-copied before enrichment. The reference artifact contains distributions but API exposes only summary/PR, not the entire population.

Keep URLs stable during MVP. If a breaking response change is needed, add a new field first, migrate frontend, then remove the old field later.
# Ballpark D4 avatar profile (draft, not D5-released)

`PATCH /api/auth/avatar` requires the existing authenticated session and accepts `{ "avatar": { "avatar_version": 1, "body_id": "tone_2", "uniform_id": "neutral_home", "palette_id": "orange", "number": null, "bats": "R", "throws": "R" } }`. `body_id` is `tone_1`–`tone_4`; uniform is `neutral_home` or `neutral_away`; palette is `orange`, `teal` or `slate`; number is null or 0–99. Both bats and throws accept `R`/`L`/`S`; `unknown` remains accepted only for old-save compatibility. New defaults and legacy-unknown creator drafts use `R`; opening/cancelling does not overwrite the saved profile. Unknown versions and invalid values are rejected with 422. The response is the existing `AuthResponse`, whose `user.avatar` contains the saved v1 appearance and `user.avatar_recovery_needed` reports an unreadable stored payload. `GET /api/auth/me` and login return the same fields. Favorite-team identity colors are derived from `user.favorite_team_code` at render time in the creator and walk runtime, never from temporary Viewing team; no avatar-version migration or saved-team mutation is required. Uniform home/away remains the saved colorway selection; a chosen favorite team overrides the manual accent, retaining the saved palette for neutral fallback. These are pixel team-color uniforms, not official jersey/logo replicas. Invalid stored data is preserved server-side while the API shows a neutral fallback. The avatar has no MLB logo, player identity, or client-side authoritative game state. Auth responses remain `Cache-Control: no-store`.
