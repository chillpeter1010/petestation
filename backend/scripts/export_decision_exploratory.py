"""Publish16.1-3 research, timeline and explicit formal-efficacy limitations."""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import re
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_exploratory as x
from scripts.export_decision_model_patch import load_project,change_field
from scripts.export_decision_action_research import trace_points

ROOT=x.ROOT;OUT=x.OUT;SAMPLE=ROOT/'data/sample/petehub_pitcher_decision_exploratory_v1.json'


def cluster_mean(frame,key):
    if not len(frame):return {'n':0,'mean':None,'interval':None,'games':0}
    groups=frame.groupby('game_pk')[key].agg(['sum','count']);rng=np.random.default_rng(x.SEED);values=[]
    for _ in range(300):
        take=rng.integers(0,len(groups),len(groups));sample=groups.iloc[take];values.append(float(sample['sum'].sum()/sample['count'].sum()))
    return {'n':len(frame),'games':len(groups),'mean':float(frame[key].mean()),'interval':[float(v) for v in np.quantile(values,[.025,.975])]}


def build():
    options=pd.read_parquet(OUT/'options_2024.parquet');cases=options[options.is_current]
    expected=(len(cases)+31)//32;parts=[];excluded=[]
    for batch in range(expected):
        parts.append(pd.read_parquet(OUT/f'scenarios_{batch:03d}.parquet'));excluded+=x.read(OUT/f'excluded_{batch:03d}.json')
    values=pd.concat(parts,ignore_index=True);assert not values.duplicated(['decision_id','variant']).any()
    attempted=set(values.decision_id)|{v['decision_id'] for v in excluded};assert attempted==set(cases.decision_id)
    x.write(values,'scenarios_all.parquet');x.save('excluded_all.json',excluded)
    replay=pd.read_parquet(OUT/'replay_2024.parquet');main=values[values.variant.eq('full_pool')&values.status.eq('modeled')]
    main=main.merge(replay[['decision_id','emitted']],on='decision_id',validate='one_to_one');summary=[]
    for variant,g in values.groupby('variant'):
        modeled=g[g.status.eq('modeled')]
        row={'variant':variant,'modeled':len(modeled),'insufficient_pool':int(g.status.ne('modeled').sum())}
        for horizon in ['pa','half']:
            supported=modeled[modeled[horizon+'_supported'].eq(True)]
            row[horizon]={'supported':len(supported),'directions':modeled[horizon+'_direction'].value_counts().to_dict(),
                'extrapolated':int(modeled[horizon+'_extrapolated'].eq(True).sum()),'censored':int(modeled[horizon+'_censored'].eq(True).sum()),
                'rare_transition':int(modeled[horizon+'_unsupported_mass_max'].gt(.01).sum()),
                'wpa':cluster_mean(supported,horizon+'_wpa_delta'),'re24':cluster_mean(supported,horizon+'_re24_delta')}
        summary.append(row)
    sensitivity=[]
    for variant in ['rest24','load72_le40','other_model']:
        paired=main.merge(values[values.variant.eq(variant)&values.status.eq('modeled')],on='decision_id',suffixes=('_main','_variant'))
        for horizon in ['pa','half']:
            g=paired[paired[horizon+'_supported_main'].eq(True)&paired[horizon+'_supported_variant'].eq(True)]
            sensitivity.append({'variant':variant,'horizon':horizon,'common_supported':len(g),
                'direction_changed':int(g[horizon+'_direction_main'].ne(g[horizon+'_direction_variant']).sum()),
                'mean_delta_change':float((g[horizon+'_wpa_delta_variant']-g[horizon+'_wpa_delta_main']).mean()) if len(g) else None})
    pool=options[options.nominal_pool&~options.is_current]
    candidate_coverage={'nominal_rows':len(pool),'own_history_supported':int(pool.history_supported.sum()),'boundaries_with2':int(pool[pool.history_supported].groupby('decision_id').size().ge(2).sum()),
        'recent_known':int(pool.recent_at.notna().sum()),'clock_violations':0,'borrowed_incumbent_live':int(pool[x.LIVE].notna().any(axis=1).sum()),
        'fields_present':{k:int(pool[k].notna().sum()) for k in x.NUM+x.LIVE},'actual_availability':'unknown'}
    bundle=joblib.load(OUT/f"model_2024_{x.read(OUT/'selection.json')['selected']}.joblib");range_diagnostics=[]
    for label,g in [('incumbent',options[options.is_current&options.history_supported]),('nominal_candidate',pool[pool.history_supported])]:
        counts={key:int((g[key].notna()&~g[key].between(low,high)).sum()) for key,(low,high) in bundle['numeric_ranges'].items()}
        range_diagnostics.append({'actor':label,'rows':len(g),'outside_any':int((~x.in_range(g,bundle)).sum()),'outside_by_field':dict(sorted(counts.items(),key=lambda kv:-kv[1]))})
    full_replay=x.read(OUT/'replay_2024.json')['groups']
    selected=replay[replay.game_pk.isin(x.read(OUT/'cases.json')['games'])];alerts=selected[selected.emitted]
    study={'version':OUT.name,'stop':'16.3','updatedAt':'2026-11-21','progress':{'done':51,'total':58},
        'protocol':x.read(OUT/'protocol.json'),'protocolHash':x.b.digest(OUT/'protocol.json'),
        'replay':[x.read(OUT/f'replay_{y}.json') for y in [2022,2023,2024]],
        'caseFlow':{'games':int(cases.game_pk.nunique()),'boundaries':len(cases),'modeled':len(main),'excluded':len(excluded),'alerts':len(alerts),
            'alerts_modeled':int(main.emitted.sum()),'alerts_pa_supported':int((main.emitted&main.pa_supported).sum()),'alerts_half_supported':int((main.emitted&main.half_supported).sum()),
            'exclusion_reasons':pd.Series([v['reason'] for v in excluded],dtype='string').value_counts().to_dict()},
        'candidateCoverage':candidate_coverage,'rangeDiagnostics':range_diagnostics,'selection':x.read(OUT/'selection.json'),
        'bridgeValidation':[x.read(OUT/f'fit_{y}.json') for y in [2022,2023,2024]],'scenarios':summary,'sensitivity':sensitivity,
        'balance_reference':x.read(x.f.entry.OUT/'evidence.json')['primary_folds'],
        'formal_efficacy_passed':False,'formal_efficacy_status':'not_estimated',
        'formal_methods':{'direct':'conditional model scenarios only, not causal policy value','SNIPS':'not_estimated_missing_joint_support','DR':'not_estimated_missing_joint_support'},
        'recommendation_allowed':False,'individual_ranking_allowed':False,'test2025_outcomes_examined':False,
        'methodNotes':['16.1是沿實際歷史的影子回放；發出提醒後仍使用實際投手後續資料，不是照建議改寫整場比賽。',
            '提醒沿15.5下一PA失分風險，不是已通過四群燈號／替代收益的換投建議；實際換投對應不等於正確率。',
            '16.2是下一完整一般打席；16.3是兩方案皆由選定投手投到半局結束的模型情境。未模擬IBB／獨立跑者事件、熱身、醫療、後續換投與牛棚長期成本。',
            '共同截點比較模型同時包含實際續投與接任案例；人選只用自身截點前能力、72／120小時負荷與最近三次已閉合且同量測版本的登板摘要，候補當場數據未知。',
            '只首PA可使用現任即時PE／狀態；後續回到共同基準，球數依訓練分布更新，不把當下下降固定延伸到局末。預定前三棒來自過去棒次，第四棒後回聯盟先驗。',
            '點區間只含配對蒙地卡羅誤差；全案例平均另列比賽群聚描述區間，重疊決策點不可加總成球隊收益或當成獨立決策。',
            '第一PA外推診斷另列各欄位，不可加總重複人選。歷史打席數自然累積超過訓練上限也會被保守範圍門檻拒絕，並非缺少打者／投手資料；本輪不事後放寬，可另版研究有效樣本數飽和或有界表示。',
            '原15.4正式資格保留，SMD未重估，SNIPS／DR尚不具共同人選／可用性與後續策略支持。探索研究完成不代表正式效益通過；2024是重用診斷、2025封存。']}
    x.save('evidence.json',study);x.b.save_json(SAMPLE,study);print('16.1-3 scenarios and reliability evidence published',flush=True)


