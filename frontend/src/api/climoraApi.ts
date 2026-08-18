import axios from 'axios'

const API_BASE_URL = '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// --- Types ---

export interface ChatRequest {
  query: string
  location?: string
  user_type?: string
  session_id?: string
  context?: Record<string, unknown>
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
}

export interface AgentInfo {
  name: string
  role: string
  status: string
  owner: string
}

// --- API Functions ---

export async function sendQuery(request: ChatRequest): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>('/chat/query', request)
  return response.data
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
