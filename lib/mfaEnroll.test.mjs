// lib/mfaEnroll.test.mjs
// Idempotent TOTP enrollment + error taxonomy. Run:
//   node --test lib/mfaEnroll.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  decideEnrollAction, classifyClientConfig, supabaseErrorCode,
  beginEnrollmentWith as beginEnrollment, listAllFactorsWith as listAllFactors, MfaError,
} from "./mfaEnroll.js";

// ── pure decision ────────────────────────────────────────────────────────────
test("decideEnrollAction: no factors -> enroll", () => {
  assert.deepEqual(decideEnrollAction({ verified: [], unverified: [] }), { action: "enroll", staleIds: [] });
});
test("decideEnrollAction: unverified -> resume with stale ids", () => {
  const d = decideEnrollAction({ verified: [], unverified: [{ id: "a" }] });
  assert.equal(d.action, "resume");
  assert.deepEqual(d.staleIds, ["a"]);
});
test("decideEnrollAction: multiple unverified -> resume all", () => {
  const d = decideEnrollAction({ verified: [], unverified: [{ id: "a" }, { id: "b" }, { id: "c" }] });
  assert.deepEqual(d.staleIds, ["a", "b", "c"]);
});
test("decideEnrollAction: verified -> already_enrolled (no enroll)", () => {
  assert.equal(decideEnrollAction({ verified: [{ id: "v" }], unverified: [] }).action, "already_enrolled");
});
test("decideEnrollAction: verified takes precedence over unverified", () => {
  const d = decideEnrollAction({ verified: [{ id: "v" }], unverified: [{ id: "u" }] });
  assert.equal(d.action, "already_enrolled");
  assert.deepEqual(d.staleIds, []);
});

// ── config + error taxonomy ──────────────────────────────────────────────────
test("classifyClientConfig", () => {
  assert.equal(classifyClientConfig("https://x.supabase.co", "anon", true), "ok");
  assert.equal(classifyClientConfig("", "anon", true), "no-env");
  assert.equal(classifyClientConfig("https://x", "", true), "no-env");
  assert.equal(classifyClientConfig("https://x", "anon", false), "ssr");
});
test("supabaseErrorCode: auth vs connectivity (never configuration)", () => {
  assert.equal(supabaseErrorCode(401), "authentication_error");
  assert.equal(supabaseErrorCode(403), "authentication_error");
  assert.equal(supabaseErrorCode(500), "connectivity_error");
  assert.equal(supabaseErrorCode(undefined), "connectivity_error");
});

// ── fake Supabase client ─────────────────────────────────────────────────────
function fakeClient(opts = {}) {
  const { factors = [], listError = null, listThrows = null, enrollError = null, enrollThrows = null } = opts;
  const calls = { list: 0, enroll: 0, unenroll: [] };
  return {
    calls,
    auth: { mfa: {
      async listFactors() {
        calls.list++;
        if (listThrows) throw listThrows;
        if (listError) return { data: null, error: listError };
        return { data: { all: factors }, error: null };
      },
      async enroll() {
        calls.enroll++;
        if (enrollThrows) throw enrollThrows;
        if (enrollError) return { data: null, error: enrollError };
        return { data: { id: "new", totp: { qr_code: "data:image/svg+xml;base64,x", secret: "JBSWY3", uri: "otpauth://totp" } }, error: null };
      },
      async unenroll({ factorId }) {
        calls.unenroll.push(factorId);
        return { data: {}, error: null };
      },
    } },
  };
}
const f = (id, status) => ({ id, factor_type: "totp", status });

// ── beginEnrollment lifecycle ────────────────────────────────────────────────
test("no factors -> enrolls exactly once, no cleanup", async () => {
  const c = fakeClient({ factors: [] });
  const res = await beginEnrollment(c);
  assert.equal(res.status, "enrollment_ready");
  assert.equal(res.secret, "JBSWY3");
  assert.equal(c.calls.enroll, 1);
  assert.equal(c.calls.unenroll.length, 0);
});

test("one unverified factor -> unenroll stale then enroll once", async () => {
  const c = fakeClient({ factors: [f("stale-1", "unverified")] });
  const res = await beginEnrollment(c);
  assert.equal(res.status, "enrollment_ready");
  assert.deepEqual(c.calls.unenroll, ["stale-1"]);
  assert.equal(c.calls.enroll, 1);
});

