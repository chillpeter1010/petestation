"""Versioned Slice14 evidence and bounded WE traces; no runtime API or browser work."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_action_values as a

b=a.b
EXTERNAL=Path('C:/intern/data_fixed/wpa_fixed__peter_0821')


def trace_points(frame: pd.DataFrame, bundle: dict) -> list[dict]:
    """Before/after points share the frozen WE basis; missing states stay gaps."""
    initial=pd.DataFrame({'inning':frame.inning,'bottom':frame.half.eq('bottom').astype(int),
        'scheduled_innings':frame.scheduled_innings,'score_diff':frame.home_score-frame.away_score,
        'outs':frame.outs,'base_state':frame.base_state,'balls':frame.balls,'strikes':frame.strikes})
    valid=initial.notna().all(axis=1)&initial.outs.between(0,2)&initial.base_state.between(0,7)
    before=np.full(len(frame),np.nan);after=np.full(len(frame),np.nan)
    if valid.any():before[valid.to_numpy(dtype=bool)]=b.we_predict(bundle,initial.loc[valid])
    runs=np.where(frame.half.eq('top'),frame.away_score_after-frame.away_score,frame.home_score_after-frame.home_score)
    valid_after=(valid&frame.is_complete&frame.outs_after.between(0,3)&frame.base_state_after.between(0,7)&(runs>=0)).fillna(False)
    chosen=np.flatnonzero(valid_after)
    if len(chosen):
        post,terminal=b.post_state(initial.iloc[chosen],runs[chosen],frame.outs_after.to_numpy()[chosen],frame.base_state_after.to_numpy()[chosen])
        predicted=b.we_predict(bundle,post);known=np.isfinite(terminal);predicted[known]=terminal[known]
        after[chosen]=predicted
    points=[]
    for i,row in enumerate(frame.itertuples()):
        fraction=(row.event_index+1)/(row.last_event_index+2)
        common={'decisionId':row.decision_id,'atBat':int(row.at_bat_number),'inning':int(row.inning),'half':row.half,
            'batterId':int(row.batter_id) if pd.notna(row.batter_id) else None,'event':row.event_type,
            'description':row.description,'homeWpa':float(after[i]-before[i]) if np.isfinite(after[i]) and np.isfinite(before[i]) else None}
        for phase,x,we,outs,bases,home,away,pitcher in [
            ('before',i+fraction,before[i],row.outs,row.base_state,row.home_score,row.away_score,row.outgoing_pitcher_id),
            ('after',i+1.,after[i],row.outs_after,row.base_state_after,row.home_score_after,row.away_score_after,row.terminal_pitcher_id)]:
            points.append({**common,'phase':phase,'x':float(x),'homeWe':float(we) if np.isfinite(we) else None,
                'outs':int(outs) if pd.notna(outs) else None,'bases':int(bases) if pd.notna(bases) else None,
                'homeScore':int(home),'awayScore':int(away),'pitcherId':int(pitcher) if pd.notna(pitcher) else None})
    return points


def traces() -> None:
    preparation=json.loads((a.OUT/'preparation.json').read_text('utf-8'))
    bundle=joblib.load(b.TEMPORAL/'models/frozen_2024/context.joblib')
    games=[];sources=[]
    with b.connection() as c,threadpool_limits(limits=2):
        base=b.ROOT/'data/research/decision_support_pipeline_20261114'
        for name in ('decisions','plays','events'):
            c.read_parquet(str(base/f'{name}_2024.parquet')).create_view(name)
        c.read_parquet(str(b.ROOT/'data/research/decision_support_slice1_20261112/feed_inventory_2024.parquet')).create_view('inventory')
        for game_pk in preparation['trace_games']:
            meta=c.execute('SELECT path,compressed_sha256 FROM inventory WHERE game_pk=?',[game_pk]).fetchone()
            path=Path(meta[0]);assert b.digest(path)==meta[1]
            payload=json.loads(gzip.decompress(path.read_bytes()))
            names={int(pid.removeprefix('ID')):p.get('fullName',str(pid)) for pid,p in payload['gameData']['players'].items()}
            descriptions={int(p['about']['atBatIndex'])+1:p.get('result',{}).get('description','') for p in payload['liveData']['plays']['allPlays']}
            frame=c.execute('''SELECT d.*,p.scheduled_innings,p.outs_after,p.base_state_after,p.home_score_after,
                p.away_score_after,p.terminal_pitcher_id,p.is_complete,p.event_type,e.last_event_index
                FROM decisions d JOIN plays p USING(outcome_key)
                JOIN (SELECT game_pk,at_bat_number,max(event_index) last_event_index FROM events GROUP BY ALL) e ON e.game_pk=d.game_pk AND e.at_bat_number=d.at_bat_number
                WHERE d.game_pk=? AND d.decision_id LIKE '%:boundary' ORDER BY d.at_bat_number''',[game_pk]).fetchdf()
            frame['description']=frame.at_bat_number.map(descriptions).fillna('')
            frame.loc[frame.outs_after.ge(3),'base_state_after']=0
            points=trace_points(frame,bundle)
            mapping={int(row.at_bat_number):(i,int(row.last_event_index)) for i,row in enumerate(frame.itertuples())}
            changes=c.execute('''SELECT event_id,event_time,at_bat_number,event_index,pitcher_id,previous_pitcher_id,description
                FROM events WHERE game_pk=? AND is_pitch_change ORDER BY at_bat_number,event_index''',[game_pk]).fetchdf()
            actual=[]
            for row in changes.itertuples():
                if int(row.at_bat_number) not in mapping:continue
                ordinal,last=mapping[int(row.at_bat_number)]
                actual.append({'eventId':row.event_id,'at':row.event_time,'x':ordinal+(row.event_index+1)/(last+2),
                    'incomingId':int(row.pitcher_id),'outgoingId':int(row.previous_pitcher_id) if pd.notna(row.previous_pitcher_id) else None,
                    'description':row.description})
            for point in points:
                point['pitcherName']=names.get(point['pitcherId'],str(point['pitcherId']))
                point['batterName']=names.get(point['batterId'],str(point['batterId']))
            teams=payload['gameData']['teams']
            games.append({'gamePk':int(game_pk),'year':2024,'date':payload['gameData']['datetime']['officialDate'],
                'home':teams['home']['name'],'away':teams['away']['name'],'points':points,'actualChanges':actual,
                'playerNames':names,'reference':'frozen_2024 neutral WE before/after official plays; gaps preserved',
                'xSemantics':'official PA/event order; before decision and after play are distinct anchors; not elapsed time'})
            sources.append({'game_pk':game_pk,'path':str(path),'sha256':meta[1]})
    external=[]
    for relative in ['HANDOFF_README.md','stats-master/frontend/src/components/GameWinProbabilityChart.tsx','stats-master/backend/app/services/wpa_service.py']:
        path=EXTERNAL/relative
        external.append({'path':str(path),'sha256':b.digest(path)})
    b.save_json(a.OUT/'traces.json',{'games':games,'sources':sources,'reference_project':external,
        'adaptation':'50% center line, home/away WE and PA drilldown structure; use bounded straight segments, separate before-decision research and actual-substitution rails; no CPBL WE table reuse',
        'future_in_game':'game_pk/year + pitcher_id + PA/event ID; exact pitch_uid requires official-to-Statcast validated alignment; no fabricated pitch_number=eventIndex join'})
    print('Two WPA/WE research timelines exported from existing official snapshots',flush=True)


def finalize() -> None:
    report=json.loads((a.OUT/'summary.json').read_text('utf-8'))
    trace=json.loads((a.OUT/'traces.json').read_text('utf-8'))
    values=pd.read_parquet(a.OUT/'action_values_2024.parquet')
    cases=pd.read_parquet(a.OUT/'supported_cases.parquet')
    rows=cases[['decision_id','game_pk','inning','half','role','outgoing_pitcher_id','observed_action','research_pa_li']].merge(values,on='decision_id',validate='one_to_one')
    examples=json.loads(rows.sort_values('decision_id').head(24).to_json(orient='records'))
    for game in trace['games']:
        game['researchPoints']=json.loads(rows[rows.game_pk.eq(game['gamePk'])].to_json(orient='records'))
    report.update({'bootstrap':json.loads((a.OUT/'bootstrap.json').read_text('utf-8')),
        'protocol':json.loads((a.OUT/'protocol.json').read_text('utf-8')),'examples':examples,'timeline':trace,
        'exporter_sha256':b.digest(Path(__file__))})
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice14_v1.json',report)
    paths=[p for p in a.OUT.iterdir() if p.is_file() and p.name!='manifest.json']
    b.save_json(a.OUT/'manifest.json',{'version':'decision_action_values_v1',
        'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':b.digest(p)} for p in sorted(paths)]})
    print(f'Slice14 evidence: {len(paths)} artifact hashes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['traces','finalize'])
    stage=parser.parse_args().stage;globals()[stage]()
