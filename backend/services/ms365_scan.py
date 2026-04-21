import os
import json
import httpx
from datetime import datetime, timezone, timedelta
from services.database import supabase_admin

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _sanitize_metadata(obj: dict) -> dict:
    return json.loads(json.dumps(obj, default=str))


def _get_frameworks(country: str, extra: list) -> list:
    c = (country or "NZ").upper()
    if c in ("UAE", "AE"):
        base = ["UAE PDPL 2021", "DIFC Data Protection Law", "ADGM", "ISO 27001"]
    elif c == "AU":
        base = ["Australian Privacy Act 1988", "ISO 27001", "ASD Essential Eight"]
    elif c == "IN":
        base = ["DPDP Act 2023", "RBI Guidelines", "CERT-In", "ISO 27001"]
    else:
        base = ["NZ Privacy Act 2020", "ISO 27001", "ASD Essential Eight"]
    return list(dict.fromkeys(base + (extra or [])))


async def _refresh_token(integration: dict) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{integration['azure_tenant_id']}/oauth2/v2.0/token",
            data={
                "grant_type": "refresh_token",
                "client_id": os.getenv("AZURE_CLIENT_ID"),
                "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
                "refresh_token": integration["refresh_token"],
                "scope": "https://graph.microsoft.com/.default offline_access",
            },
            timeout=20,
        )
        resp.raise_for_status()
        td = resp.json()

    new_token = td["access_token"]
    new_refresh = td.get("refresh_token", integration["refresh_token"])
    expires_in = td.get("expires_in", 3600)
    new_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    supabase_admin.table("integrations").update({
        "access_token": new_token,
        "refresh_token": new_refresh,
        "token_expires_at": new_expiry,
    }).eq("id", integration["id"]).execute()

    return new_token


async def _get_token(integration: dict) -> str:
    expires_at = integration.get("token_expires_at")
    if expires_at:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < expiry - timedelta(minutes=5):
            return integration["access_token"]
    return await _refresh_token(integration)


