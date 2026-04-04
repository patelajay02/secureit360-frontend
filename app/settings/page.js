// app/settings/page.js
// SecureIT360 — Settings page
// Three tabs: Team, Domains, Billing

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authFetch, requireAuth } from "../../lib/auth";

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
  const [activeTab, setActiveTab] = useState("team");
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

  useEffect(() => {
    if (!requireAuth(router)) return;
    fetchAll();
  }, []);

  async function fetchAll() {
    setLoading(true);
    try {
      const [usersRes, domainsRes, billingRes] = await Promise.all([
        authFetch("/users"),
        authFetch("/domains"),
        authFetch("/billing/subscription"),
      ]);
      setUsers(await usersRes.json());
      setDomains(await domainsRes.json());
      setBilling(await billingRes.json());
    } catch (err) {
      setError("Could not load settings. Please refresh the page.");
    } finally {
      setLoading(false);
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

  const tabs = [
    { key: "team", label: "Team" },
    { key: "domains", label: "Domains" },
    { key: "billing", label: "Billing" },
  ];

  const trialExpiry = billing?.created_at ? getTrialExpiry(billing.created_at) : null;
  const trialDaysLeft = trialExpiry ? daysLeft(trialExpiry) : null;
  const domainsAllowed = billing?.domains_allowed || 1;
  const domainLimitReached = domains.length >= domainsAllowed;

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">
            SecureIT<span className="text-indigo-400">360</span>
            <span className="text-gray-400 font-normal text-base ml-3">Settings</span>
          </h1>
          <a href="/dashboard" className="text-sm text-indigo-400 hover:text-indigo-300">
            ← Back to dashboard
          </a>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8">

        {error && (
          <div className="bg-red-900/40 border border-red-500 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="bg-green-900/40 border border-green-500 text-green-300 rounded-lg px-4 py-3 mb-6 text-sm">
            {success}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-900 rounded-xl p-1 mb-8 w-fit">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-6 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-indigo-600 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-gray-400">Loading...</div>
        ) : (
          <>
            {/* TEAM TAB */}
            {activeTab === "team" && (
              <div>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold">Team members</h2>
                  <button
                    onClick={() => setShowInvite(true)}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
                  >
                    Invite user
                  </button>
                </div>

                <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800">
                  {users.length === 0 && (
                    <div className="px-6 py-4 text-gray-500 text-sm">No team members yet.</div>
                  )}
                  {users.map((u) => (
                    <div key={u.id} className="flex items-center justify-between px-6 py-4">
                      <div>
                        <div className="text-white font-medium">{u.email}</div>
                        <div className="text-gray-500 text-sm">{u.name || "—"}</div>
                      </div>
                      <span className={`text-xs font-medium px-3 py-1 rounded-full ${
                        u.role === "owner" ? "bg-indigo-900 text-indigo-300" :
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
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Role</label>
                          <select
                            value={inviteRole}
                            onChange={(e) => setInviteRole(e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                          >
                            <option value="admin">Admin — can manage users and domains</option>
                            <option value="viewer">Viewer — can view reports only</option>
                          </select>
                        </div>
                        <div className="flex gap-3 pt-2">
                          <button
                            type="submit"
                            disabled={inviteLoading}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 rounded-lg"
                          >
                            {inviteLoading ? "Sending..." : "Send invite"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setShowInvite(false)}
                            className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg"
                          >
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
                      Plan limit reached — upgrade to add more domains
                    </span>
                  ) : (
                    <button
                      onClick={() => setShowAddDomain(true)}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
                    >
                      Add domain
                    </button>
                  )}
                </div>

                <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800">
                  {domains.length === 0 && (
                    <div className="px-6 py-4 text-gray-500 text-sm">No domains added yet.</div>
                  )}
                  {domains.map((d) => (
                    <div key={d.id} className="flex items-center justify-between px-6 py-4">
                      <div>
                        <div className="text-white font-medium">{d.domain}</div>
                        <div className="text-gray-500 text-sm">Added {new Date(d.created_at).toLocaleDateString()}</div>
                      </div>
                      <button
                        onClick={() => handleRemoveDomain(d.id)}
                        className="text-red-400 hover:text-red-300 text-sm"
                      >
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
                          <input
                            type="text"
                            value={newDomain}
                            onChange={(e) => setNewDomain(e.target.value)}
                            required
                            placeholder="yourcompany.com"
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                          />
                          <p className="text-xs text-gray-500 mt-1">Enter domain without https://</p>
                        </div>
                        <div className="flex gap-3 pt-2">
                          <button
                            type="submit"
                            disabled={domainLoading}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 rounded-lg"
                          >
                            {domainLoading ? "Adding..." : "Add domain"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setShowAddDomain(false)}
                            className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg"
                          >
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
                      <div className="text-white text-xl font-bold">
                        {billing?.plan_name || "Starter"}
                      </div>
                      <div className="text-gray-400 text-sm mt-1">
                        {billing?.price_nzd || "$250"} NZD per month
                      </div>
                    </div>
                    <span className="bg-indigo-900 text-indigo-300 text-sm font-medium px-4 py-2 rounded-full">
                      {billing?.status || "Trial"}
                    </span>
                  </div>

                  <hr className="border-gray-800" />

                  {trialExpiry && (
                    <div className="bg-amber-900/30 border border-amber-700 rounded-lg px-4 py-4">
                      <div className="text-amber-300 font-medium mb-1">
                        Free trial — {trialDaysLeft} day{trialDaysLeft !== 1 ? "s" : ""} remaining
                      </div>
                      <div className="text-amber-400/70 text-sm">
                        Your trial ends on {trialExpiry.toLocaleDateString("en-NZ", {
                          day: "numeric", month: "long", year: "numeric"
                        })}. After this date you will need an active subscription to continue scanning.
                      </div>
                    </div>
                  )}

                  <div>
                    <div className="text-gray-400 text-sm mb-2">Domains used</div>
                    <div className="flex items-center gap-3">
                      <div className="text-white font-medium">
                        {domains.length} of {domainsAllowed}
                      </div>
                      <div className="flex-1 bg-gray-800 rounded-full h-2">
                        <div
                          className="bg-indigo-500 h-2 rounded-full"
                          style={{
                            width: `${Math.min(100, (domains.length / domainsAllowed) * 100)}%`
                          }}
                        />
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

                  <button className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg transition-colors">
                    Upgrade plan
                  </button>

                  <p className="text-center text-gray-600 text-xs">
                    To cancel or change your plan contact us at support@globalcyberassurance.com
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