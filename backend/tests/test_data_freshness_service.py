from __future__ import annotations

import json
from pathlib import Path

import duckdb

from app.services.data_freshness_service import (
    _relative_status,
    build_data_freshness_report,
    render_data_freshness_markdown,
    write_data_freshness_report,
)


def _season_db(root: Path) -> None:
    target = root / "MLB2026"
    target.mkdir(parents=True)
    with duckdb.connect(str(target / "mlb_2026.duckdb")) as conn:
        conn.execute(
            """
            CREATE TABLE pitches AS
            SELECT * FROM (VALUES
                (1, DATE '2026-09-23', 'R'),
                (1, DATE '2026-09-23', 'R'),
                (2, DATE '2026-09-24', 'R')
            ) AS rows(game_pk, game_date, game_type)
            """
        )


def test_relative_status_respects_expected_lag() -> None:
    assert _relative_status("2026-09-24", "2026-09-24") == "current"
    assert _relative_status("2026-09-23", "2026-09-24", expected_lag=1) == "expected_lag"
    assert _relative_status("2026-09-20", "2026-09-24", expected_lag=1) == "stale"


def test_build_and_write_freshness_report(tmp_path: Path) -> None:
    _season_db(tmp_path)
    report = build_data_freshness_report(2026, tmp_path, include_official=False)

    pitch = next(item for item in report["datasets"] if item["key"] == "statcast_pitch_data")
    assert pitch["data_as_of"] == "2026-09-24"
    assert pitch["rows"] == 3
    stamina = next(item for item in report["datasets"] if item["key"] == "stamina_lab")
    assert stamina["status"] == "unavailable"
    shadow = next(item for item in report["datasets"] if item["key"] == "performance_state_shadow")
    assert shadow["status"] == "unavailable"
    assert shadow["automation"] == "manual frozen-model rebuild · immutable append ledger"
    legacy = next(item for item in report["datasets"] if item["key"] == "legacy_derived_exports")
    assert legacy["publication_status"] == "retired_read_only"
    reliever = next(item for item in report["datasets"] if item["key"] == "reliever_reference")
    assert reliever["publication_status"] == "manual_reference_only"
    assert any(page["route"] == "/leaderboards" for page in report["pages"])

    outputs = write_data_freshness_report(report, tmp_path, keep_history=False)
    saved = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert saved["year"] == 2026
    assert "| Statcast pitch data |" in render_data_freshness_markdown(report)
