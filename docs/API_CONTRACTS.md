# API Contracts

## Shared Query Parameters

Most pitcher analysis endpoints should share these parameters where possible:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `team` | string | Optional team filter |
| `start_date` | string | ISO date |
| `end_date` | string | ISO date |
| `pitch_types` | string[] | Repeated query param |
| `stand` | string | `All`, `L`, `R` |
| `counts` | string[] | Count buckets or exact counts |
| `results` | string[] | Pitch or PA result buckets |

## Authentication and Ballpark profile

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `PATCH /api/auth/profile`

Registration accepts the existing `username` and `password` fields plus optional `favorite_team_id`. The value is either `null` or one of the 30 official MLB team IDs; unsupported IDs return validation error `422`. Authentication responses add `favorite_team_id`, derived `favorite_team_code`, and `avatar_setup_status` (`pending` or `default`).

`PATCH /api/auth/profile` is authenticated and partial. Sending `favorite_team_id: null` clears the home-team preference; omitting it preserves the current value. Sending `avatar_setup_status: "default"` records completion of the C1 neutral-avatar bootstrap, while omitting it preserves the current state. Full avatar appearance remains a D4 concern and is not stored by this contract.

## Official active roster

- `GET /api/teams/{team_code}/active-roster?year=2026`
- Optional `refresh=true` bypasses a fresh cache and attempts an official refresh.

Contract `official_active_roster_v1` reads only MLB StatsAPI `rosterType=active`; season participants, leaderboards and local pitch tables are never roster fallbacks. Each player exposes MLBAM ID, name, jersey number, position code/name/type and official status code/description. The response includes `retrieved_at`, nullable `source_as_of`, `cache_age_seconds`, a 30-minute `stale_after_seconds` threshold and explicit `fresh`, `stale` or `unavailable` freshness.

MLB StatsAPI does not publish a roster revision timestamp in this response, so `source_as_of` remains `null`; Petehub reports the honest retrieval time instead. A failed refresh returns a version-compatible disk cache as `stale` with a warning. With no valid cache it returns `unavailable` and an empty player list, never a reconstructed season roster.

## Recommended Endpoints

### Pitchers

- `GET /api/pitchers`
- `GET /api/pitchers/metric-explorer`
- `GET /api/pitchers/{pitcher_id}`

#### `GET /api/pitchers`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Defaults to `2026` |
| `role` | string | `SP` or `RP`; any non-`RP` value is treated as `SP` |

Response:

```json
[
  {
    "value": 650644,
    "label": "Aaron Civale (ATH)",
    "name": "Aaron Civale",
    "team": "ATH",
    "role": "SP",
    "games": 14,
    "starts": 14,
    "start_rate": 1.0
  }
]
```

#### `GET /api/pitchers/metric-explorer`

Returns one row per pitcher-season for the Pitcher Metric Explorer. Query parameter `year` selects the season. The response keeps only season-level fields and exposes a metric catalog with `key`, category, unit, direction and description so the client can safely populate arbitrary X/Y axes.

The first release joins traditional results/workload, standard estimator fields, season Stuff+／Location+／Pitching+, and the separately published 2026 Stamina signals by MLBAM ID. Missing joins remain `null`; they are never converted to zero. `source_status` reports whether the basic, Plus, advanced and Stamina sources were available. Regression is computed interactively by the client over the filtered complete-case pitcher sample and is descriptive rather than causal.

### Pitcher Personal

- `GET /api/personal/overview`
- `GET /api/personal/pitches`
- `GET /api/personal/discipline`
- `GET /api/personal/sequence`
- `GET /api/personal/movement`
- `GET /api/personal/rotation`
- `GET /api/personal/videos`
- `GET /api/personal/timing`

### Game Center

- `GET /api/games`
- `GET /api/games/{game_pk}/pitching`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/location`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/sequence`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/shape`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/replay`
- `GET /api/games/{game_pk}/pitchers/{pitcher_id}/tags`

The game-detail response returns the line score, plate-appearance feed, batting box and pitching box for one local Statcast game. Batting rows use the official MLB boxscore `battingOrder` when available: the hundreds digit is the lineup slot and the remainder is the substitution sequence, so a `401` player is displayed under the `400` starter and a zero-PA defensive replacement is retained. `AVG` and `ERA` use the official boxscore `seasonStats` snapshot, which represents the cumulative season through that game; PA／AB／H／HR and the remaining box-score counting fields stay game-only. Official boxscores are cached atomically under the year-scoped local data directory. If that source is temporarily unavailable, the service falls back to completed-PA batting rotation and local through-date ERA; the batting fallback preserves lineup-slot grouping for players with a plate appearance but cannot invent a zero-PA substitute.

Location and Sequence are loaded from top-level Game Center tabs beside Feed and Box Score; both use a dropdown limited to pitchers who appeared in the selected game. They are restricted to the requested `game_pk` and pitcher and reuse the Personal analysis payload shapes and filters without allowing filtered rows to create artificial pitch adjacency. Requests are prefetched for the initially selected pitcher and deduplicated/cached briefly in the browser. The Tags endpoint is loaded only when a pitcher name receives hover or keyboard focus. It adapts the released Slice 3 season-role roster and may append versioned `practical_v1` Lab-first profiles (`Pronation`, `Supination`, and LHB/RHB More Breaking Balls or More Offspeed). Primary Pair remains in the frozen research artifact but is omitted from the read view and hover card. Every displayed item remains a full-season descriptive snapshot, not a through-game-date view; if the requested season has no assigned tag, the endpoint may return a separately labeled most-recent prior same-role reference and never presents that reference as current. Practical profiles do not alter the frozen Slice 3 data or downstream research artifacts. Pitch Out is excluded from Location and Sequence analysis.

