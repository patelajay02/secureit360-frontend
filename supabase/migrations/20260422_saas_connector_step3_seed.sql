-- SecureIT360 Universal SaaS Connector — Step 3
-- Seed app registry rows for Xero and Zoho.
-- Adds saas_update_credentials RPC used by load_credentials() to persist
-- refreshed OAuth tokens without round-tripping plaintext to Python.

-- ── saas_update_credentials RPC ────────────────────────────────────────────

create or replace function public.saas_update_credentials(
    p_connection_id uuid,
    p_user_id uuid,
    p_plaintext_json text,
    p_key text
)
returns boolean
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    v_updated int;
begin
    update public.saas_connections
    set encrypted_credentials = extensions.pgp_sym_encrypt(p_plaintext_json, p_key)
    where id = p_connection_id and user_id = p_user_id;
    get diagnostics v_updated = row_count;
    return v_updated > 0;
end;
$$;

grant execute on function public.saas_update_credentials(uuid, uuid, text, text)
    to authenticated, service_role;


-- ── Seed: Xero ─────────────────────────────────────────────────────────────

insert into public.saas_app_registry (
    slug, name, logo_url, tier, oauth_config,
    generic_check_capabilities, verified
)
values (
    'xero',
    'Xero',
    null,
    '1_oauth',
    jsonb_build_object(
        'auth_url', 'https://login.xero.com/identity/connect/authorize',
        'token_url', 'https://identity.xero.com/connect/token',
        'redirect_uri', 'https://secureit360-production.up.railway.app/saas/callback/xero',
        'scopes', 'offline_access openid profile email accounting.settings accounting.contacts.read accounting.reports.read',
        'uses_pkce', true,
        'env_client_id', 'XERO_CLIENT_ID',
        'env_client_secret', 'XERO_CLIENT_SECRET'
    ),
    '["admin_ratio", "mfa_coverage", "dormant_users"]'::jsonb,
    true
)
on conflict (slug) do update
set name = excluded.name,
    tier = excluded.tier,
    oauth_config = excluded.oauth_config,
    generic_check_capabilities = excluded.generic_check_capabilities,
    verified = excluded.verified;


-- ── Seed: Zoho ─────────────────────────────────────────────────────────────

insert into public.saas_app_registry (
    slug, name, logo_url, tier, oauth_config,
    generic_check_capabilities, verified
)
values (
    'zoho',
    'Zoho',
    null,
    '1_oauth',
    jsonb_build_object(
        'auth_url', 'https://accounts.zoho.com/oauth/v2/auth',
        'token_url', 'https://accounts.zoho.com/oauth/v2/token',
        'redirect_uri', 'https://secureit360-production.up.railway.app/saas/callback/zoho',
        'scopes', 'ZohoCRM.users.READ,ZohoCRM.org.READ,AaaServer.profile.READ',
        'uses_pkce', false,
        'regional', true,
        'env_client_id', 'ZOHO_CLIENT_ID',
        'env_client_secret', 'ZOHO_CLIENT_SECRET'
    ),
    '["admin_ratio", "mfa_coverage", "dormant_users"]'::jsonb,
    true
)
on conflict (slug) do update
set name = excluded.name,
    tier = excluded.tier,
    oauth_config = excluded.oauth_config,
    generic_check_capabilities = excluded.generic_check_capabilities,
    verified = excluded.verified;
