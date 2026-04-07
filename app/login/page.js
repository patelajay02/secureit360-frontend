// app/login/page.js
// SecureIT360 - Login page v2

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setToken, setRefreshToken, setUser, publicFetch } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();

  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await publicFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: form.email,
          password: form.password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Invalid email or password. Please try again.");
        return;
      }

      setToken(data.token);
      if (data.refresh_token) setRefreshToken(data.refresh_token);
      setUser({
        user_id: data.user_id,
        email: data.email,
        tenant_id: data.tenant_id,
        role: data.role,
        company_name: data.company_name,
        plan: data.plan,
        country: data.country,
        mobile: data.mobile,
      });

      localStorage.setItem("company_name", data.company_name || "");
      localStorage.setItem("country", data.country || "NZ");
      localStorage.setItem("plan", data.plan || "");
      localStorage.setItem("status", data.status || "trial");
      localStorage.setItem("trial_ends_at", data.trial_ends_at || "");

      router.push("/dashboard");

    } catch (err) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotPassword(e) {
    e.preventDefault();
    setLoading(true);

    try {
      await publicFetch("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: forgotEmail }),
      });
      setForgotSent(true);
    } catch (err) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">

        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">
            SecureIT<span className="text-red-500">360</span>
          </h1>
          <p className="text-gray-400 mt-2">by Global Cyber Assurance</p>
        </div>

        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">

          {!showForgot ? (
            <>
              <h2 className="text-xl font-semibold text-white mb-6">Log in to your account</h2>

              {error && (
                <div className="bg-red-900/40 border border-red-500 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Email address</label>
                  <input
                    type="email"
                    name="email"
                    value={form.email}
                    onChange={handleChange}
                    required
                    placeholder="you@yourcompany.com"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Password</label>
                  <input
                    type="password"
                    name="password"
                    value={form.password}
                    onChange={handleChange}
                    required
                    placeholder="Your password"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500"
                  />
                </div>

                <div className="text-right">
                  <button
                    type="button"
                    onClick={() => setShowForgot(true)}
                    className="text-sm text-red-400 hover:text-red-300"
                  >
                    Forgot your password?
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-900 text-white font-semibold py-3 rounded-lg transition-colors"
                >
                  {loading ? "Logging in..." : "Log in"}
                </button>
              </form>

              <p className="text-center text-gray-500 text-sm mt-6">
                Do not have an account?{" "}
                <a href="/signup" className="text-red-400 hover:text-red-300">Sign up free</a>
              </p>
            </>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-white mb-2">Reset your password</h2>
              <p className="text-gray-400 text-sm mb-6">
                Enter your email and we will send you a reset link.
              </p>

              {forgotSent ? (
                <div className="bg-green-900/40 border border-green-500 text-green-300 rounded-lg px-4 py-3 text-sm">
                  Reset link sent! Check your email inbox.
                </div>
              ) : (
                <form onSubmit={handleForgotPassword} className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Email address</label>
                    <input
                      type="email"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      required
                      placeholder="you@yourcompany.com"
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-900 text-white font-semibold py-3 rounded-lg transition-colors"
                  >
                    {loading ? "Sending..." : "Send reset link"}
                  </button>
                </form>
              )}

              <div className="text-center mt-4">
                <button
                  onClick={() => setShowForgot(false)}
                  className="text-sm text-red-400 hover:text-red-300"
                >
                  Back to login
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
