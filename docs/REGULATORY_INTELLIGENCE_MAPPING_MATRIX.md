# SecureIT360 — Regulatory Intelligence Mapping Matrix

**Date:** 2026-07-21
**Status:** Design artifact only. No code changed, no data modified, nothing deployed. The companion machine-readable file is `docs/regulatory_intelligence_mapping.json` and is **not** wired to production.
**Sources:** `docs/ARCHITECTURE_AUDIT.md`, `docs/FEATURE_AUDIT_AND_POSITIONING.md`, `docs/FINDINGS_REGULATORY_INTELLIGENCE_AUDIT.md`.

> **CRITICAL DISCLAIMER — READ FIRST.** This document is **regulatory intelligence, not legal advice.** Clause references, effective dates, penalty figures and applicability conditions below were assembled by an engineering process and **must be verified by a qualified legal practitioner in each jurisdiction (AU / NZ / AE / IN) before any statement is shown to a customer.** Every mapping is written in *potential-gap* language, never as a confirmed breach or liability determination. Fields marked `confidence: to_verify` require legal sign-off. `review_owner` for all records is **Global Cyber Assurance — Compliance (pending external legal review)**.

> **Authoring coverage (honesty note).** The finding **catalogue, country-coverage tables, clause libraries, wording templates, applicability logic, framework mapping, and priority model below are complete.** Full per-country mapping *records* are **authored in depth for the finding types the current scanners actually generate** (§10, ~20 codes). Finding types that are catalogued but **not yet detected by any scanner** are listed with `implementation_status: proposed` and are staged for the next authoring pass using the identical schema (they carry placeholder mapping objects in the JSON). This staged approach is deliberate: it establishes one legally-careful, maintainable map *before* the production engine is touched.

---

## 1. Canonical Country-Code Model

**Canonical codes (use everywhere, storage + logic + display keys):** `AU`, `NZ`, `AE`, `IN`.

The current code is inconsistent: registration **stores** `AE` for the UAE (`app/signup/page.js:16`), but backend penalty logic and the frontend branch on the string `"UAE"`, so UAE tenants silently fall through to the New Zealand default (documented in `FINDINGS_REGULATORY_INTELLIGENCE_AUDIT.md §2`). The canonical code is **`AE`**; every `"UAE"` branch is a defect.

### Migration table (do NOT implement yet)

| Current value | Canonical value | Files affected | Required correction |
|---|---|---|---|
| `"UAE"` (branch key in penalty logic) | `AE` | `backend/routes/dashboard.py:245` (`get_penalty_info`) | Branch on `AE`; delete the `"UAE"` string |
| `("UAE","AE")` (dual key) | `AE` | `backend/routes/dashboard.py:420` (`calculate_compliance_scores`) | Collapse to single `AE` branch |
| `"UAE"` (override dict key) | `AE` | `backend/services/regulatory_mapper.py:99` (`_COUNTRY_OVERRIDES`) | Rekey to `AE` |
| `'UAE'` (switch cases) | `AE` | `app/dashboard/page.tsx:640,667,676` (`getRegulations`, `getCountryLabel`, `filterRegulations`) | Rename cases to `AE` |
| `"UAE"` + `"AE"` both present | `AE` | `app/settings/page.js:13-19` (`COUNTRY_DEFAULT_FRAMEWORKS`) | Single `AE` key |
| `country` returned/stored raw, no normalisation | canonical set | `backend/routes/auth.py:64` (register), `auth.py:215` (login response), `app/dashboard/page.tsx:494` (localStorage) | Normalise to `{AU,NZ,AE,IN}` on write; validate against an allow-list |
| `"PI"` (Pacific Islands), `"OTHER"` | *unsupported* | `app/signup/page.js:17-18`, `app/admin/page.tsx:378-383` | Out of scope for regulatory mapping → route to generic guidance-only profile; do **not** show country-specific legal claims |
| Country **names** in copy ("Australia", "New Zealand") | *display only* | `app/privacy/page.js`, `app/terms/page.js`, legal pages | Acceptable as display strings; must **not** be used as logic keys |

Note also: display country is read from `localStorage` (client-mutable, cosmetic) while scoring/penalty use the **trusted** tenant record — keep that split, and drive per-finding clause filtering from the **trusted** value once normalised.

---

## 2. Finding Catalogue — Master List (Table A)

Status legend: **Real** = scanner emits it today · **Shallow** = emitted but heuristic/limited · **Proposed** = in scope but no scanner detects it yet · **N/A** = not applicable to current architecture.

