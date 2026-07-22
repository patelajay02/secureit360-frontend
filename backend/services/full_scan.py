# SecureIT360 - Full Scan Engine
# Runs all 6 scan engines in one click.
# This is what happens when a client clicks "Run Full Scan" on the dashboard.

from services.darkweb_scan import run_darkweb_scan
from services.email_scan import run_email_scan
from services.network_scan import run_network_scan
from services.website_scan import run_website_scan
from services.device_scan import run_device_scan
from services.cloud_scan import run_cloud_scan
from services.score_calculator import calculate_ransom_score, calculate_governance_score
from services.database import supabase_admin
import asyncio


async def run_full_scan(tenant_id: str, domain_id: str, domain: str, user_id: str) -> dict:
    try:
        # Create a single scan record for all 6 engines
        scan = supabase_admin.table("scans").insert({
            "tenant_id": tenant_id,
            "domain_id": domain_id,
            "triggered_by": user_id,
            "trigger_type": "full",
            "status": "running"
        }).execute()

        scan_id = scan.data[0]["id"]

        print(f"Starting full scan for {domain} - scan_id: {scan_id}")

        # Run all 6 scans - some in parallel for speed
        # Dark web and email can run at the same time
        darkweb_result, email_result = await asyncio.gather(
            run_darkweb_scan(tenant_id, scan_id, domain),
            run_email_scan(tenant_id, scan_id, domain)
        )

        # Network and website can run at the same time
        network_result, website_result = await asyncio.gather(
            run_network_scan(tenant_id, scan_id, domain),
            run_website_scan(tenant_id, scan_id, domain)
        )

        # Device and cloud can run at the same time
        device_result, cloud_result = await asyncio.gather(
            run_device_scan(tenant_id, scan_id, domain),
            run_cloud_scan(tenant_id, scan_id, domain)
        )

        # Calculate Ransom Risk Score and Governance Score
        ransom_result = calculate_ransom_score(tenant_id, scan_id)
        governance_result = calculate_governance_score(tenant_id, scan_id)

        # Regulatory intelligence is resolved per-finding at read time by
        # services/regulatory_intelligence.py (the single source of truth),
        # using the tenant's trusted country. The old dormant compliance-report
        # generator has been retired.

        # Update scan as complete
        supabase_admin.table("scans")\
            .update({"status": "complete"})\
            .eq("id", scan_id)\
            .eq("tenant_id", tenant_id)\
            .execute()

        # Count total findings
        total_findings = (
            darkweb_result.get("findings_count", 0) +
            email_result.get("findings_count", 0) +
            network_result.get("findings_count", 0) +
            website_result.get("findings_count", 0) +
            device_result.get("findings_count", 0) +
            cloud_result.get("findings_count", 0)
        )

        return {
            "scan_id": scan_id,
            "status": "complete",
            "total_findings": total_findings,
            "ransom_score": ransom_result.get("ransom_score"),
            "risk_label": ransom_result.get("risk_label"),
            "governance_score": governance_result.get("governance_score"),
            "scan_results": {
                "darkweb": darkweb_result,
                "email": email_result,
                "network": network_result,
                "website": website_result,
                "devices": device_result,
                "cloud": cloud_result
            }
        }

    except Exception as e:
        supabase_admin.table("scans")\
            .update({"status": "error"})\
            .eq("id", scan_id)\
            .eq("tenant_id", tenant_id)\
            .execute()
        return {"status": "error", "message": str(e)}