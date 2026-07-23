# SecureIT360 — Stage 1b Operator Checklist (Supabase Auth + Vercel env)

**Purpose:** the exact manual steps to satisfy the two Stage 1b prerequisites so the engineer can build native TOTP MFA. **Operator action only** — no code is changed by this document.

**Legend:**
- 🔴 **Mandatory for Stage 1b** · 🟡 recommended (not blocking) · ⚪ Stage 2+ (not needed now)
- ⚠️ **VERIFY LABEL** — Supabase has reorganised the Auth settings UI across versions; the *setting name* is authoritative, the *path* may differ slightly. Search the setting name if the path doesn't match.
- 🔑 A value you must **copy**. 🚫 A value you must **never** copy anywhere.

> **Project reference:** Supabase project URL is `https://donrxbkxodblikddtqjz.supabase.co` (public; matches `SUPABASE_URL` in the backend). Vercel project: `secureit360-frontend`.

---

## A. Supabase Auth checklist

All paths start at **Supabase Dashboard → (select the SecureIT360 project) → Authentication** in the left sidebar.

### A1. 🔴 Native TOTP MFA (Authenticator App)
- **Path:** Authentication → **Multi-Factor Authentication** ⚠️ VERIFY LABEL (may appear under **Authentication → Sign In / Providers** in some versions).
- **Setting name:** **"Authenticator app (TOTP)"** / **"TOTP"** factor — **Enabled**.
- **Required value:** Enabled (allowed as an MFA factor). Also review **"Maximum enrolled factors"** (default is fine, e.g. 10).
- **Why:** the app calls `supabase.auth.mfa.enroll({ factorType: 'totp' })` / `.challenge()` / `.verify()`; these error if TOTP is not an allowed factor.
- **Mandatory for Stage 1b:** **Yes.**
- **Plan:** Available on **all plans** (including Free). TOTP enroll/challenge/verify work via the API by default.
- **If unavailable:** If you cannot find a toggle, TOTP is likely enabled by default — VERIFY by having the engineer test `mfa.enroll` after Vercel env is set; if enroll returns an "MFA disabled" error, locate and enable the factor.
- **Expected behaviour after enabling:** users can scan a QR code in Microsoft/Google Authenticator, Authy, 1Password or Bitwarden and complete a 6-digit verification; verified sessions become **AAL2**.

### A2. 🔴 MFA enrollment  &  A3. 🔴 MFA challenge / verification
- **Path:** **No separate dashboard setting.** Enrollment (QR + manual secret + verify) and challenge/verify are **application flows** performed by the app via the JS SDK once A1 is enabled.
- **Setting name:** n/a (API-driven).
- **Why:** they are `mfa.enroll` / `mfa.challenge` / `mfa.verify` calls, not dashboard toggles.
- **Mandatory for Stage 1b:** the **capability** is (via A1). No extra dashboard action.
- **Expected behaviour:** enrollment shows a QR + manual key; a valid 6-digit code activates the factor; on later logins the app requires a code to reach AAL2.

### A4. 🟡 Leaked-password protection
- **Path:** Authentication → **Policies** ⚠️ VERIFY LABEL (may be **Authentication → Attack Protection** or **Authentication → Sign In / Providers → Password**).
- **Setting name:** **"Prevent use of leaked passwords"** / **"Leaked password protection"** (HaveIBeenPwned).
- **Required value:** Enabled.
- **Why:** blocks known-breached passwords at the Supabase layer (defence in depth alongside the app-level HIBP screen already shipped).
- **Mandatory for Stage 1b:** **No** (recommended). The app already screens passwords via HIBP k-anonymity, so Stage 1b is not blocked if this is off.
- **Plan:** Commonly a **paid (Pro+)** feature — ⚠️ VERIFY on your plan.
- **If unavailable:** rely on the shipped app-level screen (`services/compromised_password.py`); no action needed.
- **Expected behaviour after enabling:** Supabase rejects sign-up/password-update with a known-breached password.

> **Password length / composition (informational):** Authentication → **Policies** → **"Minimum password length"** and **"Password Requirements"** ⚠️ VERIFY LABEL. Per the locked decision (Modern policy), set **Minimum length = 14** and **Password Requirements = "No required characters"** (do **not** enable composition). The app enforces the same. Not blocking for Stage 1b.

### A5. 🟡 Email verification
- **Path:** Authentication → **Sign In / Providers → Email** ⚠️ VERIFY LABEL (may be **Authentication → Providers → Email**).
- **Setting name:** **"Confirm email"** / **"Enable email confirmations"**.
- **Required value:** Enabled (recommended).
- **Why:** the Account Security Score awards points for a verified contact email; confirmation reduces account-takeover risk.
- **Mandatory for Stage 1b:** **No.**
- **Plan:** All plans.
- **Expected behaviour:** new users must confirm their email before/at first login (existing flow already uses `auth-confirm`).

