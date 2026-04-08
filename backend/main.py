# SecureIT360 - Main Application File
# Entry point for the entire backend.
# Creates the FastAPI app, sets up CORS, connects all routes, and starts the scheduler.

import os
from fastapi import FastAPI
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

# Import scheduler
from services.scheduler import start_scheduler

# Create Supabase client
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

# --- Startup and shutdown -----------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(supabase)
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

# --- Health check -------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "product": "SecureIT360"}
