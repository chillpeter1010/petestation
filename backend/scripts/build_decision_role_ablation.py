"""Slice13.6: fixed next-PA, role-specific missing-aware ablations.

All actual incoming actors use past closed history, never outgoing live state.
"""
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
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_batter_matchups as h

m,r,b=h.m,h.r,h.b
OUT=b.ROOT/'data/research/decision_role_ablation_v2'
LOAD5=['pitches_5d_before','entry_rest_hours','live_idle_hours','prior_games_pitches_3d','prior_games_pitches_5d']
SEASON=['season_appearance_number','season_rp_appearance_number','season_pitches_before']
PLUS=['option_stuff','option_location']
LIVE=['quality','physical','command','live_velocity','live_whiff','live_csw','live_ev',
      'mix_delta_research_stuff_plus','mix_delta_research_location_plus','personal_delta_stuff','personal_delta_location']
RECENT=[f'recent_{window}_{metric}' for window in ['last1','last3','last5','day3','day5'] for metric in ['stuff','location','velocity','quality','physical','command']]
RECENT += ['recent_stuff_slope','recent_location_slope','recent_velocity_slope']
EXPOSURE=['exposure_bf','exposure_cycle_proxy','exposure_slot','exposure_pair','exposure_pair_pitches']
RISK=['risk_stuff','risk_location']
ATTACK=[f'game{window}_{metric}' for window in [1,2,3] for metric in ['swing','whiff','contact','foul','fair','ev','hard']]
ATTACK += [f'{scope}3_mix_{metric}' for scope in ['game','pair_game','other_game','team'] for metric in ['whiff','contact','ev']]
ATTACK += ['game_contact_change','game_whiff_change']
ATTACK += [f'game{window}_{family}_{metric}' for window in [1,2,3] for family in h.FAMILIES
           for metric in ['received_share','swing_share','swing','contact','whiff','foul','ev']]
BVP=[f'pair_{key}_rate' for key in b.OUTCOMES]
TYPE=[f'type_{key}_rate' for key in b.OUTCOMES]+['fastball_share','breaking_share','offspeed_share','fast_velocity']+['affinity_'+metric for metric in h.RATIOS]
INTERACTIONS=['pair_contact_x_encounter','pair_whiff_x_seen','affinity_x_stuff_delta','affinity_x_location_delta']
SUPPORT=['option_plus_n','option_signal_age_hours','recent_history_age_hours','arsenal_n','pair_n','type_n',
         'game1_pa_n','game2_pa_n','game3_pa_n','pair_game3_pa_n','other_game3_pa_n','team3_pa_n',
         'live_support','recent_support','risk_support','affinity_whiff_mix_support','fastball_history_swings','breaking_history_swings','offspeed_history_swings']
SUPPORT_CAT=['signal_scope','signal_status']
GROUPS={'load5':LOAD5,'season':SEASON,'plus':PLUS,'live':LIVE,'recent':RECENT,'exposure':EXPOSURE,'risk':RISK,'attack':ATTACK,'bvp':BVP,'type':TYPE,'interactions':INTERACTIONS}
CUMULATIVE=['baseline','load_extended','plus','states','exposure','attack','all']
VARIANTS={
 'baseline':[], 'ability_only':[],
 'load_extended':LOAD5+SEASON,
 'plus':LOAD5+SEASON+PLUS,
 'states':LOAD5+SEASON+PLUS+LIVE+RECENT,
 'exposure':LOAD5+SEASON+PLUS+LIVE+RECENT+EXPOSURE+RISK,
 'attack':LOAD5+SEASON+PLUS+LIVE+RECENT+EXPOSURE+RISK+ATTACK,
 'all':sum(GROUPS.values(),[]),
}
for group in ['plus','live','recent','exposure','risk','attack','bvp','type','interactions','season']:
    VARIANTS['without_'+group]=[x for x in VARIANTS['all'] if x not in GROUPS[group]]
VARIANTS['without_72h']=[x for x in VARIANTS['all'] if x not in ['prior_games_pitches_3d']]
VARIANTS['without_120h']=[x for x in VARIANTS['all'] if x not in ['pitches_5d_before','prior_games_pitches_5d']]
VARIANTS['without_streak']=VARIANTS['all'].copy()
# Remove derived descendants as well; these are bundle sensitivity tests, not causal effects.
for variant in ['without_plus','without_live','without_72h','without_120h','without_exposure']:
    VARIANTS[variant]=[x for x in VARIANTS[variant] if x not in RISK]
