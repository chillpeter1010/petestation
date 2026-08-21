from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, OptionItem, ResponseMeta
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.personal_service import (
    apply_sequence_filters,
    build_conditioned_count_subset,
    build_conditioned_summary,
    build_conditioned_wpa_summary_table,
    build_count_pitch_followup_table,
    build_count_pitch_mix,
    build_count_state_detail_table,
    build_filter_snapshot_stats,
    build_next_count_state_detail_table,
    build_pitch_location_scatter,
    build_sequence_outcome_tables,
    catcher_lookup_rows,
    clean_value,
    dataframe_to_table_payload,
    display_pitch_name,
    filter_display_pitch_rows,
    filter_exact_count,
    load_season_catcher_lookup,
    normalize_pitch_names,
)


def _pitch_source(year: int) -> tuple[str, str] | None:
    db_path = get_season_duckdb_path(int(year), settings.data_dir)
    if not db_path.exists():
        return None
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    source_table = resolve_pitch_table(tables)
    if not source_table:
        return None
    return str(db_path), source_table


def _catcher_name(year: int, catcher_id: str) -> str:
    return load_season_catcher_lookup(int(year)).get(str(catcher_id), f"Catcher {catcher_id}")


def get_catcher_options(year: int) -> list[OptionItem]:
    source = _pitch_source(year)
    if not source:
        return []
    db_path, source_table = source
    with duckdb.connect(db_path, read_only=True) as conn:
        rows = conn.execute(
            f"""
            SELECT
                CAST(fielder_2 AS VARCHAR) AS catcher_id,
                COUNT(*) AS pitches,
                COUNT(DISTINCT game_pk) AS games,
                COUNT(DISTINCT pitcher) AS pitchers
            FROM {source_table}
            WHERE game_type = 'R'
              AND fielder_2 IS NOT NULL
              AND CAST(fielder_2 AS VARCHAR) NOT IN ('', '0', 'nan', 'NaN')
            GROUP BY 1
            ORDER BY pitches DESC, catcher_id
            """
        ).fetchdf()
    if rows.empty:
        return []
    lookup = load_season_catcher_lookup(int(year))
    options: list[OptionItem] = []
    for row in rows.to_dict(orient="records"):
        catcher_id = str(row["catcher_id"])
        name = lookup.get(catcher_id, f"Catcher {catcher_id}")
        options.append(
            OptionItem(
                value=catcher_id,
                label=name,
                meta={
                    "catcher_id": catcher_id,
                    "pitches": int(row.get("pitches") or 0),
                    "games": int(row.get("games") or 0),
                    "pitchers": int(row.get("pitchers") or 0),
                },
            )
        )
    return options


def get_catcher_pitcher_options(year: int, catcher_id: str) -> list[OptionItem]:
    source = _pitch_source(year)
    if not source:
        return [OptionItem(value="All", label="All")]
    db_path, source_table = source
    with duckdb.connect(db_path, read_only=True) as conn:
        rows = conn.execute(
            f"""
            SELECT
                pitcher AS pitcher_id,
                COALESCE(MAX(player_name), CAST(pitcher AS VARCHAR)) AS pitcher_name,
                COALESCE(MAX(pitcher_team), '-') AS team,
                COUNT(*) AS pitches,
                COUNT(DISTINCT game_pk) AS games
            FROM {source_table}
            WHERE game_type = 'R'
              AND CAST(fielder_2 AS VARCHAR) = ?
              AND pitcher IS NOT NULL
            GROUP BY 1
            ORDER BY pitches DESC, pitcher_name
            """,
            [str(catcher_id)],
        ).fetchdf()
    options = [OptionItem(value="All", label="All")]
    for row in rows.to_dict(orient="records"):
        pitcher_id = int(row["pitcher_id"])
        name = str(row.get("pitcher_name") or pitcher_id)
        team = str(row.get("team") or "-")
        options.append(
            OptionItem(
                value=pitcher_id,
                label=f"{name} ({team})",
                meta={
                    "pitcher_id": pitcher_id,
                    "name": name,
                    "team": team,
                    "pitches": int(row.get("pitches") or 0),
                    "games": int(row.get("games") or 0),
                },
            )
        )
    return options