def traces():
    bundle=joblib.load(x.context(2024));games=[];sources=[];values=pd.read_parquet(OUT/'scenarios_all.parquet');replay=pd.read_parquet(OUT/'replay_2024.parquet')
    options=pd.read_parquet(OUT/'options_2024.parquet');anchors=x.value_state(options[options.is_current].reset_index(drop=True),bundle).set_index('decision_id')
    with x.b.connection() as c,threadpool_limits(limits=2):
        for name in ['decisions','plays','events']:c.read_parquet(str(x.FOUND/f'{name}_2024.parquet')).create_view(name)
        c.read_parquet(str(ROOT/'data/research/decision_support_slice1_20261112/feed_inventory_2024.parquet')).create_view('inventory')
        for game_pk in x.read(OUT/'cases.json')['games']:
            meta=c.execute('SELECT path,compressed_sha256 FROM inventory WHERE game_pk=?',[game_pk]).fetchone();path=Path(meta[0]);assert x.b.digest(path)==meta[1]
            payload=json.loads(gzip.decompress(path.read_bytes()));names={int(pid.removeprefix('ID')):p.get('fullName',pid) for pid,p in payload['gameData']['players'].items()}
            descriptions={int(p['about']['atBatIndex'])+1:p.get('result',{}).get('description','') for p in payload['liveData']['plays']['allPlays']}
            frame=c.execute('''SELECT d.*,p.scheduled_innings,p.outs_after,p.base_state_after,p.home_score_after,p.away_score_after,p.terminal_pitcher_id,p.is_complete,p.event_type,e.last_event_index
                FROM decisions d JOIN plays p USING(outcome_key) JOIN(SELECT game_pk,at_bat_number,max(event_index) last_event_index FROM events GROUP BY ALL)e ON d.game_pk=e.game_pk AND d.at_bat_number=e.at_bat_number
                WHERE d.game_pk=? AND d.decision_id LIKE '%:boundary' ORDER BY d.at_bat_number''',[game_pk]).fetchdf()
            frame['description']=frame.at_bat_number.map(descriptions).fillna('');frame.loc[frame.outs_after.ge(3),'base_state_after']=0
            points=trace_points(frame,bundle);mapping={int(row.at_bat_number):(i,int(row.last_event_index)) for i,row in enumerate(frame.itertuples())}
            # Shadow anchor is immediately after previous completed play, before the PA's actual decision.
            current=replay[replay.game_pk.eq(game_pk)];anchor_x={}
            for row in current.itertuples():
                ordinal=mapping[int(row.at_bat_number)][0];anchor_x[row.decision_id]=float(ordinal)
                before=next((p for p in points if p['decisionId']==row.decision_id and p['phase']=='before'),None)
                if before:
                    a=anchors.loc[row.decision_id];previous=frame.iloc[ordinal-1] if ordinal else None
                    anchor=before.copy();anchor.update(phase='anchor',x=float(ordinal),homeWe=float(a.research_home_we),homeWpa=None,
                        outs=int(a.outs),bases=int(a.base_state),pitcherId=int(a.outgoing_pitcher_id),
                        batterId=int(a.forecast1_id) if pd.notna(a.forecast1_id) else None,description='共同決策截點；打者是由過去棒次推估，非事後下一打者。')
                    if previous is not None:anchor.update(homeScore=int(previous.home_score_after),awayScore=int(previous.away_score_after))
                    points.append(anchor)
            for point in points:point.update(pitcherName=names.get(point['pitcherId'],str(point['pitcherId'])),batterName=names.get(point['batterId'],str(point['batterId'])) if point['batterId'] is not None else '尚未觀測棒次')
            actual=[]
            for row in c.execute('SELECT event_id,event_time,at_bat_number,event_index,pitcher_id,previous_pitcher_id,description FROM events WHERE game_pk=? AND is_pitch_change ORDER BY at_bat_number,event_index',[game_pk]).fetchdf().itertuples():
                if int(row.at_bat_number) not in mapping:continue
                ordinal,last=mapping[int(row.at_bat_number)];actual.append({'eventId':row.event_id,'at':row.event_time,'x':ordinal+(row.event_index+1)/(last+2),'incomingId':int(row.pitcher_id),'outgoingId':int(row.previous_pitcher_id) if pd.notna(row.previous_pitcher_id) else None,'description':row.description})
            alarms=[{'decisionId':row.decision_id,'x':anchor_x[row.decision_id],'risk':float(row.risk),'threshold':float(row.threshold),'role':row.role,'match':row.match,'targetObserved':bool(row.target_observed)} for row in current[current.emitted].itertuples()]
            comparisons=values[values.game_pk.eq(game_pk)&values.variant.eq('full_pool')&values.status.eq('modeled')]
            teams=payload['gameData']['teams'];games.append({'gamePk':game_pk,'year':2024,'date':payload['gameData']['datetime']['officialDate'],'home':teams['home']['name'],'away':teams['away']['name'],
                'points':sorted(points,key=lambda p:p['x']),'actualChanges':actual,'researchPoints':[],'shadowWarnings':alarms,'scenarios':json.loads(comparisons.to_json(orient='records')),'playerNames':names,'exploratory':True})
            sources.append({'game_pk':game_pk,'path':str(path),'sha256':meta[1]})
    x.save('traces.json',{'games':games,'sources':sources});study=x.read(SAMPLE);study['timeline']=games;x.b.save_json(SAMPLE,study)
    print(f'16.1: {len(games)} official WE/WPA timelines with shadow/actual markers exported',flush=True)


