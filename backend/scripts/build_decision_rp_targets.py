"""15.3 RP target observability and pre-entry-history populations. Stop15.3."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from scipy.special import expit,logit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_balance_revision as base

c,n,old,b=base.c,base.n,base.old,base.b
ROOT=base.ROOT;OUT=ROOT/'data/research/decision_rp_targets_v1'
EXTRA=['prior_rp_median_bf','prior_rp_median_pitches','relative_bf','relative_pitches','prior_rp_n']
NUM=base.CORE+base.STATE+EXTRA;CAT=base.FULLCAT+['usage_profile']
TARGETS=['next_pa','future_ten'];SUBSETS=['all','known_history','short_profile','extended_profile','short_load']


def read(path):return c.read(path)
def save(name,value):b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def usage_profile(count,bf,pitches):
    known=np.asarray(count)>=5
    short=(np.asarray(bf)<=4)&(np.asarray(pitches)<=20)
    return np.where(known,np.where(short,'short_profile','extended_profile'),'history_unknown')


def subset_mask(frame,subset):
    if subset=='all':return pd.Series(True,index=frame.index)
    if subset=='known_history':return frame.usage_profile.ne('history_unknown')
    if subset in ['short_profile','extended_profile']:return frame.usage_profile.eq(subset)
    return frame.usage_profile.eq('short_profile')&frame.relative_pitches.le(1.5)&frame.relative_bf.le(1.5)


def monitoring_mask(frame):
    key=frame.block_id.astype('string').fillna(frame.appearance_id.astype('string')+':no_complete_block')
    ordered=frame.assign(_key=key).sort_values(['anchor_at','decision_id'])
    ids=set(ordered.drop_duplicates('_key',keep='first').decision_id)
    return frame.decision_id.isin(ids)


def pa_nonout(result,outs_before,outs_after):
    # Same ordering as preparation eligible_history: explicit K/hit/BB/HBP,
    # then other_out if outs increased; never compare raw events to group names.
    reach=result.isin(['walk','hit_by_pitch','home_run','single','double','triple'])
    strikeout=result.isin(['strikeout','strikeout_double_play'])
    known=result.notna()&outs_before.notna()&outs_after.notna()
    return pd.Series(np.where(known,reach|(~strikeout&outs_after.le(outs_before)),np.nan),index=result.index)


def prepare(year):
    OUT.mkdir(exist_ok=True);f=base.features(year);f=f[f.role.eq('RP')].reset_index(drop=True)
    print(f'15.3 {year}: {len(f):,} common-clock RP decisions; joining entry-frozen usage histories',flush=True)
    with n.r.connect() as conn:
        conn.read_parquet(str(n.r.OUT/'appearance_history.parquet')).create_view('a')
        conn.execute('''CREATE TEMP TABLE h AS SELECT pitcher_id,available_at,
            median(bf) OVER win prior_rp_median_bf,median(actual_pitches) OVER win prior_rp_median_pitches,count(*) OVER win prior_rp_n
            FROM a WHERE role='RP' AND available_at IS NOT NULL AND NOT bad_timing AND bf>0 AND actual_pitches>0
            WINDOW win AS(PARTITION BY pitcher_id ORDER BY available_at,appearance_id ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)''')
        conn.register('q',f)
        hist=conn.execute('''SELECT q.decision_id,h.available_at usage_reference_at,h.prior_rp_median_bf,h.prior_rp_median_pitches,h.prior_rp_n
            FROM q ASOF LEFT JOIN h ON q.outgoing_pitcher_id=h.pitcher_id AND q.entry_at>h.available_at''').fetchdf()
        conn.read_parquet(str(n.r.OUT/f'pa_observations_{year}.parquet')).create_view('pa')
        conn.read_parquet(str(b.PREP/f'clean_labels_{year}.parquet')).create_view('labels')
        labels=conn.execute('''SELECT q.decision_id,p.anchor_at pa_start,p.available_at pa_available_at,p.actor_pitcher_id,p.final_pitcher_id,
            p.physical_actors,p.bad_timing,l.organic_pa_eligible,l.observed_pa_result,l.outs pa_outs_before,l.outs_after pa_outs_after
            FROM q LEFT JOIN pa p ON q.decision_id=p.decision_id LEFT JOIN labels l ON q.decision_id=l.decision_id''').fetchdf()
        conn.read_parquet(str(c.OUT/'game_clock.parquet')).create_view('gc')
        last=conn.execute('''SELECT q.decision_id,g.appearance_id physical_appearance,g.session_id physical_session,g.session_position physical_position
            FROM q ASOF LEFT JOIN gc g ON q.game_pk=g.game_pk AND q.outgoing_pitcher_id=g.pitcher_id AND q.anchor_at>g.available_at''').fetchdf()
        conn.read_parquet(str(n.OUT/f'block_scores_{year}.parquet')).filter(f'alpha={n.ALPHA}').create_view('s')
        future=conn.execute('''SELECT q.decision_id,s.anchor_at ten_start,s.available_at ten_available_at,s.session_id ten_session,
            s.block_number ten_block,s.residual_stuff,s.residual_velocity,s.residual_location
            FROM q ASOF LEFT JOIN s ON q.appearance_id=s.appearance_id AND q.anchor_at<=s.anchor_at''').fetchdf()
    f=f.merge(hist,on='decision_id',validate='one_to_one').merge(labels,on='decision_id',validate='one_to_one').merge(last,on='decision_id',validate='one_to_one').merge(future,on='decision_id',validate='one_to_one')
    f['pa_reach']=pa_nonout(f.observed_pa_result,f.pa_outs_before,f.pa_outs_after)
    f['usage_profile']=usage_profile(f.prior_rp_n.fillna(0),f.prior_rp_median_bf,f.prior_rp_median_pitches)
    f['relative_bf']=f.current_bf/f.prior_rp_median_bf;f['relative_pitches']=f.current_pitches/f.prior_rp_median_pitches
    for key in EXTRA:f[key]=pd.to_numeric(f[key],errors='coerce').astype(float)
    pa_known=f.changed.eq(0)&f.organic_pa_eligible.fillna(False)&f.actor_pitcher_id.eq(f.outgoing_pitcher_id)&f.final_pitcher_id.eq(f.outgoing_pitcher_id)
    pa_known &= f.pa_reach.notna()&f.physical_actors.eq(1)&f.bad_timing.eq(0).fillna(False)&f.pa_start.ge(f.anchor_at)&f.pa_available_at.gt(f.pa_start)&f.pa_available_at.le(f.game_closed_at)
    pa_known=pa_known.fillna(False).astype(bool)
    f['next_pa_observed']=pa_known.astype(int);f['next_pa_y']=f.pa_reach.where(pa_known).astype(float)
    own=f.physical_appearance.eq(f.appearance_id).fillna(False)
    position=f.physical_position.where(own,0).fillna(0)
    expected=np.ceil(position/10).astype(int)
    same_session=(~own)|f.ten_session.eq(f.physical_session)
    ten_known=f.changed.eq(0)&f.ten_start.ge(f.anchor_at)&f.ten_start.le(f.anchor_at+8*3600)&f.ten_block.eq(expected)&same_session
    ten_known &=f[['residual_stuff','residual_velocity','residual_location']].notna().all(axis=1)&f.ten_available_at.le(f.game_closed_at)
    ten_known=ten_known.fillna(False).astype(bool)
    f['future_ten_observed']=ten_known.astype(int)
    f['future_ten_y']=pd.Series(np.where(ten_known,f.residual_stuff.le(-5)|f.residual_velocity.le(-.5)|f.residual_location.le(-5),np.nan),index=f.index)
    f['monitor_unit']=monitoring_mask(f)
    # All future outcomes and diagnostics live outside the predictor allowlist.
    f['next_pa_reason']=np.where(pa_known,'observed',np.where(f.changed.eq(1),'immediate_change','organic_actor_or_clock_unavailable'))
    f['future_ten_reason']=np.where(ten_known,'observed',np.where(f.changed.eq(1),'immediate_change',np.where(f.ten_block.notna()&f.ten_block.eq(expected)&same_session,'measurement_or_support','no_entire_future_block_in_current_session')))
    assert (f.usage_reference_at.dropna()<f.loc[f.usage_reference_at.notna(),'entry_at']).all()
    write(f,f'features_{year}.parquet')
    rows=[]
    for scope,part in [('all_boundaries',f),('paired_monitoring',f[f.monitor_unit])]:
        for phase in base.PHASES:
            p=part[part.phase.eq(phase)]
            for subset in SUBSETS:
                s=p[subset_mask(p,subset)]
                for target in TARGETS:
                    rows.append({'scope':scope,'phase':phase,'subset':subset,'target':target,'n':len(s),'observed':int(s[target+'_observed'].sum()),
                        'rate':float(s[target+'_observed'].mean()) if len(s) else None,'appearances':int(s.appearance_id.nunique()),
                        'unique_ten_targets':int(s.loc[s.future_ten_observed.eq(1),['appearance_id','ten_session','ten_block']].drop_duplicates().shape[0])})
    save(f'preparation_{year}.json',{'year':year,'boundaries':len(f),'monitor_units':int(f.monitor_unit.sum()),'profiles':f.usage_profile.value_counts().to_dict(),'coverage':rows,
        'next_pa_reasons':f.next_pa_reason.value_counts().to_dict(),'ten_reasons':f.future_ten_reason.value_counts().to_dict()})
    print(f'15.3 {year}: {int(f.monitor_unit.sum()):,} paired monitor units, PA observed {int(f.next_pa_observed.sum()):,}, ten observed {int(f.future_ten_observed.sum()):,}',flush=True)


def protocol():
    paths=[Path(__file__),c.OUT/'manifest.json',base.OUT/'manifest.json',n.r.OUT/'appearance_history.parquet']
    for year in range(2021,2025):
        paths += [OUT/f'features_{year}.parquet',n.r.OUT/f'pa_observations_{year}.parquet',b.PREP/f'clean_labels_{year}.parquet']
    return {'version':'decision_rp_targets_v1','revision':2,'input_sha256':{p.relative_to(ROOT).as_posix():b.digest(p) for p in paths},
        'correction':'attempt0_label_mapping preserves exact first source/protocol/data/30 task artifacts/2024 diagnostics. Initial nextPA raw event/group-name mismatch made all known labels1. Revision2 restores preparation canonical event/outs mapping only; no feature/model/population/gate search.2024 already diagnosed; not fresh confirmation.',
        'scope':'RP common-clock eligible decisions only2021-24, inherits retrospective cohort; no SP or2025 evaluation',
        'usage':'last10 completed RP appearances strictly before current entry, min5; short history medianBF<=4 AND median pitches<=20, extended otherwise, unknown if insufficient; no current/future final stint length used',
        'subsets':SUBSETS,'primary_population':'within_inning short_profile, defined before fitting; all/known/extended and short_load are named sensitivity populations, never chosen by2024 SMD',
        'short_load':'short profile and predecision currentpitches/entry-frozen median<=1.5 AND currentBF/median<=1.5; excludes heavy-load situations, not full fatigue population',
        'monitor':'first anchored decision for each known completed block; before any completed block first decision per appearance no_complete_block key. Forward-only selection; coverage also report ALL PA decisions and unique future block counts; repeated PA/block targets not independent samples',
        'targets':{'next_pa':'outgoing actor next complete organic PA canonical nonout result, same single physical actor, first pitch>=anchor; raw strikeout/strikeout_double_play0, explicit hit/walk/HBP1, otherwise0 if outs increased else1, matches preparation eligible_history K/other_out0; not pure OBP. Replaced pitcher missing, not incoming outcome',
            'future_ten':'first entirely future fixed nonoverlap10-pitch block, expected number=ceil(last own session position/10), same current session, starts within8h, all3 normal residuals valid; Stuff<=-5 OR speed<=-.5 OR Location<=-5; missing remainsNaN'},
        'features':NUM+CAT,'learners':'fixed HGB7/60 minleaf200 L2=10 learning_rate.05 plus disjoint late-time Platt; natural sampling, only historical features; perphase action(full-boundary fit) and each target observation/conditional outcome(paired-monitor fit). Require fit>=300/cal>=100, each fit class>=20/cal class>=5; otherwise declared training-only Laplace constant baseline, not fitted improvement',
        'time':'2021->2022,21-22->23,21-23->24; chronological80/20 whole-game label-close time, spanning games excluded; preprocessing fit only, all labels before validation anchor; no hyperparameter or population selection',
        'balance':'compare frozen15.2 HGB vs new history-enriched HGB on same declared subsets; common development cell>=10 each action; overlap primary/IPW[.05,.95]secondary; SAME rich old benchmark plus history numeric/profile flags, no hidden removal. ESS>=500 each arm, maxSMD<=.1,ECE<=.03 diagnostic only',
        'observation':'paired monitoring opportunities; observation probability g from ALL observed/missing examples, conditional outcome fit only observed examples; evaluate each task only against own constant baseline. No cross-target Brier comparison',
        'sensitivity':'2024 fixed declared populations, observed mean, g>=.1 inverse observation weights capsNone/10/20/50, worst-case missing bounds, and missing-outcome odds multipliers.5/1/2 around conditional forecast for unknown rows as aggregate scenarios only; labels never imputed or fed back',
        'limits':'different target meanings (PA reach vs measured deviation), residual selection/MAR assumptions untestable, no next-batter identity at anchor, no causal value or strategy/ranking promotion;15.4 not started',
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.3'}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value
    save('protocol.json',value);print('15.3 targets, populations, features and models frozen before fitting',flush=True)


def model_fit(train,cal,label):
    counts=train[label].value_counts();calcounts=cal[label].value_counts()
    if len(train)<300 or len(cal)<100 or len(counts)!=2 or counts.min()<20 or len(calcounts)!=2 or calcounts.min()<5:
        prior=float((train[label].sum()+1)/(len(train)+2))
        return {'kind':'constant','prior':prior,'label':label,'reason':'predeclared fit/cal/class support insufficient'}
    transform=ColumnTransformer([('num','passthrough',NUM),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CAT)],sparse_threshold=0.)
    model=make_pipeline(transform,HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=7,min_samples_leaf=200,l2_regularization=10.,learning_rate=.05,max_bins=63,
        early_stopping=False,random_state=old.SEED))
    model.fit(train,train[label]);p=np.clip(model.predict_proba(cal)[:,1],1e-6,1-1e-6)
    platt=LogisticRegression(C=1.,max_iter=200).fit(logit(p)[:,None],cal[label])
    return {'kind':'hgb','model':model,'platt':platt,'prior':float(train[label].mean()),'label':label}


def predict(bundle,frame):
    if bundle['kind']=='constant':return np.full(len(frame),bundle['prior'])
    p=np.clip(bundle['model'].predict_proba(frame)[:,1],1e-6,1-1e-6)
    return bundle['platt'].predict_proba(logit(p)[:,None])[:,1]


def enrich_design(frame):
    f=frame.copy()
    for key in NUM:f[key]=pd.to_numeric(f[key],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    for key in CAT:f[key]=f[key].astype('string').fillna('unknown').astype(str)
    return f


def temporal_partition(frame):
    dates=frame.groupby('game_pk').game_closed_at.max().sort_values().to_numpy()
    boundary=float(np.floor(dates[int(.8*len(dates))]/86400)*86400)
    games=frame.groupby('game_pk').agg(first=('anchor_at','min'),last=('game_closed_at','max'))
    spanning=set(games.index[(games['first']<boundary)&(games['last']>=boundary)])
    fit=frame[frame.game_closed_at.lt(boundary)&~frame.game_pk.isin(spanning)]
    cal=frame[frame.anchor_at.ge(boundary)&~frame.game_pk.isin(spanning)]
    assert len(fit)>0 and len(cal)>0 and fit.game_closed_at.max()<cal.anchor_at.min()
    return fit,cal,{'boundary':boundary,'fit_n':len(fit),'calibration_n':len(cal),'spanning_games_excluded':len(spanning)}


def train(year,phase):
    assert read(OUT/'protocol.json')==protocol()
    past=pd.concat([enrich_design(pd.read_parquet(OUT/f'features_{y}.parquet')) for y in range(2021,year)],ignore_index=True)
    cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp();past=past[past.phase.eq(phase)&past.game_closed_at.lt(cutoff)]
    valid=enrich_design(pd.read_parquet(OUT/f'features_{year}.parquet'));valid=valid[valid.phase.eq(phase)].reset_index(drop=True)
    rows=[]
    tasks=[('action','changed')]+[(target+':observation',target+'_observed') for target in TARGETS]+[(target+':outcome',target+'_y') for target in TARGETS]
    with threadpool_limits(limits=2):
        for task,label in tasks:
            source=past if task=='action' else past[past.monitor_unit]
            if task.endswith(':outcome'):source=source[source[label].notna()]
            fit,cal,flow=temporal_partition(source);assert cal.game_closed_at.max()<valid.anchor_at.min()
            name=task.replace(':','_');print(f'15.3 {year}/{phase}/{task}: {len(fit):,} fit / {len(cal):,} cal',flush=True)
            splits=pd.concat([f[['decision_id','game_pk','anchor_at','game_closed_at']].assign(partition=p) for p,f in [('fit',fit),('calibration',cal)]],ignore_index=True)
            write(splits,f'split_{year}_{phase}_{name}.parquet')
            bundle=model_fit(fit,cal,label);joblib.dump(bundle,OUT/f'model_{year}_{phase}_{name}.joblib')
            valid[name+'_probability']=predict(bundle,valid)
            score=valid if task=='action' else valid[valid.monitor_unit]
            score=score[score[label].notna()]
            metrics=old.binary_metrics(score[label].to_numpy(int),score[name+'_probability'].to_numpy(),bundle['prior'])
            rows.append({'task':task,'kind':bundle['kind'],'flow':flow,'metrics':metrics,'fit_last_label':float(fit.game_closed_at.max()),'cal_first_anchor':float(cal.anchor_at.min()),
                'cal_last_label':float(cal.game_closed_at.max()),'validation_first_anchor':float(valid.anchor_at.min())})
    support=past.groupby('cell').changed.agg(['sum','count']);support['support']=support['sum'].ge(10)&(support['count']-support['sum']).ge(10)
    valid['past_cell_support']=valid.cell.map(support.support).fillna(False).astype(bool)
    write(valid,f'scored_{year}_{phase}.parquet');write(support.reset_index(),f'cells_{year}_{phase}.parquet')
    save(f'fit_{year}_{phase}.json',{'year':year,'phase':phase,'tasks':rows,'test2025_outcomes_examined':False})


def diagnostics(frame,probability,scheme):
    # Same immutable base benchmark, plus newly declared historical usage fields.
    result=base.diagnostics(frame,probability,scheme)
    mask=frame.past_cell_support.to_numpy(bool).copy()
    if scheme=='ipw':mask &= (probability>=.05)&(probability<=.95)
    f=frame[mask];a=f.changed.to_numpy(bool);w=base.balancing_weights(a,probability[mask],scheme)
    values={key:f[key].to_numpy(float) for key in EXTRA}
    for level in ['short_profile','extended_profile','history_unknown']:values['usage_profile='+level]=f.usage_profile.eq(level).to_numpy(float)
    for name,x in values.items():
        finite=np.isfinite(x)
        for suffix,value,known in [('value',x,finite),('missing',(~finite).astype(float),np.ones(len(x),bool))]:
            l=a&known;r=~a&known
            if l.sum()<2 or r.sum()<2:continue
            scale=np.sqrt((value[l].var()+value[r].var())/2);separated=scale<1e-9 and abs(value[l].mean()-value[r].mean())>1e-9
            if scale<1e-9 and not separated:continue
            if separated:scale=1e-8
            result['balance'].append({'field':name+':'+suffix,'before':float((value[l].mean()-value[r].mean())/scale),
                'after':float((np.average(value[l],weights=w[l])-np.average(value[r],weights=w[r]))/scale),'arm_constant_separation':bool(separated)})
    result['max_abs_smd_after']=max((abs(x['after']) for x in result['balance']),default=None)
    result['diagnostic_gate']=bool(result['change']['ess']>=500 and result['continue']['ess']>=500 and result['max_abs_smd_after'] is not None and result['max_abs_smd_after']<=.1)
    return result


def scenario_summary(frame,target):
    observed=frame[target+'_observed'].eq(1).to_numpy();y=frame[target+'_y'].to_numpy(float);g=frame[target+'_observation_probability'].to_numpy()
    p=frame[target+'_outcome_probability'].to_numpy();count=len(frame);events=float(np.nansum(y));missing=int((~observed).sum())
    if not count:return {'n':0,'observed':0,'missing':0}
    supported=observed&(g>=.1);w=1/g[supported]
    scenarios=[]
    for odds in [.5,1.,2.]:
        hypothetical=expit(logit(np.clip(p[~observed],1e-6,1-1e-6))+np.log(odds))
        scenarios.append({'missing_odds_multiplier':odds,'scenario_rate':float((events+hypothetical.sum())/count)})
    return {'n':count,'observed':int(observed.sum()),'missing':missing,'observed_rate':float(np.nanmean(y)) if observed.any() else None,
        'g10_observed':int(supported.sum()),'ip_observation_rate':float(np.average(y[supported],weights=w)) if len(w) else None,
        'weight_caps':[{'cap':cap,**old.weight_summary(old.cap_weights(w,cap))} for cap in old.CAPS],
        'worst_case_bounds':[events/count,(events+missing)/count],'missing_scenarios':scenarios,
        'label':'aggregate sensitivity only; unobserved labels remain NaN, not causal outcomes'}


def evaluate():
    assert read(OUT/'protocol.json')==protocol();balances=[];tasks=[];sensitivities=[]
    for year in [2022,2023,2024]:
        for phase in base.PHASES:
            f=pd.read_parquet(OUT/f'scored_{year}_{phase}.parquet')
            oldscore=pd.read_parquet(base.OUT/f'scored_{year}_RP_{phase}_hgb_full.parquet').set_index('decision_id').loc[f.decision_id]
            for subset in SUBSETS:
                mask=subset_mask(f,subset);part=f[mask]
                for model,prob in [('frozen15_2',oldscore.propensity.to_numpy()),('history_enriched',f.action_probability.to_numpy())]:
                    for scheme in base.SCHEMES:
                        result=diagnostics(part,prob[mask.to_numpy()],scheme)
                        action_bundle=joblib.load(OUT/f'model_{year}_{phase}_action.joblib')
                        if len(part):result['action_metrics']=old.binary_metrics(part.changed.to_numpy(int),prob[mask.to_numpy()],action_bundle['prior'])
                        result['full_gate']=bool(result['diagnostic_gate'] and len(part) and result['action_metrics']['ece']<=.03)
                        result.update(year=year,phase=phase,subset=subset,model=model)
                        balances.append(result)
                monitor=part[part.monitor_unit]
                for target in TARGETS:
                    observation=monitor[target+'_observed'].to_numpy(int);obsprob=monitor[target+'_observation_probability'].to_numpy()
                    known=observation==1;outcomes=monitor.loc[known,target+'_y'].to_numpy(int);prob=monitor.loc[known,target+'_outcome_probability'].to_numpy()
                    # Metrics are target-specific, not comparable across target labels.
                    record={'year':year,'phase':phase,'subset':subset,'target':target,'n':len(monitor),'observed':int(known.sum()),'rate':float(known.mean()) if len(known) else None}
                    # Original fit/cal metrics already use a strictly past constant; subgroup outcome metrics below use those saved priors.
                    bundle=joblib.load(OUT/f'model_{year}_{phase}_{target}_observation.joblib')
                    if len(monitor):record['observation_metrics']=old.binary_metrics(observation,obsprob,bundle['prior'])
                    obundle=joblib.load(OUT/f'model_{year}_{phase}_{target}_outcome.joblib')
                    if len(outcomes):record['outcome_metrics']=old.binary_metrics(outcomes,prob,obundle['prior'])
                    tasks.append(record)
                    if year==2024:sensitivities.append({'phase':phase,'subset':subset,'target':target,**scenario_summary(monitor,target)})
            print(f'15.3 diagnostics {year}/{phase}: paired target coverage, fixed populations and balance complete',flush=True)
    preparation=[read(OUT/f'preparation_{y}.json') for y in range(2021,2025)]
    primary=[x for x in balances if x['year']==2024 and x['phase']=='within_inning' and x['subset']=='short_profile' and x['scheme']=='overlap']
    save('summary.json',{'version':'decision_rp_targets_v1','preparation':preparation,'balance':balances,'task_results':tasks,'sensitivity2024':sensitivities,'primary2024':primary,
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.3',
        'interpretation':'coverage gains are not cross-target predictive gain; balance in restricted histories is not proof of causal strategy benefit;15.4 not started'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','train','evaluate']);parser.add_argument('--year',type=int,choices=range(2021,2025));parser.add_argument('--phase',choices=base.PHASES);args=parser.parse_args()
    if args.stage=='prepare':prepare(args.year)
    elif args.stage=='train':train(args.year,args.phase)
    else:globals()[args.stage]()
