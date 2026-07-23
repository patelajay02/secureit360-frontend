// app/settings/security/page.js
// SecureIT360 — account security landing: MFA status, manage authenticators,
// regenerate recovery codes. Fallback-safe when MFA is not configured.

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { requireAuth, authFetch } from "../../../lib/auth";
import {
  isMfaConfigured,
  hydrateSession,
  listFactors,
  unenroll,
  generateRecoveryCodes,
} from "../../../lib/mfa";

export default function SecurityPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(true);
  const [factors, setFactors] = useState([]);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [roleLabel, setRoleLabel] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [newCodes, setNewCodes] = useState(null); // shown once after regeneration

  useEffect(() => {
    if (!requireAuth(router)) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    // Backend-authoritative: does this role require MFA?
    try {
      const res = await authFetch("/auth/security/mfa-status");
      if (res.ok) {
        const s = await res.json();
        setMfaRequired(!!s.mfa_required);
        setRoleLabel(s.role || "");
      }
    } catch { /* non-fatal */ }

    if (!isMfaConfigured()) { setAvailable(false); setLoading(false); return; }
    const ok = await hydrateSession();
    if (!ok) { setAvailable(false); setLoading(false); return; }
    try {
      const { totp } = await listFactors();
      setFactors(totp);
    } catch {
      setFactors([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove(factorId) {
    if (!confirm("Remove this authenticator? You will no longer be prompted for a code from it.")) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      await unenroll(factorId);
      setSuccess("Authenticator removed.");
      await load();
    } catch (e) {
      setError(e.message || "Could not remove authenticator.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate() {
    if (!confirm("Generate a new set of recovery codes? Your existing unused codes will stop working.")) return;
    setBusy(true); setError(""); setSuccess(""); setNewCodes(null);
    try {
      const codes = await generateRecoveryCodes();
      setNewCodes(codes);
    } catch (e) {
      setError(e.message || "Could not generate recovery codes.");
    } finally {
      setBusy(false);
    }
  }

  const hasFactor = factors.length > 0;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">
            SecureIT<span className="text-red-500">360</span>
            <span className="text-gray-400 font-normal text-base ml-3">Security</span>
          </h1>
          <a href="/settings" className="text-sm text-red-400 hover:text-red-300">Back to Settings</a>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">{error}</div>
        )}
        {success && (
          <div className="bg-green-900/30 border border-green-700 text-green-300 rounded-lg px-4 py-3 mb-6 text-sm">{success}</div>
        )}

        {loading ? (
          <div className="text-gray-500 text-sm">Loading...</div>
        ) : !available ? (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-2">Two-factor authentication</h2>
            <p className="text-gray-400 text-sm">
              MFA is not available in this environment yet. Your account is protected by your password.
              {mfaRequired && " Your role will require MFA once it is enabled."}
            </p>
          </div>
        ) : (
          <>
            {/* MFA card */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-lg font-semibold">Two-factor authentication (TOTP)</h2>
                  <p className="text-gray-400 text-sm mt-1">
                    Add a time-based one-time code from an authenticator app as a second factor when you sign in.
                  </p>
                </div>
                <span className={`text-xs font-medium px-3 py-1 rounded-full flex-shrink-0 ${
                  hasFactor
                    ? "bg-green-900/50 text-green-300 border border-green-800"
                    : "bg-gray-800 text-gray-400 border border-gray-700"
                }`}>
                  {hasFactor ? "Enabled" : "Not enabled"}
                </span>
              </div>

              {mfaRequired && !hasFactor && (
                <div className="bg-amber-900/20 border border-amber-800 text-amber-300 rounded-lg px-4 py-3 text-sm mb-4">
                  Your role{roleLabel ? ` (${roleLabel})` : ""} requires two-factor authentication. Please set it up to keep access to privileged actions.
                </div>
              )}

              {hasFactor ? (
                <div className="divide-y divide-gray-800 border-t border-gray-800">
                  {factors.map((f) => (
                    <div key={f.id} className="flex items-center justify-between py-3">
                      <div>
                        <div className="text-white text-sm font-medium">{f.friendly_name || "Authenticator app"}</div>
                        <div className="text-gray-500 text-xs">Added {f.created_at ? new Date(f.created_at).toLocaleDateString() : "—"}</div>
                      </div>
                      <button onClick={() => handleRemove(f.id)} disabled={busy}
                        className="text-red-400 hover:text-red-300 text-sm disabled:opacity-50">
                        Remove
                      </button>
                    </div>
                  ))}
                  <div className="pt-4">
                    <a href="/settings/security/mfa"
                      className="inline-block bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
                      Add another authenticator
                    </a>
                  </div>
                </div>
              ) : (
                <a href="/settings/security/mfa"
                  className="inline-block bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
                  Set up two-factor authentication
                </a>
              )}
            </div>

            {/* Recovery codes card */}
            {hasFactor && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h2 className="text-lg font-semibold mb-1">Recovery codes</h2>
                <p className="text-gray-400 text-sm mb-5">
                  Single-use codes to sign in if you lose access to your authenticator. Generating a new set invalidates any unused codes.
                </p>

                {newCodes && newCodes.length > 0 && (
                  <div className="mb-5">
                    <div className="grid grid-cols-2 gap-2 bg-gray-950 border border-gray-800 rounded-lg p-4 font-mono text-sm text-gray-200">
                      {newCodes.map((c) => (<div key={c} className="text-center py-1">{c}</div>))}
                    </div>
                    <p className="text-amber-300 text-xs mt-2">
                      Save these now — they will not be shown again.
                    </p>
                  </div>
                )}

                <button onClick={handleRegenerate} disabled={busy}
                  className="bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50">
                  {busy ? "Working..." : "Generate new recovery codes"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
