"""Repaired baseline and population-first decline research for Slices 13.1-13.4."""
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
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.metrics import brier_score_loss,log_loss,roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,SplineTransformer,StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_role_observations as r

b=r.b
OUT=r.OUT
SEED=20261118
CURVE_METRICS={'stuff':('higher',5.),'location_value':('higher',5.),'velocity':('higher',.5),
    'whiff_rate':('higher',.03),'k':('higher',.03),'bb':('lower',.02),'ev':('lower',2.)}
RISK_FOLDS=[('2021_late','2021-09-01','2021-09-01','2022-01-01'),
    ('2022','2022-01-01','2022-01-01','2023-01-01'),('2023','2023-01-01','2023-01-01','2024-01-01'),
    ('frozen_2024','2024-01-01','2024-01-01','2025-01-01')]
RISK_NUM=['pitches_before','bf_index','slot_encounter','same_batter_encounter','batter_k','batter_bb','batter_hr',
    'batter_log_n','day_of_year','inning','outs','base_state','defense_lead',
    'past10_stuff','past10_location','past10_velocity','mix_delta_research_stuff_plus','mix_delta_research_location_plus',
    'pitches_1d','pitches_3d','pitches_5d','rest_hours']
RISK_CAT=['pitcher_id','pitcher_hand','batter_side','half']


def prepare_baseline(year: int) -> None:
    with r.connect() as c:
        c.read_parquet(str(b.OUT/f'observed_features_{year}.parquet')).create_view('f')
        c.read_parquet(str(OUT/f'workload_features_{year}.parquet')).create_view('w')
        names=[row[0] for row in c.execute('DESCRIBE f').fetchall()]
        patched=['option_game_pitches','pitches_1d_before','pitches_3d_before','pitches_7d_before','pitches_14d_before',
            'rest_hours','previous_pitches','consecutive_days','appeared_earlier_today','lookback_14d_complete']
        extras=[row[0] for row in c.execute('DESCRIBE w').fetchall() if row[0] not in names]
        c.execute('CREATE TABLE observed_features AS SELECT f.* REPLACE('+','.join(f'w.{name} AS {name}' for name in patched)+')'+
            (','+','.join('w.'+name for name in extras) if extras else '')+' FROM f JOIN w USING(decision_id,option_pitcher_id)')
        count=c.execute('SELECT count(*),count(DISTINCT decision_id) FROM observed_features').fetchone()
        assert count[0]==count[1] and count[0]==c.execute('SELECT count(*) FROM f').fetchone()[0]
        r.publish(c,'observed_features',OUT/f'observed_features_{year}.parquet')
        audit=c.execute('''SELECT f.is_current,f.option_role,count(*) n,
            count(*) FILTER(WHERE f.consecutive_days IS DISTINCT FROM w.consecutive_days) streak_changed,
            count(*) FILTER(WHERE f.pitches_3d_before IS DISTINCT FROM w.pitches_3d_before) three_day_changed
            FROM f JOIN w USING(decision_id,option_pitcher_id) GROUP BY ALL''').fetchdf()
        r.save(f'baseline_adapter_{year}.json',{'year':year,'rows':count[0],'audit':json.loads(audit.to_json(orient='records')),
            'streak':'consecutive prior NY appearance-entry days at actual current entry or hypothetical candidate entry; decision-day pitch/entry streaks separate',
            'rest':'hours since a completed pitch in another game at decision; entry rest and live idle separate',
            'five_day':'prepared as a new field, not inserted into old baseline whitelist before Slice13.6 ablation'})
    print(f'{year}: repaired observed actor baseline adapter published',flush=True)


def attach_batter(c,frame: pd.DataFrame) -> pd.DataFrame:
    c.register('frame',frame)
    history=(b.PREP/'ability_history.parquet').as_posix();refs=(b.PREP/'ability_references.parquet').as_posix()
    c.execute(f"CREATE OR REPLACE VIEW bh AS SELECT player_id,split,available_at,pa_n,k_n,bb_n,hr_n FROM read_parquet('{history}') WHERE actor='batter'")
    c.execute(f"CREATE OR REPLACE VIEW br AS SELECT * FROM read_parquet('{refs}') WHERE actor='batter' AND role='BAT' AND split='All'")
    result=c.execute('''SELECT f.*,coalesce(s.k_n/nullif(s.pa_n,0),a.k_n/nullif(a.pa_n,0),z.k_n/nullif(z.pa_n,0)) batter_k,
        coalesce(s.bb_n/nullif(s.pa_n,0),a.bb_n/nullif(a.pa_n,0),z.bb_n/nullif(z.pa_n,0)) batter_bb,
        coalesce(s.hr_n/nullif(s.pa_n,0),a.hr_n/nullif(a.pa_n,0),z.hr_n/nullif(z.pa_n,0)) batter_hr,
        ln(1+coalesce(a.pa_n,0)) batter_log_n,coalesce(s.available_at,a.available_at,z.latest_label_at) batter_history_at
        FROM frame f ASOF LEFT JOIN bh s ON f.batter_id=s.player_id AND f.pitcher_hand=s.split AND f.anchor_at>s.available_at
        ASOF LEFT JOIN(SELECT * FROM bh WHERE split='All') a ON f.batter_id=a.player_id AND f.anchor_at>a.available_at
        LEFT JOIN br z ON z.fold_id=f.fold_id''').fetchdf()
    assert not (result.batter_history_at>=result.anchor_at).any()
    c.unregister('frame')
    return result


