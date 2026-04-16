// app/settings/page.js
// SecureIT360 - Settings page
// Tabs: Profile, Team, Domains, Billing

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authFetch, requireAuth, getToken } from "../../lib/auth";

const TRIAL_DAYS = 7;

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

  useEffect(() => {
    if (!requireAuth(router)) return;
    setCompanyName(localStorage.getItem("company_name") || "");
    setLogoUrl(localStorage.getItem("logo_url") || null);
    fetchAll();
  }, []);

 async function fetchAll() {
    setLoading(true);
    try {
      const [usersRes, domainsRes, billingRes, tenantRes] = await Promise.all([
        authFetch("/auth/users").catch(() => null),
        authFetch("/domains").catch(() => null),
        authFetch("/billing/subscription").catch(() => null),
        authFetch("/tenants/me").catch(() => null),
      ]);
      if (usersRes) setUsers(await usersRes.json().catch(() => []));
      if (domainsRes) setDomains(await domainsRes.json().catch(() => []));
      if (billingRes) setBilling(await billingRes.json().catch(() => null));
      if (tenantRes) {
        const tenantData = await tenantRes.json().catch(() => ({}));
        setDirectorEmail(tenantData.director_email || "");
      }
    } catch (err) {
      setError("Could not load settings. Please refresh the page.");
    } finally {
      setLoading(false);
    }
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
  ];

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