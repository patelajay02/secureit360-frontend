'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

const VOICE_GUIDE_STEPS: Record<string, string[]> = {
  "Scammers can send emails pretending to be your business": [
    "Log in to wherever you manage your domain name. This is usually GoDaddy, Cloudflare, Crazy Domains, or your web hosting provider.",
    "Find the DNS settings for your domain.",
    "Add a new TXT record. Set the Name to underscore dmarc, and set the Value to: v equals DMARC1 semicolon p equals none semicolon rua equals mailto your email address.",
    "Save the record and wait up to 30 minutes for it to take effect.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Your email domain has no sender protection": [
    "Log in to wherever you manage your domain name.",
    "Find the DNS settings for your domain.",
    "Add a new TXT record. Set the Name to @ and set the Value to: v equals spf1 include colon _spf.google.com tilde all. Replace the Google part with your email provider if you do not use Google.",
    "Save the record and wait up to 30 minutes for it to take effect.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Your website security certificate is invalid or missing": [
    "Contact your website hosting provider and ask them to install or renew your SSL certificate.",
    "If you use Cloudflare, enable the SSL setting in your dashboard under the SSL slash TLS section.",
    "If you manage your own server, use Let's Encrypt to get a free SSL certificate.",
    "Once installed, visit your website and confirm the padlock icon appears in the browser address bar.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Your website is missing basic security protections": [
    "Contact your web developer or hosting provider.",
    "Ask them to add the following security headers to your website: X-Frame-Options, X-Content-Type-Options, Strict-Transport-Security, and Content-Security-Policy.",
    "If you use WordPress, install a security plugin such as Wordfence or iThemes Security which adds these automatically.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Windows remote access is open to the internet - the number one ransomware entry point": [
    "Contact your IT support person immediately. This is a critical issue.",
    "Ask them to close port 3389 on your firewall or router.",
    "If remote access is needed, ask your IT person to set up a VPN instead.",
    "Do not delay this fix. This is the most common way ransomware enters businesses.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Windows file sharing is exposed to the internet": [
    "Contact your IT support person immediately. This is a critical issue.",
    "Ask them to block port 445 on your firewall or router.",
    "Ensure Windows file sharing is not exposed to the public internet.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "No publicly exposed cloud storage found": [
    "This is good news. No action is required.",
    "Continue to ensure any cloud storage your business uses is set to private.",
    "Remind staff never to make business files publicly accessible."
  ],
  "No obvious software vulnerabilities detected on your website": [
    "This is good news. No action is required.",
    "Continue to keep all software, plugins, and themes updated regularly.",
    "Set up automatic updates where possible."
  ]
}

function getVoiceSteps(title: string): string[] {
  for (const key of Object.keys(VOICE_GUIDE_STEPS)) {
    if (title?.toLowerCase().includes(key.toLowerCase().substring(0, 30))) {
      return VOICE_GUIDE_STEPS[key]
    }
  }
  return [
    "Review this finding carefully.",
    "Contact your IT support person or email governance@secureit360.co for personalised help.",
    "Ask them to address the specific issue identified in this finding.",
    "Run your scan again after the fix is applied to confirm it is resolved."
  ]
}

function VoiceGuideModal({ finding, onClose }: { finding: any, onClose: () => void }) {
  const [speaking, setSpeaking] = useState(false)
  const [voicesReady, setVoicesReady] = useState(false)
  const steps = getVoiceSteps(finding.title)

  const fullScript = `${finding.title}. Here is how to fix this step by step. ${steps.map((s, i) => `Step ${i + 1}. ${s}`).join(" ")}`

  useEffect(() => {
    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      if (voices.length > 0) setVoicesReady(true)
    }
    loadVoices()
    window.speechSynthesis.onvoiceschanged = loadVoices
    return () => { window.speechSynthesis.cancel() }
  }, [])

  function handlePlay() {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(fullScript)
    utterance.rate = 0.9
    utterance.pitch = 1
    utterance.volume = 1
    const voices = window.speechSynthesis.getVoices()
    const english = voices.find(v => v.lang === "en-GB") || voices.find(v => v.lang.startsWith("en")) || voices[0]
    if (english) utterance.voice = english
    utterance.onstart = () => setSpeaking(true)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = (e) => { console.error("Speech error", e); setSpeaking(false) }
    window.speechSynthesis.speak(utterance)
  }

  function handleClose() {
    window.speechSynthesis.cancel()
    setSpeaking(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-white font-semibold text-lg pr-4">{finding.title}</h3>
          <button onClick={handleClose} className="text-gray-500 hover:text-white text-xl flex-shrink-0">&#x2715;</button>
        </div>

        <div className="bg-gray-800 rounded-xl p-4 mb-6 text-center">
          <p className="text-gray-400 text-sm mb-3">Click play to hear how to fix this issue</p>
          <button
            onClick={handlePlay}
            className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold text-white transition-colors ${speaking ? "bg-red-700 hover:bg-red-800" : "bg-red-600 hover:bg-red-700"}`}
          >
            {speaking ? (
              <><span className="w-3 h-3 bg-white rounded-sm inline-block"></span> Stop</>
            ) : (
              <><span style={{display:"inline-block",width:0,height:0,borderTop:"8px solid transparent",borderBottom:"8px solid transparent",borderLeft:"14px solid white"}}></span> Play voice guide</>
            )}
          </button>
          {speaking && <p className="text-green-400 text-xs mt-2 animate-pulse">Speaking...</p>}
          {!voicesReady && <p className="text-gray-600 text-xs mt-2">Loading voices...</p>}
        </div>

        <div>
          <h4 className="text-gray-300 font-medium mb-3 text-sm uppercase tracking-wide">Step-by-step instructions</h4>
          <ol className="space-y-3">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="bg-red-900/50 text-red-300 text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</span>
                <p className="text-gray-300 text-sm leading-relaxed">{step}</p>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-800">
          <p className="text-gray-500 text-xs">Need more help? Email <a href="mailto:governance@secureit360.co" className="text-gray-400 underline">governance@secureit360.co</a> and a specialist will walk you through this personally.</p>
        </div>
      </div>
    </div>
  )
} {
  const [speaking, setSpeaking] = useState(false)
  const steps = getVoiceSteps(finding.title)

  const fullScript = `${finding.title}. Here is how to fix this step by step. ${steps.map((s, i) => `Step ${i + 1}. ${s}`).join(' ')}`

  function handlePlay() {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const utterance = new SpeechSynthesisUtterance(fullScript)
    utterance.rate = 0.9
    utterance.pitch = 1
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    const voices = window.speechSynthesis.getVoices()
    if (voices.length > 0) {
      const english = voices.find(v => v.lang.startsWith("en")) || voices[0]
      utterance.voice = english
    }
    window.speechSynthesis.cancel()
    setTimeout(() => {
      window.speechSynthesis.speak(utterance)
      setSpeaking(true)
    }, 100)
  }

  function handleClose() {
    window.speechSynthesis.cancel()
    setSpeaking(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-white font-semibold text-lg pr-4">{finding.title}</h3>
          <button onClick={handleClose} className="text-gray-500 hover:text-white text-xl flex-shrink-0">&#x2715;</button>
        </div>

        <div className="bg-gray-800 rounded-xl p-4 mb-6 text-center">
          <p className="text-gray-400 text-sm mb-3">Click play to hear how to fix this issue</p>
          <button
            onClick={handlePlay}
            className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold text-white transition-colors ${speaking ? 'bg-red-700 hover:bg-red-800' : 'bg-red-600 hover:bg-red-700'}`}
          >
            {speaking ? (
              <>
                <span className="w-3 h-3 bg-white rounded-sm inline-block"></span>
                Stop
              </>
            ) : (
              <>
                <span className="w-0 h-0 border-t-8 border-b-8 border-l-12 border-transparent border-l-white inline-block" style={{borderLeftWidth: '14px'}}></span>
                Play voice guide
              </>
            )}
          </button>
          {speaking && (
            <p className="text-green-400 text-xs mt-2 animate-pulse">Speaking...</p>
          )}
        </div>

        <div>
          <h4 className="text-gray-300 font-medium mb-3 text-sm uppercase tracking-wide">Step-by-step instructions</h4>
          <ol className="space-y-3">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="bg-red-900/50 text-red-300 text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</span>
                <p className="text-gray-300 text-sm leading-relaxed">{step}</p>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-800">
          <p className="text-gray-500 text-xs">Need more help? Email <a href="mailto:governance@secureit360.co" className="text-gray-400 underline">governance@secureit360.co</a> and a specialist will walk you through this personally.</p>
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const router = useRouter()
  const [dashboard, setDashboard] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [companyName, setCompanyName] = useState('')
  const [country, setCountry] = useState('NZ')
  const [plan, setPlan] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [trialEndsAt, setTrialEndsAt] = useState<string | null>(null)
  const [voiceFinding, setVoiceFinding] = useState<any>(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const company = localStorage.getItem('company_name')
    if (!token) {
      router.push('/')
      return
    }
    setCompanyName(company || '')
    setCountry(localStorage.getItem('country') || 'NZ')
    setPlan(localStorage.getItem('plan'))
    setStatus(localStorage.getItem('status'))
    setTrialEndsAt(localStorage.getItem('trial_ends_at'))
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

  const isTrial = status === 'trial'

  const getTrialDaysLeft = () => {
    if (!trialEndsAt) return 0
    const end = new Date(trialEndsAt)
    const now = new Date()
    const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
    return Math.max(0, diff)
  }

  const getScoreColor = (score: number) => {
    if (score >= 60) return '#ef4444'
    if (score >= 30) return '#f97316'
    return '#22c55e'
  }

  const getRiskLabel = (score: number) => {
    if (score >= 60) return 'High Risk'
    if (score >= 30) return 'Medium Risk'
    return 'Low Risk'
  }

  const getGovernanceLabel = (score: number) => {
    if (score > 50) return 'Governance gaps found'
    if (score > 25) return 'Some gaps detected'
    return 'Looking good'
  }

  const getLiabilityColor = (liability: string) => {
    if (liability === 'High') return 'text-red-400'
    if (liability === 'Medium') return 'text-amber-400'
    return 'text-green-400'
  }

  const getFixButton = (fixType: string, finding: any) => {
    switch(fixType) {
      case 'auto':
        return (
          <span className="text-xs px-2 py-1 rounded font-medium bg-green-900/50 text-green-300">
            Auto-fixed
          </span>
        )
      case 'voice':
        return (
          <button
            onClick={() => setVoiceFinding(finding)}
            className="text-xs px-2 py-1 rounded font-medium bg-amber-900/50 text-amber-300 hover:bg-amber-900"
          >
            Voice guide
          </button>
        )
      case 'specialist':
        return (
          <button
            onClick={() => window.location.href = 'mailto:governance@secureit360.co'}
            className="text-xs px-2 py-1 rounded font-medium bg-red-900/50 text-red-300 hover:bg-red-900"
          >
            Get specialist
          </button>
        )
      default:
        return null
    }
  }

  const getComplianceStatus = (score: number) => {
    if (score >= 70) return 'On track'
    if (score >= 40) return 'Gaps found'
    return 'Non-compliant'
  }

  const getComplianceColor = (score: number) => {
    if (score >= 70) return 'text-green-400'
    if (score >= 40) return 'text-amber-400'
    return 'text-red-400'
  }

  const getComplianceTextColor = (score: number) => {
    if (score >= 70) return 'text-green-500'
    if (score >= 40) return 'text-amber-500'
    return 'text-red-500'
  }

  const getRegulations = (compliance: any, country: string) => {
    switch(country) {
      case 'AU':
        return [
          { name: 'AU Privacy Act 1988', score: compliance?.au_privacy ?? 0, detail: 'Amended Dec 2024 - up to $50M fine' },
          { name: 'AU Privacy Amendment 2024', score: compliance?.au_privacy_amendment ?? 0, detail: 'On-the-spot fines - no court needed' },
          { name: 'AU Cyber Security Act 2024', score: compliance?.au_cyber_security_act ?? 0, detail: 'Incident reporting readiness - 72hr obligation' },
          { name: 'AU Corporations Act', score: compliance?.au_corporations ?? 0, detail: 'Director personal liability' },
          { name: 'Essential Eight', score: compliance?.essential_eight ?? 0, detail: 'Mandatory for government, recommended all' },
          { name: 'ISO 27001', score: compliance?.iso_27001 ?? 0, detail: 'International security standard' },
        ]
      case 'UAE':
        return [
          { name: 'UAE PDPL 2021', score: compliance?.uae_pdpl ?? 0, detail: 'Personal data protection - up to AED 5M' },
          { name: 'UAE NESA Standards', score: compliance?.uae_nesa ?? 0, detail: 'National cybersecurity standards' },
          { name: 'ISO 27001', score: compliance?.iso_27001 ?? 0, detail: 'International security standard' },
        ]
      case 'IN':
        return [
          { name: 'India DPDP Act 2023', score: compliance?.india_dpdp ?? 0, detail: 'Digital Personal Data Protection - up to Rs 250Cr' },
          { name: 'CERT-In Guidelines 2022', score: compliance?.cert_in ?? 0, detail: 'Incident reporting within 6 hours' },
          { name: 'ISO 27001', score: compliance?.iso_27001 ?? 0, detail: 'International security standard' },
        ]
      default:
        return [
          { name: 'NZ Privacy Act 2020', score: compliance?.nz_privacy ?? 0, detail: 'Breach notification within 72 hours' },
          { name: 'NZ Privacy Amendment 2025', score: compliance?.nz_privacy_amendment ?? 0, detail: 'IPP 3A - in force May 2026' },
          { name: 'NZ Companies Act', score: compliance?.nz_companies ?? 0, detail: 'Director duty of care' },
          { name: 'NZ NCSC Guidelines', score: compliance?.nz_ncsc ?? 0, detail: 'Baseline security controls' },
          { name: 'Essential Eight', score: compliance?.essential_eight ?? 0, detail: '8 mitigation strategies' },
          { name: 'ISO 27001', score: compliance?.iso_27001 ?? 0, detail: 'International security standard' },
        ]
    }
  }

  const getCountryLabel = (country: string) => {
    switch(country) {
      case 'AU': return 'Australian regulations'
      case 'UAE': return 'UAE regulations'
      case 'IN': return 'Indian regulations'
      default: return 'New Zealand regulations'
    }
  }

  const filterRegulations = (regulations: string[], country: string) => {
    if (country === 'AU') return regulations.filter((r: string) => !r.startsWith('NZ'))
    if (country === 'NZ') return regulations.filter((r: string) => !r.startsWith('AU'))
    if (country === 'UAE') return regulations.filter((r: string) => r.startsWith('UAE') || r.startsWith('ISO'))
    if (country === 'IN') return regulations.filter((r: string) => r.startsWith('India') || r.startsWith('CERT') || r.startsWith('ISO'))
    return regulations
  }

  const isCarriedOver = (finding: any) => {
    if (!finding.updated_at || !finding.created_at) return false
    const created = new Date(finding.created_at).getTime()
    const updated = new Date(finding.updated_at).getTime()
    return updated > created
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
  const penaltyInfo = dashboard?.penalty_info
  const regulations = getRegulations(dashboard?.compliance, country)
  const trialDaysLeft = getTrialDaysLeft()

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      {voiceFinding && (
        <VoiceGuideModal finding={voiceFinding} onClose={() => setVoiceFinding(null)} />
      )}

      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">
          SecureIT<span className="text-red-500">360</span>
        </h1>
        <div className="flex items-center gap-6">
          <a href="/dashboard" className="text-gray-400 hover:text-white text-sm">Dashboard</a>
          <a href="/dashboard/scanning" className="text-gray-400 hover:text-white text-sm">Run Scan</a>
          <a href="/settings" className="text-gray-400 hover:text-white text-sm">Settings</a>
          <a href="/pricing" className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded-lg font-medium">Upgrade</a>
          <span className="text-gray-400 text-sm">{companyName}</span>
          <button onClick={handleLogout} className="text-gray-400 hover:text-white text-sm">Sign out</button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8">

        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white">Your Security Dashboard</h2>
          <p className="text-gray-400 mt-1">Here is your current cyber security status at a glance.</p>
        </div>

        {isTrial && (
          <div className="bg-gray-900 border border-red-800 rounded-2xl p-6 mb-8 text-center">
            <p className="text-red-400 font-semibold text-lg mb-1">
              Free trial — {trialDaysLeft > 0 ? `${trialDaysLeft} day${trialDaysLeft === 1 ? '' : 's'} remaining` : 'expires today'}
            </p>
            <p className="text-gray-400 text-sm mb-4">Your free trial includes Dark Web and Email Security scans only. Upgrade to unlock all 6 scan engines, full Ransom Risk Score, Governance Score, and regulatory compliance mapping.</p>
            <a href="/pricing" className="inline-block bg-red-600 hover:bg-red-700 text-white font-semibold px-8 py-3 rounded-lg">
              Subscribe Now — from $250 NZD/month + GST
            </a>
          </div>
        )}

        {!dashboard?.findings_summary && (
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 text-center mb-8">
            <p className="text-gray-300 text-lg mb-2">No scans completed yet.</p>
            <p className="text-gray-500 mb-6">Run your first scan to see your security risk score, compliance status, and what needs fixing.</p>
            <a href="/dashboard/scanning" className="inline-block bg-red-600 hover:bg-red-700 text-white font-semibold px-6 py-3 rounded-lg text-sm">
              Run Your First Scan
            </a>
          </div>
        )}

        {dashboard?.ransom_score && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <h3 className="text-gray-400 text-sm mb-4 uppercase tracking-wide">Ransom Risk Score</h3>
              <div className="relative inline-flex items-center justify-center mb-4">
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="70" fill="none" stroke="#1f2937" strokeWidth="12"/>
                  <circle cx="80" cy="80" r="70" fill="none" stroke={scoreColor} strokeWidth="12"
                    strokeDasharray={`${(ransomScore / 100) * 440} 440`}
                    strokeLinecap="round" transform="rotate(-90 80 80)"/>
                </svg>
                <div className="absolute text-center">
                  <p className="text-4xl font-bold" style={{color: scoreColor}}>{ransomScore}</p>
                  <p className="text-gray-400 text-xs">out of 100</p>
                </div>
              </div>
              <p className="text-lg font-semibold" style={{color: scoreColor}}>{getRiskLabel(ransomScore)}</p>
              <p className="text-gray-500 text-sm mt-2">Higher score = higher risk of ransomware attack</p>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <h3 className="text-gray-400 text-sm mb-4 uppercase tracking-wide">Governance Score</h3>
              <div className="relative inline-flex items-center justify-center mb-4">
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="70" fill="none" stroke="#1f2937" strokeWidth="12"/>
                  <circle cx="80" cy="80" r="70" fill="none" stroke="#a855f7" strokeWidth="12"
                    strokeDasharray={`${(governanceScore / 100) * 440} 440`}
                    strokeLinecap="round" transform="rotate(-90 80 80)"/>
                </svg>
                <div className="absolute text-center">
                  <p className="text-4xl font-bold" style={{color: '#a855f7'}}>{governanceScore}</p>
                  <p className="text-gray-400 text-xs">out of 100</p>
                </div>
              </div>
              <p className="text-lg font-semibold" style={{color: '#a855f7'}}>{getGovernanceLabel(governanceScore)}</p>
              <p className="text-gray-500 text-sm mt-2">Policy and process gaps that technical fixes alone cannot resolve.</p>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h3 className="text-gray-400 text-sm mb-4 uppercase tracking-wide">If Attacked Today</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                  <span className="text-gray-400 text-sm">Estimated ransom demand</span>
                  <span className="text-white font-semibold text-sm">{penaltyInfo?.ransom_demand}</span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                  <span className="text-gray-400 text-sm">Expected downtime</span>
                  <span className="text-white font-semibold text-sm">14 - 28 days</span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-800 pb-3">
                  <span className="text-gray-400 text-sm">Director personal liability</span>
                  <span className={`font-semibold text-sm ${getLiabilityColor(penaltyInfo?.liability ?? 'High')}`}>
                    {penaltyInfo?.liability ?? 'High'}
                  </span>
                </div>
                <div className="border-b border-gray-800 pb-3">
                  <p className="text-gray-400 text-xs mb-2 uppercase tracking-wide">Indicative regulatory exposure</p>
                  <p className="text-sm mb-1">{penaltyInfo?.fine_exposure}</p>
                  {penaltyInfo?.fine_if_moderate && <p className="text-sm mb-1 text-gray-400">{penaltyInfo.fine_if_moderate}</p>}
                  {penaltyInfo?.fine_if_low && <p className="text-sm text-gray-400">{penaltyInfo.fine_if_low}</p>}
                </div>
                {penaltyInfo?.residual_risk && (
                  <div className="border-b border-gray-800 pb-3">
                    <p className="text-gray-500 text-xs">{penaltyInfo.residual_risk}</p>
                  </div>
                )}
                {penaltyInfo?.ransom_reporting && (
                  <div>
                    <p className="text-gray-500 text-xs">{penaltyInfo.ransom_reporting}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {dashboard?.findings_summary && (
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-red-400">{dashboard.findings_summary.critical}</p>
              <p className="text-red-300 text-sm mt-1">Critical issues</p>
            </div>
            <div className="bg-orange-900/20 border border-orange-800 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-orange-400">{dashboard.findings_summary.moderate}</p>
              <p className="text-orange-300 text-sm mt-1">Moderate issues</p>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-gray-300">{dashboard.findings_summary.low}</p>
              <p className="text-gray-400 text-sm mt-1">Low issues</p>
            </div>
          </div>
        )}

        {dashboard?.ransom_score && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-white font-semibold">Regulatory Compliance</h3>
              <span className="text-gray-500 text-xs">{getCountryLabel(country)}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {regulations.map((reg, index) => (
                <div key={index} className="bg-gray-800 rounded-xl p-4">
                  <p className="text-gray-300 text-xs font-medium mb-1">{reg.name}</p>
                  <p className="text-gray-500 text-xs mb-2">{reg.detail}</p>
                  <p className={`text-2xl font-bold ${getComplianceColor(reg.score)}`}>{reg.score}%</p>
                  <p className={`text-xs mt-1 ${getComplianceTextColor(reg.score)}`}>{getComplianceStatus(reg.score)}</p>
                </div>
              ))}
            </div>
            {penaltyInfo?.key_law && (
              <p className="text-gray-600 text-xs mt-4 italic">Current legislation: {penaltyInfo.key_law}</p>
            )}
          </div>
        )}

        {dashboard?.top_findings && dashboard.top_findings.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h3 className="text-white font-semibold mb-4">Your top security issues</h3>
            <div className="space-y-4">
              {dashboard.top_findings.map((finding: any, index: number) => (
                <div key={index} className="border-b border-gray-800 pb-4 last:border-0 last:pb-0">
                  <div className="flex items-start gap-3">
                    <span className={`text-xs px-2 py-1 rounded font-medium mt-0.5 flex-shrink-0 ${
                      finding.severity === 'critical' ? 'bg-red-900/50 text-red-300' :
                      finding.severity === 'moderate' ? 'bg-orange-900/50 text-orange-300' :
                      'bg-gray-700 text-gray-300'
                    }`}>
                      {finding.severity === 'critical' ? 'Critical' :
                       finding.severity === 'moderate' ? 'Moderate' : 'Low'}
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-white text-sm font-medium">{finding.title}</p>
                        {isCarriedOver(finding) && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-900/40 text-amber-400 border border-amber-800">
                            Not fixed since last scan
                          </span>
                        )}
                      </div>
                      <p className="text-gray-500 text-xs mt-1">{finding.description?.substring(0, 120)}...</p>
                      {finding.governance_gap && (
                        <p className="text-gray-600 text-xs italic mt-2">{finding.governance_gap}</p>
                      )}
                      {finding.regulations && finding.regulations.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {filterRegulations(finding.regulations, country).map((reg: string, i: number) => (
                            <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">
                              {reg}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="mt-2">
                        {getFixButton(finding.fix_type, finding)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 pt-4 border-t border-gray-800">
              <p className="text-gray-500 text-xs">
                Not sure what to do next? Email us at{' '}
                <a href="mailto:governance@secureit360.co" className="text-gray-400 hover:text-white underline">
                  governance@secureit360.co
                </a>
                {' '}and a qualified cyber security specialist will review your results and explain exactly what your business needs - in plain English, no jargon, no obligation.
              </p>
            </div>
          </div>
        )}

        {dashboard?.ransom_score && penaltyInfo?.disclaimer && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mt-6">
            <p className="text-gray-600 text-xs leading-relaxed">
              <span className="text-gray-500 font-medium">Important: </span>
              {penaltyInfo.disclaimer}
            </p>
          </div>
        )}

        <p className="text-center text-gray-700 text-xs mt-8">
          &copy; 2026 Global Cyber Assurance. All rights reserved.
        </p>

      </div>
    </main>
  )
}


