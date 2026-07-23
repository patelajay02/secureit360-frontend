# backend/services/compromised_password.py
# SecureIT360 — compromised-password screening via HIBP Pwned Passwords using
# k-ANONYMITY. We send ONLY the first 5 hex chars of the SHA-1 hash; the full
# password and full hash NEVER leave the server, and are NEVER logged.
#
# This is SEPARATE from the customer HIBP breach-monitoring feature (which uses
# the authenticated breached-domain API). This module is only for screening a
# candidate password at set-time.
#
# FAIL-OPEN: if the HIBP range API is unreachable/errors, we return False (do not
# block the user on an outage). This is a documented trade-off.

import hashlib
import httpx

_RANGE_URL = "https://api.pwnedpasswords.com/range/"
_TIMEOUT = 8.0


def is_compromised(password: str) -> bool:
    """Return True iff the password appears in HIBP Pwned Passwords.

    Never sends the plaintext or the full hash; only the 5-char SHA-1 prefix.
    Never logs password material. Fails open (returns False) on any error.
    """
    if not password:
        return False
    try:
        digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]
        resp = httpx.get(
            _RANGE_URL + prefix,
            headers={"Add-Padding": "true", "user-agent": "SecureIT360-pw-screen"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return False
        for line in resp.text.splitlines():
            candidate, _, _count = line.partition(":")
            if candidate.strip().upper() == suffix:
                return True
        return False
    except Exception as e:  # network/DNS/timeout — fail open, log without secrets
        print(f"[pw-screen] HIBP range check unavailable ({type(e).__name__}); allowing")
        return False
