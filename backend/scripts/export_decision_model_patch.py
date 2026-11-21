"""Authoritative planning/results publisher for bounded pre14.2 model patches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_model_patch as patch

b=patch.b

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/research/decision_model_diagnostics_v3'
SLICES=[
 {'id':'13.6.1','phase':'models','label':'Slice 13.6.1 · 學習誤差、年度與來源穩定性診斷','status':'in_progress','depends_on':['13.6'],
  'deliverable':'保留舊凍結版，分角色檢查訓練／時間留出誤差、逐類校準、年度缺值／資料年齡與Plus／狀態分布；釐清本場與閉合歷史的scope及n單位。',
  'verification':'進行中：2026-11-19使用者授權補充模型診斷，2024已使用過，2025測試繼續封存。',
  'acceptance':'只作診斷，不由2024結果反覆調參；分開資料漂移、模型容量與泛化落差，不能僅由驗證變差認定過擬合或疲勞不存在。'},
 {'id':'13.6.2','phase':'models','label':'Slice 13.6.2 · 獨立特徵增益、正則化與機率校準','status':'planned','depends_on':['13.6.1'],
  'deliverable':'基準直接加入本場觀測、近期歷史／負荷、打者前序／相性三群獨立對照；於2021–2023時間前推內限制L2搜尋與溫度校準，再凍結候選。',
  'verification':'Pending','acceptance':'同分母／支持控制，補值尺度編碼及校準只fit相應訓練窗。特徵窗與候選範圍事先限定；2024僅已使用診斷，2025不回流。'},
 {'id':'13.6.3','phase':'models','label':'Slice 13.6.3 · 受限非線性對照與解釋穩定性','status':'planned','depends_on':['13.6.2'],
  'deliverable':'加入一種淺層HistGradientBoosting，基準與精簡完整特徵均作對照；時間前推挑選、全量確認及角色／群聚區間／校準／群組移除診斷。',
  'verification':'Pending','acceptance':'新增特徵效果與更換演算法效果分開；重要性／移除結果不稱因果。沒有增益保留基準，不以無限搜尋作為進14.2條件。'},
 {'id':'14.1.1','phase':'models','label':'Slice 14.1.1 · 凍結模型與484點決策敏感度覆核','status':'planned','depends_on':['13.6.3','14.1'],
  'deliverable':'有通過預定診斷門檻的候選才另版重跑原484點固定半局比較；否則核對原14.1仍有效並保留50／11／423。依相同終點、路徑與可用性限制評估方向穩定性。',
  'verification':'Pending','acceptance':'只更動有支持的第一PA預測，不虛造後續狀態演化／當時打線；未通過可用性及策略驗證前推薦／排名關閉。完成此補充後才進14.2，不能自動開始14.2或15。'}]


def load_project():
    path=ROOT/'docs/PROJECT_TRACKER.json'
    with path.open('r',encoding='utf-8',newline='') as stream:text=stream.read()
    decoder=json.JSONDecoder();match=re.search(r'"id"\s*:\s*"pitcher-decision-support"',text);assert match
    begin=text.rfind('{',0,match.start());project,end=decoder.raw_decode(text,begin)
    return path,text,begin,end,project,decoder


def change_field(block,key,value,decoder):
    match=re.search(r'"'+re.escape(key)+r'"\s*:\s*',block);assert match
    _,end=decoder.raw_decode(block,match.end())
    return block[:match.end()]+json.dumps(value,ensure_ascii=False)+block[end:]


def start():
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end];nl='\r\n' if '\r\n' in segment else '\n'
    def item_span(sid):
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);return at,finish,item
    anchor='13.6'
    for item in SLICES:
        if item['id']=='14.1.1':anchor='14.1'
        if not any(s['id']==item['id'] for s in project['slices']):
            _,finish,_=item_span(anchor)
            formatted=json.dumps(item,ensure_ascii=False,indent=2).splitlines()
            block=formatted[0]+nl+nl.join('    '+line for line in formatted[1:])
            segment=segment[:finish]+','+nl+'    '+block+segment[finish:]
        anchor=item['id']
    at,finish,item=item_span('14.2');block=segment[at:finish]
    deps=list(dict.fromkeys(item['depends_on']+['14.1.1']))
    segment=segment[:at]+change_field(block,'depends_on',deps,decoder)+segment[finish:]
    segment=change_field(segment,'summary','13.6.1–13.6.3及14.1.1補充診斷啟動，進度30/43。限定2021–2023內的時間前推搜尋，補獨立特徵群、正則化／校準與一種受限非線性對照；2024保持已使用診斷性質，2025測試封存。舊版本與14.1的50／11／423保留，沒有增益仍可採基準進14.2。',decoder)
    segment=change_field(segment,'next_step','完成有停止條件的13.6.1–13.6.3診斷，只有通過的候選才進14.1.1重跑固定484點；未通過則核對並保留原基準。此輪止於14.1.1，不自動開始14.2或15。所有研究模型、原協定與資料留版，畫面由使用者本人驗收。',decoder)
    segment=change_field(segment,'updated_at','2026-11-19',decoder)
    result=text[:begin]+segment+text[end:];result=change_field(result,'updated_at','2026-11-19',decoder)
    parsed=json.loads(result);p=next(x for x in parsed['projects'] if x['id']=='pitcher-decision-support')
    assert len(p['slices'])==43 and sum(s['status']=='done' for s in p['slices'])==30
    assert [x for x in parsed['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'plan_snapshot.json').write_text(json.dumps({'date':'2026-11-19','slices':SLICES,'stop':'14.1.1','test2025':'locked'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Registered bounded patches:30/43, stops at14.1.1',flush=True)


def compact():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==patch.protocol()
    diagnostic=json.loads((OUT/'diagnostics.json').read_text('utf-8'))
    roles=[]
    for role in ['SP','RP']:
        report=json.loads((OUT/f'confirmation_{role}.json').read_text('utf-8'))
        explanation=json.loads((OUT/f'explanation_{role}.json').read_text('utf-8'))
        roles.append({'role':role,'selected':report['selected'],'validationN':report['validation_n'],
            'fitN':report['flow']['fit_n'],'calibrationN':report['flow']['calibration_n'],
            'referenceLL':report['reference']['log_loss'],'referenceBrier':report['reference']['brier'],
            'candidates':[{'config':x['config'],'kind':x['kind'],'group':x['group'],'mode':x['mode'],
                'innerLL':x['mean_LL'],'logLoss':x['metrics']['log_loss'],'brier':x['metrics']['brier'],
                'ece':x['metrics']['ece'],'temperature':x['temperature'],'incrementGate':x['increment_gate'],
                'featureGate':x['matched_feature_gate'],'familyInterval':x['delta_vs_frozen']['role_family97_5'],
                'matchedInterval':x['delta_vs_tuned_family_base']['role_family97_5'],
                'innerStability':x['inner_stability'],'convergenceWarning':x['convergence_warning']}
                for x in report['candidates']],
            'groupReliance':[{'config':x['config'],'group':x['group'],'delta':x['LL_increase']['mean'],
                'interval':x['LL_increase']['role_family97_5']} for x in explanation['contrasts']]})
    impact=json.loads((OUT/'impact_review.json').read_text('utf-8'))
    impact['directionCounts']={key:int(impact['directionCounts'].get(key,0)) for key in ['pool_higher','continue_higher','uncertain_or_unsupported']}
    return {'version':'decision_model_patch_v3','updatedAt':'2026-11-19','completedSlices':['13.6.1','13.6.2','13.6.3','14.1.1'],
        'notStarted':['14.2','15'],'protocolHash':b.digest(OUT/'protocol.json'),'roles':roles,
        'search':{'learnerConfigsPerRole':16,'calibrationModes':2,'innerValidationYears':[2022,2023],
            'candidateFamiliesPerRole':6,'pilotFitCap':patch.PILOT_FIT_CAP,'pilotCalibrationCap':patch.PILOT_CAL_CAP,
            'validation2024Independent':False,'test2025Locked':True},
        'apparentErrors':[{'role':x['role'],'variant':x['variant'],'trainingLL':x['training']['log_loss'],
            'validationLL':x['validation2024']['log_loss'],'gap':x['validation_minus_training_LL']} for x in diagnostic['apparent_errors']],
        'coverage2024':[x for x in diagnostic['distributions'] if x['year']==2024 and x['field'] in ['option_stuff','option_location','quality','physical','command','recent_last1_stuff','pair_n','type_n']],
        'impact':impact,'recommendationAllowed':False,'individualRankingAllowed':False}


def finish():
    summary=compact();evidence='data/sample/petehub_pitcher_decision_model_patch_v3.json'
    b.save_json(ROOT/evidence,summary)
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    selected='、'.join(x['role']+'='+x['selected'] for x in summary['roles'])
    directions=summary['impact']['directionCounts'];counts='／'.join(str(directions.get(k,0)) for k in ['pool_higher','continue_higher','uncertain_or_unsupported'])
    verifications={
        '13.6.1':'2026-11-19：舊baseline／plus／states／all均補實際訓練與2024誤差、逐類校準；2021–2024依角色、現任／閉合歷史及量測模型版本輸出缺值、年齡、n與分位數。候補的歷史Plus不混作本場狀態，current有效球數與歷史有效登板數不作同單位收縮；不只由泛化落差宣稱過擬合或疲勞不存在。',
        '13.6.2':'2026-11-19：線性基準直接加current／recent／batter三群獨立對照，L2 alpha=.001/.01/.1；raw與訓練內溫度校準共同比較。以2021→2022、2021–22→2023時間前推，整場固定SHA樣本fit約30,000、cal至多約10,000，驗證用各年全分母。fit／cal嚴格時間切分且跨界比賽排除，補值／尺度／編碼只fit前段；先選候選再看2024，2025封存。',
        '13.6.3':f'2026-11-19：唯一非線性家族為淺層HGB，7／15葉、60迭代，base／rich比較；連同線性共16 learner設定×raw／溫度×兩個時間窗／角色。每角色凍結6族候選，再移除pilot上限以2021–23前段fit、末段cal、2024完整同分母確認。200次比賽×投手配對、角色內同時97.5%帶及兩角色校正；Brier、ECE、分群傷害、內層年度穩定及收斂共同判定，新增特徵另需勝過同演算法調整基準。固定模型作月別／scope／過去角色內整群置換，保留共同支持控制，僅解釋依賴、非因果。結果{selected}，2024已使用診斷，非獨立測試。',
        '14.1.1':f'2026-11-19：{summary["impact"]["status"]}；原484點、1,072條件池比較及原輸入留版，角色池方向{counts}。只有通過預先門檻才更動第一PA，後續回修訂global baseline；未觀測狀態演化、後續打線時點、active／熱身／醫療可用性及長期成本限制保留。研究方向不等於正式建議，14.2去重／事件對應及15尚未開始。'}
    for sid,description in verifications.items():
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish_at=decoder.raw_decode(segment,at);block=segment[at:finish_at]
        block=change_field(block,'status','done',decoder);block=change_field(block,'verification',description,decoder)
        if sid=='13.6.3':block=change_field(block,'deliverable',item['deliverable'].replace('群組移除診斷','固定模型群組置換診斷（模型依賴，非因果）'),decoder)
        if 'evidence' in item:block=change_field(block,'evidence',evidence,decoder)
        else:
            nl='\r\n' if '\r\n' in block else '\n';block=block[:-1].rstrip() + ','+nl+'      "evidence": '+json.dumps(evidence)+nl+'    }'
        segment=segment[:at]+block+segment[finish_at:]
    segment=change_field(segment,'summary',f'13.6.1–13.6.3及14.1.1完成，進度34/43。受限正則化／校準、獨立特徵群及淺層非線性診斷完成；{selected}。固定484點覆核後方向為{counts}，詳見補丁結果。2024已使用診斷，2025封存；正式推薦及排名關閉。',decoder)
    segment=change_field(segment,'next_step','本輪止於14.1.1，等待使用者確認後才開始14.2持續條件／冷卻去重及官方換投對應；不自動開始15。模型結果、分群區間、scope缺值與有限置換診斷已發布；無增益可保留基準接續，未知可用性與後續狀態演化限制仍保留。畫面由使用者本人驗收。',decoder)
    result=text[:begin]+segment+text[end:];parsed=json.loads(result)
    p=next(x for x in parsed['projects'] if x['id']=='pitcher-decision-support')
    assert len(p['slices'])==43 and sum(x['status']=='done' for x in p['slices'])==34
    assert all(x['status']=='planned' for x in p['slices'] if x['id'] in ['14.2','15'])
    assert [x for x in parsed['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    handoff=ROOT/'docs/NEXT_CHAT_HANDOFF.md';history=handoff.read_text('utf-8')
    heading='## 2026-11-19：模型診斷補丁完成，停在14.1.1（最新）'
    assert heading not in history,'Do not duplicate a completed handoff'
    history=history.replace('## 2026-11-18：13.5、13.6及14.1完成，停在14.1（最新）','## 2026-11-18：13.5、13.6及14.1完成，停在14.1（歷史）',1)
    roles={x['role']:x for x in summary['roles']};rp=next(x for x in roles['RP']['candidates'] if x['config']==roles['RP']['selected'])
    addition=f'''{heading}

使用者授權執行13.6.1–13.6.3及14.1.1，現已完成，Decision Support **34/43**。14.2及15仍planned，本輪不自動接續；2025最終測試封存，2024已使用診斷，不能稱獨立確認。沒有commit／push、開瀏覽器／server或代替畫面驗收。既有dirty worktree與全部舊版本保留。

13.6.1：補舊baseline／plus／states／all的訓練與2024逐類校準，2021–2024角色／scope／量測版本分布與缺值。舊完整群在訓練資料也較基準差，不能只歸因過擬合。current有效球數與closed-history有效登板數不混作同單位；候補歷史不當本場觀測。

13.6.2–3：2021→2022及2021–22→2023選設定，整場固定SHA pilot fit約30,000、cal至多約10,000，全年全分母驗證。base獨立加current／recent／batter，alpha=.001/.01/.1；唯一非線性家族淺層HGB base／rich、7／15葉、60迭代。各16 learner設定×raw／溫度模式×兩窗／角色，先凍結六族，再解除pilot上限用2021–23時間分離fit／cal、2024完整同分母確認。補值／尺度／編碼只fit學習段；跨界比賽排除。兩角色及多候選同時區間、Brier／ECE／分群傷害／年度穩定／收斂共同判定；新增特徵另需勝過同演算法調整基準。

結果：SP保留原基準；tree rich雖比原基準平均分數好，新增特徵相對tree base的同時區間仍跨0。RP選{roles['RP']['selected']}（{rp['mode']}），2024 LL {roles['RP']['referenceLL']:.6f}→{rp['logLoss']:.6f}、Brier {roles['RP']['referenceBrier']:.6f}→{rp['brier']:.6f}，通過預先研究門檻。固定模型按同月／scope／過去角色的整群置換另存，是模型依賴而非疲勞／熟悉度因果；不得將整群增益說成每一項都有獨立貢獻。

14.1.1：{summary['impact']['status']}。原484研究點方向替代池較高／續投較高／不明或不足={counts}；相對v2方向變動{summary['impact']['changedDirections']}點、正反直接翻轉{summary['impact']['directReversals']}點。另有1,072條件池比較。僅RP第一PA改用通過候選，SP第一及全部後續PA維持13.1修訂global matchup；沒有把未知狀態固定投到局末。256共同路徑、8次同一全域game計數重抽樣，新角色固定中央前處理／先驗、時序分離的校準再估溫度；中央快取與重複列直接推論差0。原可用性、後續打線時點、截尾／外推與長期成本限制不變，推薦／個別排名關閉。這些是研究比較點，不是獨立預警或正確率；14.2才做去重／事件對應。

新資料 `data/research/decision_model_diagnostics_v3/`、`data/research/decision_action_sensitivity_v3/`，小型證據 `data/sample/petehub_pitcher_decision_model_patch_v3.json`，source-only驗證結果 `data/sample/petehub_pitcher_decision_model_patch_audit_v3.json`。新scripts：build_decision_model_patch.py、run_decision_model_patch_impact.py、export_decision_model_patch.py、audit_decision_model_patch.py。原2025／2026預測仍是v2，不冒充新模型已上線。Lab `/lab/decision-support#model-patch` 新增候選／訓練誤差／置換／coverage摘要；下方原版本保留歷史。畫面與操作由使用者本人驗收。

'''
    first='## ';at=history.index(first)
    handoff.write_text(history[:at]+addition+history[at:],encoding='utf-8')
    print('Published bounded patches:34/43, stops at14.1.1',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','finish'])
    globals()[parser.parse_args().stage]()
