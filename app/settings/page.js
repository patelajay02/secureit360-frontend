// app/settings/page.js
// SecureIT360 - Settings page
// Tabs: Profile, Team, Domains, Billing

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authFetch, requireAuth, getToken } from "../../lib/auth";

const TRIAL_DAYS = 7;

const COUNTRY_DEFAULT_FRAMEWORKS = {
  NZ: ["NZ Privacy Act 2020", "ISO 27001", "ASD Essential Eight"],
  AU: ["Australian Privacy Act 1988", "ISO 27001", "ASD Essential Eight"],
  IN: ["DPDP Act 2023", "RBI Guidelines", "CERT-In", "ISO 27001"],
  UAE: ["UAE PDPL 2021", "DIFC Data Protection Law", "ADGM", "ISO 27001"],
  AE:  ["UAE PDPL 2021", "DIFC Data Protection Law", "ADGM", "ISO 27001"],
};

const OPTIONAL_FRAMEWORKS = [
  { id: "GDPR",    label: "GDPR (EU)",            desc: "EU General Data Protection Regulation" },
  { id: "HIPAA",   label: "HIPAA (US Healthcare)", desc: "Health Insurance Portability and Accountability Act" },
  { id: "PCI-DSS", label: "PCI-DSS (Payment Card)", desc: "Payment Card Industry Data Security Standard" },
  { id: "SOC 2",   label: "SOC 2",                 desc: "Service Organization Control 2" },
  { id: "NIST CSF",label: "NIST CSF",              desc: "NIST Cybersecurity Framework" },
  { id: "ISO 27001",label: "ISO 27001",            desc: "International Information Security Standard" },
];

const AZURE_SCOPES = [
  "User.Read.All",
  "UserAuthenticationMethod.Read.All",
  "AuditLog.Read.All",
  "Directory.Read.All",
  "Sites.Read.All",
  "offline_access",
].join(" ");

function getTrialExpiry(createdAt) {
  const created = new Date(createdAt);
  const expiry = new Date(created.getTime() + TRIAL_DAYS * 24 * 60 * 60 * 1000);
  return expiry;
}

