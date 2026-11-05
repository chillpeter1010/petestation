# Ballpark 物件盤點（生成檔，不手改）

權威來源：`data/sample/petehub_ballpark_object_catalog_v1.json`；更新：2026-11-05

狀態：使用者已接受盤點與功能配置；未接線的業務功能與 NPC／動畫仍依各物件狀態列為後續工作。

物件 ID 使用 `scene/object`；幾何 ID 使用 `scene/layer/id`。同一物件可連多形狀，多個看板也可共用父層形狀，不能把列數當實體物件數。

## 共用導覽／首頁需求

| ID | 名稱 | 功能 | Fallback | Owner |
|---|---|---|---|---|
| home-search | 首頁／球員搜尋 | 首頁與全站球員搜尋 | / | E3.1/F6 |
| recent-recommended-notices | 最近瀏覽／今日推薦／系統通知 | 沿用既有首頁內容；不存在的能力標示待實作，不杜撰通知系統 | / | F6 |
| travel-classic | 快速移動／返回 Classic | 各站選單與 Classic 永久可達，不要求走路 | / | E3.3/E4 |

## 限制與尚未完成項目

- No agent browser or movement acceptance testing performed. Source artwork may be read for authoring; visual/object completeness and function mapping require user review.
- Raw source records retain actual runtime targets. Planned semantic actions do not change those targets or prove that a feature is connected.
- Walls, furniture, nets, vegetation and lamps are blockers/decoration unless explicitly assigned a candidate function. Repeated background trim, plants and lighting without independent geometry form a declared per-scene group awaiting user additions.
- NPC points are future placeholders, not current actors or official roster identities. Random appearance and patrol behavior remain unspecified.
- User accepted original E2 and E2.1-E2.4, including the new Clubhouse C-door, ninth smoking courtyard and 59-object catalog on 2026-11-05. E2.1 is done as inventory/mapping, not all business actions connected. NPC smoking/chat remains future E3.3/F4; base source pin unchanged. Other daily/social/training action ideas are under discussion, not existing clips or automatically scheduled implementation.
- Context names below are semantic requirements, not frozen API query parameter names. Existing API/schema and auth remain authoritative.

現行九場景 runtime：`frontend/assets/ballpark/scenes/scene-kit-v4.json`；原 source pin 保留為五場景 authoring 盤點。完整有效幾何／portal／59 物件對照見 v4 object_index 及 manifest，原表不冒充整合後 target。

## Campus / Arrival Plaza · existing

場景 ID：`campus`；接線：E3.1；Fallback：`/`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| campus/game-entry · GAME 入口 | 未來進 Game 新場景；目前仍直連今日賽事 | portals/game, foreground/game-gate | selected_game_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /games/today / E2.2/F1 |
| campus/batting-entry · Batting Cages 入口 | 未來進打擊場景；目前仍直連打者站 | portals/batting, collision/cages | selected_player_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /batters / E2.3/F2 |
| campus/pitching-entry · Pitcher Mound 入口 | 未來進投手場景；目前仍直連投手站 | portals/pitching, collision/pitching-field | selected_player_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /pitchers / E2.4/F2 |
| campus/training-entry · Training & Lab 入口 | 進既有 Training & Lab 場景 | portals/training |  / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /lab / F3 |
| campus/video-entry · Video Room 入口 | 進既有 Video / Game Room | portals/video |  / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | / / F6 |
| campus/clubhouse-entry · Clubhouse 入口 | 進主隊休息室；Viewing team 可暫時切隊 | portals/clubhouse | viewing_team / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F4 |
| campus/office-entry · Team Office 入口 | 進主隊辦公室 | portals/team-office | viewing_team / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| campus/scoreboard · 外野 Leaderboard 記分板 | 排行榜；保留排名母體、as-of 及直接入口 | hotspots/leaderboard | season, ranking_filters / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /leaderboards / F1 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

