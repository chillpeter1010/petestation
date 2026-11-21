"""14.2.3 load calibration, actor-safe features and bounded outcome ablations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,OrdinalEncoder,StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_signal_calibration as n

OUT=n.OUT;b,p,u,r=n.b,n.p,n.u,n.r
EXTRA={'A':['A_expected_stuff','A_expected_velocity','A_drift_stuff','A_drift_velocity'],
       'B':['B_expected_location','B_drift_location'],'C':['C_expected_contact','C_drift_contact'],
       'D':['D_severity','load_relative']}
VARIANTS=['control','A','B','C','D','all']
COMMON=['A_supported','B_supported','C_supported','D_supported','block_age_minutes']


def load_frame(year):return p.load(year)


def attach(frame,year):
    f=frame.copy().reset_index(drop=True)
    f['request_id']=f.decision_id+':'+f.option_pitcher_id.astype(str)
    assert f.request_id.is_unique
    with r.connect() as c:
        c.register('q',f[['request_id','decision_id','option_pitcher_id','forecast_role','is_current','decision_at']])
        c.read_parquet(str(r.OUT/f'current_features_{year}.parquet')).create_view('current')
        c.read_parquet(str(OUT/f'block_scores_{year}.parquet')).filter(f'alpha={n.ALPHA}').create_view('s')
        c.read_parquet(str(r.OUT/'appearance_history.parquet')).create_view('h')
        c.execute('''CREATE TEMP TABLE history AS SELECT pitcher_id,role,available_at,
            median(actual_pitches) OVER win median_pitches,count(*) OVER win history_n FROM h
            WHERE available_at IS NOT NULL AND NOT bad_timing AND actual_pitches>0
            WINDOW win AS(PARTITION BY pitcher_id,role ORDER BY available_at,appearance_id ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)''')
        c.execute('''CREATE TEMP TABLE requests AS SELECT q.*,l.appearance_id,
            CASE WHEN q.is_current THEN l.entry_at ELSE q.decision_at END reference_clock
            FROM q LEFT JOIN current l ON q.decision_id=l.decision_id AND q.option_pitcher_id=l.pitcher_id AND q.is_current''')
        fields=['block_id','session_id','available_at','block_number','session_pitches','personal_reference_at']
        fields += [g+suffix for g in ['A','B','C'] for suffix in ['_state','_severity','_risk']]
        fields += ['expected_'+x for x in n.TARGETS]+['smooth_'+x for x in n.TARGETS]
        result=c.execute('''SELECT q.request_id,q.appearance_id,q.reference_clock,'''+','.join('s.'+v for v in fields)+''',
            h.available_at D_reference_at,h.median_pitches,h.history_n FROM requests q
            ASOF LEFT JOIN s ON q.appearance_id=s.appearance_id AND q.decision_at>s.available_at
            ASOF LEFT JOIN history h ON q.option_pitcher_id=h.pitcher_id AND q.forecast_role=h.role AND q.reference_clock>h.available_at''').fetchdf().set_index('request_id').reindex(f.request_id)
    for field in result:f[field]=result[field].to_numpy()
    f['A_expected_stuff']=f.expected_stuff;f['A_expected_velocity']=f.expected_velocity
    f['A_drift_stuff']=f.smooth_stuff;f['A_drift_velocity']=f.smooth_velocity
    f['B_expected_location']=f.expected_location;f['B_drift_location']=f.smooth_location
    f['C_expected_contact']=f.expected_contact;f['C_drift_contact']=f.smooth_contact
    f['load_relative']=f.option_game_pitches/f.median_pitches
    f['recent72_relative']=f.prior_games_pitches_3d/f.median_pitches
    f['recent120_relative']=f.prior_games_pitches_5d/f.median_pitches
    f['streak']=f.consecutive_days;f['short_rest']=-np.log1p(f.entry_rest_hours.clip(lower=0))
    f['load_known']=f.history_n.ge(5)&f.lookback_14d_complete&np.isfinite(f[n.LOAD]).all(axis=1)
    f['block_age_minutes']=(f.decision_at-f.available_at)/60
    for group in ['A','B','C']:
        f[group+'_state']=f[group+'_state'].fillna(-1).astype(int)
        f[group+'_supported']=f[group+'_state'].ge(0)&f.is_current
        f.loc[~f[group+'_supported'],EXTRA[group]]=np.nan
    f.loc[~f.load_known,n.LOAD]=np.nan
    assert (f.available_at.dropna()<f.loc[f.available_at.notna(),'decision_at']).all()
    assert (f.D_reference_at.dropna()<f.loc[f.D_reference_at.notna(),'reference_clock']).all()
    return f


def compact(frame):
    fields=['year','request_id','decision_id','game_pk','decision_at','pa_end_at','option_pitcher_id','forecast_role','outgoing_role','is_current',
        'appearance_id','block_id','session_id','available_at','block_number','session_pitches','personal_reference_at','reference_clock','D_reference_at',
        'median_pitches','history_n','load_known','block_age_minutes',*n.LOAD]
    fields += [x for values in EXTRA.values() for x in values if x!='D_severity']
    fields += [g+s for g in ['A','B','C'] for s in ['_state','_severity','_risk','_supported']]
    return frame[list(dict.fromkeys(x for x in fields if x in frame))].copy()


def prepare(year):
    f=attach(load_frame(year),year);n.write(compact(f),f'raw_features_{year}.parquet')
    print(f'14.2.3 actor-safe{year}: {len(f):,} organic PA feature requests; incoming actors never inherit outgoing blocks',flush=True)


def midrank(reference,value):
    return (np.searchsorted(reference,value,side='left')+np.searchsorted(reference,value,side='right'))/(2*len(reference))


def load_severity(frame,model):
    arrays=[midrank(model['reference'][key],frame[key].fillna(0).to_numpy()) for key in n.LOAD]
    return np.where(frame.load_known,np.max(np.column_stack(arrays),axis=1),np.nan)


def fit_load(fold):
    assert n.read(OUT/'feature_protocol.json')==protocol()
    _,cutoff,year=next(x for x in n.FOLDS if x[0]==fold);end=pd.Timestamp(cutoff,tz='UTC').timestamp()
    f=pd.concat([pd.read_parquet(OUT/f'raw_features_{y}.parquet') for y in range(2021,year+1)],ignore_index=True)
    f=f[f.pa_end_at.lt(end)].reset_index(drop=True)
    for role in ['SP','RP']:
        subset=f[f.forecast_role.eq(role)].copy();fit,cal,flow=p.temporal_partition(subset)
        good=fit[fit.load_known];valid=cal[cal.load_known]
        assert len(good)>200 and len(valid)>100
        model={'reference':{key:np.sort(good[key].to_numpy()) for key in n.LOAD},'flow':flow,'role':role,'cutoff':end}
        severity=load_severity(valid,model);model['yellow']=float(np.quantile(severity,.9));model['red']=float(np.quantile(severity,.975))
        joblib.dump(model,OUT/f'load_{fold}_{role}.joblib')
        n.save(f'load_{fold}_{role}.json',{'fold':fold,'role':role,'flow':flow,'fit_supported':len(good),'cal_supported':len(valid),'yellow':model['yellow'],'red':model['red']})
        print(f'14.2.3 load{fold}/{role}: {len(good):,}/{len(valid):,} fit/cal, personal last10 closed role appearances min5',flush=True)


def apply_load(frame,year):
    f=frame.copy();fold,cutoff,_=next(x for x in n.FOLDS if x[2]==year)
    f['D_state']=-1;f['D_severity']=np.nan;f['D_supported']=False
    for role in ['SP','RP']:
        model=joblib.load(OUT/f'load_{fold}_{role}.joblib');mask=f.forecast_role.eq(role)&f.decision_at.ge(model['cutoff'])
        part=f.loc[mask];severity=load_severity(part,model)
        high=part.load_relative.ge(1.1)|part.recent72_relative.ge(1.5)|part.recent120_relative.ge(2.5)|part.streak.ge(2)
        medium=part.load_relative.ge(1)|part.recent72_relative.ge(1)|part.recent120_relative.ge(2)|part.streak.ge(1)
        states=np.where(~np.isfinite(severity),-1,np.where((severity>=model['red'])&high,2,np.where((severity>=model['yellow'])&medium,1,0)))
        f.loc[mask,'D_severity']=severity;f.loc[mask,'D_state']=states;f.loc[mask,'D_supported']=states>=0
    return f


def finalize_features():
    assert n.read(OUT/'feature_protocol.json')==protocol()
    guards={}
    for year in range(2021,2025):
        f=apply_load(pd.read_parquet(OUT/f'raw_features_{year}.parquet'),year)
        n.write(f,f'features_{year}.parquet');guards[f'features_{year}.parquet']=b.digest(OUT/f'features_{year}.parquet')
    options=pd.read_parquet(old_path('full_options.parquet'))
    features=apply_load(compact(attach(options,2024)),2024);n.write(features,'case_features.parquet');guards['case_features.parquet']=b.digest(OUT/'case_features.parquet')
    n.save('feature_guard.json',{'files':guards,'feature_protocol_sha256':b.digest(OUT/'feature_protocol.json')})
    print('14.2.3 all forward/actual-actor feature files and fixed32-game options frozen',flush=True)


def old_path(name):return n.old.OUT/name


def protocol():
    paths=[Path(__file__),OUT/'normal_protocol.json',u.OUT/'protocol.json',p.OUT/'protocol.json',r.OUT/'appearance_history.parquet']
    for year in range(2021,2025):paths += [OUT/f'raw_features_{year}.parquet',OUT/f'block_scores_{year}.parquet']
    return {'version':'signal_feature_calibration_v1','input_sha256':{str(x.relative_to(b.ROOT)):b.digest(x) for x in paths},
        'load':'personal last10 closed same-forecast-role appearance median, min5, reference strictly before current entry or hypothetical incoming decision; complete14d history required',
        'severity':'max midrank CDF across current/personal median, other-game72h and120h / median, prior entry streak and negative log entry-rest; common-tail cal90/97.5 plus predeclared practical ratio/streak evidence; load tail is not a physiological fatigue label',
        'load_practical':'red needs current ratio>=1.1 or72h>=1.5 or120h>=2.5 orstreak>=2; yellow1/1/2/1',
        'scope':'current A/B/C only exact outgoing actor, all incoming A/B/C gray; D evaluated against the option own RP history, never outgoing history',
        'model_features':EXTRA,'common_support':COMMON,'variants':VARIANTS,'test2025_outcomes_examined':False,'recommendation_allowed':False}


def freeze():
    value=protocol();path=OUT/'feature_protocol.json'
    if path.exists():assert n.read(path)==value
    n.save(path.name,value);print('14.2.3 load/actor/feature protocol frozen',flush=True)


def frame(year):
    f=load_frame(year);extra=pd.read_parquet(OUT/f'features_{year}.parquet')
    cols=['decision_id','option_pitcher_id',*COMMON,*[v for values in EXTRA.values() for v in values]]
    return f.merge(extra[cols],on=['decision_id','option_pitcher_id'],validate='one_to_one')


def model_columns(role,variant):
    config=p.CONFIG_BY_ID['tree_rich_7']
    num,cat=(u.model_columns('baseline') if role=='SP' else p.columns(config))
    extras=sum(EXTRA.values(),[]) if variant=='all' else EXTRA.get(variant,[])
    return list(dict.fromkeys(num+COMMON+extras)),cat.copy()


def design(f,role,variant,prior):
    x=u.design(f,'baseline',prior) if role=='SP' else p.design(f,p.CONFIG_BY_ID['tree_rich_7'],prior)
    num,_=model_columns(role,variant)
    return pd.concat([x,pd.DataFrame({key:pd.to_numeric(f[key],errors='coerce') for key in num if key not in x},index=f.index)],axis=1)


def make_model(role,variant):
    num,cat=model_columns(role,variant)
    if role=='SP':
        transform=ColumnTransformer([('n',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),num),
            ('c',OneHotEncoder(handle_unknown='ignore',sparse_output=True),cat)],sparse_threshold=1.)
        return make_pipeline(transform,SGDClassifier(alpha=.001,**b.LEARNER))
    transform=ColumnTransformer([('n','passthrough',num),('c',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=np.nan,encoded_missing_value=np.nan),cat)],sparse_threshold=0.)
    return make_pipeline(transform,HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=7,min_samples_leaf=200,l2_regularization=10.,
        learning_rate=.05,max_bins=63,categorical_features=list(range(len(num),len(num)+len(cat))),early_stopping=False,random_state=n.SEED))


def fit_bundle(fit,cal,role,variant):
    prior=np.bincount(fit.target,minlength=9)/len(fit);model=make_model(role,variant)
    step='sgdclassifier' if role=='SP' else 'histgradientboostingclassifier'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning)
        model.fit(design(fit,role,variant,prior),fit.target,**{step+'__sample_weight':p.weights(fit)})
    cp=p.probability(model,design(cal,role,variant,prior));temperature=p.fit_temperature(cal.target.to_numpy(),cp,p.weights(cal)) if role=='RP' else 1.
    return {'model':model,'prior':prior,'role':role,'variant':variant,'temperature':temperature,
        'convergence_warning':any(isinstance(v.message,ConvergenceWarning) for v in caught)}


def predict(bundle,f):
    return p.temperature_probability(p.probability(bundle['model'],design(f,bundle['role'],bundle['variant'],bundle['prior'])),bundle['temperature'])


def model_protocol():
    paths=[Path(__file__),OUT/'feature_protocol.json',OUT/'feature_guard.json',p.OUT/'confirmation_SP.json',p.OUT/'confirmation_RP.json',r.OUT/'baseline_validation_2024_matchup.parquet']
    paths += [OUT/f'features_{year}.parquet' for year in range(2021,2025)]
    return {'version':'signal_pa_ablation_v1','input_sha256':{str(x.relative_to(b.ROOT)):b.digest(x) for x in paths},
        'variants':VARIANTS,'common_support':COMMON,'inner_selection':'2021->2022 and2021-22->2023; fixed whole-game pilots30k fit/10k calibration, full yearly validation; rank mean yearly LL before2024 confirmation',
        'learners':'SP original role baseline SGD L2.001; RP prior selected tree_rich7/60 + temperature; same common mask/age controls; same fit/cal time split, preprocessing only fit segment',
        'promotion':'frozen inner rank first passing; vs both matched control and actual retained model (SP repaired global, RP selected rich tree) simultaneous97.5 LL upper<0, lower Brier, ECE harm<=.01, >=500 subgroup LL harm<=.005, both inner years harm vs matched control<=.005, no warnings; no passing=>retain previous decisions',
        'scope':'result-probability increment, not causal strategy/fatigue proof; normal expected and residual both retained; no2025 outcomes','recommendation_allowed':False}


def freeze_models():
    value=model_protocol();path=OUT/'model_protocol.json'
    if path.exists():assert n.read(path)==value
    n.save(path.name,value)


def screen(role):
    assert n.read(OUT/'model_protocol.json')==model_protocol()
    frames={y:frame(y) for y in [2021,2022,2023]};rows=[]
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for year in [2022,2023]:
            past=pd.concat([f for y,f in frames.items() if y<year],ignore_index=True);past=past[past.forecast_role.eq(role)]
            fit,cal,_=p.temporal_partition(past);fit=p.game_sample(fit,30000);cal=p.game_sample(cal,10000)
            valid=frames[year][frames[year].forecast_role.eq(role)].reset_index(drop=True)
            assert cal.pa_end_at.max()<valid.decision_at.min()
            for variant in VARIANTS:
                print(f'14.2.3 inner{year}/{role}/{variant}',flush=True)
                bundle=fit_bundle(fit,cal,role,variant);prob=predict(bundle,valid)
                rows.append({'year':year,'variant':variant,'metrics':b.metrics(valid.target.to_numpy(),prob),'warning':bundle['convergence_warning']})
    ranking=sorted([{'variant':v,'mean_LL':float(np.mean([x['metrics']['log_loss'] for x in rows if x['variant']==v])),
        'warning':any(x['warning'] for x in rows if x['variant']==v)} for v in VARIANTS],key=lambda x:x['mean_LL'])
    n.save(f'inner_{role}.json',{'role':role,'rows':rows,'ranking':ranking,'2024_used_for_selection':False})


def confirm(role):
    assert n.read(OUT/'model_protocol.json')==model_protocol()
    inner=n.read(OUT/f'inner_{role}.json');rank=inner['ranking']
    development=pd.concat([frame(y) for y in [2021,2022,2023]],ignore_index=True);development=development[development.forecast_role.eq(role)]
    fit,cal,flow=p.temporal_partition(development);valid=frame(2024);valid=valid[valid.forecast_role.eq(role)].reset_index(drop=True)
    assert cal.pa_end_at.max()<valid.decision_at.min()
    oldpath=r.OUT/'baseline_validation_2024_matchup.parquet' if role=='SP' else p.OUT/'confirmation_RP_tree_rich_7.parquet'
    reference=pd.read_parquet(oldpath).set_index('decision_id').loc[valid.decision_id]
    oldprob=reference[['p_'+key for key in b.OUTCOMES]].to_numpy();y=valid.target.to_numpy();ix=np.arange(len(y))
    oldloss=-np.log(oldprob[ix,y]);oldmetrics=b.metrics(y,oldprob);rows=[];losses=[];br=[]
    with threadpool_limits(limits=2),joblib.parallel_backend('threading',n_jobs=4):
        for variant in VARIANTS:
            print(f'14.2.3 full{role}/{variant}: {len(fit):,} fit {len(cal):,} cal {len(valid):,} score',flush=True)
            bundle=fit_bundle(fit,cal,role,variant);prob=predict(bundle,valid);joblib.dump(bundle,OUT/f'pa_{role}_{variant}.joblib')
            out=valid[['decision_id','game_pk','option_pitcher_id','outgoing_role','is_current']].copy()
            for i,name in enumerate(b.OUTCOMES):out['p_'+name]=prob[:,i]
            n.write(out,f'pa_{role}_{variant}.parquet')
            losses.append(-np.log(prob[ix,y]));br.append((prob**2).sum(axis=1)-2*prob[ix,y]+1)
            rows.append({'variant':variant,'metrics':b.metrics(y,prob),'warning':bundle['convergence_warning']})
    vscontrol=u.family_intervals(valid,np.column_stack([loss-losses[0] for loss in losses]))
    vsold=u.family_intervals(valid,np.column_stack([loss-oldloss for loss in losses]))
    for i,row in enumerate(rows):
        groups=[]
        for (outgoing,current),g in valid.groupby(['outgoing_role','is_current']):
            j=g.index.to_numpy();groups.append({'outgoing_role':outgoing,'is_current':bool(current),'n':len(j),'LL_delta':float((losses[i][j]-oldloss[j]).mean())})
        harm=any(g['n']>=500 and g['LL_delta']>.005 for g in groups)
        stable=all(next(x['metrics']['log_loss'] for x in inner['rows'] if x['year']==year and x['variant']==row['variant'])<=next(x['metrics']['log_loss'] for x in inner['rows'] if x['year']==year and x['variant']=='control')+.005 for year in [2022,2023])
        row.update({'vs_control':vscontrol[i],'vs_retained':vsold[i],'subgroups':groups,'inner_stability':stable})
        row['increment_gate']=bool(row['variant']!='control' and vscontrol[i]['role_family97_5'][1]<0 and vsold[i]['role_family97_5'][1]<0
            and row['metrics']['brier']<min(rows[0]['metrics']['brier'],oldmetrics['brier']) and row['metrics']['ece']<=oldmetrics['ece']+.01 and not harm and stable and not row['warning'])
    passing={x['variant'] for x in rows if x['increment_gate']};winner=next((x['variant'] for x in rank if x['variant'] in passing and not x['warning']),'retain_previous')
    corr=valid[[v for fields in EXTRA.values() for v in fields]].corr(method='spearman',min_periods=200)
    n.save(f'pa_{role}.json',{'role':role,'flow':flow,'validation_n':len(valid),'reference':oldmetrics,'results':rows,'selected':winner,
        'ranking_sha256':b.digest(OUT/f'inner_{role}.json'),'correlations':json.loads(corr.to_json()),'test2025_outcomes_examined':False})
    print(f'14.2.3 {role}: {winner}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','fit_load','finalize_features','freeze_models','screen','confirm']);parser.add_argument('--year',type=int);parser.add_argument('--fold');parser.add_argument('--role',choices=['SP','RP']);args=parser.parse_args()
    if args.stage=='prepare':prepare(args.year)
    elif args.stage=='fit_load':fit_load(args.fold)
    elif args.stage in ['screen','confirm']:globals()[args.stage](args.role)
    else:globals()[args.stage]()
