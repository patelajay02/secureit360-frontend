// lib/mfaGate.js
// SecureIT360 — PURE, framework-free MFA gate logic. No imports, no browser
// APIs, so it is unit-testable with `node --test`. Both the login redirect and
// the global route guard consume these helpers; the backend mirrors the same
// truth table in middleware.auth_middleware.mfa_gate_decision (pytest-covered).

// Roles for which MFA is mandatory (decision D5): platform admins + tenant owners.
export function roleRequiresMfa(isPlatformAdmin, role) {
  return Boolean(isPlatformAdmin || role === "owner");
}

// Post-login decision. Mirrors the backend. Fails OPEN ("allow") when factor
// status is unknown so a transient error never locks a user out.
export function decideGate({ mfaConfigured, isPlatformAdmin, role, hasVerifiedFactor, aal }) {
  if (!mfaConfigured) return "allow";
  if (hasVerifiedFactor === null || hasVerifiedFactor === undefined) return "allow";
  if (roleRequiresMfa(isPlatformAdmin, role) && !hasVerifiedFactor) return "enroll";
  if (hasVerifiedFactor && aal !== "aal2") return "challenge";
  return "allow";
}

// Where each gate sends the user.
export const GATE_ROUTE = {
  enroll: "/settings/security/mfa",
  challenge: "/mfa-challenge",
};

// Public / setup routes always reachable (logout lands on "/"; password reset
// lives on /login). Never gate these — gating them would create a redirect loop.
const PUBLIC_PREFIXES = [
  "/login", "/register", "/signup", "/auth-confirm", "/verify-email",
  "/pricing", "/privacy", "/terms", "/cookie-policy",
];

function isPublic(pathname) {
  if (pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

// Is a path allowed to render while a gate is active?
export function isPathAllowedDuringGate(gate, pathname) {
  if (!gate || gate === "allow") return true;
  if (isPublic(pathname)) return true;                       // logout + password reset
  if (pathname.startsWith("/settings/security/mfa")) return true; // enrollment always reachable
  if (gate === "challenge") return pathname === "/mfa-challenge";
  return false; // gate === "enroll": only the enrollment path above is allowed
}

// The redirect target for the guard, or null when the current path is allowed
// (null => no redirect => no loop).
export function gateRedirectTarget(gate, pathname) {
  if (isPathAllowedDuringGate(gate, pathname)) return null;
  return GATE_ROUTE[gate] || null;
}
