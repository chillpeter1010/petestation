"""Slice 14: fixed-half, lineup-neutral continuation versus nominal RP pool.

Research scenarios only. No availability inference, individual ranking or recommendation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import make_pipeline
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_baselines as b

OUT=b.ROOT/'data/research/decision_action_values_v1'
SEED=20261118
PATHS=256
BOOTSTRAPS=8
MAX_PA=32
BATTER_COLUMNS=[f'batter_{key}_rate' for key in b.OUTCOMES]+['batter_own_split_n','batter_own_all_n','batter_ability_status','expected_stand']


def prepare() -> None:
    with b.connection() as c:
        c.read_parquet(str(b.PREP/'prepared_features_2024.parquet')).create_view('f')
        c.read_parquet(str(b.OUT/'observed_features_2024.parquet')).create_view('observed')
        c.read_parquet(str(b.ROOT/'data/research/decision_support_pipeline_20261114/decisions_2024.parquet')).create_view('d')
        games=[r[0] for r in c.execute('SELECT game_pk FROM f GROUP BY game_pk ORDER BY md5(cast(game_pk AS VARCHAR)) LIMIT 2').fetchall()]
        c.execute("""CREATE TABLE stratified AS SELECT f.decision_id FROM f JOIN observed o USING(decision_id)
            QUALIFY row_number() OVER(PARTITION BY f.role,o.observed_action,
                CASE WHEN f.research_pa_li<1 THEN 'low' WHEN f.research_pa_li<=2 THEN 'mid' ELSE 'high_or_unknown' END
                ORDER BY md5(f.decision_id))<=32""")
        c.execute('''CREATE TABLE cases AS SELECT f.*,o.observed_action,d.balls boundary_balls,d.strikes boundary_strikes
            FROM f JOIN observed o USING(decision_id) JOIN d USING(decision_id)
            WHERE f.decision_id IN(SELECT decision_id FROM stratified) OR f.game_pk IN (?,?)''',games)
        c.read_parquet(str(b.OUT/'option_features_2024.parquet')).create_view('o')
        c.execute('''CREATE TABLE options AS SELECT o.*,f.inning,f.half,f.scheduled_innings,f.defense_lead,
            f.outs,f.base_state,cast(f.inning>f.scheduled_innings AS INTEGER) extra,f.research_home_we,f.research_re
            FROM o JOIN cases f USING(decision_id)''')
        c.table('cases').write_parquet(str(OUT/'cases.parquet'),compression='zstd')
        c.table('options').write_parquet(str(OUT/'options.parquet'),compression='zstd')
    development=pd.concat([b.clean_model_frame(b.read_year(year,True))[0] for year in (2021,2022,2023)],ignore_index=True)
    assert development.pa_end_at.max()<pd.Timestamp('2024-01-01',tz='UTC').timestamp()
    # Generic future opposing batters are sampled from a frozen 2023-end player pool.
    # Their identity draws are paired across arms; handedness selects that player's history.
    with b.connection() as c:
        c.read_parquet(str(b.PREP/'ability_history.parquet')).create_view('h')
        history=c.execute("""SELECT * FROM h WHERE actor='batter' AND available_at<epoch(TIMESTAMPTZ '2024-01-01')
            QUALIFY row_number() OVER(PARTITION BY player_id,split ORDER BY available_at DESC)=1""").fetchdf()
        c.execute(f"CREATE VIEW plays AS SELECT * FROM read_parquet('{(b.ROOT/'data/research/decision_support_pipeline_20261114/plays_202[123].parquet').as_posix()}')")
        c.execute(f"CREATE VIEW labels AS SELECT * FROM read_parquet('{(b.PREP/'clean_labels_202[123].parquet').as_posix()}')")
        pitch_counts=c.execute('SELECT l.decision_id,p.pitch_count FROM labels l JOIN plays p USING(outcome_key)').fetchdf()
    all_history=history[history.split.eq('All')].set_index('player_id')
    frequencies=development.groupby('batter_id').size()
    players=sorted(set(all_history.index)&set(frequencies.index))
    weights=frequencies.loc[players].to_numpy(dtype=float);weights/=weights.sum()
    bats=development.sort_values('decision_at').groupby('batter_id').listed_bats.last()
    bank={}
    for hand in ('L','R','unknown'):
        split=history[history.split.eq(hand)].set_index('player_id')
        rows=[]
        for pid in players:
            own=all_history.loc[pid];specific=split.loc[pid] if pid in split.index else None
            chosen=specific if specific is not None and specific.pa_n>0 else own
            listed=bats.get(pid,'unknown')
            stand=listed if listed in ('L','R') else ('R' if hand=='L' else 'L' if hand=='R' else 'unknown') if listed=='S' else 'unknown'
            rows.append({**{f'batter_{key}_rate':float(chosen[f'{key}_n']/chosen.pa_n) for key in b.OUTCOMES},
                'batter_own_split_n':float(specific.pa_n) if specific is not None else 0.,
                'batter_own_all_n':float(own.pa_n),'batter_ability_status':'own_split' if specific is not None else 'own_all',
                'expected_stand':stand})
        bank[hand]=pd.DataFrame(rows)
    counts=development[['decision_id','target','option_role']].merge(pitch_counts,on='decision_id',validate='one_to_one')
    pitch_bank={}
    for role in ('SP','RP'):
        for target in range(9):
            values=counts.loc[(counts.option_role==role)&(counts.target==target),'pitch_count'].dropna().to_numpy(dtype=int)
            if len(values)<30:values=counts.loc[counts.target==target,'pitch_count'].dropna().to_numpy(dtype=int)
            assert len(values)>0 and np.min(values)>=1
            pitch_bank[(role,target)]=np.sort(values)
    joblib.dump({'profiles':bank,'cdf':np.cumsum(weights),'players':players,'pitch_counts':pitch_bank,
                 'max_training_pitches':development.groupby('option_role').option_game_pitches.max().to_dict()},OUT/'simulation_reference.joblib')
    b.save_json(OUT/'preparation.json',{'year':2024,'trace_games':games,'sample_strata':'32 per outgoing role x observed action x PA-LI group, plus all eligible trace-game decisions; not population weighted',
        'batter_pool_players':len(players),'future_lineup':'same paired historical 2023-end league batter draws, not observed future batters',
        'training_n':len(development)})
    print(f'Slice14 input cases prepared; trace games {games}',flush=True)


def protocol() -> dict:
    paths=[Path(__file__),Path(b.__file__),b.OUT/'protocol.json',b.OUT/'matchup.joblib',b.OUT/'transitions.joblib',
           OUT/'cases.parquet',OUT/'options.parquet',OUT/'simulation_reference.joblib',OUT/'preparation.json']
    return {'version':'decision_action_values_v1','input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'evaluation_year':2024,'seed':SEED,'paths_per_arm':PATHS,'maximum_completed_pa':MAX_PA,'bootstrap_models':BOOTSTRAPS,
        'model':'frozen Slice12 matchup alpha=.001 pooling=20; Slice13 signal trajectories are not projected',
        'arms':'current pitcher through half end vs uniformly selected nominal previously-observed RP through half end; no later substitution',
        'legality':'Slice11 both-actions nominal legal boundary; pitcher stays to inning end, satisfying three-batter minimum/inning-end exception; injury/medical/warmup availability unknown',
        'pool_support':'zero-ball/strike nominal legal boundary; known past RP role, >=30 own-all PA, known L/R hand, complete 14d lookback and known rest; at least two candidates; current >=30 own-all and known hand',
        'future_batters':'actual next batter only at first PA; later batters paired from frozen 2023-end league pool with hand-specific past rates, not future actual lineup',
        'workload':'increment game/rolling pitches using training-only target/role pitch-count distribution; BF +1; entry rest/history fixed; is_current true after first PA',
        'transitions':'training-only joint conditional tables, legal runner conservation, walk-off non-HR winning-run cap and terminal WE rules',
        'endpoint':'current half-inning end or walk-off; same policy in both arms; beyond-half strategy neutral WE reference; xRE24=start RE-total runs',
        'uncertainty':'paired Monte Carlo 95% normal-error interval, plus descriptive central80% across 8 game-cluster classifier refits with fixed preprocessing/transition/WE/RE; not complete uncertainty or a causal CI',
        'limits':'censored tails or model pitch-count extrapolation block supported preference; no long-term bullpen resource cost, exact future lineup, signal progression, causal policy value or individual ranking',
        'test_policy':'no 2025/2026 outcome metrics; no test-based selection','recommendation_gate':False}


def freeze() -> None:
    path=OUT/'protocol.json';value=protocol()
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen action protocol changed; use a new version')
    b.save_json(path,value);print('Slice14 protocol frozen before scenario outputs',flush=True)


def bootstrap() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    frame=pd.concat([b.clean_model_frame(b.read_year(year,True))[0] for year in (2021,2022,2023)],ignore_index=True)
    bundle=joblib.load(b.OUT/'matchup.joblib');model=bundle['model']
    x=model[0].transform(b.design(frame,'matchup',bundle['pooling'],bundle['prior']))
    codes, games=pd.factorize(frame.game_pk,sort=True)
    weights=1/frame.groupby('game_pk').decision_id.transform('count').to_numpy()
    rng=np.random.default_rng(SEED);reports=[]
    with threadpool_limits(limits=2):
        for i in range(BOOTSTRAPS):
            count=np.bincount(rng.integers(0,len(games),len(games)),minlength=len(games))
            sample_weight=weights*count[codes];sample_weight/=sample_weight.mean()
            learner=clone(model[-1]).set_params(random_state=SEED+i+1)
            print(f'Bootstrap classifier {i+1}/{BOOTSTRAPS}: {len(frame):,} training PA',flush=True)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always',ConvergenceWarning)
                learner.fit(x,frame.target,sample_weight=sample_weight)
            fit=make_pipeline(model[0],learner)
            joblib.dump({**bundle,'model':fit},OUT/f'bootstrap_{i}.joblib')
            reports.append({'replicate':i,'unique_games':int((count>0).sum()),'convergence_warning':any(isinstance(w.message,ConvergenceWarning) for w in caught)})
    b.save_json(OUT/'bootstrap.json',{'conditional_on_fixed_preprocessing_transition_WE_RE':True,'replicates':reports})


def supported_options(cases: pd.DataFrame, options: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame,list[dict]]:
    accepted=[];option_rows=[];excluded=[]
    for row in cases.itertuples():
        group=options[options.decision_id.eq(row.decision_id)]
        current=group[group.is_current]
        pool=group[~group.is_current & group.option_role.eq('RP') & group.role_known & group.pitcher_own_all_n.ge(30)
            & group.pitcher_hand.isin(['L','R']) & group.lookback_14d_complete & group.rest_hours.notna()]
        reason=None
        if row.boundary_balls!=0 or row.boundary_strikes!=0:reason='nonzero_boundary_count'
        elif len(current)!=1:reason='missing_current_option'
        elif current.iloc[0].pitcher_own_all_n<30 or current.iloc[0].pitcher_hand not in ('L','R'):reason='current_ability_support'
        elif not current.iloc[0].lookback_14d_complete:reason='current_left_truncated_history'
        elif len(pool)<2:reason='fewer_than_two_nominal_RP'
        elif not np.isfinite(row.research_home_we) or not np.isfinite(row.research_re):reason='missing_value_reference'
        if reason:excluded.append({'decision_id':row.decision_id,'reason':reason});continue
        accepted.append(row.decision_id);option_rows.append(pd.concat([current,pool.sort_values('option_pitcher_id')]))
    selected=cases[cases.decision_id.isin(accepted)].sort_values('decision_id').reset_index(drop=True)
    return selected,pd.concat(option_rows,ignore_index=True) if option_rows else options.iloc[:0],excluded


def draw_transition(frame: pd.DataFrame,p: np.ndarray,tables: dict,u: np.ndarray) -> tuple[np.ndarray,np.ndarray]:
    result=np.zeros((len(frame),4),dtype=int);unsupported=np.zeros(len(frame))
    for group,table in b.transition_groups(frame,tables):
        idx=group.index.to_numpy();conditional=table['conditional'];supported=conditional.sum(axis=1)>0
        probability=p[idx].copy();unsupported[idx]=probability[:,~supported].sum(axis=1)
        probability[:,~supported]=0;probability/=probability.sum(axis=1,keepdims=True)
        joint=probability@conditional;cdf=np.cumsum(joint,axis=1);cdf[:,-1]=1
        take=(cdf<u[idx,None]).sum(axis=1)
        result[idx]=np.asarray(table['events'])[take]
    return result,unsupported


def half_values(initial: pd.DataFrame,total_runs: np.ndarray,end_outs: np.ndarray,end_bases: np.ndarray,bundle: dict) -> tuple[np.ndarray,np.ndarray]:
    state=initial.copy();state['bottom']=state.half.eq('bottom').astype(int)
    state['score_diff']=np.where(state.bottom.eq(0),state.defense_lead,-state.defense_lead)
    state['balls']=state['strikes']=0
    post,terminal=b.post_state(state,total_runs,end_outs,end_bases)
    future=b.we_predict(bundle,post);known=np.isfinite(terminal);future[known]=terminal[known]
    wpa=np.where(state.bottom.eq(0),1,-1)*(future-state.research_home_we.to_numpy())
    return wpa,state.research_re.to_numpy()-total_runs


def simulate_arm(initial: pd.DataFrame,case_indices: np.ndarray,draws: np.ndarray,fit: dict,reference: dict,tables: dict,we: dict) -> dict:
    frame=initial.copy().reset_index(drop=True);n=len(frame)
    total_runs=np.zeros(n,dtype=int);active=np.ones(n,dtype=bool);extrapolated=np.zeros(n,dtype=bool)
    unsupported=np.zeros(n);steps=np.zeros(n,dtype=int)
    initial_lead=frame.defense_lead.to_numpy().copy()
    path_index=np.tile(np.arange(PATHS),n//PATHS)
    for step in range(MAX_PA):
        idx=np.flatnonzero(active)
        if not len(idx):break
        work=frame.iloc[idx].copy().reset_index(drop=True)
        uniforms=draws[step,case_indices[idx],path_index[idx]]
        if step:
            bank_idx=np.searchsorted(reference['cdf'],uniforms[:,3],side='right').clip(max=len(reference['cdf'])-1)
            for hand,indices in work.groupby('pitcher_hand').groups.items():
                positions=np.asarray(indices);profiles=reference['profiles'][hand].iloc[bank_idx[positions]]
                for key in BATTER_COLUMNS:work.loc[positions,key]=profiles[key].to_numpy()
            work['is_current']=True
        max_pitch=work.option_role.map(reference['max_training_pitches']).to_numpy()
        extrapolated[idx]|=work.option_game_pitches.to_numpy()>max_pitch
        p=b.probabilities(fit['model'],b.design(work,'matchup',fit['pooling'],fit['prior']))
        events,mass=draw_transition(work,p,tables,uniforms[:,0]);unsupported[idx]+=mass;steps[idx]+=1
        target,runs,end_outs,end_bases=events.T
        increment=np.zeros(len(work),dtype=int)
        for role in ('SP','RP'):
            for kind in range(9):
                mask=work.option_role.eq(role).to_numpy()&(target==kind)
                values=reference['pitch_counts'][(role,kind)]
                take=np.minimum((uniforms[mask,2]*len(values)).astype(int),len(values)-1)
                increment[mask]=values[take]
        total_runs[idx]+=runs
        work['defense_lead']=initial_lead[idx]-total_runs[idx]
        work['outs']=end_outs;work['base_state']=end_bases
        work['option_current_bf']=work.option_current_bf+1
        for key in ['option_game_pitches','pitches_1d_before','pitches_3d_before','pitches_7d_before','pitches_14d_before']:
            work[key]=work[key]+increment
        mutable=['defense_lead','outs','base_state','option_current_bf','option_game_pitches',
            'pitches_1d_before','pitches_3d_before','pitches_7d_before','pitches_14d_before','is_current']
        if step:mutable+=BATTER_COLUMNS
        for key in mutable:frame.loc[idx,key]=work[key].to_numpy()
        walkoff=work.half.eq('bottom').to_numpy() & work.inning.ge(work.scheduled_innings).to_numpy() & work.defense_lead.lt(0).to_numpy()
        active[idx[(end_outs>=3)|walkoff]]=False
    wpa,re24=half_values(initial,total_runs,frame.outs.to_numpy(dtype=int),frame.base_state.to_numpy(dtype=int),we)
    return {'wpa':wpa.reshape(-1,PATHS),'re24':re24.reshape(-1,PATHS),'censored':active.reshape(-1,PATHS),
        'extrapolated':extrapolated.reshape(-1,PATHS),'unsupported':(unsupported/np.maximum(steps,1)).reshape(-1,PATHS)}


def simulate() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    cases=pd.read_parquet(OUT/'cases.parquet');options=pd.read_parquet(OUT/'options.parquet')
    cases,options,excluded=supported_options(cases,options)
    if not len(cases):raise ValueError('No supported role-pool cases')
    cases.to_parquet(OUT/'supported_cases.parquet',index=False,compression='zstd')
    reference=joblib.load(OUT/'simulation_reference.joblib');tables=joblib.load(b.OUT/'transitions.joblib')
    we=joblib.load(b.TEMPORAL/'models/frozen_2024/context.joblib')
    rng=np.random.default_rng(SEED)
    draws=rng.random((MAX_PA,len(cases),PATHS,4));choice=rng.random((len(cases),PATHS))
    current_index=[];pool_index=[]
    for i,row in enumerate(cases.itertuples()):
        group=options[options.decision_id.eq(row.decision_id)]
        current_index.append(np.full(PATHS,group[group.is_current].index[0]))
        pool=group[~group.is_current].index.to_numpy()
        pool_index.append(pool[np.minimum((choice[i]*len(pool)).astype(int),len(pool)-1)])
    current_index=np.concatenate(current_index);pool_index=np.concatenate(pool_index)
    summaries=[];bootstrap_values=[]
    with threadpool_limits(limits=2):
        for model_index in range(BOOTSTRAPS+1):
            fit=joblib.load(b.OUT/'matchup.joblib' if model_index==0 else OUT/f'bootstrap_{model_index-1}.joblib')
            collected=[]
            print(f'Fixed-half scenarios model {model_index}/{BOOTSTRAPS}, {len(cases)} decisions x {PATHS} paired paths',flush=True)
            for start in range(0,len(cases),48):
                end=min(start+48,len(cases));slice_=slice(start*PATHS,end*PATHS)
                ids=np.repeat(np.arange(start,end),PATHS)
                arms=[simulate_arm(options.iloc[indices[slice_]].reset_index(drop=True),ids,draws,fit,reference,tables,we) for indices in (current_index,pool_index)]
                row={}
                for metric in ('wpa','re24'):
                    delta=arms[1][metric]-arms[0][metric]
                    row[metric+'_continue']=arms[0][metric].mean(axis=1)
                    row[metric+'_pool']=arms[1][metric].mean(axis=1)
                    row[metric+'_delta']=delta.mean(axis=1)
                    row[metric+'_mc_se']=delta.std(axis=1,ddof=1)/np.sqrt(PATHS)
                row['censored_paths']=(arms[0]['censored']|arms[1]['censored']).sum(axis=1)
                row['extrapolated_fraction']=(arms[0]['extrapolated']|arms[1]['extrapolated']).mean(axis=1)
                row['unsupported_mass']=np.maximum(arms[0]['unsupported'],arms[1]['unsupported']).mean(axis=1)
                collected.append(pd.DataFrame(row))
            values=pd.concat(collected,ignore_index=True)
            values.insert(0,'decision_id',cases.decision_id)
            values.to_parquet(OUT/f'scenario_model_{model_index}.parquet',index=False,compression='zstd')
            bootstrap_values.append(values)
            if model_index==0:summaries=values.copy()
    for metric in ('wpa','re24'):
        samples=np.stack([v[f'{metric}_delta'].to_numpy() for v in bootstrap_values[1:]])
        summaries[f'{metric}_bootstrap80_low'],summaries[f'{metric}_bootstrap80_high']=np.quantile(samples,[.1,.9],axis=0)
        summaries[f'{metric}_mc95_low']=summaries[f'{metric}_delta']-1.96*summaries[f'{metric}_mc_se']
        summaries[f'{metric}_mc95_high']=summaries[f'{metric}_delta']+1.96*summaries[f'{metric}_mc_se']
    summaries['simulation_supported']=(np.stack([v.censored_paths.to_numpy() for v in bootstrap_values]).max(axis=0)==0)&(np.stack([v.extrapolated_fraction.to_numpy() for v in bootstrap_values]).max(axis=0)==0)
    summaries['research_direction']=np.where(summaries.simulation_supported & summaries.wpa_bootstrap80_low.gt(0)&summaries.wpa_mc95_low.gt(0),'pool_higher',
        np.where(summaries.simulation_supported & summaries.wpa_bootstrap80_high.lt(0)&summaries.wpa_mc95_high.lt(0),'continue_higher','uncertain_or_unsupported'))
    summaries['recommendation_allowed']=False
    summaries.to_parquet(OUT/'action_values_2024.parquet',index=False,compression='zstd')
    b.save_json(OUT/'summary.json',{'version':'decision_action_values_v1','protocol_sha256':b.digest(OUT/'protocol.json'),
        'attempted_cases':len(pd.read_parquet(OUT/'cases.parquet')),'modeled_cases':len(cases),'excluded':excluded,
        'simulation_supported':int(summaries.simulation_supported.sum()),'direction_counts':summaries.research_direction.value_counts().to_dict(),
        'paths':PATHS,'bootstrap_models':BOOTSTRAPS,'maximum_completed_pa':MAX_PA,
        'recommendation_allowed':False,'individual_ranking_allowed':False,'test_outcome_metrics_examined':False,
        'policy':'same pitcher until current half end; generic paired 2023-end league future batters; neutral subsequent-game policy',
        'uncertainty':'MC95 and descriptive central80 bootstrap classifier band; fixed transition/WE/RE and no hidden-confounding correction',
        'scope':'2024 stratified research cases, not league aggregate effects; no operational recommendation or long-term resource cost'})
    print('Fixed-half research values saved',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','bootstrap','simulate'])
    stage=parser.parse_args().stage;OUT.mkdir(parents=True,exist_ok=True);globals()[stage]()
