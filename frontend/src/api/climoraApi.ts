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
  const response = await api.post<ChatResponse>('/chat/query', request)
  return response.data
}

<<<<<<< Updated upstream
=======
<<<<<<< HEAD
<<<<<<< HEAD
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
  const res = await fetch(`${API_BASE_URL}/chat/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed: ${res.status}`)
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

=======
>>>>>>> 555981c5b9f10f6cd846d1a0c184e3f6346c8b0e
=======
>>>>>>> 555981c5b9f10f6cd846d1a0c184e3f6346c8b0e
>>>>>>> Stashed changes
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
}

export async function getPlans(): Promise<{ plans: PlanDto[] }> {
  const response = await api.get('/billing/plans')
  return response.data
}

export async function getUsage(): Promise<UsageDto> {
  const response = await api.get('/billing/usage')
  return response.data
}
