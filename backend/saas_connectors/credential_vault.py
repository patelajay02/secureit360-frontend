"""Credential vault for the Universal SaaS Connector.

Uses Supabase-side pgcrypto (pgp_sym_encrypt/pgp_sym_decrypt) via two
SECURITY DEFINER RPCs so plaintext secrets never transit any path where
they could be logged:

    saas_store_connection(user_id, app_slug, app_name, connection_type,
                          plaintext_json, vault_key) -> uuid
    saas_load_credentials(connection_id, user_id, vault_key) -> jsonb

The vault_key comes from the SAAS_VAULT_KEY env var and is passed straight
to Postgres. Nothing in this module prints or returns raw plaintext outside
the two public helpers below.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from services.database import supabase_admin

REFRESH_WINDOW_SECONDS = 5 * 60  # refresh if expires within this window


def _vault_key() -> str:
    key = os.getenv("SAAS_VAULT_KEY")
    if not key:
        raise RuntimeError("SAAS_VAULT_KEY environment variable is not set")
    return key


def encrypt_credentials(plaintext_json: dict) -> bytes:
    """Encrypt a credential dict. Returns the raw ciphertext bytes.

    This helper is mostly used for unit testing the round-trip. In
    production paths prefer store_credentials() which performs the insert
    atomically on the database side.
    """
    resp = supabase_admin.rpc(
        "saas_encrypt",
        {"p_plaintext": json.dumps(plaintext_json), "p_key": _vault_key()},
    ).execute()
    value = resp.data
    if value is None:
        raise RuntimeError("saas_encrypt returned no data")
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def decrypt_credentials(encrypted: bytes) -> dict:
    """Decrypt ciphertext produced by encrypt_credentials back into a dict.

    Mirror of encrypt_credentials for tests; production code paths should
    use load_credentials() which performs the select atomically.
    """
    payload = encrypted.decode("utf-8") if isinstance(encrypted, (bytes, bytearray)) else encrypted
    resp = supabase_admin.rpc(
        "saas_decrypt",
        {"p_ciphertext": payload, "p_key": _vault_key()},
    ).execute()
    value = resp.data
    if value is None:
        raise RuntimeError("saas_decrypt returned no data")
    return json.loads(value)


def store_credentials(
    user_id: str,
    app_slug: str,
    app_name: str,
    connection_type: str,
    plaintext_credentials: dict,
) -> str:
    """Insert a saas_connections row with credentials encrypted at rest.

    Returns the new connection id. Plaintext never leaves this function —
    the RPC performs pgp_sym_encrypt inline inside the INSERT.
    """
    if connection_type not in ("oauth", "api_key"):
        raise ValueError("connection_type must be 'oauth' or 'api_key'")

    resp = supabase_admin.rpc(
        "saas_store_connection",
        {
            "p_user_id": user_id,
            "p_app_slug": app_slug,
            "p_app_name": app_name,
            "p_connection_type": connection_type,
            "p_plaintext_json": json.dumps(plaintext_credentials),
            "p_key": _vault_key(),
        },
    ).execute()
    new_id = resp.data
    if not new_id:
        raise RuntimeError("saas_store_connection returned no connection id")
    return new_id


def _parse_expires_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _update_encrypted(connection_id: str, user_id: str, plaintext: dict) -> None:
    """Re-encrypt and overwrite the stored credentials for a connection."""
    resp = supabase_admin.rpc(
        "saas_update_credentials",
        {
            "p_connection_id": connection_id,
            "p_user_id": user_id,
            "p_plaintext_json": json.dumps(plaintext),
            "p_key": _vault_key(),
        },
    ).execute()
    if not resp.data:
        raise RuntimeError("saas_update_credentials returned no rows")


def _maybe_refresh(connection_id: str, user_id: str, credentials: dict) -> dict:
    """If the access token is within REFRESH_WINDOW_SECONDS of expiring, call
    the provider's refresh_tokens() and persist the fresh credentials. Returns
    the (possibly refreshed) credentials dict.
    """
    expires_at = _parse_expires_at(credentials.get("expires_at"))
    if expires_at is None:
        return credentials

    if expires_at - datetime.now(timezone.utc) > timedelta(seconds=REFRESH_WINDOW_SECONDS):
        return credentials

    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        return credentials

    # Look up the provider slug for this connection. Lazy import avoids a
    # circular dependency at module load time.
    try:
        row = (
            supabase_admin.table("saas_connections")
            .select("app_slug")
            .eq("id", connection_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        app_slug = (row.data or {}).get("app_slug")
    except Exception:
        app_slug = None

    if not app_slug:
        return credentials

    from .providers import PROVIDER_REGISTRY  # local import: providers -> vault chain

    provider_cls = PROVIDER_REGISTRY.get(app_slug)
    if not provider_cls:
        return credentials

    try:
        provider = provider_cls()
        # Surface any flow-time context (e.g. Zoho accounts_server) from the
        # stored extras so refresh_tokens can reach the right data centre.
        extras = credentials.get("extra") or {}
        provider.flow_context = {
            "accounts_server": extras.get("accounts_server"),
        }
        refreshed = provider.refresh_tokens(refresh_token)
    except Exception as e:
        print(f"[SaaS vault] refresh_tokens failed for {app_slug}: {e}")
        return credentials

    merged = dict(credentials)
    for k in ("access_token", "refresh_token", "expires_at"):
        if refreshed.get(k):
            merged[k] = refreshed[k]
    if refreshed.get("tenant_id_or_org_id"):
        merged["tenant_id_or_org_id"] = refreshed["tenant_id_or_org_id"]
    refreshed_extra = refreshed.get("extra") or {}
    if refreshed_extra:
        merged_extra = dict(extras)
        merged_extra.update({k: v for k, v in refreshed_extra.items() if v is not None})
        merged["extra"] = merged_extra

    try:
        _update_encrypted(connection_id, user_id, merged)
    except Exception as e:
        print(f"[SaaS vault] failed to persist refreshed credentials for {app_slug}: {e}")
        return credentials

    return merged


def load_credentials(connection_id: str, user_id: str) -> dict:
    """Return the decrypted credentials dict for a connection owned by user_id.

    If the stored access token is within 5 minutes of expiring, the registered
    provider is asked to refresh it and the new credentials are re-encrypted
    before being returned.

    Raises PermissionError if the connection does not belong to user_id.
    Raises RuntimeError if decryption fails.
    """
    resp = supabase_admin.rpc(
        "saas_load_credentials",
        {
            "p_connection_id": connection_id,
            "p_user_id": user_id,
            "p_key": _vault_key(),
        },
    ).execute()
    data: Any = resp.data
    if data is None:
        raise PermissionError("Connection not found or not owned by this user")
    credentials = json.loads(data) if isinstance(data, str) else data
    return _maybe_refresh(connection_id, user_id, credentials)