| Code | Finding | Category | Current scanner | Status |
|---|---|---|---|---|
| WEB_UNAVAILABLE | Website unavailable | website | — | Proposed |
| WEB_NO_HTTPS | HTTP without HTTPS redirect | website | — | Proposed |
| TLS_CERT_INVALID | Invalid TLS certificate | tls | `website_scan.py` | Real (shallow) |
| TLS_CERT_EXPIRED | Expired certificate | tls | `website_scan.py` | Real |
| TLS_CERT_EXPIRING | Certificate expiring soon (<30d) | tls | `website_scan.py` | Real |
| TLS_WEAK_CONFIG | Weak TLS configuration (proto/cipher) | tls | — | Proposed |
| HDR_HSTS_MISSING | Missing HSTS | website | `website_scan.py` (grouped) | Shallow |
| HDR_CSP_MISSING | Missing Content-Security-Policy | website | `website_scan.py` (grouped) | Shallow |
| HDR_XCTO_MISSING | Missing X-Content-Type-Options | website | `website_scan.py` (grouped) | Shallow |
| HDR_XFO_MISSING | Missing X-Frame-Options | website | `website_scan.py` (grouped) | Shallow |
| HDR_REFERRER_MISSING | Missing Referrer-Policy | website | — | Proposed |
| HDR_PERMISSIONS_MISSING | Missing Permissions-Policy | website | — | Proposed |
| WEB_SERVER_DISCLOSURE | Server version disclosure | website | `device_scan.py` | Real (shallow) |
| WEB_TECH_DISCLOSURE | Technology disclosure | website | `device_scan.py` | Real (shallow) |
| WEB_COOKIE_INSECURE | Insecure cookies | website | — | Proposed |
| WEB_MIXED_CONTENT | Mixed content | website | — | Proposed |
| WEB_ADMIN_EXPOSED | Exposed administration interface | website | — | Proposed |
| SOFTWARE_OUTDATED | Vulnerable/outdated software (e.g. PHP<8) | vulnerability | `device_scan.py` | Real (shallow) |
| MALWARE_BLACKLIST | Malware or blacklist detection | threat_intel | `threat_intel_scan.py` | Real |
| EMAIL_SPF_MISSING | Missing SPF | email | `email_scan.py` | Real |
| EMAIL_SPF_INVALID | Invalid SPF | email | — | Proposed |
| EMAIL_SPF_PERMISSIVE | SPF too permissive (+all) | email | — | Proposed |
| EMAIL_DMARC_MISSING | Missing DMARC | email | `email_scan.py` | Real |
| EMAIL_DMARC_NONE | DMARC policy = none | email | — | Proposed |
| EMAIL_DMARC_WEAK | Weak DMARC enforcement | email | — | Proposed |
| EMAIL_DKIM_MISSING | Missing DKIM | email | *declared, never checked* | Proposed |
| EMAIL_DKIM_INVALID | Invalid DKIM | email | — | Proposed |
| DNS_MX_MISSING | Missing MX records | dns | — | Proposed |
| DNS_OPEN_RELAY | Open email relay risk | dns | — | Proposed |
| DNS_SPOOFING_EXPOSURE | Email spoofing exposure | dns | *implied by SPF/DMARC* | Partial |
| DNS_DNSSEC_MISSING | DNSSEC missing | dns | — | Proposed |
| DNS_MISCONFIG | Misconfigured DNS | dns | — | Proposed |
| DNS_DANGLING | Dangling DNS record | dns | — | Proposed |
| DNS_SUBDOMAIN_TAKEOVER | Subdomain takeover risk | dns | — | Proposed |
| BREACH_EMAIL_EXPOSED | Email address found in breach | breach | `darkweb_scan.py`, `hibp_watch.py` | Real |
| BREACH_PASSWORD_EXPOSED | Password exposure | breach | *implied by breach* | Partial |
| IDENT_PRIV_ACCOUNT_EXPOSED | Privileged account exposed in breach | breach | — | Proposed |
| IDENT_SHARED_ACCOUNT | Shared account risk | identity | — | Proposed |
| IDENT_MFA_MISSING | MFA not enabled (generic) | identity | via M365/GWS/SaaS | Partial |
| IDENT_WEAK_AUTH | Weak authentication controls | identity | — | Proposed |
| IDENT_DORMANT_ACCOUNT | Dormant account | identity | M365/GWS/SaaS | Real |
| IDENT_EXCESS_PRIV | Excessive privileges | identity | M365/GWS admin sprawl | Real |
| IDENT_ADMIN_RISK | Administrator-account risk | identity | M365/GWS/SaaS | Real |
| M365_MFA_GAP | Microsoft 365 MFA gap | cloud_posture | `ms365_scan.py` | Real |
| M365_LEGACY_AUTH | M365 legacy authentication enabled | cloud_posture | — | Proposed |
| M365_EXTERNAL_SHARING | M365 external sharing risk | cloud_posture | `ms365_scan.py` | Real |
| M365_MAIL_FORWARDING | M365 mailbox forwarding risk | cloud_posture | — | Proposed |
| M365_PRIV_ROLE | M365 privileged-role risk | cloud_posture | `ms365_scan.py` | Real |
| M365_INACTIVE | M365 inactive/stale account | cloud_posture | `ms365_scan.py` | Real |
| GWS_MFA_GAP | Google Workspace MFA/2SV gap | cloud_posture | `google_workspace_scan.py` | Real |
| GWS_EXTERNAL_SHARING | Google Workspace external sharing risk | cloud_posture | `google_workspace_scan.py` | Real |
| GWS_ADMIN_RISK | Google Workspace administrator risk | cloud_posture | `google_workspace_scan.py` | Real |
| GWS_INACTIVE | Google Workspace inactive account | cloud_posture | `google_workspace_scan.py` | Real |
| SAAS_ADMIN_RATIO | SaaS excessive-admin gap (Xero/Zoho) | saas_posture | `generic_checks.py` | Real |
| SAAS_MFA_GAP | SaaS MFA coverage gap | saas_posture | `generic_checks.py` | Real |
| SAAS_DORMANT | Inactive/stale SaaS account | saas_posture | `generic_checks.py` | Real |
| SAAS_PUBLIC_SHARING | SaaS public sharing gap | saas_posture | *check exists, no provider feed* | Partial |
| SAAS_AUDITLOG_OFF | SaaS audit logging disabled | saas_posture | *check exists, no provider feed* | Partial |
| SAAS_UNAPPROVED_APP | Unapproved third-party application | saas_posture | — | Proposed |
| PORT_RDP_EXPOSED | Exposed RDP (3389) | attack_surface | `network_scan.py` | Real (passive) |
| PORT_SMB_EXPOSED | Exposed SMB (445) | attack_surface | `network_scan.py` | Real (passive) |
| PORT_TELNET_EXPOSED | Exposed Telnet (23) | attack_surface | `network_scan.py` | Real (passive) |
| PORT_SSH_EXPOSED | Exposed SSH (22) | attack_surface | `network_scan.py` | Real (passive) |
| PORT_FTP_EXPOSED | Exposed FTP (21) | attack_surface | `network_scan.py` | Real (passive) |
| PORT_DB_EXPOSED | Public database service | attack_surface | — | Proposed |
| PORT_FILESHARE_EXPOSED | Public file-sharing service | attack_surface | *SMB partial* | Partial |
| PORT_DEV_EXPOSED | Exposed development service | attack_surface | — | Proposed |
| CLOUD_STORAGE_PUBLIC | Public cloud storage (S3) | data_exposure | `cloud_scan.py` | Real (shallow) |
| TI_TYPOSQUAT | Typosquatting domain | attack_surface | `threat_intel_scan.py` | Real |
| TI_BRAND_IMPERSONATION | Brand impersonation domain | attack_surface | `threat_intel_scan.py` | Partial |
| TI_MATCH | Threat-intelligence match | attack_surface | `threat_intel_scan.py` | Real |
| TI_IP_REPUTATION | Suspicious IP reputation | attack_surface | `threat_intel_scan.py` | Real |
| TI_DOMAIN_BLACKLIST | Domain blacklist match | attack_surface | `threat_intel_scan.py` | Real |
| GOV_NO_BACKUP | No tested backup | governance | *governance_gap text only* | Proposed |
| GOV_RANSOMWARE_RESILIENCE | Weak ransomware resilience | governance | *inferred* | Proposed |
| GOV_NO_IR_PLAN | No incident-response plan | governance | *governance_gap text only* | Proposed |
| GOV_NO_BREACH_PROCESS | No breach-response process | governance | *governance_gap text only* | Proposed |
| GOV_NO_SEC_POLICY | No security policy | governance | *governance_gap text only* | Proposed |
| GOV_NO_VULN_MGMT | No vulnerability-management process | governance | *governance_gap text only* | Proposed |
| GOV_NO_ACCESS_REVIEW | No access-review process | governance | *governance_gap text only* | Proposed |
| GOV_NO_SUPPLIER_REVIEW | No supplier-security review | governance | — | Proposed |
| GOV_NO_AWARENESS | No security-awareness programme | governance | *governance_gap text only* | Proposed |
| GOV_NO_AUDIT_LOG | No audit logging | governance | — | Proposed |
| GOV_NO_BCP | No business-continuity protection | governance | *governance_gap text only* | Proposed |

