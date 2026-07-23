# backend/tests/test_aal2.py
# Stage 1 AAL2 foundation: aal claim extraction, require_aal2 enforcement,
# and /auth/security/mfa-status role logic.

import base64
import json
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import middleware.auth_middleware as am
import routes.auth as auth_mod
from middleware.auth_middleware import get_security_context


def _make_token(aal):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64({'sub': 'u1', 'aal': aal})}.sig"


# ── aal extraction ───────────────────────────────────────────────────────────
def test_get_token_aal_reads_claim():
    assert am.get_token_aal(_make_token("aal2")) == "aal2"
    assert am.get_token_aal(_make_token("aal1")) == "aal1"


def test_get_token_aal_handles_garbage():
    assert am.get_token_aal("not-a-jwt") is None
    assert am.get_token_aal("") is None


# ── require_aal2 ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_require_aal2_allows_aal2():
    ctx = {"user_id": "u1", "aal": "aal2", "is_platform_admin": True}
    assert (await am.require_aal2(ctx))["aal"] == "aal2"


@pytest.mark.asyncio
async def test_require_aal2_denies_aal1():
    with pytest.raises(HTTPException) as e:
        await am.require_aal2({"user_id": "u1", "aal": "aal1", "is_platform_admin": True})
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_require_aal2_denies_missing_aal():
    with pytest.raises(HTTPException) as e:
        await am.require_aal2({"user_id": "u1", "aal": None, "is_platform_admin": False})
    assert e.value.status_code == 403


# ── mfa-status endpoint ──────────────────────────────────────────────────────
def _client(ctx, membership):
    app = FastAPI()
    app.include_router(auth_mod.router, prefix="/auth")
    app.dependency_overrides[get_security_context] = lambda: ctx
    return app, membership


def test_mfa_status_platform_admin_requires_mfa(monkeypatch):
    ctx = {"user_id": "admin-1", "aal": "aal1", "is_platform_admin": True}
    app, _ = _client(ctx, None)
    monkeypatch.setattr(auth_mod, "get_user_tenant_membership", lambda uid: None)
    body = TestClient(app).get("/auth/security/mfa-status").json()
    assert body["mfa_required"] is True
    assert body["is_platform_admin"] is True
    assert body["role"] == "platform_admin"
    assert body["is_aal2"] is False


def test_mfa_status_owner_requires_mfa(monkeypatch):
    ctx = {"user_id": "u2", "aal": "aal2", "is_platform_admin": False}
    app, _ = _client(ctx, {"tenant_id": "t1", "role": "owner"})
    monkeypatch.setattr(auth_mod, "get_user_tenant_membership",
                        lambda uid: {"tenant_id": "t1", "role": "owner"})
    body = TestClient(app).get("/auth/security/mfa-status").json()
    assert body["mfa_required"] is True
    assert body["role"] == "owner"
    assert body["is_aal2"] is True


def test_mfa_status_member_not_required(monkeypatch):
    ctx = {"user_id": "u3", "aal": "aal1", "is_platform_admin": False}
    app, _ = _client(ctx, {"tenant_id": "t1", "role": "member"})
    monkeypatch.setattr(auth_mod, "get_user_tenant_membership",
                        lambda uid: {"tenant_id": "t1", "role": "member"})
    body = TestClient(app).get("/auth/security/mfa-status").json()
    assert body["mfa_required"] is False
    assert body["role"] == "member"
