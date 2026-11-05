# Petehub Ballpark Game System

更新日期：2026-11-06

專案 ID：`petehub-ballpark-game-system`
狀態：In progress（Section A–D、E1～E5 與其子項已完成，36／66；新增七個 F2 Planned 子項，並非已完成進度退回；E6 效能／裝置 gate 尚未放行）

## 2026-11-06 F2 重排與開工前盤點（只規劃，未授權實作）

使用者明確否決母站 Catcher 的整張照片 pan／zoom、獨立前景 translate 與固定 PNG 打者；先前 v4／下移／白線框不能記為接受。這是共用 In game 呈現層的待替換方案，不重開已接受的 3H 資料／影片／PR，也不重開 D／E1–E5 或重畫園區背景。新三維場景屬 F2，僅供母站 Game／Pitcher Personal 與設施入口共用；Ballpark 園區仍為核准的 2D Phaser，V2 球員／V3 User 標準及 F4 roster NPC 不因本計畫自動重製。

F2.1–F2.7 狀態一律 Planned。原 G1–G6 已涵蓋動作來源／rig／投打事件，本次把「通用歷史 In game 所需的最小三維能力」提前分配 F2；G 保留球員專屬、擴充 Motion Lab 與 synthetic simulation 的後期工作，消費 F2 成果，不重做 renderer／rig／clock，也不因文字重排標 done。

### 現在未收尾的範圍

| 項目 | 現況 | 開始重建前的處理 |
|---|---|---|
| E1–E5、直接功能入口／舊 R 返回 | 使用者已接受 | 保留 done，不重問舊清單 |
| 移除浮動 R 提示、保留鍵盤 R | source 已完成；尚無針對最新移除版本的明確回報 | 可由使用者簡短確認；不重開 E5，也不是球場幾何原型的硬性前置 |
| 真名連結、收合說明、exact-count 投打資料卡 | 已有程式與前批 12 項後端測試；新增 UI 未整體結案 | F2.1 凍結原 API／分母／選球／影片與 UI 行為；不為重建重算已接受 PR，不為舊貼圖再請驗收 |
| 母站 Catcher 圖片場景 | 使用者否決；現行程式仍在，尚未撤接或 rollback | 停止疊補位置與生成站姿 PNG；F2.2 起由新 renderer 逐步替換，保留來源與可回退入口 |
| E6 數值／裝置 release gate | 操作已接受；production loading／input／frame／retained heap／GPU／裝置資料未提供 | 先保留量測缺口；可先做隔離開發原型，不假稱 E6 done。重建前建議由使用者保存現況樣本；完整認證不必先跑完再因新 renderer 重跑，正式放行仍需 E6＋F2.6 |
| Git 安全點 | 2026-11-06 讀到 HEAD 3761955，已追蹤 upstream ahead/behind 0/0；工作樹仍大量修改／未追蹤 | 未提交工作不在上述 commit／push 中。重構前建議按功能分批審閱並建立含必要素材的 checkpoint；本輪不 stage／commit／push／清理 |
| 影片補抓、Game Location／Sequence／Tags／Movement | 補抓按鈕已交付，但沒有這輪全季完成／播放證據；Game Center 四項仍 in_progress | 分開列帳，不把缺影片歸因 renderer，也不要求先結完所有母站功能才能做 F2；不自行啟動全季補抓 |

舊 JSON gate／hash 是當時的 snapshot，未覆蓋後續畫面修改；最新人工結論與 tracker 優先，不覆寫歷史為通過。

### F2 分批交付與人工 exit gates

| Slice | 交付範圍（全部 Planned） | 前置與驗收重點 |
|---|---|---|
| F2.1 · 現況封存、來源／座標與架構決策 | 列保留／待替換清單、實測與 generic 資料 coverage、座標／單位／時間／鏡頭／fallback 契約；核對現有 assets、工具與來源授權；Three.js 為首選候選，依局部載入／資產成本決策後才安裝 | 不動 Statcast／PR 公式；區分照片概念稿與可動模型。確認重構安全點與最小第一批，先前 source tests 不冒充新量測 |
| F2.2 · 同一世界的球場、相機與歷史球路 | 真正地面、本壘板、左右打擊框、投手丘／踏板、17 吋好球帶及 source ball path；捕手／投手／側面 preset，拖曳 orbit、滾輪 dolly、範圍／穿地限制與 reset | 依 F2.1；使用者驗透視／視差、相機轉動、地面線框、手部出手標記與進壘。不用整張照片 pan／前景像素位移；角色暫用明示定位標記，不能當正式美術 |
| F2.3 · 可編輯的通用投打骨架與資產 | 正常人體比例的投／打模型、Blender 或其他可編輯來源、glTF／GLB、骨架／球棒／握點／足底／左右側／材質契約、授權、版本、LOD 與尺寸預算 | 依 F2.1–F2.2 場地尺度；先交可繞看的通用模型與 ready／idle 動作供使用者驗外觀、握棒與腳落地，再製作其餘 clips；不是全隊真人建模，也不拉伸 PNG 冒充 rig |
| F2.4 · 投打動作與共用時鐘 | ready／load／stride／swing／follow-through／recover／take，加通用投球／release；pre-pitch、release、plate／contact、post-pitch 命名事件；固定時間取樣支援 pause／seek／speed／replay | 依 F2.2–F2.3；投手手部對每球 release_pos_x/y/z 定位，球不吸附丘中心或改軌跡；接觸點／揮棒時機不足則明示 generic／unknown，不強制假接觸；使用者驗左右投打、看球／揮空、重播同步 |
| F2.5 · 真實揮棒資料盤點與疊圖介面 | 分清逐幀球棒位置、單次 scalar 指標、整季平均姿態與 generic clip；以同一 pitch identity 定義 bat-tip／handle、時間基準、座標／來源／coverage；有資料才畫實測軌跡，無資料有 unavailable | 依 F2.1 與 F2.4 時鐘；bat speed／length／attack angle 等不足以唯一還原整次揮棒。首批可交來源稽核＋adapter＋明確缺資料狀態；無來源不造軌跡，不把此項 source audit 當真實 bat-path 功能已完成 |
| F2.6 · 共用接線、fallback 與新 renderer gate | 同一按需載入的三維元件供母站 Game／Pitcher Personal 使用；Ballpark 物件沿用 canonical 入口與 R 來源；原熱圖／資料卡／影片／鍵盤 DOM；錯誤／低效能／無 WebGL 的可用 fallback、unmount 資源釋放與 rollout/rollback | F2.2–F2.4 與 F2.5 資料狀態契約可用；實測 bat-path 為條件擴充，不阻擋有明確 unavailable 的核心版本。使用者驗兩母站入口／選球／影片／返回／裝置；效能證據與 E6 分開記錄，缺量測不得 production-ready |
| F2.7 · 設施業務 parity 與牛棚角色 | 保留 F2 原任務：投打分析／比較／released Lab、兩牛棚官方主隊 roster 隨機 eligible 投手、通用投球、手動投手／場次優先、前後網遮擋 | 使用既有 E3/E4 bridge 與 F2 共用面板；真實球員特製外觀／跨園區巡遊對話由 F4 負責，不為本子項重建所有 NPC。不以三維面板完成冒充設施 parity 完成 |

建議順序：先收好既有資料／UI 與 Git checkpoint → 另獲實作指示後 F2.1 → F2.2 幾何人工驗收 → F2.3 外觀／ready 人工驗收 → F2.4 動作 → F2.5 資料介面 → F2.6 整合／release。F2.7 可後續獨立排程，F1／其他設施不必先全部做完才做局部 F2 原型。各實作短批如超過 10 分鐘，開工前說明範圍，不預估為幾分鐘即可交付完整商業遊戲品質。