for variant in ['without_live','without_plus','without_attack','without_type','without_exposure']:
    VARIANTS[variant]=[x for x in VARIANTS[variant] if x not in INTERACTIONS]
VARIANTS['without_plus']=[x for x in VARIANTS['without_plus'] if not any(t in x for t in ['stuff','location'])]
for suffix in ['72h','120h','streak','season']:
    VARIANTS['load_without_'+suffix]=[x for x in VARIANTS['load_extended'] if x not in
        ({'72h':['prior_games_pitches_3d'],'120h':['pitches_5d_before','prior_games_pitches_5d'],'season':SEASON}.get(suffix,[]))]


def save(name,value):b.save_json(OUT/name,value)


def enrich_options(frame:pd.DataFrame,year:int,attack:pd.DataFrame|None=None) -> pd.DataFrame:
    """Prepare either observed actors or the fixed14.1 option subset at its own clock."""
    warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
    f=frame.copy().reset_index(drop=True)
    if 'request_id' not in f:f['request_id']=f.decision_id+':'+f.option_pitcher_id.astype(str)
    assert f.request_id.is_unique
    with r.connect() as c:
        c.register('q',f[['request_id','decision_id','option_pitcher_id']])
        c.read_parquet(str(r.OUT/f'workload_features_{year}.parquet')).create_view('w')
        names=c.table('w').columns
        load=c.execute('SELECT q.request_id,'+','.join('w.'+x for x in names if x not in ['decision_id','option_pitcher_id','decision_at','is_current','option_role'])+
            ' FROM q JOIN w USING(decision_id,option_pitcher_id)').fetchdf().set_index('request_id').reindex(f.request_id)
        assert len(load)==len(f)
        for name in load:f[name]=load[name].to_numpy()
        c.read_parquet(str(r.OUT/f'recent_links_{year}.parquet')).create_view('l')
        c.read_parquet(str(r.OUT/f'recent_profiles_{year}.parquet')).create_view('p')
        fields=[f'p.{window}_{metric}_mean AS recent_{window}_{metric}' for window in ['last1','last3','last5','day3','day5'] for metric in ['stuff','location','velocity','quality','physical','command']]
        fields += [f'p.last5_{metric}_slope_per_appearance AS recent_{metric}_slope' for metric in ['stuff','location','velocity']]
        fields += ['l.history_age_hours recent_history_age_hours','p.last1_stuff_n recent_plus_n','p.last1_quality_n recent_state_n']
        recent=c.execute('SELECT q.request_id,'+','.join(fields)+' FROM q JOIN l USING(decision_id,option_pitcher_id) JOIN p USING(profile_id)').fetchdf().set_index('request_id').reindex(f.request_id)
        for name in recent:f[name]=recent[name].to_numpy()
        c.read_parquet(str(r.OUT/f'current_features_{year}.parquet')).create_view('live')
        live=c.execute('SELECT q.request_id,live.* EXCLUDE(request_id) FROM q JOIN live USING(decision_id)').fetchdf().set_index('request_id').reindex(f.request_id)
        c.read_parquet(str(r.OUT/'lineup_slots.parquet')).create_view('slots')
        c.read_parquet(str(r.OUT/f'pa_observations_{year}.parquet')).create_view('pa')
        c.execute('''CREATE TEMP TABLE slot_history AS SELECT game_pk,final_pitcher_id,batting_slot,available_at,
            count(*) OVER(PARTITION BY game_pk,final_pitcher_id,batting_slot ORDER BY available_at,outcome_key ROWS UNBOUNDED PRECEDING) prior_count
            FROM pa WHERE is_complete AND is_batter_faced AND batting_slot IS NOT NULL AND available_at IS NOT NULL''')
        c.register('requests',f[['request_id','game_pk','option_pitcher_id','batter_id','decision_at']])
        slots=c.execute('''SELECT q.request_id,coalesce(h.prior_count,0)+1 slot_encounter FROM requests q
            LEFT JOIN slots z ON q.game_pk=z.game_pk AND q.batter_id=z.batter_id
            ASOF LEFT JOIN slot_history h ON q.game_pk=h.game_pk AND q.option_pitcher_id=h.final_pitcher_id AND z.batting_slot=h.batting_slot AND q.decision_at>h.available_at''').fetchdf().set_index('request_id').reindex(f.request_id)
        c.read_parquet(str(r.OUT/f'pitch_observations_{year}.parquet')).create_view('o')
        c.execute('''CREATE TEMP TABLE support AS SELECT appearance_id,available_at,
            count(research_stuff_plus) OVER win stuff_n,count(research_location_plus) OVER win location_n
            FROM o WHERE time_reliable WINDOW win AS(PARTITION BY session_id ORDER BY available_at,event_index ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)''')
        supports=c.execute('''SELECT q.request_id,s.stuff_n,s.location_n FROM q JOIN live USING(decision_id)
            ASOF LEFT JOIN support s ON live.appearance_id=s.appearance_id AND live.cutoff>s.available_at''').fetchdf().set_index('request_id').reindex(f.request_id)
    current=f.is_current.to_numpy(dtype=bool)
    f['forecast_role']=np.where(current,f.option_role,'RP')
    def observed(name):return live[name].to_numpy()
    for target,src,recent_name in [('option_stuff','live_research_stuff_plus','recent_last1_stuff'),('option_location','live_research_location_plus','recent_last1_location'),
        ('quality','quality_plus','recent_last1_quality'),('physical','physical_plus','recent_last1_physical'),('command','command_plus','recent_last1_command')]:
        f[target]=np.where(current,observed(src),f[recent_name])
    for target,src in [('live_velocity','live_release_speed'),('live_ev','live_ev_sum')]:
        f[target]=np.where(current,observed(src),np.nan)
    f['live_ev']=f.live_ev/np.where(current,observed('live_ev_n'),np.nan)
    for target,num,den in [('live_whiff','live_whiff_sum','live_swing_sum'),('live_csw','live_csw_sum','live_csw_n')]:
        f[target]=np.where(current,observed(num)/np.where(observed(den)>0,observed(den),np.nan),np.nan)
    for name in ['mix_delta_research_stuff_plus','mix_delta_research_location_plus','personal_delta_stuff','personal_delta_location']:
        f[name]=np.where(current,observed(name),np.nan)
    f['option_plus_n']=np.where(current,observed('live_research_stuff_plus_n'),f.recent_plus_n)
    f['option_signal_age_hours']=np.where(current,(f.decision_at-observed('observation_at'))/3600,f.recent_history_age_hours)
    f['signal_scope']=np.where(current,'current_observed_prefix','closed_same_role_history_not_readiness')
    f['signal_status']=np.where(current,observed('live_status'),'historical_prior')
    f['live_support']=np.where(current,observed('prefix_pitches'),np.nan)
    f['recent_support']=f.recent_state_n
    f['exposure_bf']=np.where(current,observed('completed_bf_before')+1,1)
    f['exposure_cycle_proxy']=np.floor((f.exposure_bf-1)/9)+1
    f['exposure_slot']=slots.slot_encounter.to_numpy()
    f['exposure_pair']=np.where(current,observed('observed_pair_encounters_before')+1,1)
    f['exposure_pair_pitches']=np.where(current,observed('observed_pair_pitches_before'),0)
    # Out-of-time risk models are evaluated at THIS decision's cutoff, never joined from the later PA anchor.
    risk=pd.DataFrame({'pitcher_id':f.option_pitcher_id,'pitcher_hand':f.pitcher_hand,'batter_side':f.expected_stand,'half':f.half,
        'pitches_before':f.option_game_pitches,'bf_index':f.exposure_bf,'slot_encounter':f.exposure_slot,'same_batter_encounter':f.exposure_pair,
        'batter_k':f.batter_k_rate,'batter_bb':f.batter_bb_rate,'batter_hr':f.batter_hr_rate,'batter_log_n':np.log1p(f.batter_own_all_n),
        'day_of_year':pd.to_datetime(f.decision_at,unit='s',utc=True).dt.dayofyear,'inning':f.inning,'outs':f.outs,'base_state':f.base_state,'defense_lead':f.defense_lead,
        'past10_stuff':observed('last10_research_stuff_plus'),'past10_location':observed('last10_research_location_plus'),
        'past10_velocity':observed('last10_release_speed'),'mix_delta_research_stuff_plus':f.mix_delta_research_stuff_plus,
        'mix_delta_research_location_plus':f.mix_delta_research_location_plus,'pitches_1d':f.pitches_1d_before,
        'pitches_3d':f.pitches_3d_before,'pitches_5d':f.pitches_5d_before,'rest_hours':f.live_idle_hours})
    f['risk_stuff']=np.nan;f['risk_location']=np.nan
    with threadpool_limits(limits=2):
        for fold,cutoff,start,end in m.RISK_FOLDS:
            lo=pd.Timestamp(start,tz='UTC').timestamp();hi=pd.Timestamp(end,tz='UTC').timestamp() if fold!='frozen_2024' else np.inf
            period=f.decision_at.ge(lo)&f.decision_at.lt(hi)
            for role in ['SP','RP']:
                for metric in ['stuff','location']:
                    mask=period&f.is_current&f.option_role.eq(role)&f.live_support.ge(35 if role=='SP' else 10)&f.signal_status.eq('observed_current_prefix')
                    mask &= supports[metric+'_n'].to_numpy()>=8
                    fit=joblib.load(r.OUT/f'risk_{fold}_{role}_{metric}_state_workload.joblib')
                    for name,(low,high) in fit['support'].items():mask &=risk[name].between(low,high)
                    if mask.any():f.loc[mask,'risk_'+metric]=m.risk_probability(fit,risk.loc[mask])
    f['risk_support']=f[RISK].notna().sum(axis=1)
    incompatible=~f.is_current&f.option_role.ne('RP')
    # Historical role remains a core predictor; SP state priors are not RP-entry state.
    f.loc[incompatible,PLUS+['quality','physical','command']+RECENT]=np.nan
    f.loc[incompatible,['option_plus_n','recent_support']]=0
    f.loc[incompatible,'signal_scope']='incompatible_prior_role_state_unavailable'
    if attack is None:attack=h.attack_features(f,year)
    f=f.merge(attack,on='request_id',validate='one_to_one')
    f['pair_contact_x_encounter']=f.pair_game3_contact*np.log1p(f.exposure_pair)
    f['pair_whiff_x_seen']=f.pair_game3_whiff*np.log1p(f.exposure_pair_pitches)
    f['affinity_x_stuff_delta']=f.affinity_whiff*f.mix_delta_research_stuff_plus
    f['affinity_x_location_delta']=f.affinity_contact*f.mix_delta_research_location_plus
    return f