`shape` is the lazy-loaded read path for the top-level Movement tab. One response contains game-only HB／IVB, compatible release X／Z fields, pitch/result/count/batter-side/catcher filter fields, Plus/Stamina context when cached, and the existing PA/pitch/video identity. The browser caches this unfiltered pitcher-game payload and applies Movement filters locally. Movement values are inches using the existing Petehub convention (`-pfx_x * 12`, `pfx_z * 12`); release position remains in the payload for compatibility, but Game Center no longer exposes a standalone Release Point tab. Pitch Out remains excluded.

`replay` is a separate lazy-loaded game/pitcher payload using contract `pitch_trajectory_statcast_v1`. It returns the same local filter fields and pitch/video identity plus a 31-point release-to-plate path for each valid pitch: `progress`, `time_seconds`, `x_ft`, `y_ft`, and `z_ft`. The backend first reconciles Statcast's actual `release_pos_*` with the velocity/acceleration state defined at 50 feet, then integrates to the front of home plate (`y = 17/12 ft`). Each pitch is explicitly labeled `supported`, `limited_trajectory`, or `unavailable`; a closure difference greater than three inches stays visible as limited data and is never pulled artificially to `plate_x/z`, while missing release/velocity/acceleration fields produce no path. Pitch Out and pitchless events are excluded. The browser caches the unfiltered response for five minutes and applies Replay filters locally. This is a ball-path reconstruction only—not body motion capture or full fluid-physics simulation.

### Batter Lab

- `GET /api/batters/lab/swing-timing`

#### `GET /api/batters/lab/swing-timing`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Available cached season; currently `2023`–`2026` |
| `pitch_group` | string | `all`, `fastball`, `breaking`, `offspeed`, `other` |
| `pitch_type` | string | Optional Statcast pitch code such as `FF`, `SL`, `CH` |
| `pitcher_hand` | string | `All`, `L`, `R` |
| `batter_side` | string | `All`, `L`, `R` |
| `batter_team` | string | Batter's season team code or `All` |
| `pitcher_team` | string | `All` 使用 Savant summary；球隊代碼使用本機精確逐球 matchup mode |
| `minimum_swings` | integer | Qualification threshold after filters |
| `minimum_plate_appearances` | integer | Season PA qualification threshold; `5`–`700`, normalized to steps of `5` |

Returns `league`, `leaderboard`, `data_mode`, filter options and sample metadata. All percentage fields use the `0–100` scale. Distances remain in inches and timing offsets in milliseconds. Rate fields are aggregated by swings; average miss distance is weighted by estimated whiffs, and conditional directional distances are weighted by their corresponding category counts.

The request path only reads local Savant summary caches under `data/MissDistance`; refreshing those caches is an explicit offline operation and does not occur during page requests.

`batter_team` is exact in summary mode. Selecting `pitcher_team` switches to exact local pitch-level matchups (`data_mode=matchup_event`). This mode returns exact tracked swings, Whiff, Competitive Rate, Bat Speed, Swing Length and attack metrics; X/Y/Z alignment and Flawed/Perfect remain null because those event-level fields are absent locally. Current pitch-level `miss_distance` coverage is 2026 only.

#### `GET /api/batters/lab/swing-timing/player`

Lazy-loaded V2 player detail endpoint. Accepts the same pitch, hand, side and pitcher-team filters plus `batter_id`. Returns player/league summary, pitch-type matrix and Bat-Speed Gear Change fields. The Lab calls it only when a leaderboard row is expanded.

#### `GET /api/personal/overview`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `role` | string | `SP` or `RP`; defaults to `SP` |
| `pitcher_id` | integer | MLBAM player id |

Response includes:

- `selected_pitcher`: pitcher option metadata from `/api/pitchers`
- `summary`: cards for `Team`, `GS`, `IP`, `ERA`, `Stuff+`, `WAR`
- `tables.dashboard`: the source dashboard row
- `tables.br`: the source BR / rotation row when available
- `tables.pitch_type_matrix`: pitch-level `Stuff+`, `Location+`, `Pitching+` matrix when available

#### `GET /api/personal/pitches`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `start_date` | string | Optional ISO date |
| `end_date` | string | Optional ISO date |
| `limit` | integer | Sample table row limit, capped at `1000` |

Response includes:

- `summary`: pitch count, game count, first game date, last game date
- `charts.pitch_type_distribution`: pitch type counts and rates
- `tables.sample_pitches`: limited pitch-level sample rows for debugging and downstream UI wiring

#### `GET /api/personal/movement`

Returns:

- `summary`: pitch count, pitcher hand, pitch type count
- `charts.movement_scatter`: horizontal/vertical break points for all valid filtered rows
- `tables.movement_summary`: pitch-level usage, movement, and velocity summary

#### `GET /api/personal/discipline`

Returns:

- `summary`: discipline metrics including swing, whiff, CSW, zone, chase, first-pitch strike
- `tables.discipline_summary`: one-row summary table
- `tables.stand_split`: L/R batter split table

#### `GET /api/personal/sequence`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `start_date` | string | Optional ISO date |
| `end_date` | string | Optional ISO date |
| `current_pitch` | string | Optional pitch filter; defaults to `All` |

Returns:

- `summary`: filtered pitch snapshot
- `tables.shallow_sequences`: shallow-count sequence outcomes
- `tables.two_strike_sequences`: two-strike sequence outcomes

#### `GET /api/personal/rotation`

Returns:

- `summary`: game count, pitch count, total WPA
- `charts.wpa_games`: game-level WPA and cumulative WPA rows
- `tables.game_log`: game-level pitch/velo/spin/batter counts
- `tables.fatigue_by_inning`: inning-level fatigue proxy for selected or latest game

#### `GET /api/personal/videos`

Returns cached video links from DuckDB columns:

- `play_id`
- `video_url`

The endpoint does not call StatsAPI or Baseball Savant at request time.

#### `GET /api/personal/timing`