### A6. 🟡 Refresh-token rotation / reuse
- **Path:** Authentication → **Sessions** ⚠️ VERIFY LABEL (may be **Authentication → Advanced / Settings**).
- **Setting name:** **"Detect and revoke potentially compromised refresh tokens"** (refresh-token **rotation** + **reuse interval**).
- **Required value:** **Enabled** (this is the Supabase default).
- **Why:** ensures the AAL2 access token that MFA produces refreshes cleanly and that stolen refresh tokens are revocable.
- **Mandatory for Stage 1b:** **No** (default-on is sufficient). Do not disable it.
- **Plan:** All plans (default).
- **Expected behaviour:** normal session refresh; reused/old refresh tokens are rejected.

### A7. ⚪ Session settings (time-box / inactivity / single session)
- **Path:** Authentication → **Sessions** ⚠️ VERIFY LABEL.
- **Setting name:** **"Time-box user sessions"**, **"Inactivity timeout"**, **"Single session per user"**.
- **Required value for Stage 1b:** **leave as-is.**
- **Why:** role-specific idle/absolute timeouts are enforced at the **application layer** in **Stage 2**, not here.
- **Mandatory for Stage 1b:** **No** — do not change now.
- **Plan:** These are **Pro+** features. Not required for 1b.

### A8. 🔴 Site URL
- **Path:** Authentication → **URL Configuration**.
- **Setting name:** **"Site URL"**.
- **Required value:** `https://app.secureit360.co`
- **Why:** default redirect target for email/confirmation links; must match the app's canonical host.
- **Mandatory for Stage 1b:** **Yes.**
- **Plan:** All plans.
- **Expected behaviour:** confirmation/reset links resolve to the app.

### A9. 🔴 Redirect URLs (allow-list)
- **Path:** Authentication → **URL Configuration → Redirect URLs**.
- **Setting name:** **"Redirect URLs"** (add each, one per line).
- **Required values (all three):**
  ```
  https://app.secureit360.co/**
  https://secureit360-frontend.vercel.app/**
  http://localhost:3000/**
  ```
- **Why:** the JS SDK / OAuth / email flows only redirect to allow-listed URLs; missing entries cause "redirect not allowed" errors.
- **Mandatory for Stage 1b:** **Yes.**
- **Plan:** All plans.
- **Expected behaviour:** production, Vercel preview, and local dev can all complete auth redirects.

> 🚫 Do **not** enter any service-role key, JWT secret, DB password, or `SUPABASE_PAT` anywhere in Auth configuration or this checklist.

---

## B. Vercel environment variables

**Path:** Vercel Dashboard → project **`secureit360-frontend`** → **Settings → Environment Variables**.

### B1. 🔴🔑 `NEXT_PUBLIC_SUPABASE_URL`
- **Where to find the value in Supabase:** Project → **Project Settings → API → "Project URL"** (⚠️ VERIFY LABEL; may be under **Settings → API** or **Settings → Data API**).
- **Value:** `https://donrxbkxodblikddtqjz.supabase.co` (public; must match `SUPABASE_URL` in the backend).
- **Exact Vercel variable name:** `NEXT_PUBLIC_SUPABASE_URL`
- **Environments:** ✅ Production ✅ Preview ✅ Development (**all three**).
- **Browser-safe:** **Yes** (public project URL).
- **Redeploy required:** **Yes** (see D5).

### B2. 🔴🔑 `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Where to find the value in Supabase:** Project → **Project Settings → API → "Project API keys" → the `anon` `public` key** (⚠️ VERIFY LABEL). **Copy the `anon`/`public` key — NOT `service_role`.**
- **Value:** copy it from the dashboard directly into Vercel — **do not paste it into any file, doc, chat, or commit.**
- **Exact Vercel variable name:** `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Environments:** ✅ Production ✅ Preview ✅ Development (**all three**).
- **Browser-safe:** **Yes** — the anon key is public by design; access is enforced by Row-Level Security. It is safe in the browser bundle.
- **🚫 Service-role key:** the **`service_role`** key must **NEVER** be added to Vercel, any `NEXT_PUBLIC_*` variable, the browser, logs, or source maps. It bypasses RLS and stays server-side only (Railway backend).
- **Redeploy required:** **Yes** (see D5).

### B3. Confirm existing: `NEXT_PUBLIC_API_URL`
- **Exact name:** `NEXT_PUBLIC_API_URL`
- **Expected production value:** `https://api.secureit360.co` (the intended API host → Railway backend).
- ⚠️ **VERIFY:** confirm this value resolves to the **deployed Railway backend the app is actually using**. If `api.secureit360.co` is not yet attached to the Railway service, set it to the working Railway URL (`https://secureit360-production.up.railway.app`) until the custom domain is confirmed. Must be present in Production (and Preview/Development as appropriate).