def features(year):
    f=pd.read_parquet(r.OUT/f'observed_features_{year}.parquet');f['request_id']=f.decision_id
    attack=pd.read_parquet(h.OUT/f'observed_attack_{year}.parquet')
    f=enrich_options(f,year,attack)
    f.to_parquet(OUT/f'features_{year}.parquet',index=False,compression='zstd')
    save(f'features_{year}.json',{'year':year,'rows':len(f),'roles':f.forecast_role.value_counts().to_dict(),
        'prior_role_differs_from_entry':int((f.option_role!=f.forecast_role).sum()),
        'current':int(f.is_current.sum()),'complete_signals':int(f[PLUS+['quality','physical','command']].notna().all(axis=1).sum()),
        'risk_current_only':int(f.risk_support.gt(0).sum()),'actor_clock':'observed actor before original decision; risk out-of-time fit and same cutoff; incoming never outgoing live state'})
    print(f'{year}: {len(f):,} actor-aligned extended PA feature rows',flush=True)


def model_columns(variant):
    numeric=b.LEVELS['matchup'][0].copy();categorical=b.LEVELS['matchup'][1].copy()
    if variant=='ability_only':
        numeric=[x for x in numeric if x not in b.LOAD_NUM]
        categorical=[x for x in categorical if x not in ['appeared_earlier_today','lookback_14d_complete']]
    if variant in ['without_72h','load_without_72h']:numeric=[x for x in numeric if x!='pitches_3d_before']
    if variant in ['without_streak','load_without_streak']:numeric=[x for x in numeric if x!='consecutive_days']
    if variant=='without_exposure':numeric=[x for x in numeric if x!='option_current_bf']
    numeric=list(dict.fromkeys(numeric+SUPPORT+VARIANTS[variant]))
    categorical=list(dict.fromkeys(categorical+SUPPORT_CAT+(['arsenal_type'] if variant in ['all'] or variant.startswith('without_') and variant!='without_type' else [])))
    return numeric,categorical


