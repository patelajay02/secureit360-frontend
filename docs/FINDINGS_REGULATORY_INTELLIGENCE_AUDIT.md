# SecureIT360 — Findings & Regulatory-Intelligence Forensic Audit

**Date:** 2026-07-21
**Method:** First-hand end-to-end inspection of scanners, finding-creation code, DB fields, dashboard route, and the rendered dashboard. Evidence cited as `file:line`. No code/data/deploy changes.
**Question under test:** *"Each technical security finding is automatically connected to the business risk and the exact regulatory clause relevant to the customer's country of registration."*

> **Headline verdict:** The differentiator is **real and uncommon — for New Zealand and Australia.** Every finding is created with an embedded array of **specific statutory clauses** (e.g. `AU Privacy Act 1988 — APP 11.1`, `NZ Privacy Act 2020 — IPP 5`, `Essential Eight ML1`), the customer's country is taken from the **trusted tenant record** (not the client) for scoring and penalty framing, and each finding is surfaced with governance context, a director-liability score, ransomware/penalty exposure, and country-filtered clause chips. This is materially more than a commodity scanner. **However**, the per-finding *clause* depth genuinely works only for **NZ and AU**; **India** gets country intelligence only at the aggregate/framework level (no per-finding clauses); and **UAE is broken** by an `AE`/`UAE` country-code split. The content is hardcoded with **no version control, effective dates, legal citations, or admin editing**, and some clauses are **imprecise or outdated**. So: the prior "just hardcoded strings" framing understates it — but the claim can only be made safely for **AU/NZ**, as *regulatory intelligence*, not legal advice.

---

## 1. Finding Lifecycle (end-to-end trace)

Two-tier scan surface: the six domain engines + MS365/GWS/threat-intel write to `findings`; the SaaS connector writes to `saas_findings`.

| Stage | Where | Evidence |
|---|---|---|
| Detection | per-engine scanner | `website_scan.py`, `email_scan.py`, `network_scan.py`, `device_scan.py`, `cloud_scan.py`, `darkweb_scan.py`, `ms365_scan.py`, `google_workspace_scan.py`, `threat_intel_scan.py` |
| Raw result → finding | each engine's `upsert_finding(...)` | e.g. `website_scan.py:11-48`, `email_scan.py:8-45` |
| **Regulatory clauses attached at creation** | hardcoded `regulations=[...]` array passed into the finding | `website_scan.py:105-111,128-133,150-155`; `email_scan.py:102-107,123-128`; `network_scan.py:18-25,73-79`; `device_scan.py:73-80`; `cloud_scan.py:107-117`; `darkweb_scan.py:122-128` |
| **Governance mapping at creation** | hardcoded `governance_gap` string per finding (inline, **not** via `governance_mapper.py`) | `website_scan.py:104,127,149`; `cloud_scan.py:106` |
| DB table + fields | `findings`: `tenant_id, scan_id, engine, severity, title, description, governance_gap, regulations (jsonb), fix_type, score_impact, status` (+ `metadata` for ms365/gws/threat_intel, `auto_fixable`) | `website_scan.py:35-47` |
| Dedup | upsert by `(tenant_id, engine, title)` (core engines); `(tenant_id, title)` (ms365/threat_intel); **GWS has no dedup** | `website_scan.py:12-17`; `google_workspace_scan.py:296-302` |
| Severity | fixed per finding-type in scanner | e.g. DMARC `critical` `email_scan.py:92` |
| Risk score (Ransom) | Σ `score_impact` clamp 0-100 (+SaaS delta) | `dashboard.py:149-153,502-504` |
| Governance score | 100 − severity-weighted per finding w/ `governance_gap` | `dashboard.py:156-166` |
| **Director-liability mapping** | keyword tally over engine+title (MS365/GWS/threat-intel) | `dashboard.py:169-191` |
| Ransomware/penalty mapping | `get_penalty_info(findings, country)` — country-branched, severity-tiered | `dashboard.py:194-385` |
| **Regulatory mapping (per-finding, displayed)** | `finding.regulations` → `filterRegulations(regs, country)` chips | `app/dashboard/page.tsx:673-679,986-991` |
| Regulatory mapping (aggregate, dormant) | `generate_compliance_report()` — country-aware, **returned in `/scans/full` JSON, not displayed** | `regulatory_mapper.py:142-168`, `full_scan.py:12,63` |
| Compliance framework scores | `calculate_compliance_scores(findings, country, extra)` | `dashboard.py:398-449` |
| Clause selection | frontend prefix filter by country | `app/dashboard/page.tsx:673-679` |
| Remediation | **static** "voice guide" scripts keyed by title; TTS read-aloud; `auto-fix` (no handlers) | `app/dashboard/page.tsx:8-111`; `backend/services/auto_fix.py` |
| Frontend display | dashboard "Your top security issues" (top 5 only) | `app/dashboard/page.tsx:952-1015` |
| Status management | `status` ∈ open / fixed / auto_resolved; set on scan (`open`) and auto-fix (`auto_resolved`) | `website_scan.py:29,46`; `scans.py` auto-fix |
| Finding history | carry-over flag `updated_at > created_at` ("Not fixed since last scan"); weekly email diff | `app/dashboard/page.tsx:681-687,980-982` |
| Resolution workflow | auto-fix → `auto_resolved`; **no manual close / assignment / comments / due dates / evidence upload** | — |

