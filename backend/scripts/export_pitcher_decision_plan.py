"""Export the Lab planning snapshot and canonical document from the project tracker."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    tracker = json.loads((ROOT / "docs/PROJECT_TRACKER.json").read_text(encoding="utf-8"))
    project = next(p for p in tracker["projects"] if p["id"] == "pitcher-decision-support")
    seen: set[str] = set()
    phases = {p["id"] for p in project["phases"]}
    for item in project["slices"]:
        if item["id"] in seen or item["phase"] not in phases:
            raise ValueError(f"Invalid slice: {item['id']}")
        if not set(item["depends_on"]).issubset(seen):
            raise ValueError(f"Unresolved or forward dependency: {item['id']}")
        seen.add(item["id"])
    audit_path = ROOT / "data/research/decision_support_audit_20261112/coverage_report.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    coverage = []
    for row in audit["years"]:
        li = next(v for v in audit["li_proxy_coverage"] if v["year"] == row["year"])
        n = row["coverage"]["pitches"]
        coverage.append({
            "year": row["year"], "pitches": n, "pa": row["pa"]["observed_pas"],
            "changes": row["changes"]["observed_pitcher_changes"],
            "wpa": 100 * row["pa"]["wpa_available"] / row["pa"]["observed_pas"],
            "re24": 100 * row["pa"]["source_re24_all_pitch_deltas_present"] / row["pa"]["observed_pas"],
            "stuff": 100 * row["coverage"]["stuff_cached"] / n,
            "location": 100 * row["coverage"]["location_cached"] / n,
            "liSupported": 100 * li["reference_state_n_ge_30"] / li["pas"],
            "quality": row["stamina"]["quality"].get("eligible"),
            "physical": row["stamina"]["physical"].get("eligible"),
            "command": row["stamina"]["command"].get("eligible"),
        })
    source_audit_path = ROOT / "data/sample/petehub_pitcher_decision_slice1_audit_v1.json"
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8")) if source_audit_path.exists() else None
    stages={}
    for stage in [2,3,4,5]:
        path=ROOT/f"data/sample/petehub_pitcher_decision_slice{stage}_v1.json"
        if path.exists():stages[stage]=json.loads(path.read_text(encoding='utf-8'))
    foundation=None
    if len(stages)==4:
        foundation={"updatedAt":"2026-11-14","repairs":[{k:g[k] for k in ['year','game_pk','before_rows','after_rows']} for g in stages[2]['games']],
            "ledger":{k:stages[3][k] for k in ['games','events','plays','appearances','physical_pitches','zero_pitch_appearances','unpriced_wpa_plays']},
            "workload":stages[4],"candidates":stages[5],"years":[],"individualRankingAllowed":False}
        for row in stages[3]['years']:
            candidate=next(v for v in stages[5]['years'] if v['year']==row['year'])
            foundation['years'].append({'year':row['year'],'pitches':row['counts']['physical_pitches'],
                'plays':row['rows']['plays'],'appearances':row['rows']['appearances'],
                'zeroPitchAppearances':row['counts']['zero_pitch_appearances'],'withCandidates':candidate['with_nominal_candidates'],
                'candidateProfiles':candidate['candidate_profiles']})
    temporal_stages={}
    for stage in range(6,11):
        path=ROOT/f'data/sample/petehub_pitcher_decision_slice{stage}_v1.json'
        if path.exists():temporal_stages[stage]=json.loads(path.read_text(encoding='utf-8'))
    temporal=None
    if len(temporal_stages)==5:
        temporal={'updatedAt':'2026-11-14','version':temporal_stages[6]['version'],'protocolHash':temporal_stages[6]['protocol_sha256'],
            'folds':temporal_stages[6]['folds'],'researchMethod':temporal_stages[7]['method'],'years':[],
            'plusValidation':temporal_stages[7]['models'][-1].get('validation_2024'),
            'weValidation':temporal_stages[10]['models'][-1].get('validation_2024'),
            'stateValidation':[m for stage in [8,9] for m in temporal_stages[stage]['models'] if m['cutoff']=='2024-01-01'],
            'formalReplacement':False,'individualRankingAllowed':False,'compositeEnergyAvailable':False,
            'minimumPrefix':{'SP':temporal_stages[8]['minimum_prefix'],'RP':temporal_stages[9]['minimum_prefix']}}
        for row in temporal_stages[7]['years']:
            sp=next(v for v in temporal_stages[8]['years'] if v['year']==row['year'])
            rp=next(v for v in temporal_stages[9]['years'] if v['year']==row['year'])
            context=next(v for v in temporal_stages[10]['years'] if v['year']==row['year'])
            boundary=next(v for v in temporal_stages[8]['decision_coverage_all_roles'] if v['year']==row['year'])
            temporal['years'].append({**row,'spAppearances':sp['eligible_appearances'],'rpAppearances':rp['eligible_appearances'],
                'context':context,'decisionStates':boundary})
    snapshot = {"project": project, "auditDate": "2026-11-12", "coverage": coverage, "sourceAudit": source_audit,"dataFoundation":foundation,'temporalResearch':temporal}
    destination = ROOT / "frontend/data/pitcherDecisionPlan.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 投手決策與預警研究", "", f"更新：{project['updated_at']}", "",
             "本文件由 PROJECT_TRACKER.json 產生；請更新權威 JSON 後執行 backend/scripts/export_pitcher_decision_plan.py。",
             "", project["summary"], "", f"入口：`{project['route']}`", "", "## 範圍與研究約束", ""]
    lines.extend(f"- {g}" for g in project["guardrails"])
    lines.extend(["", "## 評價定義", "",
                  "xWPA：固定行動與後續策略下，評估終點的預期己方勝率減當前勝率；以百分點呈現。",
                  "xRE24：當前 RE 減去預期期間失分與終點剩餘 RE，限定當前半局、守方越高越好。",
                  "ΔxWPA／ΔxRE24：替代選項減續投，需相同終點與後續策略；不是實際結果的直接因果歸屬。",
                  "", "## 時間切分", ""])
    lines.extend(f"- {e['years']}／{e['role']}：{e['detail']}" for e in project["experiment"])
    for phase in project["phases"]:
        lines.extend(["", f"## {phase['title']}", "", phase["description"]])
        for item in project["slices"]:
            if item["phase"] != phase["id"]:
                continue
            lines.extend(["", f"### {item['label']}", "", f"- 狀態：{item['status']}",
                          f"- 依賴：{', '.join(item['depends_on']) or '無'}", f"- 產出：{item['deliverable']}",
                          f"- 驗證：{item['verification']}", f"- 完成條件：{item['acceptance']}"])
            if item.get("evidence"):
                lines.append(f"- 證據：`{item['evidence']}`")
    if source_audit:
        lines.extend(["", "## Slice 1 官方賽程與事件核對結果（2026-11-12 歷史快照）", "",
                      "所有本機原始 DB 唯讀；新取六份公開賽程，沿用既有 14,577 場官方 feed；本批沒有補投球或重訓。", "",
                      "| 年份 | 已完成賽程 | 本機 game IDs | 缺場 | feed 快照 | 實投鍵差異 | 官方換投事件 |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for row in source_audit["years"]:
            lines.append(f"| {row['year']} | {row['completedGames']} | {row['localGames']} | {row['missingGames']} | {row['cachedFeeds']} | {row['missingPitchKeys']} | {row['officialPitchingSubstitutions']} |")
        lines.extend(["", "2021／2024／2026 各一場 Cancelled 已排除，不列為缺場。缺少 game ID 與整日漏抓均為零，仍有以下逐球差異：", ""])
        for row in source_audit["pitch_backfill_queue"]:
            lines.append(f"- {row['date']}／{row['game_pk']}：本機 {row['local_pitch_rows']} 球、feed {row['official_pitch_events']} 顆實投，{row['missing_official_pitch_keys']} 個鍵待查；{row['classification']}。")
        totals = source_audit["totals"]
        lines.extend(["", f"另有 {totals['unmatchedLocalKeys']:,} 個本機鍵與 feed 編號事件不對應，包含自動球與編號語意差異；不能全當作缺球或直接刪除。",
                      f"{totals['completedPlaysWithoutLocalRows']} 個官方完成 play 沒有本機投球列；{totals['localPlaysWithoutTerminal']} 個本機序列沒有終結事件，留待事件帳本核對。",
                      "三場最後比分差異為再見 balk，另外一場是 2026 截斷；WPA 終局須使用官方完整事件。",
                      "完整逐場清單、逐日清單、feed SHA 與來源 URL 在 data/research/decision_support_slice1_20261112/；小型版本化證據在 data/sample/petehub_pitcher_decision_slice1_audit_v1.json。",
                      "下一批僅針對兩個 game IDs 核對／補抓 Statcast；官方 feed 新增下載估量為零；不在 Slice 1 執行修復。"])
    if foundation:
        lines.extend(["", "## Slice 2–5 資料層交付（2026-11-14）", "",
            "### Slice 2 精準修復", ""])
        for game in foundation['repairs']:
            lines.append(f"- {game['year']}／{game['game_pk']}：{game['before_rows']} → {game['after_rows']} 筆；保留原始備份、Savant 公開 CSV 與 SHA，其他比賽指紋不變，CSV 與來源 meta 同步。")
        lines.extend(["", "### Slice 3 事件與結果", "",
            f"14,577 場、{foundation['ledger']['events']:,} 個官方事件、{foundation['ledger']['physical_pitches']:,} 顆實投、{foundation['ledger']['plays']:,} 個 play、{foundation['ledger']['appearances']:,} 個登板。",
            "官方 event key=game:atBat:eventIndex；play key=game:atBat；登板依實際進退場建立。Statcast pitch_number 與官方 eventIndex 不能直接互換，時鐘與來源修訂的逐球對位仍需品質標記。",
            "結果只存 play 表一次，事件與決策表不複製整個 PA 的 WPA。零球、打席中換投、代跑、繼承跑者、再見及七局規則均保留；未知壘包與來源時鐘異常不強行填值。",
            f"尚有 {foundation['ledger']['unpriced_wpa_plays']} 個相鄰勝率邊界無法直接定價，保留 null，待 Slice 10 的 WE／RE 參考模型處理。", "",
            "### Slice 4 時間與負荷", "",
            "全隊／全角色以 MLBAM ID、UTC 事件時間累積，只使用 t'<t 的實投；1／3／7／14 日是 24／72／168／336 小時滾動窗，連續登板按紐約 session 起始日。",
            "同日多場不依 game ID 排序；>8h 中斷切成 session 是資料處理規則，不是生理恢復假設。角色與前次完整用球等資料只在觀測到退出或 8h 無實投後進入 closed history。",
            "2021 前角色、春訓、小聯盟、熱身與醫療未知；左截斷 14 日與來源時鐘異常有旗標，曾先發不自動加體力。", "",
            "### Slice 5 名義候選與信心", "",
            f"以完整官方 game-day 玩家名單建名義候選，並非用稍後真正登板的人定義選項。72 組指定日期 active-roster 覆核：{foundation['candidates']['probe_results'].get('dated_active_exact',0)} 組一致、{foundation['candidates']['probe_results'].get('dated_roster_conflict',0)} 組衝突。",
            "多數日期仍是未逐日驗證的官方比賽名單；衝突／不足、非法換投、已使用或被換下、位置切換不明者保留原因並拒絕列為名義可換人選。",
            "候選附嚴格過去 1／3／7／14 日用球、前次用球、休息、連續登板、同日登板及距離先發／長局數的歷史資訊。當日異動精確時間、停賽、熱身與身體狀態未確認，不以 active 或名義候選推定實際可用。",
            "所有個別排名 gate=CLOSED；此表是資料層，不是最佳換投或可直接用於因果評估的完整可用牛棚。", "",
            "資料：data/research/decision_support_pipeline_20261114/；小型證據：data/sample/petehub_pitcher_decision_slice2_v1.json 至 slice5_v1.json。",
            "執行：repair_pitcher_decision_sources.py（僅兩場）→ build_pitcher_decision_ledger.py --year YEAR → build_pitcher_decision_workload.py → build_pitcher_decision_candidates.py → finalize_pitcher_decision_foundation.py。",
            "本段為 Slice 2–5 的歷史交付紀錄；後續 Slice 6–10 研究模型另存，正式 Stamina／Plus／Performance State 保留。"])
    if temporal:
        lines.extend(['','## Slice 6–10 歷史特徵與參考模型（2026-11-14）','',
            f"凍結協定：`{temporal['protocolHash']}`；資料根目錄：`data/research/decision_support_temporal_20261114/`。",
            '','### 時間、模型與研究 Plus','',
            '2021 H1 暖機；2021 H2 使用截至 7 月 1 日資料、2022 使用截至 2021 年底、2023 使用截至 2022 年底；2024–2026 均凍結截至 2023 年底的模型。訓練標籤所屬比賽必須已在 cutoff 前結束。',
            '主要速球只取登板開始前已結束登板的 FF／SI／FC，至少 20 球；保留參考關閉時間與缺值。正式模型 metadata SHA 不變。',
            '研究 Location 以位置與情境預測投手正向 RE 變化；研究 Stuff 以物理特徵預測扣除位置／情境後的殘差。這是獨立研究方法，並非正式／FanGraphs 分數，也不是正式 marginal-context Stuff+ 的補值。',
            'RE 目標參考表來自各 fold 的過去資料，沒有把來源 delta_run_exp 或來源 home_win_exp 當作訓練目標。標準化為各自訓練參考中心 100、每個標準差 10 分；當年中位數不保證 100，110 不代表好 10%。',
            '','### Prefix 三訊號與牛棚','',
            'SP 前 20 球建立同球種基準、至少再觀測 15 球；RP 前 5 球、至少再觀測 5 球。同球種早段最低 SP 3／RP 2，支持的早段配球比重需達 80%；僅對有支援的配球比例計算，保留 coverage，不稱完整球種組合。',
            '每個 prefix 僅含當下已結束的投球；>8h 中斷重新建立基準。Quality 與 Command 分別衡量 Stuff／Location 相對角色預期路徑的殘差，Ridge 控制用球數、早段狀態、嚴格過去歷史及最近打席邊界負荷／休息／角色／PA-LI，再以 n/(n+20) 向角色預期收縮。',
            'Physical 用先前訓練資料的各測量欄位差異中心／尺度，衡量球速、轉速、位移、出手點、延伸等公開測量的穩定程度；至少 75% 已訓練欄位有支援，不是生理體能量測。',
            '三訊號各按過去殘差尺度呈現 100+，仍會受抽樣與收縮影響而有不同當年分布。reliability 是 n/(n+20) 收縮權重，不是校準後的正確機率。80% 區間只是近似抽樣區間，未涵蓋完整模型與基準選擇不確定性，尚無單調耗盡的電量或合成分數。先發評估範圍至 100 球、牛棚至 60 球，超出範圍的決策不沿用過期分數。',
            '候選另附決策前已結束登板的最後觀測狀態與歷史支持，絕不讀取本次登板前五球；這是歷史觀測，不是登板準備度預測。熱身／醫療未知，個別排名 gate 關閉。',
            '','### WE／RE／LI 與結果分離','',
            '中性 WE 使用局數、上下半、預定局數、分差、出局、壘包與球數；各訓練參考期按完整比賽結束時間切 80/20 做固定 Platt 校準，沒有用 2024 校準。RE 按 24 壘包出局狀態及延長賽制度分組，以過去資料部分收縮。',
            '研究 PA-LI 是過去完成打者轉移分布下，預期絕對 WE 變化除以凍結訓練參考平均；不是同年實際 WPA 平均，也不宣稱精確重製 FanGraphs LI。少樣本回退有標記，支持不足留缺值，不補成 1。',
            '七局、再見、終局與延長賽自動跑者規則有明確處理；來源不可靠或壘包未知不強行評分。中性 WE 沒有球隊強弱或換投效果。',
            'context_features 保存前置特徵，context_labels 另存模型參考下的實現 WPA／守方 RE24；這些標籤不是換投因果貢獻，原始來源 WPA 保留在既有 play 表。',
            '','### 覆蓋與驗證','',
            '| 年份 | 全部實投 | 研究 Stuff | 研究 Location | SP 有 prefix 登板 | RP 有 prefix 登板 | WE／RE／PA-LI 邊界 |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: |'])
        for r in temporal['years']:
            lines.append(f"| {r['year']} | {r['physical_pitches']:,} | {r['stuff_available']:,} | {r['location_available']:,} | {r['spAppearances']:,} | {r['rpAppearances']:,} | {r['context']['we']:,} |")
        lines.extend(['','2021 的 Plus／WE 暖機到 7 月，狀態模型另以 7–8 月暖機至 9 月；短登板與支援不足保留 unavailable。覆蓋不是預測有效性的證據。',
            f"2024 固定 WE Brier={temporal['weValidation']['brier']:.6f}、log loss={temporal['weValidation']['log_loss']:.6f}；常數主場勝率基準 Brier={temporal['weValidation']['constant_train_home_win_brier']:.6f}。校準箱與樣本數在 Slice 10 小型證據，觀測按比賽聚集，不能當成獨立打席。",
            f"2024 Plus 參考目標 RMSE：常數={temporal['plusValidation']['mean_rmse']:.6f}、位置／情境={temporal['plusValidation']['location_rmse']:.6f}、再加物理殘差={temporal['plusValidation']['location_plus_residual_stuff_rmse']:.6f}。物理殘差的增量很小，不能據此宣稱換投效益或晉升正式模型。",
            'SP／RP 與純用球數、近期負荷（用球數＋近七日用球＋休息）基準的 2024 prefix 路徑比較，以及重疊 prefix 的描述性持續度，保存在 Slice 8／9 證據；均不代表下一段預測或決策因果效果。2025／2026 僅評分與覆蓋，沒有檢視結果指標來選模型。',
            '','### 事件身分修正與重跑','',
            'Slice 6 逐球 actor 核對發現舊 parser 把部分代跑視為當下打者替換；已修正只倒推真正打者的替換鏈，僅改事件／決策 batter_id，保存原檔備份與逐欄修正清單。投手、時間、實投數、負荷、名義候選與模型輸入均未改；剩餘來源身分歧異另列，後續對戰模型必須排除或確認。',
            '重跑：freeze_decision_temporal_protocol.py → build_decision_temporal_observations.py --year YEAR（六年）→ --references → train_decision_temporal_plus.py → build_decision_temporal_context.py → build_decision_prefix_states.py → repair_decision_batter_identity.py → finalize_decision_temporal_research.py → export_pitcher_decision_plan.py → sync_project_tracker.py。',
            '新研究結果未替代正式模型；此批沒有訓練 xWPA／xRE24 行動模型、沒有電池條／In game 同步與換投燈號。Slice 11 以後仍待使用者指示；畫面驗收由使用者執行。'])
    lines.extend(["", "## 現有盤點與後續驗證", "",
                  "data/research/decision_support_audit_20261112/ 保存觀測資料與來源限制；資料涵蓋不等於嚴格時點可用。",
                  "研究設計細節：data/research/decision_support_audit_20261112/research_notes.md。",
                  "頁面只展示 build-time 規劃快照，不新增 API、不觸發下載／訓練／預警；UI 驗收由使用者本人執行。", ""])
    (ROOT / project["document"]).write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(project['slices'])} slices and {len(coverage)} audit years.")


if __name__ == "__main__":
    main()
