// lib/mfa.js
// SecureIT360 — thin wrappers over Supabase native TOTP MFA + AAL2 step-up.
//
// Every function is fallback-safe: if the browser Supabase client is not
// configured (env vars missing), the "status" helpers report "no MFA" so the
// existing password-only experience is unchanged. Enrollment/challenge helpers
// throw a clear error only when explicitly invoked without configuration.

import { getSupabase, isMfaConfigured, mfaClientStatus } from "./supabaseClient";
import { getToken, getRefreshToken, authFetch } from "./auth";
import { MfaError, beginEnrollmentWith, listAllFactorsWith } from "./mfaEnroll";

// Re-export so callers can import MFA config + helpers from a single module.
export { isMfaConfigured, mfaClientStatus, MfaError };

function requireClient() {
  const sb = getSupabase();
  if (!sb) throw new MfaError("configuration_error", "Multi-factor authentication is not available right now.");
  return sb;
}

// Hydrate the browser Supabase client from the backend-issued session tokens so
// MFA APIs operate on the current user. Returns false when MFA is unconfigured
// or no tokens exist (caller should treat this as "MFA unavailable").
export async function hydrateSession() {
  if (!isMfaConfigured()) return false;
  const access_token = getToken();
  const refresh_token = getRefreshToken();
  if (!access_token || !refresh_token) return false;
  const sb = getSupabase();
  const { error } = await sb.auth.setSession({ access_token, refresh_token });
  return !error;
}

// Hydrate a *fresh* pair of tokens (used right after backend login, before they
// are read back from storage by hydrateSession).
export async function hydrateSessionWith(access_token, refresh_token) {
  if (!isMfaConfigured()) return false;
  if (!access_token || !refresh_token) return false;
  const sb = getSupabase();
  const { error } = await sb.auth.setSession({ access_token, refresh_token });
  return !error;
}

// { currentLevel, nextLevel } — nextLevel === 'aal2' while currentLevel ===
// 'aal1' means the user has a verified factor and must step up.
export async function getAAL() {
  if (!isMfaConfigured()) return { currentLevel: null, nextLevel: null };
  const sb = getSupabase();
  const { data, error } = await sb.auth.mfa.getAuthenticatorAssuranceLevel();
  if (error) return { currentLevel: null, nextLevel: null };
  return data || { currentLevel: null, nextLevel: null };
}

// True when the current (already password-authenticated) session must complete
// an MFA challenge to reach aal2.
export async function needsChallenge() {
  const { currentLevel, nextLevel } = await getAAL();
  return currentLevel === "aal1" && nextLevel === "aal2";
}

export async function listFactors() {
  if (!isMfaConfigured()) return { totp: [], all: [] };
  const sb = getSupabase();
  const { data, error } = await sb.auth.mfa.listFactors();
  if (error) return { totp: [], all: [] };
  const totp = (data?.totp || []).filter((f) => f.status === "verified");
  return { totp, all: data?.all || [] };
}

export async function hasVerifiedFactor() {
  const { totp } = await listFactors();
  return totp.length > 0;
}

// Browser-default wrappers over the injectable enrollment core (lib/mfaEnroll.js).
// listAllFactors() exposes verified AND unverified TOTP factors (unlike
// listFactors(), which is verified-only) so enrollment can be idempotent.
export function listAllFactors(client = getSupabase()) {
  return listAllFactorsWith(client);
}

// Idempotent enrollment — see beginEnrollmentWith(). Never enrolls while a factor
// exists; cleans stale unverified factors first. Throws a typed MfaError.
export function beginEnrollment(client = getSupabase()) {
  return beginEnrollmentWith(client);
}

// Verify a 6-digit code against a factor (used both to finish enrollment and to
// step up an existing session). Returns the new access/refresh tokens so the
// caller can persist the upgraded (aal2) session.
export async function verifyCode(factorId, code) {
  const sb = requireClient();
  const ch = await sb.auth.mfa.challenge({ factorId });
  if (ch.error) throw new MfaError("verification_error", "We couldn't verify that code. Please try again.");
  const { data, error } = await sb.auth.mfa.verify({
    factorId,
    challengeId: ch.data.id,
    code: (code || "").trim(),
  });
  // Friendly, non-leaking message; a wrong/expired code is a verification_error.
  if (error) throw new MfaError("verification_error", "That code was not correct. Please try again.");
  return {
    access_token: data?.access_token || null,
    refresh_token: data?.refresh_token || null,
  };
}

export async function unenroll(factorId) {
  const sb = requireClient();
  const { error } = await sb.auth.mfa.unenroll({ factorId });
  if (error) throw new Error(error.message || "Could not remove that authenticator.");
  return true;
}

// Backend-authoritative post-login gate: "enroll" | "challenge" | "allow".
// Fallback-safe: any failure returns "allow" so login is never blocked by an
// MFA-status hiccup (the backend guard remains the hard enforcement).
export async function fetchMfaGate() {
  try {
    const res = await authFetch("/auth/security/mfa-status");
    if (!res.ok) return "allow";
    const data = await res.json();
    return data.gate || "allow";
  } catch {
    return "allow";
  }
}

// Ask the backend to generate a fresh batch of recovery codes (returned once).
export async function generateRecoveryCodes() {
  const res = await authFetch("/auth/security/recovery-codes", { method: "POST" });
  if (!res.ok) throw new Error("Could not generate recovery codes.");
  const data = await res.json();
  return data.codes || [];
}
