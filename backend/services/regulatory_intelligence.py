# backend/services/regulatory_intelligence.py
# SecureIT360 - Regulatory intelligence resolver (SINGLE SOURCE OF TRUTH).
#
# Design decision (Phase 0, item 6 - Option A): the validated mapping is stored
# as a versioned config file at backend/data/regulatory_intelligence_mapping.json
# and loaded once here. It is READ-ONLY reference data (not tenant data), so it
# needs no RLS/tenant isolation; a file gives git-based version control (the
# audit flagged versioning as missing) and ships with the Railway app. A
# DB-backed table (Option B) is the future path once admin-editing is required.
#
# This module is the ONLY place that maps a technical finding to jurisdiction,
# law, clause, wording and legal-status. Scanners, dashboard and frontend must
# defer to it; the legacy regulatory_mapper.py / governance_mapper.py are retired.
#
# Country is ALWAYS supplied by the caller from the trusted tenant record - this
# module never reads a country from a request body.

import json
import os
from typing import Optional

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "regulatory_intelligence_mapping.json")

CANONICAL_COUNTRIES = {"AU", "NZ", "AE", "IN"}

# Unsafe phrases that must never reach a customer (Phase 0, item 4). Used both to
# assert our own content is clean and to sanitise legacy stored finding text.
UNSAFE_PHRASES = [
    "regulatory breach confirmed",
    "this is a serious privacy breach",
    "you are in breach",
    "legal violation confirmed",
    "you must report this incident",
    "the director is personally liable",
    "director is personally liable",
    "within 72 hours",  # NZ fixed-deadline claim (and over-specific elsewhere)
]

_DISCLAIMER = "Regulatory intelligence, not legal advice. A legal or compliance review may be required."


def _load():
    with open(os.path.abspath(_DATA_PATH), encoding="utf-8") as f:
        return json.load(f)


_DATA = _load()
_FINDINGS = {fn["finding_code"]: fn for fn in _DATA["findings"]}
_ALIASES = _DATA.get("resolver_aliases", {})
SCANNER_BACKED_CODES = list(_DATA.get("scanner_backed_finding_codes", []))
_WORDING_TEMPLATES = _DATA.get("wording_templates", {})


def normalize_country(raw: Optional[str]) -> Optional[str]:
    """Return a canonical code (AU/NZ/AE/IN) or None. Maps legacy 'UAE' -> 'AE'.

    Returns None for unknown/unsupported values - callers MUST fail closed
    (no silent New Zealand fallback).
    """
    if not raw or not isinstance(raw, str):
        return None
    v = raw.strip().upper()
    if v == "UAE":
        v = "AE"
    return v if v in CANONICAL_COUNTRIES else None


# ── Canonical finding-code resolution from a stored finding row ──────────────
def resolve_finding_code(engine: str, title: str) -> Optional[str]:
    """Map a scanner finding (engine + title) to a canonical finding_code.

    Covers the 12 scanner-backed codes. Returns None if no confident match
    (caller then omits regulatory intelligence rather than guessing).
    """
    e = (engine or "").lower()
    t = (title or "").lower()

    if e == "email":
        if "dmarc" in t or "pretending to be your business" in t:
            return "EMAIL_DMARC_MISSING"
        if "spf" in t or "sender protection" in t:
            return "EMAIL_SPF_MISSING"
    if e == "website":
        if "certificate" in t and ("expires in" in t or "expiring" in t):
            return "TLS_CERT_EXPIRING"
        if "certificate" in t or "ssl" in t:
            return "TLS_CERT_INVALID"
        if "security protections" in t or "header" in t:
            return "HDR_SECURITY_HEADERS_MISSING"
    if e == "devices":
        if "server version" in t or "publicly visible" in t:
            return "WEB_SERVER_DISCLOSURE"  # aliases to SOFTWARE_OUTDATED
        return "SOFTWARE_OUTDATED"
    if e == "darkweb" or e == "darkweb_realtime":
        return "BREACH_EMAIL_EXPOSED"
    if e == "cloud":
        return "CLOUD_STORAGE_PUBLIC"
    if e == "network":
        return "PORT_RDP_EXPOSED"  # represents any exposed remote/admin service
    if e == "threat_intel":
        if "typosquat" in t or "impersonat" in t or "look-alike" in t:
            return "TI_TYPOSQUAT"
        return "MALWARE_BLACKLIST"
    if e == "microsoft365" and ("mfa" in t or "two-factor" in t or "multi-factor" in t):
        return "M365_MFA_GAP"
    return None


def _clause_records(country: str, clause_ids: list, context: dict) -> list:
    """Resolve clause IDs to full records, applying applicability gating.

    Excludes clauses whose applicability conditions are not met (e.g. DIFC/ADGM
    without registration data; forthcoming laws are labelled, not hidden).
    """
    lib = _DATA["countries"][country]["clause_library"]
    out = []
    for cid in clause_ids:
        rec = lib.get(cid)
        if not rec:
            continue
        if not _clause_applies(cid, rec, context):
            continue
        out.append({
            "clause_id": cid,
            "law_name": rec.get("law_name"),
            "clause_reference": rec.get("clause_reference"),
            "clause_title": rec.get("clause_title"),
            "plain_english_summary": rec.get("plain_english_summary"),
            "legal_status": rec.get("legal_status"),
            "enforcement_status": rec.get("enforcement_status"),
            "source": rec.get("source"),
            "effective_date": rec.get("effective_date"),
            "last_verified_date": rec.get("last_verified_date"),
        })
    return out


