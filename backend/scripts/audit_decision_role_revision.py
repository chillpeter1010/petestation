"""Source/data release checks for Slices 13.1-13.4; no UI acceptance."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_role_models as m
from scripts import check_utf8

r, b, OUT = m.r, m.b, m.OUT


def read(path):
    return json.loads(path.read_text('utf-8'))


def main():
    counts = {}
    for folder in [b.PREP, b.OUT, b.ROOT/'data/research/decision_ablation_v1',
                   b.ROOT/'data/research/decision_action_values_v1', OUT]:
        manifest = read(folder/'manifest.json')
        for entry in manifest['files']:
            path = folder/entry['path']
            assert path.stat().st_size == entry['bytes'], path
            assert b.digest(path) == entry['sha256'], path
        counts[folder.name] = len(manifest['files'])
        print(f"{folder.name}: {counts[folder.name]} hashes verified", flush=True)
    assert read(OUT/'protocol.json') == m.protocol()
    for guard in read(b.ROOT/'data/research/decision_support_temporal_20261114/formal_model_guards.json'):
        assert b.digest(Path(guard['path'])) == guard['sha256']
    total_options = 0
    with r.connect() as c:
        def table(name, path):
            c.read_parquet(str(path)).create_view(name, replace=True)

        def zero(sql):
            assert c.execute(sql).fetchone()[0] == 0, sql

        for year in r.YEARS:
            table('w', OUT/f'workload_features_{year}.parquet')
            zero('SELECT count(*)-count(DISTINCT (decision_id,option_pitcher_id)) FROM w')
            zero('SELECT count(*) FROM w WHERE last_pitch_available_at>=decision_at OR role_history_available_at>=decision_at')
            for days in r.WINDOWS:
                zero(f'SELECT count(*) FROM w WHERE (NOT window_{days}d_complete AND pitches_{days}d_before IS NOT NULL) OR (window_{days}d_complete AND pitches_{days}d_before IS DISTINCT FROM observed_pitches_{days}d)')
            total_options += c.execute('SELECT count(*) FROM w').fetchone()[0]
            for anchor in ['current', 'pa']:
                table('f', OUT/f'{anchor}_features_{year}.parquet')
                zero('SELECT count(*)-count(DISTINCT request_id) FROM f')
                zero('SELECT count(*) FROM f WHERE observation_at>=cutoff OR state_observed_at>=cutoff OR prior_pa_available_at>=cutoff')
            table('l', OUT/f'recent_links_{year}.parquet')
            table('p', OUT/f'recent_profiles_{year}.parquet')
            zero('SELECT count(*)-count(DISTINCT (decision_id,option_pitcher_id)) FROM l')
            zero('SELECT count(*)-count(DISTINCT profile_id) FROM p')
            zero('SELECT count(*) FROM l LEFT JOIN p USING(profile_id) WHERE p.profile_id IS NULL OR p.pitcher_id<>l.option_pitcher_id OR p.role<>l.option_role OR p.latest_available_at>=l.decision_at OR l.history_age_hours<0')
            columns = c.table('p').columns
            for name in [n[:-2] for n in columns if n.endswith('_n')]:
                zero(f'SELECT count(*) FROM p WHERE ({name}_n=0 AND {name}_mean IS NOT NULL) OR ({name}_n<2 AND ({name}_low80 IS NOT NULL OR {name}_high80 IS NOT NULL))')
            for name in [n for n in columns if n.endswith('_observation_at')]:
                zero(f'SELECT count(*) FROM l JOIN p USING(profile_id) WHERE p.{name}>=l.decision_at')
            print(f'{year}: workload, two anchors, recent-state clocks/keys/support verified', flush=True)
        for year in range(2021, 2025):
            table('f', OUT/f'curve_cohort_{year}.parquet')
            table('roster', r.BASE/f'roster_{year}.parquet')
            zero("SELECT count(*) FROM f WHERE NOT EXISTS(SELECT 1 FROM roster z WHERE z.game_pk=f.game_pk AND z.player_id=f.pitcher_id AND z.position_code='1')")
            zero('SELECT count(*)-count(DISTINCT outcome_key) FROM f')
            zero('SELECT count(*) FROM f WHERE batter_history_at>=anchor_at OR label_available_at<anchor_at OR future10_at<anchor_at')
            zero('SELECT count(*) FROM f WHERE bf_index<>completed_bf_before+1 OR same_batter_encounter<>observed_pair_encounters_before+1')
            for metric in ['stuff', 'location']:
                zero(f'SELECT count(*) FROM f WHERE future10_{metric} IS NOT NULL AND future10_{metric}_n<8')
        for level in ['workload', 'matchup']:
            table('f', OUT/f'baseline_validation_2024_{level}.parquet')
            table('old', b.OUT/f'validation_2024_{level}.parquet')
            zero('SELECT count(*) FROM ((SELECT decision_id FROM f EXCEPT SELECT decision_id FROM old) UNION ALL (SELECT decision_id FROM old EXCEPT SELECT decision_id FROM f))')
            zero('SELECT count(*) FROM f WHERE abs('+ '+'.join('p_'+x for x in b.OUTCOMES)+'-1)>1e-9')
        for year in [2025, 2026]:
            table('f', OUT/f'risk_scores_{year}.parquet')
            assert not any(n.startswith(('future', 'target')) for n in c.table('f').columns)
            zero('SELECT count(*)-count(DISTINCT decision_id) FROM f')
            zero('SELECT count(*) FROM f WHERE stuff_drop_p NOT BETWEEN 0 AND 1 OR location_drop_p NOT BETWEEN 0 AND 1')
            assert not read(OUT/f'risk_score_{year}.json')['target_outcome_metrics_examined']
            table('f', OUT/f'baseline_predictions_{year}.parquet')
            for level in ['workload', 'matchup']:
                zero('SELECT count(*) FROM f WHERE abs('+ '+'.join(level+'_p_'+x for x in b.OUTCOMES)+'-1)>1e-9')
    for report in read(OUT/'risk_validation.json')['reports']:
        for model in report.get('models', {}).values():
            assert not model.get('convergence_warning', False)
        assert report['eligible_prefixes'] == report['observed_future10'] + report['unobserved_or_measurement_insufficient']
    assert total_options == 10415470
    assert not read(OUT/'decline_curves.json')['replicated_panels']
    for role in ['SP', 'RP']:
        figure = OUT/f'decline_{role}_2024.svg'
        ET.parse(figure)
        assert b.digest(figure) == b.digest(b.ROOT/'frontend/public/research/decision-role-observation-v2'/figure.name)
    tracker = read(b.ROOT/'docs/PROJECT_TRACKER.json')
    project = next(p for p in tracker['projects'] if p['id'] == 'pitcher-decision-support')
    assert sum(s['status']=='done' for s in project['slices']) == 27
    assert all(s['status']=='planned' for s in project['slices'] if s['id'] in ['13.5','13.6','14.1','14.2','15'])
    assert read(b.ROOT/'frontend/data/pitcherDecisionPlan.json')['project'] == project
    assert '???' not in json.dumps(project, ensure_ascii=False)
    for path in [b.ROOT/'docs'/n for n in ['PROJECT_TRACKER.json','PITCHER_DECISION_SUPPORT.md','NEXT_CHAT_HANDOFF.md','API_CONTRACTS.md']]:
        assert not check_utf8.problems(path), path
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_validation_v2.json', {
        'version':'decision_role_observation_v2', 'protocol_sha256':b.digest(OUT/'protocol.json'),
        'artifact_counts':counts, 'formal_metadata_guards_verified':2, 'option_rows':total_options,
        'source_clock_keys_support_probability_checks':'passed', 'tracker_done':27, 'tracker_total':39,
        'test_outcome_metrics_examined':False, 'ui_acceptance':'pending_user', 'recommendation_allowed':False})
    print('Source/data checks passed; UI acceptance remains pending user.', flush=True)


if __name__ == '__main__':
    main()
