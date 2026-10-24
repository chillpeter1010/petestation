from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.performance_state_v2_service import _position_player_ids


CONTRACT_VERSION = "player_archetype_slice1_warehouse_v1"
YEARS = tuple(range(2021, 2027))
SWINGS = (
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "foul_bunt",
    "missed_bunt",
)
WHIFFS = ("swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt")
STRIKES = (
    "called_strike",
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "missed_bunt",
    "automatic_strike",
)

PITCHER_NORMALIZED_FEATURES = (
    "fastball_usage_eb",
    "breaking_usage_eb",
    "offspeed_usage_eb",
    "fastball_velocity",
    "fastball_spin",
    "fastball_horizontal_break",
    "fastball_vertical_break",
    "breaking_movement_inches",
    "release_extension",
    "release_pos_x",
    "release_pos_z",
    "arm_angle",
    "zone_pct_eb",
    "chase_pct_eb",
    "whiff_pct_eb",
    "first_pitch_strike_pct_eb",
    "season_stuff_plus",
    "season_location_plus",
    "season_pitching_plus",
    "per_pitch_stuff_plus",
    "per_pitch_location_plus",
)

BATTER_NORMALIZED_FEATURES = (
    "zone_swing_pct_eb",
    "chase_pct_eb",
    "contact_pct_eb",
    "first_pitch_swing_pct_eb",
    "hard_hit_pct_eb",
    "barrel_pct_eb",
    "avg_exit_velocity",
    "avg_launch_angle",
    "avg_bat_speed",
    "avg_swing_length",
    "avg_attack_angle",
    "avg_attack_direction",
    "avg_swing_path_tilt",
    "woba",
    "fastball_woba",
    "breaking_woba",
    "offspeed_woba",
    "woba_vs_lhp",
    "woba_vs_rhp",
)


def pitcher_warehouse_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_pitcher_seasons_v1.parquet"


def batter_warehouse_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_batter_seasons_v1.parquet"


def warehouse_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice1_warehouse.json"


def warehouse_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _family_case() -> str:
    return """
        CASE
            WHEN upper(pitch_type) IN ('FF', 'FA', 'SI', 'FC') THEN 'Fastball'
            WHEN upper(pitch_type) IN ('SL', 'ST', 'CU', 'KC', 'SV') THEN 'Breaking'
            WHEN upper(pitch_type) IN ('CH', 'FS', 'FO') THEN 'Offspeed'
            ELSE NULL
        END
    """


def _display_name(value: object) -> str:
    text = str(value or "").strip()
    if "," not in text:
        return text
    last, first = (part.strip() for part in text.split(",", 1))
    return f"{first} {last}".strip()


