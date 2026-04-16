import re

with open('backend/routes/auth.py', 'r', encoding='utf-8-sig') as f:
    content = f.read()

old = '''# --- ADMIN - DELETE USER ------------------------------------------------

@router.delete("/admin/delete/{user_id}")
def admin_delete_user(user_id: str):
    try:
        supabase_admin.rpc("delete_user_completely", {"p_user_id": user_id}).execute()
        return {"message": "User deleted successfully"}
    except Exception as e:
        print(f"[ADMIN DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))'''

new = '''# --- ADMIN - DELETE USER ------------------------------------------------

@router.delete("/admin/delete/{user_id}")
def admin_delete_user(user_id: str):
    try:
        tenant_user = supabase_admin.table("tenant_users").select("tenant_id").eq("user_id", user_id).eq("role", "owner").single().execute()
        tenant_id = tenant_user.data["tenant_id"]
        domains = supabase_admin.table("domains").select("id").eq("tenant_id", tenant_id).execute()
        domain_ids = [d["id"] for d in domains.data]
        if domain_ids:
            supabase_admin.table("scans").delete().in_("domain_id", domain_ids).execute()
        supabase_admin.table("domains").delete().eq("tenant_id", tenant_id).execute()
        supabase_admin.table("tenant_users").delete().eq("tenant_id", tenant_id).execute()
        supabase_admin.table("tenants").delete().eq("id", tenant_id).execute()
        supabase_admin.auth.admin.delete_user(user_id)
        return {"message": "User deleted successfully"}
    except Exception as e:
        print(f"[ADMIN DELETE ERROR] {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))'''

if old in content:
    content = content.replace(old, new)
    with open('backend/routes/auth.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS')
else:
    print('NOT FOUND - checking line endings...')
    print(repr(content[content.find('delete_user_completely')-200:content.find('delete_user_completely')+100]))
