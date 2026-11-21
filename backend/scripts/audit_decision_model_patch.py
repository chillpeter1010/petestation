"""Source-only reproducibility/temporal/retention gates; no visual acceptance."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_model_patch as p
from scripts import build_decision_action_revision as a
from scripts import audit_decision_familiarity as familiarity
from scripts import run_decision_model_patch_impact as impact_runner

b,r,u=p.b,p.r,p.u


def read(path):return json.loads(path.read_text('utf-8'))


def main():
    counts={}
    folders=[b.PREP,b.OUT,b.ROOT/'data/research/decision_ablation_v1',a.a.OUT,r.OUT,u.h.OUT,u.OUT,a.OUT,p.OUT]
    if read(p.OUT/'impact_review.json')['rerun']:folders.append(impact_runner.OUT)
    for folder in folders:
        manifest=read(folder/'manifest.json')
        for entry in manifest['files']:
            path=folder/entry['path'];assert path.stat().st_size==entry['bytes'] and b.digest(path)==entry['sha256'],path
        counts[folder.name]=len(manifest['files'])
        print(f'{folder.name}:{len(manifest["files"])} frozen files verified',flush=True)
    assert read(p.OUT/'protocol.json')==p.protocol()
    assert read(u.OUT/'protocol.json')==u.protocol()
    assert read(u.h.OUT/'protocol.json')==u.h.protocol()
    assert read(r.OUT/'protocol.json')==u.h.m.protocol()
    assert read(a.OUT/'protocol.json')==a.protocol()
    assert read(familiarity.OUT/'protocol.json')==familiarity.protocol()
    for guard in read(b.TEMPORAL/'formal_model_guards.json'):
        assert b.digest(Path(guard['path']))==guard['sha256']
    selection=read(p.OUT/'selection.json');assert not selection['2024_used_for_selection'] and not selection['2025_outcomes_examined']
    splits=[]
    for role in ['SP','RP']:
        screen=read(p.OUT/f'screen_{role}.json');assert len(screen['reports'])==64
        assert {x['year'] for x in screen['reports']}=={2022,2023}
        for year in [2022,2023,2024]:
            ledger=pd.read_parquet(p.OUT/f'split_{role}_{year}.parquet')
            fit=ledger[ledger.partition.eq('fit')];cal=ledger[ledger.partition.eq('calibration')];valid=ledger[ledger.partition.eq('validation')]
            assert fit.pa_end_at.max()<cal.decision_at.min() and cal.pa_end_at.max()<valid.decision_at.min()
            assert ledger.decision_id.is_unique
            assert set(fit.game_pk).isdisjoint(cal.game_pk) and set(cal.game_pk).isdisjoint(valid.game_pk)
            splits.append({'role':role,'year':year,'fit':len(fit),'calibration':len(cal),'validation':len(valid)})
        report=read(p.OUT/f'confirmation_{role}.json')
        assert [x['config'] for x in report['candidates']]==[x['config'] for x in selection['candidates'][role]]
        accepted=[x['config'] for x in report['candidates'] if x['increment_gate']]
        assert report['selected']==(accepted[0] if accepted else 'frozen_v2_baseline')
        old=pd.read_parquet(u.OUT/f'validation_{role}_baseline.parquet')
        for row in report['candidates']:
            frame=pd.read_parquet(p.OUT/f'confirmation_{role}_{row["config"]}.parquet')
            assert frame.decision_id.tolist()==old.decision_id.tolist()
            matrix=frame[['p_'+x for x in b.OUTCOMES]].to_numpy()
            assert np.isfinite(matrix).all() and (matrix>0).all() and np.allclose(matrix.sum(axis=1),1,atol=1e-10)
            assert len(frame)==report['validation_n']
        assert len(read(p.OUT/f'explanation_{role}.json')['contrasts'])==6
    diagnostic=read(p.OUT/'diagnostics.json')
    for year in range(2021,2025):
        f=p.load(year)
        assert f.loc[~f.is_current,list(p.LIVE_MAP)].isna().all().all()
        assert sum(x['n'] for x in diagnostic['distributions'] if x['year']==year and x['field']=='option_stuff')==len(f)
    sample=read(b.ROOT/'data/sample/petehub_pitcher_decision_model_patch_v3.json')
    assert sample['search']['test2025Locked'] and not sample['recommendationAllowed'] and not sample['individualRankingAllowed']
    impact=read(p.OUT/'impact_review.json')
    assert sum(impact['directionCounts'].values())==484 and impact['originalCases']==484
    if impact['rerun']:
        assert read(impact_runner.OUT/'protocol.json')==impact_runner.protocol()
        assert read(impact_runner.OUT/'cache_check.json')['central_repeated_vs_direct_max_abs']<=1e-13
        old=pd.read_parquet(a.OUT/'action_values_2024.parquet');new=pd.read_parquet(impact_runner.OUT/'action_values_2024.parquet')
        assert old[['decision_id','pool']].equals(new[['decision_id','pool']]) and len(new)==1556
        assert not new.recommendation_allowed.any() and not new.individual_ranking_allowed.any()
        assert new.pool_n.ge(2).all() and new.unsupported_mass.between(0,1).all()
        for entry in read(impact_runner.OUT/'bootstrap.json')['replicates']:
            if 'sha256' in entry:assert b.digest(impact_runner.OUT/f'bootstrap_{entry["replicate"]}_{entry["role"]}.joblib')==entry['sha256']
    tracker=read(b.ROOT/'docs/PROJECT_TRACKER.json');project=next(x for x in tracker['projects'] if x['id']=='pitcher-decision-support')
    assert len(project['slices'])==43 and sum(x['status']=='done' for x in project['slices'])==34
    assert all(x['status']=='planned' for x in project['slices'] if x['id'] in ['14.2','15'])
    snapshot=read(b.ROOT/'frontend/data/pitcherDecisionPlan.json')
    assert snapshot['project']==project and snapshot['modelPatchRevision']==sample
    report={'version':'decision_model_patch_source_audit_v3','frozen_files':counts,'splits':splits,
        'progress':'34/43','stop':'14.1.1','test2025_outcomes_examined':False,'visual_acceptance':'user pending'}
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_model_patch_audit_v3.json',report)
    print('Patch source/temporal/model/authority gates passed; visual acceptance belongs to user',flush=True)


if __name__=='__main__':main()