**Counts:** 85 catalogued codes · **~34 Real/Shallow** (scanner-backed today) · ~9 Partial · ~42 Proposed.

---

## 3. Mapping Record Schema

Every finding gets one record **per country** (`AU`, `NZ`, `AE`, `IN`) with these fields (mirrored in the JSON):

`finding_code` · `finding_name` · `category` · `country_code` · `technical_description` · `technical_risk` · `business_impacts[]` · `governance_impact` · `director_or_management_context` · `applicable_laws[]` · `applicable_clauses[]` (references into the country clause library, §5) · `regulatory_relevance` · `penalty_context` · `industry_framework_mappings{}` (§8) · `recommended_remediation` · `priority` · `target_days` · `closure_evidence[]` · `legal_wording` (from templates, §6) · `source_references[]` · `effective_date` · `last_reviewed_date` · `review_owner` · `confidence` (`high`|`medium`|`to_verify`) · `implementation_status` (`real`|`shallow`|`partial`|`proposed`).

---

## 4. Regulatory Sources by Country (only genuinely-relevant provisions)

Each clause below carries a **legal_status**: *legislation* · *regulation* · *binding_direction* · *sector_requirement* · *standard* · *guidance*. **Applicability conditions gate display** (§7) — nothing is shown to every customer.

### Australia (AU)
| ID | Law / instrument | Provision | legal_status | Applies to |
|---|---|---|---|---|
| AU-PRIV-APP11 | Privacy Act 1988 (Cth) | APP 11 — Security of personal information (11.1 reasonable steps; 11.2 destroy/de-identify) | legislation | **APP entities** — generally businesses with turnover > A$3M, **plus** health-service providers, entities trading in personal information, credit providers, TFN recipients, contracted service providers to the Cth, and related bodies corporate. **Small-business exemption applies below A$3M unless an exception is met.** |
| AU-PRIV-NDB | Privacy Act 1988 Part IIIC | Notifiable Data Breaches — assess a suspected eligible breach expeditiously (within 30 days) and, if eligible, notify the OAIC and affected individuals **as soon as practicable** | legislation | APP entities (as above); triggered by an *eligible data breach* likely to result in serious harm |
| AU-PRIV-PENALTY | Privacy Act 1988 s13G | Serious or repeated interference with privacy — civil penalty up to the greater of **A$50M / 3× benefit / 30% of adjusted turnover** | legislation (enforcement) | APP entities; court-imposed on OAIC application — a maximum, not automatic |
| AU-PRIV-TORT | Privacy and Other Legislation Amendment Act 2024 | Statutory tort for serious invasions of privacy (commenced ~2025) | legislation | Broad; individual-initiated claims |
| AU-CORP-180 | Corporations Act 2001 s180 | Director/officer duty of care and diligence (cf. *ASIC v RI Advice Group* re cyber-risk management) | legislation | Company directors/officers |
| AU-CYBER-RANSOM | Cyber Security Act 2024 (Cth) | Ransomware payment reporting — report within 72 hours of making/becoming aware of a ransomware payment | legislation | Entities above a turnover threshold (set by rules) and critical-infrastructure responsible entities — **not all businesses** |
| AU-SOCI | Security of Critical Infrastructure Act 2018 | Risk-management program & incident reporting | sector_requirement | Responsible entities for CI assets only |
| AU-CPS234 | APRA Prudential Standard CPS 234 | Information security capability | sector_requirement | APRA-regulated entities only (ADIs, insurers, super) |
| AU-ACL | Australian Consumer Law (Sch 2 CCA 2010) | Misleading/deceptive conduct re security representations | legislation | Businesses making security claims to consumers |
| AU-E8 | ASD Essential Eight | Eight mitigation strategies / maturity model | guidance | Guidance for all; mandatory only for non-corporate Cth entities |

