from fastapi import APIRouter, HTTPException, Header
from services.database import supabase_admin
from services.threat_intel_scan import run_threat_intel_scan
from services.score_calculator import calculate_director_liability_score
from middleware.auth_middleware import require_active_membership

router = APIRouter()


def _get_tenant(authorization: str) -> tuple[str, str]:
    token = authorization.removeprefix("Bearer ")
    user = supabase_admin.auth.get_user(token)
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id
    # maybe_single via the shared helper: no active membership -> friendly 409,
    # never a raw PGRST116. Platform admins (no tenant) are correctly denied here.
    tenant_id = require_active_membership(user_id, "tenant_id")["tenant_id"]
    return user_id, tenant_id


@router.post("/scan")
async def run_threat_intel(authorization: str = Header(...)):
    try:
        user_id, tenant_id = _get_tenant(authorization)

        domain_result = (
            supabase_admin.table("domains")
            .select("id")
            .eq("tenant_id", tenant_id)
            .order("created_at")
            .limit(1)
            .execute()
        )
        domain_id = domain_result.data[0]["id"] if domain_result.data else None

        if not domain_id:
            raise HTTPException(status_code=400, detail="No domain configured. Add a domain in Settings first.")

        scan_payload = {
            "tenant_id": tenant_id,
            "triggered_by": user_id,
            "trigger_type": "manual",
            "status": "running",
            "domain_id": domain_id,
        }

        scan = supabase_admin.table("scans").insert(scan_payload).execute()
        scan_id = scan.data[0]["id"]

        result = await run_threat_intel_scan(tenant_id, scan_id)

        # Update director liability score across all tenant findings
        calculate_director_liability_score(tenant_id, scan_id)

        supabase_admin.table("scans").update({"status": "complete"}).eq("id", scan_id).execute()

        return {
            "message": "Threat intelligence scan complete",
            "scan_id": scan_id,
            "domain": result.get("domain"),
            "findings_count": result.get("findings_count", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
