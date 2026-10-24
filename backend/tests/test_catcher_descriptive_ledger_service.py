from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services.catcher_descriptive_ledger_service import (
    _aggregate_ledger,
    _atomic_write_json,
    _credited_event_pitcher,
    _parse_game,
    _reconciliation,
    _unresolved_runner_origin_type,
    run_slice1_year_update,
)


def _fixture_payload() -> dict:
    player = lambda player_id, name, position, substitute=False, order="100": {
        "person": {"id": player_id, "fullName": name},
        "allPositions": [{"code": position}],
        "battingOrder": order,
        "gameStatus": {"isSubstitute": substitute},
        "stats": {},
    }
    home_players = {
        "ID10": player(10, "Pitcher A", "1"),
        "ID20": player(20, "Catcher A", "2"),
    }
    home_players["ID10"]["stats"] = {"pitching": {"outs": 1, "battersFaced": 2, "runs": 1, "earnedRuns": 1, "homeRuns": 0, "baseOnBalls": 1, "intentionalWalks": 0, "hitByPitch": 0, "strikeOuts": 1}}
    away_players = {"ID30": player(30, "Batter", "8")}
    return {
        "gamePk": 1,
        "gameData": {
            "datetime": {"officialDate": "2026-04-01"},
            "game": {"scheduledInnings": 9},
            "teams": {
                "home": {"id": 100, "abbreviation": "HOM"},
                "away": {"id": 200, "abbreviation": "AWY"},
            },
        },
        "liveData": {
            "linescore": {"scheduledInnings": 9},
            "boxscore": {
                "teams": {
                    "home": {"team": {"id": 100, "abbreviation": "HOM"}, "players": home_players, "pitchers": [10]},
                    "away": {"team": {"id": 200, "abbreviation": "AWY"}, "players": away_players, "pitchers": []},
                }
            },
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 0, "isTopInning": True, "inning": 1},
                        "matchup": {"pitcher": {"id": 10}, "batter": {"id": 30}},
                        "result": {"type": "atBat", "eventType": "walk"},
                        "playEvents": [],
                        "runners": [{"movement": {"originBase": None, "end": "1B", "isOut": False, "outNumber": None}, "details": {"runner": {"id": 30}, "isScoringEvent": False}}],
                    },
                    {
                        "about": {"atBatIndex": 1, "isTopInning": True, "inning": 1},
                        "matchup": {"pitcher": {"id": 10}, "batter": {"id": 31}},
                        "result": {"type": "atBat", "eventType": "strikeout"},
                        "playEvents": [],
                        "runners": [
                            {"movement": {"originBase": None, "end": None, "isOut": True, "outNumber": 1}, "details": {"runner": {"id": 31}, "isScoringEvent": False}},
                            {"movement": {"originBase": "1B", "end": "score", "isOut": False, "outNumber": None}, "details": {"runner": {"id": 30}, "responsiblePitcher": {"id": 10}, "isScoringEvent": True, "earned": True, "teamUnearned": False}},
                        ],
                    },
                ]
            },
        },
    }


def test_inherited_count_event_pitcher_rules() -> None:
    substitutions = [{"previous_pitcher_id": 10, "new_pitcher_id": 11, "count": {"balls": 0, "strikes": 2}}]
    assert _credited_event_pitcher("strikeout", 11, substitutions) == (11, "terminal_pitcher")
    substitutions[0]["count"] = {"balls": 3, "strikes": 1}
    assert _credited_event_pitcher("walk", 11, substitutions) == (10, "inherited_walk_count")
    substitutions[0]["count"] = {"balls": 2, "strikes": 1}
    assert _credited_event_pitcher("walk", 11, substitutions) == (10, "inherited_walk_count")


def test_automatic_runner_uses_official_scheduled_innings() -> None:
    assert _unresolved_runner_origin_type(8, 7, "2B") == "automatic_runner"
    assert _unresolved_runner_origin_type(10, 9, "2B") == "automatic_runner"
    assert _unresolved_runner_origin_type(8, 9, "2B") == "unresolved_runner_origin"
    assert _unresolved_runner_origin_type(10, 9, None) == "unresolved_runner_origin"


def test_parse_game_preserves_responsible_catcher() -> None:
    pa, outs, runners, controls, diagnostics = _parse_game(2026, 1, _fixture_payload(), {})
    assert len(pa) == 2
    assert pa[0]["current_catcher_id"] == 20
    assert pa[1]["outs"] == 1
    assert runners == [
        {
            "season": 2026,
            "game_pk": 1,
            "game_date": "2026-04-01",
            "scoring_at_bat_number": 2,
            "runner_id": 30,
            "runner_name": "Batter",
            "pitching_team_id": 100,
            "pitching_team_abbr": "HOM",
            "current_pitcher_id": 10,
            "current_catcher_id": 20,
            "responsible_pitcher_id": 10,
            "responsible_pitcher_name": "Pitcher A",
            "responsible_catcher_id": 20,
            "responsible_catcher_name": "Catcher A",
            "origin_at_bat_number": 1,
            "origin_type": "plate_appearance",
            "earned": True,
            "team_unearned": False,
        }
    ]
    assert controls[0]["runs"] == 1
    assert outs == [
        {
            "season": 2026,
            "game_pk": 1,
            "game_date": "2026-04-01",
            "at_bat_number": 2,
            "out_number": 1,
            "play_index": None,
            "pitching_team_id": 100,
            "pitching_team_abbr": "HOM",
            "pitcher_id": 10,
            "pitcher_name": "Pitcher A",
            "catcher_id": 20,
            "catcher_name": "Catcher A",
        }
    ]
    assert diagnostics["unresolved_responsible_catcher_runs"] == 0
    reconciliation = _reconciliation(
        pd.DataFrame(pa), pd.DataFrame(outs), pd.DataFrame(runners), pd.DataFrame(controls)
    )
    assert reconciliation["all_metrics_match"].all()


