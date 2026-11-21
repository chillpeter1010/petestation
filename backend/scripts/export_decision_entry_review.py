"""Publish15.4 eligibility review without changing frozen prior studies."""
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_entry_review as e
from scripts.export_decision_model_patch import load_project,change_field

ROOT=e.ROOT;SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_entry_review_v1.json'


def update(done=False):
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    for sid in ['15.4','16']:
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment)
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);block=segment[at:finish]
        if sid=='15.4':
            block=change_field(block,'status','done' if done else 'in_progress',decoder)
            block=change_field(block,'verification','2026-11-21：凍結共同截點、SP／RP固定母體／模型／權重／門檻；2022–24前推平衡、校準、ESS、拒絕原因與缺失／群聚不確定性覆核'+('完成。研究工作44/51；未通過比較及實作條件，不進16、不啟用推薦，2025封存。' if done else '進行中；2024已用診斷、不作獨立確認，2025封存。'),decoder)
            if done and 'evidence' not in item:block=block[:-1].rstrip()+',\n      "evidence": "data/sample/petehub_pitcher_decision_entry_review_v1.json"\n    }'
        elif done:
            assert item['status']=='planned'
            block=change_field(block,'verification','未啟動：15.4完成資格覆核，固定主要前推平衡未過、多燈預測支持未過；共同時點的四群／價值回放、人選聯合支持／實際可用性、同半局終點及共同後續策略仍未就緒。詳見15.4證據；不可把工作完成視為進入資格。',decoder)
        segment=segment[:at]+block+segment[finish:]
    for key,value in [('updated_at','2026-11-21'),('summary',('15.4凍結前推與16資格覆核完成44/51。主要比較及實作條件未過，16維持待開始；' if done else '15.4凍結前推／16資格覆核進行中43/51；')+'2024僅診斷、2025封存，原模型／燈號及推薦狀態保留。'),
        ('next_step','依15.4拒絕清單先修共同時點的比較平衡、四群／價值回放、人選聯合支持與實際可用性，以及同半局終點／共同後續策略；另立修訂協定並取得前推支持後才可進16。不得放寬門檻、依2024換母體或開封2025。')]:segment=change_field(segment,key,value,decoder)
    result=text[:begin]+segment+text[end:]
    assert [p for p in json.loads(result)['projects'] if p['id']!='pitcher-decision-support']==[p for p in json.loads(text)['projects'] if p['id']!='pitcher-decision-support']
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print('15.4 authority '+('44/51 completed;16 remains planned' if done else '43/51 in progress'),flush=True)


def build():
    d=e.read(e.OUT/'summary.json')
    def compact(value):
        if isinstance(value,dict):
            result={k:compact(v) for k,v in value.items() if k!='balance'}
            if 'balance' in value and isinstance(value['balance'],list) and value['balance'] and 'after' in value['balance'][0]:
                result['worst_balance']=sorted(value['balance'],key=lambda x:abs(x['after']),reverse=True)[:5]
            return result
        if isinstance(value,list):return [compact(x) for x in value]
        return value
    result={k:compact(v) for k,v in d.items() if k!='balance'};result['balance_results']=compact(d['balance'])
    result['updatedAt']='2026-11-21';result['flow']={'progress':'44/51','new_models':0,'reviewed_rows':sum(x['boundaries'] for x in d['flows']),
        'initial_support':sum(x['initial_support'] for x in d['flows']),'qualified_rows':sum(x['review_eligible'] for x in d['flows']),
        'primary_folds':len(d['primary_folds']),'primary_passed':sum(x['full_gate'] for x in d['primary_folds'])}
    result['methodNotes']=[
        '15.4重算既有前推機率／平衡與固定模型條件結果，沒有訓練新模型、依2024改選母體或估策略收益。2024先前已看過且15.3修正標籤後重跑，這輪不是新的獨立確認。',
        'SP沿15.2完整HGB、局間／局中分開；RP沿15.3新增歷史HGB，主要局中短型歷史，其他固定母體只列敏感度。相同豐富欄位檢查，不能移除失衡欄位過關。',
        '主要overlap、次要IPW是不同目標母體。要求SMD≤.1、兩行動ESS≥500、ECE≤.03且無擬合警告，2022／23開發與2024診斷均過；通過也不能證明無隱藏混雜。',
        '初步點支持只用當時母體、過去分格及有效機率；年度／開發資格與拒絕原因是事後研究稽核，不是當時已知特徵、換投時點或歷史預警回放。缺失後續與實際換投不拿來挑可用點。',
        'Brier群聚區間採300次比賽與投手兩組獨立重抽後相乘權重，配對比較模型與其過去常數。只條件於固定模型及已觀測結果，沒有重訓不確定性，也不解決非隨機缺失或多重比較。',
        '缺失者維持未知；觀測加權與odds假設情境不是反事實。下一PA非出局與十球偏離不能替代策略WPA／RE24終點。',
        '16策略契約以同半局終點比較續投與多燈條件換投，接任採固定等機率支持名義RP池，屬時機／池層級研究，不是最佳人選排名；實際可用性及共同後續策略未知時拒絕評估。',
        '研究工作44/51不等於16進入資格。原xWPA／人選／燈號與0正式推薦不變，2025封存；畫面使用者驗收。']
    e.save('evidence.json',result);e.q.b.save_json(SAMPLE,result)
    print('15.4 eligibility evidence published',flush=True)


