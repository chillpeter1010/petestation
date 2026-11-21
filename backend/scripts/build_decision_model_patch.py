"""Bounded13.6.1-3 diagnostics.2024 is already used;2025 remains locked.

Independent feature additions, nested temporal calibration and one shallow tree
family. All choices freeze before inspecting new2024 scores. Old artifacts read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import warnings
import sklearn

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,OrdinalEncoder,StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_role_ablation as u

b,r=u.b,u.r
OUT=b.ROOT/'data/research/decision_model_diagnostics_v3'
SEED=20261119
PILOT_FIT_CAP=30000
PILOT_CAL_CAP=10000
LIVE_MAP={'live_stuff_dev':'option_stuff','live_location_dev':'option_location','live_quality_dev':'quality',
          'live_physical_dev':'physical','live_command_dev':'command'}
CURRENT=list(LIVE_MAP)+['live_velocity','live_whiff','live_csw','live_ev','mix_delta_research_stuff_plus',
    'mix_delta_research_location_plus','personal_delta_stuff','personal_delta_location']+u.RISK
RECENT=u.LOAD5+u.SEASON+u.RECENT
BATTER=[x for x in u.ATTACK if not any('_'+f+'_' in x for f in u.h.FAMILIES)]+u.BVP+u.TYPE+u.EXPOSURE
GROUPS={'base':[],'current':CURRENT,'recent':RECENT,'batter':BATTER,'rich':CURRENT+RECENT+BATTER}
CONFIGS=[{'id':f'linear_{group}_{alpha:g}','kind':'linear','group':group,'alpha':alpha}
    for group in ['base','current','recent','batter'] for alpha in [.001,.01,.1]]
CONFIGS += [{'id':f'tree_{group}_{leaves}','kind':'tree','group':group,'leaves':leaves}
    for group in ['base','rich'] for leaves in [7,15]]
CONFIG_BY_ID={c['id']:c for c in CONFIGS}
MODES=['raw','temperature']


def save(name,value):b.save_json(OUT/name,value)


def load(year):
    f=u.load(year,True)
    for target,source in LIVE_MAP.items():f[target]=(pd.to_numeric(f[source],errors='coerce')-100).where(f.is_current)
    return f


def columns(config):
    numeric=list(dict.fromkeys(b.LEVELS['matchup'][0]+u.SUPPORT+GROUPS[config['group']]))
    cat=list(dict.fromkeys(b.LEVELS['matchup'][1]+u.SUPPORT_CAT+(['arsenal_type'] if config['group'] in ['batter','rich'] else [])))
    return numeric,cat


def design(frame,config,prior):
    x=b.design(frame,'matchup',20,prior);numeric,cat=columns(config)
    extras={key:pd.to_numeric(frame[key],errors='coerce').replace([np.inf,-np.inf],np.nan) for key in numeric if key not in x}
    extras.update({key:frame[key].astype('string').fillna('unknown').astype(str) for key in cat if key not in x})
    return pd.concat([x,pd.DataFrame(extras,index=frame.index)],axis=1)


def make_model(config):
    numeric,cat=columns(config)
    if config['kind']=='linear':
        transform=ColumnTransformer([
            ('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),numeric),
            ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=True),cat)],sparse_threshold=1.)
        return make_pipeline(transform,SGDClassifier(alpha=config['alpha'],**b.LEARNER))
    transform=ColumnTransformer([('numeric','passthrough',numeric),
        ('categorical',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=np.nan,encoded_missing_value=np.nan),cat)],sparse_threshold=0.)
    categories=list(range(len(numeric),len(numeric)+len(cat)))
    return make_pipeline(transform,HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=config['leaves'],
        min_samples_leaf=200,l2_regularization=10.,learning_rate=.05,max_bins=63,
        categorical_features=categories,early_stopping=False,random_state=SEED))


def probability(model,x):
    p=model.predict_proba(x);out=np.zeros((len(x),9));out[:,model[-1].classes_.astype(int)]=p
    out=np.clip(out,1e-12,1);return out/out.sum(axis=1,keepdims=True)


def temperature_probability(p,temperature):
    z=np.log(np.clip(p,1e-12,1))/temperature;z-=z.max(axis=1,keepdims=True)
    p=np.exp(z);return p/p.sum(axis=1,keepdims=True)


def fit_temperature(y,p,weights=None):
    weights=np.ones(len(y)) if weights is None else np.asarray(weights)
    idx=np.arange(len(y))
    def objective(t):return float(np.average(-np.log(temperature_probability(p,t)[idx,y]),weights=weights))
    result=minimize_scalar(objective,bounds=(.5,3.),method='bounded',options={'xatol':1e-4})
    return float(result.x)


def weights(frame):
    value=1/frame.groupby('game_pk').decision_id.transform('count').to_numpy();return value/value.mean()


def temporal_partition(frame):
    """Last20% observed game-end dates calibrate; spanning games excluded."""
    dates=frame.groupby('game_pk').pa_end_at.max().sort_values().to_numpy()
    boundary=float(np.floor(dates[int(.8*len(dates))]/86400)*86400)
    games=frame.groupby('game_pk').agg(first=('decision_at','min'),last=('pa_end_at','max'))
    spanning=set(games.index[(games['first']<boundary)&(games['last']>=boundary)])
    fit=frame[frame.pa_end_at.lt(boundary)&~frame.game_pk.isin(spanning)].copy()
    cal=frame[frame.decision_at.ge(boundary)&~frame.game_pk.isin(spanning)].copy()
    assert fit.pa_end_at.max()<cal.decision_at.min()
    assert set(fit.game_pk).isdisjoint(cal.game_pk)
    return fit,cal,{'boundary':boundary,'spanning_games_excluded':len(spanning),'fit_n':len(fit),'calibration_n':len(cal)}


def game_sample(frame,cap):
    ranks=sorted(frame.game_pk.unique(),key=lambda x:hashlib.sha256(f'{SEED}:{int(x)}'.encode()).hexdigest())
    sizes=frame.groupby('game_pk').size();take=[];n=0
    for game in ranks:
        take.append(game);n+=int(sizes.loc[game])
        if n>=cap:break
    return frame[frame.game_pk.isin(take)].copy()


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    assert json.loads((u.OUT/'protocol.json').read_text('utf-8'))==u.protocol()
    cohorts=[]
    for year in range(2021,2025):
        f=load(year)
        for role,g in f.groupby('forecast_role'):
            cohorts.append({'year':year,'role':role,'n':len(g),'keys_sha256':hashlib.sha256('\n'.join(sorted(g.decision_id)).encode()).hexdigest()})
        print(f'Patch cohort{year}:{len(f):,} PA',flush=True)
    save('preparation.json',{'cohorts':cohorts,'support_units':'option_plus_n: current valid pitches vs closed-history valid appearances; never apply a common count shrinkage across scopes',
        'scope_fix':'current state channels masked for replacement; recent channels preserve same-role closed history; old source files unchanged'})


def protocol():
    paths=[Path(__file__),Path(u.__file__),u.OUT/'protocol.json',OUT/'plan_snapshot.json',OUT/'preparation.json']
    paths += [u.OUT/f'features_{y}.parquet' for y in range(2021,2025)]
    paths += [b.PREP/f'clean_labels_{y}.parquet' for y in range(2021,2025)]
    paths += [u.OUT/f'validation_{role}_baseline.parquet' for role in ['SP','RP']]
    return {'version':'decision_model_diagnostics_v3','input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'library_versions':{'sklearn':sklearn.__version__,'numpy':np.__version__,'pandas':pd.__version__},
        'date':'2026-11-19','configurations':CONFIGS,'modes':MODES,'feature_groups':GROUPS,'current_state_map':LIVE_MAP,
        'selection_windows':{'score2022':'past2021 only','score2023':'past2021-2022 only','fit_calibration':'chronological last20% game-end date; spanning games excluded; all labels strictly before calibration start',
            'pilot_fit_cap':PILOT_FIT_CAP,'pilot_calibration_cap':PILOT_CAL_CAP,'sampling':'whole games by fixed SHA ranking; same rows for all configs/modes',
            'validation':'full organic2022/2023 cohorts, average yearly log loss; no2024-based tuning'},
        'calibration':'scalar temperature[.5,3], training-internal calibration only; same fitted learner compared raw/calibrated, calibration rows never learner fit',
        'shortlist':'best alpha/mode per linear group base/current/recent/batter and best leaves/mode per tree base/rich =>6 frozen candidates/role, selected before new2024 evaluation',
        'confirmation':'fit all training-partition rows2021-23 (pilot cap removed); same temporal calibration holdout for both modes;2024 ALREADY USED diagnostic only,2025 untouched',
        'gate':'200 game x pitcher paired bootstrap, simultaneous97.5 role-family LL bands plus2role correction; upper<0 vs frozenv2 reference, Brier lower, top-label ECE<=reference+.01, >=500 subgroup LL harm<=.005, no optimizer warnings; both inner years LL harm<=.005 vs matched linear/tree base',
        'augmented_gate':'also beat tuned matched-family base in2024 LL simultaneous band and Brier, otherwise prefer baseline; no importance/feature claim from algorithm-only gain',
        'promotion_order':'first eligible by frozen inner-CV ranking; no2024 score minimization or revised search after seeing diagnostics; none=>frozen_v2_baseline',
        'explanation':'raw/calibration/training/forward metrics, year and model-fold-compatible scope distributions; fixed-model joint group permutation within current/history x previous-role x calendar-month, preserving base controls; diagnostic model reliance, not causal or conditional importance',
        'runtime':'SGD independent OVR classes threading4, numeric libraries2 threads; HGB2 threads, fixed60 iterations/7-or15 leaves',
        'stop':'14.1.1 impact review, no14.2/15; operational recommendation/individual ranking disabled',
        'test_outcome_metrics_examined':False,'recommendation_allowed':False}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen patch differs; preserve explicit revision')
    save('protocol.json',value);print('Bounded patch protocol frozen before model search',flush=True)


def fit_bundle(fit,cal,config,mode='temperature'):
    prior=np.bincount(fit.target,minlength=9)/len(fit);model=make_model(config)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning)
        model.fit(design(fit,config,prior),fit.target,**{('sgdclassifier__sample_weight' if config['kind']=='linear' else 'histgradientboostingclassifier__sample_weight'):weights(fit)})
    cp=probability(model,design(cal,config,prior));temperature=fit_temperature(cal.target.to_numpy(),cp,weights(cal))
    return {'model':model,'config':config,'prior':prior,'temperature':temperature,'mode':mode,
        'convergence_warning':any(isinstance(x.message,ConvergenceWarning) for x in caught),
        'fit_n':len(fit),'calibration_n':len(cal),'latest_fit_label':float(fit.pa_end_at.max()),'earliest_calibration_anchor':float(cal.decision_at.min()),'latest_calibration_label':float(cal.pa_end_at.max())}


def predict(bundle,frame,mode=None):
    p=probability(bundle['model'],design(frame,bundle['config'],bundle['prior']))
    return temperature_probability(p,bundle['temperature']) if (mode or bundle['mode'])=='temperature' else p


def screen(role):
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    frames={y:load(y) for y in [2021,2022,2023]};reports=[];splits=[]
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for year in [2022,2023]:
            train=pd.concat([f for y,f in frames.items() if y<year],ignore_index=True)
            train=train[train.forecast_role.eq(role)&train.pa_end_at.lt(pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp())]
            lo=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp();hi=pd.Timestamp(f'{year+1}-01-01',tz='UTC').timestamp()
            valid=frames[year][frames[year].forecast_role.eq(role)&frames[year].decision_at.ge(lo)&frames[year].pa_end_at.lt(hi)].reset_index(drop=True)
            fit,cal,flow=temporal_partition(train);fit=game_sample(fit,PILOT_FIT_CAP);cal=game_sample(cal,PILOT_CAL_CAP)
            assert cal.pa_end_at.max()<valid.decision_at.min()
            ledger=pd.concat([g[['decision_id','game_pk','decision_at','pa_end_at']].assign(partition=name) for name,g in [('fit',fit),('calibration',cal),('validation',valid)]],ignore_index=True)
            ledger.to_parquet(OUT/f'split_{role}_{year}.parquet',index=False,compression='zstd')
            splits.append({'year':year,'role':role,**flow,'pilot_fit_n':len(fit),'pilot_calibration_n':len(cal),'validation_n':len(valid)})
            for config in CONFIGS:
                started=time.perf_counter();print(f'Patch screen{role}/{year}/{config["id"]}: {len(fit):,} fit,{len(cal):,} cal,{len(valid):,} score',flush=True)
                bundle=fit_bundle(fit,cal,config)
                p=predict(bundle,valid,'raw');tp=temperature_probability(p,bundle['temperature'])
                for mode,prob in [('raw',p),('temperature',tp)]:
                    reports.append({'role':role,'year':year,'config':config['id'],'kind':config['kind'],'group':config['group'],'mode':mode,
                        'metrics':b.metrics(valid.target.to_numpy(),prob),'temperature':bundle['temperature'],'convergence_warning':bundle['convergence_warning']})
                joblib.dump(bundle,OUT/f'screen_{role}_{year}_{config["id"]}.joblib')
                print(f'Patch screen finished in{time.perf_counter()-started:.1f}s',flush=True)
    save(f'screen_{role}.json',{'role':role,'splits':splits,'reports':reports,'2024_used_for_selection':False})


def diagnose():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    fields=list(dict.fromkeys(u.PLUS+['quality','physical','command','live_velocity','live_whiff','live_ev',
        'pitches_3d_before','pitches_5d_before','consecutive_days','season_appearance_number','option_signal_age_hours','option_plus_n',
        'recent_last1_stuff','recent_last3_quality','game3_contact','game3_whiff','game3_ev','affinity_whiff','affinity_ev','pair_n','type_n']))
    frames={y:load(y) for y in range(2021,2025)};rows=[];folds=[]
    for year,f in frames.items():
        with r.connect() as c:
            c.register('q',f[['decision_id','option_pitcher_id','is_current']])
            c.read_parquet(str(r.OUT/f'current_features_{year}.parquet')).create_view('live')
            c.read_parquet(str(r.OUT/f'recent_links_{year}.parquet')).create_view('l')
            c.read_parquet(str(r.OUT/f'recent_profiles_{year}.parquet')).create_view('p')
            source=c.execute('''SELECT q.decision_id,CASE WHEN q.is_current THEN live.observation_model_id ELSE p.fold_id END model_context
                FROM q JOIN live USING(decision_id) JOIN l USING(decision_id,option_pitcher_id) JOIN p USING(profile_id)''').fetchdf()
        f=f.merge(source,on='decision_id',validate='one_to_one');f['model_context']=f.model_context.fillna('unknown_or_warmup')
        for (role,current),g in f.groupby(['forecast_role','is_current']):
            for name in fields:
                values=pd.to_numeric(g[name],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
                rows.append({'year':year,'role':role,'is_current':bool(current),'field':name,'n':len(g),'valid_n':len(values),
                    'missing_pct':100*(1-len(values)/len(g)),'mean':float(values.mean()) if len(values) else None,
                    'sd':float(values.std()) if len(values)>1 else None,'p01':float(values.quantile(.01)) if len(values) else None,
                    'p50':float(values.median()) if len(values) else None,'p99':float(values.quantile(.99)) if len(values) else None})
        for (role,current,context),g in f.groupby(['forecast_role','is_current','model_context']):
            folds.append({'year':year,'role':role,'is_current':bool(current),'model_context':context,'n':len(g),
                'stuff_n':int(g.option_stuff.notna().sum()),'stuff_mean':None if not g.option_stuff.notna().any() else float(g.option_stuff.mean()),
                'quality_n':int(g.quality.notna().sum()),'quality_mean':None if not g.quality.notna().any() else float(g.quality.mean())})
        print(f'Patch diagnostics{year}:scope/year distributions',flush=True)
    old=json.loads((u.OUT/'validation.json').read_text('utf-8'));errors=[]
    development=pd.concat([frames[y] for y in [2021,2022,2023]],ignore_index=True)
    with threadpool_limits(limits=2):
        for role in ['SP','RP']:
            f=development[development.forecast_role.eq(role)].reset_index(drop=True)
            for variant in ['baseline','plus','states','all']:
                print(f'Patch apparent training error{role}/{variant}',flush=True)
                fit=joblib.load(u.OUT/f'{role}_{variant}.joblib');parts=[]
                for start in range(0,len(f),8192):
                    parts.append(b.probabilities(fit['model'],u.design(f.iloc[start:start+8192],variant,fit['prior'])))
                metrics=b.metrics(f.target.to_numpy(),np.vstack(parts));valid=old['roles'][role]['results'][variant]['metrics']
                errors.append({'role':role,'variant':variant,'training':metrics,'validation2024':valid,
                    'validation_minus_training_LL':valid['log_loss']-metrics['log_loss']})
    save('diagnostics.json',{'distributions':rows,'model_contexts':folds,'apparent_errors':errors,
        'support_units':'current option_plus_n is valid pitches; closed prior option_plus_n is valid appearances; comparison/shrinkage must respect scope',
        'interpretation':'Apparent-training/validation gap and year drift are diagnostics, not a definitive overfit/causal label. Different research folds/scopes must not be treated as same measurement model.'})


def select():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    selected={};all_rows=[]
    for role in ['SP','RP']:
        reports=json.loads((OUT/f'screen_{role}.json').read_text('utf-8'))['reports'];rows=[]
        for config in CONFIGS:
            for mode in MODES:
                values=[x for x in reports if x['config']==config['id'] and x['mode']==mode]
                assert {x['year'] for x in values}=={2022,2023}
                rows.append({'config':config['id'],'kind':config['kind'],'group':config['group'],'mode':mode,
                    'mean_LL':float(np.mean([x['metrics']['log_loss'] for x in values])),
                    'mean_Brier':float(np.mean([x['metrics']['brier'] for x in values])),
                    'warning':any(x['convergence_warning'] for x in values),
                    'years':{str(x['year']):{'LL':x['metrics']['log_loss'],'Brier':x['metrics']['brier']} for x in values}})
        chosen=[]
        for kind,group in [('linear','base'),('linear','current'),('linear','recent'),('linear','batter'),('tree','base'),('tree','rich')]:
            eligible=[x for x in rows if x['kind']==kind and x['group']==group and not x['warning']]
            assert eligible,(role,kind,group)
            chosen.append(min(eligible,key=lambda x:(x['mean_LL'],x['mean_Brier'],x['mode']!='raw',x['config'])))
        chosen=sorted(chosen,key=lambda x:x['mean_LL']);selected[role]=chosen;all_rows +=[{'role':role,**x} for x in rows]
    save('selection.json',{'protocol_sha256':b.digest(OUT/'protocol.json'),'candidates':selected,'screen_table':all_rows,
        '2024_used_for_selection':False,'2025_outcomes_examined':False})
    print('Six candidates/role frozen from2022/2023 forward scores only',flush=True)


def confirm(role):
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    selection=json.loads((OUT/'selection.json').read_text('utf-8'))['candidates'][role]
    development=pd.concat([load(y) for y in [2021,2022,2023]],ignore_index=True)
    development=development[development.forecast_role.eq(role)].reset_index(drop=True)
    fit,cal,flow=temporal_partition(development);valid=load(2024);valid=valid[valid.forecast_role.eq(role)].reset_index(drop=True)
    assert cal.pa_end_at.max()<valid.decision_at.min()
    pd.concat([g[['decision_id','game_pk','decision_at','pa_end_at']].assign(partition=name) for name,g in [('fit',fit),('calibration',cal),('validation',valid)]],ignore_index=True).to_parquet(OUT/f'split_{role}_2024.parquet',index=False,compression='zstd')
    reference=pd.read_parquet(u.OUT/f'validation_{role}_baseline.parquet').set_index('decision_id').loc[valid.decision_id]
    reference_p=reference[['p_'+key for key in b.OUTCOMES]].to_numpy();y=valid.target.to_numpy();idx=np.arange(len(y))
    old_metrics=b.metrics(y,reference_p);base_loss=-np.log(reference_p[idx,y]);base_br=(reference_p**2).sum(axis=1)-2*reference_p[idx,y]+1
    results=[];losses=[];briers=[];ps={}
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for chosen in selection:
            config=CONFIG_BY_ID[chosen['config']];started=time.perf_counter()
            print(f'Patch full confirmation{role}/{config["id"]}/{chosen["mode"]}: {len(fit):,} fit,{len(cal):,} cal,{len(valid):,} score',flush=True)
            bundle=fit_bundle(fit,cal,config,chosen['mode']);p=predict(bundle,valid)
            bundle['role']=role;bundle['training_end']='2024-01-01'
            support=['option_game_pitches','option_current_bf']+[n for n in CURRENT if n.startswith('live_')]
            used=columns(config)[0];bundle['support_ranges']={n:[float(fit[n].min()),float(fit[n].max())] for n in support if n in used and fit[n].notna().any()}
            key=config['id'];joblib.dump(bundle,OUT/f'final_{role}_{key}.joblib')
            out=valid[['decision_id','game_pk','option_pitcher_id','outgoing_role','is_current']].copy()
            for j,name in enumerate(b.OUTCOMES):out['p_'+name]=p[:,j]
            out.to_parquet(OUT/f'confirmation_{role}_{key}.parquet',index=False,compression='zstd')
            ps[key]=p;losses.append(-np.log(p[idx,y]));briers.append((p*p).sum(axis=1)-2*p[idx,y]+1)
            results.append({**chosen,'metrics':b.metrics(y,p),'temperature':bundle['temperature'],'convergence_warning':bundle['convergence_warning']})
            print(f'Patch confirmation finished in{time.perf_counter()-started:.1f}s',flush=True)
    intervals=u.family_intervals(valid,np.column_stack([x-base_loss for x in losses]));br_intervals=u.family_intervals(valid,np.column_stack([x-base_br for x in briers]))
    matched={kind:next(i for i,x in enumerate(results) if x['kind']==kind and x['group']=='base') for kind in ['linear','tree']}
    matches=u.family_intervals(valid,np.column_stack([losses[i]-losses[matched[row['kind']]] for i,row in enumerate(results)]))
    for i,row in enumerate(results):
        baseline=results[matched[row['kind']]];groups=[]
        for (outgoing,current),g in valid.groupby(['outgoing_role','is_current']):
            ix=g.index.to_numpy();groups.append({'outgoing_role':outgoing,'is_current':bool(current),'n':len(ix),
                'LL_delta':float((losses[i][ix]-base_loss[ix]).mean())})
        harm=any(g['n']>=500 and g['LL_delta']>.005 for g in groups)
        stable=all(row['years'][str(year)]['LL']<=baseline['years'][str(year)]['LL']+.005 for year in [2022,2023])
        matched_gate=(row['group']=='base') or (matches[i]['role_family97_5'][1]<0 and row['metrics']['brier']<baseline['metrics']['brier'])
        passed=intervals[i]['role_family97_5'][1]<0 and row['metrics']['brier']<old_metrics['brier'] and row['metrics']['ece']<=old_metrics['ece']+.01 and not harm and stable and matched_gate and not row['convergence_warning']
        row.update({'delta_vs_frozen':intervals[i],'brier_delta':br_intervals[i],'delta_vs_tuned_family_base':matches[i],
            'matched_feature_gate':matched_gate,'inner_stability':stable,'subgroups':groups,'increment_gate':bool(passed)})
    accepted=[row for row in results if row['increment_gate']]
    winner=accepted[0]['config'] if accepted else 'frozen_v2_baseline'
    save(f'confirmation_{role}.json',{'role':role,'flow':flow,'validation_n':len(valid),'reference':old_metrics,'candidates':results,
        'selected':winner,'selection_rule':'first passing in frozen inner-CV rank, not lowest2024 score','2024_independent_test':False,'test_outcome_metrics_examined':False})
    print(f'Patch {role} final diagnostic gate:{winner}',flush=True)


def explain(role):
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    report=json.loads((OUT/f'confirmation_{role}.json').read_text('utf-8'))
    frame=load(2024);frame=frame[frame.forecast_role.eq(role)].reset_index(drop=True)
    frame['_month']=pd.to_datetime(frame.decision_at,unit='s',utc=True).dt.month
    y=frame.target.to_numpy();ix=np.arange(len(y));base_columns=set(sum(columns(CONFIG_BY_ID['linear_base_0.001']),[]))
    rows=[];differences=[]
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for row in report['candidates']:
            if row['group']=='base':continue
            bundle=joblib.load(OUT/f'final_{role}_{row["config"]}.joblib')
            original=predict(bundle,frame);loss=-np.log(original[ix,y]);used=set(sum(columns(bundle['config']),[]))
            for group in ['current','recent','batter']:
                names=sorted((set(GROUPS[group])|({'arsenal_type'} if group=='batter' else set()))&used-base_columns)
                if not names:continue
                changed=frame.copy();rng=np.random.default_rng(SEED)
                for _,g in frame.groupby(['is_current','option_role','_month'],dropna=False):
                    loc=g.index.to_numpy();source=rng.permutation(loc)
                    changed.loc[loc,names]=frame.loc[source,names].to_numpy()
                p=predict(bundle,changed);delta=-np.log(p[ix,y])-loss;differences.append(delta)
                rows.append({'config':row['config'],'group':group,'columns':names,'n':len(frame),
                    'original_LL':float(loss.mean()),'permuted_LL':float((-np.log(p[ix,y])).mean()),
                    'reproducible_diagnostic_only':True})
    bands=u.family_intervals(frame,np.column_stack(differences))
    for row,band in zip(rows,bands):row['LL_increase']=band
    save(f'explanation_{role}.json',{'role':role,'contrasts':rows,'scope':'one fixed joint permutation, monthly current/history x previous-role strata; base columns preserved; correlated groups and support controls can substitute for permuted inputs; no causal or fatigue claim'})
    print(f'Patch {role}: {len(rows)} fixed-model group reliance diagnostics',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','diagnose','screen','select','confirm','explain']);parser.add_argument('--role',choices=['SP','RP'])
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage in ['screen','confirm','explain']:
        assert args.role;globals()[args.stage](args.role)
    else:globals()[args.stage]()
