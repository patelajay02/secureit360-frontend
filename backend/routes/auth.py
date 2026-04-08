# SecureIT360 - Authentication Routes
import threading
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from services.database import supabase, supabase_admin
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
def register(data: RegisterRequest):
    try:
        email_domain = data.email.split('@')[-1].lower()
        company_domain = data.domain.lower().replace('www.', '')
        if email_domain != company_domain:
            raise HTTPException(
                status_code=400,
                detail=f"Your email must match your company domain. Expected an email ending in @{company_domain}"
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

        auth_response = supabase_admin.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": False
        })
        user_id = auth_response.user.id

        slug = data.company_name.lower().replace(" ", "-")

        tenant = supabase_admin.table("tenants").insert({
            "name": data.company_name,
            "slug": slug,
            "status": "trial",
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

        supabase_admin.table("domains").insert({
            "tenant_id": tenant_id,
            "domain": company_domain,
            "is_primary": True,
            "verified": False
        }).execute()

        company_name = data.company_name
        email = data.email

        def send_verification_email():
            try:
                print(f"[EMAIL] Generating verification link for {email}")
                link_response = supabase_admin.auth.admin.generate_link({
                    "type": "signup",
                    "email": email,
                })
                verification_url = link_response.properties.action_link
                print(f"[EMAIL] URL generated successfully")

                sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
                message = Mail(
                    from_email=os.getenv("SENDGRID_FROM_EMAIL"),
                    to_emails=email,
                    subject="Welcome to SecureIT360 - Please verify your email",
                    html_content=f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                            <h2 style="color: #dc2626;">Welcome to SecureIT360!</h2>
                            <p>Hi {company_name},</p>
                            <p>Thank you for registering. Your 7-day free trial has started.</p>
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
            "message": "Account created successfully",
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
def login(data: LoginRequest):
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

        tenant_user = supabase_admin.table("tenant_users")\
            .select("*, tenants(*)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant = tenant_user.data["tenants"]
        tenant_status = tenant.get("status")

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
        raise HTTPException(status_code=400, detail=str(e))


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
def delete_user(user_id: str, authorization: str = Header(...)):
    try:
        supabase_admin.rpc("delete_user_completely", {"p_user_id": user_id}).execute()
        return {"message": "User deleted successfully"}
    except Exception as e:
        print(f"[DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- INVITE USER --------------------------------------------------------

@router.post("/invite")
def invite_user(data: dict, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id, role, tenants(name)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        role = tenant_user.data["role"]
        tenant_id = tenant_user.data["tenant_id"]
        company_name = tenant_user.data["tenants"]["name"]

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

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]

        users = supabase_admin.table("tenant_users")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .execute()

        return {"users": users.data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - LIST ALL USERS ---------------------------------------------

@router.get("/admin/users")
def admin_get_users():
    try:
        tenants = supabase_admin.table("tenants")\
            .select("*, tenant_users(user_id, role, status)")\
            .execute()

        users = []
        for tenant in tenants.data:
            for tu in tenant.get("tenant_users", []):
                if tu["role"] == "owner":
                    try:
                        auth_user = supabase_admin.auth.admin.get_user_by_id(tu["user_id"])
                        users.append({
                            "user_id": tu["user_id"],
                            "email": auth_user.user.email,
                            "company_name": tenant["name"],
                            "country": tenant.get("country", ""),
                            "status": tenant.get("status", ""),
                            "plan": tenant.get("plan", ""),
                            "trial_ends_at": tenant.get("trial_ends_at", ""),
                            "created_at": tenant.get("created_at", ""),
                            "tenant_id": tenant["id"]
                        })
                    except Exception:
                        pass

        return {"users": users}

    except Exception as e:
        print(f"[ADMIN ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - DELETE USER ------------------------------------------------

# --- ADMIN - DELETE USER ------------------------------------------------

@router.delete("/admin/delete/{user_id}")
def admin_delete_user(user_id: str):
    try:
        tenant_user = supabase_admin.table("tenant_users").select("tenant_id").eq("user_id", user_id).eq("role", "owner").single().execute()
        tenant_id = tenant_user.data["tenant_id"]
        domains = supabase_admin.table("domains").select("id").eq("tenant_id", tenant_id).execute()
        domain_ids = [d["id"] for d in domains.data]
        if domain_ids:
            scans = supabase_admin.table("scans").select("id").in_("domain_id", domain_ids).execute()
            scan_ids = [s["id"] for s in scans.data]
            if scan_ids:
                supabase_admin.table("findings").delete().in_("scan_id", scan_ids).execute()
                supabase_admin.table("scan_engine_results").delete().in_("scan_id", scan_ids).execute()
            supabase_admin.table("scans").delete().in_("domain_id", domain_ids).execute()
        supabase_admin.table("subscriptions").delete().eq("tenant_id", tenant_id).execute()
        supabase_admin.table("domains").delete().eq("tenant_id", tenant_id).execute()
        supabase_admin.table("tenant_users").delete().eq("tenant_id", tenant_id).execute()
        supabase_admin.table("tenants").delete().eq("id", tenant_id).execute()
        supabase_admin.auth.admin.delete_user(user_id)
        return {"message": "User deleted successfully"}
    except Exception as e:
        print(f"[ADMIN DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - SUSPEND / UNSUSPEND ----------------------------------------

class SuspendRequest(BaseModel):
    action: str

@router.post("/admin/suspend/{user_id}")
def admin_suspend_user(user_id: str, data: SuspendRequest):
    try:
        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("role", "owner")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]
        new_status = "suspended" if data.action == "suspend" else "trial"

        supabase_admin.table("tenants")\
            .update({"status": new_status})\
            .eq("id", tenant_id)\
            .execute()

        return {"message": f"User {data.action}ed successfully"}

    except Exception as e:
        print(f"[SUSPEND ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - GRANT / REVOKE FULL ACCESS ---------------------------------

class AccessRequest(BaseModel):
    action: str

@router.post("/admin/access/{user_id}")
def admin_grant_access(user_id: str, data: AccessRequest):
    try:
        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("role", "owner")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]

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

        return {"message": f"Access {data.action}ed successfully"}

    except Exception as e:
        print(f"[ACCESS ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - EXTEND TRIAL -----------------------------------------------

class ExtendTrialRequest(BaseModel):
    days: int

@router.post("/admin/extend-trial/{user_id}")
def admin_extend_trial(user_id: str, data: ExtendTrialRequest):
    try:
        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id")\
            .eq("user_id", user_id)\
            .eq("role", "owner")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]

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

        return {"message": f"Trial extended by {data.days} days"}

    except Exception as e:
        print(f"[EXTEND TRIAL ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# --- ADMIN - CREATE TEST ACCOUNT ----------------------------------------

class CreateAccountRequest(BaseModel):
    company_name: str
    email: str
    password: str
    country: str = "NZ"

@router.post("/admin/create-account")
def admin_create_account(data: CreateAccountRequest):
    try:
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

        return {
            "message": "Test account created successfully",
            "tenant_id": tenant_id,
            "email": data.email,
            "login_url": "https://app.secureit360.co/login"
        }

    except Exception as e:
        print(f"[CREATE ACCOUNT ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