def update():
    path,text,begin,end,project,decoder=load_project();segment=text[begin:end]
    def span(sid):
        match=re.search(r'"id"\s*:\s*'+re.escape(json.dumps(sid))+r'\s*,',segment);assert match
        at=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,at);return at,finish,item
    at,finish,item=span('16');block=segment[at:finish]
    for key,value in [('status','in_progress'),('label','Slice 16 · 探索性回放、情境模擬與正式效益覆核'),
        ('deliverable','16.1–16.3先完成整合影子回放、下一PA與固定半局模型情境。原direct／SNIPS／DR正式效益評估仍須共同人選／可用性支持、平衡與後續策略對齊，另行授權後續修訂。'),
        ('verification','2026-11-21：使用者授權探索修訂16.1–16.3，另版產物完成；原15.4正式SMD／人選／可用性／後續策略資格未通過，不能將探索模擬視為策略有效。'),
        ('acceptance','探索完成與正式效益通過分開。保留原15.4契約與門檻；不以模型情境平均、配對率或MC區間啟用推薦或開封2025。')]:block=change_field(block,key,value,decoder)
    segment=segment[:at]+block+segment[finish:];anchor='16'
    for sid,title,deliverable,acceptance in [
        ('16.1','整場影子回放與實際換投對應','合併SP／RP共同截點，套用跨角色同隊冷卻；2022–24全母體提醒負擔與未知、固定32場實際WE／WPA時間軸及官方換投標記。','沿實際歷史，非反事實整場路徑；實際換投配對不是正確率，多燈／替代收益正式門檻保留。'),
        ('16.2','共同截點人選與下一PA情境','以實際續投／接任者重建同截點自身歷史，2022/23前推固定比較模型，再作2024固定32場全部邊界候選池下一完整PA估值與coverage。','候補不借現任當場狀態；相同起點／一般PA終點，時點與機率和核對；不將模型值稱因果效益。'),
        ('16.3','固定半局模擬與可靠性評估','兩方案各由選定投手留至半局結束，配對路徑、支持／截尾／外推、休息與72小時負荷／基準模型敏感度及群聚描述區間。','只含明定的模型情境，無IBB／獨立跑者事件／長期成本；MC區間非模型或因果區間，SNIPS／DR不具資格時明列未估計。')]:
        if not any(s['id']==sid for s in project['slices']):
            _,finish,_=span(anchor);item={'id':sid,'phase':'validation','label':'Slice '+sid+' · '+title,'status':'done','depends_on':['15.5.4'] if sid=='16.1' else [anchor],
                'deliverable':deliverable,'verification':'2026-11-21：研究工作交付，結果與限制見探索回測證據；畫面待使用者驗收。','acceptance':acceptance,'evidence':str(SAMPLE.relative_to(ROOT)).replace('\\','/')}
            block=json.dumps(item,ensure_ascii=False,indent=2);segment=segment[:finish]+',\n    '+block.replace('\n','\n    ')+segment[finish:]
        anchor=sid
    for key,value in [('updated_at','2026-11-21'),('summary','16.1–16.3探索回測交付51/58；整合提醒、共同截點人選與下一PA／固定半局情境另版完成。正式策略效益未通過、2025封存。'),
        ('next_step','使用者驗收Lab#exploratory-replay單場提醒與實際換投時間軸；依支持與敏感度結果決定正式效益修訂。原15.4資格保留，16主項進行中，17–21未啟動。')]:segment=change_field(segment,key,value,decoder)
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(text[:begin]+segment+text[end:])
    print('Authority updated:51/58,16 parent in progress, stop16.3',flush=True)


