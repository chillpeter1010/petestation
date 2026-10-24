from __future__ import annotations

import duckdb

from app.services.player_archetype_slice3_service import (
    CONTRACT_VERSION,
    get_player_archetype_slice3,
    get_player_archetype_slice3_view,
    slice3_distribution_path,
    slice3_roster_path,
)
from app.api.routes.derived import read_player_archetype_slice3


def test_slice3_contract_and_roster_are_unique() -> None:
    contract = get_player_archetype_slice3()
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["status"] == "ready"
    assert contract["audit"]["duplicate_roster_keys"] == 0
    assert contract["audit"]["adjacent_tag_pairs"] > 0
    assert contract["audit"]["same_role_tag_pairs"] > 0


def test_rejected_pitcher_arsenal_is_not_in_official_roster() -> None:
    with duckdb.connect() as connection:
        columns = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(slice3_roster_path())]).fetchdf()["column_name"].tolist()
        leaked = connection.execute(
            """SELECT count(*) FROM read_parquet(?)
               WHERE coalesce(tag_1, '') LIKE '%Heavy%' OR coalesce(tag_2, '') LIKE '%Heavy%'
                  OR coalesce(tag_3, '') LIKE '%Heavy%' OR coalesce(tag_4, '') LIKE '%Heavy%'""",
            [str(slice3_roster_path())],
        ).fetchone()[0]
    assert {"tag_1", "tag_1_dimension", "tag_2", "tag_2_dimension", "tag_3", "tag_3_dimension", "tag_4", "tag_4_dimension", "support_status"}.issubset(columns)
    assert leaked == 0


def test_distribution_flags_and_admin_view() -> None:
    with duckdb.connect() as connection:
        rows = connection.execute("SELECT count(*) FROM read_parquet(?)", [str(slice3_distribution_path())]).fetchone()[0]
        columns = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(slice3_distribution_path())]).fetchdf()["column_name"].tolist()
        bad_share = connection.execute(
            "SELECT count(*) FROM read_parquet(?) WHERE eligible_share_pct < 0 OR eligible_share_pct > 100",
            [str(slice3_distribution_path())],
        ).fetchone()[0]
    view = get_player_archetype_slice3_view(year=2026, population="pitcher", role="SP")
    assert rows > 0
    assert {"top_cooccurring_tag", "cooccurrence_share_pct"}.issubset(columns)
    assert bad_share == 0
    assert view["roster"]
    assert all(row["year"] == 2026 and row["role"] == "SP" for row in view["roster"])


def test_public_derived_tag_lab_payload() -> None:
    payload = read_player_archetype_slice3(year=2026, population="batter", role=None)
    assert payload["publication_scope"] == "retrospective_full_season_descriptive_only"
    assert payload["roster"]
    assert all(row["population"] == "batter" for row in payload["roster"])