**Two dormant modules found (challenge to any "it's all wired" assumption):**
- `backend/services/governance_mapper.py` — `get_governance_gap()` (`:56`) is **imported nowhere** (grep confirms only its own definition). Scanners hardcode `governance_gap` inline. **Dead code.**
- `backend/services/regulatory_mapper.py` — the **only** country-aware per-engine engine (with IN/UAE overrides) is used **solely** in `full_scan.py:63`; its output rides in the `/scans/full` response and is **not rendered** on the dashboard. Its superior IN/UAE clause coverage **never reaches users**.

---

## 2. Country Determination

| Question | Answer | Evidence |
|---|---|---|
| Registration field | `RegisterRequest.country`, stored to `tenants.country` verbatim | `backend/routes/auth.py:20,64` |
| Onboarding field | signup dropdown | `app/signup/page.js:12-19` |
| Tenant table field | `tenants.country` | `dashboard.py:469`, `tenants.py:123` |
| Supported values | `AU, NZ, IN, AE, PI, OTHER` | `app/signup/page.js:12-19` |
| Normalisation | **None** — raw code stored; no mapping of `AE`→`UAE`, `PI`/`OTHER`→handling | `auth.py:64` |
| Can country be changed by the customer? | **No** — `PATCH /tenants/me` only allows `director_email` + `compliance_frameworks` | `tenants.py:137-153` |
| Changed by admin? | Yes, at `admin/create-account` (default `NZ`) | `auth.py` create-account |
| Can a user tamper country in API requests? | **No for scoring/penalty** — backend reads country from the authenticated tenant record, never from the request body | `dashboard.py:459-469` |
| Frontend display country | `localStorage.country` (set at login from the trusted login response) — **client-mutable, display-only** | `app/dashboard/page.tsx:465,494`; `auth.py:215` |
| Does backend mapping read the trusted record or the frontend? | **Trusted tenant record** for `get_penalty_info` + `calculate_compliance_scores` | `dashboard.py:469,511-515` |

**Trust verdict:** ✅ The authoritative business-risk/penalty/compliance mapping uses the **trusted, non-user-editable tenant country**. A user cannot inflate/deflate their penalty framing via the API. The *displayed* clause chips are filtered using `localStorage.country` (cosmetic; tampering changes only which labels render, not scores).

**Country-code defects (material):**
- **`AE` vs `UAE` split (market-blocking for UAE).** Signup stores `AE` (`app/signup/page.js:16`), but `get_penalty_info` handles `AU/UAE/IN/else` and has **no `AE` branch** → a UAE tenant falls to the **NZ default** (NZD penalties, NZ Privacy Act) `dashboard.py:245,339`. `getRegulations('AE')` → **NZ** framework tiles `app/dashboard/page.tsx:652`. `filterRegulations('AE')` matches no branch → returns **all** regs unfiltered `:678`. `getCountryLabel('AE')` → "New Zealand regulations" `:669`. Only `calculate_compliance_scores` handles `("UAE","AE")` `dashboard.py:420` — but the frontend then reads `nz_*` keys, so those UAE scores are discarded. **Net: a UAE customer sees NZ everything.**
- **`PI` and `OTHER`** → always NZ default across penalty/compliance/regulations.

