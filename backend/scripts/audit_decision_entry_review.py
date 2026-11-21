"""15.4 frozen-input/forward-gate/uncertainty/ledger accounting, source only."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_entry_review as e
from scripts.audit_decision_overlap_revision import hashes


def main():
    q=e.q;previous=sum(hashes(folder) for folder in e.input_folders());assert previous==1546
    new=hashes(e.OUT);assert e.read(e.OUT/'protocol.json')==e.protocol()
    assert e.read(e.OUT/'input_audit.json')['previous_artifacts']==previous
    assert not list(e.OUT.glob('*.joblib')) and not any('2025' in p.name for p in e.OUT.iterdir())
    assert (e.OUT/'protocol.json').stat().st_mtime_ns<min((e.OUT/f'review_{y}.json').stat().st_mtime_ns for y in e.YEARS)
    summary=e.read(e.OUT/'summary.json');full=[];targets=[];flows=[];total=0
    for year in e.YEARS:
        study=e.read(e.OUT/f'review_{year}.json');ledger=pd.read_parquet(e.OUT/f'review_ledger_{year}.parquet')
        features=q.base.features(year)
        assert ledger.decision_id.is_unique and set(ledger.decision_id)==set(features.decision_id)
        assert not {'changed','future_ten_y','next_pa_y','future_ten_observed','next_pa_observed'}&set(ledger.columns)
        assert not ledger.review_eligible.any()
        for role in ['SP','RP']:
            for phase in q.base.PHASES:
                if role=='SP':
                    score=pd.read_parquet(q.base.OUT/f'scored_{year}_SP_{phase}_hgb_full.parquet')
                    f=features.set_index('decision_id').loc[score.decision_id].reset_index()
                    f['past_cell_support']=score.past_cell_support.to_numpy();f['propensity']=score.propensity.to_numpy()
                    probability=f.propensity.to_numpy();population=np.ones(len(f),bool)
                    dev=[r for r in e.read(q.base.OUT/'summary.json')['all_results'] if r['role']=='SP' and r['phase']==phase and r['year'] in [2022,2023] and r['variant']=='hgb_full' and r['scheme']=='overlap']
                else:
                    f=pd.read_parquet(q.OUT/f'scored_{year}_{phase}.parquet');probability=f.action_probability.to_numpy()
                    population=q.subset_mask(f,'short_profile').to_numpy(bool)&(phase=='within_inning')
                    dev=[r for r in e.read(q.OUT/'summary.json')['balance'] if r['phase']==phase and r['year'] in [2022,2023] and r['subset']=='short_profile' and r['model']=='history_enriched' and r['scheme']=='overlap']
                e.verify_probabilities(year,role,phase,f)
                rows=[r for r in study['balance'] if r['role']==role and r['phase']==phase]
                for row in rows:
                    mask=np.ones(len(f),bool) if role=='SP' else q.subset_mask(f,row['subset']).to_numpy(bool)
                    part=f[mask];prob=probability[mask]
                    checked=q.base.diagnostics(part,prob,row['scheme']) if role=='SP' else q.diagnostics(part,prob,row['scheme'])
                    # ECE is independent of the arbitrary constant passed here.
                    metrics=q.old.binary_metrics(part.changed.to_numpy(int),prob,.5)
                    assert np.isclose(checked['max_abs_smd_after'],row['max_abs_smd_after'])
                    assert checked['retained']==row['retained'] and np.isclose(checked['change']['ess'],row['change']['ess'])
                    assert np.isclose(metrics['ece'],row['ece'])
                    assert e.gate_failures(checked,metrics,row['warning'])==row['failures']
                    assert row['full_gate']==(not row['failures'])
                primary=next(r for r in rows if r['scheme']=='overlap' and r['subset']==('all' if role=='SP' else 'short_profile'))
                expected=e.review_ledger(f,population,probability,primary['full_gate'],all(r['full_gate'] for r in dev))
                actual=ledger[ledger.role.eq(role)&ledger.phase.eq(phase)].set_index('decision_id').loc[expected.decision_id].reset_index()
                pd.testing.assert_frame_equal(actual[expected.columns],expected.reset_index(drop=True))
                flow=next(r for r in study['flows'] if r['role']==role and r['phase']==phase)
                assert len(actual)==flow['boundaries'] and int(actual.initial_support.sum())==flow['initial_support']
                assert actual.review_rejection.value_counts().to_dict()==flow['rejections']
                assert sum(flow['rejections'].values())==len(actual)
                if role=='RP' and phase=='within_inning':
                    monitor=f[f.monitor_unit&q.subset_mask(f,'short_profile')]
                    for target in q.TARGETS:
                        row=next(r for r in study['targets'] if r['target']==target)
                        assert row['observation']==q.scenario_summary(monitor,target)
                        assert row['observed']==int(monitor[target+'_observed'].sum()) and row['n']==len(monitor)
                        assert row['missing_reasons']==monitor[target+'_reason'].value_counts().to_dict()
                        observed=monitor[monitor[target+'_observed'].eq(1)]
                        import joblib
                        bundle=joblib.load(q.OUT/f'model_{year}_{phase}_{target}_outcome.joblib')
                        checked=e.clustered_brier(observed,observed[target+'_y'].to_numpy(),observed[target+'_outcome_probability'].to_numpy(),bundle['prior'],seed=e.SEED+year+q.TARGETS.index(target))
                        assert checked==row['cluster_brier']
                        assert np.isclose(checked['delta'],row['metrics']['brier']-row['metrics']['constant_brier'])
                print(f'{year}/{role}/{phase}: fixed weights, gates, paired-model checks and non-outcome eligibility accounted',flush=True)
        total+=len(ledger);full+=study['balance'];targets+=study['targets'];flows+=study['flows']
    assert full==summary['balance'] and targets==summary['targets'] and flows==summary['flows']
    assert len(full)==72 and len(targets)==6 and len(summary['primary_folds'])==9
    assert summary['strategy_contract']==e.strategy_contract() and not summary['strategy_contract']['implementation_ready']
    for qualification in summary['qualifications']:
        rows=[r for r in summary['primary_folds'] if r['role']==qualification['role'] and r['phase']==qualification['phase']]
        assert qualification['comparison_qualified']==all(r['full_gate'] for r in rows)
        assert qualification['passed_folds']==sum(r['full_gate'] for r in rows)
    assert not summary['slice16_entry_allowed'] and not any(r['passed'] for r in summary['barriers'])
    assert not summary['strategy_value_estimated'] and not summary['recommendation_allowed'] and not summary['test2025_outcomes_examined']
    evidence=e.read(e.ROOT/'data/sample/petehub_pitcher_decision_entry_review_v1.json')
    assert evidence==e.read(e.OUT/'evidence.json')
    assert evidence['flow']=={'progress':'44/51','new_models':0,'reviewed_rows':total,'initial_support':sum(r['initial_support'] for r in flows),'qualified_rows':0,'primary_folds':9,'primary_passed':sum(r['full_gate'] for r in summary['primary_folds'])}
    project=next(p for p in e.read(e.ROOT/'docs/PROJECT_TRACKER.json')['projects'] if p['id']=='pitcher-decision-support')
    assert len(project['slices'])==51 and sum(s['status']=='done' for s in project['slices'])==44
    items={s['id']:s for s in project['slices']};assert items['15.4']['status']=='done'
    assert all(items[s]['status']=='planned' for s in ['16','17','18','19','20','21'])
    front=e.read(e.ROOT/'frontend/data/pitcherDecisionPlan.json');assert front['project']==project and front['entryReview']==evidence
    for name,file in [('rpTargetResearch','rp_targets_v1'),('overlapRevision','overlap_revision_v1'),('signalLights','signal_lights_v2')]:
        assert front[name]==e.read(e.ROOT/f'data/sample/petehub_pitcher_decision_{file}.json')
    report={'version':'decision_entry_review_source_audit_v1','previous_artifacts':previous,'new_artifacts':new,'reviewed_rows':total,'primary_folds':9,
        'primary_passed':evidence['flow']['primary_passed'],'new_models':0,'progress':'44/51','stop':'15.4','slice16_entry_allowed':False,
        'recommendation_allowed':False,'test2025_outcomes_examined':False,'visual_acceptance':'pending user',
        'checks':'source/clock/probability/gates/paired uncertainty/denominators only; retrospective qualification is not live eligibility or strategy efficacy'}
    e.save('audit.json',report);q.b.save_json(e.ROOT/'data/sample/petehub_pitcher_decision_entry_review_audit_v1.json',report)
    print('15.4 source and accounting checks passed;16 not entered; no policy/visual acceptance',flush=True)


if __name__=='__main__':main()
