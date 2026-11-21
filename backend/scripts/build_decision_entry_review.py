"""15.4 freeze and forward eligibility review. No refit, strategy value or2025."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_rp_targets as q
from scripts.audit_decision_overlap_revision import hashes

ROOT=q.ROOT;OUT=ROOT/'data/research/decision_entry_review_v1'
YEARS=[2022,2023,2024];REPS=300;SEED=1542026


def save(name,value):q.b.save_json(OUT/name,value)
def read(path):return q.read(path)


def input_folders():
    n,b,old=q.n,q.b,q.old
    return [b.PREP,b.OUT,ROOT/'data/research/decision_ablation_v1',n.old.a.a.OUT,n.r.OUT,n.u.h.OUT,n.u.OUT,n.old.a.OUT,n.p.OUT,n.old.prior.OUT,n.old.OUT,n.OUT,
        old.OUT,ROOT/'data/research/decision_overlap_pool_revision_v2',q.c.OUT,q.base.OUT,q.OUT]


def strategy_contract():
    return {'status':'specified for future feasibility; not executed or enabled',
        'trial':'one intervention at each eligible common-clock PA boundary, correlated trials retained and clustered; not a count of independent recommendations',
        'population':'SP all, between/within separate; RP within-inning short_profile from15.3; no2024 population/model/weight search',
        'reference':'continue the incumbent at the index boundary when legally possible; same frozen subsequent-action policy and terminal handling as research arm',
        'research':'at index boundary, apply existing four-reason two-red rule including A or B, mature observation and fresh-block persistence. Change only if all frozen14.2 value gates and legal/availability/support gates pass; otherwise continue when known safe, abstain if any required evidence unknown',
        'replacement_law':'for this pool-level timing estimand, uniform over predecision nominal RP options with legal and candidate-specific historical/joint-probability support and confirmed availability. No eligible options or unknown availability => abstain; not best-reliever ranking',
        'value_rule':'minimum delta defense xWPA .005; unsupported mass<=.01; MC95 lower>0 and model-bootstrap80 lower>0; original persistence/cooldown/one-alert constraints retained, never loosened for more cases',
        'subsequent_policy':'same versioned joint behavior policy at subsequent legal boundaries for both arms until the fixed half-ending endpoint. Must rebuild/version at common clock before16; original old-clock candidate behavior is not substituted',
        'primary_endpoint':'defense WE at natural end of the current/upcoming half minus defense WE at common anchor; include all intervening plays, IBB and runner events, absorbing game end; same WE version and horizon for both arms',
        'secondary_endpoint':'RE(anchor) - runs conceded from anchor to same half endpoint - RE(endpoint), defense positive; same RE version and terminal convention',
        'exploratory_endpoint':'same-definition next-PA defense WPA only if prespecified in16, reported separately; next_pa nonout and future_ten deviation are observation tasks, never substitutes for strategy WPA/RE24',
        'methods':'direct, SNIPS and doubly robust under the SAME joint action/candidate/observation support; game and pitcher dependence, year/role subgroups, weight and hidden-confounding sensitivity; no simulator-only benefit claim',
        'implementation_ready':False,'required_before16':['common-clock four-reason/persistence/value replay','candidate-specific joint propensities and availability at common clock','aligned half-ending actual endpoint adapters and common subsequent policy','forward comparison qualification and adequate strategy events'],
        'minimum_effect':'retain original .005 probability-point candidate gate; a positive strategy mean alone cannot promote, cluster interval and robustness required;16 must separately freeze any inferential minimum'}


def protocol():
    paths=[Path(__file__)]+[p/'manifest.json' for p in input_folders()]
    paths += [ROOT/'backend/scripts/decision_signal_episodes.py',ROOT/'backend/scripts/decision_alert_rules.py',q.n.OUT/'episode_protocol.json',q.n.OUT/'episode_selection.json']
    return {'version':'decision_entry_review_v1','source_sha256':{p.relative_to(ROOT).as_posix():q.b.digest(p) for p in paths},
        'scope':'recompute frozen forward2022/23/24 diagnostics; no fit or new predictions except verifying saved-model probabilities;2024 already diagnosed including15.3 label correction, not independent confirmation',
        'frozen_models':{'SP':'15.2 hgb_full, all SP, each phase separate','RP':'15.3 history_enriched, primary within_inning short_profile, fixed other populations sensitivity only'},
        'features':{'SP':q.base.CORE+q.base.STATE+q.base.FULLCAT,'RP':q.NUM+q.CAT},
        'weights':'overlap primary (A=1:1-e,A=0:e), development cell each arm>=10; IPW[.05,.95] secondary, never interchangeable estimands',
        'gates':{'max_abs_smd':.1,'min_ess_each_arm':500,'max_ece':.03,'no_fit_warning':True,'require_both_development_years':True,'require2024_diagnostic':True},
        'observation':'retain missing labels; RP paired-monitor nextPA/future10 each own training prior, observation g>=.1; no Y imputation; missing reasons retrospective diagnostics only',
        'uncertainty':{'reps':REPS,'seed':SEED,'method':'independent game and pitcher multinomial counts multiplied (pigeonhole); fixed fitted forecast/constant; paired Brier(model)-Brier(own past constant), percentile95, exploratory marginal intervals, no refit or multiplicity guarantee'},
        'review_ledger':'local initial support is past-only population/cell/probability screen. Annual/development qualification and review rejection are retrospective cohort audits, not live decision features or historical alert replay. Never condition eligibility on actual action or future Y/observation.',
        'strategy_contract':strategy_contract(),'fit_allowed':False,'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.4'}


def freeze():
    OUT.mkdir(exist_ok=True)
    previous=sum(hashes(folder) for folder in input_folders());assert previous==1546
    value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value
    save('protocol.json',value);save('input_audit.json',{'previous_artifacts':previous,'test2025_outcomes_examined':False})
    print('15.4 sources/features/populations/gates/weights/endpoints frozen for review; no new fit',flush=True)


def gate_failures(result,metrics,warning=False):
    reasons=[]
    if result['max_abs_smd_after'] is None or not np.isfinite(result['max_abs_smd_after']) or result['max_abs_smd_after']>.1:reasons.append('balance_smd')
    if min(result['change']['ess'],result['continue']['ess'])<500:reasons.append('effective_sample_size')
    if not np.isfinite(metrics['ece']) or metrics['ece']>.03:reasons.append('action_calibration')
    if warning:reasons.append('fit_warning')
    return reasons


def review_ledger(frame,in_population,probability,annual_pass,development_pass):
    initial=np.asarray(in_population,bool)&frame.past_cell_support.to_numpy(bool)&np.isfinite(probability)&(probability>0)&(probability<1)
    reason=np.full(len(frame),'pipeline_not_ready',dtype=object)
    if not annual_pass:reason[:]='annual_comparison_failed'
    if not development_pass:reason[:]='development_comparison_failed'
    reason[~np.isfinite(probability)|(probability<=0)|(probability>=1)]='invalid_propensity'
    reason[~frame.past_cell_support.to_numpy(bool)]='past_cell_unsupported'
    reason[~np.asarray(in_population,bool)]='outside_fixed_population'
    return frame[['decision_id','game_pk','appearance_id','outgoing_pitcher_id','role','phase','anchor_at']].assign(
        in_fixed_population=np.asarray(in_population,bool),past_cell_support=frame.past_cell_support.to_numpy(bool),
        initial_support=initial,annual_comparison_passed=annual_pass,development_comparison_passed=development_pass,
        review_eligible=False,review_rejection=reason)


def clustered_brier(frame,y,probability,prior,reps=REPS,seed=SEED):
    loss=(np.asarray(y)-np.asarray(probability))**2-(np.asarray(y)-prior)**2
    if not len(loss):return {'n':0,'delta':None,'interval':None,'games':0,'pitchers':0,'reps':0}
    game,gn=pd.factorize(frame.game_pk);pitcher,pn=pd.factorize(frame.outgoing_pitcher_id)
    rng=np.random.default_rng(seed);draws=[]
    for _ in range(reps):
        gw=rng.multinomial(len(gn),np.full(len(gn),1/len(gn)))
        pw=rng.multinomial(len(pn),np.full(len(pn),1/len(pn)))
        weights=gw[game]*pw[pitcher]
        if weights.sum():draws.append(float(np.average(loss,weights=weights)))
    return {'n':len(frame),'delta':float(loss.mean()),'interval':[float(x) for x in np.quantile(draws,[.025,.975])],
        'games':len(gn),'pitchers':len(pn),'reps':len(draws),'unit':'Brier(model)-Brier(own past constant); negative favors forecast; conditional on observed outcomes and fixed models'}


def verify_probabilities(year,role,phase,frame):
    with threadpool_limits(limits=2):
        if role=='SP':
            bundle=joblib.load(q.base.OUT/f'model_{year}_SP_{phase}_hgb_full.joblib')
            assert np.allclose(q.base.predict(bundle,frame.iloc[:64]),frame.propensity.iloc[:64],atol=1e-12)
        else:
            for name in ['action','next_pa_observation','future_ten_observation','next_pa_outcome','future_ten_outcome']:
                bundle=joblib.load(q.OUT/f'model_{year}_{phase}_{name}.joblib')
                assert np.allclose(q.predict(bundle,frame.iloc[:64]),frame[name+'_probability'].iloc[:64],atol=1e-12)


def review(year):
    assert read(OUT/'protocol.json')==protocol();rows=[];targets=[];ledgers=[];flows=[]
    for role in ['SP','RP']:
        features=q.base.features(year) if role=='SP' else None
        for phase in q.base.PHASES:
            if role=='SP':
                score=pd.read_parquet(q.base.OUT/f'scored_{year}_SP_{phase}_hgb_full.parquet')
                f=features.set_index('decision_id').loc[score.decision_id].reset_index()
                f['past_cell_support']=score.past_cell_support.to_numpy();f['propensity']=score.propensity.to_numpy()
                oldrow=next(x for x in read(q.base.OUT/f'results_{year}_SP.json')['rows'] if x['phase']==phase and x['variant']=='hgb_full' and x['scheme']=='overlap')
                metrics=oldrow['metrics'];warning=oldrow['warning'];subsets=['all']
            else:
                f=pd.read_parquet(q.OUT/f'scored_{year}_{phase}.parquet');warning=False;subsets=q.SUBSETS
            verify_probabilities(year,role,phase,f)
            probability=f.propensity.to_numpy() if role=='SP' else f.action_probability.to_numpy()
            primary=None
            for subset in subsets:
                mask=np.ones(len(f),bool) if role=='SP' else q.subset_mask(f,subset).to_numpy(bool)
                part=f[mask];prob=probability[mask]
                if role=='RP':
                    bundle=joblib.load(q.OUT/f'model_{year}_{phase}_action.joblib')
                    metrics=q.old.binary_metrics(part.changed.to_numpy(int),prob,bundle['prior'])
                for scheme in q.base.SCHEMES:
                    result=q.base.diagnostics(part,prob,scheme) if role=='SP' else q.diagnostics(part,prob,scheme)
                    source=(read(q.base.OUT/f'results_{year}_SP.json')['rows'] if role=='SP' else read(q.OUT/'summary.json')['balance'])
                    previous=next(x for x in source if x['year']==year and x['phase']==phase and x['scheme']==scheme and
                        ((role=='SP' and x['variant']=='hgb_full') or (role=='RP' and x['subset']==subset and x['model']=='history_enriched')))
                    assert np.isclose(result['max_abs_smd_after'],previous['max_abs_smd_after']) and result['retained']==previous['retained']
                    reasons=gate_failures(result,metrics,warning)
                    row={'year':year,'role':role,'phase':phase,'subset':subset,'scheme':scheme,**result,'ece':metrics['ece'],'warning':warning,'failures':reasons,'full_gate':not reasons,
                        'primary':role=='SP' or (phase=='within_inning' and subset=='short_profile')}
                    rows.append(row)
                    if scheme=='overlap' and (role=='SP' or subset=='short_profile'):primary=row
            if role=='SP':
                development=[x for x in read(q.base.OUT/'summary.json')['all_results'] if x['year'] in [2022,2023] and x['role']=='SP' and x['phase']==phase and x['variant']=='hgb_full' and x['scheme']=='overlap']
                in_population=np.ones(len(f),bool)
            else:
                development=[x for x in read(q.OUT/'summary.json')['balance'] if x['year'] in [2022,2023] and x['phase']==phase and x['subset']=='short_profile' and x['model']=='history_enriched' and x['scheme']=='overlap']
                in_population=q.subset_mask(f,'short_profile').to_numpy(bool)&(phase=='within_inning')
            assert len(development)==2
            ledger=review_ledger(f,in_population,probability,primary['full_gate'],all(x['full_gate'] for x in development))
            ledgers.append(ledger)
            flows.append({'year':year,'role':role,'phase':phase,'boundaries':len(f),'population':int(in_population.sum()),'initial_support':int(ledger.initial_support.sum()),
                'review_eligible':int(ledger.review_eligible.sum()),'rejections':ledger.review_rejection.value_counts().to_dict()})
            if role=='RP' and phase=='within_inning':
                monitor=f[f.monitor_unit&q.subset_mask(f,'short_profile')]
                for target in q.TARGETS:
                    known=monitor[target+'_observed'].eq(1);observed=monitor[known]
                    bundle=joblib.load(q.OUT/f'model_{year}_{phase}_{target}_outcome.joblib')
                    metrics=q.old.binary_metrics(observed[target+'_y'].to_numpy(int),observed[target+'_outcome_probability'].to_numpy(),bundle['prior'])
                    interval=clustered_brier(observed,observed[target+'_y'].to_numpy(),observed[target+'_outcome_probability'].to_numpy(),bundle['prior'],seed=SEED+year+q.TARGETS.index(target))
                    targets.append({'year':year,'target':target,'n':len(monitor),'observed':len(observed),'coverage':float(known.mean()),'metrics':metrics,'cluster_brier':interval,
                        'observation':q.scenario_summary(monitor,target),'missing_reasons':monitor[target+'_reason'].value_counts().to_dict()})
            print(f'15.4 {year}/{role}/{phase}: frozen probabilities, both weight targets and review rejections checked',flush=True)
    pd.concat(ledgers,ignore_index=True).to_parquet(OUT/f'review_ledger_{year}.parquet',index=False,compression='zstd')
    save(f'review_{year}.json',{'year':year,'balance':rows,'targets':targets,'flows':flows,'test2025_outcomes_examined':False})


def finish():
    assert read(OUT/'protocol.json')==protocol()
    folds=[read(OUT/f'review_{year}.json') for year in YEARS]
    balances=[r for f in folds for r in f['balance']];targets=[r for f in folds for r in f['targets']];flows=[r for f in folds for r in f['flows']]
    primary=[r for r in balances if r['primary'] and r['scheme']=='overlap'];assert len(primary)==9
    qualifications=[]
    for role,phase in [('SP','between_innings'),('SP','within_inning'),('RP','within_inning')]:
        rows=[r for r in primary if r['role']==role and r['phase']==phase]
        qualifications.append({'role':role,'phase':phase,'development_pass':all(r['full_gate'] for r in rows if r['year'] in [2022,2023]),
            'diagnostic2024_pass':all(r['full_gate'] for r in rows if r['year']==2024),'passed_folds':sum(r['full_gate'] for r in rows),'folds':len(rows),
            'comparison_qualified':all(r['full_gate'] for r in rows)})
    signals=read(q.n.OUT/'episode_selection.json')
    barriers=[{'id':'comparison_balance','passed':all(r['comparison_qualified'] for r in qualifications),'status':'measured','evidence':'frozen nine primary phase/year gates; no subgroup rescue'},
        {'id':'multilight_predictive_support','passed':all(v['training_predictive_support'] for v in signals['selected'].values()),'status':'inherited_failed','evidence':'14.2.4 fixed two-red research combinations, not refitted'},
        {'id':'common_clock_four_reason_value_replay','passed':False,'status':'not_ready','evidence':'common anchor A/B/C available, future next-batter D and value/persistence replay not revalidated; old-clock scores not substituted'},
        {'id':'candidate_joint_support_availability','passed':False,'status':'not_ready','evidence':'nominal snapshot is not active/warm/healthy availability; candidate-specific joint behavior must align common clock'},
        {'id':'aligned_half_endpoint_followup','passed':False,'status':'not_ready','evidence':'existing old-clock WPA labels/rollout are retained, not asserted aligned to common anchor or the new uniform supported-pool law'}]
    save('summary.json',{'version':'decision_entry_review_v1','progress':'44/51','balance':balances,'primary_folds':primary,'targets':targets,'flows':flows,'qualifications':qualifications,
        'barriers':barriers,'strategy_contract':strategy_contract(),'slice16_entry_allowed':all(x['passed'] for x in barriers),'strategy_value_estimated':False,
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15.4',
        'interpretation':'review completion is a documented no-entry decision when gates fail; bootstrap intervals conditional on observed labels and fixed models do not solve censoring, confounding or candidate availability'})
    print('15.4 frozen forward review complete;16 entry='+str(all(x['passed'] for x in barriers))+'; no strategy values calculated',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','review','finish']);parser.add_argument('--year',type=int,choices=YEARS);args=parser.parse_args()
    if args.stage=='review':review(args.year)
    else:globals()[args.stage]()
