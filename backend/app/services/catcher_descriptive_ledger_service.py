from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd
import requests

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table


CONTRACT_VERSION = "catcher_descriptive_slice1_ledger_v1"
DEFAULT_YEARS = tuple(range(2021, 2027))
EVENT_COLUMNS = ["outs", "bf", "home_runs", "walks_unintentional", "intentional_walks", "walks_total", "hit_by_pitch", "strikeouts"]
RUN_COLUMNS = ["runs_scored_while_pair", "pitcher_charged_runs", "earned_runs"]
NON_BF_EVENT_TYPES = {
    "balk",
    "caught_stealing_2b",
    "caught_stealing_3b",
    "caught_stealing_home",
    "game_advisory",
    "other_out",
    "passed_ball",
    "pickoff_1b",
    "pickoff_2b",
    "pickoff_3b",
    "pickoff_error_1b",
    "pickoff_error_2b",
    "pickoff_error_3b",
    "pickoff_error_home",
    "pickoff_caught_stealing_2b",
    "pickoff_caught_stealing_3b",
    "pickoff_caught_stealing_home",
    "stolen_base_2b",
    "stolen_base_3b",
    "stolen_base_home",
    "wild_pitch",
}


def slice1_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice1"


def snapshot_path(year: int, game_pk: int, data_dir: Path | None = None) -> Path:
    return slice1_root(data_dir) / "raw_game_feeds" / str(int(year)) / f"{int(game_pk)}.json.gz"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_with_retry(temporary: Path, target: Path, attempts: int = 8) -> None:
    for attempt in range(attempts):
        try:
            temporary.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(min(0.05 * (2**attempt), 1.0))