Returns Swing Timing / Miss Distance payloads when a yearly CSV exists under `data/MissDistance`.

- `summary`: swings, whiff rate, pitch type count
- `charts.x_timing_points`: tied-up / centered / flail points
- `charts.y_timing_points`: late / on-time / early points
- `charts.z_timing_points`: over / lined-up / under points
- `tables.timing_by_pitch`: pitch-level timing summary

### Starter Stuff

- `GET /api/stuff/leaderboard`
- `GET /api/stuff/pitch-shapes`
- `GET /api/stuff/pitcher-detail`

#### `GET /api/stuff/leaderboard`

Query parameters are `year`, `role=All|SP|RP`, `team`, and `minimum_ip`. The endpoint reads the atomic daily snapshot and never runs model inference during an HTTP request. It returns per-pitch-type Stuff+, Location+, and source-gated Pitching+ maps (`FA/SI/FC/FS/SL/CU/CH/KC/FO`), each season-level Plus score, `data_as_of`, model versions, warnings, and per-metric `source_status`.

Pitching+ overall and pitch-type values use the newest complete-feature export available. When its date trails the current pitch source, the response keeps the values, reports `source_status.pitching_plus=stale`, exposes `pitching_data_as_of`, and returns an explicit warning so the UI never implies that different metric cutoffs match.

### Pitching+ Lab

- `GET /api/pitching/overview`
- `GET /api/pitching/pitcher`

Both responses include `data_as_of`, `cache_status`, and warnings. The overview additionally reports `source_data_as_of`, so an incomplete newest tracking date is visible instead of silently presenting the export as current.

### RE24 & Leverage Lab

- `GET /api/leverage/overview?year=2025|2026`
- `POST /api/leverage/calculator`

The overview returns two explicitly separated reliever leaderboards: `estimated_rows` from the local regular-season pitch store and `reference_rows` from `data/Reliever/<year>_reliever_wpa.csv`. Local WPA is measured once per plate appearance from consecutive PA-boundary `home_win_exp` states; raw pitch-level `delta_home_win_exp` is never season-summed. A fixed 2025 component calibration (`+WPA × 0.936080`, `-WPA × 1.030875`) is applied to 2025 and 2026 and identified in `model_version`; it was stable under an MLBAM-ID parity holdout. Reference players without a local relief appearance are excluded, with a warning when mixed-role reference scope may still differ. The response also returns per-metric linear validation diagnostics (`correlation`, `r_squared`, `mae`, `rmse`, `bias`, `slope`, and `intercept`), local and reference timestamps, model version, warnings, and the empirically derived runs-per-win value.

The calculator accepts entry and exit inning, half, score, outs, and base occupancy. It estimates endpoint WPA, RE24, REW, gmLI, exLI, an endpoint span-LI proxy, WPA/LI proxy, and SD/MD result. `inLI` and Clutch remain unavailable because two endpoints do not contain the complete plate-appearance sequence required by those metrics. LI is an empirical Statcast state estimate and is not represented as an exact FanGraphs value.

### Stamina Lab

- `GET /api/stamina/overview?year=2026`
- `GET /api/stamina/research-curves?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/game-states?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/physical-stability?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/command-retention?year=2026&pitcher_id=<mlbam_id>`
- `GET /api/stamina/incremental-validation?year=2026`
- `GET /api/stamina/season-summaries?year=2026`
- `GET /api/stamina/external-validation?year=2026`
- `GET /api/stamina/season-bias-repair?year=2026`
- `GET /api/stamina/leaderboard?year=2026`

The overview reads the generated `data/derived/stamina_lab_<year>.json` audit. Slice 11 retains league multi-signal family curves and exact-pitch-type early-reference diagnostics. `slice11_game_state` exposes observed-state v1.1: prior-season empirical-Bayes exact-type opening baselines, exact-pitch-type workload splines, fixed first-20-pitch family weights, inning-clustered uncertainty, single-game Overall/family Stamina+ and season-level diagnostics.

`research-curves` reads `stamina_v2_multisignal_<year>.parquet` and returns all game/window family rows for one starter so the client can select a game locally. Values are within-appearance deviations from at least three early pitches of the same exact pitch type; movement and release-point fields are unsigned distances from the early centroid. The response is descriptive, not a leaderboard or next-start forecast.

`game-states` reads `stamina_game_states_<year>.parquet` and `stamina_game_state_windows_<year>.parquet`. It returns each eligible start's Overall/Fastball/Breaking/Offspeed Game Stamina+, 80% interval, reliability, rolling 3/5-start state and 20-pitch-window retention. Overall requires 15 supported pitches after pitch 20 and at least 80% fixed opening-family coverage; each family requires 5 late pitches. An unobserved family keeps its opening weight, uses the league family-retention prior and adds uncertainty instead of being renormalized away. Unsupported values remain null.

`physical-stability` reads `stamina_physical_games_<year>.parquet` and `stamina_physical_windows_<year>.parquet`. Contract `stamina_physical_signal_contract_v1` compares every later pitch with at least three first-20 pitches of the same exact pitch type. Velocity, spin-vector, movement-vector, release-point, extension and arm-angle drift remain separate components; contract `stamina_physical_stability_v1` robustly standardizes them on 2023, uses fixed weights, partial pooling and an 80% interval. Missing fixed weight receives a league-neutral contribution and lowers reliability instead of becoming zero or being silently renormalized. The endpoint is research-only and describes public tracking stability, not injury risk, intent or physiology. Rebuild Slice 15–16 with `python backend/scripts/build_stamina_lab.py --year 2026 --physical-stability-only`.

