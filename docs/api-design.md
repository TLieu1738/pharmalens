# PharmaLens API

Base URL: `VITE_API_BASE_URL` (local: `http://localhost:8000`). Interactive docs at `/docs` outside production.
Auth: `Authorization: Bearer <Supabase access token>`. Errors are `{"detail": "<user-safe message>"}`; unknown or
another user's sessions return 404.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | – | App name, status, version |
| GET | `/api/health` | – | `ok`/`degraded`, which integrations are configured, storage mode. No secrets. |
| POST | `/api/research` | required\* | `{"research_question": str}` (20–2000 chars, ≥3 words) → `202 {"session_id","status":"pending"}`. A worker drafts the protocol; the session then waits in `awaiting_approval`. 503 if the LLM is not configured. |
| GET | `/api/sessions` | required | Caller's sessions, newest first |
| GET | `/api/sessions/{id}` | owner | Status, protocol, approval time, attempts, all 7 agents (status, durations, per-query coverage and errors), warnings, evidence profile, run audit, report when complete |
| GET | `/api/sessions/{id}/evidence` | owner | Validated evidence records (deduplicated, with quality flags and provenance) |
| PUT | `/api/sessions/{id}/protocol` | owner | Save edits to the drafted protocol (full `ResearchPlan`). 409 unless `awaiting_approval`; 422 on invalid limits, empty sources or reversed dates. |
| POST | `/api/sessions/{id}/approve` | owner | `{"protocol": ResearchPlan?}` → approve (optionally with final edits) and queue execution. 409 if already approved or ended. |
| POST | `/api/sessions/{id}/cancel` | owner | Cancel a session that has not finished. Running agents stop before their next step. |
| POST | `/api/sessions/{id}/rerun` | owner | New session with the same question and protocol, opened in `awaiting_approval` for editing → `201`. |
| GET | `/api/library` | required | Every evidence record across the caller's sessions, deduplicated by record ID, each with the sessions it came from. |
| GET | `/api/graph?session_id=` | required | Knowledge graph built from the caller's evidence (all sessions, or one owned session; 404 otherwise): `{nodes, edges, stats}`. Every edge has `relation` and the `record_ids` that state it. |

\* Signed-out research is allowed only when `DEMO_MODE=true` (local development).

Polling: the frontend polls `GET /api/sessions/{id}` every 2 s while work is in progress and pauses while the
session awaits approval or has finished.
