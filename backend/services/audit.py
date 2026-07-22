# backend/services/audit.py
# SecureIT360 — Security audit logging for privileged actions.
#
# Writes a durable record of who did what, to which resource, from where, and
# whether it succeeded. Writes go through the service-role client into the
# audit_log table (see migration 20260721_phase0_security_foundation.sql).
#
# CONTRACT:
#   * Best-effort: a logging failure must NEVER break the underlying request.
#   * Never record secrets (tokens, passwords, keys) in `detail`. Callers are
#     responsible for passing only non-sensitive context.

from typing import Optional
from services.database import supabase_admin

# Keys that must never be persisted in the audit `detail` blob, in case a caller
# accidentally forwards a raw object. Defence in depth against secret leakage.
_FORBIDDEN_DETAIL_KEYS = {
    "password", "token", "access_token", "refresh_token", "authorization",
    "api_key", "apikey", "secret", "service_key", "key", "recaptcha_token",
}


def _scrub(detail: Optional[dict]) -> dict:
    if not detail:
        return {}
    safe = {}
    for k, v in detail.items():
        if k.lower() in _FORBIDDEN_DETAIL_KEYS:
            safe[k] = "[redacted]"
        else:
            safe[k] = v
    return safe


def log_audit(
    action: str,
    *,
    actor_user_id: Optional[str] = None,
    actor_tenant_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_tenant_id: Optional[str] = None,
    outcome: str = "success",
    ip: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Record a privileged action. Never raises."""
    try:
        supabase_admin.table("audit_log").insert({
            "actor_user_id": actor_user_id,
            "actor_tenant_id": actor_tenant_id,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id is not None else None,
            "target_tenant_id": target_tenant_id,
            "outcome": outcome,
            "ip": ip,
            "detail": _scrub(detail),
        }).execute()
    except Exception as e:  # pragma: no cover - logging must not break requests
        # Deliberately swallow. Print without secrets for diagnosis.
        print(f"[AUDIT] failed to write audit log for action={action} outcome={outcome}: {e}")
