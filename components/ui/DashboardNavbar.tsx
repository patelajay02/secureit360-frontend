"use client";

// Reusable copy of the navbar inlined at app/dashboard/page.tsx. Kept as a
// separate component so /saas/* pages can render exactly the same header
// without touching the dashboard page itself. Update the dashboard inline
// markup in lockstep with any changes here.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

function getInitials(name: string): string {
  if (!name) return "";
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .substring(0, 2);
}

export default function DashboardNavbar() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState<string>("");
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setCompanyName(localStorage.getItem("company_name") || "");
    setLogoUrl(localStorage.getItem("logo_url"));
  }, []);

  const handleLogout = () => {
    localStorage.clear();
    router.push("/");
  };

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">
          SecureIT<span className="text-red-500">360</span>
        </h1>
        <div className="hidden md:flex items-center gap-6">
          <a href="/dashboard" className="text-gray-400 hover:text-white text-sm">Dashboard</a>
          <a href="/dashboard/scanning" className="text-gray-400 hover:text-white text-sm">Run Scan</a>
          <a href="/saas/connections" className="text-gray-400 hover:text-white text-sm">SaaS Tools</a>
          <a href="/settings" className="text-gray-400 hover:text-white text-sm">Settings</a>
          <a href="/pricing" className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded-lg font-medium">Upgrade</a>
          <div className="flex items-center gap-2">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoUrl} alt={companyName} className="h-7 w-auto max-w-20 object-contain rounded" />
            ) : (
              <div className="w-7 h-7 rounded-full bg-red-900/50 flex items-center justify-center">
                <span className="text-red-300 text-xs font-bold">{getInitials(companyName)}</span>
              </div>
            )}
            <span className="text-gray-400 text-sm">{companyName}</span>
          </div>
          <button onClick={handleLogout} className="text-gray-400 hover:text-white text-sm">Sign out</button>
        </div>
        <button className="md:hidden text-gray-400 hover:text-white" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {mobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>
      {mobileMenuOpen && (
        <div className="md:hidden mt-4 flex flex-col gap-3 border-t border-gray-800 pt-4">
          <a href="/dashboard" className="text-gray-400 hover:text-white text-sm">Dashboard</a>
          <a href="/dashboard/scanning" className="text-gray-400 hover:text-white text-sm">Run Scan</a>
          <a href="/saas/connections" className="text-gray-400 hover:text-white text-sm">SaaS Tools</a>
          <a href="/settings" className="text-gray-400 hover:text-white text-sm">Settings</a>
          <a href="/pricing" className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded-lg font-medium w-fit">Upgrade</a>
          <div className="flex items-center gap-2">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoUrl} alt={companyName} className="h-7 w-auto max-w-20 object-contain rounded" />
            ) : (
              <div className="w-7 h-7 rounded-full bg-red-900/50 flex items-center justify-center">
                <span className="text-red-300 text-xs font-bold">{getInitials(companyName)}</span>
              </div>
            )}
            <span className="text-gray-400 text-sm">{companyName}</span>
          </div>
          <button onClick={handleLogout} className="text-gray-400 hover:text-white text-sm text-left">Sign out</button>
        </div>
      )}
    </nav>
  );
}