`command-retention` reads `stamina_command_games_<year>.parquet` and `stamina_command_windows_<year>.parquet`. Contract `stamina_command_retention_contract_v1` uses at least three same-game first-20 exact-type pitches, a frozen 2023 early-Location/pitch-count/pitch-type Ridge expectation, and the fixed first-20 family mix. It returns Overall and family 20-pitch windows plus game-level Command Retention+, reliability and 80% intervals. Higher means Location+ held up better than expected; it is research-only and is not an injury, physiology or future-start prediction.

`incremental-validation` reads `stamina_incremental_validation_<year>.json`. Contract `stamina_incremental_validation_v1` fits on 2025 and evaluates on 2026: a 21–40 early-Quality baseline is compared with a challenger adding Physical Stability+ and Command Retention+ to explain 61–80 Quality retention. The response exposes matched coverage, RMSE, rank correlation, calibration, distinctness gates and `composite_release_eligible`. The current challenger did not improve RMSE, so no composite score is released.

The overview additionally exposes Slice 19 from `stamina_product_integration_<year>.json`. Contract `stamina_product_integration_v1` freezes the `keep_separate` product decision, representative-pitcher audit and personal-page rules. Pitcher Personal requests the existing game-state, physical-stability and command-retention endpoints in parallel, aligns them by game and preserves each signal's own interval and reliability. This does not create a new score or alter the leaderboard response.

`season-summaries` reads `stamina_season_summaries_<year>.parquet`. It reliability-weights the observed game scores, carries both measurement and between-game uncertainty into an 80% interval, and applies scope-level empirical-Bayes partial pooling. Contract `stamina_observed_season_state_v1_1` qualifies Overall with at least 10 eligible starts, 150 supported late pitches and season-level reliability of 0.70; family scopes require 8 eligible starts, 50 supported late pitches and the same season-level reliability floor. Mean single-game reliability remains diagnostic but is no longer a hard season-ranking veto because repeated starts can yield a precise season estimate even when individual games are noisy. Only qualified rows receive an unadjusted diagnostic rank.

`external-validation` reads the frozen game-state and season-summary artifacts for the requested year and its prior year. Contract `stamina_observed_external_validation_v1_1` checks coverage, pitch RMSE gain, game-level and season-level ceiling neutrality, within-game consistency, qualified support, season precision and weighting sensitivity under the v1.1 season gate. Cross-season pitcher rank is descriptive only and is not a release gate because the score measures season state rather than a permanent trait. The unadjusted season ceiling gate still fails as expected; the downstream frozen 2025 correction must pass its separate untouched-2026 audit before publication.

`season-bias-repair` exposes contract `stamina_observed_season_bias_repair_v1_1`. It fits separate Overall/Fastball/Breaking/Offspeed low-degree early-Stuff+/velocity splines with Ridge alpha 10 on v1.1-qualified 2025 summaries only, adds correction uncertainty from 100 bootstrap refits, and evaluates the frozen correction once on 2026. Adjusted rows are written to `stamina_adjusted_season_summaries_<year>.parquet`; official ranks additionally require row-level adjusted reliability of at least 0.70. The revised 2026 audit passed every gate: maximum ceiling correlation 0.114, minimum median reliability 0.814, maximum median 80% interval width 4.052, at least 132 qualified pitchers per scope, minimum weighted-vs-unweighted rho 0.983 and minimum retained score spread 0.615. Therefore `leaderboard_release_eligible=true`, with the explicit limitation that 2026 is the only untouched external season for this correction version.

`leaderboard` is the release-gated Slice 14 read path. It refuses a season unless its bias-repair audit is eligible and identifies that season as the untouched test year. Rows are Starter-only qualified Overall adjusted scores, ordered by the persisted official adjusted rank. The response also exposes starts, eligible Stamina games, average pitches, 80% interval, adjusted reliability, and separately qualified Fastball/Breaking/Offspeed scores; a family remains null when it fails its own support or adjusted-reliability gate. Research-only `quality_game_stamina_plus`, `physical_stability_plus` and `command_retention_plus` are separately calculated means that each require at least 10 eligible games; they remain null below that threshold and never change the official rank. Contract `stamina_observed_season_leaderboard_v1_1` currently publishes 149 Overall rows for 2026 and explicitly describes observed in-season retention rather than physiology or next-start prediction.

Game Stamina+ is an observed performance-retention index with league average 100. It describes only the pitches seen in that appearance, does not predict the next start, and is not presented as a permanent trait or direct physiological measurement. Depth and other physical signals remain separate explanatory fields.

The full artifact set is rebuilt outside HTTP requests with `python backend/scripts/build_stamina_lab.py --year <year>`. Slice 11 diagnostics use `--slice11-only`; the observed single-game and season timeline artifacts use `--game-state-only`; Slice 15–16 use `--physical-stability-only`; Slice 17–18 use `--command-validation-only`; Slice 19 uses `--product-integration-only`. If the season DuckDB changes after generation, the overview reports `dataset_status=stale` and warns that the research dataset must be rebuilt before modeling.

### Starter Discipline

- `GET /api/discipline/leaderboard`
- `GET /api/discipline/swing-map`
- `GET /api/discipline/pitcher-detail`

### Pitcher Similarity

- `GET /api/similarity/search`
- `POST /api/similarity/manual-shape`

### Pitcher Comparison

- `GET /api/comparison/period/options`
- `GET /api/comparison/period/date-range`
- `GET /api/comparison/period/overview`

Pitcher labels in `period/options` use the latest regular-season team found in the yearly pitch store; an older team value in the annual comparison CSV is only a fallback. Pitcher roles are also derived from regular-season appearances using the shared `GS / G > 0.3` rule, so a stale CSV role cannot classify a starter as a reliever. The cached comparison pool is keyed by both the comparison CSV and pitch-store modification times, so a daily data refresh invalidates stale team or role labels without requiring a service restart.

