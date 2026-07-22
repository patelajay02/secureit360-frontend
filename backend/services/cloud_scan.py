# SecureIT360 - Cloud Storage Scan Engine
# Checks for publicly exposed cloud storage with specific regulation clause references

import httpx
from services.database import supabase_admin


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


def get_bucket_names(domain: str) -> list:
    company = domain.split(".")[0]
    return [
        company,
        f"{company}-backup",
        f"{company}-backups",
        f"{company}-files",
        f"{company}-documents",
        f"{company}-docs",
        f"{company}-data",
        f"{company}-media",
        f"{company}-uploads",
        f"{company}-public",
        f"{company}-private",
        f"{company}-assets"
    ]


async def check_s3_bucket(bucket_name: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://{bucket_name}.s3.amazonaws.com",
                follow_redirects=True
            )
            if response.status_code == 200:
                return True
    except Exception:
        pass
    return False


async def run_cloud_scan(tenant_id: str, scan_id: str, domain: str):
    try:
        findings_count = 0
        exposed_buckets = []

        bucket_names = get_bucket_names(domain)

        for bucket_name in bucket_names:
            is_public = await check_s3_bucket(bucket_name)
            if is_public:
                exposed_buckets.append(bucket_name)

        if exposed_buckets:
            for bucket in exposed_buckets:
                upsert_finding(
                    tenant_id, scan_id, "cloud", "critical",
                    "Your cloud files are visible to everyone on the internet",
                    (
                        f"A cloud storage area named '{bucket}' was found that is "
                        f"publicly accessible. This means anyone on the internet can "
                        f"view and download files stored there. This could include "
                        f"client records, financial documents, staff information or "
                        f"any other files your business has stored in the cloud. "
                        f"If the exposed files contain personal information, this may "
                        f"constitute a notifiable privacy breach and a legal or "
                        f"compliance review may be required. Regulatory intelligence, "
                        f"not legal advice."
                    ),
                    "No data classification or cloud security policy exists. Staff are storing sensitive business data in publicly accessible locations without awareness of the risk.",
                    [
                        "NZ Privacy Act 2020 - IPP 5 (security safeguards for personal information)",
                        "NZ Privacy Act 2020 - s113 (notifiable privacy breach - notify within 72 hours)",
                        "NZ Privacy Amendment Act 2025 - IPP 3A (indirect data collection obligations)",
                        "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
                        "AU Privacy Act 1988 - APP 11.2 (destruction or de-identification when no longer needed)",
                        "AU Privacy Act 1988 - APP 8 (cross-border disclosure of personal information)",
                        "AU Privacy Act 1988 - NDB Scheme s26WK (notifiable data breach - notify within 30 days)",
                        "AU Privacy Act 1988 (amended Dec 2024) - APP 11.1 (technical and organisational measures required)",
                        "AU Cyber Security Act 2024 - s30 (cyber incident reporting obligations)"
                    ],
                    "specialist", 25
                )
                findings_count += 1

        else:
            upsert_finding(
                tenant_id, scan_id, "cloud", "low",
                "No publicly exposed cloud storage found",
                (
                    f"No publicly accessible cloud storage was found for {domain}. "
                    f"This is good. Ensure that any cloud storage your business uses "
                    f"is set to private and that staff know not to make files public."
                ),
                "Ensure a data classification policy exists so staff know how to handle sensitive files securely.",
                [
                    "NZ Privacy Act 2020 - IPP 5 (security safeguards)",
                    "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)"
                ],
                "info", 0
            )
            findings_count = 1

        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "cloud",
            "status": "complete",
            "findings_count": findings_count
        }).execute()

        return {"status": "complete", "findings_count": findings_count}

    except Exception as e:
        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "cloud",
            "status": "error",
            "findings_count": 0
        }).execute()
        return {"status": "error", "message": str(e)}
