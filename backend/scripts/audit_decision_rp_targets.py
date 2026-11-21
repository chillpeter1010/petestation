"""15.3 source, clock, target and accounting audit; no visual/policy acceptance."""
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_rp_targets as q
from scripts.audit_decision_overlap_revision import hashes


def main():
    c,n,b,old=q.c,q.n,q.b,q.old
    folders=[b.PREP,b.OUT,q.ROOT/'data/research/decision_ablation_v1',n.old.a.a.OUT,n.r.OUT,n.u.h.OUT,n.u.OUT,n.old.a.OUT,n.p.OUT,n.old.prior.OUT,n.old.OUT,n.OUT,
        old.OUT,q.ROOT/'data/research/decision_overlap_pool_revision_v2',c.OUT,q.base.OUT]
    previous=sum(hashes(folder) for folder in folders);assert previous==1365
    new=hashes(q.OUT);assert q.read(q.OUT/'protocol.json')==q.protocol()
    guard=q.read(q.OUT/'confirmation_guard.json');assert not guard['2024_outputs_present_before_confirmation']
    for name,sha in guard['input_sha256'].items():assert b.digest(q.OUT/name)==sha
    assert (q.OUT/'confirmation_guard.json').stat().st_mtime_ns<min(p.stat().st_mtime_ns for p in q.OUT.glob('model_2024_*.joblib'))
    archive=q.OUT/'attempt0_label_mapping'
    assert q.read(archive/'protocol.json')['version']=='decision_rp_targets_v1'
    assert len(list(archive.glob('model_*.joblib')))==30
    assert b.digest(archive/'build_decision_rp_targets.py')==q.read(archive/'protocol.json')['input_sha256']['backend/scripts/build_decision_rp_targets.py']
    history=pd.read_parquet(n.r.OUT/'appearance_history.parquet')
    history=history[history.role.eq('RP')&history.available_at.notna()&history.bad_timing.eq(0)&history.bf.gt(0)&history.actual_pitches.gt(0)]
    histories={pid:g.sort_values(['available_at','appearance_id']) for pid,g in history.groupby('pitcher_id')}
    frames={};total=0;monitors=0
    for year in range(2021,2025):
        f=pd.read_parquet(q.OUT/f'features_{year}.parquet');frames[year]=q.enrich_design(f)
        expected=q.base.features(year);expected=expected[expected.role.eq('RP')]
        assert f.decision_id.is_unique and set(f.decision_id)==set(expected.decision_id)
        assert f.role.eq('RP').all() and f.anchor_at.lt(f.old_decision_at).all()
        assert np.array_equal(q.monitoring_mask(f),f.monitor_unit)
        known=f.usage_reference_at.notna();assert f.loc[known,'usage_reference_at'].lt(f.loc[known,'entry_at']).all()
        assert np.array_equal(q.usage_profile(f.prior_rp_n.fillna(0),f.prior_rp_median_bf,f.prior_rp_median_pitches),f.usage_profile)
        for row in f[known].drop_duplicates('appearance_id').sample(n=min(64,f[known].appearance_id.nunique()),random_state=15).itertuples():
            past=histories[row.outgoing_pitcher_id];past=past[past.available_at.lt(row.entry_at)].tail(10)
            assert len(past)==row.prior_rp_n and past.available_at.max()==row.usage_reference_at
            assert past.bf.median()==row.prior_rp_median_bf and past.actual_pitches.median()==row.prior_rp_median_pitches
        labels=pd.read_parquet(b.PREP/f'clean_labels_{year}.parquet').set_index('decision_id').reindex(f.decision_id)
        # Independently reconstruct the established preparation group semantics.
        raw=labels.observed_pa_result
        nonout=raw.isin(['walk','hit_by_pitch','home_run','single','double','triple'])|(~raw.isin(['strikeout','strikeout_double_play'])&labels.outs_after.le(labels.outs))
        mask=f.next_pa_observed.eq(1)
        assert np.array_equal(f.loc[mask,'next_pa_y'],nonout.to_numpy()[mask])
        assert set(f.loc[mask,'next_pa_y'])=={0.,1.}
        assert f.loc[mask,'actor_pitcher_id'].eq(f.loc[mask,'outgoing_pitcher_id']).all()
        assert f.loc[mask,'final_pitcher_id'].eq(f.loc[mask,'outgoing_pitcher_id']).all()
        assert f.loc[mask,'physical_actors'].eq(1).all() and f.loc[mask,'bad_timing'].eq(0).all()
        assert f.loc[mask,'pa_start'].ge(f.loc[mask,'anchor_at']).all()
        assert f.loc[mask,'pa_available_at'].gt(f.loc[mask,'pa_start']).all()
        ten=f.future_ten_observed.eq(1);own=f.physical_appearance.eq(f.appearance_id).fillna(False)
        position=f.physical_position.where(own,0).fillna(0)
        assert f.loc[ten,'ten_block'].eq(np.ceil(position[ten]/10)).all()
        assert ((~own)|f.ten_session.eq(f.physical_session))[ten].all()
        assert f.loc[ten,'ten_start'].ge(f.loc[ten,'anchor_at']).all()
        assert f.loc[ten,'ten_available_at'].le(f.loc[ten,'game_closed_at']).all()
        assert f.loc[ten,['residual_stuff','residual_velocity','residual_location']].notna().all().all()
        assert np.array_equal(f.loc[ten,'future_ten_y'],(f.residual_stuff.le(-5)|f.residual_velocity.le(-.5)|f.residual_location.le(-5))[ten])
        for target in q.TARGETS:
            assert f.loc[f[target+'_observed'].eq(0),target+'_y'].isna().all()
            assert f.loc[f.changed.eq(1),target+'_observed'].eq(0).all()
        assert f.loc[mask,'changed'].eq(0).all() and f.loc[ten,'changed'].eq(0).all()
        prep=q.read(q.OUT/f'preparation_{year}.json')
        for record in prep['coverage']:
            part=f[f.phase.eq(record['phase'])];part=part[q.subset_mask(part,record['subset'])]
            if record['scope']=='paired_monitoring':part=part[part.monitor_unit]
            assert len(part)==record['n'] and int(part[record['target']+'_observed'].sum())==record['observed']
        total+=len(f);monitors+=int(f.monitor_unit.sum())
        print(f'{year}: RP denominator, sampled entry histories, independent raw PA mapping, future clocks and censoring checked',flush=True)
    denied={'changed','next_pa_y','future_ten_y','next_pa_observed','future_ten_observed','actual_pitches','incoming_pitcher_id','ten_block','observed_pa_result'}
    assert not denied&set(q.NUM+q.CAT)
    task_count=0;constants=0
    with threadpool_limits(limits=2):
        for year in [2022,2023,2024]:
            past=pd.concat([frames[y] for y in range(2021,year)],ignore_index=True)
            for phase in q.base.PHASES:
                cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp()
                source=past[past.phase.eq(phase)&past.game_closed_at.lt(cutoff)]
                f=pd.read_parquet(q.OUT/f'scored_{year}_{phase}.parquet')
                fitinfo=q.read(q.OUT/f'fit_{year}_{phase}.json')
                assert len(f)==int(frames[year].phase.eq(phase).sum()) and f.decision_id.is_unique
                support=source.groupby('cell').changed.agg(['sum','count']);support=support['sum'].ge(10)&(support['count']-support['sum']).ge(10)
                assert np.array_equal(f.past_cell_support,f.cell.map(support).fillna(False))
                for task in fitinfo['tasks']:
                    name=task['task'].replace(':','_');bundle=joblib.load(q.OUT/f'model_{year}_{phase}_{name}.joblib')
                    s=source if name=='action' else source[source.monitor_unit]
                    if task['task'].endswith(':outcome'):s=s[s[bundle['label']].notna()]
                    fit,cal,flow=q.temporal_partition(s)
                    split=pd.read_parquet(q.OUT/f'split_{year}_{phase}_{name}.parquet')
                    assert set(split.loc[split.partition.eq('fit'),'decision_id'])==set(fit.decision_id)
                    assert set(split.loc[split.partition.eq('calibration'),'decision_id'])==set(cal.decision_id)
                    assert set(fit.game_pk).isdisjoint(cal.game_pk)
                    assert flow==task['flow'] and task['fit_last_label']<task['cal_first_anchor']<=task['cal_last_label']<task['validation_first_anchor']
                    assert np.allclose(q.predict(bundle,f.iloc[:64]),f[name+'_probability'].iloc[:64],atol=1e-12)
                    if bundle['kind']=='constant':
                        assert np.isclose(bundle['prior'],(fit[bundle['label']].sum()+1)/(len(fit)+2));constants+=1
                    else:
                        model=bundle['model'];assert model.steps[-1][1].get_params()['max_iter']==60
                        transform=model.steps[0][1]
                        assert set(transform.transformers_[0][2]+transform.transformers_[1][2])==set(q.NUM+q.CAT)
                    task_count+=1
                print(f'{year}/{phase}: five strict past-only task splits and direct probabilities checked',flush=True)
    summary=q.read(q.OUT/'summary.json');assert task_count==30==len(list(q.OUT.glob('model_*.joblib')))
    assert len(summary['balance'])==120 and len(summary['task_results'])==60 and len(summary['sensitivity2024'])==20
    for row in summary['primary2024']:
        f=pd.read_parquet(q.OUT/'scored_2024_within_inning.parquet');f=f[q.subset_mask(f,'short_profile')]
        if row['model']=='history_enriched':prob=f.action_probability.to_numpy()
        else:prob=pd.read_parquet(q.base.OUT/'scored_2024_RP_within_inning_hgb_full.parquet').set_index('decision_id').loc[f.decision_id,'propensity'].to_numpy()
        checked=q.diagnostics(f,prob,'overlap')
        assert np.isclose(checked['max_abs_smd_after'],row['max_abs_smd_after']) and checked['retained']==row['retained']
        assert np.isclose(checked['change']['ess'],row['change']['ess'])
    for row in summary['sensitivity2024']:
        f=pd.read_parquet(q.OUT/f"scored_2024_{row['phase']}.parquet");f=f[f.monitor_unit&q.subset_mask(f,row['subset'])]
        before=f[row['target']+'_y'].copy();checked=q.scenario_summary(f,row['target'])
        assert checked=={k:v for k,v in row.items() if k not in ['phase','subset','target']}
        pd.testing.assert_series_equal(before,f[row['target']+'_y'])
        rates=[x['scenario_rate'] for x in checked['missing_scenarios']]
        assert rates==sorted(rates) and all(checked['worst_case_bounds'][0]<=r<=checked['worst_case_bounds'][1] for r in rates)
    evidence=q.read(q.ROOT/'data/sample/petehub_pitcher_decision_rp_targets_v1.json')
    assert evidence==q.read(q.OUT/'evidence.json') and evidence['flow']=={'progress':'43/51','task_artifacts':30,'hgb':30-constants,'constant':constants,'boundaries':total,'monitor_units':monitors}
    assert not evidence['recommendation_allowed'] and not evidence['test2025_outcomes_examined']
    project=next(x for x in q.read(q.ROOT/'docs/PROJECT_TRACKER.json')['projects'] if x['id']=='pitcher-decision-support')
    assert len(project['slices'])==51 and sum(x['status']=='done' for x in project['slices'])==43
    items={x['id']:x for x in project['slices']};assert items['15.3']['status']=='done'
    assert all(items[x]['status']=='planned' for x in ['15.4','16','17','18','19','20','21'])
    front=q.read(q.ROOT/'frontend/data/pitcherDecisionPlan.json');assert front['project']==project and front['rpTargetResearch']==evidence
    assert front['overlapRevision']==q.read(q.ROOT/'data/sample/petehub_pitcher_decision_overlap_revision_v1.json')
    assert front['signalLights']==q.read(q.ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v2.json')
    report={'version':'decision_rp_targets_source_audit_v1','previous_hashes':previous,'new_artifact_hashes':new,'boundaries':total,'monitor_units':monitors,
        'task_artifacts':30,'hgb':30-constants,'constant':constants,'progress':'43/51','stop':'15.3',
        'primary_diagnostic_gate':next(x['full_gate'] for x in summary['primary2024'] if x['model']=='history_enriched'),
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'visual_acceptance':'pending user',
        'checks':'source/data/target/clock/model/accounting only; 2024 diagnostic after disclosed label correction, not causal or visual acceptance'}
    q.save('audit.json',report);b.save_json(q.ROOT/'data/sample/petehub_pitcher_decision_rp_targets_audit_v1.json',report)
    print('15.3 source/clock/target/model/accounting checks passed; stop15.3',flush=True)


if __name__=='__main__':main()
