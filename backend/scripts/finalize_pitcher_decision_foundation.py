"""Validate and publish small evidence snapshots for authorized Slices 2–5."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import duckdb

ROOT=Path(__file__).resolve().parents[2]/'data'
OUT=ROOT/'research/decision_support_pipeline_20261114'


def publish():
    c=duckdb.connect(':memory:',config={'threads':2,'memory_limit':'1GB'})
    c.execute(f"SET temp_directory='{(OUT/'duckdb_validation_tmp').as_posix()}'")
    ledgers=[json.loads((OUT/f'ledger_{y}.json').read_text(encoding='utf-8')) for y in range(2021,2027)]
    s3={'slice':3,'date':'2026-11-14','years':ledgers,'games':sum(r['games'] for r in ledgers),
        **{k:sum(r['rows'][k] for r in ledgers) for k in ['events','plays','appearances']},
        **{k:sum(r['counts'][k] for r in ledgers) for k in ['physical_pitches','zero_pitch_appearances','unpriced_wpa_plays']},
        'outcomes_stored_once':True,'source_drift':False,'seven_inning_era_supported':True}
    s4=json.loads((OUT/'slice4.json').read_text(encoding='utf-8'))
    s5=json.loads((OUT/'slice5.json').read_text(encoding='utf-8'))
    assert s3['games']==14577 and s3['physical_pitches']==4270416
    assert s4['strict_time_violations']==s5['strict_time_violations']==0
    checks=[]
    for year in range(2021,2027):
        for name,file in [('d',f'decisions_{year}.parquet'),('b',f'bullpen_candidates_{year}.parquet'),('s',f'bullpen_sets_{year}.parquet'),('p',f'plays_{year}.parquet')]:
            c.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{(OUT/file).as_posix()}')")
        bf=c.execute('SELECT count(*) FROM p WHERE is_batter_faced').fetchone()[0]
        previous=c.execute('SELECT sum(bf) FROM read_parquet(?)',[str(ROOT/f'research/catcher_descriptive/slice1/yearly/pa_accounting_{year}.parquet')]).fetchone()[0]
        assert bf==previous
        duplicates=c.execute('SELECT count(*)-count(DISTINCT (decision_id,pitcher_id)) FROM b').fetchone()[0]
        temporal=c.execute('SELECT count(*) FROM b WHERE last_pitch_epoch>=cutoff_epoch OR history_closed_epoch>=cutoff_epoch').fetchone()[0]
        bad_gate=c.execute("SELECT count(*) FROM b JOIN d USING(decision_id) WHERE nominal_eligible AND (statutory_status<>'allowed' OR is_initial_start OR NOT completed_batter_play OR NOT base_state_known OR outgoing_pitcher_id=b.pitcher_id OR json_contains(used_pitcher_ids,cast(b.pitcher_id AS VARCHAR)) OR json_contains(removed_player_ids,cast(b.pitcher_id AS VARCHAR)))").fetchone()[0]
        invented=c.execute('SELECT count(*) FROM b WHERE individual_ranking_allowed OR warmup_available IS NOT NULL OR body_available IS NOT NULL').fetchone()[0]
        sets=c.execute('SELECT count(*),count(DISTINCT decision_id) FROM s').fetchone()
        actual=c.execute("SELECT count(*),count(*) FILTER(WHERE list_contains(s.candidate_ids,d.incoming_pitcher_id)) FROM d JOIN s USING(decision_id) WHERE observed_change AND statutory_status='allowed' AND completed_batter_play AND NOT is_initial_start").fetchone()
        c.execute(f"CREATE OR REPLACE VIEW w AS SELECT * FROM read_parquet('{(OUT/f'workload_{year}.parquet').as_posix()}')")
        comparison=' OR '.join(f'b.pitches_{n}d_before<>w.pitches_{n}d_before' for n in [1,3,7,14])
        reconciled=c.execute(f'SELECT count(*),count(*) FILTER(WHERE {comparison}) FROM b JOIN w USING(decision_id,pitcher_id)').fetchone()
        assert reconciled[1]==0,('candidate/exact SQL rolling counts',year,reconciled)
        assert duplicates==temporal==bad_gate==invented==0,(year,duplicates,temporal,bad_gate,invented)
        assert sets[0]==sets[1]==next(r['rows']['decisions'] for r in ledgers if r['year']==year)
        checks.append({'year':year,'duplicate_candidate_keys':duplicates,'time_violations':temporal,'illegal_nominal_candidates':bad_gate,
            'invented_availability_or_ranking':invented,'statutorily_supported_observed_changes':actual[0],
            'observed_incoming_in_nominal_pool':actual[1], 'candidate_vs_exact_sql_rows':reconciled[0],
            'candidate_vs_exact_sql_window_disagreements':reconciled[1]})
        print(f'validation: {year} keys, time, removal/rule gates and BF accounting passed',flush=True)
    independent=json.loads((OUT/'workload_independent_check.json').read_text(encoding='utf-8'))
    assert independent['count_disagreements']==0
    s3['bf_reconciles_existing_official_ledger']=True
    s4['independent_window_check']=independent
    s5['data_checks']=checks
    for stage,value in [(3,s3),(4,s4),(5,s5)]:
        (OUT/f'slice{stage}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/f'sample/petehub_pitcher_decision_slice{stage}_v1.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    repairs=[json.loads((ROOT/f'research/decision_support_slice2_20261114/repair_{y}.json').read_text(encoding='utf-8')) for y in [2024,2026]]
    for item in repairs:
        y,pk=item['year'],item['game_pk']
        with duckdb.connect(str(ROOT/f'MLB{y}/mlb_{y}.duckdb'),read_only=True) as src:
            count=src.execute('SELECT count(*),count(DISTINCT pitch_uid) FROM pitches WHERE game_pk=?',[pk]).fetchone()
            assert count[0]==count[1]==item['after_rows']
    s2={'slice':2,'date':'2026-11-14','status':'completed','games':repairs,'physical_key_differences_resolved':249,
        'original_backups_preserved':True,'formal_models_refitted':False,'tracking_imputed':False,
        'downstream_note':'Formal derivatives remain versioned historical snapshots; this research warehouse reads repaired sources.'}
    (ROOT/'sample/petehub_pitcher_decision_slice2_v1.json').write_text(json.dumps(s2,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'date':'2026-11-14','slices':[2,3,4,5],'data_checks_passed':True,'individual_ranking_allowed':False,
        'visual_acceptance':'pending_user_for_new_results_only','checks':checks,
        'limitations':['Most roster dates are retrospective game-roster observations, not dated-active certified.',
            'Unknown warm-up, health and intraday transactions remain unknown.',
            'Unpriced WE/RE boundaries, source-clock issues and incomplete early history are retained, not imputed.',
            'No Slice 6 feature training, xWPA model or pitching alert has been started.']}
    (OUT/'foundation_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Slices 2–5 data validation passed; research-only candidate gate closed.',flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');publish()
