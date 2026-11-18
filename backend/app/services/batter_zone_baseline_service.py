"""Versioned, offline same-zone batter comparisons; never build a season in HTTP."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile

from app.api.schemas.batter_zone_rates import BatterZoneRatesResponse

VERSION = "batter_zone_pr_v1"
MIN_DENOMINATOR = 10
MIN_PEERS = 5


@lru_cache(maxsize=8)
def _pitch_fingerprint(path: str, mtime: int, size: int, wal_mtime: int, wal_size: int) -> dict:
    import duckdb
    from app.repositories.pitch_repository import resolve_pitch_table
    from app.services.batter_zone_rates_service import COLUMNS
    with duckdb.connect(path, read_only=True) as conn:
        table = resolve_pitch_table({r[0] for r in conn.execute("SHOW TABLES").fetchall()})
        if not table:
            raise ValueError("Regular-season pitch table unavailable")
        columns = {r[0] for r in conn.execute(f"DESCRIBE {table}").fetchall()}
        fields = ', '.join(f'"{c}"' if c in columns else 'NULL' for c in ('batter', *COLUMNS))
        # Order-independent content signature of ONLY the rows/columns used by
        # zone rates. Video lookup writes must not invalidate the PR population.
        count, xor, total = conn.execute(f"SELECT count(*), bit_xor(hash({fields})), sum(hash({fields})::HUGEINT) FROM {table} WHERE game_type = 'R'").fetchone()
    # Compare the actual content hashes, not a producer's patch-version label.
    return dict(rows=count, xor=str(xor), total=str(total))


def signature(db: Path) -> dict:
    from app.services.batter_zone_rates_service import aggregate_zone_rates, read_rows, COLUMNS, METRICS
    from app.services.batter_service import _count_plate_appearances
    from app.services.discipline_service import add_discipline_flags, SWING_EVENTS, WHIFF_EVENTS, HIT_EVENTS, NON_AB_EVENTS, IN_PLAY_EVENTS, FOUL_EVENTS, CALLED_STRIKE_EVENTS
    algorithm = inspect.getsource(aggregate_zone_rates) + inspect.getsource(read_rows) + inspect.getsource(_count_plate_appearances) + inspect.getsource(add_discipline_flags) + repr((COLUMNS, METRICS))
    algorithm += repr([sorted(s) for s in (SWING_EVENTS, WHIFF_EVENTS, HIT_EVENTS, NON_AB_EVENTS, IN_PLAY_EVENTS, FOUL_EVENTS, CALLED_STRIKE_EVENTS)])
    wal = db.with_suffix(db.suffix + ".wal")
    stat, wal_stat = db.stat(), wal.stat() if wal.exists() else None
    return {"database": str(db.resolve()),
            "pitches": _pitch_fingerprint(str(db), stat.st_mtime_ns, stat.st_size, wal_stat.st_mtime_ns if wal_stat else 0, wal_stat.st_size if wal_stat else 0),
            "algorithm_sha256": hashlib.sha256(algorithm.encode()).hexdigest()}


def baseline_path(db: Path) -> Path:
    return db.parent / "batter_zone_baseline_v1.json"


def rank_pr(value: float, population: list[float]) -> float | None:
    if len(population) < MIN_PEERS:
        return None
    # Midrank keeps equal-valued populations neutral (all ties -> PR50).
    return 100 * (bisect_left(population, value) + bisect_right(population, value)) / (2 * len(population))


def add_population(groups: dict, response: BatterZoneRatesResponse) -> None:
    if not response.eligible:
        return
    for cell in response.cells:
        for metric, rate in cell.rates.items():
            if rate.value is None or rate.denominator < MIN_DENOMINATOR:
                continue
            key = f"{response.pitcher_hand}|{cell.id}|{metric}"
            group = groups.setdefault(key, {"numerator": 0, "denominator": 0, "values": []})
            group["numerator"] += rate.numerator
            group["denominator"] += rate.denominator
            group["values"].append(rate.value)


def finalize(groups: dict) -> dict:
    for key, group in groups.items():
        metric = key.rsplit("|", 1)[1]
        group["values"].sort()
        group["peer_count"] = len(group["values"])
        group["league_average"] = group["numerator"] / group["denominator"] * (1 if metric in {"avg", "woba"} else 100)
    return groups


def build_baseline(year: int, db: Path, progress=print) -> dict:
    from app.services.batter_zone_rates_service import aggregate_zone_rates, read_rows
    from app.services.batter_service import _count_plate_appearances
    before = signature(db)
    progress(f"Reading {year} regular-season rows (read-only)…")
    rows = read_rows(str(db), None)
    if rows is None:
        raise ValueError("Regular-season source unavailable")
    rows["events"] = rows["events"].fillna("").astype(str).str.strip().str.lower()
    groups, qualified = {}, 0
    players = list(rows.groupby("batter", sort=True))
    progress(f"Loaded {len(rows)} pitches / {len(players)} batters; aggregating qualified players…")
    for index, (batter_id, player) in enumerate(players, 1):
        if _count_plate_appearances(player) > 30:
            qualified += 1
            for hand in ("All", "L", "R"):
                add_population(groups, aggregate_zone_rates(player, year, int(batter_id), hand))
        if index % 20 == 0:
            progress(f"Progress {index}/{len(players)} batters; {qualified} qualified")
    if signature(db) != before:
        raise ValueError("Source changed during preprocessing; no stale artifact published")
    artifact = {"version": VERSION, "year": year, "created_at": datetime.now(timezone.utc).isoformat(),
                "source": before, "min_pa_exclusive": 30, "min_denominator": MIN_DENOMINATOR,
                "min_peers": MIN_PEERS, "qualified_batters": qualified,
                "cohort": "Same season/hand/zone/metric; season PA>30 and cell denominator>=10; equal-batter midrank PR, denominator-weighted league mean",
                "groups": finalize(groups)}
    output = baseline_path(db)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, suffix=".tmp", delete=False) as f:
        temporary = Path(f.name)
        json.dump(artifact, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    os.replace(temporary, output)
    progress(f"Saved {output.name}: {qualified} qualified batters / {len(groups)} reference groups")
    return artifact


@lru_cache(maxsize=8)
def _load(path: str, mtime: int, size: int) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_benchmark(result: BatterZoneRatesResponse, db: Path) -> BatterZoneRatesResponse:
    from app.services.batter_zone_rates_service import metric_direction
    # Never mutate the cached raw per-batter response.
    result = result.model_copy(deep=True)
    path = baseline_path(db)
    if not path.exists():
        return result
    try:
        stat = path.stat()
        artifact = _load(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        result.benchmark_status = "invalid"
        return result
    if artifact.get("version") != VERSION or artifact.get("year") != result.year or artifact.get("source") != signature(db):
        result.benchmark_status = "stale"
        return result
    result.benchmark_status = "ready"
    result.benchmark_version = VERSION
    for cell in result.cells:
        for metric, rate in cell.rates.items():
            group = artifact["groups"].get(f"{result.pitcher_hand}|{cell.id}|{metric}")
            if not group:
                continue
            rate.league_average, rate.peer_count = group["league_average"], group["peer_count"]
            rate.benchmark_status = "low_sample" if rate.denominator < MIN_DENOMINATOR else "few_peers" if rate.peer_count < MIN_PEERS else "ready"
            if rate.value is None or rate.benchmark_status != "ready":
                continue
            rate.raw_pr = rank_pr(rate.value, group["values"])
            rate.color_pr = 100 - rate.raw_pr if metric_direction(metric) == "lower" else rate.raw_pr
    return result