| 幾何 ID | 參考 bounds [x,y,w,h] | 現有 runtime target |
|---|---|---|
| campus/collision/cages | [0, 0, 425, 334] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/field-fence | [420, 0, 925, 545] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/pitching-field | [1334, 0, 338, 350] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/pitching-flowerbed | [1345, 319, 87, 44] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/training-building | [0, 381, 426, 188] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/training-garden | [430, 433, 104, 152] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/cages-ballcart | [403, 310, 77, 62] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/video-building | [1420, 371, 252, 206] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/video-garden | [1355, 420, 60, 164] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/clubhouse-building | [0, 621, 566, 210] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/office-building | [1133, 618, 539, 213] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/west-plaza-garden | [552, 577, 196, 263] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/east-plaza-garden | [994, 577, 197, 266] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/gate-lamp-west | [782, 788, 39, 60] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/gate-lamp-east | [924, 791, 38, 58] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/south-west-trees | [0, 865, 794, 76] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/south-east-trees | [962, 868, 710, 73] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/west-bench | [87, 359, 90, 17] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/south-west-bench | [82, 816, 94, 22] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/south-east-bench | [1538, 815, 87, 21] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/video-lamppost | [1330, 513, 15, 19] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/west-field-lamppost | [561, 545, 23, 20] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/east-field-lamppost | [1160, 545, 23, 20] | 裝飾／阻擋／遮擋；無 action |
| campus/collision/pitching-west-net | [1320, 225, 28, 94] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/game-gate | [742, 440, 195, 99] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/west-front-lamp | [559, 417, 35, 148] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/east-front-lamp | [1158, 417, 35, 148] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/west-plaza-tree | [574, 583, 93, 99] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/east-plaza-tree | [1081, 599, 73, 87] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/west-lower-tree | [525, 723, 127, 109] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/east-lower-tree | [1053, 726, 117, 106] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/entrance-lamp-west | [782, 747, 38, 102] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/entrance-lamp-east | [923, 747, 39, 103] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/west-entry-fence | [665, 711, 116, 102] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/east-entry-fence | [963, 712, 110, 104] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/west-training-tree | [424, 436, 87, 113] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/east-path-tree | [1343, 427, 64, 84] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/west-club-roof | [0, 621, 566, 89] | 裝飾／阻擋／遮擋；無 action |
| campus/foreground/east-office-roof | [1133, 618, 539, 94] | 裝飾／阻擋／遮擋；無 action |
| campus/portals/game | [790, 540, 100, 38] | {"route":"/games/today"} |
| campus/portals/batting | [345, 289, 56, 46] | {"route":"/batters"} |
| campus/portals/pitching | [1440, 350, 100, 20] | {"route":"/pitchers"} |
| campus/portals/training | [165, 569, 145, 35] | {"room":"training-lab"} |
| campus/portals/video | [1500, 577, 125, 34] | {"room":"video-game-room"} |
| campus/portals/clubhouse | [245, 831, 165, 35] | {"room":"clubhouse"} |
| campus/portals/team-office | [1335, 831, 165, 35] | {"room":"team-office"} |
| campus/hotspots/leaderboard | [750, 45, 175, 100] | {"route":"/leaderboards"} |

背景內無獨立資料的牆面飾條、小植栽／照明與雜物列為本場景裝飾群，待使用者補漏；不是已逐像素盤點。

## Clubhouse · existing

場景 ID：`clubhouse`；接線：E3.1；Fallback：`/teams`

- 新增後門／場景補充包（使用者已驗收）：`frontend/assets/ballpark/scenes/scene-kit-clubhouse-annex-v1.json`；下方 base refs 與全量幾何清單仍為凍結來源，新增門見補充包。

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| clubhouse/player-list · PLAYER LIST／完整名單 | 官方 active roster 與直接選人；fresh/stale/unavailable | portals/roster | viewing_team, official_roster_retrieved_at / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F4 |
| clubhouse/north-lockers · 北側球員置物櫃群 | 預留選定球員資料／對話；不能把櫃上數字推定為真實名單 | collision/north-wall-lockers | viewing_team, official_roster_player / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F4 |
| clubhouse/south-lockers · 南側球員置物櫃群 | 同北側；畫面群組可依核准 NPC 站位再拆穩定子 ID | collision/south-west-lockers, collision/south-east-lockers, foreground/bottom-locker-row, foreground/bottom-locker-row-east | viewing_team, official_roster_player / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F4 |
| clubhouse/smoking-door · ???????? | ??? C ?????Enter / Exit ?????????????????????????????????? | ??????????????? bounds [1318,292,42,52] | viewing_team / active_user | nearby_C_or_equivalent_button_menu / runtime_wired_user_accepted | /ballpark/play?room=clubhouse-smoking-area / E2.1 user-requested annex |
| clubhouse/npc-lounge-points · 代表球員 NPC 互動點（未定位） | 8–10 名代表球員，走近對話／個人數據；不是本輪新增角色 | 可走動空地／休息區外緣，避免中央通道 | viewing_team, official_roster_player / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / E3.3/F4 |
| clubhouse/tv-cabinet · 電視／上方櫃體 | 本期裝飾／阻擋，暫不新增獨立影片功能 | collision/tv-upper-cabinet, collision/tv-plant |  / active_user | none / planned_not_runtime_wired | /teams / E2 |
| clubhouse/lounge-dining · 沙發／茶几／餐桌群 | 本期裝飾／阻擋；NPC 不可因布置堵住中央通道 | collision/north-sofa, collision/lounge-table, collision/east-sofa, collision/south-sofa, collision/dining-set |  / active_user | none / planned_not_runtime_wired | /teams / E2 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

