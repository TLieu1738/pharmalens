-- PharmaLens initial schema.
-- All writes are performed by the backend with the service-role key (which bypasses RLS) after it has
-- verified the caller's identity. RLS policies below grant signed-in users read access to their own data
-- only; anonymous demo sessions (user_id IS NULL) are never readable through the public anon key.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------------------------------------
create table if not exists public.research_sessions (
    id                uuid primary key default gen_random_uuid(),
    user_id           uuid references auth.users (id) on delete cascade,
    research_question text not null check (char_length(research_question) between 20 and 2000),
    status            text not null default 'pending'
                      check (status in ('pending','planning','researching','validating','synthesising','completed','failed')),
    demo_mode         boolean not null default false,
    research_plan     jsonb,
    evidence_profile  jsonb,
    warnings          jsonb not null default '[]'::jsonb,
    error_message     text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),
    completed_at      timestamptz
);
create index if not exists research_sessions_user_created_idx on public.research_sessions (user_id, created_at desc);
create index if not exists research_sessions_active_idx on public.research_sessions (status)
    where status not in ('completed','failed');

-- ---------------------------------------------------------------------------------------------------------
create table if not exists public.evidence_records (
    id                uuid primary key default gen_random_uuid(),
    session_id        uuid not null references public.research_sessions (id) on delete cascade,
    record_id         text not null,
    source_name       text not null,
    source_identifier text not null,
    category          text not null,
    title             text not null,
    summary           text,
    evidence_type     text not null,
    source_url        text not null,
    publication_date  text,
    retrieved_at      timestamptz not null,
    position          integer not null default 0,
    metadata          jsonb not null default '{}'::jsonb,
    unique (session_id, record_id)
);
create index if not exists evidence_records_session_idx on public.evidence_records (session_id, position);

-- ---------------------------------------------------------------------------------------------------------
create table if not exists public.research_reports (
    id                uuid primary key default gen_random_uuid(),
    session_id        uuid not null unique references public.research_sessions (id) on delete cascade,
    executive_summary text,
    report_content    jsonb not null,
    created_at        timestamptz not null default now()
);

-- ---------------------------------------------------------------------------------------------------------
create table if not exists public.agent_executions (
    id                    uuid primary key default gen_random_uuid(),
    session_id            uuid not null references public.research_sessions (id) on delete cascade,
    agent_name            text not null,
    execution_status      text not null
                          check (execution_status in ('pending','running','completed','partial','failed','skipped')),
    execution_duration_ms integer,
    record_count          integer,
    message               text,
    sources               jsonb not null default '[]'::jsonb,
    error_message         text,
    started_at            timestamptz,
    completed_at          timestamptz,
    unique (session_id, agent_name)
);
create index if not exists agent_executions_session_idx on public.agent_executions (session_id);

-- ---------------------------------------------------------------------------------------------------------
create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

drop trigger if exists research_sessions_touch on public.research_sessions;
create trigger research_sessions_touch before update on public.research_sessions
    for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------------------------------------
-- Row Level Security
alter table public.research_sessions enable row level security;
alter table public.evidence_records  enable row level security;
alter table public.research_reports  enable row level security;
alter table public.agent_executions  enable row level security;

drop policy if exists "own sessions readable" on public.research_sessions;
create policy "own sessions readable" on public.research_sessions
    for select to authenticated using (user_id = (select auth.uid()));

drop policy if exists "own evidence readable" on public.evidence_records;
create policy "own evidence readable" on public.evidence_records
    for select to authenticated using (exists (
        select 1 from public.research_sessions s where s.id = session_id and s.user_id = (select auth.uid())));

drop policy if exists "own reports readable" on public.research_reports;
create policy "own reports readable" on public.research_reports
    for select to authenticated using (exists (
        select 1 from public.research_sessions s where s.id = session_id and s.user_id = (select auth.uid())));

drop policy if exists "own executions readable" on public.agent_executions;
create policy "own executions readable" on public.agent_executions
    for select to authenticated using (exists (
        select 1 from public.research_sessions s where s.id = session_id and s.user_id = (select auth.uid())));

-- No insert/update/delete policies: browsers cannot write; only the backend (service role) can.
