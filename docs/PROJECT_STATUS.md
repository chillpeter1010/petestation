# Project Status

Petehub is currently a portfolio-stage baseball analytics platform. The core direction is to turn a Streamlit prototype into a maintainable website with a Nuxt 3 frontend and a FastAPI backend.

This document summarizes what is already working, what is still experimental, and what data is required to run the project locally.

## Current Product Scope

Petehub is organized around multiple baseball analysis stations.

| Station | Status | Notes |
| --- | --- | --- |
| Pitcher Station | Active | Main migrated product area. |
| Game Center | Active | Daily game pitching lines and game-level navigation. |
| Comparison | Active | Pitcher-vs-pitcher and period-vs-period comparison. |
| Rotation | Active | Starter rotation, bullpen role, and fatigue prototypes. |
| Lab | Prototype | Fatigue, Stuff+, and Location+ experiments live here first. |
| Fielder Station | Prototype | Entry point for catcher / infield / outfield workflows. |
| Catcher Station | Prototype | Catcher-pitcher sequence analysis has an initial route and filters. |
| Batter Station | Planned | Page shell can be added later; no core batter modules yet. |

## Completed User-Facing Areas

### Pitcher Personal

The Pitcher Personal page is the most complete migrated area.

Current features:

- Year / role / team / pitcher selector.
- Season summary cards.
- Rotation tab with game-level workload and WPA style views.
- Stuff tab with pitch location scatter, heatmap blend, movement chart, pitch mix, movement summary, and run-value tables.
- Sequence tab with count-state pitch mix tree and filterable sequence payloads.
- Discipline tab with reusable strike-zone panel boards.
- Outing report view inspired by Pitcher List style single-game summaries.
- Video lookup integration where local data has direct video URLs.

Known caveats:

- Some model grades are still prototype scores unless trained legacy artifacts are connected.
- Several heavy visual modules are still being visually tuned.
- Real data is local-only and is not committed to the repository.

### Pitcher Comparison

Current features:

- Two-pitcher comparison with independent year / team / pitcher selectors.
- Period comparison for one pitcher across two date ranges.
- Standard comparison metrics.
- Period location, movement, pitch mix, discipline, and video panels.
- Shared chart components reused from Pitcher Personal where possible.

Known caveats:

- Some historical-season model columns depend on which derived exports exist locally.
- Period selectors should continue moving toward explicit "apply" behavior so expensive payloads do not refresh too often.

### Rotation And Bullpen

Current features:

- Starter rotation page.
- Bullpen role page.
- Bullpen availability prototype.
- Starter fatigue lab.
- Reliever fatigue lab.
- Game WPA trend style charts.
- Workload and readiness prototypes.

Known caveats:

- Fatigue formulas are transparent prototypes, not validated predictive models.
- Bullpen availability depends on local derived data availability.
- Some role classification still needs stricter starter / reliever rules for edge cases.

### Game Center

Current features:

- Browse games by year and date.
- Previous / next day controls.
- Game cards with matchup and score.
- Game pitching lines by team.
- Pitch-type mini charts.
- Pitcher name links and outing report entry points.

Known caveats:

- Scores and pitcher game lines depend on the local game-line cache.
- Update jobs should eventually expose clearer progress and failure recovery.

### Catcher Station

Current features:

- Fielder station route.
- Catcher station route.
- Catcher sequence route.
- Catcher / paired pitcher filters.
- Reused pitch sequence visualization concept from Pitcher Personal.

Known caveats:

- Framing, blocking, throwing, and ABS modules are placeholders.
- Catcher sequence still needs deeper QA around data coverage and filter defaults.
- Batter / fielder ID lookup tables are not yet productized like pitcher and catcher lookup tables.

## Backend And Data Status

The backend is FastAPI with service-layer modules that read local DuckDB, CSV, and derived export artifacts.

Important backend areas:

- Pitcher selector and profile services.
- Personal analysis services.
- Comparison services.
- Game-line services.
- Video lookup services.
- Admin refresh endpoints.
- Prototype Stuff+ and Location+ scoring endpoints.

Local data currently lives under:

```txt
data/
```

Real data artifacts are intentionally ignored by Git. The repository should document the data contract without redistributing full MLB data, DuckDB files, parquet exports, or video assets.

Expected local artifacts can include:

- Season DuckDB files.
- Pitch-level caches.
- Pitcher game-line caches.
- Video lookup tables.
- Derived outing exports.
- Starter / reliever dashboard CSVs.
- Research model exports.

## Model Status

Model work is intentionally separated into Lab pages before being promoted to product pages.

Current model state:

| Model Area | Status | Notes |
| --- | --- | --- |
| Stuff+ | Prototype / migration planned | Legacy supervised logic exists; product pages currently need versioned artifacts before final use. |
| Location+ | Prototype / migration planned | Legacy supervised logic exists; current product output may use fallback logic unless artifacts are connected. |
| Pitching+ | Deferred | Not currently a first-class trained pipeline in the new app. |
| Fatigue | Prototype | Transparent rule-based formulas for starters and relievers. |
| PLV / HAVAA | Deferred | Intentionally skipped for the current migration scope. |

Product rule:

Do not present prototype model scores as final model outputs. Product pages should clearly distinguish trained artifacts from fallback or experimental scores.

## Portfolio Readiness

Ready for portfolio packaging:

- Clear frontend / backend split.
- Meaningful migrated pages beyond a simple demo.
- Realistic API and service architecture.
- Workboard and migration documentation.
- Local data excluded from Git.
- Demo recording prepared locally.

Still recommended before publishing:

- Add demo video link to `README.md`.
- Add screenshots or small GIFs if the video is hosted externally.
- Add a short "How to run without full data" section or a small `data/sample/` fixture.
- Run frontend typecheck and backend tests before the first public commit.
- Check for local absolute paths in docs and code comments.

## Known Public-Repo Constraints

This portfolio repository should not include:

- Full MLB / Statcast datasets.
- DuckDB cache files.
- Parquet exports.
- Compressed data archives.
- Video files.
- `.env` files.
- Private local paths that are required for normal execution.

The public repository should make it clear that the app is a data product and that the full local dataset is separate from the source code.

## Suggested Next Steps

1. Add a demo video link to `README.md`.
2. Create `docs/SECURITY_AND_DATA.md` for public-release hygiene.
3. Add a small sample dataset or mock API mode.
4. Initialize Git and make the first clean portfolio commit.
5. Push to GitHub with data artifacts excluded.
