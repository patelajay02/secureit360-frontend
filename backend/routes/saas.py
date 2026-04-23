"""FastAPI router for the Universal SaaS Connector.

Routes:
    POST   /saas/connect/oauth/{app_slug}   — start an OAuth handshake
    GET    /saas/callback/{app_slug}        — handle provider callback (302)
    POST   /saas/connect/manual/{app_slug}  — store an API key via the vault
    POST   /saas/scan/{connection_id}       — run a scan
    GET    /saas/connections                — list caller's connections
    DELETE /saas/connections/{id}           — disconnect

All routes except the OAuth callback require a Bearer token. The callback
is reached by the browser after the SaaS provider redirects the user, so
it authenticates via the state token issued at /connect/oauth time.
"""

import os
import secrets
import time
import urllib.parse
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from services.auto_fix import run_saas_fix
from services.database import supabase_admin
from saas_connectors.ai_recipe_generator import generate_recipe
from saas_connectors.credential_vault import store_credentials
from saas_connectors.providers import PROVIDER_REGISTRY
from saas_connectors.scan_runner import run_scan


router = APIRouter()


def _frontend_connections_url() -> str:
    base = (os.getenv("FRONTEND_URL") or "https://app.secureit360.co").rstrip("/")
    return f"{base}/saas/connections"


STATE_TTL_SECONDS = 600  # 10 minutes is plenty for an OAuth round-trip


# ── OAuth state cache (in-memory, per-process) ─────────────────────────────
# Acceptable for MVP single-worker deployment. Move to a saas_oauth_states
# table if we ever go multi-worker or expect FastAPI restarts mid-handshake.

_STATE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _prune_states() -> None:
    now = time.time()
    for state in list(_STATE_CACHE.keys()):
        if _STATE_CACHE[state][0] < now:
            del _STATE_CACHE[state]


def _put_state(state: str, context: dict[str, Any]) -> None:
    _prune_states()
    _STATE_CACHE[state] = (time.time() + STATE_TTL_SECONDS, context)


def _pop_state(state: str) -> dict[str, Any] | None:
    _prune_states()
    entry = _STATE_CACHE.pop(state, None)
    return entry[1] if entry else None


# ── Auth + registry helpers ─────────────────────────────────────────────────

def _get_user_id(authorization: str) -> str:
    token = authorization.removeprefix("Bearer ")
    user = supabase_admin.auth.get_user(token)
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user.user.id


def _get_registry_entry(app_slug: str) -> dict[str, Any]:
    r = (
        supabase_admin.table("saas_app_registry")
        .select("slug, name, tier, oauth_config, wizard_recipe")
        .eq("slug", app_slug)
        .single()
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail=f"App '{app_slug}' is not in the registry")
    return r.data


def _callback_error_redirect(app_slug: str, reason: str) -> RedirectResponse:
    params = urllib.parse.urlencode({"error": reason, "app": app_slug})
    return RedirectResponse(url=f"{_frontend_connections_url()}?{params}", status_code=302)


# ── OAuth start ─────────────────────────────────────────────────────────────

