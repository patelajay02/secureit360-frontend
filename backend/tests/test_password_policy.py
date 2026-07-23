# backend/tests/test_password_policy.py
import pytest
from services.password_policy import validate_password, PasswordPolicyError, MIN_LENGTH
from services import compromised_password as cp


# ── Password policy ──────────────────────────────────────────────────────────
def test_too_short_rejected():
    with pytest.raises(PasswordPolicyError):
        validate_password("short1!")


def test_minimum_length_boundary_accepted():
    assert validate_password("A" * MIN_LENGTH + "zz9q") is True  # >= 14


def test_long_passphrase_accepted_no_composition_required():
    # A long, all-lowercase passphrase with spaces — no upper/number/symbol needed.
    assert validate_password("correct horse battery staple mountain river") is True


def test_spaces_allowed():
    assert validate_password("a long passphrase here") is True


def test_over_72_bytes_rejected_not_truncated():
    with pytest.raises(PasswordPolicyError):
        validate_password("x" * 73)


def test_email_local_part_rejected():
    with pytest.raises(PasswordPolicyError):
        validate_password("ajaypatel-strongpass", email="ajaypatel@secureit360.co")


def test_full_email_rejected():
    with pytest.raises(PasswordPolicyError):
        validate_password("xx-ajay@secureit360.co-yy", email="ajay@secureit360.co")


def test_company_name_variant_rejected():
    with pytest.raises(PasswordPolicyError):
        validate_password("secureit360 is my pass", company_name="SecureIT360")


def test_common_password_rejected():
    with pytest.raises(PasswordPolicyError):
        validate_password("passwordpassword")


def test_strong_unique_passphrase_ok():
    assert validate_password("velvet-otter-lantern-42-breeze", email="jo@acme.io",
                             company_name="Acme") is True


# ── Compromised-password screening (k-anonymity; fail-open) ──────────────────
class _Resp:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text


def _sha1_suffix(pw):
    import hashlib
    return hashlib.sha1(pw.encode()).hexdigest().upper()[5:]


def test_compromised_true_when_suffix_present(monkeypatch):
    pw = "hunter2hunter2"
    suffix = _sha1_suffix(pw)
    captured = {}

    def fake_get(url, **kw):
        captured["url"] = url
        return _Resp(200, f"{suffix}:42\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:1")

    monkeypatch.setattr(cp.httpx, "get", fake_get)
    assert cp.is_compromised(pw) is True
    # Only the 5-char prefix is sent — never the full hash/plaintext.
    assert captured["url"].endswith(__import__("hashlib").sha1(pw.encode()).hexdigest().upper()[:5])
    assert pw not in captured["url"]


def test_not_compromised_when_absent(monkeypatch):
    monkeypatch.setattr(cp.httpx, "get", lambda url, **kw: _Resp(200, "DEADBEEF:1\nCAFEBABE:2"))
    assert cp.is_compromised("velvet-otter-lantern-42-breeze") is False


def test_fails_open_on_non_200(monkeypatch):
    monkeypatch.setattr(cp.httpx, "get", lambda url, **kw: _Resp(500, ""))
    assert cp.is_compromised("anything-long-enough") is False


def test_fails_open_on_exception(monkeypatch):
    def boom(url, **kw):
        raise Exception("network down")
    monkeypatch.setattr(cp.httpx, "get", boom)
    assert cp.is_compromised("anything-long-enough") is False


def test_empty_password_not_compromised():
    assert cp.is_compromised("") is False
