# SecureIT360 — Authentication, MFA, Session & Account-Security Implementation

**Date:** 2026-07-23
**Approach:** Audit-first (as instructed), report conflicts, then implement only the parts that are **fully correct, self-contained and unblocked**. MFA/AAL/session/UI/score are staged behind the blockers below because a *partial* MFA/AAL implementation would violate the spec's own rule ("do not leave the product partially enforceable — UI claims MFA is mandatory but backend accepts AAL1").

> **Status this pass:** ✅ Part 4 (password policy) + Part 5 (compromised-password screening) implemented, wired, tested. 📋 Parts 1–3, 6–13, 15–16 audited and specified; **not implemented** pending the four blocking decisions in §Conflicts. No Supabase dashboard changes, no deploys, no secret rotation.

---

## 1. Audit findings

### Current auth flow (traced)
- **Login** (`backend/routes/auth.py:login`): `POST /auth/login` → `supabase.auth.sign_in_with_password` (Python **sync** client) → returns a custom JSON `{token, refresh_token, role, is_platform_admin, …}`. Platform-admin-first (tenant-independent); regular users resolve `tenant_users` via `maybe_single`. **The browser never receives a Supabase session object** — only the raw JWT strings, stored in `localStorage` (`lib/auth.js`).
- **Token handling** (`lib/auth.js`): `authFetch` sends `Authorization: Bearer <localStorage token>`; auto-refresh via `POST /auth/refresh`; **15-minute idle auto-logout** (`SessionTimeout.js`, client-side timer only). Logout = clear localStorage + redirect.
- **Token verification** (`middleware/auth_middleware.py:_verify_token`): every request calls `supabase_admin.auth.get_user(token)` (network round-trip). **No JWT claim inspection; no `aal` reading** (local JWT verify was explicitly deferred).
- **Authorization:** `require_platform_admin` (platform_admins table), `get_current_tenant`/`require_tenant_admin`, `require_active_membership` — all Phase 0, intact.
- **Rate limiting / audit / email:** `services/rate_limit.py` (Postgres `rl_check`), `services/audit.py` (`audit_log`), `services/email_service.py` (SendGrid) — all present.
- **Registration** (`register`): reCAPTCHA (now verified) + tenant/owner/domain creation. **Admin-create** (`admin_create_account`): platform-admin creates a comped tenant + owner.

### Role model (reality — spec mapped onto it)
Roles in the schema: **`tenant_users.role ∈ {owner, admin, member}`** + a separate **`platform_admins`** table. There is **NO** `security_manager`, `compliance_manager`, or `company_admin` role. Mapping (no invented roles):
| Spec role | Actual model |
|---|---|
| platform_admin | row in `public.platform_admins` (tenant-independent) |
| owner / company_admin | `tenant_users.role = 'owner'` |
| tenant admin | `tenant_users.role = 'admin'` |
| security_manager / compliance_manager | **do not exist** — not created (per "map onto actual model") |
| ordinary user | `tenant_users.role = 'member'` |

### Supabase-native capability assessment (from code + docs; **not verified against the live project — no access**)
- **Native TOTP MFA** (`auth.mfa.enroll/challenge/verify`, `unenroll`, `listFactors`, `getAuthenticatorAssuranceLevel`): available in Supabase Auth, but the **enroll/challenge/AAL APIs are client-SDK methods** that operate on a browser Supabase **session**. Must be **enabled in the dashboard**.
- **Recovery codes:** Supabase does **not** provide first-party TOTP recovery codes in the JS/Python SDK today → would need application recovery codes (Part 3).
- **Leaked-password protection** & **min password length/strength**: dashboard Auth settings (availability/plan-dependent).
- **Session timeouts** (time-box + inactivity): dashboard Auth settings, **Pro-plan** feature; cannot vary by role → needs app-level enforcement for the role-specific matrix.
- **Existing tables:** `audit_log`, `platform_admins`, `scan_jobs`, `scheduler_runs`, `rate_limit_hits` (Phase 0 migrations — **not yet applied to the live DB**); `tenants`, `tenant_users`, `domains` (drift tables).

---

## Conflicts — must be resolved before the MFA/AAL/session core (§ "Report any conflicts before implementation")

