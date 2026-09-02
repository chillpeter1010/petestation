from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta, TablePayload
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.discipline_service import add_discipline_flags, build_discipline_panel_groups
from app.services.pitch_location_score_service import load_pitch_location_scores
from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores

ZONE_X = (-0.83, 0.83)
ZONE_Z = (1.5, 3.5)
SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "foul_bunt",
    "missed_bunt",
}
WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"}
STRIKE_DESCRIPTIONS = {
    "called_strike",
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "foul_bunt",
    "missed_bunt",
}
_BATTER_LEADERBOARD_CACHE: dict[tuple[int, str], tuple[int, pd.DataFrame]] = {}


def list_batter_options(year: int, team: str = "All") -> list[dict[str, Any]]:
    rows = list_batter_leaderboard(year, team)
    options = [
        {
            "value": row["player_id"],
            "label": f"{row['name']} ({row['team']})",
            "name": row["name"],
            "team": row["team"],
            "games": row.get("games") or 0,
            "plate_appearances": row.get("plate_appearances") or 0,
        }
        for row in rows
        if row.get("player_id")
    ]
    return sorted(options, key=lambda item: item["label"])


def list_batter_leaderboard(year: int, team: str = "All") -> list[dict[str, Any]]:
    stats = _load_batter_duckdb_leaderboard(year)
    if not stats.empty:
        if team and team != "All":
            stats = stats[stats["team"] == team]
        stats = stats.sort_values(["plate_appearances", "pitches", "name"], ascending=[False, False, True])
        return [_row_to_payload(row) for row in stats.to_dict("records")]

    stats = _load_batter_csv(year)
    supplement = _load_batter_pitch_supplement(year)
    if stats.empty and supplement.empty:
        return []
    if stats.empty:
        stats = _batter_rows_from_supplement(supplement, year)

    if not supplement.empty:
        stats = stats.merge(supplement, on="player_id", how="left", suffixes=("", "_pitch"))
        stats["team"] = stats["team_pitch"].fillna(stats["team"])
        stats["games"] = stats["games_pitch"].fillna(stats["games"])
        stats["pitches"] = stats["pitches_pitch"].fillna(stats["pitches"])
        stats["max_ev"] = stats["max_ev_pitch"].fillna(stats["max_ev"])
        stats = stats.drop(columns=[column for column in stats.columns if column.endswith("_pitch")])

    stats["team"] = stats["team"].fillna("-").astype(str).replace({"": "-"})
    if team and team != "All":
        stats = stats[stats["team"] == team]

    stats = stats.sort_values(["plate_appearances", "pitches", "name"], ascending=[False, False, True])
    return [_row_to_payload(row) for row in stats.to_dict("records")]


def get_batter_personal_overview(year: int, batter_id: int) -> AnalysisResponse:
    leaderboard = list_batter_leaderboard(year)
    selected = next((row for row in leaderboard if row.get("player_id") == batter_id), None)
    pitch_rows = _load_batter_pitch_rows(year, batter_id)

    summary = [
        _metric("games", "Games", selected.get("games") if selected else pitch_rows["game_pk"].nunique() if not pitch_rows.empty else 0),
        _metric("pa", "PA", selected.get("plate_appearances") if selected else _count_plate_appearances(pitch_rows)),
        _metric("hits", "H", selected.get("hits") if selected else int(pitch_rows["is_hit"].sum()) if not pitch_rows.empty else 0),
        _metric("hr", "HR", selected.get("home_runs") if selected else int((pitch_rows["events"] == "home_run").sum()) if not pitch_rows.empty else 0),
        _metric("avg", "AVG", selected.get("avg") if selected else _batting_average(pitch_rows)),
        _metric("ops", "OPS", selected.get("ops") if selected else None),
    ]

    tables = {
        "dashboard": _table(
            [
                "Season",
                "Name",
                "Team",
                "G",
                "PA",
                "AB",
                "H",
                "HR",
                "AVG",
                "OBP",
                "SLG",
                "OPS",
                "wOBA",
                "xBA",
                "xSLG",
                "xwOBA",
                "Avg EV",
                "Max EV",
                "HH%",
                "Barrel%",
                "Whiff%",
                "K%",
                "BB%",
            ],
            [_batter_dashboard_row(year, selected, pitch_rows)],
        ),
        "season_game_log": _build_batter_game_log(pitch_rows),
        "pitch_mix": _build_batter_pitch_mix(pitch_rows),
    }

    return AnalysisResponse(
        meta=ResponseMeta(year=year, data_updated_at=_max_pitch_date(pitch_rows), warnings=[]),
        summary=summary,
        charts={
            "selected_batter": _selected_batter_payload(year, batter_id, selected),
            "filters": _batter_filter_options(pitch_rows),
            "percentile_profile": _build_batter_percentile_profile(year, batter_id),
        },
        tables=tables,
    )


