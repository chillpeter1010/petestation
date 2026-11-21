"""15.2 bounded common-clock model/feature/weight comparisons. Stop15.2."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import warnings
import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler,SplineTransformer
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_common_clock as c

old,n,b=c.old,c.n,c.b;ROOT=c.ROOT;OUT=ROOT/'data/research/decision_balance_revision_v1'
CORE=['inning','defense_lead','current_pitches','current_bf','entry_rest_hours','pitch_rest_hours',
    'prior_games_pitches_3d','prior_games_pitches_5d','load_relative','ability_log_n','pitcher_k_rate','pitcher_bb_rate','pitcher_hr_rate',
    'pool_rp_count','pool_pitches3','pool_rest']
STATE=['smooth_stuff','smooth_velocity','smooth_location','smooth_contact','n_stuff','n_velocity','n_location','n_contact','block_age_minutes','pool_snapshot_age_minutes']
CAT=['outs','base_state','pitcher_hand','scheduled_innings'];FULLCAT=CAT+['state_support','pool_status','history_status']
CURVES=['current_pitches','current_bf','entry_rest_hours','pitch_rest_hours']
VARIANTS=['hgb_full','logit_core','logit_full','balance_logit']
PHASES=['between_innings','within_inning'];SCHEMES=['overlap','ipw']


def read(path):return c.read(path)
def save(name,value):b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def features(year):
    f=pd.read_parquet(c.OUT/f'features_{year}.parquet')
    f['ability_log_n']=np.log1p(f.ability_n)
    f['pool_status']=np.where(f.snapshot_at.notna(),'prior_snapshot','unknown')
    f['history_status']=np.where(f.lookback_complete,'complete14d','incomplete14d')
    for name in CORE+STATE:f[name]=pd.to_numeric(f[name],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    for name in FULLCAT:f[name]=f[name].astype('string').fillna('unknown').astype(str)
    return f


def columns(variant):return (CORE,CAT) if variant=='logit_core' else (CORE+STATE,FULLCAT)


def transformer(variant):
    nums,cats=columns(variant)
    return ColumnTransformer([
        ('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),nums),
        ('curves',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),SplineTransformer(n_knots=4,degree=2,include_bias=False),StandardScaler()),CURVES),
        ('categories',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)],sparse_threshold=0.)


def balance_objective(beta,x,y,ridge=.001):
    score=x@beta;raw=expit(score);p=np.clip(raw,.001,.999)
    moment=x.T@(y/p-(1-y)/(1-p))/len(y)
    penalty=beta.copy();penalty[0]=0
    loss=.5*np.mean(moment**2)+ridge*np.dot(penalty,penalty)/2
    slope=(-y*(1-p)/p-(1-y)*p/(1-p))*((raw>.001)&(raw<.999))
    gradient=x.T@(slope*(x@moment))/(len(y)*len(moment))+ridge*penalty
    return float(loss),gradient


def fit_bundle(train,cal,variant,label):
    y=train.changed.to_numpy(int)
    if variant=='hgb_full':
        trans=ColumnTransformer([('num','passthrough',CORE+STATE),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),FULLCAT)],sparse_threshold=0.)
        model=make_pipeline(trans,HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=7,min_samples_leaf=200,l2_regularization=10.,learning_rate=.05,max_bins=63,
            early_stopping=False,random_state=old.SEED))
        model.fit(train,y);raw=np.clip(model.predict_proba(cal)[:,1],1e-6,1-1e-6)
        platt=LogisticRegression(C=1.,max_iter=200).fit(np.log(raw/(1-raw))[:,None],cal.changed)
        return {'variant':variant,'model':model,'platt':platt,'warning':False}
    trans=transformer(variant);x=trans.fit_transform(train)
    model=LogisticRegression(C=.1,max_iter=300,solver='lbfgs')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(x,y)
    warning=any(isinstance(z.message,ConvergenceWarning) for z in caught)
    result={'variant':variant,'transform':trans,'model':model,'warning':warning}
    if variant=='balance_logit':
        x=np.column_stack([np.ones(len(x)),x]);beta=np.r_[model.intercept_,model.coef_[0]];iteration=[0]
        def callback(_):
            iteration[0]+=1
            if iteration[0]%20==0:print(f'15.2 {label}: balance moment iteration{iteration[0]}',flush=True)
        fitted=minimize(balance_objective,beta,args=(x,y),jac=True,method='L-BFGS-B',bounds=[(-8.,8.)]*len(beta),callback=callback,options={'maxiter':150,'ftol':1e-9})
        result.update(beta=fitted.x,converged=bool(fitted.success),iterations=int(fitted.nit),moment_objective=float(fitted.fun),warning=warning or not fitted.success)
    return result


def predict(bundle,f):
    if bundle['variant']=='hgb_full':
        raw=np.clip(bundle['model'].predict_proba(f)[:,1],1e-6,1-1e-6)
        return bundle['platt'].predict_proba(np.log(raw/(1-raw))[:,None])[:,1]
    x=bundle['transform'].transform(f)
    if bundle['variant']=='balance_logit':return np.clip(expit(bundle['beta'][0]+x@bundle['beta'][1:]),1e-6,1-1e-6)
    return np.clip(bundle['model'].predict_proba(x)[:,1],1e-6,1-1e-6)


def balancing_weights(action,propensity,scheme):
    a=np.asarray(action,bool);p=np.asarray(propensity,float)
    if scheme=='overlap':return np.where(a,1-p,p)
    return np.where(a,1/p,1/(1-p))


def diagnostics(frame,probability,scheme):
    mask=frame.past_cell_support.to_numpy(bool).copy()
    if scheme=='ipw':mask &= (probability>=.05)&(probability<=.95)
    f=frame[mask].copy();a=f.changed.to_numpy(bool);p=probability[mask];w=balancing_weights(a,p,scheme)
    rows=[]
    # The SAME rich benchmark applies to every model, including core ablation.
    values={name:f[name].to_numpy(float) for name in CORE+STATE}
    for name in FULLCAT:
        for level in f[name].unique():values[name+'='+level]=f[name].eq(level).to_numpy(float)
    for name,x in values.items():
        finite=np.isfinite(x)
        for suffix,v,valid in [('value',x,finite),('missing',(~finite).astype(float),np.ones(len(x),bool))]:
            left=a&valid;right=~a&valid
            if left.sum()<2 or right.sum()<2:continue
            scale=np.sqrt((v[left].var()+v[right].var())/2)
            separated=scale<1e-9 and abs(v[left].mean()-v[right].mean())>1e-9
            if scale<1e-9 and not separated:continue
            if separated:scale=1e-8
            rows.append({'field':name+':'+suffix,'before':float((v[left].mean()-v[right].mean())/scale),
                'after':float((np.average(v[left],weights=w[left])-np.average(v[right],weights=w[right]))/scale),'arm_constant_separation':bool(separated)})
    maximum=max((abs(z['after']) for z in rows),default=None)
    arm1=old.weight_summary(w[a]);arm0=old.weight_summary(w[~a])
    return {'scheme':scheme,'source_n':len(frame),'retained':len(f),'change':arm1,'continue':arm0,
        'max_abs_smd_after':maximum,'over_0_1':sum(abs(z['after'])>.1 for z in rows),'balance':rows,
        'diagnostic_gate':bool(arm1['ess']>=500 and arm0['ess']>=500 and maximum is not None and maximum<=.1)}


def protocol():
    paths=[Path(__file__),c.OUT/'protocol.json',old.OUT/'manifest.json']+[c.OUT/f'features_{y}.parquet' for y in range(2021,2025)]
    return {'version':'decision_balance_revision_v1','protocol_revision':2,'superseded_diagnostic_protocol_sha256':b.digest(OUT/'attempt0_readonly_mask/protocol.json'),
        'revision_reason':'copy pandas read-only boolean mask before IPW diagnostic filtering; original2 HGB2022 fits/predictions and source/protocol retained; fit, cohort, thresholds and estimands unchanged; no2024 results yet',
        'input_sha256':{p.relative_to(ROOT).as_posix():b.digest(p) for p in paths},
        'cohort':'common-clock eligible rows from15.1; outgoing SP/RP x between/within inning separate learners; no actual next batter identity or old post-anchor WE/LI/ability borrowed',
        'columns':{'core':CORE,'state':STATE,'categorical':FULLCAT,'curves':CURVES},'variants':VARIANTS,
        'learners':'hgb_full fixed7 leaves60 natural sampling + late Platt; logit C=.1 with fixed4-knot quadratic splines and onehot category; logit_core excludes STATE and state/pool/history metadata categories but evaluated on SAME rich balance benchmark',
        'balance_logit':'regularized inverse-propensity moment calibration, g=mean[X*(A/p-(1-A)/(1-p))], minimize .5 mean(g^2)+.001||beta_nonintercept||^2; train only, p clipped.001/.999 for fit stability, beta bounded+-8, max150; not official CBPS implementation or exact balance guarantee',
        'calibration':'fit chronological first80% game-closed dates, late games cal; all training labels before next-year first anchor, spanning games excluded; only HGB calibration fits Platt, linear models keep raw probability; no oversampling',
        'targets':'PRIMARY overlap weights w(change)=1-e,w(continue)=e on cells with development >=10 each action; observational equipoise target, different from full-population ATE. SECONDARY IPW e in[.05,.95], no target chosen by results; no causal utility estimated',
        'cells':'role x phase x common-anchor pitch band x lead band, development labels only',
        'gates':'each role/phase change and continue ESS>=500 and rich maximum absolute mean SMD<=.1; arm-constant differing means are separation and use finite SD floor1e-8, never omitted; calibration ECE<=.03, no fit convergence warnings; descriptive only, unmeasured confounding/availability still unknown',
        'selection':'2022 and2023 forward scores only; one variant per outgoing role, both phases use same variant. Rank first by number of failing phase/year gates, then mean worst SMD, then mean log loss, then fixed variant order. Freeze ranking before2024 confirmation; no 2024 retuning',
        'limits':'2024 already used for diagnosing old study, not independent test; no RP horizon/observation fit, candidate refits, action-value changes or strategy/causal evaluation; labels and missing-reason audits never predictors',
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'stop':'15.2'}


def freeze():
    OUT.mkdir(exist_ok=True);value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value
    save('protocol.json',value);print('15.2 fixed4 learners, rich benchmark and distinct weight targets frozen before fitting',flush=True)


def train(year,role):
    assert read(OUT/'protocol.json')==protocol()
    past=pd.concat([features(y) for y in range(2021,year)],ignore_index=True);past=past[past.role.eq(role)&past.game_closed_at.lt(pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp())]
    valid=features(year);valid=valid[valid.role.eq(role)].reset_index(drop=True);rows=[]
    # One development cell support screen shared across variants and weight targets.
    support=past.groupby('cell').changed.agg(['sum','count']);support['support']=support['sum'].ge(10)&(support['count']-support['sum']).ge(10)
    valid['past_cell_support']=valid.cell.map(support.support).fillna(False).astype(bool)
    write(support.reset_index(),f'cell_support_{year}_{role}.parquet')
    with threadpool_limits(limits=2):
        for phase in PHASES:
            subset=past[past.phase.eq(phase)];fit,cal,flow=old.partition(subset);v=valid[valid.phase.eq(phase)].reset_index(drop=True)
            assert cal.game_closed_at.max()<v.anchor_at.min()
            split=pd.concat([f[['decision_id','game_pk','anchor_at','game_closed_at']].assign(partition=part) for part,f in [('fit',fit),('calibration',cal)]],ignore_index=True)
            write(split,f'split_{year}_{role}_{phase}.parquet')
            for variant in VARIANTS:
                label=f'{year}/{role}/{phase}/{variant}';print(f'15.2 {label}: {len(fit):,} fit/{len(cal):,} cal/{len(v):,} validation',flush=True)
                bundle=fit_bundle(fit,cal,variant,label);prob=predict(bundle,v)
                joblib.dump(bundle,OUT/f'model_{year}_{role}_{phase}_{variant}.joblib')
                scored=v[['decision_id','game_pk','appearance_id','outgoing_pitcher_id','role','phase','anchor_at','changed','past_cell_support']].copy()
                scored['propensity']=prob;write(scored,f'scored_{year}_{role}_{phase}_{variant}.parquet')
                metrics=old.binary_metrics(v.changed.to_numpy(int),prob,float(fit.changed.mean()))
                for scheme in SCHEMES:
                    d=diagnostics(v,prob,scheme);d.update({'year':year,'role':role,'phase':phase,'variant':variant,'metrics':metrics,'warning':bundle['warning'],'flow':flow,
                        'fit_last_label':float(fit.game_closed_at.max()),'cal_first_anchor':float(cal.anchor_at.min()),'cal_last_label':float(cal.game_closed_at.max()),'validation_first_anchor':float(v.anchor_at.min())})
                    d['full_gate']=bool(d['diagnostic_gate'] and metrics['ece']<=.03 and not bundle['warning']);rows.append(d)
                maximum=rows[-2]['max_abs_smd_after']
                print(f'15.2 {label}: overlap SMD {maximum if maximum is not None else "unknown"}, convergence warning={bundle["warning"]}',flush=True)
    save(f'results_{year}_{role}.json',{'year':year,'role':role,'rows':rows,'test2025_outcomes_examined':False})


def select():
    assert read(OUT/'protocol.json')==protocol();rows=[];winners={};ranking={}
    for role in ['SP','RP']:
        inner=sum([read(OUT/f'results_{year}_{role}.json')['rows'] for year in [2022,2023]],[])
        for variant in VARIANTS:
            r=[x for x in inner if x['variant']==variant and x['scheme']=='overlap']
            rows.append({'role':role,'variant':variant,'failing_phase_years':sum(not x['full_gate'] for x in r),
                'mean_max_smd':float(np.mean([x['max_abs_smd_after'] if x['max_abs_smd_after'] is not None else 1e6 for x in r])),'mean_LL':float(np.mean([x['metrics']['log_loss'] for x in r]))})
        ordered=sorted([x for x in rows if x['role']==role],key=lambda x:(x['failing_phase_years'],x['mean_max_smd'],x['mean_LL'],VARIANTS.index(x['variant'])))
        ranking[role]=ordered;winners[role]={'variant':ordered[0]['variant'],'training_all_gates_passed':ordered[0]['failing_phase_years']==0}
    value={'winners':winners,'ranking':ranking,'2024_used_for_selection':False,'primary_estimand':'overlap equipoise population; not original full-population IPW ATE'}
    path=OUT/'selection.json'
    if path.exists():assert read(path)==value
    save('selection.json',value);print('15.2 inner2022/23 ranking frozen before2024 results',flush=True)


def finish():
    assert read(OUT/'protocol.json')==protocol();selection=read(OUT/'selection.json');selected=[];allrows=[]
    for role in ['SP','RP']:
        for year in [2022,2023,2024]:allrows+=read(OUT/f'results_{year}_{role}.json')['rows']
        variant=selection['winners'][role]['variant'];rows=[x for x in allrows if x['year']==2024 and x['role']==role and x['variant']==variant]
        primary=[x for x in rows if x['scheme']=='overlap']
        selected.append({'role':role,'variant':variant,'training_all_gates_passed':selection['winners'][role]['training_all_gates_passed'],
            'diagnostic2024_all_gates_passed':all(x['full_gate'] for x in primary),'phases':rows,'promoted':False})
    save('summary.json',{'version':'decision_balance_revision_v1','selection':selection,'selected':selected,'all_results':allrows,
        'foundation':[read(c.OUT/f'preparation_{y}.json') for y in range(2021,2025)],
        'missing_audits':[read(c.OUT/f'missing_audit_{y}.json') for y in range(2021,2025)],
        'interpretation':'new common-clock cohort and overlap target differ from old15; do not claim causal or predictive efficacy from balance or compare raw retained counts as same target; no new alert generation',
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.2'})
    print('15.2 confirmation summarized; model/value/recommendation promotion remains closed',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','train','select','finish']);parser.add_argument('--year',type=int,choices=[2022,2023,2024]);parser.add_argument('--role',choices=['SP','RP']);args=parser.parse_args()
    if args.stage=='train':train(args.year,args.role)
    else:globals()[args.stage]()
