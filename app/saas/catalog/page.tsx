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
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

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

  const handleGenerate = async (appName: string) => {
    setGenerating(true);
    setGenerateError(null);
    try {
      const resp = await authFetch(`/saas/generate-recipe`, {
        method: "POST",
        body: JSON.stringify({ app_name: appName }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(
          data.detail ||
            `We couldn't auto-generate a guide for ${appName}. Please email governance@secureit360.co.`
        );
      }
      // `data` is the saved saas_app_registry row. Drop it into wizard
      // state directly and drop it into our local catalog too.
      setApps((prev) => {
        const existing = prev.some((a) => a.slug === data.slug);
        return existing
          ? prev.map((a) => (a.slug === data.slug ? data : a))
          : [...prev, data];
      });
      if (data.wizard_recipe) {
        setWizardApp(data as RegistryApp);
      } else {
        throw new Error("The generated guide was empty. Please try again.");
      }
    } catch (e: any) {
      setGenerateError(e?.message || "Something went wrong. Please try again.");
    } finally {
      setGenerating(false);
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
            <>
              {wizardApp.verified === false && (
                <div className="mb-4 rounded-xl border border-amber-900/60 bg-amber-900/20 px-4 py-3 text-amber-100 text-sm">
                  <span className="font-semibold">This setup guide is in beta</span>
                  {" — let us know if any steps don't match what you see in "}
                  <span className="text-amber-200 font-medium">{wizardApp.name}</span>
                  {". Email feedback to "}
                  <a
                    href="mailto:governance@secureit360.co"
                    className="underline hover:text-white"
                  >
                    governance@secureit360.co
                  </a>
                  .
                </div>
              )}
              <GuidedWizard
                recipe={wizardApp.wizard_recipe as WizardRecipe}
                onCancel={() => setWizardApp(null)}
                onSubmit={handleWizardSubmit}
                submitting={wizardSubmitting}
              />
            </>
          ) : loading ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <p className="text-gray-400 text-sm">Loading the catalog…</p>
            </div>
          ) : (
            <AppCatalog
              apps={apps}
              onConnect={handleConnect}
              onGenerate={handleGenerate}
              generating={generating}
              generateError={generateError}
            />
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