def design(frame,variant,prior):
    x=b.design(frame,'matchup',20,prior)
    numeric,categorical=model_columns(variant)
    extra={}
    for name in numeric:
        if name not in x:extra[name]=pd.to_numeric(frame[name],errors='coerce').replace([np.inf,-np.inf],np.nan)
    for name in categorical:
        if name not in x:extra[name]=frame[name].astype('string').fillna('unknown').astype(str)
    x=pd.concat([x,pd.DataFrame(extra,index=frame.index)],axis=1)
    if variant=='without_type':
        for key in b.OUTCOMES:x['pair_'+key+'_rate']=(frame['pair_'+key+'_count'].fillna(0)+20*frame['batter_'+key+'_rate'])/(frame.pair_n+20)
    if variant=='without_recent':
        x.loc[~frame.is_current,['option_stuff','option_location','quality','physical','command']]=np.nan
    return x


def make_model(variant):
    numeric,categorical=model_columns(variant)
    transform=ColumnTransformer([
        ('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),numeric),
        ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=True),categorical)],sparse_threshold=1.)
    return make_pipeline(transform,SGDClassifier(alpha=.001,**b.LEARNER))


def load(year,labels):
    needed=set(b.LEVELS['matchup'][0]+b.LEVELS['matchup'][1]+SUPPORT+SUPPORT_CAT+VARIANTS['all'])-{'pitcher_log_n','batter_log_n'}
    needed.update(['year','decision_id','game_pk','decision_at','option_pitcher_id','outgoing_role','is_current','arsenal_type',
        'pitcher_own_all_n','pitcher_own_split_n','batter_own_all_n','batter_own_split_n','research_home_we','research_re','forecast_role'])
    needed.update('pair_'+key+'_count' for key in b.OUTCOMES)
    frame=pd.read_parquet(OUT/f'features_{year}.parquet',columns=sorted(needed))
    if not labels:return frame
    labels=pd.read_parquet(b.PREP/f'clean_labels_{year}.parquet',columns=['decision_id','organic_pa_eligible','observed_pa_result','runs_to_pa_end','outs_after','base_state_after','pa_end_at'])
    frame=frame.merge(labels,on='decision_id',validate='one_to_one');frame=frame[frame.organic_pa_eligible].copy()
    frame['post_base']=np.where(frame.outs_after.eq(3),0,frame.base_state_after)
    return b.clean_model_frame(frame)[0]


