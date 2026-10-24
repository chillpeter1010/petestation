# Research Display Contract

更新日期：2026-10-20
狀態：v1，適用於此日期後新增的研究頁面；既有頁面採小 Slice 漸進遷移，不做一次性全站重寫。

## 目的

讓同一種資訊在不同研究頁面維持相同的閱讀與互動方式。此規範只決定呈現契約，不改變模型、資料或統計結論。

## 玩家層級表格

- 正文桌面版 14 px、行高至少 1.4；表頭 12 px、粗體。窄螢幕可降至 13 px，但不可低於 12 px。
- 玩家列預設顯示 44 px 圓形頭像；無有效 MLBAM ID 或圖片載入失敗時顯示姓名縮寫，不留下破圖。
- 玩家姓名必須連到對應的 Pitcher Personal 或 Batter Personal；頭像與姓名共用同一個連結及可點擊區。
- 除純操作欄、縮圖欄或無順序意義的欄位外，表頭皆可排序。第一次點擊數值欄預設由高至低；再次點擊反轉方向，並顯示目前方向。
- 數字小數位、百分比與 Plus 指標格式由欄位契約明定，不由元件猜測。缺值一律顯示 `—`，不得用 0 代替。
- 超過可視寬度時採水平捲動並固定表頭；不壓縮到無法閱讀。大量資料要標示目前列數、總列數與篩選條件。
- 每張表都要有 loading、empty、error 三種狀態；只用顏色不足以表達排名、警告或選取狀態。
- 可展開列必須支援 Enter／Space 鍵，並以 `aria-expanded` 說明狀態；點姓名連結不可同時觸發展開。

聚合表（例如 tag 人數、年度覆蓋率）不強制放玩家頭像或球員頁連結，但仍須遵守排序、字級、缺值與狀態規範。

## PR 與績效色階

- `實際數據／PR值`只適用於有明確比較方向的玩家或搭配績效欄位；樣本量、coverage、status、日期、ID、可靠度與敏感度診斷不建立PR。
- PR是指定且固定合格母體內的經驗百分位，ties使用平均名次；搜尋、隊伍或畫面篩選不得改變同一頁的PR母體。
- 所有PR統一轉成「越高越有利」的方向。實際值較低為佳的ERA、RA9、FIP、Whiff%等欄位必須反轉百分位，不可讓使用者自行猜測方向。
- Heat map使用共用`performanceColor`色階：深紅／紅代表較有利，白色接近中位，藍／深藍代表較不利。切換實際值或PR只改顯示數字，不改底層PR與色彩。
- 不合格列的PR維持`—`且不著色，不因畫面需要而補值。描述性關聯、模型估計與來源定義仍須保留原有限制文字；上色不構成因果或talent-grade宣稱。

### 2026-10-20 leaderboard adoption audit

盤點單位是明確標示為Leaderboard、Rankings或Performance board的獨立資料視圖；不把個人頁明細、game log、校準／validation表、tag roster或一般operational roster算進來。

- 公開區：完整`實際數據／PR值 + Heat map`採用率為`9/9`。已涵蓋Pitcher Rankings的Basic／Stuff+／Location+／Pitching+／Stamina+共5個view、Batter Leaderboard的Production／Contact共2個view、Team Dashboard Performance board的Pitching／Batting共2個view。
- Lab／研究區：採用率為`6/10`。已完成Swing Timing、Stuff Attack、Location+ Field、Pitching+ Lab各1個view，以及Catcher Leaderboard／Paired Duo 2個view。仍未完成RE24 & Leverage、Performance State各1個view，以及Stamina Lab內2個研究排名表，共4個view。
- Catcher Lab的pair accounting、Tag Lab roster，以及各研究頁的diagnostic／calibration表不是PR migration目標。本輪未改動其餘4個Lab榜單；只有在提升為主要入口或使用者明確要求時再逐頁遷移。

### 未來 Leaderboard 製作須知

新增或改造任何Leaderboard、Rankings或Performance board時，PR與Heat map不是事後裝飾，而是資料契約的一部分。實作前後均須確認：

