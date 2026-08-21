from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta, TablePayload
from app.core.config import settings


def derived_db_path(data_dir=settings.data_dir):
    return data_dir / "derived" / "derived_exports.duckdb"


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def dataframe_to_table_payload(df: pd.DataFrame) -> TablePayload:
    if df.empty:
        return TablePayload()
    rows = [{key: clean_value(value) for key, value in row.items()} for row in df.to_dict(orient="records")]
    columns = [{"key": column, "label": column} for column in df.columns]
    return TablePayload(columns=columns, rows=rows)


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    return table_name in tables


def get_derived_status(year: int = 2026) -> dict[str, Any]:
    db_path = derived_db_path()
    status: dict[str, Any] = {
        "year": int(year),
        "duckdb_path": str(db_path),
        "duckdb_exists": db_path.exists(),
        "tables": [],
        "manifest": [],
    }
    if not db_path.exists():
        return status

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
        status["tables"] = tables
        if "derived_manifest" in tables:
            manifest = conn.execute(
                """
                SELECT table_name, year, generated_at, row_count, model_version, train_years, notes
                FROM derived_manifest
                WHERE year = ?
                ORDER BY table_name
                """,
                [int(year)],
            ).fetchdf()
            status["manifest"] = [
                {key: clean_value(value) for key, value in row.items()}
                for row in manifest.to_dict(orient="records")
            ]
    return status


def get_derived_outing_report(year: int, pitcher_id: int, game_pk: int) -> AnalysisResponse:
    db_path = derived_db_path()
    warnings: list[str] = []
    if not db_path.exists():
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=[f"Derived database not found: {db_path}"]),
        )

    report_table = f"outing_reports_{int(year)}"
    pitch_type_table = f"outing_pitch_type_metrics_{int(year)}"
    usage_table = f"outing_usage_splits_{int(year)}"
    location_table = f"outing_location_points_{int(year)}"
    with duckdb.connect(str(db_path), read_only=True) as conn:
        if not _table_exists(conn, report_table):
            return AnalysisResponse(
                meta=ResponseMeta(year=year, warnings=[f"Derived table not found: {report_table}"]),
            )

        report_df = conn.execute(
            f"""
            SELECT *
            FROM {report_table}
            WHERE pitcher_id = ? AND game_pk = ?
            LIMIT 1
            """,
            [int(pitcher_id), int(game_pk)],
        ).fetchdf()
        if report_df.empty:
            warnings.append(f"No derived outing report found for pitcher_id={pitcher_id}, game_pk={game_pk}.")

        pitch_type_df = pd.DataFrame()
        if _table_exists(conn, pitch_type_table):
            pitch_type_df = conn.execute(
                f"""
                SELECT *
                FROM {pitch_type_table}
                WHERE pitcher_id = ? AND game_pk = ?
                ORDER BY pitch_count DESC, pitch_name
                """,
                [int(pitcher_id), int(game_pk)],
            ).fetchdf()
        else:
            warnings.append(f"Derived table not found: {pitch_type_table}")

        usage_df = pd.DataFrame()
        if _table_exists(conn, usage_table):
            usage_df = conn.execute(
                f"""
                SELECT *
                FROM {usage_table}
                WHERE pitcher_id = ? AND game_pk = ?
                ORDER BY total_usage_pct DESC, pitch_name
                """,
                [int(pitcher_id), int(game_pk)],
            ).fetchdf()

        location_sample_df = pd.DataFrame()
        if _table_exists(conn, location_table):
            location_sample_df = conn.execute(
                f"""
                SELECT game_date, game_pk, pitcher_id, at_bat_number, pitch_number, pitch_type,
                       pitch_name, batter_id, batter_name, stand, catcher_id, catcher_name,
                       plate_x, plate_z, description, events, bb_type, launch_speed,
                       launch_angle, video_url, direct_video_url, play_id
                FROM {location_table}
                WHERE pitcher_id = ? AND game_pk = ?
                ORDER BY at_bat_number, pitch_number
                LIMIT 500
                """,
                [int(pitcher_id), int(game_pk)],
            ).fetchdf()

    summary: list[MetricItem] = []
    charts: dict[str, Any] = {}
    if not report_df.empty:
        row = report_df.iloc[0].to_dict()
        summary_specs = [
            ("game_date", "Date"),
            ("opponent", "Opponent"),
            ("IP", "IP"),
            ("H", "Hits"),
            ("R", "R"),
            ("ER", "ER"),
            ("BB", "BB"),
            ("K", "K"),
            ("pitches", "Pitches"),
            ("batters_faced", "Batters"),
            ("csw_pct", "CSW%"),
            ("zone_pct", "Zone%"),
            ("stuff_plus", "Stuff+"),
            ("location_plus", "Location+"),
            ("er_source", "ER Source"),
        ]
        summary = [
            MetricItem(key=key, label=label, value=clean_value(row.get(key)))
            for key, label in summary_specs
            if key in row
        ]
        charts["outing_report"] = {key: clean_value(value) for key, value in row.items()}
    charts["location_points_sample"] = [
        {key: clean_value(value) for key, value in row.items()}
        for row in location_sample_df.to_dict(orient="records")
    ]

    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        summary=summary,
        charts=charts,
        tables={
            "outing_report": dataframe_to_table_payload(report_df),
            "pitch_type_metrics": dataframe_to_table_payload(pitch_type_df),
            "usage_splits": dataframe_to_table_payload(usage_df),
            "location_points_sample": dataframe_to_table_payload(location_sample_df),
        },
    )


def get_derived_model_scores(year: int, scope: str = "pitcher") -> AnalysisResponse:
    db_path = derived_db_path()
    if not db_path.exists():
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=[f"Derived database not found: {db_path}"]),
        )
    table = f"model_scores_{'pitch_type' if scope == 'pitch_type' else 'pitcher'}_{int(year)}"
    with duckdb.connect(str(db_path), read_only=True) as conn:
        if not _table_exists(conn, table):
            return AnalysisResponse(meta=ResponseMeta(year=year, warnings=[f"Derived table not found: {table}"]))
        df = conn.execute(f"SELECT * FROM {table} ORDER BY stuff_plus DESC NULLS LAST LIMIT 1000").fetchdf()
    return AnalysisResponse(
        meta=ResponseMeta(year=year),
        summary=[MetricItem(key="rows", label="Rows", value=int(len(df)))],
        tables={"model_scores": dataframe_to_table_payload(df)},
    )
