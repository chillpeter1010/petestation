"""Publish audited Slice13.1-13.4 evidence and scientific plots without browser QA."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import shutil
import re

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_role_models as m

r=m.r;b=r.b;OUT=r.OUT


def streak_audit() -> dict:
    with r.connect() as c:
        c.read_parquet(str(b.OUT/'observed_features_2024.parquet')).create_view('f')
        c.read_parquet(str(OUT/'workload_features_2024.parquet')).create_view('w')
        c.read_parquet(str(r.BASE/'workload_2024.parquet')).create_view('h')
        c.read_parquet(str(OUT/'appearance_history.parquet')).create_view('a')
        frame=c.execute('''SELECT f.decision_id,f.option_pitcher_id,f.option_role,f.consecutive_days legacy,
            w.consecutive_days repaired,h.current_session_consecutive_days old_session_reference,
            a.entry_day current_entry_day,cast(h.current_session_start AT TIME ZONE 'America/New_York' AS DATE) current_session_day
            FROM f JOIN w USING(decision_id,option_pitcher_id) JOIN h USING(decision_id)
            JOIN a ON a.appearance_id=h.appearance_id WHERE f.is_current''').fetchdf()
        entries=c.execute('SELECT pitcher_id,entry_day,pitches FROM a').fetchdf()
        sessions=c.read_parquet(str(r.BASE/'workload_sessions.parquet')).fetchdf()
    rp=frame[frame.option_role.eq('RP')].copy()
    differences=rp[rp.repaired.ne(rp.old_session_reference)].copy()
    entry_days={pid:{d.toordinal() for d in group.entry_day.dropna().dt.date} for pid,group in entries.groupby('pitcher_id')}
    session_days={pid:{d.toordinal() for d in group.session_day.dropna().dt.date} for pid,group in sessions.groupby('pitcher_id')}
    records=[]
    for row in differences.itertuples():
        entry_day=row.current_entry_day.date().toordinal();session_day=row.current_session_day.date().toordinal()
        entry_expected=r.prior_streak(entry_day,entry_days[row.option_pitcher_id])
        session_expected=r.prior_streak(session_day,session_days[row.option_pitcher_id])
        assert entry_expected==row.repaired and session_expected==row.old_session_reference
        records.append({'decision_id':row.decision_id,'pitcher_id':int(row.option_pitcher_id),
            'repaired_entry_streak':int(row.repaired),'old_physical_session_streak':int(row.old_session_reference),
            'current_entry_day':str(row.current_entry_day.date()),'current_physical_session_day':str(row.current_session_day.date()),
            'source_reconstruction_verified':True})
    result={'year':2024,'current_rp_rows':len(rp),'legacy_vs_repaired':int(rp.legacy.fillna(-999).ne(rp.repaired.fillna(-999)).sum()),
        'entry_vs_physical_session_differences':len(differences),'all_differences_reconstructed':True,'difference_rows':records,
        'scope':'Core uses NY appearance-entry day at actual/hypothetical entry. Physical pitch-day and decision-day counters retained separately; zero-pitch entries, midnight boundaries and resumed sessions can differ.'}
    r.save('streak_mapping_audit.json',result)
    return result


def coverage() -> list[dict]:
    rows=[]
    for year in r.YEARS:
        with r.connect() as c:
            c.read_parquet(str(OUT/f'current_features_{year}.parquet')).create_view('live')
            c.read_parquet(str(b.PREP/f'prepared_features_{year}.parquet')).create_view('f')
            live=c.execute('''SELECT f.role,count(*) n,count(live.live_research_stuff_plus) stuff,
                count(live.live_research_location_plus) "location",count(live.quality_plus) quality,
                count(live.physical_plus) physical,count(live.command_plus) command,
                count(live.mix_delta_research_stuff_plus) same_type_delta,
                count(*) FILTER(WHERE live.observation_at>=live.cutoff OR live.state_observed_at>=live.cutoff) time_violations
                FROM f JOIN live USING(decision_id) GROUP BY f.role''').fetchdf()
        rows.append({'year':year,'roles':json.loads(live.to_json(orient='records')),
            'workload':json.loads((OUT/f'workload_{year}.json').read_text('utf-8')),
            'recent':json.loads((OUT/f'recent_{year}.json').read_text('utf-8'))})
    return rows


def plots(curves: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt']='decision-role-observation-v2'
    import matplotlib.pyplot as plt
    for role in ['SP','RP']:
        fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
        for ax,(metric,axis,title) in zip(axes.flat,[('stuff','bf','Stuff / batters faced'),('location_value','bf','Location value / batters faced'),
            ('k','slot_encounter','K rate / observed lineup-slot encounter'),('bb','slot_encounter','BB rate / observed lineup-slot encounter')]):
            panel=next(p for p in curves['panels'] if p['role']==role and p['metric']==metric and p['axis']==axis)
            rows=panel['validation_2024'];x=np.array([row['bin'] for row in rows]);y=np.array([row['delta_vs_first_bin'] for row in rows])
            low=np.array([row['simultaneous95_low'] if row['simultaneous95_low'] is not None else np.nan for row in rows])
            high=np.array([row['simultaneous95_high'] if row['simultaneous95_high'] is not None else np.nan for row in rows])
            supported=np.array([row['supported'] for row in rows])
            scale=100 if metric in ['k','bb'] else 1
            ax.axhline(0,color='#64748b',linewidth=.8);ax.fill_between(x,scale*low,scale*high,color='#38bdf8',alpha=.18)
            ax.plot(x,scale*y,color='#0369a1',linewidth=1.5);ax.scatter(x[supported],scale*y[supported],color='#0369a1',s=24)
            ax.scatter(x[~supported],scale*y[~supported],facecolors='none',edgecolors='#94a3b8',s=24)
            ax.set_title(title,fontsize=10);ax.set_ylabel('Adjusted change (pp)' if scale==100 else 'Adjusted change (Plus points)')
            ax.set_xlabel('BF bin start (37 = 37+)' if axis=='bf' else 'Slot encounter (4 = 4+)')
            ax.grid(alpha=.18);ax.set_xticks(x)
        fig.suptitle(f'{role} | 2024 observed conditional curves | NOT substitution thresholds',fontsize=12)
        fig.text(.01,-.025,'Bands: within-panel simultaneous 95%, game x pitcher bootstrap; nuisance fit fixed. Open dots: insufficient support.\nObserved survivors only; no causal familiarity/fatigue claim. Different targets/axes are exploratory families.',fontsize=8)
        figure=OUT/f'decline_{role}_2024.svg'
        fig.savefig(figure,bbox_inches='tight',metadata={'Date':None});plt.close(fig)
        public=b.ROOT/'frontend/public/research/decision-role-observation-v2'
        public.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(figure,public/figure.name)


def finalize() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==m.protocol()
    audit=streak_audit();years=coverage()
    baseline=json.loads((OUT/'baseline_validation.json').read_text('utf-8'))
    curves=json.loads((OUT/'decline_curves.json').read_text('utf-8'))
    risks=json.loads((OUT/'risk_validation.json').read_text('utf-8'))
    plots(curves)
    curve_rows=[]
    for panel in curves['panels']:
        for period,key in [('training','training'),('validation_2024','validation_2024')]:
            for row in panel[key]:curve_rows.append({'role':panel['role'],'metric':panel['metric'],'axis':panel['axis'],'period':period,**row})
    pd.DataFrame(curve_rows).to_csv(OUT/'population_curve_points.csv',index=False,encoding='utf-8')
    cohorts=[json.loads((OUT/f'curve_cohort_{y}.json').read_text('utf-8')) for y in range(2021,2025)]
    protocol_hash=b.digest(OUT/'protocol.json')
    r.save('completion_summary.json',{'version':'decision_role_observation_v2','protocol_sha256':protocol_hash,
        'completed_slices':['13.1','13.2','13.3','13.4'],'not_started':['13.5','13.6','14.1','14.2','15'],
        'years':years,'baseline':baseline,'streak_audit':audit,'curve_cohorts':cohorts,
        'replicated_panels':curves['replicated_panels'],'risk_2024':[x for x in risks['reports'] if x['fold']=='frozen_2024'],
        'risk_target_caveat':'Drop relative to previous10 mean includes sampling noise/regression to mean; it is not necessarily below personal baseline, physiological fatigue or loss of run prevention. Incremental workload evidence remains Slice13.6.',
        'recent_window_clock':'day3/day5 select closed-and-available summaries in72/120 hours; pitch-count windows use actual completed-pitch times. Observation timestamps are appearance/state endpoints; individual valid pitch counts remain in history.',
        'publisher_sha256':b.digest(Path(__file__)),
        'formal_model_replaced':False,'recommendation_allowed':False,'test_outcome_metrics_examined':False})
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_1_v2.json',{'version':'decision_role_observation_v2','protocol_sha256':protocol_hash,'audit':audit,'years':[{'year':y['year'],**y['workload']} for y in years],'baseline_validation':baseline})
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_2_v2.json',{'version':'decision_role_observation_v2','protocol_sha256':protocol_hash,'years':[{'year':y['year'],'roles':y['roles']} for y in years],
        'scope':'Observed prefix levels, same-type deltas, personal past references and outcome support; not a causal fatigue or swap indicator'})
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_3_v2.json',{'version':'decision_role_observation_v2','protocol_sha256':protocol_hash,'years':[{'year':y['year'],**y['recent']} for y in years],
        'scope':'Closed same-role history with model-compatible Plus/state; raw timestamps and denominators retained; unknown readiness'})
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_4_v2.json',{'version':'decision_role_observation_v2','protocol_sha256':protocol_hash,'cohorts':cohorts,'curves':curves,'risk':risks,
        'figures':['data/research/decision_role_observation_v2/decline_SP_2024.svg','data/research/decision_role_observation_v2/decline_RP_2024.svg']})
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json' and '.tmp.' not in p.name]
    r.save('manifest.json',{'version':'decision_role_observation_v2','protocol_sha256':protocol_hash,
        'files':[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':b.digest(p)} for p in sorted(files)]})
    print(f'13.1-13.4 evidence published, {len(files)} artifact hashes',flush=True)


def update_tracker() -> None:
    evidence=json.loads((OUT/'completion_summary.json').read_text('utf-8'))
    path=b.ROOT/'docs/PROJECT_TRACKER.json'
    with path.open('r',encoding='utf-8',newline='') as stream:text=stream.read()
    decoder=json.JSONDecoder();position=text.index('"id": "pitcher-decision-support"');start=text.rfind('{',0,position)
    project,end=decoder.raw_decode(text,start);segment=text[start:end]
    def replace(block,old,new):
        token=json.dumps(old,ensure_ascii=False);assert block.count(token)==1
        return block.replace(token,json.dumps(new,ensure_ascii=False),1)
    options=sum(y['workload']['rows'] for y in evidence['years'])
    replicated=len(evidence['replicated_panels'])
    summary=f'13.1–13.4修訂完成，進度27/39。重建{options:,}個現任／候選負荷與近期觀測連結，修正連投並保留跨日／零球語意；完成當場狀態、近期同角色觀測與全體／個人條件曲線。訓練區段在2024重現的曲線面板{replicated}個，不能給通用換投切點；下一十球模型只驗證可觀測續投的相對Plus下降風險。原v1及中止實驗保留，正式推薦關閉。'
    next_step='本輪止於13.4；等待使用者指示13.5打者前序出棒／掌握度、熟悉度與相性，再做13.6增益消融及14.1／14.2修訂換投比較。近期狀態與條件風險不等於疲勞因果或換投優勢；2025／2026僅凍結評分。新研究圖與操作待使用者驗收，不自動開始13.5或15。'
    for key,value in [('summary',summary),('next_step',next_step)]:segment=replace(segment,project[key],value)
    descriptions={
        '13.1':f'2026-11-18：修訂版嚴格取完成時間<t，整合{options:,}個選項連結及24／72／120／168／336小時窗口。核心連投按實際／假定進場前紐約登板日重建；決策日曝光、零球進場、同日其他登板、季內序號、進場休息／live idle、本場與其他場負荷分開。2024現任RP有7,334／31,638列與原欄位不同，另20列與舊實投session日參考不同，已逐列重建核對。原基準白名單固定重訓，2024 n=137,699；新5日欄位未提前選模。2筆原始結束時鐘異常保留旗標／支持缺值。',
        '13.2':'2026-11-18：六季current_features／pa_features完成，原決策現任與首顆實投前實際單一actor分開。保存prefix及最近十球Stuff／Location、物理量、CSW／揮空／接觸／界外／場內／有效擊球品質、已完成PA之K／BB、同球種固定配比變化／斜率與進場前個人參考；附有效n及時間。三項狀態暖機、35／10及100／60範圍、>8h重啟、缺值均保留；嚴格時序檢查通過，不視為生理疲勞或換投建議。',
        '13.3':'2026-11-18：六季近期同角色閉合登板history及去重profile／option links完成，分別保留last1／3／5與近72／120小時已可用摘要、均值／有效登板n／描述性80%範圍、近期斜率、觀測時間與年齡；原始有效球數在history。Plus／三項狀態要求模型版本相容，raw可觀測量另列；無近期出賽不補正常，沒有熱身／健康／準備度推論。視窗固定為候選摘要，尚未做13.6預測增益選擇。',
        '13.4':f'2026-11-18：以2021–2023建條件參考、2024驗證，全體SP／RP×7指標×4曝光軸共56面板；區分BF、球數、打序slot交手、特定打者交手，控制對手／球路／局面等，200次比賽×投手重抽樣及面板內同時區間。依預定支持、實務幅度、連續兩區與同區段重現門檻，{replicated}面板重現，沒有已驗證通用／個人切點。歷史個人曲線向角色收縮並留出驗證；下一十球相對前十球下降5研究Plus點的條件模型按時間前推／訓練內校準，可觀測者較球數基準改善，但有設限、回歸均值與選擇限制。2025／2026僅機率。修復序列化guard及名冊篩選的初輪實驗／協定均保留，未改門檻。'
    }
    for sid,description in descriptions.items():
        match=re.search(r'(?m)^ {6}"id": '+re.escape(json.dumps(sid))+r',\r?$',segment);assert match
        begin=segment.rfind('{',0,match.start());item,finish=decoder.raw_decode(segment,begin);block=segment[begin:finish]
        for key,value in [('status','done'),('verification',description)]:block=replace(block,item[key],value)
        new_evidence=f'data/sample/petehub_pitcher_decision_slice{sid.replace(".","_")}_v2.json'
        if 'evidence' in item:block=replace(block,item['evidence'],new_evidence)
        else:
            token='      "verification": '+json.dumps(description,ensure_ascii=False)+','
            assert token in block
            nl='\r\n' if '\r\n' in block else '\n'
            block=block.replace(token,token+nl+'      "evidence": '+json.dumps(new_evidence)+',',1)
        segment=segment[:begin]+block+segment[finish:]
    result=text[:start]+segment+text[end:];updated=json.loads(result)
    p=next(p for p in updated['projects'] if p['id']=='pitcher-decision-support')
    assert len(p['slices'])==39 and sum(s['status']=='done' for s in p['slices'])==27
    with path.open('w',encoding='utf-8',newline='') as stream:stream.write(result)
    print('Tracker updated from UTF-8 source: 27/39; scope stops at13.4',flush=True)


if __name__=='__main__':
    finalize()
    update_tracker()