def future_windows(times: np.ndarray,values: np.ndarray,cutoffs: np.ndarray,size: int=10):
    starts=np.searchsorted(times,cutoffs,side='left');ends=starts+size
    valid=ends<=len(times);safe=np.minimum(ends,len(times))
    mean,n,_,_=r.interval_stats(values,starts,safe)
    mean[~valid]=np.nan;n[~valid]=0
    last=np.where(valid,times[np.maximum(safe-1,0)] if len(times) else np.nan,np.nan)
    return mean,n,last


def prepare_curve(year: int) -> None:
    with r.connect() as c:
        c.read_parquet(str(OUT/f'pa_observations_{year}.parquet')).create_view('p')
        c.read_parquet(str(OUT/f'pa_features_{year}.parquet')).create_view('f')
        c.read_parquet(str(OUT/f'pitch_observations_{year}.parquet')).create_view('o')
        c.read_parquet(str(r.BASE/f'roster_{year}.parquet')).create_view('roster')
        c.read_parquet(str(r.BASE/f'events_{year}.parquet')).create_view('events')
        c.execute("""CREATE TEMP TABLE mix AS SELECT game_pk,at_bat_number,arg_min(event_id,started_at) first_event_id,
            arg_min(session_id,started_at) session_id,arg_min(p_throws,started_at) pitcher_hand,arg_min(stand,started_at) batter_side,
            count(*) FILTER(WHERE pitch_type IN('FF','SI','FC'))*1.0/nullif(count(pitch_type),0) response_fastball_mix,
            count(*) FILTER(WHERE pitch_type IN('SL','ST','CU','KC','SV'))*1.0/nullif(count(pitch_type),0) response_breaking_mix,
            count(*) FILTER(WHERE pitch_type IN('CH','FS','FO'))*1.0/nullif(count(pitch_type),0) response_offspeed_mix
            FROM o GROUP BY ALL""")
        frame=c.execute('''SELECT p.year,p.game_pk,p.outcome_key,p.decision_id,p.final_appearance_id appearance_id,
            p.final_pitcher_id pitcher_id,p.actual_batter_id batter_id,p.final_role AS role,p.anchor_at,p.available_at label_available_at,
            p.plus_model_id,p.bf_before+1 bf_index,p.slot_encounter,p.same_batter_encounters_before+1 same_batter_encounter,
            p.pitches_seen_by_batter_before,p.pitches_before,p.inning,p.half,p.scheduled_innings,
            e.outs_before outs,e.base_state_before base_state,
            CASE WHEN p.half='top' THEN p.decision_home-p.decision_away ELSE p.decision_away-p.decision_home END defense_lead,
            p.pa_research_stuff_plus stuff,p.pa_research_location_plus location_value,p.pa_release_speed velocity,
            p.pa_whiff_sum/nullif(p.pa_swing_sum,0) whiff_rate,p.k,p.bb,p.pa_ev_sum/nullif(p.pa_ev_n,0) ev,
            p.physical_pitches,p.pa_research_stuff_plus_n stuff_response_n,p.pa_research_location_plus_n location_response_n,
            f.prefix_pitches,f.live_status,f.mix_delta_research_stuff_plus,f.mix_delta_research_location_plus,
            f.fold_id,f.completed_bf_before,f.observed_pair_encounters_before,m.* EXCLUDE(game_pk,at_bat_number,first_event_id)
            FROM p JOIN f ON f.request_id=p.outcome_key||':pa_anchor' JOIN mix m ON m.game_pk=p.game_pk AND m.at_bat_number=p.at_bat_number
            JOIN events e ON e.event_id=m.first_event_id
            WHERE p.process_eligible AND p.bf_before=f.completed_bf_before
                AND p.same_batter_encounters_before=f.observed_pair_encounters_before
                AND EXISTS(SELECT 1 FROM roster z WHERE z.game_pk=p.game_pk AND z.player_id=p.final_pitcher_id AND z.position_code='1')''').fetchdf()
        frame['day_of_year']=pd.to_datetime(frame.anchor_at,unit='s',utc=True).dt.dayofyear
        frame['bf_cycle_proxy']=((frame.bf_index-1)//9+1).astype(int)
        frame=attach_batter(c,frame)
        observations=c.execute('SELECT session_id,pitcher_id,year,game_pk,available_at,time_reliable,research_stuff_plus,research_location_plus,release_speed FROM o ORDER BY session_id,available_at,event_index').fetchdf()
        groups={sid:g for sid,g in observations.groupby('session_id',sort=False)}
        for metric in ['stuff','location','velocity']:
            frame[f'past10_{metric}']=np.nan;frame[f'future10_{metric}']=np.nan;frame[f'future10_{metric}_n']=0
        frame['future10_at']=np.nan
        for sid,indices in frame.groupby('session_id').groups.items():
            idx=np.asarray(indices);h=groups[sid];times=h.available_at.to_numpy();t=frame.loc[idx,'anchor_at'].to_numpy()
            end=np.searchsorted(times,t,side='left');start=np.maximum(end-10,0)
            for metric,column in [('stuff','research_stuff_plus'),('location','research_location_plus'),('velocity','release_speed')]:
                values=h[column].to_numpy(dtype=float)
                past,n,_,_=r.interval_stats(values,start,end);past[n<8]=np.nan
                future,fn,at=future_windows(times,values,t);future[fn<8]=np.nan
                frame.loc[idx,f'past10_{metric}']=past;frame.loc[idx,f'future10_{metric}']=future
                frame.loc[idx,f'future10_{metric}_n']=fn;frame.loc[idx,'future10_at']=at
        # Only historical workload enters risk predictors. No PA response-mix field does.
        physical=pd.read_parquet(OUT/'physical_history.parquet',columns=['pitcher_id','available_at','time_reliable'])
        histories={pid:g.sort_values('available_at') for pid,g in physical.groupby('pitcher_id',sort=False)}
        for window in [1,3,5]:frame[f'pitches_{window}d']=np.nan
        frame['rest_hours']=np.nan
        earliest=physical.available_at.min()
        for pid,indices in frame.groupby('pitcher_id').groups.items():
            idx=np.asarray(indices);h=histories[pid];times=h.available_at.to_numpy();t=frame.loc[idx,'anchor_at'].to_numpy()
            end=np.searchsorted(times,t,side='left');bad=np.r_[0,np.cumsum(~h.time_reliable.to_numpy(dtype=bool))]
            for window in [1,3,5]:
                start=np.searchsorted(times,t-window*86400,side='left')
                complete=(t>=earliest+window*86400)&((bad[end]-bad[start])==0)
                frame.loc[idx,f'pitches_{window}d']=np.where(complete,r.window_counts(times,t,window),np.nan)
            last_good=h.time_reliable.to_numpy(dtype=bool)[np.maximum(end-1,0)]
            frame.loc[idx,'rest_hours']=np.where((end>0)&last_good,(t-times[np.maximum(end-1,0)])/3600,np.nan)
    assert not (frame.label_available_at<=frame.anchor_at).any()
    frame.to_parquet(OUT/f'curve_cohort_{year}.parquet',index=False,compression='zstd')
    r.save(f'curve_cohort_{year}.json',{'year':year,'rows':len(frame),'roles':frame.role.value_counts().to_dict(),
        'slots':int(frame.slot_encounter.notna().sum()),'future10_observed':int(frame.future10_at.notna().sum()),
        'clock':'prior BF/pair encounter counts must match strict-time prefix; otherwise excluded',
        'response_mix':'response-only adjustment for descriptive curves; excluded from risk feature whitelist'})
    print(f'{year}: {len(frame):,} clock-consistent actual-actor curve/risk rows prepared',flush=True)


def protocol() -> dict:
    files=[Path(__file__),Path(r.__file__),Path(b.__file__),b.OUT/'protocol.json',b.PREP/'manifest.json',OUT/'plan_source_snapshot.json']
    for year in r.YEARS:
        files.extend(OUT/f'{name}_{year}.parquet' for name in ['observed_features','current_features','recent_profiles','recent_links'])
        if year<=2024:files.append(OUT/f'curve_cohort_{year}.parquet')
    value={'version':'decision_role_observation_v2','protocol_revision':3,
        'serialization_revision':'Tuple/list guard normalized before any model training; original pretraining guard retained in protocol_attempt1_tuple_guard.json',
        'superseded_protocol_sha256':b.digest(OUT/'attempt2_roster_filter_missing/protocol.json'),
        'initial_guard_protocol_sha256':b.digest(OUT/'protocol_attempt1_tuple_guard.json'),
        'cohort_revision':'Enforce game-listed position_code=1 in PA curve/risk cohort, matching original eligibility; 1302 non-pitcher PA in preliminary 2021-2024 cohort excluded; preliminary models/source/protocol preserved. No threshold or feature changes.',
        'input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in files},
        'slices':['13.1','13.2','13.3','13.4'],'not_started':['13.5','13.6','14.1','14.2','15'],
        'train':[2021,2022,2023],'validation':[2024],'locked_test':[2025],'score_only':[2026],
        'baseline':'same Slice12 feature lists, fixed alpha .001 and matchup pooling20; no 5-day/state feature selection before Slice13.6',
        'workload_contract':'regular-season observed pitches completed strictly before cutoff; consecutive_days counts prior NY appearance-entry dates at actual/hypothetical entry, while decision-day appearance/pitch streaks remain separate; 0-pitch entries count appearances, not pitches; incomplete windows stay missing',
        'lineup_contract':'archived slot of currently observed batter only; pitcher-slot encounters, exact batter encounters, actual pitch exposure and BF-cycle proxy are distinct; no future lineup reconstruction or psychological familiarity claim',
        'curve_metrics':CURVE_METRICS,'curve_model':'role-separated Ridge alpha100, train-only numeric imputer/scaler, 4-knot quadratic splines, regularized pitcher/batter/hand/year effects; response mix for descriptive adjustment only',
        'curve_axes':['BF groups of3','20-pitch bands','observed slot encounter','exact batter encounter'],
        'curve_uncertainty':'200 game x pitcher Poisson-cluster bootstrap replicates conditional on training nuisance fit; simultaneous bands within role/metric/axis; cross-family multiple comparisons remain exploratory',
        'curve_decline_gate':'two consecutive supported bins, >=200PA/50appearances/30pitchers, simultaneous95% excludes0, effect beyond declared practical threshold; no universal threshold forced',
        'individual_curve':'training-only residual curves, shrinkage n_appearances/(n_appearances+20); <10 appearances per bin withheld; no independently confirmed individual decline threshold',
        'future_risk':'next10 physical pitches within same session, >=8 measured; drop >=5 research-Plus points from previous10 mean; current prefix >=35SP/10RP; missing continuation censored not negative',
        'risk_folds':RISK_FOLDS,'risk_model':'L2 logistic C=.1; train-internal final20% games Platt calibration; equal total appearance weights; fixed future prediction whitelist',
        'risk_numeric':RISK_NUM,'risk_categorical':RISK_CAT,
        'risk_feature_clock':'PA-anchor predictors use completed history before the first actual pitch; rest_hours is live idle time, not entry rest; 2025/2026 score current actor only with no target labels',
        'limits':'observed continuation selection, no causal TTO/fatigue or replacement recommendation; descriptive normal recent-state intervals omit serial/model uncertainty',
        'recommendation_allowed':False,'individual_ranking_allowed':False,'formal_model_replaced':False}
    return json.loads(json.dumps(value))


def freeze() -> None:
    value=protocol();path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen revision differs; preserve experiment and create explicit revision')
    r.save('protocol.json',value);print('13.1-13.4 protocol frozen',flush=True)


def load_baseline(year: int,labels: bool) -> pd.DataFrame:
    with r.connect() as c:
        c.read_parquet(str(OUT/f'observed_features_{year}.parquet')).create_view('f')
        if not labels:return c.execute('SELECT * EXCLUDE(observed_action) FROM f').fetchdf()
        c.read_parquet(str(b.PREP/f'clean_labels_{year}.parquet')).create_view('l')
        frame=c.execute('''SELECT f.* EXCLUDE(observed_action),l.observed_pa_result,l.runs_to_pa_end,l.outs_after,
            CASE WHEN l.outs_after=3 THEN 0 ELSE l.base_state_after END post_base,l.pa_end_at
            FROM f JOIN l USING(decision_id) WHERE l.organic_pa_eligible''').fetchdf()
    return b.clean_model_frame(frame)[0]


def baselines() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    train=pd.concat([load_baseline(y,True) for y in [2021,2022,2023]],ignore_index=True)
    assert train.pa_end_at.max()<pd.Timestamp('2024-01-01',tz='UTC').timestamp()
    valid=load_baseline(2024,True);prior=np.bincount(train.target,minlength=9)/len(train)
    weights=1/train.groupby('game_pk').decision_id.transform('count').to_numpy();weights/=weights.mean()
    reports={}
    with threadpool_limits(limits=2):
        for level in ['workload','matchup']:
            print(f'Repaired {level} baseline: {len(train):,} train / {len(valid):,} validation',flush=True)
            model=b.make_model(level,.001);pooling=20 if level=='matchup' else 0
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always',ConvergenceWarning)
                model.fit(b.design(train,level,pooling,prior),train.target,sgdclassifier__sample_weight=weights)
            p=b.probabilities(model,b.design(valid,level,pooling,prior));metrics=b.metrics(valid.target.to_numpy(),p)
            old=pd.read_parquet(b.OUT/f'validation_2024_{level}.parquet').set_index('decision_id').loc[valid.decision_id]
            oldp=old[[f'p_{key}' for key in b.OUTCOMES]].to_numpy();y=valid.target.to_numpy()
            reports[level]={'validation':metrics,'convergence_warning':any(isinstance(w.message,ConvergenceWarning) for w in caught),
                'delta_vs_v1':b.cluster_difference(valid,-np.log(oldp[np.arange(len(y)),y]),-np.log(p[np.arange(len(y)),y]))}
            joblib.dump({'model':model,'prior':prior,'pooling':pooling,'level':level},OUT/f'baseline_{level}.joblib')
            out=valid[['decision_id','game_pk']].copy()
            for j,key in enumerate(b.OUTCOMES):out[f'p_{key}']=p[:,j]
            out.to_parquet(OUT/f'baseline_validation_2024_{level}.parquet',index=False,compression='zstd')
            print(f"Repaired {level}: LL={metrics['log_loss']:.6f}, Brier={metrics['brier']:.6f}",flush=True)
        for year in [2025,2026]:
            f=load_baseline(year,False);out=f[['decision_id','game_pk']].copy()
            for level in ['workload','matchup']:
                fit=joblib.load(OUT/f'baseline_{level}.joblib');p=b.probabilities(fit['model'],b.design(f,level,fit['pooling'],fit['prior']))
                for j,key in enumerate(b.OUTCOMES):out[f'{level}_p_{key}']=p[:,j]
            out.to_parquet(OUT/f'baseline_predictions_{year}.parquet',index=False,compression='zstd')
    r.save('baseline_validation.json',{'training_n':len(train),'validation_n':len(valid),'models':reports,'test_outcome_metrics_examined':False,'promotion':'research_only'})


CURVE_CONTROL_NUM=['batter_k','batter_bb','batter_hr','batter_log_n','day_of_year','inning','outs','base_state','defense_lead',
    'response_fastball_mix','response_breaking_mix','response_offspeed_mix']
CURVE_CONTROL_CAT=['pitcher_id','batter_id','pitcher_hand','batter_side','year','half','plus_model_id']


def clean_design(frame: pd.DataFrame,numeric: list[str],categorical: list[str]) -> pd.DataFrame:
    x=frame[numeric+categorical].copy()
    for name in numeric:x[name]=pd.to_numeric(x[name],errors='coerce').replace([np.inf,-np.inf],np.nan)
    for name in categorical:x[name]=x[name].astype('string').fillna('unknown').astype(str)
    return x


def curve_model(control: str):
    transform=ColumnTransformer([
        ('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),CURVE_CONTROL_NUM),
        ('exposure',make_pipeline(SimpleImputer(strategy='median'),SplineTransformer(n_knots=4,degree=2,include_bias=False)),[control]),
        ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=True),CURVE_CONTROL_CAT)],sparse_threshold=1.)
    return make_pipeline(transform,Ridge(alpha=100.,solver='lsqr',max_iter=200,tol=1e-4))


