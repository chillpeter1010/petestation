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
    sample_path = ROOT / "data/sample/petehub_pitcher_decision_slice11_v1.json"
    decision_sample = None
    if sample_path.exists():
        evidence = json.loads(sample_path.read_text(encoding="utf-8"))
        decision_sample = []
        for year in evidence["years"]:
            actions = {(r["role"], r["observed_action"]): r["n"] for r in year["exploration"]}
            decision_sample.append({
                "year": year["year"], "all": year["raw_boundaries"], "included": year["included"],
                "spContinue": actions.get(("SP", "continue"), 0), "spChange": actions.get(("SP", "change"), 0),
                "rpContinue": actions.get(("RP", "continue"), 0), "rpChange": actions.get(("RP", "change"), 0),
                "halfWpa": sum(r["n_half_wpa"] for r in year["exploration"]),
            })
    preparation_paths = {stage: ROOT / f"data/sample/petehub_pitcher_decision_slice12_{stage}_v1.json" for stage in range(1, 5)}
    preparation = None
    if all(path.exists() for path in preparation_paths.values()):
        stages = {stage: json.loads(path.read_text("utf-8")) for stage, path in preparation_paths.items()}
        preparation = {"version": "decision_preparation_v1", "updatedAt": "2026-11-18", "years": [],
                       "optionalBackfill": stages[2]["source_probe"],
                       "limitations": ["Game-listed handedness can be revised by the source.",
                                       "Switch-hitter expected stand assumes the opposite side to the option pitcher.",
                                       "Own ability rates are raw frequencies; fitted pooling is deferred to 12.6."]}
        for index, label in enumerate(stages[1]["years"]):
            signal = stages[4]["years"][index]
            preparation["years"].append({"year": label["year"], "decisions": label["rows"],
                "changedStarts": label["changed_starts"], "intentionalWalks": label["intentional_walks"],
                "organicPa": sum(row["organic_pa_eligible"] for row in label["targets"]),
                "transitionValid": sum(row["transition_valid"] for row in label["targets"]),
                **signal["coverage"]})
    baseline_paths = {stage: ROOT / f"data/sample/petehub_pitcher_decision_slice12_{stage}_v1.json" for stage in (5, 6, 7)}
    baseline = None
    if all(path.exists() for path in baseline_paths.values()):
        stages = {stage: json.loads(path.read_text("utf-8")) for stage, path in baseline_paths.items()}
        validation = stages[7]
        baseline = {"version": validation["version"], "retained": validation["retained_baseline"],
                    "protocolHash": validation["frozen_protocol_sha256"], "split": stages[6]["split"],
                    "flow": validation["flow"], "years": [], "models": [],
                    "testMetricsExamined": validation["test_outcome_metrics_examined"]}
        for row in stages[5]["years"]:
            baseline["years"].append({key: row[key] for key in ("year", "decisions", "candidate_rows",
                "any_candidate_ability", "all_candidate_ability", "any_candidate_state", "all_candidate_state")})
        for level, model in validation["selected"].items():
            baseline["models"].append({"level": level, "alpha": model["alpha"], "pooling": model["pooling"],
                "convergenceWarning": model["convergence_warning"],
                "validation": {key: model["validation"][key] for key in ("n", "log_loss", "brier", "ece")},
                "transitions": model["transitions"], "cluster": model["cluster_log_loss_delta"]})
    ablation_path = ROOT / 'data/sample/petehub_pitcher_decision_slice13_v1.json'
    ablation = None
    if ablation_path.exists():
        evidence = json.loads(ablation_path.read_text('utf-8'))
        ablation = {"version": evidence['version'], "coverage": evidence['coverage'],
            "winner": evidence['supported_subset_winner'], "cohorts": {}, "formalPromotion": False}
        for name, cohort in evidence['cohorts'].items():
            ablation['cohorts'][name] = {'trainingN': cohort['training_n'], 'validationN': cohort['validation_n'],
                'models': [{'name': key, 'logLoss': r['metrics']['log_loss'], 'brier': r['metrics']['brier'],
                    'incrementGate': r['increment_gate'], 'delta': r['cluster_delta'], 'subgroups': r['subgroups']}
                    for key, r in cohort['results'].items()]}
    action_path = ROOT / 'data/sample/petehub_pitcher_decision_slice14_v1.json'
    action = None
    if action_path.exists():
        evidence = json.loads(action_path.read_text('utf-8'))
        action = {key: evidence[key] for key in ('version', 'attempted_cases', 'modeled_cases', 'simulation_supported',
            'direction_counts', 'paths', 'bootstrap_models', 'maximum_completed_pa', 'examples')}
        action['games'] = evidence['timeline']['games']
    revision_path = ROOT / 'data/research/decision_role_observation_v2/completion_summary.json'
    revision = None
    if revision_path.exists():
        evidence = json.loads(revision_path.read_text('utf-8'))
        revision = {'version': evidence['version'], 'protocolHash': evidence['protocol_sha256'],
            'optionRows': sum(y['workload']['rows'] for y in evidence['years']),
            'streakAudit': {key: evidence['streak_audit'][key] for key in ('current_rp_rows', 'legacy_vs_repaired', 'entry_vs_physical_session_differences')},
            'years': [], 'baseline': [], 'risk': [], 'replicatedPanels': evidence['replicated_panels']}
        for year in evidence['years']:
            sp = next(row for row in year['roles'] if row['role'] == 'SP')
            rp = next(row for row in year['roles'] if row['role'] == 'RP')
            revision['years'].append({'year': year['year'], 'sp': sp, 'rp': rp,
                'recentProfiles': year['recent']['unique_profiles']})
        for level, model in evidence['baseline']['models'].items():
            revision['baseline'].append({'level': level, 'n': model['validation']['n'],
                'logLoss': model['validation']['log_loss'], 'brier': model['validation']['brier'],
                'delta': model['delta_vs_v1']})
        for row in evidence['risk_2024']:
            if 'models' not in row: continue
            revision['risk'].append({'role': row['role'], 'metric': row['metric'],
                'eligible': row['eligible_prefixes'], 'observed': row['observed_future10'],
                'unobserved': row['unobserved_or_measurement_insufficient'],
                'brierCount': row['models']['count_only']['brier'], 'brierState': row['models']['state_workload']['brier'],
                'logLoss': row['models']['state_workload']['log_loss'], 'auc': row['models']['state_workload']['auc']})
    matchup_path = ROOT / 'data/sample/petehub_pitcher_decision_matchup_revision_v2.json'
    matchup_revision = json.loads(matchup_path.read_text('utf-8')) if matchup_path.exists() else None
    patch_path = ROOT / 'data/sample/petehub_pitcher_decision_model_patch_v3.json'
    model_patch = json.loads(patch_path.read_text('utf-8')) if patch_path.exists() else None
    alert_path = ROOT / 'data/sample/petehub_pitcher_decision_alert_research_v1.json'
    alert_research = json.loads(alert_path.read_text('utf-8')) if alert_path.exists() else None
    lights_path = ROOT / 'data/sample/petehub_pitcher_decision_signal_lights_v2.json'
    if not lights_path.exists():lights_path = ROOT / 'data/sample/petehub_pitcher_decision_signal_lights_v1.json'
    signal_lights = json.loads(lights_path.read_text('utf-8')) if lights_path.exists() else None
    overlap_path=ROOT/'data/sample/petehub_pitcher_decision_overlap_v1.json'
    overlap=json.loads(overlap_path.read_text('utf-8')) if overlap_path.exists() else None
    overlap_revision_path=ROOT/'data/sample/petehub_pitcher_decision_overlap_revision_v1.json'
    overlap_revision=json.loads(overlap_revision_path.read_text('utf-8')) if overlap_revision_path.exists() else None
    rp_path=ROOT/'data/sample/petehub_pitcher_decision_rp_targets_v1.json'
    rp_targets=json.loads(rp_path.read_text('utf-8')) if rp_path.exists() else None
    entry_path=ROOT/'data/sample/petehub_pitcher_decision_entry_review_v1.json'
    entry_review=json.loads(entry_path.read_text('utf-8')) if entry_path.exists() else None
    pe_path=ROOT/'data/sample/petehub_pitcher_decision_pe_revision_v1.json'
    pe_revision=json.loads(pe_path.read_text('utf-8')) if pe_path.exists() else None
    exploration_path=ROOT/'data/sample/petehub_pitcher_decision_exploratory_v1.json'
    exploration=json.loads(exploration_path.read_text('utf-8')) if exploration_path.exists() else None
    snapshot = {"project": project, "auditDate": "2026-11-12", "coverage": coverage, "sourceAudit": source_audit,"dataFoundation":foundation,'temporalResearch':temporal,"decisionSample":decision_sample,"preparation":preparation,"baselineResearch":baseline,"signalAblation":ablation,"actionResearch":action,"roleObservationRevision":revision,"matchupRevision":matchup_revision,'modelPatchRevision':model_patch,'alertResearch':alert_research,'signalLights':signal_lights,'overlapResearch':overlap,'overlapRevision':overlap_revision}
    destination = ROOT / "frontend/data/pitcherDecisionPlan.json"
    snapshot['rpTargetResearch']=rp_targets
    snapshot['entryReview']=entry_review
    snapshot['peRevision']=pe_revision
    snapshot['exploratoryReplay']=exploration
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
            'Slices 6–10 的研究結果維持獨立版本；此批未訓練 xWPA／xRE24 行動模型。'])
    if decision_sample:
        lines.extend(["", "## Slice 11 回溯決策樣本與探索分析（2026-11-18）", "",
            "只納入雙方選項符合名義規則的例行賽打席邊界。起始登板、打席中或複合換人、已知強制事件、時間／身分不確定、缺少名義候選或實際替換不在名義集合，分別記錄排除原因。候選的熱身、健康、當日異動仍未知。",
            "以 `decision_id` 對齊：`decision_features_YEAR` 保存當時可知的局面／負荷／三訊號；`decision_candidates_YEAR` 保存名義候選與嚴格過去的歷史；`decision_labels_YEAR` 另存實際續投／換投、下一打席及半局結果；`decision_audit_YEAR` 保存完整分母與排除原因。半局 WPA 為守方同一半局起迄勝率差，另存剩餘失分。時間或來源不足保留缺值，標籤只觀測實際選擇。",
            "", "| 年份 | 全部邊界 | 納入 | SP 續投 | SP 換投 | RP 續投 | RP 換投 | 有半局 WPA |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for r in decision_sample:
            lines.append(f"| {r['year']} | {r['all']:,} | {r['included']:,} | {r['spContinue']:,} | {r['spChange']:,} | {r['rpContinue']:,} | {r['rpChange']:,} | {r['halfWpa']:,} |")
        lines.extend(["", "探索摘要提供各組用球數、PA-LI 與 Quality／Physical／Command 的均值及自身分母，並列下一打席與半局標籤覆蓋。兩種實際行動的情境分布不同；組間觀測結果不可直接作為換投效益。",
            "重跑：`python backend/scripts/build_pitcher_decision_sample.py`。離線產物在 `data/research/pitcher_decision_sample_v1/`。小型證據含 24 組年度×角色×行動摘要、排除分布與案例 ID。Slice 12 才開始轉移模型。"])
        lines.extend(["", "### Slice 12 開工評估", "",
            "一個邊界對應一個官方 play，鍵為 `game_pk:atBatIndex:boundary`。有首顆實投前換投時取第一個換投事件執行前，否則在首顆實投前取樣；無實投時取第一筆事件，最末備援的 play 開始時間不進研究樣本。邊界保留當時已發生事件所形成的局面、現任投手與候選；兩個行動都須合乎名義規則，且有合格候選。候選是否已熱身、具體傷勢及私下調度資訊未知。",
            "唯讀覆核六季 824,462 筆納入列：打席結果無缺，出局數、非終局壘包、比分缺失及進攻得分 0–4 的粗篩無違規。1,527 筆零球均為故意四壞；1,371 筆官方 play 開始狀態與決策快照不同（續投 1,361、換投 10），其中 794 筆為延長賽壘包差異。這些差異可能反映決策前已經發生的跑者事件。轉移標籤須從決策局面起算，先核對自動跑者、跑壘事件及終局，無法確認來源時從轉移基準分流並保留標記。",
            "舊初始覆蓋表的 Quality／Physical／Command 是補齊前的正式單場成績檔。研究 prefix 在六季均有覆蓋；納入列中 2021 年有三項 14,100／131,922，2024 年 77,973／138,080。缺樣本、暖機與超出模型支持維持缺值並區分原因，沿用基準對照組，另在同樣有特徵的樣本做消融。保留極端值，先查來源；稀有轉移用收縮或階層回退。標準化、必要的補值及正則化限訓練資料估計，依 2024 驗證選擇；2025 凍結測試，2026 回溯。",
            "可開始 Slice 12 的目標口徑與基準驗證。Slice 13 在同分母檢查增益，Slice 14 待前兩個階段完成才比較固定半局的預期價值。"])
    if preparation:
        lines.extend(["", "## Slices 12.1–12.4 資料準備交付（2026-11-18）", "",
            "版本化離線根目錄為 `data/research/decision_preparation_v1/`。保留 Slice 11 舊產物，新增 `boundary_review_YEAR`、`clean_labels_YEAR`、`decision_matchup_YEAR`、`player_ability_features_YEAR`、`signal_features_YEAR`、`prepared_features_YEAR` 及 `field_coverage_YEAR`。`ability_history.parquet` 與 `ability_references.parquet` 供後續現任／候選使用，候選完整整合屬 12.5。",
            "12.1 對官方事件核對決策起點，分別記錄自動跑者與其他決策前事件；故意四壞標記為獨立調度，打席／半局時間或狀態不可靠則保留原始列與缺值。研究標籤用既有凍結 WE／RE 重新從決策起點定價。",
            "12.2 逐欄 coverage 分母按年、SP/RP、續投／換投拆開；候選另用決策×候選分母。欄位字典、非空／有效支持／真零、暖機與超出模型範圍保留。2020 官方賽程與單場 Statcast 來源小樣本已保存 URL／UTC／SHA，完整更早年度回填仍為條件式工作。",
            "12.3 從已完成打席累計投打 K、BB、HBP、HR、單二三壘安打、其他出局及其他上壘結果；忽略故意四壞並保留結果類別規格。自身拆分 → 自身 All → 凍結訓練參考，附各自樣本數、歷史可用時間與回退狀態。能力參數、標準化與正則化的正式選擇留 12.6。",
            "手別取既有官方快照的 game-listed 欄位，來源可能事後修訂；只使用投打手別，不使用 currentAge 或現況成績。左右開弓預期站側採投手反側假設，原始 listed_bats 保留；此假設須在後續敏感度分析揭露。",
            "12.4 決策前同登板已完成投球的 Stuff／Location 累積均值、有效 n、模型與 cutoff 已接入；三項狀態沿既有分數、近似 80% 區間及收縮權重。原始缺值與支持旗標保留。",
            "", "| 年份 | 決策點 | 起點修正 | 一般打席有效 | 有 Stuff 摘要 | 有 Location 摘要 | Quality | Physical | Command |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for row in preparation["years"]:
            lines.append(f"| {row['year']} | {row['decisions']:,} | {row['changedStarts']:,} | {row['organicPa']:,} | {row['stuff']:,} | {row['location']:,} | {row['quality']:,} | {row['physical']:,} | {row['command']:,} |")
        lines.extend(["", "重跑依序使用 `build_decision_preparation.py source`、`probe`、`labels`、`history`、`ability`、`signals`、`coverage`、`finalize`；各年度 stage 可選 `--year`。產物 manifest 保存 SHA，12.1–12.4 的小型證據分別存 `data/sample/petehub_pitcher_decision_slice12_1_v1.json` 至 `slice12_4_v1.json`。此為資料準備交付紀錄；後續基準見下節。"])
    if baseline:
        lines.extend(["", "## Slices 12.5–12.7 候選契約與三層基準（2026-11-18）", "",
            "離線版本 `data/research/decision_baseline_v1/`；原始準備資料與正式模型保留。現任與名義候選統一為 `option_features_YEAR`，`observed_features_YEAR` 依實際接任投手對位，因此換投後的結果不會錯配到被換下投手。投手 ID 僅供 join，不是模型輸入。",
            "候選能力與負荷嚴格早於決策；狀態來自已結束登板，與現任本次 prefix 各有 scope。候選角色採此前觀測角色，未知時以 RP 參考回退並保留 role_known=false，不代表當日角色或準備度。逐欄非空數按年／角色／現任或候選保存；每個決策另列至少一位及全部候選有能力／三項狀態的分母。能力的完整值含自身與訓練參考回退，不表示完整個人歷史。熱身、醫療與當日精確異動未知，個別排名仍關閉。", "",
            "### 凍結協定與特徵", "",
            f"協定 SHA：`{baseline['protocolHash']}`。2021–2023 訓練，2024 選設定與診斷，2025 最終測試保留至 Slice 17；2026 回溯。2025／2026 只保存凍結預測，未檢視結果指標。",
            "局面基準：局數、上下半、預定局數、守方分差、出局、壘包及延長賽旗標。負荷層再加選項投手本場球數／面對打者數、近 1／3／7／14 日球數、休息、前次用球、連續登板、同日登板、歷史完整度及角色／現任旗標。對戰層再加投打九類結果歷史率、歷史 n、手別及回退狀態。Quality／Physical／Command 與 Plus 均不進本批三層基準，留 Slice 13 做同分母消融。",
            "數值中位數補值＋缺值指示與 StandardScaler、未知類別與 one-hot 均只 fit 訓練資料。L2 alpha 候選 0.0001／0.001；能力向訓練結果先驗收縮的強度候選 0／20。按比賽等總權重訓練。2024 log loss 選設定，0.0001 內優先較強正則化再較簡單收縮；只有 log loss 與 Brier 都改善才保留較複雜層。",
            "目標為下一個一般完成打席的 K／BB／HBP／HR／單二三壘安打／其他出局／其他上壘，以及聯合得分、終點出局與壘包。排除故意四壞、不可靠終點及跑者不守恆列；稀有轉移只以訓練資料向同出局／壘包／結果類別回退。再見情境排除非全壘打超過致勝分的轉移，未支持的類別機率質量另報，合法轉移重新正規化。", "",
            "| 年份 | 決策 | 候選列 | 至少一位有能力 | 全部有能力 | 至少一位有三狀態 | 全部有三狀態 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for row in baseline["years"]:
            lines.append("| " + " | ".join(f"{row[key]:,}" for key in ("year", "decisions", "candidate_rows", "any_candidate_ability", "all_candidate_ability", "any_candidate_state", "all_candidate_state")) + " |")
        lines.extend(["", "| 年份 | 可靠一般打席 | 跑者守恆排除 | 最終模型分母 |",
                      "| --- | ---: | ---: | ---: |"])
        for row in baseline["flow"]:
            lines.append(f"| {row['year']} | {row['before']:,} | {row['runner_conservation_excluded']:,} | {row['after']:,} |")
        lines.extend(["", "### 相同分母的 2024 驗證", "",
            "| 層級 | n | PA log loss | 多類 Brier | 聯合轉移 log loss | WPA RMSE（勝率單位） | RE24 RMSE（分） |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for row in baseline["models"]:
            v, t = row["validation"], row["transitions"]
            lines.append(f"| {row['level']} | {v['n']:,} | {v['log_loss']:.6f} | {v['brier']:.6f} | {t['joint_log_loss']:.6f} | {t['wpa_rmse']:.6f} | {t['re24_rmse']:.6f} |")
        lines.extend(["", f"保留基準：`{baseline['retained']}`。完整候選設定、收斂旗標、逐類與 top-label 校準箱、按比賽群聚的 100 次 paired bootstrap 差異區間及樣本流向保存於 `validation.json`。2024 同時作設定選擇及診斷，群聚區間不是獨立測試證據。",
            "交付版為 v1.2；兩次中止的實驗及協定分別保存在 attempt1_nullable_category_failure／attempt2_terminal_constraint_revision，修正 nullable boolean 類別編碼與再見限制。協定列出原版本 SHA，時間切分、特徵、目標與選模規則未變。",
            "WPA／RE24 誤差只評估下一打席，以同一凍結 WE／RE 定價；不是 Slice 14 固定半局策略的 xWPA／xRE24，也不是換投因果效益。校準不足、稀有轉移回退及冷啟動仍須揭露。正式晉升與個別排名維持關閉。",
            "雖然投打能力層改善分類與聯合轉移指標，WPA／RE24 誤差改善仍很小，不能據此推出可靠的換投價值差。Slice 13 應保留三層基準，對三項狀態與 Plus 做相同支持樣本的增益及消融。",
            "重跑：`python backend/scripts/build_decision_baselines.py candidates` → `freeze` → `train` → `score` → `finalize`。已凍結協定若輸入或實作改變會拒絕訓練，須明確另開版本。小型證據為 `slice12_5_v1.json` 至 `slice12_7_v1.json`，manifest 記錄產物 SHA。此為 Slice 12 交付紀錄，後續增益與半局研究見下節；Lab 摘要由使用者人工驗收，不代為開瀏覽器。"])
    if ablation:
        lines.extend(['', '## Slice 13：狀態指標增益與消融（2026-11-18）', '',
            '研究版本 `decision_ablation_v1`，原 Slice 12 協定與模型保留。實際續投取當次 prefix；實際換投取接任者此前已結束登板的狀態／同 fold Plus，不使用被換下投手的訊號。所有來源時間嚴格早於決策。',
            '完整支持 cohort 的十個設定使用完全相同的訓練／2024 驗證分母；另作全分母 missing-aware baseline/all。每個對照均控制相同的訊號年齡、n、可靠度、scope 與缺值旗標，避免把 coverage 本身誤稱為分數增益。標準化與補值只 fit 2021–2023；固定沿用 L2 alpha=.001、能力收縮20。',
            '增益門檻：log loss 按比賽群聚100次區間上界<0、Brier改善、至少500打席的角色／實際行動分群不得惡化超過0.005，且無迭代上限警告。2024 為設定診斷，非新的獨立測試。', '',
            '| 分母 | 特徵組合 | 訓練 n | 驗證 n | log loss | Brier | 相對支持基準增益門檻 |',
            '| --- | --- | ---: | ---: | ---: | ---: | --- |'])
        for name, cohort in ablation['cohorts'].items():
            for model in cohort['models']:
                lines.append(f"| {name} | {model['name']} | {cohort['trainingN']:,} | {cohort['validationN']:,} | {model['logLoss']:.6f} | {model['brier']:.6f} | {'通過' if model['incrementGate'] else '未通過'} |")
        lines.extend(['', f"有支持子樣本保留 `{ablation['winner']}`。Quality／Physical／Command 單獨及三項合併未通過增益門檻；加入 all 的增益不能歸給三項狀態，需連同 Plus-only 與 leave-one-out 解讀。",
            '全分母 all 對自己的相同支持基準有小幅改善，但相較 Slice12 原始 matchup 的 Brier 未改善；不以單一 log loss 改善宣稱晉升。Slice14 沿用覆蓋完整的 Slice12 matchup；假想後續球質／三訊號的演化沒有被觀測，不能凍結當成準備度。',
            '離線根目錄 `data/research/decision_ablation_v1/`；features → freeze → train → score → finalize 使用 `build_decision_ablation.py`。2025／2026 僅輸出凍結機率，未查結果指標。'])
    if action:
        lines.extend(['', '## Slice 14：固定半局角色替代池與單場時間軸（2026-11-18）', '',
            f"研究版本 `{action['version']}`；抽樣 {action['attempted_cases']} 個2024邊界，名義角色／歷史支持後計算 {action['modeled_cases']} 個，其中 {action['simulation_supported']} 個所有抽樣路徑無截尾或球數範圍外推。分層樣本加兩場固定 hash 選取範例，不是聯盟效果估計。",
            '兩方案為現任續投至半局結束，以及從有過去RP角色、至少30個自身打席、已知手別／休息與完整14日歷史的名義池均勻選一人投至半局結束；至少兩個替代者。僅納入原名義合法、0球0好球邊界。投到局末符合最低打者與局末例外；熱身、醫療及精確異動仍未知，這不表示可實際調度。',
            '第一個打者使用當時投打資料；後續打者使用截至2023年底的聯盟打者池，同一身分抽樣在兩方案配對，再依投手手別取該打者歷史。沒有讀取實際後續打序、投球或結果。用球依訓練期角色×結果類別的實投分布累加，面對打者+1；新投手完成第一打席後轉為現任，之後不再換人。',
            '主要終點是當前半局結束或再見；xWPA 為該終點中性後續策略WE相對當前守方WE的差，xRE24=當前RE−期間失分。下一PA僅供原基準解釋。長期牛棚成本、實際後續打序、故意四壞策略及狀態演化尚未建模。',
            f"每方案 {action['paths']} 條共同亂數路徑；提供差值的Monte Carlo 95%誤差範圍，以及 {action['bootstrap_models']} 次按比賽重抽樣分類器的中央80%描述性範圍。後者固定前處理、轉移、WE與RE，不是完整模型／隱藏混雜的不確定區間。未收斂、外推或截尾必須揭露；所有 recommendation_allowed=false、individual_ranking_allowed=false。",
            '兩場單場WE走勢參考另一專案 GameWinProbabilityChart.tsx 的50%中線、主客勝率與逐打席查看結構；只讀來源碼並保存SHA，沒有沿用CPBL勝率表。新圖用有界直線連模型點，缺可靠局面留斷線；官方換投在上軌，決策前研究比較點在下軌，事後WPA／結果明確標為事後資料。',
            'In game未接線：後續以year/game_pk、pitcher_id、decision_id與官方PA/event_id定位；pitch_uid須經既有官方／Statcast驗證映射，不能把eventIndex當pitch_number。正式個別建議需經Slices15–18及20門檻，單場同步在19；本批沒有開始這些Slice。',
            '重跑：`build_decision_action_values.py prepare` → `freeze` → `bootstrap` → `simulate`，再 `export_decision_action_research.py traces` → `finalize`。根目錄 `data/research/decision_action_values_v1/`，小型證據 `data/sample/petehub_pitcher_decision_slice14_v1.json`。前端新圖與操作待使用者人工驗收。'])
    if revision:
        lines.extend(['', '## Slices 13.1–13.4：負荷修訂、狀態觀測與條件下滑研究', '',
            f"版本 `{revision['version']}`，協定 SHA `{revision['protocolHash']}`。原v1產物及先前兩輪協定／初步模型另存；此節記錄13.1–13.4交付當時狀態，後續修訂見下一節。",
            f"13.1：{revision['optionRows']:,}個現任／候選連結已重建負荷，滾動窗為24／72／120／168／336小時，嚴格取投球完成時間<t。窗口不完整或時鐘不可靠保留缺值及觀測計數，不以0冒充完整歷史；來源4,270,416顆實投有2筆結束時間異常另標。",
            f"現任RP原模型streak與修訂值不同 {revision['streakAudit']['legacy_vs_repaired']:,}／{revision['streakAudit']['current_rp_rows']:,}列；另有{revision['streakAudit']['entry_vs_physical_session_differences']}列與舊current-session欄不同，已逐列由登板日／實投session日重建核對。核心streak是實際／假定進場時點之前的連續紐約登板日；決策日的投球日streak、登板日streak、同日其他登板、進場前休息、本場idle及本場／跨場用球各自保存。零球進場計登板不計球，復賽session不增加季內登板序號。",
            '修訂adapter保留原三層白名單，固定原L2及能力收縮設定；五日窗與新增狀態不提前做13.6選模。2021–2023訓練、2024同分母驗證；2025／2026僅保存凍結機率。', '',
            '| 修訂基準 | 2024 n | log loss | Brier |', '| --- | ---: | ---: | ---: |'])
        for model in revision['baseline']:
            lines.append(f"| {model['level']} | {model['n']:,} | {model['logLoss']:.6f} | {model['brier']:.6f} |")
        lines.extend(['', '13.2：current_features以原決策前現任為actor，pa_features以實際單一投球actor首球前為anchor，兩者不可混用。保存prefix水準、最近十球、同球種早段固定配比差／斜率、進場前已關閉同球種個人參考、已完成PA的K／BB及原始三項狀態／區間／支持。SP35／RP10球暖機及原狀態100／60上限、>8h重啟基準均保留；Location為位置價值代理。',
            '13.3：recent_history保存已關閉同角色登板；recent_links連到去重recent_profiles，含last1／3／5及近72／120小時已可用摘要。保留觀測時間、資料年齡、有效登板數與原始有效球數；跨模型版本的Plus／三項狀態不混平均。近期均值的中央80%範圍只是n>=2的描述性近似，不含序列或完整模型不確定性。未近期出賽不等於狀態正常，也不表示已熱身。', '',
            '### 13.4：全體曲線、個人部分收縮與下一十球風險', '',
            '2021–2023建立條件參考，2024驗證。區分每三名BF、20球區間、實際對該打序位置第幾次、對該打者第幾次；官方快照slot只用於當前已觀測打者，不讀未來打線。零球IBB有交手次數但沒有投球曝光。曲線控制球數／BF、投打身分與過去打者能力、手別、日期、局面及反應期球種配比；反應期配比只作描述調整，禁止進未來預測。',
            '支持門檻為每區間至少200PA／50登板／30投手，以200次比賽×投手Poisson重抽樣建立各角色×指標×軸內同時95%帶。需達預先定義實務幅度、連續兩個支持區間，且訓練選出的同一區段在2024重現；跨指標／軸仍為探索性比較。個人曲線僅用歷史、按登板數向角色曲線收縮，少於10登板的個人區間不發布。',
            f"本次重現門檻通過的面板數：{len(revision['replicatedPanels'])}。這不表示不存在任何下降；在本次控制、支持與幅度門檻下，尚不能給通用換投球數／輪次或已驗證個人切點。保留下場選擇、倖存及未觀測續投限制。", '',
            '| 角色／目標 | 可觀測未來10球／合格prefix | 球數基準Brier | 狀態＋負荷Brier | AUC |',
            '| --- | ---: | ---: | ---: | ---: |'])
        for row in revision['risk']:
            lines.append(f"| {row['role']}／{row['metric']} | {row['observed']:,}／{row['eligible']:,} | {row['brierCount']:.6f} | {row['brierState']:.6f} | {row['auc']:.4f} |")
        lines.extend(['', '風險目標為未來10顆實投均值較前10顆下降至少5個研究Plus點，兩窗各至少8筆有效測量；不是低於個人基準、醫療疲勞或失分風險，包含抽樣波動及回歸均值。L2模型按時間前推，校準只用各訓練窗末20%比賽；未來球不足列為設限／測量不足，不能填成沒有下降。上述結果只適用於實際可觀測續投，負荷獨立增益仍須13.6，換投價值仍須14.1後續驗證。',
            '研究資料及圖：data/research/decision_role_observation_v2/，population_curve_points.csv、decline_SP_2024.svg、decline_RP_2024.svg。小型證據為slice13_1_v2至slice13_4_v2；manifest含初輪保留檔的SHA。重跑依序：build_decision_role_observations.py sources／lineups／references／workload／pa／prefix／recent_history／recent，build_decision_role_models.py adapter／cohort／freeze／baselines／curves／risks／risk_score，export_decision_role_revision.py，最後export_pitcher_decision_plan.py及sync_project_tracker.py。畫面與操作由使用者驗收。'])
    if matchup_revision:
        latest = matchup_revision
        lines.extend(['', '## Slices 13.5、13.6及14.1：打者輪廓、增益及半局重跑', '',
            '本批完成後為30/39，止於14.1；14.2去重／官方事件對應與15均未開始。所有新版本與原v1／13.1–13.4凍結產物並存。', '',
            '### 13.5 打者前序出棒、掌握與粗球路相性', '',
            '六季824,462個實際actor請求，僅使用決策前已完成PA。分開本場打者last1／2／3、同投手last3、其他投手last3、全隊對該投手last3及歷史BvP／類型。收到球種占比、球種出棒率與出棒組成分開；接觸／揮空／界外以出棒為分母，EV及HardHit只用有效場內擊球。零球IBB占PA窗但不虛造球數。',
            '粗球路類型取前3次同觀測角色已閉合登板，至少50球，手別×主導球系（>=50%，否則mixed）×速球球速（<90、90–95、95+mph）。這是預先固定的廣義分類，不是已證實最優相性或另一專案的同季整季tag。BvP以20PA收縮到同打者類型率，類型以50PA收縮到過去打者手別能力；family行為以有效分母20（EV10個BBE）回退嚴格過去手別／球系參考，保留原n與回退。110個多打者／官方實投身分衝突的完成PA已排除歷史，原初輪保留；描述分析另以乾淨PA交集凍結familiarity_identity_clean_v2，兩個無有效描述目標的cohort列排除，預測特徵不變。',
            f"接觸／揮空／EV對交手次數及此前實投曝光，共{latest['associationPanels']}個SP／RP條件面板。訓練2021–2023，2024有支持且面板內同時95%區間排除0的變化區段{latest['associationSupportedChanges2024']}個；控制球數、手別、投打身分、過去能力及反應期球數／位置／Plus／球種配比。反應期控制僅作描述調整，不進預測；保留者選擇、多面板探索與心理鎖定／因果限制。", '',
            '### 13.6 同分母角色消融與診斷選擇', '',
            '實際投球actor依當時現任角色／接任RP分層，各25設定、訓練2021–2023／2024驗證，所有設定共用各角色的完整missing-aware分母；另有完整Plus及三狀態支持下baseline/all敏感度。原option_role仍是過去觀測角色，2024有285個接任者過去為SP，forecast_role改RP，跨角色的狀態／Plus及近期窗先驗不混入。前兩輪部分訓練／資料／源碼／協定保存，修正角色與來源後重跑。不是只在有未來十球者訓練；下一PA是共同目標，被換下者不拿接任結果當續投。',
            '共同基準為修訂局面＋投打能力＋原負荷，所有設定共享n／年齡／scope等支持控制。逐組加5日負荷與季內序號、Plus、當場／近期觀測、BF／輪次代理／過去模型風險、打者前序及BvP／類型／交互項。補值、標準化、one-hot僅fit訓練，L2 alpha=.001與能力收縮20固定；沒有依2024重調參數。',
            'leave-out隨來源移除risk／交互項等派生資訊；without_type的BvP先驗直接回過去打者能力。純72／120小時、連投及季內序號對照以load_extended為基準，不含後續複合risk。這些是條件預測消融，不是疲勞因果。原決策risk另用當時可用前推模型重算，不能把較晚的PA首球前分數接回較早決策；候選entry risk缺值。',
            '200次比賽×投手配對Poisson重抽樣，對每角色全部非基準LL對照建立同時97.5%帶，再校正兩角色；通過需上界<0、Brier改善、>=500PA的current／incoming分群無LL惡化>.005及無收斂警告。只從預定累加設定選擇，all另須完整支持敏感度改善；未通過保留基準。2024為診斷選模，2025最終獨立測試仍封存。', '',
            '| 角色 | 訓練n | 2024 n | 選擇 | 基準LL | 選定LL | 基準Brier | 選定Brier |',
            '| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |'])
        for role in latest['roles']:
            lines.append(f"| {role['role']} | {role['trainingN']:,} | {role['validationN']:,} | {role['selected']} | {role['baselineLL']:.6f} | {role['selectedLL']:.6f} | {role['baselineBrier']:.6f} | {role['selectedBrier']:.6f} |")
        revised_action = latest['action']
        lines.extend(['', '### 14.1 原484個固定半局比較重跑', '',
            f"全部{revised_action['modeledCases']}個原比較點保留，角色池有{revised_action['supported']}個符合全模擬支持；另有{revised_action['conditionalComparisons']}個手別／有過去支持粗類型條件池比較。每池至少兩個候選，池內均勻抽人，不做最優池挑選或個人排名。",
            '第一PA使用13.6通過的角色設定；選擇baseline時採13.1修訂global matchup。後續全部回修訂global matchup，明示未知狀態／球路／打者掌握的未來演化，沒有把目前prefix或候選前次狀態凍結投到局末。兩方案投至相同半局終點／再見，完整九類結果接原凍結合法轉移與WE／RE。',
            '首位打者當時已知；存檔事後battingOrder缺乏獨立公開時點證明，484個均回原2023年底聯盟打者池配對抽樣，不讀實際後續打序／代打。官方game名單、active名單時點、名義法定合法、熱身、醫療與人工確認可用性分列；active／熱身／醫療／人工確認不足，不推出個別可調度。',
            f"每方案{revised_action['paths']}路徑，{revised_action['bootstrapModels']}次共同比賽重抽樣分類器；MC95與中央80模型範圍分開，前處理／轉移／WE／RE固定。外推／截尾阻擋研究方向，稀有轉移缺失機率另報。比較固定研究樣本，條件池多次探索不構成最優調度驗證。", '',
            '| 角色池研究方向 | 原v1 | 修訂v2 |', '| --- | ---: | ---: |'])
        labels={'pool_higher':'替代池較高','continue_higher':'續投較高','uncertain_or_unsupported':'不明或支持不足'}
        for row in revised_action['directions']:
            lines.append(f"| {labels[row['direction']]} | {row['old']} | {row['new']} |")
        lines.extend(['', '逐點方向交叉表、xWPA／xRE24差值與區間保存old_new_comparison.parquet。新增預計用球／BF與替代後剩餘名義RP數；滾動負荷用決策時鐘固定並累加模擬新球，無投球時間長度模型，不虛造完整長期預算或加扣WPA。正式推薦／個別排名皆關閉，14.2去重／官方事件匹配未開始。',
            '重跑：build_decision_batter_matchups.py sources → histories → features → freeze → associations；audit_decision_familiarity.py → build_decision_batter_matchups.py finalize；build_decision_role_ablation.py features → freeze → train → score → finalize（亦可train --role SP／RP後combine）；build_decision_action_revision.py prepare → freeze → bootstrap → simulate → finalize；export_decision_matchup_revision.py → export_pitcher_decision_plan.py → sync_project_tracker.py。各版本manifest保存SHA，2025／2026只保存凍結預測，未讀結果指標。新摘要頁由使用者人工驗收。'])
    if model_patch:
        lines.extend(['', '## 13.6.1–13.6.3／14.1.1 有停止條件的補充診斷（2026-11-19）', '',
            '本節是最新補充；前節保留原研究交付。只以2022／2023時間前推挑選設定，2024已使用過而僅作診斷，2025結果繼續封存。原量測模型／資料未重算或覆寫。',
            '共同基準分別直接加current、recent及batter三群，L2 alpha=.001/.01/.1；各設定比較原始與訓練內溫度校準。唯一非線性家族為淺層HistGradientBoosting，base／rich、7／15葉、60迭代。每角色16 learner設定、兩種機率模式、兩個時間窗；試選使用整場固定SHA樣本fit約30,000、cal至多約10,000，全年全分母驗證。',
            '學習前段與末20%比賽日期校準嚴格分開，跨界比賽排除，標籤完成時間早於校準anchor；補值、尺度與編碼只fit學習前段。先凍結六族候選，再解除pilot上限做全訓練窗確認。共同缺值支持／年齡保留；本場與候補歷史分開，current有效球數不與closed-history有效登板數混收縮。', '',
            '| 角色 | 候選 | 校準 | 2024 n | log loss | Brier | 研究門檻 |', '| --- | --- | --- | ---: | ---: | ---: | --- |'])
        for role in model_patch['roles']:
            for row in role['candidates']:
                lines.append(f"| {role['role']} | {row['config']} | {row['mode']} | {role['validationN']:,} | {row['logLoss']:.6f} | {row['brier']:.6f} | {'通過' if row['incrementGate'] else '未通過'} |")
        lines.extend(['', '保留：'+ '、'.join(x['role']+'='+x['selected'] for x in model_patch['roles'])+'。',
            '判定同時要求200次比賽×投手配對角色內97.5%同時帶上界<0、Brier改善、ECE與>=500列分群傷害限制、內層兩年穩定及無收斂警告；新增特徵另需勝過調整後同演算法基準。依凍結內層排序取首個通過者，不看2024最低值重新挑。',
            '診斷保存舊四組模型訓練／2024逐類校準、2021–2024角色／scope缺值與分位數、量測版本分布。完整特徵舊模型的訓練誤差也較基準差，不能僅將原失敗歸為過擬合；負荷與狀態訊息是否有用仍須看外推增益。固定候選的群組置換在同月／scope／過去角色內進行，保留基準控制，相關特徵可替代，不是因果或疲勞驗證。',
            '14.1.1：'+model_patch['impact']['status']+'。',
            '重跑入口：build_decision_model_patch.py prepare → freeze → diagnose → screen --role SP/RP → select → confirm --role SP/RP → explain --role SP/RP，再run_decision_model_patch_impact.py與export_decision_model_patch.py finish。固定協定／keys／split／模型／機率及manifest在data/research/decision_model_diagnostics_v3/；小型證據data/sample/petehub_pitcher_decision_model_patch_v3.json。此輪止於14.1.1，14.2／15未開始，推薦／排名關閉；畫面由使用者本人驗收。'])
    if alert_research:
        f=alert_research['flow']
        lines.extend(['', '## Slice14.2 完整單場時序、研究預警與官方換投對應（2026-11-19）', '',
            '版本decision_alerts_v1，2024 prepared母體依MD5(game_pk)前32場；不按換投、收益、配對或賽果挑場，非全季總量／獨立測試。沿13.6.3通過RP模型及SP基準，第一PA後回global matchup，256共同路徑、8次既有共同比賽重抽樣，無新調參或2025結果。',
            '預先凍結工程研究門檻：ΔxWPA>=0.005（+0.5pp），MC95及模型中央80下界>0、9模型皆無截尾／外推、最差模型平均缺轉移質量<=1%；RE24另報。相同登板／守備半局相鄰兩個原始邊界合格才發，所有缺口中斷；同登板最多1則，同隊發出後兩個已完成守備PA冷卻。非打者／未完成play仍中斷持續，不增加PA窗口。',
            '官方對應固定同game／team／outgoing appearance。先同邊界，否則提前1–2個已完成守備PA且<=600秒；依預警時序取最早合格事件、一對一。全部官方換投（包含mid-PA／未知／無模型）都保留事件分母。沒有事後最近匹配或因配對率調窗口。', '',
            '| 母體／流向 | 數量 |', '| --- | ---: |'])
        labels={'games':'固定比賽','raw_boundaries':'原始邊界','prepared_boundaries':'既有cohort邊界','modeled':'有支持選項可計算',
            'simulation_supported':'全部模型無截尾／外推支持','qualifying_points':'單點合格','persistent_points':'達連續條件的點（尚未去重）',
            'independent_alerts':'獨立研究預警','official_changes':'全部官方換投','official_modeled_exact':'有模型同邊界的官方事件',
            'official_modeled_window':'固定窗口內有模型機會的官方事件','same_boundary':'同邊界對應','advance_window':'提前窗口對應',
            'unmatched_alerts':'未配對預警','unmatched_events':'未配對官方事件','operational_recommendations':'操作推薦'}
        for key,label in labels.items():lines.append(f"| {label} | {f[key]:,} |")
        review=alert_research['rule_review']
        lines.extend(['',f"規則診斷（不改原預警與配對）：官方有可算同邊界{review['modeled_exact_boundaries']}個，其中{review['exact_qualified_points']}個單點合格，{review['exact_qualified_persistent_points']}個達持續條件。原窗口內有單點合格事件{review['events_with_qualified_point_in_original_window']}個、有持續合格點事件{review['events_with_persistent_point_in_original_window']}個，仍受既有同登板去重。1–3局預警{review['early_alerts_innings_1_to_3']}則，中位提前{review['median_lead_pa']}個守備PA；短半局替代池優勢不等於疲勞／最佳下場切點，未以放寬窗口新增匹配。"])
        lines.extend(['', '逐點保留cohort／選項支持／模擬支持／收益／區間及持續、冷卻、同登板去重原因；逐事件保留身分／時鐘／窗口機會與未配對。原cohort含事後身分及實際接替者核對，不能作部署母體coverage。',
            '對應率不是合理率、預警沒有對應不等於錯誤，教練行動也不是最優策略真值。點區間未作序列整體錯警控制，固定32場非人口估計。active／熱身／醫療／人工可用性未知，recommendation_allowed=false、individual_ranking_allowed=false；選擇偏差／重疊與策略效益留15–16，2025凍結評估留17。',
            '重跑：build_decision_alert_research.py prepare → freeze → simulate（可--model0–8分開）→ evaluate → finalize，再export_decision_alert_research.py finish → export_pitcher_decision_plan.py → sync_project_tracker.py → audit_decision_alert_research.py。protocol／manifest及full point／alert／match／event ledgers在data/research/decision_alerts_v1/。本輪止於14.2，15–20未開始；畫面由使用者本人驗收。'])
    if signal_lights and 'calibrationSummary' in signal_lights:
        d=signal_lights['calibrationSummary'];f=d['replay']['flow']
        lines.extend(['','## 14.2.2–14.2.4 多燈正常進程、增益與事件回放（2026-11-19）','',
            f"研究完成39/47，止於14.2.4，15–20未開始，2025結果封存。{d['blocks']:,}個完整不重疊10球塊、{d['actorRows']:,}個精確actor有機PA；進場前同球種／角色／量測版本至少20球個人參考，正常進程與額外殘差分開，固定EWMA=.3不偷看未來。正常模型四時間窗×兩角色×四目標；內部校準不優者回個人參考。",
            'A球質（Stuff／球速同群）、B位置代理、C條件接觸率、D個人負荷尾端。C尚非鎖定球種、擊球品質或熟悉度因果效果，D不等於疲勞；SP滿35球／RP滿10球只是研究支持，SP>100／RP>60、缺量測或混合版本灰。正常模型不是全面OOD檢查。局間不清除累積負荷，灰不補0；0–8等權五級總燈仍為展示設計，分燈尾端校準不代表總分／兩紅有預測效度。',
            '2022／23前推選有限設定，2024已用診斷；六個角色×A/B/C的平滑比較均未通過同時優於不平滑及常數參考的群聚區間門檻。control／A／B／C／D／all採共同支持與資料年齡控制；兩角色新增方案皆未通過相對control與實際保留模型的結果增益，保留SP global及RP rich tree+temperature，原xWPA值未變。',
            '| 角色 | 2024 PA | 原模型LL | control | A | B | C | D | all | 採用 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |'])
        for row in d['outcomeModels']:lines.append(f"| {row['role']} | {row['n']:,} | {row['referenceLL']:.6f} | "+' | '.join(f"{x['LL']:.6f}" for x in row['variants'])+' | 保留原模型 |')
        lines.extend(['',
            f"固定32場{f['raw_boundaries']:,}原始邊界、{f['modeled']:,}可算、{f['full_four']:,}四群支持（SP591/1242、RP251/495）。形成{f['state_episodes']}次SP描述性持續事件、{f['observed_recovery']}次觀測解除、{f['nominal_research_alerts']}新增換投研究候選／0官方對應／0正式推薦，208官方換投完整保留。原14.2的11預警／0配對及v1燈號快照另留版，不得相加作新成效。",
            '兩個新的相鄰10球區段確認；同區段重讀不算新證據。兩個新區段A/B綠、C非紅解除，D高負荷保留；灰暫停不算恢復，登板／session結束設限，恢復後同登板可以重新成事件。本32場未觀測解除，解除重啟只有規則測試支持。兩紅／三紅只用2022/23全未來區段風險與支持選，不用官方對應率挑門檻；兩角色均未通過。新增validation gate阻擋候選，active／熱身／醫療／人工可用性未知阻擋操作。',
            'PA決策時下一球塊可能已開始，組合目標只用anchor>=decision的第一個全未來塊，最多後移一塊；缺後續量測設限，不補為無惡化。下一塊條件風險是量測異常代理，續投選擇偏差／稀疏區間與策略價值留15–18，不能稱排除早期錯警或疲勞識別已驗證。',
            f"Lab導航{signal_lights['counts']['cases']}例：原11＋固定MD5前24＋明示狀態事件，供檢視而非統計分母。入口#signal-lights新增結果表及校準／預測支持區分；互動示範永遠非實際預測。畫面待使用者驗收。",
            '完整協定／split／模型／分塊／actor特徵／消融／逐點與事件及manifest：data/research/decision_signal_calibration_v1/；證據data/sample/petehub_pitcher_decision_signal_calibration_v1.json及燈號v2。首次序列化guard在fit前失敗，原稿保留，normal protocol revision2才開始訓練。',
            '分段重跑入口：build_decision_signal_calibration.py、build_decision_signal_models.py、build_decision_signal_replay.py；各stage與frozen protocol見交接。完成後export_decision_signal_calibration.py build／finish→export_pitcher_decision_plan.py→sync_project_tracker.py→export_decision_signal_calibration.py manifest→audit_decision_signal_calibration.py。凍結方法不可靜默修改；新方法另留版本。'])
    elif signal_lights:
        lines.extend(['', '## 14.2.1 多原因燈與景氣式綜合狀態契約（2026-11-19）', '',
            '研究展示版本decision_signal_lights_display_v1。A球質、B位置／控球代理、C對手掌握、D負荷／恢復四群各一票；同群原始特徵不另計。綠0、黃1、紅2，0–8分；0綠、1–2黃綠、3–4黃、5–6橙、7–8紅。任何灰或真實未校準訊號使總分null／灰燈，不把缺值補正常、不重算分母，仍顯示已知異常。這是待驗證的顯示設計，不是官方景氣分數或已校準風險。',
            '狀態分數與評估條件分開：展示候選暫定四群皆可判讀、兩紅且含A或B、原因持續、替代收益、名義合法及實際可用性通過；總分高不能略過。gmLI／相性不計票，收益持續不代表原因持續，灰／紅／綠均不直接改變正式推薦開關。',
            f"讀原14.2的{signal_lights['counts']['cases']}則快照，{signal_lights['counts']['belowObservationMinimum']}則低於35球觀測支持；全部原因仍未校準為灰，真實原始值及缺值可展開。另一個互動示範模式可手動切色／條件，明示非真實結果。原11預警／0配對、既有969份凍結產物不改。",
            '本輪完成14.2.1契約與介面，新增4個15前子項後36/47。14.2.2正常進程／局間與去雜訊→14.2.3分燈校準／相關與角色增益→14.2.4解除／重啟及時序研究→15選擇偏差／重疊。20消費已驗證契約作正式雙層燈號，不另造分數；2025封存，尚未啟動這些研究。',
            '重建：export_decision_signal_lights.py build／finish（finish只在首次完成跑）→export_pitcher_decision_plan.py→sync_project_tracker.py。純規則測試node frontend/scripts/test-decision-signal-lights.cjs；source-only資料與依賴檢查audit_decision_signal_lights.py。新Lab入口#signal-lights，畫面與操作均待使用者人工驗收。'])
    if overlap:
        lines.extend(['','## Slice15 選擇偏差、重疊與有效樣本（2026-11-19，原版研究）','',
            f"完成40/47研究工作；2021–24共{overlap['flow']['boundaries']:,}個回溯合法／身分／已完成play邊界、{overlap['flow']['changes']:,}次換投，恢復原38次池外實際接替而不依此結果篩調度模型。這仍非部署母體。24個時間前推模型分開調度、量測觀測、RP池歸屬及池內人選；2025結果不開啟。",
            '| 2024離場角色 | 邊界 | 主要重疊 | 比例 | 換投ESS | 續投ESS | 最大絕對SMD | 平衡門檻 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |'])
        for row in overlap['roles']:
            if row['year']!=2024:continue
            p=row['primary'];lines.append(f"| {row['role']} | {row['action']['n']:,} | {p['retained']:,} | {100*p['retained_fraction']:.1f}% | {p['change']['ess']:.0f} | {p['continue']['ess']:.0f} | {p['max_abs_smd_after']:.3f} | {'通過' if p['diagnostic_gate'] else '未過0.1'} |")
        lines.extend(['','主要重疊＝e∈[.05,.95]且訓練／校準過去分格兩行動各>=10；另列.01/.1及10/20/50權重cap敏感度。ESS是權重等權樣本量近似，不是獨立比賽數；SMD檢查已量測數值、缺失及類別均值，不能證明無隱藏混雜。兩角色主要加權平衡均未通過，不以高AUC或大ESS當因果／換投正確率。',
            '未來量測另估R，不把缺失future_bad補0：SP38087機會缺16828（44.2%），RP19115缺16630（87.0%）。全四群且g>=.1母體中有量測者再作1/g；SP觀測ESS6983、RP1002，RP觀測平衡仍不足。g>=.1導致權重<=10，因此觀測cap10/20/50相同是門檻的必然，不是穩健性證明。',
            'SP兩紅在觀測加權後偏離率63.6%對參考34.5%，差29.1pp，200次比賽×投手重抽樣區間[-4.94,50.69]pp跨0；RP經支持限制後無兩紅例，拒絕硬算區間。這是依賴觀測假設的描述敏感度，非疲勞或策略因果效應，也不晉升原多燈。',
            '原二階段人選分數只條件於實際進入RP池，原18模型／96檔core_manifest留版；診斷後顯式補正為P(change)*P(in RP pool|change)*P(actor|change,in pool)，新增6個池歸屬模型，池外＋續投＋池內機率和為1。非新的獨立2024確認。每候選還檢查自身過去被選次數、RP登板及聯合機率；這只是初篩，整體平衡失敗、active／熱身／醫療／人工可用性未知仍不能作人選推薦。',
            '固定32場2376原始邊界中1791有調度分數、633過初步重疊；1737可算值中604過初步重疊，但不能稱604個有效建議。原11／0與多燈0有效研究候選不變；沒有重跑xWPA或改原模型。',
            overlap['conclusion'],
            '完整方法：decision_overlap_v1/protocol.json revision2與core_manifest、decision_overlap_pool_revision_v2/protocol.json；模型、fit/cal splits、逐點／人選／monitoring／平衡及權重敏感度各留版。首次nullable dtype在transformer即被拒，無模型或預測；原稿封attempt0後只修float/NaN轉型。',
            '小型證據data/sample/petehub_pitcher_decision_overlap_v1.json，Lab#overlap-research，source-only audit另存。下一步先另立平衡修訂／限定母體協定，通過後才定16策略與終點；本輪止15，2025封存，畫面使用者驗收。',
            '方法參考：[Hernán／Robins What If](https://miguelhernan.org/whatifbook)、[Austin propensity score methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC3144483/)。觀測權重依賴可交換與正值支持等假設，不會補出未觀測反事實。'])
    if overlap_revision:
        d=overlap_revision
        lines.extend(['','## 15.1–15.2 共同時點、特徵表示與平衡修訂（2026-11-19）','',
            f"完成42/51：新增15.1–15.4四項，本輪完成15.1／15.2，15.3／15.4與16未開始。原{d['flow']['original']:,}個邊界排除{d['flow']['excluded']}個時點不能嚴格確認者，{d['flow']['included']:,}個重新取得共同截點特徵；{d['flow']['models']}個固定模型，不改原PA／xWPA／燈號或產生新推薦。",
            '共同截點為前一個已完成全場play結束+1ms，嚴格早於官方行動且現任已進場。局中承接前play局面，局間依已知規則重設出局／壘包；所有球數、BF、跨場72/120h用球、角色能力、原因區段按截點ASOF重取，個人負荷中位數固定進場前。下一打者／舊時點WE/LI不借用，先前名義RP快照保留年齡／未知並扣除已登板者；非完整即時可調度名單。',
            '| 2024 RP情境 | 行動 | 原時點落後共同截點中位秒 |','| --- | --- | ---: |'])
        for row in d['clock2024']:
            if row['role']=='RP':lines.append(f"| {'局間' if row['phase']=='between_innings' else '局中'} | {'換投' if row['changed'] else '續投'} | {row['gap_seconds_median']:.1f} |")
        lines.extend(['','時間差依情境改變方向，不能當生理等待或直接斷言造成多少舊偏差。截點仍只早於官方紀錄，未記錄的教練意圖未知；繼承原回溯cohort選擇，不是部署母體。',
            '原RP缺16630例：當下換投4641、後續投球機會不足10553、量測／參考不足1267、支持範圍外142、區段／session缺口27。沒有足夠機會包含稍後換下／固定區段需要10–19球，不能叫純資料缺檔；未觀測仍null。此稽核沿用舊15目標，沒有開始15.3的RP觀測模型或新目標。',
            '固定對照為共同時點HGB、核心樣條logit、完整樣條logit及受限矩條件平衡logit。相同豐富數值／缺失／類別基準檢查每個模型；核心消融不能略過移除欄位。學習／late-cal分開、時間前推，先2022/23選角色設定，凍結selection／confirmation_guard後才做2024診斷；2024不是新的獨立測試。',
            '| 2024依內層排序確認的對照 | 情境 | 重疊母體點數 | 換投／續投ESS | 最大絕對SMD | 通過完整門檻 |','| --- | --- | ---: | ---: | ---: | --- |'])
        for row in d['primary2024']:lines.append(f"| {row['role']} {row['variant']} | {'局間' if row['phase']=='between_innings' else '局中'} | {row['retained']:,} | {row['change']['ess']:.0f}／{row['continue']['ess']:.0f} | {row['max_abs_smd_after']:.3f} | {'通過' if row['full_gate'] else '未通過'} |")
        lines.extend(['','兩角色內層最穩定為hgb_full，但各4個phase/year門檻全未過；2024仍未過.1，沒有取得晉升資格。部分2024 logit較好也不回頭改選。主目標overlap為可比較情境，次目標IPW(.05/.95)另列；新舊截點、分組、欄位、母體不同，不直接宣稱SMD改善百分比。',
            f"矩條件logit為固定受限研究實作，非官方CBPS或精確平衡保證；{d['convergence_warnings']}個模型有收斂警告，保留，不增加迭代或調2024到過。0.1是研究診斷門檻，不證明無隱藏混雜。",
            '15.2首次兩個2022 HGB已fit後，IPW診斷因pandas唯讀mask失敗；source/protocol/模型／機率／split另封attempt0_readonly_mask，revision2只複製mask後篩選，沒有改模型或門檻，且在2024前修正。',
            '完整產物decision_common_clock_v1及decision_balance_revision_v1，小型證據petehub_pitcher_decision_overlap_revision_v1.json。Lab#overlap-revision新增對帳／缺失與模型對照，舊15收合保留歷史。source checks不等於畫面／模型／策略通過。後續15.3→15.4→16，2025封存，畫面使用者驗收。'])
    if rp_targets:
        d=rp_targets
        lines.extend(['','## 15.3 RP觀測目標與受限比較母體（2026-11-21，歷史版本）','',
            f"研究工作43/51。共{d['flow']['boundaries']:,}個RP邊界、{d['flow']['monitor_units']:,}個配對監測機會；{d['flow']['task_artifacts']}個任務產物含{d['flow']['hgb']}個HGB與{d['flow']['constant']}個稀少任務常數退路。15.4尚未開始、2025封存，推薦及排名維持關閉。",
            *d['methodNotes'],'',
            '| 2024主要局中短型歷史母體 | 最大SMD | 換投ESS | 續投ESS | ECE | 完整診斷 |',
            '| --- | ---: | ---: | ---: | ---: | --- |'])
        for row in d['primary2024']:lines.append(f"| {row['model']} | {row['max_abs_smd_after']:.4f} | {row['change']['ess']:.1f} | {row['continue']['ess']:.1f} | {row['action_metrics']['ece']:.4f} | {'通過此項' if row['full_gate'] else '未通過'} |")
        lines.extend(['','| 2024局中短型歷史：配對監測 | 全部 | 已觀測 | 覆蓋率 | 自身常數Brier | 結果模型Brier |','| --- | ---: | ---: | ---: | ---: | ---: |'])
        for row in d['task_results']:
            if row['year']==2024 and row['phase']=='within_inning' and row['subset']=='short_profile':
                m=row['outcome_metrics'];lines.append(f"| {row['target']} | {row['n']} | {row['observed']} | {row['rate']:.2%} | {m['constant_brier']:.5f} | {m['brier']:.5f} |")
        lines.extend(['','資料與協定decision_rp_targets_v1；摘要petehub_pitcher_decision_rp_targets_v1.json。缺失敏感度是假設情境，未觀測標籤仍NaN；固定母體未過門檻不能開始策略效益宣稱。2024已用診斷，改善須後續凍結覆核。Lab#rp-target-research，畫面由使用者驗收；本輪止15.3。'])
    if entry_review:
        d=entry_review
        lines.extend(['','## 15.4 凍結前推與16進入資格（2026-11-21，歷史版本）','',
            f"研究工作44/51。{d['flow']['new_models']}個新模型，覆核{d['flow']['reviewed_rows']:,}點，初步支持{d['flow']['initial_support']:,}點；9個主要phase/year完整診斷通過{d['flow']['primary_passed']}個。研究／實作資格通過{d['flow']['qualified_rows']}點，16維持待開始；2025封存，未估策略收益、未啟用推薦。",
            *d['methodNotes'],'',
            '| 主要前推覆核 | 年份 | 最大SMD | 換投ESS | 續投ESS | ECE | 拒絕原因 |','| --- | ---: | ---: | ---: | ---: | ---: | --- |'])
        for row in d['primary_folds']:lines.append(f"| {row['role']} / {row['phase']} | {row['year']} | {row['max_abs_smd_after']:.4f} | {row['change']['ess']:.0f} | {row['continue']['ess']:.0f} | {row['ece']:.4f} | {', '.join(row['failures']) or '通過此項'} |")
        lines.extend(['','| RP主要條件結果 | 年份 | 有結果／監測數 | Brier模型－過去常數 | game×pitcher探索性95%區間 |','| --- | ---: | ---: | ---: | --- |'])
        for row in d['targets']:
            z=row['cluster_brier'];lines.append(f"| {row['target']} | {row['year']} | {row['observed']}／{row['n']} | {z['delta']:.6f} | [{z['interval'][0]:.6f}, {z['interval'][1]:.6f}] |")
        lines.extend(['','## 16候選策略與終點契約（尚未執行）',''])
        for key,value in d['strategy_contract'].items():lines.append(f'- {key}: {value}')
        lines.extend(['','資格拒絕清單：'])
        for row in d['barriers']:lines.append(f"- {row['id']}: {'通過此項' if row['passed'] else '未通過／未就緒'}；{row['evidence']}")
        lines.extend(['','產物decision_entry_review_v1與petehub_pitcher_decision_entry_review_v1.json。Lab#entry-review，畫面使用者驗收。先另立修訂協定補拒絕清單，不能用工作44/51直接開始16。'])
    if pe_revision:
        d=pe_revision
        lines.extend(['','## 15.5.1–15.5.4 PE、個人化與有限預測對照（2026-11-21，最新）','',
            '研究工作48/55：新增四子項，本輪完成四項；16增加15.5.4依賴，仍未開始。546880個共同截點重新建立PE／個人參考／預定打線，30個九類PA＋12個PA失分模型，不改原模型／燈號／xWPA或啟用推薦，2025封存。',
            *d['methodNotes'],'',
            '| 2024依2022/23排序的研究對照 | 模型 | 九類LL | 非出局AUC | ΔLL對HGB基準 | 探索性95%區間 | 開發支持 |','| --- | --- | ---: | ---: | ---: | --- | --- |'])
        for row in d['primary2024']:
            z=row['delta_log_loss'];lines.append(f"| {row['role']} | {row['config']} | {row['metrics']['log_loss']:.5f} | {row['metrics']['nonout']['auc']:.4f} | {z['delta']:.6f} | [{z['interval'][0]:.6f},{z['interval'][1]:.6f}] | {row['development_predictive_support']} |")
        lines.extend(['','| 2024輔助PA期間失分風險，角色別回放 | 模型 | 提醒 | 未知後續 | 已觀測PPV | 同邊界換投 | 提前1–2PA/600s配對 |','| --- | --- | ---: | ---: | --- | ---: | ---: |'])
        for fold in d['folds']:
            if fold['year']!=2024:continue
            for row in fold['warnings']:lines.append(f"| {row['role']} | {row['config']} | {row['alerts']} | {row['unknown_alerts']} | {row['precision_observed']:.2%} | {row['same_boundary_change']} | {row['advance_change_2pa600s']} |")
        lines.extend(['','以上提醒為風險研究、不是正式多燈換投建議；提醒／實際換投吻合非策略收益。完整folds保存PE消融、同完整特徵三演算法、兩任務及RP配對舊二元對照；不能用跨任務或不同訓練母體宣稱純模型改善。',
            '產物decision_pe_features_v1／decision_pe_models_v1與petehub_pitcher_decision_pe_revision_v1.json。Lab#pe-revision，畫面由使用者驗收。原15.4九個SMD失敗與16實作／識別缺口保留；新增預測支持不能自動跳16。'])
    if exploration:
        d=exploration
        lines.extend(['','## 16.1–16.3：探索回放與共同截點情境（最新）','',
            '使用者授權先作探索回測，原15.4正式效益契約及失敗資格留版。16主項進行中、51/58完成，17–21未啟動、2025封存。',
            f"固定{d['caseFlow']['games']}場、{d['caseFlow']['boundaries']}個共同截點，{d['caseFlow']['modeled']}點可估、{d['caseFlow']['excluded']}點保留拒絕；風險提醒{d['caseFlow']['alerts']}次。",''])
        lines.extend('- '+note for note in d['methodNotes'])
        lines.extend(['','| 情境 | 可估點 | PA支持 | 半局支持 | 半局替代池較高／續投較高／未知 |','| --- | ---: | ---: | ---: | --- |'])
        for row in d['scenarios']:lines.append(f"| {row['variant']} | {row['modeled']} | {row['pa']['supported']} | {row['half']['supported']} | {row['half']['directions']} |")
        lines.extend(['','產物`decision_exploratory_v1/`與`petehub_pitcher_decision_exploratory_v1.json`；Lab#exploratory-replay。點區間只含MC，模型／選擇偏差與可用性未知另列，畫面由使用者驗收。'])
    lines.extend(["", "## 現有盤點與後續驗證", "",
                  "data/research/decision_support_audit_20261112/ 保存觀測資料與來源限制；資料涵蓋不等於嚴格時點可用。",
                  "研究設計細節：data/research/decision_support_audit_20261112/research_notes.md。",
                  "頁面展示 build-time 規劃與研究摘要，不新增 API、不觸發下載／訓練／預警；UI 驗收由使用者本人執行。", ""])
    (ROOT / project["document"]).write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(project['slices'])} slices and {len(coverage)} audit years.")


if __name__ == "__main__":
    main()
