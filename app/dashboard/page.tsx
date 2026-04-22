'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

const VOICE_GUIDE_STEPS: Record<string, string[]> = {
  "Scammers can send emails pretending to be your business": [
    "Log in to wherever you manage your domain name. This is usually GoDaddy, Cloudflare, Crazy Domains, or your web hosting provider.",
    "Find the DNS settings for your domain.",
    "Add a new TXT record. Set the Name to _dmarc and set the Value to: v=DMARC1; p=none; rua=mailto:your@email.com",
    "Save the record and wait up to 30 minutes for it to take effect.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Your email domain has no sender protection": [
    "Log in to wherever you manage your domain name.",
    "Find the DNS settings for your domain.",
    "Add a new TXT record. Set the Name to @ and set the Value to: v=spf1 include:_spf.google.com ~all",
    "Save the record and wait up to 30 minutes for it to take effect.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Your website security certificate is invalid or missing": [
    "Contact your website hosting provider and ask them to install or renew your SSL certificate.",
    "If you use Cloudflare, enable SSL in your dashboard under the SSL/TLS section.",
    "If you manage your own server, use Lets Encrypt to get a free SSL certificate.",
    "Once installed, visit your website and confirm the padlock icon appears in the browser address bar.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Your website is missing basic security protections": [
    "Contact your web developer or hosting provider.",
    "Ask them to add security headers to your website: X-Frame-Options, X-Content-Type-Options, Strict-Transport-Security, and Content-Security-Policy.",
    "If you use WordPress, install a security plugin such as Wordfence which adds these automatically.",
    "Run your scan again to confirm this issue is resolved."
  ],
  "Windows remote access is open to the internet": [
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
  "Google MFA not enabled": [
    "Log in to admin.google.com.",
    "Go to Security then 2-Step Verification.",
    "Find each flagged user in the Users section and click their account.",
    "Under Security, confirm 2-Step Verification is enrolled.",
    "To enforce 2SV for all users, go to Security then Authentication then 2-Step Verification and set Enforcement to On.",
    "Run your scan again to confirm resolved."
  ],
  "inactive Google Workspace accounts": [
    "Log in to admin.google.com.",
    "Go to Directory then Users.",
    "Search for each flagged account by name.",
    "Click the account and select Suspend user to immediately prevent access.",
    "For accounts that should be permanently removed, select Delete user instead.",
    "Run your scan again to confirm resolved."
  ],
  "Google admin privilege": [
    "Log in to admin.google.com.",
    "Go to Directory then Users.",
    "Click each flagged admin account.",
    "Select Admin roles and privileges.",
    "Remove Super Admin and assign a more limited role only if administrative access is still needed.",
    "Run your scan again to confirm resolved."
  ],
  "inactive Microsoft 365 accounts": [
    "Log in to admin.microsoft.com.",
    "Go to Users then Active Users.",
    "Search for each flagged account by name.",
    "Click the account and select Block sign-in to immediately prevent access.",
    "For accounts that should be deleted, select Delete user instead.",
    "Run your scan again to confirm resolved."
  ],
  "MFA not enabled": [
    "Log in to admin.microsoft.com.",
    "Go to Users then Active Users.",
    "Click Multi-factor authentication at the top.",
    "Find each flagged user and enable MFA.",
    "The user will be prompted to set up MFA on next login.",
    "Run your scan again to confirm resolved."
  ],
  "admin privilege": [
    "Log in to admin.microsoft.com.",
    "Go to Users then Active Users.",
    "Click each flagged admin account.",
    "Select Manage roles.",
    "Remove Global Administrator and assign a more limited role like User Administrator only if needed.",
    "Run your scan again to confirm resolved."
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

const REAUTH_TTL_MS = 15 * 60 * 1000
const REAUTH_KEY = 'ms365_reauth_ts'

function isReauthValid(): boolean {
  try {
    const ts = sessionStorage.getItem(REAUTH_KEY)
    return !!ts && Date.now() - parseInt(ts, 10) < REAUTH_TTL_MS
  } catch { return false }
}

function markReauthValid() {
  try { sessionStorage.setItem(REAUTH_KEY, String(Date.now())) } catch {}
}

function ReauthModal({ onVerified, onClose }: { onVerified: () => void, onClose: () => void }) {
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function handleSubmit(e: { preventDefault(): void }) {
    e.preventDefault()
    setLoading(true)
    setErr('')
    try {
      const token = localStorage.getItem('token') || ''
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/verify-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ password }),
      })
      if (!res.ok) { setErr('Incorrect password. Please try again.'); return }
      markReauthValid()
      onVerified()
    } catch {
      setErr('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 w-full max-w-sm">
        <div className="flex justify-between items-start mb-1">
          <h3 className="text-white font-semibold text-lg">Confirm your identity</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl">✕</button>
        </div>
        <p className="text-gray-400 text-sm mb-5">
          This finding contains personal data (user names and emails). Re-enter your password to view the affected accounts.
        </p>
        {err && <p className="text-red-400 text-sm mb-3">{err}</p>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your password"
            required
            autoFocus
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500 text-sm"
          />
          <div className="flex gap-3">
            <button type="submit" disabled={loading || !password}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-3 rounded-lg text-sm disabled:opacity-50">
              {loading ? 'Verifying...' : 'Confirm'}
            </button>
            <button type="button" onClick={onClose}
              className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg text-sm">
              Cancel
            </button>
          </div>
        </form>
        <p className="text-gray-600 text-xs mt-4 text-center">Access is cached for 15 minutes.</p>
      </div>
    </div>
  )
}

function MS365DetailsModal({ finding, onClose }: { finding: any, onClose: () => void }) {
  const users: any[] = finding?.metadata?.affected_users || []
  const [copiedEmail, setCopiedEmail] = useState<string | null>(null)

  async function copyEmail(email: string) {
    try {
      await navigator.clipboard.writeText(email)
      setCopiedEmail(email)
      setTimeout(() => setCopiedEmail(null), 2000)
    } catch {}
  }

  function adminCenterUrl(u: any, engine?: string): string {
    if (u.google_user_id) {
      return `https://admin.google.com/ac/users/${u.google_user_id}`
    }
    if (u.azure_object_id) {
      return `https://admin.microsoft.com/Adminportal/Home#/users/:/UserDetails/${u.azure_object_id}`
    }
    if (engine === 'google_workspace') {
      return `https://admin.google.com/ac/users`
    }
    return `https://admin.microsoft.com/Adminportal/Home#/users`
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-white font-semibold text-lg pr-4">{finding.title}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl flex-shrink-0">✕</button>
        </div>
        <p className="text-gray-400 text-sm mb-5">{finding.description}</p>
        {users.length > 0 ? (
          <div>
            <p className="text-gray-500 text-xs uppercase tracking-wide mb-3">Affected accounts ({users.length})</p>
            <div className="space-y-2">
              {users.map((u, i) => (
                <div key={i} className="bg-gray-800 rounded-xl px-4 py-3 flex flex-col gap-2">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">{u.name || 'Unknown'}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <p className="text-gray-400 text-xs truncate">{u.email || '—'}</p>
                        {u.email && (
                          <button
                            onClick={() => copyEmail(u.email)}
                            className="text-xs px-1.5 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white flex-shrink-0 transition-colors"
                          >
                            {copiedEmail === u.email ? 'Copied!' : 'Copy'}
                          </button>
                        )}
                      </div>
                      {u.roles && <p className="text-gray-500 text-xs mt-0.5">Roles: {u.roles}</p>}
                      {u.last_login && u.last_login !== 'Never' && (
                        <p className="text-gray-600 text-xs mt-0.5">
                          Last login: {new Date(u.last_login).toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </p>
                      )}
                      {u.last_login === 'Never' && <p className="text-gray-600 text-xs mt-0.5">Last login: Never</p>}
                    </div>
                    <span className="text-xs px-2 py-1 rounded bg-amber-900/40 text-amber-300 border border-amber-800 flex-shrink-0 self-start">
                      {u.recommended_action}
                    </span>
                  </div>
                  <a
                    href={adminCenterUrl(u, finding.engine)}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs px-3 py-1.5 rounded-lg bg-blue-900/30 hover:bg-blue-900/50 text-blue-400 border border-blue-800/60 transition-colors self-start"
                  >
                    Manage in Admin Center →
                  </a>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No detailed user data available.</p>
        )}
        <div className="mt-6 pt-4 border-t border-gray-800">
          <p className="text-gray-500 text-xs">Need help? Email <a href="mailto:governance@secureit360.co" className="text-gray-400 underline">governance@secureit360.co</a></p>
        </div>
      </div>
    </div>
  )
}

function VoiceGuideModal({ finding, onClose }: { finding: any, onClose: () => void }) {
  const [speaking, setSpeaking] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [paused, setPaused] = useState(false)
  const [done, setDone] = useState<boolean[]>([])
  const steps = getVoiceSteps(finding.title)

  useEffect(() => {
    window.speechSynthesis.getVoices()
    setDone(new Array(steps.length).fill(false))
    return () => { window.speechSynthesis.cancel() }
  }, [])

  function speakStep(stepIndex: number) {
    window.speechSynthesis.cancel()
    if (stepIndex >= steps.length) {
      setSpeaking(false)
      setPaused(false)
      return
    }
    setCurrentStep(stepIndex)
    const text = 'Step ' + (stepIndex + 1) + ' of ' + steps.length + '. ' + steps[stepIndex]
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.8
    utterance.pitch = 1
    utterance.volume = 1
    const voices = window.speechSynthesis.getVoices()
    const english = voices.find((v) => v.lang === 'en-GB') || voices.find((v) => v.lang.startsWith('en')) || voices[0]
    if (english) utterance.voice = english
    utterance.onend = () => {
      const next = stepIndex + 1
      if (next < steps.length) {
        speakStep(next)
      } else {
        setSpeaking(false)
        setPaused(false)
      }
    }
    utterance.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }

  function handlePlay() {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      setPaused(true)
      return
    }
    setSpeaking(true)
    setPaused(false)
    setTimeout(() => speakStep(currentStep), 200)
  }

  function handlePlayAgain() {
    window.speechSynthesis.cancel()
    setCurrentStep(0)
    setPaused(false)
    setSpeaking(true)
    setTimeout(() => speakStep(0), 200)
  }

  function handleNext() {
    const next = currentStep + 1
    if (next >= steps.length) return
    window.speechSynthesis.cancel()
    setCurrentStep(next)
    if (speaking) {
      setTimeout(() => speakStep(next), 200)
    }
  }

  function handlePrev() {
    const prev = currentStep - 1
    if (prev < 0) return
    window.speechSynthesis.cancel()
    setCurrentStep(prev)
    if (speaking) {
      setTimeout(() => speakStep(prev), 200)
    }
  }

  function toggleDone(i: number) {
    const updated = [...done]
    updated[i] = !updated[i]
    setDone(updated)
  }

  function handleClose() {
    window.speechSynthesis.cancel()
    setSpeaking(false)
    setPaused(false)
    setCurrentStep(0)
    onClose()
  }

  const completedCount = done.filter(Boolean).length

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 max-w-lg w-full max-h-screen overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-white font-semibold text-lg pr-4">{finding.title}</h3>
          <button onClick={handleClose} className="text-gray-500 hover:text-white text-xl flex-shrink-0">X</button>
        </div>

        <div className="bg-gray-800 rounded-xl p-4 mb-4">
          <div className="flex justify-between items-center mb-3">
            <p className="text-gray-400 text-sm">
              {speaking
                ? 'Reading step ' + (currentStep + 1) + ' of ' + steps.length
                : paused
                ? 'Paused at step ' + (currentStep + 1) + ' of ' + steps.length
                : 'Step ' + (currentStep + 1) + ' of ' + steps.length}
            </p>
            <span className="text-xs text-green-400 font-medium">{completedCount} of {steps.length} done</span>
          </div>

          <div className="w-full bg-gray-700 rounded-full h-1.5 mb-4">
            <div
              className="bg-green-500 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${(completedCount / steps.length) * 100}%` }}
            />
          </div>

          <div className="flex justify-center gap-2 flex-wrap">
            <button onClick={handlePrev} disabled={currentStep === 0}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-gray-700 hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
              Prev
            </button>
            <button onClick={handlePlay}
              className={`px-5 py-2 rounded-lg font-semibold text-white text-sm transition-colors ${speaking ? 'bg-amber-600 hover:bg-amber-700' : 'bg-red-600 hover:bg-red-700'}`}>
              {speaking ? 'Pause' : paused ? 'Resume' : 'Play'}
            </button>
            <button onClick={handleNext} disabled={currentStep >= steps.length - 1}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-gray-700 hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
              Next
            </button>
            <button onClick={handlePlayAgain}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-gray-600 hover:bg-gray-500 transition-colors">
              Restart
            </button>
          </div>
          {speaking && <p className="text-green-400 text-xs mt-3 text-center">Speaking step {currentStep + 1}...</p>}
        </div>

        <div>
          <h4 className="text-gray-300 font-medium mb-3 text-sm uppercase tracking-wide">Steps</h4>
          <ol className="space-y-2">
            {steps.map((step, i) => (
              <li key={i} className={`flex gap-3 rounded-lg p-3 transition-colors border ${
                i === currentStep && speaking ? 'bg-red-900/20 border-red-900/40' :
                done[i] ? 'bg-green-900/10 border-green-900/30' : 'border-transparent'
              }`}>
                <input type="checkbox" checked={done[i] || false} onChange={() => toggleDone(i)}
                  className="mt-1 flex-shrink-0 accent-green-500 w-4 h-4 cursor-pointer" />
                <div className="flex-1">
                  <span className={`text-xs font-bold mr-2 ${i === currentStep && speaking ? 'text-red-400' : 'text-gray-500'}`}>{i + 1}.</span>
                  <span className={`text-sm leading-relaxed ${done[i] ? 'line-through text-gray-500' : i === currentStep && speaking ? 'text-white font-medium' : 'text-gray-300'}`}>{step}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>

        {completedCount === steps.length && (
          <div className="mt-4 bg-green-900/30 border border-green-800 rounded-xl p-4 text-center">
            <p className="text-green-400 font-semibold text-sm">All steps completed!</p>
            <p className="text-gray-400 text-xs mt-1">Run your scan again to confirm this issue is resolved.</p>
          </div>
        )}

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
  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [reauthPending, setReauthPending] = useState<any>(null)
  const [detailsFinding, setDetailsFinding] = useState<any>(null)

  function handleViewDetails(finding: any) {
    if (isReauthValid()) {
      setDetailsFinding(finding)
    } else {
      setReauthPending(finding)
    }
  }

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
    setLogoUrl(localStorage.getItem('logo_url'))
    fetchDashboard(token)
  }, [])

  const fetchDashboard = async (token: string) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/dashboard/`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await response.json()
      setDashboard(data)
      if (data.logo_url) {
        setLogoUrl(data.logo_url)
        localStorage.setItem('logo_url', data.logo_url)
      }
      if (data.status) {
        setStatus(data.status)
        localStorage.setItem('status', data.status)
      }
      if (data.trial_ends_at) {
        setTrialEndsAt(data.trial_ends_at)
        localStorage.setItem('trial_ends_at', data.trial_ends_at)
      }
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

  const getInitials = (name: string) => {
    return name.split(' ').map(w => w[0]).join('').toUpperCase().substring(0, 2)
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

  const getDlsColor = (score: number) => {
    if (score >= 60) return '#ef4444'
    if (score >= 30) return '#f97316'
    return '#22c55e'
  }

  const getDlsLabel = (score: number) => {
    if (score >= 60) return 'High Exposure'
    if (score >= 30) return 'Medium Exposure'
    return 'Low Exposure'
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
        return <span className="text-xs px-2 py-1 rounded font-medium bg-green-900/50 text-green-300">Auto-fixed</span>
      case 'info':
        return <span className="text-xs px-2 py-1 rounded font-medium bg-green-900/50 text-green-300">Passed</span>
      case 'voice':
        return (
          <button onClick={() => setVoiceFinding(finding)} className="text-xs px-2 py-1 rounded font-medium bg-amber-900/50 text-amber-300 hover:bg-amber-900">
            Voice guide
          </button>
        )
      case 'specialist':
        return (
          <button onClick={() => window.location.href = 'mailto:governance@secureit360.co'} className="text-xs px-2 py-1 rounded font-medium bg-red-900/50 text-red-300 hover:bg-red-900">
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
    if (finding.fix_type === 'info') return false
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
  const dlsScore = dashboard?.director_liability_score ?? 0
  const scoreColor = getScoreColor(ransomScore)
  const dlsColor = getDlsColor(dlsScore)
  const penaltyInfo = dashboard?.penalty_info
  const regulations = getRegulations(dashboard?.compliance, country)
  const trialDaysLeft = getTrialDaysLeft()

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      {voiceFinding && (
        <VoiceGuideModal finding={voiceFinding} onClose={() => setVoiceFinding(null)} />
      )}
      {reauthPending && (
        <ReauthModal
          onVerified={() => { setDetailsFinding(reauthPending); setReauthPending(null) }}
          onClose={() => setReauthPending(null)}
        />
      )}
      {detailsFinding && (
        <MS365DetailsModal finding={detailsFinding} onClose={() => setDetailsFinding(null)} />
      )}

      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">SecureIT<span className="text-red-500">360</span></h1>
          <div className="hidden md:flex items-center gap-6">
            <a href="/dashboard" className="text-gray-400 hover:text-white text-sm">Dashboard</a>
            <a href="/dashboard/scanning" className="text-gray-400 hover:text-white text-sm">Run Scan</a>
            <a href="/settings" className="text-gray-400 hover:text-white text-sm">Settings</a>
            <a href="/pricing" className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded-lg font-medium">Upgrade</a>
            <div className="flex items-center gap-2">
              {logoUrl ? (
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
            <a href="/settings" className="text-gray-400 hover:text-white text-sm">Settings</a>
            <a href="/pricing" className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded-lg font-medium w-fit">Upgrade</a>
            <div className="flex items-center gap-2">
              {logoUrl ? (
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
            <a href="/dashboard/scanning" className="inline-block bg-red-600 hover:bg-red-700 text-white font-semibold px-6 py-3 rounded-lg text-sm">Run Your First Scan</a>
          </div>
        )}

        {dashboard?.ransom_score && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
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

              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
                <h3 className="text-gray-400 text-sm mb-4 uppercase tracking-wide">Director Liability Score</h3>
                <div className="relative inline-flex items-center justify-center mb-4">
                  <svg width="160" height="160" viewBox="0 0 160 160">
                    <circle cx="80" cy="80" r="70" fill="none" stroke="#1f2937" strokeWidth="12"/>
                    <circle cx="80" cy="80" r="70" fill="none" stroke={dlsColor} strokeWidth="12"
                      strokeDasharray={`${(dlsScore / 100) * 440} 440`}
                      strokeLinecap="round" transform="rotate(-90 80 80)"/>
                  </svg>
                  <div className="absolute text-center">
                    <p className="text-4xl font-bold" style={{color: dlsColor}}>{dlsScore}</p>
                    <p className="text-gray-400 text-xs">out of 100</p>
                  </div>
                </div>
                <p className="text-lg font-semibold" style={{color: dlsColor}}>{getDlsLabel(dlsScore)}</p>
                <p className="text-gray-500 text-sm mt-2">Personal exposure risk from cloud and threat intel findings.</p>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
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
                  <span className={`font-semibold text-sm ${getLiabilityColor(penaltyInfo?.liability ?? 'High')}`}>{penaltyInfo?.liability ?? 'High'}</span>
                </div>
                <div className="border-b border-gray-800 pb-3">
                  <p className="text-gray-400 text-xs mb-2 uppercase tracking-wide">Indicative regulatory exposure</p>
                  <p className="text-sm mb-1">{penaltyInfo?.fine_exposure}</p>
                  {penaltyInfo?.fine_if_moderate && <p className="text-sm mb-1 text-gray-400">{penaltyInfo.fine_if_moderate}</p>}
                  {penaltyInfo?.fine_if_low && <p className="text-sm text-gray-400">{penaltyInfo.fine_if_low}</p>}
                </div>
                {penaltyInfo?.ransom_reporting && (
                  <div className="bg-amber-900/20 border border-amber-800 rounded-lg px-3 py-2 mt-2">
                    <p className="text-amber-300 text-xs font-medium">{penaltyInfo.ransom_reporting}</p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        <div className="bg-gray-900 border border-red-900/50 rounded-2xl p-5 mb-8 flex items-center justify-between gap-4">
          <div>
            <p className="text-white font-semibold mb-1">Not sure what to do next?</p>
            <p className="text-gray-400 text-sm">A qualified cyber security specialist will review your results and explain exactly what your business needs - in plain English, no jargon, no obligation.</p>
          </div>
          <a href="mailto:governance@secureit360.co" className="flex-shrink-0 bg-red-600 hover:bg-red-700 text-white font-semibold px-5 py-3 rounded-lg text-sm whitespace-nowrap">
            Email us now
          </a>
        </div>
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
            {penaltyInfo?.key_law && <p className="text-gray-600 text-xs mt-4 italic">Current legislation: {penaltyInfo.key_law}</p>}
          </div>
        )}

        {dashboard?.top_findings && dashboard.top_findings.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h3 className="text-white font-semibold mb-4">Your top security issues</h3>
            <div className="space-y-4">
              {dashboard.top_findings.map((finding: any, index: number) => {
                const hasMeta = (finding.engine === 'microsoft365' || finding.engine === 'google_workspace') && Array.isArray(finding.metadata?.affected_users) && finding.metadata.affected_users.length > 0
                return (
                  <div
                    key={index}
                    onClick={() => hasMeta && handleViewDetails(finding)}
                    className={`border-b border-gray-800 pb-4 last:border-0 last:pb-0 rounded-xl transition-colors ${hasMeta ? 'cursor-pointer hover:bg-gray-800/60 -mx-3 px-3 pt-3' : ''}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className={`text-xs px-2 py-1 rounded font-medium mt-0.5 flex-shrink-0 ${
                        finding.severity === 'critical' ? 'bg-red-900/50 text-red-300' :
                        finding.severity === 'moderate' ? 'bg-orange-900/50 text-orange-300' :
                        'bg-gray-700 text-gray-300'
                      }`}>
                        {finding.severity === 'critical' ? 'Critical' : finding.severity === 'moderate' ? 'Moderate' : 'Low'}
                      </span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-white text-sm font-medium">{finding.title}</p>
                          {isCarriedOver(finding) && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-900/40 text-amber-400 border border-amber-800">Not fixed since last scan</span>
                          )}
                          {hasMeta && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900/30 text-blue-400 border border-blue-800/60">
                              🔒 Click to view affected users
                            </span>
                          )}
                        </div>
                        <p className="text-gray-500 text-xs mt-1">{finding.description && finding.description.length > 200 ? `${finding.description.substring(0, 200)}...` : finding.description}</p>
                        {finding.governance_gap && <p className="text-gray-600 text-xs italic mt-2">{finding.governance_gap}</p>}
                        {finding.regulations && finding.regulations.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {filterRegulations(finding.regulations, country).map((reg: string, i: number) => (
                              <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">{reg}</span>
                            ))}
                          </div>
                        )}
                        <div className="mt-2 flex items-center gap-2 flex-wrap">
                          {getFixButton(finding.fix_type, finding)}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="mt-6 pt-4 border-t border-gray-800">
              <p className="text-gray-500 text-xs">
                Not sure what to do next? Email us at{' '}
                <a href="mailto:governance@secureit360.co" className="text-gray-400 hover:text-white underline">governance@secureit360.co</a>
                {' '}and a qualified cyber security specialist will review your results and explain exactly what your business needs - in plain English, no jargon, no obligation.
              </p>
            </div>
          </div>
        )}

        {dashboard?.ransom_score && penaltyInfo?.disclaimer && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mt-6">
            <p className="text-gray-600 text-xs leading-relaxed">
              <span className="text-gray-500 font-medium">Important: </span>{penaltyInfo.disclaimer}
            </p>
          </div>
        )}

        <p className="text-center text-gray-700 text-xs mt-8">&copy; 2026 Global Cyber Assurance. All rights reserved. &nbsp;|&nbsp; <a href="/privacy" className="hover:text-gray-500 underline">Privacy Policy</a> &nbsp;|&nbsp; <a href="/terms" className="hover:text-gray-500 underline">Terms of Service</a> &nbsp;|&nbsp; <a href="/cookie-policy" className="hover:text-gray-500 underline">Cookie Policy</a></p>

      </div>
    </main>
  )
}





