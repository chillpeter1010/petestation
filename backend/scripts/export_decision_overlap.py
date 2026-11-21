"""Slice15 evidence and authority publisher; no model fitting or UI automation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_overlap as q
from scripts import build_decision_overlap_pool as pool
from scripts.export_decision_model_patch import load_project,change_field
import pandas as pd

SAMPLE=q.ROOT/'data/sample/petehub_pitcher_decision_overlap_v1.json'


def without_balance(value):
    if isinstance(value,dict):return {key:without_balance(item) for key,item in value.items() if key!='balance'}
    if isinstance(value,list):return [without_balance(item) for item in value]
    return value


def build():
    original=q.read(q.OUT/'summary.json');data=without_balance(original)
    data['candidate_support']=q.read(pool.OUT/'summary.json')['candidate_support']
    data['updatedAt']='2026-11-19';data['pool_probability_revision']='explicit_outside_pool_mass_v2'
    data['flow']={'boundaries':sum(x['boundaries'] for x in data['preparation']),
        'changes':sum(x['changes'] for x in data['preparation']),'restored':sum(x['restored_out_of_nominal'] for x in data['preparation']),
        'models':24,'training_years':'2021–2023時間前推；2022／2023／2024逐年驗證'}
    for item in data['roles']:
        if item['year']!=2024:continue
        f=pd.read_parquet(q.OUT/f'scored_2024_{item["role"]}_monitoring.parquet')
        item['missing_immediate_change']=int((f.future_observed.eq(0)&f.changed.eq(1)).sum())
        item['missing_after_continue']=int((f.future_observed.eq(0)&f.changed.eq(0)).sum())
        source=next(x for x in original['roles'] if x['role']==item['role'] and x['year']==2024)
        item['worst_balance']=sorted(source['primary']['balance'],key=lambda x:abs(x['after']),reverse=True)[:5]
    data['conclusion']='調度／量測模型有預測訊息，但2024兩角色主要加權平衡均未過0.1；固定32場只有604/1737可算點通過初步重疊，整體尚不能作可信的策略效益宣稱。先修傾向平衡／限定母體，再安排16；原多燈仍0有效研究候選。'
    data['interpretation']='AUC是歷史選擇的可預測程度，不是換投正確率；ESS是獨立等權樣本量的權重近似，不是比賽數。候選初步支持不能略過整體平衡或未知可用性。'
    data['visual_acceptance']='pending user'
    q.b.save_json(SAMPLE,data);q.save('evidence.json',data)
    print('Slice15 compact evidence published; action/observation unchanged, candidate probabilities use explicit outside-pool mass revision',flush=True)


def update(done=False):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    match=re.search(r'"id"\s*:\s*"15"\s*,',segment);at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at)
    block=change_field(segment[at:finish],'status','done' if done else 'in_progress',decoder)
    if done:
        d=q.read(SAMPLE);rows=[x for x in d['roles'] if x['year']==2024]
        description='2026-11-19：四季546,930個邊界、54,669次換投，恢復38次原池外換投；2022／23／24前推SP/RP共24個調度／觀測／RP池歸屬／人選模型。2024 '+ '；'.join(f"{x['role']}重疊{x['primary']['retained']:,}/{x['action']['n']:,}，換投ESS{x['primary']['change']['ess']:.0f}、最大SMD{x['primary']['max_abs_smd_after']:.3f}" for x in rows)+'；兩角色均未過0.1平衡。後援未來量測缺失87%；固定32場604/1737可算點過初步重疊。SP觀測加權兩紅差區間跨0，RP無足夠兩紅；沒有晉升策略或推薦。原二階段人選分數另留版，顯式加入池外機率修訂，不重寫原燈號或xWPA。'
    else:description='2026-11-19：時間前推調度、個別名義RP選擇與未來量測觀測傾向研究進行中；停止於15，2025結果封存。'
    block=change_field(block,'verification',description,decoder)
    if done and 'evidence' not in item:block=block[:-1].rstrip()+',\n      "evidence": "data/sample/petehub_pitcher_decision_overlap_v1.json"\n    }'
    segment=segment[:at]+block+segment[finish:]
    segment=change_field(segment,'summary','Slice15選擇偏差與重疊研究'+('完成40/47' if done else '進行中39/47')+'；分開換投、名義候選選擇與後續量測觀測傾向。2024主要加權平衡未過，不能直接宣稱換投策略有效；保留原多燈0新候選與11／0歷史，不自動開始16。',decoder)
    segment=change_field(segment,'next_step','15研究工作完成但平衡門檻未過；先另行授權傾向模型平衡修訂或預先限定比較母體，再決定16的策略／終點與有效樣本。不直接以現有權重做全母體因果宣稱、不開封2025，畫面由使用者驗收。' if done else '完成15的時間前推調度／候選／量測觀測模型、重疊、權重與有效樣本檢查；不開始16或2025測試，畫面由使用者驗收。',decoder)
    result=text[:begin]+segment+text[end:]
    assert [x for x in json.loads(result)['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print('Slice15 authority '+('40/47 complete' if done else '39/47 in progress'),flush=True)


def handoff():
    path=q.ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8');heading='## 2026-11-19：Slice15選擇偏差／重疊研究完成（最新）'
    if heading in text:return
    data=q.read(SAMPLE)
    section=f'''{heading}

使用者授權「開始slice15並回報成果」。工作完成 **40/47**，研究結果的平衡門檻未過；不自動進16、不開封2025、不commit/push、不開browser/server或驗收畫面。原969份研究檔、14.2.2–4的112份及凍結源碼／v1與v2燈號均保留；原11預警／0配對及新0有效多燈研究候選不變。

分開四項：P(換投|X)、P(之後有全未來有效量測|X)、P(進入名義RP池|換投,X)、P(該RP|換投且池內,X)。前兩者以固定HGB7/60＋時間內Platt，池內人選以固定L2條件softmax＋時間內temperature。所有輸入只用離場者／候選本人的決策前資訊，incoming ID只作標籤；遊戲closed時鐘作保守label available，2021→22、21–22→23、21–23→24，fit/cal整場時間分開，沒有2025結果。

母體546,930個2021–24回溯合法／身分／已完成play邊界，54,669次換投；恢復原38個實際接任者不在名義池的案例，不再以此結果排除調度傾向。仍繼承回溯身分、法定合法、已完成play、強制換投排除，非部署母體。2021後續量測只有晚季已具凍結正常進程分數，不能直接以全年比率比較。

2024：SP 96,630邊界、4,515換投，主要e∈[.05,.95]且過去分格各行動>=10後14,691（15.2%），換投ESS1943、續投ESS8769、最大絕對SMD0.209；RP 41,457邊界、9,819換投，保留31,196（75.2%），ESS4062／15948、SMD0.296。預先平衡門檻0.1兩角色皆未過，AUC雖SP.948／RP.883不能當正確率或可用因果權重。偏差主項SP為D缺失與投手K/BB能力，RP為出局、資料年齡及壘包。

監測以每完整10球block第一個合法邊界去重，目標anchor>=decision且最多來源後2個編號。SP38,087機會缺16,828（44.2%），RP19,115缺16,630（87.0%）；R=0只代表沒有有效後續量測，future_bad仍NaN。全四群、g>=.1母體SP15016中11244有量測，觀測權重ESS6983／平衡SMD.100附近；RP5271中1424有量測，ESS1002／SMD.147。這仍依賴無法驗證的觀測機制假設。主要R>=.1使1/g<=10，所以10/20/50 cap相同屬預定範圍的必然，不能稱截斷敏感度已證明穩健；調度與候選的cap敏感度另列。

SP兩紅觀測加權未來偏離率63.6%對參考34.5%，差29.1pp，200次比賽×投手重抽樣區間[-4.94,50.69]pp跨0；不是因果效果，也沒晉升。RP在g>=.1及有完整未來量測之後兩紅0例，不強算區間。樣本支持旗標只代表足夠例數算區間，不等於預測支持。固定32場2376原始、1791有調度分數、633過初步重疊；1737可算值中604過初步重疊，但整體平衡仍不通過，不能叫604個有效策略建議。

方法留版：初次fit因nullable Int64在transformer即被拒、沒有成功模型或預測，原source/protocol/split留attempt0_nullable_dtype；revision2只修float/NaN輸入後才擬合。原18模型及結果先封core_manifest（96檔）。診斷後發現兩階段人選分數不能當無條件機率，另凍結pool_mass_v2並加6個RP池歸屬模型，顯式保留池外機率；不改原18模型／原結果，不稱新的獨立2024確認。最終人選機率是P(change)*P(in RP pool|change)*P(actor|change,in pool)，池外＋續投＋池內合為1；展示候選門檻只是初篩，整體平衡及active／熱身／醫療／人工未知仍阻擋可操作建議。

完整逐點、候選、monitoring、time splits、24模型、機率、權重／平衡在 `data/research/decision_overlap_v1/` 及 `decision_overlap_pool_revision_v2/`；小型證據 `data/sample/petehub_pitcher_decision_overlap_v1.json`。核心方法及補正協定各有SHA，凍結後不得靜默改。Lab `#overlap-research` 新增主要重疊、觀測缺失、個別人選與cap／區間結果；只做source檢查，畫面待使用者。

建議下一步先做15後續平衡修訂（另立協定，不按2024結果反覆調到過）：比較受限平衡模型／預先縮小母體，分開RP短登板結構性不可觀測與量測缺失。過關後才明定16可評估策略、終點與群體；目前多燈策略0有效候選，不能直接作有效策略估值。17–21仍planned。

重跑：build_decision_overlap.py prepare --year2021..24→freeze→fit --year2022..24 --role SP/RP→evaluate；核心源碼目前已凍結，只能相同協定重跑；core_manifest固定原產物。build_decision_overlap_pool.py freeze→run為顯式池外質量補正。export_decision_overlap.py build→finish→export_pitcher_decision_plan.py→sync_project_tracker.py→manifest→audit_decision_overlap.py。

'''
    at=text.index('## ');path.write_text(text[:at]+section+text[at:],encoding='utf-8')


def manifest():
    sources=[Path(q.__file__),Path(pool.__file__),Path(__file__),q.ROOT/'backend/scripts/audit_decision_overlap.py',q.ROOT/'backend/tests/test_decision_overlap.py',SAMPLE]
    for folder in [q.OUT,pool.OUT]:
        files=sorted(p for p in folder.rglob('*') if p.is_file() and p.name not in ['manifest.json','audit.json'])
        q.b.save_json(folder/'manifest.json',{'version':folder.name,'files':[{'path':p.relative_to(folder).as_posix(),'bytes':p.stat().st_size,'sha256':q.b.digest(p)} for p in files],
            'source_sha256':{p.relative_to(q.ROOT).as_posix():q.b.digest(p) for p in sources},'stop':'15','test2025_outcomes_examined':False})
        print(f'{folder.name}: {len(files)} artifacts frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','build','finish','manifest']);args=parser.parse_args()
    if args.stage=='start':update()
    elif args.stage=='finish':update(True);handoff()
    else:globals()[args.stage]()
