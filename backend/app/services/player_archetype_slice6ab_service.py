from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.pitch_stuff_cache_service import _artifact_version, cache_path
from app.services.player_archetype_slice4_service import slice4_warehouse_path


CONTRACT_VERSION = "player_archetype_slice6ab_weapon_threat_v1"
TEST_YEAR = 2026
WEAPON_HISTORY_YEARS = (2025, 2026)
THREAT_HISTORY_YEARS = tuple(range(2021, 2026))
BASELINE_PRIOR_PITCHES = 20.0
OUTING_STUFF_PRIOR_PITCHES = 8.0
OUTING_LOCATION_PRIOR_PITCHES = 12.0
HUNT_PRIOR_PITCHES = 40.0
WHIFF_PRIOR_SWINGS = 20.0
DAMAGE_PRIOR_PITCHES = 50.0


def slice6ab_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6ab.json"


def slice6a_candidate_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6a_weapon_candidates_2026.parquet"


def slice6a_chosen_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6a_weapon_chosen_2026.parquet"


def slice6b_surface_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6b_batter_threat_surface.parquet"


def slice6ab_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any, digits: int = 6) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, digits) if math.isfinite(numeric) else None


def _pitch_family(column: str = "pitch_type") -> str:
    return f"""
        CASE
            WHEN {column} IN ('FF', 'SI', 'FC') THEN 'Fastball'
            WHEN {column} IN ('SL', 'ST', 'CU', 'KC', 'SV') THEN 'Breaking'
            WHEN {column} IN ('CH', 'FS', 'FO', 'SC') THEN 'Offspeed'
            ELSE 'Other'
        END
    """


def _count_tier(balls: str = "balls", strikes: str = "strikes") -> str:
    return f"""
        CASE
            WHEN {balls} = 0 AND {strikes} = 0 THEN 'FirstPitch'
            WHEN {balls} > {strikes} THEN 'BatterAhead'
            WHEN {balls} < {strikes} THEN 'PitcherAhead'
            ELSE 'Even'
        END
    """


def _source_table(year: int, root: Path) -> str:
    path = get_season_duckdb_path(year, root)
    if not path.exists():
        raise FileNotFoundError(path)
    with duckdb.connect(str(path), read_only=True) as connection:
        table = resolve_pitch_table({row[0] for row in connection.execute("SHOW TABLES").fetchall()})
    if not table:
        raise RuntimeError(f"No pitch table found in {path}")
    return table


def _attach_years(
    connection: duckdb.DuckDBPyConnection,
    years: tuple[int, ...],
    root: Path,
) -> dict[int, str]:
    tables: dict[int, str] = {}
    for year in years:
        path = get_season_duckdb_path(year, root)
        table = _source_table(year, root)
        connection.execute(f"ATTACH '{_sql_path(path)}' AS y{year} (READ_ONLY)")
        tables[year] = table
    return tables


def _load_stuff_scores(
    root: Path,
    years: tuple[int, ...] = WEAPON_HISTORY_YEARS,
) -> pd.DataFrame:
    version = _artifact_version(root)
    placeholders = ",".join("?" for _ in years)
    with sqlite3.connect(cache_path(root), timeout=60) as connection:
        return pd.read_sql_query(
            f"""
            SELECT year, game_pk, at_bat_number, pitch_number, pitcher, pitch_stuff_plus
            FROM pitch_stuff_scores
            WHERE year IN ({placeholders}) AND model_version = ?
            """,
            connection,
            params=[*years, version],
        )


def _weapon_history_sql(
    tables: dict[int, str],
    years: tuple[int, ...] = WEAPON_HISTORY_YEARS,
) -> str:
    parts = []
    for year in years:
        table = tables[year]
        parts.append(
            f"""
            SELECT
                {year}::INTEGER AS year,
                CAST(p.game_date AS DATE) AS game_date,
                CAST(p.game_pk AS BIGINT) AS game_pk,
                CAST(p.at_bat_number AS INTEGER) AS at_bat_number,
                CAST(p.pitch_number AS INTEGER) AS pitch_number,
                CAST(p.pitcher AS BIGINT) AS pitcher_id,
                nullif(CAST(p.p_throws AS VARCHAR), '') AS pitcher_throws,
                nullif(CAST(p.pitch_type AS VARCHAR), '') AS pitch_type,
                {_pitch_family('p.pitch_type')} AS pitch_family,
                CAST(p.pitch_uid AS VARCHAR) AS pitch_uid,
                CAST(s.pitch_stuff_plus AS DOUBLE) AS observed_stuff_plus,
                CAST(l.location_plus_pitch AS DOUBLE) AS observed_location_plus
            FROM y{year}.{table} p
            LEFT JOIN stuff_scores s
              ON s.year = {year}
             AND s.game_pk = p.game_pk
             AND s.at_bat_number = p.at_bat_number
             AND s.pitch_number = p.pitch_number
             AND s.pitcher = p.pitcher
            LEFT JOIN loc.location_pitch_scores_{year} l
              ON l.pitch_uid = CAST(p.pitch_uid AS VARCHAR)
            WHERE p.game_type = 'R'
              AND p.game_pk IS NOT NULL AND p.at_bat_number IS NOT NULL
              AND p.pitch_number IS NOT NULL AND p.pitcher IS NOT NULL
              AND p.pitch_type IS NOT NULL
            """
        )
    return " UNION ALL ".join(parts)