| 幾何 ID | 參考 bounds [x,y,w,h] | 現有 runtime target |
|---|---|---|
| clubhouse/collision/north-wall-lockers | [0, 0, 1395, 285] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/right-wall | [1368, 0, 304, 941] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/west-wall | [0, 0, 35, 941] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/tv-plant | [35, 380, 112, 166] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/north-sofa | [201, 361, 213, 42] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/lounge-table | [240, 434, 131, 45] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/east-sofa | [408, 430, 53, 75] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/south-sofa | [200, 503, 214, 37] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/dining-set | [1115, 355, 198, 123] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/south-west-lockers | [35, 571, 518, 191] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/south-east-lockers | [980, 568, 360, 192] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/plant-west | [557, 691, 39, 52] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/plant-east | [918, 691, 39, 52] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/equipment-west | [35, 800, 292, 83] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/equipment-east | [1072, 785, 278, 98] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/south-wall | [0, 884, 1672, 57] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/collision/tv-upper-cabinet | [35, 285, 77, 100] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/lounge-north-sofa | [202, 323, 212, 78] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/lounge-table | [240, 400, 131, 79] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/lounge-east-sofa | [409, 399, 50, 105] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/lounge-south-sofa | [200, 478, 213, 61] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/dining-table | [1123, 323, 190, 155] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/west-plant | [553, 627, 48, 117] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/east-plant | [914, 624, 49, 120] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/bottom-locker-row | [35, 556, 518, 54] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/foreground/bottom-locker-row-east | [980, 556, 360, 54] | 裝飾／阻擋／遮擋；無 action |
| clubhouse/portals/roster | [1040, 285, 95, 40] | {"route":"/teams"} |
| clubhouse/portals/return | [730, 842, 160, 40] | {"room":"campus","spawn":"clubhouse"} |

背景內無獨立資料的牆面飾條、小植栽／照明與雜物列為本場景裝飾群，待使用者補漏；不是已逐像素盤點。

## Team Office · existing

場景 ID：`team-office`；接線：E3.1；Fallback：`/teams`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| team-office/coach-rotation · Coach 輪值看板 | 主隊輪值 | Coach 後牆看板群內；待獨立互動框 collision/coach-rear-wall-equipment | viewing_team, season / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/coach-lineup · Coach 打線看板 | 主隊打線；資料未提供時顯示 unavailable | Coach 後牆看板群內；待獨立互動框 collision/coach-rear-wall-equipment | viewing_team, selected_game_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/coach-bullpen · Coach 牛棚看板 | 主隊牛棚 | Coach 後牆看板群內；待獨立互動框 collision/coach-rear-wall-equipment | viewing_team, season / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/coach-workspace · Coach 工作桌／白板 | 球隊 Coach 面板直接選單，三看板相同來源 | collision/coach-desk, foreground/coach-whiteboard | viewing_team / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/gm-trades · GM 交易螢幕 | 球隊交易／異動紀錄，不是執行真實交易 | GM 後牆螢幕群內；待獨立互動框 collision/manager-rear-wall-equipment | viewing_team, as_of / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/gm-payroll · GM 薪資螢幕 | 薪資資料；資料來源／功能未發布前不可用 | GM 後牆螢幕群內；待獨立互動框 collision/manager-rear-wall-equipment | viewing_team, season, salary_source / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/gm-contracts · GM 合約螢幕 | 合約資料；無可靠資料時明示 unavailable | GM 後牆螢幕群內；待獨立互動框 collision/manager-rear-wall-equipment | viewing_team, contract_source / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/gm-workspace · GM 工作桌 | 球隊 GM 面板直接選單 | collision/manager-desk, foreground/manager-desk | viewing_team / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /teams / F5 |
| team-office/admin-frame · Per aspera ad astra 畫框 | 既有後台熱區；不得另加浮動彩蛋按鈕 | hotspots/admin-frame |  / admin_and_exact_username_peter1010_server_enforced | existing_pointer_only / existing_runtime_hotspot | /admin/updates / C4/E3.1 |
| team-office/alcove-cabinet · 中央雙門壁龕／入口盆栽櫃 | 本期裝飾／阻擋，不新增假門功能 | collision/central-door-alcove, collision/manager-entry-plant-cabinet |  / active_user | none / planned_not_runtime_wired | /teams / E2 |
| team-office/meeting-lounge · 會議桌椅／GM 休息區 | 本期裝飾／阻擋，保留既有側邊通道 | collision/coach-table-chairs, collision/manager-sofa, collision/manager-coffee-table |  / active_user | none / planned_not_runtime_wired | /teams / E2 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

