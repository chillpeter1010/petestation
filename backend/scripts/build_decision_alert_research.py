"""Slice14.2: bounded full-game research alerts, never operational recommendations.

Old model/simulation artifacts remain read-only. Only2024 is evaluated; fixed32
hash-selected games, first-PA selected RP model, later global baseline. Rules and
sample are frozen before simulation/matching; no outcome-based threshold tuning.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import run_decision_model_patch_impact as prior
from scripts import decision_alert_rules as logic

p,a,b,r=prior.p,prior.a,prior.b,prior.r
OUT=b.ROOT/'data/research/decision_alerts_v1'
FOUNDATION=b.ROOT/'data/research/decision_support_pipeline_20261114'
GAME_LIMIT=32
SEED=20261119


def read(path):return json.loads(path.read_text('utf-8'))


def save(name,value):b.save_json(OUT/name,value)


def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    assert read(p.OUT/'protocol.json')==p.protocol() and read(prior.OUT/'protocol.json')==prior.protocol()
    with r.connect() as c:
        for name in ['decisions','events','appearances','plays']:c.read_parquet(str(FOUNDATION/f'{name}_2024.parquet')).create_view(name)
        c.read_parquet(str(b.PREP/'prepared_features_2024.parquet')).create_view('prepared')
        c.read_parquet(str(b.SAMPLE/'decision_audit_2024.parquet')).create_view('audit')
        games=[int(row[0]) for row in c.execute('SELECT game_pk FROM prepared GROUP BY game_pk ORDER BY md5(cast(game_pk AS VARCHAR)),game_pk LIMIT ?',[GAME_LIMIT]).fetchall()]
        c.register('games',pd.DataFrame({'game_pk':games}))
        ledger=c.execute('''SELECT d.*,epoch(try_cast(d.decision_time AS TIMESTAMPTZ)) decision_at,
            row_number() OVER(PARTITION BY d.game_pk,d.team_id ORDER BY d.at_bat_number,d.event_index) defensive_ordinal,
            coalesce(sum(cast(p.is_complete AND p.is_batter_faced AS INTEGER)) OVER(PARTITION BY d.game_pk,d.team_id
                ORDER BY d.at_bat_number,d.event_index ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) completed_pa_before,
            coalesce(a.cohort_reason,'missing_cohort_audit') cohort_reason
            FROM decisions d JOIN games USING(game_pk) JOIN plays p USING(outcome_key) LEFT JOIN audit a USING(decision_id)
            WHERE d.decision_id LIKE '%:boundary' ORDER BY d.game_pk,d.at_bat_number,d.event_index''').fetchdf()
        cases=c.execute('''SELECT f.*,d.balls boundary_balls,d.strikes boundary_strikes,d.at_bat_number,d.event_index,
            d.official_date FROM prepared f JOIN games USING(game_pk) JOIN decisions d USING(decision_id)
            ORDER BY f.game_pk,d.at_bat_number''').fetchdf()
        c.register('cases',cases)
        c.read_parquet(str(b.OUT/'option_features_2024.parquet')).create_view('o')
        options=c.execute('''SELECT o.*,f.inning,f.half,f.scheduled_innings,f.defense_lead,
            f.outs,f.base_state,cast(f.inning>f.scheduled_innings AS INTEGER) extra,f.research_home_we,f.research_re
            FROM o JOIN cases f USING(decision_id) ORDER BY o.decision_id,o.is_current DESC,o.option_pitcher_id''').fetchdf()
        events=c.execute('''SELECT e.*,epoch(try_cast(e.event_time AS TIMESTAMPTZ)) event_at,
            old.appearance_id outgoing_appearance_id,old.role outgoing_role,
            d.decision_id raw_boundary_decision_id,
            CASE WHEN d.observed_change AND d.outgoing_pitcher_id=e.previous_pitcher_id
                AND d.incoming_pitcher_id=e.pitcher_id AND d.event_index=e.event_index THEN d.decision_id END boundary_decision_id
            FROM events e JOIN games USING(game_pk)
            LEFT JOIN appearances old ON old.game_pk=e.game_pk AND old.team_id=e.team_id
                AND old.pitcher_id=e.previous_pitcher_id AND old.exit_ab=e.at_bat_number AND old.exit_event_index=e.event_index
            LEFT JOIN decisions d ON d.game_pk=e.game_pk AND d.team_id=e.team_id AND d.at_bat_number=e.at_bat_number AND d.decision_id LIKE '%:boundary'
            WHERE e.is_pitch_change ORDER BY e.game_pk,e.at_bat_number,e.event_index''').fetchdf()
    assert ledger.decision_id.is_unique and events.event_id.is_unique
    events=events.merge(ledger[['game_pk','team_id','at_bat_number','defensive_ordinal','completed_pa_before','cohort_reason']],on=['game_pk','team_id','at_bat_number'],how='left',validate='many_to_one')
    write(ledger,'boundaries.parquet');write(events,'official_changes.parquet')
    print(f'14.2 fixed{len(games)} games: {len(ledger):,} raw PA boundaries, {len(cases):,} prepared boundaries, {len(options):,} nominal option requests',flush=True)
    prepared_n=len(cases)
    options['request_id']=options.decision_id+':'+options.option_pitcher_id.astype(str)
    options=p.u.enrich_options(options,2024)
    cases,options,excluded=a.a.supported_options(cases,options)
    options['first_feature_extrapolated']=False
    for target,source in p.LIVE_MAP.items():options[target]=(pd.to_numeric(options[source],errors='coerce')-100).where(options.is_current)
    for role,name in prior.winners().items():
        fit=joblib.load(p.OUT/f'final_{role}_{name}.joblib');mask=options.forecast_role.eq(role)
        for name,(low,high) in fit['support_ranges'].items():
            options.loc[mask&options[name].notna()&~options[name].between(low,high),'first_feature_extrapolated']=True
    options['_row']=np.arange(len(options));write(options,'full_options.parquet');write(cases,'cases.parquet')
    need=set(b.LEVELS['matchup'][0]+b.LEVELS['matchup'][1])-{'pitcher_log_n','batter_log_n'}
    need.update(['_row','decision_id','option_pitcher_id','forecast_role','research_home_we','research_re','first_feature_extrapolated',
        'pitcher_own_split_n','pitcher_own_all_n','batter_own_split_n','batter_own_all_n','pitches_5d_before'])
    write(options[sorted(need)],'options.parquet');write(pd.DataFrame(excluded,columns=['decision_id','reason']),'case_exclusions.parquet')
    metadata=[];sources=[]
    with r.connect() as c:
        c.read_parquet(str(b.ROOT/'data/research/decision_support_slice1_20261112/feed_inventory_2024.parquet')).create_view('inventory')
        for game in games:
            source=c.execute('SELECT path,compressed_sha256 FROM inventory WHERE game_pk=?',[game]).fetchone()
            path=Path(source[0]);assert b.digest(path)==source[1]
            feed=json.loads(gzip.decompress(path.read_bytes()));teams=feed['gameData']['teams']
            metadata.append({'game_pk':game,'date':feed['gameData']['datetime']['officialDate'],
                'home':teams['home']['name'],'away':teams['away']['name'],
                'player_names':{str(int(pid.removeprefix('ID'))):person.get('fullName',pid) for pid,person in feed['gameData']['players'].items()}})
            sources.append({'path':str(path),'sha256':source[1]})
    save('preparation.json',{'games':games,'game_metadata':metadata,'feed_sources':sources,
        'raw_boundaries':len(ledger),'prepared_boundaries':prepared_n,
        'modeled_boundaries':len(cases),'option_rows':len(options),'case_exclusions':len(excluded),
        'selection':'first32 distinct prepared2024 game_pk by md5(cast(game_pk as VARCHAR)); no selection on substitutions, model gain or outcomes',
        'cohort_limit':'inherits Slice11 retrospective identity/action/nominal-pool exclusions; this is not deployment/population coverage',
        'rules':logic.RULES,'official_events':'retrospective evaluation ledger only; never input to alert state machine'})
    print(f'14.2 preparation ready: {len(cases):,} supported-option boundaries; original denominator and gaps retained',flush=True)


def protocol():
    paths=[Path(__file__),Path(logic.__file__),Path(a.__file__),p.OUT/'protocol.json',prior.OUT/'protocol.json',
        prior.OUT/'manifest.json',r.OUT/'baseline_matchup.joblib',b.OUT/'transitions.joblib',
        a.a.OUT/'simulation_reference.joblib',b.TEMPORAL/'models/frozen_2024/context.joblib']
    paths += [OUT/name for name in ['boundaries.parquet','official_changes.parquet','full_options.parquet','options.parquet','cases.parquet','case_exclusions.parquet','preparation.json']]
    paths += [FOUNDATION/f'{name}_2024.parquet' for name in ['decisions','events','appearances','plays']]
    paths += [b.PREP/'prepared_features_2024.parquet',b.OUT/'option_features_2024.parquet',b.SAMPLE/'decision_audit_2024.parquet']
    paths += [a.OUT/f'bootstrap_{i}_baseline.joblib' for i in range(a.BOOTSTRAPS)]
    for role,name in prior.winners().items():
        paths.append(p.OUT/f'final_{role}_{name}.joblib')
        paths += [prior.OUT/f'bootstrap_{i}_{role}.joblib' for i in range(a.BOOTSTRAPS)]
    return {'version':'decision_alerts_v1','input_sha256':{str(x.relative_to(b.ROOT)):b.digest(x) for x in paths},
        'evaluation_year':2024,'independent_test':False,'test2025_outcomes_examined':False,
        'game_limit':GAME_LIMIT,'selection':'fixed MD5 first32 games, complete raw PA-boundary sequence; no outcome-based replacement of excluded games',
        'rules':logic.RULES,'rule_status':'predeclared engineering research defaults, not trained/optimal clinical or operational thresholds; no threshold/window tuning from matching results',
        'persistence':'adjacent opposing-PA boundaries in same appearance and defensive half inning; any ineligible/unsupported/missing-value boundary breaks run',
        'cooldown':'next2 defensive PAs for same game/team, even after pitcher change; <=2 means cooling; at most one emission per appearance independently',
        'PA_clock':'advance/cooldown count only previously completed batter-faced plays, including zero-pitch IBB; raw non-batter/incomplete boundary remains a persistence gap, not a completed PA',
        'matching':'same-boundary iff official change is the boundary prelude and identity matches; else ahead1-2 defensive PA and <=600s, same game/team/outgoing appearance; chronological alerts, exact first else earliest eligible event, each used once',
        'event_denominator':'all official pitching-change events in selected games, including unmodeled/mid-PA/identity/clock exclusions; unmatched reasons and covered opportunities retained',
        'gain':'central delta>=.005 means+0.5 own-win-probability percentage points; paired MC95 and bootstrap80 lower>0, all9 no censor/extrapolation, maximum mean unsupported transition mass<=.01; RE24 report-only',
        'simulation':{'paths':a.PATHS,'bootstrap_models':a.BOOTSTRAPS,'max_PA':a.MAX_PA,'seed':SEED,
            'randomness':'per-game SHA256(seed:game_pk)32-bit RNG; same draws/league-batter identities/pool choices across both arms and all9 frozen models',
            'first_PA':prior.selected(),'future_PA':'13.1 repaired global matchup, no unobserved trajectory propagation',
            'pool':'same supported nominal RP criteria; uniform role pool only, no best hand/type/individual selection',
            'endpoint':'same current-half-end or walkoff, no later substitution; transitions/WE/RE/pitch-count reference fixed'},
        'availability':'active/warmup/medical/manual availability unknown; nominal research alerts do not authorize operational recommendations',
        'scope':'selected games in previously used2024 diagnostic; inherited retrospective cohort exclusions and no population weighting; no causal accuracy/profit claim',
        'stop':'14.2, no Slice15 or2025 final evaluation','recommendation_allowed':False,'individual_ranking_allowed':False}


def freeze():
    path=OUT/'protocol.json';value=protocol()
    if path.exists():assert read(path)==value,'Frozen experiment changed: preserve an explicit revision'
    save('protocol.json',value);print('14.2 sample, thresholds, matching window and code frozen before simulation/matching',flush=True)


def game_draws(game,n):
    seed=int(hashlib.sha256(f'{SEED}:{int(game)}'.encode()).hexdigest()[:8],16)
    rng=np.random.default_rng(seed)
    return rng.random((a.MAX_PA,n,a.PATHS,4)),rng.random((n,a.PATHS))


def first_probabilities(full,baseline,replicate):
    probability=b.probabilities(baseline['model'],b.design(full,'matchup',20,baseline['prior']))
    for role,name in prior.winners().items():
        fit=joblib.load(p.OUT/f'final_{role}_{name}.joblib' if replicate==0 else prior.OUT/f'bootstrap_{replicate-1}_{role}.joblib')
        mask=full.forecast_role.eq(role)
        if mask.any():probability[mask]=p.predict(fit,full.loc[mask])
    return probability


def simulate(model_only=None):
    assert read(OUT/'protocol.json')==protocol()
    full=pd.read_parquet(OUT/'full_options.parquet');options=pd.read_parquet(OUT/'options.parquet')
    cases=pd.read_parquet(OUT/'cases.parquet').sort_values(['game_pk','at_bat_number','decision_id']).reset_index(drop=True)
    reference=joblib.load(a.a.OUT/'simulation_reference.joblib');tables=joblib.load(b.OUT/'transitions.joblib')
    we=joblib.load(b.TEMPORAL/'models/frozen_2024/context.joblib')
    for replicate in ([model_only] if model_only is not None else range(a.BOOTSTRAPS+1)):
        rows=[]
        with threadpool_limits(limits=2):
            baseline=joblib.load(r.OUT/'baseline_matchup.joblib' if replicate==0 else a.OUT/f'bootstrap_{replicate-1}_baseline.joblib')
            cached=first_probabilities(full,baseline,replicate)
            original=a.first_probability
            a.first_probability=lambda frame,*_:cached[frame._row.to_numpy(dtype=int)]
            try:
                for game,g in cases.groupby('game_pk',sort=True):
                    g=g.reset_index(drop=True);draws,choices=game_draws(game,len(g))
                    print(f'14.2 model{replicate}/{a.BOOTSTRAPS} game{game}: {len(g)} boundaries',flush=True)
                    for start in range(0,len(g),48):
                        group=g.iloc[start:start+48];current_indices=[];pool_indices=[];pool_sizes=[]
                        for j,row in group.iterrows():
                            part=options[options.decision_id.eq(row.decision_id)];current_indices.extend(np.repeat(part[part.is_current].index[0],a.PATHS))
                            pool=part[~part.is_current].index.to_numpy();pool_sizes.append(len(pool))
                            pool_indices.extend(pool[np.minimum((choices[j]*len(pool)).astype(int),len(pool)-1)])
                        ids=np.repeat(group.index.to_numpy(),a.PATHS)
                        cur=options.loc[current_indices].reset_index(drop=True);pool=options.loc[pool_indices].reset_index(drop=True)
                        if replicate==0 and not (OUT/'cache_check.json').exists():
                            for work in [cur,pool]:
                                actual=first_probabilities(full.iloc[work._row.to_numpy(dtype=int)].reset_index(drop=True),baseline,replicate)
                                assert np.allclose(actual,cached[work._row.to_numpy(dtype=int)],atol=1e-13,rtol=0)
                            save('cache_check.json',{'central_current_and_pool_cached_vs_direct':'within1e-13','protocol_sha256':b.digest(OUT/'protocol.json')})
                        cv=a.simulate_arm(cur,ids,draws,baseline,{},reference,tables,we)
                        pv=a.simulate_arm(pool,ids,draws,baseline,{},reference,tables,we)
                        for local,case in enumerate(group.itertuples()):
                            row={'decision_id':case.decision_id,'pool_n':pool_sizes[local]}
                            for key in ['wpa','re24']:
                                delta=pv[key][local]-cv[key][local]
                                row[key+'_continue']=float(cv[key][local].mean());row[key+'_pool']=float(pv[key][local].mean())
                                row[key+'_delta']=float(delta.mean());row[key+'_mc_se']=float(delta.std(ddof=1)/np.sqrt(a.PATHS))
                            for key in ['pitches','bf']:
                                row[key+'_continue']=float(cv[key][local].mean());row[key+'_pool']=float(pv[key][local].mean())
                            row['censored_paths']=int((cv['censored'][local]|pv['censored'][local]).sum())
                            row['extrapolated_fraction']=float((cv['extrapolated'][local]|pv['extrapolated'][local]).mean())
                            row['unsupported_mass']=float(np.maximum(cv['unsupported'][local],pv['unsupported'][local]).mean())
                            rows.append(row)
            finally:a.first_probability=original
        result=pd.DataFrame(rows).sort_values('decision_id').reset_index(drop=True)
        assert len(result)==len(cases) and result.decision_id.is_unique
        path=OUT/f'scenario_model_{replicate}.parquet';write(result,path.name)
        save(f'scenario_model_{replicate}.json',{'model':replicate,'rows':len(result),'sha256':b.digest(path),'protocol_sha256':b.digest(OUT/'protocol.json')})
    print('14.2 frozen-model full-game simulations complete',flush=True)


def evaluate():
    assert read(OUT/'protocol.json')==protocol()
    frames=[]
    for i in range(a.BOOTSTRAPS+1):
        path=OUT/f'scenario_model_{i}.parquet';meta=read(OUT/f'scenario_model_{i}.json')
        assert b.digest(path)==meta['sha256'] and meta['protocol_sha256']==b.digest(OUT/'protocol.json')
        frames.append(pd.read_parquet(path))
    values=frames[0].copy()
    assert all(f.decision_id.equals(values.decision_id) for f in frames)
    for key in ['wpa','re24']:
        values[key+'_mc95_low']=values[key+'_delta']-1.96*values[key+'_mc_se'];values[key+'_mc95_high']=values[key+'_delta']+1.96*values[key+'_mc_se']
        samples=np.stack([f[key+'_delta'].to_numpy() for f in frames[1:]])
        values[key+'_bootstrap80_low'],values[key+'_bootstrap80_high']=np.quantile(samples,[.1,.9],axis=0)
    warnings=read(prior.OUT/'bootstrap.json')['replicates']
    assert not any(x['convergence_warning'] for x in warnings)
    values['simulation_supported']=(np.stack([f.censored_paths for f in frames]).max(axis=0)==0)&(np.stack([f.extrapolated_fraction for f in frames]).max(axis=0)==0)
    values['maximum_unsupported_mass']=np.stack([f.unsupported_mass for f in frames]).max(axis=0)
    values['point_reason']=logic.qualify(values);values['recommendation_allowed']=False;values['individual_ranking_allowed']=False
    write(values,'action_values.parquet')
    ledger=pd.read_parquet(OUT/'boundaries.parquet');cases=pd.read_parquet(OUT/'cases.parquet');excluded=pd.read_parquet(OUT/'case_exclusions.parquet')
    case_times=cases.set_index('decision_id').decision_at;ledger['decision_at']=ledger.decision_id.map(case_times).fillna(ledger.decision_at)
    for column in ['role','research_pa_li']:
        ledger[column]=ledger.decision_id.map(cases.set_index('decision_id')[column])
    ledger=ledger.merge(values,on='decision_id',how='left',validate='one_to_one')
    unsupported=ledger.decision_id.map(excluded.set_index('decision_id').reason)
    ledger['point_reason']=ledger.point_reason.fillna('cohort:'+ledger.cohort_reason.astype(str))
    ledger.loc[unsupported.notna(),'point_reason']='option_support:'+unsupported[unsupported.notna()]
    issued=logic.issue_alerts(ledger);write(issued,'point_ledger.parquet')
    alerts=issued[issued.alert_emitted].copy();events=pd.read_parquet(OUT/'official_changes.parquet')
    pairs=logic.match_events(alerts,events);write(pairs,'matches.parquet')
    alerts=alerts.merge(pairs,on='decision_id',how='left',validate='one_to_one')
    alerts['match_reason']=[row.match_kind if pd.notna(row.match_kind) else logic.unmatched_alert_reason(row,events) for row in alerts.itertuples()]
    write(alerts,'alerts.parquet')
    event_pairs=pairs.rename(columns={'decision_id':'matched_alert_id'})
    events=events.merge(event_pairs,on='event_id',how='left',validate='one_to_one')
    modeled=issued[issued.wpa_delta.notna()];coverage=[]
    for event in events.itertuples():
        group=modeled[modeled.game_pk.eq(event.game_pk)&modeled.team_id.eq(event.team_id)&modeled.appearance_id.eq(event.outgoing_appearance_id)]
        available=[row for row in group.itertuples() if logic.eligible_pair(row,event) is not None]
        exact=event.boundary_decision_id in set(group.decision_id)
        if pd.notna(event.matched_alert_id):reason=event.match_kind
        elif pd.isna(event.outgoing_appearance_id):reason='unknown_outgoing_appearance'
        elif not np.isfinite(event.event_at) or pd.isna(event.defensive_ordinal):reason='official_clock_or_boundary_unknown'
        elif not available:reason='no_modeled_boundary_in_fixed_window'
        elif not alerts.appearance_id.eq(event.outgoing_appearance_id).any():reason='no_persistent_alert_for_appearance'
        else:reason='alert_outside_fixed_window'
        coverage.append({'event_id':event.event_id,'modeled_exact_boundary':exact,'modeled_window_opportunity':bool(available),'event_reason':reason})
    events=events.merge(pd.DataFrame(coverage),on='event_id',validate='one_to_one');write(events,'event_ledger.parquet')
    preparation=read(OUT/'preparation.json');games=[]
    for meta in preparation['game_metadata']:
        game=meta['game_pk'];g=issued[issued.game_pk.eq(game)];ev=events[events.game_pk.eq(game)];al=alerts[alerts.game_pk.eq(game)]
        games.append({k:meta[k] for k in ['game_pk','date','home','away']}|{'boundaries':len(g),'modeled':int(g.wpa_delta.notna().sum()),
            'supported':int(g.simulation_supported.fillna(False).sum()),'qualifying':int(g.point_reason.eq('qualifies').sum()),
            'alerts':len(al),'official_changes':len(ev),'same_boundary':int(al.match_reason.eq('same_boundary').sum()),
            'advance':int(al.match_reason.eq('advance_window').sum()),'unmatched_alerts':int(al.event_id.isna().sum())})
    role_summary=[]
    for role in ['SP','RP']:
        g=issued[issued.role.eq(role)];al=alerts[alerts.role.eq(role)]
        role_summary.append({'role':role,'modeled':len(g),'qualifying':int(g.point_reason.eq('qualifies').sum()),'alerts':len(al),
            'same_boundary':int(al.match_reason.eq('same_boundary').sum()),'advance':int(al.match_reason.eq('advance_window').sum())})
    examples=[];names={meta['game_pk']:meta['player_names'] for meta in preparation['game_metadata']}
    for row in alerts.sort_values(['game_pk','team_id','defensive_ordinal']).itertuples():
        examples.append({'decision_id':row.decision_id,'game_pk':int(row.game_pk),'team_id':int(row.team_id),'inning':int(row.inning),'half':row.half,
            'role':row.role,'pitcher_id':int(row.outgoing_pitcher_id),'pitcher_name':names[row.game_pk].get(str(int(row.outgoing_pitcher_id)),str(row.outgoing_pitcher_id)),
            'wpa_delta':float(row.wpa_delta),'mc95':[float(row.wpa_mc95_low),float(row.wpa_mc95_high)],
            'bootstrap80':[float(row.wpa_bootstrap80_low),float(row.wpa_bootstrap80_high)],'re24_delta':float(row.re24_delta),
            'event_id':row.event_id if pd.notna(row.event_id) else None,'match_reason':row.match_reason,
            'lead_pa':int(row.lead_defensive_pa) if pd.notna(row.lead_defensive_pa) else None,
            'lead_seconds':float(row.lead_seconds) if pd.notna(row.lead_seconds) else None})
    matched=len(pairs);exact=int(pairs.match_kind.eq('same_boundary').sum())
    save('summary.json',{'version':'decision_alerts_v1','protocol_sha256':b.digest(OUT/'protocol.json'),'year':2024,'games':games,'rules':logic.RULES,
        'flow':{'games':len(games),'raw_boundaries':len(issued),'prepared_boundaries':preparation['prepared_boundaries'],
            'modeled':len(values),'simulation_supported':int(values.simulation_supported.sum()),'qualifying_points':int(issued.point_reason.eq('qualifies').sum()),
            'persistent_points':int(issued.run_length.ge(logic.RULES['persistence_boundaries']).sum()),'independent_alerts':len(alerts),
            'official_changes':len(events),'official_modeled_exact':int(events.modeled_exact_boundary.sum()),
            'official_modeled_window':int(events.modeled_window_opportunity.sum()),'same_boundary':exact,'advance_window':matched-exact,
            'matched_alerts':matched,'unmatched_alerts':len(alerts)-matched,'unmatched_events':len(events)-matched,
            'operational_recommendations':0},
        'roles':role_summary,'point_reasons':issued.point_reason.value_counts().to_dict(),'alert_reasons':issued.alert_reason.value_counts().to_dict(),
        'unmatched_alert_reasons':alerts.loc[alerts.event_id.isna(),'match_reason'].value_counts().to_dict(),
        'event_reasons':events.event_reason.value_counts().to_dict(),'alerts':examples,
        'correspondence':'descriptive counts on fixed selected games; same-boundary is retrospective alignment, not proven anticipatory detection; correspondence is not correctness/causal benefit',
        'limitations':['2024 already-used diagnostic, fixed32 games not population-weighted or a full-season alert total',
            'original retrospective identity/action/nominal-pool cohort exclusions retained, raw gaps reset persistence',
            'nominal role pools only; active/warmup/medical/manual availability unknown',
            'only first PA has selected RP state features; later PA global baseline and historical league batter fallback',
            'MC95/bootstrap80 are pointwise partial uncertainty, not sequence-wide false-alert control or complete uncertainty',
            'selection/overlap/causal strategy value and frozen2025 test remain Slices15-17'],
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'individual_ranking_allowed':False,'stop':'14.2'})
    print(f'14.2 results: {len(issued)} boundaries, {len(values)} modeled, {len(alerts)} unique alerts, {len(events)} official events; exact{exact}, advance{matched-exact}, unmatched{len(alerts)-matched}',flush=True)


def finalize():
    assert read(OUT/'protocol.json')==protocol()
    summary=read(OUT/'summary.json');b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice14_2_v1.json',summary)
    files=sorted(x for x in OUT.rglob('*') if x.is_file() and x.name!='manifest.json')
    save('manifest.json',{'version':'decision_alerts_v1','files':[{'path':x.relative_to(OUT).as_posix(),'bytes':x.stat().st_size,'sha256':b.digest(x)} for x in files]})
    print(f'14.2 {len(files)} evidence files frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','freeze','simulate','evaluate','finalize']);parser.add_argument('--model',type=int,choices=range(9))
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='simulate':simulate(args.model)
    else:globals()[args.stage]()
