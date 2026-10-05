import { useState } from 'react'
import { X, Loader2, ShieldCheck } from 'lucide-react'
import { BillingCycle, Plan, planAmount } from '../plans'
import { createCheckoutSession } from '../api/climoraApi'

export interface CheckoutResult {
  receipt: string
  cycle: BillingCycle
}

interface CheckoutModalProps {
  open: boolean
  plan: Plan | null
  annual: boolean
  onSuccess: (result: CheckoutResult) => void
  onClose: () => void
}

export default function CheckoutModal({ open, plan, annual, onSuccess: _onSuccess, onClose }: CheckoutModalProps) {
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<'form' | 'processing'>('form')

  if (!open || !plan) return null

  const cycle: BillingCycle = annual ? 'annual' : 'monthly'
  const amount = planAmount(plan, annual) ?? 0

  const handlePay = async () => {
    setError(null)
    setPhase('processing')
    try {
      const session = await createCheckoutSession(
        plan.id,
        annual,
        `${window.location.origin}/?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
        `${window.location.origin}/?checkout=cancelled`,
      )
      window.location.assign(session.checkout_url)
    } catch (err) {
      setPhase('form')
      setError(err instanceof Error ? err.message : 'Unable to start checkout.')
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/60 px-4"
      onClick={phase === 'processing' ? undefined : onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Stripe checkout"
    >
      <div
        className="w-full max-w-md bg-white dark:bg-slate-900 border dark:border-slate-800 rounded-2xl shadow-xl p-6"
        onClick={e => e.stopPropagation()}
      >
        {(
          <>
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Checkout</h2>
              <button
                onClick={onClose}
                disabled={phase === 'processing'}
                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
                aria-label="Close checkout"
              >
                <X className="w-5 h-5 text-slate-500 dark:text-slate-400" />
              </button>
            </div>
            <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded-xl px-3 py-2 mb-4">
              <ShieldCheck className="w-4 h-4 shrink-0" />
              Secure Stripe Checkout. Your card details are handled by Stripe.
            </div>

            <div className="flex items-center justify-between text-sm mb-4 pb-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <p className="font-semibold text-slate-800 dark:text-slate-100">{plan.name} · {cycle}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{plan.audience}</p>
              </div>
              <p className="text-lg font-bold text-slate-900 dark:text-white">Rs {amount.toLocaleString('en-LK')}</p>
            </div>

            {error && <p className="text-xs text-red-600 dark:text-red-400 mb-3">{error}</p>}

            <button
              onClick={handlePay}
              disabled={phase === 'processing'}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 transition-colors disabled:opacity-70"
            >
              {phase === 'processing' ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing…
                </>
              ) : (
                <>Pay Rs {amount.toLocaleString('en-LK')}</>
              )}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
