from __future__ import annotations

import json
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.batter_team_research import BatterLineupScenarioResponse, BatterTeamResearchResponse
from app.api.schemas.common import ResponseMeta
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.batter_period_comparison_service import compute_batter_period_metrics, normalize_batter_period_rows
from app.services.batter_service import list_batter_options

POSITION_COLUMNS = {
    "fielder_2": "C", "fielder_3": "1B", "fielder_4": "2B", "fielder_5": "3B",
    "fielder_6": "SS", "fielder_7": "LF", "fielder_8": "CF", "fielder_9": "RF",
}
LINEUP_CACHE_VERSION = "lineup-simulation-v1"


def get_batter_team_research(year: int, team: str, opponent_hand: str = "All") -> BatterTeamResearchResponse:
    pitches, positions = load_team_research_rows(year, team)
    if pitches.empty:
        return BatterTeamResearchResponse(
            meta=ResponseMeta(year=year, warnings=[f"No regular-season batting data found for {team}."]),
            team=team, opponent_hand=opponent_hand, data_mode="unavailable",
            limitations=_limitations(),
        )
    names = {int(row["value"]): row["name"] for row in list_batter_options(year)}
    terminal = _terminal_pa(pitches)
    terminal = _add_observed_order(terminal)
    game_dates = terminal.groupby("game_pk")["game_date"].max().sort_values(ascending=False)
    recent_games = game_dates.head(20).index.tolist()
    recent = terminal[terminal["game_pk"].isin(recent_games)].copy()
    starter_rows = recent.sort_values(["game_pk", "at_bat_number"]).drop_duplicates(["game_pk", "batting_order"])
    hitter_rows = _hitter_rows(terminal, names, opponent_hand)
    position_rows = _position_rows(positions, names)
    prediction = _lineup_prediction(starter_rows, hitter_rows, position_rows, names, len(recent_games))
    scenarios = _lineup_scenarios(prediction, starter_rows, hitter_rows, position_rows, names)
    max_date = pd.to_datetime(pitches["game_date"], errors="coerce").max()
    return BatterTeamResearchResponse(
        meta=ResponseMeta(year=year, data_updated_at=max_date.to_pydatetime() if pd.notna(max_date) else None),
        team=team,
        opponent_hand=opponent_hand,
        data_mode="recent_observed_research",
        coverage={
            "games": int(terminal["game_pk"].nunique()),
            "plate_appearances": int(len(terminal)),
            "recent_games": len(recent_games),
            "batting_order": "reconstructed_from_pa_sequence",
            "defensive_position_games": int(positions[["game_pk", "player_id"]].drop_duplicates().shape[0]) if not positions.empty else 0,
            "dh_ph": "unavailable_without_official_lineup_roles",
            "active_roster": "unavailable",
            "injuries": "unavailable",
            "probable_starter": "user_selected_hand_only",
        },
        order_splits=_order_splits(terminal),
        hitters=hitter_rows,
        position_coverage=position_rows,
        lineup_prediction=prediction,
        scenarios=scenarios,
        limitations=_limitations(),
    )


def lineup_scenario_cache_path(year: int, data_dir: Path | None = None) -> Path:
    return (data_dir or settings.data_dir) / "derived" / f"batter_lineup_scenarios_{int(year)}.json"


