import json

import pandas as pd

from app.services import batter_team_research_service as service


def test_observed_batting_order_cycles_by_team_pa_sequence():
    rows = pd.DataFrame({
        "game_pk": [1] * 10,
        "at_bat_number": list(range(1, 11)),
        "batter": list(range(101, 110)) + [101],
    })

    result = service._add_observed_order(rows)

    assert result["batting_order"].tolist() == [1, 2, 3, 4, 5, 6, 7, 8, 9, 1]


def test_position_coverage_keeps_observed_roles_and_games():
    positions = pd.DataFrame([
        {"game_pk": 1, "player_id": 10, "field_position": "C", "pitches": 80},
        {"game_pk": 2, "player_id": 10, "field_position": "C", "pitches": 70},
        {"game_pk": 3, "player_id": 10, "field_position": "1B", "pitches": 20},
    ])

    rows = service._position_rows(positions, {10: "Test Catcher"})

    assert rows[0]["name"] == "Test Catcher"
    assert rows[0]["primary_position"] == "C"
    assert rows[0]["positions"] == [{"position": "C", "games": 2}, {"position": "1B", "games": 1}]


def test_empirical_run_simulation_is_deterministic():
    players = list(range(1, 10))
    hitters = {player: {"event_rates": {"out": 0.7, "walk": 0.1, "single": 0.12, "double": 0.04, "triple": 0.01, "home_run": 0.03}} for player in players}

    first = service._simulate_runs(players, hitters, games=20)
    second = service._simulate_runs(players, hitters, games=20)

    assert first == second
    assert first is not None and first > 0


def test_position_assignment_enforces_eight_defensive_roles():
    players = list(range(1, 10))
    roles = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
    coverage = {player: {role} for player, role in zip(players, roles)}

    assignment = service._position_assignment(players, coverage)

    assert len(assignment) == 8
    assert set(assignment.values()) == set(roles)


def test_sample_reliability_is_a_pa_shrinkage_weight():
    assert service.sample_reliability(0) == 0
    assert service.sample_reliability(50) == 0.5
    assert service.sample_reliability(200) == 0.8
    assert service.sample_reliability(450) == 0.9


def test_cached_lineup_scenarios_return_without_running_simulation(monkeypatch, tmp_path):
    db_path = tmp_path / "MLB2026" / "mlb_2026.duckdb"
    db_path.parent.mkdir(parents=True)
    db_path.touch()
    cache_path = service.lineup_scenario_cache_path(2026, tmp_path)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps({
        "year": 2026,
        "model_version": service.LINEUP_CACHE_VERSION,
        "generated_at": "2026-09-03T12:00:00+08:00",
        "entries": {
            "AZ:R": {
                "team": "AZ",
                "opponent_hand": "R",
                "generated_at": "2026-09-03T12:00:00+08:00",
                "source_db_mtime_ns": db_path.stat().st_mtime_ns,
                "data_updated_at": "2026-09-02T00:00:00",
                "lineup_prediction": {"basis": "test"},
                "scenarios": [{
                    "label": "Latest observed",
                    "lineup": [],
                    "projected_runs_per_game": 5.1,
                    "constraint_status": "PASS",
                }],
                "limitations": [],
            }
        },
    }), encoding="utf-8")
    monkeypatch.setattr(service, "get_season_duckdb_path", lambda *_: db_path)
    monkeypatch.setattr(service, "get_batter_team_research", lambda *_: (_ for _ in ()).throw(AssertionError("must not simulate")))

    result = service.get_cached_batter_lineup_scenarios(2026, "az", "r", tmp_path)

    assert result.cache_status == "current"
    assert result.scenarios[0]["label"] == "Latest observed"


def test_cached_lineup_scenarios_keep_last_result_when_source_is_newer(monkeypatch, tmp_path):
    db_path = tmp_path / "mlb.duckdb"
    db_path.touch()
    cache_path = service.lineup_scenario_cache_path(2026, tmp_path)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps({
        "model_version": service.LINEUP_CACHE_VERSION,
        "entries": {"AZ:L": {
            "generated_at": "2026-09-02T12:00:00+08:00",
            "source_db_mtime_ns": 0,
            "lineup_prediction": {},
            "scenarios": [],
            "limitations": [],
        }},
    }), encoding="utf-8")
    monkeypatch.setattr(service, "get_season_duckdb_path", lambda *_: db_path)

    result = service.get_cached_batter_lineup_scenarios(2026, "AZ", "L", tmp_path)

    assert result.cache_status == "stale"
    assert "showing the last completed" in result.meta.warnings[0]
