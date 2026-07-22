# backend/routes/scheduler.py
# SecureIT360 — Scheduler health + safe manual test trigger.
# Both endpoints require platform-admin authorization; they expose no tenant data
# publicly.

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from services.database import supabase_admin
from services.scheduler import scheduler
from services.scan_jobs import get_scheduler_health, run_manual_test_scan
from services.target_guard import TargetValidationError
from middleware.auth_middleware import require_platform_admin, get_request_ip
from services.audit import log_audit

router = APIRouter()


@router.get("/health")
def scheduler_health(request: Request, admin: dict = Depends(require_platform_admin)):
    """Scheduler status: enabled flag, next run, previous run + result, job counts."""
    data = get_scheduler_health(scheduler)
    return data


class ManualScanRequest(BaseModel):
    tenant_id: str
    domain_id: str


@router.post("/test-scan")
async def scheduler_test_scan(data: ManualScanRequest, request: Request,
                              admin: dict = Depends(require_platform_admin)):
    """Run the daily-scan pipeline for ONE tenant + ONE verified target.

    Safe manual test path: platform-admin only, single target, does NOT trigger a
    production-wide scan.
    """
    ip = get_request_ip(request)
    tenant_res = supabase_admin.table("tenants").select("*")\
        .eq("id", data.tenant_id).limit(1).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant = tenant_res.data[0]

    try:
        result = await run_manual_test_scan(tenant, data.domain_id, supabase_admin)
    except TargetValidationError as e:
        log_audit("scheduler.test_scan", actor_user_id=admin["user_id"], target_type="domain",
                  target_id=data.domain_id, target_tenant_id=data.tenant_id,
                  outcome="denied", ip=ip, detail={"reason": str(e)})
        raise HTTPException(status_code=400, detail=f"Target not permitted: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_audit("scheduler.test_scan", actor_user_id=admin["user_id"], target_type="domain",
              target_id=data.domain_id, target_tenant_id=data.tenant_id,
              outcome="success", ip=ip, detail={"result": result.get("status")})
    return result