def axis_values(frame: pd.DataFrame,axis: str) -> np.ndarray:
    if axis=='bf':return np.minimum(((frame.bf_index.to_numpy()-1)//3)*3+1,37)
    if axis=='pitch_count':return np.minimum((frame.pitches_before.to_numpy()//20)*20,120)
    name='slot_encounter' if axis=='slot_encounter' else 'same_batter_encounter'
    return np.minimum(frame[name].to_numpy(dtype=float),4)


def cluster_curve(frame: pd.DataFrame,residual: np.ndarray,target: np.ndarray,axis: str) -> list[dict]:
    bins=axis_values(frame,axis);keep=np.isfinite(bins)&np.isfinite(residual)&np.isfinite(target)
    f=frame.loc[keep,['appearance_id','game_pk','pitcher_id']].copy();f['bin']=bins[keep]
    f['residual']=residual[keep];f['raw']=target[keep]
    f['w']=1/f.groupby(['appearance_id','bin']).appearance_id.transform('count')
    levels=np.sort(f.bin.unique());code=np.searchsorted(levels,f.bin.to_numpy())
    games,_=pd.factorize(f.game_pk,sort=True);pitchers,_=pd.factorize(f.pitcher_id,sort=True)
    w=f.w.to_numpy();value=f.residual.to_numpy();raw=f.raw.to_numpy()
    denom=np.bincount(code,weights=w,minlength=len(levels))
    point=np.bincount(code,weights=w*value,minlength=len(levels))/denom
    raw_point=np.bincount(code,weights=w*raw,minlength=len(levels))/denom
    summary=f.groupby('bin').agg(n=('bin','size'),appearances=('appearance_id','nunique'),pitchers=('pitcher_id','nunique'))
    supported=(summary.n.ge(200)&summary.appearances.ge(50)&summary.pitchers.ge(30)).to_numpy()
    rng=np.random.default_rng(SEED);bootstrap=[]
    for _ in range(200):
        weight=w*rng.poisson(1,games.max()+1)[games]*rng.poisson(1,pitchers.max()+1)[pitchers]
        d=np.bincount(code,weights=weight,minlength=len(levels));s=np.bincount(code,weights=weight*value,minlength=len(levels))
        bootstrap.append(np.divide(s,d,out=np.full(len(levels),np.nan),where=d>0))
    bootstrap=np.asarray(bootstrap);delta=point-point[0];boot_delta=bootstrap-bootstrap[:,[0]]
    se=np.nanstd(boot_delta,axis=0,ddof=1);eligible=supported&(se>1e-12)
    if eligible.any():
        z=np.abs((boot_delta[:,eligible]-delta[eligible])/se[eligible]);critical=float(np.nanquantile(np.nanmax(z,axis=1),.95))
    else:critical=1.96
    rows=[]
    for i,level in enumerate(levels):
        rows.append({'axis':axis,'bin':int(level),'n':int(summary.loc[level,'n']),'appearances':int(summary.loc[level,'appearances']),
            'pitchers':int(summary.loc[level,'pitchers']),'raw_mean':float(raw_point[i]),'adjusted_residual_mean':float(point[i]),
            'delta_vs_first_bin':float(delta[i]),'simultaneous95_low':float(delta[i]-critical*se[i]) if np.isfinite(se[i]) else None,
            'simultaneous95_high':float(delta[i]+critical*se[i]) if np.isfinite(se[i]) else None,'supported':bool(supported[i]),
            'bootstrap_replicates':200,'band_scope':'within this role/metric/axis; nuisance fit fixed'})
    return rows


def sustained_pair(rows: list[dict],metric: str) -> list[int] | None:
    direction,threshold=CURVE_METRICS[metric];passing=[]
    for row in rows:
        bound=row['simultaneous95_high'] if direction=='higher' else row['simultaneous95_low']
        effect=row['delta_vs_first_bin']
        passing.append(row['supported'] and bound is not None and (bound<0 and effect<=-threshold if direction=='higher' else bound>0 and effect>=threshold))
    for i in range(1,len(rows)-1):
        step={'bf':3,'pitch_count':20}.get(rows[i].get('axis'),1)
        if passing[i] and passing[i+1] and rows[i+1]['bin']-rows[i]['bin']==step:return [rows[i]['bin'],rows[i+1]['bin']]
    return None


def curves() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    train=pd.concat([pd.read_parquet(OUT/f'curve_cohort_{y}.parquet') for y in [2021,2022,2023]],ignore_index=True)
    train=train[train.label_available_at<pd.Timestamp('2024-01-01',tz='UTC').timestamp()].reset_index(drop=True)
    valid=pd.read_parquet(OUT/'curve_cohort_2024.parquet')
    panels=[];individuals=[];predictive=[]
    with threadpool_limits(limits=2):
        for role in ['SP','RP']:
            for metric in CURVE_METRICS:
                t=train[train.role.eq(role)&train[metric].notna()].reset_index(drop=True)
                v=valid[valid.role.eq(role)&valid[metric].notna()].reset_index(drop=True)
                if len(t)<500 or len(v)<200:continue
                print(f'{role}/{metric}: conditional curves train={len(t):,}, validation={len(v):,}',flush=True)
                weights=1/t.groupby('appearance_id').outcome_key.transform('count').to_numpy();weights/=weights.mean()
                for control,axes in [('pitches_before',['bf','slot_encounter','batter_encounter']),('bf_index',['pitch_count'])]:
                    numeric=CURVE_CONTROL_NUM+[control];fit=curve_model(control)
                    xt=clean_design(t,numeric,CURVE_CONTROL_CAT);xv=clean_design(v,numeric,CURVE_CONTROL_CAT)
                    fit.fit(xt,t[metric],ridge__sample_weight=weights)
                    pred_t=fit.predict(xt);pred_v=fit.predict(xv);rt=t[metric].to_numpy()-pred_t;rv=v[metric].to_numpy()-pred_v
                    joblib.dump(fit,OUT/f'curve_{role}_{metric}_{control}.joblib')
                    for axis in axes:
                        training=cluster_curve(t,rt,t[metric].to_numpy(),axis)
                        validation=cluster_curve(v,rv,v[metric].to_numpy(),axis)
                        proposed=sustained_pair(training,metric);observed=sustained_pair(validation,metric)
                        # Confirm the exact training-selected pair, not a newly chosen validation cutpoint.
                        if proposed is not None:
                            chosen=[row for row in validation if row['bin'] in proposed]
                            replicated=len(chosen)==2 and sustained_pair([training[0]]+chosen,metric) is not None
                        else:replicated=False
                        panels.append({'role':role,'metric':metric,'axis':axis,'training':training,'validation_2024':validation,
                            'training_proposed_pair':proposed,'validation_exploratory_pair':observed,'training_pair_replicated':bool(replicated)})
                        if axis=='bf':
                            tf=t[['pitcher_id','appearance_id']].copy();tf['bin']=axis_values(t,'bf');tf['residual']=rt
                            groups=tf.groupby(['pitcher_id','bin']).agg(n=('residual','size'),appearances=('appearance_id','nunique'),mean=('residual','mean')).reset_index()
                            role_map={row['bin']:row['adjusted_residual_mean'] for row in training}
                            groups['role_mean']=groups['bin'].map(role_map);groups['shrinkage']=groups.appearances/(groups.appearances+20)
                            groups['pooled_residual']=groups.shrinkage*groups['mean']+(1-groups.shrinkage)*groups.role_mean
                            groups['supported']=groups.appearances.ge(10)&groups.n.ge(30)
                            groups['role']=role;groups['metric']=metric;groups['valid_from']='2024-01-01';individuals.append(groups)
                            lookup=groups.set_index(['pitcher_id','bin'])
                            estimates=[];roles=[]
                            for row in v.itertuples():
                                bin_=int(min(((row.bf_index-1)//3)*3+1,37));key=(row.pitcher_id,bin_)
                                base=role_map.get(bin_,0.);roles.append(base)
                                estimates.append(float(lookup.loc[key,'pooled_residual']) if key in lookup.index and lookup.loc[key,'supported'] else base)
                            predictive.append({'role':role,'metric':metric,'n':len(v),'supported_individual_bins':int(groups.supported.sum()),
                                'role_curve_rmse':float(np.sqrt(np.mean((v[metric].to_numpy()-pred_v-np.asarray(roles))**2))),
                                'partial_pool_curve_rmse':float(np.sqrt(np.mean((v[metric].to_numpy()-pred_v-np.asarray(estimates))**2)))})
    pd.concat(individuals,ignore_index=True).to_parquet(OUT/'individual_curves_asof_2024.parquet',index=False,compression='zstd')
    r.save('decline_curves.json',{'version':'decision_role_observation_v2','panels':panels,'individual_validation':predictive,
        'replicated_panels':[{'role':p['role'],'metric':p['metric'],'axis':p['axis'],'pair':p['training_proposed_pair']} for p in panels if p['training_pair_replicated']],
        'interpretation':'Exploratory conditional association among observed retained pitchers, not causal fatigue/familiarity or a substitution threshold. Bands do not adjust across metric/axis families.',
        'test_outcome_metrics_examined':False,'individual_threshold_validated':False})
    print('Population and supported partial-pooling individual curves saved',flush=True)


def risk_eligible(frame: pd.DataFrame,metric: str) -> pd.Series:
    minimum=np.where(frame.role.eq('SP'),35,10)
    return frame.prefix_pitches.ge(minimum)&frame[f'past10_{metric}'].notna()&frame[f'future10_{metric}'].notna()&frame.live_status.eq('observed_current_prefix')


def risk_model(count_only: bool=False):
    numeric=['pitches_before','bf_index'] if count_only else RISK_NUM
    categorical=[] if count_only else RISK_CAT
    components=[('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),numeric)]
    if categorical:components.append(('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=True),categorical))
    return make_pipeline(ColumnTransformer(components,sparse_threshold=1.),LogisticRegression(C=.1,max_iter=300,solver='liblinear',random_state=SEED))


def risk_probability(fit: dict,frame: pd.DataFrame) -> np.ndarray:
    x=clean_design(frame,fit['numeric'],fit['categorical']);score=fit['model'].decision_function(x)
    return fit['calibration'].predict_proba(score.reshape(-1,1))[:,1]


def risk_metrics(y: np.ndarray,p: np.ndarray) -> dict:
    bins=[]
    for low in np.arange(0,1,.1):
        mask=(p>=low)&(p<low+.1 if low<.9 else p<=1)
        if mask.any():bins.append({'lower':round(float(low),1),'n':int(mask.sum()),'probability':float(p[mask].mean()),'event_rate':float(y[mask].mean())})
    return {'n':len(y),'events':int(y.sum()),'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,p,labels=[0,1])),
        'auc':float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,'calibration':bins}


def risks() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    frame=pd.concat([pd.read_parquet(OUT/f'curve_cohort_{y}.parquet') for y in range(2021,2025)],ignore_index=True)
    reports=[];prediction_frames=[]
    with threadpool_limits(limits=2):
        for fold,cutoff,start,end in RISK_FOLDS:
            stop=pd.Timestamp(cutoff,tz='UTC').timestamp();score_start=pd.Timestamp(start,tz='UTC').timestamp();score_end=pd.Timestamp(end,tz='UTC').timestamp()
            for role in ['SP','RP']:
                for metric in ['stuff','location']:
                    available=risk_eligible(frame,metric)&frame.role.eq(role)
                    train=frame[available&frame.future10_at.lt(stop)].copy()
                    valid=frame[available&frame.anchor_at.ge(score_start)&frame.anchor_at.lt(score_end)].copy()
                    eligible_all=frame[frame.role.eq(role)&frame.anchor_at.ge(score_start)&frame.anchor_at.lt(score_end)&frame.prefix_pitches.ge(35 if role=='SP' else 10)]
                    flow={'fold':fold,'role':role,'metric':metric,'eligible_prefixes':len(eligible_all),'observed_future10':len(valid),
                        'unobserved_or_measurement_insufficient':len(eligible_all)-len(valid)}
                    if len(train)<1000 or len(valid)<100:
                        reports.append({**flow,'status':'warmup_or_insufficient'});continue
                    train['target']=(train[f'future10_{metric}']<=train[f'past10_{metric}']-5).astype(int)
                    valid['target']=(valid[f'future10_{metric}']<=valid[f'past10_{metric}']-5).astype(int)
                    games=train.groupby('game_pk').future10_at.max().sort_values().index
                    fit_games=set(games[:int(.8*len(games))]);fit_frame=train[train.game_pk.isin(fit_games)];cal=train[~train.game_pk.isin(fit_games)]
                    if fit_frame.target.nunique()<2 or cal.target.nunique()<2:
                        reports.append({**flow,'status':'insufficient_event_classes'});continue
                    models={};out=valid[['decision_id','outcome_key','game_pk','pitcher_id','role','anchor_at','future10_at','target']].copy()
                    print(f'{fold}/{role}/{metric}: next10 risk train={len(train):,}, observed validation={len(valid):,}',flush=True)
                    for name,count_only in [('count_only',True),('state_workload',False)]:
                        numeric=['pitches_before','bf_index'] if count_only else RISK_NUM;categorical=[] if count_only else RISK_CAT
                        model=risk_model(count_only);weights=1/fit_frame.groupby('appearance_id').outcome_key.transform('count').to_numpy();weights/=weights.mean()
                        model.fit(clean_design(fit_frame,numeric,categorical),fit_frame.target,logisticregression__sample_weight=weights)
                        raw=model.decision_function(clean_design(cal,numeric,categorical))
                        cal_weights=1/cal.groupby('appearance_id').outcome_key.transform('count').to_numpy();cal_weights/=cal_weights.mean()
                        calibration=LogisticRegression(C=1e6,solver='lbfgs',max_iter=300).fit(raw.reshape(-1,1),cal.target,sample_weight=cal_weights)
                        bundle={'model':model,'calibration':calibration,'numeric':numeric,'categorical':categorical,'role':role,'metric':metric,
                            'train_cutoff':cutoff,'training_n':len(fit_frame),'calibration_n':len(cal),'scope':'conditional on observed continuation; not injury or causal swap risk'}
                        bundle['support']={key:[float(train[key].min()),float(train[key].max())] for key in ['pitches_before','bf_index']}
                        p=risk_probability(bundle,valid);models[name]=risk_metrics(valid.target.to_numpy(),p)
                        models[name]['convergence_warning']=bool(model[-1].n_iter_.max()>=300 or calibration.n_iter_.max()>=300)
                        out[name+'_p']=p
                        joblib.dump(bundle,OUT/f'risk_{fold}_{role}_{metric}_{name}.joblib')
                    prior=float(fit_frame.target.mean());models['training_prevalence']=risk_metrics(valid.target.to_numpy(),np.full(len(valid),prior))
                    out['fold']=fold;out['metric']=metric;prediction_frames.append(out)
                    reports.append({**flow,'status':'observed_conditional_validation','models':models})
    pd.concat(prediction_frames,ignore_index=True).to_parquet(OUT/'risk_forward_predictions_2021_2024.parquet',index=False,compression='zstd')
    r.save('risk_validation.json',{'version':'decision_role_observation_v2','reports':reports,
        'label':'next10 measured mean at least5 research-Plus points below previous10, >=8 valid pitches each',
        'unobserved_continuation':'censored, not counted negative; results do not resolve manager selection or substitution benefit',
        'test_outcome_metrics_examined':False,'recommendation_allowed':False})
    print('Forward-only next10 conditional-risk models and censoring report saved',flush=True)


def risk_score() -> None:
    with threadpool_limits(limits=2):
        for year in [2025,2026]:
            with r.connect() as c:
                c.read_parquet(str(OUT/f'current_features_{year}.parquet')).create_view('q')
                c.read_parquet(str(OUT/f'workload_features_{year}.parquet')).create_view('w')
                c.read_parquet(str(b.PREP/f'prepared_features_{year}.parquet')).create_view('f')
                c.read_parquet(str(OUT/'lineup_slots.parquet')).create_view('slots')
                c.read_parquet(str(OUT/f'pa_observations_{year}.parquet')).create_view('pa')
                c.read_parquet(str(OUT/f'pitch_observations_{year}.parquet')).create_view('o')
                c.execute("""CREATE TEMP TABLE support AS SELECT appearance_id,available_at,
                    count(research_stuff_plus) OVER win stuff_n,count(research_location_plus) OVER win location_n
                    FROM o WHERE time_reliable WINDOW win AS(PARTITION BY session_id ORDER BY available_at,event_index ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)""")
                c.execute("""CREATE TEMP TABLE slot_history AS SELECT game_pk,final_pitcher_id,batting_slot,available_at,
                    count(*) OVER(PARTITION BY game_pk,final_pitcher_id,batting_slot ORDER BY available_at,at_bat_number ROWS UNBOUNDED PRECEDING) prior_count
                    FROM pa WHERE is_complete AND is_batter_faced AND batting_slot IS NOT NULL AND available_at IS NOT NULL""")
                frame=c.execute('''SELECT q.request_id,q.decision_id,q.game_pk,q.pitcher_id,q.role,q.cutoff anchor_at,
                    q.prefix_pitches,q.live_status,w.option_game_pitches pitches_before,q.completed_bf_before+1 bf_index,
                    CASE WHEN z.batting_slot IS NOT NULL THEN coalesce(h.prior_count,0)+1 END slot_encounter,
                    q.observed_pair_encounters_before+1 same_batter_encounter,
                    f.batter_k_rate batter_k,f.batter_bb_rate batter_bb,f.batter_hr_rate batter_hr,
                    ln(1+f.batter_own_all_n) batter_log_n,f.inning,f.outs,f.base_state,f.defense_lead,f.half,
                    f.pitcher_hand,f.expected_stand batter_side,
                    q.last10_research_stuff_plus past10_stuff,q.last10_research_location_plus past10_location,
                    q.last10_release_speed past10_velocity,q.mix_delta_research_stuff_plus,q.mix_delta_research_location_plus,
                    w.pitches_1d_before pitches_1d,w.pitches_3d_before pitches_3d,w.pitches_5d_before pitches_5d,
                    w.live_idle_hours rest_hours,s.stuff_n,s.location_n
                    FROM q JOIN f USING(decision_id) JOIN w ON w.decision_id=q.decision_id AND w.option_pitcher_id=q.pitcher_id AND w.is_current
                    LEFT JOIN slots z ON z.game_pk=q.game_pk AND z.batter_id=q.batter_id
                    ASOF LEFT JOIN support s ON q.appearance_id=s.appearance_id AND q.cutoff>s.available_at
                    ASOF LEFT JOIN slot_history h ON q.game_pk=h.game_pk AND q.pitcher_id=h.final_pitcher_id AND z.batting_slot=h.batting_slot AND q.cutoff>h.available_at''').fetchdf()
            frame['day_of_year']=pd.to_datetime(frame.anchor_at,unit='s',utc=True).dt.dayofyear
            out=frame[['decision_id','game_pk','pitcher_id','role','anchor_at']].copy()
            for role in ['SP','RP']:
                for metric in ['stuff','location']:
                    fit=joblib.load(OUT/f'risk_frozen_2024_{role}_{metric}_state_workload.joblib')
                    mask=frame.role.eq(role)&frame.prefix_pitches.ge(35 if role=='SP' else 10)&frame.live_status.eq('observed_current_prefix')
                    mask &= frame[metric+'_n'].ge(8)&frame[f'past10_{metric}'].notna()
                    for key,(low,high) in fit['support'].items():mask &=frame[key].between(low,high)
                    out.loc[mask,f'{metric}_drop_p']=risk_probability(fit,frame.loc[mask])
            out.to_parquet(OUT/f'risk_scores_{year}.parquet',index=False,compression='zstd')
            r.save(f'risk_score_{year}.json',{'year':year,'rows':len(out),'stuff':int(out.stuff_drop_p.notna().sum()),
                'location':int(out.location_drop_p.notna().sum()),'target_outcome_metrics_examined':False,'scope':'current-actor conditional continuation forecast only, not replacement advice'})
            print(f'{year}: frozen conditional-risk probabilities only, no outcome metrics',flush=True)


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['adapter','cohort','freeze','baselines','curves','risks','risk_score']);parser.add_argument('--year',type=int,choices=r.YEARS)
    args=parser.parse_args()
    if args.stage in ['adapter','cohort']:
        for year in [args.year] if args.year else (r.YEARS if args.stage=='adapter' else range(2021,2025)):
            (prepare_baseline if args.stage=='adapter' else prepare_curve)(year)
    else:globals()[args.stage]()


if __name__=='__main__':main()
