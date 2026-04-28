# SecureIT360 - Main Application File
# Entry point for the entire backend.
# Creates the FastAPI app, sets up CORS, connects all routes, and starts the scheduler.

import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from supabase import create_client

# Load environment variables from .env file
load_dotenv()

# Import routers
from routes.auth import router as auth_router
from routes.scans import router as scans_router
from routes.billing import router as billing_router
from routes.domains import router as domains_router
from routes.dashboard import router as dashboard_router
from routes.email_preview import router as email_preview_router
from routes.tenants import router as tenants_router
from routes.integrations import router as integrations_router
from routes.google_workspace import router as google_workspace_router
from routes.threat_intel import router as threat_intel_router
from routes.saas import router as saas_router

# Import scheduler
from services.scheduler import scheduler, start_scheduler, send_weekly_email_for_tenant
from services.database import supabase_admin
from services.email_service import send_alert_email
from services.hibp_watch import check_for_new_breaches

# Create Supabase client
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

# --- Startup and shutdown -----------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(supabase)
    # Real-time HIBP breach watch — runs every 5 minutes alongside the
    # daily scans, weekly director emails, and monthly reports already
    # registered inside start_scheduler. Intentionally registered here
    # rather than inside scheduler.py so the watch is opt-in per-deploy
    # if we ever need to disable it without touching the rest of the
    # cron lineup.
    scheduler.add_job(
        check_for_new_breaches,
        "interval",
        minutes=5,
        id="hibp_breach_watch",
        replace_existing=True,
    )
    print("[SecureIT360] Scheduler started")
    yield
    print("[SecureIT360] Shutting down")

# --- Create FastAPI app -------------------------------------------------

app = FastAPI(
    title="SecureIT360",
    description="Multi-tenant cyber security platform for AU and NZ small businesses by Global Cyber Assurance.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS ---------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://secureit360.co",
        "https://secureit360.vercel.app",
        "https://app.secureit360.co",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes -------------------------------------------------------------

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(scans_router, prefix="/scans", tags=["Scans"])
app.include_router(billing_router, prefix="/billing", tags=["Billing"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(domains_router, prefix="/domains", tags=["Domains"])
app.include_router(email_preview_router, prefix="/email", tags=["Email Preview"])
app.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])
app.include_router(integrations_router, prefix="/integrations", tags=["Integrations"])
app.include_router(google_workspace_router, prefix="/integrations/google", tags=["Google Workspace"])
app.include_router(threat_intel_router, prefix="/threat-intel", tags=["Threat Intelligence"])
app.include_router(saas_router, prefix="/saas", tags=["SaaS Connector"])

# --- Health check -------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "product": "SecureIT360"}

# --- TEMP: Test weekly director email -----------------------------------
# Remove this endpoint after launch testing is complete

@app.post("/test/weekly-email")
async def test_weekly_email(x_test_secret: str = Header(...)):
    """Triggers the weekly director email for all active tenants. For testing only."""
    if x_test_secret != "secureit360-test-2024":
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        result = supabase_admin.table("tenants").select("*").in_("status", ["active", "comped"]).execute()
        tenants = result.data or []

        if not tenants:
            return {"message": "No active tenants found.", "sent": 0}

        sent = 0
        for tenant in tenants:
            await send_weekly_email_for_tenant(tenant, supabase_admin)
            sent += 1

        return {"message": f"Weekly email triggered for {sent} tenant(s).", "sent": sent}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- TEMP: Test critical alert email ------------------------------------
# Remove this endpoint after launch testing is complete

@app.post("/test/alert-email")
async def test_alert_email(x_test_secret: str = Header(...)):
    """Triggers a critical alert email for Quality Mark tenant. For testing only."""
    if x_test_secret != "secureit360-test-2024":
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        # Get Quality Mark tenant
        tenant_result = supabase_admin.table("tenants")\
            .select("*")\
            .eq("name", "Quality Mark")\
            .single()\
            .execute()

        tenant = tenant_result.data
        if not tenant:
            raise HTTPException(status_code=404, detail="Quality Mark tenant not found.")

        tenant_id = tenant["id"]
        company_name = tenant.get("name", "Your company")

        # Get owner email
        user_result = supabase_admin.table("tenant_users")\
            .select("user_id")\
            .eq("tenant_id", tenant_id)\
            .eq("role", "owner")\
            .execute()

        to_email = None
        if user_result.data:
            user_id = user_result.data[0].get("user_id")
            if user_id:
                auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
                to_email = auth_user.user.email if auth_user and auth_user.user else None

        if not to_email:
            raise HTTPException(status_code=404, detail="No owner email found.")

        # Use real findings from latest scan, or mock if none exist
        latest_scan = supabase_admin.table("scans")\
            .select("id")\
            .eq("tenant_id", tenant_id)\
            .eq("status", "complete")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        findings = []
        if latest_scan.data:
            scan_id = latest_scan.data[0]["id"]
            findings_result = supabase_admin.table("findings")\
                .select("title, severity, description")\
                .eq("scan_id", scan_id)\
                .eq("severity", "critical")\
                .limit(3)\
                .execute()
            findings = findings_result.data or []

        # Fall back to mock findings if no critical ones exist
        if not findings:
            findings = [
                {
                    "title": "SSL certificate expires in 7 days",
                    "severity": "critical",
                    "description": "Your SSL certificate for qualitymark.co expires in 7 days. If not renewed, visitors will see a security warning and your site will be marked as unsafe.",
                },
                {
                    "title": "Admin login has no two-factor authentication",
                    "severity": "critical",
                    "description": "Your admin account is not protected by two-factor authentication, making it vulnerable to password-based attacks.",
                },
            ]

        send_alert_email(company_name, to_email, findings)

        return {"message": f"Alert email sent to {to_email} with {len(findings)} finding(s)."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))