### How to verify a variable is present without exposing its value
- **Dashboard:** Settings → Environment Variables lists each **name**, the **environments** it applies to, and a **masked** value — confirm presence without revealing the secret.
- **CLI (optional):** `vercel env ls` prints variable **names + environments only** (not values). Do **not** run `vercel env pull` into a shared location.

---

## C. Safe completion check

| Check | Expected result | Completed |
|---|---|---|
| TOTP MFA enabled | Native enroll/challenge available (A1) | [ ] |
| Leaked-password protection enabled | Compromised passwords rejected (A4; app-level screen already covers this if plan-gated) | [ ] |
| Site URL correct | `https://app.secureit360.co` (A8) | [ ] |
| Redirect URLs correct | Production + Vercel preview + localhost (A9) | [ ] |
| `NEXT_PUBLIC_SUPABASE_URL` added | All environments (B1) | [ ] |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` added | All environments (B2) | [ ] |
| `NEXT_PUBLIC_API_URL` confirmed | Correct Railway/API URL (B3) | [ ] |
| No service-role key in Vercel | Confirmed — anon key only | [ ] |
| Vercel redeployed | New env loaded (D5) | [ ] |

---

## D. Final output

### 1. Exact Supabase steps
1. Authentication → **URL Configuration**: set **Site URL** = `https://app.secureit360.co`; add the three **Redirect URLs** (A9). Save.
2. Authentication → **Multi-Factor Authentication** ⚠️: ensure **TOTP / Authenticator app** is enabled (A1). Save.
3. *(Recommended)* Authentication → **Policies** ⚠️: set **Minimum password length = 14**, **Password Requirements = none**, enable **Leaked-password protection** if your plan offers it (A4).
4. *(Recommended)* Authentication → **Sign In / Providers → Email** ⚠️: ensure **Confirm email** is enabled (A5).
5. *(Confirm only)* Authentication → **Sessions** ⚠️: **Refresh-token rotation** on (default); leave time-box/inactivity as-is (A6/A7).

### 2. Exact Vercel steps
1. Project `secureit360-frontend` → **Settings → Environment Variables**.
2. Add `NEXT_PUBLIC_SUPABASE_URL` (B1) → tick **Production, Preview, Development**.
3. Add `NEXT_PUBLIC_SUPABASE_ANON_KEY` (B2, `anon`/`public` key) → tick **Production, Preview, Development**.
4. Confirm `NEXT_PUBLIC_API_URL` (B3).
5. **Redeploy** (D5).

### 3. Values the operator must COPY
- `NEXT_PUBLIC_SUPABASE_URL` = `https://donrxbkxodblikddtqjz.supabase.co` (public).
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` = the **`anon` / `public`** key from Supabase → Project Settings → API (copy dashboard → Vercel directly; do not paste into files).

### 4. Values the operator must NEVER copy 🚫
- The Supabase **`service_role`** key.
- The Supabase **JWT secret**.
- The **database password**.
- `SUPABASE_PAT` (personal access token) or any backend `.env` secret.
- None of these belong in Vercel, any `NEXT_PUBLIC_*` var, the browser, logs, or this document.

### 5. Required redeploy step (D5)
`NEXT_PUBLIC_*` variables are inlined at **build time**, so after adding/changing them you must **redeploy** for the browser to pick them up:
- Vercel Dashboard → **Deployments** → latest Production deployment → **⋯ → Redeploy** (or push a commit to `main`).
- After redeploy, the built app exposes `NEXT_PUBLIC_SUPABASE_URL` / `_ANON_KEY` to the browser SDK.

### 6. How to confirm Stage 1b prerequisites are ready
- All 9 rows in **§C** ticked.
- In the running app (browser devtools console on `app.secureit360.co` after redeploy): `window` has access to the Supabase config via the built bundle (no error), and — once the engineer wires the SDK — `supabase.auth.mfa.enroll({factorType:'totp'})` returns a QR/secret rather than an "MFA disabled" or "missing config" error. (This last check is performed by the engineer during Stage 1b, not the operator.)
- The `service_role` key appears **nowhere** in Vercel env or the browser bundle.

### 7. One-line message to send back when done
> **"Stage 1b prereqs done: TOTP MFA enabled, Site + Redirect URLs set, NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY (anon only) added to all Vercel envs, NEXT_PUBLIC_API_URL confirmed, no service-role key in Vercel, redeployed."**

---

*Stage 1b is not implemented in this document. No code, Supabase, or Vercel changes were made — this is an operator checklist only.*
