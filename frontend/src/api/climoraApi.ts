import axios from 'axios'

const API_BASE_URL = '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
})

// Commercial plan sent with every request so the backend can enforce the
// correct daily quota (X-Plan header; unknown values fall back to Free).
// NOTE: for signed-in users the server ignores X-Plan and uses the plan
// stored on their account — this header only matters for anonymous guests.
let apiPlan = 'free'
let authToken: string | null = null

try {
  authToken = localStorage.getItem('climora-token')
} catch {
  authToken = null
}

export function setApiPlan(planId: string): void {
  apiPlan = planId
}

export function setAuthToken(token: string | null): void {
  authToken = token
  try {
    if (token) localStorage.setItem('climora-token', token)
    else localStorage.removeItem('climora-token')
  } catch {
    // ignore private-mode errors
  }
}

export function getAuthToken(): string | null {
  return authToken
}

api.interceptors.request.use(config => {
  config.headers = config.headers ?? {}
  config.headers['X-Plan'] = apiPlan
  if (authToken) config.headers['Authorization'] = `Bearer ${authToken}`
  return config
})

// --- Types ---

export interface ChatRequest {
  query: string
  location?: string
  user_type?: string
  session_id?: string
  context?: Record<string, unknown>
  /** Preferred answer language: 'en' | 'si' | 'ta'. A Sinhala/Tamil query is always answered in that language. */
  language?: string
}

export interface SourceEvidence {
  source_name: string
  source_url?: string
  content_snippet: string
  retrieved_at?: string
  reliability_score?: number
}

export interface RiskAssessment {
  risk_level: string
  risk_factors: string[]
  confidence?: number
  explanation?: string
}

export interface Recommendation {
  action: string
  priority: string
  explanation?: string
}

export interface ChatResponse {
  session_id: string
  query: string
  summary: string
  detailed_analysis?: string
  risk_assessment?: RiskAssessment
  recommendations: Recommendation[]
  sources: SourceEvidence[]
  confidence_score?: number
  disclaimer: string
  processing_time_ms?: number
  agents_used: string[]
  language?: string
}

export interface VoiceQueryResponse {
  response: ChatResponse
  audio_url: string | null
  language: string
}

export interface AgentInfo {
  name: string
  role: string
  status: string
  owner: string
  port: number
}

// --- API Functions ---

export async function sendQuery(request: ChatRequest): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>('/chat/query', request)
  return response.data
}

// --- Streaming query (Server-Sent Events) ---

/** A real-time event emitted by the backend pipeline while it runs. */
export interface AgentStreamEvent {
  type: 'pipeline_start' | 'agent_start' | 'agent_end' | 'done' | 'error'
  agent?: string
  tool?: string
  /** For agent_end: 'success' | 'fallback' | 'error'. */
  outcome?: string
  duration_ms?: number
  /** For done: the final ChatResponse. */
  response?: ChatResponse
  message?: string
}

/**
 * Send a query and receive real-time pipeline events over SSE.
 *
 * `onEvent` is called for every event as it happens (agent_start / agent_end),
 * letting the UI reflect the exact live agent-communication flow. The promise
 * resolves with the final ChatResponse once the pipeline is done.
 *
 * The stream closing (or a `done` event) signals that communication has stopped.
 */
export async function streamQuery(
  request: ChatRequest,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Plan': apiPlan,
  }
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`
  const res = await fetch(`${API_BASE_URL}/chat/query/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
    signal,
  })

  if (!res.ok) {
    // Surface the real reason (e.g. guest-trial exhausted) instead of a bare status.
    let detail = `Stream request failed: ${res.status}`
    try {
      const body = await res.json() as { detail?: string }
      if (body?.detail) detail = body.detail
    } catch {
      // non-JSON error body — keep the status text
    }
    const err = new Error(detail) as Error & { status?: number }
    err.status = res.status
    throw err
  }
  if (!res.body) {
    throw new Error('Stream request failed: empty response')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResponse: ChatResponse | null = null

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE frames are separated by a blank line.
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        const line = frame.split('\n').find(l => l.startsWith('data:'))
        if (!line) continue
        const json = line.slice(5).trim()
        if (!json) continue

        let event: AgentStreamEvent
        try {
          event = JSON.parse(json) as AgentStreamEvent
        } catch {
          continue
        }

        onEvent(event)

        if (event.type === 'done' && event.response) {
          finalResponse = event.response
        } else if (event.type === 'error') {
          throw new Error(event.message || 'Pipeline error')
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  if (!finalResponse) {
    throw new Error('Stream ended without a final response')
  }
  return finalResponse
}

export async function getAgentsList(): Promise<{ agents: AgentInfo[] }> {
  const response = await api.get('/agents/list')
  return response.data
}

export async function getAgentsStatus(): Promise<Record<string, unknown>> {
  const response = await api.get('/agents/status')
  return response.data
}

export async function getHealthCheck(): Promise<Record<string, unknown>> {
  const response = await api.get('/health')
  return response.data
}

// --- Speech API Functions ---

export async function sendVoiceQuery(request: {
  query: string
  location?: string
  user_type?: string
  session_id?: string
  language?: string
}): Promise<VoiceQueryResponse> {
  const response = await api.post<VoiceQueryResponse>('/speech/voice-query', request)
  return response.data
}

export function getAudioUrl(audioPath: string): string {
  return `${API_BASE_URL}${audioPath}`
}

export async function textToSpeech(text: string, language?: string): Promise<string> {
  const response = await api.post('/speech/speak', { text, language }, {
    responseType: 'blob',
  })
  // Create a blob URL for audio playback
  const blob = new Blob([response.data], { type: 'audio/mpeg' })
  return URL.createObjectURL(blob)
}

// --- Plans & Usage API Functions ---

export interface PlanDto {
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

export interface UsageDto {
  plan: string
  plan_name: string
  used_today: number
  remaining_today: number
  daily_limit: number
  day: string
  authenticated?: boolean
}

export async function getPlans(): Promise<{ plans: PlanDto[] }> {
  const response = await api.get('/billing/plans')
  return response.data
}

export async function getUsage(): Promise<UsageDto> {
  const response = await api.get('/billing/usage')
  return response.data
}

// --- Auth (real user accounts; plan lives server-side) ---

export interface AuthUser {
  id: string
  email: string
  name: string
  provider: string
  plan_id: string
  plan_name: string
  billing_cycle: 'monthly' | 'annual'
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
  usage: UsageDto
}

export async function register(email: string, password: string, name: string): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>('/auth/register', { email, password, name })
  setAuthToken(response.data.access_token)
  return response.data
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>('/auth/login', { email, password })
  setAuthToken(response.data.access_token)
  return response.data
}

export async function googleSignIn(idToken: string): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>('/auth/google', { id_token: idToken })
  setAuthToken(response.data.access_token)
  return response.data
}