### New Zealand (NZ)
| ID | Law / instrument | Provision | legal_status | Applies to |
|---|---|---|---|---|
| NZ-PRIV-IPP5 | Privacy Act 2020 | IPP 5 — Storage and security of personal information (reasonable safeguards) | legislation | Any agency holding personal information (**no small-business exemption**) |
| NZ-PRIV-NOTIF | Privacy Act 2020 Part 6 (ss112-118) | Notifiable privacy breach — notify the Privacy Commissioner and affected individuals **as soon as practicable** after becoming aware, where the breach has caused or is likely to cause **serious harm** | legislation | Any agency. **No fixed 72-hour deadline in the Act** |
| NZ-CO-137 | Companies Act 1993 s137 (with s131) | Director duty of care, diligence and skill; duty to act in good faith and best interests | legislation | Company directors |
| NZ-FMC | Financial Markets Conduct Act 2013 | Conduct/disclosure obligations | sector_requirement | FMC reporting entities / licensed providers only |
| NZ-NCSC | NCSC guidance / NZISM | Baseline cyber-security controls | guidance / standard | Guidance (NZISM: government/public sector) |

### United Arab Emirates (AE)
| ID | Law / instrument | Provision | legal_status | Applies to |
|---|---|---|---|---|
| AE-PDPL-SEC | Federal Decree-Law No. 45 of 2021 (PDPL) | Security of processing — appropriate technical & organisational measures (article ref **to_verify**) | legislation *(Executive Regulations pending — enforceability of specifics not yet fully operational)* | Onshore-UAE controllers/processors (subject to scope exclusions); **not** DIFC/ADGM entities |
| AE-PDPL-BREACH | Federal Decree-Law No. 45 of 2021 (PDPL) | Personal-data-breach notification to the UAE Data Office and affected data subjects (article ref **to_verify**) | legislation *(pending Executive Regulations)* | Onshore-UAE controllers |
| AE-DIFC-DP | DIFC Data Protection Law No. 5 of 2020 | Security & breach obligations | regulation | **DIFC-registered entities only** |
| AE-ADGM-DP | ADGM Data Protection Regulations 2021 | Security & breach obligations | regulation | **ADGM-registered entities only** |
| AE-IA | UAE Information Assurance Regulation (TDRA/NESA); Dubai ISR | Information-assurance controls | sector_requirement | Government, critical information infrastructure, and covered sectors |

### India (IN)
| ID | Law / instrument | Provision | legal_status | Applies to |
|---|---|---|---|---|
| IN-ITA-43A | Information Technology Act 2000 s43A + SPDI Rules 2011 | Reasonable security practices and procedures for sensitive personal data (ISO/IEC 27001 recognised); compensation for negligent handling | legislation + regulation *(currently in force — operative security obligation today)* | Body corporate handling sensitive personal data or information |
| IN-CERTIN | CERT-In Directions dated 28 Apr 2022 (under IT Act s70B) | Report specified cyber incidents **within 6 hours**; log retention (180 days) | binding_direction *(in force)* | Service providers, intermediaries, data centres, body corporate |
| IN-DPDP-8 | Digital Personal Data Protection Act 2023 s8(5)/s8(6); Schedule | Reasonable security safeguards; breach notification to the Board and Data Principals; penalties up to **₹250 crore** | legislation *(ENACTED but **NOT yet in force** — awaiting notified Rules; do not present as an active obligation)* | Data Fiduciaries (once commenced) |
| IN-SECTOR | RBI / SEBI / IRDAI cyber directions | Sector cyber-security frameworks | sector_requirement | Regulated banks/NBFCs, market intermediaries, insurers only |

---

## 5. Exact-Clause Standards (clause records)

Each clause in the JSON `clause_library` carries: `law_name`, `clause_reference`, `clause_title`, `plain_english_summary`, `why_relevant`, `applicability_conditions`, `source` (official-source description/URL), `effective_date`, `last_verified_date`, `legal_status`. **Standards (ISO/E8/CIS/PCI/SOC2) are kept in a separate `framework_catalog` and never presented as legislation.** Example (abbreviated; full set in JSON):

- **AU-PRIV-APP11** — *Privacy Act 1988 (Cth), Australian Privacy Principle 11.* "An APP entity must take reasonable steps to protect personal information it holds from misuse, interference, loss, and unauthorised access, modification or disclosure." why_relevant: technical security weaknesses may indicate the reasonable-steps standard is not met. applicability: APP entity (turnover > A$3M or exception). source: OAIC APP Guidelines, Ch 11. legal_status: legislation. last_verified_date: **to_verify**.
- **NZ-PRIV-IPP5** — *Privacy Act 2020, Information Privacy Principle 5.* "An agency that holds personal information must ensure it is protected by such security safeguards as are reasonable in the circumstances." applicability: any agency. source: Privacy Act 2020 (NZ), s22 IPP 5. legal_status: legislation.
- **IN-CERTIN** — *CERT-In Directions (28 Apr 2022), para (ii).* "Report cyber incidents within six hours of noticing or being brought to notice." legal_status: binding_direction (in force). source: CERT-In Direction No. 20(3)/2022.
- **IN-DPDP-8** — *DPDP Act 2023, s8(5).* marked `legal_status: legislation`, `enforcement_status: not_in_force_pending_rules`. Must be shown as **forthcoming**, not active.

---

## 6. Safe Legal Wording Templates

Never use: "you are in breach", "legal violation confirmed", "you must report this incident", "the director is personally liable". Reusable templates (`wording_templates` in JSON):