`period/date-range` additionally returns `current_team`, `transfer_count`, and chronological `team_stints`. A stint is a contiguous run of games for one team, so A → B → A is represented as three stints and two changes. Each stint includes `stint_index`, team, first/last appearance date, pitch count, game count, and a display label. The Period Comparison UI offers a one-click before/after comparison for two stints and explicit Period A／B stint selectors when more than two stints are detected.

Period overview player cards derive their team from pitches inside each requested window. A single-team window displays that team; a manual window spanning multiple teams displays `N Tms` and exposes the ordered team list in player metadata.

### Models

- `GET /api/models/movement`
- `GET /api/models/spin-breakdown`

### Pitcher Performance State Research

- `GET /api/performance-state/overview`
- `GET /api/performance-state/leaderboard?year=2026&role=SP|RP&target=process_collapse|result_collapse|return_to_baseline|strong_rebound&minimum_forecasts=5`
- `GET /api/performance-state/player?year=2026&pitcher_id=<id>&role=SP|RP`
- `GET /api/performance-state/shadow`
- `GET /api/performance-state/v2-audit`
- `GET /api/performance-state/v2-slice14-audit`
- `GET /api/performance-state/v2-slice15-audit`
- `GET /api/performance-state/v2-slice16-audit`
- `GET /api/performance-state/v2-slice17-audit`
- `GET /api/performance-state/v2-slice18-20-audit`
- `GET /api/performance-state/v2-slice21-22-audit`
- `GET /api/performance-state/v2-strict-2026-replay`
- `GET /api/performance-state/v2-lab?year=2026&role=SP|RP&target=process_collapse|result_collapse|return_to_baseline|strong_rebound&minimum_forecasts=5`

`overview` reads the precomputed Slices 0–9 audits. It exposes the frozen collapse/rebound label contract, appearance-level coverage, leakage-safe 2025 development, 2026 external diagnostics, role-pooled state-space diagnostics, Markov regimes, GAS+HAR volatility, the GJR-GARCH challenger, POT-EVT/CAViaR tail diagnostics, and separate collapse/rebound forecast validation. Slice 3A records actual pitcher-role calendar gaps, 2025-only timing-policy comparisons, explicit 60-day reset behavior, corrected five-day/calendar-day half-life units and the expanded low-persistence grid. HTTP requests never fit a model.

`player` returns the selected pitcher's role-specific appearance timeline with the actual days since the prior same-role appearance, observed process/result scores, single-game WPA／RE24／WPA-LI and per-PA forms, mean Stuff+／Location+, collapse/rebound labels, one-step state forecasts, filtered Stuff/Command/Result states, HMM prior/filtered regime probabilities, EWMA/GAS/GAS+HAR/GJR variance forecasts, EVT extreme probability/supported severity, CAViaR 95% loss quantile, and Slice 8 probabilities/alerts for each separate target. SP and RP histories remain separate for dual-role pitchers. These states are research-only performance estimates and do not overwrite Stamina+, diagnose fatigue or predict injury.

`leaderboard` is the Slice 10 research-board payload. It reads the frozen forecast and filtered-state Parquet files, never trains a model, and returns one row per pitcher-role with the latest evaluated pre-appearance probability, season mean probability, event count/rate and last evaluated date. It also returns the selected feature layer, amended-2026 validation metrics and release gate. The ranking is retrospective over completed appearances; it is explicitly not the next-game forecast planned for Slice 11. Conditional rebound boards contain only appearances following a same-role process collapse and do not pad missing opportunities.

`shadow` reads the Slice 11 immutable long-format ledger and monitoring audit. The ledger key is year／pitcher／role／game／target; an existing key's probability is never overwritten, and a later source mismatch is counted as a preserved conflict. The initial 2026 population is labeled `historical_backfill`; only newly observed keys in later rebuilds can be labeled `prospective_append`. Monitoring reports calibration and confusion counts separately for every role-target pair. The integration gate remains closed until untouched 2027 data and at least 250 truly prospective rows per role-target are available. This endpoint does not produce a scheduled-next-game forecast.

`v2-audit` reads the independent Slices 11A–13 audit. It exposes yearly eligibility/exclusion counts, opener／traditional-starter／bulk-reliever classifications, harmonized 2023–2026 warehouse coverage, and the strict expanding-window folds 2023→2024, 2023–24→2025 and diagnostic-only 2023–25→2026. Raw and cleaned cohorts remain separate; onset and persistent collapse are separate targets. Historical Plus values were retrospectively generated with the current frozen Plus models, so this endpoint validates the Performance State layer rather than claiming pristine out-of-sample Plus-model validation.

`v2-slice14-audit` reads the independent Slice 14A/B artifact. Slice 14A reports pitcher-cluster bootstrap intervals, calibration slope/intercept/ECE and evidence status for each fold, role and target. Slice 14B fits the advanced state/regime/volatility/tail/forecast stack on 2023–2025 and evaluates once on diagnostic-only 2026; it does not touch v1 artifacts or the 2027 prospective holdout.

`v2-slice15-audit` is the 2027 prospective-shadow readiness and monitoring contract. It fingerprints every Slice 14 input, locks training years/thresholds/calibration, reports whether an untouched 2027 source exists, and keeps the integration gate closed until append-only predictions and post-game observations reach at least 250 rows per role-target. When the source is absent it returns `awaiting_untouched_2027_source` with zero predictions; it never trains during an HTTP request.

`v2-slice16-audit` is a research-only optimization challenger. It develops on 2023–2024, selects between stable EWMA/MA5 and workload/context features on 2025, refits on 2023–2025, and evaluates once on the fixed 2026 diagnostic. It reports prevalence baselines, frozen Slice 14 metrics, pitcher-cluster bootstrap intervals, and a repaired release gate that explicitly rejects zero-variance baseline-only predictions. It never overwrites Slice 14/15 and keeps production integration closed.

