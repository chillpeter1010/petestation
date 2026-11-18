from datetime import date

from scripts.build_pitcher_decision_workload import streak_before
from scripts.build_pitcher_decision_candidates import prior_load, nominal_eligibility, candidate_streak


def test_load_excludes_current_and_future_pitch_and_keeps_left_boundary():
    cutoff=200000.0
    times=[cutoff-86401,cutoff-86400,cutoff-1,cutoff,cutoff+1]
    assert prior_load(times,cutoff,1)==2
    assert prior_load(times,cutoff,3)==3


def test_same_day_appearance_is_not_an_extra_consecutive_day():
    day=date(2026,5,5)
    observed={date(2026,5,3),date(2026,5,4),day}
    assert streak_before(day,observed)==2
    assert streak_before(date(2026,5,7),observed)==0


def test_candidates_use_only_membership_and_predecision_constraints():
    assert nominal_eligibility(1,1,{1},{},{},True)=='current_pitcher'
    assert nominal_eligibility(2,1,{1},{2},{},True)=='removed_from_game'
    assert nominal_eligibility(2,1,{1,2},{},{},True)=='already_used'
    assert nominal_eligibility(3,1,{1},{},{3},True)=='unsupported_position_switch'
    assert nominal_eligibility(4,1,{1},{},{},False)=='change_not_statutorily_supported'
    assert nominal_eligibility(4,1,{1},{},{},True)=='nominal_candidate_operational_status_unknown'


def test_candidate_streak_counts_yesterday_but_not_doubleheader_twice():
    today=date(2026,5,5)
    assert candidate_streak('2026-05-04',2,today)==3
    assert candidate_streak('2026-05-05',2,today)==2
    assert candidate_streak('2026-05-03',4,today)==0
    assert candidate_streak(None,None,today) is None
