# backend/services/scan_jobs.py
# SecureIT360 — Scheduled scan orchestration with a DB-backed job lock.
#
# The scan_jobs table (migration 20260721_phase0_security_foundation.sql) has a
# UNIQUE index on (tenant_id, domain_id, scan_type, scheduled_date). Claiming a
# job is an INSERT: at most one caller can win per tenant/target/day, which is
# the duplicate-prevention lock. Every state transition is recorded, exceptions
# are surfaced (not silently swallowed), and each scan runs under a hard timeout.

import os
import socket
import uuid
import asyncio
from datetime import datetime
import pytz

from services.database import supabase_admin
from services.full_scan import run_full_scan
from services.target_guard import validate_public_hostname, TargetValidationError
from services.email_service import send_alert_email

NZ_TIMEZONE = pytz.timezone("Pacific/Auckland")

# A stable-ish identifier for the process holding a lock (diagnostics only).
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

DAILY_SCAN_TIMEOUT_SECONDS = int(os.getenv("DAILY_SCAN_TIMEOUT_SECONDS", "600"))
MAX_CONCURRENT_TENANT_SCANS = int(os.getenv("MAX_CONCURRENT_TENANT_SCANS", "3"))
SCAN_TYPE_DAILY = "daily_full"


def _now_iso() -> str:
    return datetime.now(NZ_TIMEZONE).isoformat()


def _today_nz():
    return datetime.now(NZ_TIMEZONE).date()


# ── Job lock / status helpers ────────────────────────────────────────────────
def claim_scan_job(tenant_id: str, domain_id: str, scan_type: str, scheduled_date) -> dict | None:
    """Attempt to claim the job for this tenant/target/day.

    Returns the created job row, or None if a job already exists for this cycle
    (i.e. a duplicate — the unique index blocked the insert).
    """
    payload = {
        "tenant_id": tenant_id,
        "domain_id": domain_id,
        "scan_type": scan_type,
        "scheduled_date": scheduled_date.isoformat(),
        "scheduled_for": _now_iso(),
        "status": "queued",
        "attempt_count": 1,
        "locked_by": WORKER_ID,
        "locked_at": _now_iso(),
    }
    try:
        res = supabase_admin.table("scan_jobs").insert(payload).execute()
        return res.data[0]
    except Exception:
        # Either a unique-violation (duplicate cycle) or a genuine error.
        existing = supabase_admin.table("scan_jobs")\
            .select("id, status")\
            .eq("tenant_id", tenant_id)\
            .eq("domain_id", domain_id)\
            .eq("scan_type", scan_type)\
            .eq("scheduled_date", scheduled_date.isoformat())\
            .limit(1)\
            .execute()
        if existing.data:
            return None  # duplicate — already claimed for this cycle
        raise            # a real error — surface it


def mark_job(job_id: str, status: str, *, failure_reason: str = None, scan_id: str = None):
    update = {"status": status, "updated_at": _now_iso()}
    if status == "running":
        update["started_at"] = _now_iso()
    if status in ("completed", "failed", "timed_out", "skipped_duplicate"):
        update["completed_at"] = _now_iso()
    if failure_reason is not None:
        update["failure_reason"] = failure_reason[:1000]  # bounded, no secrets
    if scan_id is not None:
        update["scan_id"] = scan_id
    try:
        supabase_admin.table("scan_jobs").update(update).eq("id", job_id).execute()
    except Exception as e:
        print(f"[scan_jobs] failed to update job {job_id} -> {status}: {e}")


# ── Per-tenant daily scan ────────────────────────────────────────────────────
def _get_owner_email(supabase, tenant_id: str):
    try:
        res = supabase.table("tenant_users")\
            .select("user_id").eq("tenant_id", tenant_id)\
            .eq("role", "owner").execute()
        if res.data:
            user_id = res.data[0].get("user_id")
            if user_id:
                auth_user = supabase.auth.admin.get_user_by_id(user_id)
                return auth_user.user.email if auth_user and auth_user.user else None
    except Exception as e:
        print(f"[scan_jobs] owner email lookup failed for tenant {tenant_id}: {e}")
    return None


