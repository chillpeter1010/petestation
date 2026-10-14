# Petehub Project Tracker

Updated: 2026-10-07

This file is generated from `docs/PROJECT_TRACKER.json`. Update the JSON first.

## Batter Comparison & Research

- Status: **done**
- Progress: **100%** (10/10 slices)
- Owner area: Batters
- Updated: 2026-09-26
- Summary: Period comparison, tracking, timing, team research and lineup simulation are complete; hitter period comparison now shares the pitcher workflow shell and transfer-stint controls.
- Next step: Only reopen when a verified exact timing, stance, roster or injury source becomes available.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Baseline | done | Checkpoint and contracts | Checkpoint recorded |
| Slice 1 · Period skeleton | done | Batter A/B period comparison | API and UI verified |
| Slice 2 · Core metrics | done | Production, quality and discipline metrics | Targeted tests passed |
| Slice 3 · Dual heatmaps | done | Bat Speed and Choice comparison | Shared scale verified |
| Slice 4 · Bat Tracking | done | Tracked-swing period metrics | Denominators verified |
| Slice 5 · Timing | done | Miss Distance and timing references | Source gates verified |
| Slice 6 · Exact visuals audit | done | Exact-payload and stance source audit | Unavailable fields remain gated |
| Slice 7 · Team research | done | Order, position, role and platoon research | Backend tests passed |
| Slice 8 · Lineup scenarios | done | Prediction and run-expectancy candidates | Research-mode limitations displayed |
| Slice 9 · Shared period workspace | done | True period percentile cards, shared discipline boards, transfer controls and filter rail | Distinct A/B production payload verified; typecheck and service tests passed |

## Pitch Quality Leaderboards

- Status: **in_progress**
- Progress: **92%** (12/13 slices)
- Owner area: Pitchers
- Updated: 2026-10-08
- Summary: Basic, Stuff+, Location+ and Pitching+ leaderboards with pitch-type splits, headshots and automated snapshots remain frozen. A separate Plus v2 research track has been opened for a second cleaning pass, tracking-era taxonomy, position-player pitching exclusion and out-of-time validation; formal scores are not replaced by the research track.
- Next step: Keep Stuff+ v2/v5 research-only; allow Location+ v2 to enter shadow monitoring, then proceed to Slice 11 historical backfill/release gate only after prospective checks.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Baseline | done | Existing leaderboard inventory | Baseline preserved |
| Slice 1 · Navigation | done | Four leaderboard views | Routes verified |
| Slice 2 · Stuff+ | done | Overall and pitch-type Stuff+ | Pete model contract verified |
| Slice 3 · Location+ | done | Overall and pitch-type Location+ | Aggregate contract verified |
| Slice 4 · Presentation | done | Filters, links and headshots | Typecheck passed |
| Slice 5 · Pitching+ export | done | Independent complete-pitch inference | Strict cutoff displayed |
| Slice 6 · Automation | done | Daily atomic snapshots | Targeted tests passed |
| Slice 7 · Plus v2 data cleaning and tracking-era audit | done | Re-audit position-player pitching, pitch taxonomy, tracking-field missingness and pre/post-Trackman comparability without changing formal scores | Generated data/derived/plus_v2_slice7.json; year-by-year exclusion counts, canonical map, Slider/Sweeper support, arm-angle/movement coverage and unmapped rows recorded |
| Slice 8 · Stuff+ scale and point-in-time challenger | done | Cleaned point-in-time Stuff+ refit with support-qualified scale | Separate v4 challenger artifact/model generated; position-player rows excluded, strictly prior FF/SI/FC references applied, 2025 validation and 2026 fixed test metrics recorded; formal v3 unchanged |
| Slice 8b · Stuff+ prior-carryover revision | done | Previous-season pitcher fastball prior and higher-support Stuff+ challenger | Separate v5 artifact/model generated with 35% deterministic training sample; grouped correlation and error improve over v4 but remain below formal v3, so v5 stays research-only |
| Slice 9 · Location+ taxonomy and context challenger | done | Canonical pitch-code/family Location+ refit with context retained | Separate v2 challenger artifact/model generated; Slider/Sweeper canonicalization, unmapped support, 2025 validation and 2026 fixed test metrics recorded; formal v1 unchanged |
| Slice 10 · Plus calibration and subgroup validation | done | Fixed-2026 paired calibration/subgroup release gate for Stuff+ and Location+ challengers | Generated data/derived/plus_v2_slice10.json using deterministic 2% paired test audit; Location+ v2 passes shadow criteria, Stuff+ v2 fails non-inferiority and remains research-only; formal contracts unchanged |
| Slice 11 · Historical backfill and release gate | planned | Full historical Plus v2 backfill, atomic snapshots, downstream Stamina/leaderboard rebuild and formal promotion decision | Pending: 2027 or later prospective evidence, 100% eligible-row verification, representative-player review and model-versioned contract |

