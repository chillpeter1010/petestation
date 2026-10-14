from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.leverage import LeverageScenarioRequest, LeverageStateInput
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.wpa_service import WPA_CALIBRATION_VERSION, calibrate_pitcher_wpa


MODEL_VERSION = f"pete_empirical_li_v2_pa_boundary_{WPA_CALIBRATION_VERSION}"
SUPPORTED_YEARS = {2025, 2026}
REFERENCE_COLUMNS = {
    "WPA": "wpa", "-WPA": "negative_wpa", "+WPA": "positive_wpa", "RE24": "re24", "REW": "rew",
    "pLI": "pli", "inLI": "inli", "gmLI": "gmli", "exLI": "exli", "Pulls": "pulls", "WPA/LI": "wpa_li",
    "Clutch": "clutch", "SD": "shutdowns", "MD": "meltdowns",
}


def _stamp(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _reference_path(year: int) -> Path:
    return settings.data_dir / "Reliever" / f"{int(year)}_reliever_wpa.csv"


def _state_key(frame: pd.DataFrame) -> pd.Series:
    inning = pd.to_numeric(frame["inning"], errors="coerce").fillna(1).clip(1, 20).astype(int)
    half = frame["inning_topbot"].fillna("Top").astype(str)
    score = pd.to_numeric(frame["score_diff"], errors="coerce").fillna(0).clip(-10, 10).astype(int)
    outs = pd.to_numeric(frame["outs"], errors="coerce").fillna(0).clip(0, 2).astype(int)
    bases = pd.to_numeric(frame["base_state"], errors="coerce").fillna(0).clip(0, 7).astype(int)
    return inning.astype(str) + "|" + half + "|" + score.astype(str) + "|" + outs.astype(str) + "|" + bases.astype(str)


def _prepare_plate_appearances(year: int) -> tuple[pd.DataFrame, str | None]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"Pitch database not found for {year}.")
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        if not source:
            raise FileNotFoundError(f"Pitch table not found for {year}.")
        frame = conn.execute(
            f"""
            WITH base AS (
                SELECT
                    game_pk, CAST(game_date AS DATE) AS game_date, pitcher, player_name, pitcher_team, home_team,
                    inning, inning_topbot, at_bat_number, pitch_number,
                    outs_when_up AS outs,
                    (CASE WHEN on_1b IS NULL THEN 0 ELSE 1 END
                     + CASE WHEN on_2b IS NULL THEN 0 ELSE 2 END
                     + CASE WHEN on_3b IS NULL THEN 0 ELSE 4 END) AS base_state,
                    CASE WHEN inning_topbot = 'Top' THEN home_score - away_score ELSE away_score - home_score END AS score_diff,
                    home_win_exp,
                    CASE WHEN inning_topbot = 'Top' THEN home_win_exp ELSE 1 - home_win_exp END AS fielding_we,
                    CASE WHEN inning_topbot = 'Top' THEN away_score ELSE home_score END AS bat_score,
                    CASE WHEN inning_topbot = 'Top' THEN post_away_score ELSE post_home_score END AS post_bat_score,
                    post_home_score, post_away_score,
                    delta_pitcher_run_exp,
                    CAST(at_bat_number AS BIGINT) * 1000 + CAST(pitch_number AS BIGINT) AS pitch_seq
                FROM {source}
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND pitcher_team IS NOT NULL
            ),
            pitcher_games AS (
                SELECT game_pk, pitcher_team, pitcher, MIN(pitch_seq) AS pitcher_first_seq
                FROM base GROUP BY 1, 2, 3
            ),
            team_games AS (
                SELECT game_pk, pitcher_team, MIN(pitch_seq) AS team_first_seq
                FROM base GROUP BY 1, 2
            ),
            pa_rows AS (
            SELECT
                b.game_pk, MIN(b.game_date) AS game_date, b.pitcher, ANY_VALUE(b.player_name) AS player_name,
                b.pitcher_team, ANY_VALUE(b.home_team) AS home_team, b.at_bat_number,
                ARG_MIN(b.inning, b.pitch_number) AS inning,
                ARG_MIN(b.inning_topbot, b.pitch_number) AS inning_topbot,
                ARG_MIN(b.outs, b.pitch_number) AS outs,
                ARG_MIN(b.base_state, b.pitch_number) AS base_state,
                ARG_MIN(b.score_diff, b.pitch_number) AS score_diff,
                ARG_MIN(b.fielding_we, b.pitch_number) AS fielding_we,
                ARG_MIN(b.home_win_exp, b.pitch_number) AS pre_home_we,
                ARG_MIN(b.bat_score, b.pitch_number) AS bat_score,
                ARG_MAX(b.post_bat_score, b.pitch_number) AS post_bat_score,
                ARG_MAX(b.post_home_score, b.pitch_number) AS final_home_score,
                ARG_MAX(b.post_away_score, b.pitch_number) AS final_away_score,
                SUM(b.delta_pitcher_run_exp) AS pa_re24,
                pg.pitcher_first_seq > tg.team_first_seq AS is_reliever,
                MIN(b.pitch_seq) AS pa_seq
            FROM base b
            JOIN pitcher_games pg USING (game_pk, pitcher_team, pitcher)
            JOIN team_games tg USING (game_pk, pitcher_team)
            GROUP BY b.game_pk, b.pitcher, b.pitcher_team, b.at_bat_number, pg.pitcher_first_seq, tg.team_first_seq
            ),
            pa_with_next AS (
                SELECT *, lead(pre_home_we) OVER (PARTITION BY game_pk ORDER BY pa_seq) AS next_home_we
                FROM pa_rows
            )
            SELECT
                * EXCLUDE (pre_home_we, next_home_we, final_home_score, final_away_score, home_team),
                CASE WHEN pitcher_team = home_team THEN 1 ELSE -1 END * (
                    coalesce(
                        next_home_we,
                        CASE
                            WHEN final_home_score > final_away_score THEN 1.0
                            WHEN final_home_score < final_away_score THEN 0.0
                            ELSE NULL
                        END
                    ) - pre_home_we
                ) AS pa_wpa
            FROM pa_with_next
            ORDER BY game_date, game_pk, pa_seq
            """
        ).fetchdf()
    data_as_of = frame["game_date"].max().strftime("%Y-%m-%d") if not frame.empty else None
    return frame, data_as_of


