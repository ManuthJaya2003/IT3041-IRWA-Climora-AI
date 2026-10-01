import { useState } from 'react'
import { X, CheckCircle2, CreditCard, Loader2, ShieldCheck } from 'lucide-react'
import { BillingCycle, Plan, makeReceipt, planAmount } from '../plans'

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

/** Demo checkout — clearly labeled mock payment for evaluation demos.
 *  No card data leaves the browser; no charge is made. */
export default function CheckoutModal({ open, plan, annual, onSuccess, onClose }: CheckoutModalProps) {
  const [card, setCard] = useState('4111 1111 1111 1111')
  const [expiry, setExpiry] = useState('12/28')
  const [cvc, setCvc] = useState('123')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<'form' | 'processing' | 'done'>('form')
  const [receipt, setReceipt] = useState('')

  if (!open || !plan) return null

  const cycle: BillingCycle = annual ? 'annual' : 'monthly'
  const amount = planAmount(plan, annual) ?? 0

  const formatCard = (v: string) =>
    v.replace(/\D/g, '').slice(0, 16).replace(/(\d{4})(?=\d)/g, '$1 ')

  const handlePay = () => {
    const digits = card.replace(/\D/g, '')
    if (digits.length !== 16) {
      setError('Enter the 16-digit demo card number.')
      return
    }
    if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(expiry.trim())) {
      setError('Expiry must look like MM/YY.')
      return
    }
    if (!/^\d{3,4}$/.test(cvc.trim())) {
      setError('CVC must be 3–4 digits.')
      return
    }
    if (!name.trim()) {
      setError('Enter the name on the card.')
      return
    }
    setError(null)
    setPhase('processing')
    // Simulated gateway latency — replace with a real provider call.
    setTimeout(() => {
      setReceipt(makeReceipt())
      setPhase('done')
    }, 1500)
  }

  const handleDone = () => {
    onSuccess({ receipt, cycle })
    setPhase('form')
    setError(null)
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/60 px-4"
      onClick={phase === 'processing' ? undefined : onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Demo checkout"
    >
      <div
        className="w-full max-w-md bg-white dark:bg-slate-900 border dark:border-slate-800 rounded-2xl shadow-xl p-6"
        onClick={e => e.stopPropagation()}
      >
        {phase === 'done' ? (
          <div className="text-center py-4">
            <CheckCircle2 className="w-14 h-14 text-climora-500 mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Payment successful</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {plan.name} · {cycle} · Rs {amount.toLocaleString('en-LK')}
            </p>
            <p className="text-xs text-slate-400 mt-2 font-mono">Receipt {receipt}</p>
            <p className="text-xs text-slate-400 mt-1">Demo checkout — no real charge was made.</p>
            <button
              onClick={handleDone}
              className="mt-5 w-full px-4 py-2.5 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
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
              Demo checkout — no real charge. Card never leaves this browser.
            </div>

            <div className="flex items-center justify-between text-sm mb-4 pb-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <p className="font-semibold text-slate-800 dark:text-slate-100">{plan.name} · {cycle}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{plan.audience}</p>
              </div>
              <p className="text-lg font-bold text-slate-900 dark:text-white">Rs {amount.toLocaleString('en-LK')}</p>
            </div>

            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5" htmlFor="co-card">
              Card number
            </label>
            <div className="relative mb-3">
              <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                id="co-card"
                inputMode="numeric"
                value={card}
                onChange={e => setCard(formatCard(e.target.value))}
                placeholder="4111 1111 1111 1111"
                disabled={phase === 'processing'}
                className={`${inputCls} pl-9`}
              />
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5" htmlFor="co-exp">Expiry</label>
                <input id="co-exp" value={expiry} onChange={e => setExpiry(e.target.value)}
                  placeholder="MM/YY" disabled={phase === 'processing'} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5" htmlFor="co-cvc">CVC</label>
                <input id="co-cvc" inputMode="numeric" value={cvc} onChange={e => setCvc(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="123" disabled={phase === 'processing'} className={inputCls} />
              </div>
            </div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5" htmlFor="co-name">
              Name on card
            </label>
            <input id="co-name" value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. Nimal Perera" disabled={phase === 'processing'} className={`${inputCls} mb-4`} />

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

const inputCls =
  'w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500 disabled:opacity-60'
