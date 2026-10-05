import { useEffect, useState } from 'react'
import { X, Check, Sparkles } from 'lucide-react'
import { AuthUser, getPlans, getUsage, UsageDto } from '../api/climoraApi'
import { onUsageChanged } from '../usageBus'
import { FALLBACK_PLANS, Plan, formatPrice, priceSubtext } from '../plans'

interface PlansModalProps {
  open: boolean
  currentPlan: string
  user: AuthUser | null
  onSelectPlan: (planId: string) => void
  onCheckout: (plan: Plan, annual: boolean) => void
  onRequireAuth: () => void
  onEnterprise: () => void
  onClose: () => void
}

export default function PlansModal({ open, currentPlan, user, onSelectPlan, onCheckout, onRequireAuth, onEnterprise, onClose }: PlansModalProps) {
  const [plans, setPlans] = useState<Plan[]>(FALLBACK_PLANS)
  const [usage, setUsage] = useState<UsageDto | null>(null)
  const [annual, setAnnual] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  // Load plans + usage from the backend every time the modal opens,
  // and refresh usage the moment any query completes.
  useEffect(() => {
    if (!open) return
    setNotice(null)
    let cancelled = false
    const loadUsage = () => {
      getUsage()
        .then(data => {
          if (!cancelled) setUsage(data)
        })
        .catch(() => {
          // Usage unavailable offline — hide the quota bar.
        })
    }
    getPlans()
      .then(data => {
        if (!cancelled && Array.isArray(data.plans) && data.plans.length > 0) {
          setPlans(data.plans)
        }
      })
      .catch(() => {
        // Backend unreachable — fall back to bundled plan data.
      })
    loadUsage()
    const off = onUsageChanged(loadUsage)
    return () => {
      cancelled = true
      off()
    }
  }, [open])

  // Close on Escape.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const handleSelect = (plan: Plan) => {
    if (plan.id === 'enterprise') {
      onEnterprise()
      return
    }
    if (!user) {
      // Real-world rule: paid plans live on an account. Guests stay on Free.
      onRequireAuth()
      return
    }
    if (plan.id === 'free') {
      onSelectPlan('free')
      setNotice('Switched to the Free plan.')
      return
    }
    // Paid plans go through checkout — server activates on the account.
    onCheckout(plan, annual)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6 overflow-y-auto"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Plans and pricing"
    >
      <div
        className="w-full max-w-4xl bg-white dark:bg-slate-900 border dark:border-slate-800 rounded-2xl shadow-xl p-4 sm:p-6 my-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Plans & pricing</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close plans"
          >
            <X className="w-5 h-5 text-slate-500 dark:text-slate-400" />
          </button>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
          {user ? (
            <>Signed in as <span className="font-medium">{user.email}</span> — your plan is stored on your account.</>
          ) : (
            <>Try 2 queries as a guest. Sign in for 100 free queries/day — paid plans are tied to your account.</>
          )}
        </p>

        {/* Billing toggle */}
        <div className="flex items-center justify-center gap-3 mb-6">
          <span className={`text-sm ${!annual ? 'font-semibold text-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'}`}>Monthly</span>
          <button
            onClick={() => setAnnual(!annual)}
            className={`relative w-11 h-6 rounded-full transition-colors ${annual ? 'bg-climora-600' : 'bg-slate-300 dark:bg-slate-700'}`}
            role="switch"
            aria-checked={annual}
            aria-label="Toggle annual billing"
          >
            <span
              className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${annual ? 'left-[22px]' : 'left-0.5'}`}
            />
          </button>
          <span className={`text-sm ${annual ? 'font-semibold text-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'}`}>
            Annual <span className="text-xs text-climora-600 font-medium">2 months free</span>
          </span>
        </div>

        {/* Quota status */}
        {usage && (
          <p className="text-xs text-slate-500 dark:text-slate-400 text-center mb-4">
            {usage.authenticated === false ? (
              <>Guest trial: {usage.used_today} / {usage.daily_limit} queries used today — sign in for 100 free/day.</>
            ) : (
              <>Today's usage: {usage.used_today}
              {usage.daily_limit > 0 ? ` / ${usage.daily_limit}` : ' (unlimited)'} queries
              {' '}· {usage.plan_name} plan</>
            )}
          </p>
        )}
        {notice && (
          <p className="text-sm text-climora-700 dark:text-climora-300 bg-climora-50 dark:bg-climora-900/30 border border-climora-200 dark:border-climora-800 rounded-xl px-4 py-2 mb-4 text-center">
            {notice}
          </p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map(plan => {
            const isCurrent = plan.id === currentPlan
            return (
              <div
                key={plan.id}
                className={`relative flex flex-col rounded-2xl border p-5 ${
                  plan.highlighted
                    ? 'border-climora-500 shadow-lg'
                    : 'border-slate-200 dark:border-slate-700'
                } ${isCurrent ? 'bg-climora-50/50 dark:bg-climora-900/20' : 'bg-white dark:bg-slate-900'}`}
              >
                {plan.highlighted && (
                  <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-climora-600 text-white rounded-full whitespace-nowrap">
                    <Sparkles className="w-3 h-3" /> Most popular
                  </span>
                )}
                <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">{plan.name}</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">{plan.audience}</p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{formatPrice(plan, annual)}</p>
                <p className="text-xs text-slate-400 dark:text-slate-500 mb-3">{priceSubtext(plan, annual)}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">{plan.tagline}</p>
                <ul className="space-y-2 mb-5 flex-1">
                  {plan.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-300">
                      <Check className="w-3.5 h-3.5 text-climora-600 shrink-0 mt-0.5" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                {plan.id === 'enterprise' ? (
                  <button
                    onClick={() => handleSelect(plan)}
                    className="block w-full text-center px-4 py-2 text-sm font-medium border border-climora-600 text-climora-700 dark:text-climora-300 rounded-xl hover:bg-climora-50 dark:hover:bg-climora-900/30 transition-colors"
                  >
                    {isCurrent ? 'Current plan' : 'Set up organization'}
                  </button>
                ) : (
                  <button
                    onClick={() => handleSelect(plan)}
                    disabled={isCurrent}
                    className={`px-4 py-2 text-sm font-medium rounded-xl transition-colors disabled:cursor-default ${
                      isCurrent
                        ? 'bg-climora-100 dark:bg-climora-900/40 text-climora-700 dark:text-climora-300'
                        : plan.highlighted
                          ? 'bg-climora-600 text-white hover:bg-climora-700'
                          : 'border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:border-climora-400 hover:bg-climora-50 dark:hover:bg-slate-800'
                    }`}
                  >
                    {isCurrent ? 'Current plan' : plan.cta}
                  </button>
                )}
              </div>
            )
          })}
        </div>
        <p className="text-xs text-slate-400 dark:text-slate-500 text-center mt-5">
          Prices in Sri Lankan Rupees. Paid plans require an account; the server — not your browser — decides your quota.
        </p>
      </div>
    </div>
  )
}
