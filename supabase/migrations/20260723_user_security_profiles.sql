-- SecureIT360 — Stage 1 authentication-security foundation
-- Per-user security profile. Supabase Auth remains the source of truth for MFA
-- factors and sessions; this table holds ONLY application metadata Supabase does
-- not track (forced-reset flags, last strong reauth, notification preference,
-- and the derived "MFA required" flag for privileged roles).
--
-- Idempotent. Does not modify or depend on the Phase 0 migrations.

create table if not exists public.user_security_profiles (
    user_id                         uuid primary key references auth.users(id) on delete cascade,
    must_change_password            boolean not null default false,
    password_changed_at             timestamptz,
    compromised_reset_required      boolean not null default false,
    last_strong_reauth_at           timestamptz,
    security_notifications_enabled  boolean not null default true,
    last_session_review_at          timestamptz,
    mfa_required                    boolean not null default false,  -- true for privileged roles
    created_at                      timestamptz not null default now(),
    updated_at                      timestamptz not null default now()
);

create index if not exists user_security_profiles_user_idx
    on public.user_security_profiles(user_id);

alter table public.user_security_profiles enable row level security;

-- A user may read their OWN profile (to render the Security Centre). All writes
-- happen server-side via the service role (no client insert/update/delete policy).
drop policy if exists user_security_profiles_select_own on public.user_security_profiles;
create policy user_security_profiles_select_own on public.user_security_profiles
    for select using (auth.uid() = user_id);