| 幾何 ID | 參考 bounds [x,y,w,h] | 現有 runtime target |
|---|---|---|
| team-office/collision/north-wall | [0, 0, 1672, 431] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/west-wall-cabinets | [0, 0, 145, 794] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/east-wall-cabinets | [1540, 0, 132, 941] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coach-chair | [330, 385, 75, 47] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coach-desk | [250, 440, 236, 88] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coach-table-chairs | [204, 554, 332, 218] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coach-whiteboard | [134, 531, 58, 85] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coach-files | [575, 549, 64, 93] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-west-wall | [643, 452, 35, 342] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-east-wall | [992, 452, 34, 342] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-west-seat | [678, 525, 42, 106] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-east-seat | [949, 525, 43, 106] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-chair | [1278, 385, 68, 37] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-desk | [1165, 430, 276, 79] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-left-chair | [1168, 533, 66, 47] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-table | [1250, 536, 110, 58] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-right-chair | [1370, 532, 66, 48] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coat-rack | [1075, 614, 51, 44] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-sofa | [1223, 682, 202, 31] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-coffee-table | [1240, 727, 151, 45] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-plant | [1468, 704, 49, 76] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-west-plant | [685, 738, 46, 46] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-west-lamp | [687, 811, 48, 40] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/hall-east-lamp | [944, 811, 44, 40] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/south-wall-west | [0, 795, 683, 146] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/south-wall-east | [989, 795, 683, 146] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/south-step | [0, 916, 1672, 25] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/coach-rear-wall-equipment | [105, 200, 559, 185] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-rear-wall-equipment | [1010, 200, 530, 185] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/central-door-alcove | [643, 300, 383, 131] | 裝飾／阻擋／遮擋；無 action |
| team-office/collision/manager-entry-plant-cabinet | [1026, 505, 57, 137] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/coach-desk | [250, 414, 236, 114] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/coach-meeting-set | [205, 554, 350, 218] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/coach-whiteboard | [133, 489, 60, 128] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/manager-desk | [1165, 387, 276, 122] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/manager-visitor-table | [1168, 490, 269, 104] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/manager-sofa | [1223, 638, 202, 75] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/manager-coffee-table | [1240, 692, 151, 80] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/manager-plant | [1460, 625, 67, 156] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/coat-rack | [1074, 507, 52, 152] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/hall-west-plant | [678, 684, 58, 103] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/entry-lamp-west | [687, 774, 48, 76] | 裝飾／阻擋／遮擋；無 action |
| team-office/foreground/entry-lamp-east | [944, 775, 44, 76] | 裝飾／阻擋／遮擋；無 action |
| team-office/portals/coach | [485, 361, 135, 70] | {"route":"/teams"} |
| team-office/portals/manager | [1040, 357, 123, 70] | {"route":"/teams"} |
| team-office/portals/return | [765, 852, 145, 45] | {"room":"campus","spawn":"team-office"} |
| team-office/hotspots/admin-frame | [785, 152, 104, 55] | {"action":"admin","route":"/admin/updates"} |

背景內無獨立資料的牆面飾條、小植栽／照明與雜物列為本場景裝飾群，待使用者補漏；不是已逐像素盤點。

## Training & Lab · existing

場景 ID：`training-lab`；接線：E3.1；Fallback：`/lab`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| training-lab/lab-directory · Lab 工作區入口／工具選單 | 完整研究工具選單與直接入口 | portals/lab | research_release_status / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /lab / F3 |
| training-lab/stuff-location · 分析桌：Stuff+／Location+ 終端 | 跨球員分析；共用既有 Lab，保留版本與研究標示 | collision/analytics-desk, foreground/analytics-desk | season, selected_players, metric_version / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /lab / F3 |
| training-lab/stamina-performance · 追蹤螢幕：Stamina／Performance State | 兩條獨立研究／狀態工具；不捏造合成分數 | collision/tracking-screen, foreground/tracking-screen | selected_player, as_of, research_release_status / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /lab / F3 |
| training-lab/comparison-calculator · 工作台：比較工具／計算器 | 共用比較入口、Stuff calculator 與其限制 | collision/lab-workbench, foreground/lab-workbench | selected_players, metric_version / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /lab / F3 |
| training-lab/cross-domain-directory · Lab 工作區跨領域選單 | 其他已發布研究、捕手／守備等工具由選單提供，不要求每工具重畫一物件 | collision/lab-workbench | research_release_status / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /lab / F3 |
| training-lab/training-equipment · 重量／練習網／攝影設備群 | 本期裝飾／阻擋；不把測量器材畫面說成實際生理檢測或新模擬 | collision/batting-net, collision/weight-rack, collision/tracking-camera, collision/tracking-net |  / active_user | none / planned_not_runtime_wired | /lab / E2 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

