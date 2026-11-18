"""Slice 4: event-time, strictly prior regular-season workload across teams/roles."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
import sys

import duckdb
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]/"data"
OUT=ROOT/"research/decision_support_pipeline_20261114"


def streak_before(day: date, observed_days: set[date]) -> int:
    count=0
    previous=day-timedelta(days=1)
    while previous in observed_days:
        count+=1;previous-=timedelta(days=1)
    return count


def build(output: Path=OUT) -> dict:
    c=duckdb.connect(":memory:",config={"threads":2,"memory_limit":"2GB"})
    c.execute(f"SET temp_directory='{(output/'duckdb_workload_tmp').as_posix()}'")
    print("workload: load chronological physical pitches and decisions",flush=True)
    c.execute(f"""CREATE TABLE pitch AS SELECT year,game_pk,pitcher_id,team_id,appearance_id,
        try_cast(event_time AS TIMESTAMPTZ) t FROM read_parquet('{(output/'events_*.parquet').as_posix()}')
        WHERE is_pitch AND pitcher_id IS NOT NULL AND event_time IS NOT NULL""")
    c.execute(f"CREATE VIEW apps AS SELECT * FROM read_parquet('{(output/'appearances_*.parquet').as_posix()}')")
    c.execute("""CREATE TABLE sessions AS WITH lagged AS (
        SELECT *,lag(t) OVER(PARTITION BY appearance_id ORDER BY t) prior_t FROM pitch),
        blocks AS (SELECT *,sum(CASE WHEN prior_t IS NULL OR t-prior_t>INTERVAL '8 hours' THEN 1 ELSE 0 END)
            OVER(PARTITION BY appearance_id ORDER BY t) session_no FROM lagged)
        SELECT appearance_id,session_no,any_value(year) AS year,any_value(game_pk) game_pk,
            any_value(pitcher_id) pitcher_id,any_value(team_id) team_id,min(t) session_start,max(t) session_end,
            count(*) pitches FROM blocks GROUP BY appearance_id,session_no""")
    c.execute("""CREATE TABLE session_history AS SELECT s.*,a.role,
        least(coalesce(try_cast(a.exit_time AS TIMESTAMPTZ),s.session_end+INTERVAL '8 hours'),s.session_end+INTERVAL '8 hours') closed_at,
        cast(s.session_start AT TIME ZONE 'America/New_York' AS DATE) session_day,
        s.session_no>1 is_resumed_session
        FROM sessions s JOIN apps a USING(appearance_id)""")
    frame=c.execute("SELECT * FROM session_history ORDER BY pitcher_id,session_start,game_pk,session_no").fetchdf()
    days=defaultdict(set)
    streaks=[]
    for row in frame.itertuples():
        day=row.session_day.date()
        streaks.append({"appearance_id":row.appearance_id,"session_no":row.session_no,
            "consecutive_days_before":streak_before(day,days[row.pitcher_id]),
            "appeared_earlier_today":day in days[row.pitcher_id]})
        days[row.pitcher_id].add(day)
    c.register("streaks",pd.DataFrame(streaks))
    c.execute("CREATE TABLE session_with_streak AS SELECT * FROM session_history JOIN streaks USING(appearance_id,session_no)")
    c.execute(f"COPY session_with_streak TO '{(output/'workload_sessions.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    # History becomes available only after the appearance was observed to end.
    c.execute("""CREATE TABLE closed_history AS SELECT *,
        sum(CASE WHEN role='SP' AND session_no=1 THEN 1 ELSE 0 END) OVER w prior_observed_starts,
        sum(CASE WHEN role='RP' AND session_no=1 THEN 1 ELSE 0 END) OVER w prior_observed_relief,
        max(CASE WHEN role='SP' AND session_no=1 THEN session_start END) OVER w last_observed_start,
        max(CASE WHEN pitches>=60 THEN session_end END) OVER w last_observed_long_session
        FROM session_with_streak WINDOW w AS(PARTITION BY pitcher_id ORDER BY closed_at ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)""")
    c.execute(f"COPY closed_history TO '{(output/'closed_role_history.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    print("workload: calculate 24/72/168/336-hour strictly prior windows",flush=True)
    c.execute(f"""CREATE TABLE decisions AS SELECT *,try_cast(decision_time AS TIMESTAMPTZ) t
        FROM read_parquet('{(output/'decisions_*.parquet').as_posix()}')""")
    c.execute(f"CREATE VIEW bad_clock AS SELECT DISTINCT game_pk FROM read_parquet('{(output/'chronology_issues_*.parquet').as_posix()}')")
    c.execute("""CREATE TABLE timeline AS
        SELECT pitcher_id,t,1 amount,NULL::VARCHAR decision_id FROM pitch
        UNION ALL SELECT outgoing_pitcher_id,t,0 amount,decision_id FROM decisions
        WHERE outgoing_pitcher_id IS NOT NULL AND t IS NOT NULL""")
    windows=",".join(f"coalesce(sum(amount) OVER(PARTITION BY pitcher_id ORDER BY t RANGE BETWEEN INTERVAL '{n} days' PRECEDING AND INTERVAL '1 microsecond' PRECEDING),0) pitches_{n}d_before" for n in [1,3,7,14])
    c.execute(f"""CREATE TABLE rolling AS SELECT *,{windows},
        max(CASE WHEN amount=1 THEN t END) OVER(PARTITION BY pitcher_id ORDER BY t RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL '1 microsecond' PRECEDING) last_pitch_before
        FROM timeline""")
    earliest=c.execute("SELECT min(epoch(t)) FROM pitch").fetchone()[0]
    print("workload: attach prior closed role history; never read a current appearance's final count",flush=True)
    c.execute("""CREATE TABLE features AS SELECT d.year,d.game_pk,d.decision_id,d.appearance_id,d.outgoing_pitcher_id pitcher_id,d.team_id,
        d.t decision_time,d.current_pitches current_game_pitches,
        r.pitches_1d_before,r.pitches_3d_before,r.pitches_7d_before,r.pitches_14d_before,r.last_pitch_before,
        h.closed_at history_closed_at,h.role previous_role,h.pitches previous_session_pitches,h.session_end previous_session_end,
        h.prior_observed_starts,h.prior_observed_relief,h.last_observed_start,h.last_observed_long_session,
        extract(epoch FROM (d.t-h.session_end))/3600 rest_hours_since_closed_session,
        h.consecutive_days_before prior_session_consecutive_days,
        cur.consecutive_days_before current_session_consecutive_days,cur.appeared_earlier_today,
        cur.session_start current_session_start,
        'MLB_regular_season_only' history_scope,
        d.game_pk NOT IN(SELECT game_pk FROM bad_clock) AND d.time_basis<>'play_start_fallback' source_clock_valid,
        CASE WHEN d.t IS NULL THEN 'missing_time' WHEN d.game_pk IN(SELECT game_pk FROM bad_clock) OR d.time_basis='play_start_fallback' THEN 'uncertain_source_clock' ELSE 'strictly_prior_event_time' END history_status
        FROM decisions d LEFT JOIN rolling r USING(decision_id)
        ASOF LEFT JOIN closed_history h ON d.outgoing_pitcher_id=h.pitcher_id AND d.t>h.closed_at
        ASOF LEFT JOIN session_with_streak cur ON d.appearance_id=cur.appearance_id AND d.t>=cur.session_start""")
    c.execute("ALTER TABLE features ADD COLUMN lookback_14d_complete BOOLEAN")
    c.execute("UPDATE features SET lookback_14d_complete=decision_time>=to_timestamp(?) + INTERVAL '14 days'",[earliest])
    counts=[]
    for year in range(2021,2027):
        c.execute(f"COPY (SELECT * FROM features WHERE year={year}) TO '{(output/f'workload_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        counts.append(dict(zip(["year","decisions","missing_time","missing_prior_role","left_censored_14d"],c.execute(f"SELECT {year},count(*),count(*) FILTER(WHERE decision_time IS NULL),count(*) FILTER(WHERE history_closed_at IS NULL),count(*) FILTER(WHERE NOT coalesce(lookback_14d_complete,false)) FROM features WHERE year={year}").fetchone())))
        print(f"workload: saved {year}",flush=True)
    leaks=c.execute("SELECT count(*) FROM features WHERE last_pitch_before>=decision_time OR history_closed_at>=decision_time").fetchone()[0]
    duplicates=c.execute("SELECT count(*)-count(DISTINCT decision_id) FROM features").fetchone()[0]
    assert leaks==duplicates==0
    report={"slice":4,"years":counts,"sessions":len(frame),"strict_time_violations":leaks,"duplicate_decisions":duplicates,
        "source_clock_issue_games":c.execute("SELECT count(*) FROM bad_clock").fetchone()[0],
        "scope":"All teams and SP/RP roles by MLBAM ID; regular-season physical pitches only; 1/3/7/14 rolling days, strict t'<t.",
        "same_day_order":"UTC event time, with New York calendar dates for consecutive-day flags; no game-ID ordering.",
        "resumed_games":"Physical sessions split after >8h gap; closed history waits for observed exit or 8h inactivity.",
        "limitations":["Spring training, minor-league pitches, warm-up, health and pre-2021 role history are unknown.","A former starter is historical context, not automatic readiness credit.","Missing-time and early-source lookback rows retain explicit flags."]}
    (output/'slice4.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
    return report


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');build()