test("multiple stale unverified -> clean all, then enroll once", async () => {
  const c = fakeClient({ factors: [f("s1", "unverified"), f("s2", "unverified"), f("s3", "unverified")] });
  const res = await beginEnrollment(c);
  assert.equal(res.status, "enrollment_ready");
  assert.deepEqual(c.calls.unenroll, ["s1", "s2", "s3"]);
  assert.equal(c.calls.enroll, 1);
});

test("verified factor -> already_enrolled, NEVER calls enroll", async () => {
  const c = fakeClient({ factors: [f("v", "verified")] });
  const res = await beginEnrollment(c);
  assert.equal(res.status, "already_enrolled");
  assert.equal(c.calls.enroll, 0);
  assert.equal(c.calls.unenroll.length, 0);
});

test("verified + leftover unverified -> already_enrolled, no enroll/cleanup", async () => {
  const c = fakeClient({ factors: [f("v", "verified"), f("u", "unverified")] });
  const res = await beginEnrollment(c);
  assert.equal(res.status, "already_enrolled");
  assert.equal(c.calls.enroll, 0);
});

test("listFactors 401 -> authentication_error", async () => {
  const c = fakeClient({ listError: { status: 401, message: "jwt expired" } });
  await assert.rejects(() => beginEnrollment(c), (e) => e instanceof MfaError && e.code === "authentication_error");
});

test("listFactors network throw -> connectivity_error", async () => {
  const c = fakeClient({ listThrows: new TypeError("fetch failed") });
  await assert.rejects(() => beginEnrollment(c), (e) => e instanceof MfaError && e.code === "connectivity_error");
});

test("duplicate-factor enroll error -> connectivity_error, NEVER configuration_error", async () => {
  // Even if a duplicate slips through, it must not read as "MFA unavailable".
  const c = fakeClient({
    factors: [],
    enrollError: { status: 422, message: "A factor with the friendly name 'Authenticator app' for this user already exists." },
  });
  await assert.rejects(() => beginEnrollment(c), (e) => {
    assert.ok(e instanceof MfaError);
    assert.equal(e.code, "connectivity_error");
    assert.notEqual(e.code, "configuration_error");
    return true;
  });
});

test("no client -> configuration_error", async () => {
  await assert.rejects(() => beginEnrollment(null), (e) => e instanceof MfaError && e.code === "configuration_error");
});

// Repeated mounts must not accumulate factors: a stateful client that persists
// factors across calls converges to exactly one after each enrollment.
function statefulClient() {
  const store = [];
  let seq = 0;
  const calls = { enroll: 0, unenroll: 0 };
  return {
    store, calls,
    auth: { mfa: {
      async listFactors() { return { data: { all: store.slice() }, error: null }; },
      async enroll() {
        calls.enroll++;
        const factor = f(`f${++seq}`, "unverified");
        store.push(factor);
        return { data: { id: factor.id, totp: { qr_code: "x", secret: "S", uri: "u" } }, error: null };
      },
      async unenroll({ factorId }) {
        calls.unenroll++;
        const i = store.findIndex((x) => x.id === factorId);
        if (i >= 0) store.splice(i, 1);
        return { data: {}, error: null };
      },
    } },
  };
}

test("repeated enrollment mounts do not create duplicate factors", async () => {
  const c = statefulClient();
  await beginEnrollment(c);            // creates f1 (unverified)
  assert.equal(c.store.length, 1);
  await beginEnrollment(c);            // sees f1 -> cleans it -> creates f2
  assert.equal(c.store.length, 1);     // still exactly one
  await beginEnrollment(c);            // sees f2 -> cleans it -> creates f3
  assert.equal(c.store.length, 1);
  assert.equal(c.calls.enroll, 3);
  assert.equal(c.calls.unenroll, 2);
});

// ── listAllFactors split ─────────────────────────────────────────────────────
test("listAllFactors splits verified vs unverified", async () => {
  const c = fakeClient({ factors: [f("v", "verified"), f("u1", "unverified"), f("u2", "unverified")] });
  const { verified, unverified } = await listAllFactors(c);
  assert.equal(verified.length, 1);
  assert.equal(unverified.length, 2);
});
