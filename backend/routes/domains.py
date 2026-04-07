# SecureIT360 - Domain Management Routes
# Handles: Adding domains, DNS verification, listing, deleting

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from services.database import supabase, supabase_admin
import hashlib
import socket
import dns.resolver

router = APIRouter()

PLAN_LIMITS = {
    "trial": 1,
    "starter": 1,
    "pro": 3,
    "enterprise": 10
}

class DomainRequest(BaseModel):
    domain: str

class VerifyRequest(BaseModel):
    domain_id: str

# ADD A DOMAIN (unverified)
@router.post("/")
def add_domain(data: DomainRequest, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id, tenants(plan)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]
        plan = tenant_user.data["tenants"]["plan"]

        existing = supabase_admin.table("domains")\
            .select("id")\
            .eq("tenant_id", tenant_id)\
            .execute()

        max_domains = PLAN_LIMITS.get(plan, 1)

        if len(existing.data) >= max_domains:
            raise HTTPException(
                status_code=400,
                detail=f"Your {plan} plan allows {max_domains} domain(s). Please upgrade to add more."
            )

        # Generate unique verification token
        raw = f"{tenant_id}:{data.domain}"
        verify_token = "secureit360-verify=" + hashlib.sha256(raw.encode()).hexdigest()[:24]

        domain = supabase_admin.table("domains").insert({
            "tenant_id": tenant_id,
            "domain": data.domain.lower().strip(),
            "verified": False,
            "is_primary": len(existing.data) == 0,
            "verify_token": verify_token
        }).execute()

        return {
            "message": "Domain added. Please verify ownership.",
            "domain": domain.data[0],
            "verify_token": verify_token
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# CHECK DNS VERIFICATION
@router.post("/verify")
def verify_domain(data: VerifyRequest, authorization: str = Header(...)):
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

        domain_row = supabase_admin.table("domains")\
            .select("*")\
            .eq("id", data.domain_id)\
            .eq("tenant_id", tenant_id)\
            .single()\
            .execute()

        if not domain_row.data:
            raise HTTPException(status_code=404, detail="Domain not found.")

        domain = domain_row.data["domain"]
        expected_token = domain_row.data["verify_token"]

        # Check DNS TXT records
        found = False
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            for rdata in answers:
                for txt_string in rdata.strings:
                    if expected_token.encode() in txt_string or expected_token in txt_string.decode("utf-8", errors="ignore"):
                        found = True
                        break
        except Exception:
            pass

        if not found:
            return {
                "verified": False,
                "message": "TXT record not found yet. DNS changes can take up to 30 minutes to spread. Please try again shortly."
            }

        # Mark as verified
        supabase_admin.table("domains")\
            .update({"verified": True})\
            .eq("id", data.domain_id)\
            .execute()

        return {"verified": True, "message": "Domain verified successfully."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# GET ALL DOMAINS
@router.get("/")
def get_domains(authorization: str = Header(...)):
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

        domains = supabase_admin.table("domains")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .execute()

        return {"domains": domains.data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# DELETE A DOMAIN
@router.delete("/{domain_id}")
def delete_domain(domain_id: str, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        tenant_user = supabase_admin.table("tenant_users")\
            .select("tenant_id, role")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .single()\
            .execute()

        tenant_id = tenant_user.data["tenant_id"]
        role = tenant_user.data["role"]

        if role not in ["owner", "admin"]:
            raise HTTPException(status_code=403, detail="Only owners and admins can delete domains.")

        domain = supabase_admin.table("domains")\
            .select("id")\
            .eq("id", domain_id)\
            .eq("tenant_id", tenant_id)\
            .single()\
            .execute()

        if not domain.data:
            raise HTTPException(status_code=404, detail="Domain not found.")

        supabase_admin.table("domains")\
            .delete()\
            .eq("id", domain_id)\
            .eq("tenant_id", tenant_id)\
            .execute()

        return {"message": "Domain deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
