# backend/tests/test_tenant_independence.py
# Proves platform admins authenticate independently of tenant membership, and
# that zero active memberships is a handled outcome (friendly 409, not PGRST116).

import pytest
from fastapi import HTTPException

import middleware.auth_middleware as am


class _Resp:
    def __init__(self, data):
        self.data = data


class _Chain:
    """Chainable stub supporting select/eq/limit/maybe_single/execute."""
    def __init__(self, data, raise_=False):
        self._data = data
        self._raise = raise_

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def maybe_single(self, *a, **k): return self
    def execute(self):
        if self._raise:
            raise Exception("db down")
        return _Resp(self._data)


class _Admin:
    def __init__(self, data, raise_=False):
        self._data = data
        self._raise = raise_

    def table(self, name):
        return _Chain(self._data, self._raise)


# ── is_platform_admin ────────────────────────────────────────────────────────
def test_is_platform_admin_true(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin([{"user_id": "u1"}]))
    assert am.is_platform_admin("u1") is True


def test_is_platform_admin_false(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin([]))
    assert am.is_platform_admin("u1") is False


def test_is_platform_admin_fails_closed_on_error(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin(None, raise_=True))
    assert am.is_platform_admin("u1") is False


# ── resolve/require active membership (maybe_single, no PGRST116) ────────────
def test_resolve_active_membership_found(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin({"tenant_id": "t1", "role": "owner"}))
    assert am.resolve_active_membership("u1") == {"tenant_id": "t1", "role": "owner"}


def test_resolve_active_membership_none_is_normal(monkeypatch):
    # Zero rows -> None (a platform admin or unprovisioned account), not an error.
    monkeypatch.setattr(am, "supabase_admin", _Admin(None))
    assert am.resolve_active_membership("u1") is None


def test_require_active_membership_raises_friendly_409(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin(None))
    with pytest.raises(HTTPException) as e:
        am.require_active_membership("u1")
    assert e.value.status_code == 409
    assert e.value.detail == am.INCOMPLETE_SETUP_DETAIL
    assert "incomplete" in am.INCOMPLETE_SETUP_DETAIL.lower()


def test_require_active_membership_returns_row(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin({"tenant_id": "t1", "role": "member"}))
    assert am.require_active_membership("u1")["tenant_id"] == "t1"


def test_require_active_membership_custom_select_joins(monkeypatch):
    # Endpoints like /auth/invite request the joined tenant name.
    monkeypatch.setattr(am, "supabase_admin",
                        _Admin({"tenant_id": "t1", "role": "owner", "tenants": {"name": "Acme"}}))
    m = am.require_active_membership("u1", "tenant_id, role, tenants(name)")
    assert m["tenants"]["name"] == "Acme"


# ── get_owner_tenant_id (admin target-user lookup, maybe_single) ─────────────
def test_get_owner_tenant_id_found(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _Admin({"tenant_id": "t9"}))
    assert am.get_owner_tenant_id("target-user") == "t9"


def test_get_owner_tenant_id_none_when_not_an_owner(monkeypatch):
    # Zero rows -> None (a 404 at the call site), never PGRST116.
    monkeypatch.setattr(am, "supabase_admin", _Admin(None))
    assert am.get_owner_tenant_id("target-user") is None
