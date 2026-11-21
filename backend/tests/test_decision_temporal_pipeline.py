from copy import deepcopy
from pathlib import Path
import hashlib
import json

import duckdb
import numpy as np
import pandas as pd

from app.services.decision_temporal_common import OUT,ROOT,PHYSICAL,LOCATION,align,fold_for,protocol
from scripts.build_decision_prefix_states import raw_prefix,MEASURES
from scripts.build_decision_temporal_context import post_state,re_get,transition_fit
from scripts.train_decision_temporal_plus import targets,epoch


def test_alignment_does_not_guess_duplicate_candidates_or_automatic_pitch_offset():
    pitch={'speed':95.,'type':'FF','x':0.,'z':2.}
    tracked={'release_speed':95.,'pitch_type':'FF','plate_x':0.,'plate_z':2.}
    assert align([pitch],[tracked,deepcopy(tracked)])=={}
    assert align([pitch],[tracked])=={0:0}
    wrong={**tracked,'release_speed':80.}
    assert align([pitch],[wrong,tracked])=={0:1}
    assert align([pitch],[{**tracked,'plate_z':3.}])=={}


def test_temporal_warmup_and_frozen_test_reference():
    assert fold_for('2021-06-30') is None
    assert fold_for('2021-07-01')['train_end']=='2021-07-01'
    assert fold_for('2025-06-01')['id']==fold_for('2026-10-01')['id']=='frozen_2024'
    assert not any('wpa' in col or 'delta_run' in col or 'until_next' in col for col in PHYSICAL+LOCATION)


def test_pitch_target_owns_reference_and_defense_sign():
    frame=pd.DataFrame({'outs_before':[0,0],'base_state_before':[0,0],'balls_before':[0,0],'strikes_before':[0,0],
        'post_outs':[3,0],'post_base':[0,0],'post_balls':[0,1],'post_strikes':[0,0],'runs_on_event':[0,1]})
    value=targets(frame,{(0,0,0,0):.5,(0,0,1,0):.6})
    assert np.allclose(value,[.5,-1.1])


def test_prefix_does_not_read_future_deliveries_and_resumption_warms_again(tmp_path,monkeypatch):
    import scripts.build_decision_prefix_states as module
    monkeypatch.setattr(module,'OUT',tmp_path)
    rows=[]
    for i in range(1,24):
        row={'year':2024,'game_pk':1,'event_id':f'1:1:{i}','appearance_id':'1:home:2','pitcher_id':2,'role':'RP',
            'observed_at':1000+i*20+(40000 if i>=13 else 0),'event_at':999+i*20+(40000 if i>=13 else 0),
            'event_index':i,'entry_at':1000,'closed_at':99999,'game_completed_at':100000,'plus_model_id':'fixture',
            'pitch_type':'FF','alignment_status':'validated_order','source_valid':True,'roster_pitcher':True}
        row.update({m:100.+i*.1 for m in MEASURES});rows.append(row)
    path=tmp_path/'scored_2024_fixture.parquet';pd.DataFrame(rows).to_parquet(path)
    raw_prefix(2024);a=pd.read_parquet(tmp_path/'prefix_raw_2024.parquet')
    changed=deepcopy(rows)
    for row in changed[10:]:
        for m in MEASURES:row[m]+=9000
    pd.DataFrame(changed).to_parquet(path);raw_prefix(2024);b=pd.read_parquet(tmp_path/'prefix_raw_2024.parquet')
    pd.testing.assert_frame_equal(a[a.event_id=='1:1:10'].reset_index(drop=True),b[b.event_id=='1:1:10'].reset_index(drop=True))
    assert '1:1:13' not in set(a.event_id) and '1:1:21' not in set(a.event_id)
    assert '1:1:22' in set(a.event_id)


