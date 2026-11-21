"""14.2.1 multi-signal display contract and workflow; no calibration or new alerts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_alert_research as q
from scripts.export_decision_model_patch import load_project,change_field

ROOT=q.b.ROOT
OUT=ROOT/'data/research/decision_signal_lights_v1'
SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v1.json'
SLICES=[
 {'id':'14.2.1','phase':'validation','label':'Slice 14.2.1 · 多原因燈與景氣式綜合燈契約／介面','status':'in_progress','depends_on':['14.2'],
  'deliverable':'A球質、B位置／控球代理、C對手掌握、D負荷四群各計一票；五級綜合狀態與資料不足灰燈，分開替代收益、名義合法、實際可用性及原因持續條件。真實11例與互動規則示範分開。',
  'verification':'2026-11-19使用者授權多燈組成綜合狀態及調整後續流程；尚未校準的真實原因燈維持灰色，不重新產生14.2預警。',
  'acceptance':'單群不重複計票，灰燈不補0或正常；總燈不單獨觸發換投。規則、資料與型別檢查完成；畫面人工驗收另外保留pending，不宣稱模型或換投有效。'},
 {'id':'14.2.2','phase':'validation','label':'Slice 14.2.2 · 個人正常進程、局間恢復與狀態去雜訊','status':'planned','depends_on':['14.2.1','13.4'],
  'deliverable':'以嚴格過去個人／同球種參考，建模累積球數、單局負荷、局間時間及角色的正常進程，分開水準／預期下降／異常殘差；研究觀測成熟、單一受限平滑、解除及跨局更新，保留累積負荷。',
  'verification':'Pending','acceptance':'不預設每場必下降，不將35球支持門檻當疲勞切點；未知／超範圍灰燈。基準／尺度／視窗只fit訓練時間窗，不能借未來局間恢復；下一段未觀測保留設限，正常下降仍進表現預測。'},
 {'id':'14.2.3','phase':'validation','label':'Slice 14.2.3 · 分燈校準、資訊重複與SP／RP增益驗證','status':'planned','depends_on':['14.2.2','13.6.3'],
  'deliverable':'校準A–D灰／綠／黃／紅，分SP／RP檢查原始支持、群間相關、缺值與額外增益；曝光／gmLI作情境，球速與Stuff不重複計票。綜合0–8及兩紅規則與有限替代設定作訓練內對照；需要影響xWPA的訊號另做角色模型增益。',
  'verification':'Pending','acceptance':'等權分數與兩紅只是展示候選，不是已驗證權重。2021–2023時間前推選設定、2024已用診斷、2025封存；控制相同分母與校準／群聚區間，不能只用教練對應率選燈或用前端門檻冒充模型納入疲勞。'},
 {'id':'14.2.4','phase':'validation','label':'Slice 14.2.4 · 多燈事件、恢復重啟與固定時序覆核','status':'planned','depends_on':['14.2.3','14.2'],
  'deliverable':'依新凍結分燈模型研究狀態事件，分開戰術池比較與狀態驅動候選；校準持續／解除／新事件重新觸發及冷卻，處理同登板首次過早吞掉後續訊號。按完整時序報分燈／組合支持、提醒負擔、恢復與預測表現、官方對應與拒絕原因。',
  'verification':'Pending','acceptance':'保留原14.2的11預警／0配對與原窗口，不為提高配對率覆寫。重疊球窗不是獨立證據，監控需評估序列提醒負擔。可用性未知仍阻擋正式推薦；通過此研究覆核後再進15重疊／選擇偏差，合理性及效益仍留15–18。'}]


def update_plan(done=False):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    def span(sid):
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);return at,finish,item
    anchor='14.2';nl='\r\n' if '\r\n' in segment else '\n'
    for item in SLICES:
        if not any(x['id']==item['id'] for x in project['slices']):
            _,finish,_=span(anchor);lines=json.dumps(item,ensure_ascii=False,indent=2).splitlines()
            block=lines[0]+nl+nl.join('    '+line for line in lines[1:])
            segment=segment[:finish]+','+nl+'    '+block+segment[finish:]
        anchor=item['id']
    for sid in ['15','20']:
        at,finish,item=span(sid);block=segment[at:finish]
        block=change_field(block,'depends_on',list(dict.fromkeys(item['depends_on']+['14.2.4'])),decoder)
        if sid=='20':block=change_field(block,'deliverable','接已驗證的14.2.4分燈／綜合狀態契約至正式狀態與決策雙層燈號，保留來源版本、灰燈、解除與冷卻；整合個人頁及In game，不另造一套總分。',decoder)
        segment=segment[:at]+block+segment[finish:]
    if done:
        at,finish,item=span('14.2.1');block=segment[at:finish]
        block=change_field(block,'status','done',decoder)
        block=change_field(block,'verification','2026-11-19：完成景氣式0–8研究展示、四群原因燈、分開的收益／合法／可用／持續條件；讀原11則實際研究例，7則未達35球觀測支持，全部原因燈尚未校準而維持灰。互動示範明確標記且永不開啟正式推薦。純規則／資料／型別檢查完成，畫面仍待使用者驗收；未重訓、未改原11／0結果、未開始14.2.2或15。',decoder)
        if 'evidence' not in item:block=block[:-1].rstrip()+','+nl+'      "evidence": '+json.dumps(str(SAMPLE.relative_to(ROOT)).replace('\\','/'))+nl+'    }'
        segment=segment[:at]+block+segment[finish:]
    progress='36/47' if done else '35/47'
    for key,value in [
        ('summary',f'多原因燈與景氣式綜合狀態介面'+('完成' if done else '啟動')+f'，進度{progress}（新增4個15前子項）。A–D四群每群一票，實際未校準燈保留灰；分開收益／合法／可用／持續條件及互動示範。原32場14.2的11研究預警／0配對留版，沒有正式換投建議。'),
        ('next_step','本輪止於14.2.1介面與規則契約，畫面由使用者驗收。接續順序14.2.2個人正常進程／局間與去雜訊→14.2.3分燈校準／相關與角色增益→14.2.4事件恢復重啟／時序覆核→15重疊與選擇偏差。尚未開始這些研究；0–8與兩紅門檻是待驗證候選，2025測試繼續封存。'),
        ('updated_at','2026-11-19')]:segment=change_field(segment,key,value,decoder)
    result=text[:begin]+segment+text[end:];result=change_field(result,'updated_at','2026-11-19',decoder)
    parsed=json.loads(result);updated=next(x for x in parsed['projects'] if x['id']=='pitcher-decision-support')
    assert len(updated['slices'])==47 and sum(x['status']=='done' for x in updated['slices'])==(36 if done else 35)
    assert all(x['status']=='planned' for x in updated['slices'] if x['id'] in ['14.2.2','14.2.3','14.2.4','15','20'])
    assert [x for x in parsed['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print(f'Multi-light roadmap {progress}; stop14.2.1',flush=True)


def number(value):return float(value) if pd.notna(value) and np.isfinite(value) else None


def metric(row,name,label,unit='',decimals=1):
    value=number(row[name]);return label+'：'+('尚無有效觀測' if value is None else f'{value:,.{decimals}f}{unit}')


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    alerts=pd.read_parquet(q.OUT/'alerts.parquet');full=pd.read_parquet(q.OUT/'full_options.parquet')
    current=full[full.is_current].set_index('decision_id');cases=[]
    names={row['decision_id']:row['pitcher_name'] for row in q.read(q.OUT/'summary.json')['alerts']}
    for alert in alerts.sort_values(['game_pk','team_id','defensive_ordinal']).itertuples():
        row=current.loc[alert.decision_id];mature=35<=row.live_support<=100
        def light(sid,title,reason,evidence,support):return {'id':sid,'title':title,'state':'gray','calibrated':False,'supportKnown':bool(support),'reason':reason,'evidence':evidence}
        lights=[
            light('A','球質下降','個人正常進程與異常下降尚未校準' if mature else '未達現行35球觀測支持；無疲勞判讀',[
                metric(row,'option_stuff','Stuff水準（研究基準100）'),metric(row,'personal_delta_stuff','同球種個人參考差','點'),metric(row,'live_physical_dev','Physical相對100','點')],mature and pd.notna(row.personal_delta_stuff)),
            light('B','位置／控球代理','位置與Command尚未校準為獨立異常證據' if mature else '短前綴觀測，三項狀態未成熟',[
                metric(row,'option_location','Location水準（研究基準100）'),metric(row,'personal_delta_location','個人位置參考差','點'),metric(row,'live_command_dev','Command相對100','點')],mature and pd.notna(row.live_command_dev)),
            light('C','對手掌握提高','有前序資料，但提高幅度／對手調整尚未校準' if row.game3_pa_n>0 else '當前打者本場尚無前序PA，不能判斷掌握提升',[
                metric(row,'game3_pa_n','當前打者前序PA','',0),metric(row,'pair_game3_pa_n','其中對現任PA','',0),metric(row,'team3_pa_n','全隊對現任近期PA（不同scope）','',0)],row.game3_pa_n>0),
            light('D','負荷／恢復壓力','負荷已有觀測，個人正常範圍與局間恢復仍待校準',[
                metric(row,'option_game_pitches','本場球數','球',0),metric(row,'prior_games_pitches_3d','其他比賽近72h用球','球',0),metric(row,'prior_games_pitches_5d','其他比賽近120h用球','球',0),metric(row,'consecutive_days','進場前連續登板日','日',0)],row.lookback_14d_complete)
        ]
        cases.append({'id':alert.decision_id,'label':f'{alert.game_pk} · {alert.inning}{"上" if alert.half=="top" else "下"} · {names[alert.decision_id]}',
            'gamePk':int(alert.game_pk),'decisionId':alert.decision_id,'pitcherName':names[alert.decision_id],
            'role':alert.role,'inning':int(alert.inning),'half':alert.half,'pitches':float(row.option_game_pitches),'observationMature':bool(mature),
            'lights':lights,'gates':{'value':'pass','legal':'pass','availability':'unknown','statePersistence':'unknown'},
            'valueNote':f'舊14.2收益門檻已過：ΔxWPA {alert.wpa_delta*100:+.2f}pp，ΔxRE24 {alert.re24_delta:+.3f}分；這是替代池比較，不是疲勞證據。',
            'matchupNote':f'首位打者已知，歷史BvP支持n={row.pair_n:.0f}；類型支持n={row.type_n:.0f}。相性未校準為分燈票數，後續打線仍用聯盟池。',
            'li':number(alert.research_pa_li)})
    data={'version':'decision_signal_lights_display_v1','updatedAt':'2026-11-19','mode':'observed','cases':cases,
        'counts':{'cases':len(cases),'belowObservationMinimum':sum(c['pitches']<35 for c in cases),'matureObservation':sum(c['observationMature'] for c in cases)},
        'scoreStatus':'0–8等權、五級與兩紅規則為展示設計；14.2.2–14.2.4完成前不稱已校準總分。灰不補0，gmLI／相性不計票，收益連續不當原因持續。',
        'recommendationAllowed':False}
    sources=[q.OUT/name for name in ['alerts.parquet','full_options.parquet','summary.json','manifest.json']]
    # Verify the selected existing inputs against the retained14.2 manifest.
    retained={entry['path']:entry['sha256'] for entry in q.read(q.OUT/'manifest.json')['files']}
    for path in sources:
        if path.name!='manifest.json':assert q.b.digest(path)==retained[path.name]
    q.b.save_json(SAMPLE,data);q.b.save_json(OUT/'prototype.json',data)
    q.b.save_json(OUT/'sources.json',{'inputs':{str(path.relative_to(ROOT)):q.b.digest(path) for path in sources},'builder_sha256':q.b.digest(Path(__file__)),
        'display_sources':{str(path.relative_to(ROOT)):q.b.digest(path) for path in [ROOT/'frontend/utils/decisionSignalLights.ts',ROOT/'frontend/components/charts/DecisionSignalLights.vue',ROOT/'frontend/scripts/test-decision-signal-lights.cjs']},
        'models_retrained':False,'new_alerts_computed':False,'test2025_outcomes_examined':False,'visual_acceptance':'pending user'})
    print(f'Multi-light observed adapter: {len(cases)} retained examples, all uncalibrated causes gray',flush=True)


def finish():
    update_plan(True)
    data=q.read(SAMPLE)
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8')
    heading='## 2026-11-19：多原因燈與景氣式綜合狀態14.2.1完成（最新）'
    assert heading not in text
    text=text.replace('## 2026-11-19：Slice14.2完整時序預警與官方換投對應完成（最新）','## 2026-11-19：Slice14.2完整時序預警與官方換投對應完成（歷史）',1)
    paragraph=f'''{heading}

使用者要求把多個原因燈組成景氣式總燈並調整後續流程。本輪完成14.2.1契約／介面，新增4個前置子項，進度 **36/47**（不是模型效果下降或新增研究完成數）。14.2.2／14.2.3／14.2.4及15仍planned，不自動訓練／校準或進15；2025測試封存。未commit／push、未開瀏覽器／server／截圖，畫面由使用者本人驗收。保留全部既有dirty worktree及969份先前凍結檔案。

新入口 `/lab/decision-support#signal-lights`：A球質、B位置／控球代理、C對手掌握、D負荷／恢復每群一票；綠0／黃1／紅2，0–8研究展示分數，0綠、1–2黃綠、3–4黃、5–6橙、7–8紅。任一灰不補0、不重算分母，總分null／總燈灰，仍列已知異常群。未校準真實訊號一律灰，不能因raw Stuff或用球數直接亮紅。

換投評估是獨立條件：展示暫定四群皆可判讀、至少兩紅且包含A或B、原因持續成立，並且替代收益／名義合法／實際可用性通過；高總分不能略過。gmLI／相性作脈絡不計票，收益的兩點連續不冒充原因的兩段持續。綜合狀態紅不直接換投，綠不保證健康。這些分數／門檻尚未校準，demo或未來研究候選也永不將recommendationAllowed改true。

資料由原14.2的{data['counts']['cases']}則預警快照轉接，其中{data['counts']['belowObservationMinimum']}則16–33球未達現行35球支持；35是觀測支持不是疲勞切點。真實11例的A–D全部尚未校準為灰，保留原始數值與缺值／資料年齡scope，不偽造新燈色或新配對。可另外切到「互動規則示範」，手動調四燈／四個條件或選預設情境，始終標明示範、不代表真實比賽。原32場11預警／0配對完全留版。

後續順序：14.2.2用訓練內個人同球種／累積與單局球數／局間時間建立正常進程、異常殘差、觀測成熟與受限平滑；正常下降仍進表現預測、累積負荷不跨局歸零，不能用未來恢復。14.2.3分SP／RP校準分燈、群間相關與增益、有限組合設定；需影響xWPA者另做角色增益，不用前端門檻假裝SP已納入疲勞。14.2.4研究解除／新事件重啟及冷卻，完整序列評估提醒負擔與恢復／預測／對應，原14.2不覆寫。15加入14.2.4依賴，20正式雙層燈號消費已驗證契約，不重造另一套分數；合理性／策略價值與封存測試仍留15–18。

新增 `frontend/components/charts/DecisionSignalLights.vue`、純規則 `frontend/utils/decisionSignalLights.ts`、契約測試 `frontend/scripts/test-decision-signal-lights.cjs`、資料／流程publisher `backend/scripts/export_decision_signal_lights.py`。小型來源快照 `data/sample/petehub_pitcher_decision_signal_lights_v1.json`，版本資料及來源SHA在 `data/research/decision_signal_lights_v1/`；不新增API、不重訓、不重新計算研究預警。source-only檢查不等於畫面驗收。

'''
    at=text.index('## ');path.write_text(text[:at]+paragraph+text[at:],encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','build','finish']);stage=parser.parse_args().stage
    if stage=='build':build()
    elif stage=='finish':finish()
    else:update_plan(False)
