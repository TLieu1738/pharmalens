# PharmaLens architecture

## System overview

```text
Browser (React/Vite on Vercel)
   │  POST /api/research, poll GET /api/sessions/{id}      Supabase Auth (sign-in only)
   ▼                                                          ▲
FastAPI (Render) ── verifies bearer token with Supabase Auth ─┘
   │  creates session → asyncio background task
   ▼
LangGraph workflow ───────────────────────────────────────────────────────────────
   planner (Claude) ─┬─> literature  (PubMed + Europe PMC, parallel) ───────┐
                     ├─> clinical    (ClinicalTrials.gov) ──> compounds ────┼─> validation ─> synthesis (Claude)
                     └─> targets     (Open Targets GraphQL) ────────────────┘       (rules)      + grounding check
   │  each node publishes running/completed/partial/failed + counts to the repository
   ▼
Supabase Postgres (sessions, agent_executions, evidence_records, research_reports; RLS on)
   — falls back to an in-memory repository when Supabase is not configured (dev/tests)
```

## Agents

| Agent | Kind | Input → output |
| --- | --- | --- |
| Research Planner | Claude (structured output, effort `low`) | question → `ResearchPlan` (disease, targets, HGNC symbols, compounds, literature query, trial terms, sources) |
| Literature | Deterministic | plan → PubMed + Europe PMC records (abstracts, DOI/PMID/PMCID, pub types) |
| Clinical Intelligence | Deterministic | plan → ClinicalTrials.gov v2 studies (status, phase, design, interventions) |
| Biological Target | Deterministic | plan → Open Targets disease→target associations (rank, datatype scores) |
| Compound | Deterministic | plan compounds **+ drug/biological interventions from retrieved trials** → ChEMBL molecules (exact name/synonym matches only) + mechanisms |
| Evidence Validation | Deterministic | all records → union-find dedup across DOI/PMID/PMCID/NCT/ChEMBL/Ensembl, quality flags, evidence profile |
| Research Synthesis | Claude (structured output, effort `medium`) + grounding | validated evidence → report; then code removes invalid citations and uncited "findings", and builds references from real records |

### Why retrieval is deterministic and Claude only plans/synthesises
- External data must be exact and reproducible; an LLM calling APIs (or "remembering" results) can fabricate identifiers.
- Typed integration modules give timeouts, bounded retries, caching, rate-limit politeness and testable parsers.
- Claude adds value where language understanding matters: turning a broad question into search parameters, and
  writing a structured narrative over the evidence. Both outputs are schema-validated.

### Why LangGraph
- Explicit, inspectable graph: parallel fan-out, a real dependency (compounds waits for trials), and fan-in at validation.
- Typed shared state with reducers for concurrent writes (agent statuses, warnings, failed sources).
- Conditional edges stop cleanly when the plan or evidence is missing, without crashing the session.

## Scientific-integrity controls
1. Claude never retrieves data; every record originates from a source API with its URL and retrieval timestamp.
2. Synthesis prompt contains only retrieved record IDs; output is validated against a Pydantic schema.
3. Post-generation grounding: citations not matching a retrieved `record_id` are dropped; "finding" statements left with
   no valid citation are removed. Counts are shown in the UI ("Report grounding check").
4. Statements are typed `finding` / `hypothesis` / `gap`; hypotheses and open questions are visually labelled.
5. Validation flags preprints (not peer reviewed), retractions, stopped trials, completed trials without posted results,
   missing abstracts/dates, and withdrawn compounds. No numeric "confidence scores" are invented.
6. Caveats are displayed where they matter (trial status ≠ efficacy; association ≠ causation; ChEMBL max phase is for any indication).

## Reliability
- Shared `SourceHttpClient`: per-host concurrency limits, exponential backoff on 429/5xx/network errors (bounded), Retry-After, 15-min TTL cache.
- A failing source marks its agent `partial`/`failed`; the session continues with partial evidence and the report scope names unavailable sources.
- Planner or synthesis failure → session `failed` with a user-safe message. Internal errors are logged server-side only.
- Claude calls use server-side refusal fallback (`fallbacks: "default"`) and handle `refusal` / `max_tokens` stop reasons explicitly.

## Execution model and its limits
Research runs as an in-process asyncio task in the API service. This is simple and adequate for a demo, but **not durable**:
if the process restarts mid-run, the session is marked `failed` ("Interrupted…") on the next startup. Upgrade path: a job
table/queue polled by a Render Background Worker running the same `run_research` function.

## Security
- Service-role key and Anthropic key are server-side only; the frontend gets only the Supabase URL + anon key.
- Backend verifies bearer tokens via Supabase Auth (`/auth/v1/user`) and never trusts a client-supplied user id.
- Owned sessions are returned only to their owner (404 otherwise). RLS: authenticated users can SELECT only their own rows;
  no client write policies exist. Signed-out demo sessions are unlisted, reachable only by UUID, and rate limited per IP.
- CORS is restricted to configured origins (wildcards are stripped). Global cap on concurrent research runs.
