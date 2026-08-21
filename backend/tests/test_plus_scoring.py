import numpy as np

from app.ml.plus_scoring import lower_is_better_plus, shrink_plus


def test_lower_xrv_maps_to_higher_plus_score():
    scores = lower_is_better_plus(
        np.array([-1.0, 0.0, 1.0]),
        mean=0.0,
        standard_deviation=1.0,
    )
    assert scores.tolist() == [110.0, 100.0, 90.0]


def test_shrinkage_is_explicit_and_converges_to_raw_score():
    adjusted, reliability = shrink_plus(
        np.array([120.0, 120.0]),
        np.array([10.0, 1000.0]),
        prior_pitches=50.0,
    )
    assert reliability[0] < reliability[1]
    assert 100.0 < adjusted[0] < adjusted[1] < 120.0

