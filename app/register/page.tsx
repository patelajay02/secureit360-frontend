'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function RegisterPage() {
  const router = useRouter()
  const [formData, setFormData] = useState({
    company_name: '',
    domain: '',
    email: '',
    password: ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleRegister = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.detail || 'Something went wrong. Please try again.')
        return
      }

      router.push('/?registered=true')

    } catch (err) {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-white mb-2">
            SecureIT<span className="text-red-500">360</span>
          </h1>
          <p className="text-gray-400">Start your free 14-day trial</p>
        </div>

        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
          <h2 className="text-xl font-semibold text-white mb-6">
            Create your account
          </h2>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 mb-4 text-sm">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="block text-gray-400 text-sm mb-2">Your business name</label>
            <input
              type="text"
              value={formData.company_name}
              onChange={(e) => setFormData({...formData, company_name: e.target.value})}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:border-red-500"
              placeholder="Acme Ltd"
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-400 text-sm mb-2">Your website address</label>
            <input
              type="text"
              value={formData.domain}
              onChange={(e) => setFormData({...formData, domain: e.target.value})}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:border-red-500"
              placeholder="acme.co.nz"
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-400 text-sm mb-2">Your email address</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:border-red-500"
              placeholder="you@acme.co.nz"
            />
          </div>

          <div className="mb-6">
            <label className="block text-gray-400 text-sm mb-2">Choose a password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:border-red-500"
              placeholder="At least 8 characters"
            />
          </div>

          <button
            onClick={handleRegister}
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg py-3 transition disabled:opacity-50"
          >
            {loading ? 'Creating your account...' : 'Start free trial'}
          </button>

          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{' '}
            <a href="/" className="text-red-400 hover:text-red-300">Sign in</a>
          </p>
        </div>

        <div className="text-center mt-6 text-gray-600 text-xs">
          <p>14-day free trial. No credit card required.</p>
          <p className="mt-1">© 2026 Global Cyber Assurance All rights reserved.</p>
        </div>

      </div>
    </main>
  )
}