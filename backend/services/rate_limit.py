# backend/services/rate_limit.py
# SecureIT360 - Distributed rate limiting.
#
# State lives in Postgres (public.rate_limit_hits + rl_check), so the limit is
# SHARED across all Railway instances rather than held in per-process memory.
# See migration 20260722_phase0_rate_limiting.sql.

from fastapi import HTTPException, status
from services.database import supabase_admin


def check_rate_limit(bucket: str, limit: int, window_seconds: int) -> bool:
    """Return True if the request is allowed, False if it should be throttled.

    Fails OPEN on limiter-infrastructure errors (availability over strictness):
    a transient DB error must not lock every user out. The failure is logged.
    """
    try:
        res = supabase_admin.rpc("rl_check", {
            "p_bucket": bucket,
            "p_limit": limit,
            "p_window_seconds": window_seconds,
        }).execute()
        allowed = res.data
        if isinstance(allowed, list):
            allowed = allowed[0] if allowed else True
        return bool(allowed)
    except Exception as e:
        print(f"[rate_limit] rl_check failed for bucket={bucket}: {e}")
        return True


def enforce_rate_limit(bucket: str, limit: int, window_seconds: int):
    """Raise HTTP 429 if the bucket is over its limit."""
    if not check_rate_limit(bucket, limit, window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
        )