| 幾何 ID | 參考 bounds [x,y,w,h] | 現有 runtime target |
|---|---|---|
| training-lab/collision/north-wall | [0, 0, 1672, 236] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/west-wall | [0, 0, 48, 941] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/east-wall | [1620, 0, 52, 941] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/south-wall-west | [0, 763, 632, 178] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/south-wall-east | [1040, 763, 632, 178] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/entry-column-west | [632, 720, 49, 221] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/entry-column-east | [991, 720, 49, 221] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/entry-door | [681, 884, 310, 57] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/batting-net | [145, 174, 338, 194] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/batting-equipment | [483, 260, 70, 106] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/west-equipment | [48, 174, 93, 236] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/north-storage | [514, 174, 102, 70] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/weight-rack | [100, 426, 220, 156] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/weight-bench | [193, 518, 48, 96] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/plyo-boxes | [370, 431, 51, 92] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/medicine-balls | [447, 405, 81, 114] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/bands-and-bench | [538, 435, 93, 145] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/kettlebell-rack | [59, 614, 117, 133] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/weight-storage | [205, 662, 70, 78] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/foam-roller-rack | [355, 638, 32, 102] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/west-water-and-plant | [588, 625, 50, 133] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/tracking-net | [1201, 174, 236, 213] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/tracking-camera | [1110, 286, 57, 86] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/tracking-screen | [1468, 281, 130, 120] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/analytics-desk | [1105, 445, 369, 129] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/lab-west-cabinet | [1060, 433, 45, 124] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/lab-east-cart | [1475, 449, 142, 137] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/lab-workbench | [1100, 618, 321, 135] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/lab-south-storage | [1428, 647, 121, 95] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/lab-south-west-cabinet | [1058, 648, 39, 94] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/lab-south-east-plant | [1572, 712, 46, 50] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/entry-plant-west | [682, 851, 48, 52] | 裝飾／阻擋／遮擋；無 action |
| training-lab/collision/entry-plant-east | [946, 851, 44, 52] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/batting-net | [146, 107, 337, 261] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/batting-cart | [483, 260, 69, 106] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/weight-rack | [100, 397, 220, 185] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/weight-bench | [193, 517, 48, 97] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/plyo-boxes | [370, 428, 51, 95] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/medicine-balls | [447, 382, 81, 137] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/bands-and-bench | [538, 428, 92, 152] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/kettlebell-rack | [59, 596, 117, 151] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/weight-storage | [205, 659, 70, 81] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/foam-rollers | [355, 631, 32, 109] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/west-plant | [588, 666, 55, 92] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/tracking-net | [1201, 120, 236, 267] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/tracking-camera | [1107, 244, 60, 128] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/tracking-screen | [1468, 208, 133, 193] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/analytics-desk | [1105, 397, 369, 160] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/analytics-chair-west | [1189, 490, 60, 84] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/analytics-chair-east | [1350, 490, 70, 84] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/lab-workbench | [1100, 594, 321, 144] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/lab-stool | [1230, 688, 56, 65] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/lab-south-storage | [1428, 599, 121, 143] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/lab-south-east-plant | [1570, 659, 53, 103] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/entry-plant-west | [675, 814, 58, 89] | 裝飾／阻擋／遮擋；無 action |
| training-lab/foreground/entry-plant-east | [940, 813, 56, 90] | 裝飾／阻擋／遮擋；無 action |
| training-lab/portals/lab | [1110, 575, 350, 30] | {"route":"/lab"} |
| training-lab/portals/return | [748, 754, 176, 56] | {"room":"campus","spawn":"training"} |

背景內無獨立資料的牆面飾條、小植栽／照明與雜物列為本場景裝飾群，待使用者補漏；不是已逐像素盤點。

## Video / Game Room · existing

場景 ID：`video-game-room`；接線：E3.1；Fallback：`/`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| video-game-room/recommended-screen · 推薦影片主螢幕 | 沿用首頁推薦影片；目前 runtime action 只開推薦說明／首頁連結，未直接嵌入完整影片功能 | portals/recommendations, foreground/television | video_identity, availability / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | / / F6 |
| video-game-room/video-library · 影片櫃／工作站 | 同一推薦影片清單的次入口，不另外建立不相干的影片庫 | collision/video-library, collision/review-workstation | video_identity, availability / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | / / F6 |
| video-game-room/future-minigames · 遊戲機／Game bay 群 | 僅預留未來小遊戲空間，本輪不製作遊戲 | collision/arcade-west, collision/arcade-east, collision/game-bay-west, collision/game-bay-east |  / active_user | none_until_separately_scoped / planned_not_runtime_wired | / / F6 |
| video-game-room/lounge-vending · 休息座椅／販賣機 | 本期裝飾／阻擋，不新增經濟系統 | collision/lounge-sofa, collision/lounge-south-sofa, collision/lounge-armchair, collision/vending |  / active_user | none / planned_not_runtime_wired | / / E2 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

