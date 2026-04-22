# SecureIT360 - Dashboard Routes
# Country-aware: NZ and AU clients see different regulations and penalties
# Penalties are indicative only - not legal advice

from fastapi import APIRouter, HTTPException, Header
from services.database import supabase, supabase_admin

router = APIRouter()

DISCLAIMER = (
    "The information on this dashboard is for awareness purposes only and does not "
    "constitute legal advice. Penalty figures are indicative maximums based on current "
    "legislation as at April 2026 and may vary based on individual circumstances. "
    "Global Cyber Assurance recommends seeking independent legal advice regarding your "
    "specific compliance obligations. Contact: governance@secureit360.co"
)

RESIDUAL_STEPS = [
    "Staff privacy awareness training",
    "A documented privacy policy",
    "An incident response plan",
    "Regular governance reviews"
]


def calculate_ransom_score(findings: list) -> int:
    score = 0
    for f in findings:
        score += f.get("score_impact", 0)
    return min(100, score)


def calculate_governance_score(findings: list) -> int:
    gaps = [f for f in findings if f.get("governance_gap")]
    score = 100
    for f in gaps:
        if f.get("severity") == "critical":
            score -= 20
        elif f.get("severity") == "moderate":
            score -= 10
        elif f.get("severity") == "low":
            score -= 5
    return max(0, min(100, score))


def calculate_director_liability_score(findings: list) -> int:
    score = 0
    for f in findings:
        engine = f.get("engine", "")
        title = (f.get("title") or "").lower()

        if engine in ("microsoft365", "google_workspace"):
            if "inactive" in title and "account" in title:
                score += 10
            elif "mfa" in title or "2-step" in title or "2sv" in title:
                score += 5
            elif "admin" in title and "privilege" in title:
                score += 15

        elif engine == "threat_intel":
            if "data breach" in title or ("email account" in title and "exposed" in title):
                score += 20
            elif "typosquat" in title or "impersonat" in title:
                score += 25
            elif "flagged" in title and ("ip address" in title or "blacklist" in title or "abuse" in title):
                score += 10

    return min(100, score)