def test_seven_inning_terminal_walkoff_and_automatic_runner():
    state=pd.DataFrame({'inning':[7,7,7,7],'bottom':[0,1,1,1],'scheduled_innings':[7]*4,
       'score_diff':[1,-1,0,0],'outs':[2]*4,'base_state':[0]*4,'balls':[0]*4,'strikes':[0]*4})
    post,terminal=post_state(state,np.array([0,0,0,1]),np.array([3,3,3,0]),np.array([0]*4))
    assert terminal[0]==1 and terminal[1]==0 and np.isnan(terminal[2]) and terminal[3]==1
    assert post.iloc[2].inning==8 and post.iloc[2].base_state==2 and post.iloc[2].bottom==0
    assert re_get(pd.DataFrame({'outs':[3],'base_state':[7],'extra':[1]}),{})[0]['mean']==0


def test_artifacts_have_past_only_provenance_and_formal_metadata_unchanged():
    for item in json.loads((OUT/'formal_model_guards.json').read_text('utf-8')):
        assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
    for path in (OUT/'models').glob('**/*metadata.json'):
        model=json.loads(path.read_text('utf-8'));cutoff=model.get('cutoff',model.get('fold',{}).get('train_end'))
        assert cutoff and model['maximum_label_available_at']<epoch(cutoff)
        assert model['formal_replacement'] is False
    c=duckdb.connect(config={'threads':1})
    assert c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/'prior_fastball_refs.parquet').as_posix()}') WHERE reference_closed_at>=entry_at").fetchone()[0]==0
    assert c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/'decision_states_*.parquet').as_posix()}') WHERE state_observed_at>=decision_at OR state_train_cutoff>state_observed_at").fetchone()[0]==0
    assert c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/'context_features_*.parquet').as_posix()}') WHERE context_train_cutoff>decision_at OR (research_home_we IS NOT NULL AND research_home_we NOT BETWEEN 0 AND 1)").fetchone()[0]==0


def test_downstream_features_keep_full_denominator_and_exclude_outcomes():
    c=duckdb.connect(config={'threads':1})
    for year in range(2021,2027):
        path=OUT/f'pitch_features_{year}.parquet'
        columns={r[0] for r in c.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()}
        assert not columns.intersection({'remaining_runs','runs_on_event','post_outs','post_base','closed_at','game_completed_at','home_win','raw_home_wpa'})
        assert 'source_batter_consistent' in columns
    assert c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/'context_features_*.parquet').as_posix()}')").fetchone()[0]==1099754
    assert c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/'candidate_state_priors_*.parquet').as_posix()}') WHERE prior_state_available_at>=cutoff_epoch OR greatest(prior_state_closed_at,prior_state_observed_at)>=cutoff_epoch OR prior_state_available_at<>greatest(prior_state_closed_at,prior_state_observed_at) OR individual_ranking_allowed").fetchone()[0]==0
    assert c.execute(f"SELECT count(*) FROM read_parquet('{(OUT/'decision_states_*.parquet').as_posix()}') WHERE (current_pitches>CASE WHEN state_role='SP' THEN 100 ELSE 60 END) AND (quality_plus IS NOT NULL OR physical_plus IS NOT NULL OR command_plus IS NOT NULL)").fetchone()[0]==0


def test_tracker_and_generated_decision_snapshot_preserve_utf8_chinese():
    root=ROOT.parent
    tracker=json.loads((root/'docs/PROJECT_TRACKER.json').read_text('utf-8'))
    project=next(p for p in tracker['projects'] if p['id']=='pitcher-decision-support')
    snapshot=json.loads((root/'frontend/data/pitcherDecisionPlan.json').read_text('utf-8'))
    assert snapshot['project']==project
    assert sum('\u4e00' <= char <= '\u9fff' for char in project['summary']) >= 20
    for obj in [project,snapshot]:
        text=json.dumps(obj,ensure_ascii=False)
        assert '???' not in text and '\ufffd' not in text
    document=(root/'docs/PITCHER_DECISION_SUPPORT.md').read_text('utf-8')
    assert '???' not in document and '核對' in document and '近 1／3／7／14 日' in document
