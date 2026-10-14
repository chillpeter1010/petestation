from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import duckdb

from app.api.schemas.batter_swing_timing import (
    SwingTimingFilters,
    SwingTimingLeaderboardRow,
    SwingTimingPitchProfile,
    SwingTimingPlayerDetailResponse,
    SwingTimingResponse,
)
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.batter_service import is_placeholder_player_name, list_batter_leaderboard
from app.services.batter_swing_matchup_service import (
    available_pitcher_teams,
    build_matchup_pitch_profiles,
    build_matchup_rows,
)


SAVANT_URL = "https://baseballsavant.mlb.com/leaderboard/bat-tracking/swing-timing-miss-distance"

PITCH_TYPE_GROUPS = [
    {"key": "fastball", "label": "Fastball", "options": [
        {"value": "FF", "label": "Four-Seam Fastball"}, {"value": "SI", "label": "Sinker"}, {"value": "FC", "label": "Cutter"},
    ]},
    {"key": "breaking", "label": "Breaking Ball", "options": [
        {"value": "SL", "label": "Slider"}, {"value": "ST", "label": "Sweeper"}, {"value": "CU", "label": "Curveball"},
        {"value": "KC", "label": "Knuckle Curve"}, {"value": "SV", "label": "Slurve"},
    ]},
    {"key": "offspeed", "label": "Offspeed", "options": [
        {"value": "CH", "label": "Changeup"}, {"value": "FS", "label": "Splitter"}, {"value": "FO", "label": "Forkball"},
    ]},
    {"key": "other", "label": "Other", "options": [
        {"value": "KN", "label": "Knuckleball"}, {"value": "EP", "label": "Eephus"}, {"value": "CS", "label": "Slow Curve"},
    ]},
]
PITCH_GROUP_OPTIONS = [{"value": "all", "label": "All pitch types"}] + [
    {"value": group["key"], "label": group["label"]} for group in PITCH_TYPE_GROUPS
]
PITCH_CODES_BY_GROUP = {
    group["key"]: {option["value"] for option in group["options"]}
    for group in PITCH_TYPE_GROUPS
}
PITCH_LABELS = {
    option["value"]: option["label"]
    for group in PITCH_TYPE_GROUPS
    for option in group["options"]
}
PERCENT_COLUMNS = [
    "flawed_percent", "perfect_percent", "tied_up_percent", "centered_percent", "flailed_percent",
    "early_percent", "on_time_percent", "late_percent", "whiff_rate", "competitive_percent",
    "over_percent", "lined_up_percent", "under_percent",
]
NUMERIC_COLUMNS = [
    "miss_distance", "avg_x_tied_up", "avg_x_flail", "avg_y_early", "avg_y_late",
    "avg_z_over", "avg_z_under", "n_swings", *PERCENT_COLUMNS,
]
NUMERIC_COLUMN_INDEX = {column: index for index, column in enumerate(NUMERIC_COLUMNS)}
TEAM_NAME_TO_CODE = {
    "Angels": "LAA", "Astros": "HOU", "Athletics": "ATH", "Blue Jays": "TOR", "Braves": "ATL",
    "Brewers": "MIL", "Cardinals": "STL", "Cubs": "CHC", "Diamondbacks": "AZ", "Dodgers": "LAD",
    "Giants": "SF", "Guardians": "CLE", "Mariners": "SEA", "Marlins": "MIA", "Mets": "NYM",
    "Nationals": "WSH", "Orioles": "BAL", "Padres": "SD", "Phillies": "PHI", "Pirates": "PIT",
    "Rangers": "TEX", "Rays": "TB", "Red Sox": "BOS", "Reds": "CIN", "Rockies": "COL",
    "Royals": "KC", "Tigers": "DET", "Twins": "MIN", "White Sox": "CWS", "Yankees": "NYY",
}


def timing_cache_path(year: int, pitcher_hand: str = "All", data_dir: Path | None = None) -> Path:
    root = Path(data_dir or settings.data_dir) / "MissDistance"
    hand = pitcher_hand.upper() if pitcher_hand.upper() in {"L", "R"} else "all"
    return root / f"{int(year)}_batter_timing_summary_{hand}.csv"


def timing_meta_path(year: int, pitcher_hand: str = "All", data_dir: Path | None = None) -> Path:
    return timing_cache_path(year, pitcher_hand, data_dir).with_suffix(".meta.json")