def load_catcher_pitch_df(
    year: int,
    catcher_id: str,
    pitcher_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    source = _pitch_source(year)
    if not source:
        return pd.DataFrame()
    db_path, source_table = source
    where = ["game_type = 'R'", "CAST(fielder_2 AS VARCHAR) = ?"]
    params: list[Any] = [str(catcher_id)]
    if pitcher_id is not None:
        where.append("pitcher = ?")
        params.append(int(pitcher_id))
    if start_date:
        where.append("game_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("game_date <= ?")
        params.append(end_date)

    with duckdb.connect(db_path, read_only=True) as conn:
        data = conn.execute(
            f"""
            SELECT *
            FROM {source_table}
            WHERE {" AND ".join(where)}
            ORDER BY game_date, game_pk, at_bat_number, pitch_number
            """,
            params,
        ).fetchdf()
    if data.empty:
        return data
    lookup = {row["catcher_id"]: row["catcher_name"] for row in catcher_lookup_rows(data, year=year)}
    data["catcher_name"] = data["fielder_2"].astype(str).map(lambda value: lookup.get(value, _catcher_name(year, value)))
    return filter_display_pitch_rows(normalize_pitch_names(data)).reset_index(drop=True)


def _paired_pitcher_table(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or "pitcher" not in data.columns:
        return pd.DataFrame()
    working = data.copy()
    working["Pitcher ID"] = pd.to_numeric(working["pitcher"], errors="coerce")
    grouped = (
        working.groupby("Pitcher ID", dropna=False)
        .agg(
            Pitcher=("player_name", "max") if "player_name" in working.columns else ("pitcher", "max"),
            Team=("pitcher_team", "max") if "pitcher_team" in working.columns else ("pitcher", "max"),
            Pitches=("pitcher", "size"),
            Games=("game_pk", "nunique") if "game_pk" in working.columns else ("pitcher", "size"),
            PitchTypes=("pitch_name", "nunique") if "pitch_name" in working.columns else ("pitcher", "size"),
        )
        .reset_index()
    )
    return grouped[["Pitcher", "Team", "Pitches", "Games", "PitchTypes", "Pitcher ID"]].sort_values(
        ["Pitches", "Games"], ascending=[False, False]
    )


def _paired_pitcher_mix(data: pd.DataFrame) -> list[dict[str, Any]]:
    table = _paired_pitcher_table(data)
    if table.empty:
        return []
    total = float(table["Pitches"].sum())
    table["usage_pct"] = table["Pitches"] / total * 100 if total else 0
    return [{key: clean_value(value) for key, value in row.items()} for row in table.head(16).to_dict(orient="records")]


def _pitch_options_from_data(data: pd.DataFrame) -> list[str]:
    if data.empty or "pitch_name" not in data.columns:
        return []
    return [
        display_pitch_name(value)
        for value in data["pitch_name"].dropna().astype(str).value_counts().index.tolist()
    ]


def get_catcher_sequence(
    year: int,
    catcher_id: str,
    pitcher_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    current_pitch: str = "All",
    stand: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    condition_count: str | None = None,
    condition_pitch: str | None = None,
    detail_count: str | None = "0-0",
    followup_pitch: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_catcher_pitch_df(
        year=year,
        catcher_id=catcher_id,
        pitcher_id=pitcher_id,
        start_date=start_date,
        end_date=end_date,
    )
    filtered_df = apply_sequence_filters(pitch_df, stand=stand, count=count, pitch=pitch, pitch_result=pitch_result)
    shallow_df, two_strike_df = build_sequence_outcome_tables(filtered_df, current_pitch_filter=current_pitch)
    snapshot = build_filter_snapshot_stats(filtered_df)
    conditioned_df = build_conditioned_count_subset(filtered_df, condition_count, condition_pitch)
    conditioned_wpa_df = build_conditioned_wpa_summary_table(filtered_df, condition_count)
    current_count_df = build_count_state_detail_table(filter_exact_count(filtered_df, detail_count))
    next_count_df = build_next_count_state_detail_table(filtered_df, detail_count)
    followup_df = build_count_pitch_followup_table(filtered_df, detail_count, followup_pitch)
    pitcher_options = get_catcher_pitcher_options(year=year, catcher_id=catcher_id)

    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[MetricItem(key=key, label=key, value=clean_value(value)) for key, value in snapshot.items()],
        charts={
            "count_pitch_mix": build_count_pitch_mix(filtered_df, current_pitch_filter=current_pitch),
            "conditioned_count_pitch_mix": build_count_pitch_mix(conditioned_df, current_pitch_filter=current_pitch),
            "conditioned_summary": build_conditioned_summary(conditioned_df, condition_count, condition_pitch),
            "pitch_location_scatter": build_pitch_location_scatter(filtered_df),
            "filter_snapshot": snapshot,
            "catcher": {"id": str(catcher_id), "name": _catcher_name(year, str(catcher_id))},
            "pitcher_options": [option.model_dump() for option in pitcher_options],
            "pitch_options": _pitch_options_from_data(pitch_df),
            "paired_pitcher_mix": _paired_pitcher_mix(filtered_df),
        },
        tables={
            "paired_pitchers": dataframe_to_table_payload(_paired_pitcher_table(filtered_df)),
            "shallow_sequences": dataframe_to_table_payload(shallow_df),
            "two_strike_sequences": dataframe_to_table_payload(two_strike_df),
            "conditioned_wpa_summary": dataframe_to_table_payload(conditioned_wpa_df),
            "count_detail_current": dataframe_to_table_payload(current_count_df),
            "count_detail_next": dataframe_to_table_payload(next_count_df),
            "count_followup_events": dataframe_to_table_payload(followup_df),
        },
    )