def protocol():
    paths=[Path(__file__),Path(h.__file__),r.OUT/'protocol.json',r.OUT/'manifest.json',h.OUT/'protocol.json',b.OUT/'transitions.joblib']
    paths += [OUT/f'features_{y}.parquet' for y in r.YEARS]
    return {'version':'decision_role_ablation_v2','protocol_revision':3,
        'superseded_protocol_sha256':b.digest(OUT/'attempt2_pa_identity_unfiltered/protocol.json'),
        'initial_protocol_sha256':b.digest(OUT/'attempt1_previous_role_grouping/protocol.json'),
        'identity_source_revision':'Rebuilt attack/matchup histories after110 multi-batter or official/physical identity conflicts excluded; all conflicting PAs already outside the organic target cohort, so train/validation denominator unchanged. Trial2 partial outputs/source retained.',
        'role_revision':'Use forecast_role: current actual role, replacement entry=RP. Preserve prior observed option_role as predictor; incompatible prior-role state/Plus/recent scores unavailable. Partial prior-role grouping trial/source archived; thresholds/variants unchanged.',
        'input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'split':{'train':[2021,2022,2023],'diagnostics_selection':[2024],'locked_test':[2025],'score_only':[2026]},
        'variants':VARIANTS,'support_numeric':SUPPORT,'support_categorical':SUPPORT_CAT,
        'fixed_settings':{'alpha':.001,'ability_pooling':20,'learner':b.LEARNER},
        'target':'next actual chosen-actor organic PA,9 outcome classes, original strict predecision cutoff; no outgoing-state/incoming-label mismatch',
        'cohort':'every variant uses identical missing-aware training/2024 rows per actual actor SP/RP; supported-signal baseline/all sensitivity separately',
        'preprocessing':'imputer/scaler/onehot fit on training only, L2 fixed; support age/n/scope controls shared across every comparison',
        'risk_clock':'original decision cutoff with forward-trained13.4 bundle; current actor only; pre-Sep2021 warmup and replacement entry risk missing; never join later PA-anchor risk',
        'descendants':'group leave-outs remove derived risk/interactions as applicable; without_type BvP prior reverts directly to batter ability; load_without variants isolate workload without downstream signal models',
        'uncertainty':'200 paired game x pitcher Poisson bootstrap; simultaneous97.5% within-role family across all nonbaseline LL contrasts, Bonferroni for2roles; point Brier and >=500-PA subgroup harm check; diagnostic selection, not independent test',
        'gate':'LL family upper<0, Brier lower, no >=500 current/incoming subgroup LL harm>.005, no convergence warning; only fixed cumulative variants eligible; all must also improve supported sensitivity to be chosen',
        'selection':'lowest2024 LL among passing predeclared cumulative candidates else baseline; no leave-out model selected by best score; no formal promotion',
        'simulation_policy':'candidate historical signals are priors, not readiness; no unsupported state evolution. Slice14.1 can condition first PA, then explicitly revert to repaired baseline.',
        'recommendation_allowed':False,'individual_ranking_allowed':False,'test_outcome_metrics_examined':False}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen role-ablation differs; preserve and revision required')
    save('protocol.json',value);print('13.6 fixed variants / role evaluation protocol frozen',flush=True)


