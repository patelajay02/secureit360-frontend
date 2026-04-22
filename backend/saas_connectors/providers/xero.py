"""Xero Tier-1 OAuth provider.

Reads XERO_CLIENT_ID / XERO_CLIENT_SECRET from the environment and
exposes the OAuth 2.0 + PKCE authorization-code flow plus the Users
endpoint adapter for admin_ratio, mfa_coverage, and dormant_users.

PKCE flow
---------
build_auth_url generates a cryptographically random code_verifier and
stashes it in self.flow_context["code_verifier"]. The route layer copies
that verifier into the OAuth state cache so it survives the browser
round-trip, then re-hydrates flow_context on the callback side before
calling exchange_code.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .base import BaseProvider, register_provider


AUTH_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"
USERS_URL = "https://api.xero.com/api.xro/2.0/Users"
REDIRECT_URI = "https://secureit360-production.up.railway.app/saas/callback/xero"

SCOPES = (
    "offline_access openid profile email "
    "accounting.settings accounting.contacts.read accounting.reports.read"
)


def _pkce_verifier() -> str:
    # 43-128 chars per RFC 7636; 64 bytes → 86 URL-safe chars
    return secrets.token_urlsafe(64)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is not set")
    return value


def _iso_expires_at(expires_in: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()


@register_provider("xero")
class XeroProvider(BaseProvider):
    def build_auth_url(self, state: str) -> str:
        client_id = _env("XERO_CLIENT_ID")
        verifier = _pkce_verifier()
        self.flow_context["code_verifier"] = verifier
        params = {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
        return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        verifier = self.flow_context.get("code_verifier")
        if not verifier:
            raise RuntimeError("Missing PKCE code_verifier for Xero token exchange")

        client_id = _env("XERO_CLIENT_ID")
        client_secret = _env("XERO_CLIENT_SECRET")

        resp = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
            auth=(client_id, client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        td = resp.json()

        tenant_id = self._fetch_tenant_id(td["access_token"])

        return {
            "access_token": td["access_token"],
            "refresh_token": td.get("refresh_token"),
            "expires_at": _iso_expires_at(td.get("expires_in", 1800)),
            "tenant_id_or_org_id": tenant_id,
            "extra": {
                "id_token": td.get("id_token"),
                "scope": td.get("scope"),
                "token_type": td.get("token_type", "Bearer"),
            },
        }

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        client_id = _env("XERO_CLIENT_ID")
        client_secret = _env("XERO_CLIENT_SECRET")

        resp = httpx.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(client_id, client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        td = resp.json()

        # Xero rotates refresh tokens. Keep whichever side refuses to lie.
        new_refresh = td.get("refresh_token") or refresh_token
        new_tenant_id = None
        try:
            new_tenant_id = self._fetch_tenant_id(td["access_token"])
        except Exception:
            pass

        return {
            "access_token": td["access_token"],
            "refresh_token": new_refresh,
            "expires_at": _iso_expires_at(td.get("expires_in", 1800)),
            "tenant_id_or_org_id": new_tenant_id,
            "extra": {
                "id_token": td.get("id_token"),
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
    def _fetch_tenant_id(access_token: str) -> str | None:
        resp = httpx.get(
            CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json() or []
        if not data:
            return None
        return data[0].get("tenantId")

    @staticmethod
    def _is_admin(role: str | None, is_subscriber: bool) -> bool:
        if is_subscriber:
            return True
        if not role:
            return False
        r = role.upper()
        # Xero roles that carry admin-level access to org data
        return r in {"FINANCIALADVISER", "MANAGEDCLIENT", "ADMIN"} or "ADMIN" in r

    def _fetch_users(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        tenant_id = credentials.get("tenant_id_or_org_id")
        access_token = credentials.get("access_token")
        if not tenant_id or not access_token:
            return []

        resp = httpx.get(
            USERS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Xero-tenant-id": tenant_id,
                "Accept": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json() or {}

        normalized: list[dict[str, Any]] = []
        for u in data.get("Users", []) or []:
            role = u.get("OrganisationRole")
            is_subscriber = bool(u.get("IsSubscriber"))
            two_factor = u.get("TwoFactorAuthentication")
            # Xero's public Users endpoint does not currently expose a
            # last-login timestamp; UpdatedDateUTC is the closest proxy we
            # can offer. Treat None as "never logged in" if missing.
            last_login_at = u.get("UpdatedDateUTC")
            normalized.append({
                "id": u.get("UserID"),
                "email": u.get("EmailAddress"),
                "is_admin": self._is_admin(role, is_subscriber),
                "has_mfa": bool(two_factor) if two_factor is not None else False,
                "last_login_at": last_login_at,
                "last_login": last_login_at,
            })
        return normalized
