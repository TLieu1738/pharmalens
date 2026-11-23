# PharmaLens

Agentic AI research intelligence over **public** biomedical evidence. A user submits a research question; specialist
LLM-powered agents plan the investigation, retrieve records from public scientific and regulatory sources
(PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov, ChEMBL, PubChem, Open Targets), validate and deduplicate the
evidence, and synthesise a structured briefing in which every claim cites a retrieved record. Workspace views add a
knowledge graph (links drawn only where a source states them), a drug pipeline by development phase and
side-by-side trial comparison.

> PharmaLens is a research-support tool. Its outputs are informational, may be incomplete, and must be verified by
> qualified researchers. It is not a medical device and does not give treatment or dosing advice.

**Status:** core workflow implemented and tested with mocked sources; live source integrations verified. See
[PROJECT_STATUS.md](PROJECT_STATUS.md) for exactly what has and has not been verified, and
[docs/architecture.md](docs/architecture.md) / [docs/api-design.md](docs/api-design.md) for design details.

## Repository layout

```text
frontend/   React + TypeScript + Vite + Tailwind CSS
backend/    FastAPI + Pydantic v2 + LangGraph + Anthropic SDK
supabase/   SQL migrations (schema + RLS)
docs/       API design notes (architecture: ARCHITECTURE.md, plans: ROADMAP.md)
```

## How it works (short)

1. **Research Planner** (LLM) drafts a research protocol from the question: objective, key questions, search
   terms, literature queries, sources, inclusion/exclusion criteria, date range, record limits and known limitations.
2. **You review and approve it.** Every field is editable; nothing is searched until you approve.
3. **Literature**, **Clinical** and **Target** agents query PubMed + Europe PMC + OpenAlex (every protocol query,
   paged), ClinicalTrials.gov and Open Targets in parallel; the **Compound** agent then looks up planned compounds and
   trial interventions in ChEMBL (with mechanism target gene symbols) and matches small molecules to PubChem by
   InChIKey. Each query records how many records matched at the source versus were taken.
4. **Evidence Validation** deduplicates by DOI/PMID/PMCID/NCT/ChEMBL/Ensembl and flags preprints, retractions,
   stopped trials and missing metadata.
5. **Research Synthesis** (LLM) writes the report against the approved protocol; code then removes any citation
   that does not match a retrieved record and any uncited "finding", and logs each removal for the audit view.

All retrieval is deterministic Python; the LLM only plans and writes. Research runs as a durable job: a worker
claims it from the database with a renewable lease, so a server restart re-queues it instead of losing it.
See [ARCHITECTURE.md](ARCHITECTURE.md) and [ROADMAP.md](ROADMAP.md).

## Prerequisites

- Python **3.12+**
- Node.js **20+** (developed on 22 LTS)

## Running locally

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then fill in keys (see below)
uvicorn app.main:app --reload --port 8000
```

- API root: http://localhost:8000/
- Health: http://localhost:8000/api/health
- OpenAPI docs (non-production only): http://localhost:8000/docs

Tests and lint (no network or API keys needed — sources and the LLM are mocked):

```bash
cd backend && source .venv/bin/activate
pytest
ruff check . && ruff format --check .
```

Live smoke test of the original five public sources (no keys needed):

```bash
python -m scripts.smoke_sources "alzheimer amyloid tau"
```

Without Supabase configured, sessions are stored **in memory** and lost on restart (`/api/health` shows `storage`).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev                   # http://localhost:5173
npm run build && npm run lint
```

## Environment variables

| Variable | Where | Required | Notes |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | backend | yes (Phase 3+) | Server-side only. |
| `ANTHROPIC_MODEL` | backend | yes | Model ID from your Anthropic account. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | backend | yes (Phase 4+) | Service-role key is **never** sent to the browser. |
| `SUPABASE_ANON_KEY` | backend | Phase 4+ | Used for token verification. |
| `FRONTEND_URL` | backend | yes | Exact CORS origin; wildcards are rejected. |
| `NCBI_API_KEY` | backend | no | Raises PubMed rate limit; works without it. |
| `OPENALEX_API_KEY` | backend | recommended | Free key from openalex.org/settings/api. Without it OpenAlex requests share a small daily budget per IP and may be refused (reported as a source failure). |
| `DEMO_MODE` | backend | no | `true` lets signed-out users run research (unlisted sessions, rate limited per IP). |
| `ADDITIONAL_CORS_ORIGINS` | backend | no | Comma-separated extra origins (e.g. Vercel preview URL). |
| `RUN_WORKER_IN_API` | backend | no | Default `true`: the API process runs research jobs. Set `false` when running `python -m app.worker` separately. |
| `JOB_LEASE_SECONDS`, `JOB_MAX_ATTEMPTS`, `JOB_POLL_SECONDS` | backend | no | Job queue tuning (defaults 90, 2, 2.0). |
| `VITE_API_BASE_URL` | frontend | yes | Backend URL. |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | frontend | Phase 4+ | Public values only. |

## Supabase setup

1. Create a project, then run each file in `supabase/migrations/` in order (`001_…`, `002_…`) in the SQL editor.
2. Authentication → Providers → Email: enabled. For a quick demo you may disable "Confirm email".
3. Copy URL, anon key and service-role key into `backend/.env`; URL + anon key into `frontend/.env.local`.

## Deployment

- **Backend (Render):** `render.yaml` blueprint (root `backend/`). Set secrets in the dashboard; set `FRONTEND_URL` to the Vercel URL.
- **Frontend (Vercel):** root directory `frontend`, build `npm run build`, output `dist`, env `VITE_API_BASE_URL`,
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. `vercel.json` provides SPA rewrites.
- Render's free tier sleeps when idle: open `/api/health` a minute before demoing.
