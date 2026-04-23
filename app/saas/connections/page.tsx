"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import DashboardNavbar from "../../../components/ui/DashboardNavbar";
import { ToastProvider, useToast } from "../../../components/ui/Toast";
import { authFetch, getToken } from "../../../lib/auth";
import ConnectionsList, {
  Connection,
} from "../../../components/saas/ConnectionsList";
import FindingsList from "../../../components/saas/FindingsList";

type Finding = Parameters<typeof FindingsList>[0]["findings"][number];

function ConnectionsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { addToast } = useToast();

  const [connections, setConnections] = useState<Connection[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);

  // Redirect to login if unauthenticated
  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
    }
  }, [router]);

  // One-shot toasts from ?connected= / ?error=
  useEffect(() => {
    const connected = params.get("connected");
    const error = params.get("error");
    const app = params.get("app") || connected;
    if (connected) {
      addToast(`${prettySlug(connected)} connected successfully`, "success");
    }
    if (error) {
      addToast(
        `We couldn't finish connecting ${app ? prettySlug(app) : "that tool"}: ${error}`,
        "error"
      );
    }
    if (connected || error) {
      // Clean the URL so a refresh doesn't refire the toast
      const url = new URL(window.location.href);
      url.searchParams.delete("connected");
      url.searchParams.delete("error");
      url.searchParams.delete("app");
      window.history.replaceState({}, "", url.toString());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [connsResp, findsResp] = await Promise.all([
        authFetch("/saas/connections"),
        authFetch("/saas/findings"),
      ]);
      const connsJson = await connsResp.json();
      const findsJson = await findsResp.json();
      setConnections(connsJson.connections || []);
      setFindings(findsJson.findings || []);
    } catch (e: any) {
      addToast(e?.message || "Could not load your connections", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleScan = async (id: string) => {
    try {
      const resp = await authFetch(`/saas/scan/${id}`, { method: "POST" });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "Scan failed");
      }
      const data = await resp.json();
      const count = data.findings_count ?? 0;
      addToast(
        count === 0
          ? "Scan complete — nothing to worry about."
          : `Scan complete — ${count} thing${count === 1 ? "" : "s"} to review.`,
        "success"
      );
      await load();
    } catch (e: any) {
      addToast(e?.message || "Scan failed", "error");
    }
  };

  const handleDisconnect = async (id: string) => {
    try {
      const resp = await authFetch(`/saas/connections/${id}`, {
        method: "DELETE",
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "Could not disconnect");
      }
      addToast("Tool disconnected", "success");
      await load();
    } catch (e: any) {
      addToast(e?.message || "Could not disconnect", "error");
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <DashboardNavbar />
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
            <div>
              <h1 className="text-2xl font-bold text-white">Your business tools</h1>
              <p className="text-gray-400 text-sm mt-1">
                Hook up the apps you already use and we&apos;ll keep an eye on
                the director-level risks hiding inside them.
              </p>
            </div>
            <Link
              href="/saas/catalog"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm px-5 py-2.5 rounded-lg text-center"
            >
              Connect a tool
            </Link>
          </div>

          {loading ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <p className="text-gray-400 text-sm">Loading your tools…</p>
            </div>
          ) : (
            <ConnectionsList
              connections={connections}
              onScan={handleScan}
              onDisconnect={handleDisconnect}
            />
          )}

          <div className="mt-10">
            <h2 className="text-white text-lg font-semibold mb-4">
              What we&apos;re seeing across your tools
            </h2>
            {loading ? (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
                <p className="text-gray-400 text-sm">Loading findings…</p>
              </div>
            ) : (
              <FindingsList findings={findings as any} />
            )}
          </div>
        </div>
    </main>
  );
}

function prettySlug(slug: string): string {
  const cleaned = slug.replace(/[_-]+/g, " ").trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export default function SaasConnectionsPage() {
  return (
    <ToastProvider>
      <Suspense fallback={null}>
        <ConnectionsInner />
      </Suspense>
    </ToastProvider>
  );
}
