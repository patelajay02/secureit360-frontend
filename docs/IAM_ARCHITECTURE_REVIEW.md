# SecureIT360 — IAM Architecture Review (pre-implementation)

**Date:** 2026-07-23
**Purpose:** Final architecture review before building the full IAM framework. **No code changed this pass.** This review maps the requested spec onto the *actual* system, flags conflicts (including with the benchmark platforms and with work already shipped + approved), and proposes a target design + staged plan. Several items need a decision before implementation (§Decisions).

---

## 1. Current shipped state (baseline)
- **Phase 0 (live on `main`):** tenant-independent platform-admin login, `require_platform_admin` / `get_current_tenant` / `require_active_membership`, distributed rate limiting (`rl_check`), audit logging (`audit_log`), reCAPTCHA verify. Tables `platform_admins`, `audit_log`, `scan_jobs`, `scheduler_runs`, `rate_limit_hits` (RLS).
- **Admin perf fix (live):** `/auth/admin/users` batched (no N+1) with server pagination/search/status.
- **This session, committed:** modern **password policy** (length 14, no composition, breach-screened) + **HIBP k-anonymity** screening; **Stage 1a AAL2 foundation** (`get_token_aal`, `get_security_context`, `require_aal2`, `GET /auth/security/mfa-status`, `user_security_profiles` migration).
- **Role model (reality):** `tenant_users.role ∈ {owner, admin, member}` + `platform_admins`. **No `security_manager`, `company_admin`, or generic role system.**
- **Auth transport:** browser holds a Supabase JWT in `localStorage`; talks only to FastAPI; **no `@supabase/supabase-js` yet** (Stage 1b will add it).

---

## 2. Benchmark reality check (important)
You set the bar at **Microsoft 365, AWS, Okta, Google Workspace**. Those platforms have, over the last several years, **deprecated forced password *composition* and forced *periodic expiry*** in line with **NIST SP 800-63B** and **OWASP**:
- Microsoft explicitly recommends **removing mandatory periodic password expiration** and **not requiring character composition**.
- NIST 800-63B: allow long passphrases, screen against breach lists, **do not impose composition rules**, **do not require periodic rotation** (rotate only on evidence of compromise).
- Okta/Google/AWS lead with **MFA (ideally phishing-resistant), SSO/conditional access, and breach screening** — not composition/expiry.

**So the specific requirements "composition (upper/lower/number/symbol)", "expiry 90/180 days", and "history of last 5" actually make the product *less* like M365/Okta/Google, not more.** This is the central finding of the review: the stated *goal* (match those IdPs) conflicts with three of the stated *requirements*. Recommendation in §Decisions D1/D2.

---

## 3. Conflicts & risks (ranked)

**C1 — Password composition reverses shipped, approved policy and contradicts the benchmark.** I shipped (and you approved, one task ago) a passphrase-first policy with **no composition** because your own earlier spec (Part 4/6) and NIST/OWASP required it. This spec now demands composition. → Decision D1.

**C2 — Routine password expiry (90/180 d) contradicts NIST/OWASP *and* the earlier approved spec** ("routine expiry disabled by default"). Forced expiry drives weaker, predictable passwords and increases help-desk/lockout load. → Decision D2.

**C3 — "Password history (last 5)" is not cleanly implementable with Supabase-native password management.** With the JS-SDK approach, password changes go through **`supabase.auth.updateUser({password})` in the browser** — the backend never sees the plaintext to hash for a history comparison, and Supabase's internal credential hashes are **opaque** (must never be copied/inspected). History would require **routing password changes through the backend** (browser POSTs the new password to FastAPI over TLS → backend hashes for history → calls `admin.updateUserById`), which diverges from the native flow. → Decision D3.

**C4 — "All protected APIs verify both role and AAL2" contradicts "MFA optional for ordinary users."** If every authenticated API requires AAL2, then `member` users (optional MFA → AAL1) are locked out of the entire product. Enterprise IdPs apply **step-up/conditional AAL2 to *privileged/sensitive* operations**, not to every request. → Decision D4 (recommend AAL2 for privileged ops only).

