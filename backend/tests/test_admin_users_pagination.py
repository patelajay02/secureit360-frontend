# backend/tests/test_admin_users_pagination.py
# Proves /auth/admin/users no longer performs per-owner Auth calls (N+1 removed),
# joins batched Auth pages correctly, handles missing emails, and supports
# pagination / search / status — with authorization unchanged.

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials

import routes.auth as auth_mod
import middleware.auth_middleware as am
from middleware.auth_middleware import require_platform_admin


# ── Fakes ────────────────────────────────────────────────────────────────────
class FakeUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email


class FakeAdminAuth:
    def __init__(self, pages):
        self.pages = pages  # list[list[FakeUser]]
        self.list_users_calls = 0
        self.get_user_by_id_calls = 0

    def list_users(self, page=1, per_page=200):
        self.list_users_calls += 1
        i = page - 1
        return self.pages[i] if 0 <= i < len(self.pages) else []

    def get_user_by_id(self, uid):  # must NOT be called by the new code
        self.get_user_by_id_calls += 1
        return FakeUser(uid, "SHOULD_NOT_BE_CALLED")


class FakeResp:
    def __init__(self, data, count):
        self.data = data
        self.count = count


class FakeTenantsQuery:
    def __init__(self, rows, total):
        self.rows = rows
        self.total = total
        self.select_cols = None
        self.select_kwargs = None
        self.eq_calls = []
        self.ilike_calls = []
        self.range_calls = []

    def select(self, cols, **kw):
        self.select_cols = cols
        self.select_kwargs = kw
        return self

    def eq(self, col, val):
        self.eq_calls.append((col, val))
        return self

    def ilike(self, col, pat):
        self.ilike_calls.append((col, pat))
        return self

    def order(self, col, desc=False):
        return self

    def range(self, a, b):
        self.range_calls.append((a, b))
        return self

    def execute(self):
        return FakeResp(self.rows, self.total)


class FakeSB:
    def __init__(self, tq, admin_auth):
        self._tq = tq
        self.auth = type("A", (), {"admin": admin_auth})()

    def table(self, name):
        assert name == "tenants"
        return self._tq


def _tenant(tid, owner_id, **over):
    row = {
        "id": tid, "name": over.get("name", f"Co-{tid}"), "country": "NZ",
        "status": over.get("status", "active"), "plan": "pro",
        "trial_ends_at": None, "created_at": "2026-01-01T00:00:00Z",
        "tenant_users": [{"user_id": owner_id, "role": "owner", "status": "active"}],
    }
    return row


def build(monkeypatch, rows, total, auth_pages):
    tq = FakeTenantsQuery(rows, total)
    aa = FakeAdminAuth(auth_pages)
    monkeypatch.setattr(auth_mod, "supabase_admin", FakeSB(tq, aa))
    monkeypatch.setattr(auth_mod, "log_audit", lambda *a, **k: None)
    app = FastAPI()
    app.include_router(auth_mod.router, prefix="/auth")
    app.dependency_overrides[require_platform_admin] = lambda: {"user_id": "admin-1"}
    return TestClient(app), tq, aa


# ── N+1 removed ──────────────────────────────────────────────────────────────
def test_one_page_triggers_no_per_tenant_auth_calls(monkeypatch):
    rows = [_tenant("t1", "o1"), _tenant("t2", "o2")]
    auth_pages = [[FakeUser("o1", "o1@x.com"), FakeUser("o2", "o2@x.com")]]
    client, tq, aa = build(monkeypatch, rows, 2, auth_pages)

    r = client.get("/auth/admin/users")
    assert r.status_code == 200
    body = r.json()
    assert aa.get_user_by_id_calls == 0            # <-- no N+1
    assert aa.list_users_calls == 1                # one batched call
    emails = {u["user_id"]: u["email"] for u in body["users"]}
    assert emails == {"o1": "o1@x.com", "o2": "o2@x.com"}
    # select() must be scoped (no "*") and request an exact count
    assert "*" not in tq.select_cols
    assert "tenant_users(user_id, role, status)" in tq.select_cols
    assert tq.select_kwargs.get("count") == "exact"


