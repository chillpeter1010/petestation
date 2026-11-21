"""Source/data gates for13.5/13.6/14.1. Never browser or visual acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_action_revision as a
from scripts import check_utf8
from scripts import audit_decision_familiarity as diagnostic

u,h,r,b=a.u,a.u.h,a.r,a.b


def read(path):return json.loads(path.read_text('utf-8'))


def main(stage):
    counts={}
    folders=[b.PREP,b.OUT,b.ROOT/'data/research/decision_ablation_v1',a.a.OUT,r.OUT,h.OUT]
    if stage=='full':folders += [u.OUT,a.OUT]
    for folder in folders:
        manifest=read(folder/'manifest.json')
        for entry in manifest['files']:
            path=folder/entry['path'];assert path.stat().st_size==entry['bytes'],path
            assert b.digest(path)==entry['sha256'],path
        counts[folder.name]=len(manifest['files']);print(f'{folder.name}:{len(manifest["files"])} hashes verified',flush=True)
    assert read(r.OUT/'protocol.json')==h.m.protocol()
    assert read(h.OUT/'protocol.json')==h.protocol()
    assert read(u.OUT/'protocol.json')==u.protocol()
    assert read(diagnostic.OUT/'protocol.json')==diagnostic.protocol()
    for guard in read(b.TEMPORAL/'formal_model_guards.json'):
        assert b.digest(Path(guard['path']))==guard['sha256']
    trials=[h.OUT/'attempt1_pa_identity_unfiltered',u.OUT/'attempt1_previous_role_grouping',u.OUT/'attempt2_pa_identity_unfiltered']
    for trial in trials:
        for relative,digest in read(trial/'protocol.json')['input_sha256'].items():
            name=Path(relative).name
            candidates=[b.ROOT/relative]
            for folder in trials:
                candidates += [folder/name,folder/(Path(name).stem+'_source.py')]
            assert any(p.exists() and b.digest(p)==digest for p in candidates),(trial,relative)
        print(f'{trial.name}:superseded protocol inputs/source retained',flush=True)
    exclusion_count=0;forecast_changes={}
    with r.connect() as c:
        def table(name,path):c.read_parquet(str(path)).create_view(name,replace=True)
        def zero(sql):assert c.execute(sql).fetchone()[0]==0,sql
        for year in r.YEARS:
            table('f',u.OUT/f'features_{year}.parquet');table('attack',h.OUT/f'observed_attack_{year}.parquet')
            zero('SELECT count(*)-count(DISTINCT decision_id) FROM f')
            zero('SELECT count(*)-count(DISTINCT request_id) FROM attack')
            zero("SELECT count(*) FROM f WHERE forecast_role<>CASE WHEN is_current THEN option_role ELSE 'RP' END")
            zero('SELECT count(*) FROM f WHERE NOT is_current AND (risk_stuff IS NOT NULL OR risk_location IS NOT NULL)')
            zero('SELECT count(*) FROM f WHERE NOT is_current AND option_role<>forecast_role AND ('+' OR '.join(n+' IS NOT NULL' for n in u.PLUS+['quality','physical','command']+u.RECENT)+')')
            forecast_changes[year]=c.execute('SELECT count(*) FROM f WHERE option_role<>forecast_role').fetchone()[0]
            for name in [n for n in c.table('attack').columns if n.endswith(('_observed_at','_history_at','_reference_at'))]:
                zero(f'SELECT count(*) FROM f JOIN attack USING(request_id) WHERE attack.{name}>=f.decision_at')
            for name in [n for n in c.table('attack').columns if n.endswith(('_received_share','_swing_share','_swing','_whiff','_contact','_foul','_fair','_hard'))]:
                zero(f'SELECT count(*) FROM attack WHERE {name} NOT BETWEEN -1e-9 AND 1.000000001')
            for stem in ['pair','type']:
                total='+'.join(stem+'_'+key+'_rate' for key in b.OUTCOMES)
                zero(f'SELECT count(*) FROM attack WHERE abs({total}-1)>1e-8')
            table('ex',h.OUT/f'identity_exclusions_{year}.parquet');exclusion_count += c.table('ex').count('*').fetchone()[0]
            table('stats',h.OUT/f'pa_stats_{year}.parquet')
            zero('SELECT count(*) FROM ex JOIN stats USING(outcome_key)')
            table('pa',r.OUT/f'pa_observations_{year}.parquet')
            zero('''SELECT count(*) FROM stats JOIN pa USING(outcome_key) WHERE NOT pa.zero_pitch AND
                (pa.actor_pitcher_id<>pa.terminal_pitcher_id OR pa.actual_batter_id<>pa.batter_id)''')
            if year<=2024:
                table('labels',b.PREP/f'clean_labels_{year}.parquet')
                zero('SELECT count(*) FROM ex JOIN labels USING(outcome_key) JOIN f USING(decision_id) WHERE organic_pa_eligible')
            print(f'{year}:identity exclusions, forecast roles, past clocks, rates and scope checks passed',flush=True)
        assert exclusion_count==110
        assert forecast_changes[2024]==285
        for flow in read(diagnostic.OUT/'summary.json')['flow']:
            assert flow['before']-flow['excluded']==flow['after']
            table('clean_stats',h.OUT/f"pa_stats_{flow['year']}.parquet")
            table('curve',r.OUT/f"curve_cohort_{flow['year']}.parquet")
            assert c.execute('SELECT count(*) FROM curve JOIN clean_stats USING(outcome_key)').fetchone()[0]==flow['after']
        if stage=='full':
            assert read(a.OUT/'protocol.json')==a.protocol()
            runtime=read(a.OUT/'runtime_projection.json')
            assert runtime['protocol_sha256']==b.digest(a.OUT/'protocol.json')
            assert runtime['runner_sha256']==b.digest(b.ROOT/'backend/scripts/run_decision_action_projected.py')
            assert runtime['central_full_vs_projected']=='exact_dataframe_equality'
            table('central',a.OUT/'scenario_model_0.parquet');table('full_columns',a.OUT/'runtime_projection/central_full_columns.parquet')
            zero('SELECT count(*) FROM ((SELECT * FROM central EXCEPT SELECT * FROM full_columns) UNION ALL (SELECT * FROM full_columns EXCEPT SELECT * FROM central))')
            report=read(u.OUT/'validation.json')
            for role in ['SP','RP']:
                winner=report['roles'][role]['selected'];assert winner in u.CUMULATIVE
                if winner!='baseline':assert report['roles'][role]['results'][winner]['increment_gate']
                for name in u.VARIANTS:
                    table('v',u.OUT/f'validation_{role}_{name}.parquet')
                    zero('SELECT count(*)-count(DISTINCT decision_id) FROM v')
                    zero('SELECT count(*) FROM v WHERE abs('+'+'.join('p_'+key for key in b.OUTCOMES)+'-1)>1e-9')
                    assert c.table('v').count('*').fetchone()[0]==report['roles'][role]['validation_n']
            table('v',u.OUT/'validation_SP_baseline.parquet');table('v2',u.OUT/'validation_RP_baseline.parquet')
            table('old',r.OUT/'baseline_validation_2024_matchup.parquet')
            zero('SELECT count(*) FROM ((SELECT decision_id FROM old EXCEPT(SELECT decision_id FROM v UNION ALL SELECT decision_id FROM v2)) UNION ALL ((SELECT decision_id FROM v UNION ALL SELECT decision_id FROM v2) EXCEPT SELECT decision_id FROM old))')
            for year in [2025,2026]:
                table('pred',u.OUT/f'predictions_{year}.parquet')
                assert not any(n.startswith(('target','future','observed_pa')) for n in c.table('pred').columns)
                zero('SELECT count(*) FROM pred WHERE abs('+'+'.join('p_'+key for key in b.OUTCOMES)+'-1)>1e-9')
            table('value_rows',a.OUT/'action_values_2024.parquet')
            zero('SELECT count(*)-count(DISTINCT(decision_id,pool)) FROM value_rows')
            zero('SELECT count(*) FROM value_rows WHERE recommendation_allowed OR individual_ranking_allowed OR pool_n<2 OR abs(wpa_continue)>1 OR abs(wpa_pool)>1 OR unsupported_mass NOT BETWEEN0 AND1'.replace('BETWEEN0','BETWEEN 0').replace('AND1','AND 1'))
            assert c.execute("SELECT count(*) FROM value_rows WHERE pool='role'").fetchone()[0]==484
            assert c.table('value_rows').count('*').fetchone()[0]==1556
            for i in range(a.BOOTSTRAPS+1):
                table('scenario',a.OUT/f'scenario_model_{i}.parquet')
                zero('SELECT count(*)-count(DISTINCT(decision_id,pool)) FROM scenario')
                zero('SELECT count(*) FROM scenario WHERE censored_paths<0 OR extrapolated_fraction NOT BETWEEN0 AND1 OR pitches_continue<0 OR pitches_pool<0'.replace('BETWEEN0','BETWEEN 0').replace('AND1','AND 1'))
            table('audit',a.OUT/'availability_lineup_audit.parquet')
            zero('SELECT count(*) FROM audit WHERE official_active_roster_at_decision IS NOT NULL OR warmup_available IS NOT NULL OR medical_available IS NOT NULL OR manual_availability_confirmed IS NOT NULL OR long_term_cost_added_to_value')
            table('cross',a.OUT/'old_new_comparison.parquet')
            assert c.table('cross').count('*').fetchone()[0]==484
    if stage=='full':
        project=next(p for p in read(b.ROOT/'docs/PROJECT_TRACKER.json')['projects'] if p['id']=='pitcher-decision-support')
        assert sum(s['status']=='done' for s in project['slices'])==30
        assert all(s['status']=='planned' for s in project['slices'] if s['id'] in ['14.2','15'])
        assert read(b.ROOT/'frontend/data/pitcherDecisionPlan.json')['project']==project
        for path in [b.ROOT/'docs'/n for n in ['PROJECT_TRACKER.json','PITCHER_DECISION_SUPPORT.md','API_CONTRACTS.md','NEXT_CHAT_HANDOFF.md']]:
            assert not check_utf8.problems(path)
        assert '???' not in json.dumps(project,ensure_ascii=False)
    b.save_json(b.ROOT/f'data/sample/petehub_pitcher_decision_matchup_{stage}_audit_v2.json',{
        'stage':stage,'artifact_counts':counts,'identity_exclusions':exclusion_count,'forecast_vs_prior_role_changes':forecast_changes,
        'frozen_protocols_verified':True,'formal_metadata_guards_verified':2,'test_outcome_metrics_examined':False,
        'recommendation_allowed':False,'ui_acceptance':'pending_user','status':'source_checks_passed'})
    print(f'{stage} source checks passed; no UI acceptance claimed',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['sources','full'],default='full')
    main(parser.parse_args().stage)