def _pitcher_year(year: int, root: Path) -> pd.DataFrame:
    path = get_season_duckdb_path(year, root)
    with duckdb.connect(str(path), read_only=True) as connection:
        frame = connection.execute(
            f"""
            WITH base AS (
                SELECT {year} AS year,
                       cast(pitcher AS BIGINT) AS player_id,
                       game_pk,
                       game_date,
                       coalesce(nullif(pitcher_team, ''),
                           CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END) AS team,
                       player_name,
                       p_throws,
                       stand,
                       inning,
                       at_bat_number,
                       pitch_number,
                       upper(pitch_type) AS pitch_type,
                       {_family_case()} AS pitch_family,
                       lower(coalesce(description, '')) AS description,
                       upper(coalesce(type, '')) AS result_type,
                       balls,
                       strikes,
                       release_speed,
                       release_spin_rate,
                       pfx_x,
                       pfx_z,
                       release_extension,
                       release_pos_x,
                       release_pos_z,
                       arm_angle,
                       plate_x,
                       plate_z,
                       min(coalesce(inning, 99) * 1000000 + coalesce(at_bat_number, 9999) * 100 + coalesce(pitch_number, 99))
                           OVER (PARTITION BY pitcher, game_pk) AS first_sequence
                FROM pitches
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND game_pk IS NOT NULL
            ),
            classified AS (
                SELECT *,
                       CASE WHEN first_sequence = min(first_sequence) OVER (PARTITION BY game_pk, team)
                            THEN 'SP' ELSE 'RP' END AS role
                FROM base
            ),
            sequenced AS (
                SELECT *,
                       lag(pitch_family) OVER (
                           PARTITION BY player_id, game_pk ORDER BY inning, at_bat_number, pitch_number
                       ) AS previous_family
                FROM classified
            ),
            appearance AS (
                SELECT player_id, game_pk, role,
                       count(*) AS appearance_pitches,
                       count(DISTINCT at_bat_number) AS batters_faced
                FROM sequenced
                GROUP BY player_id, game_pk, role
            ),
            appearance_summary AS (
                SELECT player_id, role,
                       count(*) AS appearances,
                       max(appearance_pitches) AS max_appearance_pitches,
                       avg(appearance_pitches) AS avg_appearance_pitches,
                       count(*) FILTER (WHERE role = 'SP' AND appearance_pitches < 45 AND batters_faced <= 12) AS opener_like_appearances,
                       count(*) FILTER (WHERE role = 'SP' AND (appearance_pitches >= 70 OR batters_faced >= 18)) AS traditional_start_appearances,
                       count(*) FILTER (WHERE role = 'SP' AND NOT (appearance_pitches < 45 AND batters_faced <= 12)
                           AND NOT (appearance_pitches >= 70 OR batters_faced >= 18)) AS short_start_appearances,
                       count(*) FILTER (WHERE role = 'RP' AND (appearance_pitches >= 40 OR batters_faced >= 12)) AS bulk_relief_appearances
                FROM appearance
                GROUP BY player_id, role
            ),
            pitch_type_counts AS (
                SELECT player_id, role, pitch_type, count(*) AS pitch_type_pitches,
                       row_number() OVER (PARTITION BY player_id, role ORDER BY count(*) DESC, pitch_type) AS pitch_type_rank
                FROM sequenced
                WHERE pitch_type IS NOT NULL
                GROUP BY player_id, role, pitch_type
            ),
            dominant AS (
                SELECT player_id, role, pitch_type AS dominant_pitch_type, pitch_type_pitches AS dominant_pitch_pitches
                FROM pitch_type_counts WHERE pitch_type_rank = 1
            ),
            pitch_summary AS (
                SELECT {year} AS year, player_id, role,
                       mode(player_name) AS player_name,
                       mode(team) AS team,
                       mode(p_throws) AS throws,
                       min(game_date) AS first_game_date,
                       max(game_date) AS last_game_date,
                       count(*) AS pitches,
                       count(DISTINCT pitch_type) AS pitch_type_count,
                       count(*) FILTER (WHERE pitch_family = 'Fastball') AS fastball_pitches,
                       count(*) FILTER (WHERE pitch_family = 'Breaking') AS breaking_pitches,
                       count(*) FILTER (WHERE pitch_family = 'Offspeed') AS offspeed_pitches,
                       avg(release_speed) FILTER (WHERE pitch_family = 'Fastball') AS fastball_velocity,
                       stddev_samp(release_speed) FILTER (WHERE pitch_family = 'Fastball') AS fastball_velocity_sd,
                       avg(release_spin_rate) FILTER (WHERE pitch_family = 'Fastball') AS fastball_spin,
                       avg(pfx_x * 12) FILTER (WHERE pitch_family = 'Fastball') AS fastball_horizontal_break,
                       avg(pfx_z * 12) FILTER (WHERE pitch_family = 'Fastball') AS fastball_vertical_break,
                       avg(sqrt(pfx_x * pfx_x + pfx_z * pfx_z) * 12) FILTER (WHERE pitch_family = 'Breaking') AS breaking_movement_inches,
                       avg(release_extension) AS release_extension,
                       avg(release_pos_x) AS release_pos_x,
                       avg(release_pos_z) AS release_pos_z,
                       avg(arm_angle) AS arm_angle,
                       count(arm_angle) AS arm_angle_pitches,
                       count(*) FILTER (WHERE plate_x IS NOT NULL AND plate_z IS NOT NULL) AS valid_location_pitches,
                       count(*) FILTER (WHERE plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5) AS zone_pitches,
                       count(*) FILTER (WHERE plate_x IS NOT NULL AND plate_z IS NOT NULL
                           AND NOT (plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5)) AS outside_pitches,
                       count(*) FILTER (WHERE description IN ({_values(SWINGS)})) AS swings,
                       count(*) FILTER (WHERE description IN ({_values(WHIFFS)})) AS whiffs,
                       count(*) FILTER (WHERE description IN ({_values(SWINGS)}) AND plate_x IS NOT NULL AND plate_z IS NOT NULL
                           AND NOT (plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5)) AS chase_swings,
                       count(*) FILTER (WHERE balls = 0 AND strikes = 0) AS first_pitches,
                       count(*) FILTER (WHERE balls = 0 AND strikes = 0
                           AND (result_type = 'S' OR description IN ({_values(STRIKES)}))) AS first_pitch_strikes,
                       count(*) FILTER (WHERE stand = 'L') AS pitches_vs_lhb,
                       count(*) FILTER (WHERE previous_family IS NOT NULL) AS transition_opportunities,
                       count(*) FILTER (WHERE previous_family = pitch_family AND pitch_family IS NOT NULL) AS same_family_repeats
                FROM sequenced
                GROUP BY player_id, role
            )
            SELECT p.*, a.appearances, a.max_appearance_pitches, a.avg_appearance_pitches,
                   a.opener_like_appearances, a.traditional_start_appearances,
                   a.short_start_appearances, a.bulk_relief_appearances,
                   d.dominant_pitch_type, d.dominant_pitch_pitches
            FROM pitch_summary p
            JOIN appearance_summary a USING (player_id, role)
            LEFT JOIN dominant d USING (player_id, role)
            ORDER BY player_id, role
            """
        ).fetchdf()
    return frame


