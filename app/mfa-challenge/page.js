// app/mfa-challenge/page.js
// SecureIT360 — AAL2 step-up challenge for users who have a verified TOTP factor
// but whose current session is only AAL1. Reached automatically after login (or
// by the global route guard). Offers a recovery-code fallback for a lost device.

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  getToken, setToken, setRefreshToken, clearMfaGate, getMfaReturnTo, authFetch, logout,
} from "../../lib/auth";
import { isMfaConfigured, hydrateSession, listFactors, verifyCode } from "../../lib/mfa";

export default function MfaChallengePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [available, setAvailable] = useState(true);
  const [factorId, setFactorId] = useState(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);
  const [recovery, setRecovery] = useState("");

  const dest = () => getMfaReturnTo() || "/dashboard";

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    (async () => {
      if (!isMfaConfigured()) {
        // No MFA in this environment — nothing to challenge; let them through.
        clearMfaGate();
        setAvailable(false);
        router.replace(dest());
        return;
      }
      const ok = await hydrateSession();
      if (!ok) { clearMfaGate(); router.replace(dest()); return; }
      try {
        const { totp } = await listFactors();
        if (totp.length === 0) {
          // No verified factor after all — clear the gate to avoid a loop.
          clearMfaGate();
          router.replace(dest());
          return;
        }
        setFactorId(totp[0].id);
        setReady(true);
      } catch {
        clearMfaGate();
        router.replace(dest());
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleVerify(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tokens = await verifyCode(factorId, code);
      if (tokens.access_token) setToken(tokens.access_token);   // now AAL2
      if (tokens.refresh_token) setRefreshToken(tokens.refresh_token);
      clearMfaGate();
      router.replace(dest());
    } catch (err) {
      setError(err.message || "That code was not correct. Please try again.");
      setCode("");
    } finally {
      setLoading(false);
    }
  }

  async function handleRecovery(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authFetch("/auth/security/recovery-codes/verify", {
        method: "POST",
        body: JSON.stringify({ code: recovery }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.verified) {
        // App-level access is restored (session remains AAL1 until the user
        // re-enrolls; recovery is a one-time break-glass for a lost device).
        clearMfaGate();
        router.replace("/settings/security");
      } else {
        setError("That recovery code was not valid. Please try again.");
        setRecovery("");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">
            SecureIT<span className="text-red-500">360</span>
          </h1>
        </div>
        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
          {!ready ? (
            <div className="text-gray-500 text-sm text-center">
              {available ? "Preparing verification..." : "Redirecting..."}
            </div>
          ) : !useRecovery ? (
            <>
              <h2 className="text-xl font-semibold text-white mb-2">Two-factor verification</h2>
              <p className="text-gray-400 text-sm mb-6">
                Enter the 6-digit code from your authenticator app to finish signing in.
              </p>
              {error && (
                <div className="bg-red-900/40 border border-red-500 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">{error}</div>
              )}
              <form onSubmit={handleVerify} className="space-y-4">
                <input
                  type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                  value={code} onChange={(e) => { setCode(e.target.value.replace(/\D/g, "")); setError(""); }}
                  required autoFocus placeholder="123456"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white tracking-[0.5em] text-center text-lg placeholder-gray-600 focus:outline-none focus:border-red-500"
                />
                <button type="submit" disabled={loading || code.length !== 6}
                  className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-900 text-white font-semibold py-3 rounded-lg transition-colors">
                  {loading ? "Verifying..." : "Verify"}
                </button>
              </form>
              <div className="flex items-center justify-between mt-6 text-sm">
                <button onClick={() => { setUseRecovery(true); setError(""); }}
                  className="text-red-400 hover:text-red-300">Use a recovery code</button>
                <button onClick={logout} className="text-gray-500 hover:text-gray-300">Log out</button>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-white mb-2">Enter a recovery code</h2>
              <p className="text-gray-400 text-sm mb-6">
                Use one of the single-use recovery codes you saved when setting up two-factor authentication.
              </p>
              {error && (
                <div className="bg-red-900/40 border border-red-500 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">{error}</div>
              )}
              <form onSubmit={handleRecovery} className="space-y-4">
                <input
                  type="text" value={recovery} onChange={(e) => { setRecovery(e.target.value); setError(""); }}
                  required autoFocus placeholder="XXXXX-XXXXX"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white text-center font-mono tracking-widest placeholder-gray-600 focus:outline-none focus:border-red-500"
                />
                <button type="submit" disabled={loading || !recovery.trim()}
                  className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-900 text-white font-semibold py-3 rounded-lg transition-colors">
                  {loading ? "Verifying..." : "Verify recovery code"}
                </button>
              </form>
              <div className="flex items-center justify-between mt-6 text-sm">
                <button onClick={() => { setUseRecovery(false); setError(""); }}
                  className="text-red-400 hover:text-red-300">Back to code</button>
                <button onClick={logout} className="text-gray-500 hover:text-gray-300">Log out</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