export async function fetchMe(): Promise<{ user: AuthUser; usage: UsageDto }> {
  const response = await api.get('/auth/me')
  return response.data
}

export function logout(): void {
  setAuthToken(null)
}

export async function subscribePlan(planId: string, billingCycle: 'monthly' | 'annual'): Promise<{ user: AuthUser; usage: UsageDto }> {
  const response = await api.post('/billing/subscribe', { plan_id: planId, billing_cycle: billingCycle })
  return response.data
}

export async function getAuthConfig(): Promise<{ google_client_id: string | null; google_enabled: boolean }> {
  const response = await api.get('/auth/config')
  return response.data
}

// --- Enterprise organizations + SSO ---

export interface Org {
  id: string
  slug: string
  name: string
  domain: string
  plan_id: string
  status: 'trial' | 'active' | 'expired'
  trial_ends_at: string
  activated_at: string
  billing_cycle: string
  receipt: string
  sso_issuer: string
  sso_client_id: string
  sso_configured: boolean
  role?: string | null
  created_at: string
}

export interface OrgMember extends AuthUser {
  org_role: string
}

export interface AuditEvent {
  id: string
  actor: string
  action: string
  detail: string
  created_at: string
}

export async function listMyOrgs(): Promise<{ orgs: Org[] }> {
  const response = await api.get('/orgs/mine')
  return response.data
}

export async function createOrg(name: string, slug: string, domain: string): Promise<{ org: Org }> {
  const response = await api.post('/orgs', { name, slug, domain })
  return response.data
}

export async function listOrgMembers(orgId: string): Promise<{ members: OrgMember[] }> {
  const response = await api.get(`/orgs/${encodeURIComponent(orgId)}/members`)
  return response.data
}

export async function inviteOrgMember(orgId: string, email: string, role: string): Promise<{ member: AuthUser }> {
  const response = await api.post(`/orgs/${encodeURIComponent(orgId)}/invite`, { email, role })
  return response.data
}

export async function configureOrgSso(orgId: string, issuer: string, clientId: string, clientSecret: string): Promise<{ org: Org }> {
  const response = await api.post(`/orgs/${encodeURIComponent(orgId)}/sso`, {
    issuer, client_id: clientId, client_secret: clientSecret,
  })
  return response.data
}

export async function activateOrg(orgId: string, billingCycle: string, receipt: string): Promise<{ org: Org }> {
  const response = await api.post(`/orgs/${encodeURIComponent(orgId)}/activate`, {
    billing_cycle: billingCycle, receipt,
  })
  return response.data
}

export async function getOrgAudit(orgId: string): Promise<{ events: AuditEvent[] }> {
  const response = await api.get(`/orgs/${encodeURIComponent(orgId)}/audit`)
  return response.data
}

export async function startSso(orgSlug: string): Promise<{ authorization_url: string; org: Org }> {
  const response = await api.get('/auth/sso/start', { params: { org: orgSlug } })
  return response.data
}

export async function consumeSsoCode(code: string): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>('/auth/sso/consume', { code })
  setAuthToken(response.data.access_token)
  return response.data
}

export async function createCheckoutSession(
  planId: string,
  annual: boolean,
  successUrl: string,
  cancelUrl: string,
): Promise<{ session_id: string; checkout_url: string }> {
  const response = await api.post('/billing/checkout-session', {
    plan_id: planId,
    annual,
    success_url: successUrl,
    cancel_url: cancelUrl,
  })
  return response.data
}

export async function verifyCheckoutSession(sessionId: string): Promise<{
  plan_id: string
  billing_cycle: 'monthly' | 'annual'
  session_id: string
}> {
  const response = await api.get(`/billing/checkout-session/${encodeURIComponent(sessionId)}`)
  return response.data
}

export async function getAlertConfig(): Promise<{ enabled: boolean; public_key: string | null }> {
  const response = await api.get('/alerts/config')
  return response.data
}

export async function subscribeToAlerts(subscription: PushSubscriptionJSON, location: string): Promise<void> {
  await api.post('/alerts/subscribe', { subscription, location })
}

export async function sendAlertTest(subscription: PushSubscriptionJSON): Promise<void> {
  await api.post('/alerts/test', subscription)
}
