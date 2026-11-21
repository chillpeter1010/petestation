"""14.2 authority/small evidence/UI publisher; preserve every prior project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_alert_research as q
from scripts.export_decision_model_patch import load_project,change_field

ROOT=q.b.ROOT


def review_rules():
    """Explain the frozen result; do not create alternative alerts or matches."""
    points=pd.read_parquet(q.OUT/'point_ledger.parquet');events=pd.read_parquet(q.OUT/'event_ledger.parquet');alerts=pd.read_parquet(q.OUT/'alerts.parquet')
    exact=events[['event_id','boundary_decision_id']].merge(points,left_on='boundary_decision_id',right_on='decision_id',how='inner',validate='many_to_one')
    assert exact.event_id.is_unique
    exact=exact[exact.wpa_delta.notna()];qualified=exact[exact.point_reason.eq('qualifies')]
    opportunities=[];persistent=[];leads=[]
    for event in events.itertuples():
        group=points[points.game_pk.eq(event.game_pk)&points.team_id.eq(event.team_id)&points.appearance_id.eq(event.outgoing_appearance_id)&points.point_reason.eq('qualifies')]
        candidates=[row for row in group.itertuples() if q.logic.eligible_pair(row,event) is not None]
        if candidates:opportunities.append(event.event_id)
        for row in candidates:
            if row.run_length>=2:persistent.append({'event_id':event.event_id,'decision_id':row.decision_id,'suppression':row.alert_reason})
    for alert in alerts.itertuples():
        group=events[events.game_pk.eq(alert.game_pk)&events.team_id.eq(alert.team_id)&events.outgoing_appearance_id.eq(alert.appearance_id)].sort_values(['at_bat_number','event_index'])
        if len(group):
            event=next(group.itertuples());leads.append({'decision_id':alert.decision_id,'event_id':event.event_id,
                'lead_pa':float(q.logic.pa_clock(event)-q.logic.pa_clock(alert)),
                'lead_seconds':float(event.event_at-alert.decision_at)})
    result={'protocol_sha256':q.b.digest(q.OUT/'protocol.json'),'review_source_sha256':q.b.digest(Path(__file__)),
        'modeled_exact_boundaries':len(exact),'exact_qualified_points':len(qualified),
        'exact_qualified_persistent_points':int(qualified.run_length.ge(q.logic.RULES['persistence_boundaries']).sum()),
        'exact_point_reasons':exact.point_reason.value_counts().to_dict(),
        'events_with_qualified_point_in_original_window':len(opportunities),
        'events_with_persistent_point_in_original_window':len(set(x['event_id'] for x in persistent)),
        'persistent_window_points':persistent,'early_alerts_innings_1_to_3':int(alerts.inning.le(3).sum()),
        'alerts_with_later_same_appearance_official_event':len(leads),
        'median_lead_pa':float(pd.DataFrame(leads).lead_pa.median()) if leads else None,
        'median_lead_seconds':float(pd.DataFrame(leads).lead_seconds.median()) if leads else None,
        'later_event_leads':leads,'fixed_alerts_and_matching_unchanged':True,
        'interpretation':'Explanatory accounting only; these opportunity points are NOT additional matches or an alternative policy score. Early half-inning pool advantage is not a fatigue/optimal-removal label; long-term bullpen cost and causal overlap remain unmodeled.'}
    q.save('rule_review.json',result)
    return result


def tracker(stage,summary=None):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    match=re.search(r'"id"\s*:\s*"14\.2"\s*,',segment);assert match
    at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);block=segment[at:finish]
    done=stage=='finish'
    description=('2026-11-19使用者授權：固定MD5前32場2024比賽補齊原始邊界時序，先凍結0.5pp收益、連續2點、2PA冷卻／同登板最多1則及同邊界／提前2PA且600秒的一對一對應；沿13.6.3／14.1.1模型，不重訓或調2025。')
    if done:
        f=summary['flow']
        description+=f' 完成：{f["raw_boundaries"]}原始邊界、{f["modeled"]}可計算、{f["simulation_supported"]}模擬支持、{f["qualifying_points"]}單點合格、{f["independent_alerts"]}獨立研究預警；官方事件{f["official_changes"]}，同邊界{f["same_boundary"]}、提前窗口{f["advance_window"]}，未配對預警{f["unmatched_alerts"]}／事件{f["unmatched_events"]}。支持／門檻／持續／冷卻／去重、事件時鐘／身分／範圍及未配對原因逐列保存，原始非打者／未完成邊界仍中斷持續，但不增加已完成PA計數。對應率不是正確率；點區間不是序列錯警控制，active／熱身／醫療未知、操作推薦0。'
    block=change_field(block,'status','done' if done else 'in_progress',decoder)
    block=change_field(block,'verification',description,decoder)
    if done:
        evidence='data/sample/petehub_pitcher_decision_slice14_2_v1.json'
        if 'evidence' in item:block=change_field(block,'evidence',evidence,decoder)
        else:
            nl='\r\n' if '\r\n' in block else '\n'
            block=block[:-1].rstrip()+','+nl+'      "evidence": '+json.dumps(evidence)+nl+'    }'
    segment=segment[:at]+block+segment[finish:]
    if done:
        f=summary['flow']
        overview=f'14.2完成，進度35/43。固定32場完整時序：{f["raw_boundaries"]}原始邊界→{f["modeled"]}可計算→{f["qualifying_points"]}單點合格→{f["independent_alerts"]}獨立研究預警；官方換投{f["official_changes"]}，同邊界{f["same_boundary"]}／提前窗口{f["advance_window"]}。規則事先凍結，未配對與拒絕原因留列；這是2024選場研究對應，不是全季總量或合理率，正式推薦關閉。'
        next_step='本輪止於14.2；等待使用者指示Slice15選擇偏差／換投續投重疊，再接16策略評估及17凍結後2025測試。保留SP基準與RP研究候選、全部舊484點及32場研究產物；不依對應率回調門檻，畫面由使用者本人驗收。'
    else:
        overview='14.2研究預警與官方事件對應啟動，進度34/43。固定32場完整原始邊界時序，凍結研究收益／支持／持續／冷卻／同登板去重及一對一事件窗口；2024已使用診斷，2025測試封存，正式推薦關閉。'
        next_step='依14.2.A完整時序、14.2.B凍結模擬／預警、14.2.C事件對應／原因稽核分段完成。本輪只做14.2，不開始15或2025最終評估；32場固定選取，沒有結果導向替換或配對率調參，畫面由使用者驗收。'
    for key,value in [('summary',overview),('next_step',next_step),('updated_at','2026-11-19')]:segment=change_field(segment,key,value,decoder)
    result=text[:begin]+segment+text[end:];result=change_field(result,'updated_at','2026-11-19',decoder)
    parsed=json.loads(result);p=next(x for x in parsed['projects'] if x['id']=='pitcher-decision-support')
    assert len(p['slices'])==43 and sum(x['status']=='done' for x in p['slices'])==(35 if done else 34)
    assert all(x['status']=='planned' for x in p['slices'] if x['id'] in ['15','16','17','18','19','20'])
    assert [x for x in parsed['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print('14.2 authority:'+('35/43 done' if done else '34/43 in progress'),flush=True)


def finish():
    summary=q.read(q.OUT/'summary.json');assert q.read(q.OUT/'protocol.json')==q.protocol()
    summary['rule_review']=review_rules()
    tracker('finish',summary)
    # The full per-boundary / per-event ledgers remain offline; this small snapshot
    # contains every emitted alert, all selected-game counts and reasons.
    q.b.save_json(ROOT/'data/sample/petehub_pitcher_decision_alert_research_v1.json',summary)
    handoff=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=handoff.read_text('utf-8')
    heading='## 2026-11-19：Slice14.2完整時序預警與官方換投對應完成（最新）'
    assert heading not in text
    text=text.replace('## 2026-11-19：模型診斷補丁完成，停在14.1.1（最新）','## 2026-11-19：模型診斷補丁完成，停在14.1.1（歷史）',1)
    f=summary['flow']
    paragraph=f'''{heading}

使用者授權「開始14.2並解釋成果」，現已完成，Decision Support **35/43**。本輪止於14.2，15–20仍planned，2025最終測試未開啟；未commit／push、未開瀏覽器／server或執行畫面驗收。既有dirty worktree、935份舊凍結產物及原484點留版。

固定2024 prepared母體按MD5(game_pk)前32場，不按實際換投／收益／配對挑場，不做全季或獨立測試宣稱。沿本輪SP基準、RP tree_rich_7＋溫度；僅第一PA有狀態特徵，後續global matchup／2023年底聯盟打者池。256共同路徑、8次舊共同比賽refit，不新增訓練。每場SHA(seed:game)亂數相同於兩方案及9模型；role池均勻抽人，無最佳手別／類型或個別排名。

事先凍結門檻：中央ΔxWPA>=0.005（0.5pp）、MC95與模型中央80下界>0、9模型皆無截尾／球數或首PA範圍外推、最差模型平均缺轉移質量<=1%；RE24另報不選門檻。相同登板／同守備半局相鄰2個原始邊界合格才發；任何資料缺口／拒絕點中斷。每登板最多1則、同隊發出後2個已完成守備PA冷卻。非打者／未完成play保留原始缺口，但不增加PA窗口。配對只用同game／team／outgoing appearance，先同邊界，否則提前1–2個已完成守備PA且<=600秒，依預警時序取最早合格事件，一對一，無事後最近配對。

結果：{f['raw_boundaries']}原始邊界、{f['prepared_boundaries']}既有cohort邊界、{f['modeled']}有支持選項可算、{f['simulation_supported']}無截尾／外推支持、{f['qualifying_points']}單點門檻合格、{f['independent_alerts']}獨立研究預警。官方換投{f['official_changes']}，有模型同邊界{f['official_modeled_exact']}／固定窗口內機會{f['official_modeled_window']}；預警同邊界對應{f['same_boundary']}、提前對應{f['advance_window']}、未配對預警{f['unmatched_alerts']}，未配對事件{f['unmatched_events']}。各角色／各場／原始點與事件原因、未配對保留，不能以配對率當正確率或教練行動當合理真值。固定小樣本，可能低提醒或零配對也不改閾值；序列多次查看並未有整體錯警率保證。active／熱身／醫療／人工可用性未知，操作推薦0、個別排名false。

凍結結果的規則診斷rule_review另存，不新增配對：官方有可算同邊界{summary['rule_review']['modeled_exact_boundaries']}個，其中{summary['rule_review']['exact_qualified_points']}個單點合格、{summary['rule_review']['exact_qualified_persistent_points']}個達持續條件。原固定配對窗口內，有單點合格的事件{summary['rule_review']['events_with_qualified_point_in_original_window']}個、有持續合格點的事件{summary['rule_review']['events_with_persistent_point_in_original_window']}個；若已同登板發過預警，仍依原規則拒絕重發。早期1–3局預警{summary['rule_review']['early_alerts_innings_1_to_3']}則，與同一離場事件的中位提前{summary['rule_review']['median_lead_pa']}個已完成守備PA。短半局替代池優勢不等於先發疲勞或最佳換投切點；不以放寬窗口增加配對率。這組補充不改原11／0結果，建議下一步檢查Slice15早換選擇的重疊／支持，規則敏感度另立新版本，不覆寫本輪凍結結果。

新資料 `data/research/decision_alerts_v1/`，核心 `build_decision_alert_research.py`、純規則 `decision_alert_rules.py`、發布 `export_decision_alert_research.py`、稽核 `audit_decision_alert_research.py`。protocol／manifest、所有原始點point_ledger、alerts、matches及event_ledger均存檔；小型證據slice14_2_v1.json／alert_research_v1.json，source-only audit另存sample。前端 `/lab/decision-support#alert-research` 顯示完整分母、規則、角色／場次／每則提醒與原因；畫面由使用者本人驗收。下一步需使用者指示Slice15重疊／選擇偏差，後續16策略評估及17凍結測試，不能自動開始。

'''
    at=text.index('## ');handoff.write_text(text[:at]+paragraph+text[at:],encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','finish'])
    stage=parser.parse_args().stage
    if stage=='start':tracker(stage)
    else:finish()
