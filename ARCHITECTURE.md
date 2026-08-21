# Project Architecture

## 1. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                         Frontend Layer                       │
│                    Nuxt 3 / Vue 3 / TypeScript              │
│                                                              │
│  Pages:                                                      │
│  - Starter Stuff                                             │
│  - Starter Discipline                                        │
│  - Pitcher Personal                                          │
│                                                              │
│  Components:                                                 │
│  - FiltersPanel                                              │
│  - SummaryCards                                              │
│  - PitchCharts                                               │
│  - SequenceView                                              │
│  - VideoPanel                                                │
│  - DataTables                                                │
└───────────────────────┬──────────────────────────────────────┘
                        │ HTTP / JSON API
┌───────────────────────▼──────────────────────────────────────┐
│                         Backend Layer                        │
│                      FastAPI / Python                        │
│                                                              │
│  API Domains:                                                │
│  - /api/pitchers                                             │
│  - /api/stuff                                                │
│  - /api/discipline                                           │
│  - /api/personal                                             │
│  - /api/sequence                                             │
│  - /api/similarity                                           │
│  - /api/models                                               │
└───────────────────────┬──────────────────────────────────────┘
                        │
      ┌─────────────────┼─────────────────┬──────────────────┐
      │                 │                 │                  │
┌─────▼─────┐   ┌───────▼───────┐   ┌────▼────┐   ┌─────────▼─────────┐
│ Data Layer │   │ Compute Layer │   │ Cache   │   │ Background Jobs   │
│ PostgreSQL │   │ pandas / SQL  │   │ Redis   │   │ Celery / RQ       │
│ parquet    │   │ feature logic │   │         │   │ model training    │
└────────────┘   └───────────────┘   └─────────┘   └───────────────────┘
```

## 2. Recommended Folder Structure

```text
project_transfer/
├─ frontend/
│  ├─ app.vue
│  ├─ pages/
│  │  ├─ starter-stuff.vue
│  │  ├─ starter-discipline.vue
│  │  └─ pitcher-personal.vue
│  ├─ components/
│  │  ├─ filters/
│  │  ├─ charts/
│  │  ├─ tables/
│  │  └─ video/
│  ├─ composables/
│  ├─ stores/
│  ├─ types/
│  └─ utils/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  │  ├─ routes/
│  │  │  └─ schemas/
│  │  ├─ services/
│  │  │  ├─ stuff_service.py
│  │  │  ├─ discipline_service.py
│  │  │  ├─ personal_service.py
│  │  │  ├─ sequence_service.py
│  │  │  └─ similarity_service.py
│  │  ├─ repositories/
│  │  ├─ models/
│  │  ├─ core/
│  │  └─ utils/
│  ├─ jobs/
│  └─ tests/
├─ data/
│  ├─ raw/
│  ├─ processed/
│  └─ exports/
├─ docs/
└─ ARCHITECTURE.md
```

## 3. Frontend / Backend Separation

### Frontend responsibilities
- Render pages and charts.
- Manage filter state and URL query state.
- Request API data.
- Handle click / hover / drilldown interactions.
- Display tables, cards, and videos.

### Backend responsibilities
- Read database and prepared files.
- Run sequence logic and pitch grouping logic.
- Compute stuff / discipline / similarity metrics.
- Serve model outputs and pitcher-level summaries.
- Cache expensive computations.

## 4. Suggested API Design

### Pitcher Personal
- `GET /api/personal/summary`
- `GET /api/personal/stuff`
- `GET /api/personal/discipline`
- `GET /api/personal/sequence`
- `GET /api/personal/videos`

### Starter Stuff / Discipline
- `GET /api/stuff/leaderboard`
- `GET /api/stuff/pitch-shapes`
- `GET /api/discipline/leaderboard`
- `GET /api/discipline/swing-map`

### Similarity / Models
- `GET /api/similarity/search`
- `POST /api/similarity/manual-shape`
- `GET /api/models/movement`
- `GET /api/models/spin-breakdown`

## 5. Data Flow Example

```text
User selects pitcher + year + pitch filters
          ↓
Frontend store updates local state
          ↓
Frontend calls /api/personal/sequence?...filters
          ↓
Backend service builds filtered dataframe / SQL query
          ↓
Backend returns summary + chart data + table rows
          ↓
Frontend renders sequence chart and detail tables
```

## 6. Agent Architecture

```text
                         ┌────────────────────┐
                         │   Orchestrator     │
                         │  Main coding lead  │
                         └─────────┬──────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────▼────────┐       ┌─────────▼────────┐       ┌─────────▼────────┐
│ Frontend Agent │       │ Backend Agent    │       │ Model/Data Agent │
│ Vue / Nuxt UI  │       │ FastAPI / SQL    │       │ metrics / ML     │
└───────┬────────┘       └─────────┬────────┘       └─────────┬────────┘
        │                          │                          │
        └──────────────┬───────────┴──────────────┬───────────┘
                       │                          │
               ┌───────▼────────┐        ┌────────▼────────┐
               │ QA / Debug     │        │ Product / PM    │
               │ tests / traces │        │ scope / specs   │
               └────────────────┘        └─────────────────┘
```

## 7. Recommended Skill Binding

### Orchestrator
- `karpathy-guidelines`
- Use for keeping changes small, testable, and not overbuilt.

### Frontend Agent
- `karpathy-guidelines`
- `nextlevelbuilder/ui-ux-pro-max-skill`
- Use for component breakdown, layout polish, chart interaction.

### Backend Agent
- `karpathy-guidelines`
- Use for API shape, service decomposition, SQL/dataflow clarity.

### Model / Data Agent
- `karpathy-guidelines`
- Use for feature selection, training workflow, error analysis.

### QA / Debug Agent
- `karpathy-guidelines`
- `addyosmani/agent-skills/debugging-and-error-recovery`
- Use for traceback isolation, regression testing, recovery flow.

## 8. Build Strategy

### Phase 1: Extract backend first
- Move existing Streamlit calculation logic into Python services.
- Keep current outputs, just change where logic lives.

### Phase 2: Create API contracts
- Define stable response schemas for stuff, discipline, personal, sequence.

### Phase 3: Rebuild UI in Nuxt
- Recreate page shells and filters.
- Hook up summary cards, charts, and tables.

### Phase 4: Add cache and jobs
- Cache expensive queries.
- Move heavy model training to background jobs.

## 9. Practical Recommendation for Your Current Baseball Project

If you are converting the current Streamlit project:

- Keep `Python` for all baseball logic, modeling, and data preparation.
- Use `FastAPI` as the backend API layer.
- Use `Nuxt 3 + Vue 3 + TypeScript` for the website UI.
- Start by migrating:
  1. `Pitcher Personal`
  2. `Starter Stuff`
  3. `Starter Discipline`
- Leave advanced modeling pages for a second wave after the core pages are stable.

## 10. MVP Version

If you want the leanest serious setup:

- Frontend: `Nuxt 3`
- Backend: `FastAPI`
- Database: `PostgreSQL`
- Cache: `Redis`
- Charts: `ECharts`
- Table: `AG Grid`
- Auth: add later only if needed