## RE24 & Leverage Lab

- Status: **done**
- Progress: **80%** (4/5 slices)
- Owner area: Pitcher Lab
- Updated: 2026-09-20
- Summary: Calculator, local reliever leaderboard, reference comparison and corrected plate-appearance WPA are complete.
- Next step: Automate or explicitly version the collected reliever reference cutoff.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · State model | done | RE24 and empirical LI states | Backend tests passed |
| Slice 1 · Calculator | done | Entry and exit scenario calculator | Known scenario smoke tests passed |
| Slice 2 · Leaderboard | done | Local and collected views | 2025 regression diagnostics recorded |
| Slice 3 · Global WPA audit | done | Shared plate-appearance WPA | Downstream tests passed |
| Slice 4 · Reference automation | planned | Versioned reference cutoff and refresh path | Pending |

## Daily Data Reliability

- Status: **in_progress**
- Progress: **43%** (3/7 slices)
- Owner area: Data operations
- Updated: 2026-09-30
- Summary: Pitch data is current through the latest officially completed games. Per-pitch Stuff+ requires full incremental completion and 100% eligible-row verification before downstream snapshots rebuild; Per aspera ad astra exposes resumable single-season 2021–2025 Plus backfill buttons with persisted per-year progress.
- Next step: Repair the Statcast date cap, dead-lock handling, durable logs and monolithic pitch-data step.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Core automation | done | Daily pitch, video, line, Plus and roster jobs | Previously completed runs recorded |
| Slice 1 · Freshness manifest | done | JSON, Markdown and page-impact report | Service and UI added |
| Slice 2 · Scheduler observability | planned | Sub-step heartbeat and durable stdout/stderr | Pending |
| Slice 3 · Timezone and source cap | planned | Do not request future US Statcast dates | Pending |
| Slice 4 · Failure isolation | planned | Independent downstream retries and dead-PID recovery | Pending |
| Slice 5 · Legacy/manual sources | planned | Resolve or clearly gate derived exports and reliever references | Pending |
| Slice 6 · Historical Plus backfill | done | Single-season buttons for resumable Location+, per-pitch Stuff+, leaderboard, Pitching+ and Stamina rebuilds | Each UI request sends exactly one year; resume and partial-cache tests, Nuxt typecheck and UTF-8 passed |

## Project & Slice Tracker

- Status: **done**
- Progress: **100%** (3/3 slices)
- Owner area: Per aspera ad astra
- Updated: 2026-09-26
- Summary: A tracked source of truth, progress bars, slice history and handoff-ready Markdown are available in Data operations.
- Next step: Update this tracker whenever a future request creates, completes, blocks or defers a slice.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Tracker contract | done | Versioned JSON source of truth | Schema loads |
| Slice 1 · Admin progress UI | done | Project cards and slice progress | Typecheck passed |
| Slice 2 · Handoff output | done | Generated Markdown and copy action | Markdown generated |

## Stamina+ Research & Lab

