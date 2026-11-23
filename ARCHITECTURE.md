# PharmaLens architecture

PharmaLens turns a biomedical research question into a cited evidence briefing. The user approves a research
protocol, deterministic agents retrieve records from five public databases, a rule-based step validates them,
and an LLM writes a report whose every finding is checked in code against the retrieved records.

## System overview

```text
Browser (React + TypeScript on Vercel)                      Supabase Auth (sign-in only, public key)
   │  JSON + user token                                                     ▲
   ▼                                                                        │
FastAPI (Render) ── verifies the token with Supabase Auth on every request ─┘
   │  API routes only enqueue: create session (pending) · approve protocol (queued) · cancel
   ▼
Job runner (inside the API process, or `python -m app.worker`)
   │  claims a due session with a lease, renews it while working, re-queues it if the lease lapses
   ▼
LangGraph — planning graph:   planner (LLM) → protocol saved → status awaiting_approval
            execution graph:  ┬─> literature (PubMed + Europe PMC, every protocol query) ─┐
                              ├─> clinical (ClinicalTrials.gov) ──> compounds (ChEMBL) ────┼─> validation → synthesis (LLM)
                              └─> targets (Open Targets) ──────────────────────────────────┘    (rules)      + grounding check
   │  every agent writes its status, timings and per-query coverage as it runs
   ▼
Supabase Postgres: research_sessions (also the job record) · agent_executions · evidence_records · research_reports
   — RLS on; an in-memory repository is used when Supabase is not configured (local dev and tests)
```

## Research lifecycle

| Status | Meaning | Who moves it on |
| --- | --- | --- |
| `pending` | Question received, waiting for a worker to draft the protocol | Worker claims it |
| `planning` | Research Planner is drafting the protocol | Worker |
| `awaiting_approval` | Protocol drafted; nothing has been searched | **User** edits and approves (or discards) |
| `queued` | Approved, waiting for a worker | Worker claims it |
| `researching` → `validating` → `synthesising` | Execution graph running | Worker |
| `completed` / `failed` / `cancelled` | Terminal | — |

A job re-queued after an interruption returns to `pending` or `queued` with `attempts` > 1; the UI shows it as
"Retrying". Progress updates never overwrite a terminal state, so a cancellation cannot be undone by a running agent.

## Agents

| Agent | Kind | Input → output |
| --- | --- | --- |
| Research Planner | LLM (structured output, effort `low`) | question → protocol: objective, key questions, disease, targets, HGNC symbols, compounds, drug classes, literature queries, trial condition, sources, inclusion/exclusion criteria, optional date range, intended outputs, known limitations |
| Literature | Deterministic | each protocol query × PubMed and Europe PMC, paged, with date and preprint filters |
| Clinical Intelligence | Deterministic | ClinicalTrials.gov v2 studies (status, phase, design, interventions, results posted, reason stopped), paged, optional start-date filter |
| Biological Target | Deterministic | Open Targets disease→target associations (rank, datatype scores) |
| Compound | Deterministic | protocol compounds **plus** drug interventions from retrieved trials → ChEMBL (exact name/synonym matches only) + mechanisms |
| Evidence Validation | Deterministic | union-find deduplication across DOI/PMID/PMCID/NCT/ChEMBL/Ensembl IDs, quality flags, evidence profile |
| Research Synthesis | LLM (structured output, effort `medium`) + grounding | validated evidence + approved protocol → report; code then removes invalid citations and uncited findings and builds the references from real records |

### Why retrieval is deterministic and the LLM only plans and writes
- Source data must be exact and reproducible; an LLM calling APIs or recalling results can fabricate identifiers.
- Typed integration modules give timeouts, bounded retries, caching, polite paging and testable parsers.
- The LLM adds value where language matters: turning a broad question into a protocol, and writing a structured
  narrative over the evidence. Both outputs are schema-validated.

### Why LangGraph, and why two graphs
- The execution graph is a real DAG: parallel fan-out, one dependency (compounds waits for trials, to look up drugs
  named in real registrations) and a fan-in at validation. Typed state with reducers handles concurrent writes.
- Splitting planning from execution puts a human approval step between them without holding a request or a worker
  open: the protocol is persisted, and execution starts from it whenever the user approves.
- Conditional edges stop cleanly when there is no plan or no evidence, or when the run is cancelled.

## Durable background jobs

Render's free plan has no background-worker service, and the project avoids extra infrastructure, so the job queue
lives in the existing Postgres table rather than Redis/Celery.

