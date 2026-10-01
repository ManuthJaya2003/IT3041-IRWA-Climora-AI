export interface Plan {
  id: string
  name: string
  audience: string
  tagline: string
  monthly_lkr: number | null
  annual_lkr: number | null
  monthly_usd: number | null
  annual_usd: number | null
  cta: string
  highlighted: boolean
  queries_per_day: number
  max_saved_locations: number
  history_days: number
  features: string[]
  limits_note: string
}

export const PLAN_IDS = ['free', 'premium', 'business', 'enterprise'] as const
export type PlanId = (typeof PLAN_IDS)[number]

const PLAN_KEY = 'climora-plan'

/** Fallback copy of the backend plans — the backend is the source of truth
 *  (GET /api/v1/billing/plans); this is only used when it is unreachable. */
export const FALLBACK_PLANS: Plan[] = [
  {
    id: 'free',
    name: 'Free',
    audience: 'Individuals & students',
    tagline: 'Everyday climate awareness for Sri Lanka.',
    monthly_lkr: 0,
    annual_lkr: 0,
    monthly_usd: 0,
    annual_usd: 0,
    cta: 'Get started',
    highlighted: false,
    queries_per_day: 100,
    max_saved_locations: 1,
    history_days: 7,
    features: [
      '100 AI climate queries / day',
      'Current weather + hazard risk',
      'English, Sinhala & Tamil',
      'Voice input with audio answers',
      '1 saved location',
      '7-day chat history',
    ],
    limits_note: 'Fair-use daily quota applies.',
  },
  {
    id: 'premium',
    name: 'Premium',
    audience: 'Individuals, professionals & small teams',
    tagline: 'Personal monitoring and richer analysis.',
    monthly_lkr: 1490,
    annual_lkr: 14900,
    monthly_usd: 5,
    annual_usd: 50,
    cta: 'Go Premium',
    highlighted: true,
    queries_per_day: 1000,
    max_saved_locations: 5,
    history_days: 90,
    features: [
      'Everything in Free, plus:',
      '1,000 AI climate queries / day',
      'Severe-weather browser alerts',
      '5 saved locations',
      '90-day chat history',
      'Priority support',
    ],
    limits_note: 'Per-user fair use.',
  },
  {
    id: 'business',
    name: 'Business',
    audience: 'SMEs & organizations',
    tagline: 'Climate intelligence for operations.',
    monthly_lkr: 9900,
    annual_lkr: 99000,
    monthly_usd: 33,
    annual_usd: 330,
    cta: 'Start Business trial',
    highlighted: false,
    queries_per_day: 10000,
    max_saved_locations: 25,
    history_days: 365,
    features: [
      'Everything in Premium, plus:',
      '10,000 AI climate queries / day',
      '25 saved locations',
      '1-year chat history',
      'API access for integrations',
      'Email support',
    ],
    limits_note: 'Pooled across team seats.',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    audience: 'Large orgs, NGOs & authorities',
    tagline: 'Custom deployment and support.',
    monthly_lkr: null,
    annual_lkr: null,
    monthly_usd: null,
    annual_usd: null,
    cta: 'Contact sales',
    highlighted: false,
    queries_per_day: 0,
    max_saved_locations: 0,
    history_days: 0,
    features: [
      'Unlimited queries (custom quota)',
      'SSO, audit logs & security review',
      'Dedicated / on-premise deployment',
      'Custom integrations & SLA',
      'Staff training & support',
    ],
    limits_note: 'Custom contract.',
  },
]

export function loadPlan(): string {
  try {
    const saved = localStorage.getItem(PLAN_KEY)
    if (saved && (PLAN_IDS as readonly string[]).includes(saved)) return saved
  } catch {
    // ignore — fall through to default
  }
  return 'free'
}

export function savePlan(planId: string): void {
  try {
    localStorage.setItem(PLAN_KEY, planId)
  } catch {
    // Private-mode / quota errors must never crash the app.
  }
}

export function formatPrice(plan: Plan, annual: boolean): string {
  const lkr = annual ? plan.annual_lkr : plan.monthly_lkr
  if (lkr === null || lkr === undefined) return 'Custom'
  if (lkr === 0) return 'Free'
  return `Rs ${lkr.toLocaleString('en-LK')}`
}

export function priceSubtext(plan: Plan, annual: boolean): string {
  if (plan.monthly_lkr === null) return 'annual billing'
  if (plan.monthly_lkr === 0) return 'free forever'
  return annual ? 'per year (2 months free)' : 'per month'
}

// --- Saved locations (plan-limited quick picks for the chat location box) ---

const LOCATIONS_KEY = 'climora-saved-locations'
const MAX_LOCATION_LEN = 60

export function loadLocations(): string[] {
  try {
    const raw = localStorage.getItem(LOCATIONS_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((v): v is string => typeof v === 'string')
      .map(v => v.trim().slice(0, MAX_LOCATION_LEN))
      .filter(Boolean)
      .slice(0, 50)
  } catch {
    return []
  }
}

function persistLocations(locations: string[]): void {
  try {
    localStorage.setItem(LOCATIONS_KEY, JSON.stringify(locations))
  } catch {
    // Private-mode / quota errors must never crash the app.
  }
}

/** Add a location, enforcing the plan cap (0 = unlimited). Returns an error message or null. */
export function addLocation(locations: string[], name: string, limit: number): { locations: string[]; error: string | null } {
  const clean = name.trim().slice(0, MAX_LOCATION_LEN)
  if (!clean) return { locations, error: 'Enter a location name.' }
  if (locations.some(l => l.toLowerCase() === clean.toLowerCase())) {
    return { locations, error: 'That location is already saved.' }
  }
  if (limit > 0 && locations.length >= limit) {
    return { locations, error: `Your plan allows ${limit} saved location${limit === 1 ? '' : 's'}. Upgrade for more.` }
  }
  const next = [...locations, clean]
  persistLocations(next)
  return { locations: next, error: null }
}

export function removeLocation(locations: string[], name: string): string[] {
  const next = locations.filter(l => l !== name)
  persistLocations(next)
  return next
}