@router.post("/connect/oauth/{app_slug}")
def oauth_start(app_slug: str, authorization: str = Header(...)):
    user_id = _get_user_id(authorization)
    entry = _get_registry_entry(app_slug)

    if entry.get("tier") != "1_oauth":
        raise HTTPException(status_code=400, detail=f"App '{app_slug}' is not an OAuth integration")

    provider_cls = PROVIDER_REGISTRY.get(app_slug)
    if not provider_cls:
        raise HTTPException(status_code=500, detail=f"No provider registered for '{app_slug}'")

    provider = provider_cls()
    state = secrets.token_urlsafe(32)
    try:
        auth_url = provider.build_auth_url(state)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Carry anything the provider stashed in flow_context (e.g. Xero PKCE
    # code_verifier) through the state cache so the callback can rebuild it.
    _put_state(state, {
        "user_id": user_id,
        "app_slug": app_slug,
        "flow_context": dict(provider.flow_context or {}),
    })
    return {"auth_url": auth_url, "state": state}


# ── OAuth callback ──────────────────────────────────────────────────────────

@router.get("/callback/{app_slug}")
def oauth_callback(app_slug: str, request: Request):
    qp = request.query_params
    error = qp.get("error")
    if error:
        return _callback_error_redirect(app_slug, error)

    code = qp.get("code")
    state = qp.get("state")
    if not code or not state:
        return _callback_error_redirect(app_slug, "missing_code_or_state")

    cached = _pop_state(state)
    if not cached or cached.get("app_slug") != app_slug:
        return _callback_error_redirect(app_slug, "invalid_or_expired_state")

    provider_cls = PROVIDER_REGISTRY.get(app_slug)
    if not provider_cls:
        return _callback_error_redirect(app_slug, "no_provider")

    provider = provider_cls()
    provider.flow_context = dict(cached.get("flow_context") or {})
    # Providers that learn their data-centre / token host from callback
    # query params (Zoho uses accounts-server) read it out of flow_context.
    accounts_server = qp.get("accounts-server") or qp.get("accounts_server")
    if accounts_server:
        provider.flow_context["accounts_server"] = accounts_server
    location = qp.get("location")
    if location:
        provider.flow_context["location"] = location

    try:
        tokens = provider.exchange_code(code)
    except Exception as e:
        print(f"[SaaS OAuth] exchange_code failed for {app_slug}: {e}")
        return _callback_error_redirect(app_slug, "token_exchange_failed")

    try:
        entry = _get_registry_entry(app_slug)
    except HTTPException:
        return _callback_error_redirect(app_slug, "registry_missing")

    try:
        store_credentials(
            user_id=cached["user_id"],
            app_slug=app_slug,
            app_name=entry["name"],
            connection_type="oauth",
            plaintext_credentials=tokens,
        )
    except Exception as e:
        print(f"[SaaS OAuth] store_credentials failed for {app_slug}: {e}")
        return _callback_error_redirect(app_slug, "store_failed")

    params = urllib.parse.urlencode({"connected": app_slug})
    return RedirectResponse(url=f"{_frontend_connections_url()}?{params}", status_code=302)


# ── Manual credential connect ───────────────────────────────────────────────

class ManualConnectRequest(BaseModel):
    credentials: dict[str, Any]


class GenerateRecipeRequest(BaseModel):
    app_name: str


@router.post("/connect/manual/{app_slug}")
def manual_connect(
    app_slug: str,
    data: ManualConnectRequest,
    authorization: str = Header(...),
):
    user_id = _get_user_id(authorization)
    entry = _get_registry_entry(app_slug)

    if not data.credentials:
        raise HTTPException(status_code=400, detail="credentials object is required")

    try:
        connection_id = store_credentials(
            user_id=user_id,
            app_slug=app_slug,
            app_name=entry["name"],
            connection_type="api_key",
            plaintext_credentials=data.credentials,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"connection_id": connection_id, "app_slug": app_slug, "app_name": entry["name"]}


# ── AI-generated wizard recipe ──────────────────────────────────────────────
# The catalog page calls this when the director searches for an app that
# isn't in the registry. generate_recipe() validates Claude's output
# strictly — broken JSON short-circuits to a friendly 422 rather than
# caching garbage that every subsequent user would inherit.

@router.post("/generate-recipe")
def generate_recipe_endpoint(
    data: GenerateRecipeRequest,
    authorization: str = Header(...),
):
    _get_user_id(authorization)
    app_name = (data.app_name or "").strip()
    if not app_name:
        raise HTTPException(status_code=400, detail="app_name is required")

    row = generate_recipe(app_name)
    if not row:
        raise HTTPException(
            status_code=422,
            detail=(
                f"We couldn't auto-generate a guide for {app_name} — please "
                "email governance@secureit360.co and we'll add it for you."
            ),
        )
    return row


# ── Scan trigger ────────────────────────────────────────────────────────────

@router.post("/scan/{connection_id}")
def scan_connection(connection_id: str, authorization: str = Header(...)):
    user_id = _get_user_id(authorization)

    owner = (
        supabase_admin.table("saas_connections")
        .select("user_id")
        .eq("id", connection_id)
        .single()
        .execute()
    )
    if not owner.data:
        raise HTTPException(status_code=404, detail="Connection not found")
    if owner.data["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    try:
        return run_scan(connection_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Public app catalog ──────────────────────────────────────────────────────
# Read-only, unauthenticated — the registry is catalog data. The frontend
# catalog page calls this to render connect tiles.

@router.get("/apps")
def list_apps():
    r = (
        supabase_admin.table("saas_app_registry")
        .select("slug, name, logo_url, tier, verified, wizard_recipe, generic_check_capabilities")
        .order("name")
        .execute()
    )
    return {"apps": r.data or []}


# ── All findings across caller's connections ───────────────────────────────

@router.get("/findings")
def list_findings(authorization: str = Header(...)):
    user_id = _get_user_id(authorization)
    conns = (
        supabase_admin.table("saas_connections")
        .select("id, app_slug, app_name")
        .eq("user_id", user_id)
        .execute()
    )
    conn_rows = conns.data or []
    if not conn_rows:
        return {"findings": []}

    conn_ids = [c["id"] for c in conn_rows]
    conn_map = {c["id"]: c for c in conn_rows}

    r = (
        supabase_admin.table("saas_findings")
        .select("*")
        .in_("connection_id", conn_ids)
        .order("created_at", desc=True)
        .execute()
    )

    findings = []
    for f in r.data or []:
        conn = conn_map.get(f.get("connection_id")) or {}
        f["app_slug"] = conn.get("app_slug")
        f["app_name"] = conn.get("app_name")
        findings.append(f)
    return {"findings": findings}


# ── List connections ────────────────────────────────────────────────────────

@router.get("/connections")
def list_connections(authorization: str = Header(...)):
    user_id = _get_user_id(authorization)
    r = (
        supabase_admin.table("saas_connections")
        .select("id, app_slug, app_name, connection_type, status, last_scan_at, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"connections": r.data or []}


# ── Auto-fix a SaaS finding ────────────────────────────────────────────────
# Matches the scan-side /scans/auto-fix/{id} endpoint. No handlers are
# registered today; current Xero + Zoho OAuth tokens are read-only so
# every SaaS check fails the "can we realistically fix this" bar.

@router.post("/findings/{finding_id}/auto-fix")
def auto_fix_saas_finding(finding_id: str, authorization: str = Header(...)):
    user_id = _get_user_id(authorization)

    finding_r = (
        supabase_admin.table("saas_findings")
        .select("*")
        .eq("id", finding_id)
        .single()
        .execute()
    )
    finding = finding_r.data
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    owner = (
        supabase_admin.table("saas_connections")
        .select("user_id")
        .eq("id", finding["connection_id"])
        .single()
        .execute()
    )
    if not owner.data or owner.data["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if not finding.get("auto_fixable"):
        raise HTTPException(
            status_code=400,
            detail="This finding cannot be auto-fixed. It requires action on your side.",
        )

    try:
        result = run_saas_fix(finding)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    supabase_admin.table("saas_findings").delete().eq("id", finding_id).execute()
    return {
        "message": result.get("message") or "Fixed.",
        "finding_id": finding_id,
        "status": "auto_resolved",
    }


# ── Disconnect ──────────────────────────────────────────────────────────────

@router.delete("/connections/{connection_id}")
def disconnect(connection_id: str, authorization: str = Header(...)):
    user_id = _get_user_id(authorization)

    owner = (
        supabase_admin.table("saas_connections")
        .select("user_id")
        .eq("id", connection_id)
        .single()
        .execute()
    )
    if not owner.data:
        raise HTTPException(status_code=404, detail="Connection not found")
    if owner.data["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    supabase_admin.table("saas_connections").delete().eq("id", connection_id).execute()
    return {"message": "Disconnected", "connection_id": connection_id}
