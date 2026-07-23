-- SecureIT360 — Stage 1b: MFA recovery codes
-- Supabase MFA has no native recovery codes, so these are application-managed.
-- Only SALTED HASHES are stored; plaintext codes are shown to the user exactly
-- once at generation and never persisted or logged. Server-side (service-role)
-- access only; hashes are never exposed to the browser.
--
-- Idempotent. Independent of the Phase 0 / Stage-1a migrations.

create table if not exists public.mfa_recovery_codes (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    batch_id    uuid not null,               -- regeneration invalidates old batches
    code_hash   text not null,               -- "salt:sha256hex(salt+normalized_code)"
    used_at     timestamptz,                 -- one-time use
    created_at  timestamptz not null default now()
);

create index if not exists mfa_recovery_codes_user_idx  on public.mfa_recovery_codes(user_id);
create index if not exists mfa_recovery_codes_batch_idx on public.mfa_recovery_codes(batch_id);

alter table public.mfa_recovery_codes enable row level security;
-- No policies: written/read only by the server-side service role. The browser
-- never reads hashes; plaintext codes are returned once by the generate endpoint.
