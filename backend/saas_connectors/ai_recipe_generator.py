"""AI-generated setup wizard recipes for long-tail SaaS apps.

When a director searches the catalog for an app that isn't in
saas_app_registry yet, the catalog page calls POST /saas/generate-recipe
which calls generate_recipe() below. We hit Claude with a tight prompt,
validate the JSON, and upsert the registry row with verified=false.

Philosophy: a broken recipe cached into the registry would poison every
future user who searches for the same app. So validation is strict — any
shape error short-circuits to None and the HTTP layer returns a friendly
"email us and we'll add it" message rather than writing bad data.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from services.database import supabase_admin


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048
TIMEOUT_SECONDS = 45

DEFAULT_CAPABILITIES = ["admin_ratio", "mfa_coverage", "dormant_users"]


SYSTEM_PROMPT = (
    "You are generating a setup wizard recipe JSON for SecureIT360, a "
    "security scanning tool that connects to third-party SaaS applications. "
    "Return ONLY valid JSON. No preamble. No markdown code fences. No "
    "commentary. No trailing text. Just the JSON object."
)


def _user_prompt(app_name: str) -> str:
    return (
        f"Generate a setup wizard recipe for connecting {app_name} to a "
        "third-party security scanning tool. The user is a non-technical "
        "SMB director. Return JSON with keys: app_slug (lowercased, "
        "hyphenated), app_name (original casing), steps (array). Each "
        "step has: title, instruction (plain English, no jargon), input "
        "(optional, for steps where the user enters something - has "
        "name/label/type/required/help). The final step must capture an "
        "API key. Generate 3-6 steps total. Include where to find the API "
        "key in the app's settings, what permissions to grant if "
        "applicable, and a final paste-the-key step."
    )


def _normalize_slug(raw: str) -> str:
    """Force a safe, predictable slug even if Claude returns something odd."""
    s = (raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:64]


def _extract_json(text: str) -> Any:
    """Parse JSON that may or may not be wrapped in markdown code fences."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        # Strip first fence line (```json or just ```)
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def _validate_recipe(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("app_slug"), str) or not data["app_slug"].strip():
        return False
    if not isinstance(data.get("app_name"), str) or not data["app_name"].strip():
        return False
    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) < 1:
        return False
    for step in steps:
        if not isinstance(step, dict):
            return False
        if not isinstance(step.get("title"), str) or not step["title"].strip():
            return False
        if not isinstance(step.get("instruction"), str) or not step["instruction"].strip():
            return False
        inp = step.get("input")
        if inp is not None:
            if not isinstance(inp, dict):
                return False
            if not isinstance(inp.get("name"), str) or not inp["name"].strip():
                return False
            if not isinstance(inp.get("label"), str) or not inp["label"].strip():
                return False
    # The final step must ask for a credential so we have something to store.
    final_input = steps[-1].get("input")
    if not isinstance(final_input, dict):
        return False
    return True


def _call_claude(app_name: str) -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[AI recipe] ANTHROPIC_API_KEY is not set")
        return None
    try:
        resp = httpx.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": _user_prompt(app_name)}],
            },
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        blocks = body.get("content") or []
        for block in blocks:
            if block.get("type") == "text":
                return block.get("text") or ""
        return None
    except Exception as e:
        print(f"[AI recipe] Claude call failed for '{app_name}': {e}")
        return None


def generate_recipe(app_name: str) -> dict | None:
    """Generate a wizard recipe for `app_name` and cache it in the registry.

    Returns the saved registry row on success, or None if anything — the
    Claude call, JSON parse, or schema validation — goes wrong. The
    caller should translate None into a user-facing "we couldn't
    auto-generate a guide" message.
    """
    app_name = (app_name or "").strip()
    if not app_name:
        return None

    target_slug = _normalize_slug(app_name)
    if not target_slug:
        return None

    # Idempotence + poisoning protection: if a verified entry already exists
    # for this slug, return it rather than overwriting with a fresh LLM call.
    try:
        existing = (
            supabase_admin.table("saas_app_registry")
            .select("*")
            .eq("slug", target_slug)
            .limit(1)
            .execute()
        )
        if existing.data and existing.data[0].get("verified"):
            return existing.data[0]
    except Exception:
        pass

    text = _call_claude(app_name)
    if not text:
        return None

    try:
        data = _extract_json(text)
    except Exception as e:
        print(f"[AI recipe] JSON parse failed for '{app_name}': {e}")
        return None

    if not _validate_recipe(data):
        print(f"[AI recipe] Recipe validation failed for '{app_name}'")
        return None

    # Force the slug to our normalized form even if Claude picked a
    # different one. Keeps URLs predictable and avoids collisions.
    data["app_slug"] = target_slug
    if not data.get("app_name"):
        data["app_name"] = app_name

    payload = {
        "slug": target_slug,
        "name": data["app_name"],
        "tier": "2_manual",
        "wizard_recipe": data,
        "generic_check_capabilities": DEFAULT_CAPABILITIES,
        "verified": False,
    }

    try:
        result = (
            supabase_admin.table("saas_app_registry")
            .upsert(payload, on_conflict="slug")
            .execute()
        )
        row = (result.data or [None])[0]
        return row
    except Exception as e:
        print(f"[AI recipe] Registry upsert failed for '{app_name}': {e}")
        return None
