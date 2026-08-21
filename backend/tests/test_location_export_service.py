from pathlib import Path

import duckdb
import pandas as pd

from app.services import location_export_service as service


def test_location_export_readers(tmp_path, monkeypatch):
    path = tmp_path / "scores.duckdb"
    pitcher = pd.DataFrame([{
        "pitcher_id": 7, "pitcher_name": "Test Pitcher", "team": "AZ", "pitches": 350,
        "location_plus": 111.2, "xrv_per_100": -0.5, "location_plus_vs_l": 108.0,
        "location_plus_vs_r": 113.0, "location_plus_se": 1.2, "reliability": 1.0,
        "sample_status": "qualified",
    }])
    pitch_type = pd.DataFrame([{
        "pitcher_id": 7, "pitch_name": "Slider", "pitches": 100, "location_plus": 115.0,
        "xrv_per_100": -0.6, "called_strike_pct": 20.0, "whiff_pct": 15.0,
        "barrel_pct": 2.0, "ball_pct": 35.0, "location_plus_se": 2.0,
        "sample_status": "qualified",
    }])
    outing = pd.DataFrame([
        {
            "pitcher_id": 7, "game_pk": 1, "game_date": "2026-08-01", "team": "AZ", "pitches": 90,
            "location_plus": 109.0, "xrv_per_100": -0.4, "called_strike_pct": 18.0,
            "whiff_pct": 12.0, "barrel_pct": 3.0, "location_plus_se": 3.0,
        },
        {
            "pitcher_id": 7, "game_pk": 2, "game_date": "2026-07-25", "team": "AZ", "pitches": 84,
            "location_plus": 101.0, "xrv_per_100": -0.1, "called_strike_pct": 17.0,
            "whiff_pct": 10.0, "barrel_pct": 4.0, "location_plus_se": 3.5,
        },
    ])
    outing_pitch_types = pd.DataFrame([{
        "pitcher_id": 7, "game_pk": 2, "pitch_name": "Slider", "pitches": 2,
        "location_plus": 101.5, "xrv_per_100": -1.5,
        "called_strike_pct": 22.5, "whiff_pct": 17.5,
        "barrel_pct": 1.5, "ball_pct": 32.5, "location_plus_se": 4.0,
        "sample_status": "provisional",
    }])
    manifest = pd.DataFrame([{"year": 2026, "model_version": "test", "generated_at": "now"}])
    with duckdb.connect(str(path)) as conn:
        for name, frame in [("location_pitcher_scores_2026", pitcher), ("location_pitch_type_scores_2026", pitch_type), ("location_outing_scores_2026", outing), ("location_outing_pitch_type_scores_2026", outing_pitch_types), ("location_manifest", manifest)]:
            conn.register("frame", frame)
            conn.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
            conn.unregister("frame")
    monkeypatch.setattr(service, "_database_path", lambda: Path(path))
    leaderboard = service.get_location_leaderboard(2026, 300)
    detail = service.get_location_pitcher(2026, 7)
    selected_outing = service.get_location_pitcher(2026, 7, game_pk=2)
    assert leaderboard.total_pitchers == 1
    assert leaderboard.rows[0].location_plus == 111.2
    assert detail.pitch_types[0].pitch_name == "Slider / Sweeper"
    assert detail.outings[0].game_pk == 1
    assert len(selected_outing.outings) == 1
    assert selected_outing.outings[0].game_pk == 2
    assert selected_outing.outing_pitch_types[0].pitch_name == "Slider"
    assert selected_outing.outing_pitch_types[0].pitches == 2


def test_location_comparison_matches_mlb_ids(tmp_path, monkeypatch):
    path = tmp_path / "scores.duckdb"
    model = pd.DataFrame([
        {"pitcher_id": 1, "pitcher_name": "One", "pitches": 520, "location_plus": 90.0},
        {"pitcher_id": 2, "pitcher_name": "Two", "pitches": 620, "location_plus": 100.0},
        {"pitcher_id": 3, "pitcher_name": "Three", "pitches": 720, "location_plus": 110.0},
    ])
    with duckdb.connect(str(path)) as conn:
        conn.register("frame", model)
        conn.execute("CREATE TABLE location_pitcher_scores_2026 AS SELECT * FROM frame")
    pd.DataFrame([
        {"Name": "One", "MLBAMID": 1, "Location+": 92.0},
        {"Name": "Two", "MLBAMID": 2, "Location+": 101.0},
        {"Name": "Three", "MLBAMID": 3, "Location+": 108.0},
    ]).to_csv(tmp_path / "2026_location_plus.csv", index=False)
    monkeypatch.setattr(service, "_database_path", lambda: Path(path))
    monkeypatch.setattr(service.settings, "data_dir", tmp_path)

    result = service.get_location_comparison(2026, 100)

    assert result.matched_pitchers == 3
    assert result.active.matched_pitchers == 3
    assert result.active.pearson_r > 0.9
