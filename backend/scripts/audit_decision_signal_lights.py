"""14.2.1 display contract/data/planning gates; no visual acceptance or training."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import export_decision_signal_lights as x


def main():
    read=x.q.read;digest=x.q.b.digest
    data=read(x.SAMPLE);sources=read(x.OUT/'sources.json')
    assert data==read(x.OUT/'prototype.json') and data['recommendationAllowed'] is False and data['mode']=='observed'
    for relative,sha in sources['inputs'].items():assert digest(x.ROOT/relative)==sha,relative
    for relative,sha in sources['display_sources'].items():assert digest(x.ROOT/relative)==sha,relative
    assert digest(Path(x.__file__))==sources['builder_sha256']
    assert not sources['models_retrained'] and not sources['new_alerts_computed'] and not sources['test2025_outcomes_examined']
    original=read(x.q.OUT/'summary.json')
    assert {c['decisionId'] for c in data['cases']}=={c['decision_id'] for c in original['alerts']}
    assert original['flow']['independent_alerts']==11 and original['flow']['matched_alerts']==0
    assert len(data['cases'])==len({c['id'] for c in data['cases']})==11
    assert sum(c['pitches']<35 for c in data['cases'])==data['counts']['belowObservationMinimum']==7
    assert sum(c['observationMature'] for c in data['cases'])==data['counts']['matureObservation']==4
    for case in data['cases']:
        assert case['role']=='SP' # this adapter's35/100 support is explicitly SP-only
        assert {c['id'] for c in case['lights']}==set('ABCD') and len(case['lights'])==4
        assert all(light['state']=='gray' and not light['calibrated'] for light in case['lights'])
        assert case['gates']['availability']=='unknown' and case['gates']['statePersistence']=='unknown'
    tracker=read(x.ROOT/'docs/PROJECT_TRACKER.json');project=next(p for p in tracker['projects'] if p['id']=='pitcher-decision-support')
    assert len(project['slices'])==47 and sum(s['status']=='done' for s in project['slices'])==36
    items={s['id']:s for s in project['slices']}
    assert items['14.2.1']['status']=='done'
    assert all(items[s]['status']=='planned' for s in ['14.2.2','14.2.3','14.2.4','15','16','17','18','19','20'])
    assert '14.2.4' in items['15']['depends_on'] and '14.2.4' in items['20']['depends_on']
    snapshot=read(x.ROOT/'frontend/data/pitcherDecisionPlan.json')
    assert snapshot['project']==project and snapshot['signalLights']==data
    assert snapshot['alertResearch']==read(x.ROOT/'data/sample/petehub_pitcher_decision_alert_research_v1.json')
    x.q.b.save_json(x.ROOT/'data/sample/petehub_pitcher_decision_signal_lights_audit_v1.json',{
        'version':'decision_signal_lights_display_audit_v1','existing_input_hashes_checked':len(sources['inputs']),
        'display_source_hashes_checked':len(sources['display_sources']),'real_cases':len(data['cases']),
        'uncalibrated_gray_groups':sum(len(c['lights']) for c in data['cases']),'new_alerts_computed':False,
        'old_result':{'alerts':11,'matches':0},'progress':'36/47','stop':'14.2.1',
        'test2025_outcomes_examined':False,'visual_acceptance':'pending user'})
    print('14.2.1 source/data/unknown-evidence/workflow gates passed; visual acceptance pending user',flush=True)


if __name__=='__main__':main()