def _batter_year(year: int, root: Path) -> pd.DataFrame:
    path = get_season_duckdb_path(year, root)
    with duckdb.connect(str(path), read_only=True) as connection:
        frame = connection.execute(
            f"""
            WITH base AS (
                SELECT {year} AS year,
                       cast(batter AS BIGINT) AS player_id,
                       game_pk,
                       game_date,
                       at_bat_number,
                       coalesce(nullif(batter_team, ''), offense_team) AS team,
                       stand,
                       p_throws,
                       balls,
                       strikes,
                       {_family_case()} AS pitch_family,
                       lower(coalesce(description, '')) AS description,
                       events,
                       plate_x,
                       plate_z,
                       launch_speed,
                       launch_angle,
                       launch_speed_angle,
                       bat_speed,
                       swing_length,
                       attack_angle,
                       attack_direction,
                       swing_path_tilt,
                       woba_value,
                       woba_denom
                FROM pitches
                WHERE game_type = 'R' AND batter IS NOT NULL AND game_pk IS NOT NULL
            ),
            summary AS (
                SELECT {year} AS year, player_id,
                       mode(team) AS team,
                       mode(stand) AS bats,
                       min(game_date) AS first_game_date,
                       max(game_date) AS last_game_date,
                       count(*) AS pitches_seen,
                       count(DISTINCT (game_pk, at_bat_number)) AS plate_appearances,
                       count(*) FILTER (WHERE plate_x IS NOT NULL AND plate_z IS NOT NULL
                           AND plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5) AS zone_pitches,
                       count(*) FILTER (WHERE description IN ({_values(SWINGS)}) AND plate_x IS NOT NULL AND plate_z IS NOT NULL
                           AND plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5) AS zone_swings,
                       count(*) FILTER (WHERE plate_x IS NOT NULL AND plate_z IS NOT NULL
                           AND NOT (plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5)) AS outside_pitches,
                       count(*) FILTER (WHERE description IN ({_values(SWINGS)}) AND plate_x IS NOT NULL AND plate_z IS NOT NULL
                           AND NOT (plate_x BETWEEN -0.83 AND 0.83 AND plate_z BETWEEN 1.5 AND 3.5)) AS chase_swings,
                       count(*) FILTER (WHERE description IN ({_values(SWINGS)})) AS swings,
                       count(*) FILTER (WHERE description IN ({_values(WHIFFS)})) AS whiffs,
                       count(*) FILTER (WHERE balls = 0 AND strikes = 0) AS first_pitches,
                       count(*) FILTER (WHERE balls = 0 AND strikes = 0 AND description IN ({_values(SWINGS)})) AS first_pitch_swings,
                       count(*) FILTER (WHERE launch_speed IS NOT NULL) AS tracked_batted_balls,
                       count(*) FILTER (WHERE launch_speed >= 95) AS hard_hit_balls,
                       count(*) FILTER (WHERE launch_speed_angle = 6) AS barrels,
                       avg(launch_speed) AS avg_exit_velocity,
                       avg(launch_angle) AS avg_launch_angle,
                       count(bat_speed) AS tracked_swings,
                       avg(bat_speed) AS avg_bat_speed,
                       avg(swing_length) AS avg_swing_length,
                       avg(attack_angle) AS avg_attack_angle,
                       avg(attack_direction) AS avg_attack_direction,
                       avg(swing_path_tilt) AS avg_swing_path_tilt,
                       sum(woba_value) FILTER (WHERE coalesce(woba_denom, 0) > 0) AS woba_sum,
                       sum(woba_denom) FILTER (WHERE coalesce(woba_denom, 0) > 0) AS woba_pa,
                       sum(woba_value) FILTER (WHERE pitch_family = 'Fastball' AND coalesce(woba_denom, 0) > 0) AS fastball_woba_sum,
                       sum(woba_denom) FILTER (WHERE pitch_family = 'Fastball' AND coalesce(woba_denom, 0) > 0) AS fastball_woba_pa,
                       sum(woba_value) FILTER (WHERE pitch_family = 'Breaking' AND coalesce(woba_denom, 0) > 0) AS breaking_woba_sum,
                       sum(woba_denom) FILTER (WHERE pitch_family = 'Breaking' AND coalesce(woba_denom, 0) > 0) AS breaking_woba_pa,
                       sum(woba_value) FILTER (WHERE pitch_family = 'Offspeed' AND coalesce(woba_denom, 0) > 0) AS offspeed_woba_sum,
                       sum(woba_denom) FILTER (WHERE pitch_family = 'Offspeed' AND coalesce(woba_denom, 0) > 0) AS offspeed_woba_pa,
                       sum(woba_value) FILTER (WHERE p_throws = 'L' AND coalesce(woba_denom, 0) > 0) AS woba_vs_lhp_sum,
                       sum(woba_denom) FILTER (WHERE p_throws = 'L' AND coalesce(woba_denom, 0) > 0) AS woba_vs_lhp_pa,
                       sum(woba_value) FILTER (WHERE p_throws = 'R' AND coalesce(woba_denom, 0) > 0) AS woba_vs_rhp_sum,
                       sum(woba_denom) FILTER (WHERE p_throws = 'R' AND coalesce(woba_denom, 0) > 0) AS woba_vs_rhp_pa
                FROM base
                GROUP BY player_id
            )
            SELECT s.*, m.player_name
            FROM summary s
            LEFT JOIN player_master m ON s.player_id = m.player_id
            ORDER BY s.player_id
            """
        ).fetchdf()
    return frame


