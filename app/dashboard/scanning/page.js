// app/dashboard/scanning/page.js
// SecureIT360 — Scanning progress page
// Shows 6 engine progress while first scan runs

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authFetch, getToken } from "../../../lib/auth";

const engines = [
  { key: "darkweb", label: "Dark Web", description: "Checking for leaked passwords and emails" },
  { key: "email", label: "Email Security", description: "Checking DMARC, SPF and DKIM records" },
  { key: "network", label: "Network", description: "Scanning for open ports and exposed services" },
  { key: "website", label: "Website & SSL", description: "Checking certificates and security headers" },
  { key: "devices", label: "Devices", description: "Looking for unpatched software and vulnerabilities" },
  { key: "cloud", label: "Cloud Storage", description: "Checking for publicly exposed cloud files" },
];

function StatusIcon({ status }) {
  if (status === "complete") return <span className="text-green-400 text-xl">✓</span>;
  if (status === "running") return (
    <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
  );
  return <div className="w-5 h-5 rounded-full border-2 border-gray-600" />;
}

export default function ScanningPage() {
  const router = useRouter();
  const [statuses, setStatuses] = useState(
    Object.fromEntries(engines.map((e) => [e.key, "pending"]))
  );
  const [scanId, setScanId] = useState(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    // Get latest scan id from localStorage or start polling
    const id = localStorage.getItem("secureit360_scan_id");
    if (id) setScanId(id);
  }, []);

  useEffect(() => {
    if (!scanId) return;

    const interval = setInterval(async () => {
      try {
        const response = await authFetch(`/scans/${scanId}/status`);
        const data = await response.json();

        if (data.engine_statuses) {
          setStatuses(data.engine_statuses);
        }

        // If all complete redirect to dashboard
        const allDone = Object.values(data.engine_statuses || {}).every(
          (s) => s === "complete"
        );
        if (allDone || data.status === "complete") {
          clearInterval(interval);
          setTimeout(() => router.push("/dashboard"), 1000);
        }
      } catch (err) {
        console.error("Polling error", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [scanId]);

  // Simulate progress if no scan id yet
  useEffect(() => {
    if (scanId) return;

    let i = 0;
    const keys = engines.map((e) => e.key);

    const interval = setInterval(() => {
      if (i < keys.length) {
        setStatuses((prev) => ({ ...prev, [keys[i]]: "running" }));
        if (i > 0) {
          setStatuses((prev) => ({ ...prev, [keys[i - 1]]: "complete" }));
        }
        i++;
      } else {
        setStatuses((prev) => ({ ...prev, [keys[keys.length - 1]]: "complete" }));
        clearInterval(interval);
        setTimeout(() => router.push("/dashboard"), 1500);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [scanId]);

  const completed = Object.values(statuses).filter((s) => s === "complete").length;

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-white">
            SecureIT<span className="text-indigo-400">360</span>
          </h1>
          <p className="text-gray-400 mt-2">Running your first security scan</p>
          <p className="text-gray-500 text-sm mt-1">This takes about 60 seconds — please do not close this page</p>
        </div>

        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex justify-between text-sm text-gray-400 mb-2">
            <span>Scanning in progress</span>
            <span>{completed} of {engines.length} complete</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div
              className="bg-indigo-500 h-2 rounded-full transition-all duration-700"
              style={{ width: `${(completed / engines.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Engine list */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 divide-y divide-gray-800">
          {engines.map((engine) => (
            <div key={engine.key} className="flex items-center gap-4 px-6 py-4">
              <StatusIcon status={statuses[engine.key]} />
              <div className="flex-1">
                <div className="text-white font-medium">{engine.label}</div>
                <div className="text-gray-500 text-sm">{engine.description}</div>
              </div>
              <span className="text-xs text-gray-600 capitalize">{statuses[engine.key]}</span>
            </div>
          ))}
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          by Global Cyber Assurance — Complete cyber protection
        </p>
      </div>
    </div>
  );
}