- Status: **done**
- Progress: **100%** (24/24 slices)
- Owner area: Pitcher Lab
- Updated: 2026-10-03
- Summary: Observed Game Stamina+ v1.1 and its leaderboard remain frozen. Quality Stamina+, Physical Stability+ and Command Retention+ now appear as synchronized but separate personal timelines; Slice 18 did not support a composite, and Slice 19 permanently records the keep-separate product decision for this version.
- Next step: Treat Slice 0–19 as complete. Reopen only for a genuinely untouched season validation, or begin the separate Player Health & Availability research with its event-source audit.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Data foundation | done | Clean pitch keys, appearance roles, workload sequence, coverage audit and preregistered H1–H4 contract | Clean dataset artifact, backend test, API and UI audit verified |
| Slice 1 · League decline | done | Adjusted SP/RP pitch-count and season-progression curves | Two-way fixed effects, appearance-clustered 95% CI, API/UI output and targeted tests verified |
| Slice 2 · Bias correction | done | Removal weighting, fixed-endpoint and TTO sensitivity analyses | Cross-fitted direct observation weights, paired windows, API/UI schema, 9 targeted tests and Nuxt typecheck verified |
| Slice 3 · Pitcher heterogeneity | done | Partially pooled pitcher and role retention slopes | Pitch-type matched selection-weighted slopes, empirical-Bayes shrinkage, split-half validation, API/UI, targeted tests and typecheck verified |
| Slice 4 · Recovery and season load | done | Strictly lagged cross-role workload, readiness, retention, chronic-load, standardized feature influence and validation panels | 4A–E API/UI wired; standardized within-pitcher effects exposed without causal claims; 2026 chronological validation complete |
| Slice 5 · Stamina+ retention trait | done | Role-specific two-season Stuff+ retention score plus 2025/2026 single-season research views | SP/RP held-out gates passed; 1,130 season-role scores generated; API schema, targeted tests and Nuxt typecheck passed |
| Slice 6 · Per-pitch state | done | Cached fixed trait, expected retention path and observed Stuff+/Location+ on pitch hover | 716,544 pitch rows cached; trait coverage 91.9%, expected Stuff+ coverage 83.4%; personal Movement/Location payload, backend tests and Nuxt typecheck verified |
| Slice 7 · Family and target audit | done | FO-as-Offspeed taxonomy, family coverage, baseline ceiling and regression-to-mean audit, preregistered v2 targets | 2026 artifact rebuilt with 99.8% classified SP coverage and 100% classified Stuff+ coverage; 234-pitcher bias audit, API schema, 8 targeted tests, UTF-8 and Nuxt typecheck passed |
| Slice 8 · Appearance fatigue curves | done | Context-adjusted per-game Fastball / Breaking / Offspeed trajectories and trailing MA5 research curves | 403,566 pitch curves and 83,714 appearance-family/Overall rows rebuilt; MA5 starts at fifth same-family pitch; fixed-weight Overall and 438-game 101+ support verified |
| Slice 9 · Model challengers | done | ANCOVA/GAMM, hierarchical family slopes and interpretable boosted-tree challenger | 2026 chronological 70/30 raw-pitch comparison completed; ANCOVA +3.56%, spline mixed-effects +3.99%, ML +4.02% RMSE improvement; 634 hierarchical estimates, API schema, 9 tests and Nuxt typecheck passed |
| Slice 10 · Validation and v2 scoring | done | 2025→2026 validation, ceiling-neutrality audit, family Stamina+ and calibrated overall candidate | Leakage-safe holdout completed: spline selected by parsimony; all pitch-model gates passed, but Overall and all families remained research-only; candidate rows 0; API schema, 9 tests, UTF-8 and Nuxt typecheck passed |
| Slice 11 · Lab artifacts | done | Research-only multi-signal family cache, league diagnostics and player-game selector; no leaderboard or score | 67,383 appearance-family-window rows rebuilt for 377 SP and 4,857 starts; API schemas parsed; Stamina tests 9 passed; UTF-8 and Nuxt typecheck passed |
| Slice 11A · Observed Game Stamina+ | done | Per-start fixed-mix Overall and family Stamina+ with pitch-window decline, clustered uncertainty and season timeline | v1.1: 4,563 eligible Overall starts, 93.9% coverage; RMSE 9.597; early Stuff/velocity rho 0.070/0.097; split rho 0.423; median reliability 0.834 and interval width 10.4; tests, UTF-8 and typecheck passed |
| Slice 12 · Season observed-state summaries | done | Reliability-weighted Overall and family season Stamina+ with qualification gates, partial pooling, 80% intervals and rank sensitivity audit | 2026 produced 1,207 rows; qualified Overall/Fastball/Breaking/Offspeed pitchers 164/174/178/143; median season reliability 0.895/0.893/0.933/0.917; weighted-vs-unweighted rank rho 0.998–0.999; tests, schemas, UTF-8 and typecheck passed |
| Slice 13 · Independent-season validation | done | Apply the frozen observed-state and season-summary contracts to 2025 and 2026, including a season-level ceiling-neutrality gate | Eight of nine gates passed; season ceiling neutrality failed with max |rho| 0.416 versus 0.20, so leaderboard_release_eligible=false |
| Slice 13A · Season ceiling-bias repair | done | Train scope-specific low-degree early-quality correction on 2025 and evaluate once on untouched 2026 | All gates passed after row-level reliability qualification: max 2026 |rho| 0.181, minimum median reliability 0.811, maximum interval width 4.067, minimum scope support 122, weighting rho 0.985 and retained spread 0.590 |
| Slice 14 · Stamina leaderboard | done | Starter-only adjusted observed-season Stamina+ tab with 14 aligned fields, qualification-gated family scores, depth, 80% interval and reliability | 2026 leaderboard API, schema and qualification behavior verified; Stamina tests and Nuxt typecheck passed |
| Slice 14A · Season qualification repair | done | Replace mean-game reliability veto with support plus season-level reliability while preserving adjusted uncertainty | 2026 qualified Overall/Fastball/Breaking/Offspeed counts 149/158/171/132; all release gates passed with max ceiling |rho| 0.114 |
| Slice 14B · Personal and inline timelines | done | Reusable Overall/family game timeline in Pitcher Personal plus keyboard-accessible leaderboard row expansion | Sean Burke payload returns 84 scope-game rows and 27 eligible Overall starts; Nuxt typecheck and UTF-8 passed |
| Slice 15 · Physical signal contract | done | Freeze exact-pitch-type, within-appearance velocity, spin, movement, release-point, extension and arm-angle stability definitions with 2023–2026 coverage and missingness audits | 2023–2026 supported-late coverage 80.7%/79.5%/78.0%/76.6%; 2026 arm-angle coverage 56.8% under exact-type support; null and fixed-weight rules verified |
| Slice 16 · Physical Stability+ challenger | done | Transparent 20-pitch-window and game-level Physical Stability+ with component scores, partial pooling, reliability and intervals; no Stuff+ target in score construction | 2026: 4,572 eligible games/303 pitchers, median reliability 0.905, median 80% width 7.754, split-window rho 0.553, velocity-vs-physical rho 0.564; 14 tests and Nuxt typecheck passed |
| Slice 17 · Command Retention+ | done | Separate within-game Location+ retention state by exact pitch type/family with 20-pitch windows, game scores, fixed early mix, partial pooling, reliability and intervals | 2023-frozen model applied through 2026; 2026 has 4,392 eligible games/303 pitchers, model-vs-naive RMSE gain 1.77%, early-Location rho -0.008, split rho 0.085, median reliability 0.458 and interval width 14.469; 15 Stamina tests, UTF-8 and typecheck passed |
| Slice 18 · Incremental and external validation | done | Frozen 2025-to-2026 audit of whether early Physical Stability+ and Command Retention+ improve later Quality retention beyond early Quality alone | 4,206 matched 2026 starts and 96.03% pair coverage; challenger RMSE 3.6395 versus baseline 3.6387 and velocity comparator 3.6347, so incremental-gain gates failed; pairwise max |rho| 0.041 and calibration 0.9568 passed; composite_release_eligible=false |
| Slice 19 · Product integration decision | done | Synchronized Quality, Physical and Command small multiples in Pitcher Personal and lazy-loaded leaderboard expansion; leaderboard columns also expose separate 10-game Q-Stm+, Phy-Stb+ and Cmd-Ret+ means without changing official rank | 180 pitchers have at least 10 games in all three signals; Cease/Baz/Leahy plus four contrast cases audited; Traditional and Plus leaderboard tables use a common +2px font size and a UTF-8 Traditional-Chinese custom-field guide; 16 Stamina tests, true-data schema smoke, UTF-8 and Nuxt typecheck passed |

