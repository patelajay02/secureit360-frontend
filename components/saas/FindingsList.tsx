"use client";

import FindingActions from "./FindingActions";
import SeverityBadge from "./SeverityBadge";

type Finding = {
  id: string;
  connection_id: string;
  check_id: string;
  severity: "critical" | "high" | "medium" | "low" | "info" | string;
  governance_statement: string;
  technical_detail?: string | null;
  recommended_action: string;
  regulation_refs?: string[];
  created_at: string;
  app_name?: string;
  app_slug?: string;
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;
const SEVERITY_HEADINGS: Record<string, string> = {
  critical: "Critical — act now",
  high: "High — act this week",
  medium: "Medium — schedule in",
  low: "Low — monitor",
  info: "Checks that passed",
};

export default function FindingsList({ findings }: { findings: Finding[] }) {
  if (!findings || findings.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
        <p className="text-white font-semibold mb-2">Nothing to report yet</p>
        <p className="text-gray-400 text-sm">
          Connect a tool above and run a scan. Any issues we find will show up
          here as a plain-English briefing you can hand to your director.
        </p>
      </div>
    );
  }

  const grouped: Record<string, Finding[]> = {};
  for (const f of findings) {
    const key = (f.severity || "info").toLowerCase();
    (grouped[key] ||= []).push(f);
  }

  return (
    <div className="space-y-6">
      {SEVERITY_ORDER.map((sev) => {
        const list = grouped[sev];
        if (!list || list.length === 0) return null;
        return (
          <div key={sev} className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <SeverityBadge severity={sev} />
              <h3 className="text-white font-semibold text-sm">
                {SEVERITY_HEADINGS[sev]}{" "}
                <span className="text-gray-500 font-normal">({list.length})</span>
              </h3>
            </div>
            <div className="space-y-4">
              {list.map((f) => (
                <div
                  key={f.id}
                  className="border-b border-gray-800 pb-4 last:border-0 last:pb-0"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      {f.app_name && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
                          {f.app_name}
                        </span>
                      )}
                      <span className="text-xs text-gray-500">
                        {new Date(f.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <p className="text-gray-200 text-sm leading-relaxed">
                    {f.governance_statement}
                  </p>
                  {f.recommended_action && (
                    <div className="mt-3 rounded-lg border border-indigo-900/60 bg-indigo-900/20 px-4 py-3">
                      <p className="text-indigo-200 text-xs uppercase tracking-wide font-semibold mb-1">
                        Recommended next step
                      </p>
                      <p className="text-indigo-100 text-sm">
                        {f.recommended_action}
                      </p>
                    </div>
                  )}
                  {f.regulation_refs && f.regulation_refs.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {f.regulation_refs.map((r, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400"
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  )}
                  <FindingActions finding={f} />
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