def _add_rate(frame: pd.DataFrame, numerator: str, denominator: str, output: str, groups: list[str], prior: float) -> None:
    denominator_values = pd.to_numeric(frame[denominator], errors="coerce").fillna(0.0)
    numerator_values = pd.to_numeric(frame[numerator], errors="coerce").fillna(0.0)
    frame[output.replace("_eb", "_raw")] = np.where(
        denominator_values.gt(0), numerator_values / denominator_values * 100.0, np.nan
    )
    group_success = frame.groupby(groups, dropna=False)[numerator].transform("sum")
    group_trials = frame.groupby(groups, dropna=False)[denominator].transform("sum")
    league_rate = group_success.div(group_trials.replace(0, np.nan)).fillna(0.0)
    frame[output] = (numerator_values + league_rate * prior).div(denominator_values + prior) * 100.0
    frame[f"{output}_reliability"] = denominator_values.div(denominator_values + prior)


def _add_group_zscores(
    frame: pd.DataFrame,
    features: tuple[str, ...],
    groups: list[str],
    reference_mask: pd.Series,
) -> None:
    for feature in features:
        values = pd.to_numeric(frame[feature], errors="coerce")
        grouped = values.where(reference_mask).groupby([frame[group] for group in groups], dropna=False)
        means = grouped.transform("mean")
        scales = grouped.transform("std").replace(0, np.nan)
        frame[f"z_{feature}"] = (values - means) / scales


