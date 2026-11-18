"""Slices 8/9. Prefix-only separate Quality / mechanics / location-retention states."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.decision_temporal_common import BASE,OUT,ROOT,VERSION,save,protocol
from scripts.train_decision_temporal_plus import epoch

MEASURES=['research_stuff_plus','research_location_plus','release_speed','release_spin_rate','pfx_x','pfx_z',
          'release_pos_x','release_pos_z','release_extension','arm_angle']
STATE_FOLDS=[('2021_state','2021-09-01','2021-09-01','2022-01-01'),('2022_state','2022-01-01','2022-01-01','2023-01-01'),
             ('2023_state','2023-01-01','2023-01-01','2024-01-01'),('frozen_state_2024','2024-01-01','2024-01-01','2027-01-01')]
WORKLOAD=['pitches_1d_before','pitches_3d_before','pitches_7d_before','pitches_14d_before','rest_hours_since_closed_session',
          'prior_session_consecutive_days','appeared_earlier_today','prior_observed_starts','prior_observed_relief',
          'previous_session_pitches','days_since_start','days_since_long','latest_boundary_li']
XCOLS=['prefix_pitches','log_pitch_count','early_quality','early_command','early_velocity','days_observed_history','prior_same_type_pitches',*WORKLOAD]

def raw_prefix(year:int)->None:
    c=duckdb.connect(config={'threads':2,'memory_limit':'2GB'})
    c.execute(f"SET temp_directory='{(OUT/'prefix_tmp').as_posix()}'")
    c.execute(f"CREATE TABLE s AS SELECT * FROM read_parquet('{(OUT/f'scored_{year}_*.parquet').as_posix()}')")
    # A resumption requires a fresh observed baseline; elapsed time is known at each delivery.
    c.execute("""CREATE TABLE x AS WITH lagged AS(SELECT *,lag(observed_at) OVER(PARTITION BY appearance_id ORDER BY event_at,event_index) prior_at FROM s),
     blocks AS(SELECT *,sum(CASE WHEN prior_at IS NULL OR observed_at-prior_at>28800 THEN 1 ELSE 0 END)
       OVER(PARTITION BY appearance_id ORDER BY event_at,event_index) block FROM lagged)
     SELECT *,appearance_id||':'||block session_id,row_number() OVER(PARTITION BY appearance_id,block ORDER BY event_at,event_index) pos,
       CASE WHEN role='SP' THEN 20 ELSE 5 END early_n,
       CASE WHEN role='SP' THEN 15 ELSE 5 END late_min,
       CASE WHEN role='SP' THEN 3 ELSE 2 END exact_min
     FROM blocks""")
    early=', '.join(f'avg({m}) e_{m},count({m}) en_{m}' for m in MEASURES)
    late=', '.join(f'avg({m}) OVER w l_{m},count({m}) OVER w ln_{m}' for m in MEASURES)
    c.execute(f"CREATE TABLE early AS SELECT session_id,pitch_type,count(*) en,{early} FROM x WHERE pos<=early_n AND source_valid AND roster_pitcher AND alignment_status='validated_order' GROUP BY ALL")
    c.execute(f"""CREATE TABLE late AS SELECT session_id,pitch_type,pos,count(*) OVER w ln,{late}
       FROM x WHERE pos>early_n AND alignment_status='validated_order' AND source_valid
       WINDOW w AS(PARTITION BY session_id,pitch_type ORDER BY pos ROWS UNBOUNDED PRECEDING)""")
    c.execute("""CREATE TABLE joined AS SELECT p.*,e.* EXCLUDE(session_id,pitch_type),l.* EXCLUDE(session_id,pitch_type,pos),
       e.en*1.0/p.early_n mix_weight
       FROM x p JOIN early e ON p.session_id=e.session_id
       ASOF LEFT JOIN late l ON p.session_id=l.session_id AND e.pitch_type=l.pitch_type AND p.pos>=l.pos
       WHERE p.source_valid AND p.roster_pitcher AND p.pos>=p.early_n+p.late_min AND p.pos<=CASE WHEN p.role='SP' THEN 100 ELSE 60 END""")
    aggregations=[]
    for m in MEASURES:
        gate=f'en>=exact_min AND ln>=2 AND en_{m}>=exact_min AND ln_{m}>=2'
        aggregations.extend([f'sum(CASE WHEN {gate} THEN mix_weight ELSE 0 END) coverage_{m}',
          f'sum(CASE WHEN {gate} THEN mix_weight*(l_{m}-e_{m}) END)/nullif(sum(CASE WHEN {gate} THEN mix_weight ELSE 0 END),0) delta_{m}',
          f'sum(CASE WHEN {gate} THEN mix_weight*e_{m} END)/nullif(sum(CASE WHEN {gate} THEN mix_weight ELSE 0 END),0) early_{m}'])
    c.execute(f"""CREATE TABLE prefixes AS SELECT year,game_pk,event_id,appearance_id,session_id,pitcher_id,role,
      observed_at,entry_at,closed_at,game_completed_at,plus_model_id,pos prefix_pitches,early_n,
      {','.join(aggregations)} FROM joined GROUP BY ALL""")
    c.execute(f"COPY prefixes TO '{(OUT/f'prefix_raw_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    print(f'{year}: raw prefix states {c.execute("SELECT count(*) FROM prefixes").fetchone()[0]:,}',flush=True);c.close()

def model_features(frame:pd.DataFrame)->pd.DataFrame:
    result=pd.DataFrame({'prefix_pitches':frame.prefix_pitches,'log_pitch_count':np.log1p(frame.prefix_pitches),
       'early_quality':frame.early_research_stuff_plus,'early_command':frame.early_research_location_plus,
       'early_velocity':frame.early_release_speed,'days_observed_history':frame.days_observed_history,
       'prior_same_type_pitches':frame.prior_same_type_pitches})
    for col in WORKLOAD:result[col]=pd.to_numeric(frame[col],errors='coerce')
    return result

def fit_states()->None:
    c=duckdb.connect(config={'threads':2,'memory_limit':'2GB'})
    c.execute(f"CREATE VIEW raw AS SELECT * FROM read_parquet('{(OUT/'prefix_raw_*.parquet').as_posix()}')")
    c.execute(f"CREATE VIEW scored AS SELECT * FROM read_parquet('{(OUT/'scored_*.parquet').as_posix()}')")
    # Closed, strictly prior same-pitch history is explanatory support, never future own pitches.
    c.execute("""CREATE TABLE own AS WITH ap AS(SELECT pitcher_id,pitch_type,plus_model_id,appearance_id,greatest(max(closed_at),max(observed_at)) closed_at,
      count(*) n,min(observed_at) first_at FROM scored WHERE research_stuff_plus IS NOT NULL GROUP BY ALL)
      SELECT *,sum(n) OVER w total_n,min(first_at) OVER w first_observed
      FROM ap WINDOW w AS(PARTITION BY pitcher_id,pitch_type,plus_model_id ORDER BY closed_at,appearance_id ROWS UNBOUNDED PRECEDING)""")
    c.execute("""CREATE TABLE support AS WITH entries AS(SELECT DISTINCT pitcher_id,appearance_id,plus_model_id,entry_at FROM raw),
       types AS(SELECT DISTINCT pitcher_id,appearance_id,plus_model_id,pitch_type FROM scored),
       want AS(SELECT e.*,t.pitch_type FROM entries e JOIN types t USING(pitcher_id,appearance_id,plus_model_id)),
       j AS(SELECT w.*,h.total_n,h.first_observed,h.closed_at reference_at FROM want w ASOF LEFT JOIN own h
        ON w.pitcher_id=h.pitcher_id AND w.pitch_type=h.pitch_type AND w.plus_model_id=h.plus_model_id AND w.entry_at>h.closed_at)
       SELECT appearance_id,sum(total_n) prior_same_type_pitches,(max(entry_at)-min(first_observed))/86400 days_observed_history,
         max(reference_at) history_available_at FROM j GROUP BY appearance_id""")
    assert c.execute('SELECT count(*) FROM support JOIN (SELECT DISTINCT appearance_id,entry_at FROM raw) USING(appearance_id) WHERE history_available_at>=entry_at').fetchone()[0]==0
    c.execute(f"CREATE VIEW workload AS SELECT * FROM read_parquet('{(BASE/'workload_20*.parquet').as_posix()}')")
    c.execute(f"CREATE VIEW context AS SELECT * FROM read_parquet('{(OUT/'context_features_20*.parquet').as_posix()}')")
    c.execute("""CREATE TABLE w AS SELECT workload.*,epoch(decision_time) workload_at,
       (epoch(decision_time)-epoch(last_observed_start))/86400 days_since_start,
       (epoch(decision_time)-epoch(last_observed_long_session))/86400 days_since_long,
       context.research_pa_li latest_boundary_li
       FROM workload LEFT JOIN context USING(decision_id) WHERE workload.source_clock_valid""")
    c.execute(f"""CREATE TABLE r AS SELECT raw.*,support.* EXCLUDE(appearance_id),w.workload_at,
      {','.join('w.'+col for col in WORKLOAD)}
      FROM raw LEFT JOIN support USING(appearance_id)
      ASOF LEFT JOIN w ON raw.appearance_id=w.appearance_id AND raw.pitcher_id=w.pitcher_id AND raw.observed_at>w.workload_at""")
    assert c.execute('SELECT count(*) FROM r WHERE workload_at>=observed_at').fetchone()[0]==0
    metas=[]
    with threadpool_limits(limits=2):
        for model_id,cutoff,start,end in STATE_FOLDS:
            for role in ['SP','RP']:
                print(f'{model_id} {role}: fit past prefix baseline',flush=True)
                train=c.execute('SELECT * FROM r WHERE role=? AND observed_at<? AND game_completed_at<?',[role,epoch(cutoff),epoch(cutoff)]).fetchdf()
                if len(train)<500:raise ValueError(f'Insufficient state warmup {model_id} {role}: {len(train)}')
                # One total unit of weight per appearance; long starts must not dominate the cohort.
                weights=1/train.groupby('appearance_id').event_id.transform('count').to_numpy()
                x=model_features(train);bundle={'model_id':model_id+':'+role,'train_end':cutoff,'role':role}
                metrics={}
                for key,col in [('quality','research_stuff_plus'),('command','research_location_plus')]:
                    mask=(train[f'coverage_{col}']>=.8)&train[f'delta_{col}'].notna()
                    target=train.loc[mask,f'delta_{col}'].to_numpy();fit_x=x.loc[mask]
                    model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler(),Ridge(alpha=10.))
                    model.fit(fit_x,target,ridge__sample_weight=weights[mask]);residual=target-model.predict(fit_x)
                    count_only=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),Ridge(alpha=10.))
                    count_only.fit(fit_x[['prefix_pitches','log_pitch_count']],target,ridge__sample_weight=weights[mask])
                    workload_cols=['prefix_pitches','log_pitch_count','pitches_7d_before','rest_hours_since_closed_session']
                    workload_only=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler(),Ridge(alpha=10.))
                    workload_only.fit(fit_x[workload_cols],target,ridge__sample_weight=weights[mask])
                    # Normalize each separate signal by its own past residual distribution.
                    sd=float(np.sqrt(np.average(residual**2,weights=weights[mask])))
                    bundle[key]={'model':model,'count_only':count_only,'workload_only':workload_only,'sd':max(sd,1e-4),'n':int(mask.sum())}
                    metrics[key]={'training_prefixes':int(mask.sum()),'residual_sd':sd}
                physical=[]
                for col in MEASURES[2:]:
                    delta=train[f'delta_{col}'];mask=(train[f'coverage_{col}']>=.8)&delta.notna()
                    if mask.sum()<100:continue
                    # Typical early/late difference per role. Drift is measured relative to past behavior.
                    center=float(np.average(delta[mask],weights=weights[mask]));sd=float(np.sqrt(np.average((delta[mask]-center)**2,weights=weights[mask])))
                    if sd>1e-6:physical.append({'column':col,'center':center,'sd':sd})
                bundle['physical_components']=physical
                def drift(df:pd.DataFrame)->tuple[np.ndarray,np.ndarray]:
                    values=[]
                    for comp in physical:
                        value=((df[f'delta_{comp["column"]}']-comp['center'])/comp['sd']).abs()
                        values.append(value.where(df[f'coverage_{comp["column"]}']>=.8).to_numpy())
                    v=np.asarray(values);n=np.isfinite(v).sum(axis=0)
                    out=np.divide(np.nansum(v,axis=0),n,out=np.full(len(df),np.nan),where=n>0)
                    out[n<max(1,int(np.ceil(.75*len(physical))))]=np.nan
                    return out,n
                td,_=drift(train);pv=np.isfinite(td);bundle['physical_center']=float(np.average(td[pv],weights=weights[pv]))
                bundle['physical_sd']=float(np.sqrt(np.average((td[pv]-bundle['physical_center'])**2,weights=weights[pv])))
                directory=OUT/'models'/model_id;directory.mkdir(parents=True,exist_ok=True)
                joblib.dump(bundle,directory/f'{role.lower()}_state.joblib')
                meta={'model_id':bundle['model_id'],'cutoff':cutoff,'train_rows':len(train),'train_appearances':int(train.appearance_id.nunique()),
                  'maximum_label_available_at':float(train.game_completed_at.max()),'signals':metrics,'physical_components':physical,
                  'scale':'Separate past-reference residual SD, 100 + 10 SD; EB n/(n+20); not a shared physical energy unit.',
                  'features':XCOLS,'workload_scope':'Most recent strictly earlier PA-boundary rolling load, rest, consecutive days, same-day use, prior observed roles/long outings, frozen-reference PA-LI. Not warmup or physiological availability.',
                  'partial_pooling':'Role-specific expected path with Ridge regularization; observed residual shrunk toward cohort expectation. Own closed same-type history used as support predictors.',
                  'interval':'80% approximate sampling interval; does not include full model/baseline selection uncertainty','formal_replacement':False}
                assert meta['maximum_label_available_at']<epoch(cutoff)
                for year in range(2021,2027):
                    if epoch(f'{year+1}-01-01')<=epoch(start) or epoch(f'{year}-01-01')>=epoch(end):continue
                    score=c.execute('SELECT * FROM r WHERE year=? AND role=? AND observed_at>=? AND observed_at<?',[year,role,epoch(start),epoch(end)]).fetchdf()
                    sx=model_features(score);n=(score.prefix_pitches-score.early_n).to_numpy();rel=n/(n+20.)
                    score['reliability']=rel;score['state_model_id']=bundle['model_id'];score['state_train_cutoff']=epoch(cutoff)
                    score['interval_scope']='sampling_only_80pct';score['composite_energy_percent']=np.nan
                    for key,col in [('quality','research_stuff_plus'),('command','research_location_plus')]:
                        item=bundle[key];expected=item['model'].predict(sx)
                        residual=(score[f'delta_{col}'].to_numpy()-expected)/item['sd'];valid=(score[f'coverage_{col}']>=.8).to_numpy()&np.isfinite(residual)
                        value=100+10*rel*residual;value[~valid]=np.nan
                        # Conservative effective count includes the finite early reference and late sample.
                        effective=1/(1/score.early_n.to_numpy()+1/n);se=10*np.sqrt(1/effective)*rel
                        score[key+'_plus']=value;score[key+'_low']=value-1.281552*se;score[key+'_high']=value+1.281552*se
                        score[key+'_expected_delta']=expected
                        if year==2024:
                            mask=valid;truth=score.loc[mask,f'delta_{col}'].to_numpy()
                            vw=1/score.loc[mask].groupby('appearance_id').event_id.transform('count').to_numpy()
                            baseline=item['count_only'].predict(sx.loc[mask,['prefix_pitches','log_pitch_count']])
                            workload_baseline=item['workload_only'].predict(sx.loc[mask,workload_cols])
                            meta.setdefault('validation_2024_expected_path',{})[key]={'n':int(mask.sum()),
                                'full_rmse':float(np.sqrt(np.average((truth-expected[mask])**2,weights=vw))),
                                'count_only_rmse':float(np.sqrt(np.average((truth-baseline)**2,weights=vw))),
                                'recent_workload_rmse':float(np.sqrt(np.average((truth-workload_baseline)**2,weights=vw))),
                                'scope':'Observed prefix retention, equal appearance weights; not a next-pitch outcome or causal benefit validation.'}
                    d,components=drift(score);score['physical_components_used']=components
                    score['physical_plus']=100-10*rel*(d-bundle['physical_center'])/max(bundle['physical_sd'],1e-4)
                    score['physical_low']=score.physical_plus-1.281552*10*rel/np.sqrt(n)
                    score['physical_high']=score.physical_plus+1.281552*10*rel/np.sqrt(n)
                    score['status']=np.where(score[['quality_plus','physical_plus','command_plus']].notna().all(axis=1),'three_signals_available','partial_signals')
                    score.to_parquet(OUT/f'states_{year}_{role.lower()}.parquet',index=False,compression='zstd')
                    print(f'{year} {role}: {len(score):,} prefix rows, complete {int((score.status=="three_signals_available").sum()):,}',flush=True)
                    if year==2024:
                        # Descriptive persistence only: these cumulative prefixes overlap.
                        future=score[['session_id','prefix_pitches','quality_plus','quality_expected_delta','delta_research_stuff_plus']].copy()
                        future['prefix_pitches']-=5
                        v=score[['session_id','prefix_pitches','quality_plus','delta_research_stuff_plus']].merge(future,on=['session_id','prefix_pitches'],suffixes=('_now','_future'))
                        v=v.dropna();meta['validation_2024']={'matched_prefix_pairs':len(v),'quality_state_next_prefix_correlation':float(v.quality_plus_now.corr(v.quality_plus_future)) if len(v)>10 else None,
                            'scope':'Overlapping descriptive persistence only, not disjoint future predictive validation. No promotion on this diagnostic.'}
                save(directory/f'{role.lower()}_state_metadata.json',meta);metas.append(meta)
                del train
    publish_bindings(metas)


def publish_bindings(metas:list|None=None)->None:
    c=duckdb.connect(config={'threads':2,'memory_limit':'2GB'})
    c.execute(f"CREATE VIEW scored AS SELECT * FROM read_parquet('{(OUT/'scored_*.parquet').as_posix()}')")
    if metas is None:
        metas=[json.loads(p.read_text('utf-8')) for p in (OUT/'models').glob('**/*_state_metadata.json')]
    # ASOF binds each legal decision to a strictly earlier observed prefix of its current pitcher.
    c.execute(f"CREATE VIEW states AS SELECT * FROM read_parquet('{(OUT/'states_*.parquet').as_posix()}')")
    coverage=[]
    for year in range(2021,2027):
        c.execute(f"CREATE OR REPLACE TABLE boundary AS SELECT d.*,epoch(try_cast(decision_time AS TIMESTAMPTZ)) decision_at FROM read_parquet('{(BASE/f'decisions_{year}.parquet').as_posix()}') d")
        c.execute("""CREATE OR REPLACE TABLE bound AS SELECT d.decision_id,d.game_pk,d.appearance_id,d.outgoing_pitcher_id,d.decision_at,d.current_pitches,s.role state_role,
          s.event_id state_event_id,s.observed_at state_observed_at,s.state_model_id,s.state_train_cutoff,s.prefix_pitches,
          s.quality_plus,s.quality_low,s.quality_high,s.physical_plus,s.physical_low,s.physical_high,s.command_plus,s.command_low,s.command_high,s.reliability,
          CASE WHEN s.observed_at IS NULL THEN 'warmup_or_insufficient_prefix' WHEN d.decision_at-s.observed_at>28800 THEN 'resumed_session_needs_new_baseline'
            WHEN NOT d.base_state_known OR d.time_basis='play_start_fallback' THEN 'uncertain_decision_source'
            WHEN d.current_pitches>CASE WHEN s.role='SP' THEN 100 ELSE 60 END THEN 'outside_modeled_pitch_count' ELSE s.status END status
          FROM boundary d ASOF LEFT JOIN states s ON d.appearance_id=s.appearance_id AND d.outgoing_pitcher_id=s.pitcher_id AND d.decision_at>s.observed_at""")
        c.execute("UPDATE bound SET quality_plus=NULL,physical_plus=NULL,command_plus=NULL,quality_low=NULL,quality_high=NULL,physical_low=NULL,physical_high=NULL,command_low=NULL,command_high=NULL,reliability=NULL WHERE status IN ('resumed_session_needs_new_baseline','uncertain_decision_source','outside_modeled_pitch_count')")
        assert c.execute('SELECT count(*) FROM bound WHERE state_observed_at>=decision_at OR state_train_cutoff>state_observed_at').fetchone()[0]==0
        c.execute(f"COPY bound TO '{(OUT/f'decision_states_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        rows=c.execute('SELECT count(*),count(quality_plus),count(physical_plus),count(command_plus) FROM bound').fetchone()
        coverage.append(dict(zip(['year','decisions','quality','physical','command'],[year,*rows])))
    c.execute("""CREATE TABLE closed_states AS WITH latest AS(SELECT * FROM states QUALIFY row_number() OVER(PARTITION BY appearance_id ORDER BY observed_at DESC)=1)
      SELECT *,greatest(closed_at,observed_at) completed_state_available_at,
        count(*) OVER(PARTITION BY pitcher_id ORDER BY greatest(closed_at,observed_at),appearance_id ROWS UNBOUNDED PRECEDING) prior_completed_state_count
      FROM latest WHERE closed_at IS NOT NULL""")
    prior_coverage=[]
    for year in range(2021,2027):
        c.execute(f"CREATE OR REPLACE VIEW candidates AS SELECT * FROM read_parquet('{(BASE/f'bullpen_candidates_{year}.parquet').as_posix()}')")
        c.execute("""CREATE OR REPLACE TABLE prior AS SELECT b.decision_id,b.pitcher_id,b.cutoff_epoch,
          s.closed_at prior_state_closed_at,s.observed_at prior_state_observed_at,s.completed_state_available_at prior_state_available_at,s.state_model_id prior_state_model_id,s.role previous_state_role,
          s.quality_plus prior_quality,s.physical_plus prior_physical,s.command_plus prior_command,s.reliability prior_state_reliability,
          s.prior_completed_state_count,false individual_ranking_allowed,
          CASE WHEN s.closed_at IS NULL THEN 'no_completed_prefix_history' ELSE 'prior_observed_state_not_readiness_forecast' END status
          FROM candidates b ASOF LEFT JOIN closed_states s ON b.pitcher_id=s.pitcher_id AND b.cutoff_epoch>s.completed_state_available_at""")
        assert c.execute('SELECT count(*) FROM prior WHERE greatest(prior_state_closed_at,prior_state_observed_at)>=cutoff_epoch OR prior_state_available_at<>greatest(prior_state_closed_at,prior_state_observed_at)').fetchone()[0]==0
        c.execute(f"COPY prior TO '{(OUT/f'candidate_state_priors_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        prior_coverage.append({'year':year,'candidate_profiles':c.execute('SELECT count(*) FROM prior').fetchone()[0],
            'with_prior_closed_state':c.execute('SELECT count(*) FROM prior WHERE prior_state_closed_at IS NOT NULL').fetchone()[0]})
        print(f'{year}: candidate pre-entry closed-state history exported',flush=True)
    for stage,role in [(8,'SP'),(9,'RP')]:
        rows=[]
        for year in range(2021,2027):
            available=c.execute("SELECT count(*),count(DISTINCT appearance_id),count(quality_plus),count(physical_plus),count(command_plus) FROM states WHERE year=? AND role=?",[year,role]).fetchone()
            total=c.execute("SELECT count(DISTINCT appearance_id) FROM scored WHERE year=? AND role=?",[year,role]).fetchone()[0]
            rows.append(dict(zip(['year','observed_scored_appearances','prefixes','eligible_appearances','quality','physical','command'],[year,total,*available])))
        save(ROOT/f'sample/petehub_pitcher_decision_slice{stage}_v1.json',{'slice':stage,'version':VERSION,'role':role,'years':rows,
          'minimum_prefix':35 if role=='SP' else 10,'signals_separate':True,'composite_energy_available':False,'prefix_leakage_violations':0,
          'models':[m for m in metas if m['model_id'].endswith(':'+role)],'decision_coverage_all_roles':coverage,'candidate_prior_coverage':prior_coverage,
          'limitations':['Prefix is cumulative after fixed early baseline, not a monotonic fatigue percentage.','Short RP appearances remain unavailable; cohort shrinkage cannot replace missing deliveries.',
            'Physical tracks public pitch measurements, not physiological fatigue.','Candidate/pre-entry state must not use the first five pitches; workload/candidate artifact remains separate.',
            'Historical role, same-type support, workload and roster confidence remain separate; no individual recommendation.','2024 persistence diagnostic is descriptive, not evidence of next-segment benefit.']})

if __name__=='__main__':
    if '--publish-only' in sys.argv:publish_bindings()
    else:
        if '--fit-only' not in sys.argv:
            for year in range(2021,2027):raw_prefix(year)
        fit_states()