def manifest():
    sources=[Path(__file__),Path(x.__file__),ROOT/'backend/tests/test_decision_exploratory.py',ROOT/'backend/scripts/audit_decision_exploratory.py',SAMPLE]
    paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in ['manifest.json','audit.json'])
    x.save('manifest.json',{'version':OUT.name,'files':[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':x.b.digest(p)} for p in paths],
        'sources':{str(p.relative_to(ROOT)):x.b.digest(p) for p in sources},'stop':'16.3','test2025_outcomes_examined':False})
    print(f'{len(paths)} exploration artifacts frozen',flush=True)


def docs():
    d=x.read(SAMPLE);flow=d['caseFlow'];main=next(row for row in d['scenarios'] if row['variant']=='full_pool')
    heading='## 2026-11-21：16.1–16.3探索回測完成（最新）'
    path=ROOT/'docs/NEXT_CHAT_HANDOFF.md';text=path.read_text('utf-8')
    if heading not in text:
        section=f'''{heading}

使用者明確授權探索性16.1–16.3。新增三子項，進度 **51/58**，16主項仍in_progress（原正式direct／SNIPS／DR效益未完成），17–21未開始、2025封存，未commit／push。此前把正式效益資格與探索回測綁在一起過嚴，本輪另立協定放行探索，不改原15.4契約／失敗門檻、原模型或正式多燈；推薦／人選排名仍false，畫面驗收由使用者。

16.1：沿15.5兩角色下一PA失分模型，整合全部共同截點並採SP-to-RP同隊2PA冷卻，同半局／登板兩相鄰PA、一登板一次。2022–24全母體回放，沒有早局刪除或依實際換投／標籤挑點。2024共138074點／2427場，2748提醒、1172前三局、2506可觀測／242未知，觀測失分987／2506；同邊界208、提前1–2PA且600秒內288。這是既有合法cohort對應，非全部官方事件召回或正確率；未知不算誤報，尚未套正式四燈／替代收益門檻。合併後數量恰與分角色相同，不宣稱新冷卻降低提醒。歷史不因提醒而改寫，不是反事實整場路徑。

16.2：2021–24共同截點重建actual actor（續投與實際RP接任）觀測標籤，不編碼事後身分。候補池連嚴格先前名義快照，去除已進場及現任；自身ASOF角色九類能力／手別、72／120小時用球、距上球時間、最近三次同Plus量測版本已閉合登板的相對Stuff／Location／球速與資料年齡。候補當場PE／狀態保持NaN，不借現任；熱身／健康未知。首三棒僅由過去已完成棒次預測，不使用actual next batter。observed標籤需單一actor、organic PA起點不早於anchor、終點不晚於game-close且初始局面一致；官方第三出局殘壘轉半局終止post_base=0後才檢查守恆。2024可觀測137539例，其中自身歷史支持131742例。

六個新橋接擬合（base/rich×三前推年），整場80/20 fit/cal、跨界場排除、fit自然cap60000、HGB7葉60/L2=10、cal溫度；前推2022/23平均LL base={d['selection']['development_mean_log_loss']['base']:.9f}、rich={d['selection']['development_mean_log_loss']['rich']:.9f}，依凍結最低平均LL排序選{d['selection']['selected']}，微小差距不稱顯著增益。2024重用診斷；LL與AUC是含actual entries的新cohort，不與15.5原投手續投作純模型比較。

固定MD5前{flow['games']}場全部{flow['boundaries']}邊界，{flow['modeled']}可估／{flow['excluded']}拒絕；{flow['alerts']}提醒中{flow['alerts_modeled']}可估、{flow['alerts_half_supported']}有半局模擬支持。完整名義支持池：下一PA支持{main['pa']['supported']}／半局支持{main['half']['supported']}；半局方向{main['half']['directions']}。個別點不代表獨立決策、不能相加成季效益。

16.3：uniform own-history-supported nominal RP、至少2人；256共同路徑、MAX32PA、兩臂皆選定投手留半局。第一PA用選定橋接，後續base且清空live PE／狀態，球數取訓練role×outcome分布；下PA休息回訓練局中現任中位數，不把入場前休息延續。前三棒後回先前UTC日聯盟先驗，WE／RE及轉移只前年度訓練。未模擬IBB／獨立跑者事件、後續教練行為或牛棚長期成本，非原15.4共同後續行為策略估計。unsupported最大類別質量>.01、任何路徑外推或截尾則未知；MC95只含模擬誤差、不含模型／因果不確定。群聚案例平均僅描述；休息>=24h、72h<=40球與未選用模型的共同支持敏感度另列。

`decision_exploratory_v1/`含全部逐點回放、own-actor標籤／32場options、六模型／split／排序、56批場景與排除、匯總、32場官方WE/WPA曲線及實際換投／影子提醒。共同anchor重新計WE與過去預定打者；實際事件圖層是事後描述。原1699檔hash留版。attempt0保存初稿型別／慢回放；attempt1保存未正規化第三出局殘壘的錯誤篩樣本、試算模型／場景及協定，不參與最終結果。正式SMD未重估；SNIPS／DR缺共同人選／可用性機率及後續策略支持，明列未估計，不能稱效益通過。

摘要`petehub_pitcher_decision_exploratory_v1.json`，audit另存；Lab `/lab/decision-support#exploratory-replay`。重現：先核對舊hash及protocol，build_decision_exploratory.py freeze→replay2022/23/24→prepare2021–24→train2022/23→select（必須先於2024新模型；既有版本不可原位重選）→train2024→scenarios --batch0..55；export_decision_exploratory.py build→traces→update→docs→export_pitcher_decision_plan.py→sync_project_tracker.py→manifest→audit_decision_exploratory.py。全部source-only，沒有browser／截圖／DOM或替代UI server。

'''
        text=text.replace('## 2026-11-21：15.5.1–15.5.4預測修訂研究完成（最新）','## 2026-11-21：15.5.1–15.5.4預測修訂研究完成（歷史版本）')
        at=text.index('## ');path.write_text(text[:at]+section+text[at:],encoding='utf-8')
    api=ROOT/'docs/API_CONTRACTS.md';text=api.read_text('utf-8');heading='## Decision Support16.1–16.3探索回測（2026-11-21，最新）'
    if heading not in text:
        section=f'''{heading}

Build-time新增`exploratoryReplay`，來源`petehub_pitcher_decision_exploratory_v1.json`。不新增HTTP API。`replay`列2022–24同隊跨SP／RP冷卻回放、各角色提醒／早局／未知／同邊界與提前對應；不是正式多燈換投建議或正確率。`caseFlow`為固定MD5前32場全部共同截點，不依實際行動／收益挑場；`candidateCoverage`含名義人選列、自身歷史及逐欄coverage，當場候補live欄位NaN。`bridgeValidation/selection`六個共同截點actual-actor前推模型（base/rich），排序只2022/23，2024重用診斷。

`scenarios`下一完整organic PA／固定半局兩終點獨立：兩方案選定投手留半局、均勻名義RP池、256共同路徑、MAX32PA。`pa/half_supported`要求own-history／訓練人選群支持、無外推／截尾且最大缺轉移機率<=.01；灰點數值仍可診斷，不視為支持。第三出局後殘壘必須轉終止post_base=0。首PA可用現任live／自身候補近期閉合歷史，後續base清live，更新模擬球數及訓練局中休息；前三棒過去棒次預測後回過去聯盟先驗。未含IBB／獨立跑者事件／後續換投／長期成本，非原15.4後續行為策略。點`*_mc95_*`只含配對模擬誤差，`scenarios.*.wpa.interval`為支持案例均值的比賽群聚描述區間，不是因果收益。`sensitivity`在兩側共同支持案例計方向改變，分母不可混用或加總重疊點。

`timeline`32場沿官方歷史的凍結WE／WPA；`phase=anchor`為共同截點（重算WE、預定打者），`before/after`為事後實際局面。新增`shadowWarnings`與`scenarios`，舊`researchPoints`契約留版。黃色提醒與藍色實際換投分軌；提醒以decisionId選anchor，避免與上一PA after同x誤選。元件SVG clip／title ID每實例唯一，未知曲線保留缺口。

正式效益`formal_efficacy_passed=false`、`recommendation_allowed=false`、`individual_ranking_allowed=false`、`test2025_outcomes_examined=false`；原15.4資格與SMD未變、SNIPS／DR未估。進度51/58、16父項in_progress、16.1–3done、17–21planned。UI驗收使用者本人執行。

'''
        at=text.index('## ');api.write_text(text[:at]+section+text[at:],encoding='utf-8')
    print('Handoff and data contracts updated',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['build','traces','update','manifest','docs']);globals()[parser.parse_args().stage]()