def _weapon_candidate_query(
    warehouse: Path,
    tables: dict[int, str],
    target_year: int = TEST_YEAR,
    history_years: tuple[int, ...] = WEAPON_HISTORY_YEARS,
) -> str:
    history = _weapon_history_sql(tables, history_years)
    league_year = min(history_years)
    k_base = BASELINE_PRIOR_PITCHES
    k_stuff = OUTING_STUFF_PRIOR_PITCHES
    k_location = OUTING_LOCATION_PRIOR_PITCHES
    return f"""
        WITH raw_history AS ({history}),
        history AS (
            SELECT *,
                dense_rank() OVER (
                    PARTITION BY pitcher_id ORDER BY game_date, game_pk
                ) AS pitcher_game_index,
                CAST(at_bat_number AS BIGINT) * 1000 + pitch_number AS decision_order
            FROM raw_history
        ),
        type_games AS (
            SELECT pitcher_id, pitcher_throws, pitcher_game_index, game_date, game_pk,
                   pitch_type, pitch_family,
                   count(*) AS pitch_n,
                   count(observed_stuff_plus) AS stuff_n,
                   sum(observed_stuff_plus) AS stuff_sum,
                   count(observed_location_plus) AS location_n,
                   sum(observed_location_plus) AS location_sum
            FROM history
            GROUP BY ALL
        ),
        type_post_game AS (
            SELECT *,
                sum(pitch_n) OVER type_window AS post_pitch_n,
                sum(stuff_n) OVER type_window AS post_stuff_n,
                sum(stuff_sum) OVER type_window AS post_stuff_sum,
                sum(location_n) OVER type_window AS post_location_n,
                sum(location_sum) OVER type_window AS post_location_sum
            FROM type_games
            WINDOW type_window AS (
                PARTITION BY pitcher_id, pitch_type
                ORDER BY pitcher_game_index
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        ),
        pitcher_games AS (
            SELECT pitcher_id, pitcher_throws, pitcher_game_index, game_date, game_pk,
                   count(*) AS game_pitch_n
            FROM history GROUP BY ALL
        ),
        pitcher_post_game AS (
            SELECT *,
                sum(game_pitch_n) OVER (
                    PARTITION BY pitcher_id ORDER BY pitcher_game_index
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS post_pitcher_pitch_n
            FROM pitcher_games
        ),
        current_games AS (
            SELECT * FROM pitcher_games WHERE year(game_date) = {int(target_year)}
        ),
        prior_type AS (
            SELECT cg.game_pk AS current_game_pk, cg.pitcher_id,
                   tp.pitch_type, tp.pitch_family,
                   tp.post_pitch_n AS pregame_type_pitches,
                   tp.post_stuff_n AS pregame_stuff_pitches,
                   tp.post_stuff_sum AS pregame_stuff_sum,
                   tp.post_location_n AS pregame_location_pitches,
                   tp.post_location_sum AS pregame_location_sum
            FROM current_games cg
            JOIN type_post_game tp
              ON tp.pitcher_id = cg.pitcher_id
             AND tp.pitcher_game_index < cg.pitcher_game_index
            QUALIFY row_number() OVER (
                PARTITION BY cg.game_pk, cg.pitcher_id, tp.pitch_type
                ORDER BY tp.pitcher_game_index DESC
            ) = 1
        ),
        prior_total AS (
            SELECT cg.game_pk AS current_game_pk, cg.pitcher_id,
                   pp.post_pitcher_pitch_n AS pregame_pitcher_pitches
            FROM current_games cg
            LEFT JOIN pitcher_post_game pp
              ON pp.pitcher_id = cg.pitcher_id
             AND pp.pitcher_game_index < cg.pitcher_game_index
            QUALIFY row_number() OVER (
                PARTITION BY cg.game_pk, cg.pitcher_id
                ORDER BY pp.pitcher_game_index DESC NULLS LAST
            ) = 1
        ),
        league_hand_type AS (
            SELECT pitcher_throws, pitch_type,
                   avg(observed_stuff_plus) AS league_stuff,
                   avg(observed_location_plus) AS league_location,
                   count(observed_stuff_plus) AS league_stuff_n,
                   count(observed_location_plus) AS league_location_n
            FROM history WHERE year = {int(league_year)} GROUP BY ALL
        ),
        league_type AS (
            SELECT pitch_type,
                   avg(observed_stuff_plus) AS league_stuff,
                   avg(observed_location_plus) AS league_location
            FROM history WHERE year = {int(league_year)} GROUP BY ALL
        ),
        league_all AS (
            SELECT avg(observed_stuff_plus) AS league_stuff,
                   avg(observed_location_plus) AS league_location
            FROM history WHERE year = {int(league_year)}
        ),
        decisions AS (
            SELECT decision_id, game_date, game_pk, at_bat_number, pitch_number,
                   pitcher_id, batter_id, catcher_id, pitcher_throws, batter_side,
                   balls, strikes, count_state, outs, base_state, inning,
                   pitcher_role, appearance_pitch_number,
                   target_pitch_type, target_pitch_family,
                   CAST(at_bat_number AS BIGINT) * 1000 + pitch_number AS decision_order
            FROM read_parquet('{_sql_path(warehouse)}')
        ),
        game_first_type AS (
            SELECT game_pk, pitcher_id, pitch_type,
                   min(decision_order) AS first_decision_order
            FROM history
            WHERE year = {int(target_year)}
            GROUP BY ALL
        ),
        candidate_keys AS (
            SELECT d.decision_id, pt.pitch_type AS candidate_pitch_type
            FROM decisions d
            JOIN prior_type pt
              ON pt.current_game_pk = d.game_pk AND pt.pitcher_id = d.pitcher_id
            UNION
            SELECT d.decision_id, gt.pitch_type
            FROM decisions d
            JOIN game_first_type gt
              ON gt.game_pk = d.game_pk AND gt.pitcher_id = d.pitcher_id
             AND gt.first_decision_order < d.decision_order
            UNION
            SELECT decision_id, target_pitch_type FROM decisions
        ),
        candidates AS (
            SELECT d.*, ck.candidate_pitch_type,
                   {_pitch_family('ck.candidate_pitch_type')} AS candidate_pitch_family,
                   ck.candidate_pitch_type = d.target_pitch_type AS is_chosen,
                   pt.pregame_type_pitches,
                   pt.pregame_stuff_pitches,
                   pt.pregame_stuff_sum,
                   pt.pregame_location_pitches,
                   pt.pregame_location_sum,
                   total.pregame_pitcher_pitches,
                   coalesce(lht.league_stuff, lt.league_stuff, la.league_stuff) AS league_stuff,
                   coalesce(lht.league_location, lt.league_location, la.league_location) AS league_location
            FROM candidate_keys ck
            JOIN decisions d USING (decision_id)
            LEFT JOIN prior_type pt
              ON pt.current_game_pk = d.game_pk AND pt.pitcher_id = d.pitcher_id
             AND pt.pitch_type = ck.candidate_pitch_type
            LEFT JOIN prior_total total
              ON total.current_game_pk = d.game_pk AND total.pitcher_id = d.pitcher_id
            LEFT JOIN league_hand_type lht
              ON lht.pitcher_throws = d.pitcher_throws AND lht.pitch_type = ck.candidate_pitch_type
            LEFT JOIN league_type lt ON lt.pitch_type = ck.candidate_pitch_type
            CROSS JOIN league_all la
        ),
        event_post AS (
            SELECT game_pk, pitcher_id, pitch_type, decision_order,
                   count(*) OVER outing_window AS post_outing_type_pitches,
                   count(observed_stuff_plus) OVER outing_window AS post_outing_stuff_pitches,
                   sum(observed_stuff_plus) OVER outing_window AS post_outing_stuff_sum,
                   count(observed_location_plus) OVER outing_window AS post_outing_location_pitches,
                   sum(observed_location_plus) OVER outing_window AS post_outing_location_sum
            FROM history
            WHERE year = {int(target_year)}
            WINDOW outing_window AS (
                PARTITION BY game_pk, pitcher_id, pitch_type
                ORDER BY decision_order
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        ),
        with_outing AS (
            SELECT c.*,
                   coalesce(e.post_outing_type_pitches, 0) AS outing_prior_type_pitches,
                   coalesce(e.post_outing_stuff_pitches, 0) AS outing_prior_stuff_pitches,
                   e.post_outing_stuff_sum AS outing_prior_stuff_sum,
                   coalesce(e.post_outing_location_pitches, 0) AS outing_prior_location_pitches,
                   e.post_outing_location_sum AS outing_prior_location_sum
            FROM candidates c
            ASOF LEFT JOIN event_post e
              ON c.game_pk = e.game_pk
             AND c.pitcher_id = e.pitcher_id
             AND c.candidate_pitch_type = e.pitch_type
             AND c.decision_order > e.decision_order
        ),
        baselines AS (
            SELECT *,
                (coalesce(pregame_stuff_sum, 0) + {k_base} * league_stuff)
                    / nullif(coalesce(pregame_stuff_pitches, 0) + {k_base}, 0) AS baseline_stuff_plus,
                (coalesce(pregame_location_sum, 0) + {k_base} * league_location)
                    / nullif(coalesce(pregame_location_pitches, 0) + {k_base}, 0) AS baseline_location_plus,
                outing_prior_stuff_sum / nullif(outing_prior_stuff_pitches, 0) AS outing_raw_stuff_plus,
                outing_prior_location_sum / nullif(outing_prior_location_pitches, 0) AS outing_raw_location_plus
            FROM with_outing
        ),
        observed AS (
            SELECT concat(CAST(year AS VARCHAR), ':', CAST(game_pk AS VARCHAR), ':',
                          CAST(at_bat_number AS VARCHAR), ':', CAST(pitch_number AS VARCHAR), ':',
                          CAST(pitcher_id AS VARCHAR)) AS decision_id,
                   observed_stuff_plus, observed_location_plus
            FROM history WHERE year = {int(target_year)}
        )
        SELECT
            b.decision_id, {int(target_year)}::INTEGER AS year, b.game_date, b.game_pk,
            b.at_bat_number, b.pitch_number, b.pitcher_id, b.batter_id, b.catcher_id,
            b.pitcher_throws, b.batter_side, b.pitcher_role,
            b.balls, b.strikes, b.count_state, {_count_tier('b.balls', 'b.strikes')} AS count_tier,
            b.outs, b.base_state, b.inning, b.appearance_pitch_number,
            b.target_pitch_type, b.target_pitch_family,
            b.candidate_pitch_type, b.candidate_pitch_family, b.is_chosen,
            CASE
                WHEN coalesce(b.pregame_type_pitches, 0) >= 20 THEN 'pitcher_type_supported'
                WHEN coalesce(b.pregame_type_pitches, 0) > 0 THEN 'pitcher_type_limited'
                WHEN b.is_chosen THEN 'chosen_novel_type_league_prior'
                ELSE 'league_type_prior'
            END AS weapon_backoff_level,
            coalesce(b.pregame_type_pitches, 0)::BIGINT AS pregame_type_pitches,
            coalesce(b.pregame_stuff_pitches, 0)::BIGINT AS pregame_stuff_pitches,
            coalesce(b.pregame_location_pitches, 0)::BIGINT AS pregame_location_pitches,
            coalesce(b.pregame_pitcher_pitches, 0)::BIGINT AS pregame_pitcher_pitches,
            b.baseline_stuff_plus, b.baseline_location_plus,
            b.outing_prior_type_pitches::BIGINT AS outing_prior_type_pitches,
            b.outing_prior_stuff_pitches::BIGINT AS outing_prior_stuff_pitches,
            b.outing_prior_location_pitches::BIGINT AS outing_prior_location_pitches,
            b.outing_raw_stuff_plus, b.outing_raw_location_plus,
            b.outing_prior_stuff_pitches / (b.outing_prior_stuff_pitches + {k_stuff}) AS outing_stuff_reliability,
            b.outing_prior_location_pitches / (b.outing_prior_location_pitches + {k_location}) AS outing_location_reliability,
            b.baseline_stuff_plus
                + b.outing_prior_stuff_pitches / (b.outing_prior_stuff_pitches + {k_stuff})
                  * (coalesce(b.outing_raw_stuff_plus, b.baseline_stuff_plus) - b.baseline_stuff_plus)
                AS weapon_stuff_plus,
            b.baseline_location_plus
                + b.outing_prior_location_pitches / (b.outing_prior_location_pitches + {k_location})
                  * (coalesce(b.outing_raw_location_plus, b.baseline_location_plus) - b.baseline_location_plus)
                AS weapon_location_plus,
            b.outing_prior_stuff_pitches / (b.outing_prior_stuff_pitches + {k_stuff})
                  * (coalesce(b.outing_raw_stuff_plus, b.baseline_stuff_plus) - b.baseline_stuff_plus)
                AS weapon_stuff_delta,
            b.outing_prior_location_pitches / (b.outing_prior_location_pitches + {k_location})
                  * (coalesce(b.outing_raw_location_plus, b.baseline_location_plus) - b.baseline_location_plus)
                AS weapon_location_delta,
            coalesce(b.pregame_type_pitches, 0) / nullif(b.pregame_pitcher_pitches, 0) AS pregame_usage_rate,
            b.outing_prior_type_pitches / nullif(b.appearance_pitch_number - 1, 0) AS outing_usage_rate,
            b.outing_prior_type_pitches / nullif(b.appearance_pitch_number - 1, 0)
                - coalesce(b.pregame_type_pitches, 0) / nullif(b.pregame_pitcher_pitches, 0)
                AS usage_rate_delta,
            CASE WHEN b.is_chosen THEN o.observed_stuff_plus END AS observed_chosen_stuff_plus,
            CASE WHEN b.is_chosen THEN o.observed_location_plus END AS observed_chosen_location_plus,
            'strictly_prior_game_and_prior_pitch_state; observed_columns_post_pitch_only' AS feature_time_scope
        FROM baselines b
        LEFT JOIN observed o USING (decision_id)
        ORDER BY b.game_date, b.game_pk, b.at_bat_number, b.pitch_number, b.candidate_pitch_type
    """


