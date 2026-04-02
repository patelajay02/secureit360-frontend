// SecureIT360 - Dashboard Page
// This is the main screen every director sees after logging in.
// Shows the Ransom Risk Score, Governance Score and top findings.
// Plain English only - no jargon anywhere.

'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function DashboardPage() {
  const router = useRouter()
  const [dashboard, setDashboard] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [companyName, setCompanyName] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('token')
    const company = localStorage.getItem('company_name')

    if (!token) {
      router.push('/')
      return
    }

    setCompanyName(company || '')
    fetchDashboard(token)
  }, [])

  const fetchDashboard = async (token: string) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/dashboard/`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await response.json()
      setDashboard(data)
    } catch (err) {
      console.error('Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.clear()
    router.push('/')
  }

  // Score ring colour
  const getScoreColor = (score: number) => {
    if (score >= 60) return '#ef4444' // Red
    if (score >= 30) return '#f97316' // Amber
    return '#22c55e' // Green
  }

  const getRiskLabel = (score: number) => {
    if (score >= 60) return 'High Risk'
    if (score >= 30) return 'Medium Risk'
    return 'Low Risk'
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-400 text-lg">Loading your security dashboard...</p>
      </main>
    )
  }

  const ransomScore = dashboard?.ransom_score ?? 0
  const governanceScore = dashboard?.governance_score ?? 0
  const scoreColor = getScoreColor(ransomScore)

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      {/* Top navigation bar */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">
          SecureIT<span className="text-red-500">360</span>
        </h1>
        <div className="flex items-center gap-6">
          <span className="text-gray-400 text-sm">{companyName}</span>
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-white text-sm"
          >
            Sign out
          </button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8">

        {/* Welcome message */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white">
            Your Security Dashboard
          </h2>
          <p className="text-gray-400 mt-1">
            Here is your current cyber security status at a glance.
          </p>
        </div>

        {/* No scan yet message */}
        {!dashboard?.ransom_score && (
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 text-center mb-8">
            <p className="text-gray-300 text-lg mb-2">No scans completed yet.</p>
            <p className="text-gray-500">Run your first scan to see your Ransom Risk Score.</p>
          </div>
        )}

        {/* Main scores row */}
        {dashboard?.ransom_score && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">

            {/* Ransom Risk Score */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <h3 className="text-gray-400 text-sm mb-4 uppercase tracking-wide">
                Ransom Risk Score
              </h3>

              {/* Score ring */}
              <div className="relative inline-flex items-center justify-center mb-4">
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="70" fill="none" stroke="#1f2937" strokeWidth="12"/>
                  <circle
                    cx="80" cy="80" r="70" fill="none"
                    stroke={scoreColor} strokeWidth="12"
                    strokeDasharray={`${(ransomScore / 100) * 440} 440`}
                    strokeLinecap="round"
                    transform="rotate(-90 80 80)"
                  />
                </svg>
                <div className="absolute text-center">
                  <p className="text-4xl font-bold" style={{color: scoreColor}}>
                    {ransomScore}
                  </p>
                  <p className="text-gray-400 text-xs">out of 100</p>
                </div>
              </div>

              <p className="text-lg font-semibold" style={{color: scoreColor}}>
                {getRiskLabel(ransomScore)}
              </p>
              <p className="text-gray-500 text-sm mt-2">
                Higher score = higher risk of ransomware attack
              </p>
            </div>

            {/* If Attacked Today panel */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
              <h3 className="text-gray-400 text-sm mb-4 uppercase tracking-wide">
                If Attacked Today
              </h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                  <span className="text-gray-400 text-sm">Estimated ransom demand</span>
                  <span className="text-white font-semibold">
                    NZD $85K — $220K
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                  <span className="text-gray-400 text-sm">Expected downtime</span>
                  <span className="text-white font-semibold">14 — 28 days</span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                  <span className="text-gray-400 text-sm">Director personal liability</span>
                  <span className="text-red-400 font-semibold">High</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400 text-sm">Regulatory fine exposure</span>
                  <span className="text-red-400 font-semibold">Up to $10M AU</span>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* Findings summary */}
        {dashboard?.findings_summary && (
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-red-400">
                {dashboard.findings_summary.critical}
              </p>
              <p className="text-red-300 text-sm mt-1">Critical issues</p>
            </div>
            <div className="bg-orange-900/20 border border-orange-800 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-orange-400">
                {dashboard.findings_summary.moderate}
              </p>
              <p className="text-orange-300 text-sm mt-1">Moderate issues</p>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-gray-300">
                {dashboard.findings_summary.low}
              </p>
              <p className="text-gray-400 text-sm mt-1">Low issues</p>
            </div>
          </div>
        )}

        {/* Top findings */}
        {dashboard?.top_findings && dashboard.top_findings.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h3 className="text-white font-semibold mb-4">
              Your top security issues
            </h3>
            <div className="space-y-4">
              {dashboard.top_findings.map((finding: any, index: number) => (
                <div key={index} className="border-b border-gray-800 pb-4 last:border-0 last:pb-0">
                  <div className="flex items-start gap-3">
                    <span className={`text-xs px-2 py-1 rounded font-medium mt-0.5 ${
                      finding.severity === 'critical'
                        ? 'bg-red-900/50 text-red-300'
                        : finding.severity === 'moderate'
                        ? 'bg-orange-900/50 text-orange-300'
                        : 'bg-gray-700 text-gray-300'
                    }`}>
                      {finding.severity === 'critical' ? 'Critical' :
                       finding.severity === 'moderate' ? 'Moderate' : 'Low'}
                    </span>
                    <div>
                      <p className="text-white text-sm font-medium">{finding.title}</p>
                      <p className="text-gray-500 text-xs mt-1">{finding.description?.substring(0, 120)}...</p>
                      {finding.governance_gap && (
                        <p className="text-gray-600 text-xs italic mt-2">
                          {finding.governance_gap}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-gray-700 text-xs mt-8">
          © 2026 Global Cyber Assurance. All rights reserved.
        </p>

      </div>
    </main>
  )
}