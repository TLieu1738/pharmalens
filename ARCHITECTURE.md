# PharmaLens architecture

PharmaLens turns a biomedical research question into a cited evidence briefing. The user approves a research
protocol, deterministic agents retrieve records from seven public databases, a rule-based step validates them,
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
            execution graph:  ┬─> literature (PubMed + Europe PMC + OpenAlex, every query) ┐
                              ├─> clinical (ClinicalTrials.gov) ──> compounds (ChEMBL → PubChem) ┼─> validation → synthesis (LLM)
                              └─> targets (Open Targets) ──────────────────────────────────┘    (rules)
                                                                       → claim verification (rules + LLM support check) → publish
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
| Literature | Deterministic | each protocol query × PubMed, Europe PMC and OpenAlex, paged, with date and preprint filters (OpenAlex adds citation counts, institutions, topics) |
| Clinical Intelligence | Deterministic | ClinicalTrials.gov v2 studies (status, phase, design, interventions, results posted, reason stopped), paged, optional start-date filter |
| Biological Target | Deterministic | Open Targets disease→target associations (rank, datatype scores) |
| Compound | Deterministic | protocol compounds **plus** drug interventions from retrieved trials → ChEMBL (exact name/synonym matches only) + mechanisms + mechanism target gene symbols → PubChem by standard InChIKey (small molecules only) |
| Evidence Validation | Deterministic | union-find deduplication across DOI/PMID/PMCID/NCT/ChEMBL/Ensembl IDs, quality flags, evidence profile |
| Research Synthesis | LLM (structured output, effort `medium`) | validated evidence + approved protocol → *draft* claims (typed, with citations and limitations). Never published directly. |
| Claim Verification | Deterministic rules + separate LLM support check (effort `low`) | draft → publishable report: removes fabricated/foreign citations, unsupported or contradicted factual claims, relabels unsupported interpretations as hypotheses, builds references from real records |

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

- Per-source caps come from the approved protocol (`max_results_per_source`, 5–100, default 50), split evenly
  across the protocol's literature queries.
- PubMed pages with `retstart`, Europe PMC with `cursorMark`, ClinicalTrials.gov with `pageToken` (50 per page).
- Each query records the source's own count of matching records, the cap, records returned and pages read. When
  the cap is below the matching total, a warning says so in the run ("took the top 17 of 33,287…"); the overview shows the latest run's taken-vs-matching count per source.
- Date ranges apply to publication year and trial start date; preprints can be excluded at the source.

## Evidence integrity

Integrity is enforced in code at four points, not by prompts alone.

**1. Provenance (retrieval).** Every `EvidenceRecord` carries a `Provenance` block set only by source parsers:
the exact API request that returns the record, a SHA-256 fingerprint of the raw source item, and the parser
version. LLM output schemas contain only text and record-ID strings, so a model cannot create evidence.

**2. Record validation (Evidence Validation agent).** Before anything is persisted, each record must have a
well-formed identifier for its source (PMID digits, `NCT` + 8 digits, `CHEMBL` + digits, Europe PMC
`SRC:ID`, Open Targets `disease:ENSG…`), a `record_id` matching source + identifier, a URL on that source's own
domain, and provenance pointing at that source's API. Failures are rejected and reported, never repaired.
Deduplication then merges records that share stable identifiers.

**3. Claim verification (new agent, between synthesis and publication).** Claims are typed: `finding`,
`clinical_outcome`, `comparative_analysis` (factual), `interpretation`, `hypothesis`, `gap`. Each carries its
own limitations. Existence and support are checked separately:

| Check | How | Failure |
| --- | --- | --- |
| Citation exists in this run's validated evidence **and** in evidence persisted for this session | Deterministic | Citation dropped; a factual claim left with none is removed ("fabricated or foreign record") |
| Every number in the claim appears in its cited records (or in statistics PharmaLens computed) | Deterministic; sources read permissively, claims strictly; rounding allowed | Removed: "numbers not found in the cited sources" (blocks invented enrolment, rates, doses) |
| Price, cost, ICER or QALY statements | Deterministic; no pricing source exists | Removed: "no pricing data was retrieved" |
| Efficacy or clinical-outcome claims citing only trial registrations | Deterministic | Removed: registration/status is not outcome evidence |
| "Approved" claims citing only compounds whose ChEMBL max phase < 4 | Deterministic | Removed as contradicted |
| Comparisons citing fewer than two records | Deterministic | Published as partially supported, with a note |
| Each cited record supports / partially supports / is irrelevant to / contradicts the claim | Separate LLM call, strict instructions, evidence treated as data | Irrelevant citations dropped; unsupported or contradicted factual claims removed; unsupported interpretations relabelled as hypotheses |

If the support check is unavailable, claims are published as **Not verified** (visible in the report), never as
verified. Every removal and relabelling is stored with section, claim type, status, reason and citations.

**4. Publication gate (repositories).** `ensure_publishable` runs inside both repositories' `complete()`: a report
is refused unless verification marked it validated, every factual claim has citations and a publishable status,
and every citation has a reference built from a real record. A refused report fails the session ("failed claim
verification") instead of being saved.

**Missing data.** Trial digests state "outcome results: not retrieved (registry entry only)"; enrolment carries
ACTUAL/ESTIMATED; missing enrolment, mechanisms or approval are given to the model as "not reported" / "not
recorded"; registered primary outcome *measures* are captured as measures, not results.

Other controls: statements are labelled by type in the UI; validation flags preprints, retractions, stopped
trials, trials without posted results, missing metadata and withdrawn compounds; empty report sections are
omitted rather than filled; prompts tell models never to follow instructions found inside evidence.

## Knowledge graph

`services/knowledge_graph.py` builds the graph deterministically from evidence records (`GET /api/graph`, all of the
user's sessions or one). No LLM, similarity or embedding is involved; an edge exists only because a record states it,
and it carries that record's ID.

| Edge | Stated by |
| --- | --- |
| target → disease `associated_with` | Open Targets association record (score in the edge detail) |
| compound → target `acts_on` | ChEMBL mechanism; the target's official gene symbol comes from ChEMBL's target record |
| trial → compound `tests` | Trial intervention name (dose stripped) equals the ChEMBL compound name or a synonym |
| trial → disease `studies`, trial → sponsor `sponsored_by` | Trial registration |
| publication → trial `references` | The trial's NCT number appears in the paper's title or abstract (only retrieved trials) |
| publication → compound `mentions` | The compound's name or a synonym (≥ 5 characters) appears as a whole word in the title or abstract |

Nodes from different sources merge only on what both state: HGNC symbol for targets (Open Targets ↔ ChEMBL),
normalised disease/condition name, and the PubChem record attaches to the ChEMBL compound it was matched to by
InChIKey. Publications with no qualifying link are left out (counted in `stats`). The UI renders it with Cytoscape.js
(loaded only on that page), with a neighbourhood view that expands one node at a time and a "why?" link on every
edge that shows the records behind it.

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
