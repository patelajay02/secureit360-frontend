// components/ui/TrialBanner.js
// SecureIT360 — Trial countdown banner
// Shows at top of every page during free trial

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authFetch, getToken } from "../../lib/auth";

export function TrialBanner() {
  const router = useRouter();
  const [trialInfo, setTrialInfo] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchTrialInfo();
  }, []);

  async function fetchTrialInfo() {
    try {
      const res = await authFetch("/billing/subscription");
      const data = await res.json();

      if (data.status === "Trial") {
        const createdAt = new Date(data.created_at);
        const expiry = new Date(createdAt.getTime() + 7 * 24 * 60 * 60 * 1000);
        const now = new Date();
        const daysLeft = Math.max(0, Math.ceil((expiry - now) / (1000 * 60 * 60 * 24)));
        setTrialInfo({ daysLeft, expiry });
      }
    } catch {
      // Silently fail
    }
  }

  if (!trialInfo || dismissed) return null;

  const isUrgent = trialInfo.daysLeft <= 2;

  return (
    <div className={`w-full px-4 py-3 flex items-center justify-between gap-4 ${
      isUrgent ? "bg-red-900/80 border-b border-red-700" : "bg-amber-900/60 border-b border-amber-700"
    }`}>
      <div className="flex items-center gap-3">
        <span className="text-lg">{isUrgent ? "🚨" : "⏰"}</span>
        <p className="text-sm text-white">
          {trialInfo.daysLeft === 0 ? (
            <span><strong>Your free trial has expired.</strong> Subscribe now to continue scanning.</span>
          ) : (
            <span>
              <strong>{trialInfo.daysLeft} day{trialInfo.daysLeft !== 1 ? "s" : ""} left</strong> in your free trial.
              You are currently using 2 of 6 scan engines.
            </span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        <button
          onClick={() => router.push("/pricing")}
          className={`text-xs font-bold px-4 py-2 rounded-lg transition-colors ${
            isUrgent
              ? "bg-red-500 hover:bg-red-400 text-white"
              : "bg-amber-500 hover:bg-amber-400 text-white"
          }`}
        >
          Upgrade now
        </button>
        {!isUrgent && (
          <button
            onClick={() => setDismissed(true)}
            className="text-amber-300 hover:text-white text-xs"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}