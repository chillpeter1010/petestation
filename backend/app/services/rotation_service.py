from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta, TablePayload
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, load_pitcher_cached_season, resolve_pitch_table
from app.services.discipline_service import CALLED_STRIKE_EVENTS, HIT_EVENTS, OUT_EVENTS, WHIFF_EVENTS, red_strike_zone_mask
from app.services.personal_service import canonical_pitch_name, display_pitch_name
from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores
from app.services.wpa_service import attach_plate_appearance_wpa, one_wpa_value_per_pa


STARTER_FILTER_GS = 3
STARTER_FILTER_IP_PER_GS = 3.0

ROTATION_COLUMNS = [
    "Name",
    "Tm",
    "Age",
    "IP",
    "G",
    "GS",
    "QS",
    "QS%",
    "GmScA",
    "Best",
    "Wrst",
    "IP/GS",
    "Pit/GS",
    "RS/GS",
    "RS/IP",
    "<80",
    "80-99",
    "100-119",
    ">=120",
    "Max",
    "MLBAMID",
    "PlayerId",
]

WORKLOAD_COLUMNS = [
    "Metric",
    "Value",
    "Group",
]

GAME_LOG_COLUMNS = [
    "game_date",
    "game_pk",
    "pitcher_team",
    "opponent_team",
    "pitches",
    "rest_days",
    "game_wpa",
    "cum_wpa",
]

FATIGUE_INNING_COLUMNS = [
    "Inning",
    "Pitches This Inning",
    "Cumulative Pitches",
    "Fastball Velo",
    "Breaking Move",
    "Spin Rate",
    "Pregame Readiness",
    "Fatigue Score",
]

FATIGUE_LAB_GAME_COLUMNS = [
    "Date",
    "Opponent",
    "Pitches",
    "Rest Days",
    "Start #",
    "Recent 7D Pitches",
    "Previous Start Pitches",
    "Pregame Readiness",
    "Final Fatigue Score",
]

FATIGUE_LAB_BREAKDOWN_COLUMNS = ["Factor", "Value", "Impact", "Note"]

FATIGUE_PA_SERIES_COLUMNS = [
    "pa_index",
    "at_bat_number",
    "cumulative_pitches",
    "batter_name",
    "fatigue_score",
    "suppression_score",
    "suppression_delta",
    "csw",
    "whiffs",
    "hard_hits",
    "velo_drop",
    "cumulative_wpa",
    "event",
    "description",
    "inning",
    "pitch_count",
]

PITCH_QUALITY_INNING_COLUMNS = [
    "Inning",
    "Pitch",
    "Pitches",
    "Stuff+",
    "Stuff+ SE",
    "Location+",
    "Location+ SE",
]

RELIEVER_FATIGUE_COLUMNS = [
    "Name",
    "Team",
    "Pitches Yesterday",
    "Pitches Last 3",
    "Pitches Last 7",
    "Appearances Last 3",
    "Appearances Last 7",
    "Back-to-Back",
    "Rest Days",
    "aLI",
    "Out/GR",
    "Readiness",
]

SUPPRESSION_WALK_EVENTS = {"walk", "intent_walk", "hit_by_pitch"}
SUPPRESSION_FASTBALL_TYPES = {"FF", "FA", "SI", "FC"}
SUPPRESSION_FASTBALL_NAMES = ("fastball", "4-seam", "four-seam", "sinker", "cutter")

PITCH_PROFILE_COLUMNS = ["pitch_name", "pitches", "usage_pct", "release_speed", "h_break", "v_break"]

BULLPEN_COLUMNS = [
    "Name", "Team", "G", "GR", "GF", "SVOpp", "SVSit", "SV", "BSv", "Hold",
    "IR", "IS", "IS%", "aLI", "LevHi", "LevMd", "LevLo", "Ahd", "Tie", "Bhd",
    "Runr", "Empt", "Out/GR", "Pit/GR", "IP", "ERA", "xERA", "FIP", "xFIP", "WAR",
    "MLBAMID", "PlayerId",
]

BULLPEN_ROLE_BOARD_COLUMNS = [
    "Name", "Team", "PrimaryRole", "RoleScore", "GR", "aLI", "1stIP",
    "TacticalTags", "SVSit", "SV", "BSv", "Hold", "GF", "Out/GR", "WAR",
    "MLBAMID", "PlayerId",
]

BULLPEN_TACTICAL_COLUMNS = [
    "Name", "Team", "PrimaryRole", "TacticalTags", "TacticalScore",
    "aLI", "SH%", "IR/GR", "IS%", "0DR%", "MultiInning%", "Out/GR", "WAR",
    "MLBAMID", "PlayerId",
]

BULLPEN_USAGE_TIMING_COLUMNS = [
    "Name", "Team", "PrimaryRole", "1stIP", "aLI", "HighLev%", "MidLev%",
    "Ahead%", "Tie%", "Behind%", "RunrOn%", "BasesEmpty%",
    "MultiInning%", "ZeroRest%", "Out/GR", "Pit/GR", "MLBAMID", "PlayerId",
]

BULLPEN_STABILITY_COLUMNS = [
    "Name", "Team", "PrimaryRole", "RoleConsistency", "Versatility",
    "SaveSit%", "Hold%", "HighLev%", "MultiInning%", ">3Outs%", "<3Outs%",
    "MLBAMID", "PlayerId",
]

BULLPEN_AVAILABILITY_COLUMNS = [
    "Name", "Team", "Throws", "Pitches Last 3", "Pitches Yesterday",
    "Last Game", "Availability", "MLBAMID",
]


def get_available_starter_years(data_dir: Path | None = None) -> list[int]:
    base = _starter_dir(data_dir or settings.data_dir)
    if not base.exists():
        return []
    years: set[int] = set()
    for path in base.glob("*_starter_BR.csv"):
        match = re.match(r"(\d{4})_", path.name)
        if match:
            years.add(int(match.group(1)))
    return sorted(years, reverse=True)


def get_available_reliever_years(data_dir: Path | None = None) -> list[int]:
    base = _reliever_dir(data_dir or settings.data_dir)
    if not base.exists():
        return []
    years: set[int] = set()
    for path in base.glob("*_BR_reliever.csv"):
        match = re.match(r"(\d{4})_", path.name)
        if match:
            years.add(int(match.group(1)))
    return sorted(years, reverse=True)


def get_starter_rotation_response(
    year: int = 2025,
    team: str | None = None,
    min_gs: int = STARTER_FILTER_GS,
    min_ip_per_gs: float = STARTER_FILTER_IP_PER_GS,
    player_id: int | None = None,
    fatigue_game_pk: int | None = None,
) -> AnalysisResponse:
    warnings: list[str] = []
    raw = load_starter_rotation_table(year)
    if raw.empty:
        return AnalysisResponse(
            meta=ResponseMeta(
                year=year,
                warnings=[f"No starter rotation source files found for {year}."],
            ),
            charts={
                "available_years": get_available_starter_years(),
                "teams": [],
                "selected_player": None,
                "game_log": [],
                "pitch_profile": [],
            },
        )

    teams = sorted({
        normalized
        for value in raw["Tm"].dropna().unique()
        if (normalized := normalize_team_code(value))
    })
    filtered = filter_starter_rotation(raw, team=team, min_gs=min_gs, min_ip_per_gs=min_ip_per_gs)
    selected = select_starter(filtered, player_id)
    workload = build_workload_rows(selected)
    game_log = build_game_log_rows(year, selected, warnings)
    pitch_profile = build_starter_pitch_profile(year, selected)
    selected_fatigue_game_pk = select_fatigue_game_pk(game_log, fatigue_game_pk)
    fatigue_by_inning = build_starter_fatigue_inning_rows(year, selected, selected_fatigue_game_pk)

    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        summary=build_summary(filtered),
        charts={
            "available_years": get_available_starter_years(),
            "teams": teams,
            "selected_player": selected.to_dict() if selected is not None else None,
            "game_log": game_log,
            "pitch_profile": pitch_profile,
            "selected_fatigue_game_pk": selected_fatigue_game_pk,
        },
        tables={
            "rotation": dataframe_to_table(filtered, ROTATION_COLUMNS),
            "workload": rows_to_table(workload, WORKLOAD_COLUMNS),
            "game_log": rows_to_table(game_log, GAME_LOG_COLUMNS),
            "pitch_profile": rows_to_table(pitch_profile, PITCH_PROFILE_COLUMNS),
            "fatigue_by_inning": rows_to_table(fatigue_by_inning, FATIGUE_INNING_COLUMNS),
        },
    )


def get_starter_fatigue_lab_response(
    year: int = 2025,
    team: str | None = None,
    min_gs: int = STARTER_FILTER_GS,
    min_ip_per_gs: float = STARTER_FILTER_IP_PER_GS,
    player_id: int | None = None,
    game_pk: int | None = None,
) -> AnalysisResponse:
    warnings: list[str] = []
    raw = load_starter_rotation_table(year)
    if raw.empty:
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=[f"No starter rotation source files found for {year}."]),
            charts={
                "available_years": get_available_starter_years(),
                "teams": [],
                "selected_player": None,
                "game_log": [],
                "selected_game_pk": None,
                "readiness_breakdown": [],
            },
        )

    teams = sorted(str(value) for value in raw["Tm"].dropna().unique() if str(value).strip())
    filtered = filter_starter_rotation(raw, team=team, min_gs=min_gs, min_ip_per_gs=min_ip_per_gs)
    selected = select_starter(filtered, player_id)
    game_log = build_game_log_rows(year, selected, warnings)
    selected_game_pk = select_fatigue_game_pk(game_log, game_pk)
    lab_rows, breakdown = build_starter_fatigue_lab_rows(year, selected, game_log, selected_game_pk)
    pa_series = build_starter_fatigue_pa_series(year, selected, game_log, selected_game_pk)
    pitch_quality_series, pitch_quality_by_inning = build_starter_pitch_quality(
        year, selected, selected_game_pk, warnings
    )
    game_rows = build_starter_fatigue_lab_game_rows(game_log, selected, selected_game_pk)

    final_row = lab_rows[-1] if lab_rows else {}
    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        summary=[
            MetricItem(key="pregame_readiness", label="Pregame Readiness", value=clean_scalar(final_row.get("Pregame Readiness"))),
            MetricItem(key="final_fatigue_score", label="Final Fatigue", value=clean_scalar(final_row.get("Fatigue Score"))),
            MetricItem(key="selected_game_pitches", label="Selected Game Pitches", value=clean_scalar(final_row.get("Cumulative Pitches"))),
            MetricItem(key="games_tracked", label="Games Tracked", value=len(game_log)),
        ],
        charts={
            "available_years": get_available_starter_years(),
            "teams": teams,
            "selected_player": selected.to_dict() if selected is not None else None,
            "game_log": game_log,
            "selected_game_pk": selected_game_pk,
            "readiness_breakdown": breakdown,
            "fatigue_pa_series": pa_series,
            "pitch_quality_series": pitch_quality_series,
        },
        tables={
            "rotation": dataframe_to_table(filtered, ROTATION_COLUMNS),
            "fatigue_by_inning": rows_to_table(lab_rows, FATIGUE_INNING_COLUMNS),
            "fatigue_games": rows_to_table(game_rows, FATIGUE_LAB_GAME_COLUMNS),
            "readiness_breakdown": rows_to_table(breakdown, FATIGUE_LAB_BREAKDOWN_COLUMNS),
            "pitch_quality_by_inning": rows_to_table(pitch_quality_by_inning, PITCH_QUALITY_INNING_COLUMNS),
        },
    )