| # | Blocker | Why it blocks | Decision needed |
|---|---|---|---|
| **C1** | **Frontend has no `@supabase/supabase-js`.** | Native TOTP enroll/challenge and `getAuthenticatorAssuranceLevel` are **client-SDK** operations on a browser Supabase session. The app has no Supabase session (backend-issued JWT in localStorage). | **Adopt the Supabase JS SDK in the browser** (re-architect login onto Supabase sessions so MFA/AAL work natively) **or** proxy MFA via the Python client (limited AAL support). This is a real fork; "do not redesign unrelated modules" vs native MFA are in tension. |
| **C2** | **No `aal` claim inspection.** Backend verifies tokens via a network `get_user()`, not JWT decode. | AAL2 enforcement requires reading the session `aal` from the JWT. | Approve **JWT claim decoding** for `aal`/`amr` (the perf-audit's "local JWT verification", previously deferred). |
| **C3** | **No Supabase access to verify/enable** native MFA, leaked-password protection, session timeouts, or plan. | Spec forbids claiming a setting is available without verifying it; MFA must be dashboard-enabled first. | Confirm the **Supabase plan** and **enable native TOTP MFA** (+ leaked-password protection) in the dashboard; share which session controls the plan exposes. |
| **C4** | **Phase 0 not deployed / migrations not applied.** Railway runs pre-Phase-0 code; `audit_log`/`platform_admins` not live. | Building MFA/session tables + AAL enforcement on an unapplied, undeployed base multiplies risk. | Apply Phase 0 migrations and deploy `main` first (per the earlier deployment task). |

Because of **C1** especially, native MFA cannot be wired correctly in this pass without a decision. Implementing it partially is explicitly disallowed by the spec.

---

## 2. Security architecture selected (this pass)
- **Password controls at the trust boundary:** validate + screen **server-side, before** any Supabase password-set call, so weak/breached passwords are rejected regardless of client. No composition rules (length + breach screening are primary, per NIST/OWASP).
- **k-anonymity breach screening:** only the 5-char SHA-1 prefix leaves the server; full hash/plaintext never sent or logged; **fail-open** on outage.
- Authorization, rate limiting, audit logging **unchanged**.

## 3. Supabase-native capabilities used
This pass uses **none** that require dashboard changes (password policy is app-level, pre-Supabase). Native TOTP MFA / leaked-password protection / session timeouts are **documented for enablement** (§20) but not activated (no access; spec forbids auto-changing the dashboard).

## 4. Files changed
- `backend/services/password_policy.py` **(new)** — length 14–72 bytes, no truncation, allow spaces/passphrases, block email/company variants + common passwords.
- `backend/services/compromised_password.py` **(new)** — HIBP Pwned Passwords k-anonymity screen (fail-open, no secrets logged).
- `backend/routes/auth.py` — wired both into `register` and `admin_create_account` (+ `HTTPException` passthrough; + `auth.password.compromised_blocked` audit on admin-create).
- `backend/tests/test_password_policy.py` **(new)** — 15 tests.
- `docs/AUTHENTICATION_SECURITY_IMPLEMENTATION.md` **(this report)**.

## 5. Migrations created
**None this pass.** The MFA/session/policy/score tables (`user_security_profiles`, `application_sessions`, `mfa_recovery_codes` *(only if native recovery absent)*, `tenant_security_policies`, optional `account_security_scores`) are **designed in §14 of the spec** and will be committed migrations in Stage 1–5 once C1–C4 are resolved. No historic migration edited.

## 6. Tables created
**None this pass** (see §5).

## 7. Backend endpoints created/modified
- **Modified:** `POST /auth/register`, `POST /auth/admin/create-account` (password policy + breach screen).
- **Created:** none. (MFA/session/security-centre endpoints are staged.)

## 8. Frontend pages/components
**None this pass.** The Security Centre (`/settings/security[/mfa|/sessions|/password]`), MFA-challenge page, and timeout modal are staged behind C1 (they require the Supabase JS SDK for native MFA/AAL).

## 9. Roles requiring MFA (target policy)
Mandatory: **platform_admin**, **owner**. Strongly recommended (tenant-policy-configurable): `admin`. Optional-by-default: `member`. (`security_manager`/`compliance_manager` intentionally omitted — not in the schema.)

## 10. Routes requiring AAL2 (classification — enforcement staged)
`/auth/admin/*`, tenant user/role admin (`/auth/invite`, `/auth/users/{id}` delete), billing changes (`/billing/checkout`, `/billing/portal`), MFA/recovery management, password/email change, sensitive export, tenant deletion, security-policy changes, scan target ownership/verification (`/domains/verify`), connector/credential secret changes (`/saas/*`, `/integrations/*`). **To be enforced** via a `require_aal2` dependency once C1/C2 land.

## 11. Session timeout policy (target — enforcement staged)
| Role | Idle | Absolute |
|---|---|---|
| platform_admin | 10 min | 8 h |
| privileged (owner/admin) | 15 min | 12 h |
| member | 30 min | 24 h |
Server-authoritative via `application_sessions` + a `require_live_session` dependency; frontend 60-second warning modal. Background polling/refresh must **not** extend idle. (Staged.)

## 12. Password policy (IMPLEMENTED)
- **Min 14 chars**; **max 72 bytes** (bcrypt limit — rejected, **not silently truncated**); spaces/passphrases allowed; **no composition requirements**.
- Blocks: email address / local-part, company-name variants, a local common-password set, and — via HIBP k-anonymity — **known-compromised passwords**.
- Applied at **signup** and **admin-created accounts**. *(Invited-user setup, reset, and change are not yet backend endpoints — see §23.)*
- User-facing messages never reveal breach specifics.

## 13. Password-expiry policy (routine expiry DISABLED by default — and why)
Routine periodic expiry is **off by default**, per current **NIST SP 800-63B** and **OWASP** guidance: forced rotation drives predictable, weaker passwords. Change is required **only on evidence of compromise** (admin-marked, breach-detected, temp-admin-set, incident, confirmed takeover, recovery). A **tenant-configurable "legacy/contractual" expiry** (90/180/365 days, disabled by default, with a not-recommended warning and an enforced safe minimum) is specified for §12 of the spec and will land with `tenant_security_policies` in Stage 3/5. Password **history** is documented as a limitation (§23) — Supabase Auth's internal credential hashes must never be copied/inspected.

## 14. Recovery design
Supabase has no first-party TOTP recovery codes → **application recovery codes** (Stage 4): 10 CSPRNG codes, shown once, **stored only as salted hashes**, one-time use, regeneration only after recent password+AAL2 (invalidates old batch), email + audit on use, rate-limited, generic errors, require a new factor after recovery. Plus a **support-led reset** runbook (strong identity check, dual approval for platform admins, full audit, user notice, sessions revoked). Table `mfa_recovery_codes` (RLS, service-role-only hash access) only if native recovery stays unavailable.

## 15. Account Security Score model
Server-computed 0–100 (frontend cannot manipulate): MFA +25 (privileged-without-MFA capped at 40); password meets strength +15, not-compromised-at-last-change +10, forced-reset → 0; sessions +10/+5; recovery +10/+5; activity +10/+5/+5. Statuses Critical/Needs-Attention/Good/Strong, per-item explanations, direct actions, disclaimer. **Staged** (depends on MFA/session data).

## 16. Audit events added
This pass: **`auth.password.compromised_blocked`** (admin-create). The full catalogue (`auth.login.*`, `auth.mfa.*`, `auth.session.*`, `auth.password.*`, `auth.role.changed`, …) is specified for Stages 1–4 on the existing `audit_log` (never logging secrets/tokens/codes).

## 17. Tests added
`backend/tests/test_password_policy.py` (15): too-short rejected · 14-char boundary ok · long passphrase accepted (no composition) · spaces allowed · >72 bytes rejected (not truncated) · email/local-part rejected · company variant rejected · common rejected · strong unique ok · HIBP suffix present→compromised (+ asserts only the 5-char prefix is sent, plaintext never in URL) · absent→ok · non-200 fail-open · exception fail-open · empty→not-compromised.

## 18. Full backend test result
**135 passed** (120 prior + 15 new), 1 deprecation warning.

## 19. Frontend test/type-check/lint/build
- Type-check (`tsc --noEmit`): **exit 0**.
- Build (`next build`): **✓ compiled, 21/21 pages**.
- Lint: pre-existing repo warnings only (this pass added no frontend code).

## 20. Manual Supabase steps (verify against the live project — do NOT assume)
1. **Auth → Providers/MFA:** enable **TOTP (Authenticator app)**.
2. **Auth → Passwords:** enable **Leaked-password protection**; set **minimum length ≥ 14** (align with app policy); note this cannot vary by role.
3. **Auth → Sessions** (Pro): set **time-box** + **inactivity timeout** to the *loosest* (member) tier; enforce the stricter platform-admin/owner tiers **in the app** (§11).
4. **Refresh-token reuse detection:** enable rotation/reuse-interval.
5. **Redirect URLs:** confirm `https://app.secureit360.co/*` (and `secureit360.co`) allow-listed for auth-confirm/reset.
6. **Email templates:** confirm confirm/reset/magic-link branding; security-notification emails are sent app-side via SendGrid.
7. Record **plan limits** and any control that "cannot vary by role" → app-level enforcement.

## 21. Railway env changes
- Optional `PWNED_PASSWORDS_ENABLED=true|false` (feature flag; default on) if you want to toggle the HIBP screen. No new required vars this pass. (For staged MFA/JWT work you will later need `SUPABASE_JWT_SECRET` for `aal` decoding.)

## 22. Vercel env changes
- **None this pass.** For staged native MFA you will need `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` (anon key only — never the service-role key) once the Supabase JS SDK is adopted (C1).

## 23. Remaining limitations
- **MFA/AAL/sessions/Security-Centre/score NOT implemented** — blocked by C1–C4.
- **No backend reset/change endpoints** yet; the frontend `/auth/forgot-password` button targets a **non-existent route** (dead) — reset/change flow ties into the Supabase-native decision (C1).
- Password policy applies to signup + admin-create only until reset/change/invite endpoints exist.
- **Password history / reuse prevention:** not implementable cleanly on Supabase Auth (internal credential hashes are opaque) — documented, not faked.
- HIBP screen is **fail-open** on outage (availability choice).
- Supabase-native capability claims are **unverified** against the live project (no access).

## 24. Security-review risks
- Adopting the Supabase JS SDK (C1) changes token storage/refresh — must preserve Phase 0 authorization and not expose the service-role key (anon key only in the browser).
- `aal` decoding (C2) requires the JWT secret on the backend — keep server-side.
- Until AAL2 is enforced, privileged routes rely on role only (Phase 0 behaviour) — **no regression**, but MFA is not yet enforced; the UI must not claim otherwise until Stage 1 ships.
- Fail-open breach screen means an HIBP outage lets a breached password through — acceptable, logged, reversible.

## 25 / 26. Commit & push
Recorded below after commit.

---

## Recommended implementation order (unchanged from spec, gated by C1–C4)
**Prereq:** resolve C1 (Supabase JS SDK vs proxy), C2 (JWT `aal`), C3 (enable MFA + confirm plan), C4 (apply migrations + deploy). Then:
- **Stage 1:** migration foundation → native TOTP enroll/challenge → privileged-role **AAL2 enforcement** (`require_aal2`) → audit events.
- **Stage 2:** idle + absolute session enforcement (`application_sessions`) → timeout UI → session management.
- **Stage 3:** (partly done) password policy ✅ + breach screen ✅ → forced-reset workflow → contractual-expiry option.
- **Stage 4:** recovery codes → security notifications → Account Security Score.
- **Stage 5:** tenant security policy → full regression + security testing.

*This pass delivers Stage 3's password controls (fully tested and safe) and the audit/conflict report the spec required first. The remaining stages are ready to implement once the four decisions are made.*

---

## Stage 1a — AAL2 backend foundation (DELIVERED)

**Decisions received:** adopt the Supabase JS SDK for native MFA/AAL (C1); Phase 0 is deployed + migrations applied (C4 resolved); the operator enables/verifies native MFA, leaked-password protection and session settings in the dashboard (C3). Stage 1 is split so no lockout window can occur:

- **Stage 1a (this pass — safe, non-breaking, no route hard-blocks):**
  - Migration `supabase/migrations/20260723_user_security_profiles.sql` — `user_security_profiles` (forced-reset flags, last strong reauth, notification pref, `mfa_required`), RLS (own-row select; writes service-role only). *Apply via your normal process; I did not apply it.*
  - `middleware/auth_middleware.py`: `get_token_aal()` (reads the `aal` claim from a token **already authenticated** by `get_user` — no signing secret needed), `get_security_context()` (identity + aal + platform-admin flag), and **`require_aal2`** (403 for insufficient assurance, 401 for missing auth) — a reusable, route-level dependency (not middleware-only).
  - `GET /auth/security/mfa-status` — reports `aal`, `is_aal2`, `mfa_required` (true for platform_admin and tenant `owner`), `role`, so the frontend can force enrollment / an AAL2 challenge.
  - Tests `backend/tests/test_aal2.py` (8): aal extraction (incl. malformed token), `require_aal2` allow/deny (aal2/aal1/missing), and mfa-status role logic (platform_admin/owner required, member not).
  - **`require_aal2` is intentionally NOT yet attached to routes** — it is attached in Stage 1b together with the enrollment UI, so the currently-un-enrolled platform admin cannot be locked out.

- **Stage 1b (next — frontend, built + validated carefully):** add `@supabase/supabase-js`; hydrate the JS session from the existing backend login tokens (`setSession`) as the compatibility bridge; `/settings/security/mfa` enrollment wizard (QR + manual secret + 6-digit verify via `mfa.enroll/challenge/verify`); login MFA-challenge step when a verified factor exists at AAL1; then **attach `require_aal2` to the privileged routes in §10**. This must be validated against the now-MFA-enabled Supabase project (which I cannot exercise from the audit environment), which is why it is a separate, deliberate increment rather than shipped blind.

**Stage 1a results:** 143 backend tests pass (135 + 8); type-check exit 0; production build ✓ (21/21). No frontend change, no route behaviour change, no Supabase change, no deploy.

**Manual step for Stage 1b:** in Supabase → Auth, **enable TOTP MFA** (and leaked-password protection); add `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` (anon key only) to Vercel.
