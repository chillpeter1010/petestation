"""Slice 5 nominal candidate sets, with explicit roster/operational uncertainty."""
from __future__ import annotations

import bisect
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, date
import gzip
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import requests

ROOT=Path(__file__).resolve().parents[2]/"data"
OUT=ROOT/"research/decision_support_pipeline_20261114"
NY=ZoneInfo('America/New_York')


def prior_load(times: list[float], cutoff: float, days: int) -> int:
    return bisect.bisect_left(times,cutoff)-bisect.bisect_left(times,cutoff-days*86400)


def candidate_streak(previous_day: str | None, prior_streak: int | None, today: date) -> int | None:
    if previous_day is None:return None
    gap=(today-date.fromisoformat(previous_day)).days
    if gap==1:return int(prior_streak or 0)+1
    if gap==0:return int(prior_streak or 0)
    return 0 if gap>1 else None


def nominal_eligibility(pid: int, current: int | None, used: set[int], removed: set[int], switches: set[int], allowed: bool) -> str:
    if pid==current:return "current_pitcher"
    if pid in removed:return "removed_from_game"
    if pid in switches:return "unsupported_position_switch"
    if pid in used:return "already_used"
    if not allowed:return "change_not_statutorily_supported"
    return "nominal_candidate_operational_status_unknown"


