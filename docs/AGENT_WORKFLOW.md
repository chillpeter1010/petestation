# Agent Workflow

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
