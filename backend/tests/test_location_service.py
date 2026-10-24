import pandas as pd

from app.services.location_service import (
    build_location_feature_table,
    build_prototype_location_scores,
    get_location_score,
)


def _sample_location_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pitch_name": "4-Seam Fastball",
                "plate_x": 0.0,
                "plate_z": 2.5,
                "zone": 5,
                "description": "called_strike",
                "balls": 0,
                "strikes": 0,
                "pitch_number": 1,
            },
            {
                "pitch_name": "4-Seam Fastball",
                "plate_x": 1.10,
                "plate_z": 2.6,
                "zone": 14,
                "description": "ball",
                "balls": 1,
                "strikes": 0,
                "pitch_number": 2,
            },
            {
                "pitch_name": "Slider",
                "plate_x": 1.70,
                "plate_z": 2.8,
                "zone": 16,
                "description": "swinging_strike",
                "balls": 0,
                "strikes": 2,
                "pitch_number": 3,
            },
            {
                "pitch_name": "Slider",
                "plate_x": 2.50,
                "plate_z": 4.8,
                "zone": 20,
                "description": "ball",
                "balls": 2,
                "strikes": 0,
                "pitch_number": 4,
            },
        ]
    )


def test_build_location_feature_table_uses_red_zone_separately_from_heart_zone():
    features = build_location_feature_table(_sample_location_frame())

    overall = features.loc[features["Pitch"].eq("Overall")].iloc[0]
    assert overall["zone_pct"] == 25
    assert overall["heart_pct"] == 25
    assert overall["meatball_pct"] == 25
    assert overall["shadow_pct"] > 0
    assert overall["chase_pct"] > 0


def test_build_prototype_location_scores_returns_proxy_status():
    features = build_location_feature_table(_sample_location_frame())

    scores = build_prototype_location_scores(features)

    assert "prototype_location_plus" in scores.columns
    assert scores["model_status"].eq("prototype_proxy").all()


def test_get_location_score_returns_score_feature_and_diagnostic_tables(monkeypatch):
    monkeypatch.setattr(
        "app.services.location_service.load_pitcher_cached_season",
        lambda **_: _sample_location_frame(),
    )

    payload = get_location_score(year=2026, pitcher_id=1)

    assert payload.meta.year == 2026
    assert "prototype proxy" in payload.meta.warnings[0]
    assert "location_scores" in payload.tables
    assert "location_features" in payload.tables
    assert "feature_diagnostics" in payload.tables
    assert len(payload.tables["location_scores"].rows) == 3
