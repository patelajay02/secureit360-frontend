-- SecureIT360 — Phase 0 Security Foundation
-- Adds the minimum server-side control tables the Phase 0 remediation depends on:
--   1. platform_admins   — source of truth for platform-wide (global) admin role
--   2. audit_log         — security audit trail for privileged actions
--   3. scan_jobs         — DB-backed job lock + status for scheduled/manual scans
--   4. scheduler_runs    — per-cron-run health record (for the health endpoint)
--
-- Design notes:
--   * This migration is idempotent (safe to re-run).
--   * It does NOT redesign existing tables. RLS on the pre-existing core tables
--     (findings/scans/domains/tenants/tenant_users/...) is deliberately left for
--     Phase 1 — enabling it blind here could break production, and the backend
--     accesses those via the service-role key which bypasses RLS regardless.
--   * FKs reference tables the audit confirmed exist in the live DB
--     (auth.users, tenants, domains, scans). As with the existing hibp migration,
--     the full migration set is not yet replayable from an empty database; that
--     schema-drift backfill is a Phase 1 task.

create extension if not exists pgcrypto;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. PLATFORM ADMINS — the ONLY source of truth for global administration.
--    A user is a platform admin iff a row exists here. Never derived from a
--    client-supplied value, email, or tenant_users.role.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.platform_admins (
    user_id     uuid primary key references auth.users(id) on delete cascade,
    note        text,
    created_at  timestamptz not null default now()
);