def test_multiple_auth_pages_are_joined(monkeypatch):
    rows = [_tenant("t1", "o200")]
    page1 = [FakeUser(f"x{i}", f"x{i}@x.com") for i in range(200)]  # full page, no owner
    page2 = [FakeUser("o200", "o200@x.com")]                         # owner on page 2
    client, tq, aa = build(monkeypatch, rows, 1, [page1, page2])

    r = client.get("/auth/admin/users")
    assert r.status_code == 200
    assert aa.list_users_calls == 2
    assert aa.get_user_by_id_calls == 0
    assert r.json()["users"][0]["email"] == "o200@x.com"


def test_missing_owner_email_is_safe(monkeypatch):
    rows = [_tenant("t1", "ghost")]
    client, tq, aa = build(monkeypatch, rows, 1, [[FakeUser("someone", "s@x.com")]])
    r = client.get("/auth/admin/users")
    assert r.status_code == 200
    u = r.json()["users"][0]
    assert u["email"] == ""          # blank, not an error
    assert u["user_id"] == "ghost"


# ── Pagination / search / status ─────────────────────────────────────────────
def test_pagination_range_and_totals(monkeypatch):
    rows = [_tenant("t1", "o1")]
    client, tq, aa = build(monkeypatch, rows, 25, [[FakeUser("o1", "o1@x.com")]])
    r = client.get("/auth/admin/users?page=2&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert tq.range_calls == [(10, 19)]
    assert body["page"] == 2 and body["page_size"] == 10
    assert body["total"] == 25 and body["total_pages"] == 3


def test_page_size_is_capped(monkeypatch):
    rows = [_tenant("t1", "o1")]
    client, tq, aa = build(monkeypatch, rows, 1, [[FakeUser("o1", "o1@x.com")]])
    r = client.get("/auth/admin/users?page_size=99999")
    assert r.json()["page_size"] == auth_mod.MAX_ADMIN_PAGE_SIZE


def test_search_applies_ilike(monkeypatch):
    rows = [_tenant("t1", "o1")]
    client, tq, aa = build(monkeypatch, rows, 1, [[FakeUser("o1", "o1@x.com")]])
    client.get("/auth/admin/users?search=acme")
    assert tq.ilike_calls == [("name", "%acme%")]


def test_status_filter_applies_eq(monkeypatch):
    rows = [_tenant("t1", "o1", status="trial")]
    client, tq, aa = build(monkeypatch, rows, 1, [[FakeUser("o1", "o1@x.com")]])
    client.get("/auth/admin/users?status=trial")
    assert ("status", "trial") in tq.eq_calls


def test_response_shape_compatible(monkeypatch):
    rows = [_tenant("t1", "o1")]
    client, tq, aa = build(monkeypatch, rows, 1, [[FakeUser("o1", "o1@x.com")]])
    body = client.get("/auth/admin/users").json()
    assert set(["users", "page", "page_size", "total", "total_pages"]).issubset(body)
    u = body["users"][0]
    for f in ("user_id", "email", "company_name", "country", "status", "plan",
              "trial_ends_at", "created_at", "tenant_id"):
        assert f in u


# ── Authorization unchanged ──────────────────────────────────────────────────
def _creds():
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")


def _make_sb(admin_rows):
    class Auth:
        def get_user(self, t):
            return type("U", (), {"user": type("u", (), {"id": "u1"})()})()

    class Chain:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return type("R", (), {"data": admin_rows})()

    class SB:
        auth = Auth()
        def table(self, n): return Chain()
    return SB()


@pytest.mark.asyncio
async def test_non_admin_is_denied(monkeypatch):
    monkeypatch.setattr(am, "supabase_admin", _make_sb([]))  # not in platform_admins
    monkeypatch.setattr("services.rate_limit.enforce_rate_limit", lambda *a, **k: None)
    with pytest.raises(HTTPException) as e:
        await require_platform_admin(_creds())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_tenant_less_platform_admin_is_allowed(monkeypatch):
    # A platform admin with NO tenant passes — require_platform_admin never looks
    # at tenant_users.
    monkeypatch.setattr(am, "supabase_admin", _make_sb([{"user_id": "u1"}]))
    monkeypatch.setattr("services.rate_limit.enforce_rate_limit", lambda *a, **k: None)
    result = await require_platform_admin(_creds())
    assert result["user_id"] == "u1"