def _atomic_write_gzip(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.{time.time_ns()}.tmp")
    with gzip.open(temporary, "wb", compresslevel=6) as handle:
        handle.write(payload)
    try:
        _replace_with_retry(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        _replace_with_retry(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_snapshot(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rb") as handle:
        return json.loads(handle.read())


def _game_inventory(year: int, data_dir: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        raise RuntimeError(f"DuckDB not found: {db_path}")
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            raise RuntimeError(f"Pitch table not found: {db_path}")
        return connection.execute(
            f"""
            SELECT CAST(game_pk AS BIGINT) AS game_pk,
                   MIN(CAST(game_date AS DATE)) AS game_date,
                   COUNT(*) AS local_pitches,
                   COUNT(*) FILTER (WHERE events IS NOT NULL) AS local_terminal_rows
            FROM {table}
            WHERE game_type = 'R' AND game_pk IS NOT NULL
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchdf()


def _fetch_one_snapshot(year: int, game_pk: int, target: Path, timeout: int = 90) -> dict[str, Any]:
    url = f"https://statsapi.mlb.com/api/v1.1/game/{int(game_pk)}/feed/live"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            payload = response.content
            parsed = response.json()
            returned_pk = parsed.get("gamePk") or ((parsed.get("gameData") or {}).get("game") or {}).get("pk")
            if returned_pk is not None and int(returned_pk) != int(game_pk):
                raise RuntimeError(f"gamePk mismatch: requested {game_pk}, received {returned_pk}")
            if not ((parsed.get("liveData") or {}).get("plays") or {}).get("allPlays"):
                raise RuntimeError(f"Official feed has no allPlays for game {game_pk}")
            _atomic_write_gzip(target, payload)
            return {
                "game_pk": int(game_pk),
                "status": "downloaded",
                "http_status": int(response.status_code),
                "uncompressed_bytes": len(payload),
                "payload_sha256": _sha256_bytes(payload),
            }
        except Exception as exc:  # retried and reported; never silently skipped
            last_error = exc
            if attempt < 3:
                time.sleep(0.5 * (2**attempt))
    return {"game_pk": int(game_pk), "status": "failed", "error": str(last_error)}


def snapshot_official_game_feeds(
    year: int,
    data_dir: Path | None = None,
    workers: int = 12,
    progress_every: int = 100,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    games = _game_inventory(year, root)
    targets = {int(row.game_pk): snapshot_path(year, int(row.game_pk), root) for row in games.itertuples()}
    status_path = slice1_root(root) / "status" / f"catcher_ledger_{year}.json"
    existing: list[int] = []
    invalid: list[dict[str, Any]] = []
    missing: list[int] = []
    for game_pk, path in targets.items():
        if not path.exists():
            missing.append(game_pk)
            continue
        try:
            payload = _read_snapshot(path)
            plays = (((payload.get("liveData") or {}).get("plays") or {}).get("allPlays") or [])
            if not plays:
                raise ValueError("allPlays is empty")
            existing.append(game_pk)
        except Exception as exc:
            invalid.append({"game_pk": game_pk, "error": str(exc)})
            missing.append(game_pk)

    results: list[dict[str, Any]] = []
    _atomic_write_json(
        status_path,
        {
            "contract_version": CONTRACT_VERSION,
            "season": int(year),
            "status": "downloading",
            "stage": "official_game_feeds",
            "expected_games": int(len(games)),
            "available_snapshots": len(existing),
            "remaining_games": len(missing),
            "failed_games": [],
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        futures = {
            executor.submit(_fetch_one_snapshot, year, game_pk, targets[game_pk]): game_pk
            for game_pk in missing
        }
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 25 == 0 or index == len(missing):
                downloaded = sum(row["status"] == "downloaded" for row in results)
                failures_so_far = [row for row in results if row["status"] == "failed"]
                _atomic_write_json(
                    status_path,
                    {
                        "contract_version": CONTRACT_VERSION,
                        "season": int(year),
                        "status": "downloading",
                        "stage": "official_game_feeds",
                        "expected_games": int(len(games)),
                        "available_snapshots": len(existing) + downloaded,
                        "remaining_games": max(0, len(missing) - index),
                        "failed_games": failures_so_far,
                        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )
            if progress_every and index % progress_every == 0:
                print(f"[{year}] official feeds {index}/{len(missing)} completed", flush=True)

    failures = sorted(
        (row for row in results if row["status"] == "failed"),
        key=lambda row: row["game_pk"],
    )
    completed = sorted(set(existing) | {row["game_pk"] for row in results if row["status"] == "downloaded"})
    rows: list[dict[str, Any]] = []
    for game in games.itertuples():
        game_pk = int(game.game_pk)
        path = targets[game_pk]
        row = {
            "season": int(year),
            "game_pk": game_pk,
            "game_date": str(game.game_date)[:10],
            "local_pitches": int(game.local_pitches),
            "local_terminal_rows": int(game.local_terminal_rows),
            "snapshot_path": str(path),
            "status": "available" if game_pk in completed else "failed",
            "compressed_bytes": path.stat().st_size if path.exists() else None,
            "snapshot_sha256": _sha256_file(path) if path.exists() else None,
        }
        rows.append(row)
    manifest_frame = pd.DataFrame(rows)
    manifest_dir = slice1_root(root) / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv = manifest_dir / f"official_game_feeds_{year}.csv.gz"
    manifest_frame.to_csv(manifest_csv, index=False, compression="gzip")
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "season": int(year),
        "expected_games": int(len(games)),
        "available_snapshots": int(len(completed)),
        "downloaded_this_run": sum(row["status"] == "downloaded" for row in results),
        "preexisting_valid_snapshots": len(existing),
        "invalid_preexisting_snapshots": invalid,
        "failed_games": failures,
        "complete": len(completed) == len(games) and not failures,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_csv": str(manifest_csv),
    }
    _atomic_write_json(manifest_dir / f"official_game_feeds_{year}.json", manifest)
    _atomic_write_json(
        status_path,
        {
            **manifest,
            "status": "snapshots_complete" if manifest["complete"] else "snapshot_failures",
            "stage": "official_game_feeds",
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    return manifest


def _safe_int(value: Any) -> int | None:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _team_context(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    game_teams = ((payload.get("gameData") or {}).get("teams") or {})
    box_teams = (((payload.get("liveData") or {}).get("boxscore") or {}).get("teams") or {})
    result: dict[str, dict[str, Any]] = {}
    for side in ("home", "away"):
        game_team = game_teams.get(side) or {}
        box_team = box_teams.get(side) or {}
        team = box_team.get("team") or game_team
        result[side] = {
            "team_id": _safe_int(team.get("id")),
            "team_abbr": team.get("abbreviation") or game_team.get("abbreviation"),
            "players": box_team.get("players") or {},
            "pitchers": [_safe_int(value) for value in (box_team.get("pitchers") or []) if _safe_int(value) is not None],
        }
    return result


def _people(payload: dict[str, Any]) -> dict[int, str]:
    people: dict[int, str] = {}
    for team in _team_context(payload).values():
        for player in team["players"].values():
            person = player.get("person") or {}
            player_id = _safe_int(person.get("id"))
            if player_id is not None:
                people[player_id] = person.get("fullName") or str(player_id)
    return people


def _starting_catcher(team: dict[str, Any]) -> int | None:
    candidates: list[tuple[int, int]] = []
    for player in team["players"].values():
        person = player.get("person") or {}
        player_id = _safe_int(person.get("id"))
        if player_id is None:
            continue
        positions = player.get("allPositions") or []
        is_catcher = bool(positions) and str(positions[0].get("code")) == "2"
        batting_order = str(player.get("battingOrder") or "")
        is_substitute = bool((player.get("gameStatus") or {}).get("isSubstitute"))
        if is_catcher and batting_order and not is_substitute:
            candidates.append((_safe_int(batting_order) or 9999, player_id))
    return sorted(candidates)[0][1] if candidates else None


def _pitcher_controls(payload: dict[str, Any], season: int, game_pk: int, game_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for side, team in _team_context(payload).items():
        for player in team["players"].values():
            stats = ((player.get("stats") or {}).get("pitching") or {})
            person = player.get("person") or {}
            pitcher_id = _safe_int(person.get("id"))
            if pitcher_id is None or not stats:
                continue
            rows.append(
                {
                    "season": season,
                    "game_pk": game_pk,
                    "game_date": game_date,
                    "pitching_team_id": team["team_id"],
                    "pitching_team_abbr": team["team_abbr"],
                    "home_away": side,
                    "pitcher_id": pitcher_id,
                    "pitcher_name": person.get("fullName"),
                    "outs": _safe_int(stats.get("outs")),
                    "bf": _safe_int(stats.get("battersFaced")),
                    "runs": _safe_int(stats.get("runs")),
                    "earned_runs": _safe_int(stats.get("earnedRuns")),
                    "home_runs": _safe_int(stats.get("homeRuns")),
                    "walks_total": _safe_int(stats.get("baseOnBalls")),
                    "intentional_walks": _safe_int(stats.get("intentionalWalks")),
                    "hit_by_pitch": _safe_int(stats.get("hitByPitch") if stats.get("hitByPitch") is not None else stats.get("hitBatsmen")),
                    "strikeouts": _safe_int(stats.get("strikeOuts")),
                }
            )
    return rows


def _statcast_pa_map(year: int, data_dir: Path) -> dict[tuple[int, int], dict[str, Any]]:
    db_path = get_season_duckdb_path(year, data_dir)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        frame = connection.execute(
            f"""
            SELECT CAST(game_pk AS BIGINT) AS game_pk,
                   CAST(at_bat_number AS BIGINT) AS at_bat_number,
                   arg_max(CAST(pitcher AS BIGINT), pitch_number) AS terminal_pitcher_id,
                   arg_max(CAST(fielder_2 AS BIGINT), pitch_number) AS terminal_catcher_id,
                   arg_max(events, pitch_number) AS statcast_event,
                   COUNT(DISTINCT pitcher) AS pitcher_count,
                   COUNT(*) AS pitch_count
            FROM {table}
            WHERE game_type = 'R' AND game_pk IS NOT NULL AND at_bat_number IS NOT NULL
            GROUP BY 1, 2
            """
        ).fetchdf()
    return {
        (int(row.game_pk), int(row.at_bat_number)): {
            "terminal_pitcher_id": _safe_int(row.terminal_pitcher_id),
            "terminal_catcher_id": _safe_int(row.terminal_catcher_id),
            "statcast_event": row.statcast_event,
            "pitcher_count": int(row.pitcher_count),
            "pitch_count": int(row.pitch_count),
        }
        for row in frame.itertuples()
    }


def _credited_event_pitcher(
    event_type: str,
    terminal_pitcher_id: int | None,
    substitutions: list[dict[str, Any]],
) -> tuple[int | None, str]:
    for substitution in substitutions:
        count = substitution.get("count") or {}
        previous_pitcher = _safe_int(substitution.get("previous_pitcher_id"))
        balls = _safe_int(count.get("balls")) or 0
        strikes = _safe_int(count.get("strikes")) or 0
        if event_type in {"walk", "intent_walk"} and (balls == 3 or (balls == 2 and strikes <= 1)):
            return previous_pitcher, "inherited_walk_count"
    return terminal_pitcher_id, "terminal_pitcher"


def _unresolved_runner_origin_type(
    inning: int | None,
    scheduled_innings: int | None,
    origin_base: str | None,
) -> str:
    """Classify an untracked runner without assuming every game is nine innings."""
    if (
        origin_base is not None
        and inning is not None
        and scheduled_innings is not None
        and inning > scheduled_innings
    ):
        return "automatic_runner"
    return "unresolved_runner_origin"


def _parse_game(
    season: int,
    game_pk: int,
    payload: dict[str, Any],
    statcast: dict[tuple[int, int], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    plays = ((((payload.get("liveData") or {}).get("plays") or {}).get("allPlays")) or [])
    teams = _team_context(payload)
    people = _people(payload)
    game_date = str((((payload.get("gameData") or {}).get("datetime") or {}).get("officialDate")) or "")[:10]
    scheduled_innings = _safe_int(
        (((payload.get("liveData") or {}).get("linescore") or {}).get("scheduledInnings"))
        or (((payload.get("gameData") or {}).get("game") or {}).get("scheduledInnings"))
    )
    controls = _pitcher_controls(payload, season, game_pk, game_date)
    active_pitcher = {side: (team["pitchers"][0] if team["pitchers"] else None) for side, team in teams.items()}
    active_catcher = {side: _starting_catcher(team) for side, team in teams.items()}
    runner_origins: dict[str, dict[int, dict[str, Any]]] = {"home": {}, "away": {}}
    last_half_key: tuple[int, str] | None = None
    pa_rows: list[dict[str, Any]] = []
    out_rows: list[dict[str, Any]] = []
    runner_rows: list[dict[str, Any]] = []
    catcher_crosscheck_mismatches = 0

    for play in plays:
        about = play.get("about") or {}
        half = "top" if about.get("isTopInning") else "bottom"
        offense_side = "away" if half == "top" else "home"
        defense_side = "home" if half == "top" else "away"
        half_key = (_safe_int(about.get("inning")) or 0, half)
        if last_half_key != half_key:
            runner_origins[offense_side] = {}
            last_half_key = half_key

        starting_pitcher_id = active_pitcher[defense_side]
        starting_catcher_id = active_catcher[defense_side]
        substitutions: list[dict[str, Any]] = []
        defensive_changes: list[dict[str, Any]] = []
        for event in play.get("playEvents") or []:
            if not event.get("isSubstitution"):
                continue
            details = event.get("details") or {}
            event_type = details.get("eventType") or ""
            player_id = _safe_int((event.get("player") or {}).get("id"))
            replaced_id = _safe_int((event.get("replacedPlayer") or {}).get("id"))
            position_code = str((event.get("position") or {}).get("code") or "")
            if event_type == "pitching_substitution" and player_id is not None:
                substitutions.append(
                    {
                        "previous_pitcher_id": active_pitcher[defense_side],
                        "new_pitcher_id": player_id,
                        "count": event.get("count") or {},
                        "event_index": _safe_int(event.get("index")) or 0,
                    }
                )
                defensive_changes.append(
                    {"event_index": _safe_int(event.get("index")) or 0, "pitcher_id": player_id}
                )
                active_pitcher[defense_side] = player_id
            if position_code == "2" and player_id is not None:
                defensive_changes.append(
                    {"event_index": _safe_int(event.get("index")) or 0, "catcher_id": player_id}
                )
                active_catcher[defense_side] = player_id
            if event_type == "offensive_substitution" and player_id is not None and replaced_id is not None:
                previous_origin = runner_origins[offense_side].pop(replaced_id, None)
                if previous_origin is not None:
                    runner_origins[offense_side][player_id] = {
                        **previous_origin,
                        "origin_type": "pinch_runner_inherited_origin",
                    }

        at_bat_number = (_safe_int(about.get("atBatIndex")) or 0) + 1
        matchup = play.get("matchup") or {}
        result = play.get("result") or {}
        event_type = str(result.get("eventType") or "")
        terminal_pitcher_id = _safe_int((matchup.get("pitcher") or {}).get("id")) or active_pitcher[defense_side]
        active_pitcher[defense_side] = terminal_pitcher_id
        catcher_id = active_catcher[defense_side]
        local = statcast.get((game_pk, at_bat_number))
        if local and local.get("terminal_catcher_id") is not None:
            if catcher_id is None:
                catcher_id = local["terminal_catcher_id"]
                active_catcher[defense_side] = catcher_id
            elif int(catcher_id) != int(local["terminal_catcher_id"]):
                catcher_crosscheck_mismatches += 1
        credited_pitcher_id, attribution_reason = _credited_event_pitcher(event_type, terminal_pitcher_id, substitutions)
        team = teams[defense_side]
        movements = [row.get("movement") or {} for row in (play.get("runners") or [])]
        out_numbers = {int(row["outNumber"]) for row in movements if row.get("isOut") and row.get("outNumber") is not None}
        outs = len(out_numbers)
        bf = int((result.get("type") or "") == "atBat" and event_type not in NON_BF_EVENT_TYPES)
        strikeout = int(event_type in {"strikeout", "strikeout_double_play"})
        walks_unintentional = int(event_type == "walk")
        intentional_walks = int(event_type == "intent_walk")
        pa_rows.append(
            {
                "season": season,
                "game_pk": game_pk,
                "game_date": game_date,
                "at_bat_number": at_bat_number,
                "inning": _safe_int(about.get("inning")),
                "half_inning": half,
                "pitching_team_id": team["team_id"],
                "pitching_team_abbr": team["team_abbr"],
                "pitcher_id": credited_pitcher_id,
                "pitcher_name": people.get(credited_pitcher_id),
                "terminal_pitcher_id": terminal_pitcher_id,
                "current_catcher_id": catcher_id,
                "current_catcher_name": people.get(catcher_id),
                "batter_id": _safe_int((matchup.get("batter") or {}).get("id")),
                "event_type": event_type,
                "pitcher_attribution_reason": attribution_reason,
                "outs": outs,
                "bf": bf,
                "home_runs": int(event_type == "home_run"),
                "walks_unintentional": walks_unintentional,
                "intentional_walks": intentional_walks,
                "walks_total": walks_unintentional + intentional_walks,
                "hit_by_pitch": int(event_type == "hit_by_pitch"),
                "strikeouts": strikeout,
                "runs_scored_while_pair": sum(bool((runner.get("details") or {}).get("isScoringEvent")) for runner in (play.get("runners") or [])),
                "statcast_joined": local is not None,
                "statcast_terminal_pitcher_id": local.get("terminal_pitcher_id") if local else None,
                "statcast_terminal_catcher_id": local.get("terminal_catcher_id") if local else None,
                "statcast_event": local.get("statcast_event") if local else None,
                "statcast_pitch_count": local.get("pitch_count") if local else None,
                "mid_pa_pitcher_change": bool(substitutions),
            }
        )

        seen_out_numbers: set[int] = set()
        for runner in play.get("runners") or []:
            movement = runner.get("movement") or {}
            out_number = _safe_int(movement.get("outNumber"))
            if not movement.get("isOut") or out_number is None or out_number in seen_out_numbers:
                continue
            seen_out_numbers.add(out_number)
            play_index = _safe_int((runner.get("details") or {}).get("playIndex"))
            out_pitcher_id = starting_pitcher_id
            out_catcher_id = starting_catcher_id
            if play_index is None:
                out_pitcher_id = terminal_pitcher_id
                out_catcher_id = catcher_id
            else:
                for change in defensive_changes:
                    if int(change["event_index"]) > play_index:
                        continue
                    out_pitcher_id = change.get("pitcher_id", out_pitcher_id)
                    out_catcher_id = change.get("catcher_id", out_catcher_id)
            out_rows.append(
                {
                    "season": season,
                    "game_pk": game_pk,
                    "game_date": game_date,
                    "at_bat_number": at_bat_number,
                    "out_number": out_number,
                    "play_index": play_index,
                    "pitching_team_id": team["team_id"],
                    "pitching_team_abbr": team["team_abbr"],
                    "pitcher_id": out_pitcher_id,
                    "pitcher_name": people.get(out_pitcher_id),
                    "catcher_id": out_catcher_id,
                    "catcher_name": people.get(out_catcher_id),
                }
            )

        origin_map = runner_origins[offense_side]
        for runner in play.get("runners") or []:
            movement = runner.get("movement") or {}
            details = runner.get("details") or {}
            runner_id = _safe_int((details.get("runner") or {}).get("id"))
            if runner_id is None:
                continue
            origin_base = movement.get("originBase")
            is_scoring = bool(details.get("isScoringEvent"))
            is_out = bool(movement.get("isOut"))
            if runner_id not in origin_map and origin_base is None:
                origin_map[runner_id] = {
                    "responsible_catcher_id": catcher_id,
                    "responsible_catcher_name": people.get(catcher_id),
                    "origin_pitcher_id": credited_pitcher_id,
                    "origin_game_pk": game_pk,
                    "origin_at_bat_number": at_bat_number,
                    "origin_type": "plate_appearance",
                }
            unresolved_origin_type = _unresolved_runner_origin_type(
                _safe_int(about.get("inning")),
                scheduled_innings,
                origin_base,
            )
            origin = origin_map.get(runner_id) or {
                "responsible_catcher_id": None,
                "responsible_catcher_name": None,
                "origin_pitcher_id": None,
                "origin_game_pk": game_pk,
                "origin_at_bat_number": None,
                "origin_type": unresolved_origin_type,
            }
            if is_scoring:
                responsible_pitcher_id = _safe_int((details.get("responsiblePitcher") or {}).get("id")) or origin.get("origin_pitcher_id")
                runner_rows.append(
                    {
                        "season": season,
                        "game_pk": game_pk,
                        "game_date": game_date,
                        "scoring_at_bat_number": at_bat_number,
                        "runner_id": runner_id,
                        "runner_name": (details.get("runner") or {}).get("fullName") or people.get(runner_id),
                        "pitching_team_id": team["team_id"],
                        "pitching_team_abbr": team["team_abbr"],
                        "current_pitcher_id": terminal_pitcher_id,
                        "current_catcher_id": catcher_id,
                        "responsible_pitcher_id": responsible_pitcher_id,
                        "responsible_pitcher_name": people.get(responsible_pitcher_id),
                        "responsible_catcher_id": origin.get("responsible_catcher_id"),
                        "responsible_catcher_name": origin.get("responsible_catcher_name"),
                        "origin_at_bat_number": origin.get("origin_at_bat_number"),
                        "origin_type": origin.get("origin_type"),
                        "earned": bool(details.get("earned")),
                        "team_unearned": bool(details.get("teamUnearned")),
                    }
                )
            if is_scoring or is_out:
                origin_map.pop(runner_id, None)

    diagnostics = {
        "season": season,
        "game_pk": game_pk,
        "official_pa_rows": len(plays),
        "official_out_rows": len(out_rows),
        "statcast_joined_pa_rows": sum(bool(row["statcast_joined"]) for row in pa_rows),
        "catcher_crosscheck_mismatches": catcher_crosscheck_mismatches,
        "unresolved_pa_catcher_rows": sum(row["current_catcher_id"] is None for row in pa_rows),
        "scoring_runner_rows": len(runner_rows),
        "unresolved_responsible_catcher_runs": sum(row["responsible_catcher_id"] is None for row in runner_rows),
    }
    return pa_rows, out_rows, runner_rows, controls, diagnostics


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _aggregate_ledger(pa: pd.DataFrame, outs: pd.DataFrame, runners: pd.DataFrame) -> pd.DataFrame:
    keys = ["season", "pitching_team_id", "pitching_team_abbr", "pitcher_id", "catcher_id"]
    event = pa.rename(columns={"current_catcher_id": "catcher_id"}).copy()
    event = event.dropna(subset=["pitcher_id", "catcher_id"])
    event_agg = event.groupby(keys, dropna=False).agg(
        pa_rows=("at_bat_number", "size"),
        **{column: (column, "sum") for column in EVENT_COLUMNS if column != "outs"},
    ).reset_index()
    out_agg = outs.dropna(subset=["pitcher_id", "catcher_id"]).groupby(keys, dropna=False).agg(
        outs=("out_number", "size")
    ).reset_index()
    presence = pd.concat(
        [event[[*keys, "game_pk"]], outs[[*keys, "game_pk"]]], ignore_index=True
    ).drop_duplicates().groupby(keys, dropna=False).agg(games=("game_pk", "size")).reset_index()
    identities = pd.concat(
        [
            event[[*keys, "pitcher_name", "current_catcher_name"]].rename(
                columns={"current_catcher_name": "catcher_name"}
            ),
            outs[[*keys, "pitcher_name", "catcher_name"]],
        ],
        ignore_index=True,
    ).groupby(keys, dropna=False).agg(
        pitcher_name=("pitcher_name", "first"), catcher_name=("catcher_name", "first")
    ).reset_index()
    event_agg = event_agg.merge(out_agg, on=keys, how="outer").merge(presence, on=keys, how="outer")
    event_agg = event_agg.merge(identities, on=keys, how="left")
    current_runs = pa.drop(columns=["pitcher_id", "pitcher_name"]).rename(
        columns={"terminal_pitcher_id": "pitcher_id", "current_catcher_id": "catcher_id"}
    ).groupby(keys, dropna=False).agg(
        runs_scored_while_pair=("runs_scored_while_pair", "sum")
    ).reset_index()
    event_agg = event_agg.merge(current_runs, on=keys, how="outer")
    responsibility = runners.rename(
        columns={"responsible_pitcher_id": "pitcher_id", "responsible_catcher_id": "catcher_id"}
    ).copy()
    responsibility["pitcher_charged_runs"] = 1
    responsibility["earned_runs"] = responsibility["earned"].astype(int)
    responsibility_agg = responsibility.groupby(keys, dropna=False).agg(
        pitcher_charged_runs=("pitcher_charged_runs", "sum"),
        earned_runs=("earned_runs", "sum"),
    ).reset_index()
    ledger = event_agg.merge(responsibility_agg, on=keys, how="outer")
    for column in ["games", "pa_rows", *EVENT_COLUMNS, *RUN_COLUMNS]:
        if column not in ledger:
            ledger[column] = 0
        ledger[column] = pd.to_numeric(ledger[column], errors="coerce").fillna(0).astype("int64")
    ledger["display_ip"] = ledger["outs"].map(lambda value: f"{int(value)//3}.{int(value)%3}")
    ledger["responsibility_catcher_available"] = ledger["catcher_id"].notna()
    ledger["contract_version"] = CONTRACT_VERSION
    return ledger.sort_values(keys, na_position="last").reset_index(drop=True)


def _reconciliation(
    pa: pd.DataFrame,
    outs: pd.DataFrame,
    runners: pd.DataFrame,
    controls: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["season", "game_pk", "pitcher_id"]
    pa_sums = pa.groupby(keys, dropna=False)[[column for column in EVENT_COLUMNS if column != "outs"]].sum().reset_index()
    out_sums = outs.groupby(keys, dropna=False).agg(outs=("out_number", "size")).reset_index()
    pa_sums = pa_sums.merge(out_sums, on=keys, how="outer")
    run_sums = runners.groupby(
        ["season", "game_pk", "responsible_pitcher_id"], dropna=False
    ).agg(runs=("runner_id", "size"), earned_runs=("earned", "sum")).reset_index().rename(
        columns={"responsible_pitcher_id": "pitcher_id"}
    )
    derived = pa_sums.merge(run_sums, on=keys, how="outer")
    compared = controls.merge(derived, on=keys, how="outer", suffixes=("_official", "_derived"), indicator=True)
    metrics = ["outs", "bf", "runs", "earned_runs", "home_runs", "walks_total", "intentional_walks", "hit_by_pitch", "strikeouts"]
    for metric in metrics:
        compared[f"{metric}_official"] = pd.to_numeric(compared.get(f"{metric}_official"), errors="coerce")
        compared[f"{metric}_derived"] = pd.to_numeric(compared.get(f"{metric}_derived"), errors="coerce").fillna(0)
        compared[f"{metric}_difference"] = compared[f"{metric}_derived"] - compared[f"{metric}_official"]
    compared["all_metrics_match"] = compared[[f"{metric}_difference" for metric in metrics]].fillna(0).eq(0).all(axis=1)
    return compared


def _ledger_control_differences(
    ledger: pd.DataFrame,
    controls: pd.DataFrame,
    group_keys: list[str],
) -> dict[str, int]:
    metric_map = {
        "outs": "outs",
        "bf": "bf",
        "home_runs": "home_runs",
        "walks_total": "walks_total",
        "intentional_walks": "intentional_walks",
        "hit_by_pitch": "hit_by_pitch",
        "strikeouts": "strikeouts",
        "pitcher_charged_runs": "runs",
        "earned_runs": "earned_runs",
    }
    result: dict[str, int] = {}
    for ledger_field, control_field in metric_map.items():
        derived = ledger.groupby(group_keys, dropna=False)[ledger_field].sum().reset_index(name="derived")
        official = controls.groupby(group_keys, dropna=False)[control_field].sum().reset_index(name="official")
        compared = derived.merge(official, on=group_keys, how="outer").fillna(0)
        result[ledger_field] = int((compared["derived"] - compared["official"]).abs().sum())
    return result


def build_slice1_year(year: int, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    inventory = _game_inventory(year, root)
    status_path = slice1_root(root) / "status" / f"catcher_ledger_{year}.json"
    _atomic_write_json(
        status_path,
        {
            "contract_version": CONTRACT_VERSION,
            "season": int(year),
            "status": "building",
            "stage": "pa_runner_ledger",
            "expected_games": int(len(inventory)),
            "available_snapshots": int(len(inventory)),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    statcast = _statcast_pa_map(year, root)
    all_pa: list[dict[str, Any]] = []
    all_outs: list[dict[str, Any]] = []
    all_runners: list[dict[str, Any]] = []
    all_controls: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    missing: list[int] = []
    game_ids = inventory["game_pk"].astype(int).tolist()
    for processed_games, game_pk in enumerate(game_ids, start=1):
        path = snapshot_path(year, game_pk, root)
        if not path.exists():
            missing.append(game_pk)
            continue
        pa, outs, runners, controls, game_diagnostics = _parse_game(year, game_pk, _read_snapshot(path), statcast)
        all_pa.extend(pa)
        all_outs.extend(outs)
        all_runners.extend(runners)
        all_controls.extend(controls)
        diagnostics.append(game_diagnostics)
        if processed_games % 25 == 0 or processed_games == len(game_ids):
            _atomic_write_json(
                status_path,
                {
                    "contract_version": CONTRACT_VERSION,
                    "season": int(year),
                    "status": "building",
                    "stage": "pa_runner_ledger",
                    "expected_games": int(len(inventory)),
                    "available_snapshots": int(len(inventory)),
                    "processed_games": int(processed_games),
                    "remaining_games": int(len(game_ids) - processed_games),
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
    if missing:
        raise RuntimeError(f"Missing official snapshots for {year}: {len(missing)} games; first={missing[:10]}")

    pa_frame = pd.DataFrame(all_pa)
    out_frame = pd.DataFrame(all_outs)
    runner_frame = pd.DataFrame(all_runners)
    control_frame = pd.DataFrame(all_controls)
    diagnostic_frame = pd.DataFrame(diagnostics)
    ledger = _aggregate_ledger(pa_frame, out_frame, runner_frame)
    reconciliation = _reconciliation(pa_frame, out_frame, runner_frame, control_frame)
    pitcher_team_differences = _ledger_control_differences(
        ledger,
        control_frame,
        ["season", "pitching_team_id", "pitcher_id"],
    )
    team_differences = _ledger_control_differences(
        ledger,
        control_frame,
        ["season", "pitching_team_id"],
    )
    output = slice1_root(root) / "yearly"
    paths = {
        "pa": output / f"pa_accounting_{year}.parquet",
        "outs": output / f"out_responsibility_{year}.parquet",
        "runners": output / f"runner_responsibility_{year}.parquet",
        "controls": output / f"pitcher_game_controls_{year}.parquet",
        "ledger": output / f"pitcher_catcher_ledger_{year}.parquet",
        "reconciliation": output / f"reconciliation_{year}.parquet",
        "game_diagnostics": output / f"game_diagnostics_{year}.parquet",
    }
    for name, frame in {
        "pa": pa_frame,
        "outs": out_frame,
        "runners": runner_frame,
        "controls": control_frame,
        "ledger": ledger,
        "reconciliation": reconciliation,
        "game_diagnostics": diagnostic_frame,
    }.items():
        _write_parquet(frame, paths[name])
    metric_differences = [column for column in reconciliation if column.endswith("_difference")]
    unresolved_nonautomatic_runs = int(
        runner_frame.loc[
            runner_frame["responsible_catcher_id"].isna()
            & runner_frame["origin_type"].ne("automatic_runner")
        ].shape[0]
    )
    duplicate_ledger_keys = int(
        ledger.duplicated(["season", "pitching_team_id", "pitcher_id", "catcher_id"]).sum()
    )
    duplicate_out_keys = int(
        out_frame.duplicated(["season", "game_pk", "at_bat_number", "out_number"]).sum()
    )
    completion_gate_passed = bool(
        reconciliation["all_metrics_match"].all()
        and not pa_frame.duplicated(["season", "game_pk", "at_bat_number"]).any()
        and duplicate_out_keys == 0
        and duplicate_ledger_keys == 0
        and not pa_frame["current_catcher_id"].isna().any()
        and not out_frame[["pitcher_id", "catcher_id"]].isna().any().any()
        and int(diagnostic_frame["catcher_crosscheck_mismatches"].sum()) == 0
        and unresolved_nonautomatic_runs == 0
        and all(value == 0 for value in pitcher_team_differences.values())
        and all(value == 0 for value in team_differences.values())
    )
    summary = {
        "season": year,
        "games": int(len(inventory)),
        "official_play_rows": int(len(pa_frame)),
        "official_pa_rows": int(len(pa_frame)),
        "official_out_rows": int(len(out_frame)),
        "official_bf": int(control_frame["bf"].sum()),
        "statcast_joined_pa_rows": int(pa_frame["statcast_joined"].sum()),
        "scoring_runner_rows": int(len(runner_frame)),
        "unresolved_pa_catcher_rows": int(pa_frame["current_catcher_id"].isna().sum()),
        "unresolved_responsible_catcher_runs": int(runner_frame["responsible_catcher_id"].isna().sum()),
        "unresolved_nonautomatic_responsible_catcher_runs": unresolved_nonautomatic_runs,
        "catcher_crosscheck_mismatches": int(diagnostic_frame["catcher_crosscheck_mismatches"].sum()),
        "pitcher_game_control_rows": int(len(control_frame)),
        "pitcher_catcher_rows": int(len(ledger)),
        "duplicate_pa_keys": int(pa_frame.duplicated(["season", "game_pk", "at_bat_number"]).sum()),
        "duplicate_out_keys": duplicate_out_keys,
        "duplicate_ledger_keys": duplicate_ledger_keys,
        "reconciliation_rows": int(len(reconciliation)),
        "reconciliation_all_match_rows": int(reconciliation["all_metrics_match"].sum()),
        "metric_absolute_differences": {
            column.removesuffix("_difference"): int(pd.to_numeric(reconciliation[column], errors="coerce").abs().sum())
            for column in metric_differences
        },
        "ledger_to_pitcher_team_absolute_differences": pitcher_team_differences,
        "ledger_to_team_absolute_differences": team_differences,
        "completion_gate_passed": completion_gate_passed,
        "paths": {name: str(path) for name, path in paths.items()},
    }
    _atomic_write_json(
        status_path,
        {
            "contract_version": CONTRACT_VERSION,
            "season": int(year),
            "status": "completed" if completion_gate_passed else "failed_reconciliation",
            "stage": "reconciled_year_ledger" if completion_gate_passed else "reconciliation_gate",
            "expected_games": int(len(inventory)),
            "available_snapshots": int(len(inventory)),
            "summary": summary,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    if not completion_gate_passed:
        raise RuntimeError(f"Catcher ledger reconciliation gate failed for {year}; inspect {paths['reconciliation']}")
    return summary


def _concat_parquets(paths: Iterable[Path]) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in paths]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def consolidate_slice1(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    yearly = slice1_root(root) / "yearly"
    selected = tuple(
        year for year in DEFAULT_YEARS if (yearly / f"pitcher_catcher_ledger_{year}.parquet").exists()
    )
    if not selected:
        raise RuntimeError("No completed yearly catcher ledgers are available to consolidate.")
    ledger = _concat_parquets(yearly / f"pitcher_catcher_ledger_{year}.parquet" for year in selected)
    pa = _concat_parquets(yearly / f"pa_accounting_{year}.parquet" for year in selected)
    reconciliation = _concat_parquets(yearly / f"reconciliation_{year}.parquet" for year in selected)
    output_root = slice1_root(root)
    ledger_path = output_root / "pitcher_catcher_ledger_2021_2026.parquet"
    _write_parquet(ledger, ledger_path)

    catcher_keys = ["season", "pitching_team_id", "pitching_team_abbr", "catcher_id"]
    catcher_ledger = ledger.dropna(subset=["catcher_id"]).groupby(catcher_keys, dropna=False).agg(
        catcher_name=("catcher_name", "first"),
        number_of_pitchers=("pitcher_id", "nunique"),
        pa_rows=("pa_rows", "sum"),
        **{column: (column, "sum") for column in [*EVENT_COLUMNS, *RUN_COLUMNS]},
    ).reset_index()
    catcher_games = pa.dropna(subset=["current_catcher_id"]).groupby(
        ["season", "pitching_team_id", "pitching_team_abbr", "current_catcher_id"], dropna=False
    ).agg(games=("game_pk", "nunique")).reset_index().rename(columns={"current_catcher_id": "catcher_id"})
    catcher_ledger = catcher_ledger.merge(catcher_games, on=catcher_keys, how="left")
    catcher_ledger["games"] = pd.to_numeric(catcher_ledger["games"], errors="coerce").fillna(0).astype("int64")
    catcher_ledger["display_ip"] = catcher_ledger["outs"].map(lambda value: f"{int(value)//3}.{int(value)%3}")
    catcher_ledger["contract_version"] = CONTRACT_VERSION
    catcher_path = output_root / "catcher_season_team_ledger_2021_2026.parquet"
    _write_parquet(catcher_ledger, catcher_path)

    reconciliation_path = output_root / "pitcher_game_reconciliation_2021_2026.parquet"
    _write_parquet(reconciliation, reconciliation_path)
    summary = {
        "contract_version": CONTRACT_VERSION,
        "years": list(selected),
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "pitcher_catcher_rows": int(len(ledger)),
            "catcher_season_team_rows": int(len(catcher_ledger)),
        },
        "artifacts": {
            "pitcher_catcher_ledger": {"path": str(ledger_path), "sha256": _sha256_file(ledger_path)},
            "catcher_season_team_ledger": {"path": str(catcher_path), "sha256": _sha256_file(catcher_path)},
            "pitcher_game_reconciliation": {"path": str(reconciliation_path), "sha256": _sha256_file(reconciliation_path)},
        },
    }
    summary_path = output_root / "catcher_descriptive_slice1_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def run_slice1_year_update(
    year: int,
    data_dir: Path | None = None,
    workers: int = 12,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    season = int(year)
    if season not in DEFAULT_YEARS:
        raise ValueError(f"Unsupported season: {season}")
    status_path = slice1_root(root) / "status" / f"catcher_ledger_{season}.json"
    if status_path.exists() and not force_rebuild:
        try:
            existing_status = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_status = {}
        if existing_status.get("status") == "completed":
            return {
                "contract_version": CONTRACT_VERSION,
                "season": season,
                "status": "already_completed",
                "skipped": True,
                "message": f"Catcher ledger {season} is already completed; use force_rebuild=true to rebuild it.",
                "yearly_summary": existing_status.get("summary", {}),
            }
    try:
        snapshot_manifest = snapshot_official_game_feeds(season, root, workers=workers)
        if not snapshot_manifest["complete"]:
            raise RuntimeError(
                f"Official snapshot coverage incomplete for {season}: "
                f"{snapshot_manifest['available_snapshots']}/{snapshot_manifest['expected_games']}"
            )
        yearly_summary = build_slice1_year(season, root)
        consolidated = consolidate_slice1(root)
        from app.services.catcher_descriptive_metrics_service import build_catcher_descriptive_metrics, metrics_json_path

        descriptive_metrics = build_catcher_descriptive_metrics(season, root)
        reliability = None
        if all(metrics_json_path(year, root).exists() for year in DEFAULT_YEARS):
            from app.services.catcher_descriptive_reliability_service import build_catcher_descriptive_slice4_reliability

            reliability_payload = build_catcher_descriptive_slice4_reliability(DEFAULT_YEARS, root)
            reliability = {
                "contract_version": reliability_payload["contract_version"],
                "cross_year": reliability_payload["cross_year"],
                "summary": reliability_payload["summary"],
            }
        return {
            "contract_version": CONTRACT_VERSION,
            "season": season,
            "snapshot_manifest": snapshot_manifest,
            "yearly_summary": yearly_summary,
            "consolidated": consolidated,
            "descriptive_metrics": {key: value for key, value in descriptive_metrics.items() if key != "rows"},
            "reliability": reliability,
        }
    except Exception as exc:
        previous: dict[str, Any] = {}
        if status_path.exists():
            try:
                previous = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = {}
        _atomic_write_json(
            status_path,
            {
                **previous,
                "contract_version": CONTRACT_VERSION,
                "season": season,
                "status": "failed",
                "error": str(exc),
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise


def get_slice1_status(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    status_root = slice1_root(root) / "status"
    years: dict[str, dict[str, Any]] = {}
    for year in DEFAULT_YEARS:
        path = status_root / f"catcher_ledger_{year}.json"
        if path.exists():
            try:
                years[str(year)] = json.loads(path.read_text(encoding="utf-8"))
                continue
            except json.JSONDecodeError:
                pass
        snapshot_dir = slice1_root(root) / "raw_game_feeds" / str(year)
        available = len(list(snapshot_dir.glob("*.json.gz"))) if snapshot_dir.exists() else 0
        years[str(year)] = {
            "contract_version": CONTRACT_VERSION,
            "season": year,
            "status": "partial" if available else "not_started",
            "stage": "official_game_feeds" if available else None,
            "available_snapshots": available,
            "expected_games": None,
        }
    completed = sum(row.get("status") == "completed" for row in years.values())
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "completed" if completed == len(DEFAULT_YEARS) else ("partial" if any(row.get("available_snapshots") for row in years.values()) else "not_started"),
        "completed_years": completed,
        "years": years,
        "message": f"{completed}/{len(DEFAULT_YEARS)} season ledgers completed.",
    }


def build_slice1(
    years: Iterable[int] = DEFAULT_YEARS,
    data_dir: Path | None = None,
    fetch: bool = False,
    workers: int = 12,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    selected = tuple(sorted(set(int(year) for year in years)))
    results = []
    for year in selected:
        if fetch:
            results.append(run_slice1_year_update(year, root, workers=workers))
        else:
            results.append(build_slice1_year(year, root))
    consolidated = consolidate_slice1(root)
    return {"contract_version": CONTRACT_VERSION, "years": list(selected), "results": results, "consolidated": consolidated}