async def _graph_get(token: str, path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        if resp.status_code == 429:
            return {"value": []}
        resp.raise_for_status()
        return resp.json()


async def run_ms365_scan(tenant_id: str, scan_id: str) -> dict:
    result = supabase_admin.table("integrations")\
        .select("*")\
        .eq("tenant_id", tenant_id)\
        .eq("platform", "microsoft365")\
        .eq("status", "connected")\
        .single()\
        .execute()

    if not result.data:
        return {"findings_count": 0, "skipped": True}

    integration = result.data

    # Fetch tenant country + user-selected compliance frameworks
    tenant_r = supabase_admin.table("tenants")\
        .select("country, compliance_frameworks")\
        .eq("id", tenant_id)\
        .single()\
        .execute()

    country = "NZ"
    extra_frameworks: list = []
    if tenant_r.data:
        country = tenant_r.data.get("country") or "NZ"
        extra_frameworks = tenant_r.data.get("compliance_frameworks") or []

    frameworks = _get_frameworks(country, extra_frameworks)

    try:
        token = await _get_token(integration)
    except Exception as e:
        return {"findings_count": 0, "error": str(e)}

    findings = []

    # 1 — MFA STATUS
    try:
        mfa_data = await _graph_get(token, "/reports/credentialUserRegistrationDetails")
        no_mfa = [u for u in mfa_data.get("value", []) if not u.get("isMfaRegistered")]
        if no_mfa:
            n = len(no_mfa)
            findings.append({
                "tenant_id": tenant_id,
                "scan_id": scan_id,
                "engine": "microsoft365",
                "severity": "critical",
                "title": f"MFA not enabled for {n} Microsoft 365 user{'s' if n > 1 else ''}",
                "description": (
                    f"{n} account{'s' if n > 1 else ''} in your Microsoft 365 tenant "
                    "do not have multi-factor authentication registered. "
                    "These accounts can be compromised through password spray or phishing alone."
                ),
                "governance_gap": "No policy mandates multi-factor authentication for all staff.",
                "regulations": frameworks,
                "fix_type": "voice",
                "score_impact": min(25, n * 3),
                "status": "open",
                "metadata": _sanitize_metadata({
                    "affected_users": [
                        {
                            "name": u.get("userDisplayName", "Unknown"),
                            "email": u.get("userPrincipalName", ""),
                            "azure_object_id": u.get("id"),
                            "last_login": None,
                            "recommended_action": "Enable MFA immediately",
                        }
                        for u in no_mfa
                    ]
                }),
            })
    except Exception as e:
        print(f"[MS365] MFA check failed: {e}")

    # 2 — INACTIVE USERS (90+ days)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        inactive_data = await _graph_get(
            token,
            "/users",
            params={
                "$select": "id,displayName,userPrincipalName,signInActivity",
                "$filter": f"signInActivity/lastSignInDateTime le {cutoff}",
                "$top": "100",
            },
        )
        inactive = inactive_data.get("value", [])
        if inactive:
            n = len(inactive)
            findings.append({
                "tenant_id": tenant_id,
                "scan_id": scan_id,
                "engine": "microsoft365",
                "severity": "moderate",
                "title": f"{n} inactive Microsoft 365 account{'s' if n > 1 else ''} (90+ days)",
                "description": (
                    f"{n} user account{'s' if n > 1 else ''} have not signed in for over 90 days. "
                    "Stale accounts expand your attack surface and should be disabled or removed."
                ),
                "governance_gap": "No formal offboarding process exists to disable accounts when staff leave.",
                "regulations": frameworks,
                "fix_type": "voice",
                "score_impact": min(15, n * 2),
                "status": "open",
                "metadata": _sanitize_metadata({
                    "affected_users": [
                        {
                            "name": u.get("displayName", "Unknown"),
                            "email": u.get("userPrincipalName", ""),
                            "azure_object_id": u.get("id"),
                            "last_login": (
                                u.get("signInActivity", {}).get("lastSignInDateTime") or "Never"
                            ),
                            "recommended_action": "Disable or remove account",
                        }
                        for u in inactive
                    ]
                }),
            })
    except Exception as e:
        print(f"[MS365] Inactive users check failed: {e}")

    # 3 — ADMIN PRIVILEGE SPRAWL
    try:
        roles_data = await _graph_get(token, "/directoryRoles")
        admin_roles = [r for r in roles_data.get("value", []) if "admin" in r.get("displayName", "").lower()]

        admin_map: dict = {}  # email/id → {name, roles[]}
        for role in admin_roles:
            role_name = role.get("displayName", "Admin")
            members = await _graph_get(token, f"/directoryRoles/{role['id']}/members")
            for m in members.get("value", []):
                key = m.get("userPrincipalName") or m.get("id", "unknown")
                if key not in admin_map:
                    admin_map[key] = {"name": m.get("displayName", "Unknown"), "email": key, "roles": [], "azure_object_id": m.get("id")}
                admin_map[key]["roles"].append(role_name)

        if len(admin_map) > 3:
            n = len(admin_map)
            findings.append({
                "tenant_id": tenant_id,
                "scan_id": scan_id,
                "engine": "microsoft365",
                "severity": "moderate",
                "title": f"{n} accounts hold Microsoft 365 admin privileges",
                "description": (
                    f"{n} accounts have admin roles in your Microsoft 365 tenant. "
                    "Excessive admin accounts amplify the blast radius of any account compromise. "
                    "Best practice is to limit admin access to 2–3 dedicated break-glass accounts."
                ),
                "governance_gap": "No formal privileged access management policy exists.",
                "regulations": frameworks,
                "fix_type": "voice",
                "score_impact": min(15, n * 2),
                "status": "open",
                "metadata": _sanitize_metadata({
                    "affected_users": [
                        {
                            "name": info["name"],
                            "email": info["email"],
                            "azure_object_id": info.get("azure_object_id"),
                            "roles": ", ".join(info["roles"]),
                            "last_login": None,
                            "recommended_action": "Review and remove unnecessary admin access",
                        }
                        for info in admin_map.values()
                    ]
                }),
            })
    except Exception as e:
        print(f"[MS365] Admin check failed: {e}")

    # 4 — EXTERNAL FILE SHARING
    try:
        sites_data = await _graph_get(token, "/sites", params={"$select": "id,displayName,webUrl", "$top": "10"})
        external_count = 0
        for site in sites_data.get("value", [])[:5]:
            try:
                drives = await _graph_get(token, f"/sites/{site['id']}/drives")
                for drive in drives.get("value", [])[:3]:
                    items = await _graph_get(
                        token,
                        f"/drives/{drive['id']}/root/children",
                        params={"$select": "id,name,shared", "$top": "50"},
                    )
                    for item in items.get("value", []):
                        scope = item.get("shared", {}).get("scope", "")
                        if scope in ("anonymous", "organization"):
                            external_count += 1
            except Exception:
                pass
        if external_count > 0:
            findings.append({
                "tenant_id": tenant_id,
                "scan_id": scan_id,
                "engine": "microsoft365",
                "severity": "critical" if external_count > 10 else "moderate",
                "title": f"{external_count} file{'s' if external_count > 1 else ''} shared externally in Microsoft 365",
                "description": (
                    f"{external_count} file{'s' if external_count > 1 else ''} or folder{'s' if external_count > 1 else ''} "
                    "in your SharePoint/OneDrive are shared externally or via anonymous link. "
                    "Uncontrolled external sharing can expose sensitive business data to unauthorised parties."
                ),
                "governance_gap": "No policy governs external file sharing in SharePoint or OneDrive.",
                "regulations": frameworks,
                "fix_type": "voice",
                "score_impact": min(20, external_count * 2),
                "status": "open",
                "metadata": {"external_share_count": external_count},
            })
    except Exception as e:
        print(f"[MS365] External sharing check failed: {e}")

    inserted = 0
    for finding in findings:
        try:
            existing = supabase_admin.table("findings")\
                .select("id")\
                .eq("tenant_id", finding["tenant_id"])\
                .eq("title", finding["title"])\
                .limit(1)\
                .execute()

            if existing.data:
                existing_id = existing.data[0]["id"]
                update_payload = {k: v for k, v in finding.items() if k != "tenant_id"}
                supabase_admin.table("findings")\
                    .update(update_payload)\
                    .eq("id", existing_id)\
                    .execute()
            else:
                supabase_admin.table("findings").insert(finding).execute()
            inserted += 1
        except Exception as e:
            print(f"[MS365] Failed to upsert finding '{finding.get('title', '?')}': {e}")

    supabase_admin.table("integrations")\
        .update({"last_synced_at": datetime.now(timezone.utc).isoformat()})\
        .eq("id", integration["id"])\
        .execute()

    return {"findings_count": inserted}
