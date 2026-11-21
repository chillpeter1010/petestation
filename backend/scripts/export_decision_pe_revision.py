"""15.5.1-4 authority/evidence; preserve all earlier frozen studies."""
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_pe_models as m
from scripts.export_decision_model_patch import load_project,change_field

ROOT=m.ROOT;SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_pe_revision_v1.json'
SLICES=[
    {'id':'15.5.1','phase':'validation','label':'Slice 15.5.1 · 共同截點、PE／預定打線與coverage','status':'in_progress','depends_on':['15.4'],
     'deliverable':'盤點並重建截點前完整PA、PE材料、FF基準及由已完成棒次推估的後續打線；區分觀測、預測身分與未知，保留2021–24覆蓋與時鐘對帳。',
     'verification':'進行中','acceptance':'不使用本場最終平均、最終登板長度或事後下一打者；零球及IBB仍占棒次。D是負荷，相性另列；原研究留版、2025封存。'},
    {'id':'15.5.2','phase':'validation','label':'Slice 15.5.2 · 近期PE與個人化偏離','status':'planned','depends_on':['15.5.1'],
     'deliverable':'建立PA版PE代理的最近1／2／3PA、趨勢及缺失支持，加入進場前個人PE／FF基準與收縮的預定打者歷史，凍結有限特徵群。',
     'verification':'Pending','acceptance':'PE代理非原論文精確重現或生理疲勞；缺失不補正常，個人基準早於進場、所有打者先驗早於截點。'},
    {'id':'15.5.3','phase':'validation','label':'Slice 15.5.3 · 固定特徵與有限模型對照','status':'planned','depends_on':['15.5.2'],
     'deliverable':'九類PA結果主要任務、下一PA失分輔助任務；HGB特徵消融及同完整特徵的正則化線性／Random Forest比較，整場前推及校準、2022/23凍結排序後才看2024。',
     'verification':'Pending','acceptance':'同一任務／樣本／訓練分段公平比較；不得跨標籤Brier評輸贏或依2024調參。被換下者原投手後續仍未知。'},
    {'id':'15.5.4','phase':'validation','label':'Slice 15.5.4 · 前推增益、提醒負擔與進入條件','status':'planned','depends_on':['15.5.3'],
     'deliverable':'比賽×投手群聚增益區間、校準、角色／早局提醒負擔、未知後續與提前配對；預測支持和原SMD／策略資格分開回報。',
     'verification':'Pending','acceptance':'警示與實際換投吻合非正確或因果收益；未知不可算誤報，預測提升不等於SMD改善；不進16、不啟用推薦或開封2025。'}]


