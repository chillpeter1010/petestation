import sqlite3

import pandas as pd

from app.services import pitch_stuff_cache_service


def test_refresh_pitch_stuff_cache_is_incremental(monkeypatch, tmp_path):
    source = pd.DataFrame({
        "game_pk": [1, 1], "at_bat_number": [1, 1], "pitch_number": [1, 2],
        "pitcher": [10, 10], "game_date": ["2026-04-01", "2026-04-01"],
    })
    monkeypatch.setattr(pitch_stuff_cache_service, "_load_source", lambda *_: source.copy())
    monkeypatch.setattr(pitch_stuff_cache_service, "_artifact_version", lambda *_: "model-v1")

    from app.services import personal_service

    calls = []

    def fake_score(data, reference):
        calls.append(len(data))
        result = data.copy()
        result["pitch_stuff_plus"] = result["pitch_number"].map({1: 91.0, 2: 109.0, 3: 103.0})
        return result

    monkeypatch.setattr(personal_service, "score_pitch_stuff_uncached", fake_score)
    first = pitch_stuff_cache_service.refresh_pitch_stuff_scores(2026, tmp_path)
    second = pitch_stuff_cache_service.refresh_pitch_stuff_scores(2026, tmp_path)

    assert first["cached_rows"] == 2
    assert first["refreshed_pitchers"] == 1
    assert second["refreshed_pitchers"] == 0
    assert calls == [2]

    connection = sqlite3.connect(pitch_stuff_cache_service.cache_path(tmp_path))
    try:
        assert connection.execute("SELECT COUNT(*) FROM pitch_stuff_scores").fetchone()[0] == 2
    finally:
        connection.close()


def test_refresh_pitch_stuff_cache_scores_only_new_pitch_keys(monkeypatch, tmp_path):
    source = pd.DataFrame({
        "game_pk": [1, 1], "at_bat_number": [1, 1], "pitch_number": [1, 2],
        "pitcher": [10, 10], "game_date": ["2026-04-01", "2026-04-01"],
    })
    monkeypatch.setattr(pitch_stuff_cache_service, "_load_source", lambda *_: source.copy())
    monkeypatch.setattr(pitch_stuff_cache_service, "_artifact_version", lambda *_: "model-v1")
    from app.services import personal_service
    calls = []

    def fake_score(data, reference):
        calls.append((data["pitch_number"].tolist(), len(reference)))
        result = data.copy()
        result["pitch_stuff_plus"] = 100.0
        return result

    monkeypatch.setattr(personal_service, "score_pitch_stuff_uncached", fake_score)
    pitch_stuff_cache_service.refresh_pitch_stuff_scores(2026, tmp_path)
    source.loc[len(source)] = [1, 1, 3, 10, "2026-04-01"]

    result = pitch_stuff_cache_service.refresh_pitch_stuff_scores(2026, tmp_path)

    assert calls == [([1, 2], 2), ([3], 3)]
    assert result["cached_rows"] == 3
    assert result["written_rows"] == 1


def test_refresh_pitch_stuff_cache_honors_pitcher_budget(monkeypatch, tmp_path):
    source = pd.DataFrame({
        "game_pk": [1, 2], "at_bat_number": [1, 1], "pitch_number": [1, 1],
        "pitcher": [10, 20], "game_date": ["2026-04-01", "2026-04-01"],
    })
    monkeypatch.setattr(pitch_stuff_cache_service, "_load_source", lambda *_: source.copy())
    monkeypatch.setattr(pitch_stuff_cache_service, "_artifact_version", lambda *_: "model-v1")
    from app.services import personal_service

    def fake_score(data, reference):
        result = data.copy()
        result["pitch_stuff_plus"] = 100.0
        return result

    monkeypatch.setattr(personal_service, "score_pitch_stuff_uncached", fake_score)

    result = pitch_stuff_cache_service.refresh_pitch_stuff_scores(2026, tmp_path, max_pitchers=1)

    assert result["status"] == "partial"
    assert result["refreshed_pitchers"] == 1
    assert result["deferred_pitchers"] == 1


def test_refresh_pitch_stuff_cache_rejects_unscored_eligible_rows(monkeypatch, tmp_path):
    source = pd.DataFrame({
        "game_pk": [1, 1], "at_bat_number": [1, 1], "pitch_number": [1, 2],
        "pitcher": [10, 10], "game_date": ["2026-04-01", "2026-04-01"],
        "pitch_type": ["FF", "SL"], "pitch_name": ["4-Seam Fastball", "Slider"],
    })
    monkeypatch.setattr(pitch_stuff_cache_service, "_load_source", lambda *_: source.copy())
    monkeypatch.setattr(pitch_stuff_cache_service, "_artifact_version", lambda *_: "model-v1")
    from app.services import personal_service

    def fake_score(data, reference):
        result = data.copy()
        result["pitch_stuff_plus"] = [100.0, float("nan")]
        return result

    monkeypatch.setattr(personal_service, "score_pitch_stuff_uncached", fake_score)

    result = pitch_stuff_cache_service.refresh_pitch_stuff_scores(2026, tmp_path)

    assert result["status"] == "partial"
    assert result["eligible_rows"] == 2
    assert result["cached_rows"] == 1
    assert result["missing_eligible_rows"] == 1


def test_load_pitch_stuff_scores_aligns_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(pitch_stuff_cache_service, "_artifact_version", lambda *_: "model-v1")
    connection = pitch_stuff_cache_service._connect(tmp_path)
    try:
        connection.executemany(
            "INSERT INTO pitch_stuff_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (2026, 1, 1, 1, 10, "model-v1", 88.0, "now"),
                (2026, 1, 1, 2, 10, "model-v1", 112.0, "now"),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    pitches = pd.DataFrame({
        "game_pk": [1, 1], "at_bat_number": [1, 1], "pitch_number": [2, 1],
        "pitcher": [10, 10], "game_date": ["2026-04-01", "2026-04-01"],
    }, index=[7, 3])

    scores = pitch_stuff_cache_service.load_pitch_stuff_scores(pitches, tmp_path)

    assert scores.loc[7] == 112.0
    assert scores.loc[3] == 88.0
