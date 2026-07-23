# backend/services/password_policy.py
# SecureIT360 — modern password policy (NIST/OWASP-aligned).
#
# Primary controls are LENGTH and COMPROMISED-PASSWORD screening (see
# services/compromised_password.py), NOT composition rules. Long passphrases are
# encouraged; spaces are allowed. We do not force uppercase/number/symbol mixes.
#
# NOTE ON MAX LENGTH: Supabase Auth (GoTrue) hashes with bcrypt, which only
# considers the first 72 BYTES of a password. To avoid SILENTLY truncating a
# longer password (which would weaken it without the user knowing), we reject
# passwords longer than 72 bytes with a clear message rather than truncating.

import re

MIN_LENGTH = 14          # characters
MAX_BYTES = 72           # bcrypt effective limit; reject (not truncate) beyond this

# Small local pre-filter of very common passwords. The authoritative
# compromised-password check is the HIBP k-anonymity screen; this just gives a
# fast, offline rejection for the most obvious ones.
_COMMON = frozenset({
    "password", "password1", "password123", "passw0rd", "letmein", "welcome",
    "admin", "administrator", "qwerty", "qwertyuiop", "123456", "1234567",
    "12345678", "123456789", "1234567890", "111111", "000000", "iloveyou",
    "abc123", "monkey", "dragon", "sunshine", "princess", "football",
    "changeme", "secret", "trustno1", "master", "hello123", "welcome123",
    "passwordpassword", "aaaaaaaaaaaaaa", "qwertyuiopasdf", "securepassword",
})


class PasswordPolicyError(ValueError):
    """Raised when a candidate password fails the policy. The message is safe to
    show to the user (contains no breach specifics)."""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def validate_password(password: str, *, email: str = None, company_name: str = None) -> bool:
    """Validate a candidate password. Raises PasswordPolicyError on failure.

    Applied consistently at signup, invited-user setup, password reset, password
    change and admin-created-account activation.
    """
    if not isinstance(password, str):
        raise PasswordPolicyError("Please enter a password.")

    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_LENGTH} characters. A memorable passphrase works well."
        )

    if len(password.encode("utf-8")) > MAX_BYTES:
        raise PasswordPolicyError(
            f"Password is too long (limit {MAX_BYTES} bytes). Please shorten it slightly."
        )

    low = password.lower()

    # Must not contain the user's email address or its local part.
    if email:
        e = email.lower()
        local = e.split("@")[0]
        if e in low or (len(local) >= 3 and local in low):
            raise PasswordPolicyError("Password must not contain your email address.")

    # Must not be an obvious company-name variant (best-effort).
    if company_name:
        cn = _norm(company_name)
        if len(cn) >= 4 and cn in _norm(password):
            raise PasswordPolicyError("Password must not be based on your company name.")

    # Fast local common-password rejection.
    if low in _COMMON or _norm(password) in _COMMON:
        raise PasswordPolicyError(
            "This password is too common. Please choose a stronger, unique passphrase."
        )

    return True
