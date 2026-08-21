import pandas as pd

from app.services import personal_service


def test_add_pitch_stuff_scores_keeps_individual_pitch_values(monkeypatch, tmp_path):
    artifact_dir = tmp_path / "models" / "stuff_plus"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "pete_stuff_pipeline.joblib").write_bytes(b"model")
    (artifact_dir / "pete_stuff_metadata.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(personal_service.settings, "data_dir", tmp_path)
    monkeypatch.setattr(personal_service, "_load_personal_stuff_artifact", lambda *_: (object(), {}))

    def fake_score(_model, _metadata, rows, outing=False):
        assert outing is False
        scored = rows.copy()
        scored["raw_stuff_plus"] = [91.0, 109.0]
        return scored

    monkeypatch.setattr(personal_service, "score_pitch_types", fake_score)
    pitches = pd.DataFrame({
        "pitch_name": ["Four-Seam", "Four-Seam"],
        "pitch_type": ["FF", "FF"],
        "p_throws": ["R", "R"],
        "release_speed": [91.0, 96.0],
        "pfx_x": [-0.5, -0.7],
        "pfx_z": [1.1, 1.4],
        "release_spin_rate": [2200, 2500],
        "release_extension": [6.2, 6.5],
        "release_pos_z": [5.8, 5.9],
        "release_pos_x": [-2.0, -2.1],
        "spin_axis": [200, 210],
        "arm_angle": [35, 36],
    })

    result = personal_service.add_pitch_stuff_scores(pitches, pitches)

    assert result["pitch_stuff_plus"].tolist() == [91.0, 109.0]
