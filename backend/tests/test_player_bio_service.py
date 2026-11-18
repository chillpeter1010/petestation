from datetime import datetime, timedelta, timezone

import pytest
import requests

from app.services.player_bio_service import get_player_bios, normalize_person

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)
PERSON = {"id": 605483, "fullName": "Blake Snell", "height": "6' 4\"", "weight": 225, "batSide": {"code": "L"}, "pitchHand": {"code": "L"}}


def test_normalization_preserves_source_and_units():
    bio = normalize_person(PERSON, NOW.isoformat())
    assert bio.height_raw == "6' 4\""
    assert bio.height_inches == 76
    assert bio.height_m == pytest.approx(1.9304)
    assert bio.weight_kg == pytest.approx(102.0583)
    assert bio.bats == bio.throws == "L"
    assert "not_historical" in bio.temporal_scope
    for raw in [None, "six feet", "6' 13\"", "0' 0\""]:
        assert normalize_person({**PERSON, "height": raw}, NOW.isoformat()).height_m is None


def test_batch_cache_partial_response_and_negative_retry(tmp_path):
    calls = []
    def fetch(url, timeout):
        calls.append(url)
        assert timeout == 6
        return {"people": [PERSON, {**PERSON, "id": 999}]}
    bios = get_player_bios([605483, 42, 605483], data_dir=tmp_path, now=NOW, fetcher=fetch)
    assert set(bios) == {605483, 42}
    assert bios[42].freshness == "unavailable"
    assert bios[42].height_m is None
    assert bios[605483].freshness == "fresh"
    get_player_bios([605483, 42], data_dir=tmp_path, now=NOW+timedelta(minutes=1), fetcher=fetch)
    assert len(calls) == 1
    assert not list((tmp_path / "player_bios_v1").glob("*.tmp"))


def test_failed_refresh_keeps_stale_bio_and_retries_later(tmp_path):
    get_player_bios([605483], data_dir=tmp_path, now=NOW, fetcher=lambda *a, **k: {"people": [PERSON]})
    def fail(*a, **k):
        raise requests.Timeout("offline")
    bio = get_player_bios([605483], data_dir=tmp_path, now=NOW+timedelta(days=8), fetcher=fail)[605483]
    assert bio.freshness == "stale"
    assert bio.height_m == pytest.approx(1.9304)
    assert bio.retrieved_at == NOW.isoformat()
    assert bio.warning
    # A disk-cache error must also not block usable live data.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    assert get_player_bios([605483], data_dir=blocked, now=NOW, fetcher=lambda *a, **k: {"people": [PERSON]})[605483].height_m


def test_bad_cache_and_bad_payload_are_explicitly_unavailable(tmp_path):
    cache = tmp_path / "player_bios_v1"
    cache.mkdir()
    (cache / "605483.json").write_text('{"broken":true}')
    bio = get_player_bios([605483], data_dir=tmp_path, now=NOW, fetcher=lambda *a, **k: [PERSON])[605483]
    assert bio.freshness == "unavailable"
    assert bio.height_m is None
    assert bio.warning


def test_replay_bio_attachment_does_not_change_source_path(monkeypatch):
    import pandas as pd
    from app.services import game_pitcher_analysis_service as replay
    from test_game_pitcher_analysis_service import _trajectory_pitch
    monkeypatch.setattr(replay, "catcher_lookup_rows", lambda *a, **k: [])
    frame = pd.DataFrame([_trajectory_pitch(arm_angle=37.5,home_team='ATH',away_team='AZ',inning_topbot='Top')])
    before = replay.build_game_pitch_replay_response(frame, year=2026, game_pk=824948, pitcher_id=837227)
    bio = normalize_person({**PERSON, "id": 695720}, NOW.isoformat()).model_dump()
    result = replay.build_game_pitch_replay_response(frame, year=2026, game_pk=824948, pitcher_id=837227, player_bios={695720: bio})
    row = result.charts["pitch_replay"][0]
    assert row["trajectory_points"] == before.charts["pitch_replay"][0]["trajectory_points"]
    assert row["batter_bio"]["height_m"] == pytest.approx(1.9304)
    assert row["arm_angle"] == 37.5
    assert (row["home_team"],row["away_team"],row["inning_topbot"]) == ('ATH','AZ','Top')
    assert "batter_bio" not in frame.columns


def test_shared_replay_entrypoint_loads_both_bios(monkeypatch):
    import pandas as pd
    from app.services import game_pitcher_analysis_service as replay, pitch_matchup_service, player_bio_service
    from test_game_pitcher_analysis_service import _trajectory_pitch
    monkeypatch.setattr(replay, "load_personal_pitch_df", lambda **k: pd.DataFrame([_trajectory_pitch()]))
    monkeypatch.setattr(replay, "catcher_lookup_rows", lambda *a, **k: [])
    monkeypatch.setattr(pitch_matchup_service, "resolve_replay_names", lambda *a: {837227: "Pitcher", 695720: "Batter"})
    requested = []
    def bios(ids):
        requested.extend(ids)
        return {i: normalize_person({**PERSON, "id": i}, NOW.isoformat()) for i in ids}
    monkeypatch.setattr(player_bio_service, "get_player_bios", bios)
    row = replay.get_game_pitch_replay(2026, 824948, 837227).charts["pitch_replay"][0]
    assert set(requested) == {837227, 695720}
    assert row["pitcher_bio"]["player_id"] == 837227
    assert row["batter_bio"]["player_id"] == 695720
