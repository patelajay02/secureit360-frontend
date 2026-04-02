'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })

      const data = await response.json()

      if (!response.ok) {
        setError('Incorrect email or password. Please try again.')
        return
      }

      localStorage.setItem('token', data.token)
      localStorage.setItem('tenant_id', data.tenant_id)
      localStorage.setItem('company_name', data.company_name)
      localStorage.setItem('role', data.role)

      router.push('/dashboard')

    } catch (err) {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">

        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-white mb-2">
            SecureIT<span className="text-red-500">360</span>
          </h1>
          <p className="text-gray-400">by Global Cyber Assurance</p>
        </div>

        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
          <h2 className="text-xl font-semibold text-white mb-6">
            Sign in to your account
          </h2>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 mb-4 text-sm">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="block text-gray-400 text-sm mb-2">Email address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:border-red-500"
              placeholder="you@company.com"
            />
          </div>

          <div className="mb-6">
            <label className="block text-gray-400 text-sm mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:border-red-500"
              placeholder="••••••••"
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            />
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg py-3 transition disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>

          <p className="text-center text-gray-500 text-sm mt-6">
            New to SecureIT360?{' '}
            <a href="/register" className="text-red-400 hover:text-red-300">
              Create your free account
            </a>
          </p>
        </div>

        <p className="text-center text-gray-600 text-xs mt-8">
          © 2026 Global Cyber Assurance All rights reserved.
        </p>
      </div>
    </main>
  )
}