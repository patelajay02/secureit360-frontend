import os
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from services.database import supabase_admin
from services.ms365_scan import run_ms365_scan
from middleware.auth_middleware import require_active_membership

router = APIRouter()

_MS365_SCOPES = (
    "User.Read.All UserAuthenticationMethod.Read.All "
    "AuditLog.Read.All Directory.Read.All Sites.Read.All offline_access"
)


def _get_tenant(authorization: str) -> tuple[str, str]:
    """Return (user_id, tenant_id) from a Bearer token, raising 401/403 on failure."""
    token = authorization.removeprefix("Bearer ")
    user = supabase_admin.auth.get_user(token)
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id
    # maybe_single via the shared helper: no active membership -> friendly 409,
    # never a raw PGRST116. Platform admins (no tenant) are correctly denied here.
    tenant_id = require_active_membership(user_id, "tenant_id")["tenant_id"]
    return user_id, tenant_id


# ── GET integration statuses ────────────────────────────────────────────────

@router.get("/status")
async def get_integrations_status(authorization: str = Header(...)):
    try:
        _, tenant_id = _get_tenant(authorization)
        result = (
            supabase_admin.table("integrations")
            .select("platform,status,connected_at,last_synced_at,org_name")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return {"integrations": result.data or []}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Connect Microsoft 365 ───────────────────────────────────────────────────

class MS365ConnectRequest(BaseModel):
    code: str
    redirect_uri: str


@router.post("/ms365/connect")
async def connect_ms365(data: MS365ConnectRequest, authorization: str = Header(...)):
    try:
        user_id, tenant_id = _get_tenant(authorization)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": os.getenv("AZURE_CLIENT_ID"),
                    "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
                    "code": data.code,
                    "redirect_uri": data.redirect_uri,
                    "scope": _MS365_SCOPES,
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

        azure_tenant_id = org_name = None
        try:
            async with httpx.AsyncClient() as client:
                org_resp = await client.get(
                    "https://graph.microsoft.com/v1.0/organization",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if org_resp.is_success:
                    orgs = org_resp.json().get("value", [])
                    if orgs:
                        azure_tenant_id = orgs[0].get("id")
                        org_name = orgs[0].get("displayName")
        except Exception:
            pass

        supabase_admin.table("integrations").upsert(
            {
                "tenant_id": tenant_id,
                "platform": "microsoft365",
                "status": "connected",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": token_expiry,
                "azure_tenant_id": azure_tenant_id,
                "connected_by": user_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "org_name": org_name,
            },
            on_conflict="tenant_id,platform",
        ).execute()

        return {"message": "Microsoft 365 connected successfully", "org_name": org_name}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Disconnect Microsoft 365 ────────────────────────────────────────────────

@router.delete("/ms365/disconnect")
async def disconnect_ms365(authorization: str = Header(...)):
    try:
        _, tenant_id = _get_tenant(authorization)
        supabase_admin.table("integrations").update({
            "status": "disconnected",
            "access_token": None,
            "refresh_token": None,
        }).eq("tenant_id", tenant_id).eq("platform", "microsoft365").execute()
        return {"message": "Microsoft 365 disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Trigger Microsoft 365 scan ──────────────────────────────────────────────

@router.post("/ms365/scan")
async def scan_ms365(authorization: str = Header(...)):
    try:
        user_id, tenant_id = _get_tenant(authorization)

        # Reuse primary domain if it exists; domain_id is nullable for cloud-only scans
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

        result = await run_ms365_scan(tenant_id, scan_id)

        supabase_admin.table("scans").update({"status": "complete"}).eq("id", scan_id).execute()

        return {
            "message": "Microsoft 365 scan complete",
            "scan_id": scan_id,
            "findings_count": result.get("findings_count", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
