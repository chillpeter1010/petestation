"""14.2.4 fixed-model state-event calibration and32-game replay."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_signal_models as m
from scripts import decision_signal_episodes as e

n,OUT,b,u=m.n,m.OUT,m.b,m.u


def monitoring_cohort(year):
    frame=pd.read_parquet(OUT/f'features_{year}.parquet')
    scores=pd.read_parquet(OUT/f'block_scores_{year}.parquet');scores=scores[scores.alpha.eq(n.ALPHA)]
    # One FIRST legal/model-cohort boundary per completed measurement block.
    frame=frame[frame.is_current&frame.block_id.notna()].sort_values(['decision_at','decision_id']).drop_duplicates('block_id',keep='first')
    # At a PA boundary the next numbered block may already be partly observed.
    # Evaluate only the first ENTIRELY future block, never reuse its past pitches.
    with n.r.connect() as c:
        c.register('q',frame);c.register('future',scores)
        labels=c.execute('''SELECT q.request_id,s.anchor_at target_anchor,s.available_at target_at,s.block_number target_block,
            s.residual_stuff,s.residual_velocity,s.residual_location FROM q ASOF LEFT JOIN future s
            ON q.session_id=s.session_id AND q.decision_at<=s.anchor_at''').fetchdf()
    frame=frame.merge(labels,on='request_id',validate='one_to_one')
    known=frame[['residual_stuff','residual_velocity','residual_location']].notna().all(axis=1)&frame.target_block.le(frame.block_number+2)
    frame['future_bad']=np.where(known,frame.residual_stuff.le(-5)|frame.residual_velocity.le(-.5)|frame.residual_location.le(-5),np.nan)
    assert (frame.loc[known,'target_anchor']>=frame.loc[known,'decision_at']).all()
    frame['complete']=frame[[g+'_state' for g in 'ABCD']].ge(0).all(axis=1)
    return frame


def risk_contrast(frame,flag):
    f=frame[frame.future_bad.notna()&frame.complete].copy();flag=flag.reindex(f.index).fillna(False).to_numpy(bool)
    y=f.future_bad.to_numpy(float);n1=int(flag.sum());n0=len(y)
    if n1==0 or n0==0:return {'n':n0,'flagged':n1,'appearances':0,'risk':None,'reference_risk':None,'difference':None,'interval':None}
    risk=float(y[flag].mean());reference=float(y.mean());delta=risk-reference
    influence=flag*(y-risk)/(n1/n0)-(y-reference)+delta
    interval=u.family_intervals(f,influence)[0]
    return {'n':n0,'flagged':n1,'appearances':int(f.loc[flag,'appearance_id'].nunique()),'risk':risk,'reference_risk':reference,
        'difference':delta,'interval':interval['role_family97_5']}


def normal_diagnostics():
    rows=[]
    for year in [2022,2023,2024]:
        f=pd.read_parquet(OUT/f'block_scores_{year}.parquet')
        for role in ['SP','RP']:
            slow=f[f.role.eq(role)&f.alpha.eq(n.ALPHA)].copy().reset_index(drop=True)
            fast=f[f.role.eq(role)&f.alpha.eq(1.)].set_index('block_id').loc[slow.block_id]
            slow['option_pitcher_id']=slow.pitcher_id
            for group in ['A','B','C']:
                valid=slow['future_'+group].notna()&slow[group+'_risk'].notna()&fast[group+'_risk'].notna().to_numpy()
                y=slow.loc[valid,'future_'+group].to_numpy();ps=slow.loc[valid,group+'_risk'].to_numpy();pf=fast.loc[valid.to_numpy(),group+'_risk'].to_numpy()
                cal=n.read(OUT/f'normal_{next(x[0] for x in n.FOLDS if x[2]==year)}_{role}.json')['calibrations'][f'{n.ALPHA}:{group}']
                if len(y)<50:continue
                against=(ps-y)**2-(pf-y)**2;constant=(ps-y)**2-(cal['prior']-y)**2
                intervals=u.family_intervals(slow.loc[valid].reset_index(drop=True),np.column_stack([against,constant]))
                rows.append({'year':year,'role':role,'group':group,'n':len(y),'censored_or_insufficient':int((~valid).sum()),
                    'smooth_brier':float(np.mean((ps-y)**2)),'raw_brier':float(np.mean((pf-y)**2)),
                    'constant_brier':float(np.mean((cal['prior']-y)**2)),'vs_raw':intervals[0],'vs_constant':intervals[1],
                    'predictive_gate':bool(intervals[0]['role_family97_5'][1]<0 and intervals[1]['role_family97_5'][1]<0)})
    n.save('normal_validation.json',{'rows':rows,'target':'future measured deviation, not physiological fatigue; continuers only, pointwise partial uncertainty','test2025_outcomes_examined':False})


def protocol():
    paths=[Path(__file__),Path(e.__file__),OUT/'normal_protocol.json',OUT/'feature_protocol.json',OUT/'model_protocol.json',OUT/'feature_guard.json',
        n.old.OUT/'protocol.json',n.old.OUT/'action_values.parquet',n.old.OUT/'point_ledger.parquet',n.old.OUT/'official_changes.parquet']
    paths += [OUT/f'features_{y}.parquet' for y in range(2021,2025)]
    return {'version':'multi_signal_episode_v1','input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'combo_candidates':[2,3],'selection':'pooled2022/23 first-boundary-per-block forward features; full4 groups supported, at least2/3 red includingA/B; >=20 flagged blocks and10 appearances, paired game x pitcher97.5 influence interval positive uplift for next ENTIRELY FUTURE block material A/B deviation, both annual uplift>=0; first supported in order2,3; otherwise2 exploratory only',
        'target_clock':'target block anchor>=decision_at; if next numbered block already began, use first entirely future block, at most2 block numbers ahead; no future block => censor, never negative',
        'validation':'selected frozen before2024 replay;2024 can reject predictive support but not select another configuration; no official event matching criterion used for selection',
        'persistence':'two consecutive NEW10-pitch block identifiers, same session; repeated PA reads of the same block never count as new evidence; raw gray resets entry and pauses active episode, not recovery',
        'recovery':'two fresh complete blocks with A/B green and C not red; D may stay high because cumulative load not erased. Then fresh deterioration can create another episode in same appearance',
        'ending':'session/appearance end is censored, not recovery. Active episode does not emit again, even through gray periods; only observed recovery permits rearming within session',
        'value_gate':'retain frozen32-game values if no outcome-model promotion; a passing role requires separately versioned first-PA sensitivity before any value replacement; no unobserved future state trajectory',
        'alerts':'one nominal research alert per state episode after cause support and value gates; same-team2 completed-PA cooldown; active/warmup/medical/manual unknown always blocks operational recommendation',
        'matching':'original same-boundary or1-2 completed defensivePA and600s, same game/team/outgoing appearance, chronological one-to-one; old11/0 preserved',
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'stop':'14.2.4'}


def freeze():
    value=protocol();path=OUT/'episode_protocol.json'
    if path.exists():assert n.read(path)==value
    n.save(path.name,value);print('14.2.4 multi-light episode/persistence/recovery protocol frozen',flush=True)


def select():
    assert n.read(OUT/'episode_protocol.json')==protocol()
    frames={y:monitoring_cohort(y) for y in [2022,2023]};rows=[];selected={}
    for role in ['SP','RP']:
        combined=pd.concat([f[f.forecast_role.eq(role)].assign(year=y) for y,f in frames.items()],ignore_index=True)
        for required in [2,3]:
            flag=combined.apply(lambda row:e.combination(row,required),axis=1)
            result=risk_contrast(combined,flag)
            annual=[risk_contrast(f[f.forecast_role.eq(role)],f[f.forecast_role.eq(role)].apply(lambda row:e.combination(row,required),axis=1)) for f in frames.values()]
            passed=result['flagged']>=20 and result['appearances']>=10 and result['interval'] is not None and result['interval'][0]>0 and all(x['difference'] is not None and x['difference']>=0 for x in annual)
            rows.append({'role':role,'minimum_red':required,**result,'annual':annual,'gate':bool(passed)})
        passing=[x for x in rows if x['role']==role and x['gate']]
        selected[role]={'minimum_red':passing[0]['minimum_red'] if passing else 2,'training_predictive_support':bool(passing)}
    n.save('episode_selection.json',{'selected':selected,'contrasts':rows,'2024_used_for_selection':False,'matching_used_for_selection':False})
    print('14.2.4 combination selection fixed from2022/23 only',flush=True)


def replay():
    assert n.read(OUT/'episode_protocol.json')==protocol()
    selection=n.read(OUT/'episode_selection.json');cohort=monitoring_cohort(2024);validation=[];supported={};thresholds={}
    for role,item in selection['selected'].items():
        part=cohort[cohort.forecast_role.eq(role)];flag=part.apply(lambda row:e.combination(row,item['minimum_red']),axis=1)
        result=risk_contrast(part,flag)
        gate=item['training_predictive_support'] and result['flagged']>=20 and result['appearances']>=10 and result['interval'] is not None and result['interval'][0]>0
        supported[role]=bool(gate);thresholds[role]=item['minimum_red'];validation.append({'role':role,**result,'diagnostic_gate':bool(gate)})
    points=pd.read_parquet(n.old.OUT/'point_ledger.parquet')
    features=pd.read_parquet(OUT/'case_features.parquet');features=features[features.is_current]
    columns=['decision_id','block_id','block_number','session_id','available_at',*[g+'_state' for g in 'ABCD'],*[g+'_severity' for g in 'ABCD']]
    points=points.merge(features[columns],on='decision_id',how='left',validate='one_to_one')
    # Value replacement, if necessary, is a separate versioned artifact.
    choices={role:n.read(OUT/f'pa_{role}.json')['selected'] for role in ['SP','RP']}
    if any(x!='retain_previous' for x in choices.values()):
        path=OUT/'value_sensitivity/action_values.parquet';assert path.exists(),'Passing role requires first-PA value sensitivity; do not silently retain old values'
        new=pd.read_parquet(path);keys=[c for c in new if c in points and c!='decision_id']
        points=points.drop(columns=keys).merge(new,on='decision_id',how='left',validate='one_to_one')
    logged,episodes=e.replay(points,thresholds,supported)
    n.write(logged,'signal_point_ledger.parquet');n.write(episodes,'state_episodes.parquet')
    alerts=logged[logged.nominal_research_alert].copy();events=pd.read_parquet(n.old.OUT/'official_changes.parquet')
    pairs=n.old.logic.match_events(alerts,events);n.write(pairs,'signal_matches.parquet')
    alerts=alerts.merge(pairs,on='decision_id',how='left',validate='one_to_one')
    alerts['match_reason']=[row.match_kind if pd.notna(row.match_kind) else n.old.logic.unmatched_alert_reason(row,events) for row in alerts.itertuples()]
    n.write(alerts,'signal_alerts.parquet')
    coverage=[]
    for role,g in logged[logged.wpa_delta.notna()].groupby('role'):
        coverage.append({'role':role,'modeled':len(g),'full_four':int(g[[x+'_state' for x in 'ABCD']].ge(0).all(axis=1).sum()),
            'states':{x:{str(int(k)):int(v) for k,v in g[x+'_state'].fillna(-1).value_counts().items()} for x in 'ABCD'},
            'state_episodes':int(episodes.role.eq(role).sum()),'research_alerts':int(alerts.role.eq(role).sum())})
    n.save('replay_summary.json',{'version':'multi_signal_episode_v1','selection':selection,'combination_validation2024':validation,
        'flow':{'raw_boundaries':len(logged),'modeled':int(logged.wpa_delta.notna().sum()),'full_four':int(logged[[x+'_state' for x in 'ABCD']].ge(0).all(axis=1).sum()),
            'state_episodes':len(episodes),'observed_recovery':int(episodes.end_reason.eq('observed_recovery').sum()),
            'nominal_research_alerts':len(alerts),'same_boundary':int(pairs.match_kind.eq('same_boundary').sum()),'advance_window':int(pairs.match_kind.eq('advance_window').sum()),
            'unmatched_alerts':int(alerts.event_id.isna().sum()),'official_events':len(events),'operational_recommendations':0},
        'roles':coverage,'point_reasons':logged.research_reason.value_counts().to_dict(),'episode_end_reasons':episodes.end_reason.value_counts().to_dict(),
        'retained_old_result':{'alerts':11,'matched':0},'first_PA_models':choices,'value_version':'retained14.2' if all(x=='retain_previous' for x in choices.values()) else 'new_first_PA_sensitivity',
        'interpretation':'threshold-calibrated tail states and future-measurement support are research proxies, not physiological fatigue/causal strategy correctness; gray pauses do not count as recovery',
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'14.2.4'})
    print(f'14.2.4 replay: {len(episodes)} state episodes, {len(alerts)} nominal research alerts, {len(pairs)} event matches; operational0',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','normal_diagnostics','select','replay']);args=parser.parse_args();globals()[args.stage]()
