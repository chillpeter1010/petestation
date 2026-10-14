from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.ml.stuff_plus import load_artifact, score_pitch_types
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.pitcher_service import list_pitcher_leaderboard
from app.services.stuff_service import PITCH_TYPE_CODES, build_stuff_feature_table


PITCH_CODES = ["FA", "SI", "FC", "FS", "SL", "CU", "CH", "KC", "FO"]
DISPLAY_PITCH_CODE = {"FF": "FA", "ST": "SL"}


def snapshot_path(year: int, data_dir: Path | None = None) -> Path:
    root = data_dir or settings.data_dir
    return root / "derived" / f"stuff_leaderboard_{int(year)}.json"


def _load_source(year: int, data_dir: Path) -> tuple[pd.DataFrame, str | None]:
    path = get_season_duckdb_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Missing season database: {path}")
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            raise RuntimeError(f"No pitch table found in {path}")
        available = {row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()}
        required = {
            "pitcher", "game_date", "game_type", "pitch_name", "p_throws", "release_speed",
            "pfx_x", "pfx_z", "release_spin_rate", "release_extension", "release_pos_z",
            "release_pos_x", "spin_axis", "arm_angle",
        }
        missing = sorted(required - available)
        if missing:
            raise RuntimeError(f"Pitch source is missing Stuff+ columns: {', '.join(missing)}")
        columns = ", ".join(sorted(required - {"game_type"}))
        frame = connection.execute(
            f"SELECT {columns} FROM {table} WHERE game_type = 'R' AND pitcher IS NOT NULL"
        ).fetchdf()
    dates = pd.to_datetime(frame.get("game_date"), errors="coerce")
    data_as_of = dates.max().date().isoformat() if dates.notna().any() else None
    return frame, data_as_of


def _current_source_date(year: int, data_dir: Path) -> str | None:
    path = get_season_duckdb_path(year, data_dir)
    if not path.exists():
        return None
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            return None
        latest = connection.execute(
            f"SELECT MAX(CAST(game_date AS DATE)) FROM {table} WHERE game_type = 'R'"
        ).fetchone()[0]
    return str(latest)[:10] if latest else None


def _load_location_scores(
    year: int,
    data_dir: Path,
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, float | None]], str | None]:
    path = data_dir / "derived" / "location_plus_scores.duckdb"
    table = f"location_pitcher_scores_{int(year)}"
    pitch_table = f"location_pitch_type_scores_{int(year)}"
    if not path.exists():
        return {}, {}, None
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            return {}, {}, None
        frame = connection.execute(
            f"SELECT pitcher_id, pitches, location_plus, sample_status, generated_at FROM {table}"
        ).fetchdf()
        pitch_frame = pd.DataFrame(columns=["pitcher_id", "pitch_code", "location_plus"])
        if pitch_table in tables:
            pitch_frame = connection.execute(
                f"""
                WITH canonical AS (
                    SELECT pitcher_id,
                           CASE
                               WHEN pitch_name = '4-Seam Fastball' THEN 'FA'
                               WHEN pitch_name = 'Sinker' THEN 'SI'
                               WHEN pitch_name = 'Cutter' THEN 'FC'
                               WHEN pitch_name = 'Split-Finger' THEN 'FS'
                               WHEN pitch_name IN ('Slider', 'Sweeper') THEN 'SL'
                               WHEN pitch_name = 'Curveball' THEN 'CU'
                               WHEN pitch_name = 'Changeup' THEN 'CH'
                               WHEN pitch_name = 'Knuckle Curve' THEN 'KC'
                               WHEN pitch_name = 'Forkball' THEN 'FO'
                           END AS pitch_code,
                           pitches, location_plus
                    FROM {pitch_table}
                )
                SELECT pitcher_id, pitch_code,
                       SUM(location_plus * pitches) / NULLIF(SUM(pitches), 0) AS location_plus
                FROM canonical
                WHERE pitch_code IS NOT NULL AND location_plus IS NOT NULL AND pitches > 0
                GROUP BY pitcher_id, pitch_code
                """
            ).fetchdf()
    generated = frame["generated_at"].dropna() if "generated_at" in frame else pd.Series(dtype="object")
    generated_at = str(generated.iloc[0]) if not generated.empty else None
    rows = {
        int(row["pitcher_id"]): {
            "location_plus": round(float(row["location_plus"]), 1) if pd.notna(row["location_plus"]) else None,
            "location_pitches": int(row["pitches"]) if pd.notna(row["pitches"]) else 0,
            "location_status": str(row["sample_status"]),
        }
        for row in frame.to_dict(orient="records")
    }
    pitch_rows: dict[int, dict[str, float | None]] = {}
    for row in pitch_frame.to_dict(orient="records"):
        pitcher_id = int(row["pitcher_id"])
        pitch_rows.setdefault(pitcher_id, {code: None for code in PITCH_CODES})[str(row["pitch_code"])] = (
            round(float(row["location_plus"]), 1) if pd.notna(row["location_plus"]) else None
        )
    return rows, pitch_rows, generated_at


