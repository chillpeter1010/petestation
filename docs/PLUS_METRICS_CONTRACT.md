# Stuff+ and Location+ scoring contract

This document defines the production scoring contract shared by the API,
exports, labs, player pages, outing reports, team pages, and update jobs.

## Public metrics

The product publishes one production Stuff+ and one production Location+.

- **Peter Stuff+** predicts the outcome probabilities of a pitch from its
  physical shape and release traits, evaluates that shape over shared league
  contexts, converts the expected run value to a pitch-type scale, and applies
  explicit small-sample shrinkage.
- **Peter Location+** predicts the outcome probabilities of the actual plate
  location in its count, handedness, pitch-type, and game-state context. It
  intentionally excludes velocity, movement, spin, release point, extension,
  arm angle, and pitcher identity.

Both models use the same twelve-outcome vocabulary and the same outcome-to-run
value conversion. They are separate predictive models; Location+ is not the
residual of Pitching+ after subtracting Stuff+.

## Two score surfaces, one underlying prediction

Every pitch receives one model-produced expected run value (xRV). That xRV may
be exposed on no more than two score surfaces:

1. **Per-pitch display score**: used in tooltips and heatmaps. It is calibrated
   on the per-pitch distribution and is not shrunk.
2. **Aggregate report score**: used for outings, pitch types, seasons, and
   leaderboards. It first averages the exact same per-pitch xRV values, then
   standardizes that average against the relevant league distribution and may
   shrink small samples toward 100.

The two surfaces are not two predictive algorithms. They share the same xRV;
their numerical ranges differ because a single-pitch distribution is much
wider than a multi-pitch average distribution.

For any lower-is-better xRV value:

```text
raw_plus = 100 + 10 * (league_mean_xrv - observed_xrv) / league_sd_xrv
reliability = pitches / (pitches + prior_pitches)
reported_plus = 100 + reliability * (raw_plus - 100)
```

The export stores `raw_*`, `reliability`, the reported plus score, sample size,
and standard error so a consumer never needs to recreate the score.

The current aggregation contract is identified as
`location_plus_aggregate_v2`, independently of the predictive
`model_version`.

## Production aggregation

Location+ is computed once during `export_location_scores.py` and stored in
`data/derived/location_plus_scores.duckdb`.

| Level | Small-sample prior |
| --- | ---: |
| Pitcher season | 50 pitches |
| Pitcher season × batter side | 25 pitches |
| Pitcher season × pitch type | 50 pitches |
| Outing | 15 pitches |
| Outing × pitch type | 15 pitches |

These priors are product calibration constants, not learned model features.
Changing one requires a model-version change and representative-player review.

The following tables are the only aggregate Location+ sources:

- `location_pitcher_scores_{year}`
- `location_side_scores_{year}`
- `location_pitch_type_scores_{year}`
- `location_outing_scores_{year}`
- `location_outing_pitch_type_scores_{year}`

API services must read these exports. They must not fit a regression, rebuild a
league scale, or reshrink scores at request time.

## Stuff+ calculator policy

The Stuff+ Pitch Designer uses the interaction pattern popularized by Lance
Brodowski: change a hypothetical pitch and immediately inspect the score. The
number displayed is still the Peter production Stuff+ model. It is not a second
Lance model and it must not be labelled as an independently reproduced Lance
score unless a verifiable specification and implementation are added later.

The older deterministic shape proxy is fallback/debug output only. It is not a
public Stuff+ algorithm.

## Refresh contract

The normal game-data refresh must run model inference and rebuild all five
Location+ aggregate tables after pitch ingestion. Newly ingested pitches are
therefore available to tooltips and aggregate pages from the same completed
refresh. A refresh is incomplete if the newest pitch date is later than the
Location+ manifest date.

## Change checklist

Any model or scoring change must include:

1. a new `model_version` or scoring-version identifier;
2. time-based train/validation/test results;
3. per-pitch and aggregate calibration checks;
4. representative pitch-type and pitcher reviews;
5. a full historical export backfill;
6. backend tests and frontend type checking.
