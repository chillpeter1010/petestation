from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import numpy as np

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta, TablePayload
from app.api.schemas.personal import PersonalOverviewResponse
from app.core.config import settings
from app.ml.stuff_plus import load_artifact, score_pitch_types
from app.repositories.pitch_repository import (
    get_season_duckdb_path,
    load_league_pitch_movement,
    load_pitcher_cached_season,
    resolve_pitch_table,
)
from app.services.discipline_service import build_discipline_panel_groups, red_strike_zone_mask
from app.services.game_line_service import clean_pitcher_game_line, load_official_pitcher_game_line
from app.services.pitch_location_score_service import load_pitch_location_scores
from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores
from app.services.pitcher_service import clean_name, list_pitcher_options, normalize_name, normalize_role
from app.services.stamina_lab_service import load_pitch_stamina_state
from app.services.wpa_service import attach_plate_appearance_wpa, calibrate_pitcher_wpa, one_wpa_value_per_pa


PITCH_LABELS = {
    "FA": "Four-Seam",
    "SI": "Sinker",
    "FC": "Cutter",
    "FS": "Splitter",
    "SL": "Slider",
    "CU": "Curveball",
    "CH": "Changeup",
    "KC": "Knuckle Curve",
}
PITCH_NAME_ALIASES = {
    "4-Seam": "Four-Seam",
    "4-Seam Fastball": "Four-Seam",
    "Four-Seam Fastball": "Four-Seam",
    "Fastball": "Four-Seam",
    "Split-Finger": "Splitter",
}
PITCH_DISPLAY_NAMES = {"Four-Seam": "4-Seam"}
HIDDEN_PITCH_NAMES = {"Pitch Out", "Eephus", "nan", "NaN", "None", ""}
SWING_EVENTS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
    "missed_bunt",
}
WHIFF_EVENTS = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"}
CALLED_STRIKE_EVENTS = {"called_strike"}
IN_PLAY_EVENTS = {"hit_into_play", "hit_into_play_no_out", "hit_into_play_score"}
HIT_EVENTS = {"single", "double", "triple", "home_run"}
NON_AB_EVENTS = {"walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_bunt", "sac_fly_double_play", "catcher_interf"}
OUT_EVENTS = {
    "field_out",
    "force_out",
    "grounded_into_double_play",
    "double_play",
    "fielders_choice_out",
    "strikeout",
    "strikeout_double_play",
}
WALK_EVENTS = {"walk", "intent_walk"}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
SACRIFICE_EVENTS = {"sac_bunt", "sac_fly", "sac_fly_double_play"}
FIELDERS_CHOICE_EVENTS = {"fielders_choice", "fielders_choice_out", "fielder's_choice_out"}
ERROR_EVENTS = {"field_error"}
ADVANCE_ON_THROW_EVENTS = {"reached_on_throwing_error", "reached_on_error", "throwing_error"}
FOUL_EVENTS = {"foul", "foul_tip", "foul_bunt"}
BALL_EVENTS = {"ball", "blocked_ball", "ball_in_dirt", "hit_by_pitch", "pitchout"}
FASTBALL_TYPES = {"FF", "FA", "SI", "FC"}
BREAKING_TYPES = {"SL", "CU", "KC", "SV", "ST", "CS"}
PITCH_RESULT_GROUPS = {
    "called_strike": CALLED_STRIKE_EVENTS,
    "swing": SWING_EVENTS,
    "swinging_strike": WHIFF_EVENTS,
    "foul": FOUL_EVENTS,
    "ball": BALL_EVENTS,
    "in_play": IN_PLAY_EVENTS,
}
TIMING_PITCH_CODE_LABELS = {
    "FF": "4-Seam",
    "SI": "Sinker",
    "FC": "Cutter",
    "FS": "Splitter",
    "CH": "Changeup",
    "SL": "Slider",
    "ST": "Sweeper",
    "SV": "Slurve",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "KN": "Knuckleball",
    "FO": "Forkball",
}

STUFF_PITCH_TYPE_CODES = {
    "Four-Seam": "FF", "Sinker": "SI", "Cutter": "FC", "Slider": "SL",
    "Sweeper": "ST", "Curveball": "CU", "Knuckle Curve": "KC",
    "Changeup": "CH", "Splitter": "FS", "Forkball": "FO",
}
STUFF_PRIMARY_FASTBALL_CODES = {"FF", "SI", "FC"}
TIMING_NUMERIC_COLUMNS = [
    "miss_distance",
    "flawed_percent",
    "perfect_percent",
    "tied_up_percent",
    "avg_x_tied_up",
    "centered_percent",
    "flailed_percent",
    "avg_x_flail",
    "early_percent",
    "avg_y_early",
    "on_time_percent",
    "late_percent",
    "avg_y_late",
    "n_swings",
    "whiff_rate",
    "competitive_percent",
    "over_percent",
    "avg_z_over",
    "lined_up_percent",
    "under_percent",
    "avg_z_under",
]


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def dataframe_to_table_payload(df: pd.DataFrame) -> TablePayload:
    if df.empty:
        return TablePayload()
    display_df = df.drop(columns=["name_key"], errors="ignore").copy()
    rows = [{key: clean_value(value) for key, value in row.items()} for row in display_df.to_dict(orient="records")]
    columns = [{"key": column, "label": column} for column in display_df.columns]
    return TablePayload(columns=columns, rows=rows)


def display_pitch_name(value: object) -> str:
    text = str(value)
    return PITCH_DISPLAY_NAMES.get(text, text)


def canonical_pitch_name(value: object) -> str:
    text = str(value).strip()
    return PITCH_NAME_ALIASES.get(text, text)


def normalize_pitch_names(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or "pitch_name" not in data.columns:
        return data.copy()
    normalized = data.copy()
    normalized["pitch_name"] = normalized["pitch_name"].map(canonical_pitch_name)
    return normalized


def filter_display_pitch_rows(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or "pitch_name" not in data.columns:
        return data.copy()
    filtered = data.copy()
    return filtered.loc[~filtered["pitch_name"].astype(str).isin(HIDDEN_PITCH_NAMES)].copy()


def normalize_personal_name_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        working = df.copy()
        if "name_key" not in working.columns:
            working["name_key"] = pd.Series(dtype="object")
        return working

    working = df.copy()
    if "Name" not in working.columns:
        if "player_name" in working.columns:
            working["Name"] = working["player_name"]
        elif "last_name, first_name" in working.columns:
            working["Name"] = working["last_name, first_name"].astype(str).map(
                lambda value: " ".join(reversed([part.strip() for part in value.split(",", 1)]))
                if "," in value
                else value
            )

    if "MLBAMID" not in working.columns:
        if "player_id" in working.columns:
            working["MLBAMID"] = working["player_id"]
        elif "PlayerId" in working.columns:
            working["MLBAMID"] = working["PlayerId"]

    if "Name" in working.columns:
        working["Name"] = working["Name"].map(clean_name)
        working["name_key"] = working["Name"].map(normalize_name)
    elif "name_key" not in working.columns:
        working["name_key"] = pd.Series(dtype="object")

    return working


def personal_reference_paths(year: int, role: str, data_dir: Path) -> list[tuple[str, Path]]:
    role = normalize_role(role)
    if 2021 <= int(year) <= 2024:
        mlb_dir = data_dir / f"MLB{int(year)}"
        starter_dir = data_dir / "Starter"
        starter_dashboard = starter_dir / "2021_2026_starter_dashboard.csv"
        if role == "RP":
            reliever_dir = data_dir / "Reliever"
            dashboard_path = mlb_dir / f"{int(year)}_reliever.csv"
            if not dashboard_path.exists():
                dashboard_path = mlb_dir / f"{int(year)}_all_pitcher_standard.csv"
            return [
                ("dashboard", dashboard_path),
                ("br", reliever_dir / f"{int(year)}_BR_reliever.csv"),
                ("stuff", reliever_dir / f"{int(year)}_reliever_stuff.csv"),
                ("location", reliever_dir / f"{int(year)}_reliever_location.csv"),
                ("pitching", reliever_dir / f"{int(year)}_reliever_pitching.csv"),
            ]

        dashboard_path = starter_dir / f"{int(year)}_starter_dashboard.csv"
        if not dashboard_path.exists() and starter_dashboard.exists():
            dashboard_path = starter_dashboard
        if not dashboard_path.exists():
            dashboard_path = mlb_dir / f"{int(year)}_starter.csv"
        if not dashboard_path.exists():
            dashboard_path = mlb_dir / f"{int(year)}_all_pitcher_standard.csv"
        return [
            ("dashboard", dashboard_path),
            ("br", starter_dir / f"{int(year)}_starter_BR.csv"),
            ("stuff", starter_dir / f"{int(year)}_starter_stuff.csv"),
            ("location", starter_dir / f"{int(year)}_starter_location.csv"),
            ("pitching", starter_dir / f"{int(year)}_starter_pitching.csv"),
        ]

    if year == 2025:
        if role == "RP":
            reliever_dir = data_dir / "Reliever"
            return [
                ("dashboard", reliever_dir / "2025_reliever_standard.csv"),
                ("br", reliever_dir / "2025_BR_reliever.csv"),
                ("stuff", reliever_dir / "2025_reliever_stuff.csv"),
                ("location", reliever_dir / "2025_reliever_location.csv"),
                ("pitching", reliever_dir / "2025_reliever_pitching.csv"),
            ]

        starter_dir = data_dir / "Starter"
        return [
            ("dashboard", starter_dir / "2025_starter_dashboard.csv"),
            ("br", starter_dir / "2025_starter_BR.csv"),
            ("stuff", starter_dir / "2025_starter_stuff.csv"),
            ("location", starter_dir / "2025_starter_location.csv"),
            ("pitching", starter_dir / "2025_starter_pitching.csv"),
        ]

    if year == 2026:
        starter_dir = data_dir / "Starter"
        combined_dashboard = starter_dir / "2021_2026_starter_dashboard.csv"
        if combined_dashboard.exists():
            return [("dashboard", combined_dashboard)]
        return [("dashboard", starter_dir / "2026_pitcher_0428.csv")]

    return []


def load_personal_reference_data(
    year: int,
    role: str = "SP",
    data_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    loaded_frames = {
        "dashboard": pd.DataFrame(),
        "br": pd.DataFrame(),
        "stuff": pd.DataFrame(),
        "location": pd.DataFrame(),
        "pitching": pd.DataFrame(),
    }
    root = data_dir or settings.data_dir

    for key, path in personal_reference_paths(year, role, root):
        if path.exists():
            frame = pd.read_csv(path, low_memory=False)
            if "Season" in frame.columns:
                frame = frame[pd.to_numeric(frame["Season"], errors="coerce").eq(int(year))].copy()
            loaded_frames[key] = frame

    dashboard = normalize_personal_name_frame(loaded_frames["dashboard"])
    br = normalize_personal_name_frame(loaded_frames["br"])
    stuff = normalize_personal_name_frame(loaded_frames["stuff"])
    location = normalize_personal_name_frame(loaded_frames["location"])
    pitching = normalize_personal_name_frame(loaded_frames["pitching"])

    if "NameASCII" in dashboard.columns and "Name" in dashboard.columns:
        dashboard["name_key"] = dashboard["NameASCII"].fillna(dashboard["Name"]).map(normalize_name)

    if "Stuff+" not in dashboard.columns and "Stuff+" in stuff.columns:
        dashboard = dashboard.merge(
            stuff[["name_key", "Stuff+", "Location+", "Pitching+"]].drop_duplicates(subset=["name_key"]),
            on="name_key",
            how="left",
        )

    return dashboard, br, stuff, location, pitching


def find_pitcher_row(df: pd.DataFrame, pitcher_id: int, pitcher_name: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    if "MLBAMID" in df.columns:
        ids = pd.to_numeric(df["MLBAMID"], errors="coerce")
        matched = df[ids == int(pitcher_id)]
        if not matched.empty:
            return matched
    if pitcher_name and "name_key" in df.columns:
        return df[df["name_key"] == normalize_name(pitcher_name)]
    return df.iloc[0:0]


def build_pitch_type_matrix(source_df: pd.DataFrame, pitcher_id: int, pitcher_name: str | None, value_label: str) -> pd.DataFrame:
    row_df = find_pitcher_row(source_df, pitcher_id=pitcher_id, pitcher_name=pitcher_name)
    if row_df.empty:
        return pd.DataFrame(columns=["Pitch", value_label])
    row = row_df.iloc[0]
    records = []
    for code, label in PITCH_LABELS.items():
        for prefix in ["Stf+", "Loc+", "Pit+"]:
            column = f"{prefix} {code}"
            if column in source_df.columns:
                records.append({"Pitch": label, "Metric": prefix, "Value": pd.to_numeric(row.get(column), errors="coerce")})
    if not records:
        return pd.DataFrame()
    matrix = pd.DataFrame(records).pivot(index="Pitch", columns="Metric", values="Value").reset_index()
    rename_map = {"Stf+": "Stuff+", "Loc+": "Location+", "Pit+": "Pitching+"}
    return matrix.rename(columns=rename_map).sort_values("Pitch").reset_index(drop=True)


def metric_from_row(row: pd.Series, key: str, label: str, unit: str | None = None) -> MetricItem:
    return MetricItem(key=key, label=label, value=clean_value(row.get(key)), unit=unit)


def build_overview_summary(dashboard_row: pd.DataFrame, selected_pitcher: dict[str, object]) -> list[MetricItem]:
    fallback_values = {
        "Team": selected_pitcher.get("team"),
        "GS": selected_pitcher.get("starts"),
        "IP": None,
        "ERA": None,
        "Stuff+": None,
        "WAR": None,
    }
    if dashboard_row.empty:
        return [MetricItem(key=key, label=key, value=value) for key, value in fallback_values.items()]

    row = dashboard_row.iloc[0]
    summary: list[MetricItem] = []
    for key, fallback in fallback_values.items():
        value = clean_value(row.get(key))
        summary.append(MetricItem(key=key, label=key, value=value if value is not None else fallback))
    return summary


def build_overview_percentile_profile(year: int, pitcher_id: int) -> list[dict[str, Any]]:
    # Lazy import avoids a module cycle: comparison_service reuses pitch helpers from this module.
    from app.services.comparison_service import PERIOD_METRIC_SPECS, build_metric_card, load_comparison_pool

    pool = load_comparison_pool(year)
    pitcher_row = pool[pool["player_id"].eq(int(pitcher_id))]
    if pitcher_row.empty:
        return []

    period_keys = {str(spec["key"]) for spec in PERIOD_METRIC_SPECS}
    metrics = [metric for metric in build_metric_card(pitcher_row.iloc[0], year) if metric.key in period_keys]
    return [metric.model_dump() for metric in metrics]


def _load_season_pitcher_game_lines(year: int) -> pd.DataFrame:
    csv_path = settings.data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}_pitcher_game_lines.csv.gz"
    if csv_path.exists():
        return pd.read_csv(csv_path)

    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return pd.DataFrame()
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if "pitcher_game_lines" not in tables:
                return pd.DataFrame()
            return conn.execute("SELECT * FROM pitcher_game_lines").fetchdf()
    except duckdb.Error:
        return pd.DataFrame()


def _safe_int(value: Any) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return int(numeric)


def _safe_float(value: Any, digits: int) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return round(float(numeric), digits)


def build_overview_game_log(year: int, pitcher_id: int, pitcher_name: str | None = None) -> pd.DataFrame:
    lines = _load_season_pitcher_game_lines(year)
    if lines.empty or "pitcher_id" not in lines.columns:
        return pd.DataFrame()

    lines = lines.copy()
    lines["pitcher_id"] = pd.to_numeric(lines["pitcher_id"], errors="coerce")
    lines = lines[lines["pitcher_id"] == int(pitcher_id)].copy()
    if lines.empty:
        return pd.DataFrame()

    pitch_df = load_pitcher_cached_season(
        year,
        pitcher_id,
        data_dir=settings.data_dir,
    )
    if not pitch_df.empty:
        pitch_df = filter_display_pitch_rows(normalize_pitch_names(pitch_df.copy()))

    pitch_mix_by_game: dict[Any, str] = {}
    home_runs_by_game: dict[Any, int] = {}
    hard_hits_by_game: dict[Any, int] = {}
    if not pitch_df.empty and "game_pk" in pitch_df.columns:
        if "pitch_name" in pitch_df.columns:
            for game_pk, game_df in pitch_df.groupby("game_pk", dropna=False):
                counts = game_df["pitch_name"].fillna("Unknown").astype(str).map(display_pitch_name).value_counts()
                total = int(counts.sum())
                if total:
                    pitch_mix_by_game[game_pk] = ", ".join(
                        f"{pitch} {count / total * 100:.0f}%" for pitch, count in counts.items()
                    )
        if "events" in pitch_df.columns:
            events = pitch_df["events"].fillna("").astype(str).str.lower()
            home_run_df = pitch_df.assign(_is_hr=events.eq("home_run"))
            home_runs_by_game = home_run_df.groupby("game_pk")["_is_hr"].sum().astype(int).to_dict()
        if "launch_speed" in pitch_df.columns:
            hard_hit_df = pitch_df.assign(_is_hh=pd.to_numeric(pitch_df["launch_speed"], errors="coerce").ge(95))
            hard_hits_by_game = hard_hit_df.groupby("game_pk")["_is_hh"].sum().astype(int).to_dict()

    rows: list[dict[str, Any]] = []
    for row in lines.sort_values(["game_date", "game_pk"], ascending=[True, True]).to_dict(orient="records"):
        outs = outs_from_ip_value(row.get("ip"))
        era = None
        if outs:
            earned_runs = _safe_int(row.get("earned_runs")) or 0
            era = round(earned_runs * 27 / outs, 2)
        game_pk = row.get("game_pk")
        rows.append(
            {
                "Date": clean_value(row.get("game_date")),
                "Name": clean_value(row.get("pitcher_name")) or pitcher_name or "",
                "IP": clean_value(row.get("ip")),
                "H": _safe_int(row.get("hits")),
                "R": _safe_int(row.get("runs")),
                "ER": _safe_int(row.get("earned_runs")),
                "BB": _safe_int(row.get("walks")),
                "SO": _safe_int(row.get("strikeouts")),
                "HR": int(home_runs_by_game.get(game_pk, 0)),
                "NP": _safe_int(row.get("pitches")),
                "ERA": era,
                "GS": calculate_game_score(
                    row.get("ip"),
                    row.get("hits"),
                    row.get("runs"),
                    row.get("earned_runs"),
                    row.get("walks"),
                    row.get("strikeouts"),
                ),
                "Pitch Types": pitch_mix_by_game.get(game_pk, "-"),
                "HH": int(hard_hits_by_game.get(game_pk, 0)),
                "Game PK": _safe_int(game_pk),
            }
        )
    return pd.DataFrame(rows)


def get_personal_overview(year: int, pitcher_id: int, role: str = "SP") -> PersonalOverviewResponse:
    pitcher_options = list_pitcher_options(year=year, role=role)
    selected = next((pitcher for pitcher in pitcher_options if pitcher.value == int(pitcher_id)), None)
    selected_pitcher = selected.model_dump() if selected else {"value": int(pitcher_id), "role": normalize_role(role)}
    pitcher_name = str(selected_pitcher.get("name") or "")

    dashboard_df, br_df, stuff_df, location_df, pitching_df = load_personal_reference_data(year=year, role=role)
    dashboard_row = find_pitcher_row(dashboard_df, pitcher_id=pitcher_id, pitcher_name=pitcher_name)
    br_row = find_pitcher_row(br_df, pitcher_id=pitcher_id, pitcher_name=pitcher_name)
    game_log = build_overview_game_log(year=year, pitcher_id=pitcher_id, pitcher_name=pitcher_name)

    stuff_matrix = build_pitch_type_matrix(stuff_df, pitcher_id, pitcher_name, "Stuff+")
    if not stuff_matrix.empty:
        if "Location+" not in stuff_matrix.columns:
            stuff_matrix = stuff_matrix.merge(
                build_pitch_type_matrix(location_df, pitcher_id, pitcher_name, "Location+"),
                on="Pitch",
                how="left",
            )
        if "Pitching+" not in stuff_matrix.columns:
            stuff_matrix = stuff_matrix.merge(
                build_pitch_type_matrix(pitching_df, pitcher_id, pitcher_name, "Pitching+"),
                on="Pitch",
                how="left",
            )

    return PersonalOverviewResponse(
        meta=ResponseMeta(year=year),
        pitcher_id=int(pitcher_id),
        selected_pitcher=selected_pitcher,
        summary=build_overview_summary(dashboard_row, selected_pitcher),
        charts={"percentile_profile": build_overview_percentile_profile(year, pitcher_id)},
        tables={
            "dashboard": dataframe_to_table_payload(dashboard_row),
            "br": dataframe_to_table_payload(br_row),
            "pitch_type_matrix": dataframe_to_table_payload(stuff_matrix),
            "game_log": dataframe_to_table_payload(game_log),
        },
    )


def build_pitch_type_distribution(pitch_df: pd.DataFrame) -> list[dict[str, Any]]:
    if pitch_df.empty:
        return []
    pitch_column = "pitch_name" if "pitch_name" in pitch_df.columns else ("pitch_type" if "pitch_type" in pitch_df.columns else "")
    if not pitch_column:
        return []
    counts = (
        pitch_df[pitch_column]
        .fillna("Unknown")
        .astype(str)
        .value_counts()
        .rename_axis("pitch")
        .reset_index(name="count")
    )
    total = int(counts["count"].sum())
    counts["rate"] = counts["count"] / total if total else 0
    return [{key: clean_value(value) for key, value in row.items()} for row in counts.to_dict(orient="records")]


def build_pitch_location_scatter(pitch_df: pd.DataFrame) -> list[dict[str, Any]]:
    required_cols = {"plate_x", "plate_z", "pitch_name"}
    if pitch_df.empty or not required_cols.issubset(pitch_df.columns):
        return []
    scored = pitch_df.copy()
    if "pitch_stuff_plus" not in scored.columns:
        scored["pitch_stuff_plus"] = load_pitch_stuff_scores(scored)
    if "location_plus_pitch" not in scored.columns:
        scored["location_plus_pitch"] = load_pitch_location_scores(scored)
    columns = [
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "plate_x",
        "plate_z",
        "pitch_name",
        "pitch_type",
        "description",
        "events",
        "stand",
        "zone",
        "balls",
        "strikes",
        "bb_type",
        "release_speed",
        "catcher_name",
        "play_id",
        "video_url",
        "pitch_stuff_plus",
        "location_plus_pitch",
        "stamina_plus_trait",
        "stamina_expected_retention_delta",
        "stamina_expected_stuff_plus",
        "stamina_early_stuff_baseline",
        "stamina_reliability",
        "stamina_sample_label",
        "stamina_role",
    ]
    available_columns = [column for column in columns if column in scored.columns]
    working = scored[available_columns].copy()
    working["plate_x"] = pd.to_numeric(working["plate_x"], errors="coerce")
    working["plate_z"] = pd.to_numeric(working["plate_z"], errors="coerce")
    working = working.dropna(subset=["plate_x", "plate_z", "pitch_name"])
    if working.empty:
        return []
    return [{key: clean_value(value) for key, value in row.items()} for row in working.to_dict(orient="records")]


def get_personal_pitch_data(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 250,
) -> AnalysisResponse:
    pitch_df = load_pitcher_cached_season(
        year=year,
        pitcher_id=pitcher_id,
        data_dir=settings.data_dir,
        start_date=start_date,
        end_date=end_date,
    )
    game_dates = pd.to_datetime(pitch_df.get("game_date"), errors="coerce") if not pitch_df.empty else pd.Series(dtype="datetime64[ns]")
    sample_columns = [
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "pitch_name",
        "pitch_type",
        "release_speed",
        "description",
        "events",
        "stand",
        "balls",
        "strikes",
        "plate_x",
        "plate_z",
        "pfx_x",
        "pfx_z",
    ]
    available_columns = [column for column in sample_columns if column in pitch_df.columns]
    sample_df = pitch_df[available_columns].head(max(0, min(limit, 1000))).copy() if available_columns else pd.DataFrame()

    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="pitches", label="Pitches", value=int(len(pitch_df))),
            MetricItem(key="games", label="Games", value=int(pitch_df["game_pk"].nunique()) if "game_pk" in pitch_df.columns else 0),
            MetricItem(key="first_game_date", label="First Game Date", value=game_dates.min().date().isoformat() if game_dates.notna().any() else None),
            MetricItem(key="last_game_date", label="Last Game Date", value=game_dates.max().date().isoformat() if game_dates.notna().any() else None),
        ],
        charts={
            "pitch_type_distribution": build_pitch_type_distribution(pitch_df),
            "pitch_location_scatter": build_pitch_location_scatter(pitch_df),
        },
        tables={"sample_pitches": dataframe_to_table_payload(sample_df)},
    )