def update(stage):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end];nl='\r\n' if '\r\n' in segment else '\n'
    def span(sid):
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);return at,finish,item
    anchor='15.4'
    for item in SLICES:
        if not any(s['id']==item['id'] for s in project['slices']):
            _,finish,_=span(anchor);lines=json.dumps(item,ensure_ascii=False,indent=2).splitlines()
            block=lines[0]+nl+nl.join('    '+line for line in lines[1:]);segment=segment[:finish]+','+nl+'    '+block+segment[finish:]
        anchor=item['id']
    states={'start':['in_progress','planned','planned','planned'],'features':['done','done','in_progress','planned'],'finish':['done']*4}[stage]
    for sid,state in zip([s['id'] for s in SLICES],states):
        at,finish,item=span(sid);block=change_field(segment[at:finish],'status',state,decoder)
        if state=='done':
            notes={'15.5.1':'2021–24共同截點特徵與PA／FF材料、已完成棒次打線預測及coverage完成；預測身分不等同實際下一打者。',
                '15.5.2':'近期PE代理／缺失支持、進場前個人參考及收縮打者先驗完成，特徵及模型協定已凍結。',
                '15.5.3':'30個九類PA模型及12個PA失分模型、共42個固定擬合；2022/23先凍結排序再檢查2024，未替換原模型。',
                '15.5.4':'前推增益與群聚區間、角色別提醒負擔／早局／未知及同邊界／提前配對完成；原SMD與16資格保留，不估策略收益。'}
            block=change_field(block,'verification','2026-11-21：'+notes[sid],decoder)
            if 'evidence' not in item:block=block[:-1].rstrip()+',\n      "evidence": "data/sample/petehub_pitcher_decision_pe_revision_v1.json"\n    }'
        segment=segment[:at]+block+segment[finish:]
    at,finish,item=span('16');block=change_field(segment[at:finish],'depends_on',list(dict.fromkeys(item['depends_on']+['15.5.4'])),decoder);segment=segment[:at]+block+segment[finish:]
    done=44+sum(s=='done' for s in states)
    for key,value in [('updated_at','2026-11-21'),('summary',f'15.5.1–15.5.4 PE／個人化／預定打線與有限預測模型研究'+('完成' if stage=='finish' else '進行中')+f'{done}/55。預測增益與SMD分開評估，原模型／多燈留版；16未開始、2025封存。'),
        ('next_step','依15.5固定前推結果決定新增特徵是否有預測支持；原15.4比較平衡、共同截點四群／價值／人選／半局終點資格仍需另行修訂，不以預測提升跳過SMD或開啟16／推薦，畫面使用者驗收。')]:segment=change_field(segment,key,value,decoder)
    result=text[:begin]+segment+text[end:]
    assert [p for p in json.loads(result)['projects'] if p['id']!='pitcher-decision-support']==[p for p in json.loads(text)['projects'] if p['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print(f'15.5 authority {done}/55; stop15.5.4,16 not started',flush=True)


def build():
    d=m.read(m.OUT/'summary.json');result=dict(d);result['updatedAt']='2026-11-21'
    result['flow']={'progress':'48/55','models_pa':30,'models_run':12,'features_boundaries':sum(y['boundaries'] for y in d['coverage'])}
    result['methodNotes']=[
        'PA版PE是競賽／論文啟發的固定代理，不是精確複製或生理疲勞標籤；結果、最終一球前好壞球與已知EV加權，揮空另列，避免每球／打席混計。只用已完成PA，未知打斷近期窗，部分累積附coverage。',
        'FF只比較四縫線，採截點前prefix與進場前最近50個有FF的PA個人參考（至少10才有均值），不使用全場最終平均。個人PE參考同樣在進場前鎖定；既有球數／角色條件殘差仍在共同基準。',
        '預定下三棒以先前已完成PA的棒次球員推估，包含零球／IBB占棒次。預定身分不是已確認下一打者，事後代打不回填或用來篩好案例；未知身分／冷啟動有獨立狀態。',
        '打者九類先驗只用截點前歷史，向前一UTC日已完成PA的聯盟分布收縮20；無日參考時僅有Laplace1的未資訊先驗，不冒稱觀測。D為負荷／恢復，相性／預定下一棒另列。',
        '主要任務原投手下一完整自然PA九類結果；輔助任務該PA期間是否失分，不是從anchor到半局終點WPA／RE24。當下換投或actor／時鐘不合者未知，不接接任者成績。',
        '每個角色／年度各模型同一批自然60000上限fit，整場80/20時間切學習／late-cal，跨界場排除；補值與尺度只fit學習資料。HGB三特徵群、同完整特徵的正則化線性／RF，另HGB基準／完整失分模型，共42擬合。',
        '2022/23決定研究排序、guard後才做2024診斷；2024已看過，不是新獨立確認，2025封存。群聚區間只條件於固定模型與已觀測者，不涵蓋重訓或解決非隨機缺失。',
        '警示為角色別研究回放：過去全部cal邊界風險第90百分位、同半局／同登板連續兩PA、一登板最多一次、角色流內同隊兩PA冷卻；未整合SP轉RP跨角色狀態機。早局不硬剔除，未知後續不算誤報。',
        '警示與換投只配對既有合法母體中的實際事件：同邊界與提前1–2PA且600秒內分列，不是正確率或全部官方換投召回。角色全部母體提醒與RP主要受限母體預測分母不同，明確分列。',
        '原15.3二元模型只在相同配對監測案例作補充對照，其訓練資料／任務與新九類模型不同，不是純演算法比較；十球舊任務保留原研究版本，不參與新模型排序。',
        '沒有訓練換投傾向或重算因果權重；原15.4主要SMD及16拒絕條件保留。新增預測支持也不能稱SMD改善、換投有效或直接啟用推薦。']
    m.save('evidence.json',result);m.q.b.save_json(SAMPLE,result);print('15.5 prediction evidence published; no original model promotion',flush=True)


def handoff():
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8');heading='## 2026-11-21：15.5.1–15.5.4預測修訂研究完成（最新）'
    if heading in text:return
    d=m.read(SAMPLE)
    section=f'''{heading}

使用者授權完成15.5.1–15.5.4。新增四子項，進度 **48/55**（此前44/51），16增加15.5.4依賴且仍planned；16–21未開始、2025封存，不commit/push、不改原PA／xWPA／燈號或啟用推薦。原1556份產物（含15.4）留版。D負荷／恢復字典勘誤已明定，下一打者是另一資訊群，不修改舊凍結source/hash。

15.5.1/2：四年546880個共同截點，建立PA版PE代理（固定事件權重＋最後一球前球數＋已知EV）、最近1/2/3完整PA、3PA變化、部分累積與coverage、揮空／每PA強擊球及prefix好球份額。非原論文精確重現、不稱疲勞。接觸缺EV與IBB等留未知、打斷近期窗；無接觸不是缺EV。FF僅四縫線，最後已完成PA FF均值對截點前prefix及進場前最近50有FF PA參考；個人PE同樣進場前最近50、至少10才有均值，沒有全場未來平均或最終登板長度選取。

下三棒由先前已完成官方PA依9棒次循環的最近已出現球員推估，包括零球／IBB，不使用事後首發表或實際下一PA打者。未知首輪／代打保留不確定，身分吻合度只事後盤點，不篩樣本。歷史打者九結果ASOF、收縮20到前一UTC日已完成PA聯盟先驗，無日參考僅Laplace1未資訊先驗。身分／能力／聯盟時鐘、PE prefix／entry參考各保留。標籤只在原投手續投、下一完整organic PA同一physical actor且開始不早於anchor、結束不晚於gameclose時有值；換下者未知，不借接任結果。輔助失分是PA期間比分增量，不是anchor-to-half WPA。

15.5.3：SP/RP各三年前推，主要九類PA每折HGBbase/PE/full及linear_full/RF_full五模型；輔助run每折HGBbase/full兩模型，共30+12=42。整場80/20分fit/cal，跨界場排除；取已觀測標籤，自然抽樣fit最多60000、所有設定同一fit，補值／尺度只fit；late-cal溫度[.5,3]。HGB7葉60、線性L2alpha.001/100iter、RF100棵depth8/minleaf100/maxfeatures.7固定，無超參數搜尋。2022/23依失敗fold數再平均LL排序，選設定但不保證支持；selection/guard早於2024新輸出，2024已被過去研究看過，只診斷，不稱新獨立測試。

15.5.4：主要SP全部、RP局中short_profile（entry歷史）固定；九類LL、nonout Brier／AUC／校準及game×pitcher300次配對區間。輔助run風險在全部角色risk set回放，cal全部邊界風險90百分位取門檻（非依未來觀測／實際換投）；同半局登板連續兩PA、一登板一次、角色流內同隊2PA冷卻，沒有SP-to-RP全域整合。早局保留，未知警示後續另列，不算誤報；實際事件只既有合法母體，同邊界與提前1–2PA/600秒分開，非策略效益。RP另在同paired monitoring案例對照原15.3二元預測，訓練樣本／任務不同，不能當純演算法對照。舊十球任務不改、不參與排序。

研究排序：{'; '.join(role+'='+d['selection']['selected'][role]['config']+', development_support='+str(d['selection']['selected'][role]['development_predictive_support']) for role in ['SP','RP'])}。完整數值在摘要primary2024與folds，不挑2024其他較好模型回頭改選。沒有重訓行動傾向或重算權重，原15.4三年9項SMD拒絕保留，沒有因預測增益自動進16；共同截點四群／價值回放、人選聯合支持／實際可用性及同半局終點／共同後續策略仍需另行修訂。

新來源資料`decision_pe_features_v1/`、協定／42模型／split／逐點機率／排序／guard／風險回放`decision_pe_models_v1/`；摘要`petehub_pitcher_decision_pe_revision_v1.json`，audit另存。Lab#pe-revision，畫面使用者驗收。重跑先核對原hash，build_decision_pe_features.py cache各年→references→prepare各年；build_decision_pe_models.py freeze→train/evaluate2022/23各role→select→guard→train/evaluate2024→finish；export_decision_pe_revision.py build/finish→export_pitcher_decision_plan.py→sync_project_tracker.py→manifest→audit_decision_pe_revision.py。不能靜默改已凍結source／資料／排序。

'''
    text=text.replace('## 2026-11-21：15.4凍結前推與16資格覆核完成（最新）','## 2026-11-21：15.4凍結前推與16資格覆核完成（歷史版本）')
    at=text.index('## ');path.write_text(text[:at]+section+text[at:],encoding='utf-8')


def manifest():
    sources=[Path(__file__),Path(m.__file__),Path(m.f.__file__),ROOT/'backend/scripts/audit_decision_pe_revision.py',ROOT/'backend/tests/test_decision_pe_revision.py',SAMPLE]
    for folder in [m.f.OUT,m.OUT]:
        files=sorted(p for p in folder.iterdir() if p.is_file() and p.name not in ['manifest.json','audit.json'])
        m.q.b.save_json(folder/'manifest.json',{'version':folder.name,'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':m.q.b.digest(p)} for p in files],
            'sources':{p.relative_to(ROOT).as_posix():m.q.b.digest(p) for p in sources},'stop':'15.5.4','test2025_outcomes_examined':False})
        print(f'{folder.name}: {len(files)} artifacts frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','features','build','finish','manifest']);args=parser.parse_args()
    if args.stage in ['start','features']:update(args.stage)
    elif args.stage=='finish':update('finish');handoff()
    else:globals()[args.stage]()