def _clause_applies(clause_id: str, rec: dict, context: dict) -> bool:
    """Applicability gating. Fails CLOSED for free-zone/sector clauses when the
    required context flag is absent."""
    ctx = context or {}
    # DIFC / ADGM only when explicitly registered.
    if clause_id == "AE-DIFC-DP" and not ctx.get("difc_registered"):
        return False
    if clause_id == "AE-ADGM-DP" and not ctx.get("adgm_registered"):
        return False
    # Sector-gated clauses require the matching flag.
    if clause_id == "AU-CPS234" and not ctx.get("apra_regulated"):
        return False
    if clause_id == "AU-SOCI" and not ctx.get("critical_infrastructure"):
        return False
    if clause_id == "IN-SECTOR" and not ctx.get("regulated_sector"):
        return False
    return True


def resolve(finding_code: str, country: str, context: dict = None) -> Optional[dict]:
    """Resolve a canonical finding_code + trusted country to a regulatory panel.

    Returns None if the country is not canonical (caller must render a neutral
    'mapping unavailable' state - never a silent NZ fallback), or if the code is
    unknown.
    """
    cc = normalize_country(country)
    if cc is None:
        return None  # fail closed - unsupported country

    code = _ALIASES.get(finding_code, finding_code)
    fn = _FINDINGS.get(code)
    if not fn:
        return None
    mapping = fn.get("mappings", {}).get(cc)
    if not mapping:
        return None

    context = context or {}
    clauses = _clause_records(cc, mapping.get("applicable_clauses", []), context)

    # Group by legal status so guidance is never presented as legislation.
    by_status = {}
    for c in clauses:
        by_status.setdefault(c["legal_status"] or "unspecified", []).append(c)

    return {
        "finding_code": code,
        "finding_name": fn.get("finding_name"),
        "jurisdiction": cc,
        "jurisdiction_label": _DATA["countries"][cc]["name"],
        "severity_priority": mapping.get("priority"),
        "target_days": mapping.get("target_days"),
        "technical_risk": mapping.get("technical_risk"),
        "business_impacts": mapping.get("business_impacts", []),
        "governance_impact": mapping.get("governance_impact"),
        "director_or_management_context": mapping.get("director_or_management_context"),
        "regulatory_relevance": mapping.get("regulatory_relevance"),
        "penalty_context": mapping.get("penalty_context"),
        "applicable_clauses": clauses,
        "clauses_by_legal_status": by_status,
        "industry_framework_mappings": mapping.get("industry_framework_mappings", {}),
        "recommended_remediation": mapping.get("recommended_remediation"),
        "closure_evidence": mapping.get("closure_evidence", []),
        "legal_wording": mapping.get("legal_wording"),
        "disclaimer": _DISCLAIMER,
        # Internal-only signals (surface to admins, not customers):
        "_confidence": mapping.get("confidence"),
        "_review_owner": mapping.get("review_owner"),
        "_implementation_status": fn.get("implementation_status"),
    }


def attach_to_finding(finding: dict, country: str, context: dict = None) -> dict:
    """Return a shallow copy of a stored finding row enriched with a `regulatory`
    panel resolved from the trusted country, plus sanitised text. Never mutates
    the input. If no confident mapping, `regulatory` is None and the frontend
    shows a neutral state.
    """
    out = dict(finding)
    out["description"] = sanitize_wording(finding.get("description") or "")
    if finding.get("governance_gap"):
        out["governance_gap"] = sanitize_wording(finding["governance_gap"])
    code = resolve_finding_code(finding.get("engine", ""), finding.get("title", ""))
    out["regulatory"] = resolve(code, country, context) if code else None
    return out


def sanitize_wording(text: str) -> str:
    """Replace definitive legal conclusions in legacy stored finding text with
    approved potential-gap wording (Phase 0, item 4)."""
    if not text:
        return text
    replacements = [
        ("This is a serious privacy breach under both NZ and AU privacy law and must be reported to the relevant authority within 72 hours.",
         "This may constitute a notifiable privacy breach; whether notification is required depends on the facts. A legal or compliance review may be required."),
        ("must be reported to the relevant authority within 72 hours", "may require notification depending on the facts"),
        ("must be reported to the Privacy Commissioner within 72 hours", "may require notification to the Privacy Commissioner as soon as practicable"),
        ("within 72 hours", "as soon as practicable"),
        ("regulatory breach confirmed", "potential regulatory gap identified"),
        ("This is a serious privacy breach", "This may indicate a serious privacy risk"),
        ("you are in breach", "this may indicate a gap against"),
    ]
    out = text
    for bad, good in replacements:
        out = out.replace(bad, good)
    return out


def contains_unsafe_wording(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in UNSAFE_PHRASES)