| Template key | Text |
|---|---|
| `potential_compliance_gap` | "This finding **may indicate a gap against** {clause_reference} ({law_name}). A compliance review is recommended to confirm applicability." |
| `possible_notification_obligation` | "If personal information was actually exposed, this **may give rise to a notification obligation** under {law_name}. Whether it does depends on the facts — seek advice before notifying." |
| `governance_concern` | "This reflects a **governance gap**: {gap}. Technical fixes alone may not prevent recurrence." |
| `director_oversight_concern` | "Cyber-risk oversight **may be relevant to director/officer duties** under {clause_reference}, depending on the organisation's circumstances." |
| `sector_specific_applicability` | "{clause_reference} **applies only if** the organisation is {condition} (e.g. APRA-regulated / DIFC-registered / a Data Fiduciary once the Act commences)." |
| `guidance_only_mapping` | "{framework} is **guidance/standard, not law**. It is provided to help prioritise remediation." |
| `legal_review_recommendation` | "This is **regulatory intelligence, not legal advice**. Legal or compliance review may be required before relying on it." |
| `forthcoming_law` | "{law_name} is **enacted but not yet in force**; treat this as a forward-looking consideration, not a current obligation." |

---

## 7. Applicability Logic (when a clause displays)

A clause is shown only when **all** its `applicability_conditions` are satisfied. Inputs available/collectable:

| Condition | Source today | Notes |
|---|---|---|
| `country` (AU/NZ/AE/IN) | tenant record (trusted) | primary gate |
| `personal_information_exposed` | finding type (breach/cloud/email-identity = yes; config-only = no) | gates privacy-security + notification clauses |
| `actual_breach` vs `control_weakness` | finding semantics | notification clauses only on actual exposure |
| `incident_severity` | finding severity | drives priority + penalty framing |
| `industry` / `regulated_sector` | **not collected today — must add** | gates APRA/RBI/SEBI/IRDAI/SOCI |
| `financial_services` | not collected | gates AU-CPS234, NZ-FMC, IN-SECTOR |
| `healthcare` | not collected | gates AU small-biz exception (health providers lose exemption) |
| `government` | not collected | gates NZISM, mandatory E8 |
| `critical_infrastructure` | not collected | gates AU-SOCI, AU-CYBER-RANSOM threshold |
| `difc_registered` / `adgm_registered` | not collected | **must** gate AE-DIFC-DP / AE-ADGM-DP (do NOT apply to all AE tenants) |
| `annual_turnover` | not collected | gates AU-PRIV small-business exemption (A$3M) |

**Key correction vs current code:** today every AU tenant is shown APP 11 and every AE tenant would (if wired) be shown DIFC content — both over-apply. The model above requires `turnover`/`sector`/`difc_registered` flags. **Until those are collected, AU privacy clauses must carry the small-business caveat, and DIFC/ADGM must be suppressed by default.**

---

## 8. Framework Mapping (current references only)

Standards live in `framework_catalog`, clearly separated from legislation. Use **ISO/IEC 27001:2022 Annex A** (themes A.5–A.8); mark any 2013 numbering as legacy.

| Framework | Version | Example controls used |
|---|---|---|
| ISO/IEC 27001 | **2022** Annex A | A.8.24 (cryptography/TLS), A.8.23 (web filtering), A.8.9 (config mgmt), A.8.8 (technical vulnerabilities), A.8.7 (malware), A.5.17/A.8.5 (authentication), A.5.15/A.5.18 (access control), A.8.12 (data-leakage), A.8.13 (backup), A.5.30 (ICT continuity), A.5.24–5.26 (incident mgmt), A.5.7 (threat intel), A.5.19–5.22 (supplier) |
| ISO/IEC 27002 | 2022 | Implementation guidance for the above |
| NIST CSF | **2.0** | PR.AA (identity/auth), PR.DS (data security), PR.PS (platform security), PR.IR, DE.CM (monitoring), RS.MA/RS.AN (response), RC.RP (recovery), ID.RA (risk), GV.SC (supply chain) |
| CIS Controls | **v8** | 4 (secure config), 5 (account mgmt), 6 (access control/MFA), 7 (continuous vuln mgmt), 9 (email/web protections), 10 (malware defences), 11 (data recovery), 17 (incident response) |
| Essential Eight | current | patch apps, patch OS, MFA, restrict admin, application control, restrict macros, user-app hardening, regular backups |
| PCI DSS | **4.0.1** | Req 2 (secure config), 4 (strong crypto in transit), 5 (malware), 6 (secure systems/patch), 8 (auth/MFA), 11 (test security) — **only if cardholder data is processed** |
| SOC 2 | TSC 2017 (rev.) | CC6 (logical/physical access), CC7 (system ops/vuln), CC8 (change), A1 (availability) |

**Legacy note:** ISO 27001:2013 references currently in code (`A.9.4`, `A.12.6`, `regulatory_mapper.py:43,59-60`) are superseded — map A.9.4 → **A.5.15/A.8.5**, A.12.6 → **A.8.8**.

---

## 9. Priority Model

`priority = f(technical_severity, exploitability, public_exposure, breach_evidence, asset_criticality, business_impact, regulatory_relevance, ransomware_relevance, identity_privilege, active_exploitation)`.

| Priority | target_days | Trigger heuristics |
|---|---|---|
| **Critical** | 0 (immediate) | active exploitation / confirmed breach exposure of personal data / internet-exposed RDP-SMB-Telnet / public storage of personal data / malware-blacklist hit |
| **High** | 7 | internet-facing high-risk service, missing DMARC (BEC), MFA gap on privileged/identity, exploitable outdated software, invalid TLS on data-collecting site |
| **Medium** | 30 | SPF missing, cert expiring, admin sprawl, external sharing, dormant accounts, SSH/FTP exposure |
| **Low** | 90 | missing security headers, server/tech disclosure, low-risk hygiene |
| **Informational** | monitor/accept | passed checks, low-confidence signals, typosquat with no active use |

**Penalties are never presented as guaranteed loss** — always "indicative maximum … depending on circumstances", per §6.

---

## 10. Worked Per-Finding × Country Mappings (scanner-backed findings)

Shared fields shown once; the 4-country table lists laws/clauses (by §5 ID), penalty context, and confidence. Full records are in the JSON. **All wording uses §6 templates.**

