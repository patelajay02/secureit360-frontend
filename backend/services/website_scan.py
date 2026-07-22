# SecureIT360 - Website and SSL Scan Engine
# Checks SSL certificate expiry and missing security headers with specific regulation clauses

import ssl
from datetime import datetime, timezone
from services.database import supabase_admin
from services.target_guard import get_peer_certificate, safe_get, TargetValidationError


def upsert_finding(tenant_id, scan_id, engine, severity, title, description, governance_gap, regulations, fix_type, score_impact):
    existing = supabase_admin.table("findings")\
        .select("id")\
        .eq("tenant_id", tenant_id)\
        .eq("engine", engine)\
        .eq("title", title)\
        .execute()

    if existing.data:
        supabase_admin.table("findings")\
            .update({
                "scan_id": scan_id,
                "severity": severity,
                "description": description,
                "governance_gap": governance_gap,
                "regulations": regulations,
                "fix_type": fix_type,
                "score_impact": score_impact,
                "status": "open"
            })\
            .eq("id", existing.data[0]["id"])\
            .execute()
        return False
    else:
        supabase_admin.table("findings").insert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": engine,
            "severity": severity,
            "title": title,
            "description": description,
            "governance_gap": governance_gap,
            "regulations": regulations,
            "fix_type": fix_type,
            "score_impact": score_impact,
            "status": "open"
        }).execute()
        return True


def check_ssl_expiry(domain: str) -> dict:
    # get_peer_certificate validates the target (rejecting private/localhost/
    # metadata addresses), pins to a validated IP, and verifies TLS.
    try:
        cert = get_peer_certificate(domain, 443, timeout=10)
        expiry_date_str = cert["notAfter"]
        expiry_date = datetime.strptime(
            expiry_date_str, "%b %d %H:%M:%S %Y %Z"
        ).replace(tzinfo=timezone.utc)
        days_remaining = (expiry_date - datetime.now(timezone.utc)).days
        return {"valid": True, "days_remaining": days_remaining}
    except TargetValidationError:
        return {"valid": False, "days_remaining": 0, "error": "Target not permitted"}
    except ssl.SSLCertVerificationError:
        return {"valid": False, "days_remaining": 0, "error": "Invalid certificate"}
    except Exception:
        return {"valid": False, "days_remaining": 0, "error": "Could not check SSL"}


async def check_security_headers(domain: str) -> dict:
    missing_headers = []
    important_headers = [
        "x-frame-options",
        "x-content-type-options",
        "strict-transport-security",
        "content-security-policy"
    ]
    try:
        # safe_get enforces SSRF validation, TLS verification, timeouts, and
        # size limits, and re-validates redirects.
        response = await safe_get(f"https://{domain}")
        headers = response.headers
        for header in important_headers:
            if header not in headers:
                missing_headers.append(header)
    except Exception:
        pass
    return {"missing_headers": missing_headers}


async def run_website_scan(tenant_id: str, scan_id: str, domain: str):
    try:
        findings_count = 0
        ssl_result = check_ssl_expiry(domain)

        if not ssl_result["valid"]:
            upsert_finding(
                tenant_id, scan_id, "website", "critical",
                "Your website security certificate is invalid or missing",
                (
                    f"Your website {domain} has an invalid SSL certificate. "
                    f"This means visitors see a security warning when they visit your site. "
                    f"Data sent between your website and your clients is not protected. "
                    f"Google also ranks sites without valid certificates lower in search results."
                ),
                "No asset lifecycle management process exists. SSL certificates are not being tracked or renewed before expiry.",
                [
                    "NZ Privacy Act 2020 - IPP 5 (security safeguards)",
                    "NZ Privacy Amendment Act 2025 - IPP 3A (data protection obligations)",
                    "AU Privacy Act 1988 - APP 11.1 (security of personal information)",
                    "AU Privacy Act 1988 - APP 11.2 (destruction of personal information)",
                    "AU Essential Eight ML1 - Patch applications"
                ],
                "voice", 15
            )
            findings_count += 1

        elif ssl_result["days_remaining"] < 30:
            severity = "critical" if ssl_result["days_remaining"] < 7 else "moderate"
            upsert_finding(
                tenant_id, scan_id, "website", severity,
                f"Your website security certificate expires in {ssl_result['days_remaining']} days",
                (
                    f"Your website {domain} security certificate expires in "
                    f"{ssl_result['days_remaining']} days. When it expires, visitors "
                    f"will see a warning saying your site is not secure. "
                    f"This will stop clients from trusting your website."
                ),
                "No asset lifecycle management process exists. SSL certificates are not being tracked or renewed before expiry.",
                [
                    "NZ Privacy Act 2020 - IPP 5 (security safeguards)",
                    "NZ Privacy Amendment Act 2025 - IPP 3A (data protection obligations)",
                    "AU Privacy Act 1988 - APP 11.1 (security of personal information)",
                    "AU Essential Eight ML1 - Patch applications"
                ],
                "voice", 10
            )
            findings_count += 1

        headers_result = await check_security_headers(domain)
        if len(headers_result["missing_headers"]) > 2:
            upsert_finding(
                tenant_id, scan_id, "website", "low",
                "Your website is missing basic security protections",
                (
                    f"Your website {domain} is missing {len(headers_result['missing_headers'])} "
                    f"security settings that protect your visitors. These settings tell "
                    f"web browsers how to handle your website safely. Without them, "
                    f"your website is more vulnerable to certain types of attacks."
                ),
                "No web security policy exists. Website security configuration is not being managed or reviewed.",
                [
                    "AU Essential Eight ML1 - Patch applications (web hardening)",
                    "NZ NCSC Guidelines - Web security baseline",
                    "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect data)",
                    "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
                ],
                "voice", 5
            )
            findings_count += 1

        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "website",
            "status": "complete",
            "findings_count": findings_count
        }).execute()

        return {"status": "complete", "findings_count": findings_count}

    except Exception as e:
        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "website",
            "status": "error",
            "findings_count": 0
        }).execute()
        return {"status": "error", "message": str(e)}
