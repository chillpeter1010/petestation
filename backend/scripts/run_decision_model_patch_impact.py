"""14.1.1 fixed484 sensitivity: first PA only; all old artifacts read-only.

Reuse the frozen simulation through process-local adapters, restored in finally.
Cache first-option probabilities before path expansion; future PA remains the old
global matchup. Old common-game baseline refits, paths and pools stay identical.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
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
from scripts import build_decision_model_patch as p
from scripts import build_decision_action_revision as a

b,r=p.b,p.r
OLD=a.OUT
OUT=b.ROOT/'data/research/decision_action_sensitivity_v3'


def read(path):return json.loads(path.read_text('utf-8'))


def selected():return {role:read(p.OUT/f'confirmation_{role}.json')['selected'] for role in ['SP','RP']}


def winners():return {role:name for role,name in selected().items() if name!='frozen_v2_baseline'}


def protocol():
    paths=[Path(__file__),Path(a.__file__),OLD/'protocol.json',OLD/'manifest.json',p.OUT/'protocol.json',
        p.OUT/'confirmation_SP.json',p.OUT/'confirmation_RP.json',r.OUT/'baseline_matchup.joblib',
        a.a.OUT/'simulation_reference.joblib',b.OUT/'transitions.joblib',b.TEMPORAL/'models/frozen_2024/context.joblib']
    paths += [OLD/name for name in ['cases.parquet','options.parquet','pool_members.parquet','availability_lineup_audit.parquet','action_values_2024.parquet']]
    paths += [OLD/f'bootstrap_{i}_baseline.joblib' for i in range(a.BOOTSTRAPS)]
    paths += [p.OUT/f'final_{role}_{name}.joblib' for role,name in winners().items()]
    paths += [p.u.OUT/f'features_{y}.parquet' for y in [2021,2022,2023]]
    return {'version':'decision_action_sensitivity_v3','input_sha256':{str(path.relative_to(b.ROOT)):b.digest(path) for path in paths},
        'first_PA_models':selected(),'first_PA':selected(),'future_PA_model':'original repaired global matchup; no simulated state trajectory',
        'cases':484,'paths':a.PATHS,'bootstrap_models':a.BOOTSTRAPS,'max_PA':a.MAX_PA,'seed':a.a.SEED,
        'bootstrap':'same2021-23 sorted global-game multinomial counts as14.1; reuse old global refits; new role learner refits with central fixed preprocessing and prior, same temporal fit/cal separation, temperature recalibrated on count-weighted calibration rows when selected',
        'sensitivity':'first-option probabilities cached before exact repeated-row path expansion; central cache checked against direct uncached inference; first-feature range flags join original count/truncation support',
        'unchanged':'all484 cases,3880 supported options,1556 pools,256 common random paths, subsequent league batter draw, transition/WE/RE/resource semantics and availability limits',
        'stop':'14.1.1 only; no14.2; research direction is not an operational recommendation',
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'individual_ranking_allowed':False}


def prepare():
    assert read(p.OUT/'protocol.json')==p.protocol() and read(OLD/'protocol.json')==a.protocol()
    OUT.mkdir(parents=True,exist_ok=True)
    options=pd.read_parquet(OLD/'options.parquet')
    for target,source in p.LIVE_MAP.items():options[target]=(pd.to_numeric(options[source],errors='coerce')-100).where(options.is_current)
    for role,name in winners().items():
        fit=joblib.load(p.OUT/f'final_{role}_{name}.joblib');mask=options.forecast_role.eq(role)
        for field,(low,high) in fit['support_ranges'].items():
            options.loc[mask&options[field].notna()&~options[field].between(low,high),'first_feature_extrapolated']=True
    options['_patch_row']=np.arange(len(options))
    options.to_parquet(OUT/'full_options.parquet',index=False,compression='zstd')
    needed=set(b.LEVELS['matchup'][0]+b.LEVELS['matchup'][1])-{'pitcher_log_n','batter_log_n'}
    needed.update(['decision_id','option_pitcher_id','forecast_role','research_home_we','research_re','first_feature_extrapolated',
        'pitcher_own_split_n','pitcher_own_all_n','batter_own_split_n','batter_own_all_n','pitches_5d_before','_patch_row'])
    options[sorted(needed)].to_parquet(OUT/'options.parquet',index=False,compression='zstd')
    for name in ['cases.parquet','pool_members.parquet','availability_lineup_audit.parquet']:
        shutil.copyfile(OLD/name,OUT/name)
    for i in range(a.BOOTSTRAPS):shutil.copyfile(OLD/f'bootstrap_{i}_baseline.joblib',OUT/f'bootstrap_{i}_baseline.joblib')
    value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value,'Preserve explicit revision on protocol change'
    b.save_json(path,value)
    print(f'14.1.1 frozen: first-PA winners{winners()}, all original paths/pools retained',flush=True)


def bootstrap():
    assert read(OUT/'protocol.json')==protocol()
    frame=pd.concat([p.load(y) for y in [2021,2022,2023]],ignore_index=True)
    _,games=pd.factorize(frame.game_pk,sort=True);rng=np.random.default_rng(a.a.SEED)
    draws=[np.bincount(rng.integers(0,len(games),len(games)),minlength=len(games)) for _ in range(a.BOOTSTRAPS)]
    reports=[{**x,'source':'retained14.1 global baseline'} for x in read(OLD/'bootstrap.json')['replicates']]
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for role,name in winners().items():
            central=joblib.load(p.OUT/f'final_{role}_{name}.joblib')
            sub=frame[frame.forecast_role.eq(role)].copy();fit,cal,_=p.temporal_partition(sub)
            x=central['model'][0].transform(p.design(fit,central['config'],central['prior']))
            fi=games.get_indexer(fit.game_pk);ci=games.get_indexer(cal.game_pk);assert (fi>=0).all() and (ci>=0).all()
            for i,count in enumerate(draws):
                path=OUT/f'bootstrap_{i}_{role}.joblib'
                print(f'14.1.1 common-game refit{i+1}/{a.BOOTSTRAPS} {role}',flush=True)
                learner=clone(central['model'][-1]).set_params(random_state=a.a.SEED+i+1)
                fw=p.weights(fit)*count[fi];fw/=fw.mean()
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always',ConvergenceWarning);learner.fit(x,fit.target,sample_weight=fw)
                bundle={**central,'model':make_pipeline(central['model'][0],learner)}
                if central['mode']=='temperature':
                    cp=p.probability(bundle['model'],p.design(cal,central['config'],central['prior']))
                    bundle['temperature']=p.fit_temperature(cal.target.to_numpy(),cp,p.weights(cal)*count[ci])
                warning=any(isinstance(w.message,ConvergenceWarning) for w in caught)
                joblib.dump(bundle,path);reports.append({'replicate':i,'role':role,'convergence_warning':warning,
                    'temperature':bundle['temperature'],'fit_n':len(fit),'calibration_n':len(cal),'sha256':b.digest(path)})
    b.save_json(OUT/'bootstrap.json',{'replicates':reports,'protocol_sha256':b.digest(OUT/'protocol.json')})
    print('14.1.1 common-game role refits completed',flush=True)


def simulate():
    assert read(OUT/'protocol.json')==protocol()
    options=pd.read_parquet(OUT/'full_options.parquet');cache={};win=winners()
    original_first=a.first_probability;original_protocol=a.protocol;original_load=joblib.load;original_out=a.OUT
    def tagged_load(path,*args,**kwargs):
        fit=original_load(path,*args,**kwargs)
        if isinstance(path,(str,Path)):
            path=Path(path)
            if path.resolve()==(r.OUT/'baseline_matchup.joblib').resolve():fit['_patch_replicate']=0
            elif path.parent.resolve()==OUT.resolve() and path.name.endswith('_baseline.joblib'):
                fit['_patch_replicate']=int(path.name.split('_')[1])+1
        return fit
    def first(frame,baseline,role_fits):
        rep=baseline['_patch_replicate']
        if rep not in cache:
            probability=original_first(options,baseline,{})
            fits={role:original_load(p.OUT/f'final_{role}_{name}.joblib' if rep==0 else OUT/f'bootstrap_{rep-1}_{role}.joblib') for role,name in win.items()}
            for role,fit in fits.items():
                mask=options.forecast_role.eq(role);probability[mask]=p.predict(fit,options.loc[mask])
            cache[rep]=probability
            if rep==0:
                direct=original_first(frame,baseline,{})
                for role,fit in fits.items():
                    mask=frame.forecast_role.eq(role)
                    if mask.any():direct[mask]=p.predict(fit,options.iloc[frame.loc[mask,'_patch_row'].to_numpy(dtype=int)])
                assert np.allclose(direct,probability[frame._patch_row.to_numpy(dtype=int)],rtol=0,atol=1e-13)
                b.save_json(OUT/'cache_check.json',{'central_repeated_vs_direct_max_abs':float(np.max(np.abs(direct-probability[frame._patch_row.to_numpy(dtype=int)]))),'tolerance':1e-13})
        return cache[rep][frame._patch_row.to_numpy(dtype=int)]
    # Direct check above needs only base columns for original inference; rich input
    # rows are read from the unexpanded full option table by immutable row key.
    a.OUT=OUT;a.protocol=protocol;a.first_probability=first;joblib.load=tagged_load
    try:a.simulate()
    finally:a.OUT=original_out;a.protocol=original_protocol;a.first_probability=original_first;joblib.load=original_load
    current=pd.read_parquet(OUT/'action_values_2024.parquet');old=pd.read_parquet(OLD/'action_values_2024.parquet')
    cross=current[current.pool.eq('role')].merge(old[old.pool.eq('role')],on='decision_id',validate='one_to_one',suffixes=('_new','_old'))
    assert len(cross)==484;cross.to_parquet(OUT/'v2_v3_comparison.parquet',index=False,compression='zstd')
    changed=cross.research_direction_new.ne(cross.research_direction_old)
    status='通過候選已另版重跑原484點；僅第一PA更動，研究方向與區間逐點留版'
    review={'status':status,'originalCases':484,'rerun':True,'firstModels':selected(),
        'directionCounts':cross.research_direction_new.value_counts().to_dict(),'previousDirectionCounts':cross.research_direction_old.value_counts().to_dict(),
        'supported':int(cross.simulation_supported_new.sum()),'conditionalComparisons':int(current.pool.ne('role').sum()),
        'changedDirections':int(changed.sum()),'directReversals':int(((cross.research_direction_new.eq('pool_higher')&cross.research_direction_old.eq('continue_higher'))|(cross.research_direction_new.eq('continue_higher')&cross.research_direction_old.eq('pool_higher'))).sum()),
        'directionCrosstab':pd.crosstab(cross.research_direction_old,cross.research_direction_new).to_dict(orient='index'),
        'values':{key:{'meanChange':float((cross[key+'_delta_new']-cross[key+'_delta_old']).mean()),'p10p90Change':(cross[key+'_delta_new']-cross[key+'_delta_old']).quantile([.1,.9]).tolist()} for key in ['wpa','re24']},
        'protocolHash':b.digest(OUT/'protocol.json'),'path':'data/research/decision_action_sensitivity_v3',
        'recommendationAllowed':False,'individualRankingAllowed':False,'test2025OutcomesExamined':False}
    b.save_json(p.OUT/'impact_review.json',review)
    files=[x for x in OUT.rglob('*') if x.is_file() and x.name!='manifest.json']
    b.save_json(OUT/'manifest.json',{'version':'decision_action_sensitivity_v3','files':[{'path':x.relative_to(OUT).as_posix(),'bytes':x.stat().st_size,'sha256':b.digest(x)} for x in sorted(files)]})
    print('14.1.1 direction sensitivity saved',flush=True)


def retain():
    assert not winners() and read(OLD/'protocol.json')==a.protocol()
    for entry in read(OLD/'manifest.json')['files']:assert b.digest(OLD/entry['path'])==entry['sha256']
    summary=read(OLD/'summary.json')
    b.save_json(p.OUT/'impact_review.json',{'status':'沒有候選通過預定門檻；核對原14.1輸入／模型／484點產物後保留基準，不重跑相同模擬',
        'originalCases':484,'rerun':False,'directionCounts':summary['role_direction_counts'],'supported':summary['role_supported'],
        'conditionalComparisons':summary['conditional_pool_comparisons'],'changedDirections':0,'directReversals':0,
        'firstModels':selected(),'recommendationAllowed':False,'individualRankingAllowed':False,'test2025OutcomesExamined':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','bootstrap','simulate','retain'])
    globals()[parser.parse_args().stage]()