def load_personal_pitch_df(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    pitch_df = load_pitcher_cached_season(
        year=year,
        pitcher_id=pitcher_id,
        data_dir=settings.data_dir,
        start_date=start_date,
        end_date=end_date,
    )
    return filter_display_pitch_rows(normalize_pitch_names(pitch_df))


def infer_pitcher_hand(data: pd.DataFrame) -> str:
    if data.empty or "p_throws" not in data.columns:
        return "Unknown"
    hands = data["p_throws"].dropna().astype(str).str.upper().str.strip()
    hands = hands[hands.isin(["L", "R"])]
    return hands.mode().iloc[0] if not hands.empty else "Unknown"


def build_pitch_movement_summary(data: pd.DataFrame) -> pd.DataFrame:
    required_cols = {"pitch_name", "pfx_x", "pfx_z"}
    if data.empty or not required_cols.issubset(data.columns):
        return pd.DataFrame()
    working = data.copy()
    working["pitch_name"] = working["pitch_name"].astype(str)
    working["pfx_x"] = pd.to_numeric(working["pfx_x"], errors="coerce") * -12
    working["pfx_z"] = pd.to_numeric(working["pfx_z"], errors="coerce") * 12
    if "release_speed" in working.columns:
        working["release_speed"] = pd.to_numeric(working["release_speed"], errors="coerce")
    working = working.dropna(subset=["pitch_name", "pfx_x", "pfx_z"]).copy()
    if working.empty:
        return pd.DataFrame()
    summary = (
        working.groupby("pitch_name", dropna=False)
        .agg(
            pitches=("pitch_name", "size"),
            h_break=("pfx_x", "mean"),
            v_break=("pfx_z", "mean"),
            release_speed=("release_speed", "mean") if "release_speed" in working.columns else ("pitch_name", "size"),
        )
        .reset_index()
    )
    total = float(summary["pitches"].sum())
    summary["usage_pct"] = np.where(total > 0, summary["pitches"] / total * 100, np.nan)
    summary["Pitch"] = summary["pitch_name"].map(display_pitch_name)
    return summary.sort_values("usage_pct", ascending=False).reset_index(drop=True)


def build_movement_scatter_rows(data: pd.DataFrame) -> list[dict[str, Any]]:
    if data.empty or not {"pitch_name", "pfx_x", "pfx_z"}.issubset(data.columns):
        return []
    scatter_df = data.copy()
    scatter_df["pitch_name"] = scatter_df["pitch_name"].map(display_pitch_name)
    scatter_df["h_break"] = pd.to_numeric(scatter_df["pfx_x"], errors="coerce") * -12
    scatter_df["v_break"] = pd.to_numeric(scatter_df["pfx_z"], errors="coerce") * 12
    if "release_speed" in scatter_df.columns:
        scatter_df["release_speed"] = pd.to_numeric(scatter_df["release_speed"], errors="coerce")
    if "arm_angle" in scatter_df.columns:
        scatter_df["arm_angle"] = pd.to_numeric(scatter_df["arm_angle"], errors="coerce")
    scatter_df = scatter_df.dropna(subset=["h_break", "v_break"])
    columns = [
        column
        for column in [
            "game_date", "game_pk", "at_bat_number", "pitch_number", "pitch_name", "pitch_type",
            "description", "events", "balls", "strikes", "plate_x", "plate_z", "h_break", "v_break",
            "release_speed", "arm_angle", "play_id", "video_url", "pitch_stuff_plus",
            "location_plus_pitch", "stamina_plus_trait", "stamina_expected_retention_delta",
            "stamina_expected_stuff_plus", "stamina_early_stuff_baseline", "stamina_reliability",
            "stamina_sample_label", "stamina_role",
        ]
        if column in scatter_df.columns
    ]
    return dataframe_to_table_payload(scatter_df[columns].copy()).rows


@lru_cache(maxsize=2)
def _load_personal_stuff_artifact(model_mtime: int, metadata_mtime: int):
    del model_mtime, metadata_mtime
    return load_artifact(settings.data_dir / "models" / "stuff_plus")


def score_pitch_stuff_uncached(data: pd.DataFrame, reference_data: pd.DataFrame) -> pd.DataFrame:
    """Attach an unshrunk Stuff+ score to each individual pitch."""

    if data.empty:
        return data.copy()
    artifact_dir = settings.data_dir / "models" / "stuff_plus"
    model_path = artifact_dir / "pete_stuff_pipeline.joblib"
    metadata_path = artifact_dir / "pete_stuff_metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        return data.copy()

    hand = infer_pitcher_hand(reference_data)
    hand_multiplier = -1.0 if hand == "L" else 1.0

    def prepare(source: pd.DataFrame) -> pd.DataFrame:
        prepared = source.copy()
        fallback_codes = prepared.get("pitch_name", pd.Series(index=prepared.index, dtype="object")).map(STUFF_PITCH_TYPE_CODES)
        if "pitch_type" in prepared.columns:
            raw_codes = prepared["pitch_type"].fillna("").astype(str).str.upper().str.strip()
            prepared["pitch_type"] = raw_codes.where(raw_codes.ne(""), fallback_codes)
        else:
            prepared["pitch_type"] = fallback_codes
        prepared["p_throws"] = hand
        prepared["pitches"] = 1
        prepared["release_speed"] = pd.to_numeric(prepared.get("release_speed"), errors="coerce")
        prepared["ivb"] = pd.to_numeric(prepared.get("pfx_z"), errors="coerce") * 12.0
        prepared["adj_hb"] = pd.to_numeric(prepared.get("pfx_x"), errors="coerce") * -12.0 * hand_multiplier
        prepared["release_spin_rate"] = pd.to_numeric(prepared.get("release_spin_rate"), errors="coerce")
        prepared["release_extension"] = pd.to_numeric(prepared.get("release_extension"), errors="coerce")
        prepared["release_pos_z"] = pd.to_numeric(prepared.get("release_pos_z"), errors="coerce")
        prepared["adj_release_pos_x"] = pd.to_numeric(prepared.get("release_pos_x"), errors="coerce") * hand_multiplier
        prepared["arm_angle"] = pd.to_numeric(prepared.get("arm_angle"), errors="coerce")
        spin_radians = np.deg2rad(pd.to_numeric(prepared.get("spin_axis"), errors="coerce"))
        prepared["spin_axis_x"] = np.cos(spin_radians)
        prepared["spin_axis_y"] = np.sin(spin_radians) * hand_multiplier
        return prepared

    reference = prepare(reference_data)
    fastballs = reference[reference["pitch_type"].isin(STUFF_PRIMARY_FASTBALL_CODES)]
    if fastballs.empty:
        primary_velo = primary_ivb = primary_hb = np.nan
    else:
        primary_code = fastballs["pitch_type"].value_counts().index[0]
        primary = fastballs[fastballs["pitch_type"].eq(primary_code)]
        primary_velo = primary["release_speed"].mean()
        primary_ivb = primary["ivb"].mean()
        primary_hb = primary["adj_hb"].mean()

    scored_input = prepare(data)
    scored_input["velo_diff_from_fastball"] = scored_input["release_speed"] - primary_velo
    scored_input["ivb_diff_from_fastball"] = scored_input["ivb"] - primary_ivb
    scored_input["hb_diff_from_fastball"] = scored_input["adj_hb"] - primary_hb
    valid = scored_input["pitch_type"].notna()
    if not valid.any():
        return data.copy()

    model, metadata = _load_personal_stuff_artifact(
        model_path.stat().st_mtime_ns,
        metadata_path.stat().st_mtime_ns,
    )
    pitch_scores = pd.Series(np.nan, index=scored_input.index, dtype="float64")
    valid_rows = scored_input.loc[valid]
    for start in range(0, len(valid_rows), 1000):
        batch = valid_rows.iloc[start:start + 1000]
        scored = score_pitch_types(model, metadata, batch, outing=False)
        pitch_scores.loc[batch.index] = scored["raw_stuff_plus"].to_numpy(dtype="float64")

    result = data.copy()
    result["pitch_stuff_plus"] = pitch_scores.round(1)
    return result


def add_pitch_stuff_scores(data: pd.DataFrame, reference_data: pd.DataFrame) -> pd.DataFrame:
    """Attach cached per-pitch Stuff+ values, scoring only cache misses as a fallback."""

    if data.empty:
        return data.copy()
    from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores

    result = data.copy()
    cached = load_pitch_stuff_scores(result)
    missing = cached.isna()
    if missing.any():
        fallback = score_pitch_stuff_uncached(result.loc[missing], reference_data)
        if "pitch_stuff_plus" in fallback.columns:
            cached.loc[missing] = pd.to_numeric(fallback["pitch_stuff_plus"], errors="coerce")
    result["pitch_stuff_plus"] = cached.round(1)
    return result


def build_league_movement_benchmarks(year: int) -> pd.DataFrame:
    cached = load_league_pitch_movement(year=year, data_dir=settings.data_dir)
    if cached.empty or not {"pitch_name", "pfx_x", "pfx_z", "p_throws"}.issubset(cached.columns):
        return pd.DataFrame()

    working = filter_display_pitch_rows(normalize_pitch_names(cached))
    working["pitch_name"] = working["pitch_name"].astype(str)
    working["p_throws"] = working["p_throws"].astype(str).str.upper().str.strip()
    working = working[working["p_throws"].isin(["L", "R"])].copy()
    working["pfx_x"] = pd.to_numeric(working["pfx_x"], errors="coerce") * -12
    working["pfx_z"] = pd.to_numeric(working["pfx_z"], errors="coerce") * 12
    if "release_speed" in working.columns:
        working["release_speed"] = pd.to_numeric(working["release_speed"], errors="coerce")
    working = working.dropna(subset=["pitch_name", "pfx_x", "pfx_z"]).copy()
    if working.empty:
        return pd.DataFrame()

    grouped = (
        working.groupby(["p_throws", "pitch_name"], dropna=False)
        .agg(
            league_pitches=("pitch_name", "size"),
            league_h_break=("pfx_x", "mean"),
            league_v_break=("pfx_z", "mean"),
            league_release_speed=("release_speed", "mean") if "release_speed" in working.columns else ("pitch_name", "size"),
        )
        .reset_index()
    )
    hand_totals = grouped.groupby("p_throws", dropna=False)["league_pitches"].transform("sum")
    grouped["league_usage_pct"] = np.where(hand_totals > 0, grouped["league_pitches"] / hand_totals * 100, np.nan)
    return grouped.reset_index(drop=True)


def build_movement_comparison_table(pitcher_df: pd.DataFrame, pitcher_hand: str, league_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = build_pitch_movement_summary(pitcher_df)
    if summary_df.empty:
        return pd.DataFrame()

    base = summary_df.rename(
        columns={
            "pitch_name": "Pitch Raw",
            "usage_pct": "Usage%",
            "h_break": "HB",
            "v_break": "IVB",
            "release_speed": "Velo",
        }
    ).copy()
    base["Pitch"] = base["Pitch Raw"].map(display_pitch_name)

    if league_df.empty or pitcher_hand not in {"L", "R"}:
        return base[["Pitch", "pitches", "Usage%", "HB", "IVB", "Velo"]]

    merged = base.merge(
        league_df[league_df["p_throws"].eq(pitcher_hand)][
            ["pitch_name", "league_usage_pct", "league_h_break", "league_v_break", "league_release_speed"]
        ],
        left_on="Pitch Raw",
        right_on="pitch_name",
        how="left",
    )
    hand_label = {"R": "RHP", "L": "LHP"}.get(pitcher_hand, pitcher_hand)
    merged[f"League {hand_label} Usage%"] = merged["league_usage_pct"]
    merged[f"League {hand_label} HB"] = merged["league_h_break"]
    merged[f"League {hand_label} IVB"] = merged["league_v_break"]
    merged[f"League {hand_label} Velo"] = merged["league_release_speed"]
    merged["Usage Diff"] = merged["Usage%"] - merged["league_usage_pct"]
    merged["HB Diff"] = merged["HB"] - merged["league_h_break"]
    merged["IVB Diff"] = merged["IVB"] - merged["league_v_break"]
    merged["Velo Diff"] = merged["Velo"] - merged["league_release_speed"]
    columns = [
        "Pitch",
        "pitches",
        "Usage%",
        f"League {hand_label} Usage%",
        "Usage Diff",
        "HB",
        f"League {hand_label} HB",
        "HB Diff",
        "IVB",
        f"League {hand_label} IVB",
        "IVB Diff",
        "Velo",
        f"League {hand_label} Velo",
        "Velo Diff",
    ]
    return merged[columns].sort_values("Usage%", ascending=False).reset_index(drop=True)


def filter_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip() and item.strip().lower() != "all"
    ]


def catcher_filter_ids(values: set[str]) -> set[str]:
    ids: set[str] = set()
    for value in values:
        if "(" in value and ")" in value:
            candidate = value.rsplit("(", 1)[-1].split(")", 1)[0].strip()
            if candidate.isdigit():
                ids.add(candidate)
                continue
        if value.startswith("Catcher "):
            candidate = value.replace("Catcher ", "", 1).strip()
            if candidate.isdigit():
                ids.add(candidate)
    return ids


def title_name_part(value: object) -> str:
    text = str(value).strip()
    lower = text.lower()
    if lower.startswith("mc") and len(lower) > 2:
        return f"Mc{lower[2:].capitalize()}"
    return lower.capitalize()


@lru_cache(maxsize=64)
def load_mlbam_name_lookup(player_ids: tuple[str, ...]) -> dict[str, str]:
    ids = tuple(sorted({str(player_id).strip() for player_id in player_ids if str(player_id).strip().isdigit()}))
    if not ids:
        return {}
    try:
        from pybaseball import playerid_reverse_lookup
    except Exception:
        return {}
    try:
        lookup = playerid_reverse_lookup([int(player_id) for player_id in ids], key_type="mlbam")
    except Exception:
        return {}
    if lookup.empty or "key_mlbam" not in lookup.columns:
        return {}

    working = lookup.copy()
    first = working.get("name_first", pd.Series("", index=working.index)).fillna("").astype(str).map(
        lambda value: " ".join(title_name_part(part) for part in value.split())
    )
    last = working.get("name_last", pd.Series("", index=working.index)).fillna("").astype(str).map(
        lambda value: " ".join(title_name_part(part) for part in value.split())
    )
    working["display_name"] = (first + " " + last).str.replace(r"\s+", " ", regex=True).str.strip()
    return {
        str(int(row["key_mlbam"])): str(row["display_name"])
        for _, row in working.dropna(subset=["key_mlbam"]).iterrows()
        if str(row["display_name"]).strip()
    }


@lru_cache(maxsize=8)
def load_season_catcher_lookup(year: int) -> dict[str, str]:
    db_path = get_season_duckdb_path(int(year), settings.data_dir)
    if not db_path.exists():
        return {}
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            source_table = resolve_pitch_table(tables)
            if not source_table:
                return {}
            available = {row[1] for row in conn.execute(f"PRAGMA table_info('{source_table}')").fetchall()}
            if "fielder_2" not in available:
                return {}
            ids_df = conn.execute(
                f"""
                SELECT DISTINCT CAST(fielder_2 AS VARCHAR) AS catcher_id
                FROM {source_table}
                WHERE game_type = 'R'
                  AND fielder_2 IS NOT NULL
                  AND CAST(fielder_2 AS VARCHAR) NOT IN ('', '0', 'nan', 'NaN')
                ORDER BY catcher_id
                """
            ).fetchdf()
    except Exception:
        return {}
    ids = tuple(ids_df["catcher_id"].dropna().astype(str).str.strip().tolist()) if not ids_df.empty else tuple()
    names = load_mlbam_name_lookup(ids)
    return {catcher_id: names.get(catcher_id, f"Catcher {catcher_id}") for catcher_id in ids}


def catcher_lookup_rows(data: pd.DataFrame, year: int | None = None) -> list[dict[str, str]]:
    if data.empty and year is None:
        return []
    ids: list[str] = []
    if not data.empty and "fielder_2" in data.columns:
        values = data["fielder_2"].dropna().astype(str).map(str.strip)
        ids = values[~values.str.lower().isin(["", "nan", "none", "null", "<na>", "0"])].unique().tolist()
    season_lookup = load_season_catcher_lookup(int(year)) if year is not None else {}
    local_lookup = load_mlbam_name_lookup(tuple(sorted(ids)))
    rows = []
    for catcher_id in sorted(ids):
        rows.append(
            {
                "catcher_id": catcher_id,
                "catcher_name": local_lookup.get(catcher_id) or season_lookup.get(catcher_id) or f"Catcher {catcher_id}",
            }
        )
    return rows


def catcher_names_to_ids(data: pd.DataFrame, names: set[str]) -> set[str]:
    if data.empty or "fielder_2" not in data.columns or not names:
        return set()
    lookup = {
        str(row["catcher_name"]): str(row["catcher_id"])
        for row in catcher_lookup_rows(data)
    }
    normalized_names = {str(name).strip() for name in names}
    return {catcher_id for name, catcher_id in lookup.items() if name in normalized_names}


def classify_in_play_result(data: pd.DataFrame) -> pd.Series:
    if data.empty:
        return pd.Series(dtype="object")
    description = data.get("description", pd.Series(dtype="object")).fillna("").astype(str).str.lower().str.strip()
    launch_speed = pd.to_numeric(data.get("launch_speed", pd.Series(index=data.index, dtype="float64")), errors="coerce")
    launch_angle = pd.to_numeric(data.get("launch_angle", pd.Series(index=data.index, dtype="float64")), errors="coerce")
    result = pd.Series("not_in_play", index=data.index, dtype="object")
    in_play_mask = description.isin(IN_PLAY_EVENTS)
    result.loc[in_play_mask] = "unclassified"

    valid_mask = in_play_mask & launch_speed.notna() & launch_angle.notna()
    speed = launch_speed.loc[valid_mask]
    angle = launch_angle.loc[valid_mask]

    barrel_mask = (((speed * 1.5) - angle >= 117) & ((speed + angle) >= 124) & (speed >= 98) & angle.between(4, 50))
    solid_mask = (((speed * 1.5) - angle >= 111) & ((speed + angle) >= 119) & (speed >= 95) & angle.between(0, 52))
    weak_mask = speed <= 59
    flare_mask = (
        (((speed * 2) - angle >= 87) & (angle <= 41) & ((speed * 2 + angle) <= 175) & ((speed + angle * 1.3) >= 89) & speed.between(59, 72))
        | (((speed + angle * 1.3) <= 112) & ((speed + angle * 1.55) >= 92) & speed.between(72, 86))
        | ((angle <= 20) & ((speed + angle * 2.4) >= 98) & speed.between(86, 95))
        | (((speed - angle) >= 76) & ((speed + angle * 2.4) >= 98) & (speed >= 95) & (angle <= 30))
    )
    under_mask = (speed + angle * 2) >= 116
    topped_mask = (speed + angle * 2) <= 116

    valid_index = speed.index
    result.loc[valid_index[topped_mask]] = "poorly_topped"
    result.loc[valid_index[under_mask]] = "poorly_under"
    result.loc[valid_index[flare_mask]] = "flare_burner"
    result.loc[valid_index[weak_mask]] = "poorly_weak"
    result.loc[valid_index[solid_mask]] = "solid_contact"
    result.loc[valid_index[barrel_mask]] = "barrel"
    return result


def apply_in_play_result_filter(data: pd.DataFrame, in_play_result: str | None) -> pd.DataFrame:
    results = set(filter_csv_values(in_play_result))
    if data.empty or not results:
        return data.copy()
    classified = classify_in_play_result(data)
    mask = classified.isin(results - {"hard_hit"})
    if "hard_hit" in results:
        description = data.get("description", pd.Series(index=data.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
        launch_speed = pd.to_numeric(data.get("launch_speed", pd.Series(index=data.index, dtype="float64")), errors="coerce")
        mask |= description.isin(IN_PLAY_EVENTS) & launch_speed.ge(95)
    return data[mask].copy()


def apply_pa_result_filter(data: pd.DataFrame, pa_result: str | None) -> pd.DataFrame:
    results = set(filter_csv_values(pa_result))
    if data.empty or not results:
        return data.copy()
    events = data.get("events", pd.Series(dtype="object")).fillna("").astype(str).str.lower().str.strip().replace("nan", "")
    no_result = events.eq("")
    single = events.eq("single")
    double = events.eq("double")
    triple = events.eq("triple")
    home_run = events.eq("home_run")
    strikeout = events.isin(STRIKEOUT_EVENTS)
    walk = events.isin(WALK_EVENTS)
    error = events.isin(ERROR_EVENTS)
    sacrifice = events.isin(SACRIFICE_EVENTS)
    advance_on_throw = events.isin(ADVANCE_ON_THROW_EVENTS)
    fielders_choice = events.isin(FIELDERS_CHOICE_EVENTS)
    out = events.isin(OUT_EVENTS - STRIKEOUT_EVENTS - SACRIFICE_EVENTS - {"fielders_choice_out"}) | events.eq("field_out")
    covered = no_result | single | double | triple | home_run | strikeout | walk | out | error | sacrifice | advance_on_throw | fielders_choice
    other = events.ne("") & ~covered

    groups = {
        "pa_no_result": no_result,
        "pa_single": single,
        "pa_double": double,
        "pa_triple": triple,
        "pa_home_run": home_run,
        "pa_strikeout": strikeout,
        "pa_walk": walk,
        "pa_out": out,
        "pa_error": error,
        "pa_sacrifice": sacrifice,
        "pa_advance_on_throw": advance_on_throw,
        "pa_fielders_choice": fielders_choice,
        "pa_other": other,
    }
    mask = pd.Series(False, index=data.index)
    for result in results:
        mask |= groups.get(result, pd.Series(False, index=data.index))
    return data[mask].copy()


def apply_stuff_filters(
    data: pd.DataFrame,
    *,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
    catcher: str | None = None,
) -> pd.DataFrame:
    if data.empty:
        return data.copy()

    working = data.copy()
    stands = {item.upper() for item in filter_csv_values(stand)}
    if stands and "stand" in working.columns:
        working = working[working["stand"].astype(str).str.upper().isin(stands)].copy()

    pitches = set(filter_csv_values(pitch))
    if pitches and "pitch_name" in working.columns:
        selected_pitches = {canonical_pitch_name(item) for item in pitches}
        working = working[working["pitch_name"].map(canonical_pitch_name).isin(selected_pitches)].copy()

    counts = set(filter_csv_values(count))
    if counts and {"balls", "strikes"}.issubset(working.columns):
        working["balls"] = pd.to_numeric(working["balls"], errors="coerce")
        working["strikes"] = pd.to_numeric(working["strikes"], errors="coerce")
        mask = pd.Series(False, index=working.index)
        for count_value in counts:
            if count_value == "Pitcher Ahead":
                mask |= working["strikes"] > working["balls"]
            elif count_value == "Hitter Ahead":
                mask |= working["balls"] > working["strikes"]
            elif count_value == "Two Strikes":
                mask |= working["strikes"].eq(2)
            elif "-" in count_value:
                balls, strikes = count_value.split("-", 1)
                mask |= working["balls"].eq(pd.to_numeric(balls, errors="coerce")) & working["strikes"].eq(pd.to_numeric(strikes, errors="coerce"))
        working = working[mask].copy()

    results = set(filter_csv_values(pitch_result))
    if results:
        description = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
        mask = pd.Series(False, index=working.index)
        for result in results:
            mask |= description.isin(PITCH_RESULT_GROUPS.get(result, set()))
        working = working[mask].copy()

    catchers = set(filter_csv_values(catcher))
    catcher_ids = catcher_filter_ids(catchers)
    if catchers and not catcher_ids:
        catcher_ids = catcher_names_to_ids(working, catchers)
    if catchers and catcher_ids and "fielder_2" in working.columns:
        working = working[working["fielder_2"].astype(str).isin(catcher_ids)].copy()
    elif catchers and "catcher_name" in working.columns:
        working = working[working["catcher_name"].astype(str).isin(catchers)].copy()

    working = apply_in_play_result_filter(working, in_play_result)
    return apply_pa_result_filter(working, pa_result)


def apply_sequence_filters(
    data: pd.DataFrame,
    *,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    catcher: str | None = None,
) -> pd.DataFrame:
    return apply_stuff_filters(data, stand=stand, count=count, pitch=pitch, pitch_result=pitch_result, catcher=catcher)


def build_catcher_options(data: pd.DataFrame) -> list[str]:
    if data.empty:
        return []
    if "catcher_name" in data.columns:
        values = (
            data["catcher_name"]
            .dropna()
            .astype(str)
            .map(str.strip)
        )
        values = values[~values.str.lower().isin(["", "nan", "none", "null", "<na>"])]
        return sorted(values.unique().tolist())
    if "fielder_2" in data.columns:
        return sorted({row["catcher_name"] for row in catcher_lookup_rows(data) if row.get("catcher_name")})
    return []


def build_pitch_type_run_value_table(data: pd.DataFrame, team: str = "", year: int | None = None) -> pd.DataFrame:
    if data.empty or "pitch_name" not in data.columns:
        return pd.DataFrame()

    working = filter_display_pitch_rows(normalize_pitch_names(data))
    if working.empty:
        return pd.DataFrame()
    working["pitch_name"] = working["pitch_name"].astype(str)
    for column in [
        "delta_run_exp",
        "launch_speed",
        "estimated_ba_using_speedangle",
        "estimated_slg_using_speedangle",
        "estimated_woba_using_speedangle",
        "woba_value",
    ]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    description = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    events = working.get("events", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip().replace("nan", "")
    working["_is_swing"] = description.isin(SWING_EVENTS)
    working["_is_whiff"] = description.isin(WHIFF_EVENTS)
    working["_is_in_play"] = description.isin(IN_PLAY_EVENTS)
    working["_is_terminal"] = events.ne("")
    working["_is_strikeout"] = events.isin({"strikeout", "strikeout_double_play"})
    working["_is_hit"] = events.isin(HIT_EVENTS)
    working["_events"] = events
    working["_is_hard_hit"] = pd.to_numeric(working.get("launch_speed"), errors="coerce").ge(95)
    pitch_number = pd.to_numeric(working.get("pitch_number"), errors="coerce")
    strikes = pd.to_numeric(working.get("strikes"), errors="coerce")
    working["_is_two_strike_pitch"] = strikes.eq(2) | pitch_number.ge(3)

    def safe_mean(series: pd.Series) -> float:
        values = pd.to_numeric(series, errors="coerce")
        return float(values.mean()) if values.notna().any() else np.nan

    records = []
    for pitch_name, group in working.groupby("pitch_name", dropna=False):
        pa_group = group[group["_is_terminal"]].copy()
        batted_group = group[group["_is_in_play"]].copy()
        swings = int(group["_is_swing"].sum())
        whiffs = int(group["_is_whiff"].sum())
        pas = int(pa_group.shape[0])
        strikeouts = int(pa_group["_is_strikeout"].sum())
        putaway_denom = int(group["_is_two_strike_pitch"].sum())
        ab_mask = pa_group["_events"].ne("") & ~pa_group["_events"].isin(NON_AB_EVENTS)
        hits = int(pa_group["_is_hit"].sum())
        ab_count = int(ab_mask.sum())
        total_bases = int(
            pa_group["_events"].eq("single").sum()
            + pa_group["_events"].eq("double").sum() * 2
            + pa_group["_events"].eq("triple").sum() * 3
            + pa_group["_events"].eq("home_run").sum() * 4
        )
        delta = group.get("delta_run_exp", pd.Series(dtype="float"))
        records.append(
            {
                "Year": year,
                "Pitch Type": display_pitch_name(pitch_name),
                "Team": team,
                "RV/100": safe_mean(delta) * 100 if "delta_run_exp" in group.columns else np.nan,
                "Run Value": safe_mean(delta) * len(group) if "delta_run_exp" in group.columns else np.nan,
                "Pitches": int(len(group)),
                "%": len(group) / len(working) * 100 if len(working) else np.nan,
                "PA": pas,
                "BA": hits / ab_count if ab_count else np.nan,
                "SLG": total_bases / ab_count if ab_count else np.nan,
                "wOBA": safe_mean(pa_group.get("woba_value", pd.Series(dtype="float"))),
                "Whiff%": whiffs / swings * 100 if swings else np.nan,
                "K%": strikeouts / pas * 100 if pas else np.nan,
                "PutAway %": strikeouts / putaway_denom * 100 if putaway_denom else np.nan,
                "xBA": safe_mean(batted_group.get("estimated_ba_using_speedangle", pd.Series(dtype="float"))),
                "xSLG": safe_mean(batted_group.get("estimated_slg_using_speedangle", pd.Series(dtype="float"))),
                "xwOBA": safe_mean(batted_group.get("estimated_woba_using_speedangle", pd.Series(dtype="float"))),
                "Hard Hit %": batted_group["_is_hard_hit"].mean() * 100 if not batted_group.empty else np.nan,
            }
        )
    return pd.DataFrame(records).sort_values("Pitches", ascending=False).reset_index(drop=True) if records else pd.DataFrame()


def get_personal_movement(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
    catcher: str | None = None,
    include_pitch_stuff: bool = False,
) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id, start_date=start_date, end_date=end_date)
    pitch_df = load_pitch_stamina_state(pitch_df, year=year, data_dir=settings.data_dir)
    filtered_df = apply_stuff_filters(
        pitch_df,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
        catcher=catcher,
    )
    summary_df = build_pitch_movement_summary(filtered_df)
    run_value_df = build_pitch_type_run_value_table(filtered_df, year=year)
    league_movement_df = build_league_movement_benchmarks(year)
    movement_comparison_df = build_movement_comparison_table(filtered_df, infer_pitcher_hand(pitch_df), league_movement_df)
    snapshot = build_filter_snapshot_stats(filtered_df)
    scatter_df = filtered_df.copy()
    if include_pitch_stuff:
        scatter_df = add_pitch_stuff_scores(scatter_df, pitch_df)
    movement_scatter = build_movement_scatter_rows(scatter_df)

    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="pitches", label="Pitches", value=int(len(pitch_df))),
            MetricItem(key="pitcher_hand", label="Pitcher Hand", value=infer_pitcher_hand(pitch_df)),
            MetricItem(key="pitch_types", label="Pitch Types", value=int(summary_df["pitch_name"].nunique()) if not summary_df.empty else 0),
        ],
        charts={
            "movement_scatter": movement_scatter,
            "pitch_location_scatter": build_pitch_location_scatter(filtered_df),
            "filter_snapshot": snapshot,
            "catcher_options": build_catcher_options(pitch_df),
            "catcher_lookup": catcher_lookup_rows(pitch_df, year=year),
        },
        tables={
            "movement_summary": dataframe_to_table_payload(summary_df),
            "movement_league_comparison": dataframe_to_table_payload(movement_comparison_df),
            "run_values_by_pitch_type": dataframe_to_table_payload(run_value_df),
        },
    )


