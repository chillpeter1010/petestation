# Pitcher Personal Legacy Map

Source reviewed:

- `C:\Users\郭睿承\Desktop\實習個案\abs2025\claude\pages\26_pitcher_personal.py`
- Size: 4,161 lines
- Main Streamlit UI starts around line 3,226.

## Important Correction

The legacy page structure is not the same as the current Nuxt tab structure.

Legacy tabs:

1. `Overview`
2. `Rotation`
3. `Stuff`
4. `Sequence`
5. `Discipline`

The legacy `Pitch Location Scatter (click a pitch)` belongs inside `Stuff`, not `Overview`.

The legacy video workflow is present but wrapped in `if False`, so it is effectively disabled in the Streamlit UI even though helper functions exist and the new backend already has a `/api/personal/videos` endpoint.

## Global Page Flow

The page has a single global pitcher context:

- Hero header: `Pitcher Personal`
- Button: switch to `pages/1_pitcher_model.py`
- Selectors:
  - Season
  - Role: `SP` / `RP`
  - Team
  - Pitcher
  - Start Date
  - End Date
- Global detail-data toggle:
  - `載入 Stuff / Sequence / Discipline / Videos 詳細逐球資料`

Several tabs depend on this detail toggle. In a website version, this should become explicit data loading behavior rather than a hidden Streamlit checkbox.

## Data Sources

Reference CSVs:

- Dashboard
- BR / rotation
- Stuff+
- Location+
- Pitching+

DuckDB / cached Statcast:

- `pitches_enriched` preferred
- fallback to `pitches`
- fallback to `load_cached_statcast_year`

Video helpers:

- `pitch_video.build_playbyplay_pitch_map`
- `pitch_video.fetch_sporty_video_metadata`

Timing helpers:

- `data/MissDistance/2025_pitch_timing_summary_full_season.csv`
- `data/MissDistance/daily_count_2025_min1/combined_matched.csv`

## Overview Tab

Legacy contents:

- Top summary metrics shown above tabs:
  - Team
  - GS
  - IP
  - ERA
  - Stuff+
  - WAR
- `Dashboard Row` table
- `BR / Rotation Row` table

Not in legacy Overview:

- Pitch location scatter
- Movement chart
- Sequence tree
- Timing charts

Current migration status:

- Mostly migrated through `/api/personal/overview`.
- Current Nuxt Overview should stay simple and should not own Stuff visuals.
- Updated: Nuxt Overview now only shows the dashboard and BR / rotation tables. Pitch mix and Stuff visuals have been moved out.

## Rotation Tab

Legacy contents:

- `Game Log` table
- Cumulative WPA chart
- Rotation metrics:
  - Total WPA
  - Starts
  - Avg Start WPA
- Select one game for Rotation / Fatigue
- Fatigue bar chart
- Fatigue metrics:
  - Pregame Readiness
  - Final Fatigue Score
  - Cumulative Pitches
  - Innings Tracked
- Fatigue inning table

Current migration status:

- Backend has `/api/personal/rotation`.
- Current frontend has tables for game log, WPA games, and fatigue table.
- Updated: frontend now includes a WPA line chart, a rotation/fatigue game selector, fatigue metric cards, and a fatigue bar chart.
- Still incomplete:
  - The visual styling is website-native rather than a direct Matplotlib clone.
  - More detailed per-game state can be refined later if the legacy fatigue model expands.

## Stuff Tab

Legacy contents when detail data is loaded:

- `Pitch Type Matrix`
  - Stuff+
  - Location+
  - Pitching+
- `Movement Comparison vs League`
  - Usage
  - HB
  - IVB
  - Velo
  - League hand-specific benchmarks
  - Differences vs league
- `Run Values by Pitch Type`
  - RV/100
  - Run Value
  - Pitches
  - Usage %
  - PA
  - BA / SLG / wOBA
  - Whiff%
  - K%
  - PutAway %
  - xBA / xSLG / xwOBA
  - Hard Hit %
- `Movement`
  - Pitch selector
  - Mode radio: `scatter` / `average`
  - Movement scatter or profile chart
- Stuff pitch-location workflow:
  - Right-side filters:
    - Stand
    - Count
    - Pitch
    - Pitch Result
    - In Play Result
    - PA Result
  - Filter Snapshot:
    - pitches
    - Zone%
    - Swing%
    - O-Swing%
    - Whiff%
    - AVG
  - Usage line by pitch type
  - Heatmap Blend slider
  - If heatmap is off:
    - Plotly `Pitch Location Scatter (click a pitch)`
    - point selection stores selected pitch key
    - selected pitch detail table
    - selected pitch video card
  - If heatmap is on:
    - Matplotlib heatmap / scatter blend