def _reference_rows(year: int) -> pd.DataFrame:
    path = _reference_path(year)
    if not path.exists():
        raise FileNotFoundError(f"Reliever WPA reference not found for {year}.")
    frame = pd.read_csv(path, low_memory=False).rename(columns=REFERENCE_COLUMNS)
    frame["player_id"] = pd.to_numeric(frame.get("MLBAMID"), errors="coerce")
    frame = frame.dropna(subset=["player_id"]).copy()
    frame["player_id"] = frame["player_id"].astype(int)
    frame["name"] = frame.get("Name", frame["player_id"].astype(str)).astype(str)
    frame["team"] = frame.get("Team", "-").fillna("-").astype(str)
    for column in REFERENCE_COLUMNS.values():
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _nearest_state_row(states: pd.DataFrame, inning: int, half: str, score_diff: int, outs: int, base_state: int) -> pd.Series:
    if states.empty:
        raise ValueError("No leverage states are available.")
    exact = states[
        states["inning"].eq(inning) & states["inning_topbot"].eq(half) & states["score_diff"].eq(score_diff)
        & states["outs"].eq(outs) & states["base_state"].eq(base_state)
    ]
    if not exact.empty:
        return exact.iloc[0]
    candidates = states.copy()
    candidates["distance"] = (
        (candidates["inning"] - inning).abs()
        + (candidates["score_diff"] - score_diff).abs() * 2
        + (candidates["outs"] - outs).abs() * 2
        + candidates["inning_topbot"].ne(half).astype(int) * 2
        + candidates["base_state"].ne(base_state).astype(int)
    )
    return candidates.sort_values(["distance", "samples"], ascending=[True, False]).iloc[0]


