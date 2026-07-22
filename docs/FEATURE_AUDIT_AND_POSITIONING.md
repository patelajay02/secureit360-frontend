# SecureIT360 — Feature Audit & Commercial Positioning

**Date:** 2026-07-21
**Method:** Direct inspection of frontend (`app/`, `components/`, `lib/`), backend (`backend/routes`, `backend/services`, `backend/saas_connectors`), database migrations (`supabase/migrations`), scheduler/jobs, and integrations. Evidence is cited as `file:line`. No code, data, or deployment was changed.
**Markets in scope:** Australia, New Zealand, UAE, India.

> **Repo state note:** the working tree currently contains uncommitted Phase 0 security-remediation changes (audit logging, DB-backed scan-job locking, SSRF guard, secured admin endpoints, scheduler health/test endpoints). Where these affect a feature claim they are marked **[Phase 0, backend-only]**. They add hardening, not customer-facing features.

---

## Executive answer (the positioning question)

- **Is "AI-powered" justified today? → No.** The entire codebase contains **one** LLM call: generating a SaaS-connector *setup wizard* with Anthropic Claude (`backend/saas_connectors/ai_recipe_generator.py:26-28,112-142`), surfaced in the UI once as "build a setup guide … using AI" (`components/saas/AppCatalog.tsx:90`). Core scanning, scoring, "voice guide" remediation, auto-fix, and compliance mapping are **deterministic, scripted, or static** (evidence throughout §3). There is no AI security analysis, AI findings summarisation, AI remediation, AI risk prioritisation, AI compliance mapping, or AI reporting.
- **Is "Cyber Risk & Compliance Platform" justified today? → "Cyber Risk" yes; "Compliance" only as *regulatory mapping*, not compliance management.** There is no control library, gap assessment, risk register, Statement of Applicability, evidence/policy management, or any downloadable compliance report (§4). Compliance = hardcoded regulation strings on findings + a generic severity heuristic that scores ISO 27001 / SOC 2 / PCI / NIST with *identical* math (`backend/routes/dashboard.py:389-449`).
- **Most accurate category today:** a **Continuous Cyber Risk Monitoring platform with regulatory mapping**, for SMEs in AU / NZ / UAE / India. Recommended headline/subtitle in §10–§11.

---

## 1. Complete Customer-Facing Feature Inventory

Backend base URL: `NEXT_PUBLIC_API_URL` via `lib/auth.js` (`authFetch`/`publicFetch`). Roles come from `tenant_users.role` ∈ {owner, admin, member}; platform admin is a separate table **[Phase 0]**.

### Authentication & onboarding
| Feature | Route | Backend | Tables | Access | Status | Evidence |
|---|---|---|---|---|---|---|
| Register (email=domain match, reCAPTCHA field) | `/signup` | `POST /auth/register` | tenants, tenant_users, domains | Public | Working (reCAPTCHA collected, **not verified server-side**) | `app/signup/page.js:103`, `backend/routes/auth.py:31-135` |
| Login (+ status gates) | `/login` | `POST /auth/login` | tenant_users, tenants | Public | Working | `app/login/page.js:29`, `auth.py:146-217` |
| Email verification | `/auth-confirm` | `POST /auth/verify-email` | tenants | Token-holder | Working (now token-derived **[Phase 0]**) | `app/auth-confirm/page.js:24` |
| Forgot password | `/login` | `POST /auth/forgot-password` | — | Public | Wired | `app/login/page.js:67` |
| Token refresh / idle logout | (all) | `POST /auth/refresh` | — | All | Working | `lib/auth.js`, `components/ui/SessionTimeout.js:41` |

### Organisation / tenant management
| Company profile + logo | `/settings` (Profile) | `GET/PATCH /tenants/me`, `POST/DELETE /tenants/logo` | tenants, storage `logos` | owner/admin | Working | `app/settings/page.js:225,291,318`, `backend/routes/tenants.py` |
| Compliance framework selection | `/settings` | `PATCH /tenants/me` | tenants.frameworks | owner/admin | Working (config only — see §4) | `app/settings/page.js:510-558` |

### User & role management
| Team list / invite | `/settings` (Team) | `GET /auth/users`, `POST /auth/invite` | tenant_users | owner/admin invite | Working (invite = email only, no acceptance flow) | `auth.py:263-341`, `app/settings/page.js:339` |
| Delete user | (no UI) | `DELETE /auth/users/{id}` | via RPC | self/tenant-admin/platform-admin **[Phase 0]** | Working | `auth.py:251-306` |

