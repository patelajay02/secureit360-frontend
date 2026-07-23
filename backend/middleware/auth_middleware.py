# backend/middleware/auth_middleware.py
# SecureIT360 - Authentication & authorization dependencies
#
# Every privileged route enforces authorization at the dependency layer (not
# only via any global middleware). Token is verified server-side against
# Supabase Auth; roles are loaded from the database, never trusted from the
# client. Platform-admin status is the ONLY source of global authority and is
# stored in public.platform_admins.
#
#   Return codes:
#     401 - missing or invalid authentication
#     403 - authenticated but not authorized
import os
import time
import json
import base64
from typing import Optional, Tuple
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.database import supabase_admin

# auto_error=False so a MISSING credential yields our own 401 (not the default 403).
security = HTTPBearer(auto_error=False)


def get_request_ip(request: Request) -> Optional[str]:
    """Best-effort source IP. Honors X-Forwarded-For (Railway/Vercel proxy)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # First entry is the original client.
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _verify_token(credentials: Optional[HTTPAuthorizationCredentials]) -> Tuple[str, str]:
    """Verify a Supabase access token server-side. Returns (user_id, token)."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication",
        )
    token = credentials.credentials
    try:
        user = supabase_admin.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if not user or not user.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user.user.id, token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Any authenticated user. Does not require tenant membership."""
    user_id, token = _verify_token(credentials)
    return {"user_id": user_id, "token": token}


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Authenticated user resolved to their active tenant + role."""
    user_id, token = _verify_token(credentials)
    result = supabase_admin.table("tenant_users")\
        .select("tenant_id, role")\
        .eq("user_id", user_id)\
        .eq("status", "active")\
        .limit(1)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant found for this user",
        )
    return {
        "user_id": user_id,
        "tenant_id": result.data[0]["tenant_id"],
        "role": result.data[0]["role"],
        "token": token,
    }


async def require_tenant_admin(
    tenant: dict = Depends(get_current_tenant),
):
    """Tenant owner/admin. Scoped to the caller's OWN tenant only."""
    if tenant.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires tenant owner or admin role",
        )
    return tenant


async def require_platform_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Platform-wide administrator. Authoritative source: public.platform_admins."""
    _t0 = time.perf_counter()
    user_id, token = _verify_token(credentials)
    # Throttle privileged actions (distributed limiter). Import here to avoid a
    # circular import at module load.
    from services.rate_limit import enforce_rate_limit
    enforce_rate_limit(f"admin:{user_id}", 120, 60)
    try:
        res = supabase_admin.table("platform_admins")\
            .select("user_id")\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()
    except Exception:
        # Fail closed: if we can't confirm platform-admin status, deny.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    # Step-up: platform-admin actions require an MFA-verified (AAL2) session when
    # enforcement is enabled (operator-controlled; OFF by default -> no lockout).
    if aal2_enforcement_enabled() and get_token_aal(token) != "aal2":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication is required for administrator actions.",
        )
    print(f"[PERF] admin.authz {(time.perf_counter() - _t0) * 1000:.0f}ms")
    return {"user_id": user_id, "token": token}


def get_user_tenant_membership(user_id: str) -> Optional[dict]:
    """Helper: return {tenant_id, role} for a user's active membership, or None."""
    res = supabase_admin.table("tenant_users")\
        .select("tenant_id, role")\
        .eq("user_id", user_id)\
        .eq("status", "active")\
        .limit(1)\
        .execute()
    if res.data:
        return res.data[0]
    return None


# ── Tenant-independence helpers ──────────────────────────────────────────────
# Platform admins are a GLOBAL identity that lives entirely outside the tenant
# hierarchy. Not every authenticated user belongs to a tenant, and no user is
# assumed to belong to exactly one. Zero active memberships is a normal outcome
# (a platform admin, or an incompletely-provisioned account) and is handled with
# maybe_single() + a friendly message — never a raw PGRST116 error.

INCOMPLETE_SETUP_DETAIL = "Your account setup is incomplete. Please contact support."


def is_platform_admin(user_id: str) -> bool:
    """True if the user is a platform (global) admin. Independent of any tenant."""
    try:
        res = supabase_admin.table("platform_admins")\
            .select("user_id").eq("user_id", user_id).limit(1).execute()
        return bool(res.data)
    except Exception:
        return False