**C5 — `security_manager` (and `company_admin`) roles do not exist.** The schema has `owner/admin/member`. "Company Admin" maps cleanly to `role='admin'` (or `owner`); **"Security Manager" has no home** — it needs either (a) a real, migration-backed role system, or (b) to be dropped/mapped. Inventing it silently would violate the "don't invent conflicting roles" rule you set earlier. → Decision D5.

**C6 — "Do not introduce additional database round-trips / avoid N+1" is in direct tension with server-authoritative sessions, login history, device management, and the security score.** Server-authoritative idle/absolute session enforcement inherently means **reading a session row per protected request** (or decoding it from claims). Login history, device management, impossible-travel, and score all **write/read rows**. "Zero additional round-trips" is **not literally achievable** for these features. What *is* achievable: (a) derive as much as possible from the JWT (`aal`, `exp`, role) with **no** extra call; (b) enforce idle/absolute via a **short-TTL cached** session check rather than per-request; (c) make login-history/geo/fingerprint **async/fire-and-forget** off the hot path; (d) reuse the batched admin pattern. I'll hold to "no *avoidable* round-trips and no N+1," and document each place a round-trip is unavoidable.

**C7 — Trusted-device / "remember for 30 days" is not native to Supabase TOTP.** Supabase MFA has no built-in "skip MFA on this device for 30 days." It requires **app-level trusted-device logic** (a `trusted_devices` table keyed by a signed device token + fingerprint; skip the AAL2 *challenge* — not lower the required AAL — when a valid unexpired trusted token is presented). Security caveat: trusted-device weakens MFA and must be **off for platform admins** and gated by tenant policy. → part of the design, flagged as a security trade-off.

**C8 — Browser fingerprint + geo-location + impossible-travel have privacy/compliance weight.** Fingerprinting and IP-geolocation are personal data (GDPR/AU Privacy/UAE PDPL/India DPDP — the very regimes this product maps!). They need a lawful basis, a privacy-notice update, IP minimization (store truncated/hashed IP or coarse geo), and retention limits. "Architecture" is fine now; enabling them is a privacy decision. Impossible-travel also needs an IP-geo data source (MaxMind/ipinfo) → a new dependency + cost.

**C9 — SSO (Azure AD / Google / Okta / SAML) is plan-gated.** Supabase **SAML SSO** is Pro/Enterprise; social OAuth (Google/Azure) is available broadly. "SSO-ready architecture" = keep identities keyed on Supabase `auth.users` and don't hard-code password-only assumptions; actual SSO is a later enablement + plan check. No implementation now.

**C10 — Session timeout values differ from the previous approved spec.** New: idle PA/CA 15 min, users 30 min; absolute PA 8 h, users 12 h. (Earlier: idle PA 10 min; absolute users 24 h.) These are just policy values — I'll adopt the **new** numbers, made tenant-configurable within platform-enforced min/max.

---

## 4. Target IAM architecture (proposed)

**Principle: Supabase-native as source of truth; thin app layer only for what Supabase doesn't provide.**