---

## 3. Regulatory Mapping Depth (exact clauses in code, per country)

Clauses that are **displayed per-finding** come from the scanner arrays (§1). Clauses at the **framework-tile / penalty** level come from `dashboard.py`. A third set (IN/UAE per-engine) exists only in the **dormant** `regulatory_mapper.py`.

### New Zealand (base/default; displayed per-finding ✅)
| Legislation | Clause | Mapped findings | Shown as | Source |
|---|---|---|---|---|
| NZ Privacy Act 2020 | **IPP 5** (security safeguards) | SSL, headers, SPF/DMARC, cloud, breach | per-finding chip | `website_scan.py:106`, `email_scan.py:106` |
| NZ Privacy Act 2020 | **s.113** notifiable breach ("within 72 hours") | cloud, darkweb/breach | chip + description | `cloud_scan.py:109`, `darkweb_scan.py:124` |
| NZ Privacy Amendment Act 2025 | **IPP 3A** ("in force May 2026") | SSL, cloud, breach | chip / tile | `website_scan.py:107`, `app/dashboard/page.tsx:655` |
| NZ NCSC Guidelines | email/web/network/patch baselines | email, headers, network, devices | chip | `email_scan.py:105`, `website_scan.py:152` |
| NZ Companies Act 1993 | director duty of care | network (via mapper/tile) | tile | `regulatory_mapper.py:26`, `app/dashboard/page.tsx:656` |

### Australia (displayed per-finding ✅)
| Legislation | Clause | Mapped findings | Source |
|---|---|---|---|
| AU Privacy Act 1988 | **APP 11.1**, **APP 11.2** (security/destruction) | SSL, headers, email, devices, cloud, breach | `website_scan.py:108-109`, `cloud_scan.py:111-112` |
| AU Privacy Act 1988 | **APP 8** (cross-border) | cloud | `cloud_scan.py:113` |
| AU Privacy Act 1988 | **NDB Scheme s.26WK** (notify within 30 days) | cloud, breach | `cloud_scan.py:114`, `darkweb_scan.py:127` |
| AU Privacy Act 1988 (amended Dec 2024) | APP 11.1 technical measures | devices, cloud, breach | `device_scan.py:78`, `darkweb_scan.py:128` |
| AU Essential Eight | **ML1** patch apps/OS, email hardening, web hardening; **ML2** restrict admin, user app hardening | email, network, website, devices | `network_scan.py:19-20`, `email_scan.py:103` |
| AU Cyber Security Act 2024 | **s.30** ransomware/incident reporting | network (RDP/SMB), cloud | `network_scan.py:21,76`, `cloud_scan.py:116` |
| AU Corporations Act 2001 | **s.180** director duty of care | cloud (mapper/tile) | `regulatory_mapper.py:53`, `app/dashboard/page.tsx:636` |
| AU Privacy Amendment 2024 | on-the-spot fines | tile | `app/dashboard/page.tsx:634` |

### India (framework/penalty level only; **no per-finding clauses displayed** ⚠️)
| Legislation | Clause | Where | Source |
|---|---|---|---|
| India DPDP Act 2023 | data-fiduciary obligations; up to **Rs 250 crore** | tile + penalty + dormant mapper | `app/dashboard/page.tsx:648`, `dashboard.py:296,303`, `regulatory_mapper.py:84` |
| CERT-In Guidelines 2022 | incident reporting **within 6 hours** | tile + penalty + dormant mapper | `app/dashboard/page.tsx:649`, `dashboard.py:305`, `regulatory_mapper.py:85` |

