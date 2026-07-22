# backend/services/recaptcha.py
# SecureIT360 - Server-side reCAPTCHA verification.
#
# The frontend already collects a reCAPTCHA token at signup; this verifies it
# server-side. Trusted internal workers never call user-facing endpoints, so no
# worker exemption is needed here.

import os
import httpx

_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def verify_recaptcha(token: str, remote_ip: str = None) -> bool:
    """Verify a reCAPTCHA token with Google.

    - If RECAPTCHA_SECRET_KEY is not configured (dev/test), verification is
      skipped (fail-open) with a warning so local development is not blocked.
    - If it IS configured, a missing/invalid token or a verification error
      fails CLOSED (returns False).
    """
    secret = os.getenv("RECAPTCHA_SECRET_KEY")
    if not secret:
        print("[recaptcha] RECAPTCHA_SECRET_KEY not set - skipping verification (dev only)")
        return True
    if not token:
        return False
    try:
        resp = httpx.post(
            _VERIFY_URL,
            data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
            timeout=10,
        )
        data = resp.json()
        return bool(data.get("success"))
    except Exception as e:
        print(f"[recaptcha] verification error: {e}")
        return False