### 10.1 EMAIL_DMARC_MISSING — Missing DMARC (email) · Real (`email_scan.py`)
- **technical_risk:** Without DMARC, receivers can't verify From-domain alignment → domain spoofing / BEC / phishing of customers and staff.
- **business_impacts:** invoice fraud, brand abuse, customer deception, deliverability loss.
- **governance_impact:** no email-security policy / anti-impersonation control.
- **director context (template `director_oversight_concern`):** email-fraud exposure may be relevant to director oversight duties depending on circumstances.
- **remediation:** publish SPF, then DKIM, then a DMARC record starting `p=none` for monitoring and progress to `p=quarantine`/`p=reject`.
- **priority:** High · **target_days:** 7 · **closure_evidence:** DNS TXT `_dmarc` showing an enforcing policy; re-scan pass.
- **frameworks:** ISO A.8.23; NIST PR.PS; CIS 9; E8 (email hardening); *not PCI-specific.*

| Country | applicable_clauses | penalty_context | confidence |
|---|---|---|---|
| AU | AU-PRIV-APP11 (reasonable steps), AU-ACL (if security claims made) | APP-11 gap *may* be relevant for APP entities (turnover>A$3M/exception); indicative max AU-PRIV-PENALTY on serious/repeated interference | to_verify |
| NZ | NZ-PRIV-IPP5 | reasonable-safeguards gap; Commissioner may investigate — no fixed penalty | to_verify |
| AE | AE-PDPL-SEC | security-measures gap under PDPL (Executive Regulations pending) | to_verify |
| IN | IN-ITA-43A, IN-CERTIN (if incident) | reasonable-security-practices gap under IT Act s43A/SPDI (in force); DPDP forthcoming | to_verify |

### 10.2 EMAIL_SPF_MISSING — Missing SPF · Real
Same clause set as 10.1; **priority Medium / 30d**; remediation: publish an SPF record listing authorised senders, end with `~all`/`-all`; evidence: DNS TXT SPF + re-scan.

### 10.3 TLS_CERT_INVALID / TLS_CERT_EXPIRED — Invalid/expired certificate · Real
- **technical_risk:** data in transit may be interceptable; browser warnings; loss of trust.
- **priority:** High / 7d (invalid), Medium / 30d (expiring).
- **frameworks:** ISO A.8.24; NIST PR.DS; CIS 3/4; PCI Req 4 (*if cardholder data*).

| Country | applicable_clauses | penalty_context |
|---|---|---|
| AU | AU-PRIV-APP11 (transmission security, if PI collected) | indicative APP-entity exposure |
| NZ | NZ-PRIV-IPP5 | reasonable-safeguards gap |
| AE | AE-PDPL-SEC | security-measures gap (ER pending) |
| IN | IN-ITA-43A | s43A reasonable-practices gap |

### 10.4 HDR_* — Missing security headers (HSTS/CSP/XCTO/XFO) · Shallow
- **priority:** Low / 90d. **frameworks:** ISO A.8.9/A.8.23; NIST PR.PS; CIS 4. **penalty_context:** hardening/hygiene — *control weakness, not a breach*; privacy clauses only as "reasonable steps" context. All countries `confidence: to_verify`.

### 10.5 WEB_SERVER_DISCLOSURE / SOFTWARE_OUTDATED · Real (shallow)
- **priority:** disclosure Low/90d; outdated software High/7d (or Critical if known-exploited). **frameworks:** ISO A.8.8; NIST ID.RA/PR.PS; CIS 7; E8 (patch apps/OS). Privacy clauses as reasonable-steps context; **no CVE/CVSS today** (limitation).

### 10.6 BREACH_EMAIL_EXPOSED — Email/credential found in breach · Real (`darkweb_scan`, `hibp_watch`)
- **technical_risk:** credential stuffing / account takeover from reused passwords.
- **priority:** Critical (if credentials) / immediate. **evidence:** forced password reset + MFA enforced; monitor for reuse.
- **This is the one finding where notification clauses genuinely engage — but only if the org's *own* personal data was compromised, which HIBP domain exposure does not by itself establish.**

| Country | applicable_clauses | penalty_context |
|---|---|---|
| AU | AU-PRIV-APP11, **AU-PRIV-NDB (possible_notification_obligation)** | eligible-breach assessment may be required; indicative AU-PRIV-PENALTY max |
| NZ | NZ-PRIV-IPP5, **NZ-PRIV-NOTIF** ("as soon as practicable"; *not* 72h) | notify if serious harm likely |
| AE | AE-PDPL-SEC, **AE-PDPL-BREACH** (ER pending) | breach-notification may apply once ER operative |
| IN | IN-ITA-43A, **IN-CERTIN (6-hour incident reporting, in force)**; IN-DPDP-8 forthcoming | CERT-In reporting may apply to a qualifying incident |

### 10.7 CLOUD_STORAGE_PUBLIC — Public cloud storage · Real (shallow, S3)
- **priority:** Critical / immediate (if personal data). Richest privacy mapping. Uses `possible_notification_obligation`.

| Country | applicable_clauses |
|---|---|
| AU | AU-PRIV-APP11, AU-PRIV-NDB, AU-CORP-180 (governance) |
| NZ | NZ-PRIV-IPP5, NZ-PRIV-NOTIF, NZ-CO-137 |
| AE | AE-PDPL-SEC, AE-PDPL-BREACH |
| IN | IN-ITA-43A, IN-CERTIN, IN-DPDP-8 (forthcoming) |

### 10.8 PORT_RDP_EXPOSED / PORT_SMB_EXPOSED / PORT_TELNET_EXPOSED · Real (passive)
- **priority:** Critical / immediate (primary ransomware entry points). **frameworks:** ISO A.8.9/A.8.20; NIST PR.AA/PR.PS; CIS 4/12; E8 (restrict admin, patch OS). **AU adds AU-CYBER-RANSOM context** (ransomware-payment reporting *if* over threshold/CI — `sector_specific_applicability`). SSH/FTP → High/Medium.

