// lib/mfaEnroll.js
// SecureIT360 — PURE, framework-free helpers for idempotent TOTP enrollment and
// error classification. No imports, no browser/Supabase APIs, so this is fully
// unit-testable with `node --test`. lib/mfa.js composes these with the live
// Supabase client; the enrollment page renders the resulting states.

// Decide what to do BEFORE ever calling enroll(), given the user's existing
// TOTP factors. Enterprise rule: never create a factor while one exists.
//   verified present   -> "already_enrolled" (do NOT enroll; go to challenge)
//   only unverified    -> "resume" (clean the stale factor(s), then enroll once)
//   none               -> "enroll"
export function decideEnrollAction({ verified = [], unverified = [] } = {}) {
  if (verified.length > 0) return { action: "already_enrolled", staleIds: [] };
  if (unverified.length > 0) {
    return { action: "resume", staleIds: unverified.map((f) => f.id).filter(Boolean) };
  }
  return { action: "enroll", staleIds: [] };
}

// Classify browser client configuration into a specific, honest state. Only
// "no-env" is a genuine "MFA unavailable" condition.
//   ok      -> client can be created
//   no-env  -> NEXT_PUBLIC_SUPABASE_URL / ANON_KEY missing (configuration error)
//   ssr     -> running on the server (no window) — transient, not an error
export function classifyClientConfig(url, anonKey, hasWindow) {
  if (!hasWindow) return "ssr";
  if (!url || !anonKey) return "no-env";
  return "ok";
}

// Map a Supabase/GoTrue error (or thrown network error) to one of our taxonomy
// codes. Auth/permission failures are distinct from connectivity failures, and
// NEITHER is a configuration failure — so a duplicate-factor or expired-session
// error can never surface as "MFA unavailable".
export function supabaseErrorCode(status) {
  if (status === 401 || status === 403) return "authentication_error";
  return "connectivity_error"; // transient/unknown -> retryable, never "unavailable"
}

// Typed MFA error carrying one taxonomy code so the UI can branch precisely.
export class MfaError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "MfaError";
    this.code = code;
  }
}

// Turn a Supabase/GoTrue error (object with .status) or thrown network error
// into a typed MfaError. NEVER classifies as configuration_error — a duplicate
// factor or expired session is not an "MFA unavailable" condition.
export function toMfaError(errorOrThrown) {
  const code = supabaseErrorCode(errorOrThrown?.status);
  const message =
    code === "authentication_error"
      ? "Your secure session has expired. Please sign in again."
      : "We couldn't reach the authenticator service. Please try again.";
  return new MfaError(code, message);
}

// Split a Supabase listFactors() result into verified vs unverified TOTP factors.
// Client is INJECTED so this is unit-testable with a fake. Throws a typed MfaError.
export async function listAllFactorsWith(client) {
  if (!client) throw new MfaError("configuration_error", "Multi-factor authentication is not available right now.");
  let data, error;
  try {
    ({ data, error } = await client.auth.mfa.listFactors());
  } catch (thrown) {
    throw toMfaError(thrown); // network throw -> connectivity_error
  }
  if (error) throw toMfaError(error);
  const totp = (data?.all || []).filter((f) => f.factor_type === "totp");
  return {
    verified: totp.filter((f) => f.status === "verified"),
    unverified: totp.filter((f) => f.status === "unverified"),
    all: data?.all || [],
  };
}

// Idempotent enrollment core (client injected). ALWAYS lists first and never
// enrolls while a factor exists:
//   verified present -> { status: "already_enrolled" }
//   only unverified  -> unenroll the stale factor(s), then enroll one fresh
//   none             -> enroll one fresh
// Supabase does not re-expose an existing secret, so cleaning + re-enrolling is
// the only safe "resume" and also prevents stale factors from accumulating.
export async function beginEnrollmentWith(client) {
  if (!client) throw new MfaError("configuration_error", "Multi-factor authentication is not available right now.");

  const { verified, unverified } = await listAllFactorsWith(client);
  const decision = decideEnrollAction({ verified, unverified });

  if (decision.action === "already_enrolled") return { status: "already_enrolled" };

  if (decision.action === "resume") {
    for (const factorId of decision.staleIds) {
      let error;
      try {
        ({ error } = await client.auth.mfa.unenroll({ factorId }));
      } catch (thrown) {
        throw toMfaError(thrown);
      }
      if (error) throw toMfaError(error);
    }
    if (decision.staleIds.length) {
      // Secure lifecycle log — the secret is NEVER logged.
      try { console.info(`[mfa] removed ${decision.staleIds.length} stale unverified factor(s) before re-enrollment`); } catch {}
    }
  }

  // No factor exists now — enroll exactly one. Omit friendlyName so GoTrue's
  // name-uniqueness constraint can never collide across attempts.
  let data, error;
  try {
    ({ data, error } = await client.auth.mfa.enroll({ factorType: "totp" }));
  } catch (thrown) {
    throw toMfaError(thrown);
  }
  if (error) throw toMfaError(error);
  return {
    status: "enrollment_ready",
    factorId: data.id,
    qrCode: data.totp?.qr_code || "",
    secret: data.totp?.secret || "",
    uri: data.totp?.uri || "",
  };
}
