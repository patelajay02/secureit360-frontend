# SecureIT360 - Scan Routes
# Handles: Triggering scans and retrieving scan results
# Every query filters by tenant_id so companies only see their own scans.
#
# Security gate (single source of truth: _resolve_verified_target):
#   1. Authenticate the Supabase access token.
#   2. Resolve the caller's active tenant.
#   3. Confirm the target domain belongs to that tenant (ownership).
#   4. Require the domain to be VERIFIED before any active scan.
#   5. Validate the target is a permitted PUBLIC host (SSRF guard).

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from services.database import supabase, supabase_admin
from services.darkweb_scan import run_darkweb_scan
from services.email_scan import run_email_scan
from services.network_scan import run_network_scan
from services.website_scan import run_website_scan
from services.device_scan import run_device_scan
from services.cloud_scan import run_cloud_scan
from services.full_scan import run_full_scan
from services.target_guard import validate_public_hostname, TargetValidationError
from services.rate_limit import enforce_rate_limit

router = APIRouter()


# What we expect when triggering a scan
class ScanRequest(BaseModel):
    domain_id: str


def _resolve_verified_target(authorization: str, domain_id: str):
    """Authenticate, enforce tenant ownership + domain verification + SSRF
    validation. Returns (user_id, tenant_id, domain). Raises HTTPException.
    """
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication")

    try:
        user = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = user.user.id

    tenant_user = supabase_admin.table("tenant_users")\
        .select("tenant_id")\
        .eq("user_id", user_id)\
        .eq("status", "active")\
        .limit(1)\
        .execute()
    if not tenant_user.data:
        raise HTTPException(status_code=403, detail="No tenant found for this user")
    tenant_id = tenant_user.data[0]["tenant_id"]

    # Throttle scan creation per tenant (expensive outbound work / DoS guard).
    enforce_rate_limit(f"scan:{tenant_id}", 30, 3600)

    domain_row = supabase_admin.table("domains")\
        .select("*")\
        .eq("id", domain_id)\
        .eq("tenant_id", tenant_id)\
        .limit(1)\
        .execute()
    if not domain_row.data:
        raise HTTPException(status_code=404, detail="Domain not found.")

    domain_record = domain_row.data[0]
    domain = domain_record["domain"]

    # Ownership must be proven (DNS-TXT verified) before we actively scan it.
    if not domain_record.get("verified"):
        raise HTTPException(
            status_code=403,
            detail="Domain ownership must be verified before it can be scanned.",
        )

    # SSRF guard: only permitted public hosts may be scanned.
    try:
        validate_public_hostname(domain)
    except TargetValidationError as e:
        raise HTTPException(status_code=400, detail=f"Target not permitted: {e}")

    return user_id, tenant_id, domain


def _create_scan(tenant_id: str, domain_id: str, user_id: str):
    scan = supabase_admin.table("scans").insert({
        "tenant_id": tenant_id,
        "domain_id": domain_id,
        "triggered_by": user_id,
        "trigger_type": "manual",
        "status": "running"
    }).execute()
    return scan.data[0]["id"]


def _complete_scan(scan_id: str):
    supabase_admin.table("scans")\
        .update({"status": "complete"})\
        .eq("id", scan_id)\
        .execute()


# TRIGGER DARK WEB SCAN
@router.post("/darkweb")
async def darkweb_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        scan_id = _create_scan(tenant_id, data.domain_id, user_id)
        result = await run_darkweb_scan(tenant_id, scan_id, domain)
        _complete_scan(scan_id)
        return {"message": "Dark web scan complete", "scan_id": scan_id,
                "findings_count": result.get("findings_count", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# TRIGGER EMAIL SECURITY SCAN
@router.post("/email")
async def email_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        scan_id = _create_scan(tenant_id, data.domain_id, user_id)
        result = await run_email_scan(tenant_id, scan_id, domain)
        _complete_scan(scan_id)
        return {"message": "Email security scan complete", "scan_id": scan_id,
                "findings_count": result.get("findings_count", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# GET ALL SCANS FOR THIS COMPANY
@router.get("/")
def get_scans(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]

        scans = supabase_admin.table("scans")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .order("created_at", desc=True)\
            .execute()

        return {"scans": scans.data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# GET ALL FINDINGS FOR THIS COMPANY
@router.get("/findings")
def get_findings(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]

        findings = supabase_admin.table("findings")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .order("created_at", desc=True)\
            .execute()

        return {"findings": findings.data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# TRIGGER NETWORK SCAN
@router.post("/network")
async def network_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        scan_id = _create_scan(tenant_id, data.domain_id, user_id)
        result = await run_network_scan(tenant_id, scan_id, domain)
        _complete_scan(scan_id)
        return {"message": "Network scan complete", "scan_id": scan_id,
                "findings_count": result.get("findings_count", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# TRIGGER WEBSITE AND SSL SCAN
@router.post("/website")
async def website_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        scan_id = _create_scan(tenant_id, data.domain_id, user_id)
        result = await run_website_scan(tenant_id, scan_id, domain)
        _complete_scan(scan_id)
        return {"message": "Website and SSL scan complete", "scan_id": scan_id,
                "findings_count": result.get("findings_count", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# TRIGGER DEVICE SCAN
@router.post("/devices")
async def device_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        scan_id = _create_scan(tenant_id, data.domain_id, user_id)
        result = await run_device_scan(tenant_id, scan_id, domain)
        _complete_scan(scan_id)
        return {"message": "Device scan complete", "scan_id": scan_id,
                "findings_count": result.get("findings_count", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# TRIGGER CLOUD SCAN
@router.post("/cloud")
async def cloud_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        scan_id = _create_scan(tenant_id, data.domain_id, user_id)
        result = await run_cloud_scan(tenant_id, scan_id, domain)
        _complete_scan(scan_id)
        return {"message": "Cloud scan complete", "scan_id": scan_id,
                "findings_count": result.get("findings_count", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# TRIGGER FULL SCAN - Runs all 6 engines in one click
@router.post("/full")
async def full_scan(data: ScanRequest, request: Request, authorization: str = Header(...)):
    try:
        user_id, tenant_id, domain = _resolve_verified_target(authorization, data.domain_id)
        result = await run_full_scan(tenant_id, data.domain_id, domain, user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── AUTO-FIX ───────────────────────────────────────────────────────────────
# Runs whatever handler is registered for the finding. Honest state today:
# no handlers are registered (see services/auto_fix.py audit). This route
# is the plumbing so a future engine-specific handler can plug in without
# any UI changes.

from services.auto_fix import run_scan_fix  # noqa: E402


@router.post("/auto-fix/{finding_id}")
def auto_fix_finding(finding_id: str, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()
        tenant_id = tenant_user.data["tenant_id"]

        finding_r = supabase_admin.table("findings")\
            .select("*")\
            .eq("id", finding_id)\
            .eq("tenant_id", tenant_id)\
            .single()\
            .execute()
        finding = finding_r.data
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        if not finding.get("auto_fixable"):
            raise HTTPException(
                status_code=400,
                detail="This finding cannot be auto-fixed. It requires action on your side.",
            )

        result = run_scan_fix(finding)

        supabase_admin.table("findings")\
            .update({"status": "auto_resolved"})\
            .eq("id", finding_id)\
            .eq("tenant_id", tenant_id)\
            .execute()

        return {
            "message": result.get("message") or "Fixed.",
            "finding_id": finding_id,
            "status": "auto_resolved",
        }

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