### UAE (defined but **not delivered** due to AE/UAE split ⚠️)
| Legislation | Clause | Where | Source |
|---|---|---|---|
| UAE PDPL 2021 | Art 10 (security), Art 12 (breach), Art 22 (cross-border); up to **AED 5M** | tiles/penalty/dormant mapper — routed to NZ for `AE` tenants | `app/dashboard/page.tsx:642`, `dashboard.py:249,256`, `regulatory_mapper.py:101-108` |
| UAE NESA / DIFC | national standards / controller obligations | tile / dormant mapper | `app/dashboard/page.tsx:643`, `regulatory_mapper.py:102` |

### ISO 27001 (all countries)
A.9, **A.9.4** (access control), **A.12.6** (technical vulnerability mgmt) — `regulatory_mapper.py:43,59-60`; tile `app/dashboard/page.tsx:638`.

### Breach vs potential-impact language
- `regulatory_mapper.py:118` — critical = **"regulatory breach confirmed"** (asserts a confirmed breach — risky; but this string is in the **dormant** path, likely never shown).
- `cloud_scan.py:103-104` (customer-facing description) — **"This is a serious privacy breach under both NZ and AU privacy law and must be reported to the relevant authority within 72 hours."** (definitive legal conclusion — risky).
- `dashboard.py:133-139` **DISCLAIMER** — "awareness purposes only … does not constitute legal advice … indicative maximums." (present on dashboard; good mitigation).

### Accuracy assessment (clauses are NOT assumed correct)
| Clause / claim | Assessment |
|---|---|
| AU Privacy Act APP 11.1/11.2, APP 8, NDB s26WK (30 days) | **Accurate.** |
| India DPDP Rs 250 crore; CERT-In 6-hour reporting | **Accurate.** |
| AU Cyber Security Act 2024 ransomware reporting (72h) | Plausible/accurate; **exact "s.30" needs verification.** |
| "$50M" attributed to "amended Dec 2024" | **Imprecise** — the $50M max came via the 2022 enforcement amendment, not Dec 2024. |
| NZ "breach notification within 72 hours" (s.113) | **Inaccurate** — NZ requires notice "as soon as practicable," not a fixed 72h. |
| NZ Privacy Amendment 2025 / IPP 3A "in force May 2026" | **Speculative/forward-dated** — verify status/date. |
| ISO 27001 **A.9.4 / A.12.6** | **Outdated numbering** — ISO 27001:2022 renumbered to A.8.x. |
| UAE PDPL article numbers | **Unverified** — confirm against Federal Decree-Law 45/2021 + executive regulations. |

**No version control, no effective date field, no review date, no legal-source citation/link, and content is hardcoded — not admin-editable.** When laws change, a developer must edit source and redeploy.

---

## 4. Finding-Specific Mapping Matrix

Legend: ✅ present · ➖ partial/aggregate-only · ❌ absent. "Clause (NZ/AU)" = exact per-finding statutory chip shown to NZ/AU tenants.