def _add_pitcher_derived(frame: pd.DataFrame, root: Path) -> pd.DataFrame:
    output = frame.copy()
    for numerator, denominator, target, prior in (
        ("fastball_pitches", "pitches", "fastball_usage_eb", 100.0),
        ("breaking_pitches", "pitches", "breaking_usage_eb", 100.0),
        ("offspeed_pitches", "pitches", "offspeed_usage_eb", 100.0),
        ("zone_pitches", "valid_location_pitches", "zone_pct_eb", 100.0),
        ("chase_swings", "outside_pitches", "chase_pct_eb", 100.0),
        ("whiffs", "swings", "whiff_pct_eb", 100.0),
        ("first_pitch_strikes", "first_pitches", "first_pitch_strike_pct_eb", 50.0),
        ("pitches_vs_lhb", "pitches", "pitches_vs_lhb_pct_eb", 100.0),
        ("same_family_repeats", "transition_opportunities", "same_family_repeat_pct_eb", 100.0),
    ):
        _add_rate(output, numerator, denominator, target, ["year", "role"], prior)
    output["dominant_pitch_usage_pct"] = output["dominant_pitch_pitches"].div(output["pitches"]) * 100.0
    output["arm_angle_coverage_pct"] = output["arm_angle_pitches"].div(output["pitches"]) * 100.0
    output["opener_like_share_pct"] = np.where(
        output["role"].eq("SP"), output["opener_like_appearances"].div(output["appearances"]) * 100.0, 0.0
    )

    plus_rows = []
    for year in YEARS:
        path = root / "stuff+" / f"{year}_pitcher_stuff.csv"
        plus = pd.read_csv(path, low_memory=False)
        plus_rows.append(
            pd.DataFrame(
                {
                    "year": year,
                    "player_id": pd.to_numeric(plus["MLBAMID"], errors="coerce"),
                    "season_stuff_plus": pd.to_numeric(plus["Stuff+"], errors="coerce"),
                    "season_location_plus": pd.to_numeric(plus["Location+"], errors="coerce"),
                    "season_pitching_plus": pd.to_numeric(plus["Pitching+"], errors="coerce"),
                }
            ).dropna(subset=["player_id"])
        )
    plus_frame = pd.concat(plus_rows, ignore_index=True)
    plus_frame["player_id"] = plus_frame["player_id"].astype("int64")
    output = output.merge(plus_frame, on=["year", "player_id"], how="left", validate="many_to_one")

    per_pitch_rows = []
    for year in range(2023, 2027):
        path = root / "derived" / f"stamina_lab_{year}.parquet"
        with duckdb.connect() as connection:
            scored = connection.execute(
                """SELECT ? AS year, cast(pitcher AS BIGINT) AS player_id, appearance_role AS role,
                          avg(pitch_stuff_plus) AS per_pitch_stuff_plus,
                          count(pitch_stuff_plus) AS per_pitch_stuff_pitches,
                          avg(location_plus_pitch) AS per_pitch_location_plus,
                          count(location_plus_pitch) AS per_pitch_location_pitches
                   FROM read_parquet(?) GROUP BY pitcher, appearance_role""",
                [year, str(path)],
            ).fetchdf()
        per_pitch_rows.append(scored)
    per_pitch = pd.concat(per_pitch_rows, ignore_index=True)
    output = output.merge(per_pitch, on=["year", "player_id", "role"], how="left", validate="one_to_one")
    output["per_pitch_stuff_coverage_pct"] = output["per_pitch_stuff_pitches"].div(output["pitches"]) * 100.0
    output["per_pitch_location_coverage_pct"] = output["per_pitch_location_pitches"].div(output["pitches"]) * 100.0

    season_totals = output.groupby(["year", "player_id"])["pitches"].transform("sum")
    output["role_pitch_share_pct"] = output["pitches"].div(season_totals) * 100.0
    role_counts = output.groupby(["year", "player_id"])["role"].transform("nunique")
    output["hybrid_role"] = role_counts.gt(1)
    output["sample_reliability"] = output["pitches"].div(output["pitches"] + 200.0)
    output["sample_status"] = np.select(
        [output["pitches"].ge(500), output["pitches"].ge(100)],
        ["high_support", "qualified"],
        default="provisional",
    )
    output["archetype_eligible"] = output["pitches"].ge(100)

    emergency_flags: list[bool] = []
    position_flags: list[bool] = []
    position_by_year = {year: _position_player_ids(year, root)[0] for year in YEARS}
    season_appearances = output.groupby(["year", "player_id"])["appearances"].transform("sum")
    season_max = output.groupby(["year", "player_id"])["max_appearance_pitches"].transform("max")
    for row, season_pitches, appearances, max_pitches in zip(
        output.itertuples(index=False), season_totals, season_appearances, season_max, strict=True
    ):
        position = int(row.player_id) in position_by_year[int(row.year)]
        position_flags.append(position)
        emergency_flags.append(bool(position and season_pitches < 60 and appearances <= 4 and max_pitches <= 40))
    output["appeared_as_position_player"] = position_flags
    output["low_volume_position_player_pitching"] = emergency_flags
    output.loc[output["low_volume_position_player_pitching"], "archetype_eligible"] = False

    output["season_plus_available"] = output["season_stuff_plus"].notna() & output["season_location_plus"].notna()
    output["per_pitch_plus_available"] = output["per_pitch_stuff_plus"].notna() & output["per_pitch_location_plus"].notna()
    output["season_plus_scope"] = "full_season_not_role_specific"
    output["per_pitch_plus_scope"] = "full_season_role_specific"
    output["arm_angle_missing_flag"] = output["arm_angle_coverage_pct"].lt(70.0)
    output["feature_time_scope"] = "full_season_descriptive"
    output["display_name"] = output["player_name"].map(_display_name)
    _add_group_zscores(
        output,
        PITCHER_NORMALIZED_FEATURES,
        ["year", "role", "throws"],
        output["archetype_eligible"],
    )
    return output.sort_values(["year", "player_id", "role"], kind="stable").reset_index(drop=True)