def build_discipline_summary(pitch_df: pd.DataFrame) -> pd.DataFrame:
    if pitch_df.empty:
        return pd.DataFrame()
    working = pitch_df.copy()
    description = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    swings = description.isin(SWING_EVENTS)
    whiffs = description.isin(WHIFF_EVENTS)
    called = description.isin(CALLED_STRIKE_EVENTS)
    in_zone = red_strike_zone_mask(working)
    chase_swings = swings & ~in_zone
    first_pitch = pd.to_numeric(
        working.get("pitch_number", pd.Series(index=working.index, dtype="float")),
        errors="coerce",
    ).eq(1)
    strike_events = SWING_EVENTS | CALLED_STRIKE_EVENTS
    summary = {
        "Pitches": len(working),
        "Swing%": swings.mean() * 100 if len(working) else np.nan,
        "Whiff%": (whiffs.sum() / swings.sum() * 100) if swings.sum() else np.nan,
        "CSW%": ((whiffs | called).sum() / len(working) * 100) if len(working) else np.nan,
        "Zone%": in_zone.mean() * 100 if len(working) else np.nan,
        "Chase Swings": int(chase_swings.sum()),
        "1st Pitch Strike%": (description[first_pitch].isin(strike_events).mean() * 100) if first_pitch.any() else np.nan,
    }
    return pd.DataFrame([summary])


