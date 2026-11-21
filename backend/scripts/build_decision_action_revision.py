"""Slice14.1 fixed-half revision, preserving all484 original comparisons.

First PA may use validated diagnostic signal bundles. Later PA states explicitly
revert to repaired baseline; unobserved signal trajectories are never frozen.
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
from scripts import build_decision_role_ablation as u
from scripts import build_decision_action_values as a

b,r,m=u.b,u.r,u.m
OUT=b.ROOT/'data/research/decision_action_values_v2'
PATHS,BOOTSTRAPS,MAX_PA=a.PATHS,a.BOOTSTRAPS,a.MAX_PA


def save(name,value):b.save_json(OUT/name,value)


def prepare():
    cases=pd.read_parquet(a.OUT/'supported_cases.parquet')
    assert len(cases)==484 and cases.decision_id.is_unique
    original=pd.read_parquet(a.OUT/'options.parquet');options=original[original.decision_id.isin(cases.decision_id)].copy()
    options['request_id']=options.decision_id+':'+options.option_pitcher_id.astype(str)
    print(f'14.1 prepare all{len(cases)} original cases and{len(options):,} nominal options',flush=True)
    options=u.enrich_options(options,2024)
    report=json.loads((u.OUT/'validation.json').read_text('utf-8'))
    options['first_feature_extrapolated']=False
    for role in ['SP','RP']:
        variant=report['roles'][role]['selected']
        if variant=='baseline':continue
        fit=joblib.load(u.OUT/f'{role}_{variant}.joblib');mask=options.forecast_role.eq(role)
        for name,(low,high) in fit['support_ranges'].items():
            options.loc[mask&options[name].notna()&~options[name].between(low,high),'first_feature_extrapolated']=True
    new_cases,options,excluded=a.supported_options(cases,options)
    assert set(new_cases.decision_id)==set(cases.decision_id),'Changed support must be reported, never silently replace the original denominator'
    cases=new_cases
    cases.to_parquet(OUT/'cases.parquet',index=False,compression='zstd')
    options.to_parquet(OUT/'options.parquet',index=False,compression='zstd')
    rows=[];audit=[]
    for case in cases.itertuples():
        group=options[options.decision_id.eq(case.decision_id)];pool=group[~group.is_current]
        pools={'role':pool.index.to_numpy()}
        for hand,part in pool.groupby('pitcher_hand'):
            if len(part)>=2:pools['hand_'+hand]=part.index.to_numpy()
        for kind,part in pool[pool.arsenal_type.ne('unknown')&pool.type_n.ge(20)].groupby('arsenal_type'):
            if len(part)>=2:pools['type_'+kind]=part.index.to_numpy()
        for name,indices in pools.items():
            for i in indices:rows.append({'decision_id':case.decision_id,'pool':name,'option_index':int(i)})
        audit.append({'decision_id':case.decision_id,'nominal_RP':len(pool),'conditional_pools':len(pools)-1,
            'future_lineup':'frozen_2023_end_league_fallback','lineup_reason':'no independently timestamped predecision published-lineup snapshot; final archived battingOrder cannot certify availability',
            'official_game_listed':True,'official_active_roster_at_decision':None,'nominal_legal_boundary':True,
            'warmup_available':None,'medical_available':None,'manual_availability_confirmed':None,
            'long_term_bullpen_budget':None,'long_term_cost_added_to_value':False})
    pd.DataFrame(rows).to_parquet(OUT/'pool_members.parquet',index=False,compression='zstd')
    pd.DataFrame(audit).to_parquet(OUT/'availability_lineup_audit.parquet',index=False,compression='zstd')
    save('preparation.json',{'original_cases':484,'modeled_cases':len(cases),'options':len(options),'excluded':excluded,
        'conditional_pool_comparisons':sum(x['conditional_pools'] for x in audit),'future_lineup_verified':0,
        'future_lineup_fallback':len(cases),'individual_availability':'game-listed/nominal legality known; active/warmup/medical/manual confirmation unknown',
        'type_pool':'same past hand:dominant family:velocity type, each candidate >=20 own batter-vs-type PA and >=50 repertoire pitches; >=2 candidates',
        'resource_scope':'expected added pitches/BF and nominal RP counts, no arbitrary run/WPA fatigue penalty or unobserved long-term budget'})
    print('14.1 prepared repaired role / supported hand / supported type pools; all future lineups explicitly fall back',flush=True)


def protocol():
    report=json.loads((u.OUT/'validation.json').read_text('utf-8'))
    paths=[Path(__file__),Path(u.__file__),Path(a.__file__),Path(b.__file__),u.OUT/'protocol.json',u.OUT/'validation.json',
        r.OUT/'baseline_matchup.joblib',a.OUT/'protocol.json',a.OUT/'action_values_2024.parquet',
        a.OUT/'simulation_reference.joblib',b.OUT/'transitions.joblib',b.TEMPORAL/'models/frozen_2024/context.joblib',
        *[OUT/name for name in ['cases.parquet','options.parquet','pool_members.parquet','availability_lineup_audit.parquet','preparation.json']]]
    paths += [u.OUT/f"{role}_{v['selected']}.joblib" for role,v in report['roles'].items()]
    return {'version':'decision_action_values_v2','input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'year':2024,'seed':a.SEED,'paths':PATHS,'bootstrap_models':BOOTSTRAPS,'max_completed_PA':MAX_PA,
        'original_case_set':'same484 original modeled decisions; every missing/unsupported case accounted, no new outcome-based sample',
        'first_PA':{role:v['selected'] if v['selected']!='baseline' else 'repaired_global_matchup' for role,v in report['roles'].items()},
        'future_PA':'repaired global matchup baseline for all arms after first PA; hypothetical Plus/state/attack/risk evolution not available; no frozen live state propagated',
        'lineup':'first batter known; later use original paired2023-end league draws. Archived final battingOrder is not evidence of predecision publication; all484 fallback explicit.',
        'arms':'current until half end vs uniformly selected role/hand/type supported nominal RP until half end; no later substitutions',
        'legality':'nominal legal original boundary; stays until half end, three-batter/inning-end exception; no inferred injury/warmup/active-roster certainty',
        'support':'original role-pool support, plus training count upper bounds and selected first-PA feature ranges; no censored or count-extrapolated paths for preference',
        'uncertainty':'paired MC95 plus central80 across8 common-game classifier refits; preprocessing/transition/WE/RE fixed, not complete or causal intervals',
        'bootstrap_runtime':'joblib threading4 for independent one-vs-rest class fits, BLAS2; fixed seeds and unchanged learner settings',
        'resources':'training role x outcome pitch-count increments, rolling counts updated at fixed decision-clock approximation (no duration model), expected added pitches/BF; long-term costs/budgets unknown and unpriced',
        'comparison':'paired old/new direction crosstab and value/interval differences on same484, hand/type pools separately; not alert deduplication or event matching',
        'test_outcome_metrics_examined':False,'recommendation_allowed':False,'individual_ranking_allowed':False}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen14.1 experiment differs; preserve and revision required')
    save('protocol.json',value);print('14.1 comparison protocol frozen',flush=True)


def bootstrap():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    frame=pd.concat([u.load(y,True) for y in [2021,2022,2023]],ignore_index=True)
    report=json.loads((u.OUT/'validation.json').read_text('utf-8'))
    codes,games=pd.factorize(frame.game_pk,sort=True);rng=np.random.default_rng(a.SEED);reports=[]
    global_fit=joblib.load(r.OUT/'baseline_matchup.joblib')
    transforms={'baseline':global_fit['model'][0].transform(b.design(frame,'matchup',20,global_fit['prior']))}
    fits={'baseline':global_fit}
    for role in ['SP','RP']:
        selected=report['roles'][role]['selected']
        if selected=='baseline':continue
        fit=joblib.load(u.OUT/f'{role}_{selected}.joblib');fits[role]=fit
        subset=frame[frame.forecast_role.eq(role)]
        transforms[role]=fit['model'][0].transform(u.design(subset,selected,fit['prior']))
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for i in range(BOOTSTRAPS):
            count=np.bincount(rng.integers(0,len(games),len(games)),minlength=len(games));counts=count[codes]
            for role,fit in fits.items():
                mask=np.ones(len(frame),dtype=bool) if role=='baseline' else frame.forecast_role.eq(role).to_numpy()
                sub=frame.loc[mask];weights=1/sub.groupby('game_pk').decision_id.transform('count').to_numpy()
                weights*=counts[mask];weights/=weights.mean()
                learner=clone(fit['model'][-1]).set_params(random_state=a.SEED+i+1)
                print(f'14.1 bootstrap{i+1}/{BOOTSTRAPS} {role}',flush=True)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always',ConvergenceWarning)
                    learner.fit(transforms[role],sub.target,sample_weight=weights)
                joblib.dump({**fit,'model':make_pipeline(fit['model'][0],learner)},OUT/f'bootstrap_{i}_{role}.joblib')
                reports.append({'replicate':i,'role':role,'convergence_warning':any(isinstance(w.message,ConvergenceWarning) for w in caught)})
    save('bootstrap.json',{'replicates':reports,'scope':'common game resampling; fixed transforms and transition/WE/RE'})


def first_probability(frame,baseline,role_fits):
    result=b.probabilities(baseline['model'],b.design(frame,'matchup',20,baseline['prior']))
    for role,fit in role_fits.items():
        mask=frame.forecast_role.eq(role).to_numpy()
        if mask.any():result[mask]=b.probabilities(fit['model'],u.design(frame.loc[mask],fit['variant'],fit['prior']))
    return result


def simulate_arm(initial,case_indices,draws,baseline,role_fits,reference,tables,we):
    frame=initial.copy().reset_index(drop=True);n=len(frame);active=np.ones(n,dtype=bool)
    total_runs=np.zeros(n,dtype=int);added_pitches=np.zeros(n,dtype=int);steps=np.zeros(n,dtype=int)
    extrapolated=frame.first_feature_extrapolated.to_numpy(dtype=bool).copy();unsupported=np.zeros(n);initial_lead=frame.defense_lead.to_numpy().copy()
    path_index=np.tile(np.arange(PATHS),n//PATHS)
    for step in range(MAX_PA):
        idx=np.flatnonzero(active)
        if not len(idx):break
        work=frame.iloc[idx].copy().reset_index(drop=True);uniforms=draws[step,case_indices[idx],path_index[idx]]
        if step:
            bank_index=np.searchsorted(reference['cdf'],uniforms[:,3],side='right').clip(max=len(reference['cdf'])-1)
            for hand,indices in work.groupby('pitcher_hand').groups.items():
                positions=np.asarray(indices);profiles=reference['profiles'][hand].iloc[bank_index[positions]]
                for key in a.BATTER_COLUMNS:work.loc[positions,key]=profiles[key].to_numpy()
            work['is_current']=True
        extrapolated[idx]|=work.option_game_pitches.to_numpy()>work.option_role.map(reference['max_training_pitches']).to_numpy()
        p=first_probability(work,baseline,role_fits) if step==0 else b.probabilities(baseline['model'],b.design(work,'matchup',20,baseline['prior']))
        events,mass=a.draw_transition(work,p,tables,uniforms[:,0]);unsupported[idx]+=mass;steps[idx]+=1
        target,runs,end_outs,end_bases=events.T;increment=np.zeros(len(work),dtype=int)
        for role in ['SP','RP']:
            for kind in range(9):
                mask=work.option_role.eq(role).to_numpy()&(target==kind);values=reference['pitch_counts'][(role,kind)]
                increment[mask]=values[np.minimum((uniforms[mask,2]*len(values)).astype(int),len(values)-1)]
        total_runs[idx]+=runs;added_pitches[idx]+=increment
        work['defense_lead']=initial_lead[idx]-total_runs[idx];work['outs']=end_outs;work['base_state']=end_bases
        work['option_current_bf']=work.option_current_bf+1
        loads=['option_game_pitches','pitches_1d_before','pitches_3d_before','pitches_5d_before','pitches_7d_before','pitches_14d_before']
        for key in loads:work[key]=work[key]+increment
        for key in ['defense_lead','outs','base_state','option_current_bf','is_current']+loads+(a.BATTER_COLUMNS if step else []):
            frame.loc[idx,key]=work[key].to_numpy()
        walkoff=work.half.eq('bottom').to_numpy()&work.inning.ge(work.scheduled_innings).to_numpy()&work.defense_lead.lt(0).to_numpy()
        active[idx[(end_outs>=3)|walkoff]]=False
    wpa,re24=a.half_values(initial,total_runs,frame.outs.to_numpy(dtype=int),frame.base_state.to_numpy(dtype=int),we)
    return {key:value.reshape(-1,PATHS) for key,value in {'wpa':wpa,'re24':re24,'pitches':added_pitches,'bf':steps,
        'censored':active,'extrapolated':extrapolated,'unsupported':unsupported/np.maximum(steps,1)}.items()}


def simulate():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    cases=pd.read_parquet(OUT/'cases.parquet');options=pd.read_parquet(OUT/'options.parquet');members=pd.read_parquet(OUT/'pool_members.parquet')
    reference=joblib.load(a.OUT/'simulation_reference.joblib');tables=joblib.load(b.OUT/'transitions.joblib')
    we=joblib.load(b.TEMPORAL/'models/frozen_2024/context.joblib');selection=json.loads((u.OUT/'validation.json').read_text('utf-8'))
    rng=np.random.default_rng(a.SEED);draws=rng.random((MAX_PA,len(cases),PATHS,4));choices=rng.random((len(cases),PATHS))
    current_indices=np.array([options[options.decision_id.eq(d)&options.is_current].index[0] for d in cases.decision_id])
    pool_lookup={(d,p):g.option_index.to_numpy() for (d,p),g in members.groupby(['decision_id','pool'])}
    all_models=[]
    with threadpool_limits(limits=2):
        for model_index in range(BOOTSTRAPS+1):
            baseline=joblib.load(r.OUT/'baseline_matchup.joblib' if model_index==0 else OUT/f'bootstrap_{model_index-1}_baseline.joblib')
            role_fits={}
            for role in ['SP','RP']:
                variant=selection['roles'][role]['selected']
                if variant!='baseline':role_fits[role]=joblib.load(u.OUT/f'{role}_{variant}.joblib' if model_index==0 else OUT/f'bootstrap_{model_index-1}_{role}.joblib')
            current={}
            for start in range(0,len(cases),48):
                end=min(start+48,len(cases));ids=np.repeat(np.arange(start,end),PATHS)
                print(f'14.1 model{model_index}/{BOOTSTRAPS} current cases{start+1}-{end}',flush=True)
                values=simulate_arm(options.loc[np.repeat(current_indices[start:end],PATHS)].reset_index(drop=True),ids,draws,baseline,role_fits,reference,tables,we)
                for local,i in enumerate(range(start,end)):current[i]={key:value[local] for key,value in values.items()}
            model_rows=[]
            pool_names=sorted(members.pool.unique(),key=lambda x:(x!='role',x))
            for pool_name in pool_names:
                case_ids=[i for i,d in enumerate(cases.decision_id) if (d,pool_name) in pool_lookup]
                for start in range(0,len(case_ids),48):
                    group=case_ids[start:start+48];indices=[]
                    for i in group:
                        pool=pool_lookup[(cases.decision_id.iloc[i],pool_name)]
                        indices.extend(pool[np.minimum((choices[i]*len(pool)).astype(int),len(pool)-1)])
                    print(f'14.1 model{model_index}/{BOOTSTRAPS} {pool_name} cases{start+1}-{min(start+48,len(case_ids))}/{len(case_ids)}',flush=True)
                    values=simulate_arm(options.loc[indices].reset_index(drop=True),np.repeat(group,PATHS),draws,baseline,role_fits,reference,tables,we)
                    for local,i in enumerate(group):
                        base=current[i];row={'decision_id':cases.decision_id.iloc[i],'pool':pool_name,
                            'pool_n':len(pool_lookup[(cases.decision_id.iloc[i],pool_name)])}
                        for metric in ['wpa','re24']:
                            delta=values[metric][local]-base[metric]
                            row[metric+'_continue']=float(base[metric].mean());row[metric+'_pool']=float(values[metric][local].mean())
                            row[metric+'_delta']=float(delta.mean());row[metric+'_mc_se']=float(delta.std(ddof=1)/np.sqrt(PATHS))
                        for metric in ['pitches','bf']:
                            row[metric+'_continue']=float(base[metric].mean());row[metric+'_pool']=float(values[metric][local].mean())
                        row['censored_paths']=int((base['censored']|values['censored'][local]).sum())
                        row['extrapolated_fraction']=float((base['extrapolated']|values['extrapolated'][local]).mean())
                        row['unsupported_mass']=float(np.maximum(base['unsupported'],values['unsupported'][local]).mean())
                        row['nominal_RP_remaining_after_replacement']=int((options.decision_id.eq(row['decision_id'])&~options.is_current).sum()-1)
                        model_rows.append(row)
            frame=pd.DataFrame(model_rows).sort_values(['decision_id','pool']).reset_index(drop=True)
            frame.to_parquet(OUT/f'scenario_model_{model_index}.parquet',index=False,compression='zstd');all_models.append(frame)
    summaries=all_models[0].copy()
    for metric in ['wpa','re24']:
        samples=np.stack([v[metric+'_delta'].to_numpy() for v in all_models[1:]])
        summaries[metric+'_bootstrap80_low'],summaries[metric+'_bootstrap80_high']=np.quantile(samples,[.1,.9],axis=0)
        summaries[metric+'_mc95_low']=summaries[metric+'_delta']-1.96*summaries[metric+'_mc_se']
        summaries[metric+'_mc95_high']=summaries[metric+'_delta']+1.96*summaries[metric+'_mc_se']
    summaries['simulation_supported']=(np.stack([v.censored_paths.to_numpy() for v in all_models]).max(axis=0)==0)&(np.stack([v.extrapolated_fraction.to_numpy() for v in all_models]).max(axis=0)==0)
    convergence=any(x['convergence_warning'] for x in json.loads((OUT/'bootstrap.json').read_text('utf-8'))['replicates'])
    if convergence:summaries['simulation_supported']=False
    summaries['research_direction']=np.where(summaries.simulation_supported&summaries.wpa_bootstrap80_low.gt(0)&summaries.wpa_mc95_low.gt(0),'pool_higher',
        np.where(summaries.simulation_supported&summaries.wpa_bootstrap80_high.lt(0)&summaries.wpa_mc95_high.lt(0),'continue_higher','uncertain_or_unsupported'))
    summaries['recommendation_allowed']=False;summaries['individual_ranking_allowed']=False
    summaries.to_parquet(OUT/'action_values_2024.parquet',index=False,compression='zstd')
    old=pd.read_parquet(a.OUT/'action_values_2024.parquet')
    role=summaries[summaries.pool.eq('role')].merge(old,on='decision_id',validate='one_to_one',suffixes=('_new','_old'))
    assert len(role)==484
    role.to_parquet(OUT/'old_new_comparison.parquet',index=False,compression='zstd')
    cross=pd.crosstab(role.research_direction_old,role.research_direction_new)
    delta_summary={}
    for metric in ['wpa','re24']:
        diff=role[metric+'_delta_new']-role[metric+'_delta_old']
        delta_summary[metric]={'mean_change':float(diff.mean()),'median_change':float(diff.median()),'p10_p90':diff.quantile([.1,.9]).tolist(),
            'mean_old':float(role[metric+'_delta_old'].mean()),'mean_new':float(role[metric+'_delta_new'].mean())}
    example_columns=['decision_id','wpa_delta_old','wpa_delta_new','wpa_mc95_low_new','wpa_mc95_high_new',
        'wpa_bootstrap80_low_new','wpa_bootstrap80_high_new','re24_delta_old','re24_delta_new',
        'pitches_continue','pitches_pool','simulation_supported_new','research_direction_new','pool_n','unsupported_mass_new']
    examples=role[example_columns].merge(cases[['decision_id','game_pk','inning','half','outs','base_state']],on='decision_id',validate='one_to_one')
    examples=json.loads(examples.sort_values('decision_id').head(12).to_json(orient='records'))
    save('summary.json',{'version':'decision_action_values_v2','protocol_sha256':b.digest(OUT/'protocol.json'),
        'original_cases':484,'modeled_role_cases':len(role),'role_supported':int(role.simulation_supported_new.sum()),
        'role_direction_counts':role.research_direction_new.value_counts().to_dict(),
        'old_direction_counts':role.research_direction_old.value_counts().to_dict(),
        'old_new_direction_crosstab':cross.to_dict(orient='index'),'role_value_delta_changes':delta_summary,
        'role_unsupported_mass':{'mean':float(role.unsupported_mass_new.mean()),'maximum':float(role.unsupported_mass_new.max())},
        'examples':examples,'example_selection':'first12 decision IDs, including unsupported; no value/outcome-based selection',
        'conditional_pool_comparisons':int((summaries.pool!='role').sum()),
        'pool_summary':[{'pool':name,'n':len(g),'supported':int(g.simulation_supported.sum()),'directions':g.research_direction.value_counts().to_dict()} for name,g in summaries.groupby('pool')],
        'first_PA_models':json.loads((OUT/'protocol.json').read_text('utf-8'))['first_PA'],
        'future_PA_model':'repaired_global_matchup; no hypothetical signal evolution','future_lineup':'all484 explicitly paired historical league fallback',
        'paths':PATHS,'bootstrap_models':BOOTSTRAPS,'bootstrap_convergence_warning':convergence,
        'resources':'expected added pitches/BF per arm; remaining nominal RP count; medical/warmup/budget unknown, no long-term cost priced',
        'scope':'stratified fixed484 research comparisons, conditional pools exploratory and not best-pool selection; no event matching/deduplication (14.2)',
        'recommendation_allowed':False,'individual_ranking_allowed':False,'test_outcome_metrics_examined':False})
    print('14.1 old/new role and conditional-pool results saved',flush=True)


def finalize():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    report=json.loads((OUT/'summary.json').read_text('utf-8'))
    report['preparation']=json.loads((OUT/'preparation.json').read_text('utf-8'))
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice14_1_v2.json',report)
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json']
    save('manifest.json',{'version':'decision_action_values_v2','files':[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':b.digest(p)} for p in sorted(files)]})
    print('14.1 evidence published',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','bootstrap','simulate','finalize'])
    stage=parser.parse_args().stage;OUT.mkdir(parents=True,exist_ok=True);globals()[stage]()