def build_savant_params(year: int, pitcher_hand: str = "All") -> list[tuple[str, str | int]]:
    hand = pitcher_hand.upper() if pitcher_hand.upper() in {"L", "R"} else ""
    return [
        ("type", "batter"), ("season[]", int(year)), ("splitYear", "1"), ("min", "1"),
        ("split[]", "api_pitch_type_group03"), ("minSplit", "1"), ("gameType[]", "R"),
        ("dateStart", f"{int(year)}-03-01"), ("dateEnd", f"{int(year)}-11-15"),
        ("batSide", ""), ("contactType", ""), ("attackZone", ""), ("pitchHand", hand), ("csv", "true"),
    ]


def refresh_batter_timing_cache(
    year: int,
    pitcher_hand: str = "All",
    data_dir: Path | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    path = timing_cache_path(year, pitcher_hand, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        SAVANT_URL,
        params=build_savant_params(year, pitcher_hand),
        headers={"User-Agent": "Mozilla/5.0 Petehub/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_bytes(response.content)
    frame = pd.read_csv(temp_path, low_memory=False)
    required = {"id", "name", "api_pitch_type", "n_swings", "miss_distance", "on_time_percent"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        temp_path.unlink(missing_ok=True)
        raise ValueError(f"Savant timing export is missing columns: {', '.join(missing)}")
    temp_path.replace(path)
    meta = {
        "season": int(year),
        "pitcher_hand": pitcher_hand if pitcher_hand in {"L", "R"} else "All",
        "rows": int(len(frame)),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_url": response.url,
        "output": str(path),
    }
    timing_meta_path(year, pitcher_hand, data_dir).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _aggregate_selection.cache_clear()
    return meta


def load_batter_timing_cache(year: int, pitcher_hand: str = "All", data_dir: Path | None = None) -> pd.DataFrame:
    path = timing_cache_path(year, pitcher_hand, data_dir)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, low_memory=False)
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce") if column in frame else np.nan
    frame["player_id"] = pd.to_numeric(frame.get("id"), errors="coerce").astype("Int64")
    frame["pitch_code"] = frame.get("api_pitch_type", pd.Series(index=frame.index, dtype="object")).fillna("").astype(str).str.upper()
    frame["batter_side"] = frame.get("bat_side_formatted", pd.Series(index=frame.index, dtype="object")).fillna("-").astype(str).str.upper()
    return frame[frame["player_id"].notna() & frame["pitch_code"].ne("")].copy()


def get_batter_swing_timing(
    year: int = 2026,
    pitch_group: str = "all",
    pitch_type: str = "All",
    pitcher_hand: str = "All",
    batter_side: str = "All",
    batter_team: str = "All",
    pitcher_team: str = "All",
    minimum_swings: int = 50,
    minimum_plate_appearances: int = 100,
    data_dir: Path | None = None,
) -> SwingTimingResponse:
    group = pitch_group if pitch_group in {"all", *PITCH_CODES_BY_GROUP.keys()} else "all"
    code = pitch_type.upper() if pitch_type and pitch_type.upper() in PITCH_LABELS else "All"
    hand = pitcher_hand.upper() if pitcher_hand.upper() in {"L", "R"} else "All"
    side = batter_side.upper() if batter_side.upper() in {"L", "R"} else "All"
    valid_team_codes = set(TEAM_NAME_TO_CODE.values())
    hitter_team = batter_team.upper() if batter_team.upper() in valid_team_codes else "All"
    pitcher_team_codes = set(available_pitcher_teams(year, data_dir))
    opponent_team = pitcher_team.upper() if pitcher_team.upper() in pitcher_team_codes else "All"
    requested_pa = min(700, max(5, int(minimum_plate_appearances)))
    minimum_pa = min(700, max(5, ((requested_pa + 2) // 5) * 5))
    filters = _build_filters(year, data_dir)
    if opponent_team != "All":
        rows, league, matched_swings, warnings = build_matchup_rows(
            year=year, pitch_codes=_selected_pitch_codes(group, code), pitcher_hand=hand,
            batter_side=side, batter_team=hitter_team, pitcher_team=opponent_team, data_dir=data_dir,
        )
        rows = _apply_player_context(rows, year, data_dir)
        qualified = [row for row in rows if row.n_swings >= max(0, int(minimum_swings)) and (row.plate_appearances is None or row.plate_appearances >= minimum_pa)]
        warnings.append("Pitcher Team uses exact pitch-level matchups. Savant horizontal, timing, and vertical alignment fields are unavailable in this event mode.")
        return SwingTimingResponse(
            year=year, data_mode="matchup_event", pitch_group=group, pitch_type=code,
            pitcher_hand=hand, batter_side=side, batter_team=hitter_team, pitcher_team=opponent_team,
            minimum_swings=max(0, int(minimum_swings)), minimum_plate_appearances=minimum_pa,
            matched_swings=matched_swings, matched_hitters=len(rows), qualified_hitters=len(qualified),
            league=league, leaderboard=qualified, filters=filters,
            warnings=list(dict.fromkeys(warnings)),
        )
    root = Path(data_dir or settings.data_dir).resolve()
    path = timing_cache_path(year, hand, root)
    modified_at = path.stat().st_mtime_ns if path.exists() else 0
    rows, league, matched_swings = _aggregate_selection(year, group, code, hand, side, hitter_team, str(root), modified_at)
    if league is None:
        warning = (
            f"No batter Swing Timing rows match the selected filters for {year}."
            if path.exists()
            else f"No batter Swing Timing cache is available for {year} ({hand} pitchers)."
        )
        return SwingTimingResponse(
            year=year, pitch_group=group, pitch_type=code, pitcher_hand=hand, batter_side=side,
            batter_team=hitter_team, pitcher_team=opponent_team, minimum_swings=minimum_swings,
            minimum_plate_appearances=minimum_pa, filters=filters,
            warnings=[warning],
        )
    enriched_rows = _apply_player_context(rows, year, data_dir)
    qualified = [
        row for row in enriched_rows
        if row.n_swings >= max(0, int(minimum_swings))
        and (row.plate_appearances is None or row.plate_appearances >= minimum_pa)
    ]
    meta = _read_meta(year, hand, data_dir)
    return SwingTimingResponse(
        year=year,
        data_updated_at=str(meta.get("generated_at") or "")[:10] or None,
        source_url=meta.get("source_url"),
        pitch_group=group,
        pitch_type=code,
        pitcher_hand=hand,
        batter_side=side,
        batter_team=hitter_team,
        pitcher_team=opponent_team,
        minimum_swings=max(0, int(minimum_swings)),
        minimum_plate_appearances=minimum_pa,
        matched_swings=matched_swings,
        matched_hitters=len(enriched_rows),
        qualified_hitters=len(qualified),
        league=league,
        leaderboard=qualified,
        filters=filters,
        warnings=["Pitcher Team requires a batter-by-opposing-team timing cache and is not applied yet."] if opponent_team != "All" else [],
        data_mode="summary",
    )


def get_batter_swing_timing_player(
    year: int,
    batter_id: int,
    pitch_group: str = "all",
    pitch_type: str = "All",
    pitcher_hand: str = "All",
    batter_side: str = "All",
    pitcher_team: str = "All",
    data_dir: Path | None = None,
) -> SwingTimingPlayerDetailResponse:
    response = get_batter_swing_timing(
        year=year, pitch_group=pitch_group, pitch_type=pitch_type,
        pitcher_hand=pitcher_hand, batter_side=batter_side, pitcher_team=pitcher_team,
        minimum_swings=0, minimum_plate_appearances=5, data_dir=data_dir,
    )
    player = next((row for row in response.leaderboard if row.batter_id == batter_id), None)
    codes = _selected_pitch_codes(response.pitch_group, response.pitch_type)
    event_profiles, event_warnings = build_matchup_pitch_profiles(
        year=year, batter_id=batter_id, pitch_codes=codes,
        pitcher_hand=response.pitcher_hand, batter_side=response.batter_side,
        pitcher_team=response.pitcher_team, data_dir=data_dir,
    )
    event_by_pitch = {row.pitch_type: row for row in event_profiles}
    profiles: list[SwingTimingPitchProfile] = []
    if response.data_mode == "summary":
        frame = load_batter_timing_cache(year, response.pitcher_hand, data_dir)
        if codes:
            frame = frame[frame["pitch_code"].isin(codes)]
        if response.batter_side != "All":
            frame = frame[frame["batter_side"].eq(response.batter_side)]
        frame = frame[frame["player_id"].eq(batter_id)]
        for pitch_code, group_frame in frame.groupby("pitch_code", sort=False):
            summary = _aggregate_group(group_frame, batter_id, None)
            event = event_by_pitch.get(str(pitch_code))
            profiles.append(SwingTimingPitchProfile(
                pitch_type=str(pitch_code), pitch_label=PITCH_LABELS.get(str(pitch_code), str(pitch_code)),
                n_swings=summary.n_swings, miss_distance=summary.miss_distance,
                whiff_pct=summary.whiff_pct, competitive_pct=summary.competitive_pct,
                flawed_pct=summary.flawed_pct, perfect_pct=summary.perfect_pct,
                centered_pct=summary.centered_pct, on_time_pct=summary.on_time_pct,
                lined_up_pct=summary.lined_up_pct,
                avg_bat_speed=event.avg_bat_speed if event else None,
                season_bat_speed=event.season_bat_speed if event else None,
                bat_speed_delta=event.bat_speed_delta if event else None,
                fast_swing_pct=event.fast_swing_pct if event else None,
                avg_swing_length=event.avg_swing_length if event else None,
                avg_attack_angle=event.avg_attack_angle if event else None,
                avg_attack_direction=event.avg_attack_direction if event else None,
                avg_swing_path_tilt=event.avg_swing_path_tilt if event else None,
            ))
    else:
        profiles = event_profiles
    raw_identity = next((row for row in list_batter_leaderboard(year) if int(row.get("player_id") or 0) == batter_id), {})
    return SwingTimingPlayerDetailResponse(
        year=year, batter_id=batter_id,
        name=player.name if player else str(raw_identity.get("name") or f"Batter {batter_id}"),
        team=player.team if player else str(raw_identity.get("team") or "-"),
        pitcher_team=response.pitcher_team, data_mode=response.data_mode,
        player=player, league=response.league,
        pitch_matrix=sorted(profiles, key=lambda item: -item.n_swings),
        warnings=list(dict.fromkeys([*response.warnings, *event_warnings])),
    )


def _selected_pitch_codes(group: str, code: str) -> set[str] | None:
    if code != "All":
        return {code}
    return PITCH_CODES_BY_GROUP.get(group)


@lru_cache(maxsize=64)
def _aggregate_selection(
    year: int,
    group: str,
    code: str,
    hand: str,
    side: str,
    batter_team: str,
    data_root: str,
    modified_at: int,
) -> tuple[tuple[SwingTimingLeaderboardRow, ...], SwingTimingLeaderboardRow | None, int]:
    del modified_at  # Included in the cache key so refreshed source files invalidate prior results.
    frame = load_batter_timing_cache(year, hand, Path(data_root))
    if frame.empty:
        return (), None, 0
    if group != "all":
        frame = frame[frame["pitch_code"].isin(PITCH_CODES_BY_GROUP[group])]
    if code != "All":
        frame = frame[frame["pitch_code"].eq(code)]
    if side != "All":
        frame = frame[frame["batter_side"].eq(side)]
    identity_map = {
        int(row["player_id"]): (
            str(row.get("name") or ""),
            str(row.get("team") or "-"),
            int(row["plate_appearances"]) if pd.notna(row.get("plate_appearances")) else None,
        )
        for row in list_batter_leaderboard(year)
        if row.get("player_id")
    }
    if batter_team != "All":
        source_team_codes = frame.get("team_name", pd.Series(index=frame.index, dtype="object")).map(TEAM_NAME_TO_CODE)
        identity_team_codes = frame["player_id"].map(lambda player_id: identity_map.get(int(player_id), ("", "", None))[1])
        frame = frame[identity_team_codes.where(identity_team_codes.ne(""), source_team_codes).eq(batter_team)]
    if frame.empty:
        return (), None, 0

    rows = tuple(_aggregate_batters(frame, identity_map))
    league = _aggregate_league(frame)
    matched_swings = int(pd.to_numeric(frame["n_swings"], errors="coerce").fillna(0).sum())
    return rows, league, matched_swings


def _aggregate_batters(
    frame: pd.DataFrame,
    identity_map: dict[int, tuple[str, str, int | None]] | None = None,
) -> list[SwingTimingLeaderboardRow]:
    if frame.empty:
        return []
    identity_map = identity_map or {}
    rows = []
    for player_id, group in frame.groupby("player_id", dropna=True):
        rows.append(_aggregate_group(group, int(player_id), identity_map.get(int(player_id))))
    return sorted(rows, key=lambda row: (-row.n_swings, row.name))


def _aggregate_league(frame: pd.DataFrame) -> SwingTimingLeaderboardRow | None:
    if frame.empty:
        return None
    return _aggregate_group(frame, 0, ("MLB", "MLB", None))


def _aggregate_group(
    group: pd.DataFrame,
    player_id: int,
    identity: tuple[str, str, int | None] | None,
) -> SwingTimingLeaderboardRow:
    numeric = group.reindex(columns=NUMERIC_COLUMNS).to_numpy(dtype=float)
    swings = np.nan_to_num(numeric[:, NUMERIC_COLUMN_INDEX["n_swings"]], nan=0.0)
    swings = np.clip(swings, 0, None)

    def weighted(column: str, weights: np.ndarray) -> float | None:
        values = numeric[:, NUMERIC_COLUMN_INDEX[column]]
        valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
        if not valid.any():
            return None
        value = float(np.average(values[valid], weights=weights[valid]))
        return value if np.isfinite(value) else None

    def rounded_weighted(column: str, weights: np.ndarray) -> float | None:
        value = weighted(column, weights)
        return round(value, 3) if value is not None else None

    def percent(column: str) -> float | None:
        value = weighted(column, swings)
        return round(value * 100, 3) if value is not None else None

    def conditional_mean(value_column: str, rate_column: str) -> float | None:
        rates = np.nan_to_num(numeric[:, NUMERIC_COLUMN_INDEX[rate_column]], nan=0.0)
        return rounded_weighted(value_column, swings * np.clip(rates, 0, None))

    raw_name = str(group.get("name", pd.Series([""])).iloc[0] or "")
    raw_team = str(group.get("team_name", pd.Series(["-"])).iloc[0] or "-")
    identity_name = identity[0] if identity else ""
    name = _display_name(raw_name) if is_placeholder_player_name(identity_name) else identity_name
    team = identity[1] if identity and identity[1] not in {"", "-"} else TEAM_NAME_TO_CODE.get(raw_team, "-" if raw_team == "zMLB" else raw_team)
    plate_appearances = identity[2] if identity else None
    side = str(group["batter_side"].mode().iloc[0]) if "batter_side" in group and not group["batter_side"].mode().empty else "-"
    whiff_rates = np.nan_to_num(numeric[:, NUMERIC_COLUMN_INDEX["whiff_rate"]], nan=0.0)
    whiff_weights = swings * np.clip(whiff_rates, 0, None)
    return SwingTimingLeaderboardRow(
        batter_id=player_id,
        name=name,
        team=team,
        plate_appearances=plate_appearances,
        batter_side=side,
        pitch_types=sorted(group["pitch_code"].dropna().astype(str).unique().tolist()),
        n_swings=int(round(float(swings.sum()))),
        miss_distance=rounded_weighted("miss_distance", whiff_weights),
        flawed_pct=percent("flawed_percent"),
        perfect_pct=percent("perfect_percent"),
        whiff_pct=percent("whiff_rate"),
        competitive_pct=percent("competitive_percent"),
        tied_up_pct=percent("tied_up_percent"),
        avg_tied_up_distance=conditional_mean("avg_x_tied_up", "tied_up_percent"),
        centered_pct=percent("centered_percent"),
        flail_pct=percent("flailed_percent"),
        avg_flail_distance=conditional_mean("avg_x_flail", "flailed_percent"),
        late_pct=percent("late_percent"),
        avg_late_ms=conditional_mean("avg_y_late", "late_percent"),
        on_time_pct=percent("on_time_percent"),
        early_pct=percent("early_percent"),
        avg_early_ms=conditional_mean("avg_y_early", "early_percent"),
        over_pct=percent("over_percent"),
        avg_over_distance=conditional_mean("avg_z_over", "over_percent"),
        lined_up_pct=percent("lined_up_percent"),
        under_pct=percent("under_percent"),
        avg_under_distance=conditional_mean("avg_z_under", "under_percent"),
        sample_status="Stable" if swings.sum() >= 100 else "Developing",
    )


def _display_name(value: str) -> str:
    if "," not in value:
        return value or "Unknown Batter"
    last, first = [part.strip() for part in value.split(",", 1)]
    return f"{first} {last}".strip()


def _apply_player_context(
    rows: tuple[SwingTimingLeaderboardRow, ...] | list[SwingTimingLeaderboardRow],
    year: int,
    data_dir: Path | None,
) -> list[SwingTimingLeaderboardRow]:
    root = Path(data_dir or settings.data_dir).resolve()
    path = get_season_duckdb_path(year, root)
    modified_at = path.stat().st_mtime_ns if path.exists() else 0
    context = _load_player_context(year, str(root), modified_at)
    enriched = []
    for row in rows:
        age, teams = context.get(row.batter_id, (None, ()))
        fallback_teams = (row.team,) if row.team not in {"", "-", "MLB"} else ()
        enriched.append(row.model_copy(update={"age": age, "teams": list(teams or fallback_teams)}))
    return enriched


@lru_cache(maxsize=16)
def _load_player_context(
    year: int,
    data_root: str,
    modified_at: int,
) -> dict[int, tuple[int | None, tuple[str, ...]]]:
    del modified_at  # The database mtime is part of the cache key.
    path = get_season_duckdb_path(year, Path(data_root))
    if not path.exists():
        return {}
    try:
        with duckdb.connect(str(path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            table = "pitches_enriched" if "pitches_enriched" in tables else ("pitches" if "pitches" in tables else "")
            if not table:
                return {}
            columns = {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()}
            player_column = "batter_id" if "batter_id" in columns else ("batter" if "batter" in columns else "")
            team_column = "batter_team" if "batter_team" in columns else ("offense_team" if "offense_team" in columns else "")
            age_column = "age_bat" if "age_bat" in columns else ("age_bat_legacy" if "age_bat_legacy" in columns else "")
            date_expression = "MIN(TRY_CAST(game_date AS DATE))" if "game_date" in columns else "NULL"
            if not player_column or not team_column:
                return {}
            age_expression = f"MAX(TRY_CAST({age_column} AS DOUBLE))" if age_column else "NULL"
            records = conn.execute(f"""
                SELECT CAST({player_column} AS BIGINT) AS player_id,
                       {age_expression} AS age,
                       NULLIF(TRIM(CAST({team_column} AS VARCHAR)), '') AS team,
                       {date_expression} AS first_game
                FROM {table}
                WHERE {player_column} IS NOT NULL
                GROUP BY player_id, team
                ORDER BY player_id, first_game NULLS LAST, team
            """).fetchall()
    except duckdb.Error:
        return {}

    players: dict[int, dict[str, Any]] = {}
    for player_id, age, team, _ in records:
        item = players.setdefault(int(player_id), {"age": None, "teams": []})
        if age is not None:
            item["age"] = max(item["age"] or 0, int(age))
        team_code = str(team or "").strip().upper()
        if team_code and team_code not in {"-", "NAN"} and team_code not in item["teams"]:
            item["teams"].append(team_code)
    return {
        player_id: (values["age"], tuple(values["teams"]))
        for player_id, values in players.items()
    }


def _build_filters(year: int, data_dir: Path | None = None) -> SwingTimingFilters:
    root = Path(data_dir or settings.data_dir) / "MissDistance"
    years = sorted({int(path.name[:4]) for path in root.glob("????_batter_timing_summary_all.csv") if path.name[:4].isdigit()}, reverse=True) if root.exists() else []
    teams = sorted({str(row.get("team")) for row in list_batter_leaderboard(year) if row.get("team") not in {None, "", "-"}})
    team_options = [{"value": "All", "label": "All teams"}] + [{"value": team, "label": team} for team in teams]
    return SwingTimingFilters(
        available_years=years,
        pitch_groups=PITCH_GROUP_OPTIONS,
        pitch_type_groups=PITCH_TYPE_GROUPS,
        pitcher_hands=[{"value": "All", "label": "All pitchers"}, {"value": "L", "label": "LHP"}, {"value": "R", "label": "RHP"}],
        batter_sides=[{"value": "All", "label": "All hitters"}, {"value": "L", "label": "Left-handed"}, {"value": "R", "label": "Right-handed"}],
        batter_teams=team_options,
        pitcher_teams=[{"value": "All", "label": "All pitcher teams"}] + [
            {"value": team, "label": team} for team in available_pitcher_teams(year, data_dir)
        ],
    )


def _read_meta(year: int, pitcher_hand: str, data_dir: Path | None = None) -> dict[str, Any]:
    path = timing_meta_path(year, pitcher_hand, data_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
