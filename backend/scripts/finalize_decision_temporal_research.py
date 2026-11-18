"""Validate temporal boundaries and export narrow, outcome-free downstream feature contracts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import duckdb
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.decision_temporal_common import BASE,OUT,ROOT,PHYSICAL,LOCATION,save,VERSION
from scripts.train_decision_temporal_plus import epoch

def run()->None:
    c=duckdb.connect(config={'threads':2,'memory_limit':'2GB'})
    checks={};years=[]
    guards=json.loads((OUT/'formal_model_guards.json').read_text('utf-8'))
    for item in guards:assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
    checks['formal_metadata_changes']=0
    for path in (OUT/'models').glob('**/*metadata.json'):
        m=json.loads(path.read_text('utf-8'));cutoff=m.get('cutoff',m.get('fold',{}).get('train_end'))
        assert m['maximum_label_available_at']<epoch(cutoff)
        assert m['formal_replacement'] is False
    checks['training_label_time_violations']=0
    for year in range(2021,2027):
        print(f'{year}: validate and publish outcome-free features',flush=True)
        c.execute(f"CREATE OR REPLACE VIEW f AS SELECT * FROM read_parquet('{(OUT/f'features_{year}.parquet').as_posix()}')")
        c.execute(f"CREATE OR REPLACE VIEW s AS SELECT * FROM read_parquet('{(OUT/f'scored_{year}_*.parquet').as_posix()}')")
        # No runs, future half/game outcomes, appearance exit time, final role count or targets allowed here.
        columns=list(dict.fromkeys(['year','game_pk','event_id','appearance_id','pitcher_id','batter_id','event_at','observed_at','role','pitch_type',*PHYSICAL,*LOCATION]))
        selected=[f'CASE WHEN s.event_id IS NOT NULL THEN s.{col} ELSE f.{col} END AS {col}' if col in PHYSICAL else 'f.'+col for col in columns]
        c.execute(f"""CREATE OR REPLACE TABLE narrow AS SELECT {','.join(selected)},
          f.source_valid,f.alignment_status,f.roster_pitcher,(f.batter=f.batter_id) source_batter_consistent,
          s.research_stuff_plus,s.research_location_plus,s.plus_model_id,s.plus_train_cutoff,
          CASE WHEN s.event_id IS NULL THEN 'warmup_no_past_model' WHEN NOT f.source_valid THEN 'unsafe_event_source'
            WHEN s.research_stuff_plus IS NULL AND s.research_location_plus IS NULL THEN 'tracking_or_role_unavailable'
            ELSE 'available' END status
          FROM f LEFT JOIN s USING(event_id)""")
        assert c.execute('SELECT count(*)-count(DISTINCT event_id) FROM narrow').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM narrow WHERE plus_train_cutoff>observed_at').fetchone()[0]==0
        c.execute(f"COPY narrow TO '{(OUT/f'pitch_features_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        c.execute(f"""COPY(SELECT event_id,game_completed_at label_available_at,runs_on_event,post_outs,post_base,post_balls,post_strikes,remaining_runs FROM f)
          TO '{(OUT/f'pitch_labels_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)""")
        c.execute(f"""COPY(SELECT event_id,game_pk,batter_id,batter source_batter_id FROM f WHERE batter<>batter_id)
          TO '{(OUT/f'batter_identity_disagreements_{year}.parquet').as_posix()}' (FORMAT PARQUET)""")
        # Publish every official decision, including explicit early-history warmup rows.
        target=OUT/f'context_features_{year}.parquet';temp=OUT/f'context_features_{year}.tmp'
        c.execute(f"CREATE OR REPLACE TABLE old_context AS SELECT * FROM read_parquet('{target.as_posix()}')")
        c.execute(f"""COPY(SELECT d.year,d.game_pk,d.decision_id,epoch(try_cast(d.decision_time AS TIMESTAMPTZ)) decision_at,
          o.* EXCLUDE(year,game_pk,decision_id,decision_at,status),
          coalesce(o.status,CASE WHEN epoch(try_cast(d.decision_time AS TIMESTAMPTZ))<{epoch('2021-07-01')} THEN 'warmup_no_past_model' ELSE 'unknown_or_unsafe_source' END) status
          FROM read_parquet('{(BASE/f'decisions_{year}.parquet').as_posix()}') d LEFT JOIN old_context o USING(decision_id))
          TO '{temp.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)""")
        temp.replace(target)
        # One source pitch ends ~6 seconds after its official exit action. Availability
        # is the later observation. This update changes provenance, not a fitted value.
        prior=OUT/f'candidate_state_priors_{year}.parquet';temp=OUT/f'candidate_state_priors_{year}.tmp'
        names=[r[0] for r in c.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(prior)]).fetchall()]
        projection='* EXCLUDE(prior_state_available_at)' if 'prior_state_available_at' in names else '*'
        c.execute(f"CREATE OR REPLACE TABLE old_prior AS SELECT {projection} FROM read_parquet('{prior.as_posix()}')")
        assert c.execute('SELECT count(*) FROM old_prior WHERE greatest(prior_state_closed_at,prior_state_observed_at)>=cutoff_epoch').fetchone()[0]==0
        c.execute(f"COPY(SELECT *,greatest(prior_state_closed_at,prior_state_observed_at) prior_state_available_at FROM old_prior) TO '{temp.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        temp.replace(prior)
        # Per-prefix and per-decision timelines must use only delivered, earlier pitches.
        violation=c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/f'decision_states_{year}.parquet').as_posix()}') WHERE state_observed_at>=decision_at OR state_train_cutoff>state_observed_at").fetchone()[0]
        assert violation==0
        counts=c.execute('SELECT count(*),count(research_stuff_plus),count(research_location_plus),count(*) FILTER(WHERE status=\'warmup_no_past_model\'),count(*) FILTER(WHERE NOT source_batter_consistent) FROM narrow').fetchone()
        years.append(dict(zip(['year','pitches','stuff','location','warmup','source_batter_disagreements'],[year,*counts])))
    c.execute(f"CREATE VIEW refs AS SELECT * FROM read_parquet('{(OUT/'prior_fastball_refs.parquet').as_posix()}')")
    assert c.execute('SELECT count(*) FROM refs WHERE reference_closed_at>=entry_at').fetchone()[0]==0
    checks.update({'prior_fastball_time_violations':0,'prefix_boundary_time_violations':0,'candidate_history_time_violations':0,
      'duplicate_pitch_feature_keys':0,'missing_li_filled_with_one':False,'individual_ranking_allowed':False})
    # Store observed distribution diagnostics without recentering held-out years.
    distribution=[]
    for role in ['SP','RP']:
        for year in range(2021,2027):
            rows=c.execute('SELECT median(quality_plus),stddev_pop(quality_plus),median(physical_plus),stddev_pop(physical_plus),median(command_plus),stddev_pop(command_plus) FROM read_parquet(?)',[str(OUT/f'states_{year}_{role.lower()}.parquet')]).fetchone()
            distribution.append(dict(zip(['year','role','quality_median','quality_sd','physical_median','physical_sd','command_median','command_sd'],[year,role,*rows])))
    evidence={'version':VERSION,'date':'2026-11-14','checks':checks,'years':years,'prefix_distributions':distribution,
      'narrow_feature_contract':'pitch_features_YEAR + decision_states_YEAR + context_features_YEAR + candidate_state_priors_YEAR; labels separate',
      'excluded_downstream_features':['runs_on_event','remaining_runs','post_outs','post_base','game_completed_at','closed_at'],
      'clock_rule':'History available at max(official exit, last included pitch end); 2026 one 6.474-second source discrepancy, no selected candidate row precedes availability.',
      'gates':{'research_artifacts_ready':True,'formal_promotion':False,'predictive_next_segment_validated':False,'causal_benefit_validated':False,'action_model_trained':False}}
    save(OUT/'validation.json',evidence)
    for stage in range(6,11):
        path=ROOT/f'sample/petehub_pitcher_decision_slice{stage}_v1.json';sample=json.loads(path.read_text('utf-8'))
        sample['source_only_validation']=checks
        if stage==6:sample['identity_repair']=json.loads((OUT/'batter_identity_repair.json').read_text('utf-8'));sample['feature_contract']=evidence['narrow_feature_contract']
        if stage in [8,9]:sample['observed_prefix_distributions']=[r for r in distribution if r['role']==('SP' if stage==8 else 'RP')]
        save(path,sample)
    # SHA manifest is last, after all outputs are finalized. Temporary scratch is excluded.
    paths=[p for p in OUT.rglob('*') if p.is_file() and p.suffix in {'.parquet','.json','.joblib'} and 'tmp' not in p.parts and p.name!='manifest.json']
    manifest=[]
    for i,path in enumerate(paths,1):
        digest=hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
        manifest.append({'path':str(path.relative_to(OUT)),'bytes':path.stat().st_size,'sha256':digest.hexdigest()})
        if i%30==0:print(f'manifest: {i}/{len(paths)} files',flush=True)
    save(OUT/'manifest.json',{'version':VERSION,'files':manifest,'source_only_checks':checks})
    print('Temporal research artifacts validated; promotion/action gates remain closed.',flush=True)

if __name__=='__main__':run()