`v2-slice17-audit` calibrates only the Slice 16 challenger. It selects raw, Platt or isotonic calibration on the 2025 window, applies the selected calibrator to a 2023–2025 refit, and reports raw-versus-calibrated Brier/log-loss on fixed 2026 diagnostics. A calibration is retained only when both Brier and log-loss are not worse; it does not replace Slice 14/15 automatically.

`v2-slice18-20-audit` contains three research-only diagnostics: Slice 18 empirical-Bayes pitcher partial pooling, Slice 19 residualized-workload selection-bias sensitivity, and Slice 20 SP/RP plus dominant-arsenal subgroup calibration. All use 2023–2024 development, 2025 selection and 2026 fixed diagnostics; none claims causal workload effects or retunes production probabilities.

`v2-slice21-22-audit` contains strict forward rolling-origin folds (2023→2024, 2023–2024→2025, 2023–2025→2026) for global, partial-pooling and residualized-workload challengers, followed by a research-only freeze decision. A retained challenger is never a formal model replacement; the response explicitly keeps production integration closed until untouched 2027 evidence exists.

`v2-strict-2026-replay` is a pre-registered retrospective holdout replay. Its role-target layer map, feature policy, 2025 Platt calibration rule and fixed false-alert threshold are fingerprinted before the 2026 state files are loaded for scoring. Because this project has previously inspected 2026, the response explicitly does not call it an untouched test; 2027 remains the only untouched prospective year.

`v2-lab` is the research-page synchronization contract. For the frozen 2026 diagnostic it aggregates Slice 14 role-target-specific probabilities as the Lab primary board, joins latest/season-mean deltas from Slice 18 partial-pooling and Slice 19 workload-bias challengers, and exposes the Slice 20 subgroup monitor, Slice 22 freeze decision and strict-replay status. It does not replace the formal `/leaderboards` model, overwrite v1 player timelines, or fit a model during an HTTP request; non-2026 requests should use the existing v1 Lab endpoint as fallback.

The Slice 10/11 player chart plots two same-scale performance series by appearance date, not a probability line. Process/rebound targets compare observed `process_score` (personal-baseline-adjusted Stuff+ and Location+ mean) with the mean of the available pre-appearance Stuff and Command state forecasts. Result collapse compares observed `result_score` (personal-baseline-adjusted RE24/PA and WPA/LI/PA mean) with the pre-appearance Result state forecast. Red solid circles/line are actual values, blue diamonds/dashed line are forecasts, and a light vertical dashed connector shows each game's forecast error; a purple ring marks a target event that was also alerted. Hover/focus exposes WPA, RE24, WPA/LI, Stuff+, Location+, both scores, all four target probabilities and the selected target's outcome. Forecast probabilities remain separate from forecast performance values.

Artifacts are rebuilt with `python backend/scripts/build_performance_state.py`; `--slice4-6-only` reuses the frozen v1.1 filtered states. Slice 4 compares 2–5 diagonal-Gaussian HMMs on 2025 and applies filtered, never smoothed, probabilities with elapsed-time transitions and 60-day stationary resets. Slice 5 fits Student-t GAS then a strictly lagged HAR correction with a 2025-only log-to-level smearing factor. Slice 6 uses `arch`'s Student-t likelihood with a constrained SciPy panel optimizer, resetting pitcher-role boundaries rather than concatenating unrelated players; per-pitcher GARCH fits are rejected for insufficient history. Outputs are `performance_state_slice4_6.json` and `performance_state_advanced_<year>.parquet`.

`--slice7-only` reads the frozen advanced artifacts and writes `performance_state_slice7.json` plus `performance_state_tail_<year>.parquet`. POT candidates compare 90%/92.5%/95% thresholds and declustering run lengths 0/1/2 using only the chronological 2025 fit/validation split; candidates use a comparable full-validation censored likelihood, with `log(1-q)` below the threshold and `log(q)+GPD density` above it. The final GPD is bootstrapped 100 times and audited with KS fit, support coverage, held-out alert recall and false-alert rate. EVT survival is used only when the requested raw extreme threshold lies above the fitted POT threshold; otherwise the frozen 2025 empirical survival is returned with `evt_tail_supported=false`, and expected severity remains null. CAViaR compares SAV and asymmetric-slope specifications on 2025 validation, then reports 2026 quantile loss and Kupiec unconditional coverage.

`--slice8-9-only` reads the frozen Slice 0–7 artifacts and writes `performance_state_slice8_9.json` plus `performance_state_forecasts_<year>.parquet`. For every SP/RP target, 2025 is divided chronologically into 60% training, 20% probability calibration and 20% validation. Five cumulative penalized-logistic layers are compared from lagged baseline through latent-state forecast, HMM prior, GAS+HAR and EVT; XGBoost with GJR/CAViaR is retained as a challenger. Current-appearance filtered states and innovations are forbidden predictors. Slice 9 applies the frozen choices to the amended 2026 external diagnostic and records PR-AUC, Brier/log loss, calibration bins, fixed false-alert metrics, pitcher-cluster bootstrap intervals, dominant-arsenal subgroups and explicit pass/fail gates. Targets remain separate and the overall decision is `keep_research_only`.

`--slice11-only` reads the existing frozen forecast and filtered-state artifacts; it does not refit any model. It atomically appends unseen keys to `performance_state_shadow_ledger.parquet` and writes `performance_state_slice11.json`. Performance State rebuilds are not currently part of the daily pipeline; the data-freshness report therefore labels this dataset `manual frozen-model rebuild · immutable append ledger` instead of implying automatic currency.

`--slice11a-13-only` builds only the independent v2 artifacts: `performance_state_v2_contract.json`, `performance_state_v2_slice11a_13.json`, `performance_state_v2_warehouse_<2023|2024|2025|2026>.parquet` and `performance_state_v2_predictions_<2024|2025|2026>.parquet`. It fixes the leverage reference to 2023, never rewrites v1 artifacts, and keeps 2027 untouched.

