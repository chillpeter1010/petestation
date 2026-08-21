import pandas as pd

from app.services.stuff_service import (
    build_stuff_lab_scores,
    build_prototype_stuff_scores,
    build_stuff_feature_table,
    get_stuff_score,
)


def _sample_pitch_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pitch_name": "4-Seam Fastball",
                "release_speed": 95.0,
                "release_spin_rate": 2300,
                "release_extension": 6.4,
                "release_pos_z": 5.7,
                "release_pos_x": -1.7,
                "pfx_x": -0.45,
                "pfx_z": 1.45,
                "p_throws": "R",
                "spin_axis": 185,
                "arm_angle": 52,
            },
            {
                "pitch_name": "4-Seam Fastball",
                "release_speed": 97.0,
                "release_spin_rate": 2350,
                "release_extension": 6.6,
                "release_pos_z": 5.8,
                "release_pos_x": -1.8,
                "pfx_x": -0.55,
                "pfx_z": 1.35,
                "p_throws": "R",
                "spin_axis": 190,
                "arm_angle": 52,
            },
            {
                "pitch_name": "Slider",
                "release_speed": 86.0,
                "release_spin_rate": 2500,
                "release_extension": 6.1,
                "release_pos_z": 5.5,
                "release_pos_x": -1.9,
                "pfx_x": 0.80,
                "pfx_z": 0.20,
                "p_throws": "R",
                "spin_axis": 80,
                "arm_angle": 52,
            },
        ]
    )


def test_build_stuff_feature_table_includes_fastball_deltas_and_spin_components():
    features = build_stuff_feature_table(_sample_pitch_frame())

    assert set(features["Pitch"]) == {"4-Seam", "Slider"}
    slider = features.loc[features["Pitch"].eq("Slider")].iloc[0]
    assert slider["velo_diff_from_fastball"] < 0
    assert slider["ivb_diff_from_fastball"] < 0
    assert -1 <= slider["spin_axis_x"] <= 1
    assert -1 <= slider["spin_axis_y"] <= 1


def test_build_stuff_feature_table_normalizes_spin_axis_y_by_pitcher_hand():
    right = _sample_pitch_frame().iloc[[0]].assign(spin_axis=90, p_throws="R")
    left = _sample_pitch_frame().iloc[[0]].assign(spin_axis=90, p_throws="L")

    right_features = build_stuff_feature_table(right).iloc[0]
    left_features = build_stuff_feature_table(left).iloc[0]

    assert right_features["spin_axis_x"] == left_features["spin_axis_x"]
    assert right_features["spin_axis_y"] == -left_features["spin_axis_y"]


def test_build_prototype_stuff_scores_marks_rows_as_proxy_scores():
    features = build_stuff_feature_table(_sample_pitch_frame())

    scores = build_prototype_stuff_scores(features)

    assert "prototype_stuff_plus" in scores.columns
    assert scores["model_status"].eq("prototype_proxy").all()


def test_get_stuff_score_returns_score_feature_and_diagnostic_tables(monkeypatch):
    monkeypatch.setattr(
        "app.services.stuff_service.load_pitcher_cached_season",
        lambda **_: _sample_pitch_frame(),
    )
    monkeypatch.setattr(
        "app.services.stuff_service._pete_pitch_type_scores",
        lambda *_args, **_kwargs: (pd.DataFrame(), None, None),
    )

    payload = get_stuff_score(year=2026, pitcher_id=1)

    assert payload.meta.year == 2026
    assert "shape proxy" in payload.meta.warnings[0]
    assert "stuff_scores" in payload.tables
    assert "stuff_features" in payload.tables
    assert "feature_diagnostics" in payload.tables
    assert len(payload.tables["stuff_scores"].rows) == 2


def test_build_stuff_lab_scores_joins_pete_supervised_score(monkeypatch):
    monkeypatch.setattr(
        "app.services.stuff_service._pete_pitch_type_scores",
        lambda *_args, **_kwargs: (
            pd.DataFrame([
                {"Pitch": "Four-Seam", "stuff_plus": 112.5, "raw_stuff_plus": 115.0, "reliability": 0.8}
            ]),
            "pete_stuff_outcome_probability_v2",
            "2026-07-30T00:00:00",
        ),
    )

    scores, status, generated_at = build_stuff_lab_scores(_sample_pitch_frame(), 2026, 1, scoring_mode="pete")

    four_seam = scores.loc[scores["Pitch"].eq("4-Seam")].iloc[0]
    assert four_seam["stuff_plus"] == 112.5
    assert four_seam["score_source"] == "Pete Stuff+ outcome probability v2 · pitch scaled"
    assert status == "pete_stuff_outcome_probability_v2"
    assert generated_at == "2026-07-30T00:00:00"


def test_get_stuff_score_filters_exact_game_pk(monkeypatch):
    frame = pd.concat([
        _sample_pitch_frame().assign(game_pk=101),
        _sample_pitch_frame().assign(game_pk=202),
    ], ignore_index=True)
    monkeypatch.setattr("app.services.stuff_service.load_pitcher_cached_season", lambda **_: frame)
    monkeypatch.setattr(
        "app.services.stuff_service._pete_pitch_type_scores",
        lambda *_args, **_kwargs: (pd.DataFrame(), None, None),
    )

    payload = get_stuff_score(year=2026, pitcher_id=1, game_pk=202)

    source_pitches = next(metric.value for metric in payload.summary if metric.key == "source_pitches")
    assert source_pitches == 3
