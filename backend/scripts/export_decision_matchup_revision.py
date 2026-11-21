"""Publish13.5/13.6/14.1 results and surgical authoritative tracker changes."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_action_revision as a
from scripts import audit_decision_familiarity as diagnostic

u,h,b=a.u,a.u.h,a.b


def read(path):return json.loads(path.read_text('utf-8'))


def compact():
    batter=read(h.OUT/'summary.json');ablation=read(u.OUT/'validation.json');action=read(a.OUT/'summary.json')
    year=next(y for y in batter['years'] if y['year']==2024)
    roles_at_entry=pd.read_parquet(u.OUT/'features_2024.parquet',columns=['request_id','forecast_role'])
    attack=pd.read_parquet(h.OUT/'observed_attack_2024.parquet',columns=['request_id','game3_pa_n','pair_game3_pa_n','pair_n','arsenal_type','type_n','affinity_whiff'])
    attack=roles_at_entry.merge(attack,on='request_id',validate='one_to_one')
    coverage=[]
    for role,g in attack.groupby('forecast_role'):
        coverage.append({'role':role,'n':len(g),'same_game_pa':int(g.game3_pa_n.gt(0).sum()),
            'same_pitcher_pa':int(g.pair_game3_pa_n.gt(0).sum()),'historical_pair':int(g.pair_n.gt(0).sum()),
            'known_type':int(g.arsenal_type.ne('unknown').sum()),'type_own_pa':int(g.type_n.gt(0).sum()),'affinity_whiff':int(g.affinity_whiff.notna().sum())})
    clean=read(diagnostic.OUT/'summary.json')
    assert read(diagnostic.OUT/'protocol.json')==diagnostic.protocol()
    revised_batter={**batter,'associations':clean,'diagnostic_revision':'familiarity_identity_clean_v2',
        'initial_association_report':'data/research/decision_batter_matchup_v1/familiarity_associations.json'}
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_5_v2.json',revised_batter)
    changes=sum(1 for panel in clean['panels'] for row in panel['validation_2024'] if row['supported'] and (row['low95']>0 or row['high95']<0))
    roles=[]
    for role,report in ablation['roles'].items():
        base=report['results']['baseline'];selected=report['results'][report['selected']]
        rows=[]
        for name,value in report['results'].items():
            rows.append({'variant':name,'candidate':name in u.CUMULATIVE,'logLoss':value['metrics']['log_loss'],'brier':value['metrics']['brier'],
                'delta':value.get('delta_vs_baseline',{}).get('mean',0.),
                'familyInterval':value.get('delta_vs_baseline',{}).get('role_family97_5',[0.,0.]),
                'incrementGate':value.get('increment_gate',False),'convergenceWarning':value['convergence_warning']})
        roles.append({'role':role,'trainingN':report['training_n'],'validationN':report['validation_n'],
            'selected':report['selected'],'baselineLL':base['metrics']['log_loss'],'baselineBrier':base['metrics']['brier'],
            'selectedLL':selected['metrics']['log_loss'],'selectedBrier':selected['metrics']['brier'],
            'rows':rows,'supportedN':report['supported_sensitivity']['validation_n'],
            'supportedAllIncrement':report['supported_sensitivity']['increment_gate'],
            'loadContrasts':[{'variant':name,**value} for name,value in report['load_contrasts_vs_extended'].items()]})
    directions=['pool_higher','continue_higher','uncertain_or_unsupported']
    return {'version':'decision_matchup_action_revision_v2','completedSlices':['13.5','13.6','14.1'],
        'notStarted':['14.2','15'],'coverage2024':coverage,'featureRows2024':year['rows'],
        'associationPanels':len(clean['panels']),'associationSupportedChanges2024':changes,'diagnosticFlow':clean['flow'],
        'roles':roles,'action':{
            'originalCases':action['original_cases'],'modeledCases':action['modeled_role_cases'],'supported':action['role_supported'],
            'conditionalComparisons':action['conditional_pool_comparisons'],'paths':action['paths'],'bootstrapModels':action['bootstrap_models'],
            'firstModels':[{'role':role,'model':name} for role,name in action['first_PA_models'].items()],
            'directions':[{'direction':d,'old':action['old_direction_counts'].get(d,0),'new':action['role_direction_counts'].get(d,0)} for d in directions],
            'directionTransitions':[{'old':old,'new':new,'n':n} for old,row in action['old_new_direction_crosstab'].items() for new,n in row.items()],
            'poolSummary':action['pool_summary'],'valueChanges':action['role_value_delta_changes'],'examples':action['examples'],
            'futureLineupVerified':0,'futureLineupFallback':484,'recommendationAllowed':False},
        'protocols':{name:b.digest(folder/'protocol.json') for name,folder in [('batter',h.OUT),('ablation',u.OUT),('action',a.OUT)]}}


def update_tracker(summary):
    path=b.ROOT/'docs/PROJECT_TRACKER.json'
    with path.open('r',encoding='utf-8',newline='') as stream:text=stream.read()
    decoder=json.JSONDecoder();position=text.index('"id": "pitcher-decision-support"');start=text.rfind('{',0,position)
    project,end=decoder.raw_decode(text,start);segment=text[start:end]
    def replace(block,old,new):
        token=json.dumps(old,ensure_ascii=False);assert block.count(token)==1
        return block.replace(token,json.dumps(new,ensure_ascii=False),1)
    selected='、'.join(f"{v['role']}={v['selected']}" for v in summary['roles'])
    directions=summary['action']['directions'];counts='／'.join(str(x['new']) for x in directions)
    values={
        'summary':f'13.5、13.6及14.1完成，進度30/39。六季打者前序出棒／掌握、分開本場與歷史相性資料已建立；同分母SP／RP各25設定消融，2024診斷選擇{selected}。原484個固定半局比較重跑，角色池較高／續投較高／不明或不足為{counts}。條件手別／球路池另報；不以未知未來狀態或事後打線冒充決策資料，正式推薦關閉。',
        'next_step':'本輪止於14.1，等待使用者指示14.2研究預警持續條件／冷卻去重及官方換投對應；未開始15。13.5熟悉度為條件關聯，13.6為2024診斷選模；2025最終測試仍保留。14.1只有第一PA可用選定狀態特徵，後續回修正基準，未確認後續打線用聯盟池；名單、法定、熱身、醫療與人工可用性分開，無個別推薦。新頁面由使用者驗收。'}
    for key,value in values.items():segment=replace(segment,project[key],value)
    descriptions={
        '13.5':('data/sample/petehub_pitcher_decision_slice13_5_v2.json',
            f'2026-11-18：六季824,462個實際actor請求完成；同場打者last1／2／3、同投手／其他投手／全隊last3與歷史BvP／粗球路類型分開。收到球種占比、球種出棒率、出棒中球種占比、接觸／揮空／界外／場內／有效EV保留各自分母。球路類型取此前觀測角色last3閉合登板，BvP20→類型50→過去打者能力回退，family依有效分母收縮到嚴格過去手別／球類參考；無同季整季tag。排除110個多打者／身分衝突歷史PA，原試驗完整保留；描述曲線另以乾淨PA交集凍結獨立修訂。12個描述面板2024有支持且區間排除0的區段{summary["associationSupportedChanges2024"]}個，不稱心理鎖定或熟悉度因果；未讀2025／2026結果指標。'),
        '13.6':('data/sample/petehub_pitcher_decision_slice13_6_v2.json',
            f'2026-11-18：相同2024 n=137,699，實際actor SP／RP分開、各25設定；共同缺值支持／年齡／scope控制、訓練內補值標準化及固定L2。逐組／leave-one-out／純72與120小時、連投、季內序號比較；派生risk／交互項隨來源移除，type移除時BvP改回打者先驗。200次比賽×投手配對重抽樣，角色內多設定同時97.5%帶、兩角色校正，另報校準、current／incoming分群與完整訊號支持敏感度。診斷選擇{selected}，無增益保留基準；原決策時點前推risk，無接任者吃到被換下者狀態，2025／2026僅凍結機率。'),
        '14.1':('data/sample/petehub_pitcher_decision_slice14_1_v2.json',
            f'2026-11-18：原484個研究比較完整保留，修正負荷重跑；角色池方向{counts}，手別及有過去類型支持的至少兩人條件池另報。第一PA接13.6通過設定或13.1修訂基準，後續一律明示基準，未外推未知球質／狀態。共同256路徑、8次共同比賽群聚分類器重訓、MC95／中央80模型範圍與設限／外推／稀有轉移分列；與原55／12／417方向及xWPA／xRE24差值區間逐點對照。存檔打序無獨立公開時點證明，484均明示原2023年底聯盟池回退；已知首打者保留。名義合法／game名單與active／熱身／醫療／人工確認分開，另列預計用球／BF及剩餘名義RP，無長期資源成本加分；14.2、15未開始，推薦／排名關閉。')}
    for sid,(evidence,description) in descriptions.items():
        if sid=='13.6':description+=' 角色分層採現任本次角色或接任RP，前次SP不當作本次SP；跨角色歷史狀態／Plus不當RP進場先驗。前兩輪未完成訓練與原協定／源碼保留，修正角色及來源後重跑，選模門檻不變。'
        match=re.search(r'(?m)^ {6}"id": '+re.escape(json.dumps(sid))+r',\r?$',segment);assert match
        begin=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,begin);block=segment[begin:finish]
        for key,value in [('status','done'),('verification',description)]:block=replace(block,item[key],value)
        if 'evidence' in item:block=replace(block,item['evidence'],evidence)
        else:
            token='      "verification": '+json.dumps(description,ensure_ascii=False)+',';assert token in block
            nl='\r\n' if '\r\n' in block else '\n'
            block=block.replace(token,token+nl+'      "evidence": '+json.dumps(evidence)+',',1)
        segment=segment[:begin]+block+segment[finish:]
    result=text[:start]+segment+text[end:];p=next(x for x in json.loads(result)['projects'] if x['id']=='pitcher-decision-support')
    assert len(p['slices'])==39 and sum(x['status']=='done' for x in p['slices'])==30
    assert all(x['status']=='planned' for x in p['slices'] if x['id'] in ['14.2','15'])
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print('Authority updated:30/39; stops at14.1',flush=True)


if __name__=='__main__':
    summary=compact();b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_matchup_revision_v2.json',summary)
    update_tracker(summary)
