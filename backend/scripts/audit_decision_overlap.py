"""Slice15 source/data/clock/accounting checks, never model or visual acceptance."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_overlap as q
from scripts import build_decision_overlap_pool as pool


def hashes(folder,name='manifest.json'):
    data=q.read(folder/name)
    for item in data['files']:
        p=folder/item['path'];assert p.stat().st_size==item['bytes'] and q.b.digest(p)==item['sha256'],p
    for rel,sha in data.get('source_sha256',{}).items():assert q.b.digest(q.ROOT/rel)==sha,rel
    print(f'{folder.name}/{name}: {len(data["files"])} retained hashes checked',flush=True)
    return len(data['files'])


def main():
    n=q.n;old=n.old;b=q.b
    folders=[b.PREP,b.OUT,b.ROOT/'data/research/decision_ablation_v1',old.a.a.OUT,n.r.OUT,n.u.h.OUT,n.u.OUT,old.a.OUT,n.p.OUT,old.prior.OUT,old.OUT,n.OUT]
    previous=sum(hashes(p) for p in folders);assert previous==1081
    assert q.read(q.OUT/'protocol.json')==q.protocol()
    assert q.read(pool.OUT/'protocol.json')==pool.protocol()
    core=hashes(q.OUT,'core_manifest.json');assert core==96
    latest=hashes(q.OUT)+hashes(pool.OUT)
    assert q.read(q.OUT/'protocol.json')['protocol_revision']==2
    attempt=q.read(q.OUT/'attempt0_nullable_dtype/failure.json');assert attempt['fits_completed']==0 and not attempt['outcome_results_examined']
    rows=0;changes=0;restored=0
    for year in range(2021,2025):
        f=pd.read_parquet(q.OUT/f'boundaries_{year}.parquet');risk=pd.read_parquet(q.OUT/f'monitoring_{year}.parquet')
        assert f.decision_id.is_unique and f.role.isin(['SP','RP']).all()
        assert f.cohort_reason.isin(['included','observed_replacement_outside_nominal_set']).all()
        restored+=int(f.cohort_reason.ne('included').sum());rows+=len(f);changes+=int(f.changed.sum())
        assert f.game_closed_at.gt(f.decision_at).all()
        for clock,anchor in [('available_at','decision_at'),('personal_reference_at','reference_clock'),('D_reference_at','reference_clock'),
                ('pitcher_history_available_at','decision_at'),('batter_history_available_at','decision_at')]:
            valid=f[clock].notna();assert f.loc[valid,clock].lt(f.loc[valid,anchor]).all(),(year,clock)
        assert risk.block_id.is_unique and risk.decision_id.is_unique
        assert risk.loc[risk.future_observed.eq(0),'future_bad'].isna().all()
        valid=risk.future_observed.eq(1)
        assert risk.loc[valid,'target_anchor'].ge(risk.loc[valid,'decision_at']).all()
        assert risk.loc[valid,'target_block'].between(risk.loc[valid,'block_number']+1,risk.loc[valid,'block_number']+2).all()
        assert risk.loc[valid,'target_at'].le(risk.loc[valid,'game_closed_at']).all()
        print(f'{year}: denominator, actor/source clocks and censoring checked',flush=True)
        if year==2021:continue
        for role in ['SP','RP']:
            fit=q.read(q.OUT/f'fit_{year}_{role}.json')
            for kind,part in fit['parts'].items():
                assert part['fit_last_label']<part['cal_first_decision']<=part['cal_last_label']<part['validation_first_decision']
                split=pd.read_parquet(q.OUT/f'split_{year}_{role}_{kind}.parquet')
                tf=split[split.partition.eq('fit')];cal=split[split.partition.eq('calibration')]
                assert set(tf.game_pk).isdisjoint(cal.game_pk) and tf.game_closed_at.max()<cal.decision_at.min()
            action=pd.read_parquet(q.OUT/f'scored_{year}_{role}_boundaries.parquet')
            obs=pd.read_parquet(q.OUT/f'scored_{year}_{role}_monitoring.parquet')
            assert action.propensity.between(0,1,inclusive='neither').all() and obs.propensity.between(0,1,inclusive='neither').all()
            assert set(action.decision_id)==set(f.loc[f.role.eq(role),'decision_id'])
            assert set(obs.decision_id)==set(risk.loc[risk.role.eq(role),'decision_id'])
            memberships=pd.read_parquet(pool.OUT/f'probabilities_{year}_{role}.parquet')
            assert set(memberships.decision_id)==set(action.decision_id)
            candidates=pd.read_parquet(pool.OUT/f'candidate_support_{year}_{role}.parquet')
            assert not candidates.duplicated(['decision_id','pitcher_id']).any()
            assert candidates.nominal_eligible.all() and candidates.previous_role.eq('RP').all()
            conditional=candidates.groupby('decision_id').choice_probability.sum()
            assert np.allclose(conditional,1)
            assigned=candidates.groupby('decision_id').joint_probability.sum().reindex(memberships.decision_id).fillna(0).to_numpy()
            assert np.allclose(assigned,memberships.propensity*memberships.pool_membership_probability)
            assert np.allclose(assigned+memberships.outside_pool_probability+1-memberships.propensity,1)
            assert np.allclose(candidates.joint_probability,pool.actor_mass(candidates.propensity,candidates.pool_membership_probability,candidates.choice_probability))
            assert candidates.joint_probability.le(candidates.core_conditional_score+1e-12).all()
            supported=candidates[candidates.statistical_support]
            assert supported.joint_probability.ge(.005).all() and supported.choice_probability.ge(.02).all()
            assert supported.prior_selected.ge(20).all() and supported.prior_observed_relief.ge(5).all()
            assert supported.past_cell_support.all()
            split=pd.read_parquet(pool.OUT/f'split_{year}_{role}.parquet')
            tf=split[split.partition.eq('fit')];cal=split[split.partition.eq('calibration')]
            assert set(tf.game_pk).isdisjoint(cal.game_pk) and tf.game_closed_at.max()<cal.decision_at.min()
            assert cal.game_closed_at.max()<action.decision_at.min()
            # Own support is learned before this validation year, never full-year hindsight.
            past=pd.concat([pd.read_parquet(q.OUT/f'candidates_{y}.parquet',columns=['role','pitcher_id','chosen','game_closed_at']) for y in range(2021,year)])
            cut=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp();past=past[past.role.eq(role)&past.game_closed_at.lt(cut)&past.chosen.eq(1)]
            counts=past.groupby('pitcher_id').size();expected=candidates.pitcher_id.map(counts).fillna(0).astype(int)
            assert np.array_equal(expected.to_numpy(),candidates.prior_selected.to_numpy())
            print(f'{year}/{role}: forward splits, actor probability simplex, candidate own historical support checked',flush=True)
    assert rows==546930 and changes==54669 and restored==38
    evidence=q.read(q.ROOT/'data/sample/petehub_pitcher_decision_overlap_v1.json')
    assert evidence==q.read(q.OUT/'evidence.json')
    assert len(list(q.OUT.glob('model_*.joblib')))+len(list(pool.OUT.glob('membership_*.joblib')))==24
    assert all(not x['primary']['diagnostic_gate'] for x in evidence['roles'] if x['year']==2024)
    assert all(x['operationally_available']==0 for x in evidence['candidate_support'])
    assert not evidence['recommendation_allowed'] and not evidence['test2025_outcomes_examined']
    main=pd.read_parquet(q.OUT/'fixed32_overlap.parquet');original=pd.read_parquet(n.OUT/'signal_point_ledger.parquet').set_index('decision_id').loc[main.decision_id]
    assert len(main)==2376 and main.primary_overlap.sum()==633
    assert (main.primary_overlap&main.wpa_delta.notna()).sum()==604
    assert not main.nominal_research_alert.any()
    assert np.allclose(main.wpa_delta,original.wpa_delta,equal_nan=True)
    tracker=q.read(q.ROOT/'docs/PROJECT_TRACKER.json');project=next(x for x in tracker['projects'] if x['id']=='pitcher-decision-support')
    assert len(project['slices'])==47 and sum(x['status']=='done' for x in project['slices'])==40
    statuses={x['id']:x['status'] for x in project['slices']}
    assert statuses['15']=='done' and all(statuses[x]=='planned' for x in ['16','17','18','19','20','21'])
    front=q.read(q.ROOT/'frontend/data/pitcherDecisionPlan.json')
    assert front['project']==project and front['overlapResearch']==evidence
    assert front['signalLights']==q.read(q.ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v2.json')
    report={'version':'decision_overlap_source_audit_v1','previous_hashes':previous,'retained_core_hashes':core,'new_final_hashes':latest,
        'boundaries':rows,'changes':changes,'restored_out_of_nominal':restored,'models':24,'progress':'40/47','stop':'15',
        'primary_balance_passed2024':{'SP':False,'RP':False},'operational_recommendations':0,'test2025_outcomes_examined':False,
        'visual_acceptance':'pending user','checks':'source/data/clock/assignment-mass/accounting; no efficacy, exchangeability or visual acceptance claim'}
    q.save('audit.json',report);q.b.save_json(q.ROOT/'data/sample/petehub_pitcher_decision_overlap_audit_v1.json',report)
    print('Slice15 source/clock/assignment/accounting checks passed; balance and policy efficacy remain unestablished; visual acceptance pending user',flush=True)


if __name__=='__main__':main()
