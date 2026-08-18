import { User, Globe, AlertTriangle, CheckCircle, ExternalLink } from 'lucide-react'
import { ChatResponse } from '../api/climoraApi'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  response?: ChatResponse
  timestamp: Date
}

interface ChatMessageProps {
  message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-climora-100 flex items-center justify-center shrink-0">
          <Globe className="w-4 h-4 text-climora-600" />
        </div>
      )}

      <div className={`max-w-[80%] ${isUser ? 'order-first' : ''}`}>
        {/* Message Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-climora-600 text-white'
              : 'bg-white border border-slate-200 text-slate-700'
          }`}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Extended response details (only for assistant) */}
        {!isUser && message.response && (
          <ResponseDetails response={message.response} />
        )}

        {/* Timestamp */}
        <p className={`text-xs mt-1 ${isUser ? 'text-right' : 'text-left'} text-slate-400`}>
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0">
          <User className="w-4 h-4 text-slate-600" />
        </div>
      )}
    </div>
  )
}

function ResponseDetails({ response }: { response: ChatResponse }) {
  return (
    <div className="mt-3 space-y-3">
      {/* Risk Assessment */}
      {response.risk_assessment && (
        <div className="bg-white border border-slate-200 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-medium text-slate-600">Risk Assessment</span>
          </div>
          <div className="flex items-center gap-2">
            <RiskBadge level={response.risk_assessment.risk_level} />
            {response.risk_assessment.explanation && (
              <span className="text-xs text-slate-500">
                {response.risk_assessment.explanation}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {response.recommendations.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-climora-500" />
            <span className="text-xs font-medium text-slate-600">Recommendations</span>
          </div>
          <ul className="space-y-1.5">
            {response.recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-medium shrink-0">
                  {rec.priority}
                </span>
                <span className="text-xs text-slate-600">{rec.action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sources */}
      {response.sources.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <ExternalLink className="w-4 h-4 text-blue-500" />
            <span className="text-xs font-medium text-slate-600">Sources</span>
          </div>
          <ul className="space-y-1">
            {response.sources.map((source, idx) => (
              <li key={idx} className="text-xs text-slate-500">
                {source.source_url ? (
                  <a
                    href={source.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    {source.source_name}
                  </a>
                ) : (
                  source.source_name
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Confidence & Agents */}
      <div className="flex items-center gap-3 text-xs text-slate-400">
        {response.confidence_score !== null && response.confidence_score !== undefined && (
          <span>Confidence: {Math.round(response.confidence_score * 100)}%</span>
        )}
        {response.processing_time_ms && (
          <span>{Math.round(response.processing_time_ms)}ms</span>
        )}
        {response.agents_used.length > 0 && (
          <span>{response.agents_used.length} agents used</span>
        )}
      </div>

      {/* Disclaimer */}
      {response.disclaimer && (
        <p className="text-xs text-slate-400 italic">{response.disclaimer}</p>
      )}
    </div>
  )
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    low: 'bg-green-100 text-green-700',
    moderate: 'bg-yellow-100 text-yellow-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700',
    unknown: 'bg-slate-100 text-slate-600',
  }

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[level] || colors.unknown}`}>
      {level.charAt(0).toUpperCase() + level.slice(1)}
    </span>
  )
}
