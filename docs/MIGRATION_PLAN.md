# Streamlit to Website Migration Plan

## Goal

Treat the current Streamlit app as a working prototype, then migrate it into a maintainable product architecture:

- Frontend: Nuxt 3, Vue 3, TypeScript
- Backend: FastAPI, Python
- Data and model logic: keep in Python services
- UI state, charts, filters, and page composition: move to frontend

## Migration Order

### Phase 1: Contract-first backend extraction

Start with these pages:

1. Pitcher Personal
2. Starter Stuff
3. Starter Discipline
4. Pitcher Similarity
5. Pitch Spin Breakdown

For each Streamlit page, extract in this order:

1. Data loaders
2. Filter functions
3. Metric/table builders
4. Chart-ready payload builders
5. Video lookup helpers

Do not migrate Streamlit layout code into backend services. Layout belongs to Nuxt.

### Phase 2: API contracts

Each backend endpoint should return frontend-ready JSON:

- `filters`: available filter options
- `summary`: card-level metrics
- `charts`: chart-ready series or point arrays
- `tables`: rows and column metadata
- `meta`: data freshness, selected player, date range, warnings

### Phase 3: Nuxt rebuild

Rebuild pages around stable API contracts:

- Page components own route/query synchronization
- Stores own shared filters and selected entity state
- Components render cards, filters, charts, tables, and video panels
- No baseball formulas in Vue components

### Phase 4: Performance and jobs

After API correctness is stable:

- Add Redis for expensive query caching
- Add background jobs for model training or long exports
- Add database migrations if PostgreSQL becomes the canonical store

## Streamlit Responsibility Split

| Streamlit responsibility | New location |
| --- | --- |
| `st.selectbox`, `st.slider`, `st.tabs` | Nuxt pages/components |
| `st.session_state` | Pinia store + URL query |
| `@st.cache_data` | FastAPI service cache / Redis |
| pandas filters and aggregations | Backend services |
| DuckDB/PostgreSQL reads | Backend repositories |
| plotly/matplotlib figure construction | Prefer frontend chart payloads; keep backend only for domain calculations |
| video URL lookup | Backend service, frontend video component |

## Definition of Done for One Page

- The old Streamlit page still works during migration.
- Backend service can return the same core metrics/tables as the Streamlit page.
- API response has typed Pydantic schema.
- Nuxt page consumes only API JSON.
- Filters are represented in URL query state.
- At least one backend test covers a calculation or filter edge case.
