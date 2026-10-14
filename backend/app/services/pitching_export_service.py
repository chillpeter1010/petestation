import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.pitching import (
    PitchingDistributionBin,
    PitchingLeaderboardRow,
    PitchingOutingRow,
    PitchingOverviewResponse,
    PitchingPitcherResponse,
    PitchingPitchTypeRow,
)
from app.core.config import settings


PITCH_NAMES = {
    "FF": "4-Seam", "SI": "Sinker", "FC": "Cutter", "FS": "Splitter",
    "SL": "Slider", "ST": "Sweeper", "CU": "Curveball", "KC": "Knuckle Curve",
    "CH": "Changeup", "FO": "Forkball", "SC": "Screwball",
}


def _artifact_dir(root: Path | None = None) -> Path:
    return (root or settings.data_dir) / "models" / "pitching_plus"


def _identity_map(year: int, data_root: Path | None = None) -> dict[int, tuple[str, str]]:
    db = (data_root or settings.data_dir) / f"MLB{year}" / f"mlb_{year}.duckdb"
    if not db.exists():
        return {}
    conn = duckdb.connect(str(db), read_only=True)
    try:
        rows = conn.execute("""
            SELECT CAST(pitcher AS BIGINT), arg_max(player_name, game_date),
                   mode(CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END)
            FROM pitches WHERE pitcher IS NOT NULL GROUP BY pitcher
        """).fetchall()
        return {int(pid): (str(name or pid), str(team or "—")) for pid, name, team in rows}
    finally:
        conn.close()


def _metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Pitching+ metadata not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _freshness(meta: dict) -> tuple[str | None, str | None, str, list[str]]:
    data_as_of = str(meta.get("data_as_of")) if meta.get("data_as_of") else None
    source_data_as_of = str(meta.get("source_data_as_of")) if meta.get("source_data_as_of") else data_as_of
    status = "current" if data_as_of and data_as_of == source_data_as_of else "stale"
    warnings: list[str] = []
    if status == "stale":
        warnings.append(
            f"Pitching+ 完整特徵資料截至 {data_as_of or 'unknown'}；逐球來源截至 "
            f"{source_data_as_of or 'unknown'}。缺少模型必要特徵的日期未納入推論。"
        )
    return data_as_of, source_data_as_of, status, warnings