- `Swing Timing / Miss Distance`
  - optional checkbox
  - pitch-level timing section

Current migration status:

- Updated: frontend tab label/order now matches the legacy `Stuff` section.
- Updated: `/api/personal/movement` now accepts Stuff filters for stand, count, pitch, pitch result, in-play result, and PA result.
- Updated: movement API now returns a filtered `filter_snapshot`, filtered `pitch_location_scatter`, `movement_scatter`, and `run_values_by_pitch_type`.
- Updated: strike-zone scatter payloads are no longer sampled at 1000 points; they return all valid filtered rows.
- Updated: frontend Stuff tab now has filter controls, snapshot cards, Run Values by Pitch Type, filtered location scatter, selected pitch detail, hover pitch detail, video modal behavior, movement chart scatter/average modes, in-play result filtering, PA result filtering, and nested Timing toggle.
- Missing or incomplete:
  - Heatmap Blend behavior.
  - League benchmark visual.

## Sequence Tab

Legacy contents when detail data is loaded:

- Filters:
  - Stand
  - Count
  - Pitch
  - Pitch Result
  - Catcher
- Filter Snapshot:
  - pitches
  - Zone%
  - Swing%
  - O-Swing%
  - Whiff%
  - AVG
- `Sequence Outcomes`
  - Plotly count-state tree
  - Pie charts per count state
  - optional conditioned downstream map
  - reset conditioned map button
- `Inspect count state`
  - radio selector for exact or aggregate count state
- `Count Detail`
  - Current Pitch table
  - Next Pitch table
- Conditional branch workflow:
  - choose pitch branch
  - apply branch to downstream map
  - downstream pitch / WPA / PA metrics
  - conditioned WPA summary table
  - immediate downstream event distribution table
- Separate legacy helper tables:
  - shallow-count sequences
  - two-strike sequences

Current migration status:

- Updated: `/api/personal/sequence` accepts stand, count, pitch, pitch result, and catcher filters.
- Updated: sequence API returns filtered `filter_snapshot`.
- Updated: sequence API returns `count_pitch_mix` for the count-state tree.
- Updated: sequence API returns shallow-count and two-strike sequence tables.
- Updated: sequence API accepts `condition_count` and `condition_pitch` for downstream branch analysis.
- Updated: sequence API returns conditioned downstream count-state mix, conditioned summary metrics, and conditioned WPA summary table.
- Updated: sequence API accepts `detail_count` and returns Current Pitch / Next Pitch count detail tables.
- Updated: frontend Sequence tab has filters, snapshot cards, count-state tree, Count Detail controls, Current Pitch / Next Pitch tables, conditioned branch controls, downstream metrics, conditioned downstream tree, and conditioned WPA summary table.
- Missing or incomplete:
  - Count-state inspect radio.
  - Immediate follow-up event distribution.
  - Direct click-to-condition behavior from the pie chart.

## Discipline Tab

Legacy contents:

- `Discipline Summary`
  - Pitches
  - Swing%
  - Whiff%
  - CSW%
  - Zone%
  - Chase Swings
  - 1st Pitch Strike%
- `Stand Split`
  - Stand
  - Pitches
  - Whiff%
  - CSW%
  - Zone%
- Detail-data visuals:
  - Stand Filter
  - Count Filter
  - Heatmap Blend
  - Result Panels:
    - Called Strike
    - Swing Strike
    - In-Play
    - Foul
  - Count Situation:
    - 0-0
    - Hitter Ahead
    - Pitcher Ahead
    - Two Strikes
  - Exact Count Grid:
    - 0-0 through 3-2, grouped into three rows

Current migration status:

- Backend has discipline summary and stand split.
- Frontend has summary and stand split tables.
- Missing or incomplete:
  - Stand/count filter controls for discipline visuals.
  - Result panel location charts.
  - Count situation panel charts.
  - Exact count grid.
  - Heatmap blend.

## Disabled Legacy Videos Block

Legacy code has a full video workflow under `if False`.

Contents:

- Metrics:
  - Pitches
  - Games
  - Pitcher Hand
- Game summary table
- Focus GamePk selector
- Video mapping load by game
- Coverage caption
- Pitch selector
- Selected pitch detail table
- Video card

Current migration status:

- Backend has `/api/personal/videos`.
- Frontend has a simple Videos tab table, which did not exist as an active legacy tab.
- Product decision needed:
  - Keep Videos as a first-class website tab, or
  - Reattach video as a selected-pitch detail inside Stuff, matching the active legacy workflow.

