# backend/tests/test_mfa_enrollment.py
# Mandatory-MFA enrollment gate: gate decision truth table, the backend
# enrollment guard on require_platform_admin (direct /admin bypass protection),
# verified-factor lookup parsing, and the mfa-status `gate` field.

import pytest
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import middleware.auth_middleware as am
import routes.auth as auth_mod
from middleware.auth_middleware import get_security_context


# ── gate decision truth table (mirrors lib/mfaGate.js) ───────────────────────
@pytest.mark.parametrize("is_admin,role,has_factor,aal,expected", [
    (True,  "platform_admin", False, "aal1", "enroll"),     # platform admin, no factor
    (False, "owner",          False, "aal1", "enroll"),     # owner, no factor
    (False, "owner",          True,  "aal1", "challenge"),  # privileged, factor, AAL1
    (True,  "platform_admin", True,  "aal2", "allow"),      # privileged, AAL2
    (False, "member",         False, "aal1", "allow"),      # member, no factor -> allowed
    (False, "member",         True,  "aal1", "challenge"),  # member opted in, must step up
    (True,  "platform_admin", None,  "aal1", "allow"),      # lookup unknown -> fail open
])
def test_mfa_gate_decision(is_admin, role, has_factor, aal, expected):
    assert am.mfa_gate_decision(is_admin, role, has_factor, aal) == expected


# ── verified-factor lookup parsing ───────────────────────────────────────────
def _fake_admin(factors=None, raise_exc=False):
    def list_factors(params):
        if raise_exc:
            raise RuntimeError("supabase down")
        return SimpleNamespace(factors=factors)
    mfa = SimpleNamespace(list_factors=list_factors)
    admin = SimpleNamespace(mfa=mfa)
    auth = SimpleNamespace(admin=admin)
    return SimpleNamespace(auth=auth)


def test_has_verified_factor_true(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin",
                        _fake_admin(factors=[SimpleNamespace(status="verified", factor_type="totp")]))
    assert am.user_has_verified_factor("u1") is True


def test_has_verified_factor_only_unverified(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin",
                        _fake_admin(factors=[SimpleNamespace(status="unverified", factor_type="totp")]))
    assert am.user_has_verified_factor("u1") is False


def test_has_verified_factor_none_on_error(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _fake_admin(raise_exc=True))
    assert am.user_has_verified_factor("u1") is None   # fail-open sentinel


# ── require_platform_admin enrollment guard ──────────────────────────────────
def _platform_admin_sb(is_admin=True):
    """Fake supabase_admin whose platform_admins lookup returns a row (or not)."""
    class Q:
        def select(self, *a): return self
        def eq(self, *a): return self
        def limit(self, *a): return self
        def execute(self):
            return SimpleNamespace(data=([{"user_id": "u1"}] if is_admin else []))
    class SB:
        def table(self, name):
            assert name == "platform_admins"
            return Q()
    return SB()


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setattr(am, "_verify_token", lambda creds: ("u1", "tok.aal1"))
    monkeypatch.setattr("services.rate_limit.enforce_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(am, "supabase_admin", _platform_admin_sb(is_admin=True))
    monkeypatch.delenv("AAL2_ENFORCEMENT", raising=False)          # step-up stays OFF
    monkeypatch.setenv("MFA_ENROLLMENT_REQUIRED", "on")            # enrollment guard ON
    return monkeypatch


@pytest.mark.asyncio
async def test_admin_blocked_without_factor(admin_env):
    # Direct /admin API access is blocked when the admin has no verified factor.
    admin_env.setattr(am, "user_has_verified_factor", lambda uid: False)
    with pytest.raises(HTTPException) as e:
        await am.require_platform_admin(credentials=None)
    assert e.value.status_code == 403
    assert isinstance(e.value.detail, dict)
    assert e.value.detail["code"] == "mfa_enrollment_required"


@pytest.mark.asyncio
async def test_admin_allowed_with_factor(admin_env):
    admin_env.setattr(am, "user_has_verified_factor", lambda uid: True)
    result = await am.require_platform_admin(credentials=None)
    assert result["user_id"] == "u1"


@pytest.mark.asyncio
async def test_admin_fail_open_on_unknown_factor(admin_env):
    # None (lookup failed) must NOT lock the admin out.
    admin_env.setattr(am, "user_has_verified_factor", lambda uid: None)
    result = await am.require_platform_admin(credentials=None)
    assert result["user_id"] == "u1"


@pytest.mark.asyncio
async def test_admin_guard_off_allows_without_factor(admin_env):
    admin_env.setenv("MFA_ENROLLMENT_REQUIRED", "off")
    admin_env.setattr(am, "user_has_verified_factor", lambda uid: False)
    result = await am.require_platform_admin(credentials=None)
    assert result["user_id"] == "u1"


def test_enrollment_guard_flag_default_on(monkeypatch):
    monkeypatch.delenv("MFA_ENROLLMENT_REQUIRED", raising=False)
    assert am.mfa_enrollment_guard_enabled() is True             # default ON (the fix)
    monkeypatch.setenv("MFA_ENROLLMENT_REQUIRED", "off")
    assert am.mfa_enrollment_guard_enabled() is False


# ── mfa-status returns the gate ──────────────────────────────────────────────
def _client(ctx):
    app = FastAPI()
    app.include_router(auth_mod.router, prefix="/auth")
    app.dependency_overrides[get_security_context] = lambda: ctx
    return TestClient(app)


def test_mfa_status_gate_enroll_for_admin_without_factor(monkeypatch):
    ctx = {"user_id": "admin-1", "aal": "aal1", "is_platform_admin": True}
    monkeypatch.setattr(auth_mod, "get_user_tenant_membership", lambda uid: None)
    monkeypatch.setattr(auth_mod, "user_has_verified_factor", lambda uid: False)
    body = _client(ctx).get("/auth/security/mfa-status").json()
    assert body["gate"] == "enroll"
    assert body["mfa_required"] is True
    assert body["has_verified_factor"] is False


def test_mfa_status_gate_allow_for_member(monkeypatch):
    ctx = {"user_id": "u3", "aal": "aal1", "is_platform_admin": False}
    monkeypatch.setattr(auth_mod, "get_user_tenant_membership",
                        lambda uid: {"tenant_id": "t1", "role": "member"})
    monkeypatch.setattr(auth_mod, "user_has_verified_factor", lambda uid: False)
    body = _client(ctx).get("/auth/security/mfa-status").json()
    assert body["gate"] == "allow"
    assert body["mfa_required"] is False


def test_mfa_status_gate_challenge_when_factor_but_aal1(monkeypatch):
    ctx = {"user_id": "u2", "aal": "aal1", "is_platform_admin": False}
    monkeypatch.setattr(auth_mod, "get_user_tenant_membership",
                        lambda uid: {"tenant_id": "t1", "role": "owner"})
    monkeypatch.setattr(auth_mod, "user_has_verified_factor", lambda uid: True)
    body = _client(ctx).get("/auth/security/mfa-status").json()
    assert body["gate"] == "challenge"
