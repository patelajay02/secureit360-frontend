# Backend environment variables

Set these in Railway for the FastAPI service. Local dev reads them from
`backend/.env`.

## Core

- `SUPABASE_URL`
- `SUPABASE_KEY` — anon/publishable key, used for user-scoped operations
- `SUPABASE_SERVICE_KEY` — service-role key, used by `supabase_admin`

## Email / notifications

- `SENDGRID_API_KEY`

## Integrations

- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` — Microsoft 365 OAuth
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Google Workspace OAuth

## Threat intelligence scan APIs

- `ABUSEIPDB_API_KEY`
- `VIRUSTOTAL_API_KEY`
- `URLSCAN_API_KEY`
- `OTX_API_KEY`
- `HIBP_API_KEY`
- `SHODAN_API_KEY`

## Universal SaaS Connector

- `SAAS_VAULT_KEY` — 32-character random secret used as the passphrase for
  `pgp_sym_encrypt` / `pgp_sym_decrypt` over every credential stored in
  `saas_connections.encrypted_credentials`. Generate with
  `python -c "import secrets; print(secrets.token_urlsafe(24))"` (24 bytes
  → 32 base64url characters). Never commit or log this value. Rotating it
  requires re-encrypting every existing row — plan a migration before
  rotating.
- `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET` — OAuth 2.0 (PKCE) credentials
  for the Xero Tier-1 connector. Redirect URI to register in the Xero
  developer portal:
  `https://secureit360-production.up.railway.app/saas/callback/xero`.
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET` — OAuth 2.0 credentials for the
  Zoho Tier-1 connector. Redirect URI to register in the Zoho API
  console (under the "Server-based Applications" client type):
  `https://secureit360-production.up.railway.app/saas/callback/zoho`.
  Zoho auto-detects the user's data centre on redirect — no separate
  per-region client id is required.