def _add_batter_derived(frame: pd.DataFrame, root: Path) -> pd.DataFrame:
    output = frame.copy()
    output["contacts"] = output["swings"] - output["whiffs"]
    for numerator, denominator, target, prior in (
        ("zone_swings", "zone_pitches", "zone_swing_pct_eb", 100.0),
        ("chase_swings", "outside_pitches", "chase_pct_eb", 100.0),
        ("contacts", "swings", "contact_pct_eb", 100.0),
        ("first_pitch_swings", "first_pitches", "first_pitch_swing_pct_eb", 50.0),
        ("hard_hit_balls", "tracked_batted_balls", "hard_hit_pct_eb", 50.0),
        ("barrels", "tracked_batted_balls", "barrel_pct_eb", 50.0),
    ):
        _add_rate(output, numerator, denominator, target, ["year"], prior)
    for prefix in ("", "fastball_", "breaking_", "offspeed_", "woba_vs_lhp_", "woba_vs_rhp_"):
        if prefix.startswith("woba_vs"):
            stem = prefix.removesuffix("_")
            output[stem] = output[f"{stem}_sum"].div(output[f"{stem}_pa"].replace(0, np.nan))
        else:
            target = "woba" if not prefix else f"{prefix}woba"
            output[target] = output[f"{prefix}woba_sum"].div(output[f"{prefix}woba_pa"].replace(0, np.nan))
    output["swing_shape_coverage_pct"] = output["tracked_swings"].div(output["swings"].replace(0, np.nan)) * 100.0
    output["sample_reliability"] = output["plate_appearances"].div(output["plate_appearances"] + 100.0)
    output["sample_status"] = np.select(
        [output["plate_appearances"].ge(300), output["plate_appearances"].ge(100)],
        ["high_support", "qualified"],
        default="provisional",
    )
    output["archetype_eligible"] = output["plate_appearances"].ge(100)
    position_by_year = {year: _position_player_ids(year, root)[0] for year in YEARS}
    output["appeared_as_position_player"] = [
        int(row.player_id) in position_by_year[int(row.year)] for row in output.itertuples(index=False)
    ]
    pitcher_ids: dict[int, set[int]] = {}
    for year in YEARS:
        with duckdb.connect(str(get_season_duckdb_path(year, root)), read_only=True) as connection:
            pitcher_ids[year] = {int(row[0]) for row in connection.execute(
                "SELECT DISTINCT pitcher FROM pitches WHERE game_type = 'R' AND pitcher IS NOT NULL"
            ).fetchall()}
    output["pure_pitcher_batting_flag"] = [
        int(row.player_id) in pitcher_ids[int(row.year)]
        and not bool(row.appeared_as_position_player)
        and int(row.plate_appearances) < 100
        for row in output.itertuples(index=False)
    ]
    output.loc[output["pure_pitcher_batting_flag"], "archetype_eligible"] = False
    output["swing_shape_available"] = output["swing_shape_coverage_pct"].ge(70.0)
    output["feature_time_scope"] = "full_season_descriptive"
    output["display_name"] = output["player_name"].map(_display_name)
    _add_group_zscores(
        output,
        BATTER_NORMALIZED_FEATURES,
        ["year", "bats"],
        output["archetype_eligible"],
    )
    return output.sort_values(["year", "player_id"], kind="stable").reset_index(drop=True)


