import duckdb
import numpy as np
import pandas as pd
import pytest

from app.services.batter_zone_rates_service import aggregate_zone_rates, read_rows


def season(pa=31):
    return pd.DataFrame([dict(game_pk=1, at_bat_number=i+1, pitch_number=1,
        events="field_out", description="called_strike", p_throws="R",
        plate_x=0.0, plate_z=2.5, sz_bot=1.5, sz_top=3.5) for i in range(pa)])


def center(result):
    return next(c for c in result.cells if c.id == "zone-1-1")


def test_full_season_pa_strict_boundary_and_split_independence():
    assert not aggregate_zone_rates(season(30), 2026, 5, "R").eligible
    result = aggregate_zone_rates(season(31), 2026, 5, "L")
    assert result.eligible and result.season_pa == 31 and result.split_pitches == 0
    assert result.status == "no_data" and all(c.rates["contact"].value is None for c in result.cells)


def test_unique_completed_pa_not_pitch_count():
    rows = pd.concat([season(30)]*3, ignore_index=True)
    rows.loc[len(rows)] = dict(season(1).iloc[0], at_bat_number=100, events="truncated_pa")
    assert aggregate_zone_rates(rows, 2026, 5, "All").season_pa == 30


def test_hand_and_denominators_reuse_flags_without_complement_assumption():
    rows = season()
    rows.loc[:3, "p_throws"] = "L"
    rows.loc[:3, "description"] = ["hit_into_play", "foul", "swinging_strike", "called_strike"]
    cell = center(aggregate_zone_rates(rows, 2026, 5, "L"))
    assert cell.pitches == 4
    assert cell.rates["swing"].value == 75
    assert cell.rates["contact"].numerator == 2 and cell.rates["contact"].denominator == 3
    assert cell.rates["whiff"].numerator == 1 and cell.rates["whiff"].denominator == 3
    assert cell.rates["swstr"].value == 25 and cell.rates["csw"].value == 50
    assert cell.rates["o_swing"].value is None
    assert center(aggregate_zone_rates(rows, 2026, 5, "R")).rates["swing"].value == 0


def test_cell_partition_edges_missing_locations_and_zone_height_fallback():
    rows = season()
    rows.loc[:7, "plate_x"] = [-17/24, 17/24, -2, 2, 0, 0, -2, 2]
    rows.loc[:7, "plate_z"] = [1.5, 3.5, 2.5, 2.5, 8, -2, 8, -2]
    rows.loc[8, "plate_x"] = np.nan
    rows.loc[9, "plate_z"] = np.inf
    rows.loc[10, "sz_bot"] = 4
    result = aggregate_zone_rates(rows, 2026, 5, "All")
    assert len(result.cells) == 17
    assert result.located_pitches == 29 and result.missing_location_pitches == 2
    assert result.zone_height_fallback_pitches == 1
    assert sum(c.pitches for c in result.cells) == 29
    assert all(c.rates["z_contact"].value is None for c in result.cells if c.region == "outside")
    assert result.model_dump(mode="json")


def test_height_normalization_and_unknown_hand_do_not_default_to_right():
    rows = season()
    rows.loc[0, ["sz_bot", "sz_top", "plate_z", "p_throws"]] = [2, 5, 3.5, "-"]
    all_result = aggregate_zone_rates(rows, 2026, 5, "All")
    right = aggregate_zone_rates(rows, 2026, 5, "R")
    assert center(all_result).pitches == 31 and center(right).pitches == 30
    assert aggregate_zone_rates(None, 2026, 5, "R").status == "unavailable"


def test_db_query_prefers_enriched_regular_season_and_selected_batter(tmp_path):
    path = tmp_path / "season.duckdb"
    rows = season().assign(batter=5, game_type="R")
    extra = pd.concat([rows.assign(batter=6), rows.assign(game_type="P")])
    enriched = pd.concat([rows, extra])
    with duckdb.connect(str(path)) as conn:
        conn.register("fixture", enriched)
        conn.execute("CREATE TABLE pitches_enriched AS SELECT * FROM fixture")
        conn.execute("CREATE TABLE pitches AS SELECT * FROM fixture LIMIT 1")
    loaded = read_rows(str(path), 5)
    assert len(loaded) == 31 and aggregate_zone_rates(loaded, 2026, 5, "R").eligible


def test_nullable_locations_are_counted_missing_not_zero_percent():
    rows = season()
    rows["plate_x"] = pd.Series([pd.NA]*31, dtype="Float64")
    result = aggregate_zone_rates(rows, 2026, 5, "R")
    assert result.eligible and result.missing_location_pitches == 31
    assert result.located_pitches == 0 and result.status == "no_data"


def test_outcome_metrics_have_distinct_ab_woba_and_tracked_bbe_denominators():
    rows = season()
    rows["launch_speed"] = np.nan
    rows["woba_value"] = np.nan
    rows["woba_denom"] = np.nan
    rows.loc[:3, "p_throws"] = "L"
    rows.loc[:3, "events"] = ["single", "double", "walk", "strikeout"]
    rows.loc[:3, "description"] = ["hit_into_play", "hit_into_play", "ball", "swinging_strike"]
    rows.loc[:3, "woba_value"] = [.88, 1.25, .69, 0]
    rows.loc[:3, "woba_denom"] = 1
    rows.loc[:1, "launch_speed"] = [94.9, 95.0]
    result = aggregate_zone_rates(rows, 2026, 5, "L")
    cell = center(result)
    assert len(result.metrics) == 16
    assert cell.rates["avg"].denominator == 3 and cell.rates["avg"].value == pytest.approx(2/3)
    assert cell.rates["woba"].numerator == pytest.approx(2.82)
    assert cell.rates["woba"].value == pytest.approx(.705)
    assert cell.rates["hard_hit"].numerator == 1 and cell.rates["hard_hit"].denominator == 2
    assert cell.rates["hard_hit"].value == 50


def test_missing_weights_ev_and_nonterminal_pitch_do_not_get_fake_outcomes():
    rows = season()
    rows["launch_speed"] = np.nan
    rows["woba_value"] = np.nan
    rows["woba_denom"] = np.nan
    rows.loc[0, ["events", "pitch_number"]] = ["single", 2]
    early = rows.iloc[[0]].copy()
    early["pitch_number"] = 1
    early["plate_x"] = -.5
    early["launch_speed"] = 110.0  # Stray duplicated metadata must not count.
    rows = pd.concat([early, rows], ignore_index=True)
    result = aggregate_zone_rates(rows, 2026, 5, "R")
    assert sum(c.rates["avg"].denominator for c in result.cells) == 31
    assert center(result).rates["avg"].numerator == 1
    assert all(c.rates["woba"].value is None for c in result.cells)
    assert all(c.rates["hard_hit"].value is None for c in result.cells)


def test_woba_above_one_and_real_zero_are_preserved():
    rows = season()
    rows["woba_value"] = np.nan
    rows["woba_denom"] = np.nan
    rows.loc[0, "p_throws"] = "L"
    rows.loc[0, "events"] = "home_run"
    rows.loc[0, "woba_value"] = 2.1
    rows.loc[0, "woba_denom"] = 1
    cell = center(aggregate_zone_rates(rows, 2026, 5, "L"))
    assert cell.rates["woba"].value == 2.1
    assert cell.rates["avg"].value == 1
    assert center(aggregate_zone_rates(rows, 2026, 5, "R")).rates["avg"].value == 0