### Asset & domain management
| Add / list / delete domain, DNS-TXT verify | `/dashboard/scanning`, `/settings` | `POST/GET/DELETE /domains`, `POST /domains/verify` | domains, hibp_breach_watch | owner/admin | Working (verify required before scan **[Phase 0]**) | `backend/routes/domains.py`, `app/dashboard/scanning/page.js:82-101` |

### Security scanning — see full inventory in §2
7 engines exposed in UI (`app/dashboard/scanning/page.js:7-15`), triggered per-engine or as "full scan".

### Continuous monitoring — see §5
Daily cron scan + 5-minute HIBP breach watch.

### Vulnerability & findings management
| Findings dashboard, severity, carry-over "not fixed since last scan", auto-fix, voice guide, "connect to expert" | `/dashboard` | `GET /dashboard/`, `POST /scans/auto-fix/{id}` | findings, scan_engine_results | All tenant users | Working; **auto-fix has no registered handlers today** (`backend/services/auto_fix.py`), voice guide is static (§3) | `app/dashboard/page.tsx:504,539-559`, `components/findings/FindingActionsBar.tsx` |

### Threat intelligence / dark web / email / DNS / website / SSL / cloud / SaaS
Covered in §2. Threat-intel (`/threat-intel`), dark web (HIBP), email (SPF/DMARC), website (SSL + headers), cloud (S3 guessing), MS365/Google Workspace posture, SaaS posture (Xero/Zoho).

### Compliance & risk — see §4
Regulatory mapping + three heuristic scores (Ransom Risk, Governance, Director Liability).

### Executive & board reporting — see §6
Weekly director email, monthly report email. **No PDF/CSV/board document.**

### Alerts & notifications
| Critical-finding alert, new-breach alert, weekly/monthly emails | — | SendGrid via `backend/services/email_service.py` | findings, hibp_breach_alerts | Owner/director email | Working (real per-tenant data; caveats §6) | `email_service.py`, `scheduler.py`, `hibp_watch.py:276` |

### Billing & subscriptions
| Plans, checkout, portal, webhook | `/pricing`, `/settings` (Billing) | `GET /billing/plans`, `POST /billing/checkout/{plan}`, `POST /billing/portal`, `POST /billing/webhook` | subscriptions, tenants | owner/admin | Working; **webhook secret absent from env → real webhooks rejected until set** | `backend/routes/billing.py`, `app/pricing/page.js:95` |

### Administration
| Platform admin console (list/suspend/comp/extend/create/delete tenants) | `/admin` | `/auth/admin/*` | tenants, tenant_users | Platform admin **[Phase 0]** (was unauth + hardcoded client password) | Working; **frontend still ships `ADMIN_PASSWORD` gate pending Phase 0 frontend fix** | `app/admin/page.tsx:4,35-147`, `auth.py:346-560` |

### Audit logging **[Phase 0, backend-only]**
| Privileged-action audit trail | (no UI) | writes on admin/auth/scheduler actions | `audit_log` | — | Backend only, no customer UI | `backend/services/audit.py`, migration `20260721_phase0_security_foundation.sql` |

### Settings / Support / Integrations
| Settings tabs (Profile/Team/Domains/Billing/Integrations), MS365 + Google OAuth connect/scan, SaaS catalog + guided wizard | `/settings`, `/saas/catalog`, `/saas/connections` | `/integrations/*`, `/saas/*` | integrations, saas_connections, saas_findings, saas_app_registry | owner/admin (SaaS = per-user) | Working | `app/settings/page.js`, `app/saas/*` |
| Support | BottomNav / findings | `mailto:` only | — | All | **mailto, not a ticketing system** | `components/ui/BottomNav.js:48`, `components/findings/FindingActionsBar.tsx:33` |

### AI features
| SaaS connector setup-wizard generation | `/saas/catalog` | `POST /saas/generate-recipe` → Claude | saas_app_registry | Authenticated | Working (beta; caches `verified=false`) | `app/saas/catalog/page.tsx:87`, `ai_recipe_generator.py` |

**Inconsistencies found:** marketing says "6 scan engines" but code exposes 7 (`app/dashboard/scanning/page.js:14`); `UpgradePrompt.js` (unused/dead) lists 4; support email split between `governance@` and `support@`; two root layouts (`app/layout.js` vs `app/layout.tsx`) with different taglines; `AE` vs `UAE` country-code mismatch mis-prices UAE users to USD (`app/pricing/page.js:11,76`).

---

## 2. Complete Scan Inventory

Classification key: **A** real, **B** implemented-but-shallow, **C** partial, **D** UI-only/placeholder, **E** absent. **No subprocess/shell, no CLI security tools anywhere** (grep: no `nmap`/`nuclei`/`zap`/`nikto`/`testssl`/`openssl`/`selenium`/`playwright`).