| 幾何 ID | 參考 bounds [x,y,w,h] | 現有 runtime target |
|---|---|---|
| video-game-room/collision/north-wall | [0, 0, 1672, 285] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/west-wall | [0, 0, 52, 941] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/east-wall | [1620, 0, 52, 941] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/south-wall-west | [0, 714, 655, 227] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/south-wall-east | [1018, 714, 654, 227] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/entry-column-west | [655, 685, 48, 256] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/entry-column-east | [970, 685, 48, 256] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/entry-door | [703, 818, 267, 123] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/television-console | [204, 265, 296, 40] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/review-workstation | [60, 378, 277, 160] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-sofa | [421, 365, 112, 161] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-side-table | [533, 430, 36, 86] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-north-plant | [534, 378, 41, 52] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-south-sofa | [190, 598, 196, 42] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-armchair | [420, 580, 84, 71] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-floor-lamp | [510, 615, 28, 30] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-south-plant | [544, 607, 38, 48] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/lounge-west-plant | [121, 611, 34, 30] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/video-library | [110, 644, 173, 69] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/vending | [284, 658, 87, 56] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/game-bay-west | [1091, 285, 218, 71] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/game-bay-east | [1332, 285, 222, 71] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/arcade-west | [1180, 425, 93, 116] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/arcade-stool-west | [1204, 516, 51, 44] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/arcade-east | [1358, 425, 98, 116] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/arcade-stool-east | [1385, 516, 50, 44] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/arcade-plant | [1292, 420, 45, 73] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/east-cabinet-and-plant | [1567, 407, 51, 179] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/game-display-cabinets | [1338, 645, 232, 69] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/game-south-plant | [1278, 673, 60, 41] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/game-east-plant | [1577, 645, 41, 64] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/entry-plant-west | [704, 798, 49, 51] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/collision/entry-plant-east | [916, 798, 50, 51] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/television | [204, 111, 296, 194] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/review-workstation | [60, 325, 277, 213] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-sofa | [421, 345, 112, 181] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-side-table | [533, 430, 36, 86] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-north-plant | [533, 334, 50, 96] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-south-sofa | [190, 571, 196, 69] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-armchair | [420, 548, 84, 103] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-floor-lamp | [509, 520, 29, 125] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/lounge-south-plant | [540, 558, 48, 97] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/video-library | [110, 644, 173, 69] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/vending | [284, 638, 87, 76] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/game-bay-west | [1091, 111, 218, 245] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/game-bay-east | [1332, 111, 222, 245] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/arcade-west | [1180, 374, 93, 167] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/arcade-stool-west | [1204, 516, 51, 44] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/arcade-east | [1358, 374, 98, 167] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/arcade-stool-east | [1385, 516, 50, 44] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/arcade-plant | [1287, 377, 59, 116] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/game-display-cabinets | [1338, 620, 232, 94] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/game-south-plant | [1273, 628, 67, 86] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/game-east-plant | [1573, 601, 51, 108] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/entry-plant-west | [699, 756, 61, 93] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/foreground/entry-plant-east | [912, 761, 60, 88] | 裝飾／阻擋／遮擋；無 action |
| video-game-room/portals/recommendations | [350, 307, 180, 34] | {"action":"video"} |
| video-game-room/portals/return | [760, 720, 148, 50] | {"room":"campus","spawn":"video"} |

背景內無獨立資料的牆面飾條、小植栽／照明與雜物列為本場景裝飾群，待使用者補漏；不是已逐像素盤點。

## Game 新場景 · user_accepted_scene_object_actions_pending

場景 ID：`game-center`；接線：E3.2；Fallback：`/games/today`

- 場景：球場觀賽／比賽分析控制區，能辨識棒球場，而非另一間 Team Office
- 配置草案：南側中央入口及開放主走道；北側賽程看板，側邊分析台與回放螢幕，所有互動點有可站立空間
- 畫風：沿用已核准俯視像素 RPG、暖光與 Petehub 黑橘；無角色／HUD／烘入游標
- Gate：功能配置先核准；新背景另由使用者核准後才製作幾何與 runtime 包

- 已核准背景設計：`output/ballpark/e2-facilities-v1/game-center-concept-v1.png`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| game-center/schedule-board · 賽程／比分看板 | 今日賽事、比分與選定比賽 | 北側主看板 | date, selected_game / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /games/today / F1 |
| game-center/game-analysis-console · 比賽分析控制台 | Box Score／Location／Sequence／Movement 以同一場比賽與球員選擇切頁 | 側邊工作台，從主走道可達 | selected_game, selected_player, selected_pitch_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /games/today / F1 |
| game-center/replay-screen · Pitch Replay／影片螢幕 | 同一比賽／球路的 Historical Pitch Replay 與影片；不可改成 synthetic simulation | 另一側觀賽螢幕 | selected_game, selected_pitch, video_identity_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /games/today / F1 |
| game-center/return · 返回 Campus 出口 | 靠近按 R 到 Campus GAME 入口外 | 南側中央 | origin_arrival / active_user | near_exit_R / planned_not_runtime_wired | /ballpark/play / E2.2/E4 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