def family_intervals(frame,differences):
    """Paired two-way cluster bands for a matrix of fixed contrasts."""
    differences=np.asarray(differences)
    if differences.ndim==1:differences=differences[:,None]
    groups=frame[['game_pk','option_pitcher_id']].copy()
    for i in range(differences.shape[1]):groups[str(i)]=differences[:,i]
    groups['n']=1
    agg=groups.groupby(['game_pk','option_pitcher_id'],sort=True).sum().reset_index()
    games,_=pd.factorize(agg.game_pk);pitchers,_=pd.factorize(agg.option_pitcher_id)
    values=agg[[str(i) for i in range(differences.shape[1])]].to_numpy();n=agg.n.to_numpy();rng=np.random.default_rng(m.SEED)
    boots=[]
    for _ in range(200):
        weights=rng.poisson(1,games.max()+1)[games]*rng.poisson(1,pitchers.max()+1)[pitchers]
        boots.append((weights@values)/(weights@n))
    boot=np.asarray(boots);point=differences.mean(axis=0);se=boot.std(axis=0,ddof=1);valid=se>1e-12
    critical=float(np.quantile(np.max(np.abs((boot[:,valid]-point[valid])/se[valid]),axis=1),.975)) if valid.any() else 1.96
    return [{'mean':float(point[i]),'paired_two_way95':np.quantile(boot[:,i],[.025,.975]).tolist(),
             'role_family97_5':[float(point[i]-critical*se[i]),float(point[i]+critical*se[i])],
             'replicates':200,'games':int(games.max()+1),'pitchers':int(pitchers.max()+1)} for i in range(len(point))]


