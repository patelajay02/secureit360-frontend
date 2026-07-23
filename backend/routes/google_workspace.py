import os
import base64
import urllib.parse
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from services.database import supabase_admin
from services.google_workspace_scan import run_google_workspace_scan
from middleware.auth_middleware import require_active_membership

router = APIRouter()

_REDIRECT_URI = "https://app.secureit360.co/api/google/callback"

_GOOGLE_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
])


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


# ── Generate OAuth URL ──────────────────────────────────────────────────────

@router.get("/auth")
def google_auth_url(authorization: str = Header(...)):
    """Return the full Google OAuth URL (with state) for the frontend to redirect to."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID env var is not set on the server")

    print(f"[GWS] /auth called — client_id={client_id[:20]}... redirect_uri={_REDIRECT_URI}")

    token = authorization.removeprefix("Bearer ")
    state = base64.urlsafe_b64encode(token.encode()).rstrip(b"=").decode()
    params = {
        "client_id": client_id,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": _GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print(f"[GWS] auth_url built — first 100 chars: {url[:100]}")
    return {"auth_url": url, "debug_client_id_prefix": client_id[:30]}


# ── Connect Google Workspace ────────────────────────────────────────────────

class GoogleConnectRequest(BaseModel):
    code: str
    redirect_uri: str


@router.post("/connect")
async def connect_google(data: GoogleConnectRequest, authorization: str = Header(...)):
    try:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET env var is not set")

        print(f"[GWS] /connect called — client_id={client_id[:20]}... redirect_uri={data.redirect_uri}")

        user_id, tenant_id = _get_tenant(authorization)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": data.code,
                    "redirect_uri": data.redirect_uri,
                },
                timeout=20,
            )
            if not resp.is_success:
                err = resp.json()
                raise HTTPException(
                    status_code=400,
                    detail=err.get("error_description", "Token exchange failed"),
                )
            td = resp.json()

        access_token = td["access_token"]
        refresh_token = td.get("refresh_token")
        token_expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=td.get("expires_in", 3600))
        ).isoformat()

        # Derive org name from the admin's email domain
        org_name = None
        try:
            async with httpx.AsyncClient() as client:
                info_resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if info_resp.is_success:
                    email = info_resp.json().get("email", "")
                    if "@" in email:
                        org_name = email.split("@")[1]
        except Exception:
            pass

        supabase_admin.table("integrations").upsert(
            {
                "tenant_id": tenant_id,
                "platform": "google_workspace",
                "status": "connected",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": token_expiry,
                "connected_by": user_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "org_name": org_name,
            },
            on_conflict="tenant_id,platform",
        ).execute()

        return {"message": "Google Workspace connected successfully", "org_name": org_name}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Disconnect Google Workspace ─────────────────────────────────────────────

@router.delete("/disconnect")
async def disconnect_google(authorization: str = Header(...)):
    try:
        _, tenant_id = _get_tenant(authorization)
        supabase_admin.table("integrations").update({
            "status": "disconnected",
            "access_token": None,
            "refresh_token": None,
        }).eq("tenant_id", tenant_id).eq("platform", "google_workspace").execute()
        return {"message": "Google Workspace disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Trigger Google Workspace scan ───────────────────────────────────────────

@router.post("/scan")
async def scan_google(authorization: str = Header(...)):
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

        scan_payload = {
            "tenant_id": tenant_id,
            "triggered_by": user_id,
            "trigger_type": "manual",
            "status": "running",
        }
        if domain_id:
            scan_payload["domain_id"] = domain_id

        scan = supabase_admin.table("scans").insert(scan_payload).execute()
        scan_id = scan.data[0]["id"]

        result = await run_google_workspace_scan(tenant_id, scan_id)

        supabase_admin.table("scans").update({"status": "complete"}).eq("id", scan_id).execute()

        return {
            "message": "Google Workspace scan complete",
            "scan_id": scan_id,
            "findings_count": result.get("findings_count", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