-- SECURITY DEFINER helper so RLS policies on OTHER tables can check platform-admin
-- status without being blocked by platform_admins' own RLS (avoids recursion).
create or replace function public.is_platform_admin(p_user uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (select 1 from public.platform_admins where user_id = p_user);
$$;

revoke all on function public.is_platform_admin(uuid) from public;
grant execute on function public.is_platform_admin(uuid) to authenticated, service_role;

alter table public.platform_admins enable row level security;

-- A caller may only see their OWN platform-admin row (to self-check status).
drop policy if exists platform_admins_select_self on public.platform_admins;
create policy platform_admins_select_self on public.platform_admins
    for select using (auth.uid() = user_id);
-- No insert/update/delete policies → membership is managed only via service role
-- (server-side) or a direct DB operator. This is intentional.

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. AUDIT LOG — immutable-ish trail of privileged actions.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.audit_log (
    id               uuid primary key default gen_random_uuid(),
    actor_user_id    uuid,                 -- who performed the action (nullable: system/cron)
    actor_tenant_id  uuid,                 -- actor's tenant, where applicable
    action           text not null,        -- e.g. 'admin.user.delete', 'auth.login'
    target_type      text,                 -- e.g. 'user', 'tenant', 'domain', 'scan'
    target_id        text,                 -- id of the affected resource
    target_tenant_id uuid,                 -- tenant the target belongs to (for tenant-scoped reads)
    outcome          text not null default 'success'  -- 'success' | 'denied' | 'error'
                     check (outcome in ('success', 'denied', 'error')),
    ip               text,                 -- request source IP where reliably available
    detail           jsonb not null default '{}'::jsonb,  -- non-sensitive context only
    created_at       timestamptz not null default now()
);

create index if not exists audit_log_actor_idx        on public.audit_log(actor_user_id);
create index if not exists audit_log_actor_tenant_idx on public.audit_log(actor_tenant_id);
create index if not exists audit_log_target_tenant_idx on public.audit_log(target_tenant_id);
create index if not exists audit_log_created_at_idx    on public.audit_log(created_at desc);
create index if not exists audit_log_action_idx        on public.audit_log(action);

alter table public.audit_log enable row level security;

-- Platform admins may read the full trail; a tenant member may read audit rows
-- scoped to their own tenant (actor or target). Writes are service-role only.
drop policy if exists audit_log_select on public.audit_log;
create policy audit_log_select on public.audit_log
    for select using (
        public.is_platform_admin()
        or actor_tenant_id in (
            select tenant_id from public.tenant_users
            where user_id = auth.uid() and status = 'active'
        )
        or target_tenant_id in (
            select tenant_id from public.tenant_users
            where user_id = auth.uid() and status = 'active'
        )
    );
-- No insert/update/delete policies → only the server-side service role writes here.

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. SCAN JOBS — one row per (tenant, target, scan_type, scheduled cycle).
--    Acts as the duplicate-prevention lock and the status/attempt record.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.scan_jobs (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references public.tenants(id) on delete cascade,
    domain_id       uuid references public.domains(id) on delete cascade,
    scan_type       text not null default 'daily_full',
    -- Calendar day of the scheduled cycle (NZ date). Combined with the unique
    -- index below, guarantees at most one job per tenant/target/type/day.
    scheduled_date  date not null,
    scheduled_for   timestamptz,            -- intended run time
    status          text not null default 'queued'
                    check (status in ('queued','running','completed','failed','timed_out','skipped_duplicate')),
    started_at      timestamptz,
    completed_at    timestamptz,
    attempt_count   int not null default 0,
    failure_reason  text,
    scan_id         uuid references public.scans(id) on delete set null,  -- resulting scan, if any
    locked_by       text,                   -- worker/process identifier holding the lock
    locked_at       timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- The duplicate-prevention guarantee: one job per tenant/target/type/day.
create unique index if not exists scan_jobs_unique_cycle
    on public.scan_jobs(tenant_id, domain_id, scan_type, scheduled_date);

create index if not exists scan_jobs_tenant_idx on public.scan_jobs(tenant_id);
create index if not exists scan_jobs_status_idx on public.scan_jobs(status);
create index if not exists scan_jobs_scheduled_date_idx on public.scan_jobs(scheduled_date desc);

alter table public.scan_jobs enable row level security;

-- Tenant members read their own tenant's jobs; platform admins read all.
-- Writes (queue/lock/status transitions) are performed server-side via the
-- service role only — no client write policies.
drop policy if exists scan_jobs_select on public.scan_jobs;
create policy scan_jobs_select on public.scan_jobs
    for select using (
        public.is_platform_admin()
        or tenant_id in (
            select tenant_id from public.tenant_users
            where user_id = auth.uid() and status = 'active'
        )
    );

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. SCHEDULER RUNS — operational health record, one row per cron invocation.
--    Not tenant-scoped. Read via service role (health endpoint) / platform admin.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.scheduler_runs (
    id            uuid primary key default gen_random_uuid(),
    job_name      text not null,            -- 'daily_scans' | 'weekly_emails' | ...
    status        text not null default 'running'
                  check (status in ('running','completed','failed')),
    started_at    timestamptz not null default now(),
    finished_at   timestamptz,
    tenants_total     int,
    tenants_succeeded int,
    tenants_failed    int,
    error         text,
    detail        jsonb not null default '{}'::jsonb,
    created_at    timestamptz not null default now()
);

create index if not exists scheduler_runs_job_idx on public.scheduler_runs(job_name, started_at desc);

alter table public.scheduler_runs enable row level security;

-- Platform admins only (via the is_platform_admin helper). Backend health
-- endpoint reads with the service role, which bypasses RLS.
drop policy if exists scheduler_runs_select on public.scheduler_runs;
create policy scheduler_runs_select on public.scheduler_runs
    for select using (public.is_platform_admin());

-- ─────────────────────────────────────────────────────────────────────────────
-- BOOTSTRAP (MANUAL — do NOT hardcode admin identities in migrations):
--   After applying this migration, grant platform-admin to the operator account
--   by running (in the Supabase SQL editor, replacing the email):
--
--     insert into public.platform_admins (user_id, note)
--     select id, 'bootstrap platform admin'
--     from auth.users where email = 'you@yourcompany.example'
--     on conflict (user_id) do nothing;
--
-- ─────────────────────────────────────────────────────────────────────────────
