from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table

WPA_CALIBRATION_VERSION = "fangraphs_2025_component_holdout_v1"
POSITIVE_PITCHER_WPA_SCALE = 0.936080
NEGATIVE_PITCHER_WPA_SCALE = 1.030875


def calibrated_pitcher_wpa_sql(expression: str) -> str:
    return (
        f"CASE WHEN ({expression}) >= 0 THEN ({expression}) * {POSITIVE_PITCHER_WPA_SCALE} "
        f"ELSE ({expression}) * {NEGATIVE_PITCHER_WPA_SCALE} END"
    )


def calibrate_pitcher_wpa(values: pd.Series | np.ndarray | float) -> pd.Series | np.ndarray | float:
    return np.where(
        np.asarray(values) >= 0,
        np.asarray(values) * POSITIVE_PITCHER_WPA_SCALE,
        np.asarray(values) * NEGATIVE_PITCHER_WPA_SCALE,
    )


def plate_appearance_wpa_ctes(source_table: str) -> str:
    """Return shared CTEs for WPA measured from one PA boundary to the next."""
    return f"""
        wpa_pa AS (
            SELECT
                game_pk,
                at_bat_number,
                arg_min(try_cast(home_win_exp AS DOUBLE), pitch_number) AS pre_home_we,
                arg_max(try_cast(post_home_score AS DOUBLE), pitch_number) AS final_home_score,
                arg_max(try_cast(post_away_score AS DOUBLE), pitch_number) AS final_away_score
            FROM {source_table}
            WHERE game_type = 'R'
              AND home_win_exp IS NOT NULL
              AND game_pk IS NOT NULL
              AND at_bat_number IS NOT NULL
            GROUP BY game_pk, at_bat_number
        ),
        wpa_ordered AS (
            SELECT
                *,
                lead(pre_home_we) OVER (
                    PARTITION BY game_pk ORDER BY at_bat_number
                ) AS next_home_we
            FROM wpa_pa
        ),
        wpa_values AS (
            SELECT
                game_pk,
                at_bat_number,
                coalesce(
                    next_home_we,
                    CASE
                        WHEN final_home_score > final_away_score THEN 1.0
                        WHEN final_home_score < final_away_score THEN 0.0
                        ELSE NULL
                    END
                ) - pre_home_we AS pa_home_wpa
            FROM wpa_ordered
        )
    """


@lru_cache(maxsize=4)
def _cached_plate_appearance_wpa(db_path_value: str, modified_at: int) -> pd.DataFrame:
    del modified_at
    db_path = Path(db_path_value)
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame(columns=["game_pk", "at_bat_number", "pa_home_wpa"])
        return conn.execute(
            f"""
            WITH {plate_appearance_wpa_ctes(source_table)}
            SELECT game_pk, at_bat_number, pa_home_wpa
            FROM wpa_values
            """
        ).fetchdf()


def load_plate_appearance_wpa(year: int, data_dir: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return pd.DataFrame(columns=["game_pk", "at_bat_number", "pa_home_wpa"])
    return _cached_plate_appearance_wpa(str(db_path.resolve()), db_path.stat().st_mtime_ns)


def attach_plate_appearance_wpa(data: pd.DataFrame, year: int, data_dir: Path) -> pd.DataFrame:
    working = data.copy()
    if working.empty or not {"game_pk", "at_bat_number"}.issubset(working.columns):
        working["pa_home_wpa"] = np.nan
        return working
    values = load_plate_appearance_wpa(year, data_dir)
    working = working.drop(columns=["pa_home_wpa", "pitcher_wpa", "batter_wpa"], errors="ignore")
    working = working.merge(values, on=["game_pk", "at_bat_number"], how="left")
    if "pitcher_team" not in working.columns and {"inning_topbot", "home_team", "away_team"}.issubset(working.columns):
        working["pitcher_team"] = np.where(
            working["inning_topbot"].astype(str).str.lower().eq("top"), working["home_team"], working["away_team"]
        )
    if {"pitcher_team", "home_team"}.issubset(working.columns):
        raw_pitcher_wpa = np.where(
            working["pitcher_team"].eq(working["home_team"]), working["pa_home_wpa"], -working["pa_home_wpa"]
        )
        working["pitcher_wpa"] = calibrate_pitcher_wpa(raw_pitcher_wpa)
    if "offense_team" not in working.columns and {"inning_topbot", "home_team", "away_team"}.issubset(working.columns):
        working["offense_team"] = np.where(
            working["inning_topbot"].astype(str).str.lower().eq("top"), working["away_team"], working["home_team"]
        )
    if {"offense_team", "home_team"}.issubset(working.columns):
        raw_batter_wpa = np.where(
            working["offense_team"].eq(working["home_team"]), working["pa_home_wpa"], -working["pa_home_wpa"]
        )
        working["batter_wpa"] = -calibrate_pitcher_wpa(-raw_batter_wpa)
    return working


def one_wpa_value_per_pa(data: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(data.get(column), errors="coerce")
    if data.empty or not {"game_pk", "at_bat_number"}.issubset(data.columns):
        return values
    duplicate = data.duplicated(["game_pk", "at_bat_number"])
    return values.mask(duplicate, 0.0)