def _threat_history_sql(
    tables: dict[int, str],
    years: tuple[int, ...] = THREAT_HISTORY_YEARS,
) -> str:
    swing_events = (
        "'swinging_strike','swinging_strike_blocked','foul','foul_tip','foul_bunt',"
        "'hit_into_play','hit_into_play_no_out','hit_into_play_score','missed_bunt'"
    )
    whiff_events = "'swinging_strike','swinging_strike_blocked','missed_bunt'"
    parts = []
    for year in years:
        table = tables[year]
        parts.append(
            f"""
            SELECT
                CAST(batter AS BIGINT) AS batter_id,
                nullif(CAST(p_throws AS VARCHAR), '') AS pitcher_throws,
                {_count_tier()} AS count_tier,
                {_pitch_family()} AS pitch_family,
                CASE
                    WHEN zone IS NULL AND plate_x IS NULL THEN 'Unavailable'
                    WHEN zone IN (2, 5, 8) THEN 'Middle'
                    WHEN zone IN (1, 4, 7) THEN CASE WHEN stand = 'L' THEN 'Away' ELSE 'Inside' END
                    WHEN zone IN (3, 6, 9) THEN CASE WHEN stand = 'L' THEN 'Inside' ELSE 'Away' END
                    WHEN plate_x * CASE WHEN stand = 'L' THEN -1.0 ELSE 1.0 END < -0.83 / 3.0 THEN 'Inside'
                    WHEN plate_x * CASE WHEN stand = 'L' THEN -1.0 ELSE 1.0 END > 0.83 / 3.0 THEN 'Away'
                    ELSE 'Middle'
                END || '-' ||
                CASE
                    WHEN zone IS NULL AND (plate_z IS NULL OR sz_top IS NULL OR sz_bot IS NULL) THEN 'Unavailable'
                    WHEN zone IN (1, 2, 3) THEN 'High'
                    WHEN zone IN (4, 5, 6) THEN 'Middle'
                    WHEN zone IN (7, 8, 9) THEN 'Low'
                    WHEN (plate_z - sz_bot) / nullif(sz_top - sz_bot, 0) < 1.0 / 3.0 THEN 'Low'
                    WHEN (plate_z - sz_bot) / nullif(sz_top - sz_bot, 0) > 2.0 / 3.0 THEN 'High'
                    ELSE 'Middle'
                END AS location_bucket,
                lower(coalesce(CAST(description AS VARCHAR), '')) IN ({swing_events}) AS is_swing,
                lower(coalesce(CAST(description AS VARCHAR), '')) IN ({whiff_events}) AS is_whiff,
                CAST(delta_run_exp AS DOUBLE) AS batter_run_value
            FROM y{year}.{table}
            WHERE game_type = 'R' AND batter IS NOT NULL AND pitch_type IS NOT NULL
              AND p_throws IN ('L', 'R') AND balls IS NOT NULL AND strikes IS NOT NULL
            """
        )
    return " UNION ALL ".join(parts)


