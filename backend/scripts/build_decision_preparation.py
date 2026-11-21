"""Build versioned Decision Support Slices 12.1–12.4 from frozen local inputs."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

import duckdb
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.decision_temporal_common import FOLDS
from scripts.build_decision_temporal_context import post_state, we_predict

DATA = ROOT / "data"
BASE = DATA / "research/decision_support_pipeline_20261114"
TEMPORAL = DATA / "research/decision_support_temporal_20261114"
SAMPLE = DATA / "research/pitcher_decision_sample_v1"
OUT = DATA / "research/decision_preparation_v1"
YEARS = range(2021, 2027)
OUTCOMES = ("k", "bb", "hbp", "hr", "single", "double", "triple", "other_out", "other_reach")


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp.json")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def publish(conn: duckdb.DuckDBPyConnection, table: str, year: int) -> None:
    path = OUT / f"{table}_{year}.parquet"
    temp = path.with_suffix(".tmp.parquet")
    conn.table(table).write_parquet(str(temp), compression="zstd")
    temp.replace(path)


def records(conn: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    result = conn.execute(sql)
    names = [col[0] for col in result.description]
    return [dict(zip(names, row, strict=True)) for row in result.fetchall()]


def connect(year: int) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(config={"threads": 2, "memory_limit": "2GB"})
    for folder, names in (
        (BASE, ("plays", "events", "decisions", "appearances", "roster")),
        (SAMPLE, ("decision_features", "decision_labels", "decision_candidates", "decision_audit")),
        (TEMPORAL, ("decision_states", "context_features", "pitch_features", "batter_identity_disagreements")),
    ):
        for name in names:
            conn.read_parquet(str(folder / f"{name}_{year}.parquet")).create_view(name)
    return conn


def source_hands(year: int) -> None:
    """Keep only listed handedness and play matchup, with immutable feed provenance."""
    with duckdb.connect() as conn:
        inventory = conn.read_parquet(str(DATA / f"research/decision_support_slice1_20261112/feed_inventory_{year}.parquet")).fetchdf()
    people, matchups = [], []
    for index, entry in enumerate(inventory.itertuples(index=False), 1):
        path = Path(entry.path)
        if not path.exists():
            path = DATA / f"research/catcher_descriptive/slice1/raw_game_feeds/{year}/{entry.game_pk}.json.gz"
        packed = path.read_bytes()
        if hashlib.sha256(packed).hexdigest() != entry.compressed_sha256:
            raise ValueError(f"Official snapshot drift: {entry.game_pk}")
        payload = json.loads(gzip.decompress(packed))
        for person in payload["gameData"]["players"].values():
            people.append({"game_pk": int(entry.game_pk), "player_id": int(person["id"]),
                           "listed_bats": person.get("batSide", {}).get("code"),
                           "listed_throws": person.get("pitchHand", {}).get("code")})
        for play in payload["liveData"]["plays"]["allPlays"]:
            matchup = play.get("matchup", {})
            matchups.append({"game_pk": int(entry.game_pk), "at_bat_number": int(play["atBatIndex"]) + 1,
                             "source_batter_id": matchup.get("batter", {}).get("id"),
                             "source_pitcher_id": matchup.get("pitcher", {}).get("id"),
                             "actual_stand": matchup.get("batSide", {}).get("code"),
                             "actual_pitch_hand": matchup.get("pitchHand", {}).get("code")})
        if index % 200 == 0 or index == len(inventory):
            print(f"{year}: handedness source {index}/{len(inventory)}", flush=True)
    with duckdb.connect() as conn:
        conn.register("people", pd.DataFrame(people).drop_duplicates(["game_pk", "player_id"]))
        conn.register("matchups", pd.DataFrame(matchups))
        conn.execute("CREATE TABLE listed_hands AS SELECT * FROM people")
        conn.execute("CREATE TABLE play_hands AS SELECT * FROM matchups")
        for name in ("listed_hands", "play_hands"):
            publish(conn, name, year)
    save_json(OUT / f"source_{year}.json", {"year": year, "games": len(inventory), "sha_verified": len(inventory),
              "source": "existing official game snapshots; only handedness attributes selected",
              "limitations": "gameData player attributes can be revised by the source; no claim of transaction-time roster or immutable historical bio"})


def backfill_probe() -> None:
    """Bound the optional pre-2021 backfill with two small public source probes."""
    import requests
    report = {"local_2020_db": (DATA / "MLB2020/mlb_2020.duckdb").exists(), "probes": []}
    url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2020&gameType=R"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        games = [game for day in response.json().get("dates", []) for game in day.get("games", [])
                 if game.get("status", {}).get("detailedState") in {"Final", "Completed Early"}]
        schedule_rows = len(games)
        games = list({game["gamePk"]: game for game in games}.values())
        report["probes"].append({"url": url, "http": response.status_code, "bytes": len(response.content),
                                 "sha256": hashlib.sha256(response.content).hexdigest(),
                                 "completed_schedule_rows": schedule_rows, "completed_regular_games": len(games)})
        if games:
            url = f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_pk={games[0]['gamePk']}"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
            valid = bool(rows and "game_pk" in rows[0] and "release_speed" in rows[0])
            report["probes"].append({"url": url, "http": response.status_code, "bytes": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(), "csv_contract_valid": valid,
                "sample_rows": len(rows), "scope": "one 2020 game only; season coverage not certified"})
    except (requests.RequestException, ValueError) as error:
        report["probe_error"] = type(error).__name__ + ": " + str(error)
    report["retrieved_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    save_json(OUT / "backfill_probe.json", report)
    print("Saved optional 2020 source probe", flush=True)


def clean_labels(year: int) -> None:
    with connect(year) as conn:
        conn.execute("""
            CREATE TABLE boundary_review AS
            WITH ordered AS (
                SELECT *, lag(home_score_after) OVER w AS previous_home,
                    lag(away_score_after) OVER w AS previous_away
                FROM events WINDOW w AS (PARTITION BY game_pk,at_bat_number ORDER BY event_index)
            ), preludes AS (
                SELECT d.decision_id,
                    coalesce(bool_or(e.event_type='runner_placed'), false) AS has_runner_placement,
                    count(e.event_id) AS prelude_events,
                    string_agg(e.event_type, ',' ORDER BY e.event_index) AS prelude_types
                FROM decision_features f JOIN decisions d USING(decision_id)
                LEFT JOIN events e ON e.game_pk=d.game_pk AND e.at_bat_number=d.at_bat_number AND e.event_index<d.event_index
                GROUP BY d.decision_id
            )
            SELECT f.year,f.game_pk,f.decision_id,d.outcome_key,
                p.outs_before AS original_outs,p.base_state_before AS original_bases,
                p.home_score_before AS original_home,p.away_score_before AS original_away,
                d.outs AS decision_outs,d.base_state AS decision_bases,d.home_score AS decision_home,d.away_score AS decision_away,
                d.outs IS DISTINCT FROM p.outs_before OR d.base_state IS DISTINCT FROM p.base_state_before
                    OR d.home_score IS DISTINCT FROM p.home_score_before OR d.away_score IS DISTINCT FROM p.away_score_before AS changed_start,
                coalesce(e.outs_before=d.outs AND e.base_state_before=d.base_state
                    AND coalesce(e.previous_home,p.home_score_before)=d.home_score
                    AND coalesce(e.previous_away,p.away_score_before)=d.away_score, false) AS verified_event_start,
                pr.has_runner_placement, pr.prelude_events, pr.prelude_types,
                p.zero_pitch, p.event_type='intent_walk' AS intentional_walk,
                CASE WHEN d.outs IS NOT DISTINCT FROM p.outs_before AND d.base_state IS NOT DISTINCT FROM p.base_state_before
                        AND d.home_score IS NOT DISTINCT FROM p.home_score_before AND d.away_score IS NOT DISTINCT FROM p.away_score_before
                    THEN 'unchanged_start'
                    WHEN pr.has_runner_placement THEN 'predecision_runner_placement'
                    WHEN pr.prelude_events>0 THEN 'predecision_runner_event'
                    ELSE 'unresolved_start_difference' END AS review_reason
            FROM decision_features f JOIN decisions d USING(decision_id)
            JOIN plays p ON p.outcome_key=d.outcome_key
            LEFT JOIN ordered e ON e.game_pk=d.game_pk AND e.at_bat_number=d.at_bat_number AND e.event_index=d.event_index
            JOIN preludes pr USING(decision_id)
        """)
        conn.execute("""
            CREATE TABLE clean_labels AS
            WITH endings AS (
                SELECT *, max(at_bat_number) OVER (PARTITION BY game_pk) AS game_last_ab,
                    arg_max(home_score_after,at_bat_number) OVER (PARTITION BY game_pk) AS final_home,
                    arg_max(away_score_after,at_bat_number) OVER (PARTITION BY game_pk) AS final_away
                FROM plays
            ), half_end AS (
                SELECT * FROM endings QUALIFY row_number() OVER(PARTITION BY game_pk,inning,half ORDER BY at_bat_number DESC)=1
            ), raw AS (
                SELECT f.year,f.game_pk,f.decision_id,d.outcome_key,f.role,l.observed_action,l.incoming_pitcher_id,
                    p.event_type AS observed_pa_result, r.review_reason, r.changed_start, r.intentional_walk,r.zero_pitch,
                    f.decision_at, f.inning,f.half,p.scheduled_innings,d.home_score-d.away_score AS score_diff,
                    f.outs,f.base_state,p.outs_after,p.base_state_after,
                    CASE WHEN f.half='top' THEN p.away_score_after-d.away_score ELSE p.home_score_after-d.home_score END AS runs_to_pa_end,
                    epoch(try_cast(p.end_time AS TIMESTAMPTZ)) AS pa_end_at,
                    epoch(try_cast(h.end_time AS TIMESTAMPTZ)) AS half_end_at,
                    h.outs_after AS half_end_outs,h.base_state_after AS half_end_bases,
                    CASE WHEN f.half='top' THEN h.away_score_after-d.away_score ELSE h.home_score_after-d.home_score END AS runs_to_half_end,
                    h.home_score_after-h.away_score_after AS half_end_score_diff,
                    h.is_complete AND (h.outs_after=3 OR (
                        h.at_bat_number=h.game_last_ab AND h.inning>=h.scheduled_innings
                        AND h.half='bottom' AND h.final_home>h.final_away)) AS half_is_complete,
                    r.verified_event_start AND p.is_complete AND NOT p.mid_pa_change AND NOT p.runner_index_missing
                        AND p.outs_after BETWEEN f.outs AND 3 AND p.base_state_after BETWEEN 0 AND 7 AS source_valid,
                    l.next_pa_defense_wpa AS original_pa_wpa,l.next_pa_source_defense_re24 AS original_pa_source_re24,
                    l.half_defense_wpa AS original_half_wpa,
                    cf.research_home_we,cf.research_re,cf.context_model_id
                FROM decision_features f JOIN decisions d USING(decision_id)
                JOIN boundary_review r USING(decision_id) JOIN decision_labels l USING(decision_id)
                JOIN plays p ON p.outcome_key=d.outcome_key
                JOIN half_end h ON h.game_pk=d.game_pk AND h.inning=d.inning AND h.half=d.half
                LEFT JOIN context_features cf USING(decision_id)
            )
            SELECT *, coalesce(source_valid AND runs_to_pa_end BETWEEN 0 AND 4 AND pa_end_at>=decision_at, false) AS transition_valid,
                coalesce(source_valid AND half_is_complete AND runs_to_half_end>=0
                    AND half_end_at>=pa_end_at AND pa_end_at>=decision_at,false) AS half_valid,
                coalesce(source_valid AND NOT intentional_walk AND runs_to_pa_end BETWEEN 0 AND 4
                    AND pa_end_at>=decision_at,false) AS organic_pa_eligible,
                CASE WHEN NOT changed_start THEN original_pa_wpa END AS comparable_source_pa_wpa,
                CASE WHEN NOT changed_start THEN original_pa_source_re24 END AS comparable_source_pa_re24
            FROM raw
        """)
        labels = conn.table("clean_labels").fetchdf()
        labels["research_pa_wpa"] = np.nan
        labels["research_pa_re24"] = np.nan
        labels["research_half_wpa"] = np.nan
        labels["research_half_re24"] = np.nan
        for model_id, indices in labels.groupby("context_model_id").groups.items():
            fold = model_id.rsplit(":", 1)[1]
            bundle = joblib.load(TEMPORAL / "models" / fold / "context.joblib")
            for scope in ("pa", "half"):
                selected = labels.loc[indices]
                flag = "transition_valid" if scope == "pa" else "half_valid"
                selected = selected[selected[flag] & selected.research_home_we.notna() & selected.research_re.notna()]
                if selected.empty:
                    continue
                x = selected.rename(columns={"base_state": "bases"}).copy()
                x["base_state"] = x["bases"]
                x["bottom"] = x.half.eq("bottom").astype(int)
                x["balls"] = x["strikes"] = 0
                runs = selected["runs_to_pa_end" if scope == "pa" else "runs_to_half_end"].to_numpy()
                outs = selected["outs_after" if scope == "pa" else "half_end_outs"].to_numpy()
                bases = selected["base_state_after" if scope == "pa" else "half_end_bases"].to_numpy()
                post, terminal = post_state(x, runs, outs, bases)
                future = we_predict(bundle, post)
                known = np.isfinite(terminal)
                future[known] = terminal[known]
                sign = np.where(x.bottom.eq(0), 1, -1)
                labels.loc[selected.index, f"research_{scope}_wpa"] = sign * (future - x.research_home_we.to_numpy())
                if scope == "pa":
                    from scripts.build_decision_temporal_context import re_get
                    extra = x.inning.gt(x.scheduled_innings).astype(int)
                    post_re = re_get(pd.DataFrame({"outs": outs, "base_state": bases, "extra": extra}), bundle["re"])
                    re_end = np.array([item["mean"] if item else np.nan for item in post_re])
                    # A walk-off terminates the horizon, including remaining RE.
                    re_end[known] = 0
                else:
                    re_end = 0
                labels.loc[selected.index, f"research_{scope}_re24"] = x.research_re.to_numpy() - runs - re_end
        conn.register("computed_labels", labels)
        conn.execute("CREATE OR REPLACE TABLE clean_labels AS SELECT * FROM computed_labels")
        conn.execute("UPDATE clean_labels SET comparable_source_pa_wpa=NULL,comparable_source_pa_re24=NULL WHERE NOT transition_valid")
        report = records(conn, """
            SELECT count(*) AS rows,count(*) FILTER(WHERE changed_start) AS changed_starts,
                count(*) FILTER(WHERE NOT verified_event_start) AS failed_event_starts,
                count(*) FILTER(WHERE intentional_walk) AS intentional_walks,
                count(*) FILTER(WHERE zero_pitch AND intentional_walk) AS zero_pitch_intentional_walks,
                count(*) FILTER(WHERE review_reason='predecision_runner_placement') AS runner_placements,
                count(*) FILTER(WHERE review_reason='predecision_runner_event') AS runner_events
            FROM boundary_review
        """)[0]
        assert report["failed_event_starts"] == 0
        report["targets"] = records(conn, """
            SELECT role,observed_action,count(*) AS n,count(*) FILTER(WHERE transition_valid) AS transition_valid,
                count(*) FILTER(WHERE organic_pa_eligible) AS organic_pa_eligible,
                count(*) FILTER(WHERE half_valid) AS half_valid,count(research_pa_wpa) AS research_pa_wpa,
                count(research_half_re24) AS research_half_re24 FROM clean_labels GROUP BY ALL ORDER BY ALL
        """)
        assert len(labels) == labels.decision_id.nunique()
        assert not labels.loc[~labels.transition_valid, "research_pa_wpa"].notna().any()
        assert not labels.loc[~labels.half_valid, "research_half_re24"].notna().any()
        for table in ("boundary_review", "clean_labels"):
            publish(conn, table, year)
        save_json(OUT / f"labels_{year}.json", {"year": year, **report})
        print(f"{year}: clean labels {report}", flush=True)


def historical_ability_rows(year: int) -> None:
    """Bound the event joins to one season before cumulative history aggregation."""
    with duckdb.connect(config={"threads": 2, "memory_limit": "2GB"}) as conn:
        for directory, names in ((BASE, ("plays", "events", "appearances", "roster")),
                                 (TEMPORAL, ("batter_identity_disagreements",)),
                                 (OUT, ("play_hands",))):
            for name in names:
                conn.read_parquet(str(directory / f"{name}_{year}.parquet")).create_view(name)
        conn.execute("""
            CREATE TABLE eligible_history AS
            WITH last_event AS (
                SELECT game_pk,at_bat_number,arg_max(appearance_id,event_index) AS appearance_id,
                    max(epoch(try_cast(end_time AS TIMESTAMPTZ))) FILTER(WHERE is_pitch) AS last_pitch_end
                FROM events GROUP BY 1,2
            ), disagreement AS (
                SELECT DISTINCT e.game_pk,e.at_bat_number FROM batter_identity_disagreements i JOIN events e USING(event_id)
            ), bad_clock AS (
                SELECT DISTINCT game_pk FROM read_parquet('""" + str(BASE / "chronology_issues_*.parquet").replace("\\", "/") + """')
            )
            SELECT p.year,p.game_pk,p.outcome_key,p.terminal_pitcher_id AS pitcher_id,p.batter_id,a.role,
                h.actual_stand AS batter_stand,h.actual_pitch_hand AS pitcher_hand,
                greatest(epoch(try_cast(p.end_time AS TIMESTAMPTZ)),e.last_pitch_end) AS available_at,
                CASE WHEN p.event_type IN ('strikeout','strikeout_double_play') THEN 'k'
                    WHEN p.event_type='walk' THEN 'bb' WHEN p.event_type='hit_by_pitch' THEN 'hbp'
                    WHEN p.event_type='home_run' THEN 'hr'
                    WHEN p.event_type IN ('single','double','triple') THEN p.event_type
                    WHEN p.outs_after>p.outs_before THEN 'other_out' ELSE 'other_reach' END AS result
            FROM plays p JOIN last_event e USING(game_pk,at_bat_number)
            JOIN appearances a ON a.appearance_id=e.appearance_id AND a.pitcher_id=p.terminal_pitcher_id
            JOIN play_hands h USING(game_pk,at_bat_number)
            LEFT JOIN disagreement i USING(game_pk,at_bat_number) LEFT JOIN bad_clock b USING(game_pk)
            WHERE p.is_complete AND p.is_batter_faced AND NOT p.mid_pa_change AND NOT p.runner_index_missing
                AND p.event_type<>'intent_walk' AND h.source_pitcher_id=p.terminal_pitcher_id
                AND h.source_batter_id=p.batter_id AND i.game_pk IS NULL AND b.game_pk IS NULL
                AND p.end_time IS NOT NULL
                AND a.role IN ('SP','RP')
                AND EXISTS(SELECT 1 FROM roster r WHERE r.game_pk=p.game_pk
                    AND r.player_id=p.terminal_pitcher_id AND r.position_code='1')
                AND epoch(try_cast(p.end_time AS TIMESTAMPTZ))>=epoch(try_cast(p.start_time AS TIMESTAMPTZ))
        """)
        conn.execute("""
            CREATE TABLE ability_history_exclusions AS
            SELECT p.year,p.game_pk,p.outcome_key,
                CASE WHEN NOT p.is_complete OR NOT p.is_batter_faced THEN 'non_batter_or_incomplete'
                    WHEN p.mid_pa_change THEN 'mid_pa_pitcher_responsibility'
                    WHEN p.event_type='intent_walk' THEN 'intentional_walk_action'
                    WHEN p.runner_index_missing THEN 'ambiguous_runner_index'
                    WHEN EXISTS(SELECT 1 FROM read_parquet('""" + str(BASE / "chronology_issues_*.parquet").replace("\\", "/") + """') b
                        WHERE b.game_pk=p.game_pk) THEN 'unreliable_source_clock'
                    WHEN NOT EXISTS(SELECT 1 FROM roster r WHERE r.game_pk=p.game_pk
                        AND r.player_id=p.terminal_pitcher_id AND r.position_code='1') THEN 'non_roster_pitcher'
                    WHEN p.end_time IS NULL OR NOT coalesce(epoch(try_cast(p.end_time AS TIMESTAMPTZ))>=epoch(try_cast(p.start_time AS TIMESTAMPTZ)),false)
                        THEN 'unreliable_completion_time'
                    ELSE 'actor_match_or_role_unresolved' END AS reason
            FROM plays p ANTI JOIN eligible_history e USING(outcome_key)
        """)
        assert conn.execute("SELECT (SELECT count(*) FROM eligible_history)+(SELECT count(*) FROM ability_history_exclusions)-(SELECT count(*) FROM plays)").fetchone()[0] == 0
        publish(conn, "eligible_history", year)
        publish(conn, "ability_history_exclusions", year)
        print(f"{year}: reliable completed PA history published", flush=True)


def historical_abilities() -> None:
    """Publish cumulative counts in timestamp groups; ASOF users must use strict >."""
    for year in YEARS:
        historical_ability_rows(year)
    with duckdb.connect(config={"threads": 1, "memory_limit": "2GB", "preserve_insertion_order": False}) as conn:
        for name in ("eligible_history", "ability_history_exclusions"):
            conn.read_parquet(str(OUT / f"{name}_20*.parquet")).create_view(name)
        conn.execute("""
            CREATE TABLE ability_observations AS
            SELECT 'pitcher' AS actor,pitcher_id AS player_id,role,batter_stand AS split,available_at,result FROM eligible_history
            UNION ALL SELECT 'pitcher',pitcher_id,role,'All',available_at,result FROM eligible_history
            UNION ALL SELECT 'batter',batter_id,'BAT',pitcher_hand,available_at,result FROM eligible_history
            UNION ALL SELECT 'batter',batter_id,'BAT','All',available_at,result FROM eligible_history
        """)
        sums = ",".join(f"count(*) FILTER(WHERE result='{key}') AS {key}" for key in OUTCOMES)
        running = ",".join(f"sum({key}) OVER w AS {key}_n" for key in OUTCOMES)
        conn.execute(f"""
            CREATE TABLE ability_history AS
            WITH time_groups AS (
                SELECT actor,player_id,role,split,available_at,count(*) AS n,{sums}
                FROM ability_observations WHERE split IN ('All','L','R') GROUP BY ALL
            )
            SELECT actor,player_id,role,split,available_at,sum(n) OVER w AS pa_n,{running}
            FROM time_groups WINDOW w AS (PARTITION BY actor,player_id,role,split ORDER BY available_at ROWS UNBOUNDED PRECEDING)
        """)
        print("Cumulative player-role-hand history aggregated", flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        target = OUT / "ability_history.parquet"
        temp = target.with_suffix(".tmp.parquet")
        conn.table("ability_history").write_parquet(str(temp), compression="zstd")
        temp.replace(target)
        references = []
        for fold in FOLDS:
            print(f"{fold['id']}: preparing strictly earlier fallback reference", flush=True)
            cutoff = pd.Timestamp(fold["train_end"], tz="UTC").timestamp()
            for row in records(conn, f"""
                SELECT actor,role,split,sum(pa_n) AS pa_n,{','.join(f'sum({key}_n) AS {key}_n' for key in OUTCOMES)},
                    max(available_at) AS latest_label_at FROM (
                    SELECT * FROM ability_history WHERE available_at < {cutoff}
                    QUALIFY row_number() OVER(PARTITION BY actor,player_id,role,split ORDER BY available_at DESC)=1
                ) GROUP BY ALL
            """):
                assert row["latest_label_at"] < cutoff
                references.append({"fold_id": fold["id"], "train_cutoff": cutoff, **row})
        conn.register("refs", pd.DataFrame(references))
        conn.execute("CREATE TABLE ability_references AS SELECT * FROM refs")
        conn.table("ability_references").write_parquet(str(OUT / "ability_references.parquet"), compression="zstd")
        save_json(OUT / "ability_history.json", {
            "eligible_completed_pas": conn.execute("SELECT count(*) FROM eligible_history").fetchone()[0],
            "history_rows": conn.execute("SELECT count(*) FROM ability_history").fetchone()[0],
            "excluded": records(conn, "SELECT year,reason,count(*) AS n FROM ability_history_exclusions GROUP BY ALL ORDER BY ALL"),
            "result_groups": list(OUTCOMES), "intentional_walks": "separate managerial action; excluded from organic ability rates",
            "rate_method": "own raw frequency; split -> own All -> frozen training reference; no fitted shrinkage yet",
            "source_time": "max(completed play end, last included pitch end); strict history time < decision",
        })
        print("Published all-year ability history and training-only fallback references", flush=True)


def ability_features(year: int) -> None:
    with connect(year) as conn:
        conn.read_parquet(str(OUT / f"listed_hands_{year}.parquet")).create_view("listed_hands")
        conn.read_parquet(str(OUT / "ability_history.parquet")).create_view("ability_history")
        conn.read_parquet(str(OUT / "ability_references.parquet")).create_view("ability_references")
        fold_cases = " ".join(
            f"WHEN f.decision_at >= {pd.Timestamp(fold['score_start'], tz='UTC').timestamp()} "
            f"AND f.decision_at < {pd.Timestamp(fold['score_end'], tz='UTC').timestamp()} THEN '{fold['id']}'" for fold in FOLDS)
        conn.execute(f"""
            CREATE TABLE matchup_identity AS
            SELECT f.*,CASE WHEN p.listed_throws IN ('L','R') THEN p.listed_throws ELSE 'unknown' END AS pitcher_hand,
                CASE WHEN b.listed_bats IN ('L','R','S') THEN b.listed_bats ELSE 'unknown' END AS listed_bats,
                CASE WHEN b.listed_bats IN ('L','R') THEN b.listed_bats
                    WHEN b.listed_bats='S' AND p.listed_throws='L' THEN 'R'
                    WHEN b.listed_bats='S' AND p.listed_throws='R' THEN 'L' ELSE 'unknown' END AS expected_stand,
                CASE {fold_cases} END AS ability_fold_id
            FROM decision_features f
            LEFT JOIN listed_hands p ON p.game_pk=f.game_pk AND p.player_id=f.outgoing_pitcher_id
            LEFT JOIN listed_hands b ON b.game_pk=f.game_pk AND b.player_id=f.batter_id
        """)
        all_parts = []
        for actor in ("pitcher", "batter"):
            player = "outgoing_pitcher_id" if actor == "pitcher" else "batter_id"
            role = "role" if actor == "pitcher" else "'BAT'"
            split = "expected_stand" if actor == "pitcher" else "pitcher_hand"
            conn.execute(f"""
                CREATE OR REPLACE TABLE requests AS
                SELECT decision_id,game_pk,year,decision_at,{player} AS player_id,{role} AS actor_role,
                    {split} AS requested_split,ability_fold_id FROM matchup_identity
            """)
            fields = ",".join(f"h.{key}_n AS split_{key},a.{key}_n AS all_{key},r.{key}_n AS reference_{key}" for key in OUTCOMES)
            conn.execute(f"""
                CREATE OR REPLACE TABLE own AS
                SELECT q.*,h.pa_n AS split_n,h.available_at AS split_at,a.pa_n AS all_n,a.available_at AS all_at,
                    r.pa_n AS reference_n,r.train_cutoff,r.latest_label_at,{fields}
                FROM requests q
                ASOF LEFT JOIN (SELECT * FROM ability_history WHERE actor='{actor}') h
                    ON q.player_id=h.player_id AND q.actor_role=h.role AND q.requested_split=h.split AND q.decision_at>h.available_at
                ASOF LEFT JOIN (SELECT * FROM ability_history WHERE actor='{actor}' AND split='All') a
                    ON q.player_id=a.player_id AND q.actor_role=a.role AND q.decision_at>a.available_at
                LEFT JOIN ability_references r ON r.actor='{actor}' AND r.role=q.actor_role
                    AND r.split='All' AND r.fold_id=q.ability_fold_id
            """)
            selected = ",".join(f"coalesce(split_{key}/nullif(split_n,0),all_{key}/nullif(all_n,0),reference_{key}/nullif(reference_n,0)) AS {key}_rate" for key in OUTCOMES)
            conn.execute(f"""
                CREATE OR REPLACE TABLE actor_features AS
                SELECT decision_id,game_pk,year,decision_at,'{actor}' AS actor,player_id,actor_role,requested_split,
                    coalesce(split_n,0) AS own_split_n,coalesce(all_n,0) AS own_all_n,
                    coalesce(split_at,all_at,latest_label_at) AS history_available_at,
                    CASE WHEN split_n>0 THEN 'own_split' WHEN all_n>0 THEN 'own_all'
                        WHEN reference_n>0 THEN 'frozen_reference' ELSE 'cold_start_unavailable' END AS ability_status,
                    CASE WHEN coalesce(split_n,all_n) IS NULL THEN train_cutoff END AS fallback_train_cutoff,
                    {selected}
                FROM own
            """)
            assert conn.execute("SELECT count(*) FROM actor_features WHERE history_available_at>=decision_at OR fallback_train_cutoff>decision_at").fetchone()[0] == 0
            sum_rates = "+".join(f"{key}_rate" for key in OUTCOMES)
            assert conn.execute(f"SELECT count(*) FROM actor_features WHERE abs(({sum_rates})-1)>1e-9").fetchone()[0] == 0
            all_parts.append(conn.table("actor_features").to_arrow_table())
        import pyarrow as pa
        conn.register("actors", pa.concat_tables(all_parts))
        conn.execute("CREATE TABLE player_ability_features AS SELECT * FROM actors")
        hand_fields = "decision_id,game_pk,year,pitcher_hand,listed_bats,expected_stand,ability_fold_id"
        conn.execute(f"CREATE TABLE decision_matchup AS SELECT {hand_fields} FROM matchup_identity")
        for name in ("player_ability_features", "decision_matchup"):
            publish(conn, name, year)
        save_json(OUT / f"ability_{year}.json", {"year": year,
            "rows": records(conn, "SELECT actor,ability_status,count(*) AS n FROM player_ability_features GROUP BY ALL ORDER BY ALL"),
            "hands": records(conn, "SELECT pitcher_hand,listed_bats,expected_stand,count(*) AS n FROM decision_matchup GROUP BY ALL ORDER BY ALL"),
            "future_time_violations": 0, "switch_hitters": "opposite expected stand to option pitcher hand; schematic matchup assumption; actual stance may differ"})
        print(f"{year}: player ability feature pairs published", flush=True)


def signal_features(year: int) -> None:
    with connect(year) as conn:
        fields = ("research_stuff_plus", "research_location_plus")
        sums = ",".join(f"count({key}) AS {key}_n,sum({key}) AS {key}_sum" for key in fields)
        cumulative = ",".join(f"sum({key}_n) OVER w AS {key}_n,sum({key}_sum) OVER w AS {key}_sum" for key in fields)
        conn.execute(f"""
            CREATE TABLE pitch_prefix AS
            WITH groups AS (
                SELECT appearance_id,pitcher_id,plus_model_id,plus_train_cutoff,observed_at,
                    count(*) AS n,{sums} FROM pitch_features
                WHERE source_valid AND alignment_status='validated_order' AND roster_pitcher
                    AND source_batter_consistent AND observed_at IS NOT NULL
                    AND plus_model_id IS NOT NULL AND plus_train_cutoff<=observed_at GROUP BY ALL
            )
            SELECT appearance_id,pitcher_id,plus_model_id,plus_train_cutoff,observed_at,
                sum(n) OVER w AS observed_pitches,{cumulative}
            FROM groups WINDOW w AS (PARTITION BY appearance_id,pitcher_id,plus_model_id,plus_train_cutoff ORDER BY observed_at ROWS UNBOUNDED PRECEDING)
        """)
        bounds = ",".join(f"s.{key}_{bound}" for key in ("quality", "physical", "command") for bound in ("low", "high"))
        conn.execute(f"""
            CREATE TABLE signal_features AS
            SELECT f.year,f.game_pk,f.decision_id,f.role,f.decision_at,f.current_pitches,
                p.observed_at AS plus_observed_at,p.plus_model_id,p.plus_train_cutoff,
                coalesce(p.observed_pitches,0) AS plus_source_n,
                coalesce(p.research_stuff_plus_n,0) AS stuff_n,
                p.research_stuff_plus_sum/nullif(p.research_stuff_plus_n,0) AS prior_prefix_stuff,
                coalesce(p.research_location_plus_n,0) AS location_n,
                p.research_location_plus_sum/nullif(p.research_location_plus_n,0) AS prior_prefix_location,
                f.quality_plus,f.physical_plus,f.command_plus,{bounds},s.reliability,s.prefix_pitches,
                s.state_observed_at,s.state_model_id,s.state_train_cutoff,f.prefix_status,
                CASE WHEN f.current_pitches<CASE WHEN f.role='SP' THEN 35 ELSE 10 END THEN 'insufficient_current_prefix'
                    WHEN f.current_pitches>CASE WHEN f.role='SP' THEN 100 ELSE 60 END THEN 'outside_modeled_pitch_count'
                    WHEN f.decision_at<epoch(TIMESTAMPTZ '2021-09-01') THEN 'state_model_warmup'
                    WHEN f.prefix_status='resumed_session_needs_new_baseline' THEN f.prefix_status
                    WHEN f.quality_plus IS NULL AND f.physical_plus IS NULL AND f.command_plus IS NULL THEN 'tracking_or_mix_support_unavailable'
                    WHEN f.quality_plus IS NULL OR f.physical_plus IS NULL OR f.command_plus IS NULL THEN 'partial_signals'
                    ELSE 'three_signals_available' END AS signal_support,
                CASE WHEN f.decision_at<epoch(TIMESTAMPTZ '2021-07-01') THEN 'plus_model_warmup'
                    WHEN p.observed_at IS NULL THEN 'no_supported_prior_pitch'
                    WHEN p.research_stuff_plus_n=0 OR p.research_location_plus_n=0 THEN 'partial_plus'
                    ELSE 'observed_prefix_summary' END AS plus_status
            FROM decision_features f
            LEFT JOIN decision_states s USING(decision_id)
            ASOF LEFT JOIN pitch_prefix p ON f.appearance_id=p.appearance_id
                AND f.outgoing_pitcher_id=p.pitcher_id AND f.decision_at>p.observed_at
        """)
        checks = conn.execute("""SELECT count(*) FROM signal_features WHERE plus_observed_at>=decision_at
            OR plus_train_cutoff>plus_observed_at OR state_observed_at>=decision_at
            OR state_train_cutoff>state_observed_at
            OR (quality_plus IS NOT NULL AND (quality_low>quality_plus OR quality_high<quality_plus))
            OR (physical_plus IS NOT NULL AND (physical_low>physical_plus OR physical_high<physical_plus))
            OR (command_plus IS NOT NULL AND (command_low>command_plus OR command_high<command_plus))""").fetchone()[0]
        assert checks == 0, checks
        assert conn.execute("SELECT count(*)-count(DISTINCT decision_id) FROM signal_features").fetchone()[0] == 0
        publish(conn, "signal_features", year)
        save_json(OUT / f"signals_{year}.json", {"year": year, "time_or_interval_violations": checks,
            "support": records(conn, "SELECT signal_support,count(*) AS n FROM signal_features GROUP BY 1 ORDER BY 1"),
            "coverage": records(conn, "SELECT count(*) AS n,count(prior_prefix_stuff) AS stuff,count(prior_prefix_location) AS location,count(quality_plus) AS quality,count(physical_plus) AS physical,count(command_plus) AS command FROM signal_features")[0],
            "scale": "separate reference-centered scores; reliability is shrinkage weight, interval is approximate 80% sampling only"})
        print(f"{year}: prior Plus and original state intervals published", flush=True)


def coverage(year: int) -> None:
    with connect(year) as conn:
        for name in ("signal_features", "player_ability_features", "decision_matchup", "clean_labels"):
            conn.read_parquet(str(OUT / f"{name}_{year}.parquet")).create_view(name)
        ability_columns = []
        for alias, prefix in (("pa", "pitcher"), ("ba", "batter")):
            for field in ("own_split_n", "own_all_n", "history_available_at", "ability_status", "fallback_train_cutoff",
                          *(f"{key}_rate" for key in OUTCOMES)):
                ability_columns.append(f"{alias}.{field} AS {prefix}_{field}")
        conn.execute("""
            CREATE TABLE prepared_features AS
            SELECT f.*,m.pitcher_hand,m.listed_bats,m.expected_stand,s.* EXCLUDE(year,game_pk,decision_id,role,decision_at,current_pitches,
                quality_plus,physical_plus,command_plus,prefix_status,state_observed_at,state_train_cutoff),
            """ + ",".join(ability_columns) + """
            FROM decision_features f JOIN decision_matchup m USING(decision_id) JOIN signal_features s USING(decision_id)
            JOIN player_ability_features pa ON pa.decision_id=f.decision_id AND pa.actor='pitcher'
            JOIN player_ability_features ba ON ba.decision_id=f.decision_id AND ba.actor='batter'
        """)
        columns = conn.execute("DESCRIBE prepared_features").fetchall()
        rows = []
        audits = conn.execute("SELECT decision_id,observed_action FROM decision_audit WHERE cohort_reason='included'").fetchdf()
        conn.register("actions", audits)
        for name, dtype, *_ in columns:
            numeric = any(token in dtype for token in ("INT", "DOUBLE", "FLOAT", "DECIMAL"))
            finite = f"isfinite(f.{name})" if numeric else f"f.{name} IS NOT NULL"
            zero = f"count(*) FILTER(WHERE f.{name}=0)" if numeric else "0"
            valid = f"{finite} AND f.lookback_14d_complete" if name.startswith("pitches_") else finite
            if name in {"pitcher_hand", "expected_stand", "listed_bats"}:
                valid = f"{finite} AND f.{name}<>'unknown'"
            if name == "operational_availability":
                valid = "false"
            for row in records(conn, f"""
                SELECT f.year,f.role,a.observed_action,count(*) AS denominator,'{name}' AS field,
                    count(f.{name}) AS nonnull,count(*) FILTER(WHERE {finite}) AS finite_or_present,
                    count(*) FILTER(WHERE {valid}) AS supported,{zero} AS true_zero
                FROM prepared_features f JOIN actions a USING(decision_id) GROUP BY ALL
            """):
                rows.append(row)
        conn.register("field_counts", pd.DataFrame(rows))
        conn.execute("CREATE TABLE field_coverage AS SELECT * FROM field_counts")
        publish(conn, "prepared_features", year)
        publish(conn, "field_coverage", year)
        candidate_columns = conn.execute("DESCRIBE decision_candidates").fetchall()
        candidate_coverage = []
        for name, dtype, *_ in candidate_columns:
            candidate_coverage.extend(records(conn, f"""
                SELECT f.role,a.observed_action,'{name}' AS field,count(*) AS denominator,count(c.{name}) AS nonnull,
                    count(DISTINCT c.decision_id) AS decision_denominator,
                    count(DISTINCT c.decision_id) FILTER(WHERE c.{name} IS NOT NULL) AS any_candidate_present
                FROM decision_candidates c JOIN decision_features f USING(decision_id) JOIN actions a USING(decision_id)
                GROUP BY ALL ORDER BY ALL
            """))
        dictionary = []
        for name, dtype, *_ in columns:
            provenance = name.endswith(("_at", "_cutoff")) or name.endswith("_id") or name in {
                "year", "game_pk", "role", "appearance_id", "history_status", "prefix_status", "context_status",
                "signal_support", "plus_status", "roster_confidence", "operational_availability", "listed_bats"}
            unit = "reference_points" if name.endswith(("_plus", "_low", "_high")) or name in {"prior_prefix_stuff", "prior_prefix_location"} else (
                "UTC_epoch_seconds" if name.endswith(("_at", "_cutoff")) else "hours" if name.startswith("rest_hours") else
                "pitches" if "pitches" in name else "probability" if name == "research_home_we" else
                "runs" if name in {"research_re", "defense_lead"} else "ratio" if name in {"reliability", "state_reliability"} else
                "index" if name == "research_pa_li" else "source_defined")
            dictionary.append({"name": name, "dtype": dtype, "unit": unit,
                "usage": "provenance_or_support" if provenance else "candidate_feature_pending_12.6_whitelist",
                "missing_rule": "raw null retained; support flags kept; any fitted imputation is deferred to 12.6",
                "available_rule": "source observation strictly before decision; game-listed hands have archived-source revision caveat"})
        save_json(OUT / f"coverage_{year}.json", {"year": year,
            "n": len(audits), "dictionary": dictionary,
            "candidate_columns": candidate_coverage,
            "ability": records(conn, "SELECT actor,ability_status,count(*) AS n FROM player_ability_features GROUP BY ALL ORDER BY ALL"),
            "targets": records(conn, "SELECT count(*) AS n,count(*) FILTER(WHERE organic_pa_eligible) AS organic_pa,count(*) FILTER(WHERE half_valid) AS half_valid FROM clean_labels")[0]})
        print(f"{year}: coverage dictionary and prepared feature table published", flush=True)


def finalize() -> None:
    sections = {"12_1": "labels", "12_2": "coverage", "12_3": "ability", "12_4": "signals"}
    for number, kind in sections.items():
        report = {"version": "decision_preparation_v1", "slice": number.replace("_", "."),
                  "years": [json.loads((OUT / f"{kind}_{year}.json").read_text("utf-8")) for year in YEARS]}
        if number == "12_2":
            report["source_probe"] = json.loads((OUT / "backfill_probe.json").read_text("utf-8"))
            report["missingness_policy"] = {
                "not_computed": "hand and ability aggregates completed by 12.3; Plus and state adapter completed by 12.4",
                "early_history": "2021 begins local coverage; no earlier local DB or official feed inventory found",
                "tracking_or_alignment": "leave unavailable where measurement or unambiguous alignment is absent",
                "short_or_outside_prefix": "observe fixed SP35/RP10 and SP100/RP60 bounds; not backfillable by later pitches",
                "conditional_backfill": {"needed_for_baseline": False, "proposal": "2020 official completed-game feeds plus tracked pitches, then sufficient earlier model reference",
                    "season_backfill_executed": False, "external_source_feasibility": "see bounded schedule and one-game source probes; full pre-2021 completeness unverified",
                    "scope_estimate": "inventory one regular season before download; 2020 shortened schedule and policy differences require a separate reference",
                    "expected_gain": "may extend 2021 reference and history; cannot remove within-game prefix support limits",
                    "cost": "requires season-level source audit, event alignment and retraining new reference versions; not a few missing score files"},
            }
        if number == "12_3":
            report["history"] = json.loads((OUT / "ability_history.json").read_text("utf-8"))
        save_json(DATA / f"sample/petehub_pitcher_decision_slice{number}_v1.json", report)
    guards = json.loads((TEMPORAL / "formal_model_guards.json").read_text("utf-8"))
    for guard in guards:
        assert digest(Path(guard["path"])) == guard["sha256"]
    manifest = [{"path": str(path.relative_to(OUT)), "bytes": path.stat().st_size, "sha256": digest(path)}
                for path in sorted(OUT.glob("*")) if path.is_file() and path.name != "manifest.json" and ".tmp" not in path.name]
    input_manifests = [TEMPORAL / "manifest.json", TEMPORAL / "protocol.json",
                       DATA / "sample/petehub_pitcher_decision_slice11_v1.json"]
    save_json(OUT / "manifest.json", {"version": "decision_preparation_v1", "files": manifest,
        "source_references": [{"path": str(path.relative_to(ROOT)), "sha256": digest(path)} for path in input_manifests],
        "formal_model_guard_checks": len(guards), "formal_metadata_changes": 0})
    print(f"Published four slice evidence files and {len(manifest)} artifact hashes", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("source", "probe", "labels", "history", "ability", "signals", "coverage", "finalize"))
    parser.add_argument("--year", type=int, choices=YEARS)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == "probe":
        backfill_probe()
    elif args.stage == "history":
        historical_abilities()
    elif args.stage == "finalize":
        finalize()
    else:
        functions = {"source": source_hands, "labels": clean_labels, "ability": ability_features,
                     "signals": signal_features, "coverage": coverage}
        for year in [args.year] if args.year else YEARS:
            functions[args.stage](year)


if __name__ == "__main__":
    main()