## Pitcher Metric Explorer

- Status: **active**
- Progress: **33%** (1/3 slices)
- Owner area: Pitcher Lab
- Updated: 2026-10-04
- Summary: A season-level pitcher research workbench now joins compatible traditional, advanced, Petehub Plus and published Stamina metrics without filling missing values with zero.
- Next step: Slice 2 can add a separate pitcher-game explorer for Game Score, WPA, pitch count and the aligned Quality／Physical／Command game states; it must not mix game rows into the season-level regression.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 1 · Pitcher-season explorer | done | Metric catalog, same-grain season API, classified X/Y selectors, complete-case scatter, Pearson/Spearman/OLS results with significance guidance, and axis-category tables that merge or split with the current selection | 2026 returns 868 pitchers and 35 fixed metric keys; basic/advanced/Plus/Stamina source status exposed; missing joins remain null; batter-parity regression UI, enlarged headshots and dynamic category tables pass UTF-8 and Nuxt typecheck; 23 targeted backend tests passed |
| Slice 2 · Pitcher-game explorer | planned | Separate game-level population for Game Score, WPA, pitch count and aligned Stamina signals | Pending: game-key joins, SP/RP scope, complete-case coverage and clustered-observation warning |
| Slice 3 · Pitch-type explorer | planned | Explicit pitch-type season grain for Stuff+, Location+, Pitching+, usage and physical traits | Pending: exact pitch taxonomy, minimum pitch support and no implicit cross-pitch aggregation |