def _build_bundle(year: int) -> dict[str, Any]:
    pa, data_as_of = _prepare_plate_appearances(year)
    if pa.empty:
        raise ValueError(f"No regular-season pitch data found for {year}.")
    numeric_columns = ["inning", "outs", "base_state", "score_diff", "fielding_we", "bat_score", "post_bat_score", "pa_wpa", "pa_re24"]
    for column in numeric_columns:
        pa[column] = pd.to_numeric(pa[column], errors="coerce")
    pa["pa_wpa"] = calibrate_pitcher_wpa(pa["pa_wpa"])
    pa["inning"] = pa["inning"].clip(1, 20).astype(int)
    pa["outs"] = pa["outs"].clip(0, 2).astype(int)
    pa["base_state"] = pa["base_state"].clip(0, 7).astype(int)
    pa["score_diff"] = pa["score_diff"].clip(-10, 10).astype(int)
    pa["state_key"] = _state_key(pa)

    global_abs_wpa = float(pa["pa_wpa"].abs().mean()) or 1.0
    states = (
        pa.groupby(["state_key", "inning", "inning_topbot", "score_diff", "outs", "base_state"], as_index=False)
        .agg(samples=("pa_wpa", "size"), win_expectancy=("fielding_we", "mean"), mean_abs_wpa=("pa_wpa", lambda value: value.abs().mean()))
    )
    states["li"] = (states["mean_abs_wpa"] / global_abs_wpa).clip(0, 10)
    state_li = states.set_index("state_key")["li"]
    pa["li"] = pa["state_key"].map(state_li).fillna(1.0)

    half_end = pa.groupby(["game_pk", "inning", "inning_topbot"], as_index=False)["post_bat_score"].max().rename(columns={"post_bat_score": "inning_end_score"})
    pa = pa.merge(half_end, on=["game_pk", "inning", "inning_topbot"], how="left")
    pa["runs_remaining"] = (pa["inning_end_score"] - pa["bat_score"]).clip(lower=0)
    run_states = pa.groupby(["outs", "base_state"], as_index=False).agg(samples=("runs_remaining", "size"), run_expectancy=("runs_remaining", "mean"))

    relief = pa[pa["is_reliever"].fillna(False)].copy()
    relief["positive_wpa"] = relief["pa_wpa"].clip(lower=0)
    relief["negative_wpa"] = relief["pa_wpa"].clip(upper=0)
    relief["wpa_li_event"] = relief["pa_wpa"] / relief["li"].replace(0, np.nan)

    appearance_keys = ["pitcher", "pitcher_team", "game_pk"]
    appearances = (
        relief.groupby(appearance_keys, as_index=False)
        .agg(game_date=("game_date", "min"), first_seq=("pa_seq", "min"), game_wpa=("pa_wpa", "sum"), gmli=("li", "first"))
        .sort_values(["game_pk", "pitcher_team", "first_seq"])
    )
    appearances["next_gmli"] = appearances.groupby(["game_pk", "pitcher_team"])["gmli"].shift(-1)
    appearances["pull"] = appearances["next_gmli"].notna().astype(int)
    appearances["shutdown"] = appearances["game_wpa"].ge(0.06).astype(int)
    appearances["meltdown"] = appearances["game_wpa"].le(-0.06).astype(int)

    inning_entries = relief.sort_values("pa_seq").drop_duplicates(["pitcher", "pitcher_team", "game_pk", "inning"], keep="first")
    inning_li = inning_entries.groupby("pitcher", as_index=False)["li"].mean().rename(columns={"li": "inli"})
    appearance_summary = appearances.groupby("pitcher", as_index=False).agg(
        appearances=("game_pk", "size"), gmli=("gmli", "mean"), exli=("next_gmli", "mean"), pulls=("pull", "sum"),
        shutdowns=("shutdown", "sum"), meltdowns=("meltdown", "sum"),
    )
    latest_teams = appearances.sort_values(["game_date", "first_seq"]).drop_duplicates("pitcher", keep="last")[["pitcher", "pitcher_team"]]
    local = relief.groupby("pitcher", as_index=False).agg(
        wpa=("pa_wpa", "sum"), negative_wpa=("negative_wpa", "sum"), positive_wpa=("positive_wpa", "sum"),
        re24=("pa_re24", "sum"), pli=("li", "mean"), wpa_li=("wpa_li_event", "sum"),
    )
    local = local.merge(appearance_summary, on="pitcher", how="left").merge(inning_li, on="pitcher", how="left").merge(latest_teams, on="pitcher", how="left")
    reference = _reference_rows(year)
    run_ratios = (reference["re24"] / reference["rew"]).replace([np.inf, -np.inf], np.nan).dropna()
    run_ratios = run_ratios[run_ratios.abs().between(7, 13)]
    runs_per_win = float(run_ratios.abs().median()) if not run_ratios.empty else 9.5
    local["rew"] = local["re24"] / runs_per_win
    local["clutch"] = local["wpa"] / local["pli"].replace(0, np.nan) - local["wpa_li"]
    local = local.rename(columns={"pitcher": "player_id", "pitcher_team": "team"})
    names = reference[["player_id", "name", "team"]].rename(columns={"team": "reference_team"})
    local = local.merge(names, on="player_id", how="left")
    local["name"] = local["name"].fillna(local["player_id"].astype(str))
    local["team"] = local["reference_team"].fillna(local["team"]).fillna("-")
    local = local.drop(columns=["reference_team"])
    return {
        "states": states,
        "run_states": run_states,
        "local": local,
        "reference": reference,
        "data_as_of": data_as_of,
        "runs_per_win": runs_per_win,
    }