def get_penalty_info(findings: list, country: str) -> dict:
    has_critical = any(f["severity"] == "critical" for f in findings)
    has_moderate = any(f["severity"] == "moderate" for f in findings)

    if country == "AU":
        if has_critical:
            return {
                "ransom_demand": "AUD $85K - $220K (indicative)",
                "fine_exposure": "Up to $50M AUD - you have critical issues that must be fixed now",
                "fine_if_moderate": "Up to $3.3M AUD - if you fix your critical issues",
                "fine_if_low": "Up to $330K AUD - if you fix all critical and moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains because your business still holds personal data which creates ongoing obligations under the AU Privacy Act.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "High",
                "key_law": "AU Privacy Act 1988 (amended Dec 2024) + AU Cyber Security Act 2024",
                "new_risk": "Individuals may now sue your business directly for serious privacy invasion (from June 2025)",
                "ransom_reporting": "Ransomware payments must be reported to ASD within 72 hours",
                "disclaimer": DISCLAIMER
            }
        elif has_moderate:
            return {
                "ransom_demand": "AUD $85K - $220K (indicative)",
                "fine_exposure": "Up to $3.3M AUD - you have moderate issues that should be fixed",
                "fine_if_moderate": None,
                "fine_if_low": "Up to $330K AUD - if you fix all moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the AU Privacy Act.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Medium",
                "key_law": "AU Privacy Act 1988 (amended Dec 2024) + AU Cyber Security Act 2024",
                "new_risk": "OAIC can issue compliance notices without going to court",
                "ransom_reporting": "Ransomware payments must be reported to ASD within 72 hours",
                "disclaimer": DISCLAIMER
            }
        else:
            return {
                "ransom_demand": "AUD $85K - $220K (indicative)",
                "fine_exposure": "Up to $330K AUD - minor administrative risk only",
                "fine_if_moderate": None,
                "fine_if_low": None,
                "residual_risk": "Minimum regulatory exposure - your technical controls are in place.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Low",
                "key_law": "AU Privacy Act 1988 (amended Dec 2024) + AU Cyber Security Act 2024",
                "new_risk": "Maintaining low risk reduces OAIC enforcement likelihood significantly",
                "ransom_reporting": "Ransomware payments must be reported to ASD within 72 hours",
                "disclaimer": DISCLAIMER
            }

    elif country == "UAE":
        if has_critical:
            return {
                "ransom_demand": "AED 300K - 800K (indicative)",
                "fine_exposure": "Up to AED 5M - you have critical issues that must be fixed now",
                "fine_if_moderate": "Up to AED 1M - if you fix your critical issues",
                "fine_if_low": "Up to AED 250K - if you fix all critical and moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the UAE PDPL.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "High",
                "key_law": "UAE PDPL 2021 + UAE NESA Cybersecurity Standards",
                "new_risk": "UAE regulators actively enforcing PDPL since 2023",
                "ransom_reporting": "Cyber incidents must be reported to UAE NESA",
                "disclaimer": DISCLAIMER
            }
        elif has_moderate:
            return {
                "ransom_demand": "AED 300K - 800K (indicative)",
                "fine_exposure": "Up to AED 1M - you have moderate issues that should be fixed",
                "fine_if_moderate": None,
                "fine_if_low": "Up to AED 250K - if you fix all moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the UAE PDPL.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Medium",
                "key_law": "UAE PDPL 2021 + UAE NESA Cybersecurity Standards",
                "new_risk": "UAE regulators actively enforcing PDPL since 2023",
                "ransom_reporting": "Cyber incidents must be reported to UAE NESA",
                "disclaimer": DISCLAIMER
            }
        else:
            return {
                "ransom_demand": "AED 300K - 800K (indicative)",
                "fine_exposure": "Up to AED 250K - minor administrative risk only",
                "fine_if_moderate": None,
                "fine_if_low": None,
                "residual_risk": "Minimum regulatory exposure - your technical controls are in place.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Low",
                "key_law": "UAE PDPL 2021 + UAE NESA Cybersecurity Standards",
                "new_risk": "UAE regulators actively enforcing PDPL since 2023",
                "ransom_reporting": "Cyber incidents must be reported to UAE NESA",
                "disclaimer": DISCLAIMER
            }

    elif country == "IN":
        if has_critical:
            return {
                "ransom_demand": "Rs 70L - Rs 2Cr (indicative)",
                "fine_exposure": "Up to Rs 250 crore - you have critical issues that must be fixed now",
                "fine_if_moderate": "Up to Rs 50 crore - if you fix your critical issues",
                "fine_if_low": "Up to Rs 10 crore - if you fix all critical and moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the India DPDP Act.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "High",
                "key_law": "India DPDP Act 2023 + CERT-In Guidelines 2022",
                "new_risk": "CERT-In actively monitoring and enforcing since 2022",
                "ransom_reporting": "Cyber incidents must be reported to CERT-In within 6 hours",
                "disclaimer": DISCLAIMER
            }
        elif has_moderate:
            return {
                "ransom_demand": "Rs 70L - Rs 2Cr (indicative)",
                "fine_exposure": "Up to Rs 50 crore - you have moderate issues that should be fixed",
                "fine_if_moderate": None,
                "fine_if_low": "Up to Rs 10 crore - if you fix all moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the India DPDP Act.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Medium",
                "key_law": "India DPDP Act 2023 + CERT-In Guidelines 2022",
                "new_risk": "CERT-In actively monitoring and enforcing since 2022",
                "ransom_reporting": "Cyber incidents must be reported to CERT-In within 6 hours",
                "disclaimer": DISCLAIMER
            }
        else:
            return {
                "ransom_demand": "Rs 70L - Rs 2Cr (indicative)",
                "fine_exposure": "Up to Rs 10 crore - minor administrative risk only",
                "fine_if_moderate": None,
                "fine_if_low": None,
                "residual_risk": "Minimum regulatory exposure - your technical controls are in place.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Low",
                "key_law": "India DPDP Act 2023 + CERT-In Guidelines 2022",
                "new_risk": "CERT-In actively monitoring and enforcing since 2022",
                "ransom_reporting": "Cyber incidents must be reported to CERT-In within 6 hours",
                "disclaimer": DISCLAIMER
            }

    else:
        # NZ default
        if has_critical:
            return {
                "ransom_demand": "NZD $85K - $220K (indicative)",
                "fine_exposure": "Director personal liability - you have critical issues that must be fixed now",
                "fine_if_moderate": "Privacy Commissioner investigation - if you fix your critical issues",
                "fine_if_low": "Minimal exposure - if you fix all critical and moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the NZ Privacy Act.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "High",
                "key_law": "NZ Privacy Act 2020 + Privacy Amendment Act 2025 (IPP 3A from May 2026)",
                "new_risk": "NZ government actively strengthening cyber laws - financial penalties expected soon",
                "ransom_reporting": "Notifiable breach must be reported to Privacy Commissioner within 72 hours",
                "disclaimer": DISCLAIMER
            }
        elif has_moderate:
            return {
                "ransom_demand": "NZD $85K - $220K (indicative)",
                "fine_exposure": "Privacy Commissioner investigation - you have moderate issues that should be fixed",
                "fine_if_moderate": None,
                "fine_if_low": "Minimal exposure - if you fix all moderate issues",
                "residual_risk": "Even after fixing all issues, residual risk remains under the NZ Privacy Act.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Medium",
                "key_law": "NZ Privacy Act 2020 + Privacy Amendment Act 2025 (IPP 3A from May 2026)",
                "new_risk": "NZ PM publicly called to strengthen cybersecurity laws in February 2026",
                "ransom_reporting": "Notifiable breach must be reported to Privacy Commissioner within 72 hours",
                "disclaimer": DISCLAIMER
            }
        else:
            return {
                "ransom_demand": "NZD $85K - $220K (indicative)",
                "fine_exposure": "Minimal current exposure - your technical controls are in place",
                "fine_if_moderate": None,
                "fine_if_low": None,
                "residual_risk": "Residual risk remains under the NZ Privacy Act. Technical fixes alone cannot eliminate this risk.",
                "residual_steps": RESIDUAL_STEPS,
                "downtime": "14 - 28 days",
                "liability": "Low",
                "key_law": "NZ Privacy Act 2020 + Privacy Amendment Act 2025 (IPP 3A from May 2026)",
                "new_risk": "NZ government reviewing financial penalties - act now before laws strengthen",
                "ransom_reporting": "Notifiable breach must be reported to Privacy Commissioner within 72 hours",
                "disclaimer": DISCLAIMER
            }