獨立新增場景包：`frontend/assets/ballpark/scenes/scene-kit-e2-2-v1.json`；含物件 bounds／碰撞／遮擋／出口，使用者已接受本場景介面／所列人工項目。上方 refs 仍以凍結五場景來源為準，新包明細在其 JSON；物件功能未接線。

## Batting Cages 新場景 · user_accepted_scene_object_actions_pending

場景 ID：`batting-cages`；接線：E3.2；Fallback：`/batters`

- 場景：有網籠、打擊墊與器材的室內打擊訓練區，不用 Training & Lab 背景替代
- 配置草案：南側中央入口／開放主走道；北側練習網籠，兩側名冊、數據與比較站，網子外留通道
- 畫風：沿用已核准俯視像素 RPG；無人物／HUD／烘入游標／實際揮棒動畫
- Gate：功能配置先核准；新背景另由使用者核准後才製作幾何與 runtime 包

- 已核准背景設計：`output/ballpark/e2-facilities-v1/batting-cages-concept-v1.png`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| batting-cages/batter-directory · 打者名冊／選人終端 | 打者搜尋與選定球員；完整站內工具選單 | 入口側邊 | selected_player, season / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /batters / F2 |
| batting-cages/batter-analysis · 個人數據螢幕 | 打者個人分析及排行榜；先選人，不能打開無身分的個人頁 | 練習網外側工作台 | selected_player, season, filters / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /batters / F2 |
| batting-cages/batter-comparison · 打者比較看板 | 球員／期間／球隊／打線比較共用選單 | 側邊看板 | selected_players, period, viewing_team_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /batters/comparison / F2 |
| batting-cages/batter-lab · 打擊研究終端 | 既有 Batter Lab，保留 Lab／來源／缺資料限制，不自行發布候選指標 | 另一側設備台 | selected_player, research_release_status / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /batters/lab / F2 |
| batting-cages/practice-cage · 練習網籠／器材群 | 場景裝飾與阻擋，不代表已實作打擊小遊戲 | 北側練習區 |  / active_user | none / planned_not_runtime_wired | /batters / E2.3 |
| batting-cages/return · 返回 Campus 出口 | 靠近按 R 到 Campus Batting 入口外 | 南側中央 | origin_arrival / active_user | near_exit_R / planned_not_runtime_wired | /ballpark/play / E2.3/E4 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

獨立新增場景包：`frontend/assets/ballpark/scenes/scene-kit-e2-3-4-v1.json`；含物件 bounds／碰撞／遮擋／出口，使用者已接受本場景介面／所列人工項目。上方 refs 仍以凍結五場景來源為準，新包明細在其 JSON；物件功能未接線。

## Pitcher Mound 新場景 · user_accepted_scene_object_actions_pending

場景 ID：`pitcher-mound`；接線：E3.2；Fallback：`/pitchers`

- 場景：牛棚／投球練習區，可見投手丘、捕手目標與保護網，具投手設施辨識
- 配置草案：南側中央入口及寬走道；北側投球道，側邊名冊、球路／位置螢幕與比較站，避免把網子畫在必經通道
- 畫風：沿用已核准俯視像素 RPG；無人物／HUD／烘入游標／虛構實測儀表值
- Gate：功能配置先核准；新背景另由使用者核准後才製作幾何與 runtime 包

