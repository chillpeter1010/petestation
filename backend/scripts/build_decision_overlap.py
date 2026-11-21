"""Slice15: temporal action/observation propensities and nominal RP choice support.

Research overlap diagnostics only. No outcome-value model, policy promotion,
2025 outcomes, browser work, or edits to previous frozen research.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize,minimize_scalar
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,log_loss,roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OrdinalEncoder,StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_signal_calibration as n
from scripts import build_decision_signal_models as m

b=n.b;ROOT=b.ROOT;OUT=ROOT/'data/research/decision_overlap_v1';SEED=20261119
NUM=['inning','defense_lead','outs','current_pitches','current_bf','research_pa_li','research_home_we',
    'candidate_count','rp_count','pool_pitches3','pool_rest','pitcher_k_rate','pitcher_bb_rate','batter_k_rate','batter_hr_rate',
    'prior_games_pitches_3d','prior_games_pitches_5d','entry_rest_hours','consecutive_days',
    'A_drift_stuff','A_drift_velocity','B_drift_location','C_drift_contact','D_severity','block_age_minutes']
CAT=['half','base_state','pitcher_hand','expected_stand']
CHOICE=['pitches_1d_before','pitches_3d_before','pitches_7d_before','previous_session_pitches','hours_since_last_pitch',
    'prior_observed_relief','prior_observed_starts','consecutive_days_before','appeared_earlier_today','lookback_14d_complete']
TRIMS=[.01,.05,.1];CAPS=[None,10.,20.,50.]


def read(path):return n.read(path)
def save(name,value):b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def cells(frame):
    inning=pd.cut(frame.inning,[-np.inf,3,6,9,np.inf],labels=['1-3','4-6','7-9','10+']).astype(str)
    pitches=pd.cut(frame.current_pitches,[-np.inf,29,59,89,np.inf],labels=['0-29','30-59','60-89','90+']).astype(str)
    li=pd.cut(frame.research_pa_li,[-np.inf,1,2,np.inf],right=False,labels=['low','medium','high']).astype('string').fillna('unknown')
    return frame.role.astype(str)+':'+inning+':'+pitches+':'+li


def prepare(year):
    OUT.mkdir(parents=True,exist_ok=True)
    print(f'Slice15 {year}: reading legal-boundary sources',flush=True)
    with n.r.connect() as c:
        for folder,name in [(n.old.FOUNDATION,'decisions'),(n.old.FOUNDATION,'plays'),(n.b.SAMPLE,'decision_audit'),
                (n.b.SAMPLE,'decision_candidates'),(n.b.PREP,'prepared_features'),(n.b.TEMPORAL,'context_features'),
                (n.r.OUT,'workload_features')]:c.read_parquet(str(folder/f'{name}_{year}.parquet')).create_view(name)
        c.execute('''CREATE TEMP TABLE closed AS SELECT game_pk,max(epoch(try_cast(end_time AS TIMESTAMPTZ))) game_closed_at FROM plays GROUP BY game_pk''')
        c.execute("CREATE TEMP TABLE pool AS SELECT * FROM decision_candidates WHERE nominal_eligible AND previous_role='RP' AND prior_observed_relief>0")
        c.execute('''CREATE TEMP TABLE pool_summary AS SELECT decision_id,count(*) rp_count,median(pitches_3d_before) pool_pitches3,
            median(hours_since_last_pitch) pool_rest FROM pool GROUP BY decision_id''')
        c.execute('CREATE TEMP TABLE current_workload AS SELECT * FROM workload_features WHERE is_current')
        frame=c.execute('''SELECT d.year,d.game_pk,d.decision_id,d.team_id,d.appearance_id,d.outgoing_pitcher_id,d.batter_id,
            a.role,a.cohort_reason,cf.decision_at,d.inning,d.half,p.scheduled_innings,
            CASE WHEN d.half='top' THEN d.home_score-d.away_score ELSE d.away_score-d.home_score END defense_lead,
            d.outs,d.base_state,d.current_pitches,d.current_bf,cf.research_pa_li,cf.research_home_we,
            a.candidate_count,s.rp_count,s.pool_pitches3,s.pool_rest,
            f.pitcher_hand,f.expected_stand,f.pitcher_k_rate,f.pitcher_bb_rate,f.batter_k_rate,f.batter_hr_rate,
            f.pitcher_history_available_at,f.batter_history_available_at,
            w.prior_games_pitches_3d,w.prior_games_pitches_5d,w.consecutive_days,w.entry_rest_hours,w.lookback_14d_complete,
            cast(d.observed_change AS INTEGER) changed,d.incoming_pitcher_id,closed.game_closed_at,
            d.current_pitches option_game_pitches,d.outgoing_pitcher_id option_pitcher_id,a.role forecast_role,true is_current
            FROM decision_audit a JOIN decisions d USING(decision_id) JOIN plays p ON p.outcome_key=d.outcome_key
            JOIN context_features cf USING(decision_id) JOIN closed ON closed.game_pk=d.game_pk
            LEFT JOIN prepared_features f USING(decision_id) LEFT JOIN pool_summary s USING(decision_id)
            LEFT JOIN current_workload w ON w.decision_id=d.decision_id
            WHERE a.cohort_reason IN('included','observed_replacement_outside_nominal_set')
            ORDER BY d.game_pk,d.at_bat_number,d.event_index''').fetchdf()
        assert frame.decision_id.is_unique and frame.game_closed_at.notna().all()
        print(f'Slice15 {year}: {len(frame):,} boundary rows joined; attaching past-only states',flush=True)
        # This study always observes the outgoing actor, unlike the older
        # outcome dataset which switches to the actually incoming actor.
        c.read_parquet(str(n.r.OUT/'appearance_history.parquet')).create_view('appearance')
        c.read_parquet(str(n.OUT/f'block_scores_{year}.parquet')).filter(f'alpha={n.ALPHA}').create_view('scored')
        c.execute('''CREATE TEMP TABLE load_reference AS SELECT pitcher_id,role,available_at,
            median(actual_pitches) OVER win median_pitches,count(*) OVER win history_n FROM appearance
            WHERE available_at IS NOT NULL AND NOT bad_timing AND actual_pitches>0
            WINDOW win AS(PARTITION BY pitcher_id,role ORDER BY available_at,appearance_id ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)''')
        c.register('base',frame)
        c.execute('''CREATE TEMP TABLE state_requests AS SELECT q.decision_id,q.decision_at,q.appearance_id,q.outgoing_pitcher_id,q.role,a.entry_at reference_clock
            FROM base q JOIN appearance a ON q.appearance_id=a.appearance_id''')
        fields=['block_id','block_number','session_id','available_at','personal_reference_at']+[g+s for g in 'ABC' for s in ['_state','_severity']]
        fields += ['smooth_stuff','smooth_velocity','smooth_location','smooth_contact']
        added=c.execute('''SELECT q.decision_id,q.reference_clock,'''+','.join('s.'+x for x in fields)+''',
            h.available_at D_reference_at,h.median_pitches,h.history_n FROM state_requests q
            ASOF LEFT JOIN scored s ON q.appearance_id=s.appearance_id AND q.decision_at>s.available_at
            ASOF LEFT JOIN load_reference h ON q.outgoing_pitcher_id=h.pitcher_id AND q.role=h.role AND q.reference_clock>h.available_at''').fetchdf()
        attached=frame.merge(added,on='decision_id',how='left',validate='one_to_one')
        for target,source in [('A_drift_stuff','smooth_stuff'),('A_drift_velocity','smooth_velocity'),('B_drift_location','smooth_location'),('C_drift_contact','smooth_contact')]:attached[target]=attached[source]
        attached['load_relative']=attached.current_pitches/attached.median_pitches
        attached['recent72_relative']=attached.prior_games_pitches_3d/attached.median_pitches
        attached['recent120_relative']=attached.prior_games_pitches_5d/attached.median_pitches
        attached['streak']=attached.consecutive_days;attached['short_rest']=-np.log1p(attached.entry_rest_hours.clip(lower=0))
        attached['load_known']=attached.history_n.ge(5)&attached.lookback_14d_complete.fillna(False)&np.isfinite(attached[n.LOAD]).all(axis=1)
        attached['block_age_minutes']=(attached.decision_at-attached.available_at)/60
        for g in 'ABC':attached[g+'_state']=attached[g+'_state'].fillna(-1).astype(int)
        attached=m.apply_load(attached,year)
        keep=list(frame.columns)+[x for x in attached if x not in frame and (x in NUM or x.endswith('_state') or x in ['block_id','block_number','session_id','available_at','personal_reference_at','reference_clock','D_reference_at'])]
        frame=attached[keep].copy();frame['cell']=cells(frame)
        print(f'Slice15 {year}: current-actor states ready; preparing nominal RP choices and future-observation labels',flush=True)
        c.register('requests',frame)
        candidates=c.execute('''SELECT p.*,q.role,q.incoming_pitcher_id,q.changed,q.game_closed_at,q.decision_at,q.cell,
            cast(q.changed=1 AND p.pitcher_id=q.incoming_pitcher_id AS INTEGER) chosen
            FROM pool p JOIN requests q USING(decision_id) ORDER BY q.decision_id,p.pitcher_id''').fetchdf()
        counts=candidates.groupby('decision_id').chosen.sum()
        frame['choice_observed']=frame.decision_id.map(counts).fillna(0).eq(1)
        scores=pd.read_parquet(n.OUT/f'block_scores_{year}.parquet');scores=scores[scores.alpha.eq(n.ALPHA)]
        risk=frame[frame.block_id.notna()].sort_values(['decision_at','decision_id']).drop_duplicates('block_id',keep='first').copy()
        c.register('risk',risk);c.register('future',scores)
        target=c.execute('''SELECT q.decision_id,s.anchor_at target_anchor,s.available_at target_at,s.block_number target_block,
            s.residual_stuff,s.residual_velocity,s.residual_location FROM risk q ASOF LEFT JOIN future s
            ON q.session_id=s.session_id AND q.decision_at<=s.anchor_at''').fetchdf()
    risk=risk.merge(target,on='decision_id',validate='one_to_one')
    known=risk[['residual_stuff','residual_velocity','residual_location']].notna().all(axis=1)&risk.target_block.le(risk.block_number+2)
    risk['future_observed']=known.astype(int)
    risk['future_bad']=np.where(known,risk.residual_stuff.le(-5)|risk.residual_velocity.le(-.5)|risk.residual_location.le(-5),np.nan)
    risk['complete']=risk[[g+'_state' for g in 'ABCD']].ge(0).all(axis=1)
    risk['two_red']=risk.complete&(risk[[g+'_state' for g in 'ABCD']].eq(2).sum(axis=1)>=2)&(risk.A_state.eq(2)|risk.B_state.eq(2))
    assert (risk.loc[known,'target_anchor']>=risk.loc[known,'decision_at']).all()
    for col in ['last_pitch_epoch','history_closed_epoch','prior_state_available_at']:
        assert (candidates[col].dropna()<candidates.loc[candidates[col].notna(),'decision_at']).all(),col
    write(frame,f'boundaries_{year}.parquet');write(candidates,f'candidates_{year}.parquet');write(risk,f'monitoring_{year}.parquet')
    save(f'preparation_{year}.json',{'year':year,'boundaries':len(frame),'changes':int(frame.changed.sum()),'restored_out_of_nominal':int(frame.cohort_reason.ne('included').sum()),
        'nominal_rp_rows':len(candidates),'changes_with_choice_in_pool':int((frame.changed.eq(1)&frame.choice_observed).sum()),
        'monitoring':len(risk),'future_observed':int(known.sum()),'two_red':int(risk.two_red.sum()),'test2025_outcomes_examined':False})
    print(f'Slice15 {year}: {len(frame):,} boundaries, {int(frame.changed.sum()):,} changes; {len(risk):,} first-block monitoring opportunities',flush=True)


def protocol():
    paths=[Path(__file__),n.OUT/'normal_protocol.json',n.OUT/'feature_protocol.json',n.OUT/'episode_protocol.json',n.OUT/'manifest.json',n.r.OUT/'appearance_history.parquet']
    for y in range(2021,2025):
        paths += [OUT/f'{name}_{y}.parquet' for name in ['boundaries','candidates','monitoring']]
        paths += [folder/f'{name}_{y}.parquet' for folder,name in [(b.SAMPLE,'decision_audit'),(b.PREP,'prepared_features'),(b.SAMPLE,'decision_candidates')]]
        paths += [folder/f'{name}_{y}.parquet' for folder,name in [(n.old.FOUNDATION,'decisions'),(n.old.FOUNDATION,'plays'),(b.TEMPORAL,'context_features'),(n.r.OUT,'workload_features'),(n.OUT,'block_scores')]]
    return {'version':'decision_overlap_v1','protocol_revision':2,'superseded_pre_fit_protocol_sha256':b.digest(OUT/'attempt0_nullable_dtype/protocol.json'),
        'revision_reason':'numeric nullable dtypes normalized to float NaN before sklearn; no fitted models/predictions in attempt0; thresholds, labels and estimands unchanged',
        'input_sha256':{p.relative_to(ROOT).as_posix():b.digest(p) for p in paths},
        'scope':'2021-24 only, inherited retrospective legal/identity/completed-play cohort plus restored observed-outside-nominal actions; no organic-result/transition/label-availability filter; not deployment population',
        'folds':'strict forward2021->2022,2021-22->2023,2021-23->2024; internal first80% whole-game-close dates fit, late games calibrate, spanning games excluded; all training labels/game closes strictly before validation first decision',
        'binary_features':NUM+CAT,'binary':'fixed HGB7 leaves/60 iterations, min leaf200 L2=10 learning_rate=.05; natural unweighted boundary sampling, no class balance; Platt logistic C=1 on disjoint late-time calibration; per outgoing SP/RP',
        'choice_features':CHOICE,'choice':'conditional linear softmax with training-only median imputation/missing flags/standardization, L2=.01, max150; one group per observed change with observed incoming in nominal RP pool; late-time temperature .5..3; no player IDs as predictors',
        'pool':'nominal_eligible, previous_role=RP, prior_observed_relief>0; actors outside this pool counted separately, never forced to uniform probability; candidate support depends on chosen actor, not outgoing row',
        'labels':'A=official observed change; R=ENTIRELY future first full measured block with anchor>=decision_at and number<=source+2 and all three residuals valid; missing future deviation censored, R=0 is unobserved not healthy; conservative game_closed_at as label available time',
        'monitoring':'first legal boundary per completed source block, no repeated PA read as independent sample; all predecision four-group unknowns retained',
        'overlap':{'action_trims':TRIMS,'primary':.05,'caps':CAPS,'weight':'unstabilized inverse observed-action propensity; report both arms separately; R inverse-observation weight only observed rows, primary R>=.1',
            'cells':'outgoing role x inning1-3/4-6/7-9/10+ x pitches0-29/30-59/60-89/90+ x LI<1/[1,2)/>=2/unknown; development both actions>=10; flag changes before outcome exposure',
            'candidate':'conditional choice>=.02, joint P(change)*P(actor|change)>=.005, own development selected>=20, past RP appearances>=5, development cell support; historical warmup/active unknown never actionable',
            'diagnostic_minimum':'per role>=500 weighted ESS each arm and maximum absolute measured numeric/missing/categorical mean SMD<=.1 after primary trim; descriptive support only, no unmeasured-confounding claim'},
        'selection_diagnostic':'2024 two-red IP-observation weighted future-deviation contrast, compare weighted flags vs all four-supported monitoring; R>=.1, caps None/10/20/50, fixed-model200 paired game x pitcher Poisson draws recompute ratios; flag/appearance>=20/10 and >=190 valid draws for interpretable interval; no promotion',
        'limits':'observational MAR/exchangeability untestable; relief warmup/health/availability missing; no propensity model fixes unseen outcomes, forced changes or unmeasured staff judgement; local selection model does not measure strategy value',
        'method_references':['https://miguelhernan.org/whatifbook','https://pmc.ncbi.nlm.nih.gov/articles/PMC3144483/'],
        'recommendation_allowed':False,'individual_ranking_allowed':False,'test2025_outcomes_examined':False,'stop':'15'}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value,'New research revision required'
    save('protocol.json',value);print('Slice15 methods, thresholds and sources frozen before fitting',flush=True)


def partition(frame):
    dates=frame.groupby('game_pk').game_closed_at.max().sort_values().to_numpy()
    boundary=float(np.floor(dates[int(.8*len(dates))]/86400)*86400)
    games=frame.groupby('game_pk').agg(first=('decision_at','min'),last=('game_closed_at','max'))
    spanning=set(games.index[(games['first']<boundary)&(games['last']>=boundary)])
    fit=frame[frame.game_closed_at.lt(boundary)&~frame.game_pk.isin(spanning)].copy()
    cal=frame[frame.decision_at.ge(boundary)&~frame.game_pk.isin(spanning)].copy()
    assert len(fit)>100 and len(cal)>100 and fit.game_closed_at.max()<cal.decision_at.min()
    return fit,cal,{'boundary':boundary,'fit_n':len(fit),'calibration_n':len(cal),'spanning_games_excluded':len(spanning)}


def design(frame):
    f=frame[NUM+CAT].copy()
    for key in NUM:f[key]=pd.to_numeric(f[key],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    for key in CAT:f[key]=f[key].astype('string').fillna('unknown').astype(str)
    return f


def binary_fit(fit,cal,label):
    transform=ColumnTransformer([('num','passthrough',NUM),('cat',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=np.nan,encoded_missing_value=np.nan),CAT)],sparse_threshold=0)
    model=make_pipeline(transform,HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=7,min_samples_leaf=200,l2_regularization=10.,learning_rate=.05,
        max_bins=63,categorical_features=list(range(len(NUM),len(NUM)+len(CAT))),early_stopping=False,random_state=SEED))
    model.fit(design(fit),fit[label]);raw=np.clip(model.predict_proba(design(cal))[:,1],1e-6,1-1e-6)
    platt=LogisticRegression(C=1.,max_iter=200).fit(np.log(raw/(1-raw))[:,None],cal[label])
    return {'model':model,'platt':platt,'prior':float(fit[label].mean())}


def binary_predict(bundle,frame):
    raw=np.clip(bundle['model'].predict_proba(design(frame))[:,1],1e-6,1-1e-6)
    return bundle['platt'].predict_proba(np.log(raw/(1-raw))[:,None])[:,1]


def softmax_groups(utility,groups):
    _,inverse=np.unique(groups,return_inverse=True);maximum=np.full(inverse.max()+1,-np.inf)
    np.maximum.at(maximum,inverse,utility);e=np.exp(utility-maximum[inverse])
    return e/np.bincount(inverse,weights=e)[inverse]


def choice_fit(fit,cal):
    transform=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler())
    x=transform.fit_transform(fit[CHOICE].astype(float));y=fit.chosen.to_numpy(float);groups=pd.factorize(fit.decision_id)[0]
    count=fit.decision_id.nunique()
    def objective(beta):
        prob=softmax_groups(x@beta,groups);loss=-np.log(np.clip(prob[y==1],1e-12,1)).mean()+.01*np.dot(beta,beta)/2
        grad=x.T@(prob-y)/count+.01*beta
        return loss,grad
    result=minimize(objective,np.zeros(x.shape[1]),jac=True,method='L-BFGS-B',options={'maxiter':150,'ftol':1e-9})
    assert result.success,result.message
    cx=transform.transform(cal[CHOICE].astype(float));cy=cal.chosen.to_numpy(bool);cg=pd.factorize(cal.decision_id)[0]
    optimum=minimize_scalar(lambda t:float(-np.log(np.clip(softmax_groups(cx@result.x/t,cg)[cy],1e-12,1)).mean()),bounds=(.5,3.),method='bounded')
    return {'transform':transform,'coef':result.x,'temperature':float(optimum.x),'converged':bool(result.success)}


def choice_predict(bundle,frame):
    return softmax_groups(bundle['transform'].transform(frame[CHOICE].astype(float))@bundle['coef']/bundle['temperature'],frame.decision_id.to_numpy())


def binary_metrics(y,prob,prior):
    bins=[]
    for low in np.arange(0,1,.1):
        mask=(prob>=low)&(prob<low+.1)
        if mask.any():bins.append({'lower':float(low),'n':int(mask.sum()),'predicted':float(prob[mask].mean()),'observed':float(np.mean(y[mask]))})
    return {'n':len(y),'events':int(np.sum(y)),'prevalence':float(np.mean(y)),'brier':float(brier_score_loss(y,prob)),
        'constant_brier':float(np.mean((y-prior)**2)),'log_loss':float(log_loss(y,prob,labels=[0,1])),'auc':float(roc_auc_score(y,prob)) if len(np.unique(y))==2 else None,
        'ece':float(sum(z['n']*abs(z['predicted']-z['observed']) for z in bins)/len(y)),'calibration':bins}


def fit(year,role):
    assert read(OUT/'protocol.json')==protocol()
    end=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp();parts={}
    for kind in ['boundaries','monitoring','candidates']:
        development=pd.concat([pd.read_parquet(OUT/f'{kind}_{y}.parquet') for y in range(2021,year)],ignore_index=True)
        development=development[development.role.eq(role)&development.game_closed_at.lt(end)]
        validation=pd.read_parquet(OUT/f'{kind}_{year}.parquet');validation=validation[validation.role.eq(role)].reset_index(drop=True)
        if kind=='candidates':
            good=development.groupby('decision_id').chosen.sum();development=development[development.decision_id.isin(good.index[good.eq(1)])]
        training,cal,flow=partition(development)
        assert cal.game_closed_at.max()<validation.decision_at.min()
        ledger=pd.concat([z[['decision_id','game_pk','decision_at','game_closed_at']].drop_duplicates().assign(partition=name) for name,z in [('fit',training),('calibration',cal)]],ignore_index=True)
        write(ledger,f'split_{year}_{role}_{kind}.parquet')
        print(f'Slice15 {year}/{role}/{kind}: {len(training):,} fit, {len(cal):,} cal, {len(validation):,} validation',flush=True)
        with threadpool_limits(limits=2):
            if kind=='candidates':
                bundle=choice_fit(training,cal);validation['choice_probability']=choice_predict(bundle,validation)
                counts=development[development.chosen.eq(1)].groupby('pitcher_id').size();validation['prior_selected']=validation.pitcher_id.map(counts).fillna(0).astype(int)
                chosen=validation[validation.chosen.eq(1)];sizes=validation.groupby('decision_id').size()
                metrics={'groups':int(validation.decision_id.nunique()),'observed_in_pool':len(chosen),'selected_log_loss':float(-np.log(chosen.choice_probability).mean()),
                    'uniform_log_loss':float(np.log(chosen.decision_id.map(sizes)).mean()),'temperature':bundle['temperature'],'converged':bundle['converged']}
            else:
                label='changed' if kind=='boundaries' else 'future_observed';bundle=binary_fit(training,cal,label)
                validation['propensity']=binary_predict(bundle,validation)
                metrics=binary_metrics(validation[label].to_numpy(int),validation.propensity.to_numpy(),bundle['prior'])
                if kind=='boundaries':
                    support=development.groupby('cell').changed.agg(['sum','count']);support['support']=(support['sum']>=10)&((support['count']-support['sum'])>=10)
                    validation['past_cell_support']=validation.cell.map(support.support).fillna(False).astype(bool)
                    write(support.reset_index(),f'cell_support_{year}_{role}.parquet')
            joblib.dump(bundle,OUT/f'model_{year}_{role}_{kind}.joblib')
        write(validation,f'scored_{year}_{role}_{kind}.parquet');parts[kind]={'flow':flow,'metrics':metrics,'fit_last_label':float(training.game_closed_at.max()),'cal_first_decision':float(cal.decision_at.min()),'cal_last_label':float(cal.game_closed_at.max()),'validation_first_decision':float(validation.decision_at.min())}
    save(f'fit_{year}_{role}.json',{'year':year,'role':role,'parts':parts,'test2025_outcomes_examined':False})


def ess(weights):
    weights=np.asarray(weights,float);return float(weights.sum()**2/(weights@weights)) if len(weights) and (weights@weights)>0 else 0.


def cap_weights(weights,cap):return np.minimum(weights,cap) if cap is not None else weights


def weight_summary(weights):
    w=np.asarray(weights,float)
    return {'n':len(w),'ess':ess(w),'max':float(w.max()) if len(w) else None,'q99':float(np.quantile(w,.99)) if len(w) else None,'sum':float(w.sum())}


def balance(frame,weights):
    output=[];a=frame.changed.to_numpy(bool);w=np.asarray(weights,float)
    f=frame.copy();names=list(NUM)
    for key in CAT:
        values=f[key].astype('string').fillna('unknown')
        for level in values.unique():
            name=key+'='+str(level);f[name]=values.eq(level).astype(float);names.append(name)
    for name in names:
        v=f[name].to_numpy(float);valid=np.isfinite(v)
        for variant,x,mask in [('value',v,valid),('missing',(~valid).astype(float),np.ones(len(v),bool))]:
            a1=a&mask;a0=~a&mask
            if a1.sum()<2 or a0.sum()<2:continue
            scale=np.sqrt((x[a1].var()+x[a0].var())/2)
            if scale<1e-9:continue
            output.append({'field':name+':'+variant,'before':float((x[a1].mean()-x[a0].mean())/scale),
                'after':float((np.average(x[a1],weights=w[a1])-np.average(x[a0],weights=w[a0]))/scale)})
    return output


def observation_balance(frame,cap):
    f=frame[frame.complete&frame.propensity.ge(.1)].copy();observed=f.future_observed.eq(1).to_numpy()
    w=cap_weights(1/f.loc[observed,'propensity'].to_numpy(),cap);output=[]
    names=list(NUM)
    for key in CAT:
        values=f[key].astype('string').fillna('unknown')
        for level in values.unique():
            name=key+'='+str(level);f[name]=values.eq(level).astype(float);names.append(name)
    for name in names:
        x=f[name].to_numpy(float);finite=np.isfinite(x)
        for suffix,value,valid in [('value',x,finite),('missing',(~finite).astype(float),np.ones(len(f),bool))]:
            selected=valid&observed;scale=value[valid].std() if valid.any() else 0.
            if selected.sum()<2 or scale<1e-9:continue
            ow=w[valid[observed]]
            output.append({'field':name+':'+suffix,'before':float((value[selected].mean()-value[valid].mean())/scale),
                'after':float((np.average(value[selected],weights=ow)-value[valid].mean())/scale)})
    return {'target_n':len(f),'observed_n':int(observed.sum()),'observed_ess':ess(w),'max_abs_smd_after':max((abs(x['after']) for x in output),default=None),'balance':output}


def weighted_contrast(frame,cap):
    f=frame[frame.complete&frame.future_observed.eq(1)&frame.propensity.ge(.1)].copy()
    flag=f.two_red.to_numpy(bool);y=f.future_bad.to_numpy(float);w=cap_weights(1/f.propensity.to_numpy(),cap)
    if not flag.any():return {'n':len(f),'flagged':0,'difference':None,'interval':None,'valid_draws':0,'supported':False}
    def contrast(multiplier):
        z=w*multiplier
        if z.sum()<=0 or z[flag].sum()<=0:return np.nan
        return np.average(y[flag],weights=z[flag])-np.average(y,weights=z)
    games,_=pd.factorize(f.game_pk);pitchers,_=pd.factorize(f.outgoing_pitcher_id);rng=np.random.default_rng(SEED);boot=[]
    for _ in range(200):boot.append(contrast(rng.poisson(1,games.max()+1)[games]*rng.poisson(1,pitchers.max()+1)[pitchers]))
    boot=np.array(boot);valid=boot[np.isfinite(boot)];apps=int(f.loc[flag,'appearance_id'].nunique())
    enough=int(flag.sum())>=20 and apps>=10 and len(valid)>=190
    return {'n':len(f),'flagged':int(flag.sum()),'appearances':apps,'observed_flag_risk':float(np.average(y[flag],weights=w[flag])),
        'observed_reference_risk':float(np.average(y,weights=w)),'difference':float(contrast(np.ones(len(f)))),
        'interval':np.quantile(valid,[.025,.975]).tolist() if enough else None,'valid_draws':len(valid),'supported':bool(enough),
        'flag_ess':ess(w[flag]),'overall_ess':ess(w),'inference':'descriptive MAR-based sensitivity; fixed models, not a causal or model-promotion test'}


def evaluate():
    assert read(OUT/'protocol.json')==protocol()
    tables=[];roles=[];combos=[];candidate_reports=[]
    for year in [2022,2023,2024]:
        for role in ['SP','RP']:
            frame=pd.read_parquet(OUT/f'scored_{year}_{role}_boundaries.parquet');observation=pd.read_parquet(OUT/f'scored_{year}_{role}_monitoring.parquet')
            fitted=read(OUT/f'fit_{year}_{role}.json');trimrows=[]
            for trim in TRIMS:
                keep=frame.propensity.between(trim,1-trim)&frame.past_cell_support;g=frame[keep]
                a=g.changed.to_numpy(bool);prob=g.propensity.to_numpy();w=np.where(a,1/prob,1/(1-prob))
                for cap in CAPS:
                    weight=cap_weights(w,cap);sm=balance(g,weight)
                    item={'year':year,'role':role,'trim':trim,'cap':cap,'source_n':len(frame),'retained':len(g),'retained_fraction':len(g)/len(frame),
                        'change':weight_summary(weight[a]),'continue':weight_summary(weight[~a]),'combined':weight_summary(weight),
                        'max_abs_smd_after':max((abs(x['after']) for x in sm),default=None),'balance':sm}
                    item['diagnostic_gate']=bool(item['change']['ess']>=500 and item['continue']['ess']>=500 and item['max_abs_smd_after'] is not None and item['max_abs_smd_after']<=.1)
                    trimrows.append(item)
            tables+=trimrows
            roles.append({'year':year,'role':role,'action':fitted['parts']['boundaries']['metrics'],'observation':fitted['parts']['monitoring']['metrics'],
                'primary':next(x for x in trimrows if x['trim']==.05 and x['cap'] is None),
                'monitoring_n':len(observation),'full_four':int(observation.complete.sum()),'missing_future':int(observation.future_observed.eq(0).sum()),
                'observed_under_g10':int((observation.future_observed.eq(1)&observation.propensity.lt(.1)).sum()),
                'observation_balance':[{'cap':cap,**observation_balance(observation,cap)} for cap in CAPS],
                'observed_weights':[{'cap':cap,**weight_summary(cap_weights(1/observation.loc[observation.future_observed.eq(1)&observation.propensity.ge(.1),'propensity'].to_numpy(),cap))} for cap in CAPS]})
            candidates=pd.read_parquet(OUT/f'scored_{year}_{role}_candidates.parquet')
            candidates=candidates.merge(frame[['decision_id','propensity','past_cell_support']],on='decision_id',validate='many_to_one')
            candidates['joint_probability']=candidates.propensity*candidates.choice_probability
            candidates['statistical_support']=candidates.choice_probability.ge(.02)&candidates.joint_probability.ge(.005)&candidates.prior_selected.ge(20)&candidates.prior_observed_relief.ge(5)&candidates.past_cell_support
            chosen=candidates[candidates.chosen.eq(1)];supported=chosen[chosen.statistical_support]
            candidate_reports.append({'year':year,'role':role,**fitted['parts']['candidates']['metrics'],'pool_rows':len(candidates),
                'statistically_supported_options':int(candidates.statistical_support.sum()),'changes':int(frame.changed.sum()),'changes_outside_rp_pool':int(frame.changed.sum()-len(chosen)),
                'chosen_supported':len(supported),'choice_weights':weight_summary(1/chosen.choice_probability.to_numpy()),
                'joint_weight_sensitivity':[{'cap':cap,**weight_summary(cap_weights(1/supported.joint_probability.to_numpy(),cap))} for cap in CAPS],
                'operationally_available':0,'availability_status':'unknown active/warmup/health/manual, statistical support is not deployable availability'})
            write(candidates,f'candidate_support_{year}_{role}.parquet')
            if year==2024:
                for cap in CAPS:combos.append({'role':role,'cap':cap,**weighted_contrast(observation,cap)})
            print(f'Slice15 diagnostics {year}/{role}: primary retained {roles[-1]["primary"]["retained"]:,}, change ESS {roles[-1]["primary"]["change"]["ess"]:.1f}',flush=True)
    flow=[read(OUT/f'preparation_{y}.json') for y in range(2021,2025)]
    action2024=pd.concat([pd.read_parquet(OUT/f'scored_2024_{role}_boundaries.parquet') for role in ['SP','RP']],ignore_index=True)
    original=pd.read_parquet(n.OUT/'signal_point_ledger.parquet')
    ledger=original[['decision_id','role','wpa_delta','point_reason','state_episode_id','nominal_research_alert']].merge(
        action2024[['decision_id','propensity','past_cell_support']],on='decision_id',how='left',validate='one_to_one')
    ledger['primary_overlap']=ledger.propensity.between(.05,.95)&ledger.past_cell_support.fillna(False)
    write(ledger,'fixed32_overlap.parquet')
    save('summary.json',{'version':'decision_overlap_v1','preparation':flow,'roles':roles,'weight_sensitivity':tables,'candidate_support':candidate_reports,
        'fixed32':{'raw_boundaries':len(ledger),'with_action_propensity':int(ledger.propensity.notna().sum()),'primary_overlap':int(ledger.primary_overlap.sum()),'modeled':int(ledger.wpa_delta.notna().sum()),
            'modeled_in_primary_overlap':int((ledger.wpa_delta.notna()&ledger.primary_overlap).sum()),'state_event_boundaries':int(ledger.state_episode_id.notna().sum()),
            'validated_multilight_alerts':int(ledger.nominal_research_alert.sum()),'operational_recommendations':0},
        'combination_observation_sensitivity2024':combos,'recommendation_allowed':False,'individual_ranking_allowed':False,'test2025_outcomes_examined':False,'stop':'15',
        'limits':protocol()['limits'],'next_step':'Slice16 only after explicitly defining a supported target policy and population; zero validated multi-light alerts cannot establish policy gain; no automatic16'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','fit','evaluate']);parser.add_argument('--year',type=int,choices=range(2021,2025));parser.add_argument('--role',choices=['SP','RP']);args=parser.parse_args()
    if args.stage=='prepare':prepare(args.year)
    elif args.stage=='fit':fit(args.year,args.role)
    else:globals()[args.stage]()
