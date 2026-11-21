"""Build Slice 11's retrospective decision sample from the frozen Slice 3–10 inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
YEARS = range(2021, 2027)
VERSION = "pitcher_decision_sample_v1"


def connect_year(data_dir: Path, year: int) -> duckdb.DuckDBPyConnection:
    research = data_dir / "research"
    foundation = research / "decision_support_pipeline_20261114"
    temporal = research / "decision_support_temporal_20261114"
    conn = duckdb.connect(config={"threads": 2, "memory_limit": "1500MB"})
    for directory, names in (
        (foundation, ("decisions", "plays", "appearances", "events", "workload", "bullpen_sets", "bullpen_candidates")),
        (temporal, ("decision_states", "context_features", "context_labels", "candidate_state_priors", "batter_identity_disagreements")),
    ):
        for name in names:
            conn.read_parquet(str(directory / f"{name}_{year}.parquet")).create_view(name)
    return conn


def build_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE decision_audit AS
        WITH uncertain_identity AS (
            SELECT DISTINCT e.game_pk, e.at_bat_number
            FROM batter_identity_disagreements i JOIN events e USING (event_id)
        )
        SELECT d.year, d.game_pk, d.decision_id, d.outcome_key, d.appearance_id,
            coalesce(a.role, 'unknown') AS role, d.outgoing_pitcher_id, d.incoming_pitcher_id,
            CASE WHEN d.observed_change THEN 'change' ELSE 'continue' END AS observed_action,
            b.candidate_count, b.roster_confidence, b.operational_availability,
            CASE
                WHEN d.is_initial_start THEN 'initial_start'
                WHEN NOT d.completed_batter_play OR NOT p.is_complete THEN 'not_completed_batter_play'
                WHEN p.mid_pa_change OR d.balls <> 0 OR d.strikes <> 0 THEN 'mid_pa_change_or_nonzero_count'
                WHEN d.compound_prelude THEN 'compound_prelude'
                WHEN d.injury_observed_before OR d.mandatory_removed_pitcher THEN 'forced_or_injury'
                WHEN NOT coalesce(b.statutory_change_allowed AND b.continue_nominal_allowed, false) THEN 'no_legal_choice'
                WHEN NOT coalesce(d.base_state_known AND w.source_clock_valid, false)
                    OR NOT isfinite(cf.decision_at) OR d.time_basis = 'play_start_fallback'
                    OR cf.decision_at IS NULL OR d.outs NOT BETWEEN 0 AND 2 THEN 'unknown_state_or_clock'
                WHEN d.batter_id IS NULL OR d.batter_id IS DISTINCT FROM p.batter_id
                    OR i.game_pk IS NOT NULL THEN 'uncertain_batter'
                WHEN a.role IS NULL OR a.role NOT IN ('SP', 'RP') OR d.outgoing_pitcher_id IS NULL
                    THEN 'unknown_pitcher_role'
                WHEN d.incoming_pitcher_id IS NULL OR d.incoming_pitcher_id IS DISTINCT FROM p.terminal_pitcher_id
                    OR d.observed_change IS DISTINCT FROM (d.incoming_pitcher_id <> d.outgoing_pitcher_id)
                    THEN 'uncertain_observed_action'
                WHEN coalesce(b.candidate_count, 0) = 0 THEN 'no_nominal_candidate'
                WHEN d.observed_change AND NOT list_contains(b.candidate_ids, d.incoming_pitcher_id)
                    THEN 'observed_replacement_outside_nominal_set'
                ELSE 'included'
            END AS cohort_reason
        FROM decisions d
        JOIN plays p USING (outcome_key)
        LEFT JOIN appearances a ON a.appearance_id = d.appearance_id
        LEFT JOIN workload w USING (decision_id)
        LEFT JOIN bullpen_sets b USING (decision_id)
        LEFT JOIN context_features cf USING (decision_id)
        LEFT JOIN uncertain_identity i ON i.game_pk = d.game_pk AND i.at_bat_number = d.at_bat_number
    """)
    conn.execute("""
        CREATE TABLE decision_features AS
        SELECT d.year, d.game_pk, d.decision_id, d.team_id, d.appearance_id, f.role,
            d.outgoing_pitcher_id, d.batter_id, cf.decision_at, d.inning, d.half, p.scheduled_innings,
            CASE WHEN d.half = 'top' THEN d.home_score-d.away_score ELSE d.away_score-d.home_score END AS defense_lead,
            d.outs, d.base_state, d.current_pitches, d.current_bf,
            w.pitches_1d_before, w.pitches_3d_before, w.pitches_7d_before, w.pitches_14d_before,
            epoch(w.last_pitch_before) AS last_pitch_at, epoch(w.history_closed_at) AS history_closed_at,
            w.rest_hours_since_closed_session, w.prior_session_consecutive_days, w.appeared_earlier_today,
            w.history_status, w.lookback_14d_complete,
            s.quality_plus, s.physical_plus, s.command_plus, s.reliability AS state_reliability,
            s.state_observed_at, s.state_train_cutoff, s.status AS prefix_status,
            cf.research_home_we, cf.research_re, cf.research_pa_li, cf.context_train_cutoff,
            cf.li_reference_n, cf.li_backoff, cf.status AS context_status,
            f.candidate_count, f.roster_confidence, f.operational_availability
        FROM decision_audit f JOIN decisions d USING (decision_id)
        JOIN plays p ON p.outcome_key = d.outcome_key
        JOIN workload w USING (decision_id) JOIN context_features cf USING (decision_id)
        LEFT JOIN decision_states s USING (decision_id)
        WHERE f.cohort_reason = 'included'
    """)
    conn.execute("""
        CREATE TABLE decision_labels AS
        WITH half_end AS (
            SELECT game_pk, inning, half,
                arg_max(struct_pack(away_score := away_score_after, home_score := home_score_after,
                    end_time := end_time, complete := is_complete, pre_we := pre_home_we,
                    home_wpa := raw_home_wpa), at_bat_number) AS end_play
            FROM plays GROUP BY game_pk, inning, half
        ), outcomes AS (
        SELECT f.year, f.game_pk, f.decision_id, a.outcome_key, a.observed_action, a.incoming_pitcher_id, f.decision_at,
            epoch(try_cast(p.end_time AS TIMESTAMPTZ)) AS next_pa_end_at, p.event_type AS next_pa_result,
            CASE WHEN f.half='top' THEN p.raw_home_wpa ELSE -p.raw_home_wpa END AS next_pa_defense_wpa,
            p.source_re24 AS next_pa_source_defense_re24, l.modeled_defense_re24 AS next_pa_research_defense_re24,
            CASE WHEN f.half='top' THEN l.modeled_home_wpa ELSE -l.modeled_home_wpa END AS next_pa_research_defense_wpa,
            epoch(try_cast(h.end_play.end_time AS TIMESTAMPTZ)) AS half_end_at,
            CASE WHEN h.end_play.complete THEN CASE WHEN f.half='top'
                THEN h.end_play.away_score-d.away_score ELSE h.end_play.home_score-d.home_score END END AS half_remaining_runs_allowed,
            CASE WHEN h.end_play.complete THEN (CASE WHEN f.half='top' THEN 1 ELSE -1 END)
                * (h.end_play.pre_we+h.end_play.home_wpa-p.pre_home_we) END AS half_defense_wpa
        FROM decision_features f JOIN decision_audit a USING (decision_id)
        JOIN decisions d USING (decision_id) JOIN plays p ON p.outcome_key = a.outcome_key
        JOIN half_end h ON h.game_pk = f.game_pk AND h.inning = f.inning AND h.half = f.half
        LEFT JOIN context_labels l USING (decision_id)
        ), eligibility AS (
            SELECT *, coalesce(next_pa_end_at >= decision_at, false) AS next_pa_available,
                coalesce(half_end_at >= next_pa_end_at AND next_pa_end_at >= decision_at
                         AND half_remaining_runs_allowed >= 0, false) AS half_available
            FROM outcomes
        )
        SELECT * EXCLUDE(decision_at) REPLACE (
            CASE WHEN next_pa_available THEN next_pa_end_at END AS next_pa_end_at,
            CASE WHEN next_pa_available THEN next_pa_result END AS next_pa_result,
            CASE WHEN next_pa_available THEN next_pa_defense_wpa END AS next_pa_defense_wpa,
            CASE WHEN next_pa_available THEN next_pa_source_defense_re24 END AS next_pa_source_defense_re24,
            CASE WHEN next_pa_available THEN next_pa_research_defense_re24 END AS next_pa_research_defense_re24,
            CASE WHEN next_pa_available THEN next_pa_research_defense_wpa END AS next_pa_research_defense_wpa,
            CASE WHEN half_available THEN half_end_at END AS half_end_at,
            CASE WHEN half_available THEN half_remaining_runs_allowed END AS half_remaining_runs_allowed,
            CASE WHEN half_available THEN half_defense_wpa END AS half_defense_wpa
        ) FROM eligibility
    """)
    conn.execute("""
        CREATE VIEW decision_candidates AS
        SELECT b.* EXCLUDE (individual_ranking_allowed), p.prior_state_available_at,
            p.prior_quality, p.prior_physical, p.prior_command, p.prior_state_reliability,
            p.status AS prior_state_status, false AS individual_ranking_allowed
        FROM decision_features f JOIN bullpen_candidates b USING (decision_id)
        LEFT JOIN candidate_state_priors p USING (decision_id, pitcher_id)
        WHERE b.nominal_eligible
    """)


