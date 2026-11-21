"""15.5.3/4 fixed common-clock PA forecasts and observational run-warning study."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import warnings
import time
import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier,RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import log_loss,roc_auc_score,average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_pe_features as f

q=f.q;ROOT=f.ROOT;OUT=ROOT/'data/research/decision_pe_models_v1'
CONFIGS=['hgb_base','hgb_pe','hgb_full','linear_full','rf_full'];RUN_CONFIGS=['hgb_base','hgb_full']
FIT_CAP=60000;SEED=1552026;REPS=300
NONOUT=[f.OUTCOMES.index(x) for x in f.OUTCOMES if x not in ['k','other_out']]


def read(path):return f.read(path)
def save(name,value):q.b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def columns(config):
    group=config.split('_')[1];return f.GROUPS[group],f.FULLCAT if group=='full' else f.CATS


def design(frame):
    result=frame.copy()
    for key in f.GROUPS['full']:result[key]=pd.to_numeric(result[key],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    for key in f.FULLCAT:result[key]=result[key].astype('string').fillna('unknown').astype(str)
    return result


def primary_mask(frame,role):
    return pd.Series(True,index=frame.index) if role=='SP' else frame.phase.eq('within_inning')&frame.usage_profile.eq('short_profile')


def make_model(config):
    numeric,cat=columns(config);kind=config.split('_')[0]
    num='passthrough' if kind=='hgb' else make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler())
    trans=ColumnTransformer([('num',num,numeric),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cat)],sparse_threshold=0.)
    if kind=='hgb':model=HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=7,min_samples_leaf=200,l2_regularization=10.,learning_rate=.05,max_bins=63,early_stopping=False,random_state=SEED)
    elif kind=='rf':model=RandomForestClassifier(n_estimators=100,max_depth=8,min_samples_leaf=100,max_features=.7,n_jobs=2,random_state=SEED)
    else:model=SGDClassifier(loss='log_loss',penalty='l2',alpha=.001,max_iter=100,tol=.001,average=True,early_stopping=False,random_state=SEED)
    return make_pipeline(trans,model)


def raw_probability(model,frame,classes):
    raw=model.predict_proba(frame);p=np.full((len(frame),classes),1e-12)
    p[:,model[-1].classes_.astype(int)]=raw
    p=np.clip(p,1e-12,1);return p/p.sum(axis=1,keepdims=True)


def temperature(p,value):
    z=np.log(np.clip(p,1e-12,1))/value;z-=z.max(axis=1,keepdims=True);z=np.exp(z)
    return z/z.sum(axis=1,keepdims=True)


def predict(bundle,frame):return temperature(raw_probability(bundle['model'],frame,len(bundle['prior'])),bundle['temperature'])


def fit_bundle(train,cal,config,task):
    label='y_'+task;classes=9 if task=='pa' else 2;y=train[label].to_numpy(int);yc=cal[label].to_numpy(int)
    model=make_model(config)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(train,y)
    p=raw_probability(model,cal,classes)
    optimal=minimize_scalar(lambda t:float(-np.log(temperature(p,t)[np.arange(len(yc)),yc]).mean()),bounds=(.5,3.),method='bounded',options={'xatol':1e-4})
    prior=(np.bincount(y,minlength=classes)+1)/(len(y)+classes)
    return {'model':model,'temperature':float(optimal.x),'prior':prior,'config':config,'task':task,
        'warning':any(isinstance(v.message,ConvergenceWarning) for v in caught),'classes_seen':model[-1].classes_.astype(int).tolist()}


def cluster_delta(frame,loss,reps=REPS,seed=SEED):
    loss=np.asarray(loss,float)
    if not len(loss):return {'n':0,'delta':None,'interval':None,'games':0,'pitchers':0}
    gi,gs=pd.factorize(frame.game_pk);pi,ps=pd.factorize(frame.outgoing_pitcher_id);rng=np.random.default_rng(seed);values=[]
    for _ in range(reps):
        weights=rng.multinomial(len(gs),np.full(len(gs),1/len(gs)))[gi]*rng.multinomial(len(ps),np.full(len(ps),1/len(ps)))[pi]
        if weights.sum():values.append(float(np.average(loss,weights=weights)))
    return {'n':len(loss),'delta':float(loss.mean()),'interval':[float(v) for v in np.quantile(values,[.025,.975])],'games':len(gs),'pitchers':len(ps)}


def metrics_pa(y,p,prior):
    labels=np.asarray(y,int);one=np.eye(9)[labels]
    actual=np.isin(labels,NONOUT).astype(int);reach=p[:,NONOUT].sum(axis=1)
    return {'n':len(labels),'log_loss':float(log_loss(labels,p,labels=list(range(9)))),
        'constant_log_loss':float(-np.log(prior[labels]).mean()),'multiclass_brier':float(np.mean(np.sum((one-p)**2,axis=1))),
        'nonout':q.old.binary_metrics(actual,reach,float(prior[NONOUT].sum()))}


def warning_replay(frame,probability,threshold):
    # Values/actual changes/future labels are deliberately not read here.
    out=frame[['decision_id','game_pk','team_id','appearance_id','role','inning','half','anchor_at','seen_pa_count']].copy()
    out['high']=np.asarray(probability)>=threshold;out['emitted']=False
    for _,group in out.sort_values(['anchor_at','decision_id']).groupby(['game_pk','team_id'],sort=False):
        last=None;run=0;used=set();last_emission=None
        for index,row in group.iterrows():
            adjacent=last is not None and last.high and last.appearance_id==row.appearance_id and last.inning==row.inning and last.half==row.half and last.seen_pa_count+1==row.seen_pa_count
            run=(run+1 if adjacent else 1) if row.high else 0
            if run>=2 and row.appearance_id not in used and (last_emission is None or row.seen_pa_count-last_emission>2):
                out.at[index,'emitted']=True;used.add(row.appearance_id);last_emission=row.seen_pa_count
            last=row
    return out


def warning_summary(frame,probability,threshold):
    replay=warning_replay(frame,probability,threshold);out=frame[['decision_id','target_observed','y_run','changed','old_decision_at']].merge(replay,on='decision_id',validate='one_to_one')
    alerts=out[out.emitted];known=alerts[alerts.target_observed];events=out[out.changed.eq(1)].sort_values('old_decision_at').drop_duplicates('appearance_id').set_index('appearance_id')
    same=0;advance=0;leads=[]
    for row in alerts.itertuples():
        if row.appearance_id not in events.index:continue
        event=events.loc[row.appearance_id];pa=float(event.seen_pa_count-row.seen_pa_count);seconds=float(event.old_decision_at-row.anchor_at)
        if event.decision_id==row.decision_id and seconds>=0:same+=1
        elif 1<=pa<=2 and 0<seconds<=600:advance+=1;leads.append(seconds)
    return {'n':len(out),'games':int(out.game_pk.nunique()),'appearances':int(out.appearance_id.nunique()),'alerts':len(alerts),
        'alerts_per100_appearances':100*len(alerts)/max(1,out.appearance_id.nunique()),'known_alerts':len(known),'unknown_alerts':int((~alerts.target_observed).sum()),
        'true_observed':int(known.y_run.sum()),'precision_observed':float(known.y_run.mean()) if len(known) else None,
        'events_observed':int(out.y_run.sum()),'sensitivity_observed':float(known.y_run.sum()/out.y_run.sum()) if out.y_run.sum()>0 else None,
        'early_alerts':int(alerts.inning.le(3).sum()),'same_boundary_change':same,'advance_change_2pa600s':advance,
        'advance_seconds_median':float(np.median(leads)) if leads else None,
        'limits':'target is scoring DURING next organic PA, conditional observed incumbent; unknown outcomes not negatives. Role-specific replay/cooldown stream, not integrated SP-to-RP policy. Match only eligible-cohort observed changes, no causal efficacy or full-official-event recall'}


def protocol():
    sources=[Path(__file__),Path(f.__file__)]+[folder/'manifest.json' for folder in entry_folders()]
    sources += [f.OUT/f'features_{y}.parquet' for y in range(2021,2025)]
    return {'version':'decision_pe_models_v1','source_sha256':{p.relative_to(ROOT).as_posix():q.b.digest(p) for p in sources},
        'features':f.GROUPS,'categories':{'base_pe':f.CATS,'full':f.FULLCAT},'configs':CONFIGS,'run_configs':RUN_CONFIGS,
        'scope':'15.5.1-4 only, all common-clock SP/RP2021-24; original cohort inherited. Main nine-category next organic PA by outgoing incumbent; auxiliary any score DURING that PA, NOT anchor-to-half WPA/RE24. Replaced incumbent unknown, never incoming outcome.',
        'primary':'SP all eligible common boundaries; RP within_inning short_profile entry-frozen from15.3. Others phase/role summaries only, no2024 rescue selection.',
        'pe_proxy':'PA event weights fixed (-.88,-1.25,-1.58,-2.03,-.69,-.72), out .5 except sac_fly, preterminal count .5*sign(S-B), EV>=95 -.5/<=80 +.5; noncontact EV contribution0, contact missing EV unknown. Whiffs separate, no double counting per-pitch .5; PA adaptation not exact published PE or validated physiological fatigue.',
        'prefix':'last1/2/3 complete PA scores and3-score slope, partial observed cumulative WITH coverage; unknown scores break rolling windows. Hard rate per recent PA, noncontact0, missing EV unknown. Prefix strike share excludes fair inplay. FF is FF only; last completed PA FF mean minus observed prefix, never whole-game future mean.',
        'personal':'entry-frozen last50 known PE PAs/FF PAs by pitcher/role, at least10 for means; observed recent3 average minus entry PE mean, last FF mean minus entry FF mean. Existing normal-process residuals already in base; not newly estimated BF-specific PE fatigue.',
        'lineup':'count EVERY completed observed official PA including zero-pitch/IBB, predict upcoming slots using previous completed actor in each modulo9 slot; no future actor or final batting order. Unknown first-cycle identities back off, pitcher substitutions unknown. Own batter nine-rate history strict ASOF, shrink20 toward completed previous-UTC-day league PA prior, initial Laplace1 uniform if no day prior. Forecast identity agreement diagnostic only, never sample filter.',
        'dictionary':'A quality,B location/control proxy,C opponent contact,D load/recovery; next-batter forecast is separate, correcting15.4 descriptive typo without changing prior hashes.',
        'fit':'2021->22,21-22->23,21-23->24. ALL boundary whole-game80/20 chronology using game close; spanning games excluded. Then fit/cal observed labels only; deterministic natural60000 fit cap shared by all configs/tasks. Imputer/scaler fit only. Temp[.5,3] on disjoint late observed games, no oversampling.',
        'learners':'fixed HGB7leaf60/minleaf200/L2=10/lr.05; linear SGD log_loss/L2alpha.001/100iter/averaged; RF100trees/depth8/minleaf100/maxfeatures.7. No hyperparameter search. Three HGB feature groups plus same full features for linear/RF. Auxiliary run HGBbase/full only.30 PA+12 run fits.',
        'selection':'2022/23 only per role main config; rank failing predictive folds then mean LL then fixed order. Predictive fold: paired game*player LL interval upper<0 vs hgb_base, nonout ECE<=.03 and no fit warning. A research ranking may have no promotion.2024 remains reused diagnosis, not independent confirmation.',
        'uncertainty':{'reps':REPS,'seed':SEED,'method':'game and pitcher multinomial product weights; paired losses conditional observed Y and fixed model; exploratory marginal percentile95, no refit/multiplicity claim'},
        'warnings':'auxiliary run risk threshold90th percentile of ALL past late calibration-boundary predicted risks, independent of actual change/observation. Role-specific replay streams: two adjacent same-half same-appearance PA boundaries, one alert/appearance,2defensive-PA team cooldown within role stream; not integrated SP-to-RP strategy. No fifth-inning or final-stint-length filter. Report early<=3 burden, PPV/recall only observed labels, unknown separate. Actual-change matching posthoc only, same-boundary vs1-2PA/600s advance separate.',
        'balance':'no action propensity refit or balancing claim; retain15.4 comparison gates/results and full16 barriers. Outcome performance does not lower SMD or establish strategy value.',
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.5.4'}


def entry_folders():return f.entry.input_folders()+[f.entry.OUT]


def freeze():
    OUT.mkdir(exist_ok=True);value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value
    save('protocol.json',value);print('15.5 features/labels/models/selection/warning thresholds frozen before fits',flush=True)


def train(year,role):
    assert read(OUT/'protocol.json')==protocol()
    past=pd.concat([design(pd.read_parquet(f.OUT/f'features_{y}.parquet')) for y in range(2021,year)],ignore_index=True)
    past=past[past.role.eq(role)&past.game_closed_at.lt(pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp())]
    fit_all,cal_all,flow=q.temporal_partition(past);fit=fit_all[fit_all.target_observed];cal=cal_all[cal_all.target_observed]
    if len(fit)>FIT_CAP:fit=fit.sample(FIT_CAP,random_state=SEED).sort_values(['anchor_at','decision_id'])
    valid=design(pd.read_parquet(f.OUT/f'features_{year}.parquet'));valid=valid[valid.role.eq(role)].reset_index(drop=True)
    assert fit.game_closed_at.max()<cal.anchor_at.min() and cal_all.game_closed_at.max()<valid.anchor_at.min()
    used=set(fit.decision_id)
    split=pd.concat([part[['decision_id','game_pk','anchor_at','game_closed_at','target_observed']].assign(partition=name,fit_used=part.decision_id.isin(used)) for name,part in [('fit',fit_all),('calibration',cal_all)]],ignore_index=True)
    write(split,f'split_{year}_{role}.parquet');tasks=[]
    with threadpool_limits(limits=2):
        for task,configs in [('pa',CONFIGS),('run',RUN_CONFIGS)]:
            for config in configs:
                start=time.monotonic();print(f'15.5 {year}/{role}/{task}/{config}: {len(fit):,} fit, {len(cal):,} cal',flush=True)
                bundle=fit_bundle(fit,cal,config,task);p=predict(bundle,valid)
                if task=='pa':
                    for k in range(9):valid[f'{config}_p{k}']=p[:,k]
                else:
                    valid[f'{config}_run']=p[:,1];bundle['warning_threshold']=float(np.quantile(predict(bundle,cal_all)[:,1],.9))
                joblib.dump(bundle,OUT/f'model_{year}_{role}_{task}_{config}.joblib')
                tasks.append({'task':task,'config':config,'warning':bundle['warning'],'temperature':bundle['temperature'],'classes_seen':bundle['classes_seen'],
                    'fit_n':len(fit),'cal_n':len(cal),'threshold':bundle.get('warning_threshold'),'seconds':time.monotonic()-start})
                print(f'15.5 {year}/{role}/{task}/{config}: saved in {time.monotonic()-start:.1f}s',flush=True)
    write(valid,f'scored_{year}_{role}.parquet')
    save(f'fit_{year}_{role}.json',{'year':year,'role':role,'flow':flow,'tasks':tasks,'fit_last_label':float(fit.game_closed_at.max()),'cal_first_anchor':float(cal.anchor_at.min()),
        'cal_last_label':float(cal_all.game_closed_at.max()),'validation_first_anchor':float(valid.anchor_at.min())})


def evaluate(year,role):
    assert read(OUT/'protocol.json')==protocol();frame=pd.read_parquet(OUT/f'scored_{year}_{role}.parquet');primary=primary_mask(frame,role)
    mask=primary&frame.target_observed;part=frame[mask];y=part.y_pa.to_numpy(int);base=part[[f'hgb_base_p{k}' for k in range(9)]].to_numpy()
    rows=[];run=[];alarms=[];binary_reference=[]
    for ci,config in enumerate(CONFIGS):
        bundle=joblib.load(OUT/f'model_{year}_{role}_pa_{config}.joblib');p=part[[f'{config}_p{k}' for k in range(9)]].to_numpy()
        metric=metrics_pa(y,p,bundle['prior'])
        gain=cluster_delta(part,-np.log(p[np.arange(len(y)),y])+np.log(base[np.arange(len(y)),y]),seed=SEED+year+ci)
        reach=p[:,NONOUT].sum(axis=1);br=base[:,NONOUT].sum(axis=1);truth=np.isin(y,NONOUT).astype(int)
        brier=cluster_delta(part,(truth-reach)**2-(truth-br)**2,seed=SEED+year+ci)
        rows.append({'year':year,'role':role,'config':config,'metrics':metric,'delta_log_loss':gain,'delta_nonout_brier':brier,'fit_warning':bundle['warning'],
            'predictive_gate':bool(gain['interval'][1]<0 and metric['nonout']['ece']<=.03 and not bundle['warning'])})
        print(f'15.5 {year}/{role}/{config}: paired PA loss and uncertainty evaluated',flush=True)
    for config in RUN_CONFIGS:
        bundle=joblib.load(OUT/f'model_{year}_{role}_run_{config}.joblib');prob=part[config+'_run'].to_numpy();truth=part.y_run.to_numpy(int)
        metric=q.old.binary_metrics(truth,prob,float(bundle['prior'][1]));metric['average_precision']=float(average_precision_score(truth,prob))
        gain=cluster_delta(part,(truth-prob)**2-(truth-part.hgb_base_run.to_numpy())**2,seed=SEED+year)
        run.append({'year':year,'role':role,'config':config,'metrics':metric,'delta_brier':gain})
        # Replay the entire inherited role risk set, including unknown outcomes and gaps.
        # Aggregate primary-population burden separately after full role replay.
        warning=warning_replay(frame,frame[config+'_run'].to_numpy(),bundle['warning_threshold'])
        record=warning_summary(frame,frame[config+'_run'].to_numpy(),bundle['warning_threshold'])
        primary_ids=set(frame.loc[primary,'decision_id']);primary_emitted=warning[warning.decision_id.isin(primary_ids)&warning.emitted]
        record.update(year=year,role=role,config=config,threshold=bundle['warning_threshold'],primary_alerts=len(primary_emitted),
            primary_unknown_alerts=int(frame.set_index('decision_id').loc[primary_emitted.decision_id,'target_observed'].eq(False).sum()))
        alarms.append(record)
        write(warning,f'warning_{year}_{role}_{config}.parquet')
    if role=='RP':
        old=pd.read_parquet(q.OUT/f'scored_{year}_within_inning.parquet').set_index('decision_id')
        paired=frame[primary&frame.monitor_unit&frame.target_observed].copy();prior_rows=old.loc[paired.decision_id]
        keep=prior_rows.next_pa_observed.eq(1).to_numpy();paired=paired[keep];prior_rows=prior_rows[keep]
        truth=np.isin(paired.y_pa.to_numpy(int),NONOUT).astype(int)
        assert np.array_equal(truth,prior_rows.next_pa_y.to_numpy(int))
        reference=prior_rows.next_pa_outcome_probability.to_numpy()
        reference_bundle=joblib.load(q.OUT/f'model_{year}_within_inning_next_pa_outcome.joblib')
        binary_reference.append({'config':'frozen15_3_binary','metrics':q.old.binary_metrics(truth,reference,reference_bundle['prior']),
            'delta_brier':cluster_delta(paired,np.zeros(len(paired)),seed=SEED+year),'note':'same paired validation cases; training cohort/task differs, not a pure learner ablation'})
        for config in CONFIGS:
            probability=paired[[f'{config}_p{k}' for k in NONOUT]].sum(axis=1).to_numpy()
            bundle=joblib.load(OUT/f'model_{year}_{role}_pa_{config}.joblib')
            binary_reference.append({'config':config,'metrics':q.old.binary_metrics(truth,probability,float(bundle['prior'][NONOUT].sum())),
                'delta_brier':cluster_delta(paired,(truth-probability)**2-(truth-reference)**2,seed=SEED+year),'note':'same paired validation cases; training cohort/task differs, not a pure learner ablation'})
    save(f'results_{year}_{role}.json',{'year':year,'role':role,'primary_n':int(primary.sum()),'observed_n':len(part),'pa':rows,'run':run,'warnings':alarms,'paired_binary_reference':binary_reference})


def select():
    rows=[];winners={}
    for role in ['SP','RP']:
        for config in CONFIGS:
            values=[next(v for v in read(OUT/f'results_{year}_{role}.json')['pa'] if v['config']==config) for year in [2022,2023]]
            rows.append({'role':role,'config':config,'failed_folds':sum(not v['predictive_gate'] for v in values),'mean_log_loss':float(np.mean([v['metrics']['log_loss'] for v in values]))})
        ranked=sorted([r for r in rows if r['role']==role],key=lambda r:(r['failed_folds'],r['mean_log_loss'],CONFIGS.index(r['config'])))
        winners[role]={'config':ranked[0]['config'],'development_predictive_support':ranked[0]['failed_folds']==0,'ranking':ranked}
    value={'selected':winners,'selection_uses2024':False};path=OUT/'selection.json'
    if path.exists():assert read(path)==value
    save('selection.json',value);print('15.5 PA research ranking frozen using2022/23 only',flush=True)


def guard():
    assert not list(OUT.glob('model_2024_*.joblib')) and not list(OUT.glob('scored_2024*'))
    paths=[OUT/'protocol.json',OUT/'selection.json']+[OUT/f'results_{year}_{role}.json' for year in [2022,2023] for role in ['SP','RP']]
    save('confirmation_guard.json',{'2024_outputs_present':False,'inputs':{p.name:q.b.digest(p) for p in paths},'status':'2024 reused diagnostic only, not independent confirmation'})


def finish():
    assert read(OUT/'protocol.json')==protocol();folds=[read(OUT/f'results_{year}_{role}.json') for year in [2022,2023,2024] for role in ['SP','RP']]
    selected=read(OUT/'selection.json');primary=[]
    for role in ['SP','RP']:
        winner=selected['selected'][role]['config'];r=next(v for v in read(OUT/f'results_2024_{role}.json')['pa'] if v['config']==winner)
        primary.append({**r,'development_predictive_support':selected['selected'][role]['development_predictive_support'],'original_system_promoted':False})
    save('summary.json',{'version':'decision_pe_models_v1','coverage':[read(f.OUT/f'coverage_{year}.json') for year in range(2021,2025)],'folds':folds,'selection':selected,'primary2024':primary,
        'balance_reference':read(f.entry.OUT/'evidence.json')['primary_folds'],'slice16_entry_allowed':False,'strategy_value_estimated':False,'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.5.4'})
    print('15.5.1-4 prediction/coverage/warnings summarized; comparison balance and16 gates unchanged',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','train','evaluate','select','guard','finish']);parser.add_argument('--year',type=int,choices=[2022,2023,2024]);parser.add_argument('--role',choices=['SP','RP']);args=parser.parse_args()
    if args.stage in ['train','evaluate']:globals()[args.stage](args.year,args.role)
    else:globals()[args.stage]()
