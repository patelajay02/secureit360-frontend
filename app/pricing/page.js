// app/pricing/page.js
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageTitle } from "../../components/ui/PageTitle";
import { authFetch, getToken } from "../../lib/auth";

const plans = [
  {
    key: "starter",
    name: "Starter",
    prices: {
      NZ: { amount: 250, symbol: "$", code: "NZD" },
      AU: { amount: 299, symbol: "$", code: "AUD" },
      IN: { amount: 12500, symbol: "₹", code: "INR" },
      AE: { amount: 549, symbol: "$", code: "AED" },
      PI: { amount: 149, symbol: "$", code: "USD" },
      OTHER: { amount: 149, symbol: "$", code: "USD" },
    },
    domains: 1,
    users: 3,
    popular: false,
    features: [
      "1 domain scanned daily",
      "6 security scan engines",
      "Ransom Risk Score",
      "Weekly director email",
      "Plain English findings",
      "Auto-fix simple issues",
    ],
  },
  {
    key: "pro",
    name: "Pro",
    prices: {
      NZ: { amount: 500, symbol: "$", code: "NZD" },
      AU: { amount: 599, symbol: "$", code: "AUD" },
      IN: { amount: 25000, symbol: "₹", code: "INR" },
      AE: { amount: 1099, symbol: "$", code: "AED" },
      PI: { amount: 299, symbol: "$", code: "USD" },
      OTHER: { amount: 299, symbol: "$", code: "USD" },
    },
    domains: 3,
    users: 10,
    popular: true,
    features: [
      "3 domains scanned daily",
      "6 security scan engines",
      "Ransom Risk Score",
      "Weekly director email",
      "Plain English findings",
      "Auto-fix simple issues",
      "Voice-guided fix walkthroughs",
      "Compliance gap report",
      "Director evidence report",
    ],
  },
  {
    key: "enterprise",
    name: "Enterprise",
    prices: {
      NZ: { amount: 840, symbol: "$", code: "NZD" },
      AU: { amount: 999, symbol: "$", code: "AUD" },
      IN: { amount: 42000, symbol: "₹", code: "INR" },
      AE: { amount: 1849, symbol: "$", code: "AED" },
      PI: { amount: 499, symbol: "$", code: "USD" },
      OTHER: { amount: 499, symbol: "$", code: "USD" },
    },
    domains: 10,
    users: 50,
    popular: false,
    features: [
      "10 domains scanned daily",
      "6 security scan engines",
      "Ransom Risk Score",
      "Weekly director email",
      "Plain English findings",
      "Auto-fix simple issues",
      "Voice-guided fix walkthroughs",
      "Full compliance gap report",
      "Director evidence report",
      "ISO 27001 readiness report",
      "Essential Eight maturity report",
      "Priority specialist access",
    ],
  },
];

export default function PricingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(null);
  const [country, setCountry] = useState("NZ");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    fetchUserCountry();
  }, []);

  async function fetchUserCountry() {
    try {
      const res = await authFetch("/auth/me");
      const data = await res.json();
      setCountry(data.country || "NZ");
    } catch {
      setCountry("NZ");
    }
  }

  async function handleSubscribe(planKey) {
    setLoading(planKey);
    try {
      const res = await authFetch(`/billing/checkout/${planKey}`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      console.error("Checkout error:", err);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <PageTitle title="Choose your plan" />

      <div className="text-center py-16 px-4">
        <h1 className="text-4xl font-bold text-white mb-4">
          Choose your plan
        </h1>
        <p className="text-gray-400 text-lg max-w-xl mx-auto">
          No setup fees. No lock-in contracts. Cancel any time.
        </p>
      </div>

      <div className="max-w-6xl mx-auto px-4 pb-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan) => {
            const price = plan.prices[country] || plan.prices["OTHER"];
            return (
              <div
                key={plan.key}
                className={`relative bg-gray-900 rounded-2xl border p-8 flex flex-col ${
                  plan.popular
                    ? "border-indigo-500 shadow-lg shadow-indigo-500/20"
                    : "border-gray-800"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                    <span className="bg-indigo-600 text-white text-xs font-bold px-4 py-1 rounded-full">
                      MOST POPULAR
                    </span>
                  </div>
                )}

                <div className="mb-6">
                  <h2 className="text-xl font-bold text-white mb-2">{plan.name}</h2>
                  <div className="flex items-end gap-2">
                    <span className="text-4xl font-black text-white">
                      {price.symbol}{price.amount.toLocaleString()}
                    </span>
                    <span className="text-gray-400 mb-1">{price.code}/month</span>
                  </div>
                  <p className="text-gray-500 text-sm mt-2">
                    {plan.domains} domain{plan.domains > 1 ? "s" : ""} — {plan.users} users
                  </p>
                </div>

                <ul className="space-y-3 flex-1 mb-8">
                  {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm">
                      <span className="text-green-400 mt-0.5 flex-shrink-0">✓</span>
                      <span className="text-gray-300">{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(plan.key)}
                  disabled={loading === plan.key}
                  className={`w-full py-3 rounded-lg font-semibold transition-colors ${
                    plan.popular
                      ? "bg-indigo-600 hover:bg-indigo-700 text-white"
                      : "bg-gray-800 hover:bg-gray-700 text-white"
                  } disabled:opacity-50`}
                >
                  {loading === plan.key ? "Loading..." : "Subscribe now"}
                </button>
              </div>
            );
          })}
        </div>

        <div className="text-center mt-12">
          <p className="text-gray-600 text-sm">
            Need help choosing? Email us at hello@secureit360.co
          </p>
        </div>
      </div>
    </div>
  );
}