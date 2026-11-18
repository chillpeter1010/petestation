from __future__ import annotations

import gzip
import json
from pathlib import Path

import duckdb

from scripts.audit_pitcher_decision_sources import audit_year, feed_observations, schedule_rows


def schedule_game(pk: int, state: str = "Final") -> dict:
    return {"gamePk": pk, "gameType": "R", "officialDate": "2021-04-01",
            "status": {"abstractGameState": "Final" if state == "Final" else "Preview", "detailedState": state},
            "teams": {"home": {"score": 1}, "away": {"score": 0}}}


def test_schedule_deduplicates_rescheduling_and_excludes_cancelled_from_completed() -> None:
    final = schedule_game(1)
    cancelled = schedule_game(2, "Cancelled")
    cancelled["status"]["abstractGameState"] = "Final"
    payload = {"dates": [
        {"date": "2021-04-01", "games": [final, cancelled]},
        {"date": "2021-04-02", "games": [schedule_game(1, "Postponed"), schedule_game(3)]},
    ]}
    result = schedule_rows(payload)
    assert len(result) == 3
    assert result[1]["completed"] and result[1]["schedule_occurrences"] == 2
    assert not result[2]["completed"]
    assert result[3]["completed"]  # Separate game ID is not collapsed by date/team.


def test_feed_separates_physical_pitches_zero_pitch_plays_and_substitutions() -> None:
    feed = {"liveData": {"plays": {"allPlays": [
        {"atBatIndex": 0, "about": {"isComplete": True}, "playEvents": [
            {"isPitch": True, "pitchNumber": 1, "type": "pitch"},
            {"isPitch": False, "pitchNumber": 2, "type": "action", "details": {"eventType": "pitching_substitution"}},
        ]},
        {"atBatIndex": 1, "about": {"isComplete": True}, "playEvents": []},
    ]}}}
    result = feed_observations(feed)
    assert result["pitch_keys"] == {(1, 1)}
    assert result["numbered_keys"] == {(1, 1), (1, 2)}
    assert result["zero_pitch_plays"] == {2}
    assert result["actions"]["pitching_substitution"] == 1


def test_audit_detects_partial_game_without_mutating_database(tmp_path: Path) -> None:
    root = tmp_path / "data"
    db = root / "MLB2021/mlb_2021.duckdb"
    db.parent.mkdir(parents=True)
    with duckdb.connect(str(db)) as c:
        c.execute("""CREATE TABLE pitches AS SELECT 1 game_pk,'2021-04-01' game_date,
            1 at_bat_number,1 pitch_number,NULL::VARCHAR events,'ball' description,
            0 post_home_score,0 post_away_score,1 inning,'H' pitcher_team,'R' game_type""")
    before = db.read_bytes()
    output = tmp_path / "audit"
    (output / "sources").mkdir(parents=True)
    schedule = {"dates": [{"date": "2021-04-01", "games": [schedule_game(1), schedule_game(2)]}]}
    (output / "sources/schedule_2021.json.gz").write_bytes(gzip.compress(json.dumps(schedule).encode()))
    feed_dir = root / "research/catcher_descriptive/slice1/raw_game_feeds/2021"
    feed_dir.mkdir(parents=True)
    feed = {"gamePk": 1, "gameData": {"status": {"detailedState": "Final"}}, "liveData": {
        "linescore": {"teams": {"home": {"runs": 1}, "away": {"runs": 0}}},
        "plays": {"allPlays": [{"atBatIndex": 0, "about": {"isComplete": True}, "playEvents": [
            {"isPitch": True, "pitchNumber": 1}, {"isPitch": True, "pitchNumber": 2},
        ]}]}}}
    (feed_dir / "1.json.gz").write_bytes(gzip.compress(json.dumps(feed).encode()))
    audit_year(2021, root, output)
    summary = json.loads((output / "summary_2021.json").read_text(encoding="utf-8"))
    assert summary["official_pitch_keys_missing_local"] == 1
    assert summary["issue_counts"]["completed_game_missing_local"] == 1
    assert summary["issue_counts"]["final_score_differs"] == 1
    assert summary["issue_counts"]["official_feed_snapshot_missing"] == 1
    assert db.read_bytes() == before