## Pitcher Performance State, Collapse & Rebound

- Status: **active**
- Progress: **100%** (28/28 slices)
- Owner area: Pitcher Lab
- Updated: 2026-10-08
- Summary: The v1 Slices 0–11 and independent v2 Slices 11A–23 remain frozen. The Performance State Lab now exposes Slice 14 as its role-target-specific primary board, Slice 18/19 as shadow challengers, Slice 20 subgroup monitoring and Slice 22 freeze decisions without changing formal leaderboards or production player pages.
- Next step: Keep the strict 2026 replay locked and wait for untouched 2027 prospective rows; compare the frozen Primary and shadow candidates append-only before any production integration. Upgrade the Lab player timeline only after a point-in-time v2 artifact is specified.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Research contract and label audit | done | Freeze SP/RP-separated process collapse, result collapse, combined collapse and rebound definitions for next 10/20 pitches and next appearance; define eligible information time, thresholds, uncertainty and no-injury language | 2025 role-specific 5% thresholds frozen against causal pitcher-role EB baselines; 2026 transfer drift audited (SP +4.99pp flagged, RP +1.48pp within tolerance); contract artifact and leakage checks passed |
| Slice 1 · Appearance-state warehouse | done | Build one role-specific pitcher-appearance panel joining lagged Stuff+, Location+, Quality Stamina+, Physical Stability+, Command Retention+, pitch-family states, workload/rest, opponent/park context, RE24, WPA/LI and starter-only adjusted Game Score | 2025/2026 contain 20,868/20,793 unique pitcher-game-role rows; SP/RP and dual roles remain separate; Plus and PA-result coverage near 100%; unsupported starter-oriented signals remain null; Game Score is explicitly a derived proxy |
| Slice 2 · Baselines and temporal design | done | Establish last-state, personal mean, MA5, EWMA, logistic/linear and quantile baselines; use rolling development inside 2025 and evaluate on 2026 | All features shifted before target appearance; 2026 EWMA5 RMSE 0.6729 versus last-state 0.8421; lagged logistic AP 0.2047/Brier 0.0609/log loss 0.2390 versus prevalence AP 0.0698/Brier 0.0656/log loss 0.2596; 2026 status later amended by Slice 3A |
| Slice 3 · Hierarchical multivariate state-space | done | Estimate separate latent Stuff, Command and result states from noisy observed game signals with pitcher/role partial pooling, irregular rest intervals and observation uncertainty | Superseded by the Slice 3A v1.1 protocol repair; original metrics are retained only as historical diagnostics |
| Slice 3A · Calendar-gap and persistence repair | done | Replace four-day rest filling with actual pitcher-role calendar gaps, enforce explicit long-gap reset behavior, expand phi through zero, correct half-life units and freeze amended 2026 evaluation semantics | 2025-only policy search rebuilt v1.1 artifacts; 2026 Stuff RMSE gain SP 13.80%/RP 11.57%, Command +1.87%/+0.40% exploratory, Result 0%; 243 SP and 456 RP returning histories have complete actual cross-season gaps and no four-day fill; 8 targeted tests passed |
| Slice 4 · Markov regime switching | done | Estimate role-specific filtered regime probabilities with 2–5 state comparison, calendar-dependent transitions, 60-day stationary resets and deterministic post-fit labels | 2025-only fit/validation selected SP 2 states (Stable/Collapse) and RP 3 (Stable/Collapse/High-volatility); all candidates cleared 2% occupancy, but 4–5 state held-out likelihood failed; bootstrap median emission similarity SP 0.721/RP 0.693 and transition similarity 0.979/0.870; 2026 collapse AP 0.102/0.098; no unsupported Declining/Recovering labels forced |
| Slice 5 · GAS volatility with multi-horizon load | done | Fit role-specific Student-t score-driven variance with lagged HAR 1/5/15-appearance, workload and calendar-gap correction using 2025-only Duan smearing | 2026 GAS+HAR NLL per row SP 1.6044/RP 1.6089 versus EWMA 1.6067/1.6150; QLIKE SP 1.3935/RP 1.4477 versus EWMA 1.3992/1.4555; 80%/95% coverage SP 81.1%/95.6%, RP 81.2%/95.6%; squared-standardized residual lag-1 autocorrelation 0.041/0.045; gains are small and research-only |
| Slice 6 · GJR-GARCH challenger | done | Fit pooled-by-role Student-t GJR-GARCH with explicit pitcher-role and long-gap resets, constrained stationarity and no under-supported per-pitcher fits | Both roles converged with persistence SP 0.991/RP 0.987; negative-shock gamma estimated at 0 for both, so asymmetry is not supported; 2026 GJR NLL 1.6059/1.6130 did not beat GAS+HAR; 11 targeted Performance State/WPA tests passed |
| Slice 7 · POT-EVT tail risk | done | Fit role-specific peaks-over-threshold generalized Pareto tails to GAS+HAR-standardized negative Stuff innovations; expose extreme-event probability and supported expected severity with SAV/asymmetric-slope CAViaR comparison | 2025-only censored-likelihood threshold/declustering selection chose SP q95/run0 (236 clusters, xi 0.023, bootstrap CI -0.088 to 0.129, KS p 0.926) and RP q95/run0 (758 clusters, xi 0.343, CI 0.276 to 0.446, KS p 0.390); 2026 EVT AP SP 0.076/RP 0.101 with about 20% recall at 8.6–9.8% alerts; asymmetric CAViaR selected for both, SP 95% violation 5.09% passes Kupiec p 0.785 while RP 5.74% fails p 0.000031; 13 targeted tests passed |
| Slice 8 · Collapse and rebound forecasts | done | Combine frozen latent-state forecasts, regime priors, conditional volatility and EVT tail features into separately calibrated role-specific forecasts for process collapse, result collapse, return-to-baseline and strong rebound | 2025 chronological 60/20/20 train-calibration-validation completed for 8 role-target models; five cumulative logistic ablations plus XGBoost challenger, calibration curves, fixed-negative-tail alert thresholds and feature importance persisted; filtered/current-appearance states are prohibited by test |
| Slice 9 · External-diagnostic and prospective gates | done | Complete the documented-amendment 2025-to-2026 diagnostic, benchmark primary models and challengers, audit dominant-arsenal stability, and freeze prospective 2027 gates | 2026 process-collapse AP SP 0.185 vs 0.100 baseline and RP 0.183 vs 0.065 both pass AP/Brier/log-loss gates; SP result-collapse also passes narrowly, RP return-to-baseline passes, while SP return-to-baseline, both strong-rebound models and RP result-collapse fail. Pitcher-cluster bootstrap, calibration bins, fixed false-alert metrics, arsenal subgroups, unique 20,793-row forecast artifact, API schemas and 15 targeted tests passed; overall decision remains keep_research_only |
| Slice 10 · Performance State Lab | done | Add a large-type Pitcher Lab research page for model comparison, completed-appearance rankings, player season timelines, state probabilities, volatility, tail risk, rebound probability and explicit release-gate explanations | New /lab/performance-state route and /api/performance-state/leaderboard verified for all 8 SP/RP target combinations; minimum-5 coverage is 243 SP/500 RP for collapse targets and 18 SP/51 RP for conditional rebound targets; player timeline/schema tests, 15 targeted backend tests, UTF-8 and Nuxt typecheck passed. Browser visual QA unavailable because the session exposed no browser surface; no formal leaderboard, next-game forecast or Stamina+ overwrite |
| Slice 11 · Shadow monitoring and integration gate | done | Preserve one frozen prediction per year/pitcher/role/game/target, append only unseen completed appearances, audit calibration/confusion drift, and keep later product integration gated | Immutable ledger initialized with 44,384 historical-backfill rows through 2026-09-27; rerun appended 0 and preserved 0 conflicts; prospective rows remain 0 and gate remains closed until untouched 2027 plus at least 250 prospective rows per role-target. Player selection now shows date-indexed actual red and pre-appearance forecast blue-dashed performance lines, per-game error connectors, rich WPA/RE24/probability hover details and fully sortable board/appearance columns; backend schemas, 14 focused tests, UTF-8 and Nuxt typecheck passed |
| Slice 11A · Eligibility and event semantics | done | Audit and classify position-player pitching, low-volume emergency pitchers, opener-like starts, traditional/short starts and bulk/standard relief; split first-onset collapse from persistent collapse | Across 2023–2026, 94.7–95.5% of appearances remain model-eligible. The audit detects 436 position-player pitching appearances and retains explicit exclusion reasons; 2026 includes 316 opener-like, 4,308 traditional-start and 1,003 bulk-relief appearances. Hindsight emergency flags are cohort filters only, never pregame features |
| Slice 12 · Harmonized 2023–2026 warehouses | done | Build independent versioned appearance warehouses for 2023–2026 with a common 2023 leverage reference and unchanged role/game keys | 20,629/20,693/20,868/20,793 unique appearance rows for 2023/2024/2025/2026; Plus and result coverage are effectively 100%; every pitcher-role-game key is unique. Historical Plus values use the current frozen retrospective models, and no v1 artifact was overwritten |
| Slice 13 · Expanding-window validation | done | Evaluate strictly forward folds 2023→2024 and 2023–24→2025, then reserve 2023–25→2026 as diagnostic-only; report raw and cleaned cohorts separately | Onset process-collapse beats prevalence in every SP/RP fold; return-to-baseline is consistently informative. Persistent and strong-rebound SP sets are small and require clustered intervals. SP result-collapse does not improve in the 2026 diagnostic and is blocked from advancement. Six targets, two cohorts and all fold predictions are persisted; v2 schema/artifact tests passed |
| Slice 14A · Clustered uncertainty and calibration | done | Add pitcher-cluster bootstrap intervals, calibration slope/intercept/ECE and evidence labels for every role-target fold | 100 bootstrap resamples per fold. SP/RP onset process-collapse is supported in all folds; RP return-to-baseline is supported in all folds; 2026 SP return-to-baseline and strong rebound pass the interval screen but remain diagnostic-only. Persistent SP and most strong-rebound cohorts remain ranking-only/uncertain; SP result-collapse remains unsupported |
| Slice 14B · Multiseason advanced refit | done | Fit state-space, HMM regime, GAS+HAR, GJR-GARCH, POT-EVT/CAViaR and forecast challengers on 2023–2025, then run one fixed 2026 diagnostic | 61,398 target predictions and four advanced state artifacts generated. Stuff state improves 2026 RMSE SP 18.03%/RP 11.81%; result state has 0% incremental gain. GJR gamma is 0 for both roles; GAS/GJR gains over EWMA are small. RP CAViaR passes Kupiec (p=.720), EVT supported rates are SP 65.21%/RP 69.16%; only SP/RP process-collapse and RP result/rebound forecast gates pass. 2027 untouched and all outputs research-only |
| Slice 15 · 2027 prospective shadow readiness | done | Freeze Slice 14 fingerprints, lock thresholds/calibration, detect untouched 2027 source availability and prepare append-only prospective monitoring | Readiness artifact generated with model_refit_allowed=false, thresholds/calibration locked, source status awaiting_untouched_2027_source, zero prediction/observation rows and integration gate CLOSED; frozen-input drift detection, API schema and 2 readiness tests passed |
| Slice 16 · Non-destructive model optimization challenger | done | Repair the release gate so prevalence-only predictions cannot pass; select stable EWMA/MA5 or workload/context features on 2025, refit on 2023–2025, and run a fixed 2026 diagnostic with pitcher-cluster uncertainty | performance_state_v2_slice16.json and 81,092-row diagnostic predictions generated; 2023–2024 development, 2025 selection, 2026 diagnostic; baseline-only rejection and API schema tests passed. Same-denominator comparison says keep Slice 14 frozen for all comparable targets except SP strong_rebound, which is only a diagnostic challenger; Slice 14/15 and production integration remain unchanged |
| Slice 17 · Temporal calibration challenger | done | Compare raw, Platt and isotonic calibration on the 2025 selection window, apply the selected calibration to the 2023–2025 refit, and retain calibration only when fixed 2026 Brier and log-loss are not worse | performance_state_v2_slice17.json and 81,092-row diagnostic predictions generated; calibration candidates are temporally selected, most targets retain raw probabilities on 2026, SP return-to-baseline and RP persistent-collapse are calibration-positive diagnostics; Slice 14/15 and production integration remain unchanged; 2 Slice17 tests passed |
| Slice 18 · Empirical-Bayes partial pooling challenger | done | Estimate pitcher-role residual shifts with shrinkage toward the role-global model, select global-only versus partial-pooling on 2025, and evaluate once on fixed 2026 | Slice18 section generated with 81,092 predictions; SP strong-rebound selected partial pooling while other role-targets retained global-only; approximation and no-production warnings persisted |
| Slice 19 · Workload selection-bias sensitivity | done | Compare standard workload/context features with pitcher-history residualized workload features without claiming causal identification | Slice19 section generated with 81,092 predictions; only RP persistent-collapse selected residualized workload on 2025, while other targets retained context workload; causal interpretation explicitly blocked |
| Slice 20 · Role and arsenal subgroup calibration | done | Audit calibration by SP/RP, target and dominant Fastball/Breaking/Offspeed arsenal with sparse-group monitoring flags | Slice20 subgroup audit generated for all role-target combinations; small and ECE>0.05 groups marked monitor; no automatic probability retuning; schema/API tests passed |
| Slice 21 · Rolling-origin robustness | done | Run strict 2023→2024, 2023–24→2025 and 2023–25→2026 forward folds for global, partial-pooling and residualized-workload challengers | All eight SP/RP target panels were evaluated with forward-only folds; each challenger reports per-fold AP, Brier, log-loss and non-worse flags; the 2026 fold remains diagnostic-only |
| Slice 22 · Research-only freeze decision | done | Turn rolling-origin evidence into explicit keep-Slice14 versus retain-research-challenger decisions without replacing the formal model | SP persistent-collapse residualized-workload and RP return-to-baseline partial-pooling meet the two-fold research consistency rule; all other targets keep Slice14; formal_model_replaced=false and production gate CLOSED |
| Slice 23 · Strict 2026 replay lock | done | Freeze the role-target layer map, 2023–2024 training, 2025 Platt calibration and false-alert policy before scoring 2026 once | Strict replay fingerprint bd7b04755f1d4de5608814b2c225feabf24d0fe65e547d99b2f8ce8830716a19 generated with 81,092 eligible predictions; model fit/calibration completes before the 2026 state files are loaded; rebound cohorts use the same target eligibility as Slice14; artifact explicitly says retrospective_holdout_replay and integration CLOSED |
| Slice 24 · Lab model synchronization | done | Expose Slice 14 role-target primary probabilities in /lab/performance-state with Slice 18/19 shadow deltas, Slice 20 subgroup monitoring and Slice 22 freeze context; preserve v1 player timeline as explicit fallback | New /api/performance-state/v2-lab route and Lab integration verified against frozen artifacts; formal /leaderboards remains unchanged; backend v2-lab tests, UTF-8 check and Nuxt typecheck passed |

