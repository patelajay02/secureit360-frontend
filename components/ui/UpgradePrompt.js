// components/ui/UpgradePrompt.js
// SecureIT360 — Upgrade prompt popup
// Shows when trial user tries to access locked scan engines

"use client";

import { useRouter } from "next/navigation";

export function UpgradePrompt({ onClose }) {
  const router = useRouter();

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 rounded-2xl p-8 w-full max-w-md border border-indigo-700">
        <div className="text-center">
          <div className="text-5xl mb-4">🔒</div>
          <h3 className="text-white font-bold text-xl mb-2">
            Unlock all 6 scan engines
          </h3>
          <p className="text-gray-400 text-sm mb-6">
            Your free trial includes 2 scan engines — Dark Web and Email Security.
            Upgrade to unlock all 6 engines and get complete cyber protection.
          </p>

          <div className="bg-gray-800 rounded-xl p-4 mb-6 text-left">
            <p className="text-gray-400 text-xs mb-3 font-medium">LOCKED ENGINES</p>
            <div className="space-y-2">
              {[
                "🌐 Network and firewall scan",
                "🔒 Website and SSL scan",
                "💻 Device vulnerability scan",
                "☁️ Cloud storage scan",
              ].map((engine, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-gray-500">
                  <span>🔒</span>
                  <span>{engine}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => router.push("/pricing")}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg"
            >
              See plans
            </button>
            <button
              onClick={onClose}
              className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg"
            >
              Maybe later
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}