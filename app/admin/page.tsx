'use client'
import { useState, useEffect } from 'react'
import { authFetch } from '../../lib/auth'

const PAGE_SIZE = 25

export default function AdminPage() {
  // Authorization is decided by the /auth/admin/users response itself (no separate
  // /auth/admin/me call). 403 -> denied; auth failure -> authFetch redirects to login.
  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'denied'>('checking')
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({ company_name: '', email: '', password: '', country: 'NZ' })
  const [createLoading, setCreateLoading] = useState(false)
  const [extendDays, setExtendDays] = useState<Record<string, number>>({})

  // Debounce the search box; reset to page 1 when the query settles.
  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [search])

  // Single source of fetching: refetch whenever page / search / status changes.
  useEffect(() => {
    fetchUsers(page, debouncedSearch, filterStatus)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, debouncedSearch, filterStatus])

  const fetchUsers = async (p = page, s = debouncedSearch, st = filterStatus) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) })
      if (s) params.set('search', s)
      if (st && st !== 'all') params.set('status', st)
      const res = await authFetch(`/auth/admin/users?${params.toString()}`)
      if (res.status === 403) { setAuthState('denied'); return }
      if (!res.ok) {
        setAuthState('authorized')
        showMessage('Failed to load clients.', 'error')
        return
      }
      const data = await res.json()
      setUsers(data.users || [])
      setTotal(data.total || 0)
      setTotalPages(data.total_pages || 1)
      setAuthState('authorized')
    } catch {
      // authFetch handles token expiry by redirecting to login.
    } finally {
      setLoading(false)
    }
  }

  const refresh = () => fetchUsers(page, debouncedSearch, filterStatus)

  const showMessage = (msg: string, type: 'success' | 'error' = 'success') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => setMessage(''), 4000)
  }

  const handleDelete = async (userId: string, email: string) => {
    if (!confirm(`Delete ${email}? This cannot be undone.`)) return
    setActionLoading(userId + '_delete')
    try {
      const res = await authFetch(`/auth/admin/delete/${userId}`, { method: 'DELETE' })
      if (res.ok) { showMessage(`${email} deleted successfully.`); refresh() }
      else showMessage('Could not delete user.', 'error')
    } catch { showMessage('Something went wrong.', 'error') }
    finally { setActionLoading(null) }
  }

  const handleSuspend = async (userId: string, email: string, currentStatus: string) => {
    const isSuspended = currentStatus === 'suspended'
    const action = isSuspended ? 'unsuspend' : 'suspend'
    if (!confirm(`${isSuspended ? 'Unsuspend' : 'Suspend'} ${email}?`)) return
    setActionLoading(userId + '_suspend')
    try {
      const res = await authFetch(`/auth/admin/suspend/${userId}`, { method: 'POST', body: JSON.stringify({ action }) })
      if (res.ok) { showMessage(`${email} ${action}ed successfully.`); refresh() }
      else showMessage(`Could not ${action} user.`, 'error')
    } catch { showMessage('Something went wrong.', 'error') }
    finally { setActionLoading(null) }
  }

  const handleGrantAccess = async (userId: string, email: string, currentStatus: string) => {
    const isComped = currentStatus === 'comped'
    const action = isComped ? 'revoke' : 'grant'
    if (!confirm(`${isComped ? 'Revoke full access from' : 'Grant full access to'} ${email}?`)) return
    setActionLoading(userId + '_access')
    try {
      const res = await authFetch(`/auth/admin/access/${userId}`, { method: 'POST', body: JSON.stringify({ action }) })
      if (res.ok) { showMessage(`Full access ${action}ed for ${email}.`); refresh() }
      else showMessage(`Could not ${action} access.`, 'error')
    } catch { showMessage('Something went wrong.', 'error') }
    finally { setActionLoading(null) }
  }

  const handleExtendTrial = async (userId: string, email: string) => {
    const days = extendDays[userId] || 7
    if (!confirm(`Extend trial for ${email} by ${days} days?`)) return
    setActionLoading(userId + '_extend')
    try {
      const res = await authFetch(`/auth/admin/extend-trial/${userId}`, { method: 'POST', body: JSON.stringify({ days }) })
      if (res.ok) { showMessage(`Trial extended by ${days} days for ${email}.`); refresh() }
      else showMessage('Could not extend trial.', 'error')
    } catch { showMessage('Something went wrong.', 'error') }
    finally { setActionLoading(null) }
  }

  const handleCreateAccount = async () => {
    if (!createForm.company_name || !createForm.email || !createForm.password) {
      showMessage('Please fill in all fields.', 'error'); return
    }
    setCreateLoading(true)
    try {
      const res = await authFetch(`/auth/admin/create-account`, { method: 'POST', body: JSON.stringify(createForm) })
      const data = await res.json()
      if (res.ok) {
        showMessage(`Account created for ${createForm.email}. Full access granted.`)
        setShowCreateModal(false)
        setCreateForm({ company_name: '', email: '', password: '', country: 'NZ' })
        refresh()
      } else showMessage(data.detail || 'Could not create account.', 'error')
    } catch { showMessage('Something went wrong.', 'error') }
    finally { setCreateLoading(false) }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      trial: 'bg-amber-900/50 text-amber-300',
      active: 'bg-green-900/50 text-green-300',
      comped: 'bg-purple-900/50 text-purple-300',
      suspended: 'bg-red-900/50 text-red-300',
      cancelled: 'bg-gray-800 text-gray-400',
      past_due: 'bg-orange-900/50 text-orange-300',
    }
    return styles[status] || 'bg-gray-800 text-gray-400'
  }

  if (authState === 'checking') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <p className="text-gray-400 text-sm">Verifying access…</p>
      </div>
    )
  }

  if (authState === 'denied') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-sm text-center">
          <h1 className="text-xl font-bold text-white mb-2">Admin Portal</h1>
          <p className="text-gray-500 text-sm mb-6">SecureIT360 — Global Cyber Assurance</p>
          <p className="text-red-400 text-sm mb-4">
            You are not authorised to access this page. Platform-administrator access is required.
          </p>
          <a href="/login" className="inline-block bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded-lg">
            Go to login
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold">SecureIT<span className="text-red-500">360</span> <span className="text-gray-400 font-normal text-base">Admin</span></h1>
          <p className="text-gray-500 text-xs mt-0.5">Global Cyber Assurance — Internal use only</p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">{total} clients</span>
          <button onClick={refresh} className="text-gray-400 hover:text-white text-sm">Refresh</button>
          <button onClick={() => setShowCreateModal(true)}
            className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
            + Create account
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">

        {message && (
          <div className={`rounded-lg px-4 py-3 mb-6 text-sm ${messageType === 'success' ? 'bg-green-900/30 border border-green-700 text-green-300' : 'bg-red-900/30 border border-red-700 text-red-300'}`}>
            {message}
          </div>
        )}

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by company name..."
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:border-red-500"
          />
          <select value={filterStatus} onChange={(e) => { setFilterStatus(e.target.value); setPage(1) }}
            className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white text-sm focus:outline-none">
            <option value="all">All statuses</option>
            <option value="trial">Trial</option>
            <option value="active">Active</option>
            <option value="comped">Comped</option>
            <option value="suspended">Suspended</option>
            <option value="past_due">Past due</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-5 animate-pulse">
                <div className="h-4 w-48 bg-gray-800 rounded mb-3" />
                <div className="h-3 w-64 bg-gray-800/70 rounded mb-2" />
                <div className="h-3 w-40 bg-gray-800/50 rounded" />
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {users.length === 0 && (
              <p className="text-gray-500 text-sm">No clients found.</p>
            )}
            {users.map((user) => (
              <div key={user.user_id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <p className="text-white font-semibold">{user.company_name}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getStatusBadge(user.status)}`}>
                        {user.status}
                      </span>
                      <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">{user.country}</span>
                    </div>
                    <p className="text-gray-400 text-sm">{user.email}</p>
                    <p className="text-gray-600 text-xs mt-1">
                      Registered {user.created_at ? new Date(user.created_at).toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Unknown'}
                      {user.trial_ends_at && user.status === 'trial' && (
                        <span className="ml-2 text-amber-500">
                          — trial ends {new Date(user.trial_ends_at).toLocaleDateString('en-NZ', { day: 'numeric', month: 'short' })}
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2 justify-end">
                    <button
                      onClick={() => handleGrantAccess(user.user_id, user.email, user.status)}
                      disabled={actionLoading === user.user_id + '_access'}
                      className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                        user.status === 'comped'
                          ? 'bg-purple-900/50 text-purple-300 hover:bg-purple-900'
                          : 'bg-green-900/50 text-green-300 hover:bg-green-900'
                      } disabled:opacity-50`}
                    >
                      {user.status === 'comped' ? 'Revoke access' : 'Grant full access'}
                    </button>

                    <button
                      onClick={() => handleSuspend(user.user_id, user.email, user.status)}
                      disabled={actionLoading === user.user_id + '_suspend'}
                      className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                        user.status === 'suspended'
                          ? 'bg-green-900/50 text-green-300 hover:bg-green-900'
                          : 'bg-amber-900/50 text-amber-300 hover:bg-amber-900'
                      } disabled:opacity-50`}
                    >
                      {user.status === 'suspended' ? 'Unsuspend' : 'Suspend'}
                    </button>

                    {(user.status === 'trial' || user.status === 'comped') && (
                      <div className="flex items-center gap-1">
                        <select
                          value={extendDays[user.user_id] || 7}
                          onChange={(e) => setExtendDays({...extendDays, [user.user_id]: parseInt(e.target.value)})}
                          className="bg-gray-800 border border-gray-700 text-white text-xs rounded px-2 py-1.5"
                        >
                          <option value={7}>+7 days</option>
                          <option value={14}>+14 days</option>
                          <option value={30}>+30 days</option>
                          <option value={60}>+60 days</option>
                          <option value={90}>+90 days</option>
                        </select>
                        <button
                          onClick={() => handleExtendTrial(user.user_id, user.email)}
                          disabled={actionLoading === user.user_id + '_extend'}
                          className="bg-blue-900/50 text-blue-300 hover:bg-blue-900 text-xs px-3 py-1.5 rounded-lg font-medium disabled:opacity-50"
                        >
                          Extend
                        </button>
                      </div>
                    )}

                    <button
                      onClick={() => handleDelete(user.user_id, user.email)}
                      disabled={actionLoading === user.user_id + '_delete'}
                      className="bg-red-900/50 text-red-300 hover:bg-red-900 text-xs px-3 py-1.5 rounded-lg font-medium disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="text-sm px-4 py-2 rounded-lg bg-gray-900 border border-gray-700 text-gray-300 hover:bg-gray-800 disabled:opacity-40"
            >
              ← Previous
            </button>
            <span className="text-gray-500 text-sm">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="text-sm px-4 py-2 rounded-lg bg-gray-900 border border-gray-700 text-gray-300 hover:bg-gray-800 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md">
            <h3 className="text-white font-semibold text-lg mb-4">Create test account</h3>
            <p className="text-gray-400 text-sm mb-6">Creates an account with full access. No domain matching required.</p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Company name</label>
                <input type="text" value={createForm.company_name}
                  onChange={(e) => setCreateForm({...createForm, company_name: e.target.value})}
                  placeholder="Test Company" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Email address</label>
                <input type="email" value={createForm.email}
                  onChange={(e) => setCreateForm({...createForm, email: e.target.value})}
                  placeholder="tester@gmail.com" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Temporary password</label>
                <input type="text" value={createForm.password}
                  onChange={(e) => setCreateForm({...createForm, password: e.target.value})}
                  placeholder="Min 8 characters" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Country</label>
                <select value={createForm.country}
                  onChange={(e) => setCreateForm({...createForm, country: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500">
                  <option value="NZ">New Zealand</option>
                  <option value="AU">Australia</option>
                  <option value="PI">Pacific Islands</option>
                  <option value="IN">India</option>
                  <option value="AE">United Arab Emirates</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={handleCreateAccount} disabled={createLoading}
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg disabled:opacity-50">
                  {createLoading ? 'Creating...' : 'Create account'}
                </button>
                <button onClick={() => setShowCreateModal(false)}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
