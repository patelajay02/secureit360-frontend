# SecureIT360 - Device and Software Scan Engine
# Checks for unpatched software and known vulnerabilities with specific regulation clauses

from services.database import supabase_admin
from services.target_guard import safe_get


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


async def check_common_vulnerabilities(domain: str) -> list:
    vulnerabilities = []

    try:
        # safe_get enforces SSRF validation, TLS verification, timeouts and size limits.
        response = await safe_get(f"https://{domain}")
        headers = response.headers
        server = headers.get("server", "").lower()
        x_powered_by = headers.get("x-powered-by", "").lower()

        if "php/" in x_powered_by:
            php_version = x_powered_by.split("php/")[-1].strip()
            major_version = int(php_version.split(".")[0]) if php_version else 0
            if major_version < 8:
                vulnerabilities.append({
                    "title": "Your website is running outdated software that has known security holes",
                    "description": (
                        f"Your website is running PHP version {php_version} which is outdated "
                        f"and no longer receiving security updates. Hackers actively target "
                        f"websites running old PHP versions because the security holes are "
                        f"publicly known. This needs to be updated by your web developer."
                    ),
                    "severity": "critical",
                    "score_impact": 12,
                    "governance_gap": "No patch management policy or process exists. Website software is not being updated on a regular schedule.",
                    "regulations": [
                        "AU Essential Eight ML1 - Patch applications (critical patches within 48 hours)",
                        "AU Essential Eight ML1 - Patch operating systems",
                        "NZ NCSC Guidelines - Patch management baseline",
                        "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
                        "AU Privacy Act 1988 (amended Dec 2024) - APP 11.1 (technical measures required)",
                        "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
                    ]
                })

        if "apache/" in server:
            apache_version = server.split("apache/")[-1].split(" ")[0]
            vulnerabilities.append({
                "title": "Your web server version is publicly visible to hackers",
                "description": (
                    f"Your website is revealing which web server software it uses "
                    f"(Apache {apache_version}). Hackers use this information to look up "
                    f"known vulnerabilities for that specific version and target your site. "
                    f"This information should be hidden from public view."
                ),
                "severity": "low",
                "score_impact": 5,
                "governance_gap": "No patch management process exists. Server configuration is not following security best practices.",
                "regulations": [
                    "AU Essential Eight ML1 - Patch applications",
                    "NZ NCSC Guidelines - Patch management baseline",
                    "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
                    "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
                ]
            })

    except Exception:
        pass

    return vulnerabilities


async def run_device_scan(tenant_id: str, scan_id: str, domain: str):
    try:
        findings_count = 0
        vulnerabilities = await check_common_vulnerabilities(domain)

        for vuln in vulnerabilities:
            upsert_finding(
                tenant_id, scan_id, "devices",
                vuln["severity"],
                vuln["title"],
                vuln["description"],
                vuln["governance_gap"],
                vuln["regulations"],
                "specialist" if vuln["severity"] == "critical" else "voice",
                vuln["score_impact"]
            )
            findings_count += 1

        if findings_count == 0:
            upsert_finding(
                tenant_id, scan_id, "devices", "low",
                "No obvious software vulnerabilities detected on your website",
                (
                    f"Your website does not appear to be running any "
                    f"obviously outdated software. However we recommend ensuring "
                    f"all computers and devices in your office are set to update "
                    f"automatically to stay protected."
                ),
                "Ensure a patch management process exists to keep all devices and software updated regularly.",
                [
                    "AU Essential Eight ML1 - Patch applications",
                    "NZ NCSC Guidelines - Patch management baseline",
                    "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
                    "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
                ],
                "info", 0
            )
            findings_count = 1

        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "devices",
            "status": "complete",
            "findings_count": findings_count
        }).execute()

        return {"status": "complete", "findings_count": findings_count}

    except Exception as e:
        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "devices",
            "status": "error",
            "findings_count": 0
        }).execute()
        return {"status": "error", "message": str(e)}