def _ip_to_outs(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    whole, _, fraction = text.partition(".")
    return max(0, int(float(whole)) * 3 + min(2, int((fraction or "0")[:1])))


def _innings_map(year: int, data_root: Path | None = None) -> dict[int, float]:
    db = (data_root or settings.data_dir) / f"MLB{year}" / f"mlb_{year}.duckdb"
    if not db.exists():
        return {}
    conn = duckdb.connect(str(db), read_only=True)
    try:
        lines = conn.execute("SELECT pitcher_id, ip FROM pitcher_game_lines WHERE pitcher_id IS NOT NULL").fetchall()
    finally:
        conn.close()
    outs: dict[int, int] = {}
    for pitcher_id, innings in lines:
        pid = int(pitcher_id)
        outs[pid] = outs.get(pid, 0) + _ip_to_outs(innings)
    return {pid: (value // 3) + (value % 3) / 10 for pid, value in outs.items()}


def _available_years(root: Path) -> list[int]:
    years: list[int] = []
    for path in root.glob("pitching_plus_pitchers_*.csv"):
        try:
            years.append(int(path.stem.rsplit("_", 1)[-1]))
        except ValueError:
            continue
    return sorted(set(years), reverse=True)


def _pitch_type_map(root: Path, year: int) -> dict[int, dict[str, float]]:
    path = root / f"pitching_plus_pitch_types_{year}.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path).replace([np.inf, -np.inf], np.nan).dropna(subset=["pitching_plus"])
    result: dict[int, dict[str, float]] = {}
    for record in frame.itertuples():
        result.setdefault(int(record.pitcher), {})[str(record.pitch_type)] = round(float(record.pitching_plus), 1)
    return result


def _row(
    record,
    rank: int,
    identities: dict[int, tuple[str, str]],
    innings: dict[int, float] | None = None,
    pitch_types: dict[int, dict[str, float]] | None = None,
) -> PitchingLeaderboardRow:
    pid = int(record.pitcher)
    name, team = identities.get(pid, (str(pid), "—"))
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        name = f"{first} {last}".strip()
    return PitchingLeaderboardRow(rank=rank, pitcher_id=pid, pitcher_name=name, team=team,
        pitches=int(record.pitches), innings_pitched=(innings or {}).get(pid, 0.0),
        pitch_type_scores=(pitch_types or {}).get(pid, {}), pitching_plus=round(float(record.pitching_plus), 1),
        xrv_per_100=round(float(record.xrv_pitching) * 100, 3))


def get_pitching_overview(
    year: int = 2026,
    minimum_pitches: int = 0,
    minimum_innings: float = 0,
    data_root: Path | None = None,
) -> PitchingOverviewResponse:
    root = _artifact_dir(data_root)
    csv_path = root / f"pitching_plus_pitchers_{year}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Pitching+ export not found: {csv_path}")
    meta = _metadata(root / "pete_pitching_metadata.json")
    frame = pd.read_csv(csv_path).replace([np.inf, -np.inf], np.nan).dropna(subset=["pitching_plus"])
    innings = _innings_map(year, data_root)
    pitch_types = _pitch_type_map(root, year)
    frame["innings_pitched"] = frame["pitcher"].astype(int).map(innings).fillna(0.0)
    frame = frame[(frame["pitches"] >= minimum_pitches) & (frame["innings_pitched"] >= minimum_innings)]
    frame = frame.sort_values("pitching_plus", ascending=False).reset_index(drop=True)
    identities = _identity_map(year, data_root)
    rows = [_row(row, index + 1, identities, innings, pitch_types) for index, row in enumerate(frame.itertuples())]
    values = frame["pitching_plus"].to_numpy(float)
    edges = np.arange(60, 146, 5, dtype=float)
    counts, edges = np.histogram(np.clip(values, 60, 145), bins=edges)
    distribution = [PitchingDistributionBin(low=float(edges[i]), high=float(edges[i + 1]), count=int(counts[i])) for i in range(len(counts))]
    candidates = {name: {"validation_metrics": value.get("validation_metrics", {}), "test_metrics": value.get("test_metrics", {})}
                  for name, value in meta.get("candidates", {}).items()}
    data_as_of, source_data_as_of, cache_status, warnings = _freshness(meta)
    return PitchingOverviewResponse(year=year, data_as_of=data_as_of, source_data_as_of=source_data_as_of,
        cache_status=cache_status, warnings=warnings, available_years=_available_years(root),
        generated_at=meta.get("exported_at") or meta.get("generated_at"), model_version=meta.get("model_version", "unknown"),
        public_candidate=meta.get("public_candidate", "base"), minimum_pitches=minimum_pitches, minimum_innings=minimum_innings, total_pitchers=len(rows),
        total_pitches=int(frame["pitches"].sum()), median=round(float(np.median(values)), 1) if len(values) else 0,
        p10=round(float(np.percentile(values, 10)), 1) if len(values) else 0, p90=round(float(np.percentile(values, 90)), 1) if len(values) else 0,
        rows=rows, distribution=distribution, candidates=candidates)


def get_pitching_pitcher(year: int, pitcher_id: int, data_root: Path | None = None) -> PitchingPitcherResponse:
    root = _artifact_dir(data_root)
    meta = _metadata(root / "pete_pitching_metadata.json")
    identities = _identity_map(year, data_root)
    overall = pd.read_csv(root / f"pitching_plus_pitchers_{year}.csv")
    match = overall[overall["pitcher"].astype(int) == pitcher_id]
    if match.empty:
        raise FileNotFoundError(f"Pitcher {pitcher_id} not found in {year} Pitching+ export")
    row = _row(match.iloc[0], 0, identities, _innings_map(year, data_root), _pitch_type_map(root, year))
    pitch_types = pd.read_csv(root / f"pitching_plus_pitch_types_{year}.csv")
    pitch_types = pitch_types[pitch_types["pitcher"].astype(int) == pitcher_id].sort_values("pitches", ascending=False)
    type_rows = [PitchingPitchTypeRow(pitch_type=PITCH_NAMES.get(str(r.pitch_type), str(r.pitch_type)), pitches=int(r.pitches),
        pitching_plus=round(float(r.pitching_plus), 1), xrv_per_100=round(float(r.xrv_pitching) * 100, 3)) for r in pitch_types.itertuples()]
    parquet = root / f"pitching_plus_pitches_{year}.parquet"
    conn = duckdb.connect()
    try:
        outings = conn.execute("""SELECT CAST(game_pk AS BIGINT) game_pk, CAST(game_date AS VARCHAR) game_date, count(*) pitches,
            avg(pitching_plus) pitching_plus, avg(xrv_pitching) * 100 xrv_per_100
            FROM read_parquet(?) WHERE CAST(pitcher AS BIGINT) = ? GROUP BY game_pk, game_date ORDER BY game_date""",
            [str(parquet), pitcher_id]).fetchdf()
    finally:
        conn.close()
    outing_rows = [PitchingOutingRow(game_pk=int(r.game_pk), game_date=str(r.game_date), pitches=int(r.pitches),
        pitching_plus=round(float(r.pitching_plus), 1), xrv_per_100=round(float(r.xrv_per_100), 3)) for r in outings.itertuples()]
    data_as_of, _, cache_status, warnings = _freshness(meta)
    return PitchingPitcherResponse(
        year=year, data_as_of=data_as_of, cache_status=cache_status, warnings=warnings,
        pitcher=row, pitch_types=type_rows, outings=outing_rows,
    )