def get_batter_personal_discipline(
    year: int,
    batter_id: int,
    stand: str = "All",
    count: str = "All",
    pitch: str = "All",
    pitch_result: str = "All",
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    pitch_rows = _load_batter_pitch_rows(year, batter_id)
    filtered = _apply_batter_filters(pitch_rows, stand, count, pitch, pitch_result, start_date, end_date)
    at_bats = int(filtered["is_ab"].sum()) if not filtered.empty else 0
    hits = int(filtered["is_hit"].sum()) if not filtered.empty else 0

    summary = [
        _metric("pitches", "Pitches", len(filtered)),
        _metric("zone_pct", "Zone%", _rate(filtered["is_zone"].sum(), len(filtered)) if not filtered.empty else None, "%"),
        _metric("swing_pct", "Swing%", _rate(filtered["is_swing"].sum(), len(filtered)) if not filtered.empty else None, "%"),
        _metric("str_pct", "Str%", _rate(filtered["is_strike"].sum(), len(filtered)) if not filtered.empty else None, "%"),
        _metric("whiff_pct", "Whiff%", _rate(filtered["is_whiff"].sum(), filtered["is_swing"].sum()) if not filtered.empty else None, "%"),
        _metric("avg", "AVG", hits / at_bats if at_bats else None),
    ]

    panel_groups = build_discipline_panel_groups(filtered, _batter_location_point_rows)

    return AnalysisResponse(
        meta=ResponseMeta(year=year, data_updated_at=_max_pitch_date(pitch_rows), warnings=[]),
        summary=summary,
        charts={
            "filters": _batter_filter_options(pitch_rows),
            "panel_groups": panel_groups,
        },
        tables={
            "location_points": _build_batter_location_points(filtered),
            "discipline_summary": _build_batter_discipline_summary(filtered),
            "stand_split": _build_batter_split(filtered, "stand", "Stand"),
            "count_split": _build_batter_split(filtered, "count", "Count"),
            "pitcher_hand_split": _build_batter_split(filtered, "p_throws", "Pitcher Hand"),
            "pitch_mix": _build_batter_pitch_mix(filtered),
            "pitch_results": _build_batter_pitch_results(filtered),
            "batted_ball": _build_batter_batted_ball(filtered),
            "pitchers_faced": _build_pitchers_faced(filtered),
        },
    )


def _load_batter_pitch_rows(year: int, batter_id: int) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return _empty_pitch_rows()

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return _empty_pitch_rows()

        raw = conn.execute(
            f"""
            SELECT *
            FROM {source_table}
            WHERE game_type = 'R'
              AND batter = ?
            """,
            [batter_id],
        ).fetchdf()

    return _normalize_batter_pitch_rows(raw)


def _normalize_batter_pitch_rows(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return _empty_pitch_rows()

    frame = raw.copy()
    for column in _pitch_row_columns():
        if column not in frame.columns:
            frame[column] = None

    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["game_pk", "at_bat_number", "pitch_number", "pitcher", "batter", "balls", "strikes"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in [
        "plate_x",
        "plate_z",
        "release_speed",
        "launch_speed",
        "launch_angle",
        "bat_speed",
        "delta_home_win_exp",
        "woba_value",
        "woba_denom",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    cached_stuff = load_pitch_stuff_scores(frame)
    cached_location = load_pitch_location_scores(frame)
    frame["pitch_stuff_plus"] = pd.to_numeric(frame["pitch_stuff_plus"], errors="coerce").fillna(cached_stuff).round(1)
    frame["location_plus_pitch"] = pd.to_numeric(frame["location_plus_pitch"], errors="coerce").fillna(cached_location).round(1)
    missing_video = frame["video_url"].fillna("").astype(str).str.strip().isin(["", "None", "nan", "NaN"])
    valid_play = ~frame["play_id"].fillna("").astype(str).str.strip().isin(["", "None", "nan", "NaN"])
    frame.loc[missing_video & valid_play, "video_url"] = (
        "https://baseballsavant.mlb.com/sporty-videos?playId="
        + frame.loc[missing_video & valid_play, "play_id"].astype(str)
    )

    frame["description"] = frame["description"].fillna("").astype(str).str.strip().str.lower()
    frame["events"] = frame["events"].fillna("").astype(str).str.strip().str.lower()
    frame["pitch_type"] = frame["pitch_type"].fillna("UNK").astype(str).replace({"": "UNK"})
    frame["pitch_name"] = frame["pitch_name"].fillna(frame["pitch_type"]).astype(str).replace({"": "Unknown"})
    frame["stand"] = frame["stand"].fillna("-").astype(str).replace({"": "-"})
    frame["p_throws"] = frame["p_throws"].fillna("-").astype(str).replace({"": "-"})
    frame["bb_type"] = frame["bb_type"].fillna("").astype(str).str.strip().str.lower()
    frame["count"] = frame.apply(lambda row: f"{int(row['balls'])}-{int(row['strikes'])}" if pd.notna(row["balls"]) and pd.notna(row["strikes"]) else "-", axis=1)

    pitcher_name = frame["player_name"] if "player_name" in frame.columns else pd.Series([None] * len(frame), index=frame.index)
    frame["pitcher_display"] = pitcher_name.fillna(frame["pitcher"]).astype(str).replace({"": "Unknown Pitcher"})

    frame["is_zone"] = frame["plate_x"].between(ZONE_X[0], ZONE_X[1]) & frame["plate_z"].between(ZONE_Z[0], ZONE_Z[1])
    frame["is_swing"] = frame["description"].isin(SWING_DESCRIPTIONS)
    frame["is_whiff"] = frame["description"].isin(WHIFF_DESCRIPTIONS)
    frame["is_strike"] = frame["description"].isin(STRIKE_DESCRIPTIONS) | (frame["type"].fillna("").astype(str).str.upper() == "S")
    frame["is_in_play"] = frame["description"].eq("hit_into_play")
    frame["is_hard_hit"] = frame["launch_speed"].ge(95)
    frame["is_hit"] = frame["events"].isin({"single", "double", "triple", "home_run"})
    frame["is_walk"] = frame["events"].isin({"walk", "intent_walk"})
    frame["is_strikeout"] = frame["events"].isin({"strikeout", "strikeout_double_play"})
    frame["is_ab"] = frame["events"].ne("") & ~frame["events"].isin(
        {
            "walk",
            "intent_walk",
            "hit_by_pitch",
            "sac_bunt",
            "sac_fly",
            "sac_fly_double_play",
            "catcher_interf",
            "truncated_pa",
        }
    )
    return frame[_pitch_row_columns()].reset_index(drop=True)


def _empty_pitch_rows() -> pd.DataFrame:
    frame = pd.DataFrame(columns=_pitch_row_columns())
    for column in ["is_zone", "is_swing", "is_whiff", "is_strike", "is_in_play", "is_hard_hit", "is_hit", "is_walk", "is_strikeout", "is_ab"]:
        frame[column] = pd.Series(dtype=bool)
    return frame


def _pitch_row_columns() -> list[str]:
    return [
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "pitcher",
        "pitcher_display",
        "batter",
        "offense_team",
        "home_team",
        "away_team",
        "stand",
        "p_throws",
        "balls",
        "strikes",
        "count",
        "pitch_type",
        "pitch_name",
        "description",
        "events",
        "type",
        "plate_x",
        "plate_z",
        "release_speed",
        "launch_speed",
        "launch_angle",
        "bat_speed",
        "delta_home_win_exp",
        "woba_value",
        "woba_denom",
        "bb_type",
        "play_id",
        "video_url",
        "pitch_stuff_plus",
        "location_plus_pitch",
        "is_zone",
        "is_swing",
        "is_whiff",
        "is_strike",
        "is_in_play",
        "is_hard_hit",
        "is_hit",
        "is_walk",
        "is_strikeout",
        "is_ab",
    ]


def _apply_batter_filters(
    rows: pd.DataFrame,
    stand: str,
    count: str,
    pitch: str,
    pitch_result: str,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    if rows.empty:
        return rows
    filtered = rows.copy()
    stand_values = _filter_values(stand)
    count_values = _filter_values(count)
    pitch_values = _filter_values(pitch)
    result_values = _filter_values(pitch_result)
    if stand_values:
        filtered = filtered[filtered["stand"].isin(stand_values)]
    if count_values:
        filtered = filtered[filtered["count"].isin(count_values)]
    if pitch_values:
        filtered = filtered[filtered["pitch_name"].isin(pitch_values) | filtered["pitch_type"].isin(pitch_values)]
    if result_values:
        result_mask = pd.Series(False, index=filtered.index)
        for result_value in result_values:
            if result_value == "Swing":
                result_mask |= filtered["is_swing"]
            elif result_value == "Whiff":
                result_mask |= filtered["is_whiff"]
            elif result_value == "In Play":
                result_mask |= filtered["is_in_play"]
            else:
                result_mask |= filtered["description"].eq(result_value.lower().replace(" ", "_"))
        filtered = filtered[result_mask]
    if start_date:
        filtered = filtered[filtered["game_date"] >= start_date]
    if end_date:
        filtered = filtered[filtered["game_date"] <= end_date]
    return filtered


def _filter_values(value: str | None) -> list[str]:
    if not value or value == "All":
        return []
    return [item.strip() for item in str(value).split(",") if item.strip() and item.strip() != "All"]


def _batter_filter_options(rows: pd.DataFrame) -> dict[str, list[str]]:
    if rows.empty:
        return {"stand": ["All"], "count": ["All"], "pitch": ["All"], "pitch_result": ["All"]}
    descriptions = _display_options(rows["description"])
    pitch_results = ["All", "Swing", "In Play", *descriptions]
    return {
        "stand": ["All", *_display_options(rows["stand"])],
        "count": ["All", *_count_options(rows["count"])],
        "pitch": ["All", *_display_options(rows["pitch_name"])],
        "pitch_result": pitch_results,
    }


def _display_options(series: pd.Series) -> list[str]:
    values = [str(value).strip() for value in series.dropna().unique().tolist() if str(value).strip() and str(value).strip() != "-"]
    return sorted(values)


def _count_options(series: pd.Series) -> list[str]:
    order = ["0-0", "0-1", "1-0", "0-2", "1-1", "2-0", "1-2", "2-1", "3-0", "2-2", "3-1", "3-2"]
    present = set(_display_options(series))
    return [value for value in order if value in present]


def _batter_dashboard_row(year: int, selected: dict[str, Any] | None, rows: pd.DataFrame) -> dict[str, Any]:
    selected = selected or {}
    row_team = _mode_string(rows["offense_team"]) if not rows.empty else "-"
    games = selected.get("games")
    plate_appearances = selected.get("plate_appearances")
    at_bats = selected.get("at_bats")
    hits = selected.get("hits")
    home_runs = selected.get("home_runs")
    max_ev = selected.get("max_ev")
    if max_ev is None and not rows.empty:
        max_ev = rows["launch_speed"].max()
    return {
        "Season": year,
        "Name": selected.get("name") or "Unknown Batter",
        "Team": selected.get("team") or row_team,
        "G": games if games is not None else (rows["game_pk"].nunique() if not rows.empty else 0),
        "PA": plate_appearances if plate_appearances is not None else _count_plate_appearances(rows),
        "AB": at_bats if at_bats is not None else (int(rows["is_ab"].sum()) if not rows.empty else None),
        "H": hits if hits is not None else (int(rows["is_hit"].sum()) if not rows.empty else None),
        "HR": home_runs if home_runs is not None else (int((rows["events"] == "home_run").sum()) if not rows.empty else None),
        "AVG": _format_rate(selected.get("avg") if selected.get("avg") is not None else _batting_average(rows)),
        "OBP": _format_rate(selected.get("obp")),
        "SLG": _format_rate(selected.get("slg")),
        "OPS": _format_rate(selected.get("ops")),
        "wOBA": _format_rate(selected.get("woba")),
        "xBA": _format_rate(selected.get("xba")),
        "xSLG": _format_rate(selected.get("xslg")),
        "xwOBA": _format_rate(selected.get("xwoba")),
        "Avg EV": _round(selected.get("avg_ev"), 1),
        "Max EV": _round(max_ev, 1),
        "HH%": _format_percent(selected.get("hard_hit_rate")),
        "Barrel%": _format_percent(selected.get("barrel_rate")),
        "Whiff%": _format_percent(selected.get("whiff_rate")),
        "K%": _format_percent(selected.get("strikeout_rate")),
        "BB%": _format_percent(selected.get("walk_rate")),
    }


def _selected_batter_payload(year: int, batter_id: int, selected: dict[str, Any] | None) -> dict[str, Any]:
    selected = selected or {}
    return {
        "year": year,
        "batter_id": batter_id,
        "name": selected.get("name") or f"Batter {batter_id}",
        "team": selected.get("team") or "-",
    }


def _build_batter_percentile_profile(year: int, batter_id: int) -> list[dict[str, Any]]:
    leaderboard = list_batter_leaderboard(year)
    selected = next((row for row in leaderboard if row.get("player_id") == batter_id), None)
    if not selected:
        return []

    qualified = [row for row in leaderboard if (_nullable_int(row.get("plate_appearances")) or 0) >= 50]
    specs = [
        ("batting_run_value", "Batting Run Value", "runs", True),
        ("xwoba", "xwOBA", "rate", True),
        ("xba", "xBA", "rate", True),
        ("xslg", "xSLG", "rate", True),
        ("avg_ev", "Avg Exit Velo", "mph", True),
        ("barrel_rate", "Barrel%", "percent", True),
        ("hard_hit_rate", "Hard-Hit%", "percent", True),
        ("sweet_spot_rate", "LA Sweet-Spot%", "percent", True),
        ("avg_bat_speed", "Bat Speed", "mph", True),
        ("chase_rate", "Chase%", "percent", False),
        ("whiff_rate", "Whiff%", "percent", False),
        ("strikeout_rate", "K%", "percent", False),
        ("walk_rate", "BB%", "percent", True),
    ]
    profile: list[dict[str, Any]] = []
    for key, label, unit, higher_is_better in specs:
        value = _nullable_float(selected.get(key))
        population = [
            numeric
            for row in qualified
            if (numeric := _nullable_float(row.get(key))) is not None
        ]
        percentile = None
        if value is not None and population:
            favorable = sum(candidate <= value for candidate in population) if higher_is_better else sum(candidate >= value for candidate in population)
            percentile = round(max(1.0, min(100.0, favorable / len(population) * 100)), 0)
        profile.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "unit": unit,
                "percentile": percentile,
                "sample": len(population),
            }
        )
    return profile


def _build_batter_game_log(rows: pd.DataFrame) -> TablePayload:
    columns = ["Date", "Opponent", "Pitches", "PA", "AB", "H", "HR", "BB", "SO", "AVG", "wOBA", "Game WPA", "Max EV", "HH"]
    if rows.empty:
        return _table(columns, [])
    grouped = []
    for (_, game_pk), group in rows.groupby(["game_date", "game_pk"], dropna=False):
        at_bats = int(group["is_ab"].sum())
        hits = int(group["is_hit"].sum())
        offense_team = _mode_string(group["offense_team"])
        home_team = _mode_string(group["home_team"])
        away_team = _mode_string(group["away_team"])
        opponent = away_team if offense_team == home_team else home_team
        home_wpa = pd.to_numeric(group["delta_home_win_exp"], errors="coerce")
        game_wpa = home_wpa.sum(min_count=1)
        if offense_team != home_team:
            game_wpa = -game_wpa
        woba_denom = pd.to_numeric(group["woba_denom"], errors="coerce").sum(min_count=1)
        woba_value = pd.to_numeric(group["woba_value"], errors="coerce").sum(min_count=1)
        grouped.append(
            {
                "Date": group["game_date"].iloc[0],
                "Opponent": opponent if opponent != "-" else "-",
                "Pitches": len(group),
                "PA": _count_plate_appearances(group),
                "AB": at_bats,
                "H": hits,
                "HR": int((group["events"] == "home_run").sum()),
                "BB": int(group["is_walk"].sum()),
                "SO": int(group["is_strikeout"].sum()),
                "AVG": _format_rate(hits / at_bats if at_bats else None),
                "wOBA": _round(woba_value / woba_denom, 3) if pd.notna(woba_denom) and woba_denom > 0 else None,
                "Game WPA": _round(game_wpa, 3) if pd.notna(game_wpa) else None,
                "Max EV": _round(group["launch_speed"].max(), 1),
                "HH": int(group["is_hard_hit"].sum()),
            }
        )
    return _table(columns, sorted(grouped, key=lambda row: str(row["Date"]), reverse=True))


def _build_batter_pitch_mix(rows: pd.DataFrame) -> TablePayload:
    columns = ["Pitch", "Pitches", "Usage%", "AVG", "Whiff%", "HH%"]
    if rows.empty:
        return _table(columns, [])
    grouped = []
    total = len(rows)
    for pitch_name, group in rows.groupby("pitch_name", dropna=False):
        at_bats = int(group["is_ab"].sum())
        hits = int(group["is_hit"].sum())
        grouped.append(
            {
                "Pitch": str(pitch_name),
                "Pitches": len(group),
                "Usage%": _round(_rate(len(group), total), 1),
                "AVG": _format_rate(hits / at_bats if at_bats else None),
                "Whiff%": _round(_rate(group["is_whiff"].sum(), group["is_swing"].sum()), 1),
                "HH%": _round(_rate(group["is_hard_hit"].sum(), group["is_in_play"].sum()), 1),
            }
        )
    return _table(columns, sorted(grouped, key=lambda row: row["Pitches"], reverse=True))


def _build_batter_pitch_results(rows: pd.DataFrame) -> TablePayload:
    columns = ["Pitch Result", "Pitches", "Pct"]
    if rows.empty:
        return _table(columns, [])
    counts = rows["description"].replace({"": "unknown"}).value_counts()
    total = len(rows)
    return _table(columns, [{"Pitch Result": key, "Pitches": int(value), "Pct": _round(_rate(value, total), 1)} for key, value in counts.items()])


def _build_batter_batted_ball(rows: pd.DataFrame) -> TablePayload:
    columns = ["Batted Ball", "Pitches", "Pct", "AVG EV"]
    if rows.empty:
        return _table(columns, [])
    batted = rows[rows["bb_type"].ne("")]
    total = len(batted)
    if total == 0:
        return _table(columns, [])
    payload = []
    for bb_type, group in batted.groupby("bb_type"):
        payload.append({"Batted Ball": bb_type, "Pitches": len(group), "Pct": _round(_rate(len(group), total), 1), "AVG EV": _round(group["launch_speed"].mean(), 1)})
    return _table(columns, sorted(payload, key=lambda row: row["Pitches"], reverse=True))


def _build_pitchers_faced(rows: pd.DataFrame) -> TablePayload:
    columns = ["Pitcher", "Pitches", "PA", "AVG", "Whiff%"]
    if rows.empty:
        return _table(columns, [])
    payload = []
    for pitcher, group in rows.groupby("pitcher_display", dropna=False):
        at_bats = int(group["is_ab"].sum())
        hits = int(group["is_hit"].sum())
        payload.append(
            {
                "Pitcher": str(pitcher),
                "Pitches": len(group),
                "PA": _count_plate_appearances(group),
                "AVG": _format_rate(hits / at_bats if at_bats else None),
                "Whiff%": _round(_rate(group["is_whiff"].sum(), group["is_swing"].sum()), 1),
            }
        )
    return _table(columns, sorted(payload, key=lambda row: row["Pitches"], reverse=True))


def _batter_location_point_rows(rows: pd.DataFrame) -> list[dict[str, Any]]:
    return _build_batter_location_points(rows).rows


def _build_batter_location_points(rows: pd.DataFrame) -> TablePayload:
    columns = [
        "game_date",
        "plate_x",
        "plate_z",
        "pitch_name",
        "pitch_type",
        "description",
        "events",
        "count",
        "release_speed",
        "launch_speed",
        "bat_speed",
        "is_swing",
        "play_id",
        "video_url",
        "pitch_stuff_plus",
        "location_plus_pitch",
        "selected_key",
    ]
    if rows.empty:
        return _table(columns, [])
    points = rows.dropna(subset=["plate_x", "plate_z"]).copy()
    points["selected_key"] = points.apply(lambda row: f"{row.get('game_pk')}-{row.get('at_bat_number')}-{row.get('pitch_number')}", axis=1)
    payload_frame = points[columns].astype(object).where(pd.notna(points[columns]), None)
    payload = payload_frame.to_dict("records")
    return _table(columns, payload)


def _build_batter_discipline_summary(rows: pd.DataFrame) -> TablePayload:
    columns = ["Segment", "Pitches", "Str%", "Zone%", "Swing%", "O-Swing%", "Whiff%", "Contact%", "CSW%", "AVG", "HH%"]
    if rows.empty:
        return _table(columns, [])

    payload = [_batter_discipline_row("Overall", rows)]
    for pitch_name, group in rows.groupby("pitch_name", dropna=False):
        payload.append(_batter_discipline_row(str(pitch_name), group))
    return _table(columns, sorted(payload, key=lambda row: row["Pitches"], reverse=True))


def _build_batter_split(rows: pd.DataFrame, column: str, label: str) -> TablePayload:
    columns = [label, "Pitches", "PA", "AVG", "Str%", "Zone%", "Swing%", "O-Swing%", "Whiff%", "HH%"]
    if rows.empty or column not in rows:
        return _table(columns, [])

    clean = rows[rows[column].fillna("-").astype(str).ne("-")]
    if clean.empty:
        return _table(columns, [])

    payload = []
    for value, group in clean.groupby(column, dropna=False):
        row = _batter_discipline_row(str(value), group)
        payload.append(
            {
                label: row["Segment"],
                "Pitches": row["Pitches"],
                "PA": _count_plate_appearances(group),
                "AVG": row["AVG"],
                "Str%": row["Str%"],
                "Zone%": row["Zone%"],
                "Swing%": row["Swing%"],
                "O-Swing%": row["O-Swing%"],
                "Whiff%": row["Whiff%"],
                "HH%": row["HH%"],
            }
        )
    return _table(columns, sorted(payload, key=lambda row: row["Pitches"], reverse=True))


def _batter_discipline_row(segment: str, rows: pd.DataFrame) -> dict[str, Any]:
    working = add_discipline_flags(rows)
    pitches = len(working)
    swings = int(working["_is_swing"].sum()) if not working.empty else 0
    whiffs = int(working["_is_whiff"].sum()) if not working.empty else 0
    called_strikes = int(working["_is_called_strike"].sum()) if not working.empty else 0
    in_zone = int(working["_in_zone"].sum()) if not working.empty else 0
    out_zone = int(working["_out_zone"].sum()) if not working.empty else 0
    o_swings = int((working["_is_swing"] & working["_out_zone"]).sum()) if not working.empty else 0
    in_play = int(working["is_in_play"].sum()) if "is_in_play" in working else 0
    hard_hit = int(working["is_hard_hit"].sum()) if "is_hard_hit" in working else 0
    at_bats = int(working["is_ab"].sum()) if "is_ab" in working else 0
    hits = int(working["is_hit"].sum()) if "is_hit" in working else 0
    return {
        "Segment": segment,
        "Pitches": pitches,
        "Str%": _round(_rate(int(working["_is_strike"].sum()), pitches), 1),
        "Zone%": _round(_rate(in_zone, pitches), 1),
        "Swing%": _round(_rate(swings, pitches), 1),
        "O-Swing%": _round(_rate(o_swings, out_zone), 1),
        "Whiff%": _round(_rate(whiffs, swings), 1),
        "Contact%": _round(_rate(swings - whiffs, swings), 1),
        "CSW%": _round(_rate(called_strikes + whiffs, pitches), 1),
        "AVG": _format_rate(hits / at_bats if at_bats else None),
        "HH%": _round(_rate(hard_hit, in_play), 1),
    }


def _table(columns: list[str], rows: list[dict[str, Any]]) -> TablePayload:
    return TablePayload(columns=[{"key": column, "label": column} for column in columns], rows=rows)


def _metric(key: str, label: str, value: object, unit: str | None = None) -> MetricItem:
    return MetricItem(key=key, label=label, value=_metric_value(value), unit=unit)


def _metric_value(value: object) -> int | float | str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _rate(numerator: object, denominator: object) -> float | None:
    top = _nullable_float(numerator)
    bottom = _nullable_float(denominator)
    if top is None or bottom in (None, 0):
        return None
    return top / bottom * 100


def _round(value: object, digits: int) -> float | None:
    number = _nullable_float(value)
    if number is None:
        return None
    return round(number, digits)


def _format_rate(value: object) -> str:
    number = _nullable_float(value)
    return "-" if number is None else f"{number:.3f}"


def _format_percent(value: object) -> str:
    number = _nullable_float(value)
    return "-" if number is None else f"{number * 100:.1f}%"


def _count_plate_appearances(rows: pd.DataFrame) -> int:
    if rows.empty:
        return 0
    events = rows["events"].fillna("").astype(str)
    finished = rows[events.ne("") & events.ne("truncated_pa")]
    if "game_pk" in finished and "at_bat_number" in finished:
        return int(finished[["game_pk", "at_bat_number"]].drop_duplicates().shape[0])
    return int(len(finished))


def _batting_average(rows: pd.DataFrame) -> float | None:
    if rows.empty:
        return None
    at_bats = int(rows["is_ab"].sum())
    if at_bats == 0:
        return None
    return int(rows["is_hit"].sum()) / at_bats


def _mode_string(series: pd.Series) -> str:
    clean = series.dropna().astype(str)
    if clean.empty:
        return "-"
    return str(clean.mode().iloc[0])


def _max_pitch_date(rows: pd.DataFrame):
    if rows.empty or "game_date" not in rows:
        return None
    value = pd.to_datetime(rows["game_date"], errors="coerce").max()
    if pd.isna(value):
        return None
    return value.to_pydatetime()


def _load_batter_duckdb_leaderboard(year: int) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return _empty_batter_frame()
    cache_key = (int(year), str(db_path.resolve()))
    modified_at = db_path.stat().st_mtime_ns
    cached = _BATTER_LEADERBOARD_CACHE.get(cache_key)
    if cached and cached[0] == modified_at:
        return cached[1].copy()

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return _empty_batter_frame()

        available = {row[1] for row in conn.execute(f"PRAGMA table_info('{source_table}')").fetchall()}
        required = {"batter", "game_pk", "game_date", "game_type", "events", "description", "at_bat_number", "pitch_number"}
        if not required.issubset(available):
            return _empty_batter_frame()

        def source(column: str, fallback: str = "NULL") -> str:
            return f"p.{column}" if column in available else fallback

        if "offense_team" in available:
            team_expr = "p.offense_team"
        elif {"inning_topbot", "home_team", "away_team"}.issubset(available):
            team_expr = "CASE WHEN p.inning_topbot = 'Top' THEN p.away_team ELSE p.home_team END"
        else:
            team_expr = "NULL"

        player_join = ""
        master_name_expr = "NULL"
        official_name_expr = "NULL"
        name_expr = "'Batter ' || CAST(stats.player_id AS VARCHAR)"
        if "player_master" in tables:
            player_columns = {row[1] for row in conn.execute("PRAGMA table_info('player_master')").fetchall()}
            if {"player_id", "player_name"}.issubset(player_columns):
                player_join = "LEFT JOIN player_master player ON try_cast(player.player_id AS BIGINT) = stats.player_id"
                master_name_expr = (
                    "CASE WHEN lower(trim(CAST(player.player_name AS VARCHAR))) "
                    "IN ('', 'unknown', 'unknown batter') THEN NULL "
                    "ELSE trim(CAST(player.player_name AS VARCHAR)) END"
                )
        if "game_player_lookup" in tables:
            player_join += """
                LEFT JOIN (
                    SELECT player_id, arg_max(player_name, game_pk) AS player_name
                    FROM game_player_lookup
                    WHERE lower(trim(CAST(role AS VARCHAR))) = 'batter'
                      AND lower(trim(CAST(player_name AS VARCHAR))) NOT IN ('', 'unknown', 'unknown batter')
                    GROUP BY player_id
                ) official_batter ON try_cast(official_batter.player_id AS BIGINT) = stats.player_id
            """
            official_name_expr = "nullif(trim(CAST(official_batter.player_name AS VARCHAR)), '')"
        name_expr = (
            f"coalesce({master_name_expr}, {official_name_expr}, "
            "'Batter ' || CAST(stats.player_id AS VARCHAR))"
        )

        ab_events = "'walk', 'intent_walk', 'hit_by_pitch', 'sac_bunt', 'sac_fly', 'sac_fly_double_play', 'catcher_interf'"
        rows = conn.execute(
            f"""
            WITH regular AS (
                SELECT
                    try_cast(p.batter AS BIGINT) AS player_id,
                    p.game_pk,
                    p.at_bat_number,
                    p.pitch_number,
                    CAST(p.game_date AS DATE) AS game_date,
                    nullif(trim(CAST({team_expr} AS VARCHAR)), '') AS team,
                    lower(coalesce(CAST(p.events AS VARCHAR), '')) AS events,
                    lower(coalesce(CAST(p.description AS VARCHAR), '')) AS description,
                    try_cast({source('launch_speed')} AS DOUBLE) AS launch_speed,
                    try_cast({source('launch_angle')} AS DOUBLE) AS launch_angle,
                    try_cast({source('launch_speed_angle')} AS DOUBLE) AS launch_speed_angle,
                    try_cast({source('bat_speed')} AS DOUBLE) AS bat_speed,
                    try_cast({source('zone')} AS DOUBLE) AS zone,
                    try_cast({source('delta_run_exp')} AS DOUBLE) AS delta_run_exp,
                    try_cast({source('estimated_ba_using_speedangle')} AS DOUBLE) AS estimated_ba,
                    try_cast({source('estimated_slg_using_speedangle')} AS DOUBLE) AS estimated_slg,
                    try_cast({source('estimated_woba_using_speedangle')} AS DOUBLE) AS estimated_woba,
                    try_cast({source('woba_value')} AS DOUBLE) AS woba_value,
                    try_cast({source('woba_denom')} AS DOUBLE) AS woba_denom
                FROM {source_table} p
                WHERE p.game_type = 'R'
                  AND p.batter IS NOT NULL
            ), pitch_stats AS (
                SELECT
                    player_id,
                    count(DISTINCT game_pk) AS games,
                    count(*) AS pitches,
                    avg(launch_speed) FILTER (WHERE description = 'hit_into_play' AND launch_speed IS NOT NULL) AS avg_ev,
                    max(launch_speed) FILTER (WHERE description = 'hit_into_play') AS max_ev,
                    avg(bat_speed) FILTER (WHERE bat_speed IS NOT NULL) AS avg_bat_speed,
                    sum(delta_run_exp) FILTER (WHERE delta_run_exp IS NOT NULL) AS batting_run_value,
                    count(*) FILTER (WHERE description = 'hit_into_play' AND launch_angle BETWEEN 8 AND 32) * 1.0
                        / nullif(count(*) FILTER (WHERE description = 'hit_into_play' AND launch_angle IS NOT NULL), 0) AS sweet_spot_rate,
                    count(*) FILTER (
                        WHERE zone NOT BETWEEN 1 AND 9
                          AND description IN (
                            'swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip',
                            'hit_into_play', 'foul_bunt', 'missed_bunt', 'bunt_foul_tip', 'swinging_pitchout'
                          )
                    ) * 1.0 / nullif(count(*) FILTER (WHERE zone NOT BETWEEN 1 AND 9), 0) AS chase_rate,
                    count(*) FILTER (WHERE description = 'hit_into_play' AND launch_speed >= 95) * 1.0
                        / nullif(count(*) FILTER (WHERE description = 'hit_into_play' AND launch_speed IS NOT NULL), 0) AS hard_hit_rate,
                    count(*) FILTER (WHERE launch_speed_angle = 6) * 1.0
                        / nullif(count(launch_speed_angle), 0) AS barrel_rate,
                    count(*) FILTER (
                        WHERE description IN ('swinging_strike', 'swinging_strike_blocked', 'missed_bunt', 'swinging_pitchout')
                    ) * 1.0 / nullif(count(*) FILTER (
                        WHERE description IN (
                            'swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip',
                            'hit_into_play', 'foul_bunt', 'missed_bunt', 'bunt_foul_tip', 'swinging_pitchout'
                        )
                    ), 0) AS whiff_rate
                FROM regular
                GROUP BY player_id
            ), terminal AS (
                SELECT *
                FROM regular
                WHERE events NOT IN ('', 'truncated_pa')
                QUALIFY row_number() OVER (
                    PARTITION BY player_id, game_pk, at_bat_number
                    ORDER BY pitch_number DESC
                ) = 1
            ), pa_stats AS (
                SELECT
                    player_id,
                    count(*) AS plate_appearances,
                    count(*) FILTER (WHERE events NOT IN ({ab_events})) AS at_bats,
                    count(*) FILTER (WHERE events IN ('single', 'double', 'triple', 'home_run')) AS hits,
                    count(*) FILTER (WHERE events = 'home_run') AS home_runs,
                    count(*) FILTER (WHERE events IN ('walk', 'intent_walk')) AS walks,
                    count(*) FILTER (WHERE events IN ('strikeout', 'strikeout_double_play')) AS strikeouts,
                    sum(CASE events WHEN 'single' THEN 1 WHEN 'double' THEN 2 WHEN 'triple' THEN 3 WHEN 'home_run' THEN 4 ELSE 0 END) AS total_bases,
                    count(*) FILTER (WHERE events = 'hit_by_pitch') AS hit_by_pitch,
                    count(*) FILTER (WHERE events IN ('sac_fly', 'sac_fly_double_play')) AS sacrifice_flies,
                    sum(coalesce(woba_value, 0)) FILTER (WHERE coalesce(woba_denom, 0) > 0)
                        / nullif(sum(woba_denom) FILTER (WHERE coalesce(woba_denom, 0) > 0), 0) AS woba,
                    sum(CASE WHEN events NOT IN ({ab_events}) THEN coalesce(estimated_ba, 0) ELSE 0 END) AS expected_hits,
                    sum(CASE WHEN events NOT IN ({ab_events}) THEN coalesce(estimated_slg, 0) ELSE 0 END) AS expected_total_bases,
                    sum(coalesce(estimated_woba, woba_value, 0)) FILTER (WHERE coalesce(woba_denom, 0) > 0)
                        / nullif(sum(woba_denom) FILTER (WHERE coalesce(woba_denom, 0) > 0), 0) AS xwoba
                FROM terminal
                GROUP BY player_id
            ), team_usage AS (
                SELECT player_id, team, max(game_date) AS last_game_date, count(*) AS team_pitches
                FROM regular
                WHERE team IS NOT NULL
                GROUP BY player_id, team
            ), latest_team AS (
                SELECT player_id, team
                FROM team_usage
                QUALIFY row_number() OVER (
                    PARTITION BY player_id
                    ORDER BY last_game_date DESC, team_pitches DESC, team
                ) = 1
            ), stats AS (
                SELECT
                    pitch.player_id,
                    coalesce(team.team, '-') AS team,
                    pitch.games,
                    pa.plate_appearances,
                    pitch.pitches,
                    pa.at_bats,
                    pa.hits,
                    pa.home_runs,
                    pa.walks,
                    pa.strikeouts,
                    pa.hits * 1.0 / nullif(pa.at_bats, 0) AS avg,
                    (pa.hits + pa.walks + pa.hit_by_pitch) * 1.0
                        / nullif(pa.at_bats + pa.walks + pa.hit_by_pitch + pa.sacrifice_flies, 0) AS obp,
                    pa.total_bases * 1.0 / nullif(pa.at_bats, 0) AS slg,
                    pa.woba,
                    pa.expected_hits * 1.0 / nullif(pa.at_bats, 0) AS xba,
                    pa.expected_total_bases * 1.0 / nullif(pa.at_bats, 0) AS xslg,
                    pa.xwoba,
                    pitch.avg_ev,
                    pitch.max_ev,
                    pitch.avg_bat_speed,
                    pitch.batting_run_value,
                    pitch.sweet_spot_rate,
                    pitch.chase_rate,
                    pitch.hard_hit_rate,
                    pitch.barrel_rate,
                    pitch.whiff_rate,
                    pa.strikeouts * 1.0 / nullif(pa.plate_appearances, 0) AS strikeout_rate,
                    pa.walks * 1.0 / nullif(pa.plate_appearances, 0) AS walk_rate
                FROM pitch_stats pitch
                JOIN pa_stats pa USING (player_id)
                LEFT JOIN latest_team team USING (player_id)
            )
            SELECT
                stats.player_id,
                {name_expr} AS name,
                stats.team,
                {int(year)} AS year,
                stats.games,
                stats.plate_appearances,
                stats.pitches,
                stats.at_bats,
                stats.hits,
                stats.home_runs,
                stats.walks,
                stats.strikeouts,
                stats.avg,
                stats.obp,
                stats.slg,
                stats.obp + stats.slg AS ops,
                stats.woba,
                stats.xba,
                stats.xslg,
                stats.xwoba,
                stats.avg_ev,
                stats.max_ev,
                stats.avg_bat_speed,
                stats.batting_run_value,
                stats.sweet_spot_rate,
                stats.chase_rate,
                stats.hard_hit_rate,
                stats.barrel_rate,
                stats.whiff_rate,
                stats.strikeout_rate,
                stats.walk_rate
            FROM stats
            {player_join}
            """
        ).fetchdf()

    if rows.empty:
        return _empty_batter_frame()
    for column in ["player_id", "games", "plate_appearances", "pitches", "at_bats", "hits", "home_runs", "walks", "strikeouts"]:
        rows[column] = pd.to_numeric(rows[column], errors="coerce").astype("Int64")
    rows["player_id"] = rows["player_id"].astype(int)
    rows = rows[_batter_columns()].reset_index(drop=True)
    _BATTER_LEADERBOARD_CACHE[cache_key] = (modified_at, rows.copy())
    return rows


def _load_batter_csv(year: int) -> pd.DataFrame:
    paths = [
        settings.data_dir / "Batter" / f"{year}_batter_savant.csv",
        settings.data_dir / f"MLB{year}" / f"{year}_all_batter_standard.csv",
    ]
    source = _read_first_existing_csv(paths)
    if source.empty:
        return _empty_batter_frame()

    columns = {
        "player_id": "player_id",
        "last_name, first_name": "raw_name",
        "year": "year",
        "pa": "plate_appearances",
        "ab": "at_bats",
        "hit": "hits",
        "home_run": "home_runs",
        "walk": "walks",
        "strikeout": "strikeouts",
        "batting_avg": "avg",
        "on_base_percent": "obp",
        "slg_percent": "slg",
        "on_base_plus_slg": "ops",
        "woba": "woba",
        "xba": "xba",
        "xslg": "xslg",
        "xwoba": "xwoba",
        "exit_velocity_avg": "avg_ev",
        "hard_hit_percent": "hard_hit_rate",
        "barrel_batted_rate": "barrel_rate",
        "whiff_percent": "whiff_rate",
        "k_percent": "strikeout_rate",
        "bb_percent": "walk_rate",
    }
    available = {source_column: target_column for source_column, target_column in columns.items() if source_column in source.columns}
    frame = source[list(available)].rename(columns=available).copy()

    frame["player_id"] = pd.to_numeric(frame.get("player_id"), errors="coerce")
    frame = frame.dropna(subset=["player_id"]).copy()
    frame["player_id"] = frame["player_id"].astype(int)
    raw_names = frame["raw_name"] if "raw_name" in frame.columns else pd.Series([""] * len(frame), index=frame.index)
    frame["name"] = raw_names.map(_format_savant_name)
    frame["team"] = "-"
    frame["games"] = 0
    frame["pitches"] = 0
    frame["max_ev"] = None

    for column in _numeric_columns():
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = None
    for column in ["hard_hit_rate", "barrel_rate", "whiff_rate", "strikeout_rate", "walk_rate"]:
        frame[column] = frame[column].map(_percent_to_rate)

    return frame[_batter_columns()].reset_index(drop=True)


def _load_batter_pitch_supplement(year: int) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return pd.DataFrame(columns=["player_id", "team", "games", "pitches", "max_ev"])

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame(columns=["player_id", "team", "games", "pitches", "max_ev"])

        available = {row[1] for row in conn.execute(f"PRAGMA table_info('{source_table}')").fetchall()}
        team_expr = "offense_team" if "offense_team" in available else "NULL"
        max_ev_expr = "MAX(launch_speed)" if "launch_speed" in available else "NULL"

        raw = conn.execute(
            f"""
            SELECT
                batter AS player_id,
                COALESCE(NULLIF(TRIM(CAST({team_expr} AS VARCHAR)), ''), '-') AS team,
                COUNT(DISTINCT game_pk) AS games,
                COUNT(*) AS pitches,
                {max_ev_expr} AS max_ev,
                MAX(game_date) AS last_game_date
            FROM {source_table}
            WHERE game_type = 'R'
              AND batter IS NOT NULL
            GROUP BY 1, 2
            """
        ).fetchdf()

    if raw.empty:
        return pd.DataFrame(columns=["player_id", "team", "games", "pitches", "max_ev"])

    raw["player_id"] = pd.to_numeric(raw["player_id"], errors="coerce")
    raw = raw.dropna(subset=["player_id"]).copy()
    raw["player_id"] = raw["player_id"].astype(int)
    latest_team = raw.sort_values(["player_id", "last_game_date", "pitches"], ascending=[True, False, False]).drop_duplicates("player_id")
    totals = raw.groupby("player_id", as_index=False).agg(
        games=("games", "sum"),
        pitches=("pitches", "sum"),
        max_ev=("max_ev", "max"),
    )
    return totals.merge(latest_team[["player_id", "team"]], on="player_id", how="left")


def _batter_rows_from_supplement(supplement: pd.DataFrame, year: int) -> pd.DataFrame:
    frame = supplement.copy()
    frame["name"] = frame["player_id"].map(lambda value: f"Batter {int(value)}")
    frame["year"] = year
    for column in _numeric_columns():
        if column not in frame.columns:
            frame[column] = None
    return frame[_batter_columns()]


def _read_first_existing_csv(paths: list[Path]) -> pd.DataFrame:
    for path in paths:
        if path.exists():
            return pd.read_csv(path)
    return pd.DataFrame()


def _format_savant_name(value: object) -> str:
    text = str(value or "").strip()
    if "," not in text:
        return " ".join(text.split()) or "Unknown Batter"
    last, first = [part.strip() for part in text.split(",", 1)]
    return " ".join(f"{first} {last}".split()) or "Unknown Batter"


def _percent_to_rate(value: object) -> float | None:
    number = _nullable_float(value)
    if number is None:
        return None
    return number / 100 if abs(number) > 1 else number


def _nullable_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nullable_int(value: object) -> int | None:
    number = _nullable_float(value)
    if number is None:
        return None
    return int(round(number))


def _row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": int(row["player_id"]),
        "name": str(row.get("name") or "Unknown Batter"),
        "team": str(row.get("team") or "-"),
        "games": _nullable_int(row.get("games")) or 0,
        "plate_appearances": _nullable_int(row.get("plate_appearances")),
        "pitches": _nullable_int(row.get("pitches")),
        "at_bats": _nullable_int(row.get("at_bats")),
        "hits": _nullable_int(row.get("hits")),
        "home_runs": _nullable_int(row.get("home_runs")),
        "walks": _nullable_int(row.get("walks")),
        "strikeouts": _nullable_int(row.get("strikeouts")),
        "avg": _nullable_float(row.get("avg")),
        "obp": _nullable_float(row.get("obp")),
        "slg": _nullable_float(row.get("slg")),
        "ops": _nullable_float(row.get("ops")),
        "woba": _nullable_float(row.get("woba")),
        "xba": _nullable_float(row.get("xba")),
        "xslg": _nullable_float(row.get("xslg")),
        "xwoba": _nullable_float(row.get("xwoba")),
        "avg_ev": _nullable_float(row.get("avg_ev")),
        "max_ev": _nullable_float(row.get("max_ev")),
        "avg_bat_speed": _nullable_float(row.get("avg_bat_speed")),
        "batting_run_value": _nullable_float(row.get("batting_run_value")),
        "sweet_spot_rate": _nullable_float(row.get("sweet_spot_rate")),
        "chase_rate": _nullable_float(row.get("chase_rate")),
        "hard_hit_rate": _nullable_float(row.get("hard_hit_rate")),
        "barrel_rate": _nullable_float(row.get("barrel_rate")),
        "whiff_rate": _nullable_float(row.get("whiff_rate")),
        "strikeout_rate": _nullable_float(row.get("strikeout_rate")),
        "walk_rate": _nullable_float(row.get("walk_rate")),
    }


def _empty_batter_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_batter_columns())


def _batter_columns() -> list[str]:
    return ["player_id", "name", "team", "year", "games", "plate_appearances", "pitches", *_numeric_columns()]


def _numeric_columns() -> list[str]:
    return [
        "at_bats",
        "hits",
        "home_runs",
        "walks",
        "strikeouts",
        "avg",
        "obp",
        "slg",
        "ops",
        "woba",
        "xba",
        "xslg",
        "xwoba",
        "avg_ev",
        "max_ev",
        "avg_bat_speed",
        "batting_run_value",
        "sweet_spot_rate",
        "chase_rate",
        "hard_hit_rate",
        "barrel_rate",
        "whiff_rate",
        "strikeout_rate",
        "walk_rate",
    ]
