"use client";

import { useMemo, useState } from "react";

export type RegistryApp = {
  slug: string;
  name: string;
  logo_url?: string | null;
  tier: "1_oauth" | "2_manual" | string;
  verified: boolean;
  wizard_recipe?: any;
};

type Props = {
  apps: RegistryApp[];
  onConnect: (app: RegistryApp) => void;
  onGenerate: (appName: string) => void | Promise<void>;
  generating?: boolean;
  generateError?: string | null;
};

function TierBadge({ tier }: { tier: string }) {
  const oneClick = tier === "1_oauth";
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full ${
        oneClick
          ? "bg-green-900/40 text-green-300 border border-green-800/60"
          : "bg-amber-900/40 text-amber-300 border border-amber-800/60"
      }`}
    >
      {oneClick ? "One-click" : "Guided setup"}
    </span>
  );
}

function Initials({ name }: { name: string }) {
  const initials =
    name
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0])
      .join("")
      .toUpperCase() || "?";
  return (
    <div className="w-12 h-12 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-300 font-semibold">
      {initials}
    </div>
  );
}

export default function AppCatalog({
  apps,
  onConnect,
  onGenerate,
  generating,
  generateError,
}: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return apps;
    return apps.filter(
      (a) =>
        a.name.toLowerCase().includes(q) || a.slug.toLowerCase().includes(q)
    );
  }, [apps, query]);

  const trimmedQuery = query.trim();
  const showGenerate = trimmedQuery.length > 0 && filtered.length === 0;

  return (
    <div className="space-y-6">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for the tool you use…"
        className="w-full bg-gray-900 border border-gray-800 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500"
      />

      {showGenerate ? (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 sm:p-8">
          <p className="text-white font-semibold text-lg">
            Don&apos;t see{" "}
            <span className="text-indigo-400">{trimmedQuery}</span>?
          </p>
          <p className="text-gray-400 text-sm mt-2 mb-5">
            We can build a setup guide for {trimmedQuery} right now using AI.
            It takes about 10 seconds.
          </p>
          <button
            onClick={() => onGenerate(trimmedQuery)}
            disabled={generating}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-700 text-white font-semibold text-sm px-5 py-2.5 rounded-lg"
          >
            {generating ? "Generating your setup guide…" : "Generate setup guide"}
          </button>
          {generateError && (
            <p className="text-red-400 text-sm mt-4" role="alert">
              {generateError}
            </p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((app) => (
            <div
              key={app.slug}
              className="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex flex-col gap-4"
            >
              <div className="flex items-center gap-3">
                {app.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={app.logo_url}
                    alt=""
                    className="w-12 h-12 rounded-xl bg-gray-800 border border-gray-700 object-contain"
                  />
                ) : (
                  <Initials name={app.name} />
                )}
                <div className="min-w-0">
                  <p className="text-white font-semibold truncate">
                    {app.name}
                  </p>
                  <div className="mt-1">
                    <TierBadge tier={app.tier} />
                  </div>
                </div>
              </div>
              <button
                onClick={() => onConnect(app)}
                className="mt-auto w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm py-2.5 rounded-lg"
              >
                Connect
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