@lru_cache(maxsize=4)
def _cached_bundle(year: int, _db_stamp: int, _reference_stamp: int) -> dict[str, Any]:
    return _build_bundle(year)


def _bundle(year: int) -> dict[str, Any]:
    year = int(year)
    if year not in SUPPORTED_YEARS:
        raise ValueError("Leverage Lab currently supports 2025 and 2026.")
    db_path = get_season_duckdb_path(year, settings.data_dir)
    reference_path = _reference_path(year)
    return _cached_bundle(year, _stamp(db_path), _stamp(reference_path))


def _clean(value: Any, digits: int = 3) -> float | int | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return round(float(numeric), digits)


def _leaderboard_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    ranked = frame.sort_values(["wpa", "re24"], ascending=[False, False]).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for index, row in ranked.iterrows():
        rows.append({
            "rank": index + 1, "player_id": int(row["player_id"]), "name": str(row.get("name") or row["player_id"]),
            "team": str(row.get("team") or "-"), "appearances": int(row["appearances"]) if pd.notna(row.get("appearances")) else None,
            **{key: _clean(row.get(key), 3) for key in ["wpa", "negative_wpa", "positive_wpa", "re24", "rew", "pli", "inli", "gmli", "exli", "wpa_li", "clutch"]},
            "pulls": int(row["pulls"]) if pd.notna(row.get("pulls")) else None,
            "shutdowns": int(row["shutdowns"]) if pd.notna(row.get("shutdowns")) else None,
            "meltdowns": int(row["meltdowns"]) if pd.notna(row.get("meltdowns")) else None,
        })
    return rows


def _validation(local: pd.DataFrame, reference: pd.DataFrame) -> list[dict[str, Any]]:
    joined = local.merge(reference, on="player_id", suffixes=("_estimated", "_reference"))
    rows: list[dict[str, Any]] = []
    for metric in [
        "wpa", "negative_wpa", "positive_wpa", "re24", "pli", "inli", "gmli", "exli", "pulls",
        "wpa_li", "clutch", "shutdowns", "meltdowns",
    ]:
        x = pd.to_numeric(joined.get(f"{metric}_estimated"), errors="coerce")
        y = pd.to_numeric(joined.get(f"{metric}_reference"), errors="coerce")
        valid = x.notna() & y.notna()
        x = x[valid].astype(float)
        y = y[valid].astype(float)
        if len(x) < 3:
            continue
        slope, intercept = np.polyfit(x, y, 1)
        prediction = slope * x + intercept
        residual = x - y
        correlation = float(x.corr(y))
        rows.append({
            "metric": metric, "samples": int(len(x)), "correlation": _clean(correlation), "r_squared": _clean(correlation ** 2),
            "mae": _clean(residual.abs().mean()), "rmse": _clean(np.sqrt(np.mean(residual ** 2))), "bias": _clean(residual.mean()),
            "slope": _clean(slope), "intercept": _clean(intercept),
        })
    return rows


def get_leverage_overview(year: int) -> dict[str, Any]:
    bundle = _bundle(year)
    raw_reference = bundle["reference"].copy()
    relief_ids = set(bundle["local"]["player_id"].astype(int))
    reference = raw_reference[raw_reference["player_id"].isin(relief_ids)].copy()
    reference["appearances"] = pd.NA
    warnings = [
        "Local Estimate uses PA-boundary Statcast states with a fixed 2025 component calibration; it is comparable with, but not identical to, FanGraphs WPA and LI.",
    ]
    if int(year) == 2026:
        warnings.append("The local pitch store and the collected reference may have different cutoff dates; counting-stat validation is provisional.")
    excluded_reference_rows = len(raw_reference) - len(reference)
    if excluded_reference_rows:
        warnings.append(
            f"Excluded {excluded_reference_rows} reference players with no local relief appearance; mixed-role reference rows may still include starter innings."
        )
    return {
        "year": int(year), "data_as_of": bundle["data_as_of"],
        "reference_updated_at": pd.Timestamp(_reference_path(year).stat().st_mtime, unit="s").isoformat(),
        "model_version": MODEL_VERSION, "runs_per_win": round(bundle["runs_per_win"], 3), "warnings": warnings,
        "estimated_rows": _leaderboard_records(bundle["local"]),
        "reference_rows": _leaderboard_records(reference),
        "validation": _validation(bundle["local"], reference),
    }


