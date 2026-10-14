from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.api.schemas.common import TablePayload
from app.api.schemas.comparison import (
    ComparisonMetric,
    ComparisonOptionsResponse,
    ComparisonOverviewResponse,
    ComparisonPlayer,
)
from app.api.schemas.common import ResponseMeta
from app.core.config import settings
from app.repositories.pitch_repository import (
    get_season_duckdb_path,
    load_pitcher_cached_season,
    load_pitcher_latest_teams,
    load_pitcher_master_and_appearances,
    load_pitcher_season_date_range,
)
from app.services.personal_service import (
    CALLED_STRIKE_EVENTS,
    HIT_EVENTS,
    NON_AB_EVENTS,
    STRIKEOUT_EVENTS,
    SWING_EVENTS,
    WALK_EVENTS,
    WHIFF_EVENTS,
    add_pitch_stuff_scores,
    apply_stuff_filters,
    build_discipline_panel_groups,
    build_league_movement_benchmarks,
    build_movement_comparison_table,
    build_pitch_movement_summary,
    estimate_outs_recorded,
    format_ip_from_outs,
    infer_pitcher_hand,
    build_pitch_location_scatter,
    normalize_pitch_names,
    rate_pct,
    red_strike_zone_mask,
)


BASE_METRIC_SPECS: list[dict[str, Any]] = [
    {"key": "xERA", "label": "xERA", "higher_is_better": False, "format": "{:.2f}"},
    {"key": "xBA", "label": "xBA", "higher_is_better": False, "format": "{:.3f}"},
    {"key": "fastball_velo", "label": "Fastball Velo", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "avg_ev", "label": "Avg Exit Velo", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "chase_pct", "label": "Chase %", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "whiff_pct", "label": "Whiff %", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "k_pct", "label": "K %", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "bb_pct", "label": "BB %", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "barrel_pct", "label": "Barrel %", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "hard_hit_pct", "label": "Hard-Hit %", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "gb_pct", "label": "GB %", "higher_is_better": True, "format": "{:.1f}"},
]


PERIOD_METRIC_SPECS: list[dict[str, Any]] = [
    {"key": "xBA", "label": "xBA", "higher_is_better": False, "format": "{:.3f}"},
    {"key": "fastball_velo", "label": "Fastball Velo", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "avg_ev", "label": "Avg Exit Velo", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "chase_pct", "label": "Chase %", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "whiff_pct", "label": "Whiff %", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "k_pct", "label": "K %", "higher_is_better": True, "format": "{:.1f}"},
    {"key": "bb_pct", "label": "BB %", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "barrel_pct", "label": "Barrel %", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "hard_hit_pct", "label": "Hard-Hit %", "higher_is_better": False, "format": "{:.1f}"},
    {"key": "gb_pct", "label": "GB %", "higher_is_better": True, "format": "{:.1f}"},
]


RENAME_MAP = {
    "xba": "xBA",
    "fastball_avg_speed": "fastball_velo",
    "exit_velocity_avg": "avg_ev",
    "oz_swing_percent": "chase_pct",
    "whiff_percent": "whiff_pct",
    "k_percent": "k_pct",
    "bb_percent": "bb_pct",
    "barrel_batted_rate": "barrel_pct",
    "hard_hit_percent": "hard_hit_pct",
    "groundballs_percent": "gb_pct",
}


