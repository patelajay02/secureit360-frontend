# SecureIT360 — Phase 0 Credential Rotation Checklist

**No secret values appear in this document.**

## Git-history status
`backend/.env` and all `.env*` files were **never committed** to git history — verified with
`git log --all -- '*.env'` and a full `git rev-list --all --objects` blob scan (both empty).
`.env` is covered by `backend/.gitignore` and the root `.gitignore` (`.env*`). So exposure is
**working-tree / local-machine only**, not in the repository. Rotation below is therefore
**precautionary** (the audit process read the working-tree values) but strongly recommended.

## Rotate these (manual dashboard actions — automated rotation is not safe here)

| # | Credential | Why | Where to rotate | After rotating |
|---|---|---|---|---|
| 1 | `SUPABASE_SERVICE_KEY` | Full RLS-bypass DB access | Supabase → Project Settings → API → roll `service_role` key | Update Railway var |
| 2 | `SUPABASE_PAT` | Management-API level token | Supabase → Account → Access Tokens → revoke + reissue | Update wherever used |
| 3 | `SENDGRID_API_KEY` | Full email send | SendGrid → Settings → API Keys → revoke + create | Update Railway var |
| 4 | `STRIPE_SECRET_KEY` | Payment API | Stripe → Developers → API keys → roll secret key | Update Railway var |
| 5 | `STRIPE_WEBHOOK_SECRET` | **Currently missing → webhooks rejected** | Stripe → Developers → Webhooks → signing secret | Set Railway var (new) |
| 6 | `RECAPTCHA_SECRET_KEY` | Now used server-side (real key required) | Google reCAPTCHA admin console | Set Railway var |
| 7 | `SHODAN_API_KEY`, `HIBP_API_KEY` | Empty today; only rotate if you later set + suspect exposure | Respective dashboards | Set Railway var |
| 8 | `ANTHROPIC_API_KEY` | SaaS wizard only | Anthropic console | Set Railway var (optional) |

**Supabase anon key (`SUPABASE_KEY`)** is public-by-design (RLS-enforced) — rotation optional.

## Rotation procedure (per credential)
1. Create the new secret in the provider dashboard.
2. Update the value in **Railway** (backend) and, for `NEXT_PUBLIC_*` only, in **Vercel** (frontend).
3. Redeploy the affected service.
4. Revoke/delete the old secret in the provider dashboard.
5. Confirm the app still functions (login, an email send, a Stripe test event).

## Frontend exposure verification (must all be clean)
- No `SUPABASE_SERVICE_KEY` / service-role / `SUPABASE_PAT` in any `NEXT_PUBLIC_*` var, browser bundle, network response, or source map.
- `.env.local` contains only `NEXT_PUBLIC_*` values (API URL, reCAPTCHA **site** key, Stripe **publishable** key, Azure **client id**).
- The former hardcoded admin password in `app/admin/page.tsx` has been **removed** (replaced by server-verified platform-admin auth).
- `backend/.env` and `.env.local` remain gitignored and untracked.