def fetch_probe(team: int, date: str, year: int, output: Path) -> dict:
    path=output/"dated_roster_probes"/f"{team}_{date}.json"
    if path.exists():return json.loads(path.read_text(encoding="utf-8"))
    url=f"https://statsapi.mlb.com/api/v1/teams/{team}/roster"
    try:
        r=requests.get(url,params={"rosterType":"active","date":date,"season":year},timeout=(5,12));r.raise_for_status()
        payload=r.json()
        roster=payload.get("roster")
        if not isinstance(roster,list) or not roster:raise ValueError("No historical active roster")
        raw=r.content
        record={"team_id":team,"date":date,"year":year,"url":r.url,"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
            "sha256":hashlib.sha256(raw).hexdigest(),"ids":sorted({int(v['person']['id']) for v in roster}),
            "status":"retrieved","authentication":"none; public GET"}
        path.parent.mkdir(parents=True,exist_ok=True)
        path.with_suffix('.raw.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    except (requests.RequestException,ValueError,KeyError) as exc:
        record={"team_id":team,"date":date,"year":year,"status":"unavailable","error":str(exc),"ids":[]}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return record


def build(output: Path=OUT, root: Path=ROOT, only_year: int | None=None) -> dict:
    c=duckdb.connect(':memory:',config={'threads':2,'memory_limit':'2GB'})
    print('candidates: load complete game rosters, never final used-pitcher lists',flush=True)
    c.execute(f"CREATE VIEW roster AS SELECT * FROM read_parquet('{(output/'roster_*.parquet').as_posix()}')")
    groups=c.execute("""SELECT year,game_pk,team_id,min(official_date) official_date,
        list(player_id ORDER BY player_id) FILTER(WHERE status_code='A') active_ids,
        list(player_id ORDER BY player_id) FILTER(WHERE status_code='A' AND position_code IN ('1','Y')) pitcher_ids
        FROM roster GROUP BY 1,2,3 ORDER BY year,official_date,game_pk,team_id""").fetchall()
    roster_map={(g[1],g[2]):{'year':g[0],'date':g[3],'active':set(g[4] or []),'pitchers':list(g[5] or [])} for g in groups}
    probes={}
    targets=[]
    for year in range(2021,2027):
        rows=[g for g in groups if g[0]==year]
        targets.extend(rows[round(i*(len(rows)-1)/11)] for i in range(12))
    print('candidates: cross-check 72 game-day memberships against explicit dated active rosters',flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(fetch_probe,int(g[2]),g[3],int(g[0]),output):g for g in targets}
        for i,future in enumerate(as_completed(pending),1):
            g=pending[future];p=future.result();match=p['status']=='retrieved' and set(p['ids'])==set(g[4] or [])
            probes[(g[1],g[2])]='dated_active_exact' if match else 'dated_roster_conflict' if p['status']=='retrieved' else 'dated_probe_unavailable'
            if i%12==0:print(f'candidates: dated roster probes {i}/72',flush=True)
    c.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{(output/'events_*.parquet').as_posix()}')")
    times=dict(c.execute("""SELECT pitcher_id,list(epoch(try_cast(event_time AS TIMESTAMPTZ)) ORDER BY try_cast(event_time AS TIMESTAMPTZ))
        FROM events WHERE is_pitch AND event_time IS NOT NULL AND pitcher_id IS NOT NULL GROUP BY pitcher_id""").fetchall())
    c.execute(f"CREATE VIEW history AS SELECT * FROM read_parquet('{(output/'closed_role_history.parquet').as_posix()}')")
    histories={}
    for pid, records in c.execute("""SELECT pitcher_id,list(struct_pack(closed:=epoch(closed_at),role:=role,starts:=prior_observed_starts,
        relief:=prior_observed_relief,previous_pitches:=pitches,session_day:=cast(session_day AS VARCHAR),streak:=consecutive_days_before,
        last_start:=epoch(last_observed_start),last_long:=epoch(last_observed_long_session)) ORDER BY closed_at) FROM history GROUP BY pitcher_id""").fetchall():
        histories[pid]=([v['closed'] for v in records],records)
    earliest=min(v[0] for v in times.values() if v)
    bad_clock={r[0] for r in c.execute(f"SELECT DISTINCT game_pk FROM read_parquet('{(output/'chronology_issues_*.parquet').as_posix()}')").fetchall()}
    confidence_counts=Counter()
    previous=json.loads((output/'slice5.json').read_text(encoding='utf-8')) if only_year and (output/'slice5.json').exists() else {}
    counts=[r for r in previous.get('years',[]) if r['year']!=only_year] if only_year else []
    total_leaks=0
    candidate_schema=pa.schema([
        ('year',pa.int64()),('game_pk',pa.int64()),('decision_id',pa.string()),('pitcher_id',pa.int64()),('team_id',pa.int64()),
        ('nominal_eligible',pa.bool_()),('reason',pa.string()),('roster_confidence',pa.string()),
        ('cutoff_epoch',pa.float64()),('last_pitch_epoch',pa.float64()),('history_closed_epoch',pa.float64()),
        *[(f'pitches_{d}d_before',pa.int64()) for d in [1,3,7,14]],
        ('prior_observed_starts',pa.int64()),('prior_observed_relief',pa.int64()),('previous_role',pa.string()),
        ('previous_session_pitches',pa.int64()),('consecutive_days_before',pa.int64()),('appeared_earlier_today',pa.bool_()),
        ('days_since_last_observed_start',pa.float64()),('days_since_last_long_session',pa.float64()),
        ('hours_since_last_pitch',pa.float64()),('lookback_14d_complete',pa.bool_()),
        ('warmup_available',pa.bool_()),('body_available',pa.bool_()),('individual_ranking_allowed',pa.bool_())])
    set_schema=pa.schema([('year',pa.int64()),('game_pk',pa.int64()),('decision_id',pa.string()),('team_id',pa.int64()),
        ('roster_confidence',pa.string()),('candidate_ids',pa.list_(pa.int64())),('candidate_count',pa.int64()),
        ('statutory_change_allowed',pa.bool_()),('continue_nominal_allowed',pa.bool_()),
        ('individual_ranking_allowed',pa.bool_()),('operational_availability',pa.string())])
    for year in range(2021,2027):
        if only_year is not None and year!=only_year:continue
        writer=pq.ParquetWriter(output/f'bullpen_candidates_{year}.parquet',candidate_schema,compression='zstd')
        sw=pq.ParquetWriter(output/f'bullpen_sets_{year}.parquet',set_schema,compression='zstd')
        tally=Counter();source=pq.ParquetFile(output/f'decisions_{year}.parquet')
        for batch in source.iter_batches(batch_size=1500):
            candidates=[];sets=[]
            for d in batch.to_pylist():
                ro=roster_map.get((d['game_pk'],d['team_id']))
                confidence=probes.get((d['game_pk'],d['team_id']),'official_game_roster_date_unverified')
                if ro is None or not 20<=len(ro['active'])<=30:confidence='insufficient_roster'
                if ro and d['outgoing_pitcher_id'] not in ro['active']:confidence='current_pitcher_roster_conflict'
                confidence_counts[confidence]+=1
                t=datetime.fromisoformat(d['decision_time']).timestamp() if d['decision_time'] else None
                today=datetime.fromtimestamp(t,timezone.utc).astimezone(NY).date() if t is not None else None
                allowed=d['statutory_status']=='allowed' and not d['is_initial_start'] and d['completed_batter_play']
                valid=ro is not None and confidence not in {'insufficient_roster','dated_roster_conflict','current_pitcher_roster_conflict'} and t is not None
                constraint_status='source_clock_uncertain' if d['game_pk'] in bad_clock or d['time_basis']=='play_start_fallback' else 'unknown_base_state' if not d['base_state_known'] else None
                if constraint_status:valid=False
                used=set(json.loads(d['used_pitcher_ids']));removed=set(json.loads(d['removed_player_ids']));switches=set(json.loads(d['unsupported_switch_ids']))
                eligible=[]
                for pid in (ro['pitchers'] if ro and not d['is_initial_start'] and d['completed_batter_play'] else []):
                    reason=nominal_eligibility(pid,d['outgoing_pitcher_id'],used,removed,switches,allowed)
                    ok=valid and reason=='nominal_candidate_operational_status_unknown'
                    if ok:eligible.append(pid)
                    history=histories.get(pid,([],[]));hi=bisect.bisect_left(history[0],t)-1 if t is not None else -1
                    past=history[1][hi] if hi>=0 else {}
                    pt=times.get(pid,[]);pi=bisect.bisect_left(pt,t)-1 if t is not None else -1
                    last=pt[pi] if pi>=0 else None
                    if last is not None and last>=t:total_leaks+=1
                    if past and past['closed']>=t:total_leaks+=1
                    candidates.append({'year':year,'game_pk':d['game_pk'],'decision_id':d['decision_id'],'pitcher_id':pid,'team_id':d['team_id'],
                        'nominal_eligible':ok,'reason':reason if valid else constraint_status or confidence,'roster_confidence':confidence,
                        'cutoff_epoch':t,'last_pitch_epoch':last,'history_closed_epoch':past.get('closed'),
                        **{f'pitches_{n}d_before':prior_load(pt,t,n) if t is not None else None for n in [1,3,7,14]},
                        'prior_observed_starts':past.get('starts'),'prior_observed_relief':past.get('relief'),'previous_role':past.get('role'),
                        'previous_session_pitches':past.get('previous_pitches'),
                        'consecutive_days_before':candidate_streak(past.get('session_day'),past.get('streak'),today) if today else None,
                        'appeared_earlier_today':past.get('session_day')==today.isoformat() if today and past else None,
                        'days_since_last_observed_start':(t-past['last_start'])/86400 if t is not None and past.get('last_start') is not None else None,
                        'days_since_last_long_session':(t-past['last_long'])/86400 if t is not None and past.get('last_long') is not None else None,
                        'hours_since_last_pitch':(t-last)/3600 if last is not None else None,'lookback_14d_complete':t is not None and t>=earliest+14*86400,
                        'warmup_available':None,'body_available':None,'individual_ranking_allowed':False})
                sets.append({'year':year,'game_pk':d['game_pk'],'decision_id':d['decision_id'],'team_id':d['team_id'],
                    'roster_confidence':confidence,'candidate_ids':eligible,'candidate_count':len(eligible),
                    'statutory_change_allowed':allowed,'continue_nominal_allowed':not d['mandatory_removed_pitcher'],
                    'individual_ranking_allowed':False,'operational_availability':'unknown_warmup_health_intraday_changes'})
                tally['decisions']+=1;tally['with_nominal_candidates']+=bool(eligible);tally['nominal_candidate_rows']+=len(eligible)
                tally['low_confidence_boundaries']+=not valid
            writer.write_table(pa.Table.from_pylist(candidates,schema=candidate_schema));sw.write_table(pa.Table.from_pylist(sets,schema=set_schema))
            tally['candidate_profiles']+=len(candidates)
            if tally['decisions']%15000==0:print(f"candidates {year}: {tally['decisions']} boundaries",flush=True)
        writer.close();sw.close();counts.append({'year':year,**dict(tally)})
        print(f'candidates: saved {year}',flush=True)
    assert total_leaks==0
    confidence_counts=dict(c.execute(f"SELECT roster_confidence,count(*) FROM read_parquet('{(output/'bullpen_sets_202[1-6].parquet').as_posix()}') GROUP BY roster_confidence").fetchall())
    report={'slice':5,'years':sorted(counts,key=lambda r:r['year']),'strict_time_violations':total_leaks,'dated_roster_probe_games':len(probes),
        'probe_results':dict(Counter(probes.values())),
        'roster_confidence_boundaries':confidence_counts,
        'roster_basis':'Full official game-day player roster, not final used-pitcher list; 72 explicit-date API cross-checks, not all-date certification.',
        'operational_status':'Warm-up, medical clearance, suspension and exact intraday transaction timing unknown; all individual ranking gates CLOSED.',
        'eligibility':'Nominal position P or two-way Y; exclude current, removed, previously used and unsupported position-switch players; statutory three-batter gate.',
        'limitations':['Unverified dates remain medium-confidence game-roster observations; future game usage does not define the pool.',
            'Active starters can be nominal legal relievers; role/workload is a feature, not automatic available readiness.',
            'Candidate workload uses strict timestamps across all teams/roles; historical starter counts begin in 2021.']}
    (output/'slice5.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True);return report


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');parser=argparse.ArgumentParser();parser.add_argument('--year',type=int,choices=range(2021,2027));args=parser.parse_args();build(only_year=args.year)
