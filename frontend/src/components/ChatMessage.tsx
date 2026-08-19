import { User, Globe, AlertTriangle, CheckCircle, ExternalLink, Shield, Clock } from 'lucide-react'
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
        <div className="w-8 h-8 rounded-full bg-climora-100 flex items-center justify-center shrink-0 mt-1">
          <Globe className="w-4 h-4 text-climora-600" />
        </div>
      )}

      <div className={`max-w-[85%] ${isUser ? 'order-first' : ''}`}>
        {/* Message Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-climora-600 text-white'
              : 'bg-white border border-slate-200 text-slate-700'
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <FormattedText text={message.content} />
          )}
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
        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0 mt-1">
          <User className="w-4 h-4 text-slate-600" />
        </div>
      )}
    </div>
  )
}

/** Renders text with basic markdown support (bold, newlines) */
function FormattedText({ text }: { text: string }) {
  // Convert **bold** to <strong> and handle newlines
  const parts = text.split(/(\*\*[^*]+\*\*)/g)

  return (
    <div className="text-sm whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
        }
        return <span key={i}>{part}</span>
      })}
    </div>
  )
}

function ResponseDetails({ response }: { response: ChatResponse }) {
  return (
    <div className="mt-3 space-y-3">
      {/* Risk Assessment */}
      {response.risk_assessment && response.risk_assessment.risk_level !== 'unknown' && (
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span className="text-xs font-semibold text-slate-700">Risk Assessment</span>
            </div>
            <RiskBadge level={response.risk_assessment.risk_level} />
          </div>

          {/* Risk Factors */}
          {response.risk_assessment.risk_factors.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-slate-500 mb-1.5">Risk Factors:</p>
              <div className="flex flex-wrap gap-1.5">
                {response.risk_assessment.risk_factors.map((factor, idx) => (
                  <span
                    key={idx}
                    className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full"
                  >
                    {factor}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Risk Explanation */}
          {response.risk_assessment.explanation && (
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              {response.risk_assessment.explanation}
            </p>
          )}
        </div>
      )}

      {/* Detailed Analysis (collapsible) */}
      {response.detailed_analysis && (
        <details className="bg-white border border-slate-200 rounded-xl">
          <summary className="px-4 py-3 cursor-pointer text-xs font-semibold text-slate-700 hover:bg-slate-50 rounded-xl">
            Detailed Analysis
          </summary>
          <div className="px-4 pb-3">
            <p className="text-xs text-slate-600 leading-relaxed">{response.detailed_analysis}</p>
          </div>
        </details>
      )}

      {/* Recommendations */}
      {response.recommendations.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="w-4 h-4 text-climora-500" />
            <span className="text-xs font-semibold text-slate-700">Recommendations</span>
          </div>
          <ul className="space-y-2.5">
            {response.recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <PriorityBadge priority={rec.priority} />
                <div>
                  <span className="text-xs text-slate-700 font-medium">{rec.action}</span>
                  {rec.explanation && (
                    <p className="text-xs text-slate-400 mt-0.5">{rec.explanation}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sources */}
      {response.sources.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <ExternalLink className="w-4 h-4 text-blue-500" />
            <span className="text-xs font-semibold text-slate-700">Evidence Sources</span>
            <span className="text-xs text-slate-400">({response.sources.length})</span>
          </div>
          <ul className="space-y-2">
            {response.sources.map((source, idx) => (
              <li key={idx} className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2 min-w-0">
                  <span className="text-xs text-slate-400 shrink-0">{idx + 1}.</span>
                  <div className="min-w-0">
                    {source.source_url ? (
                      <a
                        href={source.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline font-medium"
                      >
                        {source.source_name}
                      </a>
                    ) : (
                      <span className="text-xs text-slate-700 font-medium">{source.source_name}</span>
                    )}
                    <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">
                      {source.content_snippet.slice(0, 120)}...
                    </p>
                  </div>
                </div>
                {source.reliability_score !== null && source.reliability_score !== undefined && source.reliability_score > 0 && (
                  <ReliabilityBadge score={source.reliability_score} />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer: Confidence, Time, Agents */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 px-1">
        {response.confidence_score !== null && response.confidence_score !== undefined && (
          <div className="flex items-center gap-1">
            <Shield className="w-3 h-3" />
            <span>Confidence: {Math.round(response.confidence_score * 100)}%</span>
          </div>
        )}
        {response.processing_time_ms && (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>{(response.processing_time_ms / 1000).toFixed(1)}s</span>
          </div>
        )}
        {response.agents_used.length > 0 && (
          <span>{response.agents_used.length} agents</span>
        )}
      </div>

      {/* Disclaimer */}
      {response.disclaimer && (
        <p className="text-xs text-slate-400 italic px-1">{response.disclaimer}</p>
      )}
    </div>
  )
}

function RiskBadge({ level }: { level: string }) {
  const config: Record<string, { bg: string; text: string; dot: string }> = {
    low: { bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' },
    moderate: { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500' },
    high: { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
    critical: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
    unknown: { bg: 'bg-slate-100', text: 'text-slate-600', dot: 'bg-slate-400' },
  }

  const c = config[level] || config.unknown

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${c.bg} ${c.text}`}>
      <span className={`w-2 h-2 rounded-full ${c.dot}`}></span>
      {level.charAt(0).toUpperCase() + level.slice(1)} Risk
    </span>
  )
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    immediate: 'bg-red-100 text-red-700 border-red-200',
    'short-term': 'bg-amber-100 text-amber-700 border-amber-200',
    'long-term': 'bg-blue-100 text-blue-700 border-blue-200',
  }

  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium shrink-0 ${colors[priority] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
      {priority}
    </span>
  )
}

function ReliabilityBadge({ score }: { score: number }) {
  const percentage = Math.round(score * 100)
  let color = 'text-slate-400'
  if (percentage >= 70) color = 'text-green-600'
  else if (percentage >= 50) color = 'text-amber-600'

  return (
    <span className={`text-xs font-medium shrink-0 ${color}`}>
      {percentage}%
    </span>
  )
}