def build_starter_pitch_quality(
    year: int,
    selected: pd.Series | None,
    game_pk: int | None,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join precomputed per-pitch model scores for the selected starter outing."""
    if selected is None or game_pk is None:
        return [], []
    pitcher_id = clean_scalar(selected.get("MLBAMID"))
    if pitcher_id is None:
        return [], []
    pitch_df = load_pitcher_cached_season(year, int(float(pitcher_id)), settings.data_dir)
    if pitch_df.empty or "game_pk" not in pitch_df.columns:
        return [], []
    game = pitch_df[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    if game.empty:
        return [], []
    sort_columns = [column for column in ["inning", "at_bat_number", "pitch_number"] if column in game.columns]
    game = game.sort_values(sort_columns).reset_index(drop=True)
    game["pitch_index"] = range(1, len(game) + 1)
    game["stuff_plus"] = load_pitch_stuff_scores(game, settings.data_dir)
    game["location_plus"] = load_location_pitch_scores(year, int(float(pitcher_id)), int(game_pk), game)
    raw_names = game.get("pitch_name", pd.Series("Unknown", index=game.index))
    game["pitch_name_display"] = raw_names.map(canonical_pitch_name).map(display_pitch_name)

    for score in ["stuff_plus", "location_plus"]:
        game[score] = pd.to_numeric(game[score], errors="coerce")
    game["stuff_ma5"] = game.groupby("pitch_name_display", sort=False)["stuff_plus"].transform(
        lambda values: values.rolling(5, min_periods=5).mean()
    )

    if game["stuff_plus"].notna().sum() == 0:
        warnings.append("Per-pitch Stuff+ cache is not available for this outing yet.")
    if game["location_plus"].notna().sum() == 0:
        warnings.append("Per-pitch Location+ cache is not available for this outing yet.")

    series_rows = [
        {
            "pitch_index": int(row.pitch_index),
            "inning": clean_scalar(row.inning) if "inning" in game.columns else None,
            "pitch": str(row.pitch_name_display),
            "stuff_plus": clean_scalar(row.stuff_plus),
            "stuff_ma5": clean_scalar(row.stuff_ma5),
            "location_plus": clean_scalar(row.location_plus),
        }
        for row in game.itertuples(index=False)
    ]

    inning_rows: list[dict[str, Any]] = []
    if "inning" in game.columns:
        for (inning, pitch), group in game.groupby(["inning", "pitch_name_display"], dropna=True, sort=True):
            stuff = group["stuff_plus"].dropna()
            location = group["location_plus"].dropna()
            inning_rows.append({
                "Inning": int(inning),
                "Pitch": str(pitch),
                "Pitches": int(len(group)),
                "Stuff+": round(float(stuff.mean()), 1) if len(stuff) else None,
                "Stuff+ SE": round(float(stuff.sem()), 1) if len(stuff) > 1 else None,
                "Location+": round(float(location.mean()), 1) if len(location) else None,
                "Location+ SE": round(float(location.sem()), 1) if len(location) > 1 else None,
            })
    return sanitize_rows(series_rows), sanitize_rows(inning_rows)


def load_location_pitch_scores(
    year: int,
    pitcher_id: int,
    game_pk: int,
    game: pd.DataFrame,
) -> pd.Series:
    result = pd.Series(float("nan"), index=game.index, dtype="float64")
    path = settings.data_dir / "derived" / "location_plus_scores.duckdb"
    table = f"location_pitch_scores_{int(year)}"
    if not path.exists():
        return result
    try:
        with duckdb.connect(str(path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if table not in tables:
                return result
            scores = conn.execute(
                f"SELECT pitch_uid, location_plus_pitch FROM {table} WHERE game_pk = ? AND pitcher_id = ?",
                [int(game_pk), int(pitcher_id)],
            ).fetchdf()
    except duckdb.Error:
        return result
    if scores.empty:
        return result
    if "pitch_uid" in game.columns:
        keys = game["pitch_uid"].astype(str)
    elif {"at_bat_number", "pitch_number"}.issubset(game.columns):
        keys = (
            str(int(game_pk)) + "_"
            + pd.to_numeric(game["at_bat_number"], errors="coerce").astype("Int64").astype(str) + "_"
            + pd.to_numeric(game["pitch_number"], errors="coerce").astype("Int64").astype(str)
        )
    else:
        return result
    score_map = scores.drop_duplicates("pitch_uid", keep="last").set_index("pitch_uid")["location_plus_pitch"]
    return pd.to_numeric(keys.map(score_map), errors="coerce")


def get_reliever_fatigue_lab_response(
    year: int = 2025,
    team: str | None = None,
    min_games: int = 5,
    player_id: int | None = None,
    availability_date: str | None = None,
) -> AnalysisResponse:
    raw = load_bullpen_role_table(year)
    if raw.empty:
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=[f"No bullpen role source files found for {year}."]),
            charts={
                "available_years": get_available_reliever_years(),
                "teams": [],
                "selected_player": None,
                "availability_date": None,
                "readiness_breakdown": [],
            },
        )

    teams = sorted(str(value) for value in raw["Team"].dropna().unique() if str(value).strip())
    filtered = raw.copy()
    if team and team != "All":
        filtered = filtered[filtered["Team"].astype(str).eq(team)]
    filtered = filtered[pd.to_numeric(filtered["G"], errors="coerce").fillna(0) >= int(min_games)].reset_index(drop=True)
    selected = select_pitcher_by_id(filtered, player_id)
    usage = prepare_bullpen_usage_rows(load_bullpen_usage_rows(year, settings.data_dir))
    usage_groups = build_bullpen_usage_groups(usage)
    context = build_reliever_fatigue_context(year, selected, availability_date, usage, usage_groups)
    readiness, breakdown = calculate_reliever_readiness(context, selected)
    lab_rows = build_reliever_fatigue_table(year, filtered, availability_date, usage, usage_groups)

    selected_row = {
        "Name": clean_scalar(selected.get("Name")) if selected is not None else None,
        "Team": clean_scalar(selected.get("Team")) if selected is not None else None,
        **context,
        "aLI": clean_scalar(selected.get("aLI")) if selected is not None else None,
        "Out/GR": clean_scalar(selected.get("Out/GR")) if selected is not None else None,
        "Readiness": round(readiness, 1),
    }

    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="readiness", label="Readiness", value=round(readiness, 1)),
            MetricItem(key="yesterday_pitches", label="Yesterday", value=clean_scalar(context.get("Pitches Yesterday"))),
            MetricItem(key="last3_pitches", label="Last 3 Days", value=clean_scalar(context.get("Pitches Last 3"))),
            MetricItem(key="last7_pitches", label="Last 7 Days", value=clean_scalar(context.get("Pitches Last 7"))),
        ],
        charts={
            "available_years": get_available_reliever_years(),
            "teams": teams,
            "selected_player": selected.to_dict() if selected is not None else None,
            "availability_date": context.get("availability_date"),
            "readiness_breakdown": breakdown,
        },
        tables={
            "relievers": dataframe_to_table(filtered, BULLPEN_COLUMNS),
            "selected_readiness": rows_to_table([selected_row], RELIEVER_FATIGUE_COLUMNS),
            "readiness_board": rows_to_table(lab_rows, RELIEVER_FATIGUE_COLUMNS),
            "readiness_breakdown": rows_to_table(breakdown, FATIGUE_LAB_BREAKDOWN_COLUMNS),
        },
    )


def get_bullpen_role_response(
    year: int = 2025,
    team: str | None = None,
    min_games: int = 5,
    player_id: int | None = None,
    availability_date: str | None = None,
) -> AnalysisResponse:
    raw = load_bullpen_role_table(year)
    if raw.empty:
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=[f"No bullpen role source files found for {year}."]),
            charts={
                "available_years": get_available_reliever_years(),
                "teams": [],
                "selected_player": None,
                "role_usage": [],
            },
        )

    teams = sorted(str(value) for value in raw["Team"].dropna().unique() if str(value).strip())
    filtered = raw.copy()
    if team and team != "All":
        filtered = filtered[filtered["Team"].astype(str).eq(team)]
    filtered = filtered[pd.to_numeric(filtered["G"], errors="coerce").fillna(0) >= int(min_games)].reset_index(drop=True)
    selected = select_pitcher_by_id(filtered, player_id)
    role_usage = build_bullpen_role_usage(selected)
    role_usage_horizontal = build_bullpen_role_usage_horizontal(selected)
    role_board, usage_timing, stability, tactical = build_bullpen_role_views(filtered)
    availability_year = 2026
    availability_team = select_availability_team(team, teams, selected)
    availability = build_bullpen_availability_table(availability_year, availability_team, availability_date)

    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="relievers", label="Relievers", value=int(len(filtered))),
            MetricItem(key="avg_ali", label="Avg aLI", value=mean_value(filtered, "aLI")),
            MetricItem(key="saves", label="Saves", value=sum_value(filtered, "SV")),
            MetricItem(key="holds", label="Holds", value=sum_value(filtered, "Hold")),
        ],
        charts={
            "available_years": get_available_reliever_years(),
            "teams": teams,
            "selected_player": selected.to_dict() if selected is not None else None,
            "role_usage": role_usage,
            "availability_year": availability_year,
            "availability_team": availability_team,
            "availability_date": availability.attrs.get("availability_date"),
        },
        tables={
            "bullpen": dataframe_to_table(filtered, BULLPEN_COLUMNS),
            "role_usage": rows_to_table(role_usage, WORKLOAD_COLUMNS),
            "role_usage_horizontal": rows_to_table(role_usage_horizontal, [row["Metric"] for row in role_usage]),
            "tactical": dataframe_to_table(tactical, BULLPEN_TACTICAL_COLUMNS),
            "role_board": dataframe_to_table(role_board, BULLPEN_ROLE_BOARD_COLUMNS),
            "usage_timing": dataframe_to_table(usage_timing, BULLPEN_USAGE_TIMING_COLUMNS),
            "stability": dataframe_to_table(stability, BULLPEN_STABILITY_COLUMNS),
            "availability": dataframe_to_table(availability, BULLPEN_AVAILABILITY_COLUMNS),
        },
    )


def load_starter_rotation_table(year: int, data_dir: Path | None = None) -> pd.DataFrame:
    base = _starter_dir(data_dir or settings.data_dir)
    br_path = base / f"{int(year)}_starter_BR.csv"
    if not br_path.exists():
        return pd.DataFrame()
    dashboard = load_starter_dashboard(year, data_dir=data_dir)
    if dashboard.empty:
        return pd.DataFrame()

    br = pd.read_csv(br_path)
    if "Name" in br.columns:
        br["raw_name"] = br["Name"]
    br = clean_starter_br(br)
    dashboard_lookup = dashboard[["name_key", "Name", "Team", "G", "GS", "IP", "MLBAMID", "PlayerId"]].copy()
    dashboard_lookup = dashboard_lookup.rename(columns={"Name": "dashboard_name", "Team": "dashboard_team"})
    dashboard_lookup["damaged_name_key"] = dashboard_lookup["dashboard_name"].map(damaged_latin_name_key)
    if "NameASCII" in dashboard.columns:
        dashboard_lookup["damaged_name_key"] = dashboard["NameASCII"].map(damaged_latin_name_key)
    damaged_source = br["raw_name"] if "raw_name" in br.columns else br["Name"]
    br["damaged_name_key"] = damaged_source.map(damaged_latin_name_key)
    merged = br.merge(
        dashboard_lookup[["name_key", "dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]],
        on="name_key",
        how="left",
    )
    missing_ids = merged["MLBAMID"].isna()
    if missing_ids.any():
        damaged_lookup = dashboard_lookup[
            dashboard_lookup["dashboard_team"].notna()
            & ~dashboard_lookup["dashboard_team"].astype(str).isin(["", "- - -"])
        ].drop_duplicates(["damaged_name_key", "dashboard_team"], keep="first")
        damaged = merged.loc[missing_ids].merge(
            damaged_lookup[["damaged_name_key", "dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]],
            left_on=["damaged_name_key", "Tm"],
            right_on=["damaged_name_key", "dashboard_team"],
            how="left",
            suffixes=("", "_damaged"),
        )
        for column in ["dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]:
            damaged_column = f"{column}_damaged"
            if damaged_column in damaged.columns:
                damaged[column] = damaged[column].combine_first(damaged[damaged_column])
        merged.loc[missing_ids, ["dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]] = damaged[
            ["dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]
        ].to_numpy()
    missing_ids = merged["MLBAMID"].isna()
    if missing_ids.any():
        fallback_lookup = dashboard_lookup.dropna(subset=["dashboard_team", "G", "GS", "IP"]).copy()
        fallback_lookup = fallback_lookup.drop_duplicates(["dashboard_team", "G", "GS", "IP"], keep="first")
        fallback = merged.loc[missing_ids].merge(
            fallback_lookup[["dashboard_name", "dashboard_team", "G", "GS", "IP", "MLBAMID", "PlayerId"]],
            left_on=["Tm", "G", "GS", "IP"],
            right_on=["dashboard_team", "G", "GS", "IP"],
            how="left",
            suffixes=("", "_fallback"),
        )
        for column in ["dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]:
            fallback_column = f"{column}_fallback"
            if fallback_column in fallback.columns:
                fallback[column] = fallback[column].combine_first(fallback[fallback_column])
        merged.loc[missing_ids, ["dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]] = fallback[
            ["dashboard_name", "dashboard_team", "MLBAMID", "PlayerId"]
        ].to_numpy()
    missing_ids = merged["MLBAMID"].isna()
    if missing_ids.any() and "Name-additional" in merged.columns:
        bbref_ids = tuple(
            sorted(
                str(value).strip()
                for value in merged.loc[missing_ids, "Name-additional"].dropna().unique()
                if str(value).strip()
            )
        )
        bbref_lookup = load_bbref_player_lookup(bbref_ids)
        if not bbref_lookup.empty:
            bbref_match = merged.loc[missing_ids].merge(
                bbref_lookup,
                left_on="Name-additional",
                right_on="key_bbref",
                how="left",
            )
            for column in ["dashboard_name", "MLBAMID", "PlayerId"]:
                bbref_column = f"{column}_bbref"
                if bbref_column in bbref_match.columns:
                    bbref_match[column] = bbref_match[column].combine_first(bbref_match[bbref_column])
            merged.loc[missing_ids, ["dashboard_name", "MLBAMID", "PlayerId"]] = bbref_match[
                ["dashboard_name", "MLBAMID", "PlayerId"]
            ].to_numpy()
    merged["Name"] = merged["dashboard_name"].combine_first(merged["Name"])
    merged = merged.drop(columns=["dashboard_name", "dashboard_team", "damaged_name_key"], errors="ignore")
    if ">=120" not in merged.columns and "≥120" in merged.columns:
        merged[">=120"] = merged["≥120"]
    merged = merged.drop_duplicates(["Name", "Tm"], keep="first")
    merged = merged.sort_values(["GS", "IP"], ascending=[False, False]).reset_index(drop=True)
    return merged


def load_starter_dashboard(year: int, data_dir: Path | None = None) -> pd.DataFrame:
    base = _starter_dir(data_dir or settings.data_dir)
    yearly_path = base / f"{int(year)}_starter_dashboard.csv"
    combined_path = base / "2021_2026_starter_dashboard.csv"
    if yearly_path.exists():
        return clean_starter_dashboard(pd.read_csv(yearly_path, low_memory=False))
    if combined_path.exists():
        dashboard = pd.read_csv(combined_path, low_memory=False)
        if "Season" in dashboard.columns:
            dashboard = dashboard[pd.to_numeric(dashboard["Season"], errors="coerce").eq(int(year))].copy()
        return clean_starter_dashboard(dashboard)
    return pd.DataFrame()


@lru_cache(maxsize=32)
def load_bbref_player_lookup(bbref_ids: tuple[str, ...]) -> pd.DataFrame:
    if not bbref_ids:
        return pd.DataFrame(columns=["key_bbref", "dashboard_name_bbref", "MLBAMID_bbref", "PlayerId_bbref"])
    try:
        from pybaseball import playerid_reverse_lookup
    except Exception:
        return pd.DataFrame(columns=["key_bbref", "dashboard_name_bbref", "MLBAMID_bbref", "PlayerId_bbref"])

    try:
        lookup = playerid_reverse_lookup(list(bbref_ids), key_type="bbref")
    except Exception:
        return pd.DataFrame(columns=["key_bbref", "dashboard_name_bbref", "MLBAMID_bbref", "PlayerId_bbref"])
    if lookup.empty:
        return pd.DataFrame(columns=["key_bbref", "dashboard_name_bbref", "MLBAMID_bbref", "PlayerId_bbref"])

    working = lookup.copy()
    first = working.get("name_first", pd.Series("", index=working.index)).fillna("").astype(str).str.title()
    last = working.get("name_last", pd.Series("", index=working.index)).fillna("").astype(str).str.title()
    working["dashboard_name_bbref"] = (first + " " + last).str.strip()
    return working.rename(
        columns={
            "key_mlbam": "MLBAMID_bbref",
            "key_fangraphs": "PlayerId_bbref",
        }
    )[["key_bbref", "dashboard_name_bbref", "MLBAMID_bbref", "PlayerId_bbref"]]


def load_bullpen_role_table(year: int, data_dir: Path | None = None) -> pd.DataFrame:
    base = _reliever_dir(data_dir or settings.data_dir)
    br_path = base / f"{int(year)}_BR_reliever.csv"
    standard_path = base / f"{int(year)}_reliever_standard.csv"
    advanced_path = base / f"{int(year)}_reliever_advanced.csv"
    if not br_path.exists() or not standard_path.exists() or not advanced_path.exists():
        return pd.DataFrame()

    br = clean_reliever_br(pd.read_csv(br_path))
    standard = clean_reliever_table(pd.read_csv(standard_path))
    advanced = clean_reliever_table(pd.read_csv(advanced_path))
    merged = (
        standard[["name_key", "Name", "Team", "ERA", "xERA", "FIP", "xFIP", "WAR", "MLBAMID", "PlayerId"]]
        .merge(
            br[[
                "name_key", "G", "GR", "GF", "SVOpp", "SVSit", "SV", "BSv", "Hold", "IR", "IS", "IS%",
                "1stIP", "aLI", "LevHi", "LevMd", "LevLo", "Ahd", "Tie", "Bhd", "Runr", "Empt",
                ">3o", "<3o", "IPmult", "0DR", "Out/GR", "Pit/GR", "IP",
            ]],
            on="name_key",
            how="inner",
        )
        .merge(advanced[["name_key", "K-BB%"]], on="name_key", how="left")
    )
    return merged.sort_values(["SVSit", "Hold", "SV", "aLI"], ascending=[False, False, False, False]).reset_index(drop=True)


def clean_starter_br(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    if "Name" not in cleaned.columns:
        return pd.DataFrame()
    cleaned["Name"] = cleaned["Name"].map(clean_name)
    cleaned["name_key"] = cleaned["Name"].map(normalize_name)
    for col in cleaned.columns:
        if col in {"Name", "raw_name", "Tm", "Name-additional", "name_key"}:
            continue
        cleaned[col] = parse_numeric_series(cleaned[col])
    return cleaned.drop_duplicates("name_key", keep="first")


def clean_starter_dashboard(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    source = cleaned["NameASCII"] if "NameASCII" in cleaned.columns else cleaned.get("Name", pd.Series(dtype=str))
    cleaned["name_key"] = source.map(clean_name).map(normalize_name)
    for col in ["MLBAMID", "PlayerId"]:
        if col not in cleaned.columns:
            cleaned[col] = pd.NA
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
    return cleaned


def clean_reliever_br(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["Name"] = cleaned["Name"].map(clean_name)
    cleaned["name_key"] = cleaned["Name"].map(normalize_name)
    for col in cleaned.columns:
        if col in {"Name", "Tm", "Name-additional", "name_key"}:
            continue
        cleaned[col] = parse_numeric_series(cleaned[col])
    return cleaned


def clean_reliever_table(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["Name"] = cleaned["Name"].map(clean_name)
    source = cleaned["NameASCII"] if "NameASCII" in cleaned.columns else cleaned.get("Name", pd.Series(dtype=str))
    cleaned["name_key"] = source.map(clean_name).map(normalize_name)
    for col in cleaned.columns:
        if col in {"Name", "NameASCII", "Team", "name_key"}:
            continue
        cleaned[col] = parse_numeric_series(cleaned[col])
    return cleaned.drop_duplicates("name_key", keep="first")


def filter_starter_rotation(
    df: pd.DataFrame,
    team: str | None,
    min_gs: int,
    min_ip_per_gs: float,
) -> pd.DataFrame:
    filtered = df.copy()
    if team and team != "All":
        selected_team = normalize_team_code(team)
        normalized_teams = filtered["Tm"].map(normalize_team_code)
        filtered = filtered[normalized_teams.eq(selected_team)]
    if "GS" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["GS"], errors="coerce").fillna(0) >= int(min_gs)]
    if "IP/GS" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["IP/GS"], errors="coerce").fillna(0) >= float(min_ip_per_gs)]
    return filtered.reset_index(drop=True)


def select_starter(df: pd.DataFrame, player_id: int | None) -> pd.Series | None:
    return select_pitcher_by_id(df, player_id)


def select_pitcher_by_id(df: pd.DataFrame, player_id: int | None) -> pd.Series | None:
    if df.empty:
        return None
    if player_id is not None and "MLBAMID" in df.columns:
        matched = df[pd.to_numeric(df["MLBAMID"], errors="coerce").eq(int(player_id))]
        if not matched.empty:
            return matched.iloc[0]
    return df.iloc[0]


def build_summary(df: pd.DataFrame) -> list[MetricItem]:
    if df.empty:
        return [
            MetricItem(key="starters", label="Starters", value=0),
            MetricItem(key="avg_gs", label="Avg GS", value=None),
            MetricItem(key="avg_ip_gs", label="Avg IP/GS", value=None),
            MetricItem(key="avg_pit_gs", label="Avg Pit/GS", value=None),
        ]

    return [
        MetricItem(key="starters", label="Starters", value=int(len(df))),
        MetricItem(key="avg_gs", label="Avg GS", value=mean_value(df, "GS")),
        MetricItem(key="avg_ip_gs", label="Avg IP/GS", value=mean_value(df, "IP/GS")),
        MetricItem(key="avg_pit_gs", label="Avg Pit/GS", value=mean_value(df, "Pit/GS")),
    ]


def build_workload_rows(selected: pd.Series | None) -> list[dict[str, Any]]:
    if selected is None:
        return []
    groups = {
        "Season": ["IP", "G", "GS", "IP/GS", "Pit/GS"],
        "Start Length": ["<80", "80-99", "100-119", ">=120", "Max"],
        "Quality": ["QS", "QS%", "GmScA", "Best", "Wrst"],
        "Run Support": ["RS/GS", "RS/IP"],
    }
    rows: list[dict[str, Any]] = []
    for group, keys in groups.items():
        for key in keys:
            rows.append({"Metric": key, "Value": clean_scalar(selected.get(key)), "Group": group})
    return rows


def build_game_log_rows(year: int, selected: pd.Series | None, warnings: list[str]) -> list[dict[str, Any]]:
    if selected is None:
        return []
    pitcher_id = clean_scalar(selected.get("MLBAMID"))
    if pitcher_id is None:
        warnings.append("Selected starter has no MLBAMID, so game WPA cannot be loaded.")
        return []

    pitch_df = load_pitcher_cached_season(year, int(float(pitcher_id)), settings.data_dir)
    if pitch_df.empty:
        warnings.append("No cached pitch rows found for selected starter.")
        return []

    pitch_df = pitch_df.copy()
    pitch_df = attach_plate_appearance_wpa(pitch_df, year, settings.data_dir)
    if "pitcher_wpa" not in pitch_df.columns or pitch_df["pitcher_wpa"].isna().all():
        warnings.append("Plate-appearance WPA is unavailable for the selected starter.")
        return []
    pitch_df["pitcher_wpa_once"] = one_wpa_value_per_pa(pitch_df, "pitcher_wpa")
    if {"inning_topbot", "home_team", "away_team"}.issubset(pitch_df.columns):
        is_top = pitch_df["inning_topbot"].astype(str).str.lower().eq("top")
        pitch_df["pitcher_team"] = pitch_df["away_team"]
        pitch_df.loc[is_top, "pitcher_team"] = pitch_df.loc[is_top, "home_team"]
        pitch_df["opponent_team"] = pitch_df["home_team"]
        pitch_df.loc[is_top, "opponent_team"] = pitch_df.loc[is_top, "away_team"]
    else:
        if "pitcher_team" not in pitch_df.columns:
            pitch_df["pitcher_team"] = ""
        if "opponent_team" not in pitch_df.columns:
            pitch_df["opponent_team"] = ""

    game_log = (
        pitch_df.groupby(["game_date", "game_pk", "pitcher_team", "opponent_team"], dropna=False)
        .agg(game_wpa=("pitcher_wpa_once", "sum"), pitches=("pitcher_wpa", "size"))
        .reset_index()
        .sort_values(["game_date", "game_pk"])
    )
    game_log["cum_wpa"] = game_log["game_wpa"].cumsum()
    game_dates = pd.to_datetime(game_log["game_date"], errors="coerce")
    game_log["rest_days"] = game_dates.diff().dt.days
    return sanitize_rows(game_log[GAME_LOG_COLUMNS].to_dict("records"))


def select_fatigue_game_pk(game_log: list[dict[str, Any]], requested_game_pk: int | None) -> int | None:
    if not game_log:
        return None
    game_pks = {int(float(row["game_pk"])) for row in game_log if clean_scalar(row.get("game_pk")) is not None}
    if requested_game_pk is not None and int(requested_game_pk) in game_pks:
        return int(requested_game_pk)
    last_game = game_log[-1].get("game_pk")
    return int(float(last_game)) if clean_scalar(last_game) is not None else None


def build_starter_fatigue_inning_rows(year: int, selected: pd.Series | None, game_pk: int | None) -> list[dict[str, Any]]:
    if selected is None or game_pk is None:
        return []
    pitcher_id = clean_scalar(selected.get("MLBAMID"))
    if pitcher_id is None:
        return []
    pitch_df = load_pitcher_cached_season(year, int(float(pitcher_id)), settings.data_dir)
    if pitch_df.empty or "game_pk" not in pitch_df.columns or "inning" not in pitch_df.columns:
        return []

    game_pitch_df = pitch_df[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    if game_pitch_df.empty:
        return []
    sort_cols = ["inning", "pitch_number"] if "pitch_number" in game_pitch_df.columns else ["inning"]
    game_pitch_df = game_pitch_df.sort_values(sort_cols)
    for column in ["release_speed", "release_spin_rate", "pfx_x", "pfx_z"]:
        if column in game_pitch_df.columns:
            game_pitch_df[column] = pd.to_numeric(game_pitch_df[column], errors="coerce")

    rows: list[dict[str, Any]] = []
    cumulative_pitches = 0
    for inning, inning_df in game_pitch_df.groupby("inning", dropna=True):
        cumulative_pitches += len(inning_df)
        fatigue_score = float(max(20, min(100, 100 - cumulative_pitches * 0.75)))
        pitch_type = inning_df["pitch_type"].astype(str) if "pitch_type" in inning_df.columns else pd.Series("", index=inning_df.index)
        fastball_mask = pitch_type.isin({"FF", "SI", "FC", "FA"})
        breaking_mask = pitch_type.isin({"SL", "ST", "CU", "KC", "SV"})
        breaking_move = math.nan
        if {"pfx_x", "pfx_z"}.issubset(inning_df.columns):
            breaking_move = (
                ((inning_df.loc[breaking_mask, "pfx_x"] * 12) ** 2 + (inning_df.loc[breaking_mask, "pfx_z"] * 12) ** 2) ** 0.5
            ).mean()
        rows.append(
            {
                "Inning": int(inning),
                "Pitches This Inning": int(len(inning_df)),
                "Cumulative Pitches": int(cumulative_pitches),
                "Fastball Velo": clean_scalar(inning_df.loc[fastball_mask, "release_speed"].mean()) if "release_speed" in inning_df.columns else None,
                "Breaking Move": clean_scalar(breaking_move),
                "Spin Rate": clean_scalar(inning_df["release_spin_rate"].mean()) if "release_spin_rate" in inning_df.columns else None,
                "Pregame Readiness": 100.0,
                "Fatigue Score": clean_scalar(fatigue_score),
            }
        )
    return sanitize_rows(rows)


def build_starter_fatigue_lab_rows(
    year: int,
    selected: pd.Series | None,
    game_log: list[dict[str, Any]],
    game_pk: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if selected is None or game_pk is None:
        return [], []
    pitcher_id = clean_scalar(selected.get("MLBAMID"))
    if pitcher_id is None:
        return [], []
    pitch_df = load_pitcher_cached_season(year, int(float(pitcher_id)), settings.data_dir)
    if pitch_df.empty or "game_pk" not in pitch_df.columns or "inning" not in pitch_df.columns:
        return [], []

    game_context = build_fatigue_game_context(game_log, game_pk)
    readiness, breakdown = calculate_pregame_readiness(
        age=clean_scalar(selected.get("Age")),
        rest_days=game_context.get("rest_days"),
        start_number=game_context.get("start_number"),
        recent_7d_pitches=game_context.get("recent_7d_pitches"),
        previous_start_pitches=game_context.get("previous_start_pitches"),
    )
    fatigue_rate = fatigue_rate_for_readiness(readiness)

    game_pitch_df = pitch_df[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    if game_pitch_df.empty:
        return [], breakdown
    sort_cols = ["inning", "pitch_number"] if "pitch_number" in game_pitch_df.columns else ["inning"]
    game_pitch_df = game_pitch_df.sort_values(sort_cols)
    for column in ["release_speed", "release_spin_rate", "pfx_x", "pfx_z"]:
        if column in game_pitch_df.columns:
            game_pitch_df[column] = pd.to_numeric(game_pitch_df[column], errors="coerce")

    rows: list[dict[str, Any]] = []
    cumulative_pitches = 0
    for inning, inning_df in game_pitch_df.groupby("inning", dropna=True):
        cumulative_pitches += len(inning_df)
        fatigue_score = float(max(15, min(105, readiness - cumulative_pitches * fatigue_rate)))
        pitch_type = inning_df["pitch_type"].astype(str) if "pitch_type" in inning_df.columns else pd.Series("", index=inning_df.index)
        fastball_mask = pitch_type.isin({"FF", "SI", "FC", "FA"})
        breaking_mask = pitch_type.isin({"SL", "ST", "CU", "KC", "SV"})
        breaking_move = math.nan
        if {"pfx_x", "pfx_z"}.issubset(inning_df.columns):
            breaking_move = (
                ((inning_df.loc[breaking_mask, "pfx_x"] * 12) ** 2 + (inning_df.loc[breaking_mask, "pfx_z"] * 12) ** 2) ** 0.5
            ).mean()
        rows.append(
            {
                "Inning": int(inning),
                "Pitches This Inning": int(len(inning_df)),
                "Cumulative Pitches": int(cumulative_pitches),
                "Fastball Velo": clean_scalar(inning_df.loc[fastball_mask, "release_speed"].mean()) if "release_speed" in inning_df.columns else None,
                "Breaking Move": clean_scalar(breaking_move),
                "Spin Rate": clean_scalar(inning_df["release_spin_rate"].mean()) if "release_spin_rate" in inning_df.columns else None,
                "Pregame Readiness": round(readiness, 1),
                "Fatigue Score": clean_scalar(round(fatigue_score, 1)),
            }
        )
    return sanitize_rows(rows), breakdown


def build_starter_fatigue_pa_series(
    year: int,
    selected: pd.Series | None,
    game_log: list[dict[str, Any]],
    game_pk: int | None,
) -> list[dict[str, Any]]:
    if selected is None or game_pk is None:
        return []
    pitcher_id = clean_scalar(selected.get("MLBAMID"))
    if pitcher_id is None:
        return []
    pitch_df = load_pitcher_cached_season(year, int(float(pitcher_id)), settings.data_dir)
    if pitch_df.empty or "game_pk" not in pitch_df.columns:
        return []

    game_context = build_fatigue_game_context(game_log, game_pk)
    readiness, _ = calculate_pregame_readiness(
        age=clean_scalar(selected.get("Age")),
        rest_days=game_context.get("rest_days"),
        start_number=game_context.get("start_number"),
        recent_7d_pitches=game_context.get("recent_7d_pitches"),
        previous_start_pitches=game_context.get("previous_start_pitches"),
    )
    fatigue_rate = fatigue_rate_for_readiness(readiness)

    game_pitch_df = pitch_df[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    if game_pitch_df.empty:
        return []
    game_pitch_df = attach_plate_appearance_wpa(game_pitch_df, year, settings.data_dir)
    game_pitch_df["pitcher_wpa"] = pd.to_numeric(game_pitch_df.get("pitcher_wpa"), errors="coerce").fillna(0)
    if "at_bat_number" not in game_pitch_df.columns:
        game_pitch_df["at_bat_number"] = (range(len(game_pitch_df)))
    sort_cols = [column for column in ["inning", "at_bat_number", "pitch_number"] if column in game_pitch_df.columns]
    game_pitch_df = game_pitch_df.sort_values(sort_cols or game_pitch_df.index.name or "game_pk")
    game_pitch_df["_pitch_sequence"] = range(1, len(game_pitch_df) + 1)
    baseline_fastball_velo = calculate_fastball_velo_baseline(game_pitch_df)

    rows: list[dict[str, Any]] = []
    cumulative_wpa = 0.0
    for pa_index, (_, pa_df) in enumerate(game_pitch_df.groupby("at_bat_number", dropna=False), start=1):
        last_pitch = pa_df.iloc[-1]
        cumulative_pitches = int(last_pitch["_pitch_sequence"])
        cumulative_wpa += float(pd.to_numeric(pa_df["pitcher_wpa"], errors="coerce").dropna().iloc[0]) if pa_df["pitcher_wpa"].notna().any() else 0.0
        fatigue_score = max(15, min(105, readiness - cumulative_pitches * fatigue_rate))
        event = first_text(last_pitch, ["events", "description", "type"])
        description = first_text(last_pitch, ["des", "description", "events"])
        batter_name = extract_batter_name(last_pitch)
        inning = clean_scalar(last_pitch.get("inning"))
        suppression = calculate_pa_suppression_score(pa_df, baseline_fastball_velo)
        rows.append(
            {
                "pa_index": pa_index,
                "at_bat_number": clean_scalar(last_pitch.get("at_bat_number")),
                "cumulative_pitches": cumulative_pitches,
                "batter_name": batter_name,
                "fatigue_score": round(fatigue_score, 1),
                "suppression_score": suppression["score"],
                "suppression_delta": suppression["delta"],
                "csw": suppression["csw"],
                "whiffs": suppression["whiffs"],
                "hard_hits": suppression["hard_hits"],
                "velo_drop": suppression["velo_drop"],
                "cumulative_wpa": round(cumulative_wpa, 4),
                "event": event,
                "description": description,
                "inning": inning,
                "pitch_count": int(len(pa_df)),
            }
        )
    return sanitize_rows(rows)


def calculate_fastball_velo_baseline(data: pd.DataFrame) -> float | None:
    if data.empty or "release_speed" not in data.columns:
        return None
    fastball_mask = pd.Series(False, index=data.index)
    if "pitch_type" in data.columns:
        fastball_mask |= data["pitch_type"].fillna("").astype(str).str.upper().isin(SUPPRESSION_FASTBALL_TYPES)
    if "pitch_name" in data.columns:
        pitch_name = data["pitch_name"].fillna("").astype(str).str.lower()
        fastball_mask |= pitch_name.apply(lambda value: any(name in value for name in SUPPRESSION_FASTBALL_NAMES))
    speeds = pd.to_numeric(data.loc[fastball_mask, "release_speed"], errors="coerce").dropna()
    if speeds.empty:
        return None
    early_speeds = speeds.head(25)
    return float((early_speeds if not early_speeds.empty else speeds).mean())


def calculate_pa_suppression_score(pa_df: pd.DataFrame, baseline_fastball_velo: float | None) -> dict[str, Any]:
    description = text_series(pa_df, "description")
    events = text_series(pa_df, "events")
    launch_speed = numeric_pa_series(pa_df, "launch_speed")
    csw = int(description.isin(CALLED_STRIKE_EVENTS | WHIFF_EVENTS).sum())
    whiffs = int(description.isin(WHIFF_EVENTS).sum())
    hard_hits = int(launch_speed.ge(95).sum())
    hits = int(events.isin(HIT_EVENTS).sum())
    walks = int(events.isin(SUPPRESSION_WALK_EVENTS).sum())
    outs = int(events.isin(OUT_EVENTS).sum())
    strikeouts = int(events.isin({"strikeout", "strikeout_double_play"}).sum())
    home_runs = int(events.eq("home_run").sum())
    zone_penalty = heart_contact_count(pa_df)
    velo_drop = calculate_pa_fastball_velo_drop(pa_df, baseline_fastball_velo)

    pitch_count = max(int(len(pa_df)), 1)
    csw_rate = csw / pitch_count
    whiff_rate = whiffs / pitch_count

    score = 68.0
    score += csw_rate * 24
    score += whiff_rate * 18
    score += outs * 6
    score += strikeouts * 7
    score -= hits * 8
    score -= walks * 7
    score -= hard_hits * 7
    score -= home_runs * 12
    score -= zone_penalty * 2.5
    if velo_drop is not None and velo_drop > 0:
        score -= velo_drop * 3

    clamped = max(10.0, min(110.0, score))
    return {
        "score": round(clamped, 1),
        "delta": round(clamped - 68.0, 1),
        "csw": csw,
        "whiffs": whiffs,
        "hard_hits": hard_hits,
        "velo_drop": round(velo_drop, 1) if velo_drop is not None else None,
    }


def text_series(data: pd.DataFrame, column: str) -> pd.Series:
    return data.get(column, pd.Series(index=data.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()


def numeric_pa_series(data: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(data.get(column, pd.Series(index=data.index, dtype="float")), errors="coerce")


def heart_contact_count(data: pd.DataFrame) -> int:
    if data.empty:
        return 0
    try:
        in_zone = red_strike_zone_mask(data)
    except Exception:
        in_zone = pd.Series(False, index=data.index)
    plate_x = numeric_pa_series(data, "plate_x")
    plate_z = numeric_pa_series(data, "plate_z")
    heart = plate_x.between(-0.67, 0.67) & plate_z.between(1.83, 3.17)
    contact = text_series(data, "description").isin({"foul", "foul_tip", "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"})
    return int((heart & contact & in_zone.reindex(data.index, fill_value=False)).sum())


def calculate_pa_fastball_velo_drop(pa_df: pd.DataFrame, baseline_fastball_velo: float | None) -> float | None:
    if baseline_fastball_velo is None or "release_speed" not in pa_df.columns:
        return None
    fastball_mask = pd.Series(False, index=pa_df.index)
    if "pitch_type" in pa_df.columns:
        fastball_mask |= pa_df["pitch_type"].fillna("").astype(str).str.upper().isin(SUPPRESSION_FASTBALL_TYPES)
    if "pitch_name" in pa_df.columns:
        pitch_name = pa_df["pitch_name"].fillna("").astype(str).str.lower()
        fastball_mask |= pitch_name.apply(lambda value: any(name in value for name in SUPPRESSION_FASTBALL_NAMES))
    speeds = pd.to_numeric(pa_df.loc[fastball_mask, "release_speed"], errors="coerce").dropna()
    if speeds.empty:
        return None
    return float(baseline_fastball_velo - speeds.mean())


def extract_batter_name(row: pd.Series) -> str:
    description = first_text(row, ["des"])
    if description and description not in {"-", "Called Strike", "Ball", "Foul", "Swinging Strike"}:
        match = re.match(
            r"^(.+?)\s+(strikes|singles|doubles|triples|homers|walks|grounds|flies|lines|pops|reaches|called|hit|sacrifices|bunts|out|intentionally)",
            description,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    batter_id = clean_scalar(row.get("batter"))
    return f"Batter {int(float(batter_id))}" if batter_id is not None else "-"


def first_text(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        if column not in row.index:
            continue
        value = clean_scalar(row.get(column))
        if value is not None and str(value).strip():
            return str(value).strip()
    return "-"


def build_starter_fatigue_lab_game_rows(
    game_log: list[dict[str, Any]],
    selected: pd.Series | None,
    selected_game_pk: int | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in enriched_fatigue_game_contexts(game_log):
        readiness, _ = calculate_pregame_readiness(
            age=clean_scalar(selected.get("Age")) if selected is not None else None,
            rest_days=row.get("rest_days"),
            start_number=row.get("start_number"),
            recent_7d_pitches=row.get("recent_7d_pitches"),
            previous_start_pitches=row.get("previous_start_pitches"),
        )
        pitches = NumberLike(row.get("pitches")).to_float(0)
        final_score = max(15, min(105, readiness - pitches * fatigue_rate_for_readiness(readiness)))
        rows.append(
            {
                "Date": row.get("game_date"),
                "Opponent": row.get("opponent_team"),
                "Pitches": int(pitches),
                "Rest Days": clean_scalar(row.get("rest_days")),
                "Start #": clean_scalar(row.get("start_number")),
                "Recent 7D Pitches": clean_scalar(row.get("recent_7d_pitches")),
                "Previous Start Pitches": clean_scalar(row.get("previous_start_pitches")),
                "Pregame Readiness": round(readiness, 1),
                "Final Fatigue Score": round(final_score, 1),
                "selected": int(float(row.get("game_pk"))) == selected_game_pk if clean_scalar(row.get("game_pk")) is not None else False,
            }
        )
    return sanitize_rows(rows)


def build_fatigue_game_context(game_log: list[dict[str, Any]], game_pk: int) -> dict[str, Any]:
    for row in enriched_fatigue_game_contexts(game_log):
        if clean_scalar(row.get("game_pk")) is not None and int(float(row["game_pk"])) == int(game_pk):
            return row
    return {}


def enriched_fatigue_game_contexts(game_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(game_log, key=lambda row: (str(row.get("game_date") or ""), NumberLike(row.get("game_pk")).to_float(0)))
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        date = pd.to_datetime(row.get("game_date"), errors="coerce")
        recent_pitches = 0
        if not pd.isna(date):
            for previous in rows[:index]:
                previous_date = pd.to_datetime(previous.get("game_date"), errors="coerce")
                if not pd.isna(previous_date) and 0 < (date - previous_date).days <= 7:
                    recent_pitches += int(NumberLike(previous.get("pitches")).to_float(0))
        previous_pitches = int(NumberLike(rows[index - 1].get("pitches")).to_float(0)) if index > 0 else 0
        copied = dict(row)
        copied["start_number"] = index + 1
        copied["recent_7d_pitches"] = recent_pitches
        copied["previous_start_pitches"] = previous_pitches
        enriched.append(copied)
    return enriched


def calculate_pregame_readiness(
    age: Any,
    rest_days: Any,
    start_number: Any,
    recent_7d_pitches: Any,
    previous_start_pitches: Any,
) -> tuple[float, list[dict[str, Any]]]:
    readiness = 100.0
    breakdown: list[dict[str, Any]] = []

    age_value = NumberLike(age).to_float(None)
    age_penalty = 0.0
    if age_value is not None:
        if age_value >= 35:
            age_penalty = -6
        elif age_value >= 31:
            age_penalty = -4
        elif age_value >= 26:
            age_penalty = -2
    readiness += age_penalty
    breakdown.append({"Factor": "Age recovery", "Value": clean_scalar(age_value), "Impact": age_penalty, "Note": "Older pitchers get a mild pregame recovery tax."})

    rest_value = NumberLike(rest_days).to_float(None)
    rest_impact = 0.0
    if rest_value is None:
        rest_impact = 0
    elif rest_value >= 6:
        rest_impact = 3
    elif rest_value == 5:
        rest_impact = 0
    elif rest_value == 4:
        rest_impact = -4
    elif rest_value == 3:
        rest_impact = -8
    else:
        rest_impact = -14
    readiness += rest_impact
    breakdown.append({"Factor": "Rest days", "Value": clean_scalar(rest_value), "Impact": rest_impact, "Note": "Short rest hurts readiness; 6+ days gives a small recovery bonus."})

    recent_value = NumberLike(recent_7d_pitches).to_float(0)
    breakdown.append({"Factor": "Recent 7D load", "Value": clean_scalar(recent_value), "Impact": 0, "Note": "Reference only for starters; previous start carries the workload penalty."})

    previous_value = NumberLike(previous_start_pitches).to_float(0)
    previous_penalty = 0.0
    if previous_value >= 115:
        previous_penalty = -7
    elif previous_value >= 105:
        previous_penalty = -4
    elif previous_value >= 90:
        previous_penalty = -2
    readiness += previous_penalty
    breakdown.append({"Factor": "Previous start", "Value": clean_scalar(previous_value), "Impact": previous_penalty, "Note": "A heavy previous outing slightly lowers the next start."})

    start_value = NumberLike(start_number).to_float(None)
    season_penalty = 0.0
    if start_value is not None:
        if start_value >= 25:
            season_penalty = -6
        elif start_value >= 17:
            season_penalty = -4
        elif start_value >= 9:
            season_penalty = -2
    readiness += season_penalty
    breakdown.append({"Factor": "Season start #", "Value": clean_scalar(start_value), "Impact": season_penalty, "Note": "Small season-level wear penalty as starts accumulate."})

    readiness = max(60.0, min(105.0, readiness))
    breakdown.append({"Factor": "Clamped readiness", "Value": round(readiness, 1), "Impact": 0, "Note": "Prototype output is bounded to 60-105."})
    return readiness, sanitize_rows(breakdown)


def fatigue_rate_for_readiness(readiness: float) -> float:
    if readiness >= 95:
        return 0.65
    if readiness >= 85:
        return 0.75
    return 0.85


class NumberLike:
    def __init__(self, value: Any) -> None:
        self.value = value

    def to_float(self, default: float | None) -> float | None:
        if self.value is None:
            return default
        try:
            number = float(self.value)
        except (TypeError, ValueError):
            return default
        if math.isnan(number) or math.isinf(number):
            return default
        return number


def build_starter_pitch_profile(year: int, selected: pd.Series | None) -> list[dict[str, Any]]:
    if selected is None:
        return []
    pitcher_id = clean_scalar(selected.get("MLBAMID"))
    if pitcher_id is None:
        return []
    pitch_df = load_pitcher_cached_season(year, int(float(pitcher_id)), settings.data_dir)
    if pitch_df.empty or "pitch_name" not in pitch_df.columns:
        return []
    df = pitch_df.copy()
    for col in ["release_speed", "pfx_x", "pfx_z"]:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    total = max(len(df), 1)
    grouped = (
        df.groupby("pitch_name", dropna=False)
        .agg(
            pitches=("pitch_name", "size"),
            release_speed=("release_speed", "mean"),
            h_break=("pfx_x", "mean"),
            v_break=("pfx_z", "mean"),
        )
        .reset_index()
    )
    grouped["usage_pct"] = grouped["pitches"] / total * 100
    grouped["h_break"] = grouped["h_break"] * 12
    grouped["v_break"] = grouped["v_break"] * 12
    grouped = grouped.sort_values("pitches", ascending=False)
    return sanitize_rows(grouped[PITCH_PROFILE_COLUMNS].to_dict("records"))


def build_bullpen_role_usage(selected: pd.Series | None) -> list[dict[str, Any]]:
    if selected is None:
        return []
    groups = {
        "Role": ["G", "GR", "GF", "SVOpp", "SVSit", "SV", "BSv", "Hold"],
        "Inherited": ["IR", "IS", "IS%"],
        "Leverage": ["aLI", "LevHi", "LevMd", "LevLo"],
        "Situation": ["Ahd", "Tie", "Bhd", "Runr", "Empt"],
        "Workload": ["Out/GR", "Pit/GR", "IP"],
    }
    rows: list[dict[str, Any]] = []
    for group, keys in groups.items():
        for key in keys:
            rows.append({"Metric": key, "Value": clean_scalar(selected.get(key)), "Group": group})
    return rows


def build_bullpen_role_usage_horizontal(selected: pd.Series | None) -> list[dict[str, Any]]:
    rows = build_bullpen_role_usage(selected)
    if not rows:
        return []
    return [{str(row["Metric"]): clean_scalar(row.get("Value")) for row in rows}]


def build_reliever_fatigue_table(
    year: int,
    relievers: pd.DataFrame,
    selected_date: str | None = None,
    usage: pd.DataFrame | None = None,
    usage_groups: dict[tuple[int, str], pd.DataFrame] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    usage_df = usage if usage is not None else prepare_bullpen_usage_rows(load_bullpen_usage_rows(year, settings.data_dir))
    grouped_usage = usage_groups if usage_groups is not None else build_bullpen_usage_groups(usage_df)
    for _, reliever in relievers.iterrows():
        context = build_reliever_fatigue_context(year, reliever, selected_date, usage_df, grouped_usage)
        readiness, _ = calculate_reliever_readiness(context, reliever)
        rows.append(
            {
                "Name": clean_scalar(reliever.get("Name")),
                "Team": clean_scalar(reliever.get("Team")),
                **context,
                "aLI": clean_scalar(reliever.get("aLI")),
                "Out/GR": clean_scalar(reliever.get("Out/GR")),
                "Readiness": round(readiness, 1),
            }
        )
    return sorted(sanitize_rows(rows), key=lambda row: NumberLike(row.get("Readiness")).to_float(0) or 0, reverse=True)


def prepare_bullpen_usage_rows(usage: pd.DataFrame) -> pd.DataFrame:
    if usage.empty:
        return usage
    working = usage.copy()
    working["MLBAMID"] = pd.to_numeric(working["MLBAMID"], errors="coerce")
    working["Team"] = working["Team"].astype(str).str.upper().str.strip()
    working["game_date"] = pd.to_datetime(working["game_date"], errors="coerce")
    working = working.dropna(subset=["MLBAMID", "Team", "game_date"]).copy()
    working["MLBAMID"] = working["MLBAMID"].astype(int)
    working["game_day"] = working["game_date"].dt.normalize()
    return working.reset_index(drop=True)


def build_bullpen_usage_groups(usage: pd.DataFrame) -> dict[tuple[int, str], pd.DataFrame]:
    if usage.empty:
        return {}
    return {
        (int(player_id), str(team)): group.reset_index(drop=True)
        for (player_id, team), group in usage.groupby(["MLBAMID", "Team"], sort=False)
    }


def build_reliever_fatigue_context(
    year: int,
    selected: pd.Series | None,
    selected_date: str | None = None,
    usage: pd.DataFrame | None = None,
    usage_groups: dict[tuple[int, str], pd.DataFrame] | None = None,
) -> dict[str, Any]:
    pitcher_id = clean_scalar(selected.get("MLBAMID")) if selected is not None else None
    team = normalize_team_code(selected.get("Team")) if selected is not None else None
    default_context = {
        "Pitches Yesterday": 0,
        "Pitches Last 3": 0,
        "Pitches Last 7": 0,
        "Appearances Last 3": 0,
        "Appearances Last 7": 0,
        "Back-to-Back": "N",
        "Rest Days": None,
        "availability_date": selected_date,
    }
    if pitcher_id is None or team is None:
        return default_context

    usage_df = usage if usage is not None else prepare_bullpen_usage_rows(load_bullpen_usage_rows(year, settings.data_dir))
    if usage_df.empty:
        return default_context
    grouped_usage = usage_groups if usage_groups is not None else build_bullpen_usage_groups(usage_df)
    reliever_usage = grouped_usage.get((int(float(pitcher_id)), team), pd.DataFrame()).copy()
    if reliever_usage.empty:
        return default_context

    end_date = pd.to_datetime(selected_date, errors="coerce") if selected_date else reliever_usage["game_date"].max()
    if pd.isna(end_date):
        return default_context
    end_date = pd.Timestamp(end_date).normalize()

    last3_start = end_date - pd.Timedelta(days=2)
    last7_start = end_date - pd.Timedelta(days=6)
    yesterday = end_date - pd.Timedelta(days=1)
    day_before_yesterday = end_date - pd.Timedelta(days=2)
    active = reliever_usage[reliever_usage["game_day"].le(end_date)].copy()
    if active.empty:
        return {**default_context, "availability_date": end_date.strftime("%Y-%m-%d")}

    last_game = active["game_day"].max()
    rest_days = int((end_date - last_game).days) if not pd.isna(last_game) else None
    pitches_yesterday = int((reliever_usage["game_day"] == yesterday).sum())
    pitches_day_before = int((reliever_usage["game_day"] == day_before_yesterday).sum())
    last3 = reliever_usage[reliever_usage["game_day"].between(last3_start, end_date)]
    last7 = reliever_usage[reliever_usage["game_day"].between(last7_start, end_date)]
    return {
        "Pitches Yesterday": pitches_yesterday,
        "Pitches Last 3": int(len(last3)),
        "Pitches Last 7": int(len(last7)),
        "Appearances Last 3": int(last3["game_day"].nunique()),
        "Appearances Last 7": int(last7["game_day"].nunique()),
        "Back-to-Back": "Y" if pitches_yesterday > 0 and pitches_day_before > 0 else "N",
        "Rest Days": rest_days,
        "availability_date": end_date.strftime("%Y-%m-%d"),
    }


def calculate_reliever_readiness(context: dict[str, Any], selected: pd.Series | None) -> tuple[float, list[dict[str, Any]]]:
    readiness = 100.0
    breakdown: list[dict[str, Any]] = []

    yesterday = NumberLike(context.get("Pitches Yesterday")).to_float(0) or 0
    yesterday_impact = 0.0
    if yesterday > 25:
        yesterday_impact = -14
    elif yesterday > 15:
        yesterday_impact = -8
    elif yesterday > 0:
        yesterday_impact = -4
    readiness += yesterday_impact
    breakdown.append({"Factor": "Yesterday pitches", "Value": yesterday, "Impact": yesterday_impact, "Note": "Most important reliever fatigue signal."})

    last3 = NumberLike(context.get("Pitches Last 3")).to_float(0) or 0
    last3_impact = 0.0
    if last3 > 70:
        last3_impact = -12
    elif last3 > 50:
        last3_impact = -8
    elif last3 > 30:
        last3_impact = -4
    readiness += last3_impact
    breakdown.append({"Factor": "Last 3 days", "Value": last3, "Impact": last3_impact, "Note": "Short-term bullpen availability pressure."})

    last7 = NumberLike(context.get("Pitches Last 7")).to_float(0) or 0
    last7_impact = 0.0
    if last7 > 130:
        last7_impact = -9
    elif last7 > 100:
        last7_impact = -6
    elif last7 > 70:
        last7_impact = -3
    readiness += last7_impact
    breakdown.append({"Factor": "Recent 7D load", "Value": last7, "Impact": last7_impact, "Note": "Broader recent workload signal for relievers."})

    back_to_back = context.get("Back-to-Back") == "Y"
    b2b_impact = -6 if back_to_back else 0
    readiness += b2b_impact
    breakdown.append({"Factor": "Back-to-back", "Value": context.get("Back-to-Back"), "Impact": b2b_impact, "Note": "Penalty if used on both prior two days."})

    ali = NumberLike(selected.get("aLI") if selected is not None else None).to_float(0) or 0
    leverage_impact = 0.0
    if ali >= 1.8:
        leverage_impact = -5
    elif ali >= 1.3:
        leverage_impact = -3
    readiness += leverage_impact
    breakdown.append({"Factor": "Leverage stress", "Value": clean_scalar(ali), "Impact": leverage_impact, "Note": "Higher leverage roles get a small stress tax."})

    out_per_gr = NumberLike(selected.get("Out/GR") if selected is not None else None).to_float(0) or 0
    multi_impact = 0.0
    if out_per_gr >= 4.5:
        multi_impact = -4
    elif out_per_gr >= 3.5:
        multi_impact = -2
    readiness += multi_impact
    breakdown.append({"Factor": "Multi-inning role", "Value": clean_scalar(out_per_gr), "Impact": multi_impact, "Note": "Longer outings tend to cost more recovery."})

    rest_days = NumberLike(context.get("Rest Days")).to_float(None)
    rest_impact = 0.0
    if rest_days is not None and rest_days >= 3:
        rest_impact = 3
    readiness += rest_impact
    breakdown.append({"Factor": "Rest days", "Value": clean_scalar(rest_days), "Impact": rest_impact, "Note": "Three or more days off gives a small recovery bonus."})

    readiness = max(35.0, min(100.0, readiness))
    breakdown.append({"Factor": "Clamped readiness", "Value": round(readiness, 1), "Impact": 0, "Note": "Prototype output is bounded to 35-100."})
    return readiness, sanitize_rows(breakdown)


def select_availability_team(team: str | None, teams: list[str], selected: pd.Series | None = None) -> str | None:
    if team and team != "All":
        return normalize_team_code(team)
    if selected is not None:
        selected_team = normalize_team_code(selected.get("Team"))
        if selected_team:
            return selected_team
    valid_teams = [normalize_team_code(value) for value in teams]
    valid_teams = [value for value in valid_teams if value]
    return valid_teams[0] if valid_teams else None


def normalize_team_code(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text or text in {"-", "FA", "TOT", "ALL", "NAN", "NONE"}:
        return None
    aliases = {
        "KCR": "KC",
        "KAN": "KC",
        "ARI": "AZ",
        "SDP": "SD",
        "SFG": "SF",
        "TBR": "TB",
        "WSN": "WSH",
        "CHW": "CWS",
    }
    return aliases.get(text, text)


def build_bullpen_availability_table(
    year: int,
    team: str | None,
    selected_date: str | None = None,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    columns = BULLPEN_AVAILABILITY_COLUMNS
    empty = pd.DataFrame(columns=columns)
    if not team:
        return empty

    data_root = data_dir or settings.data_dir
    roster = load_bullpen_roster(year, data_root)
    usage = load_bullpen_usage_rows(year, data_root)
    if roster.empty or usage.empty:
        return empty

    team_code = normalize_team_code(team)
    if not team_code:
        return empty
    roster_team = roster[roster["Team"].astype(str).str.upper().eq(team_code)].copy()
    if roster_team.empty:
        return empty

    usage_team = usage[usage["Team"].astype(str).str.upper().eq(team_code)].copy()
    if usage_team.empty:
        return empty

    usage_team["game_date"] = pd.to_datetime(usage_team["game_date"], errors="coerce")
    usage_team = usage_team.dropna(subset=["game_date"]).copy()
    if usage_team.empty:
        return empty

    end_date = pd.to_datetime(selected_date, errors="coerce") if selected_date else usage_team["game_date"].max()
    if pd.isna(end_date):
        return empty
    end_date = pd.Timestamp(end_date).normalize()
    active_start = end_date - pd.Timedelta(days=11)
    recent_start = end_date - pd.Timedelta(days=2)

    active_ids = set(
        pd.to_numeric(
            usage_team.loc[usage_team["game_date"].between(active_start, end_date), "MLBAMID"],
            errors="coerce",
        )
        .dropna()
        .astype(int)
        .tolist()
    )
    if active_ids:
        roster_team = roster_team[roster_team["MLBAMID"].isin(active_ids)].copy()
    if roster_team.empty:
        return empty

    recent = usage_team[usage_team["game_date"].between(recent_start, end_date)].copy()
    grouped = (
        recent.groupby(["MLBAMID"], dropna=False)
        .agg(
            **{
                "Pitches Last 3": ("MLBAMID", "size"),
                "Pitches Yesterday": ("game_date", lambda value: int((value.dt.normalize() == end_date).sum())),
                "Last Game": ("game_date", "max"),
            }
        )
        .reset_index()
    )
    availability = roster_team.merge(grouped, on="MLBAMID", how="left")
    availability["Pitches Last 3"] = pd.to_numeric(availability["Pitches Last 3"], errors="coerce").fillna(0).astype(int)
    availability["Pitches Yesterday"] = pd.to_numeric(availability["Pitches Yesterday"], errors="coerce").fillna(0).astype(int)
    availability["Last Game"] = pd.to_datetime(availability["Last Game"], errors="coerce").dt.strftime("%Y-%m-%d")
    availability["Availability"] = (45 - availability["Pitches Last 3"]).clip(lower=0, upper=45)
    availability["hand_sort"] = availability["Throws"].map({"L": 0, "R": 1}).fillna(2)
    availability = availability.sort_values(["hand_sort", "Pitches Last 3", "Name"]).reset_index(drop=True)
    availability.attrs["availability_date"] = end_date.strftime("%Y-%m-%d")
    return availability[columns]


def load_bullpen_roster(year: int, data_dir: Path) -> pd.DataFrame:
    candidates = [
        data_dir / f"{int(year)}_pitcher_comparison_with_est_xera.csv",
        data_dir / f"{int(year)}_pitcher_comparison.csv",
    ]
    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        return pd.DataFrame(columns=["MLBAMID", "Name", "Team", "Throws"])

    roster = pd.read_csv(source, low_memory=False)
    required = {"player_id", "last_name, first_name", "team", "role"}
    if not required.issubset(roster.columns):
        return pd.DataFrame(columns=["MLBAMID", "Name", "Team", "Throws"])

    roster = roster[roster["role"].astype(str).str.upper().eq("RP")].copy()
    roster["MLBAMID"] = pd.to_numeric(roster["player_id"], errors="coerce")
    roster = roster.dropna(subset=["MLBAMID", "team"]).copy()
    roster["MLBAMID"] = roster["MLBAMID"].astype(int)
    roster["Name"] = roster["last_name, first_name"].map(format_statcast_name)
    roster["Team"] = roster["team"].astype(str).str.strip().str.upper()
    throw_col = "p_throws" if "p_throws" in roster.columns else ("throws" if "throws" in roster.columns else "")
    roster["Throws"] = roster[throw_col].astype(str).str.upper().str.strip() if throw_col else "R"
    roster["Throws"] = roster["Throws"].replace({"": "R", "NAN": "R"})
    return roster[["MLBAMID", "Name", "Team", "Throws"]].drop_duplicates(["MLBAMID", "Team"]).reset_index(drop=True)


def load_bullpen_usage_rows(year: int, data_dir: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return pd.DataFrame(columns=["MLBAMID", "Team", "game_date"])

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame(columns=["MLBAMID", "Team", "game_date"])
        available = {row[1] for row in conn.execute(f"PRAGMA table_info('{source_table}')").fetchall()}
        if not {"pitcher", "game_date"}.issubset(available):
            return pd.DataFrame(columns=["MLBAMID", "Team", "game_date"])

        team_expr = "pitcher_team" if "pitcher_team" in available else (
            "CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END"
            if {"inning_topbot", "home_team", "away_team"}.issubset(available)
            else "NULL"
        )
        game_type_clause = "game_type = 'R' AND" if "game_type" in available else ""
        usage = conn.execute(
            f"""
            SELECT
                CAST(pitcher AS BIGINT) AS MLBAMID,
                UPPER(TRIM(CAST({team_expr} AS VARCHAR))) AS Team,
                CAST(game_date AS DATE) AS game_date
            FROM {source_table}
            WHERE {game_type_clause}
                  pitcher IS NOT NULL
              AND game_date IS NOT NULL
              AND {team_expr} IS NOT NULL
            """
        ).fetchdf()

    return usage.dropna(subset=["MLBAMID", "Team", "game_date"]).reset_index(drop=True)


def build_bullpen_role_views(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    working = df.copy()
    working["gr"] = numeric_column(working, "GR")
    working["gf"] = numeric_column(working, "GF")
    working["svopp"] = numeric_column(working, "SVOpp")
    working["svsit"] = numeric_column(working, "SVSit")
    working["sv"] = numeric_column(working, "SV")
    working["bsv"] = numeric_column(working, "BSv")
    working["hold"] = numeric_column(working, "Hold")
    working["ir"] = numeric_column(working, "IR")
    working["is"] = numeric_column(working, "IS")
    working["is_pct"] = numeric_column(working, "IS%")
    working["ali"] = numeric_column(working, "aLI")
    working["lev_hi"] = numeric_column(working, "LevHi")
    working["lev_md"] = numeric_column(working, "LevMd")
    working["lev_lo"] = numeric_column(working, "LevLo")
    working["ahd"] = numeric_column(working, "Ahd")
    working["tie"] = numeric_column(working, "Tie")
    working["bhd"] = numeric_column(working, "Bhd")
    working["runr"] = numeric_column(working, "Runr")
    working["empt"] = numeric_column(working, "Empt")
    working["first_ip"] = numeric_column(working, "1stIP")
    working["more_than_3_outs"] = numeric_column(working, ">3o")
    working["fewer_than_3_outs"] = numeric_column(working, "<3o")
    working["multi_inning"] = numeric_column(working, "IPmult")
    working["zero_day_rest"] = numeric_column(working, "0DR")
    working["out_per_gr"] = numeric_column(working, "Out/GR")
    working["pit_per_gr"] = numeric_column(working, "Pit/GR")
    working["war"] = numeric_column(working, "WAR")

    working["gf_share"] = safe_rate(working["gf"], working["gr"])
    working["high_lev_share"] = safe_rate(working["lev_hi"], working["gr"])
    working["mid_lev_share"] = safe_rate(working["lev_md"], working["gr"])
    working["ahead_share"] = safe_rate(working["ahd"], working["gr"])
    working["tie_share"] = safe_rate(working["tie"], working["gr"])
    working["behind_share"] = safe_rate(working["bhd"], working["gr"])
    working["runner_share"] = safe_rate(working["runr"], working["gr"])
    working["empty_share"] = safe_rate(working["empt"], working["gr"])
    working["multi_share"] = safe_rate(working["multi_inning"], working["gr"])
    working["more_than_3_outs_share"] = safe_rate(working["more_than_3_outs"], working["gr"])
    working["fewer_than_3_outs_share"] = safe_rate(working["fewer_than_3_outs"], working["gr"])
    working["zero_rest_share"] = safe_rate(working["zero_day_rest"], working["gr"])
    working["save_share"] = safe_rate(working["svsit"], working["gr"])
    working["hold_share"] = safe_rate(working["hold"], working["gr"])
    working["save_hold_share"] = safe_rate(working["sv"] + working["hold"], working["svsit"])
    working["inherited_runner_share"] = safe_rate(working["ir"], working["gr"])

    working["PrimaryRole"] = working.apply(classify_bullpen_role, axis=1)
    working["RoleScore"] = (
        working["ali"].fillna(0) * 20
        + working["save_share"] * 25
        + working["hold_share"] * 20
        + working["multi_share"] * 15
        + working["high_lev_share"] * 20
    ).round(1)

    role_mix = working[["save_share", "hold_share", "high_lev_share", "multi_share", "tie_share", "behind_share"]].fillna(0)
    working["RoleConsistency"] = (role_mix.max(axis=1) * 100).round(1)
    working["Versatility"] = ((role_mix.gt(0.15).sum(axis=1) / role_mix.shape[1]) * 100).round(1)
    working["Fireman"] = (working["ali"] >= 1.45) & (working["inherited_runner_share"] >= 0.25)
    working["Durable"] = working["zero_rest_share"] >= 0.22
    working["LongWork"] = (working["out_per_gr"] >= 4.2) | (working["multi_share"] >= 0.28)
    working["SaveHold"] = (working["svsit"] >= 10) & (working["save_hold_share"] >= 0.65)
    working["TacticalScore"] = (
        working["ali"].fillna(0) * 18
        + working["save_hold_share"].fillna(0) * 18
        + working["inherited_runner_share"].fillna(0) * 14
        + working["zero_rest_share"].fillna(0) * 12
        + working["multi_share"].fillna(0) * 10
        + working["high_lev_share"].fillna(0) * 18
        + working["war"].fillna(0) * 2
    ).round(1)
    working["TacticalTags"] = working.apply(build_bullpen_tactical_tags, axis=1)

    role_board = (
        working[[
            "Name", "Team", "PrimaryRole", "RoleScore", "gr", "ali", "first_ip",
            "TacticalTags", "svsit", "sv", "bsv", "hold", "gf", "out_per_gr", "WAR",
            "MLBAMID", "PlayerId",
        ]]
        .rename(columns={
            "gr": "GR", "ali": "aLI", "first_ip": "1stIP", "svsit": "SVSit",
            "sv": "SV", "bsv": "BSv", "hold": "Hold", "gf": "GF", "out_per_gr": "Out/GR",
        })
        .sort_values(["PrimaryRole", "RoleScore", "Name"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    tactical = (
        working[[
            "Name", "Team", "PrimaryRole", "TacticalTags", "TacticalScore",
            "ali", "save_hold_share", "inherited_runner_share", "is_pct",
            "zero_rest_share", "multi_share", "out_per_gr", "WAR", "MLBAMID", "PlayerId",
        ]]
        .rename(columns={
            "ali": "aLI", "save_hold_share": "SH%", "inherited_runner_share": "IR/GR",
            "is_pct": "IS%", "zero_rest_share": "0DR%", "multi_share": "MultiInning%",
            "out_per_gr": "Out/GR",
        })
        .sort_values(["TacticalScore", "Name"], ascending=[False, True])
        .reset_index(drop=True)
    )
    usage_timing = (
        working[[
            "Name", "Team", "PrimaryRole", "first_ip", "ali", "high_lev_share", "mid_lev_share",
            "ahead_share", "tie_share", "behind_share", "runner_share", "empty_share",
            "multi_share", "zero_rest_share", "out_per_gr", "pit_per_gr", "MLBAMID", "PlayerId",
        ]]
        .rename(columns={
            "first_ip": "1stIP", "ali": "aLI", "high_lev_share": "HighLev%",
            "mid_lev_share": "MidLev%", "ahead_share": "Ahead%", "tie_share": "Tie%",
            "behind_share": "Behind%", "runner_share": "RunrOn%", "empty_share": "BasesEmpty%",
            "multi_share": "MultiInning%", "zero_rest_share": "ZeroRest%",
            "out_per_gr": "Out/GR", "pit_per_gr": "Pit/GR",
        })
        .sort_values(["aLI", "HighLev%", "Name"], ascending=[False, False, True])
        .reset_index(drop=True)
    )
    stability = (
        working[[
            "Name", "Team", "PrimaryRole", "RoleConsistency", "Versatility",
            "save_share", "hold_share", "high_lev_share", "multi_share",
            "more_than_3_outs_share", "fewer_than_3_outs_share", "MLBAMID", "PlayerId",
        ]]
        .rename(columns={
            "save_share": "SaveSit%", "hold_share": "Hold%", "high_lev_share": "HighLev%",
            "multi_share": "MultiInning%", "more_than_3_outs_share": ">3Outs%",
            "fewer_than_3_outs_share": "<3Outs%",
        })
        .sort_values(["RoleConsistency", "Versatility", "Name"], ascending=[False, False, True])
        .reset_index(drop=True)
    )

    for view in [usage_timing, stability, tactical]:
        for column in [
            "HighLev%", "MidLev%", "Ahead%", "Tie%", "Behind%", "RunrOn%", "BasesEmpty%",
            "MultiInning%", "ZeroRest%", "SaveSit%", "Hold%", ">3Outs%", "<3Outs%",
            "SH%", "IR/GR", "0DR%",
        ]:
            if column in view.columns:
                view[column] = (pd.to_numeric(view[column], errors="coerce") * 100).round(1)

    return role_board, usage_timing, stability, tactical


def classify_bullpen_role(row: pd.Series) -> str:
    is_closer = (
        row["svsit"] >= 12
        and row["sv"] >= 5
        and row["ali"] >= 1.25
        and (row["gf_share"] >= 0.35 or row["save_share"] >= 0.25)
    )
    if is_closer:
        return "Closer"

    is_setup = (
        row["hold"] >= 7
        and row["ali"] >= 1.05
        and (row["high_lev_share"] >= 0.25 or row["svsit"] >= 6)
    ) or (
        row["hold"] >= 4
        and row["ali"] >= 1.25
        and row["high_lev_share"] >= 0.35
    )
    if is_setup:
        return "Setup"

    if row["first_ip"] <= 2.0 and row["empty_share"] >= 0.6 and row["gr"] >= 5:
        return "Opener"

    has_long_workload = (
        (row["multi_share"] >= 0.38 and row["more_than_3_outs_share"] >= 0.30)
        or row["more_than_3_outs_share"] >= 0.45
        or row["out_per_gr"] >= 5.0
    )
    is_not_late_leverage_role = (
        row["ali"] < 1.05
        and row["hold"] < 5
        and row["svsit"] < 6
        and row["high_lev_share"] < 0.25
    )
    if has_long_workload and is_not_late_leverage_role:
        return "Long Relief"

    return "Middle Relief"


def build_bullpen_tactical_tags(row: pd.Series) -> str:
    tags: list[str] = []
    if row["Fireman"]:
        tags.append("Fireman")
    if row["SaveHold"]:
        tags.append("Save-Hold")
    if row["Durable"]:
        tags.append("Durable")
    if row["LongWork"]:
        tags.append("Long Work")
    return ", ".join(tags) if tags else "Standard"


def safe_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, pd.NA)
    return numerator.divide(denominator).fillna(0.0)


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column].astype(str).str.replace("%", "", regex=False), errors="coerce").fillna(0)


def rows_to_table(rows: list[dict[str, Any]], columns: list[str]) -> TablePayload:
    return TablePayload(
        columns=[{"key": column, "label": column} for column in columns],
        rows=sanitize_rows(rows),
    )


def dataframe_to_table(df: pd.DataFrame, columns: list[str]) -> TablePayload:
    present = [column for column in columns if column in df.columns]
    return rows_to_table(df[present].to_dict("records"), present)


def sanitize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: clean_scalar(value) for key, value in row.items()} for row in rows]


def clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def clean_name(value: object) -> str:
    text = str(value or "").replace("\xa0", " ").replace("?", " ").strip()
    return re.sub(r"[*#]+$", "", text).strip()


def format_statcast_name(value: object) -> str:
    text = clean_name(value)
    if "," not in text:
        return text
    last, first = [part.strip() for part in text.split(",", 1)]
    return clean_name(f"{first} {last}")


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean_name(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def damaged_latin_name_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[\*\#]+$", "", text).lower()
    text = re.sub(r"[^a-z0-9?]+", "", text)
    for vowel in "aeiou":
        text = text.replace(vowel, "?")
    text = text.replace("?", "")
    text = re.sub(r"\?+", "?", text)
    return text


def parse_numeric_series(series: pd.Series) -> pd.Series:
    if not pd.api.types.is_object_dtype(series):
        return series
    cleaned = series.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    return parsed.where(parsed.notna(), series)


def mean_value(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return None
    return round(float(values.mean()), 2)


def sum_value(df: pd.DataFrame, column: str) -> int | float | None:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return None
    value = float(values.sum())
    return int(value) if value.is_integer() else round(value, 2)


def _starter_dir(data_dir: Path) -> Path:
    return data_dir / "Starter"


def _reliever_dir(data_dir: Path) -> Path:
    return data_dir / "Reliever"
