# Agent Workflow

更新日期：2026-10-24
文件狀態：**CURRENT — 工作方式與文件生命週期的權威規則**

## Orchestrator

Owns scope, sequencing, and integration.

- Keeps migration slices small
- Decides which page or endpoint is next
- Checks that frontend and backend contracts match
- Prevents speculative rewrites

## Frontend Agent

Owns Nuxt UI and interaction.

- Pages and layouts
- Filter components
- Chart/table/video components
- Pinia stores
- TypeScript API types

## Backend/Data Agent

Owns API and data services.

- FastAPI routes
- Pydantic schemas
- pandas/DuckDB/PostgreSQL repositories
- Service extraction from Streamlit files
- Caching boundaries

## Model Agent

Owns model and metric logic.

- Feature engineering
- Model loading/training workflow
- Similarity metrics
- Stuff/discipline/spin calculations

## QA/Debug Agent

Owns verification.

- Repro cases from old Streamlit outputs
- Backend service tests
- API smoke tests
- Frontend route and component checks

## Working Rule

For every migrated page, write the API contract before rebuilding the Nuxt page. This keeps the frontend and backend agents from coupling through hidden assumptions.

## Documentation Rule

- One small project owns one canonical human-readable Markdown document in `docs/`; Slice boundaries are sections inside that document, not separate top-level files.
- Starting or completing a Slice updates the existing project document, `PROJECT_TRACKER.json`, generated `PROJECT_TRACKER.md`, and—when cross-chat context changes—only the concise current/recent sections of `NEXT_CHAT_HANDOFF.md`.
- Generated evidence belongs in versioned JSON, Parquet, manifests, or immutable snapshots under `data/`; builders must not generate a new `SLICE*.md` report.
- Create another top-level project document only when the tracker defines a genuinely separate project with a separate scope and lifecycle.
- Current consolidated research documents are `CATCHER_DESCRIPTIVE_METRICS.md` and `PLAYER_ARCHETYPES_PITCH_STRATEGY.md`.

## Handoff And Progress Rule

- `PROJECT_TRACKER.json` is the only authority for project/Slice status, verification and next step. `PROJECT_TRACKER.md` is generated and must never be edited independently.
- `NEXT_CHAT_HANDOFF.md` is a short operational handoff, not a historical notebook. It contains stable cross-project rules, the generated current-progress block, only recent changes and current blockers.
- `archive/PROJECT_HISTORY.md` owns detailed past progress and incident history. Search or read only the relevant section when needed; do not load it by default at the start of every conversation.
- `python backend/scripts/sync_project_tracker.py` must regenerate both `PROJECT_TRACKER.md` and the marked current-progress block in `NEXT_CHAT_HANDOFF.md` after tracker changes.
- Do not duplicate detailed metric definitions in the handoff. Link to the relevant project document or metric contract.

## Document Categories And Lifecycle

| Category | Canonical source | Lifecycle / rule |
| --- | --- | --- |
| Current progress | `PROJECT_TRACKER.json` | **CURRENT / AUTHORITATIVE**; update first |
| Generated progress | `PROJECT_TRACKER.md` | **GENERATED**; never hand-edit |
| Cross-chat handoff | `NEXT_CHAT_HANDOFF.md` | **CURRENT**; keep concise |
| Frontend display rules | `RESEARCH_DISPLAY_CONTRACT.md` | **CURRENT** |
| Backend API rules | `API_CONTRACTS.md` | **CURRENT** |
| Plus metric rules | `PLUS_METRICS_CONTRACT.md` | **CURRENT** |
| Catcher project | `CATCHER_DESCRIPTIVE_METRICS.md` | **CURRENT PROJECT REFERENCE**; tracker owns status |
| Archetype / strategy project | `PLAYER_ARCHETYPES_PITCH_STRATEGY.md` | **CURRENT PROJECT REFERENCE**; tracker owns status |
| Batter timing / comparison | `BATTER_SWING_TIMING_ROADMAP.md` | **PROJECT REFERENCE**; status table may be historical, tracker wins |
| Pitching+ design | `PITCHING_PLUS_DESIGN.md` | **DESIGN REFERENCE**; production status is a dated snapshot |
| Private-site operations | `PRIVATE_SITE.md` | **CURRENT OPERATIONS REFERENCE**; verify commands against runtime |
| Migration plan | `MIGRATION_PLAN.md` | **REFERENCE**; architectural principles only, not current order |
| Module candidates | `MODULE_CANDIDATES.md` | **REFERENCE / REVIEW BEFORE USE**; candidates may already be implemented or obsolete |
| Pitcher Personal legacy map | `PITCHER_PERSONAL_LEGACY_MAP.md` | **HISTORICAL REFERENCE**; old Streamlit parity only |
| Pitcher Personal migration | `PITCHER_PERSONAL_MIGRATION.md` | **HISTORICAL REFERENCE**; API contracts and current code win |
| Past progress | `archive/PROJECT_HISTORY.md` | **ARCHIVE**; load on demand only |
| Old status/workboard | `archive/PROJECT_STATUS_2026-07.md`, `archive/WORKBOARD_2026-07.md` | **SUPERSEDED / ARCHIVE** |

Lifecycle labels mean:

- **CURRENT / AUTHORITATIVE**: may define present behavior or status.
- **GENERATED**: rebuilt from another authority; never edit directly.
- **REFERENCE**: useful design/history, but verify against current code and tracker.
- **ARCHIVE / SUPERSEDED**: retained for provenance only and must not drive new work.

## Handoff Maintenance Checklist

1. Update the relevant project document without creating a per-Slice Markdown.
2. Update status, slices, verification, next step and `updated_at` in `PROJECT_TRACKER.json`.
3. Run `python backend/scripts/sync_project_tracker.py`.
4. Keep only recent cross-project changes or live blockers in `NEXT_CHAT_HANDOFF.md`; move durable detail to the project document or archive.
5. Run UTF-8 validation, relevant tests and `git diff --check`.