| Scan | Class | What it actually does | Tools/APIs | Scheduling | Evidence |
|---|---|---|---|---|---|
| Website / SSL | **B** | SSL **cert expiry only** + presence of 4 security headers (XFO/XCTO/HSTS/CSP), flags if >2 missing | stdlib `ssl`/socket, `httpx` | Daily (full) + manual | `backend/services/website_scan.py:51-158` |
| Certificate expiry | **B** | Days-to-expiry from peer cert; no chain/protocol/cipher analysis | stdlib ssl | as above | `website_scan.py:51-66` |
| Security headers | **B** | Checks 4 headers only | httpx | as above | `website_scan.py:69-86` |
| Email — SPF | **B** | DNS-over-HTTPS TXT lookup for `v=spf1` | Google DoH | Daily + manual | `backend/services/email_scan.py:68-77` |
| Email — DMARC | **B** | DoH TXT for `v=DMARC1` | Google DoH | as above | `email_scan.py:57-66` |
| Email — **DKIM** | **E** | Declared in results dict + header comment, **never implemented** | — | — | `email_scan.py:2,52` |
| DNS scanning | **B** | Only SPF/DMARC TXT (email) + ownership TXT verify; no zone/records enumeration | DoH, dnspython | manual | `email_scan.py`, `domains.py:114` |
| Port / exposed-service | **B (passive)** | **Passive Shodan host lookup**; flags dangerous ports (3389/445/23/22/21) from Shodan's last-seen data. **No active scan / nmap** | `shodan` SDK | Daily + manual | `backend/services/network_scan.py:125-165` |
| Public IP scanning | **B** | IP only used to key Shodan/AbuseIPDB/OTX; no active IP scan | — | — | `network_scan.py`, `threat_intel_scan.py` |
| Technology detection | **B** | `Server` / `X-Powered-By` header string parse | httpx | Daily + manual | `backend/services/device_scan.py:48-107` |
| CVE detection | **E** | Only "PHP<8" + "Apache banner" heuristics; **no CVE/NVD/CVSS/CPE** (grep: none) | — | — | `device_scan.py`; grep confirms absence |
| Cloud storage exposure | **B** | Guesses 12 bucket names from domain, GETs `*.s3.amazonaws.com`, 200 ⇒ "public". **AWS S3 only** | httpx | Daily + manual | `backend/services/cloud_scan.py:48-77` |
| Malware / blacklist | **A (passive)** | VirusTotal + AbuseIPDB + URLScan + OTX reputation lookups | 4 REST APIs (key-gated) | Daily (enrichment) + manual | `backend/services/threat_intel_scan.py:96-265` |
| Typosquatting | **B** | Generates ≤25 look-alike domains, flags those that **resolve in DNS** (no WHOIS) | getaddrinfo | as above | `threat_intel_scan.py:51-91,270-296` |
| Dark web / breach (batch) | **A** | HIBP `breacheddomain` per scan | HIBP v3 (key-gated; key currently empty) | Daily + manual | `backend/services/darkweb_scan.py:82-155` |
| **HIBP real-time breach watch** | **A** | Polls HIBP every 5 min per verified domain; inserts findings + emails director | HIBP v3 | **Interval 5 min** | `backend/services/hibp_watch.py:300`, `main.py:54-60` |
| Threat intelligence | **A/B** | Concurrent AbuseIPDB/VT/URLScan/OTX/typosquat/HIBP against tenant's own domain | as above | Daily (enrichment) + manual | `threat_intel_scan.py:350-388` |
| Microsoft 365 posture | **A** | Real Graph API: MFA, inactive 90d, admin sprawl, external sharing (sampled 5 sites×3 drives×50) | MS Graph OAuth | **Manual only** | `backend/services/ms365_scan.py:111-324` |
| Google Workspace posture | **A** | Real Admin/Drive API: 2SV, inactive, admin sprawl, public Drive sharing. **Dedup bug (duplicates each run); governance_gap stored as boolean** | Google APIs | **Manual only** | `backend/services/google_workspace_scan.py:94-302` |
| SaaS posture | **C** | Framework + Xero & Zoho providers only; checks admin-ratio/MFA/dormant. `public_sharing`/`audit_log` checks exist but **no provider feeds them**. No dedup | Xero/Zoho OAuth | **Manual only** | `backend/saas_connectors/scan_runner.py:77`, `generic_checks.py:163-169`, `providers/{xero,zoho}.py` |
| Device scanning (endpoints) | **D/E** | "Device scan" only inspects the *website's* HTTP headers; scans no actual devices | httpx | Daily + manual | `device_scan.py:110-167` |
| OWASP checks | **E** | none | — | — | grep: none |
| API-security scanning | **E** | none | — | — | grep: none |
| Vendor / supplier risk | **E** | none (typosquat/threat-intel target the tenant's own domain) | — | — | grep: none |
| Web app vuln scanning (nuclei/ZAP/nikto) | **E** | none | — | — | grep: none |
| TLS deep analysis (testssl) | **E** | none | — | — | grep: none |

**Net:** genuinely-real scans = MS365 posture, Google Workspace posture, SaaS posture (Xero/Zoho), threat-intel reputation, HIBP dark-web/real-time. Everything "website/port/SSL/CVE/device/cloud" is **shallow heuristic**. DKIM, CVE, OWASP, API-security, vendor risk, active port scanning are **absent**.

---

## 3. AI Capability Audit

**Confirmed AI capabilities: exactly one.**

| Attribute | Finding |
|---|---|
| User-facing feature | SaaS connector **setup-wizard generation** ("build a setup guide … using AI", `components/saas/AppCatalog.tsx:90`) |
| Provider / model | **Anthropic Claude** `claude-sonnet-4-20250514` via `https://api.anthropic.com/v1/messages` (`ai_recipe_generator.py:26-28`) |
| Trigger | User searches the SaaS catalog for an app not in `saas_app_registry` → `POST /saas/generate-recipe` (`app/saas/catalog/page.tsx:87`, `backend/routes/saas.py:232`) |
| Inputs sent to AI | The app **name** only (`_user_prompt`, `ai_recipe_generator.py:43-55`). **No tenant data, credentials, or findings.** |
| Output | JSON "wizard recipe" (connection steps), strictly validated, cached with `verified=false` (`ai_recipe_generator.py:80-215`) |
| Shown in UI | Yes — as a guided setup wizard, flagged beta/unverified (`app/saas/catalog/page.tsx:159-173`) |
| Production-ready | Partially — works, validated, poisoning-protected; needs `ANTHROPIC_API_KEY` (returns None/"email us" if unset) |
| Privacy / injection risk | Low — only an app name leaves the system; output is schema-validated, not executed. Auto-`verified=true` on first successful scan is a minor trust concern (`scan_runner.py:148-158`) |
| Cost / rate-limit controls | None specific (no per-tenant cap); one call per catalog miss |

**Deterministic features that use "intelligent-sounding" words but are NOT AI:**
- **"Voice-guided fix walkthroughs"** — 100% hand-authored static scripts (`VOICE_GUIDE_STEPS`, `app/dashboard/page.tsx:8-97`) read aloud by the browser's `speechSynthesis` (`:293-320`). No model call.
- **Auto-fix / "fixed automatically"** — deterministic route with **no handlers registered today** (`backend/routes/scans.py` auto-fix, `backend/services/auto_fix.py`).
- **Ransom/Governance/Director-Liability scores** — arithmetic/keyword heuristics (§4).
- **"Regulatory compliance mapping"** — static dictionary lookups (§4).
- **BreachWatch "real-time"** — HIBP polling every 5 min.

**AI wording issues:** the one UI AI claim (`AppCatalog.tsx:90`) is *accurate and narrow*. There is **no "AI-powered" anywhere** in the product. No unused AI code, no hardcoded "AI" responses masquerading as generation. Risk is the reverse: marketing must not *add* AI claims the product can't back.

---

## 4. Compliance & Risk-Management Audit

**Mechanism = static regulation strings + heuristic scores. No compliance *workflows*.** Three overlapping mapper modules, all dictionary lookups: `backend/services/regulatory_mapper.py:3-66`, `backend/services/governance_mapper.py:6-54`, `backend/saas_connectors/governance_mapper.py:17-99`.

| Item | Status | Evidence |
|---|---|---|
| ISO 27001 | **Report-only label + generic heuristic** | strings `regulatory_mapper.py:43,59-60`; score = generic `score_for_engines(_ALL_ENGINES)` `dashboard.py:418-439`. No Annex A control list, no SoA |
| NIST CSF | **Label key only** | `dashboard.py:394` — identical generic heuristic |
| CIS Controls | **Absent** | no match anywhere |
| Essential Eight (ASD/ACSC) | **Label + heuristic** | strings `regulatory_mapper.py:15,23,40`; **no ML1/ML2/ML3 maturity model** |
| SOC 2 | **Label key only** | `dashboard.py:393` (same math as ISO/PCI/NIST) |
| PCI DSS | **Label key only** | `dashboard.py:392` |
| GDPR | **Absent from scoring dict** (settings UI offers it) | `app/settings/page.js:22`; not in `dashboard.py` framework dict |
| AU Privacy Act / Cyber Security Act 2024 | **Label + static penalty text** | `regulatory_mapper.py:8,33`; `dashboard.py:203-224` |
| NZ Privacy Act 2020 / Amendment 2025 | **Label + heuristic + static text** | `regulatory_mapper.py:7,32`; `dashboard.py:347-351` |
| UAE PDPL 2021 / NESA / DIFC / ADGM | **Label only** (PDPL heuristic-scored) | `regulatory_mapper.py:101-108`; `dashboard.py:256,422` |
| India DPDP 2023 / CERT-In / RBI | **Label + heuristic** (RBI unused) | `regulatory_mapper.py:84-92`; `dashboard.py:303-305` |
| Control library / control status | **Absent** | — |
| Gap assessment workflow | **Absent** | "compliance_gaps" = findings + labels (`regulatory_mapper.py:144-161`) |
| Risk register / treatment plan / SoA | **Absent** | grep: no matches |
| Internal audit / management review | **Absent** | grep: no matches (`log_audit` is telemetry) |
| Supplier / vendor risk | **Absent** | — |
| Certification readiness | **Advertised, not built** | "ISO 27001 readiness report" `app/pricing/page.js:56` has no generator |

**Scores (`backend/services/score_calculator.py`):**
- **Ransom Risk** = sum of finding `score_impact`, clamped 0–100 (`:28-44`; the "start at 100 and deduct" comment is dead code — it's additive). Static $ / downtime bands by tier (`:55-72`).
- **Governance** = % of 8 hardcoded domains with no keyword-matched gap (`:118-158`). (Dashboard uses a *different* 100-minus-severity formula, `dashboard.py:156-166`.)
- **Director Liability** = keyword point-tally over finding titles (`:194-215`); **never actually populated in the weekly email** (always passed `None`, `scheduler.py:186`).

**Verdict:** SecureIT360 performs **regulatory *mapping and awareness*, not compliance *management*.** It should **not** be called a "compliance platform" without qualification.

---

## 5. Continuous Monitoring Audit

| Capability | Exists today | Evidence |
|---|---|---|
| Daily scheduler | ✅ Cron 06:00 NZ | `backend/services/scheduler.py:261-267` |
| DB-backed job lock / duplicate prevention | ✅ **[Phase 0]** unique `(tenant,domain,type,day)` | `services/scan_jobs.py:47-79`, migration |
| Retries | ❌ (single attempt) | `scan_jobs.py` |
| Timeout handling | ✅ **[Phase 0]** per-scan `asyncio.wait_for` | `scan_jobs.py` |
| Job status (queued/running/completed/failed/timed_out/skipped_duplicate) | ✅ **[Phase 0]** | `scan_jobs` table |
| Tenant/target selection (verified only) | ✅ **[Phase 0]** | `scan_jobs.py` `_pick_verified_target` |
| Concurrency limit | ✅ **[Phase 0]** semaphore | `scheduler.py` |
| New-finding detection & alert | ✅ diff vs prev critical findings | `scan_jobs.py`, `scheduler.py` |
| Resolved-finding detection | ⚠️ carry-over "not fixed since last scan" shown in UI; no explicit "resolved" event | `app/dashboard/page.tsx:681,980-982` |
| Recurring breach checks | ✅ HIBP every 5 min | `hibp_watch.py`, `main.py:54` |
| Recurring cloud/SaaS posture (MS365/Google/SaaS) | ❌ **manual only** — not scheduled | `routes/integrations.py:183`, `routes/google_workspace.py:201`, `routes/saas.py:272` |
| Historical results / trend | ⚠️ weekly email compares last two scans; no trend charts in UI | `scheduler.py:148-167` |

**Truth:** continuous monitoring is **real for website/email/network/threat-intel (daily) and breach (5-min)**, but **cloud & SaaS posture are not continuous** (button-triggered). "Continuous monitoring" is defensible if scoped to daily scans + breach watch; do not imply continuous cloud/SaaS posture.

---

## 6. Reporting & Executive Intelligence

| Report | Status | Evidence |
|---|---|---|
| Technical scan results (dashboard) | Real, customer-facing | `app/dashboard/page.tsx`, `GET /dashboard/` |
| Weekly director email | Real per-tenant data, **but Director-Liability tile always blank** and scores fall back to 50 | `email_service.py:319-539`, `scheduler.py:142-188` |
| Monthly report email | Real (3 numbers: score, total, fixed) | `email_service.py:544-613` |
| Critical alert / new-breach email | Real per-event | `email_service.py:154-253`, `hibp_watch.py:276` |
| JSON "compliance report" | Report-only JSON in scan response, **not persisted, not a document** | `regulatory_mapper.py:142-168`, `full_scan.py:99` |
| PDF export | **Absent** (no reportlab/weasyprint) | grep: none |
| CSV / XLSX export | **Absent** | grep: none |
| Board report / exec-summary document | **Absent** | grep: none |
| Director-liability report (advertised) | **Absent generator** | `app/pricing/page.js:40` |
| ISO 27001 readiness / Essential Eight maturity reports (advertised) | **Absent generator** | `app/pricing/page.js:56-57` |
| Scheduled reports | Real as **emails**, not documents | `scheduler.py:270-285` |
| Customer-branded reports | Logo upload exists; **no branded report output** | `tenants.py`, no report code |

**Gap:** four report types are sold in pricing (§8) with **no generation code**. This is the single biggest advertised-vs-built discrepancy.

---

## 7. Feature Wiring & Maturity

- **Backend features with no UI:** `audit_log` **[Phase 0]**; scheduler health/test endpoints **[Phase 0]**; auto-fix route exists but no handlers (`auto_fix.py`).
- **UI advertised, backend missing:** compliance/ISO/Essential-Eight/director-evidence **reports** (§6); reCAPTCHA collected but never verified (`auth.py:22`).
- **Dead/placeholder:** `components/ui/UpgradePrompt.js` (no importer); landing mobile menu `#pricing` anchor with no matching section (`app/page.tsx:35`); `dashboard_backup.txt` stale copy at repo root.
- **Bugs affecting feature quality:** Google Workspace findings duplicate every run (no dedup) + `governance_gap` stored as boolean (`google_workspace_scan.py:158,296-302`); SaaS findings no dedup (`scan_runner.py:130-142`); director-liability never sent in weekly email (`scheduler.py:186`); `AE`/`UAE` code mismatch mis-prices UAE users (`app/pricing/page.js:11,76`).
- **Duplicate frontends / layouts:** two root layouts with different taglines (`app/layout.js` vs `app/layout.tsx`); dashboard nav duplicated inline (`DashboardNavbar.tsx:1-6`).
- **Missing env vars that break features:** `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_AZURE_CLIENT_ID`, `HIBP_API_KEY`/`SHODAN_API_KEY` (empty → breach/port scans no-op), `ANTHROPIC_API_KEY` (AI wizard).

---

## 8. Commercial Feature Matrix

| Module | Feature | Implemented? | Customer-visible? | Production-ready? | Commercially valuable? | Differentiator? | Marketing-claim-safe? | Evidence |
|---|---|---|---|---|---|---|---|---|
| Onboarding | Register/verify/login | Yes | Yes | Yes | Yes | No | Yes | `auth.py`, `app/signup` |
| Domains | Add + DNS-verify | Yes | Yes | Yes | Yes | No | Yes | `domains.py` |
| Scanning | Daily multi-engine scan | Yes | Yes | Mostly (shallow) | Yes | Partly | Yes ("daily automated scanning") | `scheduler.py`, `scan_jobs.py` |
| Breach | HIBP real-time watch | Yes | Yes | Yes | **Yes** | **Yes** | Yes ("real-time breach monitoring") | `hibp_watch.py` |
| Email sec | SPF/DMARC | Yes | Yes | Yes | Yes | No | Yes (omit DKIM) | `email_scan.py` |
| Website/SSL | Cert expiry + headers | Shallow | Yes | Yes | Yes | No | Cautiously | `website_scan.py` |
| Port | Passive Shodan | Shallow | Yes | Yes | Medium | No | Say "exposure check", not "port scan" | `network_scan.py` |
| Threat intel | Reputation lookups | Yes | Yes | Yes | Yes | Partly | Yes | `threat_intel_scan.py` |
| Cloud posture | MS365 / Google Workspace | Yes | Yes | Yes (GWS dedup bug) | **Yes** | **Yes** | Yes (say "on-demand") | `ms365_scan.py`, `google_workspace_scan.py` |
| SaaS posture | Xero/Zoho | Partial | Yes | Beta | Yes | **Yes** | "Xero & Zoho" only | `scan_runner.py` |
| Risk scoring | Ransom/Governance/Director | Heuristic | Yes | Yes | **Yes** | **Yes** (SMB-friendly framing) | Yes, as "risk score" (not "assessment") | `score_calculator.py` |
| Compliance | Regulatory mapping | Static | Yes | Yes | Yes | Partly | "regulatory mapping/awareness" only | `regulatory_mapper.py` |
| Reporting | Weekly/monthly emails | Yes | Yes | Yes (caveats) | Yes | No | Yes | `email_service.py` |
| Reporting | PDF/board/compliance docs | **No** | Advertised | No | Yes | Would be | **No — do not claim** | grep: none |
| Remediation | Voice guide | Static scripts | Yes | Yes | Yes | Partly | "guided remediation" (not "AI") | `app/dashboard/page.tsx:8-97` |
| Remediation | Auto-fix | Route only, no handlers | Yes (button) | No | Yes | Would be | **No — do not claim "auto-fix"** | `auto_fix.py` |
| AI | Connector setup wizard | Yes | Yes | Beta | Low-medium | Minor | "AI-assisted setup" only | `ai_recipe_generator.py` |
| Admin | Platform console | Yes | Admin | Yes **[Phase 0]** | Internal | No | n/a | `app/admin` |
| Billing | Stripe | Yes | Yes | Yes (webhook secret needed) | Yes | No | Yes | `billing.py` |

---

## 9. Market Positioning Assessment

Based only on verified features, SecureIT360 today is **B/C leaning**, not E:

- **A. Website security scanner** — understates it (has breach, cloud posture, scoring). ❌ too narrow.
- **B. Cybersecurity monitoring platform** — ✅ **accurate** (daily scans + 5-min breach watch + alerts).
- **C. Cyber risk platform** — ✅ **accurate** (Ransom/Governance/Director scores, penalty framing) — this is the genuine differentiator for SMEs.
- **D. Cyber risk & compliance platform** — ⚠️ only if "compliance" = *regulatory mapping/awareness*; **not** a compliance-management platform.
- **E. AI-powered cyber risk & compliance platform** — ❌ **overclaims on both AI and compliance.**
- **F. More accurate:** **"Continuous Cyber Risk Monitoring & Regulatory-Mapping platform for SMEs."**

**SME suitability by market (verified in code):**
- **Australia** — Strong. Real hardcoded AU framing (Privacy Act 1988, Cyber Security Act 2024, Essential Eight), AUD pricing, Sydney data residency. ✅
- **New Zealand** — Strongest. Default region, NZ Privacy Act 2020 + 2025 Amendment framing, NZD pricing. ✅
- **UAE** — Weak-to-moderate. PDPL/NESA/DIFC are **string labels only**; **privacy policy omits UAE regime** (`app/privacy/page.js:65-67`); data residency is Sydney (sovereignty concern); `AE` code mis-prices to USD. ⚠️
- **India** — Weak-to-moderate. DPDP 2023/CERT-In/RBI are labels; privacy policy omits India; Sydney residency; CERT-In 6-hour breach reporting is *displayed* but not operationalised. ⚠️

Do **not** claim country-specific compliance capability for UAE/India beyond "regulatory mapping."

---

## 10. AI-Wording Recommendation (phrase by phrase)

| Phrase | Accurate now? | Evidence | Overclaim risk | Missing before use |
|---|---|---|---|---|
| "AI-powered Cyber Risk & Compliance Platform" | **No** | 1 peripheral AI feature (`ai_recipe_generator.py`); no compliance mgmt (§4) | **High** (false-advertising exposure in AU/NZ consumer law) | AI in core scan/scoring/remediation **and** real compliance workflows |
| "AI-driven Cyber Risk & Compliance Platform" | **No** | same | **High** | same |
| "Cyber Risk & Compliance Platform with AI-driven guidance" | **No** | "guidance" (voice guide) is static scripts, not AI (`app/dashboard/page.tsx:8-97`) | **High** — implies AI remediation guidance that doesn't exist | AI-generated findings/remediation guidance |
| "Continuous Cyber Risk Monitoring Platform" | **Yes (scoped)** | daily scans + 5-min HIBP (§5) | Low — avoid implying continuous cloud/SaaS posture | (optional) schedule MS365/Google/SaaS |
| "Cyber Risk Intelligence Platform" | **Partly** | threat-intel + scores are real; "intelligence" is defensible, "AI" is not | Medium — some read "intelligence" as AI | Nothing strictly; keep AI out |
| "Cybersecurity Monitoring and Compliance Platform" | **Partly** | monitoring ✅; "compliance" only as mapping (§4) | Medium | qualify "compliance" as regulatory mapping, or add real compliance workflows |

**Direct recommendation:** **Avoid "AI" in the main headline.** If AI is mentioned at all, restrict it to a *feature* label — "AI-assisted connector setup" — never a platform descriptor. Do not use "AI-powered", "AI-driven", or "AI-driven guidance" until AI reaches the core scanning/scoring/remediation.

### Recommended main positioning
> **Main statement:** *SecureIT360 — Continuous Cyber Risk Monitoring for small and medium businesses.*
> **Subtitle:** *Daily automated security scans, real-time breach monitoring, and plain-English risk scores mapped to the laws that apply to your business — across Australia, New Zealand, the UAE and India.*

(If "compliance" must appear commercially: *"Cyber Risk Monitoring & Regulatory Mapping platform"* — accurate; avoid the unqualified word "compliance.")

---

## 11. Website Copy Recommendations

- **Homepage headline:** *Know Your Cyber Risk. Monitored Every Day.*
- **Subtitle:** *Automated security scanning and real-time breach monitoring for SMEs — plain-English findings, risk scores, and the local regulations that apply to your business. No IT team required.*
- **Trust banner:** *Built for organisations across Australia, New Zealand, the UAE and India.* (Do **not** say "global" — international capability is not implemented; data residency is Sydney only.)
- **Three value propositions:**
  1. *See your risk in 60 seconds* — Ransom Risk, Governance and Director-Liability scores in plain English.
  2. *Watched every day* — daily automated scans plus breach monitoring that checks every 5 minutes.
  3. *Mapped to your local laws* — findings tied to AU/NZ/UAE/India regulations so you know what to fix and why.
- **Feature-section headings:** *Daily Security Scanning* · *Real-Time Breach Monitoring* · *Cyber Risk Scores Directors Understand* · *Cloud & SaaS Posture (Microsoft 365, Google Workspace, Xero, Zoho)* · *Regulatory Mapping for Your Region*.
- **AI feature wording (only if used):** *"AI-assisted setup for connecting your business tools."* Nothing more.
- **Continuous-monitoring wording:** *"Daily automated scans and real-time (5-minute) breach monitoring."* Avoid implying continuous cloud/SaaS posture (those are on-demand).
- **Compliance wording:** *"Regulatory mapping and awareness — your findings tied to the laws that apply to you."* Avoid "compliant", "certification", "audit-ready", "ISO 27001 certified".
- **Region wording:** *"Built for Australia, New Zealand, the UAE and India"* with local pricing and local-law mapping. For UAE/India, say *"regulatory mapping"* — not *"compliance"* — until policies/data-residency support those markets.
- **Claims NOT to use yet:** "AI-powered/AI-driven", "compliance platform", "ISO 27001 / Essential Eight readiness reports", "auto-fix / self-healing", "penetration testing / vulnerability scanning" (it's passive/heuristic), "port scanning" (it's passive Shodan), "DKIM", "board reports / PDF reports", "global".

---

## 12. Final Verdict

1. **Confirmed customer-facing feature modules:** ~24 (auth, tenant, users, domains, scanning, continuous monitoring, findings, threat-intel, dark-web, email, DNS, website, SSL, cloud/S3, MS365, Google Workspace, SaaS posture, risk scoring, regulatory mapping, email reporting, alerts, billing, admin, AI setup wizard).
2. **Confirmed scan types:** ~11 distinct (darkweb, email, network/port, website/SSL, device, cloud, threat-intel, MS365, Google Workspace, SaaS, HIBP real-time) — of which **~5 are genuinely real** and the rest shallow heuristics.
3. **Real AI features:** **1** (SaaS connector setup-wizard via Claude).
4. **Real compliance workflows:** **0** (mapping + heuristic scores only; no control library, gap assessment, risk register, SoA, or reports).
5. **Placeholders / incomplete / advertised-not-built:** ~10 (four report types, auto-fix handlers, DKIM, GWS/SaaS dedup, director-liability email, UpgradePrompt, `#pricing` anchor, AE/UAE pricing, dual layouts, reCAPTCHA verification).
6. **Strongest differentiators:** SMB-friendly **Ransom / Governance / Director-Liability risk scoring with local-law framing**; **real-time HIBP breach monitoring**; **Microsoft 365 / Google Workspace / Xero / Zoho posture** in one SMB dashboard.
7. **Biggest gaps:** no real vulnerability scanning (CVE/OWASP/active ports), no compliance-management workflows, no downloadable reports, cloud/SaaS posture not continuous, UAE/India support is labels-only.
8. **Is "AI-powered" justified today?** **No.**
9. **Is "Cyber Risk & Compliance Platform" justified today?** **"Cyber Risk" yes; "Compliance" no** — only "regulatory mapping".
10. **Recommended category / headline / subtitle:**
    - **Category:** *Continuous Cyber Risk Monitoring & Regulatory-Mapping platform for SMEs (AU / NZ / UAE / India).*
    - **Headline:** *Know Your Cyber Risk. Monitored Every Day.*
    - **Subtitle:** *Automated security scanning and real-time breach monitoring for small and medium businesses — plain-English risk scores mapped to the laws that apply to you, across Australia, New Zealand, the UAE and India.*

*End of audit. No code, data, or deployment was changed.*
