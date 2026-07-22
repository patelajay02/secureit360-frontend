# backend/services/scheduler.py
# SecureIT360 — Automated scheduler
# Daily scans at 6am NZ time
# Weekly director email every Monday 8am NZ time
# Monthly report on 1st of every month 9am NZ time

import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

from services.email_service import (
    send_weekly_director_email,
    send_monthly_report_email,
)
from services.scan_jobs import (
    run_daily_scan_for_tenant,
    start_scheduler_run,
    finish_scheduler_run,
    MAX_CONCURRENT_TENANT_SCANS,
)

NZ_TIMEZONE = pytz.timezone("Pacific/Auckland")
scheduler = AsyncIOScheduler(timezone=NZ_TIMEZONE)


def get_owner_email(supabase, tenant_id: str):
    """Looks up the owner email for a tenant via Supabase Auth."""
    try:
        user_result = supabase.table("tenant_users")\
            .select("user_id")\
            .eq("tenant_id", tenant_id)\
            .eq("role", "owner")\
            .execute()
        if user_result.data:
            user_id = user_result.data[0].get("user_id")
            if user_id:
                auth_user = supabase.auth.admin.get_user_by_id(user_id)
                return auth_user.user.email if auth_user and auth_user.user else None
    except Exception as e:
        print(f"[Scheduler] Error getting owner email for tenant {tenant_id}: {e}")
    return None


# ─── Daily Scan Job ───────────────────────────────────────────────────────────

async def run_daily_scans(supabase):
    """Daily scan across all active tenants.

    Each tenant runs under a DB-backed job lock (see services/scan_jobs.py), with
    bounded concurrency, a per-scan timeout, and full status recording. Per-tenant
    failures are RECORDED (job status + scheduler_runs + logs) rather than silently
    swallowed, and the fix routes through the real run_full_scan entry point.
    """
    started = datetime.now(NZ_TIMEZONE)
    print(f"[Scheduler] Daily scan started at {started}")
    run_id = start_scheduler_run("daily_scans")

    total = 0
    outcomes = {"completed": 0, "skipped_no_target": 0, "skipped_duplicate": 0,
                "failed": 0, "timed_out": 0}
    try:
        result = supabase.table("tenants").select("*").in_("status", ["active", "comped"]).execute()
        tenants = result.data or []
        total = len(tenants)
        print(f"[Scheduler] Running daily scans for {total} tenants "
              f"(max {MAX_CONCURRENT_TENANT_SCANS} concurrent)")

        sem = asyncio.Semaphore(MAX_CONCURRENT_TENANT_SCANS)
        lock = asyncio.Lock()

        async def _one(tenant):
            tid = tenant.get("id")
            async with sem:
                try:
                    outcome = await run_daily_scan_for_tenant(tenant, supabase)
                except Exception as e:
                    outcome = "failed"
                    # Surface with context (no secrets) — not swallowed silently.
                    print(f"[Scheduler] ERROR scanning tenant {tid}: {type(e).__name__}: {e}")
            async with lock:
                outcomes[outcome] = outcomes.get(outcome, 0) + 1

        await asyncio.gather(*[_one(t) for t in tenants])

        succeeded = (outcomes["completed"] + outcomes["skipped_no_target"]
                     + outcomes["skipped_duplicate"])
        failed = outcomes["failed"] + outcomes["timed_out"]
        finish_scheduler_run(run_id, "completed", total=total, succeeded=succeeded, failed=failed)
        print(f"[Scheduler] Daily scan finished at {datetime.now(NZ_TIMEZONE)}: {outcomes}")
    except Exception as e:
        succeeded = (outcomes["completed"] + outcomes["skipped_no_target"]
                     + outcomes["skipped_duplicate"])
        failed = outcomes["failed"] + outcomes["timed_out"]
        finish_scheduler_run(run_id, "failed", total=total, succeeded=succeeded,
                             failed=failed, error=f"{type(e).__name__}: {e}")
        print(f"[Scheduler] Daily scan run FAILED: {type(e).__name__}: {e}")


# ─── Weekly Director Email Job ────────────────────────────────────────────────

async def run_weekly_director_emails(supabase):
    print(f"[Scheduler] Weekly director emails started at {datetime.now(NZ_TIMEZONE)}")
    try:
        result = supabase.table("tenants").select("*").in_("status", ["active", "comped"]).execute()
        tenants = result.data or []
        for tenant in tenants:
            try:
                await send_weekly_email_for_tenant(tenant, supabase)
            except Exception as e:
                print(f"[Scheduler] Error sending weekly email for tenant {tenant.get('id')}: {e}")
    except Exception as e:
        print(f"[Scheduler] Weekly email error: {e}")


