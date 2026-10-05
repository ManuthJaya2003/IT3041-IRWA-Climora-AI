import { useEffect, useState } from 'react'
import { X, Loader2, Mail, Lock, User as UserIcon, Eye, EyeOff, Building2 } from 'lucide-react'
import { getAuthConfig, googleSignIn, login, register, startSso } from '../api/climoraApi'

interface AuthModalProps {
  open: boolean
  mode: 'login' | 'register'
  onModeChange: (mode: 'login' | 'register') => void
  onSuccess: () => void
  onClose: () => void
}

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    google?: any
  }
}

const inputCls =
  'w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 pl-9 pr-3 py-2 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500'

export default function AuthModal({ open, mode, onModeChange, onSuccess, onClose }: AuthModalProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [googleId, setGoogleId] = useState<string | null>(null)
  const [ssoSlug, setSsoSlug] = useState('')
  const [ssoBusy, setSsoBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError(null)
    setBusy(false)
    setConfirmPassword('')
    setShowPassword(false)
    setShowConfirm(false)
    getAuthConfig()
      .then(cfg => setGoogleId(cfg.google_client_id))
      .catch(() => setGoogleId(null))
  }, [open, mode])

  // Render the Google button when a client ID is configured.
  useEffect(() => {
    if (!open || !googleId || !window.google) return
    try {
      window.google.accounts.id.initialize({
        client_id: googleId,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        callback: async (resp: any) => {
          setError(null)
          setBusy(true)
          try {
            await googleSignIn(resp.credential)
            onSuccess()
          } catch (e) {
            setError(e instanceof Error ? e.message : 'Google sign-in failed.')
            const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
            if (msg) setError(msg)
          } finally {
            setBusy(false)
          }
        },
      })
      window.google.accounts.id.renderButton(document.getElementById('climora-google-btn'), {
        theme: 'outline',
        size: 'large',
        width: 320,
      })
    } catch {
      // GIS failed — email login still works.
    }
  }, [open, googleId, onSuccess])

  if (!open) return null

  const submit = async () => {
    setError(null)
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError('Enter a valid email address.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (mode === 'register' && password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      if (mode === 'register') await register(email.trim(), password, name.trim())
      else await login(email.trim(), password)
      onSuccess()
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const submitSso = async () => {
    setError(null)
    if (!ssoSlug.trim()) {
      setError('Enter your organization slug (e.g. ministry).')
      return
    }
    setSsoBusy(true)
    try {
      const { authorization_url } = await startSso(ssoSlug.trim().toLowerCase())
      window.location.href = authorization_url
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not start SSO. Check the organization slug.')
      setSsoBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/60 px-4" onClick={onClose} role="dialog" aria-modal="true" aria-label="Sign in">
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 border dark:border-slate-800 rounded-2xl shadow-xl p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
            {mode === 'register' ? 'Create your account' : 'Welcome back'}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close sign in">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          {mode === 'register'
            ? 'Your plan and quota are tied to this account — no one can spoof a tier.'
            : 'Sign in to use your plan, saved locations and quota.'}
        </p>

        {mode === 'register' && (
          <div className="relative mb-3">
            <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" aria-label="Full name" className={inputCls} />
          </div>
        )}
        <div className="relative mb-3">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" type="email" autoComplete="email" aria-label="Email" className={inputCls} />
        </div>
        <div className="relative mb-3">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Password (min 8 characters)"
            type={showPassword ? 'text' : 'password'}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            aria-label="Password"
            className={`${inputCls} pr-10`}
            onKeyDown={e => { if (e.key === 'Enter') submit() }}
          />
          <button
            type="button"
            onClick={() => setShowPassword(v => !v)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {mode === 'register' && (
          <div className="relative mb-4">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="Confirm password"
              type={showConfirm ? 'text' : 'password'}
              autoComplete="new-password"
              aria-label="Confirm password"
              className={`${inputCls} pr-10`}
              onKeyDown={e => { if (e.key === 'Enter') submit() }}
            />
            <button
              type="button"
              onClick={() => setShowConfirm(v => !v)}
              aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        )}
        {mode === 'login' && <div className="mb-1" />}

        {error && <p className="text-xs text-red-600 dark:text-red-400 mb-3">{error}</p>}

        <button
          onClick={submit}
          disabled={busy}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 disabled:opacity-70"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          {mode === 'register' ? 'Create account' : 'Sign in'}
        </button>

        <button
          onClick={() => { setError(null); onModeChange(mode === 'register' ? 'login' : 'register') }}
          className="w-full mt-3 text-xs text-climora-700 dark:text-climora-300 hover:underline"
        >
          {mode === 'register' ? 'Already have an account? Sign in' : "Don't have an account? Create one"}
        </button>

        <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
          {googleId ? (
            <>
              <div id="climora-google-btn" className="flex justify-center min-h-[40px]" />
              <p className="text-[11px] text-slate-400 text-center mt-2">Google sign-in verifies directly with Google.</p>
            </>
          ) : (
            <p className="text-[11px] text-slate-400 text-center">
              Google sign-in is disabled (no <code>VITE_GOOGLE_CLIENT_ID</code> / <code>GOOGLE_CLIENT_ID</code> configured).
            </p>
          )}
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 mb-2">
              <Building2 className="w-3.5 h-3.5" /> Enterprise SSO
            </p>
            <div className="flex gap-2">
              <input
                value={ssoSlug}
                onChange={e => setSsoSlug(e.target.value)}
                placeholder="Organization slug"
                aria-label="Organization slug"
                className="flex-1 min-w-0 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500"
                onKeyDown={e => { if (e.key === 'Enter') submitSso() }}
              />
              <button
                onClick={submitSso}
                disabled={ssoBusy}
                className="px-3 py-1.5 text-sm font-medium border border-slate-300 dark:border-slate-600 rounded-lg hover:border-climora-400 disabled:opacity-60 shrink-0"
              >
                {ssoBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Continue'}
              </button>
            </div>
            <p className="text-[11px] text-slate-400 mt-1.5">Redirects to your organization's identity provider.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
