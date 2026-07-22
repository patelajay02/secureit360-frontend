-- SecureIT360 - Phase 0 distributed rate limiting
-- A Postgres-backed fixed-window limiter so rate-limit state is SHARED across
-- all Railway instances (not per-process memory). The rl_check function performs
-- the window check + increment atomically in a single upsert.

create table if not exists public.rate_limit_hits (
    bucket        text primary key,
    window_start  timestamptz not null default now(),
    count         int not null default 0
);

alter table public.rate_limit_hits enable row level security;
-- No policies: this table is written/read only by the server-side service role.

create or replace function public.rl_check(
    p_bucket text,
    p_limit int,
    p_window_seconds int
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := now();
    v_count int;
begin
    insert into public.rate_limit_hits (bucket, window_start, count)
    values (p_bucket, v_now, 1)
    on conflict (bucket) do update
        set count = case
                when public.rate_limit_hits.window_start < v_now - make_interval(secs => p_window_seconds)
                    then 1
                    else public.rate_limit_hits.count + 1
            end,
            window_start = case
                when public.rate_limit_hits.window_start < v_now - make_interval(secs => p_window_seconds)
                    then v_now
                    else public.rate_limit_hits.window_start
            end
    returning count into v_count;

    -- true = allowed (within limit), false = throttled
    return v_count <= p_limit;
end;
$$;

revoke all on function public.rl_check(text, int, int) from public;
grant execute on function public.rl_check(text, int, int) to service_role;

-- Optional periodic cleanup helper (call from a cron if desired).
create or replace function public.rl_gc(p_older_than_seconds int default 86400)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    v_deleted int;
begin
    delete from public.rate_limit_hits
    where window_start < now() - make_interval(secs => p_older_than_seconds);
    get diagnostics v_deleted = row_count;
    return v_deleted;
end;
$$;

revoke all on function public.rl_gc(int) from public;
grant execute on function public.rl_gc(int) to service_role;