async def send_weekly_email_for_tenant(tenant, supabase):
    tenant_id = tenant.get("id")
    company_name = tenant.get("name", "Your company")

    # Use director_email if set, otherwise fall back to owner email
    to_email = tenant.get("director_email") or None
    if not to_email:
        to_email = get_owner_email(supabase, tenant_id)

    if not to_email:
        print(f"[Scheduler] No email address for tenant {tenant_id} — skipping weekly email")
        return

    # Get latest two completed scans
    latest_scan_result = supabase.table("scans")\
        .select("id, ransom_score, governance_score")\
        .eq("tenant_id", tenant_id)\
        .eq("status", "complete")\
        .order("created_at", desc=True)\
        .limit(2)\
        .execute()

    scans = latest_scan_result.data or []

    current_score = 50
    governance_score = None
    previous_score = 50

    if len(scans) >= 1:
        current_score = int(scans[0].get("ransom_score") or 50)
        governance_score = scans[0].get("governance_score")

    if len(scans) >= 2:
        previous_score = int(scans[1].get("ransom_score") or current_score)

    # Get top 3 recommended actions from latest scan
    top_actions = []
    if scans:
        scan_id = scans[0]["id"]
        findings_result = supabase.table("findings")\
            .select("id, title, severity, description, governance_gap")\
            .eq("scan_id", scan_id)\
            .order("severity", desc=True)\
            .limit(3)\
            .execute()
        top_actions = findings_result.data or []

    # Get unresolved findings from latest scan
    unresolved_findings = []
    if scans:
        scan_id = scans[0]["id"]
        unresolved_result = supabase.table("findings")\
            .select("title, severity, description")\
            .eq("scan_id", scan_id)\
            .neq("status", "fixed")\
            .order("severity", desc=True)\
            .execute()
        unresolved_findings = unresolved_result.data or []

    print(f"[Scheduler] Sending weekly email to {to_email} for {company_name}")

    send_weekly_director_email(
        company_name=company_name,
        to_email=to_email,
        current_score=current_score,
        previous_score=previous_score,
        top_actions=top_actions,
        governance_score=governance_score,
        director_liability_score=None,
        unresolved_findings=unresolved_findings,
    )


# ─── Monthly Report Job ───────────────────────────────────────────────────────

async def run_monthly_reports(supabase):
    print(f"[Scheduler] Monthly reports started at {datetime.now(NZ_TIMEZONE)}")
    try:
        result = supabase.table("tenants").select("*").in_("status", ["active", "comped"]).execute()
        tenants = result.data or []
        for tenant in tenants:
            try:
                await send_monthly_report_for_tenant(tenant, supabase)
            except Exception as e:
                print(f"[Scheduler] Error sending monthly report for tenant {tenant.get('id')}: {e}")
    except Exception as e:
        print(f"[Scheduler] Monthly report error: {e}")


async def send_monthly_report_for_tenant(tenant, supabase):
    tenant_id = tenant.get("id")
    company_name = tenant.get("name", "Your company")

    owner_email = get_owner_email(supabase, tenant_id)
    if not owner_email:
        return

    current_scan = supabase.table("scans")\
        .select("ransom_score")\
        .eq("tenant_id", tenant_id)\
        .eq("status", "complete")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    current_score = 50
    if current_scan.data:
        current_score = int(current_scan.data[0].get("ransom_score") or 50)

    latest_scan = supabase.table("scans")\
        .select("id")\
        .eq("tenant_id", tenant_id)\
        .eq("status", "complete")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    total_findings = 0
    fixed_this_month = 0

    if latest_scan.data:
        scan_id = latest_scan.data[0]["id"]
        findings = supabase.table("findings")\
            .select("id, status")\
            .eq("scan_id", scan_id)\
            .execute()
        all_findings = findings.data or []
        total_findings = len(all_findings)
        fixed_this_month = len([f for f in all_findings if f.get("status") == "fixed"])

    send_monthly_report_email(
        company_name=company_name,
        to_email=owner_email,
        current_score=current_score,
        total_findings=total_findings,
        fixed_this_month=fixed_this_month,
    )


# ─── Scheduler Setup ──────────────────────────────────────────────────────────

def start_scheduler(supabase):
    # Daily scan — 6am NZ time every day
    scheduler.add_job(
        run_daily_scans,
        CronTrigger(hour=6, minute=0, timezone=NZ_TIMEZONE),
        args=[supabase],
        id="daily_scans",
        replace_existing=True,
    )

    # Weekly director email — Monday 8am NZ time
    scheduler.add_job(
        run_weekly_director_emails,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=NZ_TIMEZONE),
        args=[supabase],
        id="weekly_emails",
        replace_existing=True,
    )

    # Monthly report — 1st of every month 9am NZ time
    scheduler.add_job(
        run_monthly_reports,
        CronTrigger(day=1, hour=9, minute=0, timezone=NZ_TIMEZONE),
        args=[supabase],
        id="monthly_reports",
        replace_existing=True,
    )

    scheduler.start()
    print("[Scheduler] Started — daily scans 6am, weekly emails Monday 8am, monthly reports 1st of month 9am")