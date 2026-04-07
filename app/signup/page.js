// app/signup/page.js
// SecureIT360 — Signup page
// With reCAPTCHA, domain validation, business email validation, country selection

"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import ReCAPTCHA from "react-google-recaptcha";
import { setToken, setUser, publicFetch } from "../../lib/auth";

const countries = [
  { code: "AU", name: "Australia", currency: "aud" },
  { code: "NZ", name: "New Zealand", currency: "nzd" },
  { code: "IN", name: "India", currency: "inr" },
  { code: "AE", name: "United Arab Emirates", currency: "aed" },
  { code: "PI", name: "Pacific Islands", currency: "usd" },
  { code: "OTHER", name: "Other", currency: "usd" },
];

function isValidDomain(domain) {
  const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$/;
  return domainRegex.test(domain);
}

function emailMatchesDomain(email, domain) {
  const emailDomain = email.split("@")[1];
  return emailDomain === domain;
}

export default function SignupPage() {
  const router = useRouter();
  const recaptchaRef = useRef(null);

  const [form, setForm] = useState({
    company_name: "",
    country: "",
    domain: "",
    email: "",
    password: "",
    confirm_password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    // Validate country
    if (!form.country) {
      setError("Please select where your business is based");
      return;
    }

    // Validate domain format
    if (!isValidDomain(form.domain)) {
      setError("Please enter a valid domain e.g. yourcompany.com");
      return;
    }

    // Validate business email matches domain
    if (!emailMatchesDomain(form.email, form.domain)) {
      setError("Your email must match your company domain e.g. you@yourcompany.com");
      return;
    }

    // Validate passwords match
    if (form.password !== form.confirm_password) {
      setError("Passwords do not match");
      return;
    }

    // Validate password length
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    // Validate reCAPTCHA
    const recaptchaToken = recaptchaRef.current.getValue();
    if (!recaptchaToken) {
      setError("Please tick the I am not a robot box");
      return;
    }

    setLoading(true);

    try {
      const response = await publicFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          company_name: form.company_name,
          country: form.country,
          domain: form.domain,
          email: form.email,
          password: form.password,
          recaptcha_token: recaptchaToken,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Signup failed. Please try again.");
        recaptchaRef.current.reset();
        return;
      }

      setToken(data.access_token);
      setUser(data.user);

      await publicFetch("/scans/full", {
        method: "POST",
        body: JSON.stringify({ domain: form.domain }),
      });

      router.push("/dashboard/scanning");

    } catch (err) {
      setError("Something went wrong. Please try again.");
      recaptchaRef.current.reset();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">
            SecureIT<span className="text-indigo-400">360</span>
          </h1>
          <p className="text-gray-400 mt-2">by Global Cyber Assurance</p>
        </div>

        {/* Card */}
        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
          <h2 className="text-xl font-semibold text-white mb-6">
            Create your account
          </h2>

          {error && (
            <div className="bg-red-900/40 border border-red-500 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Company Name */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Company name
              </label>
              <input
                type="text"
                name="company_name"
                value={form.company_name}
                onChange={handleChange}
                required
                placeholder="Your company name"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Country */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Where is your business based?
              </label>
              <select
                name="country"
                value={form.country}
                onChange={handleChange}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="" disabled>Select your country</option>
                {countries.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Domain */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Company domain
              </label>
              <input
                type="text"
                name="domain"
                value={form.domain}
                onChange={handleChange}
                required
                placeholder="yourcompany.com"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Enter your domain without https:// e.g. yourcompany.com
              </p>
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Business email
              </label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                required
                placeholder="you@yourcompany.com"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Must match your company domain
              </p>
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Password
              </label>
              <input
                type="password"
                name="password"
                value={form.password}
                onChange={handleChange}
                required
                placeholder="Minimum 8 characters"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Confirm password
              </label>
              <input
                type="password"
                name="confirm_password"
                value={form.confirm_password}
                onChange={handleChange}
                required
                placeholder="Repeat your password"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* reCAPTCHA */}
            <div className="flex justify-center">
              <ReCAPTCHA
                ref={recaptchaRef}
                sitekey={process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY}
                theme="dark"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-900 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              {loading ? "Creating your account..." : "Create account"}
            </button>

          </form>

          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{" "}
            <a href="/login" className="text-indigo-400 hover:text-indigo-300">
              Log in
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}