from datetime import date

import pandas as pd
import pytest

from app.services.pitch_scout_service import build_context


def history():
    return pd.DataFrame([dict(game_date="2026-06-01",game_pk=1,at_bat_number=pa,pitcher=7,pitch_number=p,
        events="field_out" if p==2 else "",description="called_strike" if p==1 else "foul",
        p_throws="R",stand="L",balls=0,strikes=p-1,pitch_type="FF" if p==1 else "SL",
        plate_x=0,plate_z=2.5,sz_bot=1.5,sz_top=3.5,launch_speed=None) for pa in range(40) for p in (1,2)])


def run(rows, **kw):
    args=dict(year=2026,batter_id=5,hand="R",stand="L",before=date(2026,7,1),balls=0,strikes=1,previous_type="FF",previous_result="called_strike")
    return build_context(rows,**(args|kw))


def test_strict_prior_date_and_context_without_future_leak():
    rows=history()
    result=run(rows)
    future=rows.copy();future.game_date="2026-07-01";future.description="swinging_strike"
    assert run(pd.concat([rows,future])).model_dump()==result.model_dump()
    assert result.context_pitches==40 and result.swing_pct==100 and result.take_pct==0
    assert result.target.zone=="Zone row 2, col 2"
    assert result.candidates[0]["family"]=="Breaking"
    assert sum(c.pitches for c in result.heatmap.cells)==40
    assert result.heatmap.benchmark_status=="context_rates"
    assert all(r.color_pr is None for c in result.heatmap.cells for r in c.rates.values())


def test_backoff_missing_predecessor_hands_and_minimum_history():
    rows=history()
    assert run(rows,previous_type="__missing__").tier=="Exact count"
    assert run(rows,previous_type="CH").tier=="Exact count"
    assert run(rows,hand="L").status=="insufficient_history"
    assert run(rows,stand="R").target is None
    assert run(rows,before=date(2026,6,1)).swing_pct is None
    assert run(rows.iloc[:40]).status=="insufficient_history"
    assert run(rows[rows.pitch_number.eq(2)]).tier=="Exact count"


def test_broad_count_fallback_and_raw_denominators():
    rows=history()
    result=run(rows,balls=1,strikes=2)
    assert result.status=="insufficient_history"
    rows.loc[rows.pitch_number.eq(2),["balls","strikes"]]=[1,2]
    result=run(rows,balls=0,strikes=2)
    assert result.tier=="Two strikes"
    cell=next(c for c in result.heatmap.cells if c.id=="zone-1-1")
    assert cell.rates["contact"].denominator==40
    assert cell.rates["contact"].value==100
    assert cell.rates["hard_hit"].value is None


def test_outer_partition_and_terminal_ev_only():
    rows=history()
    mask=rows.pitch_number.eq(2)
    rows.loc[mask,"description"]="hit_into_play"
    rows.loc[mask,"launch_speed"]=100
    rows.loc[mask,"plate_x"]=[-2,2,0,0]*10
    rows.loc[mask,"plate_z"]=[2.5,2.5,0,6]*10
    result=run(rows)
    assert len(result.heatmap.cells)==17
    assert sum(c.pitches for c in result.heatmap.cells)==40
    assert sum(c.rates["hard_hit"].denominator for c in result.heatmap.cells)==40
    assert result.swing_pct==pytest.approx(100)


def test_unknown_and_automatic_penalties_do_not_become_takes():
    rows=history()
    extra=rows.copy();extra.at_bat_number+=100;extra.description="automatic_strike"
    assert run(pd.concat([rows,extra])).context_pitches==40
    assert run(rows.assign(description=None)).swing_pct is None
    assert run(rows.assign(balls=None)).status=="insufficient_history"
