"""Source/data-only checks for14.2.2-4. Never a visual or efficacy acceptance."""
from __future__ import annotations

from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_signal_calibration as n
from scripts import build_decision_signal_models as m
from scripts import build_decision_signal_replay as r
from scripts import decision_signal_episodes as e


def hashed(folder):
    manifest=n.read(folder/'manifest.json')
    for entry in manifest['files']:
        path=folder/entry['path']
        assert path.stat().st_size==entry['bytes'] and n.b.digest(path)==entry['sha256'],path
    print(f'{folder.name}: {len(manifest["files"])} retained hashes checked',flush=True)
    return len(manifest['files'])


def main():
    old=n.old;b=n.b
    folders=[b.PREP,b.OUT,b.ROOT/'data/research/decision_ablation_v1',old.a.a.OUT,n.r.OUT,m.u.h.OUT,m.u.OUT,old.a.OUT,m.p.OUT,old.prior.OUT,old.OUT]
    old_count=sum(hashed(folder) for folder in folders);assert old_count==969
    for guard in n.read(b.TEMPORAL/'formal_model_guards.json'):assert b.digest(Path(guard['path']))==guard['sha256']
    for key,protocol in [('normal',n.protocol),('feature',m.protocol),('model',m.model_protocol),('episode',r.protocol)]:
        assert n.read(n.OUT/f'{key}_protocol.json')==protocol(),key
        print(f'{key} protocol and source/input hashes checked',flush=True)
    artifact_count=hashed(n.OUT)
    for rel,sha in n.read(n.OUT/'manifest.json')['source_sha256'].items():assert b.digest(b.ROOT/rel)==sha,rel
    prior=b.ROOT/'data/research/decision_signal_lights_v1';sources=n.read(prior/'sources.json')
    for rel,sha in sources['inputs'].items():assert b.digest(b.ROOT/rel)==sha
    for rel,sha in sources['display_sources'].items():assert b.digest(n.OUT/'previous_display_contract'/rel)==sha
    assert b.digest(b.ROOT/'backend/scripts/export_decision_signal_lights.py')==sources['builder_sha256']
    assert n.read(prior/'prototype.json')==n.read(b.ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v1.json')
    rows=0;blocks=0
    for fold,cutoff,year in n.FOLDS:
        cutoff=pd.Timestamp(cutoff,tz='UTC').timestamp()
        raw=pd.read_parquet(n.OUT/f'blocks_{year}.parquet');blocks+=len(raw)
        assert raw.block_id.is_unique and raw.measured_pitches.eq(10).all()
        known=raw.personal_reference_at.notna()
        assert (raw.loc[known,'personal_reference_at']<raw.loc[known,'entry_at']).all()
        assert (raw.available_at>=raw.anchor_at).all()
        f=pd.read_parquet(n.OUT/f'features_{year}.parquet');rows+=len(f)
        assert f.request_id.is_unique
        for clock,anchor in [('available_at','decision_at'),('D_reference_at','reference_clock'),('personal_reference_at','reference_clock')]:
            known=f[clock].notna();assert (f.loc[known,clock]<f.loc[known,anchor]).all(),(year,clock)
        incoming=f[~f.is_current]
        assert incoming[[g+'_state' for g in 'ABC']].eq(-1).all().all()
        assert incoming[[v for g in 'ABC' for v in m.EXTRA[g]]].isna().all().all()
        for g in 'ABCD':assert f[g+'_state'].isin([-1,0,1,2]).all()
        # Actor joins must resolve to this actor's block, never merely the same game.
        actor=f[f.block_id.notna()].merge(raw[['block_id','pitcher_id']],on='block_id',how='left',validate='many_to_one')
        assert actor.is_current.all() and actor.option_pitcher_id.eq(actor.pitcher_id).all()
        for role in ['SP','RP']:
            bundle=joblib.load(n.OUT/f'normal_{fold}_{role}.joblib')
            assert bundle['fit_last_label']<bundle['cal_first_anchor']<=bundle['cal_last_label']<cutoff
            split=pd.read_parquet(n.OUT/f'normal_split_{fold}_{role}.parquet')
            fit=split[split.partition.eq('fit')];cal=split[split.partition.eq('calibration')]
            assert set(fit.game_pk).isdisjoint(cal.game_pk) and fit.available_at.max()<cal.anchor_at.min()
            assert cal.available_at.max()<cutoff
            assert all(x['fit_n']>500 and x['cal_n']>100 for x in bundle['models'].values())
        print(f'{year}: actor/unknown/block support and fit/cal clocks checked',flush=True)
    assert blocks==244179 and rows==545204
    guard=n.read(n.OUT/'feature_guard.json')
    for rel,sha in guard['files'].items():assert b.digest(n.OUT/rel)==sha
    for role in ['SP','RP']:
        result=n.read(n.OUT/f'pa_{role}.json');inner=n.read(n.OUT/f'inner_{role}.json')
        assert not inner['2024_used_for_selection'] and result['ranking_sha256']==b.digest(n.OUT/f'inner_{role}.json')
        assert result['selected']=='retain_previous' and not any(x['increment_gate'] for x in result['results'])
        ids=None
        for variant in m.VARIANTS:
            prob=pd.read_parquet(n.OUT/f'pa_{role}_{variant}.parquet')
            assert len(prob)==result['validation_n'] and prob.decision_id.is_unique
            assert ids is None or prob.decision_id.equals(ids)
            ids=prob.decision_id
            matrix=prob[['p_'+name for name in b.OUTCOMES]].to_numpy()
            assert np.isfinite(matrix).all() and (matrix>0).all() and np.allclose(matrix.sum(axis=1),1)
        assert not result['test2025_outcomes_examined']
        print(f'{role}: identical outcome validation denominators, probabilities and non-promotion checked',flush=True)
    selection=n.read(n.OUT/'episode_selection.json')
    assert not selection['2024_used_for_selection'] and not selection['matching_used_for_selection']
    assert all(not item['training_predictive_support'] for item in selection['selected'].values())
    for year in [2022,2023,2024]:
        f=r.monitoring_cohort(year);known=f.future_bad.notna()
        assert f.block_id.is_unique and f.is_current.all()
        assert (f.loc[known,'target_anchor']>=f.loc[known,'decision_at']).all()
        assert (f.loc[known,'target_at']>f.loc[known,'target_anchor']).all()
        assert f.loc[known,'target_block'].between(f.loc[known,'block_number']+1,f.loc[known,'block_number']+2).all()
        print(f'{year}: first-boundary-per-block and ENTIRELY future target clocks checked',flush=True)
    points=pd.read_parquet(n.OUT/'signal_point_ledger.parquet')
    assert len(points)==2376 and points.decision_id.is_unique
    original=pd.read_parquet(old.OUT/'point_ledger.parquet').set_index('decision_id').loc[points.decision_id]
    for key in ['wpa_delta','re24_delta','point_reason']:
        assert original[key].reset_index(drop=True).equals(points[key].reset_index(drop=True)),key
    threshold={role:item['minimum_red'] for role,item in selection['selected'].items()}
    logged,episodes=e.replay(points,threshold,{'SP':False,'RP':False})
    assert logged.state_event_entered.sum()==len(episodes)==1 and not logged.nominal_research_alert.any()
    saved=pd.read_parquet(n.OUT/'state_episodes.parquet');pd.testing.assert_frame_equal(saved,episodes)
    assert len(pd.read_parquet(n.OUT/'signal_alerts.parquet'))==len(pd.read_parquet(n.OUT/'signal_matches.parquet'))==0
    summary=n.read(n.OUT/'replay_summary.json');flow=summary['flow']
    assert flow['modeled']==1737 and flow['full_four']==842 and flow['official_events']==208
    assert flow['operational_recommendations']==0 and flow['observed_recovery']==0
    assert not summary['recommendation_allowed'] and not summary['test2025_outcomes_examined']
    data=n.read(b.ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v2.json')
    assert data==n.read(n.OUT/'display.json') and data['recommendationAllowed'] is False
    assert data['calibrationSummary']==n.read(n.OUT/'evidence.json')
    assert len(data['cases'])==len({c['id'] for c in data['cases']})==36
    early={x['id'] for x in n.read(prior/'prototype.json')['cases'] if x['pitches']<35}
    assert len(early)==7
    for case in data['cases']:
        assert case['gates']['validation']=='fail' and case['gates']['availability']=='unknown'
        if case['id'] in early:assert all(x['state']=='gray' for x in case['lights'] if x['id'] in 'ABC')
    project=next(x for x in n.read(b.ROOT/'docs/PROJECT_TRACKER.json')['projects'] if x['id']=='pitcher-decision-support')
    assert len(project['slices'])==47 and sum(x['status']=='done' for x in project['slices'])==39
    items={x['id']:x for x in project['slices']}
    assert all(items[x]['status']=='done' for x in ['14.2.1','14.2.2','14.2.3','14.2.4'])
    assert all(items[x]['status']=='planned' for x in ['15','16','17','18','19','20'])
    assert all('14.2.4' in items[x]['depends_on'] for x in ['15','20'])
    front=n.read(b.ROOT/'frontend/data/pitcherDecisionPlan.json')
    assert front['project']==project and front['signalLights']==data
    assert front['alertResearch']==n.read(b.ROOT/'data/sample/petehub_pitcher_decision_alert_research_v1.json')
    report={'version':'decision_signal_calibration_audit_v1','retained_artifact_hashes':old_count,'new_artifact_hashes':artifact_count,
        'blocks':blocks,'actor_rows':rows,'flow':flow,'old_result':{'alerts':11,'matches':0},'progress':'39/47','stop':'14.2.4',
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'visual_acceptance':'pending user',
        'limits':'Source/data/clock/accounting checks only, not proof of predictive improvement, fatigue or causal utility'}
    n.save('audit.json',report);b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_signal_calibration_audit_v1.json',report)
    print('14.2.2-4 source/data/clock/accounting gates passed; efficacy support not established; visual acceptance pending user',flush=True)


if __name__=='__main__':main()
