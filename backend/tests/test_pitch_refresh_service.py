from pathlib import Path
from datetime import date

import duckdb

from app.services import pitch_refresh_service


def test_completed_schedule_excludes_postponed_games(monkeypatch):
    monkeypatch.setattr(
        pitch_refresh_service,
        "fetch_json",
        lambda *_args, **_kwargs: {
            "dates": [
                {
                    "date": "2026-08-04",
                    "games": [
                        {"gamePk": 1, "officialDate": "2026-08-04", "status": {"detailedState": "Final"}},
                        {"gamePk": 2, "officialDate": "2026-08-17", "status": {"abstractGameState": "Final", "detailedState": "Postponed"}},
                    ],
                }
            ]
        },
    )

    result = pitch_refresh_service.fetch_completed_regular_season_games(2026, date(2026, 8, 9))

    assert result == [{"game_pk": 1, "game_date": "2026-08-04"}]


def test_audit_pitch_coverage_reports_missing_completed_games(tmp_path: Path, monkeypatch):
    target_dir = tmp_path / "MLB2026"
    target_dir.mkdir(parents=True)
    db_path = target_dir / "mlb_2026.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE pitches AS
            SELECT 1001::BIGINT AS game_pk, DATE '2026-08-04' AS game_date, 'R'::VARCHAR AS game_type
            """
        )

    monkeypatch.setattr(
        pitch_refresh_service,
        "fetch_completed_regular_season_games",
        lambda year, through=None: [
            {"game_pk": 1001, "game_date": "2026-08-04"},
            {"game_pk": 1002, "game_date": "2026-08-05"},
        ],
    )

    result = pitch_refresh_service.audit_pitch_coverage(2026, tmp_path)

    assert result["complete"] is False
    assert result["missing_game_pks"] == [1002]
    assert result["missing_dates"] == ["2026-08-05"]


def test_recent_missing_dates_are_classified_as_source_pending():
    result = pitch_refresh_service.classify_source_pending(
        {"missing_dates": ["2026-08-09"]},
        today=date(2026, 8, 10),
    )

    assert result["source_pending"] is True
    assert result["pending_dates"] == ["2026-08-09"]
    assert result["stale_dates"] == []


def test_older_missing_date_remains_a_hard_failure():
    result = pitch_refresh_service.classify_source_pending(
        {"missing_dates": ["2026-08-01", "2026-08-09"]},
        today=date(2026, 8, 10),
    )

    assert result["source_pending"] is False
    assert result["stale_dates"] == ["2026-08-01"]