## Player Health & Availability Research

- Status: **planned**
- Progress: **0%** (0/7 slices)
- Owner area: Player research
- Updated: 2026-10-02
- Summary: Plan a non-diagnostic workload, availability and mechanics-change monitor. Official IL and roster transactions supply outcome events; public pitch/game data supply workload and observable-change features. The product must not claim medical diagnosis or causality.
- Next step: Begin with Slice 0: audit and, if the official source is stable, backfill immutable year-scoped transaction/IL event caches before fitting any alert model.

| Slice | Status | Deliverable | Verification |
|---|---|---|---|
| Slice 0 · Event-source and coverage audit | planned | Audit MLB transaction semantics and backfill feasibility; distinguish IL placement, activation, transfer, trade, option, DFA and ordinary absence | Pending: year-by-year row/player/date coverage, duplicate handling, player-ID and team matching, source limitations |
| Slice 1 · Availability event warehouse | planned | Immutable normalized 2021–2026 transaction/IL events plus observed player-team stints and appearance calendar | Pending: raw payload retention, deterministic taxonomy, reconciliation samples and refresh/backfill tests |
| Slice 2 · Workload and recovery timeline | planned | Strictly lagged pitch counts, rest days, 7/14/28-day load, role changes, gaps and return-from-absence markers | Pending: no future leakage, SP/RP separation, traded-player continuity and missing-appearance disclosure |
| Slice 3 · Mechanics change detection | planned | Pitcher-specific exact-pitch-type change points and robust deviations in velocity, movement, release geometry, extension, spin and arm angle | Pending: minimum support, false-alert stability, tracking-batch missingness and intentional arsenal-change review |
| Slice 4 · IL-event risk challenger | planned | Research-only 7/14/30-day association model for future official IL placement, with workload-only, mechanics-only and combined baselines | Pending: time-based validation, precision-recall, calibration, lead time, subgroup coverage and leakage audit |
| Slice 5 · Health management UI | planned | Player availability timeline and team monitoring board showing evidence, uncertainty and data freshness rather than medical diagnoses | Pending: alert explanations, false-positive warnings, permissions, API/schema tests and Nuxt typecheck |
| Slice 6 · Prospective monitoring | planned | Frozen-model shadow monitoring and post-event evaluation before any operational alert claims | Pending: prospective season results and explicit release/no-release decision |

## Player Salary & Value

- Status: **idea**
- Progress: **0%** (0/0 slices)
- Owner area: Future feature
- Updated: 2026-09-26
- Summary: Captured idea for a page comparing player salary, contract cost and estimated on-field value.
- Next step: Define trusted salary sources, the value model and slices before implementation.
