// app/settings/security/mfa/page.js
// SecureIT360 — TOTP MFA enrollment wizard (native Supabase MFA).
// Steps: 1) scan QR / enter secret  2) verify 6-digit code  3) save recovery codes.

"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { requireAuth, setToken, setRefreshToken, setMfaGate, clearMfaGate, getMfaReturnTo } from "../../../../lib/auth";
import {
  mfaClientStatus,
  hydrateSession,
  beginEnrollment,
  verifyCode,
  getAAL,
  generateRecoveryCodes,
} from "../../../../lib/mfa";

// Explicit enrollment state machine (see error taxonomy in lib/mfaEnroll.js).
//   loading | configuration_error | authentication_error | connectivity_error
//   already_enrolled | scan (enrollment_ready) | verify | recovery
// "verification_error" is surfaced inline on the verify step via `error`.
export default function MfaEnrollPage() {
  const router = useRouter();
  const [step, setStep] = useState("loading");
  const [factorId, setFactorId] = useState(null);
  const [qrCode, setQrCode] = useState("");
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // Guards against a single mount enrolling twice (rapid re-renders / StrictMode
  // within one mount). Cross-mount duplicates are additionally prevented by the
  // list-first cleanup in beginEnrollment().
  const startedRef = useRef(false);

  async function init() {
    setError("");
    setStep("loading");

    // 1) Configuration — the ONLY genuine "MFA unavailable" case.
    const clientStatus = mfaClientStatus();
    if (clientStatus === "no-env") { setStep("configuration_error"); return; }
    if (clientStatus !== "ok") { return; } // "ssr" — effect re-runs client-side

    // 2) Session hydration (backend JWT -> Supabase session).
    let hydrated = false;
    try { hydrated = await hydrateSession(); } catch { hydrated = false; }
    if (!hydrated) { setStep("authentication_error"); return; }

    // 3) Idempotent enrollment: list first, never enroll while a factor exists.
    try {
      const res = await beginEnrollment();
      if (res.status === "already_enrolled") {
        // Verified factor exists. If a step-up is pending, move the gate to
        // "challenge" (keeps the guard and the challenge page consistent) and
        // redirect ONCE; otherwise it is simply already enabled.
        const { currentLevel, nextLevel } = await getAAL();
        if (nextLevel === "aal2" && currentLevel !== "aal2") {
          setMfaGate("challenge");
          router.replace("/mfa-challenge");
          return;
        }
        setStep("already_enrolled");
        return;
      }
      setFactorId(res.factorId);
      setQrCode(res.qrCode);
      setSecret(res.secret);
      setStep("scan");
    } catch (e) {
      // Map typed MfaError codes to distinct states — never collapse to "unavailable".
      if (e?.code === "configuration_error") setStep("configuration_error");
      else if (e?.code === "authentication_error") setStep("authentication_error");
      else setStep("connectivity_error"); // retryable
      setError(e?.message || "");
    }
  }

  function retry() {
    startedRef.current = true;
    init();
  }

  useEffect(() => {
    if (!requireAuth(router)) return;
    if (startedRef.current) return;
    startedRef.current = true;
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleVerify(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tokens = await verifyCode(factorId, code);
      // Factor verified — the session is now AAL2. Persist the upgraded tokens and
      // clear the mandatory-enrollment gate so protected pages open again.
      if (tokens.access_token) setToken(tokens.access_token);
      if (tokens.refresh_token) setRefreshToken(tokens.refresh_token);
      clearMfaGate();
      let codes = [];
      try { codes = await generateRecoveryCodes(); } catch { codes = []; }
      setRecoveryCodes(codes);
      setStep("recovery");
    } catch (e) {
      setError(e?.message || "That code was not correct. Please try again.");
      setCode("");
    } finally {
      setLoading(false);
    }
  }

  function copyRecoveryCodes() {
    try {
      navigator.clipboard.writeText(recoveryCodes.join("\n"));
      setSaved(true);
    } catch {
      setSaved(true);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">
            SecureIT<span className="text-red-500">360</span>
            <span className="text-gray-400 font-normal text-base ml-3">Set up two-factor authentication</span>
          </h1>
          <a href="/settings/security" className="text-sm text-red-400 hover:text-red-300">Back to Security</a>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Inline error banner only on interactive steps; dedicated error states
            render their own copy (never collapsing to a single message). */}
        {error && (step === "scan" || step === "verify") && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">{error}</div>
        )}

        {step === "loading" && <div className="text-gray-500 text-sm">Preparing enrollment...</div>}

        {/* configuration_error — the ONLY genuine "unavailable" state */}
        {step === "configuration_error" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-2">Two-factor authentication is unavailable</h2>
            <p className="text-gray-400 text-sm">
              MFA is not configured for this environment yet. Please contact your administrator.
            </p>
          </div>
        )}

        {/* authentication_error — session expired / not hydrated */}
        {step === "authentication_error" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-2">Please sign in again</h2>
            <p className="text-gray-400 text-sm mb-5">
              Your secure session has expired. Sign in again to set up two-factor authentication.
            </p>
            <a href="/login" className="inline-block bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
              Return to login
            </a>
          </div>
        )}

        {/* connectivity_error — transient; offer retry */}
        {step === "connectivity_error" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-2">We couldn't reach the authenticator service</h2>
            <p className="text-gray-400 text-sm mb-5">
              {error || "This is usually temporary. Please try again."}
            </p>
            <button onClick={retry}
              className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
              Retry
            </button>
          </div>
        )}

        {/* already_enrolled — a verified factor already exists */}
        {step === "already_enrolled" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-green-400 text-lg">✓</span>
              <h2 className="text-lg font-semibold">Two-factor authentication is already enabled</h2>
            </div>
            <p className="text-gray-400 text-sm mb-5">
              Your account already has a verified authenticator. You can manage it from the Security page.
            </p>
            <a href="/settings/security" className="inline-block bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
              Go to Security
            </a>
          </div>
        )}

        {step === "scan" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-1">Step 1 — Scan the QR code</h2>
            <p className="text-gray-400 text-sm mb-6">
              Open your authenticator app (Google Authenticator, Microsoft Authenticator, 1Password, Authy…) and scan this code.
            </p>
            <div className="flex flex-col items-center gap-5">
              {qrCode ? (
                // Supabase returns an SVG data URL
                <img src={qrCode} alt="TOTP QR code" className="w-52 h-52 bg-white rounded-lg p-2" />
              ) : (
                <div className="w-52 h-52 bg-gray-800 rounded-lg flex items-center justify-center text-gray-500 text-sm">
                  QR unavailable
                </div>
              )}
              <div className="w-full">
                <p className="text-gray-500 text-xs uppercase tracking-wide mb-2 text-center">Can't scan? Enter this key manually</p>
                <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 font-mono text-sm text-center break-all text-gray-200">
                  {secret || "—"}
                </div>
              </div>
            </div>
            <button
              onClick={() => { setStep("verify"); setError(""); }}
              className="w-full mt-6 bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              Next
            </button>
          </div>
        )}

        {step === "verify" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-1">Step 2 — Enter the 6-digit code</h2>
            <p className="text-gray-400 text-sm mb-6">
              Enter the current code shown in your authenticator app to confirm setup.
            </p>
            <form onSubmit={handleVerify} className="space-y-4">
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => { setCode(e.target.value.replace(/\D/g, "")); setError(""); }}
                required
                autoFocus
                placeholder="123456"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white tracking-[0.5em] text-center text-lg placeholder-gray-600 focus:outline-none focus:border-red-500"
              />
              <div className="flex gap-3">
                <button type="button" onClick={() => { setStep("scan"); setError(""); }}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg">
                  Back
                </button>
                <button type="submit" disabled={loading || code.length !== 6}
                  className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-red-900 text-white font-semibold py-3 rounded-lg">
                  {loading ? "Verifying..." : "Verify & enable"}
                </button>
              </div>
            </form>
          </div>
        )}

        {step === "recovery" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-green-400 text-lg">✓</span>
              <h2 className="text-lg font-semibold">Two-factor authentication enabled</h2>
            </div>
            <p className="text-gray-400 text-sm mb-5">
              Save these recovery codes somewhere safe. Each can be used <span className="text-gray-200">once</span> if you
              lose access to your authenticator. <span className="text-amber-300">They will not be shown again.</span>
            </p>
            {recoveryCodes.length > 0 ? (
              <>
                <div className="grid grid-cols-2 gap-2 bg-gray-950 border border-gray-800 rounded-lg p-4 font-mono text-sm text-gray-200">
                  {recoveryCodes.map((c) => (<div key={c} className="text-center py-1">{c}</div>))}
                </div>
                <div className="flex gap-3 mt-4">
                  <button onClick={copyRecoveryCodes}
                    className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg">
                    {saved ? "Copied ✓" : "Copy codes"}
                  </button>
                </div>
              </>
            ) : (
              <div className="bg-amber-900/20 border border-amber-800 text-amber-300 rounded-lg px-4 py-3 text-sm">
                Recovery codes could not be generated right now. You can generate them later from the Security page.
              </div>
            )}
            <label className="flex items-start gap-3 mt-5 cursor-pointer">
              <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)}
                className="mt-0.5 accent-red-500 w-4 h-4" />
              <span className="text-gray-300 text-sm">I have saved my recovery codes in a safe place.</span>
            </label>
            <button
              onClick={() => router.push(getMfaReturnTo() || "/settings/security")}
              disabled={recoveryCodes.length > 0 && !saved}
              className="w-full mt-5 bg-red-600 hover:bg-red-700 disabled:bg-red-900 disabled:opacity-60 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
