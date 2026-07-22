# backend/tests/test_regulatory_intelligence.py
# Proves the single-source regulatory resolver: country correctness (incl. AE not
# NZ), no unsafe fallback, applicability gating, legal-status separation, safe
# wording, full 12-code coverage, and clause-reference integrity.

import pytest
from services import regulatory_intelligence as ri


# ── Country normalisation & canonical codes ─────────────────────────────────
def test_uae_normalises_to_ae():
    assert ri.normalize_country("UAE") == "AE"
    assert ri.normalize_country("uae") == "AE"
    assert ri.normalize_country("AE") == "AE"


@pytest.mark.parametrize("bad", ["PI", "OTHER", "XX", "", None, "AUS", "Australia"])
def test_unknown_country_is_none(bad):
    assert ri.normalize_country(bad) is None


# ── Country-correct mappings (no NZ fallback) ───────────────────────────────
def test_au_tenant_receives_au_mapping():
    r = ri.resolve("EMAIL_DMARC_MISSING", "AU")
    assert r["jurisdiction"] == "AU"
    ids = [c["clause_id"] for c in r["applicable_clauses"]]
    assert "AU-PRIV-APP11" in ids
    assert not any(cid.startswith("NZ") for cid in ids)


def test_nz_tenant_receives_nz_mapping():
    r = ri.resolve("EMAIL_DMARC_MISSING", "NZ")
    assert r["jurisdiction"] == "NZ"
    ids = [c["clause_id"] for c in r["applicable_clauses"]]
    assert "NZ-PRIV-IPP5" in ids
    assert not any(cid.startswith("AU") for cid in ids)


def test_ae_tenant_receives_uae_federal_not_nz():
    # The AE/UAE bug fix: an AE tenant must get UAE PDPL, never NZ.
    r = ri.resolve("EMAIL_DMARC_MISSING", "AE")
    assert r["jurisdiction"] == "AE"
    assert r["jurisdiction_label"] == "United Arab Emirates"
    ids = [c["clause_id"] for c in r["applicable_clauses"]]
    assert "AE-PDPL-SEC" in ids
    assert not any(cid.startswith("NZ") for cid in ids)
    # And the legacy string 'UAE' resolves to the same AE mapping.
    assert ri.resolve("EMAIL_DMARC_MISSING", "UAE")["jurisdiction"] == "AE"


def test_in_tenant_receives_operative_indian_mapping():
    # India's operative security law today is IT Act s43A (not DPDP, which is
    # enacted-but-not-in-force).
    r = ri.resolve("EMAIL_DMARC_MISSING", "IN")
    assert r["jurisdiction"] == "IN"
    ids = [c["clause_id"] for c in r["applicable_clauses"]]
    assert "IN-ITA-43A" in ids
    # Breach findings additionally engage the in-force CERT-In 6-hour direction.
    rb = ri.resolve("BREACH_EMAIL_EXPOSED", "IN")
    bids = [c["clause_id"] for c in rb["applicable_clauses"]]
    assert "IN-CERTIN" in bids


def test_unknown_country_does_not_fall_back_to_nz():
    for bad in ["PI", "OTHER", "XX", None]:
        assert ri.resolve("EMAIL_DMARC_MISSING", bad) is None


def test_frontend_cannot_override_country():
    # The resolver only honours the country argument (from the trusted tenant
    # record). Anything a caller might smuggle in `context` is ignored for
    # jurisdiction selection.
    r = ri.resolve("EMAIL_DMARC_MISSING", "AU", context={"country": "NZ", "jurisdiction": "NZ"})
    assert r["jurisdiction"] == "AU"


# ── Applicability gating: DIFC/ADGM & sector clauses fail closed ────────────
def test_difc_adgm_not_applied_without_registration():
    lib = ri._DATA["countries"]["AE"]["clause_library"]
    assert "AE-DIFC-DP" in lib and "AE-ADGM-DP" in lib
    # Without registration flags, gated clauses are excluded.
    assert ri._clause_applies("AE-DIFC-DP", lib["AE-DIFC-DP"], {}) is False
    assert ri._clause_applies("AE-ADGM-DP", lib["AE-ADGM-DP"], {}) is False
    # With the flag, they apply.
    assert ri._clause_applies("AE-DIFC-DP", lib["AE-DIFC-DP"], {"difc_registered": True}) is True
    # No scanner-backed AE mapping surfaces DIFC/ADGM by default.
    for code in ri.SCANNER_BACKED_CODES:
        r = ri.resolve(code, "AE")
        if r:
            ids = [c["clause_id"] for c in r["applicable_clauses"]]
            assert "AE-DIFC-DP" not in ids and "AE-ADGM-DP" not in ids


def test_sector_clauses_gated():
    au = ri._DATA["countries"]["AU"]["clause_library"]
    assert ri._clause_applies("AU-CPS234", au["AU-CPS234"], {}) is False
    assert ri._clause_applies("AU-CPS234", au["AU-CPS234"], {"apra_regulated": True}) is True


