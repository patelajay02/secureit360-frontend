// lib/mfaGate.test.mjs
// Pure-logic tests for the MFA route gate. Run: node --test lib/mfaGate.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  roleRequiresMfa, decideGate, GATE_ROUTE,
  isPathAllowedDuringGate, gateRedirectTarget,
} from "./mfaGate.js";

test("roleRequiresMfa: platform admin and owner require MFA", () => {
  assert.equal(roleRequiresMfa(true, null), true);
  assert.equal(roleRequiresMfa(false, "owner"), true);
  assert.equal(roleRequiresMfa(false, "admin"), false);
  assert.equal(roleRequiresMfa(false, "member"), false);
});

test("decideGate: platform admin with no factor -> enroll -> /settings/security/mfa", () => {
  const g = decideGate({ mfaConfigured: true, isPlatformAdmin: true, role: "platform_admin", hasVerifiedFactor: false, aal: "aal1" });
  assert.equal(g, "enroll");
  assert.equal(GATE_ROUTE[g], "/settings/security/mfa");
});

test("decideGate: owner with no factor -> enroll -> /settings/security/mfa", () => {
  const g = decideGate({ mfaConfigured: true, isPlatformAdmin: false, role: "owner", hasVerifiedFactor: false, aal: "aal1" });
  assert.equal(g, "enroll");
  assert.equal(GATE_ROUTE[g], "/settings/security/mfa");
});

test("decideGate: verified factor + AAL1 -> challenge -> /mfa-challenge", () => {
  const g = decideGate({ mfaConfigured: true, isPlatformAdmin: false, role: "owner", hasVerifiedFactor: true, aal: "aal1" });
  assert.equal(g, "challenge");
  assert.equal(GATE_ROUTE[g], "/mfa-challenge");
});

test("decideGate: AAL2 -> allow", () => {
  assert.equal(decideGate({ mfaConfigured: true, isPlatformAdmin: true, role: "platform_admin", hasVerifiedFactor: true, aal: "aal2" }), "allow");
});

test("decideGate: member without MFA -> allow", () => {
  assert.equal(decideGate({ mfaConfigured: true, isPlatformAdmin: false, role: "member", hasVerifiedFactor: false, aal: "aal1" }), "allow");
});

test("decideGate: unknown factor status / unconfigured -> allow (fail open)", () => {
  assert.equal(decideGate({ mfaConfigured: true, isPlatformAdmin: true, role: "platform_admin", hasVerifiedFactor: null, aal: "aal1" }), "allow");
  assert.equal(decideGate({ mfaConfigured: false, isPlatformAdmin: true, role: "platform_admin", hasVerifiedFactor: false, aal: "aal1" }), "allow");
});

test("enroll gate: direct /admin (and other protected pages) are blocked", () => {
  for (const p of ["/admin", "/dashboard", "/dashboard/scanning", "/settings", "/saas/connections"]) {
    assert.equal(isPathAllowedDuringGate("enroll", p), false, p);
    assert.equal(gateRedirectTarget("enroll", p), "/settings/security/mfa", p);
  }
});

test("enroll gate: enrollment page is reachable (no redirect loop)", () => {
  assert.equal(isPathAllowedDuringGate("enroll", "/settings/security/mfa"), true);
  assert.equal(gateRedirectTarget("enroll", "/settings/security/mfa"), null); // null => no redirect
});

test("challenge gate: /mfa-challenge reachable, protected pages blocked", () => {
  assert.equal(gateRedirectTarget("challenge", "/mfa-challenge"), null);       // no loop
  assert.equal(gateRedirectTarget("challenge", "/admin"), "/mfa-challenge");
});

// Regression for the flicker loop: under the ENROLL gate, /mfa-challenge must be
// reachable so the enrollment page can hand an already-enrolled user to the
// challenge page without the guard bouncing them back.
test("enroll gate: /mfa-challenge is ALWAYS reachable (breaks enroll<->challenge loop)", () => {
  assert.equal(isPathAllowedDuringGate("enroll", "/mfa-challenge"), true);
  assert.equal(gateRedirectTarget("enroll", "/mfa-challenge"), null); // no redirect back
});

test("both MFA-flow routes reachable under EVERY gate (no self-redirect)", () => {
  for (const gate of ["enroll", "challenge"]) {
    assert.equal(gateRedirectTarget(gate, "/settings/security/mfa"), null, gate);
    assert.equal(gateRedirectTarget(gate, "/mfa-challenge"), null, gate);
  }
});

test("no mutual redirect loop between enrollment and challenge", () => {
  // Neither MFA route ever redirects to the other, under any gate.
  assert.equal(gateRedirectTarget("enroll", "/mfa-challenge"), null);
  assert.equal(gateRedirectTarget("challenge", "/settings/security/mfa"), null);
});

test("navigation to /admin while enrollment required redirects back exactly once", () => {
  assert.equal(gateRedirectTarget("enroll", "/admin"), "/settings/security/mfa");
  // ...and once on the enrollment page there is no further redirect (loop-free).
  assert.equal(gateRedirectTarget("enroll", "/settings/security/mfa"), null);
});

test("any gate: public + logout + password-reset routes are never blocked", () => {
  for (const p of ["/", "/login", "/register", "/signup", "/verify-email", "/auth-confirm"]) {
    assert.equal(gateRedirectTarget("enroll", p), null, p);
    assert.equal(gateRedirectTarget("challenge", p), null, p);
  }
});

test("no gate: everything allowed", () => {
  assert.equal(gateRedirectTarget("", "/admin"), null);
  assert.equal(gateRedirectTarget("allow", "/admin"), null);
});