def _pick_verified_target(supabase, tenant_id: str):
    """Return (domain_id, domain) for the tenant's verified primary domain, or None."""
    res = supabase.table("domains")\
        .select("id, domain, verified, is_primary")\
        .eq("tenant_id", tenant_id)\
        .eq("verified", True)\
        .execute()
    verified = res.data or []
    if not verified:
        return None
    primary = next((d for d in verified if d.get("is_primary")), verified[0])
    return primary["id"], primary["domain"]


async def run_daily_scan_for_tenant(tenant: dict, supabase, *, scheduled_date=None) -> str:
    """Run one tenant's daily scan under a DB job lock. Returns a status string
    ('completed' | 'skipped_no_target' | 'skipped_duplicate' | 'failed' | 'timed_out').
    Raises only on unexpected errors after the job is marked failed.
    """
    tenant_id = tenant.get("id")
    company_name = tenant.get("name", "Your company")
    scheduled_date = scheduled_date or _today_nz()

    target = _pick_verified_target(supabase, tenant_id)
    if not target:
        return "skipped_no_target"
    domain_id, domain = target

    # Claim the job (duplicate-prevention lock).
    job = claim_scan_job(tenant_id, domain_id, SCAN_TYPE_DAILY, scheduled_date)
    if job is None:
        return "skipped_duplicate"
    job_id = job["id"]

    # SSRF guard before any active scanning.
    try:
        validate_public_hostname(domain)
    except TargetValidationError as e:
        mark_job(job_id, "failed", failure_reason=f"target not permitted: {e}")
        return "failed"

    # Snapshot previous critical findings so we only alert on NEW ones.
    prev_titles = set()
    try:
        prev_scan = supabase.table("scans").select("id").eq("tenant_id", tenant_id)\
            .eq("status", "complete").order("created_at", desc=True).limit(1).execute()
        if prev_scan.data:
            prev = supabase.table("findings").select("title")\
                .eq("scan_id", prev_scan.data[0]["id"]).execute()
            prev_titles = {f["title"] for f in (prev.data or [])}
    except Exception as e:
        print(f"[scan_jobs] prev-findings lookup failed for tenant {tenant_id}: {e}")

    mark_job(job_id, "running")

    try:
        result = await asyncio.wait_for(
            run_full_scan(tenant_id, domain_id, domain, None),
            timeout=DAILY_SCAN_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        mark_job(job_id, "timed_out", failure_reason="scan exceeded timeout")
        return "timed_out"
    except Exception as e:
        mark_job(job_id, "failed", failure_reason=str(e))
        raise

    if result.get("status") == "error":
        mark_job(job_id, "failed", failure_reason=str(result.get("message", "scan error")))
        return "failed"

    scan_id = result.get("scan_id")
    mark_job(job_id, "completed", scan_id=scan_id)

    # Best-effort enrichment + alerting (never fail the job over these).
    try:
        from services.threat_intel_scan import run_threat_intel_scan
        from services.score_calculator import calculate_director_liability_score
        await run_threat_intel_scan(tenant_id, scan_id)
        calculate_director_liability_score(tenant_id, scan_id)
    except Exception as e:
        print(f"[scan_jobs] enrichment failed for tenant {tenant_id}: {e}")

    try:
        new_crit = supabase.table("findings").select("*").eq("scan_id", scan_id)\
            .eq("severity", "critical").execute()
        truly_new = [f for f in (new_crit.data or []) if f.get("title") not in prev_titles]
        if truly_new:
            owner_email = _get_owner_email(supabase, tenant_id)
            if owner_email:
                send_alert_email(company_name, owner_email, truly_new)
    except Exception as e:
        print(f"[scan_jobs] alert step failed for tenant {tenant_id}: {e}")

    return "completed"


# ── Manual test mode (single tenant + single verified target) ────────────────
async def run_manual_test_scan(tenant: dict, domain_id: str, supabase) -> dict:
    """Safely run ONE verified target for ONE tenant, under a job lock. Used by
    the authorized manual test endpoint. Never triggers a production-wide scan.
    """
    tenant_id = tenant["id"]
    row = supabase.table("domains")\
        .select("id, domain, verified")\
        .eq("id", domain_id).eq("tenant_id", tenant_id).limit(1).execute()
    if not row.data:
        raise ValueError("Domain not found for this tenant")
    record = row.data[0]
    if not record.get("verified"):
        raise ValueError("Domain must be verified before scanning")

    domain = record["domain"]
    validate_public_hostname(domain)  # raises TargetValidationError if not permitted

    job = claim_scan_job(tenant_id, domain_id, "manual_test", _today_nz())
    if job is None:
        return {"status": "skipped_duplicate"}
    job_id = job["id"]
    mark_job(job_id, "running")

    try:
        result = await asyncio.wait_for(
            run_full_scan(tenant_id, domain_id, domain, None),
            timeout=DAILY_SCAN_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        mark_job(job_id, "timed_out", failure_reason="scan exceeded timeout")
        return {"status": "timed_out"}
    except Exception as e:
        mark_job(job_id, "failed", failure_reason=str(e))
        raise

    if result.get("status") == "error":
        mark_job(job_id, "failed", failure_reason=str(result.get("message")))
        return {"status": "failed", "detail": result.get("message")}

    mark_job(job_id, "completed", scan_id=result.get("scan_id"))
    return {"status": "completed", "scan_id": result.get("scan_id"), "job_id": job_id}


# ── Scheduler-run health record ──────────────────────────────────────────────
def start_scheduler_run(job_name: str):
    try:
        res = supabase_admin.table("scheduler_runs").insert({
            "job_name": job_name, "status": "running", "started_at": _now_iso(),
        }).execute()
        return res.data[0]["id"]
    except Exception as e:
        print(f"[scan_jobs] could not open scheduler_run for {job_name}: {e}")
        return None


def finish_scheduler_run(run_id, status, *, total=None, succeeded=None, failed=None, error=None):
    if not run_id:
        return
    try:
        supabase_admin.table("scheduler_runs").update({
            "status": status,
            "finished_at": _now_iso(),
            "tenants_total": total,
            "tenants_succeeded": succeeded,
            "tenants_failed": failed,
            "error": (error[:1000] if error else None),
        }).eq("id", run_id).execute()
    except Exception as e:
        print(f"[scan_jobs] could not close scheduler_run {run_id}: {e}")


def get_scheduler_health(scheduler) -> dict:
    """Assemble non-sensitive scheduler health info for the health endpoint."""
    enabled = bool(getattr(scheduler, "running", False))
    next_run = None
    try:
        job = scheduler.get_job("daily_scans")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    except Exception:
        pass

    previous = None
    try:
        res = supabase_admin.table("scheduler_runs").select("*")\
            .eq("job_name", "daily_scans").order("started_at", desc=True).limit(1).execute()
        if res.data:
            r = res.data[0]
            previous = {
                "started_at": r.get("started_at"),
                "finished_at": r.get("finished_at"),
                "status": r.get("status"),
                "tenants_total": r.get("tenants_total"),
                "tenants_succeeded": r.get("tenants_succeeded"),
                "tenants_failed": r.get("tenants_failed"),
            }
    except Exception:
        pass

    counts = {"queued": 0, "running": 0, "failed": 0}
    try:
        today = _today_nz().isoformat()
        for status in counts:
            c = supabase_admin.table("scan_jobs").select("id", count="exact")\
                .eq("scheduled_date", today).eq("status", status).execute()
            counts[status] = c.count or 0
    except Exception:
        pass

    return {
        "scheduler_enabled": enabled,
        "next_scheduled_run": next_run,
        "previous_run": previous,
        "jobs_today": counts,
    }
