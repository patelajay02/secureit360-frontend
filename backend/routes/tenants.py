# backend/routes/tenants.py
# SecureIT360 - Tenant routes
# Handles logo upload, tenant profile management, and director email

import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, EmailStr
from typing import Optional
from middleware.auth_middleware import get_current_tenant
from services.database import supabase_admin

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
LOGOS_BUCKET = "logos"


# --- Upload Logo --------------------------------------------------------

@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    tenant=Depends(get_current_tenant)
):
    try:
        tenant_id = tenant["tenant_id"]

        allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload PNG, JPG, SVG or WebP.")

        contents = await file.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 2MB.")

        ext = file.filename.split(".")[-1].lower()
        file_path = f"{tenant_id}/logo.{ext}"

        supabase_admin.storage.from_(LOGOS_BUCKET).upload(
            file_path,
            contents,
            {"content-type": file.content_type, "upsert": "true"}
        )

        logo_url = f"{SUPABASE_URL}/storage/v1/object/public/{LOGOS_BUCKET}/{file_path}"

        supabase_admin.table("tenants")\
            .update({"logo_url": logo_url})\
            .eq("id", tenant_id)\
            .execute()

        return {"logo_url": logo_url}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGO UPLOAD ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Could not upload logo.")


# --- Delete Logo --------------------------------------------------------

@router.delete("/logo")
async def delete_logo(tenant=Depends(get_current_tenant)):
    try:
        tenant_id = tenant["tenant_id"]

        tenant_result = supabase_admin.table("tenants")\
            .select("logo_url")\
            .eq("id", tenant_id)\
            .single()\
            .execute()

        logo_url = tenant_result.data.get("logo_url")
        if logo_url:
            for ext in ["png", "jpg", "jpeg", "svg", "webp"]:
                try:
                    supabase_admin.storage.from_(LOGOS_BUCKET).remove([f"{tenant_id}/logo.{ext}"])
                except Exception:
                    pass

        supabase_admin.table("tenants")\
            .update({"logo_url": None})\
            .eq("id", tenant_id)\
            .execute()

        return {"message": "Logo removed successfully."}

    except Exception as e:
        print(f"[LOGO DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Could not remove logo.")


# --- Get Tenant Profile -------------------------------------------------

@router.get("/profile")
async def get_profile(tenant=Depends(get_current_tenant)):
    try:
        tenant_id = tenant["tenant_id"]

        result = supabase_admin.table("tenants")\
            .select("*")\
            .eq("id", tenant_id)\
            .single()\
            .execute()

        return result.data

    except Exception as e:
        print(f"[PROFILE ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Could not load profile.")


# --- Get Tenant (Me) ----------------------------------------------------

@router.get("/me")
async def get_tenant_me(tenant=Depends(get_current_tenant)):
    try:
        tenant_id = tenant["tenant_id"]

        result = supabase_admin.table("tenants")\
            .select("id, name, country, director_email, logo_url, compliance_frameworks")\
            .eq("id", tenant_id)\
            .single()\
            .execute()

        return result.data

    except Exception as e:
        print(f"[TENANT ME ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Could not load tenant.")


# --- Update Tenant (Me) -------------------------------------------------

class TenantUpdateRequest(BaseModel):
    director_email: Optional[str] = None
    compliance_frameworks: Optional[list] = None

@router.patch("/me")
async def update_tenant_me(
    body: TenantUpdateRequest,
    tenant=Depends(get_current_tenant)
):
    try:
        tenant_id = tenant["tenant_id"]

        updates = {}
        if body.director_email is not None:
            updates["director_email"] = body.director_email if body.director_email.strip() != "" else None
        if body.compliance_frameworks is not None:
            updates["compliance_frameworks"] = body.compliance_frameworks

        if not updates:
            raise HTTPException(status_code=400, detail="Nothing to update.")

        supabase_admin.table("tenants")\
            .update(updates)\
            .eq("id", tenant_id)\
            .execute()

        return {"message": "Tenant updated successfully."}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[TENANT UPDATE ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Could not update tenant.")