def test_out_before_mid_pa_pitching_change_stays_with_previous_pitcher() -> None:
    payload = _fixture_payload()
    players = payload["liveData"]["boxscore"]["teams"]["home"]["players"]
    players["ID11"] = {
        "person": {"id": 11, "fullName": "Pitcher B"},
        "allPositions": [{"code": "1"}],
        "battingOrder": "100",
        "gameStatus": {"isSubstitute": True},
        "stats": {},
    }
    payload["liveData"]["boxscore"]["teams"]["home"]["pitchers"].append(11)
    payload["liveData"]["plays"]["allPlays"].append(
        {
            "about": {"atBatIndex": 2, "isTopInning": True, "inning": 1},
            "matchup": {"pitcher": {"id": 11}, "batter": {"id": 33}},
            "result": {"type": "atBat", "eventType": "single"},
            "playEvents": [
                {"index": 0, "isPitch": True, "details": {}, "count": {"outs": 1}},
                {"index": 1, "isPitch": False, "details": {}, "count": {"outs": 2}},
                {
                    "index": 2,
                    "isPitch": False,
                    "isSubstitution": True,
                    "details": {"eventType": "pitching_substitution"},
                    "player": {"id": 11},
                    "position": {"code": "1"},
                    "count": {"balls": 1, "strikes": 0, "outs": 2},
                },
                {"index": 3, "isPitch": True, "details": {}, "count": {"outs": 2}},
            ],
            "runners": [
                {
                    "movement": {"originBase": "1B", "end": None, "isOut": True, "outNumber": 2},
                    "details": {"runner": {"id": 32}, "isScoringEvent": False, "playIndex": 1},
                },
                {
                    "movement": {"originBase": None, "end": "1B", "isOut": False, "outNumber": None},
                    "details": {"runner": {"id": 33}, "isScoringEvent": False, "playIndex": 3},
                },
            ],
        }
    )

    pa, outs, runners, _, _ = _parse_game(2026, 1, payload, {})
    ledger = _aggregate_ledger(pd.DataFrame(pa), pd.DataFrame(outs), pd.DataFrame(runners))

    assert pa[-1]["pitcher_id"] == 11
    assert outs[-1]["pitcher_id"] == 10
    assert int(ledger.loc[ledger.pitcher_id.eq(10), "outs"].sum()) == 2
    assert int(ledger.loc[ledger.pitcher_id.eq(11), "outs"].sum()) == 0
    assert int(ledger.loc[ledger.pitcher_id.eq(11), "bf"].sum()) == 1


def test_walkoff_balk_does_not_count_as_batter_faced() -> None:
    payload = _fixture_payload()
    payload["liveData"]["plays"]["allPlays"].append(
        {
            "about": {"atBatIndex": 2, "isTopInning": True, "inning": 1},
            "matchup": {"pitcher": {"id": 10}, "batter": {"id": 32}},
            "result": {"type": "atBat", "eventType": "balk"},
            "playEvents": [],
            "runners": [],
        }
    )

    pa, _, _, _, _ = _parse_game(2026, 1, payload, {})

    assert pa[-1]["event_type"] == "balk"
    assert pa[-1]["bf"] == 0


def test_inning_ending_pickoff_error_does_not_count_as_batter_faced() -> None:
    payload = _fixture_payload()
    payload["liveData"]["plays"]["allPlays"].append(
        {
            "about": {"atBatIndex": 2, "isTopInning": True, "inning": 1},
            "matchup": {"pitcher": {"id": 10}, "batter": {"id": 32}},
            "result": {"type": "atBat", "eventType": "pickoff_error_3b"},
            "playEvents": [],
            "runners": [],
        }
    )

    pa, _, _, _, _ = _parse_game(2026, 1, payload, {})

    assert pa[-1]["event_type"] == "pickoff_error_3b"
    assert pa[-1]["bf"] == 0


def test_completed_year_update_is_noop_without_force(tmp_path, monkeypatch) -> None:
    status_dir = tmp_path / "research" / "catcher_descriptive" / "slice1" / "status"
    status_dir.mkdir(parents=True)
    (status_dir / "catcher_ledger_2024.json").write_text(
        json.dumps({"status": "completed", "summary": {"games": 2430}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.catcher_descriptive_ledger_service.snapshot_official_game_feeds",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("completed year must not restart")),
    )

    result = run_slice1_year_update(2024, data_dir=tmp_path)

    assert result["status"] == "already_completed"
    assert result["skipped"] is True
    assert result["yearly_summary"] == {"games": 2430}


def test_atomic_status_write_retries_transient_windows_lock(tmp_path, monkeypatch) -> None:
    target = tmp_path / "status.json"
    original_replace = Path.replace
    attempts = 0

    def flaky_replace(source: Path, destination: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("simulated Windows sharing violation")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr("app.services.catcher_descriptive_ledger_service.time.sleep", lambda _seconds: None)

    _atomic_write_json(target, {"status": "building", "processed_games": 50})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "building", "processed_games": 50}
    assert not list(tmp_path.glob("*.tmp"))
