"""Authority and research-evidence publisher for14.2.2-4."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_signal_calibration as q
from scripts.export_decision_model_patch import load_project,change_field
import pandas as pd

ROOT=q.b.ROOT
SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v2.json'


def evidence():
    replay=q.read(q.OUT/'replay_summary.json')
    normal=q.read(q.OUT/'normal_validation.json')
    models={role:q.read(q.OUT/f'pa_{role}.json') for role in ['SP','RP']}
    return {'version':'decision_signal_calibration_v1','stop':'14.2.4','updatedAt':'2026-11-19',
        'blocks':sum(q.read(q.OUT/f'blocks_{y}.json')['blocks'] for y in range(2021,2025)),
        'actorRows':sum(len(pd.read_parquet(q.OUT/f'features_{y}.parquet',columns=['decision_id'])) for y in range(2021,2025)),
        'normal2024':[x for x in normal['rows'] if x['year']==2024],
        'outcomeModels':[{'role':role,'n':d['validation_n'],'selected':d['selected'],'referenceLL':d['reference']['log_loss'],
            'variants':[{'variant':x['variant'],'LL':x['metrics']['log_loss'],'Brier':x['metrics']['brier'],
                'vsControl':x['vs_control'],'vsRetained':x['vs_retained'],'passed':x['increment_gate']} for x in d['results']]} for role,d in models.items()],
        'replay':replay,'recommendationAllowed':False,'test2025OutcomesExamined':False,'visualAcceptance':'pending user'}


def build():
    data=evidence();summary=data['replay']
    full=pd.read_parquet(q.old.OUT/'full_options.parquet');full=full[full.is_current].set_index('decision_id')
    features=pd.read_parquet(q.OUT/'case_features.parquet');features=features[features.is_current].set_index('decision_id')
    points=pd.read_parquet(q.OUT/'signal_point_ledger.parquet').set_index('decision_id')
    old=q.read(ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v1.json')
    selected=[c['id'] for c in old['cases']]
    others=sorted(set(full.index)-set(selected),key=lambda s:hashlib.md5(s.encode()).hexdigest())[:24]
    selected+=others
    # Explicit event example for navigation only; never use this enriched sample as a denominator.
    for sid in pd.read_parquet(q.OUT/'state_episodes.parquet').start_decision_id:
        if sid not in selected:selected.append(sid)
    prep=q.read(q.old.OUT/'preparation.json');names={x['game_pk']:x['player_names'] for x in prep['game_metadata']}
    def num(value):return float(value) if pd.notna(value) else None
    def metric(row,key,label,unit=''):
        value=num(row.get(key));return label+'：'+('未知' if value is None else f'{value:.2f}{unit}')
    cases=[]
    for sid in selected:
        row=full.loc[sid];f=features.loc[sid];point=points.loc[sid]
        name=names[int(row.game_pk)].get(str(int(row.option_pitcher_id)),str(row.option_pitcher_id))
        lights=[]
        titles={'A':'球質偏離','B':'位置／控球代理','C':'對手接觸偏離','D':'負荷／恢復壓力'}
        supporting={
            'A':[metric(f,'A_expected_stuff','正常進程預期差',' Plus點'),metric(f,'A_drift_stuff','平滑後額外Stuff偏離',' Plus點'),metric(f,'A_drift_velocity','額外球速偏離',' mph')],
            'B':[metric(f,'B_expected_location','正常進程預期差',' Plus點'),metric(f,'B_drift_location','平滑後位置偏離',' Plus點')],
            'C':[metric(f,'C_expected_contact','對手／球質條件下接觸參考'),metric(f,'C_drift_contact','平滑接觸率偏離')],
            'D':[metric(f,'median_pitches','進場前同角色近期中位用球','球'),metric(f,'load_relative','本場／個人中位用球'),metric(f,'recent72_relative','近72h其他場／中位用球'),metric(f,'streak','進場前連續登板日','日')]}
        for group in 'ABCD':
            state=int(f[group+'_state']);known=state>=0
            reason=('通過量測與角色支持；燈色描述相對過去校準尾端，不代表疲勞成立。' if known else '未達角色／量測／個人參考支持；不補正常值。')
            if group=='C':reason+=' 接觸率代理尚不等於打者鎖定球種或熟悉度的因果效果。'
            if group=='D':reason+=' 高負荷不直接等同壓制力下降；局間不清除累積負荷。'
            lights.append({'id':group,'title':titles[group],'state':{-1:'gray',0:'green',1:'yellow',2:'red'}[state],
                'calibrated':True,'supportKnown':known,'reason':reason,'evidence':supporting[group]+[metric(f,group+'_severity','標準化／百分位嚴重度')]})
        mature=bool(f.session_pitches>= (35 if point.role=='SP' else 10)) if pd.notna(f.session_pitches) else False
        active=pd.notna(point.state_episode_id)
        predictive=next(x['diagnostic_gate'] for x in summary['combination_validation2024'] if x['role']==point.role)
        cases.append({'id':sid,'decisionId':sid,'label':f'{int(row.game_pk)} · {int(point.inning)}'+('上' if point.half=='top' else '下')+f' · {name}'+(' · 持續狀態事件' if point.state_event_entered else ''),
            'gamePk':int(row.game_pk),'pitcherName':name,'role':point.role,'inning':int(point.inning),'half':point.half,
            'pitches':float(row.option_game_pitches),'observationMature':mature,'lights':lights,
            'gates':{'value':'pass' if point.point_reason=='qualifies' else 'fail','legal':'pass','availability':'unknown',
                'statePersistence':'pass' if active and all(x['supportKnown'] for x in lights) else 'unknown','validation':'pass' if predictive else 'fail'},
            'valueNote':f'沿用原14.2替代池：ΔxWPA {point.wpa_delta*100:+.2f}pp，ΔxRE24 {point.re24_delta:+.3f}分。收益門檻：{point.point_reason}。兩角色新增特徵皆未通過替換，未改xWPA。',
            'matchupNote':f'區段 {f.block_id if pd.notna(f.block_id) else "未知"}；決策前資料年齡 '+('未知' if pd.isna(f.block_age_minutes) else f'{f.block_age_minutes:.1f}分鐘')+'。相性／LI不加票，後續打線仍用聯盟池。',
            'li':num(point.research_pa_li)})
    display={'version':'decision_signal_lights_calibrated_tails_v2','updatedAt':'2026-11-19','mode':'observed','cases':cases,
        'counts':{'cases':len(cases),'belowObservationMinimum':sum(not c['observationMature'] for c in cases),'matureObservation':sum(c['observationMature'] for c in cases)},
        'scoreStatus':'分燈為訓練內尾端校準；0–8等權及兩紅未通過預測支持，只供狀態展示。灰不補0，任何總燈都不直接換投。',
        'recommendationAllowed':False,'calibrationSummary':data}
    q.b.save_json(SAMPLE,display);q.save('display.json',display)
    q.b.save_json(ROOT/'data/sample/petehub_pitcher_decision_signal_calibration_v1.json',data);q.save('evidence.json',data)
    print(f'Published calibration evidence and {len(cases)} navigation examples; no operational recommendations',flush=True)


def manifest():
    paths=[Path(__file__),ROOT/'backend/scripts/audit_decision_signal_calibration.py',ROOT/'backend/tests/test_decision_signal_calibration.py',
        ROOT/'frontend/utils/decisionSignalLights.ts',ROOT/'frontend/components/charts/DecisionSignalLights.vue',ROOT/'frontend/scripts/test-decision-signal-lights.cjs',
        SAMPLE,ROOT/'data/sample/petehub_pitcher_decision_signal_calibration_v1.json']
    files=sorted(p for p in q.OUT.rglob('*') if p.is_file() and p.name not in ['manifest.json','audit.json'])
    q.save('manifest.json',{'version':'decision_signal_calibration_v1',
        'files':[{'path':p.relative_to(q.OUT).as_posix(),'bytes':p.stat().st_size,'sha256':q.b.digest(p)} for p in files],
        'source_sha256':{p.relative_to(ROOT).as_posix():q.b.digest(p) for p in paths},'stop':'14.2.4','test2025_outcomes_examined':False})
    print(f'Frozen {len(files)} research artifacts and {len(paths)} publisher/display/audit sources',flush=True)


def handoff():
    d=q.read(q.OUT/'evidence.json');f=d['replay']['flow']
    text=f'''## 2026-11-19：14.2.2–14.2.4多燈正常進程／增益／事件回放完成（最新）

進度 **39/47**，本輪止於14.2.4。15–20仍planned，2025結果封存，不自動進15或commit／push。畫面由使用者驗收。保留原969份凍結研究產物及14.2的11預警／0配對，v1燈號資料未覆寫，原三份顯示源碼另存previous_display_contract。

14.2.2：2021–2024共{d['blocks']:,}個完整且不重疊10球塊。進場前同人／角色／球種／量測版本至少20球個人參考；固定Ridge100控制累積／單局用球、局間時間、配球與過去打者能力，內部校準不優者回個人參考。4時間窗×2角色×4目標32個正常進程模型；EWMA=.3與不平滑、常數基準比較。2024六個角色×原因組合均未通過同時改善的群聚區間門檻，不能宣稱去雜訊已提高預測。SP滿35球、RP滿10球只是研究觀測成熟，SP>100／RP>60或量測不足灰；正常模型只限制預先指定支持範圍，尚非全面OOD檢定或生理疲勞真值。

14.2.3：四季{d['actorRows']:,}個有機PA，當前原因只接精確outgoing，incoming不借其A/B/C；D以進場前最近10次已閉合同角色登板中位數（至少5次）及14日完整負荷。control／A／B／C／D／all共同缺值與資料年齡控制，先2022/23前推排序，再2024固定分母確認（SP92,013、RP45,686）。兩角色所有新增方案均未通過對control及實際保留模型的增益門檻；保留SP原global及RP原rich tree+temperature，不覆寫值模擬、不另生成新的第一PA敏感度產物。正常進程與殘差均入候選特徵，但未因此取得決策模型替換資格。

14.2.4：兩個新的相鄰10球區段且同session確認，重複PA讀同block不算持續；灰暫停不當恢復。兩個新區段A/B綠、C非紅可解除，D累積負荷可仍高；恢復後同登板可重新形成事件，結束未恢復則設限。兩紅／三紅組合只以2022/23決策後「全未來」區段選支持（該區段anchor>=decision，下一塊已開始則找再下一塊）；不依官方配對挑設定。兩角色兩紅組合均不通過，三紅SP只有3例、RP0，不擴大解釋；2024診斷不能改選。

固定32場{f['raw_boundaries']:,}原始邊界、{f['modeled']:,}可算、{f['full_four']:,}四群皆支持（SP591/1242、RP251/495）；{f['state_episodes']}次SP描述性狀態事件，{f['observed_recovery']}次實際觀測解除、{f['nominal_research_alerts']}新增研究候選、0官方對應、208官方換投、操作推薦0。這不能叫「降低錯警已驗證」，也不是沒有疲勞；組合尚缺預測支持，灰與未來續投缺失均保留。恢復／重啟僅規則測試通過，此32場沒有實際解除例。

Lab `/lab/decision-support#signal-lights` 顯示校準尾端色、增益與回放摘要、原11例＋固定MD5前24例＋明示1個狀態事件導航例；這36例不是估計分母。0–8總分仍為展示，新增validation gate（實際fail），可用性unknown。C實際只驗證條件接觸率代理，未完成鎖定球種／擊球品質／熟悉度因果辨識；B位置也不是主觀控球意圖。

完整產物 `data/research/decision_signal_calibration_v1/`：normal／feature／model／episode四份凍結協定、fit/cal ledgers、模型、逐區段分數、actor特徵、角色消融與機率、episode選擇及32場逐點／事件／候選／對應表；manifest與audit另列SHA及時鐘檢查。首次協定序列化guard在訓練前失敗，原稿留attempt0_protocol_serialization，revision2修正tuple/list一致性後才開始擬合。2024已使用診斷，2025不開封；小樣本區間及續投選擇偏差尚需15研究，15是研究下一步，不是上線批准。

重跑分段：build_decision_signal_calibration.py prepare→freeze→fit_normal --fold→score_year --year；build_decision_signal_models.py prepare→freeze→fit_load→finalize_features→freeze_models→screen→confirm（按角色）；build_decision_signal_replay.py freeze→select→normal_diagnostics→replay。最後export_decision_signal_calibration.py build→finish，export_pitcher_decision_plan.py、sync_project_tracker.py、manifest與audit。模型／核心腳本凍結後不得靜默修改；新方法另留協定版本。畫面仍pending user。

'''
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';old=path.read_text('utf-8')
    if text.splitlines()[0] not in old:
        old=old.replace('14.2.1完成（最新）','14.2.1完成（歷史）',1);at=old.index('## ')
        path.write_text(old[:at]+text+old[at:],encoding='utf-8')


def update(stage):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    status_map={'start':['in_progress','planned','planned'],'models':['done','in_progress','planned'],
        'replay':['done','done','in_progress'],'finish':['done','done','done']}[stage]
    for position,sid in enumerate(['14.2.2','14.2.3','14.2.4']):
        if status_map[position]=='planned':continue
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);block=segment[at:finish]
        block=change_field(block,'status',status_map[position],decoder)
        if sid=='14.2.2':description='2026-11-19：四季244,179個非重疊完整10球塊，個人同球種及同量測版本參考固定於進場前、至少20球；控制累積／單局用球、局間時間、球類配比與過去打者能力。四個時間窗、兩角色、Stuff／球速／Location／接觸共32個固定Ridge正常進程模型，內部校準不優於個人參考者保留原參考；EWMA=.3與不平滑對照，下一完整球塊未觀測保留設限。2024已用診斷，模型與來源協定留版；首次序列化guard失敗未訓練，原協定／源碼另存。'
        elif sid=='14.2.3':description='2026-11-19：精確actor及決策時鐘對位545,204個有機PA，incoming不繼承outgoing A/B/C；D以進場前同角色近期登板中位數及完整負荷參考。共同支持／資料年齡控制下比較control、A、B、C、D、all，2022／23前推排序、2024 SP92,013／RP45,686確認；兩角色新增方案均未通過增益門檻，保留原SP global及RP rich tree+temperature，xWPA沿用原版。'
        else:description='2026-11-19：兩個新的非重疊球塊確認／解除，灰暫停不當恢復，D累積負荷保留，可解除後重啟。2022／23兩紅與三紅均未取得角色預測支持。原32場2376邊界／1737可算／842四群支持，1次SP描述性狀態事件、0觀測解除／新增研究候選／對應／正式推薦；原11／0留版，沒有為提高配對率改窗口。'
        if sid=='14.2.2' and stage=='finish':description+=' 2024六組平滑對不平滑及常數比較均未通過完整增益門檻，僅保留描述性去雜訊版本，不宣稱疲勞預測有效。'
        block=change_field(block,'verification',description,decoder);segment=segment[:at]+block+segment[finish:]
        # Evidence points to this revision, not the earlier display prototype.
        if status_map[position]=='done':
            match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at)
            block=segment[at:finish]
            if 'evidence' not in item:block=block[:-1].rstrip()+',\n      "evidence": "data/sample/petehub_pitcher_decision_signal_calibration_v1.json"\n    }'
            segment=segment[:at]+block+segment[finish:]
    completed=36+sum(x=='done' for x in status_map)
    if stage=='finish':
        match=re.search(r'"id"\s*:\s*"15"\s*,',segment);at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at)
        block=change_field(segment[at:finish],'deliverable','時間交叉擬合歷史調度與續投／未來量測觀測傾向，檢查各候選及分燈組合的重疊、極端權重與有效樣本；承接14.2.4未通過增益／組合支持的結果，先處理續投選擇、稀疏群聚區間及提醒母體，不能將兩紅或零新候選視作模型成效通過。',decoder)
        segment=segment[:at]+block+segment[finish:]
    for key,value in [('summary',f'14.2.2–14.2.4研究進度{completed}/47。以嚴格過去同球種個人參考及不重疊10球塊處理正常進程／異常偏離，分燈校準、增益與新事件恢復重啟分開驗證；2024已使用診斷，2025封存，原11／0留版。'),
        ('next_step','14.2.2–14.2.4完成研究評估；正常平滑、角色新增特徵及兩紅組合尚未取得完整增益支持。保留原決策模型，0新研究候選／0操作推薦；下一步可另授權15重疊／續投選擇偏差與不確定性研究，不能視作上線通過。止於14.2.4，不自動進15；2025封存，畫面由使用者驗收。' if stage=='finish' else '分段完成14.2.2–14.2.4，不進15；畫面由使用者驗收。')]:segment=change_field(segment,key,value,decoder)
    result=text[:begin]+segment+text[end:];parsed=json.loads(result)
    assert [x for x in parsed['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print(f'Research authority {completed}/47, stop14.2.4',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','models','replay','build','manifest','finish']);args=parser.parse_args()
    if args.stage=='build':build()
    elif args.stage=='manifest':manifest()
    elif args.stage=='finish':update('finish');handoff()
    else:update(args.stage)