def _base_state(state: LeverageStateInput) -> int:
    return int(state.runner_first) + int(state.runner_second) * 2 + int(state.runner_third) * 4


def _scenario_state(bundle: dict[str, Any], state: LeverageStateInput) -> dict[str, Any]:
    row = _nearest_state_row(
        bundle["states"], state.inning, state.half, int(np.clip(state.fielding_score - state.opponent_score, -10, 10)),
        state.outs, _base_state(state),
    )
    run_rows = bundle["run_states"]
    run_match = run_rows[run_rows["outs"].eq(state.outs) & run_rows["base_state"].eq(_base_state(state))]
    run_expectancy = float(run_match.iloc[0]["run_expectancy"]) if not run_match.empty else 0.0
    return {
        "win_expectancy": _clean(row["win_expectancy"]), "li": _clean(row["li"]), "run_expectancy": _clean(run_expectancy),
        "state_samples": int(row["samples"]), "matched_inning": int(row["inning"]), "matched_score_diff": int(row["score_diff"]),
    }


def calculate_scenario(request: LeverageScenarioRequest) -> dict[str, Any]:
    bundle = _bundle(request.year)
    opponent_runs = request.exit.opponent_score - request.entry.opponent_score
    if opponent_runs < 0:
        raise ValueError("Exit opponent score cannot be lower than entry opponent score.")
    entry = _scenario_state(bundle, request.entry)
    exit_state = _scenario_state(bundle, request.exit)
    raw_wpa = float(exit_state["win_expectancy"] or 0) - float(entry["win_expectancy"] or 0)
    wpa = float(calibrate_pitcher_wpa(raw_wpa))
    re24 = float(entry["run_expectancy"] or 0) - float(exit_state["run_expectancy"] or 0) - opponent_runs
    span_li = (float(entry["li"] or 0) + float(exit_state["li"] or 0)) / 2
    outcome = "Shutdown" if wpa >= 0.06 else "Meltdown" if wpa <= -0.06 else "Neutral"
    metrics = [
        {"key": "wpa", "label": "WPA", "value": _clean(wpa), "note": "Exit fielding-team WE minus entry WE."},
        {"key": "re24", "label": "RE24", "value": _clean(re24), "note": "Entry RE minus exit RE minus opponent runs scored."},
        {"key": "rew", "label": "REW", "value": _clean(re24 / bundle["runs_per_win"]), "note": f"RE24 divided by {bundle['runs_per_win']:.3f} runs per win."},
        {"key": "gmli", "label": "gmLI", "value": entry["li"], "note": "LI at the entered game state."},
        {"key": "exli", "label": "exLI", "value": exit_state["li"], "note": "LI at the supplied exit state."},
        {"key": "pli_proxy", "label": "Span LI proxy", "value": _clean(span_li), "status": "proxy", "note": "Mean of entry and exit LI; full pLI needs every PA state."},
        {"key": "wpa_li_proxy", "label": "WPA/LI proxy", "value": _clean(wpa / span_li) if span_li else None, "status": "proxy", "note": "Endpoint estimate; leaderboard WPA/LI uses every PA."},
        {"key": "result", "label": "SD/MD result", "value": outcome, "status": "derived"},
        {"key": "inli", "label": "inLI", "value": None, "status": "requires_sequence", "note": "Needs the first state of every inning pitched."},
        {"key": "clutch", "label": "Clutch", "value": None, "status": "requires_sequence", "note": "Needs full event-level pLI and WPA/LI."},
    ]
    return {
        "year": request.year, "data_as_of": bundle["data_as_of"], "model_version": MODEL_VERSION,
        "entry": entry, "exit": exit_state, "metrics": metrics,
        "warnings": ["This calculator estimates endpoint value. pLI, inLI and Clutch require the full appearance sequence."],
    }
