"""15.3 authority and research evidence;15.4 remains planned."""
from pathlib import Path
import argparse
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_rp_targets as q
from scripts.export_decision_model_patch import load_project,change_field

ROOT=q.ROOT;SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_rp_targets_v1.json'


def update(done=False):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    match=re.search(r'"id"\s*:\s*"15.3"\s*,',segment);at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at)
    block=change_field(segment[at:finish],'status','done' if done else 'in_progress',decoder)
    block=change_field(block,'verification','2026-11-21：RP共同時點、進場前歷史使用型態、下一PA／完整十球目標、受限母體與觀測機制敏感度研究'+('完成；詳見新證據，15.4未開始。' if done else '進行中；原結果留版，2025封存。'),decoder)
    if done and 'evidence' not in item:block=block[:-1].rstrip()+',\n      "evidence": "data/sample/petehub_pitcher_decision_rp_targets_v1.json"\n    }'
    segment=segment[:at]+block+segment[finish:]
    for key,value in [('updated_at','2026-11-21'),('summary',('15.3 RP觀測目標與受限母體研究完成43/51。' if done else '15.3 RP目標／母體研究進行中42/51。')+'下一PA與十球為不同目標，歷史型態只用進場前資料；原模型／燈號留版，15.4未開始、2025封存。'),
            ('next_step','完成15.3目標可觀測性、歷史型態受限母體與缺失敏感度後，再另行授權15.4凍結／前推覆核；沒有可比性及效益支持不進16或開啟推薦，畫面使用者驗收。')]:segment=change_field(segment,key,value,decoder)
    result=text[:begin]+segment+text[end:]
    assert [x for x in json.loads(result)['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print('15.3 authority '+('43/51 complete' if done else '42/51 in progress'),flush=True)


def guard():
    assert not list(q.OUT.glob('*2024*joblib')) and not list(q.OUT.glob('scored_2024*'))
    paths=[q.OUT/'protocol.json']+[q.OUT/f'fit_{year}_{phase}.json' for year in [2022,2023] for phase in q.base.PHASES]
    value={'2024_outputs_present_before_confirmation':False,'input_sha256':{p.name:q.b.digest(p) for p in paths},
        'selection':'none: targets, models and primary within-inning short-history population fixed before all fitting; revision2 corrects raw event mapping after first2024 diagnostics, exact first attempt archived.2024 diagnostic only, not fresh confirmation'}
    path=q.OUT/'confirmation_guard.json'
    if path.exists():assert q.read(path)==value
    q.save('confirmation_guard.json',value)
    print('15.3 fixed design and inner artifacts guarded before2024',flush=True)


def build():
    d=q.read(q.OUT/'summary.json')
    def compact(value):
        if isinstance(value,dict):
            result={k:compact(v) for k,v in value.items() if k!='balance'}
            if 'balance' in value:result['worst_balance']=sorted(value['balance'],key=lambda x:abs(x['after']),reverse=True)[:5]
            return result
        if isinstance(value,list):return [compact(x) for x in value]
        return value
    result={k:compact(v) for k,v in d.items() if k!='balance'}
    result['balance_results']=compact(d['balance'])
    fits=[q.read(q.OUT/f'fit_{year}_{phase}.json') for year in [2022,2023,2024] for phase in q.base.PHASES]
    kinds=[t['kind'] for f in fits for t in f['tasks']]
    result['flow']={'progress':'43/51','task_artifacts':len(kinds),'hgb':kinds.count('hgb'),'constant':kinds.count('constant'),
        'boundaries':sum(p['boundaries'] for p in d['preparation']),'monitor_units':sum(p['monitor_units'] for p in d['preparation'])}
    result['fit_tasks']=[{'year':f['year'],'phase':f['phase'],'task':t['task'],'kind':t['kind']} for f in fits for t in f['tasks']]
    result['updatedAt']='2026-11-21'
    result['methodNotes']=[
        '短型／延長型是進場前最近10次已結束RP登板的歷史中位數：至少5次；BF≤4且球數≤20為短型，其餘為延長型；未知仍保留。不按本場最後登板長度挑樣本。',
        '主要比較母體預先指定為局中短型歷史RP；全體、歷史已知、延長型及短型相對負荷≤1.5是固定敏感度，不用2024挑過關者。短負荷版會排除高負荷局面，不能代表所有疲勞情境。',
        '同一已知球塊只留第一個監測邊界，尚無完整球塊時每登板保留一個起始機會；同時報全部PA邊界覆蓋。重複球塊／同投手／同場資料不是獨立樣本。',
        '下一PA是原投手下一個完整自然打席的非出局結果；未來十球是完整固定十球塊的研究殘差偏離。兩者意義不同，不比較跨目標Brier，也不稱體能下降或換投效益。',
        '觀測模型包含有／無後續標籤；結果模型只用已觀測者。每項只與自身過去常數基準比較；稀少任務保留預先定義常數退路，沒有小樣本硬擬合。',
        '換下者兩任務仍未知，未借用接任投手結果。觀測權重依賴未能驗證的缺失假設；最壞界限及缺失者odds×0.5／1／2僅為總體假設情境，不補成訓練標籤。',
        '新舊行動模型在同一受限母體、相同豐富平衡欄位（含新增歷史）對照。最大SMD≤0.1、兩臂ESS≥500及ECE≤0.03只作診斷，不是策略有效證明。',
        '2022／23／24時間前推，整場fit與cal分隔；2024前鎖定協定及內層產物。2024先前已作診斷，不能稱全新獨立測試；2025維持封存，15.4未開始。']
    result['methodNotes'].append('首次下一PA將來源事件誤當分組名稱，已知標籤全為1；整批source／protocol／資料／30任務產物／2024診斷封存attempt0_label_mapping。revision2按既有preparation映射修正、加測試後全重跑；沒有改母體、特徵或門檻挑2024。')
    q.save('evidence.json',result);q.b.save_json(SAMPLE,result)
    print('15.3 evidence published; no recommendation promotion',flush=True)


def handoff():
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8');heading='## 2026-11-21：15.3 RP目標與受限母體研究完成（最新）'
    if heading in text:return
    d=q.read(SAMPLE);p=next(x for x in d['primary2024'] if x['model']=='history_enriched')
    prep=next(x for x in d['preparation'] if x['year']==2024)
    tasks=[x for x in d['task_results'] if x['year']==2024 and x['phase']=='within_inning' and x['subset']=='short_profile']
    section=f'''{heading}

使用者本輪只要求完成15.3，現 **43/51**；15.4／16–21維持planned。2025封存，沒有新推薦、改燈號、重跑xWPA、commit/push或瀏覽器／畫面驗收。15.1–15.2及更早協定／資料／模型／源碼留版。

進場前最近10次已結束RP登板，至少5次，歷史BF中位≤4且球數中位≤20為short_profile，其餘extended_profile，不足history_unknown。全體、已知歷史、短型、延長型、短型相對BF及球數≤1.5共5固定母體；主要局中short_profile在擬合前指定，不按2024或本場最終登板長度挑選。所有特徵沿15.1共同截點；不借用截點後打者或較晚狀態。

原投手next_pa目標：下一個完整自然PA的非出局（K／other_out為0，其他來源自然類別為1），同一實體投手且開始不早於anchor，並非xWPA或純安打率。future_ten：第一個完整位於anchor後的固定十球塊，預期編號ceil(當前session已投球數/10)，不跳過未量測的塊找較晚完整者；Stuff殘差≤-5或速度≤-.5或Location≤-5。缺任一量測則未知，不是已確認生理疲勞。換下者兩任務均未知，不能接接任者成績。監測為同已知球塊首個邊界，無完整塊時每登板首個起始機會；另報全部邊界與唯一未來球塊，不能把重複預測當獨立證據。

2024 RP全部共同截點邊界{prep['boundaries']:,}、配對監測{prep['monitor_units']:,}。主要局中短型監測：{'; '.join(x['target']+' '+str(x['observed'])+'/'+str(x['n'])+' ('+format(x['rate']*100,'.2f')+'%)' for x in tasks)}。兩種標籤含義不同，只與各自過去常數基準比較，不能跨標籤Brier判斷改善。

固定HGB自然抽樣及late-time Platt，兩phase×3前推年×(action、2觀測、2條件結果)共{d['flow']['task_artifacts']}任務產物，其中HGB{d['flow']['hgb']}、預先稀少任務常數退路{d['flow']['constant']}。每個任務按整場時間80/20 fit/cal，嚴格早於次年驗證。conditional outcome只用R=1；observation用全部監測。protocol與confirmation_guard均在2024前留版，沒有超參數或母體挑選；2024已被前輪診斷使用，不稱全新獨立測試。

revision2修正紀錄：首次將來源raw事件錯當分組名稱，已知nextPA標籤全為1；source／protocol／資料／30任務產物／2024診斷完整封存attempt0_label_mapping。新增原始事件映射測試、按既有preparation事件與出局數規則修正後全重跑，未改母體、特徵、模型或門檻。修正版guard早於修正版2024，但2024已被診斷，不能稱獨立確認。

主要2024局中短型歷史、overlap，新增歷史模型最大絕對SMD={p['max_abs_smd_after']:.6f}，換投ESS={p['change']['ess']:.1f}、續投ESS={p['continue']['ess']:.1f}、ECE={p['action_metrics']['ece']:.6f}，完整診斷門檻{'通過' if p['full_gate'] else '未通過'}。新舊15.2行動模型在同一subset、同一豐富基準含新增歷史欄位對照；完整矩陣有2022/23/24、5母體、2phase、2模型、2權重，不依2024改選或宣稱因果策略有效。

缺失敏感度包含g≥.1的逆觀測加權（caps無／10／20／50）、最壞情況界限、未知者預測odds×.5／1／2總體情境。所有原未知Y仍NaN，情境數值不回填、不進訓練，不能用觀測模型宣稱已解決非隨機缺失或換下後反事實。資料／模型證據`data/research/decision_rp_targets_v1/`，摘要`data/sample/petehub_pitcher_decision_rp_targets_v1.json`，source audit另存。Lab新增#rp-target-research，手動畫面驗收由使用者進行。

下一步15.4需據固定母體、平衡／校準／ESS與拒絕原因作凍結覆核，明定16策略與終點；工作完成不等於獲准啟用推薦。沒有支持時維持研究／未知。重跑先核對舊manifest與新protocol：build_decision_rp_targets.py prepare --year2021..24→freeze→train2022/23各phase→export_decision_rp_targets.py guard→train2024→evaluate→export build/finish→export_pitcher_decision_plan.py→sync_project_tracker.py→manifest→audit_decision_rp_targets.py。不可靜默覆寫已凍結研究產物。

'''
    at=text.index('## ');path.write_text(text[:at]+section+text[at:],encoding='utf-8')


def manifest():
    sources=[Path(__file__),Path(q.__file__),ROOT/'backend/scripts/audit_decision_rp_targets.py',ROOT/'backend/tests/test_decision_rp_targets.py',SAMPLE]
    files=sorted(p for p in q.OUT.rglob('*') if p.is_file() and p.name not in ['manifest.json','audit.json'])
    q.save('manifest.json',{'version':'decision_rp_targets_v1','files':[{'path':p.relative_to(q.OUT).as_posix(),'bytes':p.stat().st_size,'sha256':q.b.digest(p)} for p in files],
        'sources':{p.relative_to(ROOT).as_posix():q.b.digest(p) for p in sources},'stop':'15.3','test2025_outcomes_examined':False})
    print(f'15.3 {len(files)} research artifacts frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','guard','build','finish','manifest']);args=parser.parse_args()
    if args.stage=='start':update()
    elif args.stage=='finish':update(True);handoff()
    else:globals()[args.stage]()