### 10.9 M365_MFA_GAP / GWS_MFA_GAP / SAAS_MFA_GAP · Real
- **priority:** High / 7d. **frameworks:** ISO A.5.17/A.8.5; NIST PR.AA; CIS 6; E8 (MFA). **evidence:** MFA/2SV enrolment report. Privacy clauses as reasonable-steps context; identity privilege raises director-oversight relevance.

### 10.10 M365_PRIV_ROLE / GWS_ADMIN_RISK / SAAS_ADMIN_RATIO — Excessive privilege · Real
- **priority:** Medium / 30d (High if combined with no-MFA). **frameworks:** ISO A.5.15/A.5.18; NIST PR.AA; CIS 5/6; E8 (restrict admin). director_oversight_concern applies.

### 10.11 M365_INACTIVE / GWS_INACTIVE / SAAS_DORMANT — Dormant accounts · Real
- **priority:** Medium / 30d. **frameworks:** ISO A.5.18; NIST PR.AA; CIS 5.

### 10.12 M365_EXTERNAL_SHARING / GWS_EXTERNAL_SHARING — External sharing · Real
- **priority:** High/Medium. **frameworks:** ISO A.5.14/A.8.12; NIST PR.DS; CIS 3. Privacy clauses engage where personal data is shared externally.

### 10.13 MALWARE_BLACKLIST / TI_IP_REPUTATION / TI_DOMAIN_BLACKLIST · Real
- **priority:** Critical. **frameworks:** ISO A.8.7; NIST DE.CM/PR.PS; CIS 10. director/DLS relevance.

### 10.14 TI_TYPOSQUAT / TI_BRAND_IMPERSONATION · Real/Partial
- **priority:** Medium (monitor) → High if active impersonation. **frameworks:** ISO A.5.7; NIST ID.RA/DE.CM. AU-ACL / consumer-protection context possible; mostly brand/fraud risk rather than a privacy obligation.