def resolve_active_membership(user_id: str, select: str = "tenant_id, role") -> Optional[dict]:
    """Return the user's active tenant_users row (dict) or None.

    Uses maybe_single() so 0 rows is a normal result, not an exception.
    """
    res = supabase_admin.table("tenant_users")\
        .select(select)\
        .eq("user_id", user_id)\
        .eq("status", "active")\
        .maybe_single()\
        .execute()
    return res.data if res and getattr(res, "data", None) else None


def require_active_membership(user_id: str, select: str = "tenant_id, role") -> dict:
    """Resolve the active membership or raise a friendly 409 (never PGRST116)."""
    membership = resolve_active_membership(user_id, select)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=INCOMPLETE_SETUP_DETAIL,
        )
    return membership


# ── Assurance level (AAL) — MFA enforcement ─────────────────────────────────
# The session's assurance level lives in the `aal` claim of the Supabase JWT
# ("aal1" = password only, "aal2" = password + verified MFA). We read it ONLY
# from a token that _verify_token has already authenticated against Supabase Auth
# (get_user), so the claim is trustworthy and no signing secret is needed here.

def _decode_jwt_claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # pad base64url
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def get_token_aal(token: str) -> Optional[str]:
    """Return the session assurance level ('aal1'|'aal2') from a validated token."""
    return _decode_jwt_claims(token).get("aal")


async def get_security_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Reusable security context for privileged routes: verified identity plus
    assurance level and platform-admin flag. 401 on missing/invalid auth."""
    user_id, token = _verify_token(credentials)  # authenticity confirmed by Supabase
    aal = get_token_aal(token)
    is_admin = False
    try:
        res = supabase_admin.table("platform_admins")\
            .select("user_id").eq("user_id", user_id).limit(1).execute()
        is_admin = bool(res.data)
    except Exception:
        is_admin = False
    return {"user_id": user_id, "token": token, "aal": aal, "is_platform_admin": is_admin}


def role_requires_mfa(is_platform_admin: bool, role: Optional[str]) -> bool:
    """Roles for which MFA is MANDATORY (decision D5, mapped onto the real model):
    platform admins and tenant OWNERS. Tenant `admin` may additionally be required
    by tenant security policy (later stage); `member` is optional-by-default.
    (`security_manager`/`company_admin` intentionally absent — not in the schema.)
    """
    return bool(is_platform_admin or role == "owner")


def aal2_enforcement_enabled() -> bool:
    """Whether AAL2 (MFA) is actively enforced on privileged routes.

    Controlled by the AAL2_ENFORCEMENT env var (default OFF). This is the
    NO-LOCKOUT-WINDOW safety valve: the operator flips it ON only AFTER
    confirming (smoke test) that enrollment + challenge work and privileged
    users can reach AAL2. While OFF, privileged routes behave exactly as before
    (role-only), so shipping this code cannot lock anyone out.
    """
    return os.getenv("AAL2_ENFORCEMENT", "off").strip().lower() in ("on", "true", "1", "yes")


async def require_aal2(ctx: dict = Depends(get_security_context)):
    """Require an MFA-verified (AAL2) session for a high-risk operation. 403 for
    insufficient assurance (distinct from 401 for missing authentication). Reused
    explicitly at route level — never relied on from the frontend alone. Gated by
    aal2_enforcement_enabled() so activation is operator-controlled."""
    if aal2_enforcement_enabled() and ctx.get("aal") != "aal2":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication is required for this action.",
        )
    return ctx


def get_owner_tenant_id(user_id: str) -> Optional[str]:
    """Return the tenant_id a user OWNS (role='owner'), or None.

    This is a TARGET-user lookup used by platform-admin actions (suspend/comp/
    extend a customer) — distinct from caller-membership resolution above. Uses
    maybe_single() so a user who owns no tenant yields None (a 404), never a
    raw PGRST116.
    """
    res = supabase_admin.table("tenant_users")\
        .select("tenant_id")\
        .eq("user_id", user_id)\
        .eq("role", "owner")\
        .maybe_single()\
        .execute()
    return res.data["tenant_id"] if res and getattr(res, "data", None) else None
