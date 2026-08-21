"""Shared scoring helpers for lower-is-better expected run values.

The model-specific modules remain responsible for predicting xRV.  This module
only owns the public plus-scale contract used after prediction:

1. convert an xRV estimate to a league-centred raw plus score;
2. optionally shrink small samples toward 100;
3. report the reliability used by that shrinkage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def lower_is_better_plus(
    values: pd.Series | np.ndarray,
    *,
    mean: float,
    standard_deviation: float,
    points_per_sd: float = 10.0,
) -> np.ndarray:
    """Map lower-is-better values to a 100-centred plus scale."""

    if not np.isfinite(standard_deviation) or standard_deviation <= 0:
        raise ValueError("Plus-score standard deviation must be positive")
    numeric = np.asarray(values, dtype="float64")
    return 100.0 + points_per_sd * (float(mean) - numeric) / float(standard_deviation)


def shrink_plus(
    raw_scores: pd.Series | np.ndarray,
    sample_sizes: pd.Series | np.ndarray,
    *,
    prior_pitches: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Shrink raw plus scores toward 100 using an explicit sample-size prior."""

    scores = np.asarray(raw_scores, dtype="float64")
    samples = np.maximum(np.asarray(sample_sizes, dtype="float64"), 0.0)
    if prior_pitches < 0:
        raise ValueError("prior_pitches cannot be negative")
    if prior_pitches == 0:
        reliability = np.ones_like(samples)
    else:
        reliability = samples / (samples + float(prior_pitches))
    return 100.0 + reliability * (scores - 100.0), reliability