| Finding | Detected? | Tech expl. | Business impact | Severity | Ransom/$ impact | Director/gov | Country reg | Exact clause (NZ/AU) | Reg relevance expl. | Remediation | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Missing SPF | ✅ | ✅ | ✅ | moderate | ➖ (aggregate) | ✅ | ✅ NZ/AU | ✅ APP 11.1 / IPP 5 / EE ML1 | ✅ | ✅ static | ❌ |
| Missing DMARC | ✅ | ✅ | ✅ | critical | ➖ | ✅ | ✅ | ✅ EE ML1 DMARC / APP 11.1 / IPP 5 | ✅ | ✅ | ❌ |
| Weak DMARC policy (p=none) | ❌ (only presence of `v=DMARC1`) | — | — | — | — | — | — | — | — | — | — |
| Missing DKIM | ❌ (declared, never checked) | — | — | — | — | — | — | — | — | — | — |
| Expired/invalid SSL | ✅ | ✅ | ✅ | critical | ➖ | ✅ | ✅ | ✅ IPP 5 / IPP 3A / APP 11.1 / APP 11.2 / EE ML1 | ✅ | ✅ | ❌ |
| Weak TLS (proto/cipher) | ❌ (expiry only) | — | — | — | — | — | — | — | — | — | — |
| Missing security headers | ✅ | ✅ | ➖ | low | ➖ | ✅ | ✅ | ✅ EE ML1 / NCSC / APP 11.1 / IPP 5 | ✅ | ✅ | ❌ |
| Exposed credentials | ➖ (via breach only) | ✅ | ✅ | by pwn count | ➖ | ✅ | ✅ | ✅ IPP 5 / s113 / APP 11.1 / NDB s26WK | ✅ | ✅ | ❌ |
| Breach exposure (HIBP) | ✅ | ✅ | ✅ | scaled | ➖ | ✅ | ✅ | ✅ (rich) | ✅ | ✅ | ➖ (breach name in metadata) |
| Malware/blacklist | ✅ (VT/AbuseIPDB/URLScan/OTX) | ✅ | ✅ | varies | ➖ | ✅ (DLS) | ➖ | ➖ (governance framing) | ➖ | ➖ | ➖ (metadata) |
| Exposed service/port | ✅ (passive Shodan) | ✅ | ✅ | crit/mod | ➖ | ✅ | ✅ | ✅ EE ML1/ML2 / Cyber Sec Act s30 / APP 11.1 | ✅ | ✅ | ❌ |
| Vulnerable software / CVE | ➖ (PHP<8, Apache banner only) | ✅ | ➖ | crit/low | ➖ | ✅ | ✅ | ✅ EE ML1 patch / APP 11.1 | ✅ | ➖ | ❌ |
| Weak Microsoft 365 config | ✅ (Graph API) | ✅ | ✅ | varies | ➖ | ✅ (DLS) | ➖ | ➖ (ISO/EE via mapper; sparse on finding) | ➖ | ➖ | ✅ (`metadata.affected_users`) |
| Weak Google Workspace config | ✅ (Admin/Drive API) | ✅ | ✅ | varies | ➖ | ✅ (DLS) | ➖ | ➖ | ➖ | ➖ | ✅ (metadata) |
| SaaS posture issue | ✅ (Xero/Zoho) | ✅ | ✅ | varies | ➖ | ➖ | ✅ (`regulation_refs`, country-aware) | ➖ (country list, not clause) | ✅ | ✅ (`recommended_action`) | ❌ |
| Typosquatting | ✅ | ✅ | ✅ | varies | — | ✅ (DLS +25) | ➖ | ➖ | ➖ | ➖ | ➖ (metadata) |
| Data exposure (public cloud) | ✅ (S3 guess) | ✅ | ✅ | critical | ➖ | ✅ | ✅ | ✅ (richest: IPP 5/s113/APP 11.1/11.2/8/NDB/Cyber Sec Act) | ✅ | ✅ | ❌ |
| Lack of MFA (M365/GWS/SaaS) | ✅ | ✅ | ✅ | crit/high | ➖ | ✅ (DLS +5) | ➖ | ➖ | ➖ | ➖ | ✅ (metadata) |
| Privileged-account risk | ✅ (admin sprawl) | ✅ | ✅ | moderate | ➖ | ✅ (DLS +15) | ➖ | ➖ | ➖ | ➖ | ✅ (metadata) |

**Pattern:** the **six domain engines** (email/website/network/device/cloud/darkweb) carry the **richest per-finding NZ/AU clause arrays**. The **cloud/SaaS/identity engines** (MS365/GWS/threat-intel/SaaS) are strong on evidence + governance + director-liability but **thin on exact statutory clauses per finding** (they lean on ISO/EE or `regulation_refs` country lists). Financial/ransomware impact is **aggregate** (dashboard panel), not per-finding.

---

## 5. Frontend Findings Audit

There is **no dedicated `/findings` route.** Findings are surfaced in two places:

**A. Dashboard "Your top security issues"** (`app/dashboard/page.tsx:952-1015`):
- Shows **only `top_findings` = top 5 by `score_impact`** (`dashboard.py:479,538`). No full list, pagination, or all-findings view.
- Per finding: severity badge (`:970-976`), title, **carry-over tag** "Not fixed since last scan" (`:980-982`), truncated description (200 chars, `:984`), grey `governance_gap` line (`:985`), **country-filtered regulation chips** (`filterRegulations(finding.regulations, country)`, `:986-991`), and `FindingActionsBar` (Auto-Fix / Voice Guide / Connect-to-Expert-mailto, `:993-1000`).
- MS365/GWS findings with `metadata.affected_users` open a **password-gated detail modal** (`:962-967`, ReauthModal).
- **Regulatory Compliance panel** (`:932-950`): per-framework % score tiles via `getRegulations(compliance, country)` + `getCountryLabel(country)` + "Current legislation: {key_law}".
- **"If Attacked Today"** panel renders `penalty_info` (fines, liability, ransom reporting, downtime).

**B. SaaS Findings list** (`components/saas/FindingsList.tsx`): severity badge, `governance_statement`, `recommended_action`, `regulation_refs` chips (`:88-108`).

| Attribute | State |
|---|---|
| Filters | ❌ none (dashboard); admin page has filters, not findings |
| Severity badges | ✅ |
| Country/regulation display | ✅ NZ/AU real; ➖ IN aggregate; ❌ UAE broken |
| Exact-clause display | ✅ NZ/AU chips per finding |
| Business-impact / director-liability | ✅ (aggregate panels + DLS gauge) |
| Remediation | ✅ static voice-guide scripts + Auto-Fix (no handlers) |
| Evidence | ➖ MS365/GWS affected-user lists (modal); ❌ for core engines |
| Status workflow | ➖ open → auto_resolved; **no manual close/reopen** |
| Assignment / due dates / comments | ❌ none |
| Export / download | ❌ none (no PDF/CSV) |
| Trend / history | ➖ carry-over flag + weekly-email diff; no charts |
| Mock/static/hidden | Voice-guide text static; only top-5 shown (rest hidden); `top_findings` unfiltered by country server-side (filtering is client-side) |

---

## 6. Is the Differentiator Real?

| Question | Answer (evidence) |
|---|---|
| Does **every** finding receive regulatory mapping? | **Most core-engine findings do** (embedded `regulations`); MS365/GWS/threat-intel are thin; SaaS uses `regulation_refs`. Not 100%. |
| Only selected findings? | The six domain engines are consistently mapped; identity/cloud engines less so. |
| Is the mapping country-specific? | **Yes for scoring/penalty (trusted country).** Per-finding **clauses** are country-*filtered* client-side — real for NZ/AU, empty for IN, unfiltered/misrouted for UAE(`AE`). |
| Country from the tenant registration record? | **Yes** for backend scoring/penalty (`dashboard.py:469`); display uses `localStorage` (set from trusted login). |
| Exact clauses shown? | **Yes for NZ/AU** (APP 11.1, IPP 5, s113, NDB s26WK, EE ML1/ML2, Cyber Sec Act s30). |
| Exact clauses unique by country? | **Partly** — findings carry NZ+AU together; the frontend strips the other country. IN/UAE clause strings are never attached to findings. |
| Breach vs potential vs awareness? | **Mixed** — dashboard carries an awareness/not-legal-advice disclaimer, but some finding text ("this **is** a serious privacy breach … **must** be reported within 72 hours", `cloud_scan.py:103-104`) and a dormant "regulatory breach confirmed" string state definitive conclusions. |
| Deterministic, reliable, maintainable? | **Deterministic yes.** Maintainable **poorly** — hardcoded across ~9 files + frontend, duplicated logic, two dormant modules, no single source of truth. |
| One finding → several regulations/clauses? | **Yes** (arrays of 3–9 clauses per finding). |
| Version control for legal content? | ❌ None (git only; no in-app versioning). |
| Effective date / review date? | ❌ None (one global "as at April 2026" disclaimer string). |
| Legal-source citation / link? | ❌ None (clause text only, no URLs). |
| Editable via admin tools? | ❌ Hardcoded only. |
| What happens when laws change? | Developer edits source + redeploys; risk of drift across the 9+ files. |

**Verdict:** The differentiator is **genuine and uncommon for AU/NZ** — findings are integrated with specific statutory clauses, governance framing, director-liability, and country-true penalty modelling from a trusted country field. It is **overstated for India (aggregate only) and currently broken for the UAE.** The prior "hardcoded strings" label is **too dismissive** of real, specific, integrated, country-aware content — but the content's **operational maturity** (accuracy, versioning, coverage, maintainability) is low.

