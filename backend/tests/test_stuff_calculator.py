import pandas as pd

from app.api.schemas.stuff import StuffCalculatorRequest
from app.services.stuff_service import calculate_stuff_pitch


def test_calculator_builds_hand_adjusted_model_features(monkeypatch, tmp_path):
    captured = {}

    artifact_dir = tmp_path / "models" / "stuff_plus"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "pete_stuff_pipeline.joblib").touch()
    (artifact_dir / "pete_stuff_metadata.json").touch()
    monkeypatch.setattr("app.services.stuff_service.settings.data_dir", tmp_path)
    monkeypatch.setattr("app.services.stuff_service._load_pete_artifact", lambda *_: (object(), {
        "model_version": "test-v3",
        "standard_contexts": [{}] * 312,
    }))

    def fake_score(_model, _metadata, rows, outing=False):
        captured.update(rows.iloc[0].to_dict())
        assert outing is False
        return pd.DataFrame([{
            **rows.iloc[0].to_dict(),
            "stuff_plus": 111.2,
            "raw_stuff_plus": 116.8,
            "reliability": 0.5,
            "scale_source": "pitch_type:SL",
        }])

    monkeypatch.setattr("app.services.stuff_service.score_pitch_types", fake_score)
    result = calculate_stuff_pitch(StuffCalculatorRequest(
        pitch_type="SL", pitcher_hand="L", hb=-8.0, release_pos_x=2.0,
        primary_fastball_hb=-14.0, release_speed=86.0, primary_fastball_speed=94.0,
    ))

    assert captured["adj_hb"] == 8.0
    assert captured["adj_release_pos_x"] == -2.0
    assert captured["velo_diff_from_fastball"] == -8.0
    assert captured["hb_diff_from_fastball"] == -6.0
    assert result.stuff_plus == 111.2
    assert result.grade == "A-"
    assert result.contexts_evaluated == 312
