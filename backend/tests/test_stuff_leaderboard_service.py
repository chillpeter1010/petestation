import json

import duckdb
import pandas as pd

from app.services import stuff_leaderboard_service


def test_get_stuff_leaderboard_filters_snapshot_without_rescoring(monkeypatch, tmp_path):
    path = stuff_leaderboard_service.snapshot_path(2026, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "year": 2026,
        "data_as_of": "2026-09-08",
        "generated_at": "2026-09-10T00:00:00+00:00",
        "model_version": "model-v1",
        "location_generated_at": None,
        "cache_status": "current",
        "pitch_types": ["FA"],
        "total_pitchers": 2,
        "warnings": [],
        "rows": [
            {"player_id": 10, "role": "SP", "team": "ARI", "ip": 120.0},
            {"player_id": 20, "role": "RP", "team": "ARI", "ip": 40.0},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(stuff_leaderboard_service, "_current_source_date", lambda *_: "2026-09-08")

    result = stuff_leaderboard_service.get_stuff_leaderboard(
        year=2026, role="SP", team="ARI", minimum_ip=100, data_dir=tmp_path
    )

    assert result["cache_status"] == "current"
    assert result["total_pitchers"] == 1
    assert result["rows"][0]["player_id"] == 10


def test_get_stuff_leaderboard_marks_old_snapshot_stale(monkeypatch, tmp_path):
    path = stuff_leaderboard_service.snapshot_path(2026, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "year": 2026, "data_as_of": "2026-09-06", "model_version": "model-v1",
        "cache_status": "current", "pitch_types": [], "total_pitchers": 0,
        "warnings": [], "rows": [],
    }), encoding="utf-8")
    monkeypatch.setattr(stuff_leaderboard_service, "_current_source_date", lambda *_: "2026-09-08")

    result = stuff_leaderboard_service.get_stuff_leaderboard(year=2026, data_dir=tmp_path)

    assert result["cache_status"] == "stale"
    assert "2026-09-06" in result["warnings"][0]


def test_pitching_scores_use_latest_complete_export_when_date_is_stale(tmp_path):
    root = tmp_path / "models" / "pitching_plus"
    root.mkdir(parents=True)
    (root / "pete_pitching_metadata.json").write_text(json.dumps({
        "model_version": "pitching-v1", "data_as_of": "2026-09-06", "exported_at": "now",
    }), encoding="utf-8")
    pd.DataFrame([{"pitcher": 10, "pitching_plus": 112.0}]).to_csv(
        root / "pitching_plus_pitchers_2026.csv", index=False
    )

    scores, pitch_scores, source = stuff_leaderboard_service._load_pitching_scores(
        2026, "2026-09-08", tmp_path
    )

    assert scores == {10: 112.0}
    assert pitch_scores == {}
    assert source["status"] == "stale"
    assert "最新 Pitching+" in source["warning"]


def test_pitching_scores_load_only_at_matching_cutoff(tmp_path):
    root = tmp_path / "models" / "pitching_plus"
    root.mkdir(parents=True)
    (root / "pete_pitching_metadata.json").write_text(json.dumps({
        "model_version": "pitching-v1", "data_as_of": "2026-09-08", "exported_at": "now",
    }), encoding="utf-8")
    pd.DataFrame([{"pitcher": 10, "pitching_plus": 112.04}]).to_csv(
        root / "pitching_plus_pitchers_2026.csv", index=False
    )
    pd.DataFrame([
        {"pitcher": 10, "pitch_type": "FF", "pitches": 30, "pitching_plus": 110.0},
        {"pitcher": 10, "pitch_type": "SL", "pitches": 20, "pitching_plus": 100.0},
        {"pitcher": 10, "pitch_type": "ST", "pitches": 10, "pitching_plus": 120.0},
    ]).to_csv(root / "pitching_plus_pitch_types_2026.csv", index=False)

    scores, pitch_scores, source = stuff_leaderboard_service._load_pitching_scores(
        2026, "2026-09-08", tmp_path
    )

    assert scores == {10: 112.0}
    assert pitch_scores[10]["FA"] == 110.0
    assert pitch_scores[10]["SL"] == 106.7
    assert source["status"] == "current"


def test_location_scores_include_weighted_canonical_pitch_types(tmp_path):
    root = tmp_path / "derived"
    root.mkdir(parents=True)
    with duckdb.connect(str(root / "location_plus_scores.duckdb")) as connection:
        connection.execute("""
            CREATE TABLE location_pitcher_scores_2026 AS
            SELECT 10 AS pitcher_id, 100 AS pitches, 108.04 AS location_plus,
                   'qualified' AS sample_status, 'now' AS generated_at
        """)
        connection.execute("""
            CREATE TABLE location_pitch_type_scores_2026 AS
            SELECT * FROM (VALUES
                (10, '4-Seam Fastball', 40, 110.0),
                (10, 'Slider', 20, 100.0),
                (10, 'Sweeper', 10, 120.0)
            ) scores(pitcher_id, pitch_name, pitches, location_plus)
        """)

    scores, pitch_scores, generated_at = stuff_leaderboard_service._load_location_scores(2026, tmp_path)

    assert scores[10]["location_plus"] == 108.0
    assert pitch_scores[10]["FA"] == 110.0
    assert pitch_scores[10]["SL"] == 106.7
    assert generated_at == "now"