def _threat_surface_query(
    tables: dict[int, str],
    years: tuple[int, ...] = THREAT_HISTORY_YEARS,
) -> str:
    history = _threat_history_sql(tables, years)
    history_label = f"{min(years)}-{max(years)}"
    return f"""
        WITH history AS ({history}),
        batter_cells AS (
            SELECT batter_id, pitcher_throws, count_tier, pitch_family,
                   location_bucket,
                   count(*) AS pitches,
                   count(*) FILTER (WHERE is_swing) AS swings,
                   count(*) FILTER (WHERE is_whiff) AS whiffs,
                   count(batter_run_value) AS run_value_pitches,
                   sum(batter_run_value) AS run_value_sum
            FROM history
            WHERE location_bucket <> 'Unavailable-Unavailable'
            GROUP BY ALL
            UNION ALL
            SELECT batter_id, pitcher_throws, count_tier, pitch_family, 'All' AS location_bucket,
                   count(*) AS pitches,
                   count(*) FILTER (WHERE is_swing) AS swings,
                   count(*) FILTER (WHERE is_whiff) AS whiffs,
                   count(batter_run_value) AS run_value_pitches,
                   sum(batter_run_value) AS run_value_sum
            FROM history
            GROUP BY batter_id, pitcher_throws, count_tier, pitch_family
        ),
        league_cells AS (
            SELECT pitcher_throws, count_tier, pitch_family,
                   location_bucket,
                   count(*) AS league_pitches,
                   count(*) FILTER (WHERE is_swing) AS league_swings,
                   count(*) FILTER (WHERE is_whiff) AS league_whiffs,
                   count(batter_run_value) AS league_run_value_pitches,
                   avg(batter_run_value) AS league_run_value,
                   stddev_samp(batter_run_value) AS league_run_value_sd
            FROM history
            WHERE location_bucket <> 'Unavailable-Unavailable'
            GROUP BY ALL
            UNION ALL
            SELECT pitcher_throws, count_tier, pitch_family, 'All' AS location_bucket,
                   count(*) AS league_pitches,
                   count(*) FILTER (WHERE is_swing) AS league_swings,
                   count(*) FILTER (WHERE is_whiff) AS league_whiffs,
                   count(batter_run_value) AS league_run_value_pitches,
                   avg(batter_run_value) AS league_run_value,
                   stddev_samp(batter_run_value) AS league_run_value_sd
            FROM history
            GROUP BY pitcher_throws, count_tier, pitch_family
        ),
        joined AS (
            SELECT b.*, l.* EXCLUDE (pitcher_throws, count_tier, pitch_family, location_bucket),
                   (b.swings + {HUNT_PRIOR_PITCHES} * l.league_swings / nullif(l.league_pitches, 0))
                     / (b.pitches + {HUNT_PRIOR_PITCHES}) AS hunt_rate,
                   (b.whiffs + {WHIFF_PRIOR_SWINGS} * l.league_whiffs / nullif(l.league_swings, 0))
                     / (b.swings + {WHIFF_PRIOR_SWINGS}) AS whiff_per_swing,
                   (coalesce(b.run_value_sum, 0) + {DAMAGE_PRIOR_PITCHES} * l.league_run_value)
                     / (b.run_value_pitches + {DAMAGE_PRIOR_PITCHES}) AS damage_run_value_per_pitch
            FROM batter_cells b
            JOIN league_cells l USING (pitcher_throws, count_tier, pitch_family, location_bucket)
        ),
        scaled AS (
            SELECT *,
                   stddev_samp(damage_run_value_per_pitch) OVER (
                       PARTITION BY pitcher_throws, count_tier, pitch_family, location_bucket
                   ) AS context_batter_damage_sd,
                   stddev_samp(damage_run_value_per_pitch) OVER () AS global_batter_damage_sd
            FROM joined
        ),
        batter_output AS (
            SELECT 'batter' AS surface_level, batter_id, pitcher_throws, count_tier,
                   pitch_family, location_bucket, pitches, swings, whiffs, run_value_pitches,
                   pitches / (pitches + {DAMAGE_PRIOR_PITCHES}) AS sample_reliability,
                   CASE WHEN pitches >= 100 THEN 'high_support'
                        WHEN pitches >= 30 THEN 'limited_support' ELSE 'sparse' END AS support_level,
                   hunt_rate,
                   100.0 * hunt_rate / nullif(league_swings / league_pitches, 0) AS hunt_plus,
                   1.0 - whiff_per_swing AS contact_rate,
                   100.0 * (1.0 - whiff_per_swing)
                     / nullif(1.0 - league_whiffs / nullif(league_swings, 0), 0) AS contact_plus,
                   damage_run_value_per_pitch,
                   100.0 + 15.0 * (damage_run_value_per_pitch - league_run_value)
                     / coalesce(nullif(context_batter_damage_sd, 0), nullif(global_batter_damage_sd, 0)) AS damage_plus,
                   league_pitches, league_swings / league_pitches AS league_hunt_rate,
                   1.0 - league_whiffs / nullif(league_swings, 0) AS league_contact_rate,
                   league_run_value AS league_damage_run_value_per_pitch,
                   '{history_label}_only; safe_for_{max(years) + 1}_pre_pitch_use' AS feature_time_scope
            FROM scaled
        ),
        league_output AS (
            SELECT 'league' AS surface_level, NULL::BIGINT AS batter_id,
                   pitcher_throws, count_tier, pitch_family, location_bucket,
                   league_pitches AS pitches, league_swings AS swings, league_whiffs AS whiffs,
                   league_run_value_pitches AS run_value_pitches,
                   0.0 AS sample_reliability, 'league_fallback' AS support_level,
                   league_swings / league_pitches AS hunt_rate, 100.0 AS hunt_plus,
                   1.0 - league_whiffs / nullif(league_swings, 0) AS contact_rate, 100.0 AS contact_plus,
                   league_run_value AS damage_run_value_per_pitch, 100.0 AS damage_plus,
                   league_pitches, league_swings / league_pitches AS league_hunt_rate,
                   1.0 - league_whiffs / nullif(league_swings, 0) AS league_contact_rate,
                   league_run_value AS league_damage_run_value_per_pitch,
                   '{history_label}_league_fallback; safe_for_{max(years) + 1}_pre_pitch_use' AS feature_time_scope
            FROM league_cells
        )
        SELECT * FROM batter_output
        UNION ALL
        SELECT * FROM league_output
        ORDER BY surface_level, batter_id, pitcher_throws, count_tier, pitch_family, location_bucket
    """