- 已核准背景設計：`output/ballpark/e2-facilities-v1/pitcher-mound-concept-v1.png`

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| pitcher-mound/pitcher-directory · 投手名冊／選人終端 | 投手搜尋／選人及完整站內工具選單 | 入口側邊 | selected_player, season / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /pitchers / F2 |
| pitcher-mound/pitch-analysis · Shape／球路與位置分析螢幕 | 僅保留個人球路、位置與 spin；In game 移至兩條牛棚道，不在此重複提供入口 | 左側分析台（移除原 In game 區） | selected_player, season, filters / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /pitchers / F2 |
| pitcher-mound/pitcher-comparison · 投手比較／相似度看板 | 個人／期間比較與相似投手工具 | 側邊看板 | selected_players, period / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /comparison/personal / F2 |
| pitcher-mound/pitcher-tools · 投手工具／輪值牛棚選單 | 保留既有投手工具與輪值／牛棚 direct links；球隊管理主入口仍在 Team Office，跨領域研究主入口仍 Training | 另一側工作台 | selected_player_optional, viewing_team_optional, research_release_status / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /pitchers / F2 |
| pitcher-mound/in-game-west · 左牛棚 In game | 未來隨機刷新所屬球隊投手在道內投球；可用等價 DOM 選單選投手及出賽場次，共用 Personal In game 逐球／影片。預設球隊為 favorite team，Viewing team 切換時跟隨瀏覽球隊；以官方 active roster 的投手候選為準。投球人體動作為明示 generic 展示，不宣稱歷史 mechanics 重建。尚未實作 actor／動畫或業務接線 | 西側投球道，站在網外操作 | viewing_team, favorite_team_default, official_active_roster, selected_player, season, selected_game, selected_pitch_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /pitchers / E3.2/E4/F2 |
| pitcher-mound/in-game-east · 右牛棚 In game | 與左牛棚相同的所屬球隊投手隨機刷新／投球展示及投手、場次選單；兩道各有穩定物件 ID。隨機不覆蓋使用者手動選擇；無 roster／無出賽資料須有明確 unavailable，不能造球員／場次。刷新頻率、兩道去重與動畫規格在 F2 實作前細化，現在未執行 | 東側投球道，站在網外操作 | viewing_team, favorite_team_default, official_active_roster, selected_player, season, selected_game, selected_pitch_optional / active_user | nearby_E_or_pointer_with_equivalent_direct_menu / planned_not_runtime_wired | /pitchers / E3.2/E4/F2 |
| pitcher-mound/return · 返回 Campus 出口 | 靠近按 R 到 Campus Pitcher 入口外 | 南側中央 | origin_arrival / active_user | near_exit_R / planned_not_runtime_wired | /ballpark/play / E2.4/E4 |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

獨立新增場景包：`frontend/assets/ballpark/scenes/scene-kit-e2-3-4-v1.json`；含物件 bounds／碰撞／遮擋／出口，使用者已接受本場景介面／所列人工項目。上方 refs 仍以凍結五場景來源為準，新包明細在其 JSON；物件功能未接線。

## Clubhouse ????? · user_accepted_scene_object_actions_pending

場景 ID：`clubhouse-smoking-area`；接線：E3.3/F4；Fallback：`/teams`

- 場景：?????????????????????????? Clubhouse
- 配置草案：???????????????????? R ?? Clubhouse ???
- 畫風：?????? RPG??????????????
- Gate：??????C/R ?????????? 2026-11-05 ???NPC??????????

### 功能物件／候選配置

父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。

| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |
|---|---|---|---|---|---|
| clubhouse-smoking-area/bench-west · ??????? | ?????????????? action | ??? bounds [181, 350, 354, 132] |  / active_user | none / user_accepted_decoration_geometry | /teams / E2.1 annex |
| clubhouse-smoking-area/bench-east · ??????? | ?????????????? action | ??? bounds [1137, 350, 357, 132] |  / active_user | none / user_accepted_decoration_geometry | /teams / E2.1 annex |
| clubhouse-smoking-area/ashtray · ????? | ?????????????? action | ??? bounds [1258, 526, 65, 132] |  / active_user | none / user_accepted_decoration_geometry | /teams / E2.1 annex |
| clubhouse-smoking-area/chat-spot-west · ???????????? | ???????????????????????????????????????????????? NPC??????????????????? F4 ?? | ??? bounds [560, 480, 80, 80] | viewing_team, official_active_roster, npc_dialogue_state / active_user | future_nearby_chat_with_equivalent_menu / planned_not_runtime_wired | /teams / E3.3/F4 |
| clubhouse-smoking-area/chat-spot-east · ???????????? | ???????????????????????????????????????????????? NPC??????????????????? F4 ?? | ??? bounds [1030, 480, 80, 80] | viewing_team, official_active_roster, npc_dialogue_state / active_user | future_nearby_chat_with_equivalent_menu / planned_not_runtime_wired | /teams / E3.3/F4 |
| clubhouse-smoking-area/return · ?? Clubhouse ?? | ??? R ? Clubhouse smoking-door ?????????? | ???????? portals/return | viewing_team, origin_arrival / active_user | near_exit_R / runtime_wired_user_accepted | /ballpark/play?room=clubhouse&spawn=smoking-door / E2.1 annex |

### 來源幾何／現有入口全量清單

未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。

獨立新增場景包：`frontend/assets/ballpark/scenes/scene-kit-clubhouse-annex-v1.json`；含物件 bounds／碰撞／遮擋／出口，使用者已接受本場景介面／所列人工項目。上方 refs 仍以凍結五場景來源為準，新包明細在其 JSON；物件功能未接線。

來源覆蓋：9 場景（5 base／4 supplemental）；59 個語意物件／候選；凍結五場景來源含 138 collision、82 foreground、16 portals、2 hotspots。不是人工畫面驗收。