def rows(conn: duckdb.DuckDBPyConnection, query: str) -> list[dict]:
    result = conn.execute(query)
    fields = [col[0] for col in result.description]
    return [dict(zip(fields, row, strict=True)) for row in result.fetchall()]


def audit_year(conn: duckdb.DuckDBPyConnection, year: int) -> dict:
    (total, unique, audit, audit_unique, features, feature_unique, labels, label_unique) = conn.execute("""
        SELECT (SELECT count(*) FROM decisions), (SELECT count(DISTINCT decision_id) FROM decisions),
            (SELECT count(*) FROM decision_audit), (SELECT count(DISTINCT decision_id) FROM decision_audit),
            (SELECT count(*) FROM decision_features), (SELECT count(DISTINCT decision_id) FROM decision_features),
            (SELECT count(*) FROM decision_labels), (SELECT count(DISTINCT decision_id) FROM decision_labels)
    """).fetchone()
    assert total == unique == audit == audit_unique
    assert features == feature_unique == labels == label_unique > 0
    checks = rows(conn, """
        SELECT (SELECT count(*) FROM decision_features WHERE last_pitch_at >= decision_at
                    OR history_closed_at >= decision_at OR state_observed_at >= decision_at
                    OR state_train_cutoff > state_observed_at OR context_train_cutoff > decision_at) AS feature_time,
               (SELECT count(*) FROM decision_labels l JOIN decision_features f USING(decision_id)
                    WHERE next_pa_end_at < decision_at OR half_end_at < next_pa_end_at
                        OR half_remaining_runs_allowed < 0) AS outcome_time_or_runs,
               (SELECT count(*) FROM (
                    SELECT f.decision_id FROM decision_features f LEFT JOIN decision_candidates c USING(decision_id)
                    GROUP BY f.decision_id,f.candidate_count
                    HAVING count(c.pitcher_id) <> f.candidate_count OR count(DISTINCT c.pitcher_id) <> f.candidate_count
                        OR bool_or(c.cutoff_epoch IS DISTINCT FROM f.decision_at OR c.last_pitch_epoch >= f.decision_at
                                  OR c.history_closed_epoch >= f.decision_at OR c.prior_state_available_at >= f.decision_at)))
                    AS candidate_key_or_time
    """)[0]
    assert all(n == 0 for n in checks.values()), checks
    (training_columns,) = conn.execute("SELECT list(column_name) FROM (DESCRIBE decision_features)").fetchone()
    assert not {"observed_action", "incoming_pitcher_id", "outcome_key", "next_pa_result"}.intersection(training_columns)
    return {
        "year": year, "raw_boundaries": total, "included": features, "checks": checks,
        "cohorts": rows(conn, """
            SELECT role, observed_action, cohort_reason, count(*) AS n FROM decision_audit GROUP BY ALL ORDER BY ALL
        """),
        "exploration": rows(conn, """
            SELECT role, observed_action, count(*) AS n,
                round(avg(current_pitches), 2) AS mean_current_pitches,
                count(research_pa_li) AS n_pa_li, round(avg(research_pa_li), 3) AS mean_pa_li,
                count(quality_plus) AS n_quality, round(avg(quality_plus), 2) AS mean_quality,
                count(physical_plus) AS n_physical, round(avg(physical_plus), 2) AS mean_physical,
                count(command_plus) AS n_command, round(avg(command_plus), 2) AS mean_command,
                count(half_defense_wpa) AS n_half_wpa, count(half_remaining_runs_allowed) AS n_half_runs,
                count(next_pa_defense_wpa) AS n_next_pa_wpa, count(next_pa_source_defense_re24) AS n_next_pa_re24
            FROM decision_features f JOIN decision_labels l USING(decision_id) GROUP BY ALL ORDER BY ALL
        """),
        "examples": rows(conn, """
            SELECT decision_id, game_pk, role, observed_action, current_pitches, candidate_count,
                next_pa_result, half_remaining_runs_allowed
            FROM decision_features JOIN decision_labels USING(decision_id, game_pk, year)
            WHERE quality_plus IS NOT NULL AND half_defense_wpa IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY role, observed_action ORDER BY game_pk, decision_at, decision_id)=1
            ORDER BY role, observed_action
        """),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=YEARS)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    out = args.data_dir / "research" / VERSION
    out.mkdir(parents=True, exist_ok=True)
    years = [args.year] if args.year else YEARS
    reports = []
    for year in years:
        with connect_year(args.data_dir, year) as conn:
            build_tables(conn)
            report = audit_year(conn, year)
            for name in ("decision_audit", "decision_features", "decision_labels", "decision_candidates"):
                target = out / f"{name}_{year}.parquet"
                temp = target.with_suffix(".tmp")
                conn.table(name).write_parquet(str(temp), compression="zstd")
                temp.replace(target)
            year_report = out / f"summary_{year}.json"
            year_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            reports.append(report)
            print(f"{year}: {report['included']:,} / {report['raw_boundaries']:,} boundaries", flush=True)
    if not args.year:
        report = {"version": VERSION, "years": reports, "individual_ranking_allowed": False,
                  "observed_actions_only": True, "candidate_availability": "nominal_only"}
        sample = args.data_dir / "sample" / "petehub_pitcher_decision_slice11_v1.json"
        sample.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
