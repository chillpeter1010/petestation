# Petehub 新對話交接

更新日期：2026-11-06
專案根目錄：`C:\intern\project_transfer`

本文件只保存「接手下一個對話所需」的短摘要。專案完整歷史已移至 `docs/archive/PROJECT_HISTORY.md`，不得在每次開新對話時整份載入。

## 2026-11-06 目前決策與下一步（優先於下方舊快照）

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
Tracker updated: 2026-11-06

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
| Game Center Analysis Modules | in_progress | 6/17 | User checks F1 mother-site Game identity/tab/refresh and preserved names/Personal links, folded notes and exact-count cards; Ballpark F1 owns this new acceptance, original 3H remains done. Rejected photo/PNG rendering is reserved for planned F2 replacement, not more pixel nudging. Location/Sequence/Tags/Movement and video full-season coverage remain independently unfinished; no engine work or data backfill started. |
| Petehub Ballpark Game System | in_progress | 36/66 | User performs the five F1 checks documented atop PETEHUB_BALLPARK_GAME_SYSTEM.md: GAME/objects/direct entry, game/pitcher/tab/refresh identity, scoreboard leaderboard year/team/view/cutoff, preserved name/notes/count-card/video UI, and guarded R return without banner. F1 stays in_progress until report. Do not reopen accepted D/E1-E5 or original 3H. Rejected photo/PNG rendering awaits separately authorized F2 replacement; do not install engines/start F2 or NPCs. E6 measurements remain pending. |
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
