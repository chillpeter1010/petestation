import json

import pytest

from app.api.schemas.batter_zone_rates import BatterZoneRatesResponse
from app.services import batter_zone_baseline_service as baseline


def response(value, denominator=20, metric="whiff"):
    return BatterZoneRatesResponse(year=2026, batter_id=1, pitcher_hand="R", status="ready", season_pa=31,
        eligible=True, split_pitches=20, located_pitches=20, missing_location_pitches=0,
        zone_height_fallback_pitches=0, metrics=[], cells=[dict(id="zone-1-1", label="Center", region="zone",
            bounds=(1/3,1/3,2/3,2/3), pitches=20,
            rates={metric: dict(numerator=value/100*denominator, denominator=denominator, value=value)})])


def test_midrank_handles_ties_and_small_peer_groups():
    assert baseline.rank_pr(20, [10,20,30,40,50]) == 30
    assert baseline.rank_pr(20, [20]*5) == 50
    assert baseline.rank_pr(100, [20]*5) == 100
    assert baseline.rank_pr(20, [20]*4) is None


def test_weighted_mean_is_not_unweighted_average_and_low_sample_excluded():
    groups = {}
    baseline.add_population(groups, response(20, 10))
    baseline.add_population(groups, response(80, 30))
    baseline.add_population(groups, response(100, 1))
    group = baseline.finalize(groups)["R|zone-1-1|whiff"]
    assert group["league_average"] == pytest.approx(65)
    assert group["peer_count"] == 2 and group["values"] == [20,80]


def artifact(tmp_path, monkeypatch, metric="whiff"):
    db = tmp_path / "mlb_2026.duckdb"
    db.touch()
    monkeypatch.setattr(baseline, "signature", lambda _: {"revision":1})
    groups = {}
    for v in [10,20,30,40,50]: baseline.add_population(groups, response(v, metric=metric))
    data = dict(version=baseline.VERSION, year=2026, source={"revision":1}, groups=baseline.finalize(groups))
    baseline.baseline_path(db).write_text(json.dumps(data), encoding="utf-8")
    return db


def test_batter_direction_reversal_and_cached_raw_response_not_mutated(tmp_path, monkeypatch):
    db = artifact(tmp_path, monkeypatch)
    raw = response(20)
    result = baseline.apply_benchmark(raw, db)
    rate = result.cells[0].rates["whiff"]
    assert result.benchmark_status == "ready"
    assert rate.raw_pr == 30 and rate.color_pr == 70 and rate.league_average == 30
    assert raw.cells[0].rates["whiff"].color_pr is None
    assert baseline.apply_benchmark(response(20, denominator=9), db).cells[0].rates["whiff"].color_pr is None


@pytest.mark.parametrize("metric", ["swing", "contact"])
def test_frequency_and_higher_metrics_preserve_raw_pr(tmp_path, monkeypatch, metric):
    db = artifact(tmp_path, monkeypatch, metric)
    rate = baseline.apply_benchmark(response(20, metric=metric), db).cells[0].rates[metric]
    assert rate.raw_pr == rate.color_pr == 30


def test_missing_and_stale_references_never_fall_back_to_absolute_colors(tmp_path, monkeypatch):
    db = artifact(tmp_path, monkeypatch)
    monkeypatch.setattr(baseline, "signature", lambda _: {"revision":2})
    result = baseline.apply_benchmark(response(100), db)
    assert result.benchmark_status == "stale" and result.cells[0].rates["whiff"].color_pr is None
    baseline.baseline_path(db).unlink()
    assert baseline.apply_benchmark(response(100), db).benchmark_status == "unavailable"
