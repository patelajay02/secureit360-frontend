"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import DashboardNavbar from "../../../components/ui/DashboardNavbar";
import { ToastProvider, useToast } from "../../../components/ui/Toast";
import { authFetch, getToken } from "../../../lib/auth";
import AppCatalog, { RegistryApp } from "../../../components/saas/AppCatalog";
import GuidedWizard, {
  WizardRecipe,
} from "../../../components/saas/GuidedWizard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function CatalogInner() {
  const router = useRouter();
  const { addToast } = useToast();
  const [apps, setApps] = useState<RegistryApp[]>([]);
  const [loading, setLoading] = useState(true);
  const [wizardApp, setWizardApp] = useState<RegistryApp | null>(null);
  const [wizardSubmitting, setWizardSubmitting] = useState(false);
  const [requestOpen, setRequestOpen] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
    }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // /saas/apps is public — no auth required
      const resp = await fetch(`${API_BASE}/saas/apps`);
      const data = await resp.json();
      setApps(data.apps || []);
    } catch (e: any) {
      addToast(e?.message || "Could not load the catalog", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConnect = async (app: RegistryApp) => {
    if (app.tier === "1_oauth") {
      try {
        const resp = await authFetch(`/saas/connect/oauth/${app.slug}`, {
          method: "POST",
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.detail || "Could not start the connection");
        }
        const data = await resp.json();
        if (!data.auth_url) {
          throw new Error("No sign-in link was returned");
        }
        window.location.href = data.auth_url;
      } catch (e: any) {
        addToast(e?.message || "Could not start the connection", "error");
      }
      return;
    }

    // Tier-2 manual
    if (app.wizard_recipe) {
      setWizardApp(app);
    } else {
      addToast(
        "This tool's guided setup isn't ready yet. Check back soon.",
        "warning"
      );
    }
  };

  const handleWizardSubmit = async (values: Record<string, string>) => {
    if (!wizardApp) return;
    setWizardSubmitting(true);
    try {
      const resp = await authFetch(`/saas/connect/manual/${wizardApp.slug}`, {
        method: "POST",
        body: JSON.stringify({ credentials: values }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "Connection failed");
      }
      router.push(`/saas/connections?connected=${wizardApp.slug}`);
    } catch (e: any) {
      addToast(e?.message || "Connection failed", "error");
    } finally {
      setWizardSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <DashboardNavbar />
      <div className="max-w-6xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-white">Add a tool</h1>
              <p className="text-gray-400 text-sm mt-1">
                Pick the business app you want us to keep an eye on.
              </p>
            </div>
            <Link
              href="/saas/connections"
              className="text-sm text-gray-400 hover:text-white"
            >
              ← Back to connections
            </Link>
          </div>

          {wizardApp ? (
            <GuidedWizard
              recipe={wizardApp.wizard_recipe as WizardRecipe}
              onCancel={() => setWizardApp(null)}
              onSubmit={handleWizardSubmit}
              submitting={wizardSubmitting}
            />
          ) : loading ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <p className="text-gray-400 text-sm">Loading the catalog…</p>
            </div>
          ) : (
            <AppCatalog
              apps={apps}
              onConnect={handleConnect}
              onRequestNewApp={() => setRequestOpen(true)}
            />
          )}

          {requestOpen && (
            <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-md w-full">
                <h3 className="text-white font-semibold mb-2">
                  Add a tool manually
                </h3>
                <p className="text-gray-400 text-sm mb-4">
                  Coming soon — Step 5 unlocks this. You&apos;ll be able to type
                  the name of any business tool and we&apos;ll build a guided
                  connection for you on the spot.
                </p>
                <button
                  onClick={() => setRequestOpen(false)}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-lg text-sm"
                >
                  Got it
                </button>
              </div>
            </div>
          )}
        </div>
    </main>
  );
}

export default function SaasCatalogPage() {
  return (
    <ToastProvider>
      <CatalogInner />
    </ToastProvider>
  );
}