`--slice14-only` builds `performance_state_v2_slice14.json`, one advanced state Parquet per year, and `performance_state_v2_slice14_predictions_2026.parquet`. It requires the Slices 11A–13 warehouses and uses 2023–2025 for all fitting/model selection; 2026 is diagnostic-only.

`--slice15-only` writes the readiness artifact `performance_state_v2_slice15.json`. It fingerprints the frozen Slice 14 inputs and checks for `data/MLB2027/mlb_2027.duckdb`; it does not materialize, refit or retune a 2027 model. The source must be available before a future append-only materialization step can create prospective rows.

`--slice16-only` writes `performance_state_v2_slice16.json` and `performance_state_v2_slice16_predictions_2026.parquet`. It is a non-destructive challenger build using only frozen Slice 14 state inputs; 2026 remains diagnostic-only and no production artifact is changed.

`--slice17-only` writes `performance_state_v2_slice17.json` and `performance_state_v2_slice17_predictions_2026.parquet`. It calibrates the Slice 16 challenger using the temporally separate 2025 selection window; it never refits Slice 14/15 or opens production integration.

`--slice18-20-only` writes `performance_state_v2_slice18_20.json`, plus separate Slice 18 and Slice 19 2026 challenger prediction Parquets. It performs partial-pooling, workload-sensitivity and subgroup-calibration diagnostics without changing frozen production inputs.

`--slice21-22-only` writes `performance_state_v2_slice21_22.json` with forward-fold metrics and the non-production freeze decision. It does not rewrite Slice 14/15 or open any integration gate.

`--strict-2026-replay-only` writes `performance_state_v2_strict_2026_replay.json` and `performance_state_v2_strict_2026_replay_predictions.parquet`. It fits only on 2023–2024, calibrates on 2025, then loads 2026 after the model fingerprint is fixed; it does not tune on 2026 or open production integration.

The build uses 2025 to freeze empirical-Bayes personal baselines, thresholds, calendar-gap policy and all Slice 3A–6 parameters, then evaluates on 2026. Because Slice 3A was introduced after inspecting the first 2026 diagnostic, 2026 is labeled `test_with_documented_slice3a_amendment`, not pristine untouched validation; 2027 is reserved for prospective untouched validation. RE24 is pitcher-positive, WPA uses the shared plate-appearance boundary contract, and WPA/LI uses a shrunk 2025 empirical leverage table. `game_score_proxy` is explicitly a starter-only Bill James-style proxy, not an official earned-run Game Score.

### Catcher Descriptive Metrics

- `GET /api/catchers/descriptive/leaderboard?year&minimum_outs=0`
- `GET /api/catchers/descriptive/pairs/leaderboard?year&minimum_outs=120`
- `GET /api/catchers/descriptive/{catcher_id}?year`
- `GET /api/catchers/descriptive/{catcher_id}/strategy-bridge?year`

The catcher leaderboard returns the reconciled Slice 2–3 raw counts, cERA/cRA9/cFIP, full-season pitcher-mix tERA/tRA9/tFIP, cSaveRun and cSaveRun/IP. When the Slice 4 artifact is present, catcher rows also include adjacent-season support, a transparent reliability tier, and a dominant-pair sensitivity calculation that removes the pitcher with the most paired outs before recomputing cRA9, tRA9 and cSaveRun/IP. A stable dominant-pair row does not override a failed project-wide cross-year gate. Values remain observed associations and are never annualized or labeled causal catcher value.

When the passed Slice 5 artifact is present, catcher rows additionally expose `cxera`, `txera`, `x_runs_vs_mix`, `x_runs_vs_mix_per_ip`, `xera_expected_runs`, `pitcher_mix_expected_runs`, `xera_source_coverage_pct`, `xera_status` and `xera_model_version`. The response-level `xera` object carries model/contract versions, definitions, source coverage, evaluation periods and warnings. Petehub xERA v1 is a chronological additive calibration of Statcast `estimated_woba_using_speedangle`; it is explicitly not MLB's published xERA formula. `x_runs_vs_mix = pitcher_mix_expected_runs - xera_expected_runs` is an expected-results association, not causal catcher value.

When the passed Slice 6 v2 artifact is present, catcher-season rows additionally expose primary product fields `frv`, `throwing`, `blocking`, `framing`, `frv_status`, `source_innings_status`, `source_display_ip` and `outs_difference`. FRV and each component are source-provided runs above the source-defined average, not absolute runs prevented. Rounded components may differ from total FRV by one run, so `frv` remains authoritative and components must not be added to it again. Comparison-only DRS fields remain in the API/artifact for audit compatibility but are not displayed as the primary defense scale. The response-level `defense` object carries both source fingerprints, cross-source and canonical reconciliation, definitions, cross-year/overlap diagnostics and release-gate status. Canonical catcher outs remain the qualification denominator; source innings are audit-only. Defense fields are not added to cSaveRun or x Runs vs Mix. Park factor is `deferred_by_user`, so no park-adjusted metric is returned.

Paired Duo remains one season-pitcher-catcher row and defaults to 120 outs (40 IP). Its pair cSaveRun uses the pair's shared outs; Slice 4 reliability tiers apply only to the aggregate catcher-season view. Slice 5 adds pair `xera`, full-season `pitcher_xera`, `x_runs_vs_mix`, `x_runs_vs_mix_per_ip`, `xera_expected_runs`, source coverage and status. All expected-run numerators and outs reconcile through PA → pitcher → pair → catcher → team. Slice 6 FRV and components are intentionally unavailable on Paired Duo because a season-catcher total cannot be defensibly allocated to individual pitchers.

