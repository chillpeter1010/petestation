"""Authority/evidence for15.1-15.4; this run stops at15.2."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.export_decision_model_patch import load_project,change_field
from scripts import build_decision_common_clock as common
from scripts import build_decision_balance_revision as balance

ROOT=Path(__file__).resolve().parents[2]
SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_overlap_revision_v1.json'
SLICES=[
 {'id':'15.1','phase':'validation','label':'Slice 15.1 · 共同觀測時點、局間／局中與缺失原因稽核','status':'in_progress','depends_on':['15'],
  'deliverable':'建立早於官方行動的共同觀測截點，能力／球數／負荷／原因訊號按截點重取；分局間／局中、保留舊點與新點對帳及時間不足排除，分類後續量測缺失原因。',
  'verification':'2026-11-19啟動；原15產物與正式事件時鐘留版。',
  'acceptance':'不能只改decision_at而沿用較晚特徵；無法確認截點早於換投或資訊當時可知者拒絕比較。未觀測不補正常；不把資料切片差異直接稱生理疲勞。'},
 {'id':'15.2','phase':'validation','label':'Slice 15.2 · 特徵表示、平衡模型與權重對照','status':'planned','depends_on':['15.1'],
  'deliverable':'在共同時點上比較固定HGB、樣條logit、核心特徵消融及矩條件平衡logit；預先分開IPW與overlap目標母體，依2022／23前推的平衡／校準／ESS選設定，2024只診斷。',
  'verification':'Pending','acceptance':'保留能力、局面及缺值支持檢查，不靠刪失衡欄位過關；同演算法／特徵與加權目標分開。訓練內平衡不保證未來平衡，不以2024反覆挑設定；不改xWPA或推薦。'},
 {'id':'15.3','phase':'validation','label':'Slice 15.3 · RP觀測目標與受限比較母體','status':'planned','depends_on':['15.2'],
  'deliverable':'分開短登板／換下／量測不足，預先研究RP下一打席與完整十球任務、可比較母體及觀測機制敏感度；保留被換下者未知後續。',
  'verification':'Pending','acceptance':'任務及目標母體改動另立協定；不得用未來登板長度挑容易觀測者或將沒有後續當無惡化，不能把不同目標Brier直接比較。'},
 {'id':'15.4','phase':'validation','label':'Slice 15.4 · 凍結修訂、前推覆核與16進入條件','status':'planned','depends_on':['15.3'],
  'deliverable':'鎖定比較母體、特徵／時點、權重及支持門檻，完整前推覆核平衡、校準、ESS與拒絕原因，明定16可評估策略與終點。',
  'verification':'Pending','acceptance':'未過支持不晉升；2025封存、2024已用診斷需揭露，不以研究工作完成等同策略有效。正式換投／人選排名維持關閉。'}]


def update(stage):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end];nl='\r\n' if '\r\n' in segment else '\n'
    def span(sid):
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);return at,finish,item
    anchor='15'
    for item in SLICES:
        if not any(x['id']==item['id'] for x in project['slices']):
            _,finish,_=span(anchor);lines=json.dumps(item,ensure_ascii=False,indent=2).splitlines()
            block=lines[0]+nl+nl.join('    '+line for line in lines[1:]);segment=segment[:finish]+','+nl+'    '+block+segment[finish:]
        anchor=item['id']
    status={'start':['in_progress','planned'],'models':['done','in_progress'],'finish':['done','done']}[stage]
    for sid,state in zip(['15.1','15.2'],status):
        at,finish,item=span(sid);block=change_field(segment[at:finish],'status',state,decoder)
        if state=='done':
            if sid=='15.1':description='2026-11-19：共同截點為前一完整play結束+1ms，546,930點重取球數／能力／負荷／原因與先前名義RP快照，排除50個不能確認早於行動的點，留546,880。2024後援局間原時間間隔中位續投133秒／換投92秒，局中28／61秒；不能把時間切片差異直接叫疲勞。原RP缺16,630例分當下換投4,641、未來投球機會不足10,553、量測／參考不足1,267等，未觀測標籤仍空值。'
            else:description='2026-11-19：4固定對照×SP/RP×局間/局中×3前推年度共48模型，先2022/23凍結研究排序，再2024診斷。兩角色HGB對照最穩定但內層全門檻未過；2024 overlap最大SMD：SP局間.195／局中.148，RP.255／.108，均未過.1；固定矩條件logit部分不收斂，不改次數調到過。IPW與overlap母體分開，不改原xWPA／燈號、不產生新推薦。'
            block=change_field(block,'verification',description,decoder)
            if 'evidence' not in item:block=block[:-1].rstrip()+',\n      "evidence": "data/sample/petehub_pitcher_decision_overlap_revision_v1.json"\n    }'
        segment=segment[:at]+block+segment[finish:]
    at,finish,item=span('16');block=change_field(segment[at:finish],'depends_on',list(dict.fromkeys(item['depends_on']+['15.4'])),decoder)
    segment=segment[:at]+block+segment[finish:]
    done=40+sum(x=='done' for x in status)
    segment=change_field(segment,'summary',f'15.1–15.2共同時點與平衡修訂研究'+('完成' if stage=='finish' else '進行中')+f'，進度{done}/51（新增4個15後子項）。共同截點與局間／局中已拆開，固定模型對照仍未通過完整平衡；原15及多燈留版，15.3–15.4與16未開始，2025封存。',decoder)
    segment=change_field(segment,'next_step','本輪完成15.1共同觀測時點／情境與缺失稽核、15.2特徵表示及有限平衡模型對照；之後依15.3觀測目標／母體→15.4凍結前推覆核→16策略效益。未取得平衡支持不晉升，畫面使用者驗收。',decoder)
    result=text[:begin]+segment+text[end:];parsed=json.loads(result)
    assert [x for x in parsed['projects'] if x['id']!='pitcher-decision-support']==[x for x in json.loads(text)['projects'] if x['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print(f'Overlap revision authority {done}/51; stop15.2',flush=True)


def build():
    d=balance.read(balance.OUT/'summary.json')
    def compact(v):
        if isinstance(v,dict):return {key:compact(value) for key,value in v.items() if key!='balance'}
        if isinstance(v,list):return [compact(x) for x in v]
        return v
    result=compact(d);result['updatedAt']='2026-11-19'
    result['flow']={'original':sum(x['original'] for x in d['foundation']),'included':sum(x['included'] for x in d['foundation']),
        'excluded':sum(x['original']-x['included'] for x in d['foundation']),'models':48,'progress':'42/51'}
    result['clock2024']=next(x for x in d['foundation'] if x['year']==2024)['clock_by_role_action_phase']
    result['missing2024']=next(x for x in d['missing_audits'] if x['year']==2024)['rows']
    result['convergence_warnings']=len({(x['year'],x['role'],x['phase'],x['variant']) for x in d['all_results'] if x['warning']})
    result['primary2024']=[]
    for selected in d['selected']:
        for phase in selected['phases']:
            if phase['scheme']=='overlap':
                row=compact(phase);row['worst_balance']=sorted(phase['balance'],key=lambda x:abs(x['after']),reverse=True)[:5]
                result['primary2024'].append(row)
    result['methodNotes']=[
        '共同截點嚴格早於官方行動；是觀測風險集時間，不保證早於未記錄的教練意圖。所有特徵重新ASOF取得，沒有只改時間沿用原資料。',
        '新半局壘包只用已知例行賽規則；未來打者身分／能力、舊時點WE/LI不借用。牛棚只用截點前的名義快照並扣除已登板者，實際熱身／健康仍未知。',
        '樣條logit、固定矩條件平衡logit與HGB作有限對照；矩條件版為受限研究實作，非官方CBPS套件，部分未收斂不能推論整類平衡方法無效。',
        'overlap為主要的可比較情境母體；IPW原全母體風格另列，不能挑結果漂亮的目標或直接把舊15的SMD／點數當相同比較。',
        '所有模型都用相同豐富欄位檢查平衡，核心特徵消融也不能略過被移除欄位。0.1只是預先研究門檻，不證明沒有隱藏混雜。']
    balance.save('evidence.json',result);common.b.save_json(SAMPLE,result)
    print('15.1/15.2 evidence published; no model/value/recommendation promotion',flush=True)


def handoff():
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8');heading='## 2026-11-19：15.1–15.2共同時點與平衡修訂完成（最新）'
    if heading in text:return
    d=common.read(SAMPLE)
    section=f'''{heading}

使用者要求改規劃並開始15.1–15.2。新增15.1–15.4四子項，進度由40/47改為 **42/51**；15.1／15.2完成研究工作，平衡門檻仍未過。15.3 RP觀測任務／母體、15.4凍結前推覆核planned，16增加15.4依賴；不自動開始15.3、16或開封2025、不commit/push、不開browser/server。原研究產物與源碼全部留版。

15.1：共同截點＝前一個全場已完成play結束+1ms，必須嚴格早於原官方行動時間、現任已進場及局面可重建。546930點中排除50個時點不能嚴格確認的點，留546880（2021 131918、2022 137323、2023 139565、2024 138074）。這仍繼承原回溯合法／身分／完整play母體，不是部署覆蓋或真實教練思考時點。

所有球數、BF、72/120h其他場用球、角色能力、當前原因區段均ASOF重取；個人負荷中位數固定進場前，避免把現任整段當過去。累積pitcher／game clocks相減處理同場與跨場負荷。局間以已知比分及規定壘包重建，局中沿前play出局／壘包；未來打者身分／能力及舊時點WE/LI不沿用。牛棚採截點前最近名義RP快照，扣除截點前已登板者並保留年齡／未知，非完整active／熱身／醫療資訊。不能只改decision_at沿用舊欄位。

2024 RP共同截點到舊時點的中位間隔，局間續投132.6秒／換投91.9秒；局中續投27.9秒／換投61.5秒。差異方向依情境變動，需把局間／局中分開；不能將其直接稱成疲勞或斷言造成多少舊偏差。保留原官方時間與所有排除對帳。

原15 RP監測19115例，缺16630：當下換投4641、後續投球機會不足10553、量測／參考不足1267、原支持範圍外142、區段／session缺口27。有量測2485。分類以舊15目標為準，只作事後稽核，不入模型；不足機會包含稍後換下／原固定區段要10–19球等，不等同資料缺檔或生理疲勞。SP缺16828另列1812／6244／2883／5730／159；有量測21259。沒有開始15.3的新RP目標／觀測模型。

15.2：4個固定設定（共同時點HGB、核心樣條logit、完整樣條logit、固定矩條件平衡logit）×兩離場角色×局間/局中×三前推年度，共48模型。學習分段80/20整場時間、所有label早於次年首anchor；僅HGB做late-time Platt，線性模型保留原機率。所有候選以同一豐富數值／缺失／類別基準檢查平衡；核心消融不能刪檢查欄位過關。主目標overlap weights、次目標IPW(.05/.95)，兩母體分開，不以結果挑目標。

只用2022/23前推排序，SP/RP都選hgb_full作最穩定研究對照，但各4個phase/year門檻全未過，沒有取得晉升資格。selection與confirmation_guard在任何2024結果前凍結；2024已用診斷，不稱獨立新測試。2024主要overlap最大SMD：SP局間.195、局中.148；RP局間.255、局中.108，仍均高於.1。新舊時點、分組、欄位與目標不同，不能宣稱比舊15改善多少%。2024部分logit表面較好也不回頭改選。

固定矩條件模型最小化IPW平衡矩加L2、限制150迭代／係數範圍；不是官方CBPS實作、沒有精確平衡保證。共{d['convergence_warnings']}模型有收斂警告，保留失敗，不加迭代調到2024過。原研究矩陣48模型的重複兩scheme共96結果，不是96個獨立模型。原xWPA／PA模型、名義人選、兩紅、11／0及新0多燈研究候選全部未變；推薦／排名關閉。

留版：15.2首次兩個2022 HGB模型擬合後，IPW診斷遇pandas唯讀mask錯誤；原source/protocol/2模型/機率/split留attempt0_readonly_mask。revision2只複製mask再篩選，模型與門檻／母體／排序不變；沒有2024結果時即修正留版。15.1的源碼／資料協定凍結在15.2模型之前，所有核心源碼不可靜默改。

產物 `data/research/decision_common_clock_v1/`（逐點時點／重取特徵／缺失原因／時鐘快取）及 `decision_balance_revision_v1/`（協定、splits、48模型／機率、排序、guard、結果、manifest）；小型證據 `data/sample/petehub_pitcher_decision_overlap_revision_v1.json`。新Lab#overlap-revision，舊15收進歷史組並保留#overlap-research，規劃表依數字顯示15.1–15.4及依賴。畫面使用者驗收。

接下來依15.3檢查RP目標及受限母體；15.4再凍結完整前推、明定16策略與終點，未達支持不晉升。本輪只完成15.1–15.2，不進後續。方法局限包括未來打者於新截點未知、牛棚快照不完整、歷史選擇、未記錄意圖／健康與觀測缺失，平衡過關也不能直接稱策略有效。

重跑分段：build_decision_common_clock.py cache→prepare/missing_audit --year2021..24→freeze；build_decision_balance_revision.py freeze→train --year2022/23 --role SP/RP→select→confirmation_guard→train --year2024→finish。export_decision_overlap_revision.py build／finish→export_pitcher_decision_plan.py→sync_project_tracker.py→manifest→audit_decision_overlap_revision.py。原協定／來源先核對再重跑，新方法另立版本。

'''
    at=text.index('## ');path.write_text(text[:at]+section+text[at:],encoding='utf-8')


def manifest():
    sources=[Path(__file__),Path(common.__file__),Path(balance.__file__),ROOT/'backend/scripts/audit_decision_overlap_revision.py',
        ROOT/'backend/tests/test_decision_common_clock.py',ROOT/'backend/tests/test_decision_balance_revision.py',SAMPLE]
    for folder in [common.OUT,balance.OUT]:
        files=sorted(p for p in folder.rglob('*') if p.is_file() and p.name not in ['manifest.json','audit.json'])
        common.b.save_json(folder/'manifest.json',{'version':folder.name,'files':[{'path':p.relative_to(folder).as_posix(),'bytes':p.stat().st_size,'sha256':common.b.digest(p)} for p in files],
            'sources':{p.relative_to(ROOT).as_posix():common.b.digest(p) for p in sources},'stop':'15.2','test2025_outcomes_examined':False})
        print(f'{folder.name}: {len(files)} artifacts frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','models','build','finish','manifest']);args=parser.parse_args()
    if args.stage in ['start','models']:update(args.stage)
    elif args.stage=='finish':update('finish');handoff()
    else:globals()[args.stage]()