_ALL_ENGINES = ["darkweb", "email", "network", "website", "devices", "cloud", "microsoft365", "google_workspace", "threat_intel"]
_EXTRA_FRAMEWORK_KEYS = {
    "GDPR": "gdpr",
    "HIPAA": "hipaa",
    "PCI-DSS": "pci_dss",
    "SOC 2": "soc2",
    "NIST CSF": "nist_csf",
}


def calculate_compliance_scores(findings: list, country: str, extra_frameworks: list = None) -> dict:
    def score_for_engines(engines: list) -> int:
        score = 100
        for f in findings:
            if f["engine"] in engines:
                if f["severity"] == "critical":
                    score -= 30
                elif f["severity"] == "moderate":
                    score -= 15
                elif f["severity"] == "low" and f.get("score_impact", 0) > 0:
                    score -= 5
        return max(0, min(100, score))

    if country == "AU":
        base = {
            "au_privacy": score_for_engines(["darkweb", "email", "cloud", "website", "microsoft365"]),
            "au_privacy_amendment": score_for_engines(["darkweb", "cloud", "email", "microsoft365"]),
            "au_corporations": score_for_engines(["darkweb", "network", "devices", "email", "website", "cloud", "microsoft365"]),
            "au_cyber_security_act": score_for_engines(["network", "devices", "cloud", "microsoft365"]),
            "essential_eight": score_for_engines(["email", "devices", "network", "website", "microsoft365"]),
            "iso_27001": score_for_engines(_ALL_ENGINES),
        }
    elif country in ("UAE", "AE"):
        base = {
            "uae_pdpl": score_for_engines(["darkweb", "email", "cloud", "website", "microsoft365"]),
            "uae_nesa": score_for_engines(["network", "devices", "cloud", "microsoft365"]),
            "iso_27001": score_for_engines(_ALL_ENGINES),
        }
    elif country == "IN":
        base = {
            "india_dpdp": score_for_engines(["darkweb", "email", "cloud", "website", "microsoft365"]),
            "cert_in": score_for_engines(["network", "devices", "cloud", "microsoft365"]),
            "iso_27001": score_for_engines(_ALL_ENGINES),
        }
    else:
        base = {
            "nz_privacy": score_for_engines(["darkweb", "email", "cloud", "website", "microsoft365"]),
            "nz_privacy_amendment": score_for_engines(["darkweb", "cloud", "microsoft365"]),
            "nz_companies": score_for_engines(["darkweb", "network", "devices", "email", "website", "cloud", "microsoft365"]),
            "nz_ncsc": score_for_engines(["email", "network", "website", "microsoft365"]),
            "essential_eight": score_for_engines(["email", "devices", "network", "website", "microsoft365"]),
            "iso_27001": score_for_engines(_ALL_ENGINES),
        }

    # Additional user-selected frameworks — all engines contribute
    extra = {}
    for fw in (extra_frameworks or []):
        key = _EXTRA_FRAMEWORK_KEYS.get(fw)
        if key and key not in base:
            extra[key] = score_for_engines(_ALL_ENGINES)

    return {**base, **extra, "selected_extra_frameworks": extra_frameworks or []}


