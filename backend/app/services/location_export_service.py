"""Read batch Location+ exports for the Lab UI."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.api.schemas.location import LocationComparisonResponse, LocationComparisonSeries, LocationComparisonSlice, LocationLeaderboardResponse, LocationPitcherResponse
from app.core.config import settings


def _database_path():
    return settings.data_dir / "derived" / "location_plus_scores.duckdb"


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    return table in {row[0] for row in conn.execute("SHOW TABLES").fetchall()}


def _pitch_type_score_cte(table: str) -> str:
    return f"""
    canonical_pitch AS (
        SELECT pitcher_id,
               CASE
                   WHEN pitch_name = '4-Seam Fastball' THEN 'FA'
                   WHEN pitch_name = 'Sinker' THEN 'SI'
                   WHEN pitch_name = 'Cutter' THEN 'FC'
                   WHEN pitch_name = 'Split-Finger' THEN 'FS'
                   WHEN pitch_name IN ('Slider', 'Sweeper') THEN 'SL'
                   WHEN pitch_name = 'Curveball' THEN 'CU'
                   WHEN pitch_name = 'Changeup' THEN 'CH'
                   WHEN pitch_name = 'Knuckle Curve' THEN 'KC'
                   WHEN pitch_name = 'Forkball' THEN 'FO'
               END AS pitch_code,
               pitches, xrv_per_100, location_plus, called_strike_pct,
               whiff_pct, barrel_pct, ball_pct, location_plus_se
        FROM {table}
        WHERE pitch_name IN ('4-Seam Fastball', 'Sinker', 'Cutter', 'Split-Finger', 'Slider', 'Sweeper', 'Curveball', 'Changeup', 'Knuckle Curve', 'Forkball')
    ),
    pitch_scored AS (
        SELECT pitcher_id, pitch_code,
               CASE pitch_code
                   WHEN 'FA' THEN '4-Seam Fastball' WHEN 'SI' THEN 'Sinker'
                   WHEN 'FC' THEN 'Cutter' WHEN 'FS' THEN 'Split-Finger'
                   WHEN 'SL' THEN 'Slider / Sweeper' WHEN 'CU' THEN 'Curveball'
                   WHEN 'CH' THEN 'Changeup' WHEN 'KC' THEN 'Knuckle Curve'
                   WHEN 'FO' THEN 'Forkball'
               END AS pitch_name,
               SUM(pitches) AS pitches,
               SUM(xrv_per_100 * pitches) / SUM(pitches) AS xrv_per_100,
               SUM(location_plus * pitches) / SUM(pitches) AS location_plus,
               SUM(called_strike_pct * pitches) / SUM(pitches) AS called_strike_pct,
               SUM(whiff_pct * pitches) / SUM(pitches) AS whiff_pct,
               SUM(barrel_pct * pitches) / SUM(pitches) AS barrel_pct,
               SUM(ball_pct * pitches) / SUM(pitches) AS ball_pct,
               SQRT(SUM(POWER(location_plus_se * pitches, 2))) / SUM(pitches) AS location_plus_se,
               CASE WHEN SUM(pitches) >= 50 THEN 'qualified' ELSE 'provisional' END AS sample_status
        FROM canonical_pitch
        GROUP BY pitcher_id, pitch_code
    )
    """


def get_location_leaderboard(year: int, minimum_pitches: int = 300) -> LocationLeaderboardResponse:
    table = f"location_pitcher_scores_{int(year)}"
    path = _database_path()
    if not path.exists():
        raise FileNotFoundError("Location+ exports have not been generated")
    with duckdb.connect(str(path), read_only=True) as conn:
        if not _table_exists(conn, table):
            raise FileNotFoundError(f"Location+ export for {year} is not available")
        rows = conn.execute(
            f"""
            WITH {_pitch_type_score_cte(f'location_pitch_type_scores_{int(year)}')},
            pitch_wide AS (
                SELECT pitcher_id,
                       SUM(pitches) AS standard_pitches,
                       MAX(CASE WHEN pitch_code = 'FA' THEN location_plus END) AS loc_fa,
                       MAX(CASE WHEN pitch_code = 'SI' THEN location_plus END) AS loc_si,
                       MAX(CASE WHEN pitch_code = 'FC' THEN location_plus END) AS loc_fc,
                       MAX(CASE WHEN pitch_code = 'FS' THEN location_plus END) AS loc_fs,
                       MAX(CASE WHEN pitch_code = 'SL' THEN location_plus END) AS loc_sl,
                       MAX(CASE WHEN pitch_code = 'CU' THEN location_plus END) AS loc_cu,
                       MAX(CASE WHEN pitch_code = 'CH' THEN location_plus END) AS loc_ch,
                       MAX(CASE WHEN pitch_code = 'KC' THEN location_plus END) AS loc_kc,
                       MAX(CASE WHEN pitch_code = 'FO' THEN location_plus END) AS loc_fo
                FROM pitch_scored
                GROUP BY pitcher_id
            )
            SELECT ROW_NUMBER() OVER (ORDER BY location_plus DESC, pitches DESC) AS rank,
                   s.pitcher_id, s.pitcher_name, s.team, s.pitches,
                   ROUND(s.location_plus, 1) AS location_plus,
                   ROUND(s.xrv_per_100, 3) AS xrv_per_100,
                   ROUND(s.location_plus_vs_l, 1) AS location_plus_vs_l,
                   ROUND(s.location_plus_vs_r, 1) AS location_plus_vs_r,
                   ROUND(s.location_plus_se, 2) AS location_plus_se,
                   ROUND(s.reliability, 3) AS reliability,
                   s.sample_status,
                   ROUND(w.loc_fa, 1) AS loc_fa, ROUND(w.loc_si, 1) AS loc_si,
                   ROUND(w.loc_fc, 1) AS loc_fc, ROUND(w.loc_fs, 1) AS loc_fs,
                   ROUND(w.loc_sl, 1) AS loc_sl, ROUND(w.loc_cu, 1) AS loc_cu,
                   ROUND(w.loc_ch, 1) AS loc_ch, ROUND(w.loc_kc, 1) AS loc_kc,
                   ROUND(w.loc_fo, 1) AS loc_fo
            FROM {table} s
            LEFT JOIN pitch_wide w USING (pitcher_id)
            WHERE s.pitches >= ?
              AND w.standard_pitches > 0
            ORDER BY location_plus DESC, pitches DESC
            """,
            [int(minimum_pitches)],
        ).fetchdf()
        manifest = conn.execute(
            "SELECT model_version, generated_at FROM location_manifest WHERE year = ? LIMIT 1",
            [int(year)],
        ).fetchone()
    return LocationLeaderboardResponse(
        year=year,
        generated_at=str(manifest[1]) if manifest else None,
        model_version=str(manifest[0]) if manifest else "unknown",
        minimum_pitches=minimum_pitches,
        total_pitchers=len(rows),
        rows=rows.to_dict(orient="records"),
    )


def get_location_pitcher(year: int, pitcher_id: int, game_pk: int | None = None) -> LocationPitcherResponse:
    leaderboard_table = f"location_pitcher_scores_{int(year)}"
    pitch_table = f"location_pitch_type_scores_{int(year)}"
    outing_table = f"location_outing_scores_{int(year)}"
    outing_pitch_type_table = f"location_outing_pitch_type_scores_{int(year)}"
    path = _database_path()
    if not path.exists():
        raise FileNotFoundError("Location+ exports have not been generated")
    with duckdb.connect(str(path), read_only=True) as conn:
        for table in [leaderboard_table, pitch_table, outing_table, outing_pitch_type_table]:
            if not _table_exists(conn, table):
                raise FileNotFoundError(f"Location+ export for {year} is incomplete")
        pitcher = conn.execute(
            f"""
            SELECT 1 AS rank, pitcher_id, pitcher_name, team, pitches,
                   ROUND(location_plus, 1) AS location_plus,
                   ROUND(xrv_per_100, 3) AS xrv_per_100,
                   ROUND(location_plus_vs_l, 1) AS location_plus_vs_l,
                   ROUND(location_plus_vs_r, 1) AS location_plus_vs_r,
                   ROUND(location_plus_se, 2) AS location_plus_se,
                   ROUND(reliability, 3) AS reliability,
                   sample_status
            FROM {leaderboard_table}
            WHERE pitcher_id = ?
            """,
            [int(pitcher_id)],
        ).fetchdf()
        if pitcher.empty:
            raise FileNotFoundError("Pitcher Location+ score was not found")
        pitch_types = conn.execute(
            f"""
            WITH {_pitch_type_score_cte(pitch_table)}
            SELECT pitch_name, pitches, ROUND(location_plus, 1) AS location_plus,
                   ROUND(xrv_per_100, 3) AS xrv_per_100,
                   ROUND(called_strike_pct, 1) AS called_strike_pct,
                   ROUND(whiff_pct, 1) AS whiff_pct,
                   ROUND(barrel_pct, 1) AS barrel_pct,
                   ROUND(ball_pct, 1) AS ball_pct,
                   ROUND(location_plus_se, 2) AS location_plus_se,
                   sample_status
            FROM pitch_scored
            WHERE pitcher_id = ?
            ORDER BY pitches DESC
            """,
            [int(pitcher_id)],
        ).fetchdf()
        outing_filter = "AND game_pk = ?" if game_pk is not None else ""
        outing_limit = "" if game_pk is not None else "LIMIT 20"
        outing_params = [int(pitcher_id), int(game_pk)] if game_pk is not None else [int(pitcher_id)]
        outings = conn.execute(
            f"""
            SELECT game_pk, CAST(game_date AS VARCHAR) AS game_date, team, pitches,
                   ROUND(location_plus, 1) AS location_plus,
                   ROUND(xrv_per_100, 3) AS xrv_per_100,
                   ROUND(called_strike_pct, 1) AS called_strike_pct,
                   ROUND(whiff_pct, 1) AS whiff_pct,
                   ROUND(barrel_pct, 1) AS barrel_pct,
                   ROUND(location_plus_se, 2) AS location_plus_se
            FROM {outing_table}
            WHERE pitcher_id = ?
              {outing_filter}
            ORDER BY game_date DESC, game_pk DESC
            {outing_limit}
            """,
            outing_params,
        ).fetchdf()
        outing_pitch_types = pd.DataFrame()
        if game_pk is not None:
            outing_pitch_types = conn.execute(
                f"""
                SELECT pitch_name, pitches,
                       ROUND(location_plus, 1) AS location_plus,
                       ROUND(xrv_per_100, 3) AS xrv_per_100,
                       ROUND(called_strike_pct, 1) AS called_strike_pct,
                       ROUND(whiff_pct, 1) AS whiff_pct,
                       ROUND(barrel_pct, 1) AS barrel_pct,
                       ROUND(ball_pct, 1) AS ball_pct,
                       ROUND(location_plus_se, 2) AS location_plus_se,
                       sample_status
                FROM {outing_pitch_type_table}
                WHERE pitcher_id = ? AND game_pk = ?
                ORDER BY pitches DESC, pitch_name
                """,
                [int(pitcher_id), int(game_pk)],
            ).fetchdf()
    return LocationPitcherResponse(
        year=year,
        pitcher=pitcher.iloc[0].to_dict(),
        pitch_types=pitch_types.to_dict(orient="records"),
        outing_pitch_types=outing_pitch_types.to_dict(orient="records"),
        outings=outings.to_dict(orient="records"),
    )


def _comparison_slice(frame: pd.DataFrame, minimum_pitches: int) -> LocationComparisonSlice:
    sample = frame.loc[frame["pitches"] >= minimum_pitches].copy()
    ours = sample["location_plus"].to_numpy(dtype=float)
    reference = sample["fangraphs_location_plus"].to_numpy(dtype=float)
    regression = LinearRegression().fit(ours.reshape(-1, 1), reference)
    predicted = regression.predict(ours.reshape(-1, 1))
    return LocationComparisonSlice(
        minimum_pitches=minimum_pitches,
        matched_pitchers=len(sample),
        pearson_r=float(np.corrcoef(ours, reference)[0, 1]),
        spearman_rho=float(sample["location_plus"].corr(sample["fangraphs_location_plus"], method="spearman")),
        r_squared=float(r2_score(reference, predicted)),
        mae=float(mean_absolute_error(reference, ours)),
        rmse=float(np.sqrt(mean_squared_error(reference, ours))),
        slope=float(regression.coef_[0]),
        intercept=float(regression.intercept_),
    )


def _comparison_points(frame: pd.DataFrame, minimum_pitches: int) -> list[dict[str, object]]:
    return frame.loc[
        frame["pitches"] >= minimum_pitches,
        ["pitcher_id", "pitcher_name", "pitches", "location_plus", "fangraphs_location_plus"],
    ].rename(columns={"location_plus": "ours", "fangraphs_location_plus": "fangraphs"}).to_dict(orient="records")


def get_location_comparison(year: int, minimum_pitches: int = 100) -> LocationComparisonResponse:
    reference_path = settings.data_dir / f"{int(year)}_location_plus.csv"
    if not reference_path.exists():
        raise FileNotFoundError(f"FanGraphs Location+ CSV for {year} was not found")
    path = _database_path()
    table = f"location_pitcher_scores_{int(year)}"
    if not path.exists():
        raise FileNotFoundError("Location+ exports have not been generated")
    with duckdb.connect(str(path), read_only=True) as conn:
        if not _table_exists(conn, table):
            raise FileNotFoundError(f"Location+ export for {year} is not available")
        model = conn.execute(
            f"SELECT pitcher_id, pitcher_name, pitches, location_plus FROM {table}"
        ).fetchdf()
        pitch_table = f"location_pitch_type_scores_{int(year)}"
        if _table_exists(conn, pitch_table):
            model_pitch = conn.execute(
                f"WITH {_pitch_type_score_cte(pitch_table)} SELECT pitcher_id, pitch_code, pitches, location_plus FROM pitch_scored"
            ).fetchdf().merge(model[["pitcher_id", "pitcher_name"]], on="pitcher_id", how="left")
        else:
            model_pitch = pd.DataFrame(columns=["pitcher_id", "pitch_code", "pitches", "location_plus", "pitcher_name"])
    pitch_codes = ["FA", "SI", "FC", "FS", "SL", "CU", "CH", "KC", "FO"]
    reference_raw = pd.read_csv(reference_path)
    reference = reference_raw[["Name", "MLBAMID", "Location+"]].rename(
        columns={"MLBAMID": "pitcher_id", "Location+": "fangraphs_location_plus"}
    )
    matched = model.merge(reference, on="pitcher_id", how="inner").dropna(subset=["location_plus", "fangraphs_location_plus"])
    thresholds = [0, 100, 300, 500]
    if minimum_pitches not in thresholds:
        thresholds.append(int(minimum_pitches))
    slices = [_comparison_slice(matched, threshold) for threshold in sorted(set(thresholds))]
    active = next(item for item in slices if item.minimum_pitches == minimum_pitches)
    points = _comparison_points(matched, minimum_pitches)
    series = [LocationComparisonSeries(key="overall", label="Overall", statistics=active, points=points)]
    labels = {"FA": "4-Seam", "SI": "Sinker", "FC": "Cutter", "FS": "Splitter", "SL": "Slider / Sweeper", "CU": "Curveball", "CH": "Changeup", "KC": "Knuckle Curve", "FO": "Forkball"}
    for code in pitch_codes:
        if f"Loc+ {code}" not in reference_raw.columns:
            continue
        pitch_reference = reference_raw[["MLBAMID", f"Loc+ {code}"]].rename(
            columns={"MLBAMID": "pitcher_id", f"Loc+ {code}": "fangraphs_location_plus"}
        )
        pitch_matched = model_pitch.loc[model_pitch["pitch_code"] == code].merge(pitch_reference, on="pitcher_id", how="inner").dropna(subset=["location_plus", "fangraphs_location_plus"])
        if len(pitch_matched.loc[pitch_matched["pitches"] >= 50]) < 20:
            continue
        statistics = _comparison_slice(pitch_matched, 50)
        series.append(LocationComparisonSeries(key=code.lower(), label=labels[code], statistics=statistics, points=_comparison_points(pitch_matched, 50)))
    return LocationComparisonResponse(
        year=year,
        fangraphs_rows=len(reference),
        model_rows=len(model),
        matched_pitchers=len(matched),
        recommended_minimum_pitches=100,
        active=active,
        sensitivity=slices,
        points=points,
        series=series,
    )
