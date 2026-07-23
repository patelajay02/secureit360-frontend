# backend/services/recovery_codes.py
# SecureIT360 — MFA recovery codes (application-managed; Supabase has no native
# recovery codes). Only salted hashes are stored; plaintext is returned to the
# user exactly once at generation and NEVER logged. One-time use. Regeneration
# invalidates the previous batch.

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from services.database import supabase_admin

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # unambiguous (no O/0/I/1)
_N_CODES = 10
_GROUP = 5
_GROUPS = 2  # code format: XXXXX-XXXXX


def _normalize(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch in _ALPHABET)


def _hash(normalized: str, salt: str) -> str:
    return hashlib.sha256((salt + normalized).encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return "-".join(
        "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP)) for _ in range(_GROUPS)
    )


def generate_recovery_codes(user_id: str) -> list:
    """Generate a fresh batch of 10 recovery codes for the user, invalidating any
    previous unused codes. Returns the PLAINTEXT codes ONCE (never stored)."""
    batch_id = str(uuid.uuid4())

    # Regeneration invalidates the old batch (delete unused; used ones are history).
    try:
        supabase_admin.table("mfa_recovery_codes")\
            .delete().eq("user_id", user_id).is_("used_at", "null").execute()
    except Exception as e:
        print(f"[recovery] could not clear old codes for user: {type(e).__name__}")

    codes = [_generate_code() for _ in range(_N_CODES)]
    rows = []
    for c in codes:
        salt = secrets.token_hex(16)
        rows.append({
            "user_id": user_id,
            "batch_id": batch_id,
            "code_hash": f"{salt}:{_hash(_normalize(c), salt)}",
        })
    supabase_admin.table("mfa_recovery_codes").insert(rows).execute()
    return codes  # plaintext, shown once


def verify_recovery_code(user_id: str, submitted: str) -> bool:
    """Verify + consume a recovery code (one-time). Returns True/False only —
    the caller must not disclose whether a code was structurally valid."""
    norm = _normalize(submitted)
    if not norm:
        return False
    try:
        res = supabase_admin.table("mfa_recovery_codes")\
            .select("id, code_hash, used_at").eq("user_id", user_id)\
            .is_("used_at", "null").execute()
    except Exception as e:
        print(f"[recovery] verify lookup failed: {type(e).__name__}")
        return False

    for row in (res.data or []):
        salt, _, expected = (row.get("code_hash") or "").partition(":")
        if salt and expected and secrets.compare_digest(_hash(norm, salt), expected):
            try:
                supabase_admin.table("mfa_recovery_codes")\
                    .update({"used_at": datetime.now(timezone.utc).isoformat()})\
                    .eq("id", row["id"]).execute()
            except Exception:
                pass
            return True
    return False
