"use client";

import { useEffect, useState } from "react";

// Three action buttons shown under every SaaS finding.
// Styling mirrors the dashboard's getFixButton (Auto / Voice guide /
// Get specialist) so Auto Fix / Voice Guide / Connect to Expert read
// identically across the two surfaces. Auto Fix stays disabled until a
// SaaS finding actually supports automated remediation.

type Finding = {
  check_id: string;
  severity: string;
  governance_statement: string;
  recommended_action: string;
  technical_detail?: string | null;
  app_name?: string;
};

export default function FindingActions({ finding }: { finding: Finding }) {
  const [voiceOpen, setVoiceOpen] = useState(false);

  return (
    <>
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <button
          type="button"
          disabled
          title="Automated fixing isn't available for this finding yet"
          className="text-xs px-2 py-1 rounded font-medium bg-gray-800 text-gray-500 cursor-not-allowed border border-gray-700"
        >
          Auto Fix
        </button>
        <button
          type="button"
          onClick={() => setVoiceOpen(true)}
          className="text-xs px-2 py-1 rounded font-medium bg-amber-900/50 text-amber-300 hover:bg-amber-900"
        >
          Voice Guide
        </button>
        <a
          href={`mailto:governance@secureit360.co?subject=${encodeURIComponent(
            `Expert help: ${finding.app_name || "SaaS"} — ${finding.check_id}`
          )}&body=${encodeURIComponent(finding.governance_statement)}`}
          className="text-xs px-2 py-1 rounded font-medium bg-red-900/50 text-red-300 hover:bg-red-900"
        >
          Connect to Expert
        </a>
      </div>
      {voiceOpen && (
        <VoiceGuideModal finding={finding} onClose={() => setVoiceOpen(false)} />
      )}
    </>
  );
}


function VoiceGuideModal({
  finding,
  onClose,
}: {
  finding: Finding;
  onClose: () => void;
}) {
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    // Safety: cancel any in-flight speech when the modal unmounts.
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const speak = (text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 0.95;
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utter);
  };

  const stop = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    setSpeaking(false);
  };

  const script =
    `${finding.governance_statement} ` +
    `Here is the recommended next step. ${finding.recommended_action}`;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-lg w-full">
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="text-white font-semibold text-lg">Voice guide</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <p className="text-gray-300 text-sm leading-relaxed mb-3">
          {finding.governance_statement}
        </p>
        <div className="rounded-lg border border-indigo-900/60 bg-indigo-900/20 px-4 py-3 mb-4">
          <p className="text-indigo-200 text-xs uppercase tracking-wide font-semibold mb-1">
            Recommended next step
          </p>
          <p className="text-indigo-100 text-sm">{finding.recommended_action}</p>
        </div>
        <div className="flex items-center gap-2">
          {speaking ? (
            <button
              onClick={stop}
              className="text-xs px-3 py-2 rounded-lg bg-amber-900/60 hover:bg-amber-900 text-amber-100 font-medium"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={() => speak(script)}
              className="text-xs px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium"
            >
              Read it aloud
            </button>
          )}
          <button
            onClick={onClose}
            className="text-xs px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 font-medium"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
