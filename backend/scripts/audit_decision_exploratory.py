"""Source/data contract audit; never browser or visual acceptance."""
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_exploratory as x


def main():
    assert x.read(x.OUT/'protocol.json')==x.protocol()
    old=x.read(x.OUT/'prior_hashes.json')
    for name,digest in old.items():assert x.b.digest(x.ROOT/name)==digest,name
    manifest=x.read(x.OUT/'manifest.json')
    for row in manifest['files']:assert x.b.digest(x.OUT/row['path'])==row['sha256'],row['path']
    for name,digest in manifest['sources'].items():assert x.b.digest(x.ROOT/name)==digest,name
    opts=pd.read_parquet(x.OUT/'options_2024.parquet')
    for clock in ['own_ability_at','own_last_pitch_at','hand_at','recent_at','snapshot_clock']:
        assert (opts[clock].isna()|opts[clock].lt(opts.anchor_at)).all(),clock
    assert opts.loc[~opts.is_current,x.LIVE].isna().all().all()
    assert not opts.duplicated(['decision_id','pitcher_id']).any()
    assert opts.loc[opts.nominal_pool,'option_role'].eq('RP').all()
    for y in [2021,2022,2023,2024]:
        data=pd.read_parquet(x.OUT/f'observed_{y}.parquet')
        assert data.decision_id.is_unique and data.actor_pitcher_id.eq(data.pitcher_id).all()
        assert data.final_pitcher_id.eq(data.pitcher_id).all() and data.target_start.ge(data.anchor_at).all()
        assert data.target_available_at.le(data.game_closed_at).all()
        assert data.loc[data.outs_after.ge(3),'post_base'].eq(0).all()
        for clock in ['own_ability_at','own_last_pitch_at','hand_at','recent_at']:
            assert (data[clock].isna()|data[clock].lt(data.anchor_at)).all(),(y,clock)
        assert data.loc[~data.is_current,x.LIVE].isna().all().all()
    for y in [2022,2023,2024]:
        flow=x.read(x.OUT/f'fit_{y}.json');assert flow['fit_last_at']<flow['cal_first_at']<=flow['cal_last_at']<flow['validation_first_at']
        split=pd.read_parquet(x.OUT/f'split_{y}.parquet');assert split.groupby('game_pk').part.nunique().max()==1
        data=pd.read_parquet(x.OUT/f'observed_{y}.parquet');assert data.decision_id.is_unique
        assert data.loc[data.outs_after.ge(3),'post_base'].eq(0).all()
        assert data.actor_pitcher_id.eq(data.pitcher_id).all() and data.final_pitcher_id.eq(data.pitcher_id).all()
        assert data.target_start.ge(data.anchor_at).all() and data.target_available_at.le(data.game_closed_at).all()
        # Direct retained probabilities on real incumbent AND entry cases.
        fit=joblib.load(x.OUT/f'model_{y}_base.joblib')
        p=x.pe.predict(fit,x.design(data.head(256)));assert np.isfinite(p).all() and np.allclose(p.sum(axis=1),1)
        replay=pd.read_parquet(x.OUT/f'replay_{y}.parquet');again=x.replay_frame(replay)
        assert np.array_equal(replay.emitted.to_numpy(),again.emitted.to_numpy())
        assert replay[replay.emitted].groupby(['game_pk','team_id','appearance_id']).size().max()<=1
        for _,g in replay[replay.emitted].groupby(['game_pk','team_id']):assert g.seen_pa_count.diff().dropna().gt(2).all()
    selection=x.read(x.OUT/'selection.json');assert not selection['uses2024']
    assert (x.OUT/'selection.json').stat().st_mtime_ns<(x.OUT/'model_2024_base.joblib').stat().st_mtime_ns
    values=pd.read_parquet(x.OUT/'scenarios_all.parquet');modeled=values[values.status.eq('modeled')]
    assert not values.duplicated(['decision_id','variant']).any()
    for horizon in ['pa','half']:
        for metric in ['wpa','re24']:
            key=horizon+'_'+metric
            assert np.isfinite(modeled[[key+'_delta',key+'_continue',key+'_pool',key+'_mc95_low',key+'_mc95_high']]).all().all()
            assert np.allclose(modeled[key+'_delta'],modeled[key+'_pool']-modeled[key+'_continue'])
        supported=modeled[horizon+'_supported'].eq(True)
        assert not modeled.loc[supported,horizon+'_extrapolated'].any() and not modeled.loc[supported,horizon+'_censored'].any()
        assert modeled.loc[supported,horizon+'_unsupported_mass_max'].le(.01).all()
    sample=x.read(x.ROOT/'data/sample/petehub_pitcher_decision_exploratory_v1.json')
    assert sample['stop']=='16.3' and not sample['recommendation_allowed'] and not sample['formal_efficacy_passed'] and not sample['test2025_outcomes_examined']
    assert len(sample['timeline'])==32
    for game in sample['timeline']:
        anchors={p['decisionId']:p for p in game['points'] if p['phase']=='anchor'}
        for alert in game['shadowWarnings']:assert alert['decisionId'] in anchors and alert['x']==anchors[alert['decisionId']]['x']
    tracker=x.read(x.ROOT/'docs/PROJECT_TRACKER.json');project=next(p for p in tracker['projects'] if p['id']=='pitcher-decision-support')
    assert len(project['slices'])==58 and sum(s['status']=='done' for s in project['slices'])==51
    states={s['id']:s['status'] for s in project['slices']};assert states['16']=='in_progress'
    assert all(states['16.'+str(i)]=='done' for i in [1,2,3]) and all(states[str(i)]=='planned' for i in range(17,22))
    report={'version':x.OUT.name,'passed':True,'prior_artifacts_unchanged':len(old),'new_artifacts_verified':len(manifest['files']),
        'candidate_rows':len(opts),'scenario_rows':len(values),'source_only':True,'visual_acceptance':'pending_user','formal_efficacy_passed':False,'test2025_outcomes_examined':False}
    x.save('audit.json',report);x.b.save_json(x.ROOT/'data/sample/petehub_pitcher_decision_exploratory_audit_v1.json',report);print(report,flush=True)


if __name__=='__main__':
    with x.threadpool_limits(limits=2):main()