def _load_pitching_scores(
    year: int,
    data_as_of: str | None,
    data_dir: Path,
) -> tuple[dict[int, float], dict[int, dict[str, float | None]], dict[str, Any]]:
    root = data_dir / "models" / "pitching_plus"
    csv_path = root / f"pitching_plus_pitchers_{int(year)}.csv"
    metadata_path = root / "pete_pitching_metadata.json"
    if not csv_path.exists() or not metadata_path.exists():
        return {}, {}, {"status": "unavailable", "warning": "Pitching+ 匯出尚未建立。"}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    export_date = metadata.get("data_as_of")
    if not export_date:
        parquet_path = root / f"pitching_plus_pitches_{int(year)}.parquet"
        if parquet_path.exists():
            with duckdb.connect() as connection:
                latest = connection.execute(
                    "SELECT MAX(CAST(game_date AS DATE)) FROM read_parquet(?)", [str(parquet_path)]
                ).fetchone()[0]
            export_date = str(latest)[:10] if latest else None
    status = "current" if export_date == data_as_of else "stale"
    source = {
        "status": status,
        "data_as_of": export_date,
        "generated_at": metadata.get("exported_at") or metadata.get("generated_at"),
        "model_version": metadata.get("model_version", "unknown"),
    }
    if status != "current":
        source["warning"] = (
            f"Pitching+ 截至 {export_date or 'unknown'}，逐球來源已到 {data_as_of or 'unknown'}；"
            "排行榜顯示目前可完整計算的最新 Pitching+，並分別標示截止日。"
        )
    frame = pd.read_csv(csv_path).replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(subset=["pitcher", "pitching_plus"])
    scores = {
        int(row.pitcher): round(float(row.pitching_plus), 1)
        for row in frame.itertuples()
    }
    pitch_scores: dict[int, dict[str, float | None]] = {}
    pitch_csv_path = root / f"pitching_plus_pitch_types_{int(year)}.csv"
    if pitch_csv_path.exists():
        pitch_frame = pd.read_csv(pitch_csv_path).replace([np.inf, -np.inf], np.nan)
        pitch_frame = pitch_frame.dropna(subset=["pitcher", "pitch_type", "pitching_plus", "pitches"])
        pitch_frame["display_pitch_code"] = (
            pitch_frame["pitch_type"].astype(str).map(DISPLAY_PITCH_CODE).fillna(pitch_frame["pitch_type"].astype(str))
        )
        pitch_frame = pitch_frame.loc[pitch_frame["display_pitch_code"].isin(PITCH_CODES)].copy()
        for (pitcher_id, pitch_code), group in pitch_frame.groupby(["pitcher", "display_pitch_code"]):
            weights = pd.to_numeric(group["pitches"], errors="coerce").fillna(0)
            values = pd.to_numeric(group["pitching_plus"], errors="coerce")
            valid = values.notna() & weights.gt(0)
            if not valid.any():
                continue
            pitcher_id = int(pitcher_id)
            pitch_scores.setdefault(pitcher_id, {code: None for code in PITCH_CODES})[str(pitch_code)] = round(
                float(np.average(values.loc[valid], weights=weights.loc[valid])), 1
            )
    else:
        pitch_warning = "Pitching+ 各球種匯出尚未建立；目前只顯示整體分數。"
        source["warning"] = f"{source['warning']} {pitch_warning}" if source.get("warning") else pitch_warning
    return scores, pitch_scores, source


