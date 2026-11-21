"""15.1/15.2 source/data/model-clock accounting; no visual/causal acceptance."""
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_common_clock as c
from scripts import build_decision_balance_revision as q


def hashes(folder):
    manifest=c.read(folder/'manifest.json')
    for entry in manifest['files']:
        path=folder/entry['path'];assert path.stat().st_size==entry['bytes'] and c.b.digest(path)==entry['sha256'],path
    for key in ['source_sha256','sources']:
        for path,sha in manifest.get(key,{}).items():assert c.b.digest(c.ROOT/path)==sha,path
    print(f'{folder.name}: {len(manifest["files"])} frozen artifact hashes checked',flush=True)
    return len(manifest['files'])


def main():
    n,b,old=c.n,c.b,c.old
    folders=[b.PREP,b.OUT,c.ROOT/'data/research/decision_ablation_v1',n.old.a.a.OUT,n.r.OUT,n.u.h.OUT,n.u.OUT,n.old.a.OUT,n.p.OUT,n.old.prior.OUT,n.old.OUT,n.OUT,
        old.OUT,c.ROOT/'data/research/decision_overlap_pool_revision_v2']
    previous=sum(hashes(folder) for folder in folders);assert previous==1205
    assert c.read(c.OUT/'protocol.json')==c.protocol()
    assert c.read(q.OUT/'protocol.json')==q.protocol()
    new=hashes(c.OUT)+hashes(q.OUT)
    guard=c.read(q.OUT/'confirmation_guard.json');assert not guard['2024_outputs_present_before_confirmation']
    assert c.b.digest(q.OUT/'selection.json')==guard['selection_sha256']
    for key,sha in guard['inner_results'].items():assert c.b.digest(q.OUT/f'results_{key}.json')==sha
    assert (q.OUT/'confirmation_guard.json').stat().st_mtime_ns<min(p.stat().st_mtime_ns for p in q.OUT.glob('model_2024_*.joblib'))
    original=0;included=0;excluded=0
    for year in range(2021,2025):
        audit=pd.read_parquet(c.OUT/f'anchor_audit_{year}.parquet');f=q.features(year)
        original+=len(audit);included+=len(f);excluded+=int(audit.anchor_reason.ne('included').sum())
        assert audit.decision_id.is_unique and f.decision_id.is_unique
        assert set(audit.decision_id)==set(pd.read_parquet(old.OUT/f'boundaries_{year}.parquet',columns=['decision_id']).decision_id)
        assert set(f.decision_id)==set(audit.loc[audit.anchor_reason.eq('included'),'decision_id'])
        assert f.anchor_at.lt(f.old_decision_at).all() and f.entry_at.lt(f.anchor_at).all()
        for field,clock in [('pitch_available_at','anchor_at'),('ability_available_at','anchor_at'),('available_at','anchor_at'),
                ('snapshot_at','anchor_at'),('personal_reference_at','entry_at'),('load_reference_at','entry_at'),('entry_last_pitch_at','entry_at')]:
            known=f[field].notna();assert f.loc[known,field].lt(f.loc[known,clock]).all(),(year,field)
        assert f.loc[f.snapshot_id.notna(),'snapshot_id'].ne(f.loc[f.snapshot_id.notna(),'decision_id']).all()
        assert f.outs.isin(['0','1','2']).all() and f.base_state.isin([str(x) for x in range(8)]).all()
        assert f.current_pitches.dropna().ge(0).all() and f.current_bf.ge(0).all()
        for key in ['prior_games_pitches_3d','prior_games_pitches_5d']:assert f[key].dropna().ge(0).all()
        scores=pd.read_parquet(n.OUT/f'block_scores_{year}.parquet');scores=scores[scores.alpha.eq(n.ALPHA)]
        actors=f[f.block_id.notna()].merge(scores[['block_id','pitcher_id','appearance_id','available_at']],on='block_id',how='left',validate='many_to_one',suffixes=('','_source'))
        assert actors.pitcher_id.eq(actors.outgoing_pitcher_id).all() and actors.appearance_id.eq(actors.appearance_id_source).all()
        assert actors.available_at.eq(actors.available_at_source).all()
        missing=pd.read_parquet(c.OUT/f'missing_audit_{year}.parquet');old_monitor=pd.read_parquet(old.OUT/f'monitoring_{year}.parquet').set_index('decision_id').loc[missing.decision_id]
        assert missing.decision_id.is_unique and len(missing)==len(old_monitor)
        assert np.allclose(missing.future_bad,old_monitor.future_bad,equal_nan=True)
        assert missing.loc[missing.future_observed.eq(0),'future_bad'].isna().all()
        assert missing.missing_reason.eq('observed').equals(missing.future_observed.eq(1))
        print(f'{year}: common-anchor eligibility, reobserved actor clocks and unchanged censored targets checked',flush=True)
        if year==2021:continue
        for role in ['SP','RP']:
            result=c.read(q.OUT/f'results_{year}_{role}.json');assert len(result['rows'])==16
            development=pd.concat([q.features(y) for y in range(2021,year)],ignore_index=True)
            cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp()
            development=development[development.role.eq(role)&development.game_closed_at.lt(cutoff)]
            counts=development.groupby('cell').changed.agg(['sum','count'])
            supported=counts['sum'].ge(10)&(counts['count']-counts['sum']).ge(10)
            for phase in q.PHASES:
                split=pd.read_parquet(q.OUT/f'split_{year}_{role}_{phase}.parquet');fit=split[split.partition.eq('fit')];cal=split[split.partition.eq('calibration')]
                assert set(fit.game_pk).isdisjoint(cal.game_pk) and fit.game_closed_at.max()<cal.anchor_at.min()
                assert cal.game_closed_at.max()<f.loc[f.role.eq(role)&f.phase.eq(phase),'anchor_at'].min()
                for variant in q.VARIANTS:
                    scored=pd.read_parquet(q.OUT/f'scored_{year}_{role}_{phase}_{variant}.parquet')
                    assert scored.decision_id.is_unique and scored.propensity.between(0,1,inclusive='neither').all()
                    expected=f[f.role.eq(role)&f.phase.eq(phase)].set_index('decision_id').loc[scored.decision_id].reset_index()
                    assert expected.changed.eq(scored.changed).all()
                    assert np.array_equal(scored.past_cell_support,expected.cell.map(supported).fillna(False).to_numpy())
                    bundle=joblib.load(q.OUT/f'model_{year}_{role}_{phase}_{variant}.joblib')
                    assert np.allclose(q.predict(bundle,expected.iloc[:64]),scored.propensity.iloc[:64],atol=1e-12)
                    rows=[x for x in result['rows'] if x['phase']==phase and x['variant']==variant]
                    assert len(rows)==2 and all(x['warning']==bundle['warning'] for x in rows)
                    for row in rows:
                        assert row['fit_last_label']<row['cal_first_anchor']<=row['cal_last_label']<row['validation_first_anchor']
                    if year==2024 and variant==c.read(q.OUT/'selection.json')['winners'][role]['variant']:
                        expected['past_cell_support']=scored.past_cell_support.to_numpy()
                        for scheme in q.SCHEMES:
                            checked=q.diagnostics(expected,scored.propensity.to_numpy(),scheme)
                            row=next(x for x in rows if x['scheme']==scheme)
                            assert np.isclose(checked['max_abs_smd_after'],row['max_abs_smd_after'])
                            assert np.isclose(checked['change']['ess'],row['change']['ess']) and checked['retained']==row['retained']
            print(f'{year}/{role}: paired variants, strict training, probabilities and frozen balance definitions checked',flush=True)
    assert original==546930 and included==546880 and excluded==50
    selection=c.read(q.OUT/'selection.json')
    for role in ['SP','RP']:
        assert selection['winners'][role]=={'variant':'hgb_full','training_all_gates_passed':False}
        rows=[]
        for variant in q.VARIANTS:
            data=[x for year in [2022,2023] for x in c.read(q.OUT/f'results_{year}_{role}.json')['rows'] if x['variant']==variant and x['scheme']=='overlap']
            rows.append({'role':role,'variant':variant,'failing_phase_years':sum(not x['full_gate'] for x in data),
                'mean_max_smd':float(np.mean([x['max_abs_smd_after'] for x in data])),'mean_LL':float(np.mean([x['metrics']['log_loss'] for x in data]))})
        ordered=sorted(rows,key=lambda x:(x['failing_phase_years'],x['mean_max_smd'],x['mean_LL'],q.VARIANTS.index(x['variant'])))
        assert selection['ranking'][role]==ordered
    evidence=c.read(c.ROOT/'data/sample/petehub_pitcher_decision_overlap_revision_v1.json')
    assert evidence==c.read(q.OUT/'evidence.json') and not evidence['recommendation_allowed'] and not evidence['test2025_outcomes_examined']
    assert evidence['flow']=={'original':546930,'included':546880,'excluded':50,'models':48,'progress':'42/51'}
    assert len(list(q.OUT.glob('model_*.joblib')))==48
    assert len(evidence['primary2024'])==4 and all(not x['full_gate'] for x in evidence['primary2024'])
    assert all(not x['promoted'] for x in evidence['selected'])
    project=next(x for x in c.read(c.ROOT/'docs/PROJECT_TRACKER.json')['projects'] if x['id']=='pitcher-decision-support')
    assert len(project['slices'])==51 and sum(x['status']=='done' for x in project['slices'])==42
    items={x['id']:x for x in project['slices']}
    assert items['15.1']['status']==items['15.2']['status']=='done'
    assert all(items[x]['status']=='planned' for x in ['15.3','15.4','16','17','18','19','20','21'])
    assert '15.4' in items['16']['depends_on']
    front=c.read(c.ROOT/'frontend/data/pitcherDecisionPlan.json');assert front['project']==project and front['overlapRevision']==evidence
    assert front['overlapResearch']==c.read(c.ROOT/'data/sample/petehub_pitcher_decision_overlap_v1.json')
    assert front['signalLights']==c.read(c.ROOT/'data/sample/petehub_pitcher_decision_signal_lights_v2.json')
    report={'version':'decision_overlap_revision_source_audit_v1','previous_hashes':previous,'new_artifact_hashes':new,'original':original,'included':included,'excluded':excluded,
        'models':48,'progress':'42/51','stop':'15.2','2024_complete_balance_passed':False,'recommendation_allowed':False,
        'test2025_outcomes_examined':False,'visual_acceptance':'pending user','checks':'source/clock/actor/paired model/probability/ranking/accounting only; not causal or visual acceptance'}
    c.save('audit.json',report);c.b.save_json(c.ROOT/'data/sample/petehub_pitcher_decision_overlap_revision_audit_v1.json',report)
    print('15.1/15.2 source/data/clock/model/accounting checks passed; no balance/policy/visual promotion',flush=True)


if __name__=='__main__':main()
