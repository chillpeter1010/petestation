"""Export team pinch-hit totals from the official event ledger for RE24 Lab."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.mlb_teams import MLB_TEAM_ID_TO_CODE
from app.services.wpa_service import calibrate_pitcher_wpa


def main() -> None:
    source = ROOT / "data/research/decision_support_pipeline_20261114"
    seasons = {}
    with duckdb.connect(config={"threads": 2}) as conn:
        for year in (2025, 2026):
            for name in ("events", "plays", "roster"):
                conn.read_parquet(str(source / f"{name}_{year}.parquet")).create_view(name, replace=True)
            hits = conn.execute("""
                WITH first_pitch AS (
                    SELECT game_pk, at_bat_number, min(event_index) AS first_index
                    FROM events WHERE is_pitch GROUP BY 1, 2
                ), batting_teams AS (
                    SELECT * FROM (SELECT DISTINCT game_pk, team_id FROM roster)
                    QUALIFY count(*) OVER (PARTITION BY game_pk)=2
                )
                SELECT e.game_pk, e.at_bat_number, e.event_index, t.team_id, e.official_date,
                    CASE WHEN p.half='top' THEN p.raw_home_wpa ELSE -p.raw_home_wpa END AS defense_wpa,
                    p.source_re24 AS defense_re24,
                    coalesce(e.event_index < fp.first_index AND p.is_complete AND p.is_batter_faced
                        AND NOT p.mid_pa_change AND p.batter_id = e.player_id, false) AS matched
                FROM events e JOIN plays p USING(game_pk, at_bat_number)
                JOIN batting_teams t ON t.game_pk=e.game_pk AND t.team_id<>e.team_id
                LEFT JOIN first_pitch fp USING(game_pk, at_bat_number)
                WHERE e.event_type='offensive_substitution'
                    AND starts_with(e.description, 'Offensive Substitution: Pinch-hitter ')
                ORDER BY e.game_pk, e.at_bat_number, e.event_index
            """).fetchdf()
            # If an announced pinch hitter is replaced before batting, only the
            # terminal actor can qualify. Repeated records for that actor use the last event.
            matched = hits[hits["matched"]].drop_duplicates(["game_pk", "at_bat_number"], keep="last").copy()
            matched["wpa"] = -calibrate_pitcher_wpa(matched["defense_wpa"])
            matched["re24"] = -matched["defense_re24"]
            def total(values: pd.Series) -> float | None:
                return round(float(values.sum(min_count=1)), 6) if values.notna().any() else None

            rows = []
            for team_id, team in sorted(MLB_TEAM_ID_TO_CODE.items(), key=lambda item: item[1]):
                sample = matched[matched["team_id"].eq(team_id)]
                rows.append({
                    "team": team, "moves": len(sample),
                    "announced_moves": int(hits["team_id"].eq(team_id).sum()),
                    "wpa_n": int(sample["wpa"].count()), "re24_n": int(sample["re24"].count()),
                    "wpa": total(sample["wpa"]), "re24": total(sample["re24"]),
                    "wpa_per_move": total(pd.Series([sample["wpa"].mean()])),
                    "re24_per_move": total(pd.Series([sample["re24"].mean()])),
                })
            assert not hits.empty and not matched.empty
            assert set(hits["team_id"]).issubset(MLB_TEAM_ID_TO_CODE)
            assert sum(row["announced_moves"] for row in rows) == len(hits)
            seasons[year] = {"data_as_of": hits["official_date"].max(), "rows": rows}
            print(f"{year}: {len(matched):,} completed / {len(hits):,} announced pinch hitters")
    path = ROOT / "data/sample/petehub_leverage_pinch_hits_v1.json"
    path.write_text(json.dumps({"version": "leverage_pinch_hits_v1", "seasons": seasons}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
