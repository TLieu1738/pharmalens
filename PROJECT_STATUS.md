# PharmaLens — Project Status

_Last updated: 2026-11-23. Interview demo: Tuesday 2026-11-24._

> **Branch `phase-1`** holds the Phase 1 upgrade (protocol approval, durable jobs, paged retrieval, audit trail, richer reports). `main` is the deployed version. See the Phase 1 section below; it needs migration `002` before it can run against Supabase.

## Verified working
| Area | How it was verified |
| --- | --- |
| Five live source integrations (PubMed, Europe PMC, ClinicalTrials.gov, ChEMBL, Open Targets) | `python -m scripts.smoke_sources` against the live APIs — all returned records |
| Parsers, dedup, quality flags, retries/backoff | Unit tests on fixtures recorded from real API responses |
| Full LangGraph workflow (planner → parallel retrieval → compounds → validation → synthesis) | Integration test with mocked sources + mocked LLM, incl. source outages, planner/synthesis failure, total outage |
| Citation grounding (fabricated IDs and uncited findings removed) | `tests/test_workflow.py` |
| API: create, poll, evidence, ownership (404 for others), auth errors, anon rate limit, 503 without LLM key | `tests/test_api_research.py` |
| Supabase evidence row mapping round-trip | `tests/test_supabase_mapping.py` |
| **Supabase persistence (live project)** | 2026-11-22: migration applied; a live run wrote 1 session, 71 evidence rows, 1 report, 7 agent executions; session reloads after backend restart; publishable key sees no rows (RLS). Supports new `sb_secret_`/`sb_publishable_` keys and legacy JWT keys. |
| Backend lint/format | `ruff check .` and `ruff format` |
| Frontend type-check, build, lint | `npm run build`, `npm run lint` |
| Running servers: health, 503 without key, 422 validation, SPA deep links | curl against local uvicorn + vite |
| **Live end-to-end run with the real LLM** on the demo Alzheimer's question | 2026-11-22 via the API: all 7 agents completed in ~60 s (synthesis ~45 s); 72 records from 5 sources (30 papers, 20 trials, 15 targets, 7 compounds); 44 report statements, 0 removed as unsupported, 0 invalid citations |

| **Deployed stack (live)** | 2026-11-23: frontend https://pharmalens-ten.vercel.app + API https://pharmalens-api-1e8g.onrender.com. Scripted test with two temporary Supabase users (deleted afterwards): research run via the deployed API completed in 58 s, all 5 sources ok, 45 statements / 61 refs / 0 unsupported; user B gets 404 on A's session and sees 0 rows via RLS; CORS allows only the Vercel origin; `/docs` hidden in production; no secrets in the JS bundle. |

| **Frontend redesign (2026-11-23)** | Sidebar workspace layout: Overview, Research Workspace, Evidence Library, Drug Intelligence, Clinical Trials, Saved Research. Rendered in headless Chrome against the local stack with a temporary user (deleted afterwards) after a real research run: all pages populated with real data, no console errors, mobile layout checked. Market Access & Costs deliberately not built (no real pricing source). |

**Test suite:** 81 passed on `phase-1` (61 on `main`) (`cd backend && .venv/bin/pytest`).

## Implemented but NOT yet verified
- Supabase Auth sign-in UI and backend token verification against a real project.
- Frontend results/workspace screens with real data (built against the typed API; not yet exercised with a live run).
- Forgot/reset password pages (`/forgot-password`, `/reset-password`) — built, not yet tested with a real reset email.

## Next steps (priority order)
1. ~~Frontend with real data~~ done.
2. ~~Supabase sign-in + saved sessions~~ done.
3. ~~Deploy~~ done. Remaining: test password reset on the live site; keep backend awake before the demo (UptimeRobot or open early).
4. Run the demo question; keep one verified completed session as the dated backup.
5. Interview prep doc (overview, architecture diagram, challenges, limitations, demo script).

## Fixes from the first live run (2026-11-22)
- Trial search now includes the planner's named compounds (was class phrases only → 4 trials; now 20 of 80 matches).
- Trial intervention names keep code names intact (`AV-1980R` was being cut to `AV-`) and arm labels like "lecanemab treatment group" are no longer looked up separately.

## Sign-in flow (2026-11-22)
- Full-page `/login` and `/signup` replace the old modal; every app page requires sign-in (`RequireAuth`), returning the user to the page they asked for.
- Dashboard and Saved research list the signed-in account's sessions.
- Local `.env` uses `DEMO_MODE=false`: the API returns 401 to signed-out research requests (verified with curl).
- Verified 2026-11-23: account created in the browser, research run completed and saved with the user as owner, listed under Saved research.

## Phase 1 (branch `phase-1`)

| Feature | Verified by |
| --- | --- |
| Protocol drafted → edited → approved → executed; validation (limits, sources, dates); lock after approval; owner-only; cancel; re-run | `tests/test_protocol.py` (6 tests) |
| Durable jobs: exclusive claims, lease renewal, crash recovery, bounded retries, cancellation not overwritten | `tests/test_jobs.py` (6 tests) — found and fixed a bug where a progress update could undo a cancellation |
| Paging (PubMed retstart, Europe PMC cursor, CT.gov page token), date / preprint filters, multi-query literature, coverage counts and truncation warnings | `tests/test_retrieval_paging.py` (6 tests) |
| Grounding audit (removed statements with reasons, invalid IDs) and deduplication merge log | `tests/test_retrieval_paging.py` (2 tests) |
| Frontend: protocol editor, workflow stepper, cancel / re-run, methodology + data-source sections, audit view, PDF print page | TypeScript, lint and production build pass; **live browser check pending migration 002** |

Migration `supabase/migrations/002_protocol_jobs_audit.sql` (additive; safe for the deployed `main` code).

## New API
- `GET /api/library`: the signed-in user's evidence across all sessions, deduplicated by record ID, each with the sessions it came from (`tests/test_api_research.py::test_library_merges_users_evidence_and_is_private`).

## Known limitations
- Background execution is an in-process asyncio task: not durable across restarts (interrupted sessions are marked failed on startup).
- Without Supabase, storage is in-memory (lost on restart).
- Retrieval takes top-ranked results per source (≈15 papers/source, 20 trials, ≤8 compounds, 15 targets) — not a systematic review.
- Contradiction detection relies on the synthesis agent reading abstracts; it is not a formal meta-analysis.
- PubChem and OpenAlex not integrated (ChEMBL/PubMed/Europe PMC cover the needs) — future work.
- Library aggregates up to 50 most recent sessions per request (one evidence query per session); fine at demo scale, would need a single SQL query for heavy users.
- Anonymous rate limiting is per-process memory and per IP.

## Environment notes (this machine)
- Node 22 at `~/.local/node/bin`, uv + Python 3.12 at `~/.local/bin`. Add both to PATH:
  `export PATH="$HOME/.local/bin:$HOME/.local/node/bin:$PATH"`