- **Enqueue:** API routes only write a status (`pending` or `queued`) and wake the runner.
- **Claim:** a worker selects due sessions and claims one with a conditional update guarded on `status` and
  `attempts`; only one worker can win. It records `worker_id` and `lease_expires_at`.
- **Heartbeat:** while running, the worker renews the lease every third of its length (default lease 90 s).
- **Recovery:** every poll, sessions in a running state with a lapsed lease are re-queued (to `pending` if not yet
  approved, else `queued`), up to `JOB_MAX_ATTEMPTS` (default 2); then they fail with a clear message.
- **Retry hygiene:** before an execution attempt, outputs of any earlier attempt are cleared, so a retry starts clean.
- **Cancel:** the API marks the session `cancelled`; each agent checks before it starts and the run stops.
- **Scaling out:** set `RUN_WORKER_IN_API=false` on the web service and run `python -m app.worker` processes.
- **Reconnecting:** the browser only polls the session record, so closing the tab or restarting the server does not
  lose a run; reopening the page shows its real state.

## Retrieval coverage

- Per-source caps come from the approved protocol (`max_results_per_source`, 5–100, default 20), split evenly
  across the protocol's literature queries.
- PubMed pages with `retstart`, Europe PMC with `cursorMark`, ClinicalTrials.gov with `pageToken` (50 per page).
- Each query records the source's own count of matching records, the cap, records returned and pages read. When
  the cap is below the matching total, a warning says so in the run ("took the top 20 of 3,412…").
- Date ranges apply to publication year and trial start date; preprints can be excluded at the source.

## Scientific-integrity controls

1. The LLM never retrieves data; every record originates from a source API with its URL and retrieval timestamp.
2. The synthesis prompt contains only retrieved records and the approved protocol; output is schema-validated.
3. Retrieved text is treated as data: the prompt instructs the model never to follow instructions found inside
   evidence (prompt-injection defence), and nothing from the evidence can change which tools or sources run.
4. Grounding: citations that do not match a retrieved `record_id` are dropped; findings left without a valid
   citation are removed. Each removal is stored with its section and reason and shown in the audit view.
5. Statements are typed `finding` / `hypothesis` / `gap`; hypotheses and open questions are labelled in the UI.
6. Validation flags preprints, retractions, stopped trials, completed trials without posted results, missing
   abstracts/dates/authors and withdrawn compounds. No numeric confidence scores are invented.
7. Report sections without supported statements are omitted rather than filled.

## Report structure

AI-written (each finding cited): executive summary, key scientific findings, biological target analysis, compound
and drug development analysis, clinical trial analysis, evidence quality (strengths and limitations), conflicting
or inconclusive evidence, research gaps, conclusions.

Generated by code from the session record: research question, approved protocol, methodology (what ran, counts,
deduplication, grounding results), data-source coverage table, references (from real records only), disclaimer.

Exports: Markdown (download) and PDF (print-optimised page; the browser's "Save as PDF" keeps links clickable).

## Reproducibility and audit

Stored per run: question, approved protocol and approval time, every source query with matching/retrieved counts
and pages, failures with reasons, agent timings and messages, deduplication merges (kept ID ← merged IDs),
validation profile and flags, grounding removals with reasons, invalid citation IDs, records given to the model,
model ID and effort settings, attempts, execution start/finish times and report generation time. No API keys,
prompts or internal errors are exposed.

## Reliability

- Shared `SourceHttpClient`: per-host concurrency limits, exponential backoff on 429/5xx/network errors (bounded),
  Retry-After support, 15-minute response cache.
- A failing source marks its agent `partial`/`failed`; the run continues with partial evidence and says so.
- Planner or synthesis failure → session `failed` with a user-safe message; internals are logged server-side only.
- LLM calls use server-side refusal fallback and handle `refusal` / `max_tokens` stop reasons explicitly.

## Security

- The LLM key and Supabase secret key are server-side only; the frontend has only the Supabase URL and publishable key.
- The backend verifies bearer tokens with Supabase Auth and never trusts a client-supplied user ID.
- Owned sessions are returned and changed only by their owner (404 otherwise, so existence is not revealed).
  RLS lets signed-in users SELECT only their own rows; there are no client write policies.
- With `DEMO_MODE=false` (production) signed-out users cannot run research.
- CORS is restricted to configured origins; inputs are validated with Pydantic (question length, protocol limits,
  date order, at least one source).

## API

See [docs/api-design.md](docs/api-design.md).
