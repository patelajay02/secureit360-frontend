# Backend environment variables

Set these in Railway for the FastAPI service. Local dev reads them from
`backend/.env`.

## Core

- `SUPABASE_URL`
- `SUPABASE_KEY` — anon/publishable key, used for user-scoped operations
- `SUPABASE_SERVICE_KEY` — service-role key, used by `supabase_admin`
- `FRONTEND_URL` — base URL of the Next.js frontend, used for OAuth
  callback redirects. Optional; defaults to `https://app.secureit360.co`.
  Set to e.g. `http://localhost:3000` in local dev.

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

## AI recipe generator

- `ANTHROPIC_API_KEY` — Claude API key used by
  `backend/saas_connectors/ai_recipe_generator.py` when a director
  searches the catalog for an app that isn't in the registry yet.
  We call `claude-sonnet-4-20250514` via the REST API (no SDK) with a
  strict JSON-only system prompt. Obtain from
  <https://console.anthropic.com/>. Never commit.

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