# ── Legal-status separation (guidance != legislation) ───────────────────────
def test_guidance_labelled_separately_from_legislation():
    # GOV_NO_BACKUP (AU) mixes legislation (AU-CORP-180) and guidance (AU-E8).
    r = ri.resolve("GOV_NO_BACKUP", "AU")
    groups = r["clauses_by_legal_status"]
    assert "legislation" in groups
    assert "guidance" in groups
    e8 = ri._DATA["countries"]["AU"]["clause_library"]["AU-E8"]
    assert e8["legal_status"] == "guidance"
    app11 = ri._DATA["countries"]["AU"]["clause_library"]["AU-PRIV-APP11"]
    assert app11["legal_status"] == "legislation"


def test_forthcoming_law_labelled():
    dpdp = ri._DATA["countries"]["IN"]["clause_library"]["IN-DPDP-8"]
    assert dpdp.get("enforcement_status") == "not_in_force_pending_rules"


# ── Safe wording ────────────────────────────────────────────────────────────
def test_no_unsafe_wording_anywhere_in_mappings():
    for fn in ri._DATA["findings"]:
        for cc, m in fn["mappings"].items():
            for field in ("legal_wording", "regulatory_relevance", "penalty_context", "technical_description"):
                assert not ri.contains_unsafe_wording(m.get(field, "")), (fn["finding_code"], cc, field)


def test_sanitizer_rewrites_legacy_cloud_text():
    legacy = ("A cloud storage area was found. This is a serious privacy breach under both NZ and AU "
              "privacy law and must be reported to the relevant authority within 72 hours.")
    fixed = ri.sanitize_wording(legacy)
    assert not ri.contains_unsafe_wording(fixed)
    assert "72 hours" not in fixed
    assert "may" in fixed.lower()


# ── Coverage & integrity ────────────────────────────────────────────────────
def test_all_scanner_backed_codes_resolve_in_all_countries():
    assert len(ri.SCANNER_BACKED_CODES) == 12
    for code in ri.SCANNER_BACKED_CODES:
        for cc in ["AU", "NZ", "AE", "IN"]:
            r = ri.resolve(code, cc)
            assert r is not None, (code, cc)
            assert r["jurisdiction"] == cc
            assert r["applicable_clauses"], (code, cc)
            assert r["disclaimer"]


def test_every_referenced_clause_exists():
    for fn in ri._DATA["findings"]:
        for cc, m in fn["mappings"].items():
            lib = ri._DATA["countries"][cc]["clause_library"]
            for cid in m.get("applicable_clauses", []):
                assert cid in lib, (fn["finding_code"], cc, cid)


# ── Finding-code resolution from scanner rows ───────────────────────────────
@pytest.mark.parametrize("engine,title,expected", [
    ("email", "Scammers can send emails pretending to be your business", "EMAIL_DMARC_MISSING"),
    ("email", "Your email domain has no sender protection", "EMAIL_SPF_MISSING"),
    ("website", "Your website security certificate expires in 5 days", "TLS_CERT_EXPIRING"),
    ("website", "Your website security certificate is invalid or missing", "TLS_CERT_INVALID"),
    ("website", "Your website is missing basic security protections", "HDR_SECURITY_HEADERS_MISSING"),
    ("devices", "Your web server version is publicly visible to hackers", "WEB_SERVER_DISCLOSURE"),
    ("cloud", "Your cloud files are visible to everyone on the internet", "CLOUD_STORAGE_PUBLIC"),
    ("network", "Windows remote access is open to the internet", "PORT_RDP_EXPOSED"),
    ("darkweb", "Staff email found in data breach", "BREACH_EMAIL_EXPOSED"),
    ("threat_intel", "Look-alike domain registered", "TI_TYPOSQUAT"),
    ("threat_intel", "Domain flagged on abuse blacklist", "MALWARE_BLACKLIST"),
])
def test_resolve_finding_code(engine, title, expected):
    assert ri.resolve_finding_code(engine, title) == expected


def test_web_server_disclosure_aliases_to_software_outdated():
    r = ri.resolve("WEB_SERVER_DISCLOSURE", "AU")
    assert r is not None
    assert r["finding_code"] == "SOFTWARE_OUTDATED"


def test_attach_to_finding_enriches_and_sanitises():
    finding = {"engine": "cloud", "title": "Your cloud files are visible to everyone on the internet",
               "severity": "critical",
               "description": "This is a serious privacy breach and must be reported within 72 hours.",
               "regulations": ["NZ Privacy Act 2020 - IPP 5"]}
    out = ri.attach_to_finding(finding, "AE")
    assert out["regulatory"]["jurisdiction"] == "AE"
    assert not ri.contains_unsafe_wording(out["description"])
    # original not mutated
    assert "72 hours" in finding["description"]
