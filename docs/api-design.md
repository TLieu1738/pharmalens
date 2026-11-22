# PharmaLens API

Base URL: `VITE_API_BASE_URL` (local: `http://localhost:8000`). Interactive docs at `/docs` outside production.
Auth: optional `Authorization: Bearer <Supabase access token>`.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | – | App name, status, version |
| GET | `/api/health` | – | `ok`/`degraded`, which integrations are configured, storage mode. No secrets. |
| POST | `/api/research` | optional | `{"research_question": str}` (20–2000 chars, ≥3 words) → `202 {"session_id","status":"pending"}`. 401 if signed-out and `DEMO_MODE=false`; 429 when busy/rate-limited; 503 if the LLM is not configured. |
| GET | `/api/sessions` | required | Caller's sessions, newest first |
| GET | `/api/sessions/{id}` | owner / demo | Status, plan, all 7 agents (pending → running → completed/partial/failed/skipped, durations, per-source counts and errors), warnings, evidence profile, report when complete |
| GET | `/api/sessions/{id}/evidence` | owner / demo | Validated evidence records (deduplicated, with quality flags and provenance) |

Errors are `{"detail": "<user-safe message>"}`. Unknown or foreign sessions return 404.

Polling: the frontend polls `GET /api/sessions/{id}` every 2 s until `completed` or `failed`.
