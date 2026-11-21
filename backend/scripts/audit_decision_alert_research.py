"""Source-only14.2 completeness, causal-clock and accounting invariants."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_alert_research as q

b,r,p,a=q.b,q.r,q.p,q.a


def main():
    counts={}
    folders=[b.PREP,b.OUT,b.ROOT/'data/research/decision_ablation_v1',a.a.OUT,r.OUT,p.u.h.OUT,p.u.OUT,a.OUT,p.OUT,q.prior.OUT,q.OUT]
    for folder in folders:
        manifest=q.read(folder/'manifest.json')
        for row in manifest['files']:
            path=folder/row['path'];assert path.stat().st_size==row['bytes'] and b.digest(path)==row['sha256'],path
        counts[folder.name]=len(manifest['files']);print(f'{folder.name}: {len(manifest["files"])} hashes verified',flush=True)
    assert q.read(q.OUT/'protocol.json')==q.protocol()
    assert q.read(p.OUT/'protocol.json')==p.protocol()
    assert q.read(q.prior.OUT/'protocol.json')==q.prior.protocol()
    for guard in q.read(b.TEMPORAL/'formal_model_guards.json'):assert b.digest(Path(guard['path']))==guard['sha256']
    prep=q.read(q.OUT/'preparation.json');summary=q.read(q.OUT/'summary.json');flow=summary['flow']
    for source in prep['feed_sources']:assert b.digest(Path(source['path']))==source['sha256']
    raw=pd.read_parquet(q.OUT/'boundaries.parquet');points=pd.read_parquet(q.OUT/'point_ledger.parquet')
    events=pd.read_parquet(q.OUT/'event_ledger.parquet');alerts=pd.read_parquet(q.OUT/'alerts.parquet');pairs=pd.read_parquet(q.OUT/'matches.parquet')
    values=pd.read_parquet(q.OUT/'action_values.parquet');cases=pd.read_parquet(q.OUT/'cases.parquet')
    full=pd.read_parquet(q.OUT/'full_options.parquet');projected=pd.read_parquet(q.OUT/'options.parquet')
    assert len(raw)==len(points)==flow['raw_boundaries'] and set(raw.decision_id)==set(points.decision_id)
    assert raw.decision_id.is_unique and points.decision_id.is_unique and alerts.decision_id.is_unique and events.event_id.is_unique
    assert len(cases)==len(values)==flow['modeled'] and set(cases.decision_id)==set(values.decision_id)
    assert np.isfinite(values[['wpa_continue','wpa_pool','wpa_delta','re24_delta','pitches_continue','pitches_pool']]).all().all()
    assert values.wpa_continue.between(-1,1).all() and values.wpa_pool.between(-1,1).all()
    assert values.pitches_continue.ge(0).all() and values.pitches_pool.ge(0).all()
    assert int(values.simulation_supported.sum())==flow['simulation_supported']
    assert int(points.point_reason.eq('qualifies').sum())==flow['qualifying_points']
    assert int(points.run_length.ge(q.logic.RULES['persistence_boundaries']).sum())==flow['persistent_points']
    assert int(events.modeled_exact_boundary.sum())==flow['official_modeled_exact']
    assert int(events.modeled_window_opportunity.sum())==flow['official_modeled_window']
    assert full.request_id.is_unique and np.array_equal(full._row.to_numpy(),np.arange(len(full)))
    pd.testing.assert_frame_equal(full[projected.columns],projected,check_exact=True)
    assert full.loc[~full.is_current,list(p.LIVE_MAP)].isna().all().all()
    assert full.forecast_role.eq(np.where(full.is_current,full.option_role,'RP')).all()
    for field in full.columns:
        if field.endswith(('_observed_at','_history_at','_reference_at')):
            present=pd.to_numeric(full[field],errors='coerce');assert (present.dropna()<full.loc[present.notna(),'decision_at']).all(),field
    with r.connect() as c:
        c.read_parquet(str(b.PREP/'prepared_features_2024.parquet')).create_view('f')
        expected=[int(row[0]) for row in c.execute('SELECT game_pk FROM f GROUP BY game_pk ORDER BY md5(cast(game_pk AS VARCHAR)),game_pk LIMIT32'.replace('LIMIT32','LIMIT 32')).fetchall()]
        assert expected==prep['games'] and set(expected)==set(raw.game_pk)
        c.register('games',pd.DataFrame({'game_pk':expected}))
        c.read_parquet(str(q.FOUNDATION/'events_2024.parquet')).create_view('e')
        official=c.execute('SELECT event_id FROM e JOIN games USING(game_pk) WHERE is_pitch_change').fetchdf()
        assert set(official.event_id)==set(events.event_id)
        c.read_parquet(str(q.FOUNDATION/'plays_2024.parquet')).create_view('plays')
        c.register('raw',raw[['decision_id','outcome_key','game_pk','team_id','defensive_ordinal','completed_pa_before']])
        checks=c.execute('SELECT raw.*,p.is_complete AND p.is_batter_faced completed FROM raw JOIN plays p USING(outcome_key)').fetchdf()
        for _,g in checks.sort_values('defensive_ordinal').groupby(['game_pk','team_id']):
            assert g.defensive_ordinal.tolist()==list(range(1,len(g)+1))
            clock=g.completed.astype(int).cumsum()-g.completed.astype(int)
            assert np.array_equal(clock.to_numpy(),g.completed_pa_before.to_numpy())
    for _,g in points.groupby(['game_pk','team_id']):
        g=g.sort_values('defensive_ordinal').reset_index(drop=True);issued=g[g.alert_emitted]
        assert issued.appearance_id.is_unique
        assert (issued.completed_pa_before.diff().dropna()>q.logic.RULES['cooldown_defensive_pa']).all()
        for index,row in issued.iterrows():
            assert index>0 and row.point_reason=='qualifies' and row.run_length>=2
            previous=g.iloc[index-1]
            assert previous.point_reason=='qualifies' and previous.appearance_id==row.appearance_id
            assert previous.inning==row.inning and previous.half==row.half and previous.defensive_ordinal+1==row.defensive_ordinal
    assert not points.loc[points.wpa_delta.isna(),'alert_emitted'].any()
    assert len(alerts)==flow['independent_alerts'] and set(alerts.decision_id)==set(points.loc[points.alert_emitted,'decision_id'])
    assert pairs.decision_id.is_unique and pairs.event_id.is_unique
    for pair in pairs.itertuples():
        alert=alerts[alerts.decision_id.eq(pair.decision_id)].iloc[0]
        event=events[events.event_id.eq(pair.event_id)].iloc[0]
        assert q.logic.eligible_pair(alert,event)==pair.match_kind
        assert alert.game_pk==event.game_pk and alert.team_id==event.team_id and alert.appearance_id==event.outgoing_appearance_id
        if pair.match_kind=='same_boundary':assert event.boundary_decision_id==alert.decision_id
        else:assert 1<=pair.lead_defensive_pa<=2 and 0<pair.lead_seconds<=600
    assert len(events)==flow['official_changes']==flow['matched_alerts']+flow['unmatched_events']
    assert len(alerts)==flow['matched_alerts']+flow['unmatched_alerts']
    assert len(pairs)==flow['same_boundary']+flow['advance_window']
    assert sum(summary['point_reasons'].values())==len(points)
    assert sum(summary['alert_reasons'].values())==len(points)
    assert sum(summary['event_reasons'].values())==len(events)
    assert sum(summary['unmatched_alert_reasons'].values())==flow['unmatched_alerts']
    assert flow['operational_recommendations']==0 and not summary['recommendation_allowed'] and not summary['test2025_outcomes_examined']
    assert not values.recommendation_allowed.any() and not values.individual_ranking_allowed.any()
    with threadpool_limits(limits=2):
        probability=q.first_probabilities(full,q.joblib.load(r.OUT/'baseline_matchup.joblib'),0)
    assert np.isfinite(probability).all() and (probability>0).all() and np.allclose(probability.sum(axis=1),1,atol=1e-12)
    track=q.read(b.ROOT/'docs/PROJECT_TRACKER.json');project=next(x for x in track['projects'] if x['id']=='pitcher-decision-support')
    assert sum(x['status']=='done' for x in project['slices'])==35 and len(project['slices'])==43
    assert all(x['status']=='planned' for x in project['slices'] if x['id'] in ['15','16','17','18','19','20'])
    snapshot=q.read(b.ROOT/'frontend/data/pitcherDecisionPlan.json');published=q.read(b.ROOT/'data/sample/petehub_pitcher_decision_alert_research_v1.json')
    review=published['rule_review']
    assert review==q.read(q.OUT/'rule_review.json')
    assert review['review_source_sha256']==b.digest(b.ROOT/'backend/scripts/export_decision_alert_research.py')
    assert {k:v for k,v in published.items() if k!='rule_review'}==summary
    assert snapshot['project']==project and snapshot['alertResearch']==published
    q.b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_alert_research_audit_v1.json',{
        'version':'decision_alert_research_source_audit_v1','frozen_files':counts,'flow':flow,
        'rules_frozen':True,'raw_boundaries_and_event_denominators_complete':True,'one_to_one_identity_and_time_checked':True,
        'probability_simplex_checked':True,'old_models_unchanged':True,'progress':'35/43','stop':'14.2',
        'test2025_outcomes_examined':False,'visual_acceptance':'pending user'})
    print('14.2 source, full-sequence, clock, de-duplication, one-to-one and authority gates passed; visual acceptance belongs to user',flush=True)


if __name__=='__main__':main()