研究依據：官方 [MLB The Show 動作更新](https://blog.playstation.com/2026/02/03/mlb-the-show-26-gameplay-revealed/)、[KONAMI 三維場地與動作介紹](https://www.konami.com/games/prospi/2024-2025/)、[Savant 整季平均 swing 視覺說明](https://baseballsavant.mlb.com/changelog/2025-05-20-swing-path-attack-angle)。這些支援設計方向，不代表 Petehub 已具備其資產／資料或效能。

## 最新操作接受與入口／文字小修

2026-11-05 後續接受與新要求優先：使用者已驗收所有功能物件直接進母站、前段 R 返回；不再限單連結，也不再要求在中繼面板選人。母站路徑保留 Ballpark 來源 token／checkpoint，多工具可由各自直接入口前往。依最新要求已移除浮動 R 按鍵／banner，只保留受帳號、來源、輸入與彈窗防護的鍵盤 R 返回。這次移除視覺元件待使用者確認；以下較舊限制與 pending 文字為歷史。E6 的數值與裝置 gate 未因此完成。

最新人工結果：使用者回覆「都通過」，已接受單一目的地直接進功能、正確球隊／返回位置及放大文字，不重問。新增使用者要求：從 Ballpark 進 Classic 後，當有效來源 token 屬目前帳號，按 R 可回來源房間及 E5 保存位置；僅條件式 Classic 返回元件註冊按鍵並於卸載移除，無來源不觸發。忽略輸入框／選單／可編輯區／對話框、IME、修飾組合鍵、長按與已被頁面處理的事件；不搶既有輸入。這是使用者明確授權的快捷返回，取代舊「Classic 不註冊 R」的絕對敘述；原意的表單不被攔截仍保留。新 R 快捷鍵待人工驗收，未跑瀏覽器或為小修重跑 typecheck／build／audit。

使用者回報「操作上都沒問題」：E5 保存／恢復操作以整體人工回報結案，36／59；E6 操作獲接受，但未提供效能 JSON／裝置型號／部署與 retained-heap 數值，這些不補記通過，E6 保持 In progress。下方 E5 待驗與 35／59 為此前交付快照。

使用者要求移除 Coach workspace 截圖中的單連結中繼頁：`play.vue` 對 `kind=links` 且只有一個目的地的物件，點擊／E／Enter／直接選單即導向原功能，保留 season／team、位置 checkpoint 和 Classic 返回；舊 object deep link 也直接導向，不閃中繼面板。多工具選擇、真正有內容的 Game／In game／選人／對話面板與 admin 精確帳號限制保留。

`createBallparkGame.ts` 把靠近互動提示 13→20px、guide 標籤 11→18px、出口 12→20px、地面方向 16→22px；粗體、高對比底色／描邊與雙倍文字材質解析度，出口文字在提示層顯示。未改背景／碰撞／角色素材。這兩項新 UI 修改待使用者人工驗收；未因小修重跑 typecheck／build／完整 audit 或任何瀏覽器／畫面檢查，先前 source gate hash 為當時快照。

## 2026-11-05 E3～E4 全數接受；E5～E6 接續交付

使用者明確釐清「E3-4 都通過」，E3、E3.1、E3.2、E3.3、E4 全部 Done，35／59，不再重問舊清單。先前把接受範圍縮成 Campus 兩項是代理判讀錯誤；下方 pending／30／59／局部回報文字保留作歷史，以上述釐清與 tracker 為準。此接受不包含未製作的 F4 真實球隊 NPC，也不補造裝置／數值效能測量。

**E5 實作：** `worldState.ts` 定義 version 1 本機世界存檔，`useBallparkWorld.ts` 由 Nuxt 保存／恢復；key 為 `petehub.ballpark.world.v1:{account_id}`。只保存最後場景、Viewing team、各房間 x／y／facing／物件來源 ID、world revision 與 timestamp；不保存 auth secrets、Phaser instance、逐幀狀態或複製 avatar profile。使用本瀏覽器 localStorage，可跨同瀏覽器重登入，不提供伺服器／跨裝置同步。移動時最多每秒排一次寫入，另於離開、pagehide、切入背景、Classic 開啟前以當前 snapshot checkpoint；儲存失敗保留本次記憶體狀態並提示，Classic 不受阻。

URL 的明確 room 先於上次場景，無 room 時恢復 last_room；明確 Portal 到達點先於該房間舊位置。spawn query 在首次 ready 後消耗，但本次 runtime key 保留到達身分，避免開關面板重建場景；之後重新整理使用已存 pose。房間固定導覽可恢復該房間位置，Portal／C／R 仍落在指定到達點。無合法舊 world schema 可遷移，未知 schema／帳號不符／壞欄位回新存檔；世界包變更或非法位置以目前 collision／footprint 重驗，必要時依目前物件 approach／場景 spawn 安全恢復，不出生在牆內。Safe reset 回安全入口而非任意舊存點。離開 Classic 返回仍使用 E4 的帳號隔離來源 token，加上 E5 的有效位置恢復。

**E6 交付與限制：** runtime 下方 `Runtime options / E6 recording` 提供 Reduced motion、Canvas renderer；切換保留當前 pose，跟隨系統 reduced-motion 變動。背景載入／逾時沿既有 fallback，新增 graphics-context loss 的 Retry／Static／Classic，清理 recorder timer、media change、context-loss、visibility/pagehide、ResizeObserver 及原 runtime。沒有為本輪另開 server、登入 fixture 或控制瀏覽器。

使用者按 `Record 20 seconds` 才紀錄 frame deltas（上限 3600）、moving samples、median／p95、約略 FPS、長幀與可用的 performance.memory，隱藏／paused 段落排除；可下載 JSON。報告含 dev／production、viewport／DPR、browser、renderer、reduced motion、load-to-first-state 及 owned created／destroyRequested／destroyed 計數。它不是 navigation LCP、forced-GC retained heap、GPU 或全瀏覽器 listener 認證；純 idle／少量移動列 limited，p95 >33.3ms 提供 Classic／Canvas 建議。原 A4 的部署 LCP／input／transfer、20 cycles retained-heap、實體低階裝置與多瀏覽器 budgets 尚未量測，不能由 local dev sample 推定通過。

來源證據：`data/sample/petehub_ballpark_e5_e6_source_gate_v1.json`（七組 focused contract tests）、`petehub_ballpark_e5_e6_release_gate_v1.json`（保存策略、人工 checklist、未量測 matrix／budget 與 release pending）。單次直接 vue-tsc PASS，只代表編譯。E5／E6 保持 In progress；E6 是驗收準備已交付，尚未正式效能放行，不宣稱 production-ready。F 區與球員美術未開工；核准背景／幾何未改。

人工網址：`http://127.0.0.1:3000/ballpark/play`，只驗新 E5／E6：

1. 在房內走動／轉向後重新整理、離開 Classic 返回及登出重登入，位置／方向／房間／Viewing team 恢復；另一帳號不串檔。
2. 九場景進出／固定導覽、Clubhouse C／庭院 R、各房間 R 回 Campus 指定入口及 Safe reset；有條件時測壞存檔／儲存受限，否則如實列未測。
3. 目前桌面、窄視窗、可取得的實機與 keyboard／touch／gamepad；Reduced motion／系統偏好與 Canvas 切換保留 pose。沒有的實機／輸入裝置列 unavailable。
4. 展開 runtime options，按 Record 20 seconds 並實際走動，下載 JSON；可重複房間／Classic 往返後觀察計數、卡頓、閒置／切背景。dev、無法取得的 API 與設備不得冒充部署量測。
5. 錯誤或低效能時 Retry／Static／Classic 可用，往返後無重複角色／卡鍵，面板與表單仍可操作；E6 數值認證未滿足時保留 pending／limited。

## 2026-11-05 E3／E4 互動交付（人工待驗）

**最新人工接受範圍：** 使用者對 Campus 導覽員「完整顯示」與「靠近 E／Enter 或點擊開啟對話」兩項回覆「兩個都可以」，這兩項已通過，不再重問。這次回覆沒有涵蓋其餘房間物件、Game／牛棚 context、面板／Classic 返回、mini-map／快速移動及權限等完整 E3／E4 清單；E3／E3.1–E3.3／E4 仍為 In progress，30／59 不變。程式實作到 E4，E5／E6 未開始；真實球隊 NPC 是 F4。下段「修正待確認」只描述該回覆之前的交付狀態。

**使用者後續釐清／缺陷：** 使用者所指 NPC 是所屬球隊的真實球員，應可隨機出現在園區與各房間；通用 guide 只代表互動基礎，不能當成這項球員需求已完成。目前只有 V3 User 與 V2 Gabriel Moreno 樣本，沒有全隊球員美術／動畫。F4 應承接官方 active roster 身分、代表球員 V2 素材、全園區與各房間的可用生成點及對話，再細化數量／刷新時機／去重／巡遊與場景活動規則；先前 8–10 名 Clubhouse 代表只是一個範圍，不能解讀成只會出現在 Clubhouse。本次不開始建模或隨機球員實作。使用者另回報 Campus guide 只見標籤，來源定位為原站位 [770,811] 被 west-entry-fence 前景（depth 815）遮住；改為中央廣場 [850,745]，保留正常足底排序，不修改核准背景／遮罩／碰撞。這是待使用者確認的修正，E3.3 與 E4 等人工狀態不變。

使用者授權 E3＋E4，包含 E3.1–E3.3。五個 Slice 保持 In progress，done 仍為 30／59。未操作瀏覽器、截圖、DOM 視覺檢查或角色／碰撞；來源檢查不代表畫面／互動通過。下方舊「E3 未開工」文字屬歷史快照。

- **E3：** `frontend/components/ballpark/runtime/interactionCatalog.ts` 以 v4 穩定 ID 建立 44 個物件／guide 綁定。獨立 bounds／approach、最近距離及穩定 ID prompt、400ms debounce，E／Enter、點擊與房間 DOM 選單走同一 typed intent。房間出口與 C 門優先；裝飾保留。環境包既有 pending-binding 描述保留為環境製作快照，現行接線以上述目錄為準。
- **E3.1：** 舊五場景物件有命名入口；Clubhouse 使用官方 active roster，保留 fresh／stale／unavailable、retrieved_at、source_as_of；Video Room 共用首頁推薦影片 API。Coach／GM／Lab 目前為命名橋接面板及既有 Classic 工具，完整房內業務面板仍屬 F3–F6，不以連結冒充完成。記分板可點及用直接選單；admin 畫框維持 pointer-only、admin＋精確 username peter1010，沒有額外彩蛋按鈕，server 授權不變。
- **E3.2：** Game 可選賽事／投手，Box Score 只轉接既有資料，Location／Sequence／Movement／In game 重用 GamePitcherAnalysisPanel。Batting／Shape 可選人並開對應 Classic personal。左右牛棚均使用 PitcherInGameTab，從瀏覽隊官方 roster 選投手及出賽場次（預設最後一場），影片跟隨實際球；無資料不造球員／場次。Shape 不重複 In game。原元件只加 optional select-game event，母站原使用方式不變；完整 F1／F2 parity 不在本輪。
- **E3.3：** 10 位虛構 stationary idle guide 使用既有角色素材，含八位新增 room guide、兩個沿用 courtyard chat-spot ID。九場景背景物件基準仍為 59，不把新增 runtime 身分當成核准背景變動。提供 DOM 對話分支／travel、目前房間小地圖、玩家位置及九場景快速移動。真實 roster／8–10 位代表、隨機刷新巡遊、個別對話、抽菸／坐下等活動動畫仍為 F4／後續動作工作；未重製角色或凍結隨機政策。
- **E4：** Nuxt 擁有 object／year／player／game／date／mode query、表單與權限。runtime key 只依 room／spawn；面板開關保留原場景，暫停並釋放遊戲鍵盤 capture，具 focus trap／返回、scroll lock／cleanup、Close／Escape／Back／forward／直接 URL。每隊／功能選人 context 只在本頁暫存；refresh 由 URL 重建面板並使用安全 spawn，精確位置保存仍 E5。Classic 入口記錄來源房間／team／spawn，app.vue 只加條件式返回連結；帳號／tab 隔離並驗證本地路徑，不引入全域引擎或 Classic R 攔截。既有 auth middleware 與 server 授權保留，C／R 房間出口沿用。

Source-only：`node frontend/scripts/check-ballpark-interactions.mjs --report` 與直接 vue-tsc PASS。來源證據與 44 個接線／bounds／anchor／hash 在 `data/sample/petehub_ballpark_e3_e4_source_gate_v1.json`。合法足底 anchor 不等於實走可達性；沒有重跑完整 build／舊 audit／效能矩陣，E5／E6／F 未開始。

人工網址：`http://127.0.0.1:3000/ballpark/play`。使用者驗收五項：

1. 各房間物件靠近 E／Enter、點擊與下方直接選單等價；連按不重複開啟。
2. Game 選比賽／投手及分析／影片；左右牛棚官方投手／場次與選球影片 context；Batting／Shape personal 保留所選人。
3. 面板暫停移動、表單可輸入；Close／Escape／上一頁／下一頁／帶 query 重新整理、focus／捲動恢復；Classic 返回正確設施。重載精確原位置不屬本輪。
4. generic guide 對話、小地圖／玩家位置、九場景快速移動保留 Viewing team；C 庭院門與 R 出口仍正確。
5. 普通帳號看不到 admin 入口，符合權限者點原畫框能進更新區；未開放、無名單／場次／影片、API 錯誤與 roster freshness 提示明確。

## 1. 產品目標與邊界

Petehub Ballpark 是現有分析網站上方的可選遊戲化入口，而不是一次重寫所有分析頁。第一階段以 2D／2.5D 俯視球場、可建立的玩家角色、自由移動與區域入口為主；Pitcher、Batter、Game Center、Video Room、Training、Clubhouse 與 Admin 等區域仍開啟現有 Nuxt 功能。任何階段都必須保留可直接深連結的 Classic UI、鍵盤操作、reduced-motion 與低效能 fallback。

技術基線：

- 現有 Nuxt／Vue／TypeScript 保留為網站、表單、資料表與分析面板層。
- 第一版球場 runtime 優先評估 Phaser＋TypeScript；不先把整站改成 Unity／Godot build。
- 3D 投打動作只在通過 Section F engine spike 後，以獨立 lazy-loaded 場景評估 Babylon.js＋TypeScript＋Havok／WebAssembly。
- FastAPI／Python 保留 API、資料處理、能力值、可重現 simulation 與 Monte Carlo Lab；不以 Python 驅動瀏覽器逐幀動畫。
- 投手與打者人體動作使用 rigged animation、state machine、animation event 與必要 IK；物理引擎處理球、球棒、碰撞與場景，不宣稱 rigid-body solver 能自行產生真實人體 mechanics。
- 現有 `pitch_trajectory_statcast_v1` 是資料重播，不可直接改名成投球動作模擬。Simulation 與 historical replay 必須是不同模式、不同契約。

## 2. Skill 與工具鏈計畫

### 2.1 2026-10-30 已安裝的官方 skills

| Skill | 用途 | 使用階段 |
|---|---|---|
| `playwright` | 瀏覽器端到端、輸入、路由、存檔與效能 gate | C–H |
| `playwright-interactive` | 自由移動、碰撞、區域觸發、拖曳與鏡頭互動稽核 | C–F |
| `screenshot` | 多解析度像素回歸與視覺比較 | B–H |
| `figma` | 讀取／操作 Figma 設計來源 | B–E |
| `figma-create-design-system-rules` | 將 token、元件與場景規則固定成可實作契約 | B |
| `figma-generate-design` | 角色建立、HUD、球場導覽與 overlay 原型 | B–D |
| `figma-implement-design` | 依核准設計實作，不由程式端猜外觀 | C–E |
| `jupyter-notebook` | Simulation calibration、Monte Carlo、balance 與效能分析 | F–G |
| `security-threat-model` | 存檔、角色資料、未來多人與 UGC 的威脅模型 | H |

上述 skills 從下一個對話回合開始可用。Figma 類 skills 仍需要可用的 Figma connection；沒有 connection 時不得假裝已完成設計同步。

### 2.2 既有 skills 的角色

- `ui-ux-pro-max`：沉浸式入口、mobile fallback、Classic UI 與無障礙決策。
- `design-system`、`design`、`ui-styling`：共用 token、HUD、overlay 與角色建立 UI。
- `visualize`：互動概念與 simulation inspection prototype。
- `imagegen`：只做 moodboard、背景概念與 style exploration；不當正式 rig、連續 animation frames 或可交付 sprite atlas。
- `skill-creator`：建立下列 Petehub 專用 skills。

### 2.3 Section A3 已建立的專案 skills

| Project skill | 必須固定的內容 |
|---|---|
| `petehub-game-architecture` | Nuxt／Phaser／Babylon／FastAPI 邊界、lazy load、Classic UI、route ownership、save contract |
| `petehub-baseball-motion` | Statcast 座標、左右視角、release/contact animation events、historical replay 與 simulation 分界 |
| `petehub-game-art-pipeline` | Aseprite／Blender、sprite atlas、glTF、骨架、命名、LOD、壓縮與授權 provenance |
| `petehub-game-performance-audit` | bundle、FPS、memory、input latency、低階裝置、mobile、reduced-motion 與 fallback gates |

四個 skills 已建立在 `.codex/skills/`，各自以精簡 `SKILL.md` 路由至一份必要 reference，並保留適用範圍、禁止事項、輸入、輸出與驗證方式。它們不取代本文件或 tracker，也不把未通過的 engine／asset／performance gate 宣稱成既定事實。

## 3. Section 與 Slice Roadmap

狀態定義沿用 `PROJECT_TRACKER.json`。Section A–D、E1 已完成；使用者於 2026-11-04 接受 Game 介面，E2.2 Done，現為 25／59，並授權 Batting／Pitcher 製作。先前重排新增八個分項，總數由 51 變為 59，不是既有進度退回。D2 的 2026-10-31 試作已遭否決，不得沿用畫風或視為格尺寸已核准；已完成 D1–D5 不因本次擴充重開。

### Section A · Programme、Skills 與安全邊界

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| A1 · Programme charter and roadmap | Done | 凍結本文件、Section/Slice 結構、技術分層、非目標與 Classic UI 原則 | 主文件與 tracker 一致；不改寫 Game Center 既有 slices |
| A2 · Official skill bootstrap | Done | 安裝 Playwright、Screenshot、Figma、Jupyter 與 threat-model skills | 安裝清單可重查；下一回合可載入；無來源不明 skill |
| A3 · Petehub project skills | Done | 使用 `skill-creator` 建立四個專案 skills | 四個 skill 均有明確 scope、trigger、reference、驗證與禁止事項，且通過 `quick_validate.py` |
| A4 · Baseline and compatibility matrix | Done | 記錄目前 bundle、LCP、FPS、memory、browser/device、auth flow 與 Classic UI browser baseline | Chrome／Edge／Firefox、桌面／窄版與 reduced-motion 已實測；auth、實體 mobile／低階裝置限制明示，不把未測項目列為 pass |

### Section B · Experience Architecture 與 Art Direction

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| B1 · User journey and fallback contract | Done | 定義登入、首次角色建立、回訪、Ballpark／Classic UI 切換、深連結與 skip flow | 所有功能可不經走路抵達；browser back／refresh／direct URL 行為明確 |
| B2 · Ballpark map and zone IA | Done | 把 Pitcher、Batter、Game、Video、Training、Clubhouse、Front Office 映射成球場區域 | 每區 owner、入口、離開、loading、空狀態與權限固定；現有 55 條 Nuxt page routes 全數有歸屬 |
| B3 · Pixel-RPG visual art bible | Done | 凍結俯視 2D 像素 RPG、Petehub 黑橘 HUD、主球場／Team Office／Clubhouse 模板 | 使用者明確核准主畫風；含 Pitcher Mound 永久圍欄招牌的 v4 主畫面、Team Office v2、Clubhouse v1 成為後續設計基準 |
| B4 · Interactive prototype gate | Done | 本機 `/ballpark` 已依核准模板重建主隊選擇、主園區、Clubhouse、Team Office、Video overlay、fast travel 與 Classic fallback | 使用者已核准最終原型；Nuxt UTF-8 check 與 typecheck 通過，Section B 關閉 |

### Section C · Account、Home Team 與 Roster Contract

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| C1 · Registration and character bootstrap | Done | 註冊可選主隊；帳號保存可修改的 `favorite_team_id` 與 pending/default avatar 狀態；首次進入 Ballpark 可使用預設角色或略過主隊 | 舊 SQLite 帳號無損 migration；30 隊 ID／null 驗證、API/auth/schema 測試 8/8、Nuxt typecheck 與 Playwright NYY bootstrap flow 通過；不阻塞 Classic UI |
| C2 · Official active-roster contract | Done | 以 MLB StatsAPI `rosterType=active` 建立 30 分鐘持久快取、position/status 與 fresh/stale/unavailable fallback | v1 API 與 9 項 targeted／Team Dashboard tests 通過；本季出賽名單不能進入 active-roster contract，來源未提供 revision time 時 `source_as_of=null` |
| C3 · Home-team context and switching | Done | `/teams` 以帳號主隊導向、無主隊時顯示 30 隊選單；Team page、Clubhouse、Team Office 可暫時瀏覽其他隊 | Nuxt typecheck 通過；使用者於 2026-10-31 明確驗收，靜態室內背景跨隊共用為已知限制 |
| C4 · Special admin access contract | Done | `Per aspera ad astra` 彩蛋與 `/admin/updates` 權限 | `/api/admin/*` server 同時驗證 admin role 與精確 username `peter1010`；拒絕／允許與路由覆蓋測試通過 |
| C5 · Account/team data gate | Done | 稽核註冊、session、主隊、roster freshness、權限與隱私；auth/admin 回應加 `no-store` | 22 項 targeted tests、Nuxt typecheck／UTF-8 通過；使用者提供登入後室內截圖，並明確表示移除兩處 HOME TEAM 後可結案；原圖已更新，完整自動化 browser matrix 未宣稱通過 |

### Section D · 分層場景素材、可操作驗收與 Avatar v1

2026-11-02 調整：保留 `/ballpark/play` 的 V0 runtime、已核准畫面與角色設定；在既有成果上補齊分層素材和場景資料。採固定背景、獨立物件、前景遮擋與明確碰撞／入口的場景製作方式；圖塊只用於需要重用的部分，不要求把三張核准場景全部重畫成 32×32 tileset。此調整改變製作方法，沒有將既有預覽自動升為完成品。已核准畫風不再重審，內部格尺寸由助手負責選擇和驗證。詳見第 19 節。

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| D1 · Scene and asset manifest contract | Done | 固定世界座標、圖層、foot anchor、碰撞／入口格式、來源／授權和可重現輸出 | 分層背景契約、manifest、來源 hash、可重現匯出與 Clubhouse 1671→1672 明確轉換完成 |
| D2.1 · Game entrance layered pilot | Done | 以已核准 Game 入口製作可編輯分層樣本，分離背景、遮擋、碰撞與互動資料 | 原構圖與畫風沿用核准結果；輸出／幾何檢查完成，2026-11-02 使用者完成合併人工驗收；未重複送審入口圖 |
| D2.2 · Minimum shared scene kit | Done | 三場景實際需要的共用素材、mask、場景資料格式、匯出程序與來源清單 | v2 共 66 collision、36 foreground、12 portals；來源、可編輯 SVG、hash 與可重現輸出完成 |
| D2.3 · Campus layered scene | Done | 保留核准 Campus 背景，補齊獨立物件／前景遮擋、完整碰撞、起點與七個入口 | Campus 23 collision、15 foreground、7 portals；技術檢查完成，2026-11-02 使用者完成最新合併人工驗收 |
| D2.4 · Clubhouse and Team Office layered scenes | Done | 在兩間核准室內構圖上製作可編輯場景包、家具碰撞、遮擋、出入口與互動定位 | Clubhouse corridor v2、Team Office 地面標示、0.8 zoom／viewport sizing 由使用者於 2026-11-02 驗收通過；真實 roster NPC／業務面板仍屬 F4／F5 |
| D2.5 · Training & Lab and Video／Game Room | Done | 兩間核准內裝的可編輯分層、碰撞、遮擋、出入口及既有 runtime 接線 | 兩室各 33 collision／23 foreground／2 portals；使用者完成五項操作驗收及 R 出口鍵驗收 |
| D2.6 · Five-scene asset package | Done | `d2-scenes-v3` 統一五場景、manifest、fallback、可重現 SVG／JSON 輸出及 inventory | 現行 135 collision／82 foreground／16 portals，含已驗收圍網及 D5 待驗的兩側辦公室後牆追加；不代替 D5 |
| D3 · Versioned avatar and NPC contract | Done | avatar v1 外觀欄位、四方向 idle／walk、NPC identity、預設與 migration／隱私 | 規格已凍結；sprite、creator、移動與對話仍屬後續 Slice |
| D4 · Creator UX and persistence | Done | V3 User 分件及 V2 Moreno 樣本、四方向 idle／walk、creator／保存／runtime 外觀對應 | 使用者於 2026-11-02 確認功能與全部 followup 通過，含 favorite-team 隊色、R／L／S、樣本按鈕移除 |
| D5 · Pixel asset/avatar release gate | Done | atlas memory、組合覆蓋、方向、載入、depth sorting 與 provenance 稽核 | 2026-11-04 使用者明確回報 D5 通過；最終資產 gate PASS，device／效能細節不推定，完整 E6 仍獨立 |

### Section E · Ballpark Runtime Foundation

2026-11-04 E2 穿模 followup：依使用者黃框，在 Team Office 中央雙門／盆栽壁龕與右側入口盆栽櫃、Clubhouse 左側電視上方櫃體補三個獨立碰撞；`collision_additions`、SVG／JSON／manifest 同步。現行 **138 collision／82 foreground／16 portals**，已驗收背景與 18×10 足底尺寸不變。針對性來源幾何檢查覆蓋三處阻擋、門前橫向走道、右側櫃旁繞行、電視旁走道、出生點／入口與來源差異／輸出一致，PASS 不是人工手感通過；新三處只列 E2 待驗，不重開 D5，也不重跑 typecheck／build／全 audit。

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| E1 · Layered scene runtime integration | Done | 沿用 V0，補 latest-only／可取消載入、錯誤／卸載清理及 canvas ownership | 使用者於 2026-11-04 明確回報「E1可以」；正式 bundle／GPU／效能仍為 E6，無代理瀏覽器測試 |
| E2 · Movement, camera and tile collision | Done | 原五場景移動／碰撞及失焦／暫停／表單輸入防護、手把中立復位／按下沿觸發 | 使用者明確回報 E2 通過；不推定未提供的裝置型號／逐裝置結果，不因新附屬區重開 |
| E2.1 · 全場景物件盤點與功能配置 | Done | 九場景／59 語意物件，包含 Clubhouse C 後門、吸菸庭院長椅／煙灰缸／兩個未來聊天點及 R 回門旁 | 2026-11-05 使用者明確回報「都可以 通過」，包含新增區五項清單及盤點；NPC／抽菸／聊天與業務接線仍未實作 |
| E2.2 · Game 新場景 | Done | 獨立包 21 collision／19 foreground／1 return portal，三個物件定位；Campus GAME／固定按鍵進入及 R 返回 | 2026-11-04 使用者明確回報 Game 介面驗證通過；物件功能仍 E3.2／F1，不推定特定裝置通過 |
| E2.3 · Batting Cages 新場景 | Done | 16 collision／14 foreground／1 R 出口／5 物件定位；Campus Batting 與固定導覽已接線 | 使用者明確回報 E2.3 通過；物件功能仍 E3.2／F2 |
| E2.4 · Pitcher Mound 新場景 | Done | 兩牛棚改 IN GAME、左分析台只留 Shape；19 collision／17 foreground／1 R 出口／6 物件定位；Campus／固定導覽已接線 | 2026-11-04 使用者以「都可以」接受新配置及三項人工清單；不推定裝置／效能。投手隨機出現／投球及選單仍屬 E3.2／E4／F2 |
| E2.5 · 九場景統一包與物件對齊 | Done | `scene-kit-v4.json`／manifest／九場景可編輯 SVG／JSON，59 物件 index；211 collision／147 foreground／21 portals；runtime 單一包 | 2026-11-05 使用者回報「都可以」，接受統一包五項人工清單；原 source-only PASS 保留，不推定裝置／效能測量 |
| E3 · 共用物件互動框架 | Done | 靠近／焦點／啟動提示、按鍵／點擊／選單等價、優先序／防連發及 Nuxt action dispatch | 框架本身驗收；不與 E3.1–E3.3 的實際物件／NPC 接線重複計工 |
| E3.1 · 既有五場景物件接線 | Done | Campus／Clubhouse／Team Office／Training／Video 物件綁定；保留 admin 畫框權限 | 盤點 ID、範圍、提示／action 一致；不強迫裝飾可點，業務面板仍屬 F |
| E3.2 · 三個新增設施物件接線 | Done | Game／Batting／Pitcher 物件及 game／player／team context 接 E4 bridge | 功能未接時明示不可用；接 E4 後人工驗證開啟／關閉／選單等價，完整業務 parity 為 F1／F2 |
| E3.3 · 通用 NPC／對話／快速移動 | Done | generic NPC、對話、mini-map、走路／直接選單等價 | 真實 roster 仍 F4；隨機生成／巡遊規格不自動視為已核准 |
| E4 · Nuxt portal and overlay bridge | Done | 既有 Vue 面板／獨立頁、URL、focus、scroll、auth、close/back、world pause 與來源場景／物件返回契約 | 關閉回原設施；R 出口到 Campus 對應入口，不全域攔截 Classic 輸入；Canvas 不擁有表格／表單／權限 |
| E5 · World/session state | Done | last valid scene／position／facing／return context、account isolation、version migration 與復原 | refresh／relogin／Classic 往返安全恢復；壞位置回安全點，不只依賴 browser history；無 client secrets |
| E6 · Runtime release gate | In progress | desktop／narrow／keyboard／reduced-motion／低階裝置／long-idle 稽核 | 達 A4 loading、FPS、memory、input、cleanup 與 crash-fallback budgets |

#### E 分項執行與驗收界線（2026-11-04 重排）

**最新 E2.5 人工結案（2026-11-05）：** 使用者對統一包五項清單回報「都可以」，E2.5 Done，總進度 30／59；E2 原項與 E2.1–E2.5 全數完成，不再重問同一批畫面／接線。下一個 Planned 為 E3 共用物件互動框架，尚未自行開工。另已確認 In game 後端 replay scalar columns 保留 `p_throws`，Selected Pitch 前端以 Throws 顯示，Batter Personal 原始 rows／hand split 也有該欄。熱圖不是缺投手手別資料；待擴充的是獨立 pitcher_hand 查詢與各格比率分子／分母。相關需求在 Game Center 主文件 6.1，本次未改母站功能或執行畫面測試。下方 v4 pending 文字是人工通過前快照。

**最新 E2.5 統一包（2026-11-05）：** 使用者明確要求開始 E2.5。`build_ballpark_scene_package.py` 將 v3＋Game＋Batting/Pitcher＋Clubhouse annex 依原 runtime 的合併次序製成 v4，原 authoring 包／背景保留；不重新產圖或修改碰撞座標。runtime 與 play fallback 改讀單一 `scene-kit-v4.json`，共 9 場景／59 個穩定物件 ID、211 collision／147 foreground／21 portals／2 hotspots。`object_index` 分開已定位 bounds／實際 portal target 與未定位候選／未接線業務，不把盤點功能文字當已啟用 action。`petehub_ballpark_scene_manifest_v4.json`、`output/ballpark/scenes-v4/` 留背景 hash、原來源 hash、image_size／world_scale、物件 refs、體積與可重現匯出；九張背景合計 22,587,524 bytes，decoded RGBA 合計 56,633,144 bytes 是資產估計，不是同時 GPU 使用或效能測量。數值／source-only 來源及單次直接 vue-tsc 通過，沒有重跑舊場景 BFS、完整 build／audit 或任何瀏覽器測試。E2.5 保持 in_progress，人工只驗統一包的固定導覽／入口／C-R／team／fallback 接線，不重審已接受畫風。E3、NPC 或母站熱區圖本輪未實作。

**NPC 美術／對話順序：** 現有 D4 V2 球員樣本不是完整隊伍 NPC。E3.3 開始通用 NPC identity、靠近／選單互動與對話觸發、取消／focus／pause 基礎；E3.1 為既有場景物件接線。F4 再製作／映射所屬隊伍 8–10 名代表球員 V2 外觀（可參考既有官方大頭照來源），綁官方 active roster、個人數據與各自對話；吸菸區的出現／抽菸／聊天亦於 F4 細化。F2 負責牛棚投手與其 generic 投球及 In game，非整個 roster 一次重製；正式人體 mechanics／揮棒仍 G3–G5。實際新增角色美術與對話內容須在對應 Slice 開工後逐批交使用者驗收，不因 E2.5 組包開始而自動製作。

**最新結案（2026-11-05）：** 使用者對新增後門／吸菸區及含盤點的五項清單回報「都可以 通過」，E2.1 Done，總進度 29／59。E2 原項及 E2.1–E2.4 全部完成；E2.5 九場景統一包仍 Planned，未自動開工。環境／盤點通過不代表未來 NPC、角色動作或業務物件已接線；不重開 D4、D5 或重新驗收已接受場景。下方待驗文字屬先前快照。

**User／NPC 動作盤點（2026-11-05，需求釐清，不是動畫開工）：** 可沿現有 2D runtime 擴充角色動作，但現有 V3 User／V2 NPC 素材正式 clip 只有四方向 idle／walk；NPC 代表樣本有素材，完整 roster actor 尚待 F4。吸菸／聊天為 E3.3／F4 預留，牛棚 generic 投球為 F2 預留；正式 motion pipeline／投球／揮棒另為 G3／G4／G5。蹲下、坐下、碰拳、臥推、傳接球，以及 User 與 NPC 各可執行哪些動作、主動選單或自動情境觸發，尚無完整 clip／狀態／驗收清單，記為本次詢問的候選需求，不宣稱已排定或已製作。坐下／臥推需要座椅及器材接點、遮擋與離開動作；碰拳／傳接球需要雙角色站位、同步事件及可取消復原；每個角色外觀／方向／道具／reduced-motion 都須有素材與 fallback。日常情境動作可以是 generic 像素動畫，不必等待或冒充 Section G 的精確棒球 mechanics；投打左右側及 release/contact、歷史球路／影片 identity 仍遵守原契約。後續需另列 User/NPC 共用動作規格並獲開工指示，不用重做已完成 D4，也不由本次問答新增自動執行的 Slice。

**最新 E2／E2.3 通過與 Clubhouse 附屬區（2026-11-05 接續中斷工作）：** 使用者明確接受 E2、E2.3，兩項 Done，總進度 28／59；E2.1 須等新增物件完成且使用者盤點後才能結案。依黃框於 Clubhouse 餐飲區右牆增小門，`clubhouse-backdoor-v1.png` 為局部編修，原素材不覆寫；靠近 C 進 `clubhouse-smoking-area`，南門 R 返回 `clubhouse/smoking-door` 到達點。新吸菸庭院 1672×941、17 collision／15 foreground／1 return portal；長椅、煙灰缸與兩個未來球員抽菸／聊天候選點已列盤點，現為九場景／59 物件。完整提示詞、圖片 hash、明確 1670→1672 的 Clubhouse 背景座標縮放與來源檢查在 `petehub_ballpark_clubhouse_annex_v1.json`；可編輯包 `scene-kit-clubhouse-annex-v1.json` 與 SVG／manifest 另存，v3 base 不改。新增 C 鍵有靠近／失焦／表單／暫停防護，保留等價按鈕／固定導覽；資料與型別檢查不是人工畫面通過。新門／庭院／往返待使用者驗收。偶爾刷新球員抽菸與聊天屬後續 E3.3／F4：遊戲虛構情境，不推論真人習慣；名單、頻率、動畫及對話內容待實作時細化，本次沒有 NPC、煙霧動畫或聊天功能。E2.5 整合範圍擴為九場景，仍 Planned；下方較舊的 26／59、八場景與 E2／E2.3 待驗文字均屬歷史快照，不再重問已通過項目。

**最新人工結案與剩餘項目：** 使用者以「都可以」接受 Pitcher v2 兩牛棚 In game、左台 Shape 及通道／遮擋／R 出口三項清單，E2.4 Done，總進度 26／59；Game E2.2 已完成，不再重問。未明確結案的是 E2 原本失焦／暫停／表單輸入防護、移動／Safe reset 與可用 touch/gamepad 操作（無裝置記未測，不造 pass）；E2.1 的 52 物件盤點完整性／功能分配；E2.3 Batting 入口、走道／圍網／遮擋、R 返回、team／direct fallback。E2.5 八場景統一包尚未製作，不是現成待驗項目。本次只同步使用者回報，沒有代理畫面測試或新 Slice 開工；下方 Pitcher pending 文字屬結案前快照。

**最新 Pitcher In game 配置（2026-11-04）：** 依使用者要求，兩條牛棚道均改為 In game，穩定 ID 為 `in-game-west`／`in-game-east`，取代舊 `bullpen-lanes` 群，盤點總數由 51 成為 52。`pitcher-mound-v2.png` 由內建 image_gen 局部修改，左分析台移除原 In game 螢幕，只留 Shape；原 v1 保留。來源、完整 prompt／hash 與規格在 `petehub_ballpark_pitcher_in_game_layout_v2.json`。碰撞／遮擋／出口座標未變；新圖與兩區配置待使用者驗收，未由代理進行畫面或操作測試，也不重跑完整 typecheck／build。

**未來牛棚功能已納入：** E3.2 為兩區提供同等的投手／場次 DOM 選單及 team／player／game／pitch intent，E4 處理面板開關、pause／focus 與返回原牛棚。F2 再製作球員隨機刷新與道內投球展示：帳號 favorite team 為預設，切 Viewing team 跟隨瀏覽隊伍，投手候選遵守官方 active-roster contract；手動選擇不被隨機刷新覆蓋，無名單／無出賽須顯示 unavailable。場次沿用共用 Personal In game（預設所選年度最近出賽，保留明確選擇），逐球資料與影片不另寫一套。人體投球為明示 generic 動作，不能宣稱重建該球員歷史 mechanics，不能改 Statcast 軌跡；需獨立動畫及牛棚前／後網遮擋分層，確保道內角色可見。刷新頻率、兩道去重與動畫規格在 F2 實作前細化。本次只交配置與規劃，尚無投手 actor、隨機刷新、投球動畫或選單功能；也未開始 E3／E4／F2。

**最新 Game 結案與 Batting／Pitcher 交付：** 使用者明確回報「game區的介面驗證通過 然後batter pitcher區也開始做」，E2.2 Done，25／59。新兩站沿用已核准原圖，分別複製至 `batting-cages-v1.png`／`pitcher-mound-v1.png`，不重畫。`scene-kit-e2-3-4-v1.json` 獨立追加 Batting 16 collision／14 foreground、Pitcher 19 collision／17 foreground；每站一個 R 出口與五個物件 bounds／approach，練習網籠／牛棚道目前為裝飾與阻擋。可編輯 SVG／compact JSON 在 `output/ballpark/scenes-e2-3-4-v1/`，manifest 與來源證據同步。Campus Batting／Pitcher 入口及固定按鍵進房，南側 R 回各自 Campus 到達點；Nuxt 保留 URL／Viewing team／Static／Classic ownership，原五場景 v3 不變。只做新包數值幾何／來源與一次直接 vue-tsc，不執行瀏覽器或操作驗收；E2.3／E2.4 保持 in_progress，等使用者人工回報。Directory／Stats／Compare／Lab／Shape／In game 等業務物件仍未接線，留 E3.2／F2；不開始 E2.5 統一包或 E3 之後。以下 Game 待驗、Batting／Pitcher 未製作等文字只屬先前快照，現況以本段及表格／tracker 為準。

**最新核准與 E2.2 短批交付：** 使用者明確回覆「三張都可以接受」，三站背景設計已核准，不再重審。為控制單批耗時，先交 Game 可走動版：核准原圖原樣複製為 `game-center-v1.png`，新增 `scene-kit-e2-2-v1.json`、`petehub_ballpark_scene_manifest_e2-2-v1.json` 與 `output/ballpark/scenes-e2-2-v1/` 可編輯 SVG／compact JSON。含 21 碰撞、19 遮擋、1 R 出口及三個未啟用功能的物件 bounds／approach。runtime 在 v3 外加獨立補充包，只 override Campus GAME target，原五場景 source hash 不變，未開始 E2.5 統一包。Nuxt 仍管 URL／Viewing team，Phaser 只在既有 lazy runtime 使用新房間；Static／Classic 直接入口保留。數值入口／站位可達、匯出可重現、單次直接 vue-tsc PASS，證據／五項人工清單為 `petehub_ballpark_e2_2_source_gate_v1.json`；未開瀏覽器／截圖／走角色。新房間在 `/ballpark/play?room=game-center` 待使用者驗收，E2.2 不標 done。Batting／Pitcher 只核准美術，待後續短批分層，不推定操作通過；E2.1 仍未明確結案。

下方「候選待核准／未改 runtime」為本次使用者核准前的歷史交付，現況以上段及 tracker 為準。

2026-11-04 使用者後續明確回報「E1可以，開始E2.1–2.4」，E1 因而 Done，這四項開始第一個短批次；E2.5／E3 之後不在本次授權內。第一批建立盤點與三站設計 brief；其後使用者再次要求開始 E2.2–E2.4，已沿用配置產三張新圖候選，仍未改 runtime，且不能把開工指示當作 E2.1 完整盤點或新圖的人工核准。E2 原項是既有五場景的移動／相機／碰撞與輸入防護，不是子項總括；E3 收斂共用框架，NPC／travel 移到 E3.3。八份獨立交付不以父項自動帶入完成，亦不阻止原 E1／E2 依原範圍結案。

**E2.2–E2.4 新背景候選交付：** `output/ballpark/e2-facilities-v1/` 的 `game-center-concept-v1.png`、`batting-cages-concept-v1.png`、`pitcher-mound-concept-v1.png` 均為 1672×941；內建 image_gen 以既有 Team Office clean v1 作畫風參考產生新場景，沒有修改或重新送審舊背景。完整提示詞、原始生成路徑、參考 hash、PNG 大小與 hash 存在 `data/sample/petehub_ballpark_e2_facility_concepts_v1.json`。素材規範要求先以 concept candidate 交付，`production_eligible=false`／`runtime_wired=false`，碰撞／foreground／觸發範圍仍未製作；檔頭尺寸與 hash 紀錄不是畫面驗收。使用者確認三張新設計的物件配置、通道和南側出口後，才製作可編輯場景包並接入既有 runtime。投手分析台預留共用 Personal In game，母站模組已存在不代表 Ballpark 物件已接線。E2.1、E2.2–E2.4 維持 in_progress；未開始 E2.5／E3 之後。

- **E1／E2 現況：** E1 已由使用者整體接受，人工清單同步；不推定特定裝置／數值認證，不重問 E1。E2「目前沒大問題」仍只記正向整體回饋，未補造每一輸入裝置／碰撞的逐項通過。正式 bundle／GPU／效能留 E6，不要求本次重跑。
- **E2.1 第一批交付：** 權威 `data/sample/petehub_ballpark_object_catalog_v1.json` 由 `backend/scripts/build_ballpark_object_catalog.py` 生成 `output/ballpark/object-catalog-v1.md`。51 個語意物件／候選及三站 layout brief，另逐一列出目前 138 collision／82 foreground／16 portals／2 hotspots；幾何列數不等於實體物件數。程式只讀 JSON／座標／hash，未看圖／瀏覽器。父層 bounds 只是參考外框，看板／螢幕仍須單獨定位互動框；未獨立建模的背景裝飾群及 NPC 點明列待補。草案不是已完成畫面物件盤點或業務接線，待使用者確認配置／補漏後才可關 E2.1。
- **返回問題歸屬：** 三站 Campus 入口現均進各自可走動房間，R 回對應 Campus 到達點；Game 已由使用者接受，新 Batting／Pitcher 待驗。直接 `/games/today`／`/batters`／`/pitchers` 保留，Classic 不全域攔截 R。未來功能面板關閉／history／focus 仍由 E4 負責，卸載／refresh 的安全位置恢復仍為 E5；不能以本次房間出口宣稱所有 Classic 返回問題已解決。
- **E2.1 盤點規格：** 單一 versioned JSON 及由其生成的可讀表，包含 scene/object ID、名稱／位置或 bounds、裝飾／阻擋／互動標記、collision／foreground refs、觸發方式、action／canonical fallback、game/player/team context、權限／資料依賴、負責 Slice、實作／驗收狀態。既有五場景完整列主要設施／家具／可互動候選，重複植栽／燈具可明確分組；三新站先列 planned，核准設計後補實際範圍。不把碰撞清單冒充完整盤點，不為盤點重畫或切割全部背景。
- **三站功能配置：** Game 預留賽程看板、選定比賽分析控制台、回放／影片螢幕；Box Score／Location／Sequence／Movement／Pitch Replay 共用選定比賽／投手脈絡，影片附屬比賽／球路。Batting 預留選人、個人分析、比較及已發布 Lab；Pitcher 預留選人、個人球路／位置分析及比較。先由 E2.1 確認物件功能再產新背景；研究未發布或資料 unavailable 不能假裝可用。
- **素材交付：** 新場景沿用核准畫風、1672×941 世界／現行足底契約及同一 lazy runtime；新設計由使用者核准後才生產獨立碰撞／foreground／portal、可編輯來源與可重現輸出，manifest 留來源／生成與修改紀錄／hash。現有五場景不重畫；D5 done 僅覆蓋已接受素材，新素材驗收落 E2.2–E2.5，完整 runtime gate 仍 E6。
- **接線不等於業務完成：** E3／子項是物件、prompt、typed intent、context 與直接選單；E4 後才完成 Vue 面板關閉／返回。F1–F6 負責對應既有功能的實際資料／權限／freshness／Classic parity，不重寫分析公式，也不以 placeholder 冒充完成。Nuxt 仍是 URL、auth、DOM owner，FastAPI 是資料 owner；不靠 iframe 複製另一套網站。
- **建議順序：** 原 E1／E2 完成人工結案 → 另獲開工指示後 E2.1 → E2.2／E2.3／E2.4 逐站設計核准與製作 → E2.5；E3 框架依盤點規格定義，先接 E4 的最小 bridge 再交 E3.1／E3.2 實際開關返回驗收，避免依編號假設所有 E3 子項先於 E4 完成。E3.3 不提前做真實 roster；E5／E6 依擴充後場景與返回情境驗收，之後 F 完整功能接線。

### Section F · Petehub World Facilities

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| F1 · Main field, Game and Leaderboard | Planned | GAME gate 連 Game Center；外野記分板呈現 Leaderboard | canonical route／game identity／ranking as-of 一致；記分板不是唯一入口 |
| F2 · Pitching and Batting facilities | Planned | 七個子項 F2.1–F2.7：母站共用三維歷史 In game、rig／clock／揮棒資料介面與 gate，以及原兩牛棚／投打設施 parity | 詳見最上方 2026-11-06 分項；不改 2D 園區／原始軌跡，不把 generic 動作當真實量測；parent 需完成其實際範圍，不因規劃先 done |
| F3 · Training & Lab | Planned | 集中 Stuff+、Location+、Stamina、Performance State、比較與計算器 | 研究與 production 標示清楚；不複製公式 |
| F4 · Clubhouse active-roster experience | Planned | 主隊休息室、8–10 名場景 NPC、完整 PLAYER LIST、球員互動與個人數據；吸菸附屬區預留偶爾刷新球員抽菸與聊天 | official active roster／as-of 顯示；選單永遠可直接選人；附屬區刷新頻率、虛構情境動畫／聊天及通道不阻擋待實作 |
| F5 · Team Office | Planned | 主隊預設；Coach Office 放輪值／牛棚／打線，GM Office 放交易／薪資／合約 | 球隊切換、資料 freshness、權限與 Classic Team page 一致 |
| F6 · Video／Game Room and parity gate | Planned | 現階段推薦影片；保留未來 mini-game 空間；完成全設施 route parity audit | video unavailable 誠實 fallback；所有核心 route 可 direct-link／Classic 到達 |

### Section G · Baseball Motion Lab（Post-MVP）

2026-11-06 責任調整：下表保留 Planned，專指 F2 之後的球員專屬資料／動作、擴充 Lab 與 simulation event bridge；通用歷史場景 renderer、基本 rig、投打 clock 與首批相機 gate 改由 F2.1–F2.6 唯一實作。G1 延伸 player bio／stance coverage，G2 只在 F2 有實測限制時比較進階 engine，G3 擴充專屬 clips／retarget，G4/G5 擴充專屬動作與未來 H 的事件適配，G6 認證擴充 Motion Lab；不重做已交付通用能力，不自動授權 synthetic simulation。

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| G1 · Motion data and bio feasibility | Planned | 稽核身高／體型／投打側／stance／motion asset 與可追溯 bio cache | 缺值用明示 generic fallback；不得由 release point 推測身高 |
| G2 · Engine decision spike | Planned | 比較 Phaser skeletal、Babylon 與不升級 | 量測畫質／bundle／FPS／memory／開發成本／mobile 後才選 engine |
| G3 · Rigged asset and animation pipeline | Planned | 核准 2D skeleton 或 Blender/glTF、rig、clips、IK、provenance | reusable clips、license、size 與左右側規則通過 |
| G4 · Pitcher motion and release event | Planned | state machine 與明確 release event 接 replay／simulation path | 人體動畫不得改 trajectory；左右投／arm slot／pause/replay 對帳 |
| G5 · Batter swing and contact event | Planned | stance／load／swing／check／miss／contact 與 timing feedback | 左右打、早晚／高低、take／check cases 通過 |
| G6 · Motion Lab release gate | Planned | camera、HUD、audio、reduced-motion、device 與資源稽核 | 未達 gate 維持 Lab，不取代 SVG Replay |

### Section H · Deterministic Simulation Game（Post-MVP）

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| H1 · Simulation domain contract | Planned | 分離 historical replay 與 synthetic simulation；版本化 seed／clock／state／event log | deterministic replay；synthetic event 不寫成真實 Statcast |
| H2 · Roster, ratings and role state | Planned | point-in-time ratings、左右側、球種、疲勞、替補與 fallback | source fingerprints／season boundary／unavailable state 清楚 |
| H3 · Pitch choice, location and outcome | Planned | 只串接通過研究 gate 的元件 | probability／calibration／impossible event／cold start／leakage tests |
| H4 · Inning, game and AI state machine | Planned | count／PA／base-out／換人／延長賽／AI strategy／catcher context | 規則 fixtures；AI 不偷看結果、無不支援的 causal claim |
| H5 · Balance Lab and simulation gate | Planned | Monte Carlo、難度、存檔、長局、效能與版本稽核 | distributions、replay、API/schema/browser gates 通過 |

### Section I · Security、Release 與後續擴充

| Slice | 狀態 | 交付內容 | Exit gate |
|---|---|---|---|
| I1 · Threat model and trust boundary | Planned | auth／save／client tampering／未來 UGC／多人／asset upload | server-authoritative／client-only、abuse path 與 mitigation owner 凍結 |
| I2 · Deployment and observability | Planned | asset manifest、CDN/cache、errors、performance、rollout／rollback | 可回 Classic；舊新 asset 不混用；故障可定位 |
| I3 · Accessibility and device certification | Planned | keyboard／touch／screen reader bridge／reduced-motion／contrast／低階裝置 | 不支援裝置自動進 Classic UI，不顯示壞場景 |
| I4 · Closed beta and migration | Planned | opt-in beta、回饋、save migration、退出與資料刪除 | 不強迫既有使用者；任務成功率、穩定度與 rollback rehearsal 通過 |
| I5 · Default-entry and post-MVP gate | Planned | 決定是否改預設入口；另排 3D avatar／多人／經濟 | 所有前置 gate 與明確產品決策通過才改預設 |

## 4. 依賴與執行順序

MVP 主路徑：`A → B → C → D → E → F`。C 先凍結主隊、roster 與權限；D 才生產資產；E 才重啟 runtime；F 完成設施 parity。G／H 均為 Post-MVP；I 負責正式發布。

可平行項目：

- C1 profile schema 與 C2 roster contract 可在 B4 後平行。
- D1 manifest 與 D3 avatar contract 可在 C schema 凍結後平行。
- Post-MVP 的 G1／H1 可先做純研究 contract，但不得拖慢 MVP 或先做產品宣稱。

不可平行或不可跳過：

- 未完成 B4 不開始 production tileset／sprite 批量製作。
- 未完成 C5 不讓 Clubhouse／Team Office 消費未版本化的 profile／roster／權限資料。
- 未完成 D5 不把 AI 示意圖當 production asset。
- 未完成 E6 不把 Phaser 放進全域 app shell。
- 三維分析限定在 F2：F2.1 的來源／單位／引擎／載入與預算決策完成並另獲實作授權後，才可加入該局部 renderer dependency；不提前放進 production／全域 app shell。G 的進階 engine 擴充仍須先完成 G1，不能藉 F2 規劃自動安裝 Babylon／Havok。
- 未完成 H1 不混用 historical Replay 與 Simulation event vocabulary。
- 未完成 I4 不把 Ballpark 設為預設登入入口。

## 5. MVP 與明確非目標

第一個可發布 MVP 到 F6 為止：俯視像素 RPG Ballpark、主隊／active roster、角色、自由移動、fast travel、設施入口、Nuxt overlay 與 Classic parity。Motion Lab、完整 simulation、3D 捏臉、多人與遊戲經濟均不是 MVP 必要條件。

2026-11-06 規劃擴充僅將「局部共用歷史 In game 三維分析」與基本可動投打模型納入 F2；不把整個 Ballpark、User creator、所有真實 NPC 改成 3D，也不代表已滿足 F2.6／E6 的 production gate。

不接受的捷徑：

- 用單張 AI 圖拉伸成正式角色動畫。
- 讓 Canvas／WebGL 接管資料表、表單與可存取文字。
- 以走到特定位置作為存取核心分析功能的唯一方式。
- 直接讓 client 決定未來多人或競技結果。
- 因畫面需要而改寫 Statcast 座標、落點、球路或研究結論。
- 在沒有量測前承諾 2K 畫質、完整臉部雕塑或所有行動裝置流暢運行。

## 6. 全專案驗收標準

每個 Section 關閉前至少完成：相關 unit/integration tests、schema 或 contract smoke、Nuxt typecheck、UTF-8、`git diff --check`、Playwright desktop/narrow interaction、console severe error、資源與 memory cleanup、reduced-motion、Classic UI fallback。涉及 simulation 時再加 deterministic seed、event-log replay、calibration 與 impossible-state tests；涉及新資產時再加 license/provenance、atlas/glTF size、LOD 與版本 manifest。

驗收責任分開處理：可重現的 API、schema、auth、migration、typecheck 與 regression tests 由 assistant 完成；畫風、視覺一致性、操作手感與真實裝置顯示可交由使用者依最多七項短清單驗收。等待使用者回報期間不重跑同一套 browser matrix，且沒有使用者明確核准時不得把 subjective acceptance 標成通過。完整成本與止損規則以 `AGENT_WORKFLOW.md` 為準。

## 7. Slice A3 · Petehub project skills

2026-10-30 使用官方 `skill-creator` initializer 建立以下 repo-local skills；每個 skill 都有 `agents/openai.yaml`、一份精簡 entrypoint 與按需讀取的 reference：

| Skill | 主要 reference | Trigger 邊界 |
|---|---|---|
| `.codex/skills/petehub-game-architecture` | `references/boundaries-and-contracts.md` | 只處理 Ballpark 的 Nuxt/runtime/FastAPI、route、overlay、save 與 fallback 邊界；一般 Nuxt 功能不觸發 |
| `.codex/skills/petehub-baseball-motion` | `references/motion-data-contract.md` | 只處理 Statcast 座標、左右投打、motion event、replay/simulation 與 generic fallback；一般圖表動畫不觸發 |
| `.codex/skills/petehub-game-art-pipeline` | `references/asset-contract.md` | 只處理 Aseprite／Blender 到 atlas／glTF 的 production pipeline、manifest 與 provenance；moodboard／一般網站圖片不觸發 |
| `.codex/skills/petehub-game-performance-audit` | `references/audit-protocol.md` | 只處理明確的 baseline／performance／compatibility／release gate；一般 UI debug 不觸發 |

驗證結果：四個目錄均通過 `skill-creator/scripts/quick_validate.py`；無 initializer TODO 殘留；frontmatter description 能區分相鄰工作；每個 reference 都由 `SKILL.md` 說明何時讀取。固定禁止事項包括：A4 前不加入 Phaser、F2 前不加入 Babylon/Havok、不把 engine 放進全域 app shell、不修改 Statcast 原始資料、不用 AI 單張圖冒充正式動畫 atlas，以及不把未執行的 performance check 列為 pass。

## 8. Slice A4 · 2026-10-30 Classic UI baseline

原始 evidence：`data/sample/petehub_ballpark_a4_baseline_2026-10-30.json`。視覺 artifact：`output/playwright/a4-login-narrow-reduced.png`。本節是加入任何 Ballpark runtime dependency 前的現況基準，不代表未來 runtime 已達 gate。

### 8.1 環境與重現方式

- Windows 11 Home `10.0.26200`；Intel Core Ultra 7 258V（8 logical processors）；33,804,771,328 bytes RAM。
- Node `20.20.2`、npm `11.12.1`、Nuxt `3.21.8`、Nitro `2.13.4`、Vite `7.3.6`。
- Production build：`cd frontend && npm run build`；本次 3:07.734 完成，client 3061 modules、server 756 modules。只有 Vue／VueUse dependency 的 Node `DEP0155` warning，無 build error。
- Backend：`cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`；本次量測使用當時已在 `8000` 監聽的同一 backend virtualenv 服務。
- Frontend：在 `frontend` 設 `PORT=3100`、`NUXT_API_INTERNAL_BASE=http://127.0.0.1:8000/api`，執行 `node .output/server/index.mjs`。
- 所有 loading 數值來自 local loopback、無 network/CPU throttling；不能外推為部署環境或低階裝置結果。repository commit 為 `d5f3ad1fed5010635b522f7fa9d0c0bc011ba523`，且量測時保留使用者既有 dirty worktree。

### 8.2 Bundle 與 route loading

| 範圍 | Files | Raw | Gzip |
|---|---:|---:|---:|
| 全部 emitted client JavaScript（含所有 lazy chunks） | 96 | 1,203,362 B | 419,025 B |
| 全部 emitted client CSS（含所有 routes） | 73 | 520,259 B | 112,390 B |
| 合計 | 169 | 1,723,621 B | 531,415 B |

Nuxt 目前先回傳 SSR HTML，再載入 hashed client assets；route CSS 與其他 route chunks 分離。`/login` fresh browser context 實際為 8 個 resource entries、263,455 B transfer／260,755 B encoded body；同一 browser warm cache 後為 13,618 B transfer（cache body 不再計入 `transferSize`）。這是 Classic UI 基準；目前沒有 Phaser、Babylon、WebGL runtime 或 Ballpark asset request。

### 8.3 Loading 實測

每個 browser 建立三個 fresh context，viewport `1280×720`，等待 `load` 後再等待 750 ms；表中是三次中位數：

| Browser | Version | TTFB | DOMContentLoaded | Load | FCP | LCP | Severe console |
|---|---|---:|---:|---:|---:|---:|---:|
| Chrome | 153.0.8010.48 | 20.5 ms | 166.4 ms | 184.2 ms | 164 ms | 164 ms | 0 |
| Edge | 155.0.4283.62 | 23.1 ms | 182.6 ms | 191.1 ms | 168 ms | 168 ms | 0 |
| Firefox | 156.0 | 28 ms | 206 ms | 218 ms | 169 ms | 169 ms | 0 |

LCP 由 navigation 前註冊的 buffered `PerformanceObserver` 收集。這些結果只代表本機 production server 的未登入 `/login`；不得當成真實網路 p75。

### 8.4 Memory、frame 與 cleanup

- Chrome `/login` 等待 2 秒的 `performance.memory.usedJSHeapSize` 為 5,620,091 B。
- `/login ↔ /register` 使用 client navigation，於每 10 個來回後等待 1 秒並執行 CDP `HeapProfiler.collectGarbage`：0／10／20／30 cycles 分別為 2,511,545／4,263,057／4,452,577／4,554,677 B。首 10 cycles 包含 lazy route 載入；10→30 cycles 增加 291,620 B。這是 retained-heap baseline，不足以單獨證明或排除 listener leak。
- 未登入 `/login` 靜態頁的 3 秒 `requestAnimationFrame` sample 為 180 frames、median 16.7 ms、p95 17.0 ms、約 60.0 FPS、0 frames >20 ms。頁面沒有 Pitch Replay 連續動畫，因此這個數值是 scheduling baseline，**不是** Pitch Replay／Ballpark FPS pass。
- 跨瀏覽器 listener count API 不可用；目前只保留 forced-GC route-cycle evidence。C1/C5 必須加入 runtime mount/unmount 的 loop/listener/GPU cleanup 專項驗證。

### 8.5 Compatibility 與 auth matrix

| 項目 | Chrome | Edge | Firefox | 結果／限制 |
|---|---|---|---|---|
| Desktop `1280×720` cold load | Pass | Pass | Pass | 實際 production route，三次 fresh context |
| Narrow `390×844` | Pass | Pass | Pass | 無 horizontal overflow；這是 viewport，不是實體 mobile |
| `prefers-reduced-motion: reduce` | Pass | Pass | Pass | media query 實際為 `true` |
| Keyboard | Pass | Pass | Pass | focus 順序：username → password → Sign in → Request access |
| 未登入 protected route | Pass | Pass | Pass | `/games/today` 導向 `/login?redirect=/games/today` |
| Severe console error | Pass | Pass | Pass | compatibility run 為 0 |
| 登入後 routes／admin | Blocked | Blocked | Blocked | 沒有核准憑證或既有 authenticated session；未建立或猜測帳號 |
| Pitch Replay FPS／interaction | Blocked | Blocked | Blocked | 代表場景在登入後；不得用靜態 login FPS 代替 |
| 實體 mobile／低階裝置 | Unavailable | Unavailable | Unavailable | 無 attached representative hardware；未以 resize 偽稱 device pass |
| Input latency | Limited | Limited | Limited | keyboard reachability 已驗證，未量測登入後代表互動 latency |

窄版 reduced-motion 截圖已人工查看：完整 login hero、表單、focus ring 與 Request access 均可見，未出現水平裁切。

### 8.6 後續 gate 使用的 budgets（尚未通過）

以下是未來 C/E/F release gate 的明確預算，與上面的現況量測分開；A4 不宣稱它們已通過：

- Classic UI initial route transfer ≤300,000 B，且非 Ballpark route 不得要求 Phaser、Babylon、WebGL runtime 或 Ballpark assets。
- 部署環境 supported desktop 的 LCP p75 ≤2,500 ms、代表互動 p75 ≤200 ms。
- Ballpark runtime desktop p95 frame time ≤20 ms；p95 >33.3 ms 時必須降級或提供 Classic UI，而不是隱藏卡頓。
- 相同 route pair 完成 lazy warm-up 後，20 cycles forced-GC retained-heap 增量 ≤1 MiB；runtime 另需零殘留 loop/listener/GPU resource 的可觀測證據。
- 上述 budgets 必須在 deployed network、authenticated representative routes 與至少一台真實低階裝置重新量測；本次 unavailable 項目不得沿用為 pass。

## 9. Slice B1 · User journey and fallback contract

本節是未來產品行為契約，不代表 `/ballpark`、角色建立或 runtime 已實作。已驗證的現況只有 Nuxt auth middleware、登入 redirect、Classic routes 與現有導覽；Ballpark 行為要到對應 Slice 才能標成 browser pass。

### 9.1 入口、owner 與不可混用的狀態

- 在 H5 明確決策前，`/` 永遠是預設 Classic 首頁。C1 才可建立獨立且 lazy-loaded 的 `/ballpark`；B1 不新增 route 或 dependency。
- Nuxt 是唯一 URL、auth、history、DOM overlay、表單、資料表與 accessibility owner。Ballpark runtime 只能提供位置、移動、prompt 與場景狀態，不能建立第二套 router。
- FastAPI 與既有 service 仍是資料 owner；runtime 不複製公式、權限或 API 語意。
- 現有 `site-brand-mode` cookie 只代表 Peteclub／Petehub 品牌顯示，不得解讀成 Ballpark opt-in、最後位置或存檔。
- B1 沒有新增 persistence。C4 必須另定 versioned world/session state，且不得序列化 engine object 或敏感資料。

### 9.2 核心 journeys

| Journey | 開始 | 必須行為 | Skip／fallback |
|---|---|---|---|
| 未帶 redirect 的首次／一般登入 | `/login` | 登入成功回 `/` Classic | C1 後可顯示可選 Ballpark CTA，但不得自動進站 |
| Protected Classic 深連結 | 任一 Classic URL | 未登入先到 `/login?redirect=<exact fullPath>`；成功後回原 URL | redirect 只接受同 origin 的 `/...`，不接受 `//...` |
| 未來 Ballpark 深連結 | `/ballpark` | 未登入先到 `/login?redirect=/ballpark`；登入後才載入 runtime | runtime 不可用就顯示 Classic `/` 與對應區域入口 |
| 第一次進 Ballpark | optional CTA | 預設角色永遠可用；提供 Customize now 與 Later／Skip | Skip 直接以預設角色進 Arrival Plaza；不得強制完成細部捏角 |
| 回訪 | 一般登入或 `/ballpark` 深連結 | H5 前一般登入仍回 Classic；直接 Ballpark 才進站 | C4 後只能還原最後「有效且版本相容」狀態，否則回 plaza 並顯示修復訊息 |
| Ballpark → Classic | 常駐切換或 zone activation | 開啟唯一 canonical Nuxt URL | 不依賴 Canvas 才能讀取頁面內容 |
| Classic → Ballpark | 常駐切換／browser Back | 回 `/ballpark` 並將焦點交回已記錄的安全互動點 | runtime 無法恢復時回 plaza，不嘗試回到非法座標 |
| session 到期 | Ballpark 使用中 | 暫停並清理 runtime，導向帶 `/ballpark` redirect 的登入 | 重新登入只恢復安全狀態；失敗則回 Classic |
| runtime／asset error | 載入或執行中 | 顯示可理解錯誤、Retry 與 Classic fallback | 禁止自動 reload loop；核心功能不可一起消失 |
| reduced motion／低效能／不支援裝置 | 進站前或執行中 | 尊重偏好並允許降級 | 自動或一鍵切回 Classic；不得顯示破損場景 |

Pending／disabled account 不能進 world。非 admin 使用者可看見 Front Office 的一般名稱與鎖定原因，但不得預取敏感資料；直接 admin URL 繼續由現有 middleware 決定權限行為。

### 9.3 URL、Back、Refresh 與 focus matrix

| 情境 | URL／history | Back | Refresh／direct URL | Focus 與退出 |
|---|---|---|---|---|
| World 內走動 | URL 維持 `/ballpark`，不新增 history | 交給 browser，不當遊戲移動鍵 | 由 C4 從安全 plaza／有效狀態重建 | keyboard、gamepad、touch 不可困住 focus |
| Walk prompt 進區 | 與 fast travel 呼叫同一 bridge，push 一個 canonical Classic URL | 回 `/ballpark` | Classic page 可獨立 SSR／hydrate | 關閉／Back 後 focus 回觸發點或安全替代點 |
| Fast travel 進區 | 與 walk prompt 完全同義，不建立替代 URL | 回 `/ballpark` | 同上 | 選單支援鍵盤，Escape 關閉選單而非破壞 history |
| Classic route 重新整理 | 維持原 URL | 正常 browser history | 不需要隱藏 Canvas 或 world state | 依既有頁面焦點規則 |
| `/ballpark` 重新整理 | 維持 `/ballpark` | 正常 browser history | safe restore；壞檔回 plaza＋訊息 | runtime ready 前由 Nuxt DOM loading／fallback 持有 focus |
| Auth redirect | 保留 exact fullPath | 正常 browser history | 登入頁可獨立載入 | 登入成功後回原任務，不丟失 destination |

所有核心任務必須同時具備至少一個不走路入口：Classic 直接 URL、Arrival Plaza fast travel、或兩者皆有。常駐 Ballpark／Classic switch 必須可由鍵盤操作；Canvas prompt 不能是唯一入口。未來 E1 實作 bridge 時，URL 開啟、focus restoration、scroll lock、auth failure 與 close/back 必須成為同一個共用契約。

### 9.4 Recovery 優先序

1. 若 canonical Classic route 可用，立即提供該 route。
2. 若 zone identity 有效但指定內容不可用，保留 zone、標示 `limited` 或 `unavailable`，並提供最接近的 Classic fallback。
3. 若位置／存檔不合法，捨棄位置而非整份帳號資料，回 Arrival Plaza 並顯示一次性 repair message。
4. 若 runtime 不支援或連續失敗，結束 mount、停止 loop/listener、回 Classic；不得反覆自動重試。

## 10. Slice B2 · Ballpark map and zone information architecture

原始 route inventory 仍保存 55 條 page routes 的 ownership。B3 核准後更新設施名稱與內容：Training Complex 改為 Training & Lab，Front Office 改為 Team Office；Video Room 先承接 Petehub 首頁推薦影片並保留未來 Game Room；GAME gate 與外野 Leaderboard 記分板分別成為 Game／排行榜入口。

### 10.1 概念地圖與 ownership

B2 只固定相鄰關係與功能 ownership，不固定像素座標、tile 或美術比例；B3 可移動幾何位置，但不得偷偷改 route owner。

```text
                         [Leaderboard scoreboard]
                                  |
                 [Video Room]—[Main Field / Scoreboard]
                       \          /
 [Pitcher Facilities]—[Arrival Plaza]—[Batter Facilities]
                       /          \
              [Clubhouse]———[Training & Lab]
                   \          /
                     [Team Office]
```

| Zone | 概念位置／owner | Canonical Classic fallback | 入口與離開 | 權限／現況 |
|---|---|---|---|---|
| Arrival Plaza | 中央 hub；Nuxt shell＋未來 runtime prompt | `/` | spawn、常駐 fast travel、Classic switch | active user；Ballpark route 尚未實作 |
| Pitcher Facilities | 西側 mound／bullpen；Pitcher、Comparison、Rotation | `/pitchers` | walk prompt／fast travel；返回 plaza 或 browser Back | active user；14 routes |
| Batter Facilities | 東側 cages；Batter、Comparison、Batter Lab | `/batters` | 同一 bridge；返回 plaza 或 browser Back | active user；13 routes |
| Main Field | 北側 field／scoreboard；Games | `/games/today` | scoreboard／gate／fast travel | active user；2 routes |
| Video／Game Room | 東側；首頁推薦影片，未來 mini-game 預備空間 | `/` | walk prompt／fast travel；影片仍由 Nuxt DOM 播放 | active user；影片 unavailable 時保留首頁 fallback |
| Training & Lab | 西側；Lab、Fielders、Catchers、比較與計算器 | `/lab` | walk prompt／fast travel | active user；研究／production 狀態必須保留 |
| Clubhouse | 西南 team wing；主隊 active roster 與 player context | team page | walk-up NPC／PLAYER LIST／fast travel | active user；場景只放代表 NPC，完整 roster 由選單提供 |
| Team Office | 東南 team wing；Coach rotation／bullpen／lineup 與 GM transactions／payroll／contracts | team page | team selector／fast travel | active user；`Per aspera ad astra` 彩蛋另以 server-side peter1010 gate 連 `/admin/updates` |

### 10.2 共用 zone state machine

每區 availability 只能使用：`available → loading → ready`，或明確進入 `empty`、`limited`、`locked`、`unavailable`、`error`。互動 UI 使用 `idle → nearby → focused → activating → open → returning`。這些是產品語意，不要求 B2 建立 runtime state machine。

- `loading`：由 Nuxt DOM 顯示且可被輔助技術宣告；保留 Cancel／Back，不用 Canvas 字樣取代。
- `empty`：說明沒有資料的原因，保留篩選、返回與 Classic navigation。
- `limited`：明示 coverage、身份或資料來源限制，不以空白畫面偽裝完整。
- `locked`：顯示所需角色；進入前不請求敏感 payload。
- `unavailable`：說明尚未提供或裝置不支援，提供最近的有效 Classic route。
- `error`：提供 Retry 與 Classic fallback；不得 reload loop。
- `returning`：runtime 只接受 bridge 回傳的 zone／focus token，不接受任意 DOM 或 engine object。

### 10.3 Fast travel 與 navigation inventory

固定順序為 Home、Game、Pitcher、Batter、Video、Training、Clubhouse、Front Office。一般使用者看到 Front Office 為 disabled／Admin required，讓 IA 可理解但不洩漏內容；Video 在 E4 前顯示 unavailable 並導向 Game Center fallback。每個可用項目都必須與對應 walk prompt 使用同一 canonical route activation function。

路由歸屬摘要：

- Pitcher Facilities：`/pitchers`、Pitcher Personal／Similarity／Spin、Comparison、Rotation、Starter／Reliever 共 14 routes。
- Batter Facilities：`/batters`、Batter Personal／Comparison／Leaderboard／Labs 共 13 routes。
- Main Field：`/games`、`/games/today`。
- Training Complex：`/lab` 系列、Fielders／Catchers、`/leaderboards` 共 20 routes。
- Clubhouse：`/teams/{teamId}`；Arrival Plaza：`/`；Front Office：兩條 `/admin/*`。
- `/login`、`/register` 維持 world 外的 Nuxt auth owner；Video Room 目前沒有可捏造的 standalone route。

### 10.4 實作邊界與 B2 exit gate

- Render owner：Nuxt 負責所有可操作 DOM、狀態說明、overlay、表單、表格與影片 modal；未來 runtime 只畫 world 與非必要提示。
- Data owner：現有 FastAPI／service／cache；zone 不建立第二份資料、公式或 permission model。
- Route owner：Nuxt；進入、直接 URL、refresh、Back 必須得到同一功能。
- Permission owner：現有 auth middleware 與 server；runtime 的 locked 外觀不是授權判斷。
- Exit gate：55／55 現有 pages 已有 owner；每區具有 fallback、進出方式、loading／empty／permission／error 語意；所有核心功能皆有不走路的入口。這是 contract／inventory pass，不是 authenticated browser 或 runtime pass。

## 11. Petehub 產品版本、升級與退版生命週期

本節是所有後續 Slice 共用的 release contract。它不代表目前已建立 production release pipeline，也不把 B3 或 H2–H5 標成完成。版本號代表一個可建置、驗證、部署與回復的產品快照；Slice 編號只代表內部工作進度，兩者不得混用。

### 11.1 產品名稱與版本階段

- 現有分析網站對使用者稱為 **Petehub Classic**。在正式盤點其既有 release history 前，不追溯宣稱它是 `v0` 或任意 SemVer；內部基準可用不可變名稱 `classic-baseline-2026-10-30`。
- Ballpark 在正式發布前使用 `0.x.y`：`0` 表示尚未承諾完整向後相容，minor 表示可驗收能力階段，patch 表示不改契約的修復。
- E5 完成 Classic parity、H1–H4 release gates 通過並有明確 release decision 後，才可建立 `1.0.0` release candidate／stable。
- H5 只決定 Ballpark 是否成為預設入口；`1.0.0` 已可正式使用，不代表必須立即取代 Classic 首頁。
- `1.x` 的相容新增使用 minor，例如 `1.1.0`；不改契約的修復使用 patch，例如 `1.1.1`；需要破壞性 route、API、save 或主要操作 migration 時才升 `2.0.0`。

建議里程碑不是自動發版承諾：C1 可形成 `0.2` integration preview、C5 可形成 `0.5` runtime preview、E5 可形成 `0.9` beta、H4 可形成 `1.0.0-rc.1`。只有各自 gate 與 release checklist 通過，才建立對應 tag。

### 11.2 分離的版本維度

產品版號不能取代技術契約版本；每個維度只在自己的相容邊界變更時升版。

| 維度 | 例子 | Owner | 升版條件 |
|---|---|---|---|
| Product release | `1.1.0` | Product／release owner | 對使用者可交付的一組功能與修復 |
| Frontend build | commit SHA＋build ID | Nuxt deployment | 每個不可變 build artifact |
| API contract | `/api/v1` 或 schema version | FastAPI | request／response 發生需協調的 breaking change |
| Database schema | migration revision | Backend/data | schema migration；不直接等同產品版號 |
| World save | `world_version` | C4 contract | world state schema 或 reconciliation 改變 |
| Avatar save | `avatar_version` | D1 contract | avatar domain schema 或資產對應改變 |
| Simulation | `simulation_version` | G1 contract | seed、規則、event vocabulary 或計算契約改變 |
| Asset manifest | manifest hash／version | Art pipeline | atlas、glTF、audio 或 mapping 發布 |

持久化資料只保存 domain state 與明確版本，不保存 Phaser／Babylon instance、DOM reference 或 live object。未來最低欄位應可表達：

```json
{
  "world_version": 1,
  "avatar_version": 1,
  "asset_manifest_version": "ballpark-assets-1",
  "updated_at": "ISO-8601 timestamp"
}
```

實際 schema 由 C4、D1 凍結；上例只定義版本分離原則，不是已實作 payload。

### 11.3 Route 與 Classic 共存策略

- 穩定產品 URL 優先維持 `/` 與既有分析 deep links，不因產品版號改成 `/v0`、`/v1`、`/v2`。
- H5 前 `/` 保持 Classic，未來 `/ballpark` 保持可選且 lazy-loaded；Classic／Ballpark switch 是 user fallback，不是部署 rollback。
- 若 H5 決定 Ballpark 成為預設，必須先為 Classic 指定穩定入口（建議 `/classic`）與 redirect／bookmark 過渡期，不能在同一發布直接移除舊入口。
- API 可在確有 breaking contract 時使用版本路徑或 header；UI route 不應為每次 minor release 複製一套頁面。
- Classic 的直接 URL、auth redirect、Back／Refresh 行為在任何 Ballpark 版本中都必須保持可用。

### 11.4 Release channels 與標準作業流程

```text
local development
  → automated checks
  → test / staging
  → internal preview
  → opt-in beta / canary
  → staged rollout
  → stable
```

每個候選 release 必須：

1. 從明確 commit 建立唯一版本與 Git tag，例如 `ballpark-v0.5.0`；同一 tag 不得重建成不同內容。
2. 產生不可變 frontend／backend artifacts、asset manifest、dependency lock 與 migration 清單。
3. 在 staging 驗證 Classic deep links、auth、API/schema、save migration、browser/device、accessibility、performance、cleanup 與 fallback。
4. 先以 feature flag 開給 internal／opt-in 使用者；flag 必須由 Nuxt／server 決定功能可用性，不能當作真正 authorization。
5. Canary／staged rollout 依明確比例或 cohort 擴大，監控 error rate、LCP／input latency、runtime crash、save migration failure 與核心任務成功率。
6. 達到 gate 才升到 stable；未達 gate 就停止擴大、關閉 feature flag 或回滾 artifact。
7. 保存 release note、已知限制、migration 結果與 rollback decision；不得只以「部署成功」宣稱 release 通過。

### 11.5 升級與資料 migration 模式

資料庫與 API 採 **expand → migrate → switch → contract**，避免部署新版本時立即破壞舊版本：

1. Expand：先新增相容欄位／endpoint，舊程式仍可運作。
2. Migrate：使用可重跑、可觀測、具備 backup／checkpoint 的 migration 更新資料。
3. Switch：新程式開始讀寫新契約，必要時短期 dual-read／dual-write；必須定義結束條件。
4. Contract：觀察期與 rollback window 結束後，才移除舊欄位、舊 API 或舊 reader。

World／avatar save migration 必須提供舊版 reader、逐版 migration、validation、安全預設與壞檔復原。不能把無法讀取的存檔靜默清空；應保留原始 payload／備份識別、回 Arrival Plaza 或 default avatar，並顯示修復訊息。跨越多個版本時依序 migration，例如 `v1 → v2 → v3`，不得假設所有使用者只落後一版。

### 11.6 Rollback、fallback 與 downgrade

| 狀況 | 優先處理 | 禁止事項 |
|---|---|---|
| Ballpark UI／runtime 異常 | 關閉 feature flag，導回等價 Classic route | 不讓 Classic 一起依賴壞掉的 runtime chunk |
| Frontend build 異常 | 重新指向上一個已驗證 artifact | 不用同一 tag 覆寫修正版 |
| Backend/API 異常 | 回滾相容 backend 或切回舊 endpoint | 新 schema 已寫入後，不盲目部署無法讀取它的舊程式 |
| Database migration 異常 | 停止 migration、使用 checkpoint／備份與 forward fix | 未驗證前不直接做破壞性 down migration |
| Save migration 異常 | 停止寫入新版、保留原始 save、使用舊 reader／安全 fallback | 不靜默刪除角色或進度 |
| Asset manifest 異常 | pin 上一個完整 manifest，清楚處理 cache key | 不混用跨版本 atlas／mapping |

「返回 Classic」是產品 fallback；「部署上一個 artifact」是 rollback；「把新資料轉回舊 schema」才是 downgrade。三者風險不同，不得用同一個按鈕或說法混在一起。優先設計向前相容與 forward fix；只有 down migration 經獨立 rehearsal 且不會遺失資料時才允許資料 downgrade。

### 11.7 Release 與退版最低紀錄

每次 beta／stable release 至少記錄：版本與 commit、環境、artifact／manifest IDs、feature flags、schema/save versions、migration 狀態、驗證結果、rollout cohort、監控連結、Classic fallback URL、rollback owner、觸發門檻與最後決策。H2 必須把此清單落成 deployment／observability 流程；H4 必須實際演練 opt-in、migration、退出與 rollback；H5 才能決定預設入口。

## 12. Slice B3 · Visual art bible

原 machine-readable contract 與 concept board 保留作為被拒絕方向的歷史證據，不再是現行 art bible。使用者重新確認的目標是 RPG Maker 類型的俯視 2D 像素 RPG：以棒球場園區取代城鎮，使用 tilemap、四方向像素角色、NPC、建築入口、互動提示／對話框與 Petehub 黑橘 UI。任何新 runtime 實作前，必須先交付一張此方向的棒球場主畫面並取得明確核准。

使用者已核准俯視像素 RPG 方向。後續視覺基準為 `output/ballpark/b3-pixel-rpg-main-v4-pitcher-mound-2026-10-30.png`、`b3-team-office-interior-v2-easter-egg-2026-10-30.png` 與 `b3-clubhouse-interior-v1-2026-10-30.png`。v4 在右側牛棚外圍欄加入與其他設施一致的永久 `PITCHER MOUND` 招牌。它們凍結構圖、視角、角色比例、設施語意與 HUD 方向，但仍是 concept；D1–D2 必須拆成有 provenance 的 tileset／sprite／manifest，不能直接拉伸概念圖。

### 12.1 Petehub brand bridge

Ballpark 延續現有 Petehub 的黑／炭黑底、`#FF9900` 主橘與高對比分析介面，但加入克制的球場綠、紅土與 chalk off-white。方向是「專業棒球分析園區」，不是霓虹 cyberpunk、卡通 mobile town 或真實 MLB 授權球場。橘色用於品牌、focus、選取與主要動作；不可作白底長篇 body text。

字體沿用現況：display 使用 Segoe UI Variable Display 系列，body 使用 Fira Sans／Segoe UI，數據使用 Fira Code／Consolas。可存取文字、狀態、導航與 route identity 仍由 Nuxt DOM render；Canvas 文字只能裝飾或重複，不得成為唯一資訊。

### 12.2 World perspective、tile 與 scale

| 項目 | 凍結規則 |
|---|---|
| Projection | D1 凍結為 RPG Maker 類型的正交俯視 2D，不使用原 oblique 2.5D |
| Logical tile | `32×32` logical px 只是候選的地圖／碰撞格，尚未獲視覺驗收；圖塊、建築、角色可以跨多格或使用獨立 sprite，不能把它誤解為整張畫面的美術精度。核准後所有可走動場景才共用同一格 |
| Character | 球員／NPC 採 V2（64×96 級），User 採 V3（96×144 分件級）；這是製作精細度標準，世界顯示比例與 footprint 由 D4 校準，詳見第 19 節 |
| Door／path | 可通行入口至少 2 tiles（64 logical px）；互動 DOM target 至少 `44×44 CSS px` |
| Exterior／interior | 相同 projection、world scale、key light 方向；室內不可突然換成正面 side view |
| Camera | target zoom `0.85–1.2`；B3 是 target，不是效能或 runtime pass |

畫面改採一致的 pixel-art tile 與 nearest-neighbor filtering。單張生成圖只能作構圖／色調參考，不能拉伸成正式背景；正式可玩場景必須拆成 tileset、object layer、collision layer、entrance data 與 sprite sheet。

### 12.3 Palette 與 lighting

| Role | Token |
|---|---|
| Petehub orange | `#FF9900` |
| Ink／charcoal | `#070707`／`#141414` |
| Raised surface | `#292F38` |
| Field green | `#477A4B`／`#6D9A61` |
| Clay／chalk | `#B86B3D`／`#F3EFE3` |
| Data blue-gray | `#7F94AE` |
| Success／warning／danger | `#72CD8B`／`#F5B84B`／`#F06B62` |
| Focus | `#FFD166`，3 px outline＋2 px offset |

預設 early-evening stadium light，key light 朝 upper-left、shadow 朝 lower-right，shadow opacity 不超過 0.28。室內使用 neutral-warm lighting。光影可協助分區，但 availability 不能只靠顏色或明暗表達。

### 12.4 Avatar 與 animation cadence

- 預設角色永遠可用；brand-neutral Petehub uniform，不使用真實球隊商標。
- 先 author north／east／south／west 四方向，不做 runtime mirror，避免背號與圖樣反轉；八方向 input 對應最近 authored facing。
- `idle`：4 frames／6 fps loop；`walk`：8 frames／10 fps loop；optional `run`：8 frames／12 fps loop；一般 interaction：6–10 frames／10 fps、non-loop。
- reduced-motion 使用 static idle、無 camera easing／parallax，以 DOM 即時切換狀態，不播放 travel animation。
- 本節只涵蓋 Ballpark avatar 移動。投球、揮棒、左右投打與 release/contact event 仍屬 Section F，不得由本節資產推論完成。

### 12.5 HUD 與 responsive composition

- Desktop：top status bar、左側 fast-travel rail、右下 contextual prompt。
- Narrow：compact top bar、底部橫向 fast travel／bottom-sheet 模式、全寬 contextual action。
- Classic UI、Fast travel、Help、Account 是持續可達動作；modal／menu／Classic overlay 取得 focus 時，world input 暫停。
- `loading`、`ready`、`empty`、`limited`、`locked`、`unavailable`、`error` 都要有文字 label；不得只用 icon 或色彩。

### 12.6 Production asset handoff

正式資產由 D2 接手：editable Aseprite／核准後 Blender source 與 runtime PNG／WebP atlas、manifest 分離；manifest 必須包含 logical ID、asset version、source identity、hash、dimensions、density、directions、clips、anchor、license、author/source、modification note 與 exporter version。缺資產時使用 neutral silhouette＋Nuxt 說明，不得留下 invisible collision。B3 concept board 不得切片後直接當 atlas。

## 13. Slice B4 · Interactive prototype gate

本機可操作原型：`output/ballpark/b4-interactive-prototype.html`。驗證資料：`data/sample/petehub_ballpark_b4_prototype_validation_2026-10-30.json`。這個 standalone artifact 不修改產品 route、不呼叫 auth／API、不建立存檔，也不載入 game engine。

### 13.1 已完成的 prototype coverage

- Desktop map prompts 與 fast travel 共用同一 zone selection；Narrow 改為底部水平 fast travel。
- Classic UI 永遠可達，且每區顯示 canonical Nuxt route。
- Nuxt DOM overlay model 支援開啟、Escape／Back to Ballpark、focusable controls，並明示 production 只 push 一個 history entry。
- Video Room 顯示 `unavailable` 並使用 `/games/today` fallback；Front Office 顯示 `locked` 且主要動作 disabled。
- 可切換 loading state，保留 Classic navigation，不以 loading 畫面困住使用者。
- Prototype 使用 B3 concept image 作背景方向參考，但明確標示沒有 runtime、backend request 或 persistence。

### 13.2 Browser evidence

| Gate | 結果 |
|---|---|
| Chromium `1440×900` | Pass；Front Office locked、無 X/Y overflow、console error 0 |
| Chromium `390×844`＋reduced motion | Pass；Video unavailable fallback、無 X/Y overflow、console error 0 |
| Fast travel／Video fallback | Pass；顯示 `/games/today` |
| DOM overlay／Escape close | Pass |
| Admin locked action | Pass；button disabled |
| Screenshots | `output/playwright/b4-desktop-front-office.png`、`output/playwright/b4-narrow-video-reduced.png` |
| 真實 mobile／低階裝置 | Unavailable；不可由 viewport resize 宣稱 pass |

### 13.3 Figma editable prototype 與完成決策

Figma file：`Petehub Ballpark`（`https://www.figma.com/design/yzxkj0LVR67yHbfKTvVcuy`），page：`B4 Prototype`。檔案包含 17 個 variables、5 個 text styles、1 個 effect style 與 4 個 reusable components；六個 editable screens 覆蓋 desktop home／video unavailable／front-office locked／loading，以及 narrow home／video unavailable。Desktop 與 narrow 均設 flow start，desktop 13 條、narrow 2 條 prototype connections；Video／locked state 支援 Escape 返回，loading 以 timeout 回 Home。

結構稽核確認 desktop screen 約 83 個 descendants、21 個 component instances，narrow 24 個 descendants、7 個 instances；文字使用 Fira Sans／Fira Code，沒有 full-page raster 或 image-filled node。與本機 prototype 的 desktop／narrow screenshot 比對後修正 header fill；最終證據為 `output/playwright/b4-figma-desktop-home-final.png`、`output/playwright/b4-figma-narrow-home.png`。

B4 為 **Done**。核准的主園區、Team Office 與 Clubhouse 模板已接入本機 `/ballpark`：場景與 fast travel 可進入 Game、Leaderboard、Clubhouse、Team Office、Training & Lab 及 Video Room overlay；Classic UI 始終保留。`peter1010` 且具 admin role 時，Team Office 的 `Per aspera ad astra` 畫框才提供後台連結。2026-10-31 使用者核准最終主園區原型，Nuxt UTF-8 check 與 typecheck 通過，Section B 正式關閉。

## 14. Slice C1 · Registration and character bootstrap

### 14.1 Account contract 與 ownership

- FastAPI／SQLite 是帳號主隊與 bootstrap 狀態的唯一持久化 owner；Nuxt 只負責註冊、首次進入與修改主隊介面。已登入帳號的主隊不再從 browser localStorage 回填。
- `users.favorite_team_id` 可為 `null` 或 30 個官方 MLB team ID 之一；API 同時回傳衍生的 `favorite_team_code`。不合法 ID 在 schema 與 service 兩層拒絕。
- `users.avatar_setup_status` 僅有 `pending`／`default`。C1 的角色交付是永遠可用的 neutral default avatar；外觀、圖層、制服與完整 creator 留在 D3–D4。
- `POST /api/auth/register` 可選主隊；authenticated `PATCH /api/auth/profile` 是 partial update，可修改或清空主隊並保存 default-avatar bootstrap。既有 SQLite DB 以 additive migration 補欄位，不重建或清空帳號。
- 沒選主隊時顯示 `MLB HOME CAMPUS` 與 Choose later；Clubhouse／Team Office 不產生無效 team route，而是重新開啟選隊視窗。Petehub logo／skip flow 仍可回 Classic UI。

### 14.2 C1 verification

| Gate | 結果 |
|---|---|
| SQLite legacy migration | Pass；既有使用者保留，新增欄位預設為 `null`／`pending` |
| Team validation | Pass；官方 30 隊 ID 與 `null` 可用，未知 ID 被拒絕 |
| Auth/schema/API tests | Pass；8/8 targeted tests |
| Registration／change-team | Pass；註冊可選主隊，profile PATCH 可修改或清空且不重設已完成 avatar 狀態 |
| Nuxt UTF-8＋typecheck | Pass |
| Browser bootstrap | Pass；mocked authenticated flow 選 NYY、關閉 onboarding、顯示 `NYY HOME CAMPUS` 並保存 local fallback |
| Classic fallback | Pass；略過主隊與 default avatar 均不封鎖 Classic UI |

C1 為 **Done**。架構邊界刻意不在本 Slice 建立 Phaser player save 或完整 avatar creator；舊 mechanics spike 只保留作 E1–E2 技術參考，不再冒充 C1／C2 現況。

## 15. Slice C2 · Official active-roster contract

C2 為 **Done**。FastAPI 是 active roster 與 freshness 的唯一 owner；`GET /api/teams/{team_code}/active-roster?year=2026` 回傳 `official_active_roster_v1`。來源固定為 MLB StatsAPI `rosterType=active`，cache key 包含 year/team，成功資料以 atomic replace 保存於 `MLB{year}/official_active_rosters/{team}.json`，30 分鐘內為 fresh。每位球員保留 MLBAM ID、姓名、背號、position code/name/type 與官方 status code/description。

官方 response 沒有 roster revision timestamp，因此 `source_as_of` 誠實維持 `null`，另提供 Petehub `retrieved_at` 與 `cache_age_seconds`。更新失敗且有有效版本 cache 時回 `stale`＋warning；沒有 cache 時回 `unavailable`＋空名單，不以本季出賽、leaderboard 或本地 pitch table 重建。既有 Team Dashboard 的 active pitcher 過濾已改用同一契約，避免第二套 roster 定義。

驗證：5 項新 service tests 加上 4 項既有 Team Dashboard tests 共 9/9 通過，涵蓋官方欄位正規化、fresh disk cache、不重複抓取、stale fallback、unavailable、錯誤 payload 不得冒充 active roster，以及 dashboard 相容性。舊 movement／camera／collision spike 屬 Section E，不是 C2 交付。

## 16. Slice C3 · Home-team context and switching

C3 已由使用者明確驗收，狀態為 **Done**。帳號 profile 的 `favorite_team_code` 是主隊偏好，只有 Ballpark 主園區的 Home team 選單會呼叫 profile PATCH。`/teams` 入口在已選主隊時導向 `/teams/{homeTeam}`；沒有主隊時顯示 30 隊選單。Team page 原有球隊切換連結維持 `/teams/{teamCode}`，並新增 My team 返回入口；切換只改網址，不寫入帳號設定。球隊代碼與名稱共用 `frontend/config/mlbTeams.ts`。

Ballpark 的 Clubhouse 與 Team Office 使用同一帳號主隊作為預設瀏覽隊伍；室內 Viewing team 選單可切換到其他隊並寫入 `/ballpark?room=clubhouse|team-office&team={teamCode}`。直接連結、refresh 與 browser back 由 Nuxt route query 還原；URL 的有效 team 優先於主隊，無效代碼安全回到主隊。回主園區會清除暫時選隊，帳號主隊仍維持原值。室內的 team page 連結使用目前正在瀏覽的隊伍。

已通過 Nuxt UTF-8/typecheck；本機前端可於 `http://127.0.0.1:3000` 檢視。使用者確認 C3 可驗收。Clubhouse 與 Team Office 目前仍共用靜態示意背景，換隊只改瀏覽資料與網址，不代表各隊球衣或球員圖像已動態實作；這是後續設施內容工作，不算 C3 缺陷。

## 17. Slice C4 · Special admin access contract

C4 為 **Done**。Team Office 的 `Per aspera ad astra` 牆面熱區是進入 `/admin/updates` 的彩蛋；Nuxt 只對登入帳號同時具有 `admin` role 與精確 username `peter1010` 顯示入口，直接輸入後台網址也由 route middleware 擋下。真正的資料與操作權限由 FastAPI 在整個 `/api/admin/*` router 入口執行同一個雙條件檢查；不以隱藏連結充當安全邊界。未登入回 401，登入但不符任一條件回 403，拒絕請求不執行後台 handler。其他 admin 帳號仍可透過既有 `/api/auth/users` 審核會員，但不能進入資料維護後台。

Nuxt 擁有熱區、頁面路由與登入導向；FastAPI 擁有授權與後台資料。Classic UI 的一般深連結不受影響。此 Slice 不新增 world/session save 或 schema，也不啟動 game runtime。授權測試涵蓋匿名、一般會員、同名非 admin、異名 admin、大小寫不同名稱及正確帳號，並確認所有 `/api/admin/*` 路由都套用檢查。實際牆面位置與操作手感可由使用者目測，不作為後端權限測試的替代。

## 18. Slice C5 · Account/team data gate

C5 為 **Done**。資料與權限稽核：註冊帳號先為 pending，須經管理員核准才可登入；session cookie 為 HttpOnly／SameSite=Lax，停用帳號會使既有 session 失效；profile 主隊變更由登入者自己的 session 決定，`favorite_team_id` 必須是 30 隊之一或 null；Team／Clubhouse／Team Office 的暫時瀏覽隊伍不得改寫主隊；官方 active roster 有版本、來源、fresh／stale／unavailable 與時間欄位，不能用本季出賽者假冒。`/api/admin/*` 必須同時具備 admin role 與精確 `peter1010` username。auth/admin HTTP 回應已統一加 `Cache-Control: no-store`，登入回應不得把密碼、hash 或 session token 放進 body。

驗證：`test_account_team_gate.py` 加上 C1／C2／C4 的 targeted tests 共 22/22 通過，涵蓋 pending→核准→登入→主隊 PATCH→再次讀取、官方名單快取、一般使用者後台拒絕、停用後 session 拒絕、另一管理員拒絕與正確後台帳號允許。瀏覽器確認未登入的 Clubhouse 深連結轉到登入頁；使用者提供 Clubhouse／Team Office 登入後截圖，確認新版固定導航與 Viewing team，並明確表示移除兩處多餘的 `HOME TEAM` 招牌即可完成 C5。兩張背景已分別更新為 `clubhouse-v2.png`、`team-office-v3.png`，舊版本保留，PLAYER LIST 與管理員畫框維持；Nuxt typecheck／UTF-8 通過。完整自動化 authenticated direct URL／refresh／back browser matrix 仍未執行，不能誤列為 pass；後續 D／E release gate 仍須覆蓋。這兩張仍是 concept 背景，不是 D1–D2 的 production tileset。

## 19. Section D · 分層場景素材與 Avatar（2026-11-02 調整）

### 19.1 製作方法、V0 保留與驗收決策

本節的 2026-11-02 決策取代先前「所有場景先重製成 tileset 才能前進」和「格尺寸必須由使用者核准」的工作順序；下方日期紀錄保留為歷史證據。V0 的移動、相機、輸入、角色設定／保存及路由基礎繼續沿用。`/ballpark` 是現有靜態入口與回退路徑，`/ballpark/play` 是同一 runtime 的增量製作／驗收入口。場景切換與新素材逐項替換、保留舊版本與 manifest，不刪除 V0 或另寫一套引擎。文件調整不改變實際產品版本，也不把任何 Slice 自動標 Done。

場景採「核准構圖的背景＋可編輯物件／前景遮擋＋獨立碰撞／入口資料」。需要重用、替換或動畫的物件才獨立製作；不以 32×32 格子重畫全部背景，也不要求全部背景變為可拼接圖塊。分層來源可以含 raster 背景，但需有可編輯的物件／mask／對齊關係和可重現輸出。單張 PNG 原封不動另存為多圖層檔不能算交付。AI 背景保留模型／生成方式／參考與修改紀錄及 hash；來源／授權與各項交付檢查需通過，不能把概念圖直接改標 production，或將靜態圖宣稱為動畫 atlas。

已通過並沿用：B3 像素 RPG 畫風、Game 入口完整示意與獨立入口外觀、Campus 主構圖與區域配置、Clubhouse／Team Office 內裝模板；Character 面板初步操作與 V0 大致走動手感亦已有使用者回饋。入口、三張模板和現有面板不再逐次送審同一張圖。助手決定內部格子／座標、匯出格式與工具並完成 source-only 檢查；畫面與實際通行結果只以使用者人工驗收為準。

D2.1–D2.4 的製作順序：入口分層小樣完成技術檢查 → 建立這三場景需要的最小共用素材與資料輸出 → Campus → 兩間室內 → 一次三場景可操作交付。D2.1 不另開同圖審核；若製作結果明顯改變已核准構圖或畫風，才提出具體差異與替代稿供判斷。素材與互動資料可先在既有 runtime 接線驗證，E 區再完成路由／輸入／保存／效能的完整發行檢查，無須等 E 才首次看到 D 的成果。

### D1 · Scene／asset manifest contract

**狀態：Done。** 世界採正交俯視；以現有 `1672×941` 世界座標對齊背景、碰撞、物件和足底 anchor。`32×32` 可作編輯輔助格，不限制背景細節、建築尺寸或碰撞形狀，也不構成人工驗收阻擋。碰撞可採多邊形／矩形或格狀資料；比例、窄步道和入口寬度由 source-only 幾何檢查與使用者實際操作分開驗收。角色尺寸與比例若變更，必須連同 footprint 和通行資料更新。座標以左上為原點，`x` 向右、`y` 向下；角色足底 anchor 為 `(0.5, 1)`。場景依責任分為 `ground`、`decoration_back`、`collision`、`objects`、`actors`、`decoration_front`、`interactions`；可合併無獨立編輯需求的視覺底層，碰撞、入口與前景遮擋則必須獨立。入口須有 `scene_id`、世界座標、facing、目的場景／spawn 與直接導航 fallback。門寬以實際角色 footprint 加通行餘量驗證，不綁定兩個未凍結的 tile。

每個正式資產的 manifest entry 必填 `logical_id`、`kind`、`asset_version`、`source_path`、`source_sha256`、`runtime_path`、`runtime_sha256`、`width`、`height`、`anchor`、`license`、`author`、`provenance`、`modification_note`、`exporter`、`exported_at`；圖塊補 `tile_size`，角色補 `frame_size`、`directions`／`clips`，背景／mask 補世界範圍與對齊座標。場景標記 `render_mode`，允許分層背景或 tilemap；均需獨立碰撞／入口／遮擋資料。manifest 以不可變版本與 SHA-256 pin，完整驗證後才切換整包。來源／授權不明或缺必要編輯來源的資產仍只能標 `reference`。現有 PNG 的 hash 保留於 inventory；新交付前不變更其 reference 身分。

### D2.1–D2.6 · Exterior／interior production set

**狀態：D2.1–D2.6 Done。** 五個 scene ID 固定為 `campus`、`team_office`、`clubhouse`、`training_lab`、`video_game_room`。現行統一包為 `d2-scenes-v3`；v2 與 D2.5 補充包保留作為已驗收來源。正式場景包具可編輯來源、runtime 視覺層、獨立碰撞／入口／前景遮擋和可追溯輸出；可採背景與物件混合，不強制每張場景都有 atlas 或 tileset。

D2.1 以 Game 入口、鄰近圍欄／步道和角色作最小分層樣本。使用者已接受 `output/ballpark/d2-1-game-entrance-visual-study-v1.png` 和獨立入口外觀；後續製作由專案承擔。需交可編輯分層、前景 mask、獨立碰撞／互動與輸出結果；驗證步道／圍欄對齊、足底比例、前後遮擋及入口可達。這些是助手的製作與技術檢查，不要求使用者重新核准相同畫風或內部格子。資料範例、PNG 和幾何草稿仍不足以單獨將 D2.1 標 Done。

D2.2 將樣本方法整理成三場景實際使用的共用物件／mask、palette、anchor、場景資料與可重現匯出程序，附來源／授權／hash；可按需匯出獨立 PNG 或 atlas，不先製作整套通用美術庫。D2.3 沿用 Campus 核准背景補齊全場景的物件／遮擋／碰撞／七個入口；D2.4 沿用兩間室內模板補齊家具碰撞、遮擋、出入口與互動定位，沿用 V0 runtime 串接可操作驗收。D2.4 不包含將全部 roster 變成真實球員 NPC，也不重做輪值／交易等業務面板；這些保留於 F4／F5。D2.5 再核准 Training & Lab、Video／Game Room 的新內裝設計。D2.6 整合五場景版本、來源和 fallback 後交 D5；D5 檢查素材大小／記憶體、角色方向、缺件和深度等，不因採背景圖方式而略過。

2026-11-02 D2.1／D2.3／D2.4 人工驗收完成：使用者確認 Clubhouse 中央通道已移除阻擋沙發／桌子且可接受、Team Office 可看到 `◀ COACH` 與 `GM ▶` 方向標示，以及 `0.8` camera zoom 與依 viewport 高度調整的頁面尺寸。此結果是使用者本人回報的畫面／操作驗收；v2 現況為 Campus 23／15／7、Clubhouse 16／9／2、Team Office 27／12／3，合計 66 collision polygons、36 foreground masks、12 portals。D2.1、D2.3、D2.4 因而關閉；D2.2 保持 Done。source-only 技術 PASS 不取代本次人工回報。

2026-11-02 D2.5 開始：以 Campus、Clubhouse corridor v2、Team Office clean v1 作已核准風格／世界比例參考，分別產生 `output/ballpark/d2-5-training-lab-interior-candidate-v1.png` 與 `output/ballpark/d2-5-video-game-room-interior-candidate-v1.png`。兩張皆為 1672×941 concept candidate，來源、hash、prompt 摘要與限制記錄於 `data/sample/petehub_ballpark_d2_5_design_candidates_v1.json`；目前 `production_eligible=false`、`runtime_wired=false`。畫面由使用者本人驗收，核准前不得建立正式碰撞、foreground、portal 或開始 D2.6。

2026-11-02 D2.5 製作交付：使用者明確回覆兩張設計皆可，授權完成製作。核准 PNG 原樣複製至 `training-lab-v1.png`／`video-game-room-v1.png`，hash 與設計候選一致。新增 `frontend/assets/ballpark/scenes/scene-kit-d2-5-v1.json`：每室 33 collision、23 foreground、2 portals，保留中央通道，Training Lab 可直接開 `/lab`，Video 的推薦入口沿用首頁功能；遊戲機僅為未來 Game Room 預留，未實作 F6 業務。`output/ballpark/scenes-d2-5-v1/` 交付兩室可編輯 SVG／JSON，版本、hash、來源、人工狀態與 Campus portal override 記錄於 `data/sample/petehub_ballpark_scene_manifest_d2-5-v1.json`。沿用原 v2 加載獨立補充包，原三場景素材與幾何不變；尚未開始 D2.6 的五場景統一包。

`/ballpark/play` 新增兩室固定切換按鍵、query room 與 Campus 往返入口；viewing-team query、0.8 camera、safe reset、靜態 `/ballpark` 與直接功能連結繼續沿用。`node frontend/scripts/check-ballpark-scenes.mjs d2-5-v1` source-only PASS（每室兩入口幾何可達），Nuxt typecheck PASS；代理未啟動／操作瀏覽器或進行畫面驗證。使用者隨後明確回報五項操作驗收「都通過」，D2.5 因而 Done，進度 20／51。

2026-11-02 驗收後小修改：依使用者建議，四間室內靠近 `return` 出口時以 `R` 返回 Campus；`E／Enter` 保留給其他設施入口，gamepad 與 DOM `Enter / Exit` 按鍵仍可操作。出口顯示 `▼ BALLPARK · R`，DOM 說明同步；輸入欄位、暫停與 hidden 狀態沿用既有防護。使用者後續明確回報「驗收過關」，R 行為人工驗收完成，並授權開始 D2.6。

2026-11-01 D2.3 視覺核准：`output/ballpark/d2-3-campus-environment-visual-candidate-v1.png`（1672×941）由內建圖片生成工具以 B3 Campus 構圖和使用者已接受的 D2.1 Game 入口樣稿為參考產生，去掉舊主圖烙印的頂部 HUD、時間、對話框與人物，保留八個場域的原本位置；使用者已回覆「可以」。同圖保存為 `frontend/assets/ballpark/main-campus-v5.png` 供靜態 `/ballpark` 頁面使用，原有導覽獨立置於圖片上方；Nuxt UTF-8 與 typecheck 通過。使用者隨後回報導覽、記分板顯示與區域點擊均通過。來源與 hash 記在 `data/sample/petehub_ballpark_d1_d3_asset_inventory_v1.json`。這仍不是正式分層來源、圖塊集、碰撞或可行走地圖；不能因靜態頁面更新就把 D2.3 標 Done。

Campus 地圖資料草稿 `output/ballpark/d2-3-campus-geometry-draft-v1.tmx` 可由 Tiled 編輯，使用核准畫面作明確標示的非正式參考層，另設粗略碰撞區、七個場域入口、玩家起點與僅指標點擊的 Leaderboard 區域；XML 結構、參考圖片 hash、物件 ID 與入口範圍檢查通過。這些形狀尚未經角色足底碰撞／可操作預覽驗證，32 px 地圖格也未核准；不得視為 D2.3 正式 tilemap 或已可行走。

2026-11-01 V0 走動預覽：`/ballpark` 保留已核准的靜態點擊版本，新增 `Walk V0` 入口到 `/ballpark/play`。此預覽以三張已核准但仍為扁平概念圖的 Campus／Clubhouse／Team Office 作背景，沿用 C2 的 lazy Phaser runtime，暫用程式繪製的中性 `32×48` 角色、WASD／方向鍵／gamepad／觸控移動、相機、粗略矩形碰撞及 E／Enter／觸控 Enter 入口互動；另有房間導覽及回靜態地圖的 fallback。碰撞及入口座標是 V0 手感試驗，不是經核准的分層 tilemap，也沒有前景遮擋、四方向正式動畫或 roster NPC。Nuxt UTF-8／typecheck 通過；未登入瀏覽器被既有登入閘導向 `/login?redirect=/ballpark/play`。在該日期 D2.3 仍 In progress、D2.4 仍 Planned；後續完成結果以上方 2026-11-02 紀錄為準。

D2.1 另有 `output/ballpark/d2-1-game-entrance-geometry-draft-v1.tmx`：以已核准入口圖為 Tiled 參考影像，獨立記錄入口觸發區、玩家到達點與粗略不可通行區。地圖格仍標為 `32 px candidate_not_approved`，影像層標為 `production_art=false`，且尚未接入 runtime；需在實際分層美術和角色尺寸核對後重測碰撞，不得把此草稿當作 D2.1／D2.3 完成證據。

2026-11-01 工具準備：從官方來源下載 Krita 5.3.4 portable（分層場景）、LibreSprite 1.3 portable（像素圖塊／角色）及 Tiled 1.12.2 Windows MSI（地圖／碰撞）；SHA-256、大小、來源與本機路徑列在 `data/sample/petehub_ballpark_d2_toolchain_2026-11-01.json`。當時三者尚未安裝或執行；後續解壓狀態見下段。下載完成不代表 D2.2 可編輯美術已交付；Node／Nuxt／Phaser／Pillow 原已具備，Aseprite 付費版與 Blender 不是此 2D Slice 的必要條件。

2026-11-01 D2.1／D2.2 後續準備：已核對下載雜湊，將 Krita 與 LibreSprite 便攜版解壓於 `.codex/toolchain/`；Tiled MSI 仍僅下載。使用內建圖片生成工具、以已核准 D2.1 視覺樣稿作畫風／比例參考，產生透明背景的獨立 Game 入口候選 `output/ballpark/d2-1-game-gate-isolated-concept-v1.png`（1774×887，SHA-256 與來源見資產 inventory）。使用者於 2026-11-01 再次明確回覆「可以」，獨立入口的視覺方向已核准，不再重複要求驗收同一入口。此物件仍是單張 AI 生成概念圖，不是可編輯分層源檔、圖塊或 atlas；不得因視覺核准或工具可執行而將 D2.1–D2.4 標 Done。後續由專案建立真正可編輯的分件小場景及共用素材。

**技術尺寸，由助手驗證：** 背景世界維持 `1672×941`，不為湊格數裁切核准構圖。`32×32` 可作編輯輔助格，碰撞可獨立採形狀；現行暫用角色仍為 `32×48`，正式美術改採下方 V2 球員／NPC、V3 User 標準。D2.6 已將當前 inventory 對齊 runtime 的 `half_width=9,height=10`（18×10）足底規格；舊 `20×12` 僅留在歷史紀錄。D4 製作新角色時仍需校準顯示比例，不能因提高貼圖解析度就等比例放大碰撞。需打包時 atlas 目標 `1024×1024`、個別頁面候選上限 `2048×2048` 和 2 px extrusion，均為待量測預算。桌面與窄螢幕以 camera／適當縮放保持可讀性，D5 記錄檔案大小與解碼紋理估算；實際載入、記憶體與裝置結果由使用者驗收／提供。使用者驗收角色比例和畫面結果，不必核准這些內部數字。

各 scene 先經來源／授權、分層接縫、walkable／入口對齊、前景遮擋及缺件 fallback 檢查，再沿用 V0 runtime 展示；正式整合 gate 留給 E1。`/ballpark` 保留靜態原型與直接導航，`/ballpark/play` 承接本批可操作成果。Team Office 原型背景為 `team-office-v4.png`，已修補烘入的手形游標；透明畫框點擊區及後台權限沿用。

2026-10-31 的 `output/ballpark/d2-campus-tile-pilot-v1.png` **已被使用者明確否決**。它和 `frontend/assets/ballpark/pilot/campus-tiles-v1.png`、`backend/scripts/build_ballpark_tile_pilot.py`、`data/sample/petehub_ballpark_d2_tile_pilot_v1.json` 只保留為失敗試作紀錄，禁止接入 `/ballpark`、沿用畫風或當成 D1 尺寸／D2 美術驗收。失敗原因是極簡程序圖樣無法呈現已核准 B3 概念圖的建築、角色、層次與細節；`32×32` 只描述候選網格，不是這種粗糙畫風的理由。D2 尚無獲核准的正式圖塊。

### D3 · Versioned avatar／NPC contract

**狀態：Done（角色資料與動畫規格，不代表 sprite 已完成）。** `avatar_version=1` 僅儲存可選外觀：`body_id`、`uniform_id`、`palette_id`、`number`（`0–99` 或 null）、`bats`（`R`／`L`／`S`／`unknown`）、`throws`（`R`／`L`／`unknown`）。不得把主隊、帳號名稱或任何私密資料烘進圖層、公開檔名或共用 atlas；制服預設為無 MLB 商標的 Petehub neutral。`npc_id` 為穩定非個資識別碼；名單球員僅由 C2 官方 roster ID 於 F4 動態對應，絕不由概念圖人物推定真實球員。缺圖層、未知版本或壞存檔一律以 neutral default 呈現，保留原 payload 供修復，不默默清空。

正式角色每個方向 `north/east/south/west` 都必須有 `idle` 4 frames／6 fps 與 `walk` 8 frames／10 fps；不得鏡像含背號／圖樣的方向。舊統一 `32×48` frame 標準由下方 2026-11-02 V2／V3 角色製作決策取代；足底 anchor 維持 normalized `(0.5, 1)`，每包另記 source-pixel anchor、world display scale 與實際 collision footprint。動畫 clip 的 frame order、fps、loop、anchor、source hash 與 exporter 隨 manifest 發布。`avatar_version` 與 asset manifest version 分離；變更資料語意才升 avatar version，換圖不改帳號資料。D4 已實作 creator／持久化，尚缺正式角色素材；E2 負責正式移動驗收，E3 負責觸發對話，F4 才將官方 active roster 對應成 Clubhouse NPC。D3 保持 Done，不因美術升級重做帳號契約。

### D1–D3 驗收與人工測試界線

2026-11-02 使用者再次明確指定畫面／操作測試由本人進行。助手已停止本輪 Playwright 與隔離登入伺服器，不再自行啟動瀏覽器、畫面截圖或替代登入環境；後續只做程式、場景結構、匯出／hash、幾何與型別檢查。畫面載入或操作尚未經使用者確認時明列待驗收，不能宣稱通過。

助手只負責來源／hash／檔案／匯出、場景資料與相關型別／授權等 source-only 檢查；這些結果不等於畫面、碰撞手感、穿模、互動、響應式或路由操作通過。所有 Ballpark 畫面與操作驗收由使用者本人執行。背景圖核准、技術檢查和使用者人工驗收分別記錄；相同背景不反覆送審，文件調整也不代替實作。

D2.1–D2.4 的人工驗收已由使用者於 2026-11-02 完成。驗收入口維持 `/ballpark/play`；代理未代替使用者操作瀏覽器、走角色、測碰撞或宣稱畫面通過。未來 UI 修改仍只交一個檢查網址與最多五項人工清單，不另要求重新核准既有入口外觀。

後續另有真正的新設計才需確認：D4 的改善角色外觀與四方向辨識；D2.5 的 Training & Lab 和 Video／Game Room 新內裝；D5／E6 的實體手機／低階裝置操作。只有使用者指示進入對應 Slice 並有新結果時才提出。

### D4 · Creator UX／persistence implementation

**最新狀態：Done。** 使用者已明確回報「都通過，進入 D5」，包含前述全部 followup；D4 與 Campus 圍網／頁寬不再列待驗。角色來源、manifest、inventory 已記錄本次人工接受，Ballpark 22／51。以下保留初次交付／待驗時的歷史描述，現況以本段及 tracker 為準；不再展示或要求重驗 Moreno 樣本按鈕。

2026-11-02 最新回報：使用者確認 **D4 功能上都通過**，不再重測原完整清單。新增要求已修正：移除 Character 的 Moreno 樣本切換按鈕（保留球員素材）；User 球衣在預覽與 runtime 共用帳號 `favorite_team_code` 隊色，不隨 Viewing team 改變。沿用像素球衣版型，並非官方球衣／隊徽的逐款複製；主場款用主隊色、客場款灰底主隊色飾邊，選主隊時 Accent 顯示隊色並停用手選。投／打選單皆僅 R／L／S；舊 unknown 仍可讀，開啟面板以 R 作待存草稿，取消不改原資料。**D4 保持 in_progress，僅等待這些新增要求的人工確認；以下為原候選交付紀錄，不表示要求重驗全部功能。** 型別與 R／L／S 相容契約 source-only 檢查通過，未進行瀏覽器／畫面測試，D5 未開始新工作。

**狀態：In progress，實作交付、待使用者人工驗收。** `/ballpark` 的 Character 面板已由舊正面 SVG 改接四方向動畫預覽，可切 User／V2 Gabriel Moreno 樣本、facing、Idle／Walk 及 Pause／Play；保留膚色／球衣／配色／背號／左右打投、Randomize、Undo、Reset、Cancel、Save。FastAPI `PATCH /api/auth/avatar`、`/api/auth/me`、舊資料保留／neutral recovery 及 `avatar_version=1` 沿用既有成果，沒有重做帳號或主隊。保存的外觀接入 `/ballpark/play`，User 使用四個分件材質圖層、獨立背號及真正的四方向 frame；不再以 `player-v0` 作正常角色。舊面板接受不能取代本次新素材與動作驗收，D4 暫不列 Done。

2026-11-02 D4 角色候選交付：`avatar-source-v1.json` 與 `build_ballpark_characters.py` 獨立編寫像素多邊形／關節姿勢；概念圖及官方大頭照僅作風格／身分參考，不取其像素、不拉伸／裁切概念板作 atlas。V3 User 為 96×144、V2 Moreno 樣本為 64×96，各 north／east／south／west 皆有 idle 4 frames／6 fps、walk 8 frames／10 fps，共各 48 格。User 有 detail／skin／uniform／accent 四張 atlas、neutral composite 及 0–99 背號圖集；球員樣本是獨立固定外觀 atlas，不會覆蓋 User 或接入完整 roster。`output/ballpark/characters-v1/` 保留八張具命名分件的可編輯 SVG，JSON／Python 為可重現來源；PNG、runtime kit 與 hash／來源／exporter 記於 `petehub_ballpark_character_manifest_v1.json`。

角色候選的世界顯示高度為 80，足底 anchor `(0.5,1)`，碰撞保持已核准場景的 18×10；顯示高度、四方向辨識及手腳動作是否符合 V2／V3 標準仍待使用者判斷。runtime 依實際位移選擇 walk／idle，八方向輸入映射 authored facing，沒有 runtime 水平翻圖；reduced-motion 使用 static pose。DOM 預覽使用相同 atlas 的材質調色與方向格，timer／media listener 隨卸載清除；runtime 沿用既有 scene lifecycle。缺圖時使用 neutral atlas，連 neutral 也缺時顯示有文字提示的暫用輪廓；保留保存外觀，不靜默清空。

已通過：角色匯出、`build_ballpark_characters.py --check` 及 Nuxt typecheck。只代表來源／可重現／型別檢查；未開啟瀏覽器、截圖、比較圖片或代替使用者操作。人工清單最多五項：User／Moreno 四方向與動畫、外觀設定與保存／Undo／Reset／Cancel、走動停止與外觀一致、五場景比例／腳底／遮擋、桌面／窄版與 reduced-motion。`production_ready=false` 保留，D5 不在本輪自動開始或完成。

### D5 · Asset／avatar release gate

**2026-11-04 最終狀態：Done，Section D 關閉，23／51。** 使用者明確回報「目前 D5 驗收通過」，人工清單及場景／角色 acceptance metadata 已同步，含兩側後牆、Coach 會議桌右側／下方通道 followup。`petehub_ballpark_d5_release_gate_v1.json` 記錄更新 metadata 後的 D5 asset gate PASS、零 findings；沒有代做瀏覽器或畫面測試，也沒有重跑不受影響的 build/typecheck。使用者未提供瀏覽器／硬體型號或數值效能，不推定特定實機認證；E6 仍須另驗。inventory／角色 manifest 的 `production_ready=true` 僅表示 D5 素材可交給下一階段整合，**不是整個網站／runtime production-ready**。以下待驗文字保留作歷史，現況以本段和 tracker 為準；Section E 尚未授權實作。

本輪規劃確認：背景在 E／F 階段仍可修改，不需要推翻整個 D。純色彩／裝飾微調只重驗影響區；改家具、門或可走區，須同步 versioned source、hash／manifest、collision、foreground、portal，並在 E5 對舊存檔座標做安全復原。substantial art change 才重新審外觀，不重複核准相同入口。

NPC 文件現況：E3 是通用互動／NPC 機制，F4 是官方主隊 active roster 的 8–10 名代表 NPC、PLAYER LIST 及球員資料。**全園區／所有室內隨機刷新、隨機巡遊的生成區域、密度、路線、時機與互動暫停規則尚未凍結**，不能將既有 NPC 規劃解讀成這些已承諾。建議後續先於 E3 定義通用機制，再於 F4 接真實球員；此處僅記錄規格缺口，未擴增 tracker deliverable 或開始製作。

E5 範圍說明：定義有版本的最後有效場景／位置、session 與重登入恢復策略、依帳號隔離、舊版／壞存檔 migration、安全 spawn 及離線／儲存不可用 fallback；不保存 Phaser instance、認證秘密或逐幀狀態，不複製 D4 avatar profile。驗證方向為重新整理／離開返回的一致性、帳號切換不串檔、改版／背景碰撞更新後不出生在牆內、壞座標／未知版本安全復原、儲存失敗仍可進 Classic。具體哪些欄位留本機或伺服器、是否跨裝置，須在 E5 實作前凍結，不能由本段推定已有跨裝置保存。

2026-11-03 會議桌通道 followup：使用者回報 Coach 會議桌下方無法抵達。原桌椅右緣 x556 與文件櫃左緣 x575 僅餘 19px，18px 足底幾乎無繞行空間。只將桌椅過寬的右側碰撞外緣收至 x536，間隔改為 39px；不縮角色、不改櫃體／背景／遮擋／入口或其他房間。`collision_overrides` 明列版本差異，匯出及 manifest 同步；數量仍 135／82／16。針對性來源 swept geometry 檢查重現舊阻擋、核對修正後可沿右側到下方橫向通道，並保留桌椅／後牆阻擋及入口到達點；不是畫面／手感通過。D5 source gate v2 是這次新座標前的歷史證據，本次沒有重跑全 audit/typecheck/build。人工清單第 1 項補上右側／下方繞行，仍待使用者確認。

**2026-11-03 最新收尾：代理可完成的程式／資料端已完成，人工 gate 待驗。** 對最新 135 collision／82 foreground／16 portals 場景包執行 `audit_ballpark_assets.py --scope=d5-source --report data/sample/petehub_ballpark_d5_source_gate_v2.json`，零 findings；v2 記錄現行來源／manifest hash、角色／場景完整性與紋理估算，v1 原檔保留為歷史。既有十項 focused tests 未受本輪資料／文件整理影響，不再重跑；未跑 frontend build、瀏覽器或圖片比較，未改 runtime／美術。inventory 已指向 v2 與 `petehub_ballpark_d5_manual_acceptance_v1.json`，詳細步驟及通過條件固定在五項待驗記錄內；只有使用者回報才能改狀態。D5 維持 in_progress，不以「來源工作完成」冒充整個 Slice done，`production_ready=false` 保留。

本次人工驗收入口與範圍：

1. **Team Office 穿模修正**：`/ballpark/play?room=team-office`，重新整理後兩側後牆看板／螢幕／櫃體不能走入，前方、入口及中央走道仍可走。此次新碰撞尚未收到使用者通過回報。
2. **五場景資產載入／遮擋／邊緣**：`/ballpark/play`，切換五場景並觀察角色前後遮擋，無漏圖、白邊、裁切、相鄰 atlas 格或閃爍；不重新審核既有畫風／背景設計。
3. **窄版／可用實機**：同一入口用窄視窗確認素材及控制不被裁切；實機只在既有可連線部署上測，手機的 `127.0.0.1` 不是電腦位址。不另開 server；沒有實機請明說 unavailable，不等同桌面窄版通過。
4. **Reduced-motion**：先啟用系統／瀏覽器減少動態效果並重新整理，在 `/ballpark` Character 預覽與 `/ballpark/play` 確認改用固定方向姿勢，但移動／導覽仍可用；不重做 D4 保存功能驗收。
5. **缺圖 fallback**：由使用者自己的 DevTools Request blocking 暫時封鎖 `*user-skin-v1*` 後重整看 neutral／警告；改封鎖 `*user-*-v1*` 看 silhouette／警告；清除後改封鎖 `*team-office-clean-v1*` 重整 Team Office 看錯誤面板及 Static／Classic 連結。全部解除後重整應恢復，保存外觀不能被清空；不刪除／覆寫 PNG 或建立 fixture。

以上五項逐項回報；未測或硬體不可得須保留限制，不推定通過。全部必要人工結果確認後才更新 D5 done／資產 release 決策；尚不表示整個 Ballpark production-ready，Section E／E6 的正式 runtime 與效能認證仍須另行授權。

2026-11-03 D5 穿模回報修正：使用者提供 Coach 看板及 GM 螢幕／櫃體可穿過的截圖並要求修正。只新增 `coach-rear-wall-equipment`、`manager-rear-wall-equipment` 兩個獨立碰撞，補齊後牆至椅子後方的空隙；不改背景、角色、遮擋層、入口、出生點或任何網站觸發功能。舊來源不回寫，新增項記於 `collision_additions`，SVG／JSON／manifest 同步，現行總數 **135 collision／82 foreground／16 portals**。單一針對性來源檢查涵蓋後牆阻擋、向北 swept movement、入口／中央走道可站立、來源差異及輸出一致；PASS 不是人工碰撞通過。未重跑 typecheck／build／全 audit；下方 2026-11-02 D5 source gate JSON 是本次座標修正前的證據，不代表新修正已人工通過。待使用者確認兩側後牆、前方站立區與入口／走道，D5 保持 in_progress，D4 不重開。

**狀態：In progress；source-only gate PASS，人工 release gate 未放行。** D4 與其 followup 已由使用者確認，D5 已獲授權。`audit_ballpark_characters.py` 與既有 audit 整合，檢查兩角色 96 格 allocation、方向／clip 順序與 fps、frame size、anchor／世界比例／footprint、背號位置／100 格、四材質／palette、30 隊隊色、八份 SVG 具名身體分件及來源／參考／匯出 hash。只讀 PNG header／metadata，不讀畫面、不做像素比較；格數配置完整不代表每種外觀都人工看過。九項後再增 palette 反例，現為十項 focused regression tests。來源檢查零 findings，結果記於 `data/sample/petehub_ballpark_d5_source_gate_v1.json`；inventory `production_ready=false` 保留。

五背景＋七張角色／數字 PNG 合計 **13,042,611 B（12.44 MiB）**；全包 RGBA8 估算 **45,961,964 B（43.83 MiB）**，單房＋User 常載六張貼圖估算 **19,612,448 B（18.70 MiB）**。遮擋層重用同一背景 texture，不乘 82。以上只是 width×height×4，不是瀏覽器 heap／GPU 實測，未含 driver、CPU 副本或 mipmaps。角色頁面最大 1152px，超過 1024px 目標但在候選 2048px 上限內；0 gutter／nearest／roundPixels 沿用已驗收素材，2px extrusion 仍為候選，不為符合數字重做角色；實際邊緣／bleed 留給人工確認。可用材質／palette／背號的中性組合 2,424、主隊組合 24,240 是資料覆蓋數，不是逐張渲染通過數。

剩餘人工項目只測 D5 新 gate：五場景載入／前後遮擋與 atlas 邊緣、窄版及可取得的實機、reduced-motion、缺角色／背景時的 neutral／silhouette／Static／Classic fallback。失敗注入必須由使用者在自己的瀏覽器操作，不刪 repo 素材、不另開 server。不能把既有 D4 接受擴大解讀成裝置或缺圖情境通過；沒有實機則誠實列 unavailable。FPS／LCP／GPU-memory／長時間 cleanup 與瀏覽器矩陣未量測，仍屬 E6 的完整 runtime gate；本輪未開始 Section E。source-only 與最終 release 由不同檢查模式區分，單改 `production_ready=true` 不能繞過 D5 人工結果。

### 19.2 · 角色製作標準與 D5 前置核對（2026-11-02）

使用者明確指定：**球員／NPC 用 V2，User 用 V3**。這項核准固定美術製作方向，不代表已完成動畫或人工操作驗收。

| 角色 | 製作標準 | 核准的概念參考 |
|---|---|---|
| 球員／NPC | V2，64×96 px 級四方向逐格角色；手腳擺動清楚、保留球員辨識特徵 | `output/ballpark/character-studies/gabriel-moreno-v2-64x96-concept.png` |
| User | V3，96×144 px 級分件角色；保留頭、軀幹與四肢可編輯來源，支援外觀組合 | `output/ballpark/character-studies/gabriel-moreno-v3-96x144-modular-concept.png` |

兩張由 built-in image_gen 生成，模型名稱未由工具揭露；風格參考已核准的 B3 Clubhouse，球員臉部參考 Petehub `MlbPlayerHeadshot.vue` 同源 MLB 官方大頭照（Gabriel Moreno，MLBAM ID `672515`）。照片來源為 `https://img.mlbstatic.com/mlb-photos/image/upload/w_640,q_auto:best,f_png/v1/people/672515/headshot/silo/current`，本機副本在 `output/ballpark/character-studies/_reference-gabriel-moreno-672515.png`。兩張仍為 concept reference，`production_eligible=false`、`runtime_wired=false`；不得直接裁切成 atlas。V1 不作正式角色標準。Gabriel Moreno 僅作球員範例，User 維持可自訂外觀及 Petehub neutral 預設，不綁定他的臉、捕手裝備或球隊商標。

64×96／96×144 表示目標製作精細度，並非概念板實際 frame 格尺寸，也不表示 User 在世界中必須比 NPC 大 1.5 倍。D4 需建立真正可編輯的來源與可重現匯出，定義 frame box、各方向足底位置、分件對齊、世界顯示比例與 footprint，讓兩種角色在同一 1672×941 場景尺度中一致。V3 可匯出逐格 atlas；本次未選定 skeletal runtime，也不因此新增 3D／Section G 工作。兩種標準均須覆蓋四方向 idle 4 frames／6 fps、walk 8 frames／10 fps，reduced-motion static idle 與 neutral fallback；正式素材與使用者驗收仍待完成。

以下彙整現行來源檢查及使用者回報；未執行瀏覽器或畫面驗證：

1. **D2.5 Done**：兩張設計、分層包、五項操作驗收及 R 出口鍵已由使用者核准。
2. **D2.6 Done**：五場景已統一為 v3，runtime／inventory 改讀同一版本；已驗收來源保留，當前 acceptance 及碰撞 footprint 已對齊，詳見第 19.3 節。
3. **D4 In progress**：V3 User 分件／四方向動畫、面板與 runtime 外觀對應、V2 Moreno 樣本及來源 manifest 已交付，待使用者驗收；批量 roster 身分映射及 NPC 互動仍屬 F4。
4. **D5 In progress／未放行**：audit 已支援統一五場景、已驗收資料等價、hash、fallback 與入口關聯；avatar 仍僅檢查有限欄位。正式角色交付後須補 V2／V3 真正的 frame bounds、方向／clip／組合、匯出、hash、紋理預算及使用者畫面／裝置結果，不能只填 `neutral_sprite` 或把 `production_ready` 改成 true。

接續順序：D4 已由使用者驗收完成 → D5 source-only 已通過、等待上述人工 gate → 使用者另行授權 Section E。Ballpark 22／51；不重做 D2／D4。

### 19.3 · D2.6 統一五場景交付（2026-11-02）

同日後續修正（優先於下方初版交付數量）：依使用者紫框，在 Campus 右外野與 Pitcher Mound 間補 `pitching-west-net` 碰撞；現行 v3 為 **133 collision／82 foreground／16 portals**。`collision_additions` 明列相對已驗收、hash 固定的舊來源新增內容；不回寫舊包、不改背景／spawn／portal，SVG／JSON／manifest 已同步匯出。`pending_manual_acceptance` 單列新圍網待驗，不能繼承舊碰撞驗收。`/ballpark/play` 桌面頁寬改為 `min(2000px,70vw)`、1100px 以下使用全寬，保留 camera zoom 0.8 與圖像比例。新碰撞及寬度由使用者確認，source-only 檢查不能代替手感／畫面通過。

`frontend/assets/ballpark/scenes/scene-kit-v3.json` 是目前唯一 runtime 場景來源，版本 `d2-scenes-v3`，沿用世界 1672×941、footprint 18×10。碰撞、前景、出生點及實際 portal target 與已驗收兩包逐欄等價；沒有重畫背景、變更碰撞或重審入口。`output/ballpark/scenes-v3/` 交付五場景 SVG／JSON 及 Game 入口 pilot；`data/sample/petehub_ballpark_scene_manifest_v3.json` 統一來源、hash、fallback、人工驗收繼承紀錄與總量：132 collision、82 foreground、16 portals。舊檔保留，inventory 改指 v3，正式角色缺件與 `production_ready=false` 保持誠實。

各室保留 `/ballpark` 靜態回退及對應 Classic route（首頁、`/teams`、`/lab`）；Team 連結由 Nuxt 套用目前 viewing team。runtime 仍 lazy-load，auth／URL／DOM owner 不變。失敗面板補直接 Classic 連結；未實際觸發錯誤或進行瀏覽器驗收。D2.6 以包裝／資料契約完成並繼承使用者既有場景與 R 驗收，不宣稱新增 browser／performance PASS。

必要檢查已通過：v3 匯出、`build_ballpark_scenes.py --version v3 --check`、`audit_ballpark_assets.py --scope=d2` 及 Nuxt typecheck。背景 PNG hash 及所有已驗收場景資料維持一致。初次 JSON 排版曾把座標逐值展開至 7,082 行，已修正為 351 行且語意完全一致；生成的 runtime JSON 使用 compact 格式，沒有新增數千行逐座標內容。

D4 接續製作內容：V3 User neutral／可自訂分件與 V2 球員代表樣本；兩者各四方向 idle 4 frames、walk 8 frames，建立可編輯來源／atlas／manifest，接回 Character 外觀保存與預覽，校準世界比例、足底、碰撞及缺件 fallback，再交使用者驗收。現有保存 API 與建角操作保留；完整 roster NPC 身分／互動仍屬 F4。D5 在這些實際素材存在後完成上述檢查與人工結果彙整。