def train(role_only=None):
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    development=pd.concat([load(y,True) for y in [2021,2022,2023]],ignore_index=True);validation=load(2024,True)
    assert development.pa_end_at.max()<pd.Timestamp('2024-01-01',tz='UTC').timestamp()
    report={'version':'decision_role_ablation_v2','protocol_sha256':b.digest(OUT/'protocol.json'),'roles':{},
        'training_n':len(development),'validation_n':len(validation),'test_outcome_metrics_examined':False,
        'formal_promotion':False,'recommendation_allowed':False}
    with threadpool_limits(limits=2):
        for role in ['SP','RP']:
            if role_only is not None and role!=role_only:continue
            t=development[development.forecast_role.eq(role)].reset_index(drop=True)
            v=validation[validation.forecast_role.eq(role)].reset_index(drop=True)
            prior=np.bincount(t.target,minlength=9)/len(t);weights=1/t.groupby('game_pk').decision_id.transform('count').to_numpy();weights/=weights.mean()
            results={};losses={};briers={}
            for variant in VARIANTS:
                print(f'13.6 {role}/{variant}: train={len(t):,} validation={len(v):,}',flush=True)
                fit=make_model(variant)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always',ConvergenceWarning)
                    fit.fit(design(t,variant,prior),t.target,sgdclassifier__sample_weight=weights)
                p=b.probabilities(fit,design(v,variant,prior));y=v.target.to_numpy();idx=np.arange(len(y))
                loss=-np.log(p[idx,y]);br=np.sum(p*p,axis=1)-2*p[idx,y]+1
                results[variant]={'metrics':b.metrics(y,p),'convergence_warning':any(isinstance(w.message,ConvergenceWarning) for w in caught)}
                losses[variant]=loss;briers[variant]=br
                used=model_columns(variant)[0]
                ranges={key:[float(t[key].min()),float(t[key].max())] for key in ['option_game_pitches','option_current_bf']+PLUS+['quality','physical','command'] if key in used and t[key].notna().any()}
                joblib.dump({'model':fit,'variant':variant,'prior':prior,'role':role,'train_cutoff':'2024-01-01','support_ranges':ranges},OUT/f'{role}_{variant}.joblib')
                out=v[['decision_id','game_pk','option_pitcher_id','outgoing_role','is_current']].copy()
                for j,key in enumerate(b.OUTCOMES):out['p_'+key]=p[:,j]
                out.to_parquet(OUT/f'validation_{role}_{variant}.parquet',index=False,compression='zstd')
            names=[x for x in VARIANTS if x!='baseline']
            intervals=family_intervals(v,np.column_stack([losses[x]-losses['baseline'] for x in names]))
            br_intervals=family_intervals(v,np.column_stack([briers[x]-briers['baseline'] for x in names]))
            full_intervals=family_intervals(v,np.column_stack([losses[x]-losses['all'] for x in names]))
            for i,name in enumerate(names):
                groups=[]
                for (outgoing,is_current),g in v.groupby(['outgoing_role','is_current']):
                    ix=g.index.to_numpy();groups.append({'outgoing_role':outgoing,'is_current':bool(is_current),'n':len(ix),
                        'log_loss_delta':float((losses[name][ix]-losses['baseline'][ix]).mean())})
                harm=any(g['n']>=500 and g['log_loss_delta']>.005 for g in groups)
                results[name].update({'delta_vs_baseline':intervals[i],'brier_delta_vs_baseline':br_intervals[i],
                    'delta_vs_all':full_intervals[i],'subgroups':groups,
                    'increment_gate':bool(intervals[i]['role_family97_5'][1]<0 and np.mean(briers[name])<np.mean(briers['baseline']) and not harm and not results[name]['convergence_warning'])})
            # Pure workload contrasts avoid the composite risk score as a descendant.
            load_names=['load_without_'+x for x in ['72h','120h','streak','season']]
            load_intervals=family_intervals(v,np.column_stack([losses[x]-losses['load_extended'] for x in load_names]))
            supported={};ts=t[t[PLUS+['quality','physical','command']].notna().all(axis=1)].reset_index(drop=True)
            vs=v[v[PLUS+['quality','physical','command']].notna().all(axis=1)].reset_index(drop=True)
            if len(ts)>=1000 and len(vs)>=500:
                sprior=np.bincount(ts.target,minlength=9)/len(ts);sw=1/ts.groupby('game_pk').decision_id.transform('count').to_numpy();sw/=sw.mean()
                ps={}
                for variant in ['baseline','all']:
                    print(f'13.6 {role}/supported_{variant}: {len(ts):,}/{len(vs):,}',flush=True)
                    fit=make_model(variant)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always',ConvergenceWarning)
                        fit.fit(design(ts,variant,sprior),ts.target,sgdclassifier__sample_weight=sw)
                    ps[variant]=b.probabilities(fit,design(vs,variant,sprior))
                    supported[variant]={'metrics':b.metrics(vs.target.to_numpy(),ps[variant]),'convergence_warning':any(isinstance(w.message,ConvergenceWarning) for w in caught)}
                    joblib.dump({'model':fit,'variant':variant,'prior':sprior,'role':role},OUT/f'{role}_supported_{variant}.joblib')
                y=vs.target.to_numpy();ix=np.arange(len(y))
                delta=family_intervals(vs,-np.log(ps['all'][ix,y])+np.log(ps['baseline'][ix,y]))[0]
                supported['delta']=delta;supported['training_n']=len(ts);supported['validation_n']=len(vs)
                supported['increment_gate']=bool(delta['role_family97_5'][1]<0 and supported['all']['metrics']['brier']<supported['baseline']['metrics']['brier'] and not supported['all']['convergence_warning'])
            else:supported={'training_n':len(ts),'validation_n':len(vs),'increment_gate':False,'status':'insufficient_support'}
            candidates=[name for name in CUMULATIVE[1:] if results[name]['increment_gate'] and (name!='all' or supported['increment_gate'])]
            winner=min(candidates,key=lambda x:results[x]['metrics']['log_loss']) if candidates else 'baseline'
            fit=joblib.load(OUT/f'{role}_{winner}.joblib')
            p=b.probabilities(fit['model'],design(v,winner,fit['prior']))
            joint=b.transition_scores(v,p,joblib.load(b.OUT/'transitions.joblib'),True)
            transition={'joint_log_loss':float(np.mean(joint['joint_ll'])),'joint_brier':float(np.mean(joint['joint_brier'])),
                'mean_unsupported_mass':float(np.mean(joint['unsupported_mass'])),'mean_predicted_runs':float(np.mean(joint['runs']))}
            report['roles'][role]={'training_n':len(t),'validation_n':len(v),'results':results,'supported_sensitivity':supported,
                'load_contrasts_vs_extended':dict(zip(load_names,load_intervals)),'selected':winner,'selected_transitions':transition,
                'selection_scope':'2024 diagnostics; not independent final confirmation; simulation state evolution unavailable'}
            print(f'13.6 {role} diagnostic selection: {winner}',flush=True)
    save('validation_'+role_only+'.json' if role_only else 'validation.json',report)