## Timing

Legacy timing is not a top-level tab.

It is nested inside Stuff:

- `Swing Timing / Miss Distance`
- Explicit checkbox: `Show swing timing / miss distance`
- 2025-only message when year is not 2025
- Pitch selector
- Metrics:
  - Whiff Rate
  - Miss Distance
  - Perfect Contact
  - Competitive Swing
  - Swing Coverage
- Three timing charts:
  - tied up / centered / flail
  - late / on time / early
  - over / lined up / under
- Pitch Timing Coverage Table

Current migration status:

- Backend has `/api/personal/timing`.
- Frontend currently has a top-level Timing tab.
- This is structurally different from legacy.
- Product decision needed:
  - Keep Timing top-level for website clarity, or
  - Move it back under Stuff to preserve legacy mental model.

## Shape Lab Residue

Legacy file still contains:

- `build_shape_lab_reference_features`
- `build_shape_lab_benchmarks`

These helpers reference `MOVEMENT_MODEL_BASE_FEATURES`, but the page does not import it.

Current interpretation:

- This is deferred model / Shape Lab code, not core Pitcher Personal UI.
- It should not be mixed into the current personal page migration until the model API boundary is designed.

## Migration Implications

Do not migrate by endpoint names alone. Migrate by legacy product sections:

1. Global context and data loading.
2. Overview.
3. Rotation.
4. Stuff.
5. Sequence.
6. Discipline.
7. Decide whether Videos and Timing become first-class website tabs or nested workflows.

The next migration slice should focus on one legacy section at a time, preserving:

- Filter ownership.
- Chart ownership.
- Selection state.
- Tables created by a selected chart point or selected count state.
- Whether a feature was active in the old UI or disabled behind `if False`.

## Recommended Next Slice

`Stuff parity slice 2`

Goal:

- Continue the legacy Stuff visual workflow after the first filter/data slice.

Scope:

- Movement chart modes: scatter / average.
- League benchmark visual or explicit benchmark table.
- Click pitch -> selected pitch detail payload.
- Decide whether selected pitch video card belongs inside Stuff now or waits for a video slice.
- Do not add Sequence or Discipline changes in the same slice.

## Latest Sequence / Discipline Update

Sequence migration now includes:

- `/api/personal/sequence` filters: stand, count, pitch, pitch result, catcher.
- Filtered snapshot payload.
- Filtered pitch location scatter payload.
- Frontend filter controls, snapshot cards, count tree, filtered location scatter, and sequence tables.

Still missing from legacy Sequence:

- Count-state inspect radio.
- Current Pitch / Next Pitch detail tables.
- Conditional downstream branch workflow.
- WPA downstream summaries.
- Immediate follow-up event distribution.

Discipline migration now includes:

- `/api/personal/discipline` filters: stand, count.
- Filtered snapshot payload.
- Filtered pitch location scatter payload.
- Result panel location payloads: Called Strike, Swinging Strike, In Play, Foul.
- Count situation payloads: 0-0, Hitter Ahead, Pitcher Ahead, Two Strikes, plus exact count payloads.
- Frontend filter controls, snapshot cards, result panels, and count situation panels.

Still missing from legacy Discipline:

- Exact count grid rendering.
- Heatmap blend behavior.

## Latest Videos / Timing Decision

Legacy item 7 is not a request to blindly create top-level tabs.

- `Videos` is not active as a top-level legacy tab. The large video workflow exists under `if False`, so Streamlit never renders it.
- The reachable legacy video behavior is inside Stuff: click/select a pitch in `Pitch Location Scatter`, then show selected pitch detail and `render_pitch_video_card(selected_pitch_row)`.
- `Timing` is not a top-level legacy tab. It is nested inside Stuff behind `Show swing timing / miss distance`.

Recommended website direction:

- Put selected pitch video back inside Stuff selected-pitch detail.
- Put Timing back inside Stuff as an explicit nested toggle.
- Only create a first-class Videos page later if video review becomes a separate product workflow.

Implemented status:

- Stuff `Pitch Location Scatter` points are selectable in the Nuxt UI.
- Selected pitch detail is shown under the Stuff location scatter.
- Selected pitch video is exposed as an `Open Video` link when the payload includes `video_url` or `play_id`.
- Stuff has a nested `Swing Timing / Miss Distance` toggle that lazy-loads `/api/personal/timing`.
- A separate top-level Videos or Timing tab is still intentionally not part of the migrated legacy tab structure.