def build_stand_split_table(pitch_df: pd.DataFrame) -> pd.DataFrame:
    if pitch_df.empty or "stand" not in pitch_df.columns:
        return pd.DataFrame()
    records = []
    for stand_value, group in pitch_df.groupby(pitch_df["stand"].astype(str).str.upper()):
        description = group.get("description", pd.Series(index=group.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
        swings = description.isin(SWING_EVENTS)
        whiffs = description.isin(WHIFF_EVENTS)
        called = description.isin(CALLED_STRIKE_EVENTS)
        zones = pd.to_numeric(group.get("zone"), errors="coerce")
        records.append(
            {
                "Stand": stand_value,
                "Pitches": len(group),
                "Whiff%": (whiffs.sum() / swings.sum() * 100) if swings.sum() else np.nan,
                "CSW%": ((whiffs | called).sum() / len(group) * 100) if len(group) else np.nan,
                "Zone%": zones.between(1, 9).mean() * 100 if len(group) else np.nan,
            }
        )
    return pd.DataFrame(records).sort_values("Stand").reset_index(drop=True)


def get_personal_discipline(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    catcher: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id, start_date=start_date, end_date=end_date)
    filtered_df = apply_stuff_filters(pitch_df, stand=stand, count=count, pitch=pitch, catcher=catcher)
    discipline_df = build_discipline_summary(filtered_df)
    stand_split_df = build_stand_split_table(filtered_df)
    snapshot = build_filter_snapshot_stats(filtered_df)
    result_panels = build_discipline_result_panels(filtered_df)
    count_panels = build_discipline_count_panels(filtered_df)
    panel_groups = build_discipline_panel_groups(filtered_df, build_pitch_location_scatter)
    summary = [
        MetricItem(key=str(row["label"]), label=str(row["label"]), value=clean_value(row["value"]))
        for row in (
            discipline_df.iloc[0].rename_axis("label").reset_index(name="value").to_dict(orient="records")
            if not discipline_df.empty
            else []
        )
    ]
    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=summary,
        tables={
            "discipline_summary": dataframe_to_table_payload(discipline_df),
            "stand_split": dataframe_to_table_payload(stand_split_df),
        },
        charts={
            "filter_snapshot": snapshot,
            "pitch_location_scatter": build_pitch_location_scatter(filtered_df),
            "result_panels": result_panels,
            "count_panels": count_panels,
            "pa_result_panels": panel_groups.get("result", {}).get("pa_result", []),
            "batted_ball_panels": panel_groups.get("result", {}).get("batted_ball", []),
            "panel_groups": panel_groups,
            "catcher_options": build_catcher_options(pitch_df),
            "catcher_lookup": catcher_lookup_rows(pitch_df, year=year),
        },
    )


def build_filter_snapshot_stats(pitch_df: pd.DataFrame) -> dict[str, float | int | None]:
    if pitch_df.empty:
        return {"pitches": 0, "zone_pct": np.nan, "swing_pct": np.nan, "o_swing_pct": np.nan, "whiff_pct": np.nan, "avg": np.nan}
    working = pitch_df.copy()
    description = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    events = working.get("events", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip().replace("nan", "")
    zone = pd.to_numeric(working.get("zone"), errors="coerce")
    in_zone = zone.between(1, 9)
    out_zone = ~in_zone
    swings = description.isin(SWING_EVENTS)
    whiffs = description.isin(WHIFF_EVENTS)
    chase_swings = swings & out_zone
    ab_mask = events.ne("") & ~events.isin(NON_AB_EVENTS)
    hits = events.isin(HIT_EVENTS)
    ab_count = int(ab_mask.sum())
    return {
        "pitches": int(len(working)),
        "zone_pct": in_zone.mean() * 100 if len(working) else np.nan,
        "swing_pct": swings.mean() * 100 if len(working) else np.nan,
        "o_swing_pct": (chase_swings.sum() / out_zone.sum() * 100) if out_zone.sum() else np.nan,
        "whiff_pct": (whiffs.sum() / swings.sum() * 100) if swings.sum() else np.nan,
        "avg": (hits.sum() / ab_count) if ab_count else np.nan,
    }


def build_discipline_result_panels(pitch_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if pitch_df.empty:
        return {}
    description = pitch_df.get("description", pd.Series(index=pitch_df.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    specs = {
        "called_strike": CALLED_STRIKE_EVENTS,
        "swinging_strike": WHIFF_EVENTS,
        "in_play": IN_PLAY_EVENTS,
        "foul": {"foul", "foul_tip", "foul_bunt"},
    }
    return {
        key: build_pitch_location_scatter(pitch_df[description.isin(values)].copy())
        for key, values in specs.items()
    }


def build_discipline_count_panels(pitch_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if pitch_df.empty or not {"balls", "strikes"}.issubset(pitch_df.columns):
        return {}
    working = pitch_df.copy()
    working["balls"] = pd.to_numeric(working["balls"], errors="coerce")
    working["strikes"] = pd.to_numeric(working["strikes"], errors="coerce")
    specs = {
        "0-0": working["balls"].eq(0) & working["strikes"].eq(0),
        "hitter_ahead": working["balls"] > working["strikes"],
        "pitcher_ahead": working["strikes"] > working["balls"],
        "two_strikes": working["strikes"].eq(2),
    }
    for balls in range(4):
        for strikes in range(3):
            specs[f"{balls}-{strikes}"] = working["balls"].eq(balls) & working["strikes"].eq(strikes)
    return {
        key: build_pitch_location_scatter(working[mask].copy())
        for key, mask in specs.items()
    }


def build_count_pitch_mix(pitch_df: pd.DataFrame, current_pitch_filter: str = "All") -> list[dict[str, Any]]:
    required_cols = {"balls", "strikes", "pitch_name"}
    if pitch_df.empty or not required_cols.issubset(pitch_df.columns):
        return []
    working = pitch_df.copy()
    working["balls"] = pd.to_numeric(working["balls"], errors="coerce")
    working["strikes"] = pd.to_numeric(working["strikes"], errors="coerce")
    working = working.dropna(subset=["balls", "strikes", "pitch_name"])
    working = working[working["balls"].between(0, 3) & working["strikes"].between(0, 2)].copy()
    if current_pitch_filter != "All":
        working = working[working["pitch_name"].astype(str).eq(current_pitch_filter)].copy()
    if working.empty:
        return []
    description = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    events = working.get("events", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    launch_speed = pd.to_numeric(
        working.get("launch_speed", pd.Series(index=working.index, dtype="float")),
        errors="coerce",
    )
    at_bat_number = working.get("at_bat_number", pd.Series(index=working.index, dtype="object"))
    working["_is_strike"] = description.isin(SWING_EVENTS | CALLED_STRIKE_EVENTS)
    working["_is_swing"] = description.isin(SWING_EVENTS)
    working["_is_whiff"] = description.isin(WHIFF_EVENTS)
    working["_is_hard_hit"] = launch_speed.ge(95)
    working["_is_hit"] = events.isin(HIT_EVENTS)
    working["_is_ab"] = events.notna() & ~events.isin(WALK_EVENTS | SACRIFICE_EVENTS) & events.ne("")
    working["_at_bat_number"] = at_bat_number
    working["count"] = working["balls"].astype(int).astype(str) + "-" + working["strikes"].astype(int).astype(str)
    grouped = (
        working.groupby(["count", "pitch_name"], dropna=False)
        .agg(
            pitches=("pitch_name", "size"),
            strikes=("_is_strike", "sum"),
            swings=("_is_swing", "sum"),
            whiffs=("_is_whiff", "sum"),
            hard_hits=("_is_hard_hit", "sum"),
            hits=("_is_hit", "sum"),
            abs=("_is_ab", "sum"),
            pas=("_at_bat_number", "nunique"),
        )
        .reset_index()
        .sort_values(["count", "pitches"], ascending=[True, False])
    )
    totals = grouped.groupby("count")["pitches"].transform("sum")
    grouped["rate"] = np.where(totals > 0, grouped["pitches"] / totals, np.nan)
    grouped["strike_pct"] = grouped["strikes"] / grouped["pitches"] * 100.0
    grouped["swing_pct"] = grouped["swings"] / grouped["pitches"] * 100.0
    grouped["whiff_pct"] = np.where(grouped["swings"] > 0, grouped["whiffs"] / grouped["swings"] * 100.0, np.nan)
    grouped["hard_hit_pct"] = np.where(grouped["pitches"] > 0, grouped["hard_hits"] / grouped["pitches"] * 100.0, np.nan)
    grouped["avg"] = np.where(grouped["abs"] > 0, grouped["hits"] / grouped["abs"], np.nan)
    grouped["Pitch"] = grouped["pitch_name"].map(display_pitch_name)
    grouped["Strike%"] = grouped["strike_pct"]
    grouped["Swing%"] = grouped["swing_pct"]
    grouped["Whiff%"] = grouped["whiff_pct"]
    grouped["Hard Hit%"] = grouped["hard_hit_pct"]
    grouped["AVG"] = grouped["avg"]
    return [{key: clean_value(value) for key, value in row.items()} for row in grouped.to_dict(orient="records")]


COUNT_STATE_LINKS = [
    ("0-0", "1-0"),
    ("0-0", "0-1"),
    ("1-0", "2-0"),
    ("1-0", "1-1"),
    ("0-1", "1-1"),
    ("0-1", "0-2"),
    ("2-0", "3-0"),
    ("2-0", "2-1"),
    ("1-1", "2-1"),
    ("1-1", "1-2"),
    ("0-2", "1-2"),
    ("2-1", "3-1"),
    ("2-1", "2-2"),
    ("3-0", "3-1"),
    ("1-2", "2-2"),
    ("2-2", "3-2"),
    ("3-1", "3-2"),
]


def parse_exact_count(count_key: str | None) -> tuple[int | None, int | None]:
    if not count_key or "-" not in str(count_key):
        return None, None
    balls, strikes = str(count_key).split("-", 1)
    return pd.to_numeric(balls, errors="coerce"), pd.to_numeric(strikes, errors="coerce")


def build_count_state_descendants(anchor_count_key: str) -> set[str]:
    descendants = {anchor_count_key}
    queue = [anchor_count_key]
    while queue:
        current = queue.pop(0)
        for source_key, target_key in COUNT_STATE_LINKS:
            if source_key != current or target_key in descendants:
                continue
            descendants.add(target_key)
            queue.append(target_key)
    return descendants


def build_conditioned_count_subset(data: pd.DataFrame, anchor_count_key: str | None, selected_pitch: str | None) -> pd.DataFrame:
    required_cols = {"game_pk", "at_bat_number", "pitch_number", "balls", "strikes", "pitch_name"}
    if data.empty or not selected_pitch or not required_cols.issubset(data.columns):
        return pd.DataFrame()

    anchor_balls, anchor_strikes = parse_exact_count(anchor_count_key)
    if pd.isna(anchor_balls) or pd.isna(anchor_strikes):
        return pd.DataFrame()

    working = add_pitcher_wpa_column(data)
    working = working.drop(columns=["anchor_pitch_number"], errors="ignore")
    for column in ["game_pk", "at_bat_number", "pitch_number", "balls", "strikes"]:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    working["pitch_name"] = working["pitch_name"].astype(str)
    working["Pitch"] = working["pitch_name"].map(display_pitch_name)
    working = working.dropna(subset=["game_pk", "at_bat_number", "pitch_number", "balls", "strikes"]).copy()
    if working.empty:
        return pd.DataFrame()

    anchor_rows = working[
        working["balls"].eq(anchor_balls)
        & working["strikes"].eq(anchor_strikes)
        & working["Pitch"].eq(selected_pitch)
    ][["game_pk", "at_bat_number", "pitch_number"]].copy()
    if anchor_rows.empty:
        return pd.DataFrame()

    conditioned = working.merge(
        anchor_rows.rename(columns={"pitch_number": "anchor_pitch_number"}),
        on=["game_pk", "at_bat_number"],
        how="inner",
    )
    conditioned = conditioned[conditioned["pitch_number"] >= conditioned["anchor_pitch_number"]].copy()
    descendants = build_count_state_descendants(str(anchor_count_key))
    conditioned["count"] = conditioned["balls"].astype(int).astype(str) + "-" + conditioned["strikes"].astype(int).astype(str)
    conditioned = conditioned[conditioned["count"].isin(descendants)].copy()
    return conditioned.drop_duplicates(subset=["game_pk", "at_bat_number", "pitch_number"]).copy()


def build_conditioned_wpa_summary_table(data: pd.DataFrame, count_key: str | None) -> pd.DataFrame:
    balls, strikes = parse_exact_count(count_key)
    if data.empty or pd.isna(balls) or pd.isna(strikes) or "pitch_name" not in data.columns:
        return pd.DataFrame()
    working = data.copy()
    working["balls"] = pd.to_numeric(working.get("balls"), errors="coerce")
    working["strikes"] = pd.to_numeric(working.get("strikes"), errors="coerce")
    exact_frame = working[working["balls"].eq(balls) & working["strikes"].eq(strikes)].copy()
    if exact_frame.empty:
        return pd.DataFrame()

    pitch_options = (
        exact_frame["pitch_name"]
        .dropna()
        .astype(str)
        .map(display_pitch_name)
        .drop_duplicates()
        .tolist()
    )
    records: list[dict[str, Any]] = []
    for pitch_name in pitch_options:
        conditioned = build_conditioned_count_subset(data, count_key, pitch_name)
        if conditioned.empty:
            continue
        pitcher_wpa = one_wpa_value_per_pa(conditioned, "pitcher_wpa")
        downstream_pas = int(conditioned[["game_pk", "at_bat_number"]].drop_duplicates().shape[0])
        records.append(
            {
                "Pitch": pitch_name,
                "downstream_pitches": int(len(conditioned)),
                "downstream_pas": downstream_pas,
                "downstream_wpa_sum": pitcher_wpa.sum(min_count=1),
                "wpa_per_100": pitcher_wpa.sum(min_count=1) / downstream_pas * 100 if downstream_pas and pitcher_wpa.notna().any() else np.nan,
            }
        )
    return pd.DataFrame(records).sort_values(["downstream_wpa_sum", "downstream_pitches"], ascending=[False, False]).reset_index(drop=True) if records else pd.DataFrame()


def build_conditioned_summary(conditioned: pd.DataFrame, count_key: str | None, selected_pitch: str | None) -> dict[str, Any]:
    pitcher_wpa = one_wpa_value_per_pa(conditioned, "pitcher_wpa") if not conditioned.empty else pd.Series(dtype="float")
    downstream_pas = int(conditioned[["game_pk", "at_bat_number"]].drop_duplicates().shape[0]) if not conditioned.empty else 0
    return {
        "count": count_key,
        "pitch": selected_pitch,
        "downstream_pitches": int(len(conditioned)),
        "downstream_pas": downstream_pas,
        "downstream_wpa_sum": clean_value(pitcher_wpa.sum(min_count=1)) if pitcher_wpa.notna().any() else None,
        "wpa_per_100": clean_value(pitcher_wpa.sum(min_count=1) / downstream_pas * 100) if downstream_pas and pitcher_wpa.notna().any() else None,
    }


def filter_exact_count(data: pd.DataFrame, count_key: str | None) -> pd.DataFrame:
    balls, strikes = parse_exact_count(count_key)
    if data.empty or pd.isna(balls) or pd.isna(strikes) or not {"balls", "strikes"}.issubset(data.columns):
        return pd.DataFrame()
    working = data.copy()
    working["balls"] = pd.to_numeric(working["balls"], errors="coerce")
    working["strikes"] = pd.to_numeric(working["strikes"], errors="coerce")
    return working[working["balls"].eq(balls) & working["strikes"].eq(strikes)].copy()


def summarize_count_state_pitch_usage(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or "pitch_name" not in data.columns:
        return pd.DataFrame()
    working = data.copy()
    working["pitch_name"] = working["pitch_name"].astype(str)
    working = working.loc[~working["pitch_name"].isin(HIDDEN_PITCH_NAMES)].copy()
    if working.empty:
        return pd.DataFrame()
    working["description"] = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    working["events"] = working.get("events", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip().replace("nan", "")
    working["launch_speed"] = pd.to_numeric(working.get("launch_speed"), errors="coerce")
    strike_descriptions = SWING_EVENTS | CALLED_STRIKE_EVENTS
    working["_is_strike"] = working["description"].isin(strike_descriptions)
    working["_is_swing"] = working["description"].isin(SWING_EVENTS)
    working["_is_whiff"] = working["description"].isin(WHIFF_EVENTS)
    working["_is_hard_hit"] = working["launch_speed"].ge(95)
    working["_is_hit"] = working["events"].isin(HIT_EVENTS)
    working["_is_ab_event"] = working["events"].ne("") & ~working["events"].isin(NON_AB_EVENTS)
    working["_is_in_play"] = working["description"].isin(IN_PLAY_EVENTS)

    grouped = (
        working.groupby("pitch_name", dropna=False)
        .agg(
            pitches=("pitch_name", "size"),
            strikes=("_is_strike", "sum"),
            swings=("_is_swing", "sum"),
            whiffs=("_is_whiff", "sum"),
            hard_hits=("_is_hard_hit", "sum"),
            ab_count=("_is_ab_event", "sum"),
            hits=("_is_hit", "sum"),
            in_play_count=("_is_in_play", "sum"),
        )
        .reset_index()
    )
    if grouped.empty:
        return pd.DataFrame()
    grouped["usage_pct"] = grouped["pitches"] / grouped["pitches"].sum() * 100.0
    grouped["strike_pct"] = grouped["strikes"] / grouped["pitches"] * 100.0
    grouped["swing_pct"] = grouped["swings"] / grouped["pitches"] * 100.0
    grouped["whiff_pct"] = np.where(grouped["swings"] > 0, grouped["whiffs"] / grouped["swings"] * 100.0, np.nan)
    grouped["hard_hit_pct"] = np.where(grouped["in_play_count"] > 0, grouped["hard_hits"] / grouped["in_play_count"] * 100.0, np.nan)
    grouped["avg"] = np.where(grouped["ab_count"] > 0, grouped["hits"] / grouped["ab_count"], np.nan)
    grouped["Pitch"] = grouped["pitch_name"].map(display_pitch_name)
    return grouped.sort_values("pitches", ascending=False).reset_index(drop=True)


def build_count_state_detail_table(data: pd.DataFrame) -> pd.DataFrame:
    grouped = summarize_count_state_pitch_usage(data)
    if grouped.empty:
        return grouped
    return grouped[["Pitch", "pitches", "usage_pct", "strike_pct", "swing_pct", "whiff_pct", "hard_hit_pct", "avg"]]


def build_next_count_state_detail_table(data: pd.DataFrame, count_key: str | None) -> pd.DataFrame:
    if data.empty or not count_key:
        return pd.DataFrame()
    next_count_keys = [target_key for source_key, target_key in COUNT_STATE_LINKS if source_key == str(count_key)]
    if not next_count_keys:
        return pd.DataFrame()
    next_frames = [filter_exact_count(data, next_key) for next_key in next_count_keys]
    next_frames = [frame for frame in next_frames if not frame.empty]
    if not next_frames:
        return pd.DataFrame()
    next_data = pd.concat(next_frames, ignore_index=True)
    detail = build_count_state_detail_table(next_data)
    if detail.empty:
        return detail
    detail.insert(0, "next_counts", " + ".join(next_count_keys))
    return detail


def classify_terminal_pitch_outcome(row: pd.Series) -> str:
    description = str(row.get("description", "")).strip().lower()
    events = str(row.get("events", "")).strip().lower()
    if events in STRIKEOUT_EVENTS:
        return "PA Ends: Strikeout"
    if events in WALK_EVENTS:
        return "PA Ends: Walk"
    if events in HIT_EVENTS:
        return "PA Ends: Hit"
    if events in SACRIFICE_EVENTS:
        return "PA Ends: Sacrifice"
    if events in ERROR_EVENTS or events in ADVANCE_ON_THROW_EVENTS:
        return "PA Ends: Reached on Error"
    if events in OUT_EVENTS or description in IN_PLAY_EVENTS:
        return "PA Ends: Ball in Play Out"
    if description in CALLED_STRIKE_EVENTS:
        return "Result: Called Strike"
    if description in WHIFF_EVENTS:
        return "Result: Whiff"
    if description in FOUL_EVENTS:
        return "Result: Foul"
    if description in BALL_EVENTS:
        return "Result: Ball"
    return "Result: Other"


def build_count_pitch_followup_table(data: pd.DataFrame, count_key: str | None, selected_pitch: str | None) -> pd.DataFrame:
    required_cols = {"game_pk", "at_bat_number", "pitch_number", "balls", "strikes", "pitch_name"}
    if data.empty or not selected_pitch or not required_cols.issubset(data.columns):
        return pd.DataFrame()

    balls, strikes = parse_exact_count(count_key)
    if pd.isna(balls) or pd.isna(strikes):
        return pd.DataFrame()

    working = data.copy()
    for column in ["game_pk", "at_bat_number", "pitch_number", "balls", "strikes"]:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    working["pitch_name"] = working["pitch_name"].astype(str)
    working["Pitch"] = working["pitch_name"].map(display_pitch_name)
    working["description"] = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str)
    working["events"] = working.get("events", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).replace("nan", "")
    working = working.dropna(subset=["game_pk", "at_bat_number", "pitch_number", "balls", "strikes"]).copy()
    if working.empty:
        return pd.DataFrame()

    working = working.sort_values(["game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)
    group_keys = ["game_pk", "at_bat_number"]
    working["next_balls"] = working.groupby(group_keys, dropna=False)["balls"].shift(-1)
    working["next_strikes"] = working.groupby(group_keys, dropna=False)["strikes"].shift(-1)
    working["next_pitch_name"] = working.groupby(group_keys, dropna=False)["pitch_name"].shift(-1)

    selected_rows = working[
        working["balls"].eq(balls)
        & working["strikes"].eq(strikes)
        & working["Pitch"].eq(selected_pitch)
    ].copy()
    if selected_rows.empty:
        return pd.DataFrame()

    selected_rows["followup_event"] = np.where(
        selected_rows["next_balls"].notna() & selected_rows["next_strikes"].notna(),
        "Next Count: "
        + selected_rows["next_balls"].astype("Int64").astype(str)
        + "-"
        + selected_rows["next_strikes"].astype("Int64").astype(str),
        selected_rows.apply(classify_terminal_pitch_outcome, axis=1),
    )
    selected_rows["next_pitch"] = selected_rows["next_pitch_name"].dropna().astype(str).map(display_pitch_name)
    selected_rows["next_pitch"] = selected_rows["next_pitch"].fillna("-")

    summary = (
        selected_rows.groupby("followup_event", dropna=False)
        .agg(
            pitches=("pitch_number", "size"),
            next_pitch=("next_pitch", lambda values: values.mode().iloc[0] if not values.mode().empty else "-"),
        )
        .reset_index()
        .sort_values("pitches", ascending=False)
        .reset_index(drop=True)
    )
    total = float(summary["pitches"].sum())
    summary["prob_pct"] = np.where(total > 0, summary["pitches"] / total * 100.0, np.nan)
    return summary[["followup_event", "pitches", "prob_pct", "next_pitch"]]


def build_sequence_outcome_tables(pitch_df: pd.DataFrame, current_pitch_filter: str = "All") -> tuple[pd.DataFrame, pd.DataFrame]:
    if pitch_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    required_cols = ["game_pk", "at_bat_number", "pitch_number", "pitch_name", "description", "game_date", "balls", "strikes"]
    if any(column not in pitch_df.columns for column in required_cols):
        return pd.DataFrame(), pd.DataFrame()

    working = pitch_df.copy()
    for column in ["game_pk", "at_bat_number", "pitch_number", "balls", "strikes"]:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    working["game_date"] = pd.to_datetime(working["game_date"], errors="coerce")
    working["description"] = working["description"].fillna("").astype(str).str.lower().str.strip()
    working["events"] = working.get("events", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip().replace("nan", "")
    working["launch_speed"] = pd.to_numeric(working.get("launch_speed"), errors="coerce")
    working = working.dropna(subset=["game_pk", "at_bat_number", "pitch_number", "game_date", "balls", "strikes"]).copy()
    if working.empty:
        return pd.DataFrame(), pd.DataFrame()

    working = working.sort_values(["game_date", "game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)
    shallow_count_mask = (
        (working["balls"].eq(0) & working["strikes"].isin([0, 1, 2]))
        | (working["balls"].eq(1) & working["strikes"].isin([0, 1]))
        | (working["balls"].eq(2) & working["strikes"].eq(0))
    )
    strike_descriptions = SWING_EVENTS | CALLED_STRIKE_EVENTS
    working["is_strike"] = working["description"].isin(strike_descriptions)
    working["is_swing"] = working["description"].isin(SWING_EVENTS)
    working["is_whiff"] = working["description"].isin(WHIFF_EVENTS)
    working["is_hard_hit"] = working["launch_speed"].ge(95)
    working["is_hit"] = working["events"].isin(HIT_EVENTS)
    working["is_ab_event"] = working["events"].ne("") & ~working["events"].isin(NON_AB_EVENTS)
    working["is_in_play"] = working["description"].isin(IN_PLAY_EVENTS)
    working["shallow_sequence"] = pd.NA
    working["two_strike_count_sequence"] = pd.NA

    for _, group in working.groupby(["game_pk", "at_bat_number"], sort=False, dropna=False):
        indices = group.index.tolist()
        pitch_labels = [display_pitch_name(name) for name in group["pitch_name"].astype(str)]
        cumulative_labels: list[str] = []
        two_strike_start_pos: int | None = None
        for pos, idx in enumerate(indices):
            cumulative_labels.append(pitch_labels[pos])
            if bool(shallow_count_mask.loc[idx]):
                working.at[idx, "shallow_sequence"] = " -> ".join(cumulative_labels)
            if two_strike_start_pos is None and float(group.iloc[pos]["strikes"]) == 2.0:
                two_strike_start_pos = pos
            if two_strike_start_pos is not None and pos >= two_strike_start_pos:
                working.at[idx, "two_strike_count_sequence"] = " -> ".join(pitch_labels[two_strike_start_pos : pos + 1])

    if current_pitch_filter != "All":
        working = working[working["pitch_name"].astype(str).eq(current_pitch_filter)].copy()

    def summarize(sequence_col: str, label: str, min_pitches: int) -> pd.DataFrame:
        usable = working[working[sequence_col].notna()].copy()
        if usable.empty:
            return pd.DataFrame()
        grouped = (
            usable.groupby([sequence_col, "pitch_name"], dropna=False)
            .agg(
                pitches=("pitch_number", "size"),
                games=("game_pk", "nunique"),
                strikes=("is_strike", "sum"),
                swings=("is_swing", "sum"),
                whiffs=("is_whiff", "sum"),
                hard_hits=("is_hard_hit", "sum"),
                ab_count=("is_ab_event", "sum"),
                hits=("is_hit", "sum"),
                in_play_count=("is_in_play", "sum"),
            )
            .reset_index()
        )
        grouped = grouped[grouped["pitches"] >= min_pitches].copy()
        if grouped.empty:
            return pd.DataFrame()
        grouped["strike_pct"] = grouped["strikes"] / grouped["pitches"] * 100.0
        grouped["swing_pct"] = grouped["swings"] / grouped["pitches"] * 100.0
        grouped["whiff_pct"] = np.where(grouped["swings"] > 0, grouped["whiffs"] / grouped["swings"] * 100.0, np.nan)
        grouped["hard_hit_pct"] = np.where(grouped["in_play_count"] > 0, grouped["hard_hits"] / grouped["in_play_count"] * 100.0, np.nan)
        grouped["avg"] = np.where(grouped["ab_count"] > 0, grouped["hits"] / grouped["ab_count"], np.nan)
        grouped["Current Pitch"] = grouped["pitch_name"].map(display_pitch_name)
        grouped["Sequence"] = grouped[sequence_col].astype(str)
        grouped["Type"] = label
        return grouped[
            ["Type", "Sequence", "Current Pitch", "pitches", "strike_pct", "swing_pct", "whiff_pct", "hard_hit_pct", "avg", "games"]
        ].sort_values(["pitches", "games", "strike_pct"], ascending=[False, False, False]).reset_index(drop=True)

    return summarize("shallow_sequence", "Shallow Count", 3), summarize("two_strike_count_sequence", "Two-Strike Count", 1)


def get_personal_sequence(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    current_pitch: str = "All",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    catcher: str | None = None,
    condition_count: str | None = None,
    condition_pitch: str | None = None,
    detail_count: str | None = "0-0",
    followup_pitch: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id, start_date=start_date, end_date=end_date)
    pitch_df = add_pitcher_wpa_column(attach_plate_appearance_wpa(pitch_df, year, settings.data_dir))
    filtered_df = apply_sequence_filters(pitch_df, stand=stand, count=count, pitch=pitch, pitch_result=pitch_result, catcher=catcher)
    shallow_df, two_strike_df = build_sequence_outcome_tables(filtered_df, current_pitch_filter=current_pitch)
    snapshot = build_filter_snapshot_stats(filtered_df)
    conditioned_df = build_conditioned_count_subset(filtered_df, condition_count, condition_pitch)
    conditioned_wpa_df = build_conditioned_wpa_summary_table(filtered_df, condition_count)
    current_count_df = build_count_state_detail_table(filter_exact_count(filtered_df, detail_count))
    next_count_df = build_next_count_state_detail_table(filtered_df, detail_count)
    followup_df = build_count_pitch_followup_table(filtered_df, detail_count, followup_pitch)
    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[MetricItem(key=key, label=key, value=clean_value(value)) for key, value in snapshot.items()],
        charts={
            "count_pitch_mix": build_count_pitch_mix(filtered_df, current_pitch_filter=current_pitch),
            "conditioned_count_pitch_mix": build_count_pitch_mix(conditioned_df, current_pitch_filter=current_pitch),
            "conditioned_summary": build_conditioned_summary(conditioned_df, condition_count, condition_pitch),
            "pitch_location_scatter": build_pitch_location_scatter(filtered_df),
            "filter_snapshot": snapshot,
            "catcher_options": build_catcher_options(pitch_df),
            "catcher_lookup": catcher_lookup_rows(pitch_df, year=year),
        },
        tables={
            "shallow_sequences": dataframe_to_table_payload(shallow_df),
            "two_strike_sequences": dataframe_to_table_payload(two_strike_df),
            "conditioned_wpa_summary": dataframe_to_table_payload(conditioned_wpa_df),
            "count_detail_current": dataframe_to_table_payload(current_count_df),
            "count_detail_next": dataframe_to_table_payload(next_count_df),
            "count_followup_events": dataframe_to_table_payload(followup_df),
        },
    )


def build_game_log(pitch_df: pd.DataFrame) -> pd.DataFrame:
    if pitch_df.empty or "game_pk" not in pitch_df.columns:
        return pd.DataFrame()
    game_df = pitch_df.copy()
    game_df["game_date"] = pd.to_datetime(game_df.get("game_date"), errors="coerce")
    if "release_speed" in game_df.columns:
        game_df["release_speed"] = pd.to_numeric(game_df["release_speed"], errors="coerce")
    if "release_spin_rate" in game_df.columns:
        game_df["release_spin_rate"] = pd.to_numeric(game_df["release_spin_rate"], errors="coerce")
    grouped = (
        game_df.groupby(["game_date", "game_pk"], dropna=False)
        .agg(
            pitches=("game_pk", "size"),
            avg_velo=("release_speed", "mean") if "release_speed" in game_df.columns else ("game_pk", "size"),
            avg_spin=("release_spin_rate", "mean") if "release_spin_rate" in game_df.columns else ("game_pk", "size"),
            batters=("at_bat_number", "nunique") if "at_bat_number" in game_df.columns else ("game_pk", "size"),
        )
        .reset_index()
        .sort_values(["game_date", "game_pk"], ascending=[False, False])
    )
    return grouped


def rate_pct(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) * 100 if denominator else np.nan


def format_ip_from_outs(outs: int) -> str:
    innings = outs // 3
    remainder = outs % 3
    return f"{innings}.{remainder}"


def outs_from_ip_value(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    innings_text, _, partial_text = text.partition(".")
    innings = pd.to_numeric(pd.Series([innings_text]), errors="coerce").iloc[0]
    partial = pd.to_numeric(pd.Series([partial_text or "0"]), errors="coerce").iloc[0]
    if pd.isna(innings):
        return None
    return max(0, int(innings) * 3 + (min(2, int(partial)) if pd.notna(partial) else 0))


def estimate_outs_recorded(data: pd.DataFrame) -> int:
    if data.empty or "events" not in data.columns:
        return 0
    events = data["events"].fillna("").astype(str).str.lower().str.strip()
    outs = int(events.isin(OUT_EVENTS).sum())
    outs += int(events.isin({"grounded_into_double_play", "double_play", "strikeout_double_play", "sac_fly_double_play"}).sum())
    return outs


def calculate_game_score(
    ip: Any,
    hits: Any,
    runs: Any,
    earned_runs: Any,
    walks: Any,
    strikeouts: Any,
    fallback_outs: int = 0,
) -> int | None:
    outs = outs_from_ip_value(ip)
    if outs is None:
        outs = int(fallback_outs) if fallback_outs else None
    numeric_values = {
        "hits": pd.to_numeric(pd.Series([hits]), errors="coerce").iloc[0],
        "runs": pd.to_numeric(pd.Series([runs]), errors="coerce").iloc[0],
        "earned_runs": pd.to_numeric(pd.Series([earned_runs]), errors="coerce").iloc[0],
        "walks": pd.to_numeric(pd.Series([walks]), errors="coerce").iloc[0],
        "strikeouts": pd.to_numeric(pd.Series([strikeouts]), errors="coerce").iloc[0],
    }
    if outs is None or pd.isna(numeric_values["hits"]) or pd.isna(numeric_values["walks"]) or pd.isna(numeric_values["strikeouts"]):
        return None

    runs_value = 0 if pd.isna(numeric_values["runs"]) else int(numeric_values["runs"])
    earned_value = 0 if pd.isna(numeric_values["earned_runs"]) else int(numeric_values["earned_runs"])
    unearned_runs = max(0, runs_value - earned_value)
    completed_innings_after_fourth = max(0, (int(outs) // 3) - 4)
    score = (
        50
        + int(outs)
        + completed_innings_after_fourth * 2
        + int(numeric_values["strikeouts"])
        - int(numeric_values["hits"]) * 2
        - earned_value * 4
        - unearned_runs * 2
        - int(numeric_values["walks"])
    )
    return int(score)


def outing_catcher_name(game_df: pd.DataFrame, year: int | None = None) -> str | None:
    if game_df.empty:
        return None
    if "catcher_name" in game_df.columns:
        names = (
            game_df["catcher_name"]
            .dropna()
            .astype(str)
            .map(str.strip)
        )
        names = names[~names.str.lower().isin(["", "nan", "none", "null", "<na>"])]
        if not names.empty:
            return str(names.mode().iloc[0])
    if "fielder_2" not in game_df.columns:
        return None
    ids = (
        game_df["fielder_2"]
        .dropna()
        .astype(str)
        .map(str.strip)
    )
    ids = ids[~ids.str.lower().isin(["", "nan", "none", "null", "<na>", "0"])]
    if ids.empty:
        return None
    catcher_id = str(ids.mode().iloc[0])
    lookup = {row["catcher_id"]: row["catcher_name"] for row in catcher_lookup_rows(game_df, year=year)}
    return lookup.get(catcher_id) or f"Catcher {catcher_id}"


def strike_mask(data: pd.DataFrame) -> pd.Series:
    if data.empty:
        return pd.Series(dtype="bool")
    if "type" in data.columns:
        pitch_type = data["type"].fillna("").astype(str).str.upper().str.strip()
        return pitch_type.isin({"S", "X"})
    description = data.get("description", pd.Series(index=data.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    return description.isin(SWING_EVENTS | CALLED_STRIKE_EVENTS | IN_PLAY_EVENTS)


def build_outing_options(pitch_df: pd.DataFrame) -> pd.DataFrame:
    if pitch_df.empty or "game_pk" not in pitch_df.columns:
        return pd.DataFrame()
    working = pitch_df.copy()
    working["game_date"] = pd.to_datetime(working.get("game_date"), errors="coerce")
    if "pitcher_team" not in working.columns and {"inning_topbot", "home_team", "away_team"}.issubset(working.columns):
        working["pitcher_team"] = np.where(working["inning_topbot"].astype(str) == "Top", working["home_team"], working["away_team"])
    if "opponent_team" not in working.columns and {"pitcher_team", "home_team", "away_team"}.issubset(working.columns):
        working["opponent_team"] = np.where(working["pitcher_team"] == working["home_team"], working["away_team"], working["home_team"])
    group_cols = [column for column in ["game_date", "game_pk", "pitcher_team", "opponent_team"] if column in working.columns]
    grouped = (
        working.groupby(group_cols, dropna=False)
        .agg(
            pitches=("game_pk", "size"),
            batters=("at_bat_number", "nunique") if "at_bat_number" in working.columns else ("game_pk", "size"),
            avg_velo=("release_speed", "mean") if "release_speed" in working.columns else ("game_pk", "size"),
        )
        .reset_index()
        .sort_values(["game_date", "game_pk"], ascending=[False, False])
    )
    if "game_date" in grouped.columns:
        grouped["Date"] = grouped["game_date"].dt.strftime("%Y-%m-%d")
    if "opponent_team" in grouped.columns:
        grouped["Opponent"] = grouped["opponent_team"].fillna("-").astype(str)
    else:
        grouped["Opponent"] = "-"
    grouped["Game PK"] = pd.to_numeric(grouped["game_pk"], errors="coerce").fillna(0).astype(int)
    grouped["Pitches"] = pd.to_numeric(grouped["pitches"], errors="coerce").fillna(0).astype(int)
    grouped["Batters"] = pd.to_numeric(grouped["batters"], errors="coerce").fillna(0).astype(int)
    grouped["Avg Velo"] = pd.to_numeric(grouped["avg_velo"], errors="coerce").round(1)
    grouped["Label"] = grouped.apply(
        lambda row: f"{row['Date']} vs {row['Opponent']} ({row['Pitches']} pitches)",
        axis=1,
    )
    return grouped[["Label", "Date", "Opponent", "Game PK", "Pitches", "Batters", "Avg Velo"]].reset_index(drop=True)


def build_outing_summary(game_df: pd.DataFrame, official_line: dict[str, Any] | None = None, year: int | None = None) -> list[MetricItem]:
    if game_df.empty:
        return []
    description = game_df.get("description", pd.Series(index=game_df.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    events = game_df.get("events", pd.Series(index=game_df.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    swings = description.isin(SWING_EVENTS)
    whiffs = description.isin(WHIFF_EVENTS)
    called = description.isin(CALLED_STRIKE_EVENTS)
    in_zone = red_strike_zone_mask(game_df)
    strikes = strike_mask(game_df)
    outs = estimate_outs_recorded(game_df)
    avg_velo = pd.to_numeric(game_df.get("release_speed", pd.Series(dtype="float")), errors="coerce").mean()
    game_date = pd.to_datetime(game_df.get("game_date"), errors="coerce")
    opponent = "-"
    if {"pitcher_team", "home_team", "away_team"}.issubset(game_df.columns):
        pitcher_team = str(game_df["pitcher_team"].dropna().astype(str).iloc[0]) if game_df["pitcher_team"].notna().any() else ""
        home_team = str(game_df["home_team"].dropna().astype(str).iloc[0]) if game_df["home_team"].notna().any() else ""
        away_team = str(game_df["away_team"].dropna().astype(str).iloc[0]) if game_df["away_team"].notna().any() else ""
        if pitcher_team:
            opponent = away_team if pitcher_team == home_team else home_team
    pa_count = int(game_df["at_bat_number"].nunique()) if "at_bat_number" in game_df.columns else int(len(game_df))
    hits = int(events.isin(HIT_EVENTS).sum())
    walks = int(events.isin(WALK_EVENTS).sum())
    strikeouts = int(events.isin(STRIKEOUT_EVENTS).sum())
    line = clean_pitcher_game_line(official_line)
    official_ip = line.get("ip")
    official_hits = line.get("hits")
    official_runs = line.get("runs")
    official_earned_runs = line.get("earned_runs")
    official_walks = line.get("walks")
    official_strikeouts = line.get("strikeouts")
    official_pitches = line.get("pitches")
    official_batters = line.get("batters_faced")
    summary_hits = official_hits if official_hits is not None else hits
    summary_walks = official_walks if official_walks is not None else walks
    summary_strikeouts = official_strikeouts if official_strikeouts is not None else strikeouts
    game_score = calculate_game_score(
        official_ip or format_ip_from_outs(outs),
        summary_hits,
        official_runs,
        official_earned_runs,
        summary_walks,
        summary_strikeouts,
        fallback_outs=outs,
    )
    catcher_name = outing_catcher_name(game_df, year=year)
    return [
        MetricItem(key="date", label="Date", value=game_date.min().date().isoformat() if game_date.notna().any() else "-"),
        MetricItem(key="opponent", label="Opponent", value=opponent),
        MetricItem(key="catcher_name", label="Catcher", value=catcher_name),
        MetricItem(key="ip", label="IP", value=official_ip or format_ip_from_outs(outs)),
        MetricItem(key="hits", label="Hits", value=summary_hits),
        MetricItem(key="runs", label="R", value=official_runs),
        MetricItem(key="earned_runs", label="ER", value=official_earned_runs),
        MetricItem(key="walks", label="BB", value=summary_walks),
        MetricItem(key="strikeouts", label="K", value=summary_strikeouts),
        MetricItem(key="pitches", label="Pitches", value=official_pitches if official_pitches is not None else int(len(game_df))),
        MetricItem(key="batters", label="Batters", value=official_batters if official_batters is not None else pa_count),
        MetricItem(key="game_score", label="Game Score", value=game_score),
        MetricItem(key="avg_velo", label="Avg Velo", value=round(float(avg_velo), 1) if pd.notna(avg_velo) else None),
        MetricItem(key="strike_pct", label="Strike%", value=round(rate_pct(int(strikes.sum()), len(game_df)), 1)),
        MetricItem(key="csw_pct", label="CSW%", value=round(rate_pct(int((whiffs | called).sum()), len(game_df)), 1)),
        MetricItem(key="whiffs", label="Whiffs", value=int(whiffs.sum())),
        MetricItem(key="zone_pct", label="Zone%", value=round(float(in_zone.mean() * 100), 1) if len(game_df) else None),
        MetricItem(key="official_line_status", label="Official Line", value="matched" if line else "fallback"),
    ]


def build_outing_pitch_type_metrics(game_df: pd.DataFrame) -> pd.DataFrame:
    if game_df.empty or "pitch_name" not in game_df.columns:
        return pd.DataFrame()
    working = normalize_pitch_names(game_df.copy())
    working = filter_display_pitch_rows(working)
    if working.empty:
        return pd.DataFrame()
    for column in ["release_speed", "pfx_x", "pfx_z", "estimated_slg_using_speedangle"]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    description = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    working["_swing"] = description.isin(SWING_EVENTS)
    working["_whiff"] = description.isin(WHIFF_EVENTS)
    working["_called"] = description.isin(CALLED_STRIKE_EVENTS)
    working["_strike"] = strike_mask(working)
    records = []
    total = len(working)
    for pitch_name, group in working.groupby("pitch_name", dropna=False):
        batted = group.dropna(subset=["estimated_slg_using_speedangle"]) if "estimated_slg_using_speedangle" in group.columns else pd.DataFrame()
        records.append(
            {
                "Pitch": display_pitch_name(pitch_name),
                "#": int(len(group)),
                "Usage%": round(rate_pct(len(group), total), 1),
                "Velo": round(float(group["release_speed"].mean()), 1) if "release_speed" in group.columns and group["release_speed"].notna().any() else np.nan,
                "IVB": round(float(group["pfx_z"].mean() * 12), 1) if "pfx_z" in group.columns and group["pfx_z"].notna().any() else np.nan,
                "HB": round(float(group["pfx_x"].mean() * -12), 1) if "pfx_x" in group.columns and group["pfx_x"].notna().any() else np.nan,
                "Str%": round(rate_pct(int(group["_strike"].sum()), len(group)), 1),
                "SwStr%": round(rate_pct(int(group["_whiff"].sum()), len(group)), 1),
                "CSW%": round(rate_pct(int((group["_whiff"] | group["_called"]).sum()), len(group)), 1),
                "xSLGcon": round(float(batted["estimated_slg_using_speedangle"].mean()), 3) if not batted.empty else np.nan,
            }
        )
    return pd.DataFrame(records).sort_values("#", ascending=False).reset_index(drop=True)


def build_outing_usage_by_stand(game_df: pd.DataFrame) -> list[dict[str, Any]]:
    if game_df.empty or not {"pitch_name", "stand"}.issubset(game_df.columns):
        return []
    working = filter_display_pitch_rows(normalize_pitch_names(game_df.copy()))
    if working.empty:
        return []
    working["pitch_name"] = working["pitch_name"].astype(str)
    working["stand"] = working["stand"].fillna("").astype(str).str.upper().str.strip()
    total = len(working)
    overall_counts = working["pitch_name"].value_counts()
    rows: list[dict[str, Any]] = []
    for stand_value, label in [("L", "vs LHB"), ("R", "vs RHB")]:
        stand_df = working[working["stand"].eq(stand_value)].copy()
        stand_total = len(stand_df)
        for pitch_name, overall_count in overall_counts.items():
            split_count = int((stand_df["pitch_name"] == pitch_name).sum()) if stand_total else 0
            overall_usage = rate_pct(int(overall_count), total)
            split_usage = rate_pct(split_count, stand_total)
            diff = split_usage - overall_usage if pd.notna(split_usage) and pd.notna(overall_usage) else np.nan
            rows.append(
                {
                    "stand": stand_value,
                    "label": label,
                    "Pitch": display_pitch_name(pitch_name),
                    "pitches": split_count,
                    "total": stand_total,
                    "usage_pct": round(split_usage, 1) if pd.notna(split_usage) else np.nan,
                    "overall_usage_pct": round(overall_usage, 1) if pd.notna(overall_usage) else np.nan,
                    "usage_diff": round(diff, 1) if pd.notna(diff) else np.nan,
                    "direction": "up" if pd.notna(diff) and diff > 0 else ("down" if pd.notna(diff) and diff < 0 else "flat"),
                }
            )
    return rows


def build_outing_location_by_stand(game_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if game_df.empty or "stand" not in game_df.columns:
        return {"L": [], "R": []}
    working = game_df.copy()
    stand = working["stand"].fillna("").astype(str).str.upper().str.strip()
    return {
        "L": build_pitch_location_scatter(working[stand.eq("L")].copy()),
        "R": build_pitch_location_scatter(working[stand.eq("R")].copy()),
    }


def build_primary_fastball_profile(game_df: pd.DataFrame) -> dict[str, Any]:
    if game_df.empty or "pitch_name" not in game_df.columns:
        return {}
    working = filter_display_pitch_rows(normalize_pitch_names(game_df.copy()))
    if working.empty:
        return {}
    pitch_names = working["pitch_name"].fillna("").astype(str)
    fastball_df = working[pitch_names.isin({"Four-Seam", "Sinker", "Cutter"})].copy()
    if fastball_df.empty:
        fastball_df = working.copy()
    primary_pitch = fastball_df["pitch_name"].value_counts().idxmax()
    pitch_df = working[working["pitch_name"].astype(str).eq(str(primary_pitch))].copy()
    for column in ["release_speed", "release_extension", "pfx_x", "pfx_z"]:
        if column in pitch_df.columns:
            pitch_df[column] = pd.to_numeric(pitch_df[column], errors="coerce")
    total = len(working)
    return {
        "Pitch": display_pitch_name(primary_pitch),
        "Pitches": int(len(pitch_df)),
        "Usage%": round(rate_pct(len(pitch_df), total), 1),
        "Velo": round(float(pitch_df["release_speed"].mean()), 1) if "release_speed" in pitch_df.columns and pitch_df["release_speed"].notna().any() else None,
        "Ext": round(float(pitch_df["release_extension"].mean()), 1) if "release_extension" in pitch_df.columns and pitch_df["release_extension"].notna().any() else None,
        "IVB": round(float(pitch_df["pfx_z"].mean() * 12), 1) if "pfx_z" in pitch_df.columns and pitch_df["pfx_z"].notna().any() else None,
        "HB": round(float(pitch_df["pfx_x"].mean() * -12), 1) if "pfx_x" in pitch_df.columns and pitch_df["pfx_x"].notna().any() else None,
    }


def get_personal_outings(year: int, pitcher_id: int) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id)
    outings = build_outing_options(pitch_df)
    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="games", label="Games", value=int(len(outings))),
            MetricItem(key="pitches", label="Pitches", value=int(len(pitch_df))),
        ],
        charts={
            "outing_options": outings.to_dict(orient="records") if not outings.empty else [],
        },
        tables={"outings": dataframe_to_table_payload(outings)},
    )


def get_personal_outing_report(year: int, pitcher_id: int, game_pk: int) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id)
    if pitch_df.empty or "game_pk" not in pitch_df.columns:
        game_df = pd.DataFrame()
    else:
        game_df = pitch_df[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    scored_game_df = add_pitch_stuff_scores(game_df, pitch_df) if not game_df.empty else game_df
    warnings = [] if not game_df.empty else [f"No pitch rows found for game_pk={game_pk}."]
    official_line: dict[str, Any] | None = None
    if not game_df.empty:
        try:
            official_line = load_official_pitcher_game_line(game_pk=game_pk, pitcher_id=pitcher_id, year=year)
        except Exception as exc:
            warnings.append(f"Official game line unavailable; using pitch-level fallback. ({exc})")
        if official_line is None:
            warnings.append("Official game line unavailable; using pitch-level fallback.")
    pitch_type_df = build_outing_pitch_type_metrics(game_df)
    movement_summary_df = build_pitch_movement_summary(game_df)
    league_movement_df = build_league_movement_benchmarks(year)
    pitcher_hand = infer_pitcher_hand(game_df if not game_df.empty else pitch_df)
    movement_comparison_df = build_movement_comparison_table(game_df, pitcher_hand, league_movement_df)
    season_movement_summary_df = build_pitch_movement_summary(pitch_df)
    season_movement_comparison_df = build_movement_comparison_table(pitch_df, pitcher_hand, league_movement_df)
    sample_cols = [
        "game_date",
        "inning",
        "at_bat_number",
        "pitch_number",
        "balls",
        "strikes",
        "pitch_name",
        "release_speed",
        "description",
        "events",
        "stand",
    ]
    sample_df = game_df[[column for column in sample_cols if column in game_df.columns]].copy() if not game_df.empty else pd.DataFrame()
    if "pitch_name" in sample_df.columns:
        sample_df["pitch_name"] = sample_df["pitch_name"].map(display_pitch_name)
    return AnalysisResponse(
        meta=ResponseMeta(
            year=year,
            warnings=warnings,
        ),
        summary=build_outing_summary(game_df, official_line, year=year),
        charts={
            "pitch_mix": build_pitch_type_distribution(game_df),
            "season_pitch_mix": build_pitch_type_distribution(pitch_df),
            "pitch_location_scatter": build_pitch_location_scatter(game_df),
            "movement_scatter": build_movement_scatter_rows(scored_game_df),
            "pitcher_hand": pitcher_hand,
            "usage_by_stand": build_outing_usage_by_stand(game_df),
            "location_by_stand": build_outing_location_by_stand(game_df),
            "primary_fastball": build_primary_fastball_profile(game_df),
        },
        tables={
            "pitch_type_metrics": dataframe_to_table_payload(pitch_type_df),
            "movement_summary": dataframe_to_table_payload(movement_summary_df),
            "movement_league_comparison": dataframe_to_table_payload(movement_comparison_df),
            "season_movement_summary": dataframe_to_table_payload(season_movement_summary_df),
            "season_movement_league_comparison": dataframe_to_table_payload(season_movement_comparison_df),
            "pitches": dataframe_to_table_payload(sample_df),
        },
    )


def add_pitcher_wpa_column(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        working = data.copy()
        working["pitcher_wpa"] = pd.Series(dtype="float")
        return working
    working = data.copy()
    if "pitcher_wpa" in working.columns:
        working["pitcher_wpa"] = pd.to_numeric(working["pitcher_wpa"], errors="coerce")
        return working
    if "pa_home_wpa" not in working.columns:
        working["pitcher_wpa"] = np.nan
        return working
    if "pitcher_team" not in working.columns and {"inning_topbot", "home_team", "away_team"}.issubset(working.columns):
        working["pitcher_team"] = np.where(working["inning_topbot"].astype(str) == "Top", working["home_team"], working["away_team"])
    if {"pitcher_team", "home_team"}.issubset(working.columns):
        raw_pitcher_wpa = np.where(
            working["pitcher_team"] == working["home_team"],
            pd.to_numeric(working["pa_home_wpa"], errors="coerce"),
            -pd.to_numeric(working["pa_home_wpa"], errors="coerce"),
        )
        working["pitcher_wpa"] = calibrate_pitcher_wpa(raw_pitcher_wpa)
    else:
        working["pitcher_wpa"] = np.nan
    return working


def build_pitcher_wpa_games(pitch_df: pd.DataFrame) -> pd.DataFrame:
    if pitch_df.empty or not {"game_date", "game_pk"}.issubset(pitch_df.columns):
        return pd.DataFrame()
    working = add_pitcher_wpa_column(pitch_df)
    working["pitcher_wpa_once"] = one_wpa_value_per_pa(working, "pitcher_wpa")
    working["game_date"] = pd.to_datetime(working["game_date"], errors="coerce")
    if "pitcher_team" not in working.columns and {"inning_topbot", "home_team", "away_team"}.issubset(working.columns):
        working["pitcher_team"] = np.where(working["inning_topbot"].astype(str) == "Top", working["home_team"], working["away_team"])
    if "opponent_team" not in working.columns and {"pitcher_team", "home_team", "away_team"}.issubset(working.columns):
        working["opponent_team"] = np.where(working["pitcher_team"] == working["home_team"], working["away_team"], working["home_team"])
    group_cols = [column for column in ["game_date", "game_pk", "pitcher_team", "opponent_team"] if column in working.columns]
    games = (
        working.groupby(group_cols, dropna=False)
        .agg(game_wpa=("pitcher_wpa_once", "sum"), pitches=("game_pk", "size"))
        .reset_index()
        .sort_values(["game_date", "game_pk"])
    )
    games["cum_wpa"] = games["game_wpa"].cumsum()
    if {"game_date", "opponent_team", "pitches"}.issubset(games.columns):
        games["label"] = games.apply(lambda row: f"{row['game_date'].date()} vs {row['opponent_team']} ({row['pitches']:.0f} pitches)", axis=1)
    return games


def build_fatigue_inning_table(pitch_df: pd.DataFrame, selected_game_pk: int) -> pd.DataFrame:
    if pitch_df.empty or "game_pk" not in pitch_df.columns or "inning" not in pitch_df.columns:
        return pd.DataFrame()
    game_pitch_df = pitch_df[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(selected_game_pk))].copy()
    if game_pitch_df.empty:
        return pd.DataFrame()
    game_pitch_df = game_pitch_df.sort_values(["inning", "pitch_number"] if "pitch_number" in game_pitch_df.columns else ["inning"])
    for column in ["release_speed", "release_spin_rate", "pfx_x", "pfx_z"]:
        if column in game_pitch_df.columns:
            game_pitch_df[column] = pd.to_numeric(game_pitch_df[column], errors="coerce")
    rows = []
    cumulative_pitches = 0
    for inning, inning_df in game_pitch_df.groupby("inning", dropna=True):
        cumulative_pitches += len(inning_df)
        fatigue_score = float(np.clip(100 - cumulative_pitches * 0.75, 20, 100))
        fastball_mask = inning_df["pitch_type"].isin(FASTBALL_TYPES) if "pitch_type" in inning_df.columns else pd.Series(False, index=inning_df.index)
        breaking_mask = inning_df["pitch_type"].isin(BREAKING_TYPES) if "pitch_type" in inning_df.columns else pd.Series(False, index=inning_df.index)
        breaking_move = np.nan
        if {"pfx_x", "pfx_z"}.issubset(inning_df.columns):
            breaking_move = np.sqrt((inning_df.loc[breaking_mask, "pfx_x"] * 12) ** 2 + (inning_df.loc[breaking_mask, "pfx_z"] * 12) ** 2).mean()
        rows.append(
            {
                "Inning": int(inning),
                "Pitches This Inning": len(inning_df),
                "Cumulative Pitches": cumulative_pitches,
                "Fastball Velo": inning_df.loc[fastball_mask, "release_speed"].mean() if "release_speed" in inning_df.columns else np.nan,
                "Breaking Move": breaking_move,
                "Spin Rate": inning_df["release_spin_rate"].mean() if "release_spin_rate" in inning_df.columns else np.nan,
                "Pregame Readiness": 100.0,
                "Fatigue Score": fatigue_score,
            }
        )
    return pd.DataFrame(rows)


def get_personal_rotation(
    year: int,
    pitcher_id: int,
    game_pk: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id, start_date=start_date, end_date=end_date)
    pitch_df = attach_plate_appearance_wpa(pitch_df, year, settings.data_dir)
    game_log_df = build_game_log(pitch_df)
    wpa_games_df = build_pitcher_wpa_games(pitch_df)
    selected_game_pk = int(game_pk) if game_pk is not None else (int(wpa_games_df["game_pk"].iloc[-1]) if not wpa_games_df.empty else None)
    fatigue_df = build_fatigue_inning_table(pitch_df, selected_game_pk) if selected_game_pk is not None else pd.DataFrame()
    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="games", label="Games", value=int(game_log_df["game_pk"].nunique()) if not game_log_df.empty else 0),
            MetricItem(key="pitches", label="Pitches", value=int(len(pitch_df))),
            MetricItem(key="total_wpa", label="Total WPA", value=clean_value(wpa_games_df["game_wpa"].sum()) if not wpa_games_df.empty else None),
        ],
        charts={"wpa_games": dataframe_to_table_payload(wpa_games_df).rows},
        tables={
            "game_log": dataframe_to_table_payload(game_log_df),
            "fatigue_by_inning": dataframe_to_table_payload(fatigue_df),
        },
    )


def get_personal_videos(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id, start_date=start_date, end_date=end_date)
    video_columns = [
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "pitch_name",
        "description",
        "events",
        "batter",
        "player_name",
        "play_id",
        "video_url",
    ]
    available_columns = [column for column in video_columns if column in pitch_df.columns]
    if not available_columns:
        video_df = pd.DataFrame()
    else:
        video_df = pitch_df[available_columns].copy()
        if "video_url" in video_df.columns:
            video_df = video_df[video_df["video_url"].notna() & video_df["video_url"].astype(str).str.strip().ne("")]
        elif "play_id" in video_df.columns:
            video_df = video_df[video_df["play_id"].notna() & video_df["play_id"].astype(str).str.strip().ne("")]
            video_df["video_url"] = "https://baseballsavant.mlb.com/sporty-videos?playId=" + video_df["play_id"].astype(str)
        video_df = video_df.head(max(0, min(limit, 1000)))
    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[
            MetricItem(key="video_rows", label="Video Rows", value=int(len(video_df))),
            MetricItem(key="cached_pitches", label="Cached Pitches", value=int(len(pitch_df))),
        ],
        tables={"videos": dataframe_to_table_payload(video_df)},
    )


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    values_num = pd.to_numeric(values, errors="coerce")
    weights_num = pd.to_numeric(weights, errors="coerce")
    mask = values_num.notna() & weights_num.notna() & weights_num.gt(0)
    if not mask.any():
        return float("nan")
    return float(np.average(values_num[mask], weights=weights_num[mask]))


def numeric_column(df: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(default, index=df.index, dtype="float64")


def load_pitch_timing_summary(year: int) -> pd.DataFrame:
    summary_path = settings.data_dir / "MissDistance" / f"{int(year)}_pitch_timing_summary_full_season.csv"
    if not summary_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(summary_path, low_memory=False)
    for column in TIMING_NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["player_id"] = pd.to_numeric(df.get("id"), errors="coerce").astype("Int64")
    df["pitch_code"] = df.get("api_pitch_type", pd.Series(index=df.index, dtype="object")).fillna("").astype(str)
    df["pitch_name"] = df["pitch_code"].map(lambda value: TIMING_PITCH_CODE_LABELS.get(value, value))
    df["n_swings"] = numeric_column(df, "n_swings").fillna(0)
    df["whiff_rate"] = numeric_column(df, "whiff_rate").fillna(0)
    df["whiff_swings"] = df["n_swings"] * df["whiff_rate"]
    return df[df["player_id"].notna()].copy()


def build_timing_pitch_table(player_df: pd.DataFrame) -> pd.DataFrame:
    if player_df.empty:
        return pd.DataFrame()
    for column in [
        "flawed_percent",
        "perfect_percent",
        "competitive_percent",
        "early_percent",
        "on_time_percent",
        "late_percent",
        "over_percent",
        "lined_up_percent",
        "under_percent",
    ]:
        if column not in player_df.columns:
            player_df[column] = np.nan
    group_cols = ["pitch_name", "pitch_code"]
    aggregations = {
        "n_swings": ("n_swings", "sum"),
        "whiff_swings": ("whiff_swings", "sum"),
        "miss_distance": ("miss_distance", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "flawed_percent": ("flawed_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "perfect_percent": ("perfect_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "competitive_percent": ("competitive_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "early_percent": ("early_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "on_time_percent": ("on_time_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "late_percent": ("late_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "over_percent": ("over_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "lined_up_percent": ("lined_up_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
        "under_percent": ("under_percent", lambda s: weighted_average(s, player_df.loc[s.index, "n_swings"])),
    }
    table = player_df.groupby(group_cols, dropna=False).agg(**aggregations).reset_index()
    table["whiff_rate"] = np.where(table["n_swings"] > 0, table["whiff_swings"] / table["n_swings"], np.nan)
    return table.sort_values("n_swings", ascending=False).reset_index(drop=True)


def build_timing_axis_points(player_df: pd.DataFrame, axis_type: str) -> list[dict[str, float | str]]:
    total_swings = numeric_column(player_df, "n_swings").fillna(0).sum()
    if total_swings <= 0:
        return []
    points: list[dict[str, float | str]] = []
    for row in player_df.itertuples(index=False):
        row_swings = float(getattr(row, "n_swings", 0) or 0)
        if row_swings <= 0:
            continue
        swing_share = row_swings / total_swings
        pitch_name = str(getattr(row, "pitch_name", "") or "")
        if axis_type == "x":
            specs = [
                ("Tied Up", getattr(row, "avg_x_tied_up", np.nan), getattr(row, "tied_up_percent", np.nan)),
                ("Centered", 0.0, getattr(row, "centered_percent", np.nan)),
                ("Flail", getattr(row, "avg_x_flail", np.nan), getattr(row, "flailed_percent", np.nan)),
            ]
        elif axis_type == "y":
            specs = [
                ("Late", getattr(row, "avg_y_late", np.nan), getattr(row, "late_percent", np.nan)),
                ("On Time", 0.0, getattr(row, "on_time_percent", np.nan)),
                ("Early", getattr(row, "avg_y_early", np.nan), getattr(row, "early_percent", np.nan)),
            ]
        else:
            specs = [
                ("Over", getattr(row, "avg_z_over", np.nan), getattr(row, "over_percent", np.nan)),
                ("Lined Up", 0.0, getattr(row, "lined_up_percent", np.nan)),
                ("Under", getattr(row, "avg_z_under", np.nan), getattr(row, "under_percent", np.nan)),
            ]
        for category, x_value, pct in specs:
            pct_value = pd.to_numeric(pd.Series([pct]), errors="coerce").iloc[0]
            x_numeric = pd.to_numeric(pd.Series([x_value]), errors="coerce").iloc[0]
            if pd.isna(pct_value) or pct_value <= 0 or pd.isna(x_numeric):
                continue
            points.append({"pitch_name": pitch_name, "category": category, "x": float(x_numeric), "y": float(pct_value * swing_share * 100.0)})
    return points


def get_personal_timing(year: int, pitcher_id: int) -> AnalysisResponse:
    timing_df = load_pitch_timing_summary(year)
    player_df = timing_df[numeric_column(timing_df, "player_id").eq(int(pitcher_id))].copy() if not timing_df.empty else pd.DataFrame()
    timing_table = build_timing_pitch_table(player_df)
    total_swings = numeric_column(player_df, "n_swings").fillna(0).sum() if not player_df.empty else 0
    total_whiffs = numeric_column(player_df, "whiff_swings").fillna(0).sum() if not player_df.empty else 0
    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=[] if year == 2025 else ["Timing summary is currently available only when the matching yearly CSV exists."]),
        summary=[
            MetricItem(key="n_swings", label="Swings", value=clean_value(total_swings)),
            MetricItem(key="whiff_rate", label="Whiff Rate", value=clean_value(total_whiffs / total_swings if total_swings else None)),
            MetricItem(key="pitch_types", label="Pitch Types", value=int(timing_table["pitch_name"].nunique()) if not timing_table.empty else 0),
        ],
        charts={
            "x_timing_points": build_timing_axis_points(player_df, "x"),
            "y_timing_points": build_timing_axis_points(player_df, "y"),
            "z_timing_points": build_timing_axis_points(player_df, "z"),
        },
        tables={"timing_by_pitch": dataframe_to_table_payload(timing_table)},
    )
