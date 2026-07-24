// lib/mfa.js
// SecureIT360 — thin wrappers over Supabase native TOTP MFA + AAL2 step-up.
//
// Every function is fallback-safe: if the browser Supabase client is not
// configured (env vars missing), the "status" helpers report "no MFA" so the
// existing password-only experience is unchanged. Enrollment/challenge helpers
// throw a clear error only when explicitly invoked without configuration.

import { getSupabase, isMfaConfigured } from "./supabaseClient";
import { getToken, getRefreshToken, authFetch } from "./auth";

// Re-export so callers can import MFA config + helpers from a single module.
export { isMfaConfigured };

function requireClient() {
  const sb = getSupabase();
  if (!sb) throw new Error("Multi-factor authentication is not available right now.");
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

// Begin TOTP enrollment. Returns { factorId, qrCode(svg dataurl), secret, uri }.
export async function startEnrollment(friendlyName) {
  const sb = requireClient();
  const opts = { factorType: "totp" };
  if (friendlyName) opts.friendlyName = friendlyName;
  const { data, error } = await sb.auth.mfa.enroll(opts);
  if (error) throw new Error(error.message || "Could not start MFA enrollment.");
  return {
    factorId: data.id,
    qrCode: data.totp?.qr_code || "",
    secret: data.totp?.secret || "",
    uri: data.totp?.uri || "",
  };
}

// Verify a 6-digit code against a factor (used both to finish enrollment and to
// step up an existing session). Returns the new access/refresh tokens so the
// caller can persist the upgraded (aal2) session.
export async function verifyCode(factorId, code) {
  const sb = requireClient();
  const ch = await sb.auth.mfa.challenge({ factorId });
  if (ch.error) throw new Error(ch.error.message || "Could not start verification.");
  const { data, error } = await sb.auth.mfa.verify({
    factorId,
    challengeId: ch.data.id,
    code: (code || "").trim(),
  });
  if (error) throw new Error(error.message || "That code was not correct. Please try again.");
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
