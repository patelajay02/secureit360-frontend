# backend/tests/test_rate_limit_recaptcha.py
import pytest
from fastapi import HTTPException

import services.rate_limit as rl
import services.recaptcha as rc


class _Exec:
    def __init__(self, data):
        self._d = data

    def execute(self):
        return type("R", (), {"data": self._d})()


class _Admin:
    def __init__(self, data, raise_=False):
        self._d = data
        self._raise = raise_

    def rpc(self, name, params):
        assert name == "rl_check"
        if self._raise:
            raise Exception("db down")
        return _Exec(self._d)


def test_rate_limit_allows(monkeypatch):
    monkeypatch.setattr(rl, "supabase_admin", _Admin(True))
    assert rl.check_rate_limit("b", 5, 60) is True


def test_rate_limit_throttles_and_raises_429(monkeypatch):
    monkeypatch.setattr(rl, "supabase_admin", _Admin(False))
    assert rl.check_rate_limit("b", 5, 60) is False
    with pytest.raises(HTTPException) as e:
        rl.enforce_rate_limit("b", 5, 60)
    assert e.value.status_code == 429


def test_rate_limit_handles_list_result(monkeypatch):
    monkeypatch.setattr(rl, "supabase_admin", _Admin([True]))
    assert rl.check_rate_limit("b", 5, 60) is True


def test_rate_limit_fails_open_on_infra_error(monkeypatch):
    # Availability: a limiter DB error must not lock everyone out.
    monkeypatch.setattr(rl, "supabase_admin", _Admin(None, raise_=True))
    assert rl.check_rate_limit("b", 5, 60) is True


# ── reCAPTCHA ────────────────────────────────────────────────────────────────
def test_recaptcha_skips_when_unconfigured(monkeypatch):
    monkeypatch.delenv("RECAPTCHA_SECRET_KEY", raising=False)
    assert rc.verify_recaptcha("tok") is True


def test_recaptcha_empty_token_fails_when_configured(monkeypatch):
    monkeypatch.setenv("RECAPTCHA_SECRET_KEY", "x")
    assert rc.verify_recaptcha("") is False


def test_recaptcha_success(monkeypatch):
    monkeypatch.setenv("RECAPTCHA_SECRET_KEY", "x")
    monkeypatch.setattr(rc.httpx, "post", lambda *a, **k: type("R", (), {"json": lambda self: {"success": True}})())
    assert rc.verify_recaptcha("tok") is True


def test_recaptcha_rejected(monkeypatch):
    monkeypatch.setenv("RECAPTCHA_SECRET_KEY", "x")
    monkeypatch.setattr(rc.httpx, "post", lambda *a, **k: type("R", (), {"json": lambda self: {"success": False}})())
    assert rc.verify_recaptcha("tok") is False


def test_recaptcha_fails_closed_on_error(monkeypatch):
    monkeypatch.setenv("RECAPTCHA_SECRET_KEY", "x")
    def boom(*a, **k):
        raise Exception("network")
    monkeypatch.setattr(rc.httpx, "post", boom)
    assert rc.verify_recaptcha("tok") is False