The Slice 8 strategy-bridge endpoint is research-only and currently returns model-consistent diagnostics for 2026. A row contains the on-field catcher context, total decisions, supported-set and chosen-support coverage, normalized entropy, effective supported choices, top-choice probability, supported deviation, model-minimum-choice rate, noise-floor count and count-tier splits. For 2021–2025 it returns `status=unavailable` and does not impute. The endpoint never returns a rank, composite catcher score, factual best pitch, true exploitability or causal caller attribution.

### Batter Comparison

- `GET /api/batter-comparison/period/options`
- `GET /api/batter-comparison/period/date-range`
- `GET /api/batter-comparison/period/overview`
- `GET /api/batter-comparison/team-research`
- `GET /api/batter-comparison/team-research/lineup-scenarios?year&team&opponent_hand=L|R`

`period/overview` returns Period A／B values, `delta = B - A`, and separate denominators for production, discipline, Bat Tracking and Miss Distance metrics. Percentage deltas use percentage points (`pp`). Both zone maps share one heatmap color domain.

Arbitrary-date X/Y/Z timing is not available locally. `timing_reference` therefore contains explicitly labeled full-season Savant summaries and never enters the period delta. `source_audit` records unavailable exact-distribution, Squared-Up／Blast and batting-stance fields rather than returning fabricated zeroes.

`team-research` uses `data_mode=recent_observed_research`. Batting order is reconstructed from team PA sequence and defensive positions from fielder IDs. It returns descriptive order splits, observed pitcher-hand splits, recent starter/order probabilities and three empirical run-expectancy scenarios. Active roster, injuries, official DH／PH roles and probable starters are not available from the local tables and are listed in `coverage`／`limitations`.

`team-research/lineup-scenarios` is the read-only Team Dashboard path for the three lineup cards: recent consensus, latest observed and run-expectancy candidate. It never reconstructs positions or runs simulations during an HTTP request. The data refresh pipeline computes both vs RHP and vs LHP results for every team, then atomically replaces `data/derived/batter_lineup_scenarios_<year>.json`. Responses expose `cache_status=current|stale|unavailable`; when newer pitch data exists or a rebuild fails, the endpoint continues serving the last completed entry with a warning.

### Data Operations Observability

- `GET /api/admin/data-freshness?year=2026` reads the latest generated freshness manifest. If no manifest exists for the requested year, it builds a non-persisted local snapshot without an external coverage request.
- `POST /api/admin/data-freshness/refresh?year=2026` rebuilds official coverage, dataset cutoffs, automation state and page-impact mappings, then writes the latest JSON, Markdown and timestamped history snapshot under `data/admin_job_logs`.
- `GET /api/admin/project-tracker` reads the Git-tracked `docs/PROJECT_TRACKER.json`, calculates project and portfolio progress from slice statuses, and returns handoff-ready Markdown.
- `GET /api/admin/daily-update-settings` reads the atomic daily scheduler settings.
- `PUT /api/admin/daily-update-settings?game_updates_enabled=false` pauses or enables the heavy game-data stages for future scheduled runs. It never disables the scheduled task itself: the transaction refresh and freshness report continue every day. Explicit `daily_update.py --step ...` commands remain available for manual maintenance even while the automatic game stages are paused.

The freshness manifest is the runtime authority for data cutoff reporting. `docs/PROJECT_TRACKER.json` is the planning authority for project, slice, verification and next-step status.

- `POST /api/admin/jobs/backfill-historical-plus?year=2024` starts the resumable local historical Plus pipeline for exactly one selected season. That season runs Location+, per-pitch Stuff+, Stuff leaderboard, Pitching+ and Stamina in dependency order; downstream stages do not run while per-pitch Stuff+ remains partial. A resumed season skips stages already marked `completed` or `current`. Admin child processes force UTF-8 on stdin/stdout/stderr so Windows legacy console encodings cannot turn a successfully written artifact into a failed job response.
- `GET /api/admin/jobs/historical-plus-status` returns the persisted season/stage status and, while Stuff+ is running, its cached-row and pitcher progress. Re-running the POST resumes the per-pitch cache instead of discarding completed pitchers.

## Standard Response Shape

```json
{
  "meta": {
    "year": 2026,
    "data_updated_at": "2026-07-02T00:00:00Z",
    "warnings": []
  },
  "summary": [],
  "charts": {},
  "tables": {}
}
```

## Versioning Rule

Keep URLs stable during MVP. If a breaking response change is needed, add a new field first, migrate frontend, then remove the old field later.
# Ballpark D4 avatar profile (draft, not D5-released)

`PATCH /api/auth/avatar` requires the existing authenticated session and accepts `{ "avatar": { "avatar_version": 1, "body_id": "tone_2", "uniform_id": "neutral_home", "palette_id": "orange", "number": null, "bats": "R", "throws": "R" } }`. `body_id` is `tone_1`–`tone_4`; uniform is `neutral_home` or `neutral_away`; palette is `orange`, `teal` or `slate`; number is null or 0–99. Both bats and throws accept `R`/`L`/`S`; `unknown` remains accepted only for old-save compatibility. New defaults and legacy-unknown creator drafts use `R`; opening/cancelling does not overwrite the saved profile. Unknown versions and invalid values are rejected with 422. The response is the existing `AuthResponse`, whose `user.avatar` contains the saved v1 appearance and `user.avatar_recovery_needed` reports an unreadable stored payload. `GET /api/auth/me` and login return the same fields. Favorite-team identity colors are derived from `user.favorite_team_code` at render time in the creator and walk runtime, never from temporary Viewing team; no avatar-version migration or saved-team mutation is required. Uniform home/away remains the saved colorway selection; a chosen favorite team overrides the manual accent, retaining the saved palette for neutral fallback. These are pixel team-color uniforms, not official jersey/logo replicas. Invalid stored data is preserved server-side while the API shows a neutral fallback. The avatar has no MLB logo, player identity, or client-side authoritative game state. Auth responses remain `Cache-Control: no-store`.
