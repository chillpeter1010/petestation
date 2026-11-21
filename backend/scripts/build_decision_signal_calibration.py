"""14.2.2-4 normal-process and multi-light research.2025 stays sealed.

Ten-pitch NONOVERLAPPING completed blocks, entry-frozen same-type personal
references, temporal normal models and training-internal calibration. Existing
models,32-game values and11/0 alert result remain immutable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,SplineTransformer,StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_alert_research as old

p,u,r,b=old.p,old.p.u,old.r,old.b
OUT=b.ROOT/'data/research/decision_signal_calibration_v1'
ALPHA=.3
SEED=20261119
FOLDS=[('2021_late','2021-09-01',2021),('2022','2022-01-01',2022),('2023','2023-01-01',2023),('2024','2024-01-01',2024)]
TARGETS=['stuff','velocity','location','contact']
GROUPS={'A':['stuff','velocity'],'B':['location'],'C':['contact']}
MARGINS={'stuff':5.,'velocity':.5,'location':5.,'contact':.15}
NUM=['game_pitches','inning_pitches','log_idle','inning','fastball_share','breaking_share','offspeed_share','batter_k','reference_stuff','reference_velocity']
CURVES=['game_pitches','inning_pitches','log_idle']
LOAD=['load_relative','recent72_relative','recent120_relative','streak','short_rest']


def read(path):return json.loads(path.read_text('utf-8'))


def save(name,value):b.save_json(OUT/name,value)


def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def prepare(year):
    OUT.mkdir(parents=True,exist_ok=True)
    with r.connect() as c:
        c.read_parquet(str(r.OUT/f'pitch_observations_{year}.parquet')).create_view('o')
        c.read_parquet(str(r.OUT/'type_prior.parquet')).create_view('t')
        c.read_parquet(str(r.OUT/'appearance_history.parquet')).create_view('a')
        c.read_parquet(str(old.FOUNDATION/f'events_{year}.parquet')).create_view('events')
        c.read_parquet(str(u.h.OUT/f'identity_exclusions_{year}.parquet')).create_view('ex')
        c.read_parquet(str(b.PREP/'ability_history.parquet')).create_view('history')
        c.execute("CREATE TEMP TABLE batters AS SELECT * FROM history WHERE actor='batter' AND split='All' QUALIFY row_number() OVER(PARTITION BY player_id,available_at ORDER BY pa_n DESC)=1")
        c.execute('''CREATE TEMP TABLE pitches AS SELECT o.*,e.inning,e.half,a.entry_at,
            row_number() OVER(PARTITION BY o.session_id,e.inning,e.half ORDER BY o.available_at,o.event_index) inning_pitch,
            greatest(0.,o.started_at-lag(o.available_at) OVER(PARTITION BY o.session_id ORDER BY o.available_at,o.event_index))/60. idle_minutes,
            floor((o.session_pitch_position-1)/10)::INTEGER block_number
            FROM o JOIN events e USING(event_id) JOIN a ON a.appearance_id=o.appearance_id
            WHERE o.time_reliable AND o.alignment_status='validated_order' AND o.role IN('SP','RP')
                AND NOT EXISTS(SELECT1 FROM ex WHERE ex.game_pk=o.game_pk AND ex.at_bat_number=o.at_bat_number)'''.replace('SELECT1','SELECT 1'))
        c.execute('''CREATE TEMP TABLE referenced AS SELECT o.*,t.available_at personal_reference_at,
            CASE WHEN t.research_stuff_plus_n>=20 THEN t.research_stuff_plus_sum/t.research_stuff_plus_n END reference_stuff,
            CASE WHEN t.research_location_plus_n>=20 THEN t.research_location_plus_sum/t.research_location_plus_n END reference_location,
            CASE WHEN t.release_speed_n>=20 THEN t.release_speed_sum/t.release_speed_n END reference_velocity,
            h.available_at batter_history_at,h.k_n/nullif(h.pa_n,0) batter_k
            FROM pitches o ASOF LEFT JOIN t ON o.pitcher_id=t.pitcher_id AND o.role=t.role AND o.pitch_type=t.pitch_type
                AND o.plus_model_id=t.model_id AND o.entry_at>t.available_at
            ASOF LEFT JOIN batters h ON o.batter_id=h.player_id AND o.started_at>h.available_at''')
        c.execute('''CREATE TABLE blocks AS SELECT session_id||':'||cast(block_number AS VARCHAR) block_id,
            any_value(year) AS year,any_value(game_pk) game_pk,any_value(appearance_id) appearance_id,
            any_value(pitcher_id) pitcher_id,any_value(role) AS role,session_id,block_number,
            min(started_at) anchor_at,max(available_at) available_at,max(appearance_pitch_position) game_pitches,
            max(session_pitch_position) session_pitches,avg(inning_pitch) inning_pitches,
            ln(1+coalesce(max(least(idle_minutes,480.)),0)) log_idle,max(inning) inning,
            avg(CASE WHEN pitch_type IN('FF','SI','FC') THEN1 ELSE0 END) fastball_share,
            avg(CASE WHEN pitch_type IN('SL','ST','CU','KC','SV','CS') THEN1 ELSE0 END) breaking_share,
            avg(CASE WHEN pitch_type IN('CH','FS','FO','SC') THEN1 ELSE0 END) offspeed_share,
            avg(batter_k) batter_k,avg(reference_stuff) reference_stuff,avg(reference_velocity) reference_velocity,
            avg(research_stuff_plus) mean_stuff,avg(research_location_plus) mean_location,avg(release_speed) mean_velocity,
            avg(research_stuff_plus-reference_stuff) y_stuff,count(research_stuff_plus-reference_stuff) n_stuff,
            avg(release_speed-reference_velocity) y_velocity,count(release_speed-reference_velocity) n_velocity,
            avg(research_location_plus-reference_location) y_location,count(research_location_plus-reference_location) n_location,
            avg(contact) FILTER(WHERE swing=1) y_contact,count(contact) FILTER(WHERE swing=1) n_contact,
            max(personal_reference_at) personal_reference_at,max(batter_history_at) batter_history_at,min(entry_at) entry_at,
            count(*) measured_pitches,count(DISTINCT plus_model_id) measurement_models,any_value(plus_model_id) measurement_model
            FROM referenced GROUP BY session_id,block_number HAVING count(*)=10 AND max(session_pitch_position)-min(session_pitch_position)=9'''.replace('THEN1','THEN 1').replace('ELSE0','ELSE 0'))
        blocks=c.table('blocks').fetchdf().sort_values(['session_id','block_number']).reset_index(drop=True)
    assert blocks.block_id.is_unique
    assert (blocks.personal_reference_at.dropna()<blocks.loc[blocks.personal_reference_at.notna(),'entry_at']).all()
    assert (blocks.batter_history_at.dropna()<blocks.loc[blocks.batter_history_at.notna(),'available_at']).all()
    write(blocks,f'blocks_{year}.parquet')
    save(f'blocks_{year}.json',{'year':year,'blocks':len(blocks),'roles':blocks.role.value_counts().to_dict(),
        'personal_stuff_n8':int(blocks.n_stuff.ge(8).sum()),'personal_location_n8':int(blocks.n_location.ge(8).sum()),
        'mixed_measurement_blocks':int(blocks.measurement_models.ne(1).sum()),'identity_exclusions_retained':True})
    print(f'14.2.2 {year}: {len(blocks):,} closed nonoverlapping blocks, personal references frozen before appearance entry',flush=True)


def scope(frame):
    return frame.session_pitches.ge(np.where(frame.role.eq('SP'),35,10))&frame.game_pitches.le(np.where(frame.role.eq('SP'),100,60))&frame.measurement_models.eq(1)


def supported(frame,target):return scope(frame)&frame['n_'+target].ge(4 if target=='contact' else 8)&frame['y_'+target].notna()


def split(frame):
    dates=frame.groupby('game_pk').available_at.max().sort_values().to_numpy()
    boundary=float(np.floor(dates[int(.8*len(dates))]/86400)*86400)
    games=frame.groupby('game_pk').agg(first=('anchor_at','min'),last=('available_at','max'))
    spanning=set(games.index[(games['first']<boundary)&(games['last']>=boundary)])
    fit=frame[frame.available_at.lt(boundary)&~frame.game_pk.isin(spanning)].copy()
    cal=frame[frame.anchor_at.ge(boundary)&~frame.game_pk.isin(spanning)].copy()
    assert fit.available_at.max()<cal.anchor_at.min() and set(fit.game_pk).isdisjoint(cal.game_pk)
    return fit,cal,{'boundary':boundary,'fit_n':len(fit),'calibration_n':len(cal),'spanning_games_excluded':len(spanning)}


def normal_model(target):
    numeric=NUM+(['mean_stuff','mean_location','mean_velocity'] if target=='contact' else [])
    transform=ColumnTransformer([
        ('linear',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),numeric),
        ('curves',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),SplineTransformer(n_knots=4,degree=2)),CURVES)])
    return make_pipeline(transform,Ridge(alpha=100.,solver='lsqr'))


def equal_game_weights(frame):
    w=1/frame.groupby('game_pk').block_id.transform('count').to_numpy();return w/w.mean()


def predict_residual(frame,models):
    result=frame.copy()
    for target,bundle in models.items():
        valid=supported(result,target)
        expected=np.full(len(result),np.nan)
        if valid.any():
            pred=bundle['model'].predict(result.loc[valid]) if bundle['use_normal'] else np.full(int(valid.sum()),bundle['fallback'])
            if target=='contact':pred=np.clip(pred,.02,.98)
            expected[valid]=pred
        result['expected_'+target]=expected
        result['residual_'+target]=result['y_'+target]-expected
    return result


def smooth(frame,name,alpha):
    valid=frame[name].notna();segment=(~valid).groupby(frame.session_id,sort=False).cumsum()
    keys=[frame.loc[valid,'session_id'],segment[valid]]
    return frame.loc[valid,name].groupby(keys,sort=False).transform(lambda s:s.ewm(alpha=alpha,adjust=False).mean()).reindex(frame.index)


def future_labels(frame):
    result=frame.copy();g=result.groupby('session_id',sort=False)
    adjacent=g.block_number.shift(-1).eq(result.block_number+1)
    for group,targets in GROUPS.items():
        valid=np.ones(len(result),bool);bad=np.zeros(len(result),bool)
        for target in targets:
            f=g['residual_'+target].shift(-1);valid &=f.notna().to_numpy()
            bad |= (f.ge(MARGINS[target]) if group=='C' else f.le(-MARGINS[target])).to_numpy()
        result['future_'+group]=pd.Series(np.where(valid&adjacent,bad.astype(float),np.nan),index=result.index)
    result['future_at']=g.available_at.shift(-1).where(adjacent)
    return result


def score_continuous(frame,models,alpha):
    result=frame.copy()
    for target in TARGETS:result['smooth_'+target]=smooth(result,'residual_'+target,alpha)
    for group,targets in GROUPS.items():
        values=[];effect=[]
        for target in targets:
            sign=1. if group=='C' else -1.
            value=result['smooth_'+target]
            values.append(sign*value/models[target]['scale']);effect.append(sign*value/MARGINS[target])
        arr=np.column_stack(values);eff=np.column_stack(effect)
        known=np.isfinite(arr).all(axis=1)
        result[group+'_severity']=np.where(known,np.max(arr,axis=1),np.nan)
        result[group+'_effect']=np.where(known,np.max(eff,axis=1),np.nan)
    return result


def calibrator(frame,group):
    valid=frame[group+'_severity'].notna();scores=frame.loc[valid,group+'_severity'].to_numpy()
    assert len(scores)>100
    cuts=np.unique(np.quantile(scores,np.linspace(0,1,11)))
    observed=frame.loc[valid&frame['future_'+group].notna()]
    prior=float(observed['future_'+group].mean()) if len(observed) else None;bins=[]
    for low,high in zip(cuts[:-1],cuts[1:]):
        mask=observed[group+'_severity'].between(low,high,inclusive='left')
        y=observed.loc[mask,'future_'+group]
        if len(observed)>=50:bins.append({'low':float(low),'high':float(high),'risk':float((y.sum()+50*prior)/(len(y)+50)),'n':len(y)})
    return {'yellow':float(np.quantile(scores,.9)),'red':float(np.quantile(scores,.975)),'prior':prior,'bins':bins,'n':len(scores),'future_observed_n':len(observed)}


def color_and_risk(frame,group,calibration):
    score=frame[group+'_severity'];effect=frame[group+'_effect']
    frame[group+'_state']=np.where(score.isna(),-1,np.where(score.ge(calibration['red'])&effect.ge(1),2,
        np.where(score.ge(calibration['yellow'])&effect.ge(.5),1,0)))
    frame[group+'_risk']=np.nan
    if calibration['bins']:
        upper=np.array([row['high'] for row in calibration['bins']]);indices=np.searchsorted(upper,score.fillna(0).to_numpy(),side='right').clip(max=len(upper)-1)
        risks=np.array([row['risk'] for row in calibration['bins']]);frame[group+'_risk']=np.where(score.notna(),risks[indices],np.nan)
    return frame


def fit_normal(fold):
    assert read(OUT/'normal_protocol.json')==protocol()
    name,cutoff,year=next(x for x in FOLDS if x[0]==fold);end=pd.Timestamp(cutoff,tz='UTC').timestamp()
    development=pd.concat([pd.read_parquet(OUT/f'blocks_{y}.parquet') for y in range(2021,year+1)],ignore_index=True)
    development=development[development.available_at.lt(end)].sort_values(['session_id','block_number']).reset_index(drop=True)
    for role in ['SP','RP']:
        data=development[development.role.eq(role)].reset_index(drop=True);fit,cal,flow=split(data);models={};errors=[]
        write(pd.concat([f[['block_id','game_pk','anchor_at','available_at']].assign(partition=part) for part,f in [('fit',fit),('calibration',cal)]],ignore_index=True),f'normal_split_{fold}_{role}.parquet')
        with threadpool_limits(limits=2):
            for target in TARGETS:
                tf=fit[supported(fit,target)];vc=cal[supported(cal,target)]
                assert len(tf)>500 and len(vc)>100,(fold,role,target,len(tf),len(vc))
                print(f'14.2.2 normal{fold}/{role}/{target}: {len(tf):,} fit {len(vc):,} cal',flush=True)
                model=normal_model(target);model.fit(tf,tf['y_'+target],ridge__sample_weight=equal_game_weights(tf))
                prediction=model.predict(vc)
                if target=='contact':prediction=np.clip(prediction,.02,.98)
                mse=float(np.mean((vc['y_'+target]-prediction)**2));reference=float(np.mean(vc['y_'+target]**2)) if target!='contact' else float(np.mean((vc['y_'+target]-tf['y_'+target].mean())**2))
                fallback=float(tf['y_'+target].mean()) if target=='contact' else 0.
                use=bool(mse<reference)
                residual=vc['y_'+target]-(prediction if use else fallback)
                models[target]={'model':model,'use_normal':use,'scale':float(max(residual.std(),1e-6)),
                    'fit_n':len(tf),'cal_n':len(vc),'mse':mse,'personal_only_mse':reference,'fallback':fallback}
                errors.append({'target':target,'normal_mse':mse,'personal_only_mse':reference,'normal_selected_in_calibration':use})
            residual=future_labels(predict_residual(cal.reset_index(drop=True),models));calibrations={}
            for alpha in [ALPHA,1.]:
                scored=score_continuous(residual,models,alpha)
                scored.loc[scored.future_at.ge(end),['future_'+g for g in GROUPS]]=np.nan
                for group in GROUPS:calibrations[f'{alpha}:{group}']=calibrator(scored,group)
        bundle={'fold':fold,'role':role,'cutoff':end,'flow':flow,'models':models,'calibrations':calibrations,
            'fit_last_label':float(fit.available_at.max()),'cal_first_anchor':float(cal.anchor_at.min()),'cal_last_label':float(cal.available_at.max())}
        joblib.dump(bundle,OUT/f'normal_{fold}_{role}.joblib');save(f'normal_{fold}_{role}.json',{'fold':fold,'role':role,'flow':flow,'errors':errors,'calibrations':calibrations})


def score_year(year):
    assert read(OUT/'normal_protocol.json')==protocol()
    frame=pd.read_parquet(OUT/f'blocks_{year}.parquet');outputs=[];metrics=[]
    fold=next(x[0] for x in FOLDS if x[2]==year)
    for role in ['SP','RP']:
        bundle=joblib.load(OUT/f'normal_{fold}_{role}.joblib')
        f=frame[frame.role.eq(role)&frame.anchor_at.ge(bundle['cutoff'])].sort_values(['session_id','block_number']).reset_index(drop=True)
        with threadpool_limits(limits=2):residual=future_labels(predict_residual(f,bundle['models']))
        for alpha in [ALPHA,1.]:
            scored=score_continuous(residual,bundle['models'],alpha)
            for group in GROUPS:
                cal=bundle['calibrations'][f'{alpha}:{group}'];scored=color_and_risk(scored,group,cal)
                mask=scored['future_'+group].notna()&scored[group+'_risk'].notna()
                y=scored.loc[mask,'future_'+group];prob=scored.loc[mask,group+'_risk']
                metrics.append({'year':year,'role':role,'group':group,'alpha':alpha,'n':int(mask.sum()),
                    'brier':float(np.mean((y-prob)**2)) if len(y) else None,'constant_brier':float(np.mean((y-cal['prior'])**2)) if len(y) else None,
                    'observed_event_rate':float(y.mean()) if len(y) else None,'unobserved_or_insufficient':int((~mask).sum())})
            scored['alpha']=alpha;scored['normal_fold']=fold;outputs.append(scored)
    out=pd.concat(outputs,ignore_index=True);write(out,f'block_scores_{year}.parquet');save(f'block_scores_{year}.json',{'year':year,'metrics':metrics})
    print(f'14.2.2 {year}: forward-scored{len(out):,} block/alpha rows; missing future continuation is not a negative label',flush=True)


def protocol():
    paths=[Path(__file__),Path(r.__file__),u.h.OUT/'protocol.json',r.OUT/'protocol.json',r.OUT/'type_prior.parquet',r.OUT/'appearance_history.parquet',b.PREP/'ability_history.parquet']
    for year in range(2021,2025):paths +=[OUT/f'blocks_{year}.parquet',r.OUT/f'pitch_observations_{year}.parquet',u.h.OUT/f'identity_exclusions_{year}.parquet']
    return {'version':'decision_normal_process_v1','protocol_revision':2,'superseded_pre_fit_protocol_sha256':b.digest(OUT/'attempt0_protocol_serialization/normal_protocol.json'),'input_sha256':{str(path.relative_to(b.ROOT)):b.digest(path) for path in paths},
        'folds':[list(x) for x in FOLDS],'fixed_ewma_alpha':ALPHA,'comparator_alpha':1.,'normal_model':'fixed Ridge100, spline4 knots degree2, personal reference frozen before appearance entry; contact conditions on measured block quality and strictly past batter K history',
        'time':'fit chronological first80% available game-end dates; remaining dates calibrate, spanning games excluded; all fit/cal labels before fold cutoff;2021-late startsSep1; each subsequent year uses previous years only',
        'baseline':'same pitcher/role/pitch-type/measurement-model prior >=20 valid pitches, asof strictly before entry; no full-season player average; normal drift selected vs personal-only by internal calibration MSE',
        'unit':'10 completed measured pitches in a fixed nonoverlapping session block; remove identity-conflict PA; missing pitch breaks complete block; no use before final pitch availability',
        'maturity':'SP session>=35 and game<=100; RP session>=10 and game<=60; resets after source8h session break, cumulative game load retained',
        'support':'A both stuff/velocity n>=8 with personal references; B location n>=8; C contact on >=4 swings, descriptive opponent control, not familiarity causality',
        'colors':'training-calibration90th/97.5th severity percentiles with half/full practical margin; green means no observed tail exceedance; gray is unsupported, never normal',
        'practical_margins':MARGINS,'future_target':'next NONOVERLAPPING block deviation beyond practical margin relative to expected normal; observed continuers only; no future block => censored, not negative',
        'normal_and_noise':'normal expected drift is preserved for outcome prediction; smoothing uses past completed blocks only, invalid blocks reset filter, simple inning change does not erase cumulative load; overlap not used as new evidence',
        'limits':'no physiological fatigue ground truth, injury/warmup/health or causal replacement value; response-block pitch mix/quality controls used only for descriptive residual/target, never forecast future covariates',
        'evaluation':'2022/2023 forward diagnostics,2024 already-used confirmation,2025 outcomes sealed','recommendation_allowed':False}


def freeze():
    value=protocol();path=OUT/'normal_protocol.json'
    if path.exists():assert read(path)==value,'Preserve explicit normal-process revision'
    save('normal_protocol.json',value);print('14.2.2 normal/filter/color/clock protocol frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','fit_normal','score_year']);parser.add_argument('--year',type=int,choices=range(2021,2025));parser.add_argument('--fold',choices=[x[0] for x in FOLDS]);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='prepare':
        for year in [args.year] if args.year else range(2021,2025):prepare(year)
    elif args.stage=='fit_normal':fit_normal(args.fold)
    elif args.stage=='score_year':score_year(args.year)
    else:freeze()