def handoff():
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8');heading='## 2026-11-21：15.4凍結前推與16資格覆核完成（最新）'
    if heading in text:return
    d=e.read(SAMPLE)
    section=f'''{heading}

使用者授權下一步15.4，本輪完成 **44/51**，16–21仍planned。15.4研究交付完成但16進入資格=False；沒有執行16、訓練新模型、產生新策略收益／推薦、開封2025、commit/push或瀏覽器／畫面驗收。原1546份產物（含15.3留版）按manifest核對保留。

15.4協定`decision_entry_review_v1/protocol.json`在這輪重算前凍結source／既有manifest／特徵／母體／模型／門檻／權重及16策略終點。SP沿15.2 hgb_full、兩phase分開；RP沿15.3 history_enriched、主要within_inning short_profile，其餘固定subset敏感度。沒有改選或重新擬合，2024早已診斷、15.3亦曾修正標籤，本輪不是獨立確認。2022/23/24共72個平衡結果（非模型數）、9個主要phase/year門檻，通過{d['flow']['primary_passed']}/9。全部逐點覆核{d['flow']['reviewed_rows']:,}，初步支持{d['flow']['initial_support']:,}，通過所有研究／實作資格0；不能把初步支持當有效建議數。

門檻沿既有SMD≤.1、兩臂ESS≥500、ECE≤.03、無fit警告，兩個開發年度與2024均過才取得比較資格。主要overlap及次要IPW分列不同estimand。新ledger只用當時已知母體、過去cell與有效機率作initial_support；年度／開發資格及review_rejection是回溯研究稽核，非當時可知訊號。實際換投／未來Y／觀測狀態不入資格判斷；不把被換下標籤補正常。

六個RP主要條件結果（兩目標×三年）增加300次game×pitcher pigeonhole配對Brier差95%區間；只針對固定模型、有觀測結果與各自過去常數，不含重訓不確定性、不解決選擇偏差，屬探索性邊際區間，不作多重比較保證。逐年覆蓋、缺失原因、g≥.1加權／最壞界限及odds情境重算保留。

16五道資格：前推比較、多燈預測支持、共同時點四群／價值／持續性回放、人選聯合支持與實際可用性、同半局終點及共同後續策略；目前均未取得通過。共同比較時點沒有可借用的未來打者D，原較晚時點xWPA／候選行為不能直接代入。這些是實作／識別缺口，不是調高門檻到沒建議，也不能用換分類器直接補齊。

16候選策略契約：同一合法index boundary比較續投與既有兩紅含A/B、成熟度、fresh-block持續性及14.2價值／合法／可用性等全門檻觸發換投；接任從當時合法、有自身歷史／聯合機率支持且確認可用的名義RP等機率抽樣，沒有支持或關鍵未知則abstain，不作最佳人選排名。兩臂後續用相同版本調度策略。主要終點守方WE(同當前／即將開始半局自然終點)-WE(anchor)，次要RE(anchor)-失分-RE(同終點)，納入所有中間play／IBB／跑壘與吸收終局；原nonout／十球偏離不替代策略收益。這是待實作的feasibility契約，沒有計算值。16才可在資格過後做direct／SNIPS／DR、相同joint支持及群聚區間／敏感度。

下一步先另立修訂協定處理拒絕清單，不自動跳16或以15.4done當授權。新產物`data/research/decision_entry_review_v1/`、摘要`data/sample/petehub_pitcher_decision_entry_review_v1.json`、audit另存；Lab#entry-review及規劃總覽同步。重跑先核對協定與原hash：build_decision_entry_review.py freeze→review --year2022/23/24→finish；export_decision_entry_review.py build/finish→export_pitcher_decision_plan.py→sync_project_tracker.py→manifest→audit_decision_entry_review.py。原產物及source不得靜默改。

'''
    text=text.replace('## 2026-11-21：15.3 RP目標與受限母體研究完成（最新）','## 2026-11-21：15.3 RP目標與受限母體研究完成（歷史版本）')
    at=text.index('## ');path.write_text(text[:at]+section+text[at:],encoding='utf-8')


def manifest():
    sources=[Path(__file__),Path(e.__file__),ROOT/'backend/scripts/audit_decision_entry_review.py',ROOT/'backend/tests/test_decision_entry_review.py',SAMPLE]
    files=sorted(p for p in e.OUT.iterdir() if p.is_file() and p.name not in ['manifest.json','audit.json'])
    e.save('manifest.json',{'version':'decision_entry_review_v1','files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':e.q.b.digest(p)} for p in files],
        'sources':{p.relative_to(ROOT).as_posix():e.q.b.digest(p) for p in sources},'stop':'15.4','test2025_outcomes_examined':False})
    print(f'15.4 {len(files)} artifacts frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['start','build','finish','manifest']);args=parser.parse_args()
    if args.stage=='start':update()
    elif args.stage=='finish':update(True);handoff()
    else:globals()[args.stage]()
