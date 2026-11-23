# PharmaLens — Project Status

_Last updated: 2026-11-23. Interview demo: Tuesday 2026-11-24._

> **Branches.** `main` is deployed. `phase-1` adds protocol approval, durable jobs, paged retrieval, the audit trail and evidence integrity. `phase-2` (built on `phase-1`) adds the knowledge graph, trial comparison, drug pipeline, PubChem and OpenAlex. Both need migration `002` applied before they can run against Supabase; Phase 2 needs no further migration.

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

**Test suite:** 104 passed on `phase-1` (61 on `main`) (`cd backend && .venv/bin/pytest`).

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

Migration `supabase/migrations/002_protocol_jobs_audit.sql` (additive; safe for the deployed `main` code). **Not yet applied** to the Supabase project as of this update.

## Evidence integrity (branch `phase-1`)

| Requirement | Implementation | Verified by |
| --- | --- | --- |
| Provenance on every record | `Provenance` (API URL, payload SHA-256, parser version) set only in parsers; stored in Supabase metadata | `test_every_parsed_record_carries_provenance`, `test_llm_output_cannot_create_evidence_records` |
| Reject malformed / untraceable records | `services/record_checks.py` in the validation agent | `test_validation_rejects_malformed_and_untraceable_records`, `test_malformed_source_items_are_skipped_not_guessed` |
| Structured claims | `ClaimDraft` → `Statement` with type, citations, limitations, status, per-citation verdicts | all `test_evidence_integrity.py` |
| Citation existence + session ownership | `agents/verification.py` pass 1 (validated records ∩ persisted for the session) | fabricated ID, invalid citation, cross-session tests |
| Semantic support, separate from existence | Separate LLM call; irrelevant citations dropped; unsupported/contradicted removed | irrelevant, contradicted, partially supported, interpretation-relabel, outage tests |
| Numbers, prices, efficacy-from-registry, approval | Deterministic rules | invented count, missing outcomes, missing prices, approval vs max phase, years-from-dates tests |
| Publication cannot bypass validation | New LangGraph node + `ensure_publishable` in both repositories | `test_repositories_refuse_unverified_reports`, `test_workflow_cannot_publish_without_verification_node` |

**Live run (real model and sources, in-memory storage, 2026-11-23):** protocol drafted in 14 s; after approval the run took 149 s (synthesis 69 s, verification 30 s, ChEMBL 40 s). 85 records; 49 claims drafted, 47 published (28 supported, 12 partially supported, 7 hypotheses/gaps), 2 removed: one efficacy claim resting only on a trial registration (correct) and one false positive where a year in a source date was not matched. That bug is fixed and covered by `test_years_from_source_dates_are_accepted`.

**Known limitations:** the support check is itself an LLM judgement (strictly instructed, separate call, auditable) and can err; number checks confirm a number appears in a cited source, not that it is used in the same sense; runs take about 2.5 minutes (142 s at the default of 50 per source), so lower the per-source limit for live demos if time matters.

## Phase 2 (branch `phase-2`)

| Feature | Verified by |
| --- | --- |
| OpenAlex parsing (abstract rebuilt from inverted index, DOI/PMID/PMCID, institutions, topics, preprint and retraction flags), filters, paging, API key never stored, refusal = source failure, merge with PubMed by DOI | `tests/test_phase2_sources.py` (fixtures recorded from the live API) |
| PubChem by InChIKey only (biologics skipped, not-found skipped, outage fails, different structure ignored) | `tests/test_phase2_sources.py` |
| ChEMBL mechanism targets with official gene symbols only | `tests/test_phase2_sources.py` |
| Knowledge graph: exactly the source-stated edges, merges only on shared identifiers, every edge traceable, no invented nodes; endpoint private (401 / 404 / empty for other users) | `tests/test_knowledge_graph.py` |
| CORS now allows `PUT` (protocol "Save draft" was blocked in browsers on `phase-1`) | Live preflight returned 200 with `PUT` |
| Frontend: Knowledge Graph, Drug Pipeline, trial comparison/timeline/distributions, PubChem and target panels on Drug Intelligence | TypeScript, lint, production build; headless Chrome against the live local API with a temporary user (deleted): no console errors |

**Test suite:** 124 passed on `phase-2`.

**More data per run (2026-11-23):** default cap raised from 20 to 50 per source; the synthesis prompt holds up to 150 records chosen round-robin by category (`select_for_prompt`, tested) so literature cannot crowd out trials, targets or compounds; overview source cards show library counts plus the latest run's taken-vs-matching counts. Live run against Supabase with all seven sources up: 142 s, 243 records (PubMed 45, Europe PMC 45, OpenAlex 46, ClinicalTrials.gov 50, Open Targets 50, ChEMBL 6, PubChem 1), 49 claims published, graph 205 entities / 277 links.

**Live compound path (2026-11-23, after ChEMBL recovered):** compound and target agents against live ChEMBL,
PubChem and Open Targets for donepezil, lecanemab and memantine in Alzheimer disease: 3 exact ChEMBL matches; PubChem
CIDs 3152 (donepezil) and 4054 (memantine) matched by InChIKey, lecanemab (antibody) skipped; 9 compound → target
edges; 7 targets joined across Open Targets and ChEMBL by gene symbol. This exposed a bug present since the first
version (including `main`): mechanisms were requested by the drug's own ChEMBL ID, but ChEMBL files many under the salt
form, so donepezil and memantine had none. Fixed by querying `parent_molecule_chembl_id`; covered by
`test_chembl_mechanisms_are_looked_up_by_parent_molecule`.

**Live run (2026-11-23, real model and sources, in-memory storage, cap 10 per source):** protocol in 15 s with all seven sources selected; save draft and approve both 200; run completed in 185 s. OpenAlex returned 12 records, PubMed 12, ClinicalTrials.gov 10, Open Targets 10. **Europe PMC and ChEMBL were both returning HTTP 500/503 from EBI during this run**, so the run completed as partial (as designed) and no compounds, PubChem records or compound edges were produced. Graph: 41 entities, 37 edges, every edge traceable to a retrieved record; another user saw nothing (404 / empty). Claims: 20 supported, 19 partially supported, 7 hypotheses/gaps, 2 removed.

## New API
- `GET /api/graph?session_id=` — knowledge graph over the user's evidence (all sessions, or one).
- `GET /api/library`: the signed-in user's evidence across all sessions, deduplicated by record ID, each with the sessions it came from (`tests/test_api_research.py::test_library_merges_users_evidence_and_is_private`).

## Known limitations
- On `main` (deployed), background execution is an in-process task and interrupted sessions are marked failed; `phase-1`/`phase-2` use the lease-based job queue instead.
- Without Supabase, storage is in-memory (lost on restart).
- Retrieval takes the top-ranked results per source (protocol cap, default 50) — not a systematic review.
- Contradiction detection relies on the synthesis agent reading abstracts; it is not a formal meta-analysis.
- OpenAlex without an API key shares a small daily budget per IP address; set `OPENALEX_API_KEY` (free) for reliable use.
- Graph compound ↔ trial links need an exact name or synonym match; drugs registered under other names are not linked. Paper ↔ target links are not drawn.
- Library aggregates up to 50 most recent sessions per request (one evidence query per session); fine at demo scale, would need a single SQL query for heavy users.
- Anonymous rate limiting is per-process memory and per IP.

## Environment notes (this machine)
- Node 22 at `~/.local/node/bin`, uv + Python 3.12 at `~/.local/bin`. Add both to PATH:
  `export PATH="$HOME/.local/bin:$HOME/.local/node/bin:$PATH"`
