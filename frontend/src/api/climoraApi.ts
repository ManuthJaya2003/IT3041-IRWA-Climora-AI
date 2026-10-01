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
let apiPlan = 'free'

export function setApiPlan(planId: string): void {
  apiPlan = planId
}

api.interceptors.request.use(config => {
  config.headers = config.headers ?? {}
  config.headers['X-Plan'] = apiPlan
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
  /** AbortSignal to cancel an in-flight request (never sent to the backend). */
  signal?: AbortSignal
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

// --- API Functions ---

export async function sendQuery(request: ChatRequest): Promise<ChatResponse> {
  const { signal, ...body } = request
  const response = await api.post<ChatResponse>('/chat/query', body, { signal })
  return response.data
}

// --- Speech API Functions ---

export async function sendVoiceQuery(request: {
  query: string
  location?: string
  user_type?: string
  session_id?: string
  language?: string
  signal?: AbortSignal
}): Promise<VoiceQueryResponse> {
  const { signal, ...body } = request
  const response = await api.post<VoiceQueryResponse>('/speech/voice-query', body, { signal })
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
}

export async function getPlans(): Promise<{ plans: PlanDto[] }> {
  const response = await api.get('/billing/plans')
  return response.data
}

export async function getUsage(): Promise<UsageDto> {
  const response = await api.get('/billing/usage')
  return response.data
}
