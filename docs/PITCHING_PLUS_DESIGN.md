# Pitching+ design proposal

## Product definition

Pitching+ should be a third, independently trained pitch-level outcome model.
It estimates the expected run value of the complete pitch: physical traits,
actual location, and game context together. It must not replace Stuff+ or
Location+, and it must not define either metric as a residual.

## Inputs

The first production candidate should use one XGBoost multiclass model with the
same twelve outcomes used by Stuff+ and Location+.

- Stuff traits: pitch type, pitcher hand, velocity, IVB, HB, spin rate, spin
  axis, release position, extension, arm angle, and differentials from the
  pitcher's primary fastball.
- Location traits: plate x, standardized plate z, batter side, batter strike
  zone, balls, strikes, outs, and base state.
- Excluded leakage: pitcher/batter name, game date, observed run value, final
  plate-appearance result, and post-pitch information.

Use 2021-2024 for training, 2025 for validation and calibration, and 2026 as an
untouched test set. Refit only after the design is frozen.

## Output and scoring

The model outputs twelve outcome probabilities. Their probability-weighted run
values produce one per-pitch `xRV_pitching`. Aggregation and plus conversion use
the same shared scoring contract as the other metrics:

```text
Pitching+ = 100 + 10 * (league_mean_xrv - observed_xrv) / league_sd_xrv
```

Only one public Pitching+ is recommended. Research diagnostics may compare
other model families, but they must not become competing production scores.

## Validation

The release gate should include:

- multiclass log loss and Brier score;
- probability calibration by outcome and pitch family;
- xRV MAE/RMSE on the 2026 test set;
- pitcher and pitch-type year-to-year stability;
- performance by count, batter side, and sample-size band;
- comparison against an additive Stuff-only + Location-only baseline.

## Stuff × Location interaction

Pitching+ cannot uniquely be reverse-engineered into a true Stuff component and
a true Location component. Once the full model learns interactions, many
different decompositions can reproduce the same prediction.

The interaction can still be estimated as a separate diagnostic:

```text
interaction(S, L) = f(S, L) - f(S, L0) - f(S0, L) + f(S0, L0)
```

`S0` and `L0` are clearly defined league-reference shape and location states.
This counterfactual term answers whether a particular shape works unusually
well or poorly at a particular location beyond their additive effects.

Two supporting checks are recommended:

1. XGBoost SHAP interaction values for local feature-pair attribution.
2. Full-model performance versus `Stuff xRV + Location xRV` as an additive
   baseline.

Publish the result as `Stuff × Location interaction`, not as another Stuff+ or
Location+ score. It is model-dependent and should include uncertainty from
bootstrap refits before it is shown in player-facing reports.

## Delivery sequence

1. Freeze and version current Stuff+/Location+ exports.
2. Build a research-only Pitching+ artifact and evaluation report.
3. Add counterfactual and SHAP interaction diagnostics in Pitcher Lab.
4. Validate stability across pitch families and seasons.
5. Only then connect Pitching+ to player, outing, and team pages.

## Pitch order research track

The public base model deliberately excludes the previous pitch. Published
baseball research nevertheless finds measurable within-plate-appearance
dependence in pitch type, location, velocity, and movement. The training code
therefore maintains a separate sequence challenger with previous pitch type,
pitch number, and physical/location differences from the preceding pitch.

Sequence rows are ordered only inside the same game and plate appearance; lag
features are reset at every new plate appearance. The challenger is compared
with the base model on the same 2025 validation and 2026 test rows. It does not
replace public Pitching+ unless it improves log loss, Brier score, calibration,
run-value error, and pitcher-level stability rather than only in-sample fit.

This is distinct from game-level fatigue or season-level time trends. Those are
separate longitudinal questions and should not be mixed into the definition of
single-pitch quality.