| Capability | Source of truth | App layer needed? |
|---|---|---|
| Password auth, JWT, refresh | Supabase Auth (JS SDK) | Bridge existing backend login → `setSession` (Stage 1b) |
| TOTP MFA enroll/challenge/verify, AAL | Supabase Auth native | UI only (JS SDK) |
| Leaked-password + min length (server) | Supabase Auth setting **+ app policy** (belt-and-braces) | Keep app `password_policy` + HIBP |
| SSO / social | Supabase Auth (plan-gated) | Later; keep architecture identity-keyed on `auth.users` |
| Recovery codes | **Not native** → app | `mfa_recovery_codes` (salted hashes, one-time, RLS) |
| Trusted devices (30 d) | **Not native** → app | `trusted_devices` (signed token + fingerprint hash; PA excluded) |
| Server-authoritative sessions (idle/absolute/revoke/remote-logout) | **App** (Supabase sessions aren't per-role/revocable-by-id) | `application_sessions` (+ short-TTL cache) |
| Login history / IP / geo / fingerprint / impossible-travel | **App** | reuse `audit_log` for events; `login_events` only if query patterns demand it |
| Password history / forced-reset | **App** (if D3=yes) | `user_security_profiles` + `password_history` (own hashes) |
| Account security score | **App**, computed server-side | derive from Supabase factors + profiles (cache) |
| Tenant security policy | **App** | `tenant_security_policies` (platform min/max clamps) |
| Audit (immutable) | `audit_log` (append-only; consider a delete/update-blocking policy or WORM) | extend action catalogue |

**Backend security context (extend Stage 1a):** one dependency returns `{user_id, tenant_id?, role, is_platform_admin, aal, session_id, recent_reauth}` — reused by `require_role`, `require_aal2`, `require_recent_reauth`. Explicit at route level (not middleware-only).

**Performance design:** JWT-derived checks (role/aal/exp) cost **0 extra calls**; session liveness via a per-request row read is the one unavoidable add — mitigate with a short in-process TTL cache keyed on `session_id`, or accept absolute/idle enforcement at token-refresh boundaries. Login history/geo/fingerprint run **async** off the response path. Admin/session lists reuse the **batched, paginated** pattern (no N+1).

---

## 5. Security invariants (non-negotiable, all preserved)
- Service-role key **server-only**; browser gets the **anon key** only.
- Backend remains **authoritative** for authz; frontend guards are UX.
- AAL2 + role enforced at the **route layer** (explicit dependencies).
- **Tenant isolation** never bypassed; **platform admins tenant-independent** (governed by platform policy, not any tenant).
- Audit logs never contain passwords, TOTP secrets/codes, recovery codes, or tokens.

---

## 6. Data model to add (migrations, RLS, indexed)
`application_sessions`, `trusted_devices`, `mfa_recovery_codes` (if native absent — it is), `tenant_security_policies`, `password_history` (only if D3=yes), extend `user_security_profiles` (Stage 1a). Optional `login_events` only if `audit_log` query patterns prove insufficient. All: RLS (own-row / tenant-scoped / platform-admin), service-role writes, cleanup/retention jobs, indexes for expiry + lookup.

---

## 7. Staged implementation plan (gated on decisions)
1. **Stage 1b:** Supabase JS SDK + `setSession` bridge; MFA enroll/challenge UI; attach `require_aal2` to privileged routes (with enrollment shipped together — no lockout).
2. **Stage 2:** `application_sessions` + idle/absolute enforcement (cached) + timeout modal + Active Sessions / Devices / Login History UI + revoke/remote-logout.
3. **Stage 3:** recovery codes + MFA reset workflow + trusted devices (policy-gated, PA excluded).
4. **Stage 4:** admin security actions (force reset / force MFA / disable MFA / lock / unlock / disable / revoke-all) + full audit catalogue.
5. **Stage 5:** Account Security Score + tenant security policies + password-policy decisions (D1–D3) + Security Center UI polish.
6. **Later:** SSO/SAML enablement (plan-gated), passwordless, impossible-travel with a geo provider.

---

## Decisions needed before implementation

- **D1 — Password composition.** Recommend **NO forced composition** (keep length 14 + breach screen + MFA), matching NIST/OWASP and M365/Okta/Google. Alternative: add composition as a **tenant-configurable, off-by-default** contractual option. (Implementing mandatory composition would reverse shipped, approved policy.)
- **D2 — Password expiry.** Recommend **no routine expiry**; force change only on compromise/reset/first-login. Alternative: **tenant-configurable contractual expiry** (90/180 d) off by default with a "not recommended" warning. (Mandatory global expiry contradicts NIST/OWASP + the benchmark + prior approval.)
- **D3 — Password history (last 5).** Choose: **(a)** skip (document Supabase-native limitation) or **(b)** route password changes through the backend so it can hash-for-history (diverges from the pure JS-SDK-native change flow).
- **D4 — AAL2 scope.** Recommend **AAL2 for privileged/sensitive operations only** (so optional-MFA members can still use the product). Alternative: AAL2 for all APIs (blocks all AAL1 users — conflicts with "optional for users").
- **D5 — Roles.** Map **Company Admin → `role='admin'`** and **drop `security_manager`** (not in the model)? Or build a **real migration-backed role system** (adds `security_manager`, etc.) as a prerequisite stage?
- **D6 — Privacy features.** Approve enabling **fingerprint + IP/geo + impossible-travel** (needs a geo provider + privacy-notice/data-map update for AU/NZ/AE/IN), or keep **architecture-only** for now?

---

---

## Decisions locked (2026-07-24)

| # | Decision | Impact |
|---|---|---|
| **D1 Password philosophy** | **Modern** — length 14 + breach screening + MFA; **no forced composition, no routine expiry**. Force change only on compromise / admin-reset / first-login. | **Validates the already-shipped `password_policy` + HIBP screen — no change needed.** No composition/expiry code will be added. |
| **D4 AAL2 scope** | **Privileged operations only** (admin routes, user/role admin, billing, MFA/recovery mgmt, password/email change, tenant deletion, security-policy, sensitive export, credential/connector changes). Members keep AAL1 access. | `require_aal2` attaches to the §10 list in Stage 1b; members are never blocked. |
| **D5 Roles** | **Map onto existing:** Company Admin → `role='admin'`; Owner → `role='owner'`; **drop `security_manager`**. MFA mandatory for **platform_admin + owner** (tenant `admin` may be required via tenant policy later). | Encoded now as `role_requires_mfa(is_platform_admin, role)` (+ test); `mfa-status` uses it. |
| **D3 Password history** | **Skip** (document limitation). Rely on breach screening + MFA; backend never handles password plaintext. | No `password_history` table; native JS-SDK password change preserved. |
| **D6 Privacy features** | **Architecture-only** default (fingerprint/geo/impossible-travel designed for, not enabled) until a privacy-notice/data-map update for AU/NZ/AE/IN and a geo provider are approved. | No PII collection added; interfaces designed to slot in later. |

**Encoded this pass (safe, tested, non-breaking):** `role_requires_mfa()` helper (D5) + `mfa-status` refactor + test. 144 backend tests pass. No routes hard-blocked, no frontend/login change, no deploy.

## Stage 1b — scope + prerequisites (next)
**Prerequisites (operator — I can't do these from here):**
1. **Supabase → Auth: enable TOTP MFA** (native enroll/challenge errors until enabled) and **leaked-password protection**.
2. **Vercel env (all environments): add `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`** (anon key **only** — never the service-role key).

**Stage 1b build (once prerequisites are set):** add `@supabase/supabase-js`; bridge the existing backend-token login into a JS session (`setSession`) — the compatibility shim, with fallback so non-MFA login keeps working; `/settings/security/mfa` enroll wizard (QR + manual secret + 6-digit verify) via `mfa.enroll/challenge/verify`; login MFA-challenge when a verified factor exists at AAL1; **then attach `require_aal2` to the §10 privileged routes** (shipped together with enrollment so `ajay` is never locked out). Because I cannot exercise the live TOTP flow from this environment, Stage 1b requires a **manual smoke test** (enroll an authenticator → log out/in → confirm challenge → confirm privileged routes then require AAL2) before enforcement is relied upon — nothing deploys until that passes.

*Awaiting confirmation that the two prerequisites are in place, then I proceed with Stage 1b, and onward through Stages 2–5 with tests, measured performance, and docs before any deploy.*