def refresh_batter_lineup_scenario_cache(
    year: int = 2026,
    data_dir: Path | None = None,
    teams: list[str] | None = None,
) -> dict[str, Any]:
    root = data_dir or settings.data_dir
    db_path = get_season_duckdb_path(year, root)
    if not db_path.exists():
        raise FileNotFoundError(f"Season database not found: {db_path}")
    available_teams = sorted({str(row["team"]).upper() for row in list_batter_options(year) if row.get("team") not in {None, "", "-"}})
    selected_teams = sorted({str(team).strip().upper() for team in (teams or available_teams) if str(team).strip()})
    path = lineup_scenario_cache_path(year, root)
    entries: dict[str, Any] = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("model_version") == LINEUP_CACHE_VERSION:
                entries.update(previous.get("entries", {}))
        except (OSError, json.JSONDecodeError):
            entries = {}
    source_mtime = db_path.stat().st_mtime_ns
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    failures: dict[str, str] = {}
    for team in selected_teams:
        for hand in ("R", "L"):
            key = f"{team}:{hand}"
            try:
                response = get_batter_team_research(year, team, hand)
                entries[key] = {
                    "team": team,
                    "opponent_hand": hand,
                    "generated_at": generated_at,
                    "source_db_mtime_ns": source_mtime,
                    "data_updated_at": response.meta.data_updated_at.isoformat() if response.meta.data_updated_at else None,
                    "lineup_prediction": response.lineup_prediction,
                    "scenarios": response.scenarios,
                    "limitations": response.limitations,
                }
            except Exception as exc:
                failures[key] = str(exc)
    payload = {
        "year": int(year),
        "model_version": LINEUP_CACHE_VERSION,
        "generated_at": generated_at,
        "entries": entries,
        "failures": failures,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp_path.replace(path)
    return {
        "status": "completed" if not failures else "partial",
        "year": int(year),
        "generated_at": generated_at,
        "teams": len(selected_teams),
        "entries": len(entries),
        "failures": failures,
        "path": str(path),
    }


def get_cached_batter_lineup_scenarios(
    year: int,
    team: str,
    opponent_hand: str,
    data_dir: Path | None = None,
) -> BatterLineupScenarioResponse:
    team_code = str(team).strip().upper()
    hand = str(opponent_hand).strip().upper()
    if hand not in {"L", "R"}:
        raise ValueError("opponent_hand must be L or R")
    root = data_dir or settings.data_dir
    path = lineup_scenario_cache_path(year, root)
    db_path = get_season_duckdb_path(year, root)
    if not path.exists():
        return _unavailable_lineup_cache(year, team_code, hand, "Precomputed lineup scenarios are not available yet.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _unavailable_lineup_cache(year, team_code, hand, "Precomputed lineup scenario cache is unreadable.")
    if payload.get("model_version") != LINEUP_CACHE_VERSION:
        return _unavailable_lineup_cache(year, team_code, hand, "Precomputed lineup scenario cache uses an older model version.")
    entry = payload.get("entries", {}).get(f"{team_code}:{hand}")
    if not entry:
        return _unavailable_lineup_cache(year, team_code, hand, "This team and pitcher-hand scenario has not been precomputed yet.")
    current_mtime = db_path.stat().st_mtime_ns if db_path.exists() else 0
    cache_status = "current" if int(entry.get("source_db_mtime_ns", 0)) == current_mtime else "stale"
    warnings = [] if cache_status == "current" else ["Newer pitch data exists; showing the last completed lineup scenario cache while it rebuilds."]
    return BatterLineupScenarioResponse(
        meta=ResponseMeta(year=year, data_updated_at=entry.get("data_updated_at"), warnings=warnings),
        team=team_code,
        opponent_hand=hand,
        cache_status=cache_status,
        generated_at=entry.get("generated_at"),
        model_version=LINEUP_CACHE_VERSION,
        lineup_prediction=entry.get("lineup_prediction", {}),
        scenarios=entry.get("scenarios", []),
        limitations=entry.get("limitations", []),
    )


def _unavailable_lineup_cache(year: int, team: str, hand: str, warning: str) -> BatterLineupScenarioResponse:
    return BatterLineupScenarioResponse(
        meta=ResponseMeta(year=year, warnings=[warning]),
        team=team,
        opponent_hand=hand,
        cache_status="unavailable",
        model_version=LINEUP_CACHE_VERSION,
    )


def load_team_research_rows(year: int, team: str, *, include_positions: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return pd.DataFrame(), pd.DataFrame()
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        if not source:
            return pd.DataFrame(), pd.DataFrame()
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info('{source}')").fetchall()}
        offense = _team_expression(columns, offense=True)
        raw = conn.execute(
            f"SELECT * FROM {source} WHERE game_type = 'R' AND {offense} = ?",
            [team],
        ).fetchdf()
        position_frame = pd.DataFrame()
        if include_positions:
            defense = _team_expression(columns, offense=False)
            unions = []
            for column, position in POSITION_COLUMNS.items():
                if column in columns:
                    unions.append(
                        f"SELECT game_pk, try_cast({column} AS BIGINT) player_id, '{position}' field_position, count(*) pitches "
                        f"FROM {source} WHERE game_type = 'R' AND {defense} = ? AND {column} IS NOT NULL GROUP BY game_pk, player_id"
                    )
            if unions:
                position_frame = conn.execute(" UNION ALL ".join(unions), [team] * len(unions)).fetchdf()
    return normalize_batter_period_rows(raw), position_frame


def _team_expression(columns: set[str], *, offense: bool) -> str:
    direct = "batter_team" if "batter_team" in columns else "offense_team" if "offense_team" in columns else None
    inning_expression = "CASE WHEN inning_topbot = 'Top' THEN away_team ELSE home_team END"
    if not offense:
        inning_expression = "CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END"
        return inning_expression
    return f"coalesce(nullif(trim(cast({direct} as varchar)), ''), {inning_expression})" if direct else inning_expression


def _terminal_pa(rows: pd.DataFrame) -> pd.DataFrame:
    terminal = rows[rows["events"].ne("") & rows["events"].ne("truncated_pa")].copy()
    return terminal.sort_values(["game_pk", "at_bat_number", "pitch_number"]).groupby(
        ["game_pk", "at_bat_number"], as_index=False
    ).tail(1)


def _add_observed_order(pa: pd.DataFrame) -> pd.DataFrame:
    result = pa.sort_values(["game_pk", "at_bat_number"]).copy()
    result["batting_order"] = result.groupby("game_pk").cumcount().mod(9).add(1)
    return result


def _order_splits(pa: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for order, group in pa.groupby("batting_order"):
        metrics = compute_batter_period_metrics(group)
        rows.append({
            "batting_order": int(order), "pa": len(group),
            "avg": metrics["avg"][0], "obp": metrics["obp"][0], "slg": metrics["slg"][0],
            "woba": metrics["woba"][0], "k_pct": metrics["k_pct"][0], "bb_pct": metrics["bb_pct"][0],
        })
    return rows


def _hitter_rows(pa: pd.DataFrame, names: dict[int, str], opponent_hand: str) -> list[dict[str, Any]]:
    filtered = pa if opponent_hand not in {"L", "R"} else pa[pa["p_throws"].eq(opponent_hand)]
    rows = []
    for player_id, group in filtered.groupby("batter"):
        if pd.isna(player_id):
            continue
        metrics = compute_batter_period_metrics(group)
        rows.append({
            "player_id": int(player_id), "name": names.get(int(player_id), f"Batter {int(player_id)}"),
            "pa": len(group), "avg": metrics["avg"][0], "obp": metrics["obp"][0],
            "slg": metrics["slg"][0], "woba": metrics["woba"][0],
            "k_pct": metrics["k_pct"][0], "bb_pct": metrics["bb_pct"][0],
            "reliability": sample_reliability(len(group)),
            "event_rates": _event_rates(group),
        })
    return sorted(rows, key=lambda row: row["pa"], reverse=True)


def sample_reliability(plate_appearances: int) -> float:
    pa = max(0, int(plate_appearances))
    return round(pa / (pa + 50), 3)


def _position_rows(positions: pd.DataFrame, names: dict[int, str]) -> list[dict[str, Any]]:
    if positions.empty:
        return []
    grouped = positions.groupby(["player_id", "field_position"], as_index=False).agg(games=("game_pk", "nunique"), pitches=("pitches", "sum"))
    rows = []
    for player_id, group in grouped.groupby("player_id"):
        ordered = group.sort_values(["games", "pitches"], ascending=False)
        rows.append({
            "player_id": int(player_id), "name": names.get(int(player_id), f"Player {int(player_id)}"),
            "primary_position": str(ordered.iloc[0]["field_position"]),
            "positions": [{"position": row.field_position, "games": int(row.games)} for row in ordered.itertuples()],
            "fielding_games": int(group["games"].sum()),
        })
    return sorted(rows, key=lambda row: row["fielding_games"], reverse=True)


def _lineup_prediction(starters: pd.DataFrame, hitters: list[dict[str, Any]], positions: list[dict[str, Any]], names: dict[int, str], games: int) -> dict[str, Any]:
    position_map = {row["player_id"]: row["primary_position"] for row in positions}
    player_games = starters.groupby("batter")["game_pk"].nunique()
    order_counts = starters.groupby(["batter", "batting_order"]).size()
    probabilities = []
    for player_id, started in player_games.items():
        order_map = {str(int(order)): int(count) / int(started) for order, count in order_counts.loc[player_id].items()}
        probabilities.append({
            "player_id": int(player_id), "name": names.get(int(player_id), f"Batter {int(player_id)}"),
            "start_probability": round(int(started) / max(games, 1), 3), "starts": int(started),
            "order_probabilities": order_map, "primary_position": position_map.get(int(player_id), "DH/PH unknown"),
        })
    probabilities.sort(key=lambda row: row["start_probability"], reverse=True)
    return {
        "basis": f"Observed starters from the most recent {games} team games; not an official lineup.",
        "players": probabilities,
    }


def _lineup_scenarios(prediction: dict[str, Any], starters: pd.DataFrame, hitters: list[dict[str, Any]], positions: list[dict[str, Any]], names: dict[int, str]) -> list[dict[str, Any]]:
    eligible = prediction.get("players", [])[:12]
    hitter_map = {row["player_id"]: row for row in hitters}
    consensus = _consensus_lineup(eligible)
    latest_game = starters.sort_values("game_date", ascending=False)["game_pk"].iloc[0] if not starters.empty else None
    latest = []
    if latest_game is not None:
        for row in starters[starters["game_pk"].eq(latest_game)].sort_values("batting_order").itertuples():
            latest.append(int(row.batter))
    pool = [row["player_id"] for row in eligible if row["player_id"] in hitter_map]
    optimized_roster = _position_valid_roster(pool[:12], hitter_map, positions)
    optimized = _optimized_lineup(optimized_roster, hitter_map)
    candidates = [("Recent consensus", consensus), ("Latest observed", latest), ("Run-expectancy candidate", optimized)]
    output = []
    observed_positions = {
        row["player_id"]: {item["position"] for item in row["positions"]}
        for row in positions
    }
    for label, player_ids in candidates:
        unique = list(dict.fromkeys(player_ids))[:9]
        if len(unique) < 9:
            unique.extend(player_id for player_id in pool if player_id not in unique and len(unique) < 9)
        assignment = _position_assignment(unique, observed_positions)
        lineup = [{
            "slot": index + 1, "player_id": player_id,
            "name": names.get(player_id, f"Batter {player_id}"),
            "position": assignment.get(player_id, "DH/PH unknown"),
        } for index, player_id in enumerate(unique)]
        output.append({
            "label": label, "lineup": lineup,
            "projected_runs_per_game": _simulate_runs(unique, hitter_map),
            "constraint_status": (
                "PASS: all eight observed defensive positions can be assigned; ninth hitter is labeled DH/PH unknown."
                if len(assignment) == 8 else
                "LIMITED: this observed candidate cannot cover all eight defensive positions from local position records."
            ),
        })
    return output


def _consensus_lineup(players: list[dict[str, Any]]) -> list[int]:
    selected: list[int] = []
    for slot in range(1, 10):
        ranked = sorted(players, key=lambda row: row["order_probabilities"].get(str(slot), 0), reverse=True)
        match = next((row["player_id"] for row in ranked if row["player_id"] not in selected), None)
        if match is not None:
            selected.append(match)
    return selected


def _shape_lineup(player_ids: list[int], hitters: dict[int, dict[str, Any]]) -> list[int]:
    if len(player_ids) < 3:
        return player_ids
    by_obp = sorted(player_ids, key=lambda pid: hitters[pid].get("obp") or 0, reverse=True)
    by_power = sorted(player_ids, key=lambda pid: hitters[pid].get("slg") or 0, reverse=True)
    front = [by_obp[0], by_obp[1], by_power[0]]
    return list(dict.fromkeys(front + by_power + by_obp))[:len(player_ids)]


def _optimized_lineup(player_ids: list[int], hitters: dict[int, dict[str, Any]]) -> list[int]:
    if len(player_ids) < 9:
        return _shape_lineup(player_ids, hitters)
    seeds = [
        _shape_lineup(player_ids, hitters),
        sorted(player_ids, key=lambda pid: hitters[pid].get("obp") or 0, reverse=True),
        sorted(player_ids, key=lambda pid: hitters[pid].get("slg") or 0, reverse=True),
        sorted(player_ids, key=lambda pid: _lineup_value(hitters[pid]), reverse=True),
    ]
    candidates: list[list[int]] = []
    for seed in seeds:
        candidates.extend(seed[offset:] + seed[:offset] for offset in range(9))
    return max(candidates, key=lambda lineup: _simulate_runs(lineup, hitters, games=120) or 0)


def _position_valid_roster(player_ids: list[int], hitters: dict[int, dict[str, Any]], position_rows: list[dict[str, Any]]) -> list[int]:
    position_sets = {
        row["player_id"]: {item["position"] for item in row["positions"]}
        for row in position_rows
    }
    valid = [player_id for player_id in player_ids if player_id in hitters]
    if len(valid) < 9:
        return valid
    rosters = [list(roster) for roster in combinations(valid, 9) if len(_position_assignment(list(roster), position_sets)) == 8]
    if not rosters:
        return valid[:9]
    return max(rosters, key=lambda roster: sum(_lineup_value(hitters[player_id]) for player_id in roster))


def _position_assignment(player_ids: list[int], position_sets: dict[int, set[str]]) -> dict[int, str]:
    required = ["C", "SS", "2B", "3B", "1B", "CF", "LF", "RF"]

    def assign(index: int, used: set[int], result: dict[int, str]) -> dict[int, str] | None:
        if index == len(required):
            return result.copy()
        position = required[index]
        candidates = [player_id for player_id in player_ids if player_id not in used and position in position_sets.get(player_id, set())]
        for player_id in candidates:
            used.add(player_id)
            result[player_id] = position
            matched = assign(index + 1, used, result)
            if matched is not None:
                return matched
            used.remove(player_id)
            result.pop(player_id, None)
        return None

    return assign(0, set(), {}) or {}


def _lineup_value(hitter: dict[str, Any]) -> float:
    return float(hitter.get("obp") or 0) * 0.58 + float(hitter.get("slg") or 0) * 0.42


def _event_rates(pa: pd.DataFrame) -> dict[str, float]:
    events = pa["events"]
    total = max(len(events), 1)
    categories = {
        "walk": events.isin({"walk", "intent_walk", "hit_by_pitch"}),
        "single": events.eq("single"), "double": events.eq("double"),
        "triple": events.eq("triple"), "home_run": events.eq("home_run"),
    }
    rates = {key: float(mask.sum() / total) for key, mask in categories.items()}
    rates["out"] = max(0.0, 1 - sum(rates.values()))
    return rates


def _simulate_runs(player_ids: list[int], hitters: dict[int, dict[str, Any]], games: int = 400) -> float | None:
    if len(player_ids) < 9 or any(player_id not in hitters for player_id in player_ids):
        return None
    rng = np.random.default_rng(20260902)
    total_runs = 0
    for _ in range(games):
        slot = 0
        for _inning in range(9):
            outs = 0
            bases = [False, False, False]
            while outs < 3:
                rates = hitters[player_ids[slot]]["event_rates"]
                slot = (slot + 1) % 9
                keys = ["out", "walk", "single", "double", "triple", "home_run"]
                probabilities = np.array([rates[key] for key in keys], dtype=float)
                probabilities /= probabilities.sum()
                outcome = rng.choice(keys, p=probabilities)
                if outcome == "out":
                    outs += 1
                elif outcome == "walk":
                    if all(bases): total_runs += 1
                    bases = [True, bases[0] or bases[1], bases[1] or bases[2]]
                elif outcome == "single":
                    total_runs += int(bases[1]) + int(bases[2]); bases = [True, bases[0], False]
                elif outcome == "double":
                    total_runs += sum(bases); bases = [False, True, False]
                elif outcome == "triple":
                    total_runs += sum(bases); bases = [False, False, True]
                else:
                    total_runs += sum(bases) + 1; bases = [False, False, False]
    return round(total_runs / games, 2)


def _limitations() -> list[str]:
    return [
        "Batting order is reconstructed from the observed PA sequence; it is descriptive, not causal.",
        "Defensive positions are reconstructed from fielder IDs. Players without fielding records are labeled DH/PH unknown because those roles cannot be separated locally.",
        "Lineup probabilities use recent observed starters; active roster, injuries and official probable starters are not available locally.",
        "Run projections are empirical PA-outcome simulations for scenario comparison, not an official forecast or causal estimate.",
    ]