@router.get("/")
def get_dashboard(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id, role, tenants(*)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]
        company_name = tenant_user.data["tenants"]["name"]
        plan = tenant_user.data["tenants"].get("plan")
        country = tenant_user.data["tenants"].get("country", "NZ") or "NZ"
        logo_url = tenant_user.data["tenants"].get("logo_url")
        status = tenant_user.data["tenants"].get("status", "trial")
        trial_ends_at = tenant_user.data["tenants"].get("trial_ends_at")
        extra_frameworks = tenant_user.data["tenants"].get("compliance_frameworks") or []

        findings = supabase_admin.table("findings")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .eq("status", "open")\
            .order("score_impact", desc=True)\
            .execute()

        if not findings.data:
            return {
                "company_name": company_name,
                "plan": plan,
                "country": country,
                "logo_url": logo_url,
            "status": status,
            "trial_ends_at": trial_ends_at,
                "message": "No scans completed yet.",
                "ransom_score": None,
                "governance_score": None,
                "findings_summary": None
            }

        ransom_score = calculate_ransom_score(findings.data)
        governance_score = calculate_governance_score(findings.data)
        director_liability_score = calculate_director_liability_score(findings.data)
        compliance = calculate_compliance_scores(findings.data, country, extra_frameworks)
        penalty_info = get_penalty_info(findings.data, country)

        real_findings = [f for f in findings.data if f.get("fix_type") != "info"]
        critical = [f for f in real_findings if f["severity"] == "critical"]
        moderate = [f for f in real_findings if f["severity"] == "moderate"]
        low = [f for f in real_findings if f["severity"] == "low"]

        return {
            "company_name": company_name,
            "plan": plan,
            "country": country,
            "logo_url": logo_url,
            "status": status,
            "trial_ends_at": trial_ends_at,
            "ransom_score": ransom_score,
            "governance_score": governance_score,
            "director_liability_score": director_liability_score,
            "findings_summary": {
                "critical": len(critical),
                "moderate": len(moderate),
                "low": len(low),
                "total": len(real_findings)
            },
            "top_findings": findings.data[:5],
            "compliance": compliance,
            "penalty_info": penalty_info
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