function daysLeft(expiryDate) {
  const now = new Date();
  const diff = expiryDate - now;
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("profile");
  const [users, setUsers] = useState([]);
  const [domains, setDomains] = useState([]);
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [integrations, setIntegrations] = useState([]);
  const [ms365Scanning, setMs365Scanning] = useState(false);

  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [inviteLoading, setInviteLoading] = useState(false);

  const [showAddDomain, setShowAddDomain] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [domainLoading, setDomainLoading] = useState(false);

  const [logoUrl, setLogoUrl] = useState(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [companyName, setCompanyName] = useState("");

  // Director email
  const [directorEmail, setDirectorEmail] = useState("");
  const [directorEmailSaving, setDirectorEmailSaving] = useState(false);

  // Compliance frameworks
  const [tenantCountry, setTenantCountry] = useState("NZ");
  const [selectedFrameworks, setSelectedFrameworks] = useState([]);
  const [frameworksSaving, setFrameworksSaving] = useState(false);

  useEffect(() => {
    if (!requireAuth(router)) return;
    setCompanyName(localStorage.getItem("company_name") || "");
    setLogoUrl(localStorage.getItem("logo_url") || null);

    const params = new URLSearchParams(window.location.search);
    if (params.get("tab") === "integrations") setActiveTab("integrations");
    if (params.get("ms_connected")) setSuccess("Microsoft 365 connected successfully.");
    if (params.get("ms_error")) setError(`Microsoft 365 connection failed: ${params.get("ms_error")}`);
    if (params.get("ms_connected") || params.get("ms_error") || params.get("tab")) {
      window.history.replaceState({}, "", "/settings");
    }

    fetchAll();
  }, []);

 async function fetchAll() {
    setLoading(true);
    try {
      const [usersRes, domainsRes, billingRes, tenantRes, intRes] = await Promise.all([
        authFetch("/auth/users").catch(() => null),
        authFetch("/domains").catch(() => null),
        authFetch("/billing/subscription").catch(() => null),
        authFetch("/tenants/me").catch(() => null),
        authFetch("/integrations/status").catch(() => null),
      ]);
      if (usersRes) setUsers(await usersRes.json().catch(() => []));
      if (domainsRes) setDomains(await domainsRes.json().catch(() => []));
      if (billingRes) setBilling(await billingRes.json().catch(() => null));
      if (tenantRes) {
        const tenantData = await tenantRes.json().catch(() => ({}));
        setDirectorEmail(tenantData.director_email || "");
        setTenantCountry(tenantData.country || "NZ");
        setSelectedFrameworks(tenantData.compliance_frameworks || []);
      }
      if (intRes) {
        const intData = await intRes.json().catch(() => ({}));
        setIntegrations(intData.integrations || []);
      }
    } catch (err) {
      setError("Could not load settings. Please refresh the page.");
    } finally {
      setLoading(false);
    }
  }

  function handleMs365Connect() {
    const token = localStorage.getItem("token") || "";
    const state = btoa(token).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
    const redirectUri = `${window.location.origin}/api/ms365/callback`;
    const params = new URLSearchParams({
      client_id: process.env.NEXT_PUBLIC_AZURE_CLIENT_ID,
      response_type: "code",
      redirect_uri: redirectUri,
      scope: AZURE_SCOPES,
      response_mode: "query",
      prompt: "consent",
      state,
    });
    window.location.href = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?${params}`;
  }

  async function handleMs365Disconnect() {
    if (!confirm("Disconnect Microsoft 365? Existing findings will remain but no new scans will run.")) return;
    try {
      const res = await authFetch("/integrations/ms365/disconnect", { method: "DELETE" });
      if (!res.ok) { setError("Could not disconnect Microsoft 365."); return; }
      setSuccess("Microsoft 365 disconnected.");
      fetchAll();
    } catch {
      setError("Something went wrong. Please try again.");
    }
  }

  async function handleMs365Scan() {
    setMs365Scanning(true);
    setError("");
    setSuccess("");
    try {
      const res = await authFetch("/integrations/ms365/scan", { method: "POST" });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Scan failed."); return; }
      setSuccess(`Microsoft 365 scan complete — ${data.findings_count} finding${data.findings_count !== 1 ? "s" : ""} recorded.`);
      fetchAll();
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setMs365Scanning(false);
    }
  }

  async function handleSaveFrameworks(newSelected) {
    setFrameworksSaving(true);
    setError("");
    setSuccess("");
    try {
      const res = await authFetch("/tenants/me", {
        method: "PATCH",
        body: JSON.stringify({ compliance_frameworks: newSelected }),
      });
      if (!res.ok) { const d = await res.json(); setError(d.detail || "Could not save."); return; }
      setSelectedFrameworks(newSelected);
      setSuccess("Compliance frameworks saved.");
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setFrameworksSaving(false);
    }
  }

  function toggleFramework(id) {
    const next = selectedFrameworks.includes(id)
      ? selectedFrameworks.filter((f) => f !== id)
      : [...selectedFrameworks, id];
    handleSaveFrameworks(next);
  }

  async function handleSaveDirectorEmail() {
    setDirectorEmailSaving(true);
    setError("");
    setSuccess("");
    try {
      const res = await authFetch("/tenants/me", {
        method: "PATCH",
        body: JSON.stringify({ director_email: directorEmail }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Could not save director email.");
        return;
      }
      setSuccess("Director email saved. Weekly reports will be sent here every Monday at 8am.");
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setDirectorEmailSaving(false);
    }
  }

  async function handleLogoUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setError("Logo must be under 2MB.");
      return;
    }

    if (!file.type.startsWith("image/")) {
      setError("Please upload an image file (PNG, JPG, SVG).");
      return;
    }

    setLogoUploading(true);
    setError("");
    setSuccess("");

    try {
      const token = getToken();
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/tenants/logo`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Could not upload logo.");
        return;
      }

      setLogoUrl(data.logo_url);
      localStorage.setItem("logo_url", data.logo_url);
      setSuccess("Logo uploaded successfully. It will appear in your dashboard nav.");
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLogoUploading(false);
    }
  }

  async function handleLogoRemove() {
    if (!confirm("Remove your logo? The initials avatar will be shown instead.")) return;
    setLogoUploading(true);
    setError("");
    try {
      const res = await authFetch("/tenants/logo", { method: "DELETE" });
      if (!res.ok) {
        setError("Could not remove logo.");
        return;
      }
      setLogoUrl(null);
      localStorage.removeItem("logo_url");
      setSuccess("Logo removed.");
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLogoUploading(false);
    }
  }

  async function handleInvite(e) {
    e.preventDefault();
    setInviteLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await authFetch("/auth/invite", {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Could not send invite.");
        return;
      }
      setSuccess(`Invite sent to ${inviteEmail}`);
      setShowInvite(false);
      setInviteEmail("");
      fetchAll();
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleAddDomain(e) {
    e.preventDefault();
    setDomainLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await authFetch("/domains", {
        method: "POST",
        body: JSON.stringify({ domain: newDomain }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Could not add domain.");
        return;
      }
      setSuccess(`${newDomain} added successfully`);
      setShowAddDomain(false);
      setNewDomain("");
      fetchAll();
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setDomainLoading(false);
    }
  }

  async function handleRemoveDomain(domainId) {
    if (!confirm("Are you sure you want to remove this domain?")) return;
    try {
      await authFetch(`/domains/${domainId}`, { method: "DELETE" });
      setSuccess("Domain removed.");
      fetchAll();
    } catch {
      setError("Could not remove domain.");
    }
  }

  const getInitials = (name) => {
    return name.split(" ").map(w => w[0]).join("").toUpperCase().substring(0, 2);
  };

  const tabs = [
    { key: "profile", label: "Profile" },
    { key: "team", label: "Team" },
    { key: "domains", label: "Domains" },
    { key: "billing", label: "Billing" },
    { key: "integrations", label: "Integrations" },
  ];

  const ms365 = integrations.find((i) => i.platform === "microsoft365");
  const ms365Connected = ms365?.status === "connected";

  const trialExpiry = billing?.created_at ? getTrialExpiry(billing.created_at) : null;
  const trialDaysLeft = trialExpiry ? daysLeft(trialExpiry) : null;
  const domainsAllowed = billing?.max_domains || 1;
  const domainLimitReached = domains.length >= domainsAllowed;

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      <div className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">
            SecureIT<span className="text-red-500">360</span>
            <span className="text-gray-400 font-normal text-base ml-3">Settings</span>
          </h1>
          <a href="/dashboard" className="text-sm text-red-400 hover:text-red-300">
            Back to Dashboard
          </a>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8">

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">{error}</div>
        )}
        {success && (
          <div className="bg-green-900/30 border border-green-700 text-green-300 rounded-lg px-4 py-3 mb-6 text-sm">{success}</div>
        )}

        <div className="flex gap-1 mb-8 bg-gray-900 rounded-xl p-1 border border-gray-800">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setError(""); setSuccess(""); }}
              className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-red-600 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-gray-500 text-sm">Loading...</div>
        ) : (
          <>
            {/* PROFILE TAB */}
            {activeTab === "profile" && (
              <div>
                <h2 className="text-lg font-semibold mb-6">Company Profile</h2>

                {/* Logo card */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
                  <h3 className="text-white font-medium mb-4">Company Logo</h3>
                  <p className="text-gray-400 text-sm mb-6">Upload your company logo to display it in your dashboard navigation. PNG, JPG or SVG, max 2MB.</p>

                  <div className="flex items-center gap-6 mb-6">
                    <div className="w-20 h-20 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                      {logoUrl ? (
                        <img src={logoUrl} alt="Company logo" className="w-full h-full object-contain p-2" />
                      ) : (
                        <span className="text-2xl font-bold text-red-300">{getInitials(companyName)}</span>
                      )}
                    </div>
                    <div>
                      <p className="text-white font-medium mb-1">{companyName}</p>
                      <p className="text-gray-500 text-sm">{logoUrl ? "Custom logo uploaded" : "Using initials avatar"}</p>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <label className={`cursor-pointer bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors ${logoUploading ? "opacity-50 cursor-not-allowed" : ""}`}>
                      {logoUploading ? "Uploading..." : logoUrl ? "Change logo" : "Upload logo"}
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={handleLogoUpload}
                        disabled={logoUploading}
                      />
                    </label>
                    {logoUrl && (
                      <button
                        onClick={handleLogoRemove}
                        disabled={logoUploading}
                        className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                      >
                        Remove logo
                      </button>
                    )}
                  </div>
                </div>

                {/* Compliance Frameworks card */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
                  <h3 className="text-white font-medium mb-1">Compliance Frameworks</h3>
                  <p className="text-gray-400 text-sm mb-5">
                    Your country defaults are applied automatically. Tick any additional frameworks your business must comply with — they will appear in your scan findings and compliance scores.
                  </p>

                  {/* Country defaults — read-only */}
                  <div className="mb-5">
                    <p className="text-gray-500 text-xs uppercase tracking-wide mb-2">Included by default ({tenantCountry})</p>
                    <div className="flex flex-wrap gap-2">
                      {(COUNTRY_DEFAULT_FRAMEWORKS[tenantCountry] || COUNTRY_DEFAULT_FRAMEWORKS["NZ"]).map((fw) => (
                        <span key={fw} className="text-xs px-3 py-1.5 rounded-full bg-gray-800 border border-gray-700 text-gray-400">
                          {fw}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Optional frameworks — selectable */}
                  <div>
                    <p className="text-gray-500 text-xs uppercase tracking-wide mb-3">Additional frameworks</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {OPTIONAL_FRAMEWORKS.filter((f) => {
                        const defaults = COUNTRY_DEFAULT_FRAMEWORKS[tenantCountry] || COUNTRY_DEFAULT_FRAMEWORKS["NZ"];
                        return !defaults.includes(f.id);
                      }).map((fw) => {
                        const checked = selectedFrameworks.includes(fw.id);
                        return (
                          <label key={fw.id} className={`flex items-start gap-3 rounded-xl p-3 border cursor-pointer transition-colors ${
                            checked ? "bg-red-900/20 border-red-800" : "bg-gray-800 border-gray-700 hover:border-gray-600"
                          } ${frameworksSaving ? "opacity-50 cursor-not-allowed" : ""}`}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => !frameworksSaving && toggleFramework(fw.id)}
                              className="mt-0.5 flex-shrink-0 accent-red-500 w-4 h-4"
                            />
                            <div>
                              <p className="text-white text-sm font-medium">{fw.label}</p>
                              <p className="text-gray-500 text-xs mt-0.5">{fw.desc}</p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                  {frameworksSaving && <p className="text-gray-500 text-xs mt-3">Saving...</p>}
                </div>

                {/* Director email card */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h3 className="text-white font-medium mb-1">Director / Board Email</h3>
                  <p className="text-gray-400 text-sm mb-6">
                    Weekly cyber risk and governance summaries will be sent here every Monday at 8am. This can be a director, board member, or executive — whoever needs board-level visibility.
                  </p>
                  <div className="flex gap-3 items-start">
                    <input
                      type="email"
                      value={directorEmail}
                      onChange={(e) => setDirectorEmail(e.target.value)}
                      placeholder="director@yourcompany.com"
                      className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500 text-sm"
                    />
                    <button
                      onClick={handleSaveDirectorEmail}
                      disabled={directorEmailSaving}
                      className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-5 py-3 rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
                    >
                      {directorEmailSaving ? "Saving..." : "Save"}
                    </button>
                  </div>
                  {directorEmail && (
                    <p className="text-gray-500 text-xs mt-3">
                      Weekly reports will be sent to <span className="text-gray-300">{directorEmail}</span>
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* TEAM TAB */}
            {activeTab === "team" && (
              <div>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold">Team members</h2>
                  <button
                    onClick={() => setShowInvite(true)}
                    className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
                  >
                    Invite member
                  </button>
                </div>

                <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800">
                  {users.length === 0 && (
                    <div className="px-6 py-4 text-gray-500 text-sm">No team members yet.</div>
                  )}
                  {users.map && users.map((u) => (
                    <div key={u.id} className="flex items-center justify-between px-6 py-4">
                      <div>
                        <div className="text-white font-medium">{u.email}</div>
                        <div className="text-gray-500 text-sm">{u.name || "-"}</div>
                      </div>
                      <span className={`text-xs font-medium px-3 py-1 rounded-full ${
                        u.role === "owner" ? "bg-red-900 text-red-300" :
                        u.role === "admin" ? "bg-blue-900 text-blue-300" :
                        "bg-gray-800 text-gray-400"
                      }`}>
                        {u.role}
                      </span>
                    </div>
                  ))}
                </div>

                {showInvite && (
                  <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
                    <div className="bg-gray-900 rounded-2xl p-8 w-full max-w-md border border-gray-700">
                      <h3 className="text-lg font-semibold mb-6">Invite a team member</h3>
                      <form onSubmit={handleInvite} className="space-y-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Email address</label>
                          <input
                            type="email"
                            value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                            required
                            placeholder="colleague@yourcompany.com"
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Role</label>
                          <select
                            value={inviteRole}
                            onChange={(e) => setInviteRole(e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500"
                          >
                            <option value="admin">Admin - can manage users and domains</option>
                            <option value="viewer">Viewer - can view reports only</option>
                          </select>
                        </div>
                        <div className="flex gap-3 pt-2">
                          <button type="submit" disabled={inviteLoading}
                            className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-3 rounded-lg">
                            {inviteLoading ? "Sending..." : "Send invite"}
                          </button>
                          <button type="button" onClick={() => setShowInvite(false)}
                            className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg">
                            Cancel
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* DOMAINS TAB */}
            {activeTab === "domains" && (
              <div>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold">Domains</h2>
                  {domainLimitReached ? (
                    <span className="text-amber-400 text-sm font-medium bg-amber-900/30 border border-amber-700 px-4 py-2 rounded-lg">
                      Plan limit reached - upgrade to add more domains
                    </span>
                  ) : (
                    <button onClick={() => setShowAddDomain(true)}
                      className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
                      Add domain
                    </button>
                  )}
                </div>

                <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800">
                  {domains.length === 0 && (
                    <div className="px-6 py-4 text-gray-500 text-sm">No domains added yet.</div>
                  )}
                  {domains.map && domains.map((d) => (
                    <div key={d.id} className="flex items-center justify-between px-6 py-4">
                      <div>
                        <div className="text-white font-medium">{d.domain}</div>
                        <div className="text-gray-500 text-sm">Added {new Date(d.created_at).toLocaleDateString()}</div>
                      </div>
                      <button onClick={() => handleRemoveDomain(d.id)}
                        className="text-red-400 hover:text-red-300 text-sm">
                        Remove
                      </button>
                    </div>
                  ))}
                </div>

                {showAddDomain && (
                  <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
                    <div className="bg-gray-900 rounded-2xl p-8 w-full max-w-md border border-gray-700">
                      <h3 className="text-lg font-semibold mb-6">Add a domain</h3>
                      <form onSubmit={handleAddDomain} className="space-y-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Domain</label>
                          <input type="text" value={newDomain} onChange={(e) => setNewDomain(e.target.value)}
                            required placeholder="yourcompany.com"
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500" />
                          <p className="text-xs text-gray-500 mt-1">Enter domain without https://</p>
                        </div>
                        <div className="flex gap-3 pt-2">
                          <button type="submit" disabled={domainLoading}
                            className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-3 rounded-lg">
                            {domainLoading ? "Adding..." : "Add domain"}
                          </button>
                          <button type="button" onClick={() => setShowAddDomain(false)}
                            className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg">
                            Cancel
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* INTEGRATIONS TAB */}
            {activeTab === "integrations" && (
              <div>
                <h2 className="text-lg font-semibold mb-2">Integrations</h2>
                <p className="text-gray-400 text-sm mb-6">
                  Connect cloud platforms to extend your security scans beyond your domains.
                </p>

                {/* Microsoft 365 card */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0">
                        <svg width="28" height="28" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
                          <rect x="12" y="1" width="10" height="10" fill="#7FBA00"/>
                          <rect x="1" y="12" width="10" height="10" fill="#00A4EF"/>
                          <rect x="12" y="12" width="10" height="10" fill="#FFB900"/>
                        </svg>
                      </div>
                      <div>
                        <div className="text-white font-semibold">Microsoft 365</div>
                        <div className="text-gray-400 text-sm mt-0.5">
                          Scan for MFA gaps, inactive accounts, admin sprawl, and external file sharing.
                        </div>
                        {ms365Connected && ms365.org_name && (
                          <div className="text-gray-500 text-xs mt-1">
                            Connected to <span className="text-gray-300">{ms365.org_name}</span>
                          </div>
                        )}
                        {ms365Connected && ms365.last_synced_at && (
                          <div className="text-gray-600 text-xs mt-0.5">
                            Last scanned {new Date(ms365.last_synced_at).toLocaleDateString("en-NZ", {
                              day: "numeric", month: "short", year: "numeric"
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                    <span className={`text-xs font-medium px-3 py-1 rounded-full flex-shrink-0 ${
                      ms365Connected
                        ? "bg-green-900/50 text-green-300 border border-green-800"
                        : "bg-gray-800 text-gray-500 border border-gray-700"
                    }`}>
                      {ms365Connected ? "Connected" : "Not connected"}
                    </span>
                  </div>

                  <div className="mt-5 pt-5 border-t border-gray-800">
                    <div className="text-gray-500 text-xs mb-4">
                      Checks performed: MFA status · Inactive users (90+ days) · Admin privilege sprawl · External file sharing
                    </div>
                    {ms365Connected ? (
                      <div className="flex gap-3">
                        <button
                          onClick={handleMs365Scan}
                          disabled={ms365Scanning}
                          className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {ms365Scanning ? "Scanning..." : "Run scan"}
                        </button>
                        <button
                          onClick={handleMs365Disconnect}
                          className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                        >
                          Disconnect
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={handleMs365Connect}
                        className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                      >
                        Connect Microsoft 365
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* BILLING TAB */}
            {activeTab === "billing" && (
              <div>
                <h2 className="text-lg font-semibold mb-6">Billing & plan</h2>
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-gray-400 text-sm mb-1">Current plan</div>
                      <div className="text-white text-xl font-bold">{billing?.plan_name || "Trial"}</div>
                    </div>
                    <span className={`text-sm font-medium px-4 py-2 rounded-full ${
                      billing?.status === "active" ? "bg-green-900 text-green-300" :
                      billing?.status === "past_due" ? "bg-amber-900 text-amber-300" :
                      "bg-gray-800 text-gray-400"
                    }`}>
                      {billing?.status || "Trial"}
                    </span>
                  </div>

                  <hr className="border-gray-800" />

                  {trialExpiry && billing?.status?.toLowerCase() === "trial" && (
                    <div className="bg-amber-900/30 border border-amber-700 rounded-lg px-4 py-4">
                      <div className="text-amber-300 font-medium mb-1">
                        Free trial - {trialDaysLeft} day{trialDaysLeft !== 1 ? "s" : ""} remaining
                      </div>
                      <div className="text-amber-400/70 text-sm">
                        Your trial ends on {trialExpiry.toLocaleDateString("en-NZ", {
                          day: "numeric", month: "long", year: "numeric"
                        })}.
                      </div>
                    </div>
                  )}

                  <div>
                    <div className="text-gray-400 text-sm mb-2">Domains used</div>
                    <div className="flex items-center gap-3">
                      <div className="text-white font-medium">{domains.length} of {domainsAllowed}</div>
                      <div className="flex-1 bg-gray-800 rounded-full h-2">
                        <div className="bg-red-500 h-2 rounded-full"
                          style={{ width: `${Math.min(100, (domains.length / domainsAllowed) * 100)}%` }} />
                      </div>
                    </div>
                  </div>

                  {billing?.renewal_date && (
                    <div>
                      <div className="text-gray-400 text-sm mb-1">Next renewal</div>
                      <div className="text-white font-medium">
                        {new Date(billing.renewal_date).toLocaleDateString("en-NZ", {
                          day: "numeric", month: "long", year: "numeric"
                        })}
                      </div>
                    </div>
                  )}

                  <hr className="border-gray-800" />

                  <a href="/pricing"
                    className="block w-full text-center bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg transition-colors">
                    Upgrade plan
                  </a>

                  <p className="text-center text-gray-600 text-xs">
                    To cancel or change your plan contact us at governance@secureit360.co
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}