"""Slices16.1-3: integrated shadow replay and explicitly model-based scenarios.

No off-policy efficacy estimate, operational recommendation, or2025 outcomes.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_pe_models as pe
from scripts import build_decision_action_values as action

b=pe.q.b;f=pe.f;ROOT=pe.ROOT
OUT=ROOT/'data/research/decision_exploratory_v1'
FOUND=f.q.n.old.FOUNDATION
SEED=1612026;PATHS=256;MAX_PA=32;GAMES=32
NUM=['inning','defense_lead','outs','current_pitches','current_bf','prior_games_pitches_3d',
     'prior_games_pitches_5d','rest_hours','ability_log_n','recent_stuff','recent_location',
     'recent_velocity','recent_n','recent_age_hours']+[f'pitcher_{x}_rate' for x in f.OUTCOMES]
NUM += [f'forecast{i}_{x}' for i in [1,2,3] for x in ['log_n','nonout','extra_base','k','bb']]
LIVE=['smooth_stuff','smooth_velocity','smooth_location','smooth_contact','pe_last1','pe_last2','pe_last3','pe_slope3','prefix_strike_share']
CAT=['half','base_state','scheduled_innings','phase','option_role','is_current','pitcher_hand','recent_model','lineup_status']


def read(path):return pe.read(path)
def save(name,value):b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')
def context(year):return b.TEMPORAL/'models'/('frozen_2024' if year==2024 else str(year))/'context.joblib'


def protocol():
    return {'version':OUT.name,'source_sha256':b.digest(Path(__file__)),
        'prior_manifests':{str(p.relative_to(ROOT)):b.digest(p) for p in [pe.OUT/'manifest.json',f.OUT/'manifest.json',f.entry.OUT/'manifest.json']},
        'authorization':'2026-11-21 user explicitly authorized16.1-3 exploratory revision; original15.4 formal estimand/gates retained separately',
        'years':[2021,2022,2023,2024],'validation':'2022/23 forward ranking before2024 bridge scoring;2024 previously inspected diagnostic,2025 sealed',
        'shadow':'ALL inherited common boundaries; past-calibration role-specific run thresholds, two adjacent same-half same-appearance PAs, maxone/appearance; unified SP-to-RP team2PA cooldown. Original observed history continues after alert; NOT counterfactual full-game path. Unknown/gaps reset persistence.',
        'case_selection':f'2024 common-clock games ordered by md5(str(game_pk)), first{GAMES}; ALL boundaries retained regardless alert/action/outcome. Historical legal cohort is retrospectively selected, not deployment population.',
        'candidate':'strictly earlier nominal roster snapshot; exclude already-entered pitchers at anchor and outgoing, require previous RP role. No current-active/warmup/medical inference. Own ability/load/recent closed-history ASOF anchor, no incumbent live features on replacements.',
        'bridge':'9-class PA observed actual actor including replacement entries. Common anchor before PA start; require matching initial outs/bases/scores, single actor, organic PA, legal runner conservation. Normalize post_base=0 when outs_after=3 (official raw residual runners are not a live next state). Actual actor used as training label/action, never future batter predictor. Entry and incumbent support separately reported.',
        'implementation_revision':'attempt0 preserves initial string-state adapter/slow replay; attempt1 preserves incorrect raw third-out residual-base exclusion and all provisional fits/scenarios. Neither used for final research. Correct absorbing third-out state before any label support filter, retrain/reselect all folds.',
        'features':{'base':NUM,'rich':NUM+LIVE,'cat':CAT},
        'fit':'whole-game chronological80/20 fit/cal, spanning games excluded; fixed natural60000 fit cap; HGB7leaves60iterations/minleaf200/L2=10/lr.05; one-hot cats, temperature .5-3. Rank base/rich on2022/23 meanLL, no2024 selection. No ID encoded.',
        'pool_law':'uniform over own-history-supported nominal RP pool, at least2; no individual ranking. Full, rest>=24h,72h pitches<=40 sensitivity, no retuning.',
        'next_pa':'paired256paths; same anchor, full organic PA and conditional training-only legal runner transitions, frozen WE/RE. Excludes intervening non-PA events and IBB; conditional organic-PA scenario, not complete action-policy value.',
        'half':'hold selected pitcher to current half end, no later substitutions; same paired random numbers; forecast first3 slots from past, fourth+ previous-UTC-day league prior; first PA selected bridge, later base bridge without frozen live states. Simulated PA pitch increments sampled from training by role/outcome; later inter-PA rest uses past training within-inning incumbent median (never retain pre-entry rest). No simulated future Stuff/PE.32PA cap.',
        'support':'own role history>=30 PA, known prior hand, complete14day pitch history; >=30 training labels per role/is_current; first-PA numeric range checks; max unsupported category mass per path<=.01, no capped path or model pitch-range extrapolation for supported half direction.',
        'intervals':'paired MC95 conditional fixed models/transitions/WE; NOT model/causal uncertainty. Mean case differences game-cluster descriptive95, samplecases not league policy effect. Unselected base/rich alternative and availability sensitivity separate.',
        'formal_offpolicy':'SNIPS/DR withheld: inherited SMD fails, missing common-clock joint candidate/availability propensities and aligned subsequent behavior policy. Do not reuse observed half outcomes to validate hold-pitcher policy when later actual substitutions differ.',
        'recommendation_allowed':False,'formal_efficacy_passed':False,'test2025_outcomes_examined':False,'stop':'16.3'}


def freeze():
    OUT.mkdir(parents=True,exist_ok=True)
    value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value,'Frozen source changed: version or preserve attempt explicitly'
    save('protocol.json',value)
    # Snapshot every prior frozen artifact. Exporters can change, research data cannot.
    if not (OUT/'prior_hashes.json').exists():
        folders=pe.entry_folders()+[f.OUT,pe.OUT]
        paths=sorted(set(p for folder in folders for p in folder.rglob('*') if p.is_file()))
        save('prior_hashes.json',{str(p.relative_to(ROOT)):b.digest(p) for p in paths})
    frame=pd.read_parquet(f.OUT/'features_2024.parquet',columns=['game_pk'])
    games=sorted(frame.game_pk.unique(),key=lambda x:hashlib.md5(str(x).encode()).hexdigest())[:GAMES]
    save('cases.json',{'games':[int(x) for x in games],'selection':value['case_selection']})
    print('16 protocol/cases/prior artifacts frozen',flush=True)


def replay_frame(frame):
    """Preserve the raw ordering, use team-global cooldown across SP/RP."""
    result=frame.sort_values(['game_pk','team_id','anchor_at','decision_id']).copy()
    emissions=[];reasons=[]
    for _,group in result.groupby(['game_pk','team_id'],sort=False):
        last=None;run=0;used=set();emission=None
        for row in group.itertuples():
            high=bool(pd.notna(row.risk) and row.risk>=row.threshold)
            adjacent=last is not None and last.risk>=last.threshold and last.appearance_id==row.appearance_id and last.inning==row.inning and last.half==row.half and last.seen_pa_count+1==row.seen_pa_count
            run=(run+1 if adjacent else 1) if high else 0
            reason='below_threshold'
            if high:
                reason='awaiting_persistence'
                if row.appearance_id in used:reason='already_emitted'
                elif emission is not None and row.seen_pa_count-emission<=2:reason='team_cooldown'
                elif run>=2:
                    reason='emitted';used.add(row.appearance_id);emission=row.seen_pa_count
            emissions.append(reason=='emitted');reasons.append(reason);last=row
    result['emitted']=emissions;result['replay_reason']=reasons
    return result


def replay(year):
    columns=['decision_id','game_pk','team_id','appearance_id','outgoing_pitcher_id','role','inning','half','anchor_at',
             'seen_pa_count','at_bat_number','changed','old_decision_at','target_observed','y_run']
    parts=[]
    for role in ['SP','RP']:
        frame=pd.read_parquet(pe.OUT/f'scored_{year}_{role}.parquet',columns=columns+['hgb_full_run'])
        bundle=joblib.load(pe.OUT/f'model_{year}_{role}_run_hgb_full.joblib')
        frame['risk']=frame.pop('hgb_full_run');frame['threshold']=bundle['warning_threshold'];parts.append(frame)
    combined=pd.concat(parts,ignore_index=True);result=replay_frame(combined)
    result['match']='none';result['lead_pa']=np.nan;result['lead_seconds']=np.nan
    events=result[result.changed.eq(1)].sort_values('old_decision_at').drop_duplicates('appearance_id').set_index('appearance_id')
    consumed=set()
    for idx,row in result[result.emitted].sort_values(['anchor_at','decision_id']).iterrows():
        if row.appearance_id not in events.index:continue
        event=events.loc[row.appearance_id];lead=event.seen_pa_count-row.seen_pa_count;seconds=event.old_decision_at-row.anchor_at
        if event.decision_id in consumed:continue
        match='same_boundary' if event.decision_id==row.decision_id and seconds>=0 else 'advance_2pa600s' if 1<=lead<=2 and 0<seconds<=600 else 'none'
        if match!='none':consumed.add(event.decision_id)
        result.loc[idx,['match','lead_pa','lead_seconds']]=[match,lead,seconds]
    write(result,f'replay_{year}.parquet');rows=[]
    for role,g in [('ALL',result)]+list(result.groupby('role')):
        alerts=g[g.emitted];known=alerts[alerts.target_observed]
        rows.append({'role':role,'boundaries':len(g),'games':int(g.game_pk.nunique()),'appearances':int(g.appearance_id.nunique()),
            'alerts':len(alerts),'early_alerts':int(alerts.inning.le(3).sum()),'known':len(known),'unknown':len(alerts)-len(known),
            'observed_run_positive':int(known.y_run.sum()),'observed_ppv':float(known.y_run.mean()) if len(known) else None,
            'same_boundary':int(alerts.match.eq('same_boundary').sum()),'advance':int(alerts.match.eq('advance_2pa600s').sum()),
            'eligible_actual_changes':int(g.changed.sum()),'reasons':g.replay_reason.value_counts().to_dict()})
    save(f'replay_{year}.json',{'year':year,'groups':rows});print(f'16.1 {year}: {len(result):,} points, {int(result.emitted.sum())} unified alerts',flush=True)


def recent_reference():
    h=pd.read_parquet(f.q.n.r.OUT/'recent_history.parquet');h=h[h.year.le(2024)].sort_values(['pitcher_id','role','model_id','available_at'])
    for name,target in [('relative_stuff','recent_stuff'),('relative_location','recent_location'),('velocity','recent_velocity')]:
        h[target]=h.groupby(['pitcher_id','role','model_id'])[name].transform(lambda x:x.rolling(3,min_periods=1).mean())
    h['recent_n']=h.groupby(['pitcher_id','role','model_id']).cumcount().add(1).clip(upper=3)
    return h


def prepare(year):
    frame=pd.read_parquet(f.OUT/f'features_{year}.parquet');games=read(OUT/'cases.json')['games']
    print(f'16.2 {year}: own actor ASOF adapters for {len(frame):,} common anchors',flush=True)
    with b.connection() as c:
        c.register('f',frame);c.register('recent',recent_reference())
        for folder,name in [(FOUND,'bullpen_candidates'),(FOUND,'decisions'),(FOUND,'plays')]:c.read_parquet(str(folder/f'{name}_{year}.parquet')).create_view(name)
        c.read_parquet(str(f.q.n.r.OUT/'appearance_history.parquet')).create_view('apps')
        c.read_parquet(str(f.q.base.c.OUT/'pitcher_clock.parquet')).create_view('pc')
        c.read_parquet(str(b.PREP/'ability_history.parquet')).filter("actor='pitcher' AND split='All'").create_view('ability')
        c.read_parquet([str(f.q.n.r.OUT/f'pitch_observations_{y}.parquet') for y in range(2021,year+1)]).filter('time_reliable').create_view('pitches')
        c.register('selected_games',pd.DataFrame({'game_pk':games if year==2024 else []},dtype='int64'))
        c.execute('''CREATE TEMP TABLE pool AS SELECT f.decision_id,p.pitcher_id,p.previous_role option_role,p.cutoff_epoch snapshot_clock
            FROM f JOIN selected_games g USING(game_pk) JOIN bullpen_candidates p ON p.decision_id=f.snapshot_id
            WHERE p.nominal_eligible AND p.previous_role='RP' AND p.prior_observed_relief>0 AND p.pitcher_id<>f.outgoing_pitcher_id
            AND NOT EXISTS(SELECT 1 FROM apps a WHERE a.game_pk=f.game_pk AND a.team_id=f.team_id AND a.pitcher_id=p.pitcher_id AND a.entry_at<f.anchor_at)''')
        # Actual actor identity is used only to construct observed training actions/labels.
        c.execute('''CREATE TEMP TABLE requests AS SELECT DISTINCT decision_id,pitcher_id,option_role,is_current FROM(
            SELECT decision_id,outgoing_pitcher_id pitcher_id,role option_role,true is_current FROM f
            UNION ALL SELECT decision_id,actor_pitcher_id,'RP',false FROM f WHERE changed=1 AND actor_pitcher_id<>outgoing_pitcher_id
            UNION ALL SELECT decision_id,pitcher_id,option_role,false FROM pool)''')
        c.execute('''CREATE TEMP TABLE q AS SELECT row_number() OVER() request_id,r.*,f.anchor_at,f.anchor_at-72*3600 cut3,f.anchor_at-120*3600 cut5,
            f.current_pitches incumbent_pitches,f.current_bf incumbent_bf,f.prior_games_pitches_3d incumbent_load3,f.prior_games_pitches_5d incumbent_load5
            FROM requests r JOIN f USING(decision_id)''')
        rates=','.join(f'a.{key}_n/a.pa_n pitcher_{key}_rate' for key in f.OUTCOMES)
        own=c.execute('''SELECT q.request_id,a.available_at own_ability_at,a.pa_n ability_n,'''+rates+''',
            p.available_at own_last_pitch_at,p.cumulative_pitches-coalesce(p3.cumulative_pitches,0) own_load3,
            p.cumulative_pitches-coalesce(p5.cumulative_pitches,0) own_load5,h.available_at hand_at,h.p_throws pitcher_hand,
            r.available_at recent_at,r.model_id recent_model,r.recent_stuff,r.recent_location,r.recent_velocity,r.recent_n
            FROM q ASOF LEFT JOIN ability a ON q.pitcher_id=a.player_id AND q.option_role=a.role AND q.anchor_at>a.available_at
            ASOF LEFT JOIN pc p ON q.pitcher_id=p.pitcher_id AND q.anchor_at>p.available_at
            ASOF LEFT JOIN pc p3 ON q.pitcher_id=p3.pitcher_id AND q.cut3>p3.available_at
            ASOF LEFT JOIN pc p5 ON q.pitcher_id=p5.pitcher_id AND q.cut5>p5.available_at
            ASOF LEFT JOIN pitches h ON q.pitcher_id=h.pitcher_id AND q.anchor_at>h.available_at
            ASOF LEFT JOIN recent r ON q.pitcher_id=r.pitcher_id AND q.option_role=r.role AND q.anchor_at>r.available_at''').fetchdf()
        opts=c.execute('SELECT q.*,p.pitcher_id IS NOT NULL nominal_pool,p.snapshot_clock FROM q LEFT JOIN pool p USING(decision_id,pitcher_id)').fetchdf().merge(own,on='request_id',validate='one_to_one')
        labels=c.execute('''SELECT f.decision_id,p.outs_before,p.base_state_before,p.home_score_before,p.away_score_before,
            p.outs_after,p.base_state_after post_base,p.terminal_pitcher_id,p.is_complete
            FROM f JOIN decisions d USING(decision_id) JOIN plays p USING(outcome_key)''').fetchdf()
    # Strip incumbent actor fields before joining, so candidate actor histories cannot be overwritten.
    keep=['decision_id','game_pk','team_id','appearance_id','outgoing_pitcher_id','role','anchor_at','game_closed_at','inning','half','scheduled_innings','phase','outs','base_state','defense_lead','entry_at','at_bat_number','seen_pa_count','snapshot_at','lookback_complete','changed','target_start','target_available_at','actor_pitcher_id','final_pitcher_id','physical_actors','bad_timing','organic_pa_eligible','observed_pa_result','target_runs','lineup_status']+LIVE+[f'forecast{i}_{x}' for i in [1,2,3] for x in ['id','identity_at','history_at','league_at','log_n','nonout','extra_base','k','bb']]
    opts=opts.drop(columns=['anchor_at']).merge(frame[keep],on='decision_id',validate='many_to_one').merge(labels,on='decision_id',validate='many_to_one')
    opts['current_pitches']=np.where(opts.is_current,opts.incumbent_pitches,0.);opts['current_bf']=np.where(opts.is_current,opts.incumbent_bf,0.)
    opts['prior_games_pitches_3d']=np.where(opts.is_current,opts.incumbent_load3,opts.own_load3)
    opts['prior_games_pitches_5d']=np.where(opts.is_current,opts.incumbent_load5,opts.own_load5)
    opts['rest_hours']=(opts.anchor_at-opts.own_last_pitch_at)/3600
    opts['ability_log_n']=np.log1p(opts.ability_n);opts['recent_age_hours']=(opts.anchor_at-opts.recent_at)/3600
    opts.loc[~opts.is_current,LIVE]=np.nan
    for key in ['inning','outs','base_state','scheduled_innings']:opts[key]=pd.to_numeric(opts[key],errors='raise')
    opts['extra']=opts.inning.gt(opts.scheduled_innings).astype(int)
    opts['runs_to_pa_end']=opts.target_runs
    opts.loc[opts.outs_after.ge(3),'post_base']=0
    initial_lead=np.where(opts.half.eq('top'),opts.home_score_before-opts.away_score_before,opts.away_score_before-opts.home_score_before)
    good=opts.actor_pitcher_id.eq(opts.pitcher_id)&opts.final_pitcher_id.eq(opts.pitcher_id)&opts.physical_actors.eq(1)&opts.bad_timing.eq(0)&opts.organic_pa_eligible.fillna(False)&opts.is_complete
    good &= opts.target_start.ge(opts.anchor_at)&opts.target_available_at.gt(opts.target_start)&opts.target_available_at.le(opts.game_closed_at)
    good &= opts.outs.eq(opts.outs_before)&opts.base_state.eq(opts.base_state_before)&opts.defense_lead.eq(initial_lead)&opts.target_runs.between(0,4)
    group=f.outcome_group(opts.observed_pa_result,opts.outs_before,opts.outs_after);good &= group.notna()
    opts['target']=group.map({key:i for i,key in enumerate(f.OUTCOMES)}).where(good)
    legal=np.zeros(len(opts),bool)
    for row in opts[good].itertuples():legal[row.Index]=b.legal_transition(int(row.outs),int(row.base_state),int(row.target_runs),int(row.outs_after),int(row.post_base))
    opts['observed']=good&legal;opts.loc[~opts.observed,'target']=np.nan
    earliest=read(f.q.base.c.OUT/'cache.json')['earliest']
    opts['history_supported']=opts.ability_n.ge(30)&opts.pitcher_hand.isin(['L','R'])&opts.anchor_at.ge(earliest+14*86400)&opts.own_last_pitch_at.notna()
    for name in ['own_ability_at','own_last_pitch_at','hand_at','recent_at','snapshot_clock']:
        assert (opts[name].isna()|opts[name].lt(opts.anchor_at)).all(),name
    assert opts.loc[~opts.is_current,LIVE].isna().all().all()
    obs=opts[opts.observed].copy();assert obs.decision_id.is_unique
    write(obs,f'observed_{year}.parquet')
    if year==2024:write(opts[opts.game_pk.isin(games)],'options_2024.parquet')
    save(f'prepare_{year}.json',{'year':year,'boundaries':len(frame),'observed_actions':len(obs),
        'groups':[{'role':role,'is_current':bool(current),'n':len(g),'supported':int(g.history_supported.sum()),'recent':int(g.recent_at.notna().sum())} for (role,current),g in obs.groupby(['option_role','is_current'])],
        'candidate_live_fields_borrowed':0,'clock_violations':0})
    print(f'16.2 {year}: {len(obs):,} observed actual-actor labels, own histories verified',flush=True)


def design(frame):
    result=frame.copy()
    for key in NUM+LIVE:result[key]=pd.to_numeric(result[key],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    for key in CAT:result[key]=result[key].astype('string').fillna('unknown').astype(str)
    return result


def train(year):
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.pipeline import make_pipeline
    from sklearn.ensemble import HistGradientBoostingClassifier
    from scipy.optimize import minimize_scalar
    train=pd.concat([pd.read_parquet(OUT/f'observed_{y}.parquet') for y in range(2021,year)],ignore_index=True)
    train=train[train.history_supported].copy();games=train.groupby('game_pk').agg(first=('anchor_at','min'),last=('game_closed_at','max')).sort_values(['last','game_pk'])
    split=int(.8*len(games));cut=games.iloc[split]['first'];fit_ids=games[games['last']<cut].index;cal_ids=games.iloc[split:].index
    fit=train[train.game_pk.isin(fit_ids)].copy();cal=train[train.game_pk.isin(cal_ids)].copy()
    if len(fit)>60000:fit=fit.sample(60000,random_state=SEED).sort_values(['anchor_at','decision_id'])
    assert fit.game_closed_at.max()<cal.anchor_at.min()
    valid=pd.read_parquet(OUT/f'observed_{year}.parquet');valid=valid[valid.history_supported].copy()
    assert cal.game_closed_at.max()<valid.anchor_at.min()
    write(pd.concat([fit[['decision_id','game_pk']].assign(part='fit'),cal[['decision_id','game_pk']].assign(part='cal')]),f'split_{year}.parquet')
    reports=[]
    with threadpool_limits(limits=2):
        for name in ['base','rich']:
            nums=NUM+(LIVE if name=='rich' else [])
            model=make_pipeline(ColumnTransformer([('num','passthrough',nums),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CAT)],sparse_threshold=0.),
                HistGradientBoostingClassifier(max_iter=60,max_leaf_nodes=7,min_samples_leaf=200,l2_regularization=10.,learning_rate=.05,max_bins=63,early_stopping=False,random_state=SEED))
            model.fit(design(fit),fit.target.astype(int));p=pe.raw_probability(model,design(cal),9)
            optimal=minimize_scalar(lambda t:-np.log(pe.temperature(p,t)[np.arange(len(cal)),cal.target.astype(int)]).mean(),bounds=(.5,3),method='bounded')
            bundle={'model':model,'temperature':float(optimal.x),'prior':(np.bincount(fit.target.astype(int),minlength=9)+1)/(len(fit)+9),
                'numeric_ranges':{k:[float(fit[k].min()),float(fit[k].max())] for k in nums if fit[k].notna().any()},
                'groups':{f'{r}:{v}':len(g) for (r,v),g in fit.groupby(['option_role','is_current'])},'fit_last_at':float(fit.game_closed_at.max()),'cal_last_at':float(cal.game_closed_at.max())}
            joblib.dump(bundle,OUT/f'model_{year}_{name}.joblib');p=pe.predict(bundle,design(valid));metric=pe.metrics_pa(valid.target.astype(int),p,bundle['prior'])
            rows=[]
            for (role,current),g in valid.groupby(['option_role','is_current']):
                pos=valid.index.get_indexer(g.index);rows.append({'role':role,'is_current':bool(current),**pe.metrics_pa(g.target.astype(int),p[pos],bundle['prior'])})
            reports.append({'model':name,'metrics':metric,'groups':rows})
            print(f'16.2 {year}/{name}: validation {len(valid):,} LL={metric["log_loss"]:.6f}',flush=True)
    tables=b.fit_transitions(train)
    # Historical transition and pitch-count references never use validation outcomes.
    pitch_counts={}
    with b.connection() as c:
        c.read_parquet([str(FOUND/f'plays_{y}.parquet') for y in range(2021,year)]).create_view('p')
        c.register('train_ids',train[['game_pk','at_bat_number','option_role','target']])
        counts=c.execute('SELECT t.option_role,t.target,p.pitch_count FROM train_ids t JOIN p USING(game_pk,at_bat_number) WHERE p.pitch_count BETWEEN 1 AND 20').fetchdf()
    for role in ['SP','RP']:
        for k in range(9):
            values=counts.loc[counts.option_role.eq(role)&counts.target.eq(k),'pitch_count'].to_numpy(int)
            pitch_counts[(role,k)]=values if len(values) else np.array([4])
    joblib.dump({'tables':tables,'pitch_counts':pitch_counts,'max_pitch':train.groupby('option_role').current_pitches.max().to_dict(),
        'inter_pa_rest_hours':float(train.loc[train.is_current&train.phase.eq('within_inning'),'rest_hours'].median())},OUT/f'transitions_{year}.joblib')
    save(f'fit_{year}.json',{'year':year,'fit':len(fit),'cal':len(cal),'validation':len(valid),'fit_last_at':float(fit.game_closed_at.max()),'cal_first_at':float(cal.anchor_at.min()),'cal_last_at':float(cal.game_closed_at.max()),'validation_first_at':float(valid.anchor_at.min()),'models':reports})


def select():
    scores={name:float(np.mean([next(x for x in read(OUT/f'fit_{y}.json')['models'] if x['model']==name)['metrics']['log_loss'] for y in [2022,2023]])) for name in ['base','rich']}
    value={'selected':min(scores,key=scores.get),'development_mean_log_loss':scores,'uses2024':False}
    if (OUT/'selection.json').exists():assert read(OUT/'selection.json')==value
    assert not (OUT/'model_2024_base.joblib').exists(),'Selection must precede2024 bridge fit'
    save('selection.json',value);print('16 bridge selection frozen',value,flush=True)


def value_state(frame,bundle):
    state=frame.copy();state['extra']=state.inning.gt(state.scheduled_innings).astype(int)
    state['bottom']=state.half.eq('bottom').astype(int);state['score_diff']=np.where(state.bottom.eq(0),state.defense_lead,-state.defense_lead)
    state['balls']=state['strikes']=0;state['research_home_we']=b.we_predict(bundle,state)
    state['research_re']=[r['mean'] if r else np.nan for r in b.re_get(state,bundle['re'])]
    return state


def event_values(initial,runs,outs,bases,bundle,half=False):
    post,terminal=b.post_state(initial,runs,outs,bases);future=b.we_predict(bundle,post);known=np.isfinite(terminal);future[known]=terminal[known]
    wpa=np.where(initial.bottom.eq(0),1,-1)*(future-initial.research_home_we.to_numpy())
    remaining=np.asarray([r['mean'] if r else np.nan for r in b.re_get(pd.DataFrame({'outs':outs,'base_state':bases,'extra':initial.extra}),bundle['re'])]);remaining[known]=0
    re24=initial.research_re.to_numpy()-runs-remaining
    return wpa,re24


def in_range(frame,bundle):
    ok=np.ones(len(frame),bool)
    for key,(low,high) in bundle['numeric_ranges'].items():
        ok &= frame[key].isna().to_numpy()|frame[key].between(low,high).to_numpy()
    return ok


def simulate_arm(option_rows,draws,models,reference,we,league):
    frame=value_state(option_rows.reset_index(drop=True),we);initial=frame.copy();n=len(frame)
    total=np.zeros(n,int);active=np.ones(n,bool);unsupported=np.zeros(n);outside=np.zeros(n,bool)
    first=None
    for step in range(MAX_PA):
        indices=np.flatnonzero(active)
        if not len(indices):break
        work=frame.iloc[indices].copy().reset_index(drop=True);u=draws[step,indices]
        if step:
            # Only the first three forecast identities are available. No future actual lineup.
            for slot in [1,2,3]:
                source=step+slot
                for key in ['log_n','nonout','extra_base','k','bb']:
                    work[f'forecast{slot}_{key}']=initial.iloc[indices][f'forecast{source}_{key}'].to_numpy() if source<=3 else (0. if key=='log_n' else league[key][indices])
            work[LIVE]=np.nan;work['is_current']=True;work['phase']='within_inning';work['rest_hours']=reference['inter_pa_rest_hours']
        bundle=models[0 if step==0 else 1]
        outside[indices]|=~in_range(work,bundle)
        outside[indices]|=work.current_pitches.to_numpy()>work.option_role.map(reference['max_pitch']).to_numpy()
        p=pe.predict(bundle,design(work));events,mass=action.draw_transition(work,p,reference['tables'],u[:,0]);unsupported[indices]=np.maximum(unsupported[indices],mass)
        target,runs,outs,bases=events.T;total[indices]+=runs
        frame.loc[indices,'defense_lead']=initial.defense_lead.to_numpy()[indices]-total[indices]
        frame.loc[indices,'outs']=outs;frame.loc[indices,'base_state']=bases
        increment=np.zeros(len(work),int)
        for role in ['SP','RP']:
            for k in range(9):
                mask=work.option_role.eq(role).to_numpy()&(target==k);values=reference['pitch_counts'][(role,k)]
                increment[mask]=values[np.minimum((u[mask,1]*len(values)).astype(int),len(values)-1)]
        frame.loc[indices,'current_pitches']=work.current_pitches.to_numpy()+increment
        frame.loc[indices,'current_bf']=work.current_bf.to_numpy()+1
        walkoff=work.half.eq('bottom').to_numpy()&work.inning.ge(work.scheduled_innings).to_numpy()&(frame.defense_lead.to_numpy()[indices]<0)
        active[indices[(outs>=3)|walkoff]]=False
        if step==0:
            wpa,re24=event_values(initial,total,frame.outs.to_numpy(int),frame.base_state.to_numpy(int),we)
            first={'wpa':wpa.copy(),'re24':re24.copy(),'unsupported':unsupported.copy(),'outside':outside.copy()}
    wpa,re24=event_values(initial,total,frame.outs.to_numpy(int),frame.base_state.to_numpy(int),we,half=True)
    return {'pa':first,'half':{'wpa':wpa,'re24':re24,'unsupported':unsupported,'outside':outside,'censored':active}}


def scenarios(batch):
    opts=pd.read_parquet(OUT/'options_2024.parquet');cases=opts[opts.is_current].sort_values(['game_pk','anchor_at','decision_id']).reset_index(drop=True)
    start=batch*32;cases=cases.iloc[start:start+32];winner=read(OUT/'selection.json')['selected']
    models={name:joblib.load(OUT/f'model_2024_{name}.joblib') for name in ['base','rich']}
    reference=joblib.load(OUT/'transitions_2024.joblib');we=joblib.load(context(2024));prior=pd.read_parquet(f.OUT/'league_prior.parquet')
    rows=[];excluded=[];prepared=[]
    for case in cases.itertuples():
        group=opts[opts.decision_id.eq(case.decision_id)];current=group[group.is_current];nominal=group[group.nominal_pool&~group.is_current];pool=nominal[nominal.history_supported]
        reason=None
        if not case.history_supported:reason='incumbent_history_unsupported'
        elif len(pool)<2:reason='fewer_than_two_supported_nominal_RP'
        elif not models[winner]['groups'].get(f'{case.option_role}:True',0)>=30 or models[winner]['groups'].get('RP:False',0)<30:reason='entry_training_support'
        if reason:excluded.append({'decision_id':case.decision_id,'reason':reason,'nominal':len(nominal),'supported':len(pool)});continue
        league=prior[prior.available_at.lt(case.anchor_at)].iloc[-1]
        league={'nonout':1-league['k']-league['other_out'],'extra_base':league['hr']+league['double']+league['triple'],'k':league['k'],'bb':league['bb']}
        rng=np.random.default_rng(SEED+int(hashlib.md5(case.decision_id.encode()).hexdigest()[:8],16));draws=rng.random((MAX_PA,PATHS,2));choice=rng.random(PATHS)
        prepared.append((case,current,pool,nominal,league,draws,choice))
    with threadpool_limits(limits=2):
        for variant in ['full_pool','rest24','load72_le40','other_model']:
            selected=[];current_rows=[];pool_rows=[];all_draws=[];leagues=[]
            for case,current,pool,nominal,league,draws,choice in prepared:
                subpool=pool[pool.rest_hours.ge(24)] if variant=='rest24' else pool[pool.prior_games_pitches_3d.le(40)] if variant=='load72_le40' else pool
                if len(subpool)<2:
                    rows.append({'decision_id':case.decision_id,'variant':variant,'status':'insufficient_pool','pool_n':len(subpool)});continue
                subpool=subpool.sort_values('pitcher_id');selected.append((case,len(subpool),len(nominal)))
                current_rows.append(current.iloc[np.zeros(PATHS,int)])
                pool_rows.append(subpool.iloc[np.minimum((choice*len(subpool)).astype(int),len(subpool)-1)])
                all_draws.append(draws);leagues.append(league)
            if not selected:continue
            shared=np.concatenate(all_draws,axis=1);league={key:np.repeat([v[key] for v in leagues],PATHS) for key in leagues[0]}
            first_name=('rich' if winner=='base' else 'base') if variant=='other_model' else winner
            arms=[simulate_arm(pd.concat(z,ignore_index=True),shared,[models[first_name],models['base']],reference,we,league) for z in [current_rows,pool_rows]]
            for ci,(case,pool_n,nominal_n) in enumerate(selected):
                sl=slice(ci*PATHS,(ci+1)*PATHS)
                result={'decision_id':case.decision_id,'game_pk':int(case.game_pk),'role':case.role,'inning':int(case.inning),'half':case.half,'variant':variant,'status':'modeled','pool_n':pool_n,'nominal_n':nominal_n,'recommendation_allowed':False}
                for horizon in ['pa','half']:
                    unsupported=max(float(a[horizon]['unsupported'][sl].max()) for a in arms);outside=bool(any(a[horizon]['outside'][sl].any() for a in arms))
                    censored=bool(any(a[horizon].get('censored',np.zeros(len(shared[0]),bool))[sl].any() for a in arms))
                    result.update({horizon+'_supported':bool(unsupported<=.01 and not outside and not censored),horizon+'_unsupported_mass_max':unsupported,horizon+'_extrapolated':outside,horizon+'_censored':censored})
                    for metric in ['wpa','re24']:
                        delta=arms[1][horizon][metric][sl]-arms[0][horizon][metric][sl];mean=float(delta.mean());se=float(delta.std(ddof=1)/np.sqrt(PATHS));key=horizon+'_'+metric
                        result.update({key+'_continue':float(arms[0][horizon][metric][sl].mean()),key+'_pool':float(arms[1][horizon][metric][sl].mean()),key+'_delta':mean,key+'_mc95_low':mean-1.96*se,key+'_mc95_high':mean+1.96*se})
                    key=horizon+'_wpa';result[horizon+'_direction']='pool_higher' if result[horizon+'_supported'] and result[key+'_mc95_low']>0 else 'continue_higher' if result[horizon+'_supported'] and result[key+'_mc95_high']<0 else 'uncertain_or_unsupported'
                rows.append(result)
            print(f'16.2/3 batch{batch}/{variant}: {len(selected)} decisions x{PATHS} paired paths',flush=True)
    write(pd.DataFrame(rows),f'scenarios_{batch:03d}.parquet');save(f'excluded_{batch:03d}.json',excluded)
    print(f'Batch{batch} complete: {len(cases)} boundaries',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','replay','prepare','train','select','scenarios']);parser.add_argument('--year',type=int,choices=range(2021,2025));parser.add_argument('--batch',type=int);args=parser.parse_args()
    if args.stage!='freeze':assert read(OUT/'protocol.json')==protocol(),'Frozen source/protocol mismatch'
    if args.stage in ['replay','prepare','train']:globals()[args.stage](args.year)
    elif args.stage=='scenarios':scenarios(args.batch)
    else:globals()[args.stage]()
