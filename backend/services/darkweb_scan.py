# SecureIT360 - Dark Web Scan Engine
# Checks if business email addresses have been found in data breaches
# Uses HaveIBeenPwned API with specific regulation clause references

import os
import httpx
from services.database import supabase_admin

HIBP_API_KEY = os.getenv("HIBP_API_KEY")


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


def get_severity(pwn_count: int) -> str:
    if pwn_count > 1000000:
        return "critical"
    elif pwn_count > 100000:
        return "moderate"
    else:
        return "low"


def get_score_impact(pwn_count: int) -> int:
    if pwn_count > 1000000:
        return 20
    elif pwn_count > 100000:
        return 12
    else:
        return 6


def plain_english_description(breach: dict) -> str:
    name = breach.get("Name", "A website")
    year = breach.get("BreachDate", "")[:4] if breach.get("BreachDate") else "recently"
    return (
        f"Your business email addresses were found in a data breach from {name} in {year}. "
        f"This means hackers may have access to passwords used by your staff. "
        f"If any staff member reused that password on other accounts, "
        f"your business could be at risk right now. "
        f"Depending on the circumstances, privacy law may require you to notify "
        f"affected individuals. A legal or compliance review may be required."
    )


async def run_darkweb_scan(tenant_id: str, scan_id: str, domain: str):
    try:
        headers = {
            "hibp-api-key": HIBP_API_KEY,
            "user-agent": "SecureIT360"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://haveibeenpwned.com/api/v3/breacheddomain/{domain}",
                headers=headers,
                timeout=30
            )

        findings_count = 0

        if response.status_code == 200:
            breaches = response.json()

            async with httpx.AsyncClient() as client:
                for email, breach_list in breaches.items():
                    for breach_name in breach_list:
                        breach_response = await client.get(
                            f"https://haveibeenpwned.com/api/v3/breach/{breach_name}",
                            headers=headers,
                            timeout=30
                        )

                        if breach_response.status_code == 200:
                            breach = breach_response.json()
                            pwn_count = breach.get("PwnCount", 0)
                            severity = get_severity(pwn_count)
                            description = plain_english_description(breach)
                            score_impact = get_score_impact(pwn_count)
                            title = f"Staff email found in data breach - {breach.get('Name')}"

                            upsert_finding(
                                tenant_id, scan_id, "darkweb", severity,
                                title, description,
                                "No staff security awareness training program exists. Staff are not aware of the risks of reusing passwords across accounts.",
                                [
                                    "NZ Privacy Act 2020 - IPP 5 (security safeguards for personal information)",
                                    "NZ Privacy Act 2020 - s113 (notifiable privacy breach - must notify within 72 hours)",
                                    "NZ Privacy Amendment Act 2025 - IPP 3A (indirect collection notification)",
                                    "AU Privacy Act 1988 - APP 11.1 (security of personal information)",
                                    "AU Privacy Act 1988 - NDB Scheme s26WK (notifiable data breach - notify within 30 days)",
                                    "AU Privacy Act 1988 (amended Dec 2024) - APP 11.1 (technical and organisational measures required)"
                                ],
                                "voice", score_impact
                            )
                            findings_count += 1

        elif response.status_code == 404:
            findings_count = 0

        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "darkweb",
            "status": "complete",
            "findings_count": findings_count
        }).execute()

        return {"status": "complete", "findings_count": findings_count}

    except Exception as e:
        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "darkweb",
            "status": "error",
            "findings_count": 0
        }).execute()
        return {"status": "error", "message": str(e)}