def combine():
    reports=[json.loads((OUT/f'validation_{role}.json').read_text('utf-8')) for role in ['SP','RP']]
    digest=b.digest(OUT/'protocol.json')
    assert all(x['protocol_sha256']==digest for x in reports)
    report=reports[0];report['roles'].update(reports[1]['roles'])
    assert sum(x['validation_n'] for x in report['roles'].values())==report['validation_n']
    save('validation.json',report)
    print('13.6 two independently computed role reports combined',flush=True)


def score():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    report=json.loads((OUT/'validation.json').read_text('utf-8'))
    with threadpool_limits(limits=2):
        for year in [2025,2026]:
            frame=load(year,False);out=frame[['decision_id','game_pk','option_pitcher_id','option_role','forecast_role']].copy()
            for role in ['SP','RP']:
                variant=report['roles'][role]['selected'];fit=joblib.load(OUT/f'{role}_{variant}.joblib');mask=frame.forecast_role.eq(role)
                p=b.probabilities(fit['model'],design(frame.loc[mask],variant,fit['prior']))
                for j,key in enumerate(b.OUTCOMES):out.loc[mask,'p_'+key]=p[:,j]
                out.loc[mask,'selected_variant']=variant
            out.to_parquet(OUT/f'predictions_{year}.parquet',index=False,compression='zstd')
            print(f'{year}:13.6 selected predictions only; outcomes closed',flush=True)


def finalize():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    report=json.loads((OUT/'validation.json').read_text('utf-8'))
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_6_v2.json',report)
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json']
    save('manifest.json',{'version':'decision_role_ablation_v2','files':[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':b.digest(p)} for p in sorted(files)]})
    print('13.6 evidence published',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['features','freeze','train','combine','score','finalize']);parser.add_argument('--year',type=int,choices=r.YEARS);parser.add_argument('--role',choices=['SP','RP'])
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='features':
        for year in [args.year] if args.year else r.YEARS:features(year)
    elif args.stage=='train':train(args.role)
    else:globals()[args.stage]()
