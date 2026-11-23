-- PharmaLens 002: protocol approval workflow, durable job queue and run audit.
-- Additive and backward compatible: existing rows and the previous application version keep working.

-- New lifecycle states: awaiting_approval (protocol drafted, waiting for the user), queued (approved,
-- waiting for a worker) and cancelled.
alter table public.research_sessions drop constraint if exists research_sessions_status_check;
alter table public.research_sessions add constraint research_sessions_status_check
    check (status in ('pending','planning','awaiting_approval','queued','researching','validating',
                      'synthesising','completed','failed','cancelled'));

-- Job fields: a worker claims a session by taking a lease, renews it while it works, and a lapsed lease
-- means the worker died, so the job is re-queued (bounded by attempts).
alter table public.research_sessions
    add column if not exists attempts             integer not null default 0,
    add column if not exists worker_id            text,
    add column if not exists lease_expires_at     timestamptz,
    add column if not exists protocol_approved_at timestamptz,
    add column if not exists run_audit            jsonb;

-- Workers poll for due jobs; keep that query cheap.
drop index if exists public.research_sessions_active_idx;
create index if not exists research_sessions_jobs_idx
    on public.research_sessions (status, lease_expires_at, created_at)
    where status not in ('completed','failed','cancelled','awaiting_approval');