---

## 7. Legal & Marketing Accuracy

**Risky definitive wording found:**
- `cloud_scan.py:103-104` — "This **is** a serious privacy breach under both NZ and AU privacy law and **must** be reported to the relevant authority within 72 hours." → recommend: *"This may constitute a notifiable privacy breach under NZ/AU privacy law and may require reporting — seek compliance review."*
- `regulatory_mapper.py:118` — "regulatory **breach confirmed**" → recommend: *"potential regulatory gap identified — review required"* (also: this path is dormant; either fix or remove).
- `dashboard.py:344,350,208` — "Director personal liability", "liability: High" → keep as a **risk indicator**, but ensure UI frames it as *potential* exposure, not a legal determination.
- Compliance status `dashboard.py`/`app/dashboard/page.tsx:614` labels a low score **"Non-compliant"** → recommend *"Significant gaps"* / *"Below target"* to avoid a definitive compliance conclusion.
- NZ "within 72 hours" (`cloud_scan.py`, `darkweb_scan.py`, `dashboard.py:353`) → correct to NZ's *"as soon as practicable"* standard.

**Keep (good):** the dashboard DISCLAIMER (`dashboard.py:133-139`) and "indicative"/"(indicative)" penalty qualifiers. **Do not weaken accurate clause references** (APP 11.1, DPDP Rs 250cr, CERT-In 6h) — only reframe *conclusions* from "breach/violation" to "potential gap / requires compliance review."

**Recommended safe phrasing bank:** "may indicate a gap against {clause}", "may increase the risk of non-compliance with {law}", "potentially relevant obligation: {clause}", "requires legal or compliance review".

---

## 8. Comparison vs Common Scanners

Commodity scanners typically output: vulnerability + severity + CVSS + technical remediation.

| Capability | Commodity scanner | SecureIT360 |
|---|---|---|
| Vulnerability + severity | ✅ | ✅ (though scanning is shallow/heuristic) |
| CVSS | ✅ | ❌ (uses its own `score_impact`) |
| Technical remediation | ✅ | ➖ (plain-English static scripts) |
| **Business impact / $ modelling** | ✗ | ✅ ransom range, downtime, fine exposure |
| **Governance impact** | ✗ | ✅ per-finding `governance_gap` |
| **Director-liability context** | ✗ | ✅ Director Liability Score + personal-liability framing |
| **Country-specific legal mapping** | ✗ | ✅ **AU/NZ** (trusted country) |
| **Exact clause references per finding** | ✗ | ✅ **AU/NZ** (APP 11.1, IPP 5, …) |
| **Prioritised remediation** | ➖ | ✅ score-ranked + "top issues" |

**Assessment:** binding **exact statutory clauses + director-liability + country-true business/penalty framing onto each finding, for AU/NZ SMEs**, is an **uncommon differentiator** among commodity scanners (which stop at CVSS + technical fix). It is best described as a **strong market differentiator for the AU/NZ SME segment**, provided the clause content is legally reviewed. (Not claiming *no* competitor does this — GRC/ASM vendors offer control mapping — but few SME-priced scanners deliver per-finding local-statute framing.)

---

## 9. Positioning Recommendation

| Description | Accurate now? | Supporting features | Missing before use | Overclaim risk |
|---|---|---|---|---|
| Continuous Cyber Risk Monitoring Platform | **Yes (scoped)** | daily scans + 5-min HIBP + scores | schedule cloud/SaaS posture | Low |
| Cyber Risk **Intelligence** Platform | **Yes** | risk scores + threat-intel + business/penalty framing | — | Low–Med (some read "intelligence" as AI) |
| **Regulatory** Cyber Risk Intelligence Platform | **Yes for AU/NZ** | per-finding clauses + country penalty/compliance from trusted country | fix UAE(`AE`), add IN per-finding clauses, legal review, versioning | Medium (only if sold beyond AU/NZ or as legal-grade) |
| Cyber Risk & **Compliance** Platform | **No (as full compliance)** | mapping + scores | control library, gap-assessment, evidence, reports (see prior audit) | High |
| **AI-Powered** Cyber Risk Platform | **No** | 1 peripheral AI feature | AI in core scan/scoring/mapping | High |