def _copy_atomic(connection: duckdb.DuckDBPyConnection, query: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    if temporary.exists():
        temporary.unlink()
    connection.execute(
        f"COPY ({query}) TO '{_sql_path(temporary)}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    temporary.replace(output)


def _rows(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    return [
        {key: (_number(value) if isinstance(value, float) else value) for key, value in row.items()}
        for row in connection.execute(query).fetchdf().to_dict(orient="records")
    ]


def build_player_archetype_slice6ab(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    warehouse = slice4_warehouse_path(TEST_YEAR, root)
    location_db = root / "derived" / "location_plus_scores.duckdb"
    for source in (warehouse, location_db, cache_path(root)):
        if not source.exists():
            raise FileNotFoundError(source)

    candidates = slice6a_candidate_path(root)
    chosen = slice6a_chosen_path(root)
    surface = slice6b_surface_path(root)
    stuff_scores = _load_stuff_scores(root)

    with duckdb.connect() as connection:
        connection.execute("SET preserve_insertion_order = false")
        weapon_tables = _attach_years(connection, WEAPON_HISTORY_YEARS, root)
        connection.execute(f"ATTACH '{_sql_path(location_db)}' AS loc (READ_ONLY)")
        connection.register("stuff_scores", stuff_scores)
        _copy_atomic(connection, _weapon_candidate_query(warehouse, weapon_tables), candidates)
        _copy_atomic(
            connection,
            f"SELECT * FROM read_parquet('{_sql_path(candidates)}') WHERE is_chosen",
            chosen,
        )

    del stuff_scores

    with duckdb.connect() as connection:
        connection.execute("SET preserve_insertion_order = false")
        threat_tables = _attach_years(connection, THREAT_HISTORY_YEARS, root)
        _copy_atomic(connection, _threat_surface_query(threat_tables), surface)

    with duckdb.connect() as connection:
        candidate_path = _sql_path(candidates)
        chosen_path = _sql_path(chosen)
        surface_sql_path = _sql_path(surface)
        warehouse_path = _sql_path(warehouse)
        weapon_audit = connection.execute(
            f"""
            SELECT count(*) candidates,
                   count(DISTINCT decision_id) decisions,
                   count(*) FILTER (WHERE is_chosen) chosen_rows,
                   count(*) FILTER (WHERE outing_prior_type_pitches < 0
                                      OR outing_prior_type_pitches > appearance_pitch_number - 1) bad_prior_rows,
                   count(*) FILTER (WHERE observed_chosen_stuff_plus IS NOT NULL) observed_stuff_rows,
                   count(*) FILTER (WHERE observed_chosen_location_plus IS NOT NULL) observed_location_rows,
                   count(*) FILTER (WHERE weapon_stuff_plus IS NOT NULL) weapon_stuff_rows,
                   count(*) FILTER (WHERE weapon_location_plus IS NOT NULL) weapon_location_rows
            FROM read_parquet('{candidate_path}')
            """
        ).fetchone()
        warehouse_rows = connection.execute(
            f"SELECT count(*) FROM read_parquet('{warehouse_path}')"
        ).fetchone()[0]
        chosen_audit = connection.execute(
            f"""
            SELECT count(*) AS row_count, count(*) - count(DISTINCT decision_id) AS duplicates,
                   count(*) FILTER (WHERE target_pitch_type <> candidate_pitch_type) target_mismatch,
                   count(*) FILTER (WHERE outing_prior_type_pitches = 0) first_type_rows
            FROM read_parquet('{chosen_path}')
            """
        ).fetchone()
        support = _rows(
            connection,
            f"""
            SELECT weapon_backoff_level, count(*) AS row_count
            FROM read_parquet('{candidate_path}') GROUP BY 1 ORDER BY row_count DESC
            """,
        )
        threat_audit = connection.execute(
            f"""
            SELECT count(*) AS row_count,
                   count(*) FILTER (WHERE surface_level = 'batter') batter_rows,
                   count(*) FILTER (WHERE surface_level = 'league') league_rows,
                   count(*) FILTER (WHERE hunt_plus IS NULL OR contact_plus IS NULL OR damage_plus IS NULL) null_metric_rows,
                   count(*) FILTER (WHERE feature_time_scope NOT LIKE '2021-2025%') bad_time_scope_rows
            FROM read_parquet('{surface_sql_path}')
            """
        ).fetchone()
        threat_support = _rows(
            connection,
            f"""
            SELECT support_level, count(*) AS row_count
            FROM read_parquet('{surface_sql_path}')
            WHERE surface_level = 'batter' GROUP BY 1 ORDER BY row_count DESC
            """,
        )
        decision_threat_support = _rows(
            connection,
            f"""
            SELECT coalesce(s.support_level, 'league_fallback') AS support_level,
                   count(*) AS row_count
            FROM read_parquet('{candidate_path}') c
            LEFT JOIN read_parquet('{surface_sql_path}') s
              ON s.surface_level = 'batter'
             AND s.location_bucket = 'All'
             AND s.batter_id = c.batter_id
             AND s.pitcher_throws = c.pitcher_throws
             AND s.count_tier = c.count_tier
             AND s.pitch_family = c.candidate_pitch_family
            GROUP BY 1 ORDER BY row_count DESC
            """,
        )
        yamamoto = _rows(
            connection,
            f"""
            SELECT candidate_pitch_type, is_chosen, pregame_type_pitches,
                   round(baseline_stuff_plus, 2) baseline_stuff_plus,
                   round(outing_raw_stuff_plus, 2) outing_raw_stuff_plus,
                   round(weapon_stuff_plus, 2) weapon_stuff_plus,
                   round(weapon_stuff_delta, 2) weapon_stuff_delta,
                   round(baseline_location_plus, 2) baseline_location_plus,
                   round(outing_raw_location_plus, 2) outing_raw_location_plus,
                   round(weapon_location_plus, 2) weapon_location_plus,
                   round(weapon_location_delta, 2) weapon_location_delta,
                   outing_prior_type_pitches,
                   round(100 * pregame_usage_rate, 2) pregame_usage_pct,
                   round(100 * outing_usage_rate, 2) outing_usage_pct,
                   observed_chosen_stuff_plus, observed_chosen_location_plus
            FROM read_parquet('{candidate_path}')
            WHERE game_pk = 823926 AND pitcher_id = 808967
              AND batter_id = 543510 AND at_bat_number = 44 AND pitch_number = 2
            ORDER BY candidate_pitch_type
            """,
        )

    candidate_rows = int(weapon_audit[0])
    decision_rows = int(weapon_audit[1])
    chosen_rows = int(weapon_audit[2])
    release_ready = bool(
        decision_rows == int(warehouse_rows)
        and chosen_rows == int(warehouse_rows)
        and int(weapon_audit[3]) == 0
        and int(chosen_audit[1]) == 0
        and int(chosen_audit[2]) == 0
        and int(threat_audit[3]) == 0
        and int(threat_audit[4]) == 0
    )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "ready" if release_ready else "failed_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "test_year": TEST_YEAR,
            "weapon_history_years": list(WEAPON_HISTORY_YEARS),
            "threat_history_years": list(THREAT_HISTORY_YEARS),
            "slice5_retrained": False,
            "purpose": "Strictly prior pitcher weapon readiness and historical batter threat inputs for Slice 6 strategy research.",
        },
        "slice6a_weapon_contract": {
            "baseline": "Pitcher exact-pitch history from 2025 and earlier 2026 games, empirically shrunk toward the 2025 league pitch-type mean.",
            "outing_update": "Only earlier same-game pitches of that exact pitch type; target-pitch scores are observed outcome columns only.",
            "stuff_prior_pitches": OUTING_STUFF_PRIOR_PITCHES,
            "location_prior_pitches": OUTING_LOCATION_PRIOR_PITCHES,
            "candidate_rule": "Pitch types observed in prior games or earlier in the current game, plus the chosen type; a first-time chosen type is marked as league-prior and unsupported as a counterfactual.",
            "interpretation": "Stuff and Location remain separate. A positive state is current availability evidence, not proof of the optimal call.",
        },
        "slice6b_threat_contract": {
            "history_cutoff": "All regular-season pitches from 2021-2025; no 2026 outcomes.",
            "dimensions": ["batter", "pitcher hand", "count tier", "pitch family", "batter-relative 3x3 location or All"],
            "hunt": "Empirical-Bayes swing probability per pitch.",
            "contact": "Empirical-Bayes contact probability conditional on swing.",
            "damage": "Empirical-Bayes batter RE24 per pitch; Damage+ is context-standardized because run value can cross zero.",
            "plus_scale": "Hunt+ and Contact+ are league-ratio indices; Damage+ is league 100 with 15 points per standard deviation across shrunken batter estimates in the same context.",
            "pre_pitch_rule": "Only the All-location row is eligible before a target location is selected. Location cells are historical surfaces, not future observed locations.",
        },
        "audit": {
            "slice6a": {
                "candidate_rows": candidate_rows,
                "decision_rows": decision_rows,
                "warehouse_rows": int(warehouse_rows),
                "chosen_rows": chosen_rows,
                "bad_prior_rows": int(weapon_audit[3]),
                "chosen_observed_stuff_coverage": _number(int(weapon_audit[4]) / chosen_rows if chosen_rows else 0),
                "chosen_observed_location_coverage": _number(int(weapon_audit[5]) / chosen_rows if chosen_rows else 0),
                "weapon_stuff_coverage": _number(int(weapon_audit[6]) / candidate_rows if candidate_rows else 0),
                "weapon_location_coverage": _number(int(weapon_audit[7]) / candidate_rows if candidate_rows else 0),
                "chosen_duplicates": int(chosen_audit[1]),
                "chosen_target_mismatches": int(chosen_audit[2]),
                "chosen_first_type_rows": int(chosen_audit[3]),
                "backoff": support,
            },
            "slice6b": {
                "rows": int(threat_audit[0]),
                "batter_rows": int(threat_audit[1]),
                "league_rows": int(threat_audit[2]),
                "null_metric_rows": int(threat_audit[3]),
                "bad_time_scope_rows": int(threat_audit[4]),
                "support": threat_support,
                "decision_candidate_support": decision_threat_support,
            },
        },
        "case_823926_yamamoto_mccann_before_home_run": yamamoto,
        "release_gate": {
            "slice6a_ready": release_ready,
            "slice6b_ready": release_ready,
            "counterfactual_best_pitch_supported": False,
            "causal_claim_supported": False,
            "next_step": "Slice 6C must add overlap and propensity gates before comparing observed strategy value.",
        },
        "artifacts": {
            "weapon_candidates_2026": str(candidates),
            "weapon_candidates_2026_sha256": _sha256(candidates),
            "weapon_chosen_2026": str(chosen),
            "weapon_chosen_2026_sha256": _sha256(chosen),
            "batter_threat_surface": str(surface),
            "batter_threat_surface_sha256": _sha256(surface),
        },
    }
    slice6ab_contract_path(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return payload


def get_player_archetype_slice6ab(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(slice6ab_contract_path(data_dir).read_text(encoding="utf-8"))


def render_slice6ab_report(payload: dict[str, Any]) -> str:
    weapon = payload["audit"]["slice6a"]
    threat = payload["audit"]["slice6b"]
    lines = [
        "# Player Archetypes Slice 6A–6B — Weapon State and Batter Threat Surface",
        "",
        f"Contract: `{payload['contract_version']}`  ",
        f"Status: **{payload['status']}**  ",
        "",
        "## Slice 6A — Pitcher Weapon State",
        "",
        "- The pregame exact-pitch baseline uses 2025 plus earlier 2026 games and shrinks toward the 2025 league pitch-type mean.",
        "- The outing update uses only earlier pitches in the same game. Stuff+ and Location+ stay separate.",
        "- The chosen pitch's observed scores are outcome columns; they are never used to construct that pitch's pre-pitch state.",
        f"- {weapon['candidate_rows']:,} candidate rows cover {weapon['decision_rows']:,} decisions; chosen rows: {weapon['chosen_rows']:,}.",
        f"- Candidate-state coverage: Stuff {weapon['weapon_stuff_coverage']:.3%}, Location {weapon['weapon_location_coverage']:.3%}.",
        "",
        "## Slice 6B — Batter Threat Surface",
        "",
        "- The surface uses only 2021–2025 regular-season history and is safe for 2026 pre-pitch research.",
        "- Hunt is swing probability, Contact is contact conditional on swing, and Damage is batter RE24 per pitch.",
        "- Pre-pitch models may use the All-location row. The nine location cells describe historical attack zones and cannot reveal the future pitch location.",
        f"- Surface rows: {threat['rows']:,}; batter rows: {threat['batter_rows']:,}; league fallback rows: {threat['league_rows']:,}.",
        "",
        "## Yamamoto vs. McCann, game 823926, before the 1-0 home-run pitch",
        "",
        "| Type | Chosen | Prior N | Baseline Stuff+ | Outing Stuff+ | State delta | Baseline Loc+ | Outing Loc+ | State delta | Game usage |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["case_823926_yamamoto_mccann_before_home_run"]:
        lines.append(
            f"| {row['candidate_pitch_type']} | {row['is_chosen']} | {row['outing_prior_type_pitches']} | "
            f"{row['baseline_stuff_plus'] or 0:.2f} | {row['outing_raw_stuff_plus'] or 0:.2f} | "
            f"{row['weapon_stuff_delta'] or 0:.2f} | {row['baseline_location_plus'] or 0:.2f} | "
            f"{row['outing_raw_location_plus'] or 0:.2f} | {row['weapon_location_delta'] or 0:.2f} | "
            f"{row['outing_usage_pct'] or 0:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "These artifacts describe information available before a pitch and historical batter tendencies. They do not yet identify a factual best unthrown pitch. Slice 6C must enforce overlap, propensity, and uncertainty gates before alternative-value comparisons.",
            "",
        ]
    )
    return "\n".join(lines)
