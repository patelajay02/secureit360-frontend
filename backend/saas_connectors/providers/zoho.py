"""Zoho Tier-1 OAuth provider (Zoho CRM + account data center).

Reads ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET from the environment. Zoho
authorizes against the global accounts.zoho.com host and then redirects
the user back with accounts-server and location query-string parameters
identifying their regional data centre. We use accounts-server for token
exchange and use the api_domain returned on token exchange for
subsequent API calls.
"""

from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .base import BaseProvider, register_provider


AUTH_URL = "https://accounts.zoho.com/oauth/v2/auth"
DEFAULT_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
DEFAULT_API_DOMAIN = "https://www.zohoapis.com"
REDIRECT_URI = "https://secureit360-production.up.railway.app/saas/callback/zoho"

SCOPES = "ZohoCRM.users.READ,ZohoCRM.org.READ,AaaServer.profile.READ"


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is not set")
    return value


def _iso_expires_at(expires_in: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()


def _token_url_from_accounts_server(accounts_server: str | None) -> str:
    if not accounts_server:
        return DEFAULT_TOKEN_URL
    base = accounts_server.rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    return f"{base}/oauth/v2/token"


def _resolve_org_id(api_domain: str, access_token: str) -> str | None:
    try:
        resp = httpx.get(
            f"{api_domain}/crm/v5/org",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        orgs = (resp.json() or {}).get("org") or []
        if orgs:
            return str(orgs[0].get("zgid") or orgs[0].get("id") or "")
    except Exception:
        pass
    return None


@register_provider("zoho")
class ZohoProvider(BaseProvider):
    def build_auth_url(self, state: str) -> str:
        client_id = _env("ZOHO_CLIENT_ID")
        params = {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        client_id = _env("ZOHO_CLIENT_ID")
        client_secret = _env("ZOHO_CLIENT_SECRET")
        accounts_server = self.flow_context.get("accounts_server")
        token_url = _token_url_from_accounts_server(accounts_server)

        resp = httpx.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": REDIRECT_URI,
                "code": code,
            },
            timeout=30,
        )
        resp.raise_for_status()
        td = resp.json()
        if "error" in td:
            raise RuntimeError(f"Zoho token exchange failed: {td.get('error')}")

        api_domain = td.get("api_domain") or DEFAULT_API_DOMAIN
        access_token = td["access_token"]
        org_id = _resolve_org_id(api_domain, access_token)

        return {
            "access_token": access_token,
            "refresh_token": td.get("refresh_token"),
            "expires_at": _iso_expires_at(td.get("expires_in", 3600)),
            "tenant_id_or_org_id": org_id,
            "extra": {
                "api_domain": api_domain,
                "accounts_server": accounts_server,
                "scope": td.get("scope"),
                "token_type": td.get("token_type", "Bearer"),
            },
        }

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        client_id = _env("ZOHO_CLIENT_ID")
        client_secret = _env("ZOHO_CLIENT_SECRET")
        accounts_server = self.flow_context.get("accounts_server")
        token_url = _token_url_from_accounts_server(accounts_server)

        resp = httpx.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        td = resp.json()
        if "error" in td:
            raise RuntimeError(f"Zoho token refresh failed: {td.get('error')}")

        api_domain = td.get("api_domain") or DEFAULT_API_DOMAIN
        return {
            "access_token": td["access_token"],
            # Zoho does not rotate the refresh_token on refresh_grant
            "refresh_token": refresh_token,
            "expires_at": _iso_expires_at(td.get("expires_in", 3600)),
            "tenant_id_or_org_id": None,
            "extra": {
                "api_domain": api_domain,
                "accounts_server": accounts_server,
                "scope": td.get("scope"),
                "token_type": td.get("token_type", "Bearer"),
            },
        }

    def fetch_payloads(
        self,
        credentials: dict[str, Any],
        capabilities: list[str],
    ) -> dict[str, Any]:
        user_caps = {"admin_ratio", "mfa_coverage", "dormant_users"}
        if not any(c in user_caps for c in capabilities):
            return {}

        users = self._fetch_users(credentials)
        payloads: dict[str, Any] = {}
        for cap in capabilities:
            if cap in user_caps:
                payloads[cap] = users
        return payloads

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_admin(role_name: str | None) -> bool:
        if not role_name:
            return False
        r = role_name.lower()
        return (
            "administrator" in r
            or "admin" in r
            or "ceo" in r
            or r in {"owner", "super admin"}
        )

    def _fetch_users(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        access_token = credentials.get("access_token")
        api_domain = (credentials.get("extra") or {}).get("api_domain") or DEFAULT_API_DOMAIN
        if not access_token:
            return []

        users: list[dict[str, Any]] = []
        page = 1
        while True:
            resp = httpx.get(
                f"{api_domain}/crm/v5/users",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                params={"type": "AllUsers", "page": page, "per_page": 200},
                timeout=30,
            )
            if resp.status_code == 204:
                break
            resp.raise_for_status()
            data = resp.json() or {}
            page_users = data.get("users") or []
            if not page_users:
                break
            for u in page_users:
                role = u.get("role") or {}
                role_name = role.get("name") if isinstance(role, dict) else None
                last_login = u.get("last_login_time")
                users.append({
                    "id": u.get("id"),
                    "email": u.get("email"),
                    "is_admin": self._is_admin(role_name),
                    "has_mfa": bool(u.get("two_factor_auth_enabled")),
                    "last_login_at": last_login,
                    "last_login": last_login,
                })
            info = data.get("info") or {}
            if not info.get("more_records"):
                break
            page += 1

        return users