**Recommended:** **"Regulatory Cyber Risk Intelligence Platform"** — *for Australia & New Zealand SMEs* — is the most accurate elevated positioning today, because the per-finding statutory mapping is real and specific for those two markets. Market UAE/India as "regulatory mapping" only until the `AE`/`UAE` bug and per-finding IN/UAE clauses are shipped.

---

## 10. Final Verdict

1. **Finding types (detected):** ~18 distinct (SPF, DMARC, SSL expiry/invalid, headers, breach/HIBP, malware-blacklist ×4 sources, port/RDP/SMB/SSH/FTP/Telnet, PHP/Apache version, S3 exposure, typosquat, M365 MFA/inactive/admin/sharing, GWS 2SV/inactive/admin/sharing, SaaS admin/MFA/dormant). **Not detected:** weak-DMARC-policy, DKIM, weak-TLS, real CVE.
2. **Country-specific regulatory mappings:** 4 country branches (AU, NZ, IN, UAE) in penalty + compliance; per-finding clause delivery real for **2** (AU, NZ).
3. **Exact clauses/provisions in code:** ~30+ distinct (NZ IPP 5/IPP 3A/s113; AU APP 11.1/11.2/8, NDB s26WK, EE ML1/ML2, Cyber Sec Act s30, Corporations s180; ISO A.9.4/A.12.6; IN DPDP/CERT-In 6h; UAE PDPL Art 10/12/22, DIFC, NESA). Displayed per-finding: NZ ~4–6, AU ~8–10.
4. **Countries genuinely supported (per-finding clause depth):** **New Zealand and Australia.** India = aggregate/framework only. **UAE = broken** (`AE`/`UAE`).
5. **Strongest real differentiator:** every AU/NZ finding is bound to **specific statutory clauses + governance gap + director-liability + country-true business/penalty impact**, driven by a **trusted, tamper-resistant country field** — an uncommon, SME-priced "regulatory intelligence" layer over scanning.
6. **Limitations:** per-finding clauses AU/NZ-only; UAE broken; IN per-finding absent; no version control / effective dates / citations / admin editing; some clauses imprecise/outdated (NZ 72h, ISO 2013 numbering, $50M attribution); dead `governance_mapper.py`; dormant country-aware `regulatory_mapper.py`; only top-5 findings shown; no export/assignment/manual-close; remediation is static, auto-fix has no handlers.
7. **Unsafe claims to avoid:** "you are in breach", "regulatory breach confirmed", "legal violation", "non-compliant" (as a verdict), "must be reported within 72 hours" (NZ), unqualified "director is liable", "AI-powered", "compliance platform", and any country-specific legal capability for UAE/India beyond "mapping".
8. **Exact recommended category:** **Regulatory Cyber Risk Intelligence Platform for Australian & New Zealand SMEs** (market UAE/India as "regulatory mapping").
9. **Exact homepage headline:** **"Know Your Cyber Risk — Mapped to the Laws That Apply to You."**
10. **Exact subtitle:** *"Daily security scanning and real-time breach monitoring for small and medium businesses — every finding tied to the specific Australian and New Zealand regulatory obligations, with plain-English business and director-liability impact. Regulatory intelligence, not legal advice."*
11. **Exact Findings-feature-section wording:** **"Every finding, connected to your obligations."** *"We don't just tell you what's wrong — each issue is linked to the exact clause it touches (e.g. Privacy Act APP 11 / IPP 5, Essential Eight), the governance gap behind it, the business and director-liability impact, and a plain-English fix. Clause mapping is tailored to your country of registration (full statutory depth for Australia and New Zealand). For awareness and prioritisation — not a substitute for legal advice."*

*Evidence-based; challenges the prior "hardcoded strings" framing (the mapping is specific, per-finding, country-aware and trusted for AU/NZ) while documenting where it is shallow, broken, or legally risky. No code, data, or deployment changed.*