1. 明列PR參考母體、年度、角色與最低樣本門檻。會改變分析問題的條件（例如球種、投手慣用手、Minimum IP／PA）可以重建母體；搜尋、隊伍與純畫面篩選不得偷偷改變母體。
2. 每個可排名欄位必須登記`higher`或`lower`方向；轉成PR後一律維持「越高越有利」。沒有單一好壞方向的策略、使用量或選擇欄位不得硬套PR。
3. 樣本量、局數、PA、球數、日期、ID、coverage、status、可靠度、不確定區間與敏感度診斷預設不排名、不上色。累計型結果只有在產品明確要衡量產量且文件說明時才能例外。
4. 使用共用`LeaderboardDisplayControls`、`buildLeaderboardPercentiles`與`leaderboardHeatStyle`；ties採平均名次，缺值不補0，單一有效樣本回到PR 50。
5. `實際數據／PR值`只改儲存格顯示；Heat map永遠依相同底層PR著色。深紅／紅代表有利，藍／深藍代表不利，不可因頁面主題反轉。
6. PR模式排序必須按PR，而不是按已反轉前的原始值；低為佳欄位尤其需要驗證。若使用共用`DataTable`，可把顯示值換成PR並保留`__percentiles`供色階使用。
7. 畫面必須就近揭露母體、門檻、方向與排除欄位；低於門檻或母體外列顯示`—`且不著色，不能用補值製造排名。
8. 完成前至少驗證：百分位範圍、ties、低為佳反轉、缺值、搜尋／隊伍篩選不變性、門檻變更行為、PR排序、鍵盤操作、窄螢幕水平捲動、Nuxt typecheck與UTF-8。

## 玩家座標圖與回歸圖

- 圖名必須直接說明比較的兩個量；X／Y 軸均顯示完整名稱、單位與「高代表較好或較差」。
- Plus 指標以 100 為中心時要畫 100 參考線；其他指標只在具有明確統計意義時畫平均線或零線。
- 玩家層級點位必須可聚焦、可點擊前往個人頁，並在 tooltip 顯示姓名、隊伍、樣本數、X／Y 精確值與可靠度。
- 大量點位預設使用一致尺寸的圓點；只對選取或強調的球員顯示頭像，避免數百張圖片遮蔽資料。不得以點的面積暗示第三個變數，除非圖例明確說明。
- 圖下固定揭露年度、角色、合格門檻、有效樣本數、資料截止日及缺值排除數。
- 回歸線不是預設結論。只有樣本與變異足夠時才顯示，並同時揭露斜率、R²、區間、樣本數及「相關不等於因果」提示。
- 色彩必須有文字或形狀的第二重編碼；tooltip、鍵盤焦點與圖例不可只靠 hover。
- 桌面圖繪圖區建議至少 720×440 px；窄螢幕保持至少 320 px 高並允許圖例換行，不縮成不可辨識的小圖。

## Slice 3 tag 檢視契約

Slice 3 必須同時產出兩種可排序表格：

1. 玩家 tag roster：年度、頭像、姓名、隊伍、角色、3–4 個 tag、各 tag membership probability、可靠度、有效樣本數與未指派原因。
2. Tag distribution：年度、角色、tag、合格人數、合格母體占比、有效樣本數、跨年保留率、主要共現 tag 及不平衡警示。

不要求所有 tag 人數相同，因為真實球員型態本來可能不均。下列只觸發人工檢查，不會自動判定模型失敗：單一年度／角色的 tag 少於 30 人或低於合格母體 2%、單一 tag 超過 60%，或未指派率超過 20%。檢查時還要區分真實稀有型態、切分過細、低樣本與特徵缺漏。

## 實作順序

1. 新的 archetype 頁面從第一版就遵守本契約。
2. 共用 `DataTable` 作為一般表格基準；特殊研究表格若不使用它，仍要達到相同互動與可及性。
3. 既有頁面只在後續明確的 UI migration Slice 中調整；每次修改都要跑 Nuxt typecheck、UTF-8 檢查及受影響頁面的互動檢查。