def refresh_stuff_leaderboard(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Build one atomic, page-ready league Stuff+/Location+ snapshot."""

    root = data_dir or settings.data_dir
    source, data_as_of = _load_source(int(year), root)
    source["pitcher"] = pd.to_numeric(source["pitcher"], errors="coerce")
    source = source.dropna(subset=["pitcher"]).copy()
    source["pitcher"] = source["pitcher"].astype(int)

    feature_parts: list[pd.DataFrame] = []
    for pitcher_id, pitches in source.groupby("pitcher", sort=True):
        features = build_stuff_feature_table(pitches)
        if features.empty:
            continue
        features["pitcher_id"] = int(pitcher_id)
        hand = pitches["p_throws"].dropna().astype(str).str.upper()
        features["p_throws"] = hand.mode().iloc[0] if not hand.empty else "R"
        features["pitch_type"] = features["Pitch"].map(PITCH_TYPE_CODES).fillna("UN")
        feature_parts.append(features)
    if not feature_parts:
        raise RuntimeError("No valid Stuff+ feature rows were produced")

    feature_rows = pd.concat(feature_parts, ignore_index=True)
    artifact_dir = root / "models" / "stuff_plus"
    model, metadata = load_artifact(artifact_dir)
    scored = score_pitch_types(model, metadata, feature_rows, outing=False)
    scored["pitches"] = pd.to_numeric(scored["pitches"], errors="coerce").fillna(0)
    scored["stuff_plus"] = pd.to_numeric(scored["stuff_plus"], errors="coerce")

    basic_rows = {row.player_id: row for row in list_pitcher_leaderboard(year=int(year))}
    location_rows, location_pitch_rows, location_generated_at = _load_location_scores(int(year), root)
    pitching_rows, pitching_pitch_rows, pitching_source = _load_pitching_scores(int(year), data_as_of, root)
    output_rows: list[dict[str, Any]] = []
    for pitcher_id, group in scored.groupby("pitcher_id", sort=False):
        pitcher_id = int(pitcher_id)
        basic = basic_rows.get(pitcher_id)
        location = location_rows.get(pitcher_id, {})
        valid = group.dropna(subset=["stuff_plus"])
        total_pitches = int(valid["pitches"].sum())
        overall = (
            float(np.average(valid["stuff_plus"], weights=valid["pitches"]))
            if total_pitches > 0 else None
        )
        pitch_scores: dict[str, float | None] = {code: None for code in PITCH_CODES}
        valid = valid.copy()
        valid["display_pitch_code"] = valid["pitch_type"].map(DISPLAY_PITCH_CODE).fillna(valid["pitch_type"])
        for pitch_code, pitch_group in valid[valid["display_pitch_code"].isin(PITCH_CODES)].groupby("display_pitch_code"):
            weights = pitch_group["pitches"]
            if float(weights.sum()) > 0:
                pitch_scores[str(pitch_code)] = round(float(np.average(pitch_group["stuff_plus"], weights=weights)), 1)
        output_rows.append({
            "rank": 0,
            "player_id": pitcher_id,
            "name": basic.name if basic else str(pitcher_id),
            "team": basic.team if basic else "",
            "role": basic.role if basic else "",
            "ip": basic.ip if basic else None,
            "pitches": total_pitches,
            "pitch_type_scores": pitch_scores,
            "location_pitch_type_scores": location_pitch_rows.get(
                pitcher_id, {code: None for code in PITCH_CODES}
            ),
            "pitching_pitch_type_scores": pitching_pitch_rows.get(
                pitcher_id, {code: None for code in PITCH_CODES}
            ),
            "stuff_plus": round(overall, 1) if overall is not None else None,
            "location_plus": location.get("location_plus"),
            "pitching_plus": pitching_rows.get(pitcher_id),
            "location_pitches": location.get("location_pitches", 0),
            "location_status": location.get("location_status", "unavailable"),
        })
    output_rows.sort(key=lambda row: (row["stuff_plus"] is not None, row["stuff_plus"] or -np.inf, row["pitches"]), reverse=True)
    for index, row in enumerate(output_rows, start=1):
        row["rank"] = index

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "year": int(year),
        "data_as_of": data_as_of,
        "generated_at": generated_at,
        "model_version": str(metadata.get("model_version") or "unknown"),
        "location_generated_at": location_generated_at,
        "cache_status": "current",
        "pitch_types": PITCH_CODES,
        "total_pitchers": len(output_rows),
        "pitching_generated_at": pitching_source.get("generated_at"),
        "pitching_model_version": pitching_source.get("model_version"),
        "pitching_data_as_of": pitching_source.get("data_as_of"),
        "source_status": {
            "stuff_plus": "current",
            "location_plus": "current" if location_rows else "unavailable",
            "pitching_plus": pitching_source.get("status", "unavailable"),
        },
        "warnings": [pitching_source["warning"]] if pitching_source.get("warning") else [],
        "rows": output_rows,
    }
    path = snapshot_path(int(year), root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return {key: value for key, value in payload.items() if key != "rows"} | {"path": str(path)}


def get_stuff_leaderboard(
    year: int = 2026,
    role: str = "All",
    team: str = "All",
    minimum_ip: float = 0,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = data_dir or settings.data_dir
    path = snapshot_path(int(year), root)
    if not path.exists():
        raise FileNotFoundError(f"Stuff+ leaderboard snapshot for {int(year)} is unavailable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    current_date = _current_source_date(int(year), root)
    if payload.get("data_as_of") != current_date:
        payload["cache_status"] = "stale"
        payload.setdefault("warnings", []).append(
            f"排行榜資料截至 {payload.get('data_as_of') or 'unknown'}；逐球來源已到 {current_date or 'unknown'}。"
        )
    role_value = str(role).upper()
    team_value = str(team).upper()
    rows = []
    for row in payload.get("rows", []):
        if role_value in {"SP", "RP"} and str(row.get("role", "")).upper() != role_value:
            continue
        if team_value != "ALL" and str(row.get("team", "")).upper() != team_value:
            continue
        ip = row.get("ip")
        if ip is None or float(ip) < float(minimum_ip):
            continue
        rows.append(row)
    payload["rows"] = rows
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    payload["total_pitchers"] = len(rows)
    return payload