def comparison_data_dir() -> Path:
    candidates = [
        settings.data_dir,
        Path.home() / "Desktop" / "實習個案" / "abs2025" / "data",
        Path(__file__).resolve().parents[3] / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def comparison_path(year: int) -> Path:
    return comparison_data_dir() / f"{year}_pitcher_comparison.csv"


def pitching_estimators_path(year: int) -> Path:
    return comparison_data_dir() / f"{year}_pitching_estimators.csv"


def available_comparison_years() -> list[int]:
    years: list[int] = []
    for path in comparison_data_dir().glob("*_pitcher_comparison.csv"):
        stem = path.stem.split("_", 1)[0]
        if stem.isdigit():
            years.append(int(stem))
    return sorted(set(years), reverse=True)


def metric_specs(year: int) -> list[dict[str, Any]]:
    return [
        {"key": "fip", "label": "FIP", "higher_is_better": False, "format": "{:.2f}"},
        {"key": "xfip", "label": "xFIP", "higher_is_better": False, "format": "{:.2f}"},
        *[spec for spec in BASE_METRIC_SPECS if spec["key"] != "xERA"],
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
    rows = [{key: clean_value(value) for key, value in row.items()} for row in df.to_dict(orient="records")]
    columns = [{"key": column, "label": column} for column in df.columns]
    return TablePayload(columns=columns, rows=rows)


def format_metric_value(value: Any, fmt: str, key: str) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return "-"
    formatted = fmt.format(float(numeric))
    if key in {"chase_pct", "whiff_pct", "k_pct", "bb_pct", "barrel_pct", "hard_hit_pct", "gb_pct"}:
        return f"{formatted}%"
    return formatted


def _read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def merge_role_metric_sources(pool: pd.DataFrame, year: int) -> pd.DataFrame:
    sources = [
        ("SP", comparison_data_dir() / "Starter" / f"{year}_starter_advanced.csv"),
        ("SP", comparison_data_dir() / "Starter" / "2021_2026_starter_dashboard.csv"),
        ("SP", comparison_data_dir() / f"MLB{year}" / f"{year}_starter.csv"),
        ("RP", comparison_data_dir() / "Reliever" / f"{year}_reliever_standard.csv"),
        ("RP", comparison_data_dir() / "Reliever" / "2021_2026_reliever_dashboard.csv"),
        ("RP", comparison_data_dir() / f"MLB{year}" / f"{year}_reliever.csv"),
    ]
    metric_frames: list[pd.DataFrame] = []
    for role, path in sources:
        source = _read_optional_csv(path)
        if source.empty or "MLBAMID" not in source.columns:
            continue
        if "Season" in source.columns:
            source = source[pd.to_numeric(source["Season"], errors="coerce").eq(int(year))].copy()
        if source.empty:
            continue
        source = source.rename(columns={"FIP": "fip", "xFIP": "xfip", "Team": "source_team"})
        source["player_id"] = pd.to_numeric(source["MLBAMID"], errors="coerce")
        source = source.dropna(subset=["player_id"]).copy()
        source["player_id"] = source["player_id"].astype(int)
        source["source_role"] = role
        keep_cols = [column for column in ["player_id", "fip", "xfip", "source_team", "source_role"] if column in source.columns]
        metric_frames.append(source[keep_cols])
    if not metric_frames:
        return pool

    metrics = pd.concat(metric_frames, ignore_index=True).drop_duplicates("player_id", keep="first")
    merged = pool.merge(metrics, on="player_id", how="left", suffixes=("", "_source"))
    for column in ["fip", "xfip"]:
        source_column = f"{column}_source"
        if column not in merged.columns:
            merged[column] = pd.NA
        if source_column in merged.columns:
            merged[column] = merged[column].combine_first(merged[source_column])
            merged = merged.drop(columns=[source_column])

    if "team" not in merged.columns:
        merged["team"] = pd.NA
    if "source_team" in merged.columns:
        missing_team = merged["team"].isna() | merged["team"].astype(str).str.strip().isin(["", "FA"])
        merged.loc[missing_team, "team"] = merged.loc[missing_team, "source_team"]
        merged = merged.drop(columns=["source_team"])

    if "role" not in merged.columns:
        merged["role"] = pd.NA
    if "source_role" in merged.columns:
        missing_role = merged["role"].isna() | merged["role"].astype(str).str.strip().isin(["", "RP"])
        merged.loc[missing_role, "role"] = merged.loc[missing_role, "source_role"]
        merged = merged.drop(columns=["source_role"])
    return merged


@lru_cache(maxsize=16)
def _load_comparison_pool_cached(year: int, _comparison_stamp: int, _pitch_stamp: int) -> pd.DataFrame:
    path = comparison_path(year)
    if not path.exists():
        return pd.DataFrame()

    pool = pd.read_csv(path, low_memory=False).rename(columns=RENAME_MAP)
    pool["player_id"] = pd.to_numeric(pool.get("player_id"), errors="coerce")
    pool["year"] = pd.to_numeric(pool.get("year"), errors="coerce")
    pool = pool[(pool["year"] == year) & pool["player_id"].notna()].copy()
    if pool.empty:
        return pool

    pool["player_id"] = pool["player_id"].astype(int)

    estimators = _read_optional_csv(pitching_estimators_path(year))
    if not estimators.empty:
        estimators["player_id"] = pd.to_numeric(estimators.get("player_id"), errors="coerce")
        estimators = estimators.dropna(subset=["player_id"]).copy()
        estimators["player_id"] = estimators["player_id"].astype(int)
        keep_cols = [column for column in ["player_id", "fip", "xfip", "siera"] if column in estimators.columns]
        if len(keep_cols) > 1:
            pool = pool.merge(estimators[keep_cols].drop_duplicates("player_id"), on="player_id", how="left")
    pool = merge_role_metric_sources(pool, year)

    if "display_name" not in pool.columns:
        pool["display_name"] = pd.NA
    if "last_name, first_name" in pool.columns:
        fallback_name = pool["last_name, first_name"].astype(str).map(
            lambda value: " ".join(part.strip() for part in value.split(",")[::-1]).strip()
        )
        pool["display_name"] = pool["display_name"].fillna(fallback_name)
    pool["display_name"] = pool["display_name"].fillna(pool["player_id"].astype(str))

    if "team" not in pool.columns:
        pool["team"] = pd.NA
    team_lookup = load_pitcher_latest_teams(year, settings.data_dir).rename(columns={"team": "team_from_pitches"})
    if not team_lookup.empty:
        pool = pool.merge(team_lookup, on="player_id", how="left")
        latest_team = pool["team_from_pitches"].fillna("").astype(str).str.strip()
        pool.loc[latest_team.ne(""), "team"] = latest_team[latest_team.ne("")]
        pool = pool.drop(columns=["team_from_pitches"])
    pool["team"] = pool["team"].replace("", pd.NA).fillna("FA").astype(str)

    if "role" not in pool.columns:
        pool["role"] = "RP"
    pool["role"] = pool["role"].replace("", pd.NA).fillna("RP").astype(str).str.upper()
    _, appearance_stats = load_pitcher_master_and_appearances(year, settings.data_dir)
    if not appearance_stats.empty and {"player_id", "G", "GS"}.issubset(appearance_stats.columns):
        roles = appearance_stats[["player_id", "G", "GS"]].copy()
        roles["player_id"] = pd.to_numeric(roles["player_id"], errors="coerce")
        roles["G"] = pd.to_numeric(roles["G"], errors="coerce").fillna(0)
        roles["GS"] = pd.to_numeric(roles["GS"], errors="coerce").fillna(0)
        roles = roles[roles["player_id"].notna() & roles["G"].gt(0)].copy()
        roles["player_id"] = roles["player_id"].astype(int)
        roles["role_from_appearances"] = np.where(roles["GS"] / roles["G"] > 0.3, "SP", "RP")
        pool = pool.merge(roles[["player_id", "role_from_appearances"]], on="player_id", how="left")
        has_appearance_role = pool["role_from_appearances"].notna()
        pool.loc[has_appearance_role, "role"] = pool.loc[has_appearance_role, "role_from_appearances"]
        pool = pool.drop(columns=["role_from_appearances"])

    pool["display_label"] = (
        pool["display_name"].astype(str)
        + " ("
        + pool["team"].astype(str)
        + ", "
        + pool["role"].astype(str)
        + ")"
    )

    for spec in metric_specs(year):
        key = str(spec["key"])
        if key not in pool.columns:
            pool[key] = np.nan
        series = pd.to_numeric(pool[key], errors="coerce")
        pct = series.rank(pct=True) * 100
        if not bool(spec["higher_is_better"]):
            non_null = int(series.notna().sum())
            pct = (1 - series.rank(pct=True) + (1 / non_null if non_null else 0)) * 100
        pool[f"{key}_pct"] = pct.clip(1, 100)

    return pool.sort_values("display_name").reset_index(drop=True)


def _file_stamp(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def load_comparison_pool(year: int) -> pd.DataFrame:
    normalized_year = int(year)
    return _load_comparison_pool_cached(
        normalized_year,
        _file_stamp(comparison_path(normalized_year)),
        _file_stamp(get_season_duckdb_path(normalized_year, settings.data_dir)),
    )


def clear_comparison_pool_cache() -> None:
    _load_comparison_pool_cached.cache_clear()


def player_from_row(row: pd.Series) -> ComparisonPlayer:
    return ComparisonPlayer(
        player_id=int(row["player_id"]),
        display_name=str(row.get("display_name") or ""),
        team=str(row.get("team") or "FA"),
        role=str(row.get("role") or ""),
        display_label=str(row.get("display_label") or ""),
        meta={
            "year": clean_value(row.get("year")),
            "hand": clean_value(row.get("p_throws")),
        },
    )


def build_metric_card(row: pd.Series, year: int) -> list[ComparisonMetric]:
    card: list[ComparisonMetric] = []
    for spec in metric_specs(year):
        key = str(spec["key"])
        value = clean_value(row.get(key))
        card.append(
            ComparisonMetric(
                key=key,
                label=str(spec["label"]),
                value=value,
                formatted_value=format_metric_value(value, str(spec["format"]), key),
                percentile=clean_value(row.get(f"{key}_pct")),
                higher_is_better=bool(spec["higher_is_better"]),
            )
        )
    return card


def percentile_from_pool(year: int, key: str, value: Any, higher_is_better: bool) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    pool = load_comparison_pool(year)
    if pool.empty or key not in pool.columns:
        return None
    series = pd.to_numeric(pool[key], errors="coerce").dropna()
    if series.empty:
        return None
    percentile = (series <= numeric).mean() * 100 if higher_is_better else (series >= numeric).mean() * 100
    return float(np.clip(percentile, 1, 100))


def build_metric_card_from_values(values: dict[str, Any], year: int, specs: list[dict[str, Any]]) -> list[ComparisonMetric]:
    card: list[ComparisonMetric] = []
    for spec in specs:
        key = str(spec["key"])
        value = clean_value(values.get(key))
        card.append(
            ComparisonMetric(
                key=key,
                label=str(spec["label"]),
                value=value,
                formatted_value=format_metric_value(value, str(spec["format"]), key),
                percentile=percentile_from_pool(year, key, value, bool(spec["higher_is_better"])),
                higher_is_better=bool(spec["higher_is_better"]),
            )
        )
    return card


def build_metric_comparison_table(
    left_metrics: list[ComparisonMetric],
    right_metrics: list[ComparisonMetric],
) -> TablePayload:
    left_by_key = {metric.key: metric for metric in left_metrics}
    right_by_key = {metric.key: metric for metric in right_metrics}
    ordered_keys: list[str] = []
    for metric in [*left_metrics, *right_metrics]:
        if metric.key not in ordered_keys:
            ordered_keys.append(metric.key)

    rows: list[dict[str, Any]] = []
    for key in ordered_keys:
        left = left_by_key.get(key)
        right = right_by_key.get(key)
        label = left.label if left else (right.label if right else key)
        left_pct = pd.to_numeric(left.percentile if left else None, errors="coerce")
        right_pct = pd.to_numeric(right.percentile if right else None, errors="coerce")
        pct_gap = left_pct - right_pct if pd.notna(left_pct) and pd.notna(right_pct) else np.nan
        if pd.isna(pct_gap):
            edge = "-"
        elif abs(float(pct_gap)) < 0.5:
            edge = "Even"
        else:
            edge = "Left" if pct_gap > 0 else "Right"
        rows.append(
            {
                "Metric": label,
                "Left": left.formatted_value if left else "-",
                "Left Pctl": round(float(left_pct)) if pd.notna(left_pct) else None,
                "Right": right.formatted_value if right else "-",
                "Right Pctl": round(float(right_pct)) if pd.notna(right_pct) else None,
                "Pctl Gap": round(float(pct_gap), 1) if pd.notna(pct_gap) else None,
                "Edge": edge,
            }
        )
    return dataframe_to_table_payload(pd.DataFrame(rows))


def build_advantages(table: TablePayload) -> dict[str, list[dict[str, Any]]]:
    rows = table.rows
    parsed = []
    for row in rows:
        gap = pd.to_numeric(row.get("Pctl Gap"), errors="coerce")
        if pd.notna(gap):
            parsed.append({**row, "gap_abs": abs(float(gap))})
    left = [row for row in parsed if row.get("Edge") == "Left"]
    right = [row for row in parsed if row.get("Edge") == "Right"]
    return {
        "left": sorted(left, key=lambda row: row["gap_abs"], reverse=True)[:4],
        "right": sorted(right, key=lambda row: row["gap_abs"], reverse=True)[:4],
    }


def get_comparison_options(year: int) -> ComparisonOptionsResponse:
    pool = load_comparison_pool(year)
    pitchers = [player_from_row(row) for _, row in pool.iterrows()]
    return ComparisonOptionsResponse(
        meta=ResponseMeta(year=year, warnings=[] if pitchers else [f"No comparison data found for {year}."]),
        years=available_comparison_years(),
        pitchers=pitchers,
    )


def build_pitcher_team_stints(pitches: pd.DataFrame) -> list[dict[str, object]]:
    required = {"game_date", "pitcher_team"}
    if pitches.empty or not required.issubset(pitches.columns):
        return []

    working = pitches.copy()
    working["game_date"] = pd.to_datetime(working["game_date"], errors="coerce")
    working["pitcher_team"] = working["pitcher_team"].fillna("").astype(str).str.strip()
    working = working[working["game_date"].notna() & working["pitcher_team"].ne("")].copy()
    if working.empty:
        return []

    game_keys = ["game_date"]
    if "game_pk" in working.columns:
        game_keys.append("game_pk")
    games = (
        working.groupby([*game_keys, "pitcher_team"], dropna=False)
        .size()
        .reset_index(name="pitches")
        .sort_values([*game_keys, "pitches", "pitcher_team"], ascending=[True] * len(game_keys) + [False, True])
        .drop_duplicates(game_keys, keep="first")
        .sort_values(game_keys)
        .reset_index(drop=True)
    )
    games["stint_group"] = games["pitcher_team"].ne(games["pitcher_team"].shift()).cumsum()

    stints: list[dict[str, object]] = []
    for stint_index, (_, stint) in enumerate(games.groupby("stint_group", sort=True), start=1):
        team = str(stint["pitcher_team"].iloc[0])
        start_date = stint["game_date"].min().strftime("%Y-%m-%d")
        end_date = stint["game_date"].max().strftime("%Y-%m-%d")
        stints.append(
            {
                "stint_index": stint_index,
                "team": team,
                "start_date": start_date,
                "end_date": end_date,
                "pitches": int(stint["pitches"].sum()),
                "games": int(len(stint)),
                "label": f"{team} · {start_date}–{end_date}",
            }
        )
    return stints


def get_period_date_range(year: int, pitcher_id: int) -> dict[str, object]:
    pitches = load_pitcher_cached_season(year, pitcher_id, settings.data_dir)
    team_stints = build_pitcher_team_stints(pitches)
    return {
        "year": int(year),
        "pitcher_id": int(pitcher_id),
        **load_pitcher_season_date_range(year, pitcher_id, settings.data_dir),
        "current_team": team_stints[-1]["team"] if team_stints else None,
        "transfer_count": max(0, len(team_stints) - 1),
        "team_stints": team_stints,
    }


def get_comparison_overview(
    left_year: int,
    right_year: int,
    left_pitcher_id: int,
    right_pitcher_id: int,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
) -> ComparisonOverviewResponse:
    left_pool = load_comparison_pool(left_year)
    right_pool = load_comparison_pool(right_year)
    warnings: list[str] = []
    left_rows = left_pool[left_pool["player_id"] == int(left_pitcher_id)] if not left_pool.empty else pd.DataFrame()
    right_rows = right_pool[right_pool["player_id"] == int(right_pitcher_id)] if not right_pool.empty else pd.DataFrame()

    if left_rows.empty:
        warnings.append(f"Left pitcher {left_pitcher_id} was not found for {left_year}.")
    if right_rows.empty:
        warnings.append(f"Right pitcher {right_pitcher_id} was not found for {right_year}.")

    left_row = left_rows.iloc[0] if not left_rows.empty else None
    right_row = right_rows.iloc[0] if not right_rows.empty else None

    left_metrics = build_metric_card(left_row, left_year) if left_row is not None else []
    right_metrics = build_metric_card(right_row, right_year) if right_row is not None else []
    metric_table = build_metric_comparison_table(left_metrics, right_metrics)
    left_df = load_pitcher_cached_season(left_year, left_pitcher_id, settings.data_dir)
    right_df = load_pitcher_cached_season(right_year, right_pitcher_id, settings.data_dir)
    left_df = apply_stuff_filters(
        left_df,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
    )
    right_df = apply_stuff_filters(
        right_df,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
    )

    return ComparisonOverviewResponse(
        meta=ResponseMeta(year=right_year, warnings=warnings),
        players={
            "left": player_from_row(left_row) if left_row is not None else None,
            "right": player_from_row(right_row) if right_row is not None else None,
        },
        percentile_cards={
            "left": left_metrics,
            "right": right_metrics,
        },
        charts={
            "advantages": build_advantages(metric_table),
            "period_counts": {"left": int(len(left_df)), "right": int(len(right_df))},
            "period_locations": {
                "left": build_period_location_points(left_df),
                "right": build_period_location_points(right_df),
            },
            "period_movement": {
                "left": build_period_movement_payload(left_df, left_year),
                "right": build_period_movement_payload(right_df, right_year),
            },
            "period_pitch_mix": {
                "left": build_period_pitch_mix_payload(left_df),
                "right": build_period_pitch_mix_payload(right_df),
            },
            "period_discipline": {
                "left": build_period_discipline_payload(left_df),
                "right": build_period_discipline_payload(right_df),
            },
            "period_videos": {
                "left": build_period_video_payload(left_df),
                "right": build_period_video_payload(right_df),
            },
        },
        tables={"metric_comparison": metric_table},
        notes=[
            "Stuff detail is intentionally excluded from this first migration slice.",
            "Each side's percentiles are calculated within that side's selected season pool.",
        ],
    )


def compute_period_metrics(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {str(spec["key"]): np.nan for spec in PERIOD_METRIC_SPECS}

    working = normalize_pitch_names(df)
    descriptions = working.get("description", pd.Series(dtype="object")).fillna("").astype(str).str.lower().str.strip()
    events = working.get("events", pd.Series(dtype="object")).fillna("").astype(str).str.lower().str.strip()
    zones = pd.to_numeric(working.get("zone"), errors="coerce")
    out_zone = zones.notna() & ~zones.between(1, 9)
    swings = descriptions.isin(SWING_EVENTS)
    whiffs = descriptions.isin(WHIFF_EVENTS)
    launch_speed = pd.to_numeric(working.get("launch_speed"), errors="coerce")
    xba = pd.to_numeric(working.get("estimated_ba_using_speedangle"), errors="coerce")

    pitch_names = working.get("pitch_name", pd.Series(dtype="object")).astype(str)
    fastball_mask = pitch_names.isin(["Four-Seam", "Sinker", "Cutter", "4-Seam Fastball", "Fastball"])
    fastball_velo = pd.to_numeric(working.loc[fastball_mask, "release_speed"], errors="coerce").mean() if "release_speed" in working.columns else np.nan

    pa_df = working.copy()
    if {"game_pk", "at_bat_number", "pitch_number"}.issubset(pa_df.columns):
        pa_df["pitch_number"] = pd.to_numeric(pa_df["pitch_number"], errors="coerce")
        pa_df = pa_df.sort_values(["game_pk", "at_bat_number", "pitch_number"])
        pa_df = pa_df.groupby(["game_pk", "at_bat_number"], as_index=False).tail(1)
    pa_events = pa_df.get("events", pd.Series(dtype="object")).fillna("").astype(str).str.lower().str.strip()
    pa_count = len(pa_df)
    ab_mask = pa_events.ne("") & ~pa_events.isin(NON_AB_EVENTS)

    bb_type = working.get("bb_type", pd.Series(dtype="object")).fillna("").astype(str).str.lower().str.strip()
    bb_type_mask = bb_type.isin({"ground_ball", "fly_ball", "line_drive", "popup"})
    tracked_batted_ball = bb_type_mask & launch_speed.notna()
    launch_speed_angle = pd.to_numeric(working.get("launch_speed_angle"), errors="coerce")

    return {
        "xBA": xba.fillna(0).sum() / int(ab_mask.sum()) if int(ab_mask.sum()) else np.nan,
        "fastball_velo": fastball_velo,
        "avg_ev": launch_speed[tracked_batted_ball].mean() if tracked_batted_ball.any() else np.nan,
        "chase_pct": swings[out_zone].sum() / out_zone.sum() * 100 if out_zone.sum() else np.nan,
        "whiff_pct": whiffs.sum() / swings.sum() * 100 if swings.sum() else np.nan,
        "k_pct": pa_events.isin({"strikeout", "strikeout_double_play"}).sum() / pa_count * 100 if pa_count else np.nan,
        "bb_pct": pa_events.isin({"walk", "intent_walk"}).sum() / pa_count * 100 if pa_count else np.nan,
        "barrel_pct": launch_speed_angle[tracked_batted_ball].eq(6).mean() * 100 if tracked_batted_ball.any() else np.nan,
        "hard_hit_pct": launch_speed[tracked_batted_ball].ge(95).mean() * 100 if tracked_batted_ball.any() else np.nan,
        "gb_pct": bb_type[bb_type_mask].eq("ground_ball").mean() * 100 if bb_type_mask.any() else np.nan,
    }


def period_pa_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    if {"game_pk", "at_bat_number", "pitch_number"}.issubset(df.columns):
        working = df.copy()
        working["pitch_number"] = pd.to_numeric(working["pitch_number"], errors="coerce")
        return working.sort_values(["game_pk", "at_bat_number", "pitch_number"]).groupby(
            ["game_pk", "at_bat_number"], as_index=False
        ).tail(1)
    return df[df.get("events", pd.Series(index=df.index, dtype="object")).notna()].copy()


def format_period_stat(value: Any, kind: str) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return "-"
    if kind == "int":
        return f"{int(round(float(numeric))):,}"
    if kind == "pct":
        return f"{float(numeric):.1f}%"
    if kind == "avg":
        return f"{float(numeric):.3f}"
    if kind == "one":
        return f"{float(numeric):.1f}"
    return str(value)


def compute_standard_period_stats(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}

    working = normalize_pitch_names(df)
    pa_df = period_pa_rows(working)
    descriptions = working.get("description", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    events = pa_df.get("events", pd.Series(index=pa_df.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    swings = descriptions.isin(SWING_EVENTS)
    whiffs = descriptions.isin(WHIFF_EVENTS)
    called = descriptions.isin(CALLED_STRIKE_EVENTS)
    in_zone = red_strike_zone_mask(working)
    launch_speed = pd.to_numeric(working.get("launch_speed"), errors="coerce")
    bb_type = working.get("bb_type", pd.Series(index=working.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()
    bbe_mask = bb_type.isin({"ground_ball", "fly_ball", "line_drive", "popup"})
    ab_mask = events.ne("") & ~events.isin(NON_AB_EVENTS)
    ab_count = int(ab_mask.sum())
    hits = int(events.isin(HIT_EVENTS).sum())
    walks = int(events.isin(WALK_EVENTS).sum())
    strikeouts = int(events.isin(STRIKEOUT_EVENTS).sum())
    home_runs = int(events.eq("home_run").sum())
    total_bases = int(
        events.map({"single": 1, "double": 2, "triple": 3, "home_run": 4}).fillna(0).sum()
    )
    woba_values = pd.to_numeric(
        pa_df.get("woba_value", pd.Series(index=pa_df.index, dtype="float64")),
        errors="coerce",
    )
    pitches = int(len(working))
    pa_count = int(len(pa_df))
    games = int(working["game_pk"].nunique()) if "game_pk" in working.columns else 0

    return {
        "games": games,
        "pitches": pitches,
        "pa": pa_count,
        "ip": format_ip_from_outs(estimate_outs_recorded(working)),
        "hits": hits,
        "bb": walks,
        "k": strikeouts,
        "hr": home_runs,
        "k_pct": rate_pct(strikeouts, pa_count),
        "bb_pct": rate_pct(walks, pa_count),
        "whiff_pct": rate_pct(int(whiffs.sum()), int(swings.sum())),
        "csw_pct": rate_pct(int((called | whiffs).sum()), pitches),
        "zone_pct": rate_pct(int(in_zone.sum()), pitches),
        "avg": hits / ab_count if ab_count else np.nan,
        "slg": total_bases / ab_count if ab_count else np.nan,
        "woba": woba_values.mean() if woba_values.notna().any() else np.nan,
        "hard_hit_pct": rate_pct(int(launch_speed[bbe_mask].ge(95).sum()), int(bbe_mask.sum())),
        "gb_pct": rate_pct(int(bb_type[bbe_mask].eq("ground_ball").sum()), int(bbe_mask.sum())),
        "avg_ev": launch_speed[bbe_mask].mean() if bbe_mask.any() else np.nan,
        "avg_velo": pd.to_numeric(working.get("release_speed"), errors="coerce").mean(),
    }


STANDARD_PERIOD_ROWS: list[tuple[str, str, str]] = [
    ("games", "Games", "int"),
    ("pitches", "Pitches", "int"),
    ("pa", "Batters Faced", "int"),
    ("ip", "IP", "text"),
    ("hits", "H", "int"),
    ("bb", "BB", "int"),
    ("k", "K", "int"),
    ("hr", "HR", "int"),
    ("k_pct", "K%", "pct"),
    ("bb_pct", "BB%", "pct"),
    ("whiff_pct", "Whiff%", "pct"),
    ("csw_pct", "CSW%", "pct"),
    ("zone_pct", "Zone%", "pct"),
    ("avg", "AVG", "avg"),
    ("slg", "SLG", "avg"),
    ("woba", "wOBA", "avg"),
    ("hard_hit_pct", "Hard-Hit%", "pct"),
    ("gb_pct", "GB%", "pct"),
    ("avg_ev", "Avg EV", "one"),
    ("avg_velo", "Avg Velo", "one"),
]


def build_standard_period_comparison(left_df: pd.DataFrame, right_df: pd.DataFrame) -> TablePayload:
    left_stats = compute_standard_period_stats(left_df)
    right_stats = compute_standard_period_stats(right_df)
    rows: list[dict[str, Any]] = []
    for key, label, kind in STANDARD_PERIOD_ROWS:
        left_value = left_stats.get(key)
        right_value = right_stats.get(key)
        rows.append(
            {
                "metric": label,
                "period_a": left_value if kind == "text" else format_period_stat(left_value, kind),
                "period_b": right_value if kind == "text" else format_period_stat(right_value, kind),
                "period_a_raw": clean_value(left_value),
                "period_b_raw": clean_value(right_value),
            }
        )
    return TablePayload(
        columns=[
            {"key": "metric", "label": "Metric"},
            {"key": "period_a", "label": "Period A"},
            {"key": "period_b", "label": "Period B"},
        ],
        rows=rows,
    )


def period_team_label(pitches: pd.DataFrame) -> tuple[str | None, list[str]]:
    stints = build_pitcher_team_stints(pitches)
    teams = [str(stint["team"]) for stint in stints]
    if not teams:
        return None, []
    unique_teams = list(dict.fromkeys(teams))
    return (unique_teams[0] if len(unique_teams) == 1 else f"{len(unique_teams)} Tms"), unique_teams


def period_player_from_options(
    year: int,
    pitcher_id: int,
    period_label: str,
    start_date: str,
    end_date: str,
    pitches: pd.DataFrame | None = None,
) -> ComparisonPlayer | None:
    pool = load_comparison_pool(year)
    rows = pool[pool["player_id"] == int(pitcher_id)] if not pool.empty else pd.DataFrame()
    if rows.empty:
        return None
    player = player_from_row(rows.iloc[0])
    period_team, teams = period_team_label(pitches) if pitches is not None else (None, [])
    if period_team:
        player.team = period_team
    player.meta.update(
        {"year": year, "period": period_label, "start_date": start_date, "end_date": end_date, "teams": teams}
    )
    player.display_label = f"{player.display_name} ({player.team}, {player.role}) - {period_label}"
    return player


def build_period_location_points(df: pd.DataFrame) -> list[dict[str, Any]]:
    return build_pitch_location_scatter(normalize_pitch_names(df))


def build_period_movement_payload(df: pd.DataFrame, year: int) -> dict[str, Any]:
    if df.empty or not {"pitch_name", "pfx_x", "pfx_z"}.issubset(df.columns):
        return {"scatter": [], "summary": [], "league": [], "pitcher_hand": "Unknown"}

    working = normalize_pitch_names(df)
    pitcher_hand = infer_pitcher_hand(working)
    scatter = working.copy()
    scatter["h_break"] = pd.to_numeric(scatter["pfx_x"], errors="coerce") * -12
    scatter["v_break"] = pd.to_numeric(scatter["pfx_z"], errors="coerce") * 12
    if "release_speed" in scatter.columns:
        scatter["release_speed"] = pd.to_numeric(scatter["release_speed"], errors="coerce")
    if "arm_angle" in scatter.columns:
        scatter["arm_angle"] = pd.to_numeric(scatter["arm_angle"], errors="coerce")

    scatter_columns = ["pitch_name", "h_break", "v_break", "release_speed", "arm_angle", "pitch_stuff_plus"]
    available_scatter_columns = [column for column in scatter_columns if column in scatter.columns]
    scatter_df = scatter[available_scatter_columns].dropna(subset=["h_break", "v_break"]).copy()
    summary_df = build_pitch_movement_summary(working)
    league_df = build_league_movement_benchmarks(year)
    league_rows = build_movement_comparison_table(working, pitcher_hand, league_df)

    return {
        "scatter": dataframe_to_table_payload(scatter_df).rows,
        "summary": dataframe_to_table_payload(summary_df).rows,
        "league": dataframe_to_table_payload(league_rows).rows,
        "pitcher_hand": pitcher_hand,
    }


def build_period_pitch_mix_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty or "pitch_name" not in df.columns:
        return {"rows": [], "total": 0}

    working = normalize_pitch_names(df)
    counts = working["pitch_name"].dropna().astype(str).value_counts().rename_axis("pitch").reset_index(name="pitches")
    total = int(counts["pitches"].sum())
    counts["usage_pct"] = counts["pitches"] / total * 100 if total else 0
    return {
        "rows": dataframe_to_table_payload(counts).rows,
        "total": total,
    }


def build_period_discipline_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"panel_groups": {}, "total": 0}
    return {
        "panel_groups": build_discipline_panel_groups(normalize_pitch_names(df), build_period_location_points),
        "total": int(len(df)),
    }


def build_period_video_payload(df: pd.DataFrame, limit: int | None = None) -> dict[str, Any]:
    if df.empty:
        return {"rows": [], "total": 0}

    working = normalize_pitch_names(df)
    columns = [
        "game_date",
        "pitch_name",
        "description",
        "events",
        "balls",
        "strikes",
        "release_speed",
        "stand",
        "bb_type",
        "launch_speed",
        "launch_angle",
        "plate_x",
        "plate_z",
        "video_url",
        "play_id",
    ]
    available_columns = [column for column in columns if column in working.columns]
    if not available_columns:
        return {"rows": [], "total": 0}

    video_df = working[available_columns].copy()
    if "video_url" not in video_df.columns and "play_id" not in video_df.columns:
        return {"rows": [], "total": 0}

    if "video_url" not in video_df.columns:
        video_df["video_url"] = pd.NA
    if "play_id" in video_df.columns:
        play_id = video_df["play_id"].fillna("").astype(str).str.strip()
        existing_url = video_df["video_url"].fillna("").astype(str).str.strip()
        missing_url = existing_url.eq("") | existing_url.isin({"None", "nan", "NaN"})
        video_df.loc[missing_url & play_id.ne("") & ~play_id.isin({"None", "nan", "NaN"}), "video_url"] = (
            "https://baseballsavant.mlb.com/sporty-videos?playId=" + play_id
        )
    video_url = video_df["video_url"].fillna("").astype(str).str.strip()
    video_df = video_df[video_url.ne("") & ~video_url.isin({"None", "nan", "NaN"})].copy()

    if "game_date" in video_df.columns:
        video_df["game_date"] = pd.to_datetime(video_df["game_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    total = int(len(video_df))
    if limit is not None:
        video_df = video_df.head(max(0, limit))
    video_df = video_df.replace({np.nan: None})
    return {
        "rows": dataframe_to_table_payload(video_df).rows,
        "total": total,
    }


def get_period_comparison_overview(
    pitcher_id: int,
    left_year: int,
    right_year: int,
    left_start: str,
    left_end: str,
    right_start: str,
    right_end: str,
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
    include_pitch_stuff: bool = False,
) -> ComparisonOverviewResponse:
    warnings: list[str] = []
    left_source_df = load_pitcher_cached_season(
        left_year, pitcher_id, settings.data_dir, start_date=left_start, end_date=left_end
    )
    right_source_df = load_pitcher_cached_season(
        right_year, pitcher_id, settings.data_dir, start_date=right_start, end_date=right_end
    )
    left_df = left_source_df
    right_df = right_source_df
    left_df = apply_stuff_filters(
        left_df,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
    )
    right_df = apply_stuff_filters(
        right_df,
        stand=stand,
        count=count,
        pitch=pitch,
        pitch_result=pitch_result,
        in_play_result=in_play_result,
        pa_result=pa_result,
    )
    if left_df.empty:
        warnings.append(f"No period pitches found for {pitcher_id} from {left_start} to {left_end}.")
    if right_df.empty:
        warnings.append(f"No period pitches found for {pitcher_id} from {right_start} to {right_end}.")

    left_metrics = build_metric_card_from_values(compute_period_metrics(left_df), left_year, PERIOD_METRIC_SPECS)
    right_metrics = build_metric_card_from_values(compute_period_metrics(right_df), right_year, PERIOD_METRIC_SPECS)
    metric_table = build_metric_comparison_table(left_metrics, right_metrics)
    standard_table = build_standard_period_comparison(left_df, right_df)
    left_player = period_player_from_options(
        left_year, pitcher_id, "Period A", left_start, left_end, pitches=left_source_df
    )
    right_player = period_player_from_options(
        right_year, pitcher_id, "Period B", right_start, right_end, pitches=right_source_df
    )
    left_movement_df = left_df
    right_movement_df = right_df
    if include_pitch_stuff:
        reference_by_year: dict[int, pd.DataFrame] = {}
        for year in {left_year, right_year}:
            reference_by_year[year] = load_pitcher_cached_season(year, pitcher_id, settings.data_dir)
        left_movement_df = add_pitch_stuff_scores(left_df, reference_by_year[left_year])
        right_movement_df = add_pitch_stuff_scores(right_df, reference_by_year[right_year])
    left_movement = build_period_movement_payload(left_movement_df, left_year)
    right_movement = build_period_movement_payload(right_movement_df, right_year)
    left_pitch_mix = build_period_pitch_mix_payload(left_df)
    right_pitch_mix = build_period_pitch_mix_payload(right_df)
    left_discipline = build_period_discipline_payload(left_df)
    right_discipline = build_period_discipline_payload(right_df)
    left_videos = build_period_video_payload(left_df)
    right_videos = build_period_video_payload(right_df)

    return ComparisonOverviewResponse(
        meta=ResponseMeta(year=right_year, warnings=warnings),
        players={"left": left_player, "right": right_player or left_player},
        percentile_cards={"left": left_metrics, "right": right_metrics},
        charts={
            "advantages": build_advantages(metric_table),
            "period_counts": {"left": int(len(left_df)), "right": int(len(right_df))},
            "period_locations": {
                "left": build_period_location_points(left_df),
                "right": build_period_location_points(right_df),
            },
            "period_movement": {
                "left": left_movement,
                "right": right_movement,
            },
            "period_pitch_mix": {
                "left": left_pitch_mix,
                "right": right_pitch_mix,
            },
            "period_discipline": {
                "left": left_discipline,
                "right": right_discipline,
            },
            "period_videos": {
                "left": left_videos,
                "right": right_videos,
            },
        },
        tables={"metric_comparison": metric_table, "standard_comparison": standard_table},
        notes=[
            "Period comparison uses the legacy 25 metric definitions for the first migration slice.",
            "Each period's percentile is evaluated against that period side's selected season comparison pool.",
        ],
    )
