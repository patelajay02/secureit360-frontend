# SecureIT360 - Authentication Routes
import threading
import hashlib
import time
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from services.database import supabase, supabase_admin
from middleware.auth_middleware import (
    require_platform_admin,
    get_current_user,
    get_request_ip,
    get_user_tenant_membership,
    is_platform_admin,
    require_active_membership,
    get_owner_tenant_id,
    get_security_context,
    role_requires_mfa,
    user_has_verified_factor,
    mfa_gate_decision,
    INCOMPLETE_SETUP_DETAIL,
)
from services.audit import log_audit
from services.rate_limit import enforce_rate_limit
from services.recaptcha import verify_recaptcha
from services.password_policy import validate_password, PasswordPolicyError
from services.compromised_password import is_compromised
from services.recovery_codes import generate_recovery_codes, verify_recovery_code
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str
    company_name: str
    domain: str
    country: str
    mobile: Optional[str] = ""
    recaptcha_token: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str


# --- REGISTER -----------------------------------------------------------

@router.post("/register")
def register(data: RegisterRequest, request: Request):
    ip = get_request_ip(request)
    enforce_rate_limit(f"register:{ip}", 5, 3600)
    if not verify_recaptcha(data.recaptcha_token, ip):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed. Please try again.")
    try:
        email_domain = data.email.split('@')[-1].lower()
        company_domain = data.domain.lower().replace('www.', '')
        if email_domain != company_domain:
            raise HTTPException(
                status_code=400,
                detail=f"Your email must match your company domain. Expected an email ending in @{company_domain}"
            )

        # Password policy + compromised-password screening (before Supabase sign-up).
        try:
            validate_password(data.password, email=data.email, company_name=data.company_name)
        except PasswordPolicyError as pe:
            raise HTTPException(status_code=400, detail=str(pe))
        if is_compromised(data.password):
            raise HTTPException(
                status_code=400,
                detail="This password has appeared in a known data breach. Please choose a different one.",
            )

        existing_domain = supabase_admin.table("domains")\
            .select("id")\
            .eq("domain", company_domain)\
            .execute()

        if existing_domain.data:
            raise HTTPException(
                status_code=400,
                detail="This domain is already registered. If you believe this is an error, contact governance@secureit360.co"
            )

        auth_response = supabase.auth.sign_up({"email": data.email, "password": data.password})
        user_id = auth_response.user.id

        slug = data.company_name.lower().replace(" ", "-")

        tenant = supabase_admin.table("tenants").insert({
            "name": data.company_name,
            "slug": slug,
            "status": "pending",
            "trial_ends_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "country": data.country,
            "mobile": data.mobile
        }).execute()

        tenant_id = tenant.data[0]["id"]

        supabase_admin.table("tenant_users").insert({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": "owner",
            "status": "active"
        }).execute()

        verify_token = "secureit360-verify=" + hashlib.sha256(f"{tenant_id}:{company_domain}".encode()).hexdigest()[:24]
        supabase_admin.table("domains").insert({
            "tenant_id": tenant_id,
            "domain": company_domain,
            "is_primary": True,
            "verified": False,
            "verify_token": verify_token
        }).execute()

        company_name = data.company_name
        email = data.email

        def send_verification_email():
            try:
                print(f"[EMAIL] Generating verification link for {email}")
                link_response = supabase_admin.auth.admin.generate_link({
                    "type": "signup",
                    "email": email,
                    "options": {
                        "redirect_to": "https://app.secureit360.co/auth-confirm"
                    }
                })
                verification_url = link_response.properties.action_link
                print(f"[EMAIL] URL generated: {verification_url}")

                sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
                message = Mail(
                    from_email=os.getenv("SENDGRID_FROM_EMAIL"),
                    to_emails=email,
                    subject="Welcome to SecureIT360 - Please verify your email",
                    html_content=f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                            <h2 style="color: #dc2626;">Welcome to SecureIT360!</h2>
                            <p>Hi {company_name},</p>
                            <p>Thank you for registering. Your 7-day free trial will start once you verify your email.</p>
                            <p>Please click the button below to verify your email address and activate your account:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{verification_url}" style="display: inline-block; background-color: #dc2626; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">Verify My Email</a>
                            </div>
                            <p style="color: #666; font-size: 14px;">If the button does not work, copy and paste this link into your browser:</p>
                            <p style="color: #666; font-size: 12px; word-break: break-all;">{verification_url}</p>
                            <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                            <p style="color: #666; font-size: 14px;">The SecureIT360 Team<br>hello@secureit360.co</p>
                        </div>
                    """
                )
                sg_response = sg.send(message)
                print(f"[EMAIL] SendGrid status: {sg_response.status_code}")
            except Exception as email_error:
                print(f"[EMAIL ERROR] {str(email_error)}")
                if hasattr(email_error, 'body'):
                    print(f"[EMAIL ERROR BODY] {email_error.body}")

        threading.Thread(target=send_verification_email).start()

        return {
            "message": "Account created successfully. Please check your email to verify your account.",
            "tenant_id": tenant_id,
            "email": data.email
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[REGISTER ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- LOGIN --------------------------------------------------------------

@router.post("/login")
def login(data: LoginRequest, request: Request):
    ip = get_request_ip(request)
    enforce_rate_limit(f"login:{ip}", 10, 300)
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

        user_id = auth_response.user.id
        if not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid login credentials")
        token = auth_response.session.access_token
        refresh_token = auth_response.session.refresh_token

        # ── Platform admins authenticate INDEPENDENTLY of tenant membership ──
        # A global admin has no tenant, tenant_users row, or domain. Check
        # platform_admins first and return a tenant-less session; never fall
        # through to the tenant lookup for them.
        if is_platform_admin(user_id):
            return {
                "token": token,
                "refresh_token": refresh_token,
                "user_id": user_id,
                "email": data.email,
                "tenant_id": None,
                "role": "platform_admin",
                "is_platform_admin": True,
                "company_name": "SecureIT360",
                "plan": None,
                "status": "active",
                "trial_ends_at": None,
                "country": None,
                "mobile": "",
            }

        # ── Regular users: resolve their active tenant membership ──
        # maybe_single() so 0 rows is a normal, handled outcome (not PGRST116).
        tenant_user = supabase_admin.table("tenant_users")\
            .select("*, tenants(*)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .maybe_single()\
            .execute()

        if not tenant_user or not getattr(tenant_user, "data", None):
            raise HTTPException(status_code=409, detail=INCOMPLETE_SETUP_DETAIL)

        tenant = tenant_user.data["tenants"]
        tenant_status = tenant.get("status")

        if tenant_status == "pending":
            raise HTTPException(
                status_code=403,
                detail="Please verify your email address before logging in. Check your inbox for the verification link."
            )

        if tenant_status == "trial":
            trial_ends_at = tenant.get("trial_ends_at")
            if trial_ends_at:
                trial_end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
                if datetime.now(trial_end.tzinfo) > trial_end:
                    raise HTTPException(
                        status_code=403,
                        detail="Your free trial has expired. Please subscribe to continue at app.secureit360.co/pricing"
                    )

        if tenant_status == "suspended":
            raise HTTPException(
                status_code=403,
                detail="Your account has been suspended. Please contact governance@secureit360.co"
            )

        if tenant_status == "cancelled":
            raise HTTPException(
                status_code=403,
                detail="Your subscription has been cancelled. Please resubscribe at app.secureit360.co/pricing"
            )

        if tenant_status == "past_due":
            raise HTTPException(
                status_code=403,
                detail="Your last payment failed. Please update your payment details at app.secureit360.co/pricing"
            )

        return {
            "token": token,
            "refresh_token": refresh_token,
            "user_id": user_id,
            "email": data.email,
            "tenant_id": tenant_user.data["tenant_id"],
            "role": tenant_user.data["role"],
            "company_name": tenant["name"],
            "plan": tenant.get("plan"),
            "status": tenant_status,
            "trial_ends_at": tenant.get("trial_ends_at"),
            "country": tenant.get("country", "NZ"),
            "mobile": tenant.get("mobile", "")
        }

    except HTTPException:
        raise
    except Exception as e:
        # Never leak raw PGRST/DB errors to the client; log securely server-side.
        print(f"[LOGIN ERROR] {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail="We couldn't log you in right now. Please try again or contact support.",
        )


# --- MFA STATUS (Stage 1) ----------------------------------------------
# Reports whether MFA is required for the caller's role and the current session
# assurance level, so the frontend can require enrollment / an AAL2 challenge.
# Privileged roles (platform_admin, tenant owner) require MFA.

@router.get("/security/mfa-status")
def mfa_status(ctx: dict = Depends(get_security_context)):
    if ctx["is_platform_admin"]:
        role = "platform_admin"
    else:
        membership = get_user_tenant_membership(ctx["user_id"])
        role = membership.get("role") if membership else None
    has_factor = user_has_verified_factor(ctx["user_id"])  # None if lookup failed
    # Authoritative post-login routing decision (frontend maps this to a route).
    gate = mfa_gate_decision(ctx["is_platform_admin"], role, has_factor, ctx.get("aal"))
    return {
        "aal": ctx.get("aal"),
        "is_aal2": ctx.get("aal") == "aal2",
        "mfa_required": role_requires_mfa(ctx["is_platform_admin"], role),
        "has_verified_factor": bool(has_factor),  # False when unknown; see `gate`
        "gate": gate,  # "enroll" | "challenge" | "allow"
        "is_platform_admin": ctx["is_platform_admin"],
        "role": role,
    }


# --- MFA RECOVERY CODES (Stage 1b) -------------------------------------
# Generation returns plaintext ONCE (never stored/logged); verification is
# one-time and rate-limited and does not disclose structural validity.

class RecoveryVerifyRequest(BaseModel):
    code: str


@router.post("/security/recovery-codes")
def create_recovery_codes(request: Request, ctx: dict = Depends(get_security_context)):
    """Generate a fresh batch of recovery codes for the authenticated user.
    Requires AAL2 when enforcement is enabled (the user has just verified MFA)."""
    ip = get_request_ip(request)
    enforce_rate_limit(f"recovery-gen:{ctx['user_id']}", 5, 3600)
    codes = generate_recovery_codes(ctx["user_id"])
    log_audit("auth.mfa.recovery_regenerated", actor_user_id=ctx["user_id"],
              target_type="user", target_id=ctx["user_id"], outcome="success", ip=ip,
              detail={"count": len(codes)})
    return {"codes": codes}  # shown once


@router.post("/security/recovery-codes/verify")
def verify_recovery(data: RecoveryVerifyRequest, request: Request,
                    caller: dict = Depends(get_current_user)):
    """Verify + consume a recovery code (one-time). Generic response; does not
    reveal whether the code was structurally valid."""
    ip = get_request_ip(request)
    enforce_rate_limit(f"recovery-verify:{ip}", 10, 900)
    enforce_rate_limit(f"recovery-verify-user:{caller['user_id']}", 10, 900)
    ok = verify_recovery_code(caller["user_id"], data.code)
    log_audit("auth.mfa.recovery_used", actor_user_id=caller["user_id"],
              target_type="user", target_id=caller["user_id"],
              outcome="success" if ok else "denied", ip=ip)
    return {"verified": ok}


# --- REFRESH TOKEN ------------------------------------------------------

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh")
def refresh_token(data: RefreshRequest):
    try:
        session = supabase.auth.refresh_session(data.refresh_token)
        if not session or not session.session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        return {
            "token": session.session.access_token,
            "refresh_token": session.session.refresh_token
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[REFRESH ERROR] {str(e)}")
        raise HTTPException(status_code=401, detail="Could not refresh session")


# --- DELETE USER (authenticated) ----------------------------------------

@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request, caller: dict = Depends(get_current_user)):
    """Delete a user account. Authorized only when the caller is:
      - deleting their own account, OR
      - an owner/admin of the SAME tenant as the target, OR
      - a platform admin.
    """
    caller_id = caller["user_id"]
    ip = get_request_ip(request)

    target_membership = get_user_tenant_membership(user_id)
    target_tenant_id = target_membership["tenant_id"] if target_membership else None

    # Platform-admin check (authoritative table).
    is_admin = False
    try:
        admin_row = supabase_admin.table("platform_admins")\
            .select("user_id").eq("user_id", caller_id).limit(1).execute()
        is_admin = bool(admin_row.data)
    except Exception:
        is_admin = False

    authorized = False
    if caller_id == user_id:
        authorized = True  # self-deletion
    elif is_admin:
        authorized = True
    else:
        caller_membership = get_user_tenant_membership(caller_id)
        if (caller_membership and target_membership
                and caller_membership["tenant_id"] == target_membership["tenant_id"]
                and caller_membership["role"] in ("owner", "admin")):
            authorized = True

    if not authorized:
        log_audit("auth.user.delete", actor_user_id=caller_id, target_type="user",
                  target_id=user_id, target_tenant_id=target_tenant_id,
                  outcome="denied", ip=ip)
        raise HTTPException(status_code=403, detail="Not authorized to delete this user")

    try:
        supabase_admin.rpc("delete_user_completely", {"p_user_id": user_id}).execute()
        log_audit("auth.user.delete", actor_user_id=caller_id, target_type="user",
                  target_id=user_id, target_tenant_id=target_tenant_id,
                  outcome="success", ip=ip)
        return {"message": "User deleted successfully"}
    except Exception as e:
        log_audit("auth.user.delete", actor_user_id=caller_id, target_type="user",
                  target_id=user_id, target_tenant_id=target_tenant_id,
                  outcome="error", ip=ip)
        print(f"[DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- INVITE USER --------------------------------------------------------

@router.post("/invite")
def invite_user(data: dict, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        membership = require_active_membership(user_id, "tenant_id, role, tenants(name)")
        role = membership["role"]
        tenant_id = membership["tenant_id"]
        company_name = membership["tenants"]["name"]

        if role not in ["owner", "admin"]:
            raise HTTPException(status_code=403, detail="Only owners and admins can invite team members.")

        invited_email = data.get("email")
        invited_role = data.get("role", "member")

        message = Mail(
            from_email=os.getenv("SENDGRID_FROM_EMAIL"),
            to_emails=invited_email,
            subject=f"You have been invited to join {company_name} on SecureIT360",
            html_content=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #dc2626;">You have been invited!</h2>
                    <p>Hello,</p>
                    <p>You have been invited to join <strong>{company_name}</strong> on SecureIT360.</p>
                    <p>Your role will be: <strong>{invited_role}</strong></p>
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                    <p style="color: #666; font-size: 14px;">The SecureIT360 Team<br>hello@secureit360.co</p>
                </div>
            """
        )

        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        sg.send(message)

        return {"message": f"Invitation sent to {invited_email}"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[INVITE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- GET USERS ----------------------------------------------------------

@router.get("/users")
def get_users(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_id = require_active_membership(user_id, "tenant_id")["tenant_id"]

        users = supabase_admin.table("tenant_users")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .execute()

        return {"users": users.data}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - LIST ALL USERS ---------------------------------------------

@router.get("/admin/me")
def admin_me(admin: dict = Depends(require_platform_admin)):
    """Frontend gate: 200 + is_platform_admin only for a verified platform admin;
    otherwise require_platform_admin raises 401/403. No secret, no client trust."""
    return {"is_platform_admin": True, "user_id": admin["user_id"]}


# Batched owner-email retrieval config.
_ADMIN_LIST_PAGE_SIZE = 200      # Supabase Auth list_users page size
_ADMIN_LIST_MAX_PAGES = 50       # safety cap (<= 10k users scanned)
MAX_ADMIN_PAGE_SIZE = 100        # max tenants per /admin/users page


def _fetch_owner_emails(owner_ids: set) -> dict:
    """Return {user_id: email} for the given owner ids using the batched Supabase
    Auth list-users API — NO per-owner network calls.

    Pages through admin.list_users(page, per_page); stops as soon as every needed
    id is found, a short/empty page is returned, or the safety cap is hit. Ids not
    found (e.g. a deleted auth user) are simply absent from the map and handled by
    the caller as a blank email.
    """
    email_map: dict = {}
    remaining = set(owner_ids)
    if not remaining:
        return email_map

    page = 1
    while page <= _ADMIN_LIST_MAX_PAGES and remaining:
        batch = supabase_admin.auth.admin.list_users(page=page, per_page=_ADMIN_LIST_PAGE_SIZE)
        if not batch:
            break
        for u in batch:
            uid = getattr(u, "id", None)
            if uid in remaining:
                email_map[uid] = getattr(u, "email", None)
                remaining.discard(uid)
        if len(batch) < _ADMIN_LIST_PAGE_SIZE:
            break  # last page reached
        page += 1
    return email_map


@router.get("/admin/users")
def admin_get_users(
    request: Request,
    admin: dict = Depends(require_platform_admin),
    page: int = 1,
    page_size: int = 25,
    search: str = "",
    status: str = "",
):
    t0 = time.perf_counter()
    try:
        page = max(1, page)
        page_size = min(max(1, page_size), MAX_ADMIN_PAGE_SIZE)
        offset = (page - 1) * page_size

        # Only the fields the admin UI needs — no select("*").
        q = supabase_admin.table("tenants").select(
            "id, name, country, status, plan, trial_ends_at, created_at, "
            "tenant_users(user_id, role, status)",
            count="exact",
        )
        if status:
            q = q.eq("status", status)
        if search:
            q = q.ilike("name", f"%{search}%")

        t_q = time.perf_counter()
        res = q.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
        tenant_query_ms = (time.perf_counter() - t_q) * 1000

        tenants = res.data or []
        total = getattr(res, "count", None) or 0

        # Owner id for each tenant on THIS page only.
        owner_by_tenant: dict = {}
        owner_ids: set = set()
        for tenant in tenants:
            for tu in (tenant.get("tenant_users") or []):
                if tu.get("role") == "owner":
                    owner_by_tenant[tenant["id"]] = tu["user_id"]
                    owner_ids.add(tu["user_id"])
                    break

        t_a = time.perf_counter()
        email_map = _fetch_owner_emails(owner_ids)
        auth_fetch_ms = (time.perf_counter() - t_a) * 1000

        users = []
        for tenant in tenants:
            owner_id = owner_by_tenant.get(tenant["id"])
            if not owner_id:
                continue  # no owner membership (unchanged behaviour)
            users.append({
                "user_id": owner_id,
                "email": email_map.get(owner_id) or "",
                "company_name": tenant.get("name", ""),
                "country": tenant.get("country", ""),
                "status": tenant.get("status", ""),
                "plan": tenant.get("plan", ""),
                "trial_ends_at": tenant.get("trial_ends_at", ""),
                "created_at": tenant.get("created_at", ""),
                "tenant_id": tenant["id"],
            })

        total_pages = ((total + page_size - 1) // page_size) if total else 1
        total_ms = (time.perf_counter() - t0) * 1000
        print(f"[PERF] /auth/admin/users tenant_query={tenant_query_ms:.0f}ms "
              f"auth_fetch={auth_fetch_ms:.0f}ms total={total_ms:.0f}ms "
              f"tenants={len(tenants)} owners={len(owner_ids)}")

        log_audit("admin.users.list", actor_user_id=admin["user_id"],
                  outcome="success", ip=get_request_ip(request),
                  detail={"count": len(users), "page": page, "total": total})
        return {
            "users": users,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    except HTTPException:
        raise
    except Exception as e:
        # Never leak raw DB errors to the browser.
        print(f"[ADMIN ERROR] {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Could not load the client list. Please try again.")


# --- ADMIN - DELETE USER ------------------------------------------------

@router.delete("/admin/delete/{user_id}")
def admin_delete_user(user_id: str, request: Request, admin: dict = Depends(require_platform_admin)):
    ip = get_request_ip(request)
    target_membership = get_user_tenant_membership(user_id)
    target_tenant_id = target_membership["tenant_id"] if target_membership else None
    try:
        supabase_admin.rpc("delete_user_completely", {"p_user_id": user_id}).execute()
        log_audit("admin.user.delete", actor_user_id=admin["user_id"], target_type="user",
                  target_id=user_id, target_tenant_id=target_tenant_id,
                  outcome="success", ip=ip)
        return {"message": "User deleted successfully"}
    except Exception as e:
        log_audit("admin.user.delete", actor_user_id=admin["user_id"], target_type="user",
                  target_id=user_id, target_tenant_id=target_tenant_id,
                  outcome="error", ip=ip)
        print(f"[ADMIN DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - SUSPEND / UNSUSPEND ----------------------------------------

class SuspendRequest(BaseModel):
    action: str

@router.post("/admin/suspend/{user_id}")
def admin_suspend_user(user_id: str, data: SuspendRequest, request: Request,
                       admin: dict = Depends(require_platform_admin)):
    ip = get_request_ip(request)
    try:
        tenant_id = get_owner_tenant_id(user_id)
        if not tenant_id:
            raise HTTPException(status_code=404, detail="This user does not own a tenant.")
        new_status = "suspended" if data.action == "suspend" else "trial"

        supabase_admin.table("tenants")\
            .update({"status": new_status})\
            .eq("id", tenant_id)\
            .execute()

        log_audit("admin.tenant.suspend", actor_user_id=admin["user_id"], target_type="tenant",
                  target_id=tenant_id, target_tenant_id=tenant_id, outcome="success", ip=ip,
                  detail={"action": data.action, "new_status": new_status})
        return {"message": f"User {data.action}ed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        log_audit("admin.tenant.suspend", actor_user_id=admin["user_id"], target_type="user",
                  target_id=user_id, outcome="error", ip=ip, detail={"action": data.action})
        print(f"[SUSPEND ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - GRANT / REVOKE FULL ACCESS ---------------------------------

class AccessRequest(BaseModel):
    action: str

@router.post("/admin/access/{user_id}")
def admin_grant_access(user_id: str, data: AccessRequest, request: Request,
                       admin: dict = Depends(require_platform_admin)):
    ip = get_request_ip(request)
    try:
        tenant_id = get_owner_tenant_id(user_id)
        if not tenant_id:
            raise HTTPException(status_code=404, detail="This user does not own a tenant.")

        if data.action == "grant":
            supabase_admin.table("tenants")\
                .update({"status": "comped", "plan": "comped"})\
                .eq("id", tenant_id)\
                .execute()
        else:
            supabase_admin.table("tenants")\
                .update({"status": "trial", "plan": None})\
                .eq("id", tenant_id)\
                .execute()

        log_audit("admin.tenant.access", actor_user_id=admin["user_id"], target_type="tenant",
                  target_id=tenant_id, target_tenant_id=tenant_id, outcome="success", ip=ip,
                  detail={"action": data.action})
        return {"message": f"Access {data.action}ed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        log_audit("admin.tenant.access", actor_user_id=admin["user_id"], target_type="user",
                  target_id=user_id, outcome="error", ip=ip, detail={"action": data.action})
        print(f"[ACCESS ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - EXTEND TRIAL -----------------------------------------------

class ExtendTrialRequest(BaseModel):
    days: int

@router.post("/admin/extend-trial/{user_id}")
def admin_extend_trial(user_id: str, data: ExtendTrialRequest, request: Request,
                       admin: dict = Depends(require_platform_admin)):
    ip = get_request_ip(request)
    try:
        tenant_id = get_owner_tenant_id(user_id)
        if not tenant_id:
            raise HTTPException(status_code=404, detail="This user does not own a tenant.")

        tenant = supabase_admin.table("tenants")\
            .select("trial_ends_at")\
            .eq("id", tenant_id)\
            .single()\
            .execute()

        current_end = tenant.data.get("trial_ends_at")
        if current_end:
            current_dt = datetime.fromisoformat(current_end.replace("Z", "+00:00"))
            if current_dt < datetime.now(current_dt.tzinfo):
                new_end = datetime.now(current_dt.tzinfo) + timedelta(days=data.days)
            else:
                new_end = current_dt + timedelta(days=data.days)
        else:
            new_end = datetime.utcnow() + timedelta(days=data.days)

        supabase_admin.table("tenants")\
            .update({
                "trial_ends_at": new_end.isoformat(),
                "status": "trial"
            })\
            .eq("id", tenant_id)\
            .execute()

        log_audit("admin.tenant.extend_trial", actor_user_id=admin["user_id"], target_type="tenant",
                  target_id=tenant_id, target_tenant_id=tenant_id, outcome="success", ip=ip,
                  detail={"days": data.days})
        return {"message": f"Trial extended by {data.days} days"}

    except HTTPException:
        raise
    except Exception as e:
        log_audit("admin.tenant.extend_trial", actor_user_id=admin["user_id"], target_type="user",
                  target_id=user_id, outcome="error", ip=ip, detail={"days": data.days})
        print(f"[EXTEND TRIAL ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - CREATE TEST ACCOUNT ----------------------------------------

class CreateAccountRequest(BaseModel):
    company_name: str
    email: str
    password: str
    country: str = "NZ"

@router.post("/admin/create-account")
def admin_create_account(data: CreateAccountRequest, request: Request,
                         admin: dict = Depends(require_platform_admin)):
    ip = get_request_ip(request)
    try:
        # Admin-created accounts must meet the same password policy + screening.
        try:
            validate_password(data.password, email=data.email, company_name=data.company_name)
        except PasswordPolicyError as pe:
            raise HTTPException(status_code=400, detail=str(pe))
        if is_compromised(data.password):
            log_audit("auth.password.compromised_blocked", actor_user_id=admin["user_id"],
                      target_type="account", outcome="denied", ip=ip,
                      detail={"reason": "compromised_password"})
            raise HTTPException(
                status_code=400,
                detail="This password has appeared in a known data breach. Please choose a different one.",
            )

        auth_response = supabase_admin.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": True
        })
        user_id = auth_response.user.id

        slug = data.company_name.lower().replace(" ", "-") + "-test"

        tenant = supabase_admin.table("tenants").insert({
            "name": data.company_name,
            "slug": slug,
            "status": "comped",
            "plan": "comped",
            "trial_ends_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
            "country": data.country,
        }).execute()

        tenant_id = tenant.data[0]["id"]

        supabase_admin.table("tenant_users").insert({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": "owner",
            "status": "active"
        }).execute()

        domain = data.email.split('@')[-1]
        supabase_admin.table("domains").insert({
            "tenant_id": tenant_id,
            "domain": domain,
            "is_primary": True,
            "verified": True
        }).execute()

        log_audit("admin.account.create", actor_user_id=admin["user_id"], target_type="tenant",
                  target_id=tenant_id, target_tenant_id=tenant_id, outcome="success", ip=ip,
                  detail={"company_name": data.company_name, "country": data.country})
        return {
            "message": "Test account created successfully",
            "tenant_id": tenant_id,
            "email": data.email,
            "login_url": "https://app.secureit360.co/login"
        }

    except HTTPException:
        raise
    except Exception as e:
        log_audit("admin.account.create", actor_user_id=admin["user_id"],
                  outcome="error", ip=ip, detail={"company_name": data.company_name})
        print(f"[CREATE ACCOUNT ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- RE-AUTHENTICATE (for sensitive data reveal) ------------------------

class ReauthRequest(BaseModel):
    password: str

@router.post("/verify-password")
def verify_password(data: ReauthRequest, authorization: str = Header(...)):
    """Verify the caller's password before revealing sensitive finding metadata."""
    try:
        token = authorization.replace("Bearer ", "")
        user_obj = supabase_admin.auth.get_user(token)
        if not user_obj or not user_obj.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        auth_user = supabase_admin.auth.admin.get_user_by_id(user_obj.user.id)
        if not auth_user or not auth_user.user:
            raise HTTPException(status_code=401, detail="Could not resolve user")

        email = auth_user.user.email
        supabase.auth.sign_in_with_password({"email": email, "password": data.password})
        return {"verified": True}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Incorrect password")


# --- VERIFY EMAIL CALLBACK ----------------------------------------------

@router.post("/verify-email")
def verify_email(request: Request, caller: dict = Depends(get_current_user)):
    """Activate the caller's OWN account (pending -> trial).

    The user_id is derived from the verified Supabase access token supplied in
    the Authorization header (the token present on the email-confirmation
    redirect) — never trusted from the request body. This prevents an attacker
    from activating an arbitrary account by POSTing someone else's user_id.
    """
    ip = get_request_ip(request)
    enforce_rate_limit(f"verify-email:{ip}", 20, 3600)
    try:
        user_id = caller["user_id"]

        tenant_id = require_active_membership(user_id, "tenant_id")["tenant_id"]

        supabase_admin.table("tenants")\
            .update({"status": "trial"})\
            .eq("id", tenant_id)\
            .eq("status", "pending")\
            .execute()

        log_audit("auth.email.verify", actor_user_id=user_id, actor_tenant_id=tenant_id,
                  target_type="tenant", target_id=tenant_id, target_tenant_id=tenant_id,
                  outcome="success", ip=ip)
        return {"message": "Account activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[VERIFY EMAIL ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))



