# PharmaLens — Project Status

_Last updated: 2026-11-22 (evening). Interview demo: Tuesday 2026-11-24._

## Verified working
| Area | How it was verified |
| --- | --- |
| Five live source integrations (PubMed, Europe PMC, ClinicalTrials.gov, ChEMBL, Open Targets) | `python -m scripts.smoke_sources` against the live APIs — all returned records |
| Parsers, dedup, quality flags, retries/backoff | Unit tests on fixtures recorded from real API responses |
| Full LangGraph workflow (planner → parallel retrieval → compounds → validation → synthesis) | Integration test with mocked sources + mocked Claude, incl. source outages, planner/synthesis failure, total outage |
| Citation grounding (fabricated IDs and uncited findings removed) | `tests/test_workflow.py` |
| API: create, poll, evidence, ownership (404 for others), auth errors, anon rate limit, 503 without Claude key | `tests/test_api_research.py` |
| Supabase evidence row mapping round-trip | `tests/test_supabase_mapping.py` |
| Backend lint/format | `ruff check .` and `ruff format` |
| Frontend type-check, build, lint | `npm run build`, `npm run lint` |
| Running servers: health, 503 without key, 422 validation, SPA deep links | curl against local uvicorn + vite |
| **Live end-to-end run with real Claude (`claude-opus-5-5`)** on the demo Alzheimer's question | 2026-11-22 via the API: all 7 agents completed in ~60 s (synthesis ~45 s); 72 records from 5 sources (30 papers, 20 trials, 15 targets, 7 compounds); 44 report statements, 0 removed as unsupported, 0 invalid citations |

**Test suite:** 59 passed (`cd backend && .venv/bin/pytest`).

## Implemented but NOT yet verified
- Supabase repository + migration + RLS (`app/services/supabase_repository.py`, `supabase/migrations/001_initial_schema.sql`). **Needs Supabase project.**
- Supabase Auth sign-in UI and backend token verification against a real project.
- Frontend results/workspace screens with real data (built against the typed API; not yet exercised with a live run).
- Deployment (Render blueprint `render.yaml`, `frontend/vercel.json`) — not deployed.

## Next steps (priority order)
1. Run the demo question through the frontend (`npm run dev`) and check the workspace/results screens with real data.
2. Create Supabase project → run migration → set keys → verify persistence, sign-in, saved sessions, RLS.
3. Push to GitHub → deploy backend on Render, frontend on Vercel → set CORS/env → live test in a fresh browser.
4. Run the demo question; keep one verified completed session as the dated backup.
5. Interview prep doc (overview, architecture diagram, challenges, limitations, demo script).

## Fixes from the first live run (2026-11-22)
- Trial search now includes the planner's named compounds (was class phrases only → 4 trials; now 20 of 80 matches).
- Trial intervention names keep code names intact (`AV-1980R` was being cut to `AV-`) and arm labels like "lecanemab treatment group" are no longer looked up separately.

## Known limitations
- Background execution is an in-process asyncio task: not durable across restarts (interrupted sessions are marked failed on startup).
- Without Supabase, storage is in-memory (lost on restart).
- Retrieval takes top-ranked results per source (≈15 papers/source, 20 trials, ≤8 compounds, 15 targets) — not a systematic review.
- Contradiction detection relies on the synthesis agent reading abstracts; it is not a formal meta-analysis.
- PubChem and OpenAlex not integrated (ChEMBL/PubMed/Europe PMC cover the needs) — future work.
- Anonymous rate limiting is per-process memory and per IP.

## Environment notes (this machine)
- Node 22 at `~/.local/node/bin`, uv + Python 3.12 at `~/.local/bin`. Add both to PATH:
  `export PATH="$HOME/.local/bin:$HOME/.local/node/bin:$PATH"`