*(Full field-level records for all of the above — including every country's `regulatory_relevance`, `legal_wording`, `source_references`, dates and `confidence` — are in `docs/regulatory_intelligence_mapping.json`.)*

---

## 11. Required Tables

### B. Country coverage (per finding)
Complete = full clause mapping authored · Partial = generic/reasonable-steps only · Missing = to author · N/A.

| Finding | AU | NZ | AE | IN |
|---|---|---|---|---|
| EMAIL_SPF_MISSING | Complete | Complete | Partial | Partial |
| EMAIL_DMARC_MISSING | Complete | Complete | Partial | Partial |
| TLS_CERT_INVALID/EXPIRED | Complete | Complete | Partial | Partial |
| TLS_CERT_EXPIRING | Complete | Complete | Partial | Partial |
| HDR_* headers | Partial | Partial | Partial | Partial |
| WEB_SERVER_DISCLOSURE | Partial | Partial | Partial | Partial |
| SOFTWARE_OUTDATED | Complete | Complete | Partial | Partial |
| BREACH_EMAIL_EXPOSED | Complete | Complete | Partial | Complete (CERT-In) |
| CLOUD_STORAGE_PUBLIC | Complete | Complete | Partial | Partial |
| PORT_RDP/SMB/TELNET_EXPOSED | Complete | Complete | Partial | Partial |
| PORT_SSH/FTP_EXPOSED | Complete | Complete | Partial | Partial |
| MALWARE_BLACKLIST / TI_* | Complete | Complete | Partial | Partial |
| TI_TYPOSQUAT | Partial | Partial | Partial | Partial |
| M365/GWS/SAAS MFA/admin/inactive/sharing | Complete | Complete | Partial | Partial |
| All `Proposed` governance/DNS/identity codes | Missing | Missing | Missing | Missing |

"Partial" for AE reflects that PDPL article numbers and enforceability are **to_verify** (Executive Regulations pending). "Partial" for IN reflects reliance on IT Act s43A/SPDI/CERT-In (in force) while DPDP is forthcoming.

### C. Clause coverage
| Country | Law / instrument | # clauses defined | Finding types mapped |
|---|---|---|---|
| AU | Privacy Act 1988 (APP 11, NDB, s13G, tort) | 4 | email, tls, web, breach, cloud, ports, identity/cloud-posture |
| AU | Corporations Act 2001 s180 | 1 | cloud, ports, identity (governance) |
| AU | Cyber Security Act 2024 (ransomware reporting) | 1 | ports/ransomware-relevant (sector-gated) |
| AU | SOCI / CPS 234 / ACL / Essential Eight | 4 | sector-gated / guidance |
| NZ | Privacy Act 2020 (IPP 5, Part 6 notif) | 2 | email, tls, web, breach, cloud, ports, posture |
| NZ | Companies Act 1993 s137/s131 | 1 | cloud, ports (governance) |
| NZ | FMC / NCSC-NZISM | 2 | sector-gated / guidance |
| AE | PDPL 2021 (security, breach) | 2 | email, tls, breach, cloud, posture (to_verify) |
| AE | DIFC / ADGM / IA Regulation | 3 | registration-/sector-gated only |
| IN | IT Act s43A + SPDI Rules | 1 | email, tls, web, breach, cloud, posture (in force) |
| IN | CERT-In Directions 2022 | 1 | breach/incident (in force) |
| IN | DPDP Act 2023 (forthcoming) | 1 | privacy findings (mark forthcoming) |
| IN | RBI/SEBI/IRDAI | 1 | sector-gated |

### D. Existing vs required mapping
| Finding | Current mapping (in code) | Gap | Required action |
|---|---|---|---|
| Core 6-engine findings | NZ+AU clause strings hardcoded on finding; frontend strips other country | AE/IN clauses never attached; `filterRegulations` empties AE/IN | Attach country-resolved clauses server-side from this matrix; drop client-side string filtering |
| AE tenants | routed to NZ default (AE/UAE bug) | wrong country entirely | Apply §1 migration + AE clause set |
| IN tenants | framework tiles + penalty only; no per-finding clause | no per-finding IN clause | Attach IN-ITA-43A/CERT-In per finding |
| MS365/GWS/threat-intel | governance text; sparse clauses | thin statutory mapping | Add identity/privacy clause set per §10.9–10.13 |
| Notification wording | "must be reported within 72 hours" (NZ) | inaccurate | Replace with `possible_notification_obligation` / NZ "as soon as practicable" |
| `regulatory_mapper.py` | country-aware but **dormant** (not displayed) | superior coverage unused | Replace with this matrix as single source of truth |
| `governance_mapper.py` | **dead code** | unused | Retire |

### E. Legal accuracy risks
| Current wording / reference | Problem | Corrected approach |
|---|---|---|
| "regulatory breach confirmed" (`regulatory_mapper.py:118`) | asserts a confirmed legal breach | `potential_compliance_gap` template |
| "This **is** a serious privacy breach … **must** be reported within 72 hours" (`cloud_scan.py:103-104`) | definitive legal conclusion + wrong NZ deadline | "may constitute a notifiable breach … may require notification — seek review" |
| NZ "within 72 hours" (`darkweb_scan.py`, `dashboard.py:353`) | no fixed NZ 72h rule | "as soon as practicable" (NZ-PRIV-NOTIF) |
| AU "$50M … amended Dec 2024" (`dashboard.py:209`, `page.tsx:633`) | penalty from 2022 Act, not Dec 2024 | attribute to s13G (2022); frame as indicative maximum |
| AU NDB "notify within 30 days" | 30 days is the *assessment* window | "assess within 30 days; notify as soon as practicable if eligible" |
| APP 11 shown to all AU tenants | ignores A$3M small-business exemption | gate by turnover/sector; add caveat |
| DIFC/ADGM implied for all UAE | applies only to DIFC/ADGM entities | gate by registration; suppress by default |
| India DPDP Rs 250cr as active | DPDP not yet in force | `forthcoming_law`; rely on IT Act s43A/CERT-In now |
| ISO `A.9.4` / `A.12.6` (`regulatory_mapper.py:43,59`) | ISO 27001:2013 legacy numbering | map to 2022 A.5.15/A.8.5 and A.8.8 |
| "Non-compliant" score label (`page.tsx:614`) | definitive compliance verdict | "Significant gaps" / "Below target" |

### F. Implementation priority
| Priority | Mapping work | Reason |
|---|---|---|
| P0 | Adopt canonical `AE` code + remove `"UAE"` branches (§1) | UAE customers currently get NZ law — factually wrong |
| P0 | Replace unsafe wording (Table E) with §6 templates | legal-exposure / misrepresentation risk |
| P1 | Move per-finding clause resolution server-side from this matrix (trusted country) | fixes AE/IN empty chips; single source of truth |
| P1 | India: attach IT Act s43A + CERT-In per finding; mark DPDP forthcoming | India currently has no per-finding clause; DPDP mis-stated as active |
| P2 | Collect `turnover`, `sector`, `difc/adgm` flags for applicability gating (§7) | stop over-applying APP 11 / DIFC / sector rules |
| P2 | Update frameworks to ISO 27001:2022 / NIST CSF 2.0 / CIS v8 / PCI 4.0.1 | current-reference accuracy |
| P3 | Author `Proposed` findings (DNS, DKIM, backups, IR, etc.) using this schema | catalogue completeness |
| P3 | External legal verification of every `to_verify` clause (AU/NZ/AE/IN) | production sign-off |

---

## 12. Conclusion

1. **Total current finding types (scanner-backed):** ~34 Real/Shallow + ~9 Partial.
2. **Total proposed canonical finding types (full catalogue):** **85** codes.
3. **Existing AU mappings:** substantive per-finding clause mapping exists today (NZ+AU strings on core findings) → **~15 finding types Complete for AU** in this matrix.
4. **Existing NZ mappings:** **~15 Complete** (NZ is the code's default/base and best-covered).
5. **Existing AE mappings:** **effectively 0 delivered today** (AE/UAE bug routes to NZ); this matrix defines AE at **Partial** (PDPL to_verify) pending legal verification.
6. **Existing IN mappings:** **framework/penalty-level only today**; this matrix adds per-finding IT Act s43A/CERT-In (in force) and marks DPDP forthcoming.
7. **Missing mappings by country:** AE — all per-finding (author + verify); IN — all per-finding clause depth; AU/NZ — the ~42 `Proposed` finding types; all four — applicability gating inputs (turnover/sector/DIFC-ADGM).
8. **Incorrect or outdated clauses:** NZ "72-hour" rule; AU "$50M/Dec-2024" attribution + APP-11 over-application; AU NDB "30-day notify"; DPDP-as-active; DIFC/ADGM-for-all-UAE; ISO 27001:2013 numbering; "regulatory breach confirmed" / "you must report" wording.
9. **Highest-priority legal corrections:** (a) canonical `AE`; (b) replace definitive breach/notification wording with §6 templates; (c) NZ "as soon as practicable"; (d) India DPDP → forthcoming, use s43A/CERT-In now; (e) gate APP 11 (turnover) and DIFC/ADGM (registration).
10. **Exact implementation sequence:** P0 canonical codes + safe wording → P1 server-side per-finding clause resolution from this matrix (retire `regulatory_mapper.py`/`governance_mapper.py`) + India in-force clauses → P2 applicability inputs + 2022/2.0/v8 framework refresh → P3 author `Proposed` findings + external legal verification of all `to_verify` records → only then wire the JSON into the production engine.

*Regulatory intelligence, not legal advice. No code, data, or deployment changed.*