def _write_parquet(frame: pd.DataFrame, path: Path, relation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation, frame)
        connection.execute(f"COPY {relation} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)])
        connection.unregister(relation)
    temporary.replace(path)


def _audit(pitchers: pd.DataFrame, batters: pd.DataFrame) -> dict[str, Any]:
    years = []
    for year in YEARS:
        pitcher_year = pitchers[pitchers["year"].eq(year)]
        batter_year = batters[batters["year"].eq(year)]
        years.append(
            {
                "year": year,
                "pitcher_rows": int(len(pitcher_year)),
                "pitchers": int(pitcher_year["player_id"].nunique()),
                "qualified_pitcher_rows": int(pitcher_year["archetype_eligible"].sum()),
                "hybrid_pitchers": int(pitcher_year.loc[pitcher_year["hybrid_role"], "player_id"].nunique()),
                "opener_like_appearances": int(pitcher_year["opener_like_appearances"].sum()),
                "position_player_pitcher_rows": int(pitcher_year["low_volume_position_player_pitching"].sum()),
                "season_plus_rows": int(pitcher_year["season_plus_available"].sum()),
                "per_pitch_plus_rows": int(pitcher_year["per_pitch_plus_available"].sum()),
                "arm_angle_missing_rows": int(pitcher_year["arm_angle_missing_flag"].sum()),
                "batter_rows": int(len(batter_year)),
                "qualified_batters": int(batter_year["archetype_eligible"].sum()),
                "pure_pitcher_batting_rows": int(batter_year["pure_pitcher_batting_flag"].sum()),
                "swing_shape_available_rows": int(batter_year["swing_shape_available"].sum()),
            }
        )
    return {
        "pitcher_duplicate_keys": int(pitchers.duplicated(["year", "player_id", "role"]).sum()),
        "batter_duplicate_keys": int(batters.duplicated(["year", "player_id"]).sum()),
        "pitcher_rows": int(len(pitchers)),
        "batter_rows": int(len(batters)),
        "years": years,
    }


def build_player_archetype_warehouses(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    pitchers = _add_pitcher_derived(pd.concat([_pitcher_year(year, root) for year in YEARS], ignore_index=True), root)
    batters = _add_batter_derived(pd.concat([_batter_year(year, root) for year in YEARS], ignore_index=True), root)
    _write_parquet(pitchers, pitcher_warehouse_path(root), "pitcher_warehouse")
    _write_parquet(batters, batter_warehouse_path(root), "batter_warehouse")
    audit = _audit(pitchers, batters)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if not audit["pitcher_duplicate_keys"] and not audit["batter_duplicate_keys"] else "invalid",
        "publication_status": "research_only",
        "scope": {"years": list(YEARS), "game_type": "R", "pitcher_key": ["year", "player_id", "role"], "batter_key": ["year", "player_id"]},
        "artifacts": {"pitcher": str(pitcher_warehouse_path(root)), "batter": str(batter_warehouse_path(root))},
        "artifact_fingerprints": {
            "pitcher_sha256": _sha256(pitcher_warehouse_path(root)),
            "batter_sha256": _sha256(batter_warehouse_path(root)),
        },
        "rules": {
            "plus_sources": "season_* Plus is full-season CSV and distinct from per_pitch_* Plus from the current Stamina cache; neither fills the other",
            "role": "first fielding-team pitcher is SP; opener-like is separately flagged as <45 pitches and <=12 batters faced",
            "hybrid": "a pitcher with both SP and RP rows retains both identities and role pitch share",
            "missingness": "no feature imputation; availability flags are audit fields and are excluded from normalized style features",
            "pitcher_support": "100 role pitches for qualified, 500 for high support; low-volume position-player pitching is ineligible",
            "batter_support": "100 PA for qualified, 300 for high support; sub-100-PA pure pitcher batting is ineligible",
            "shrinkage": "rate features use transparent league-by-year and role empirical-Bayes priors while preserving raw numerator and denominator",
            "normalization": "pitchers standardized within year x role x throwing hand; batters within year x batting side",
            "time_scope": "all rows are full-season descriptive and cannot be used as same-season pre-pitch beliefs",
        },
        "normalized_feature_columns": {"pitcher": [f"z_{name}" for name in PITCHER_NORMALIZED_FEATURES], "batter": [f"z_{name}" for name in BATTER_NORMALIZED_FEATURES]},
        "audit": audit,
        "warnings": [
            "Opener-like is a workload heuristic, not an official roster role.",
            "Season Plus repeats across a pitcher's SP/RP rows because the source is not role-specific; role models must use the source flag.",
            "Swing-shape missingness reflects tracking availability and is never converted to an average-looking player.",
            "The warehouse is an input to Slice 2; no tags or cluster identities are emitted here.",
        ],
    }
    contract = warehouse_contract_path(root)
    temporary = contract.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(contract)
    return payload


def get_player_archetype_warehouse_contract(data_dir: Path | None = None) -> dict[str, Any]:
    path = warehouse_contract_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Player archetype Slice 1 contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def render_warehouse_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Player Archetypes & Pitch Strategy · Slice 1 Warehouse",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Warehouse audit",
        "",
        "| Year | Pitcher role rows | Eligible | Hybrid pitchers | Opener appearances | Per-pitch Plus rows | Batter rows | Eligible batters | Swing-shape available |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["audit"]["years"]:
        lines.append(
            f"| {row['year']} | {row['pitcher_rows']:,} | {row['qualified_pitcher_rows']:,} | {row['hybrid_pitchers']:,} | {row['opener_like_appearances']:,} | {row['per_pitch_plus_rows']:,} | {row['batter_rows']:,} | {row['qualified_batters']:,} | {row['swing_shape_available_rows']:,} |"
        )
    lines.extend(
        [
            "",
            f"Pitcher duplicate keys: **{payload['audit']['pitcher_duplicate_keys']}**  ",
            f"Batter duplicate keys: **{payload['audit']['batter_duplicate_keys']}**",
            "",
            "## Frozen rules",
            "",
            *[f"- **{key}**: {value}" for key, value in payload["rules"].items()],
            "",
            "## Warnings",
            "",
            *[f"- {warning}" for warning in payload["warnings"]],
            "",
        ]
    )
    return "\n".join(lines)
