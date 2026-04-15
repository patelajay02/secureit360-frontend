// app/page.tsx
// SecureIT360 - Public Landing Page

"use client";

import { useState } from "react";

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      {/* Nav */}
      <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">SecureIT<span className="text-red-500">360</span></h1>
          <div className="hidden md:flex items-center gap-6">
            <a href="#features" className="text-gray-400 hover:text-white text-sm">Features</a>
            <a href="#how-it-works" className="text-gray-400 hover:text-white text-sm">How it works</a>
            <a href="#pricing" className="text-gray-400 hover:text-white text-sm">Pricing</a>
            <a href="/login" className="text-gray-400 hover:text-white text-sm">Sign in</a>
            <a href="/signup" className="bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2 rounded-lg font-medium">Start free trial</a>
          </div>
          <button className="md:hidden text-gray-400" onClick={() => setMenuOpen(!menuOpen)}>
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={menuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
            </svg>
          </button>
        </div>
        {menuOpen && (
          <div className="md:hidden border-t border-gray-800 px-6 py-4 space-y-3 bg-gray-900">
            <a href="#features" className="block text-gray-400 hover:text-white text-sm">Features</a>
            <a href="#how-it-works" className="block text-gray-400 hover:text-white text-sm">How it works</a>
            <a href="#pricing" className="block text-gray-400 hover:text-white text-sm">Pricing</a>
            <a href="/login" className="block text-gray-400 hover:text-white text-sm">Sign in</a>
            <a href="/signup" className="block bg-red-600 text-white text-sm px-4 py-2 rounded-lg font-medium text-center">Start free trial</a>
          </div>
        )}
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 py-20 text-center">
        <div className="inline-flex items-center gap-2 bg-red-900/30 border border-red-800 rounded-full px-4 py-1.5 mb-8">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
          <span className="text-red-300 text-sm font-medium">Trusted by businesses across the Asia-Pacific region</span>
        </div>
        <h2 className="text-4xl md:text-6xl font-bold text-white mb-6 leading-tight">
          Know Your Cyber Risk<br />
          <span className="text-red-500">In 60 Seconds</span>
        </h2>
        <p className="text-gray-400 text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
          Automated cyber security scanning for small and medium businesses. Plain English findings. No jargon. No IT team required.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center mb-6">
          <a href="/signup" className="bg-red-600 hover:bg-red-700 text-white font-semibold px-8 py-4 rounded-xl text-lg transition-colors">
            Start Your Free 7-Day Trial
          </a>
          <a href="/login" className="border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white font-semibold px-8 py-4 rounded-xl text-lg transition-colors">
            Sign In
          </a>
        </div>
        <p className="text-gray-600 text-sm">No credit card required. Free trial includes Dark Web and Email Security scans.</p>
      </section>

      {/* Trust signals */}
      <section className="border-y border-gray-800 bg-gray-900/50">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            <div>
              <p className="text-2xl font-bold text-white">6</p>
              <p className="text-gray-500 text-sm mt-1">Scan engines</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-white">60s</p>
              <p className="text-gray-500 text-sm mt-1">Scan time</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-white">Sydney</p>
              <p className="text-gray-500 text-sm mt-1">Data stored in Australia</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-white">24/7</p>
              <p className="text-gray-500 text-sm mt-1">Daily automated scanning</p>
            </div>
          </div>
        </div>
      </section>

      {/* Risk score preview */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-12">
          <h3 className="text-3xl font-bold text-white mb-4">What You See When You Log In</h3>
          <p className="text-gray-400 max-w-2xl mx-auto">Your security dashboard shows exactly where your business stands — and what it could cost you if attacked today.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 text-center">
            <div className="w-24 h-24 rounded-full border-4 border-red-500 flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl font-bold text-red-500">72</span>
            </div>
            <p className="text-white font-semibold">Ransom Risk Score</p>
            <p className="text-red-400 text-sm mt-1">High Risk</p>
            <p className="text-gray-500 text-xs mt-2">Higher score = higher risk of ransomware attack</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 text-center">
            <div className="w-24 h-24 rounded-full border-4 border-purple-500 flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl font-bold text-purple-500">58</span>
            </div>
            <p className="text-white font-semibold">Governance Score</p>
            <p className="text-purple-400 text-sm mt-1">Gaps detected</p>
            <p className="text-gray-500 text-xs mt-2">Policy and process gaps that technical fixes alone cannot resolve</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <p className="text-gray-400 text-sm uppercase tracking-wide mb-4">If Attacked Today</p>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400 text-sm">Estimated ransom demand</span>
                <span className="text-white font-semibold text-sm">$85K - $220K</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400 text-sm">Expected downtime</span>
                <span className="text-white font-semibold text-sm">14 - 28 days</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400 text-sm">Director liability</span>
                <span className="text-red-400 font-semibold text-sm">High</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="bg-gray-900/50 border-y border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <div className="text-center mb-12">
            <h3 className="text-3xl font-bold text-white mb-4">Six Scan Engines. One Dashboard.</h3>
            <p className="text-gray-400 max-w-2xl mx-auto">Every scan runs automatically. Results appear in plain English. No technical knowledge required.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon: "🔍", title: "Dark Web Scan", desc: "Checks if your business emails and passwords have been leaked in data breaches" },
              { icon: "📧", title: "Email Security Scan", desc: "Checks if scammers can send emails pretending to be your business (DMARC, SPF, DKIM)" },
              { icon: "🌐", title: "Network Scan", desc: "Scans for open ports and exposed services that hackers could exploit" },
              { icon: "🔒", title: "Website & SSL Scan", desc: "Checks your security certificate and missing website security protections" },
              { icon: "💻", title: "Device Scan", desc: "Looks for unpatched software and known vulnerabilities on your network" },
              { icon: "☁️", title: "Cloud Storage Scan", desc: "Checks for publicly exposed cloud files visible to anyone on the internet" },
            ].map((feature, i) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="text-3xl mb-3">{feature.icon}</div>
                <h4 className="text-white font-semibold mb-2">{feature.title}</h4>
                <p className="text-gray-400 text-sm">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-12">
          <h3 className="text-3xl font-bold text-white mb-4">Up and Running in 3 Steps</h3>
          <p className="text-gray-400">No installation. No IT team. No technical knowledge required.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            { step: "1", title: "Register your business", desc: "Create your account with your business domain. Takes 2 minutes." },
            { step: "2", title: "Verify your domain", desc: "Add a simple DNS record to confirm you own your domain. We guide you through it." },
            { step: "3", title: "See your results", desc: "Your Ransom Risk Score, Governance Score, and plain English findings appear instantly." },
          ].map((item, i) => (
            <div key={i} className="text-center">
              <div className="w-12 h-12 rounded-full bg-red-600 flex items-center justify-center mx-auto mb-4">
                <span className="text-white font-bold text-lg">{item.step}</span>
              </div>
              <h4 className="text-white font-semibold mb-2">{item.title}</h4>
              <p className="text-gray-400 text-sm">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Compliance */}
      <section className="bg-gray-900/50 border-y border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <div className="text-center mb-12">
            <h3 className="text-3xl font-bold text-white mb-4">Built for Local Regulations</h3>
            <p className="text-gray-400 max-w-2xl mx-auto">SecureIT360 automatically maps your security findings to the laws that apply to your business.</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[
              "NZ Privacy Act 2020",
              "NZ Privacy Amendment 2025",
              "AU Privacy Act 1988",
              "AU Cyber Security Act 2024",
              "Essential Eight",
              "ISO 27001",
            ].map((reg, i) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                <p className="text-white text-sm font-medium">{reg}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Teaser */}
      <section className="max-w-6xl mx-auto px-6 py-16 text-center">
        <h3 className="text-3xl font-bold text-white mb-4">Simple, Transparent Pricing</h3>
        <p className="text-gray-400 mb-2">Plans starting from <span className="text-white font-semibold">$250 NZD/month + GST</span></p>
        <p className="text-gray-500 text-sm mb-8">Pricing shown in your local currency after signup. 7-day free trial included — no credit card required.</p>
        <a href="/signup" className="inline-block bg-red-600 hover:bg-red-700 text-white font-semibold px-8 py-3 rounded-xl transition-colors">See Pricing After Signup</a>
      </section>

      {/* CTA */}
      <section className="bg-red-900/20 border-y border-red-900/40">
        <div className="max-w-4xl mx-auto px-6 py-16 text-center">
          <h3 className="text-3xl font-bold text-white mb-4">Ready to Know Your Cyber Risk?</h3>
          <p className="text-gray-400 mb-8 text-lg">Join businesses across New Zealand, Australia, the Pacific Islands, India and the UAE who trust SecureIT360 to protect their operations and their directors.</p>
          <a href="/signup" className="inline-block bg-red-600 hover:bg-red-700 text-white font-semibold px-10 py-4 rounded-xl text-lg transition-colors">
            Start Your Free 7-Day Trial
          </a>
          <p className="text-gray-600 text-sm mt-4">No credit card required. No IT team needed. Results in 60 seconds.</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6 py-10">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div>
              <h4 className="text-white font-bold mb-3">SecureIT<span className="text-red-500">360</span></h4>
              <p className="text-gray-500 text-sm">Cyber security for small and medium businesses in New Zealand and Australia.</p>
              <p className="text-gray-600 text-xs mt-3">By Global Cyber Assurance Ltd</p>
            </div>
            <div>
              <h4 className="text-gray-400 font-medium text-sm mb-3">Platform</h4>
              <ul className="space-y-2">
                <li><a href="/signup" className="text-gray-500 hover:text-white text-sm">Start free trial</a></li>
                <li><a href="/login" className="text-gray-500 hover:text-white text-sm">Sign in</a></li>
                <li><a href="#pricing" className="text-gray-500 hover:text-white text-sm">Pricing</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-gray-400 font-medium text-sm mb-3">Legal</h4>
              <ul className="space-y-2">
                <li><a href="/privacy" className="text-gray-500 hover:text-white text-sm">Privacy Policy</a></li>
                <li><a href="/terms" className="text-gray-500 hover:text-white text-sm">Terms of Service</a></li>
                <li><a href="/cookie-policy" className="text-gray-500 hover:text-white text-sm">Cookie Policy</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-gray-400 font-medium text-sm mb-3">Contact</h4>
              <ul className="space-y-2">
                <li><a href="mailto:governance@secureit360.co" className="text-gray-500 hover:text-white text-sm">governance@secureit360.co</a></li>
                <li><p className="text-gray-600 text-xs mt-2">Data stored in Sydney, Australia</p></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 pt-6 text-center">
            <p className="text-gray-600 text-xs">&copy; 2026 Global Cyber Assurance Ltd. All rights reserved. &nbsp;|&nbsp; <a href="/privacy" className="hover:text-gray-400 underline">Privacy</a> &nbsp;|&nbsp; <a href="/terms" className="hover:text-gray-400 underline">Terms</a></p>
          </div>
        </div>
      </footer>

    </main>
  )
}



