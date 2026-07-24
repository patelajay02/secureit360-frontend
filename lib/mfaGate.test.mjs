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
