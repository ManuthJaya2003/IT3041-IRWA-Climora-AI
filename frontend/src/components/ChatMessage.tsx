import { useState } from 'react'
import { User, Globe, AlertTriangle, CheckCircle, ExternalLink, Shield, Clock, Volume2, Loader2 } from 'lucide-react'
import { ChatResponse, textToSpeech } from '../api/climoraApi'
import { Message } from './ChatInterface'
import { uiText } from '../i18n'

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

      <div className={`max-w-[92%] sm:max-w-[85%] min-w-0 ${isUser ? 'order-first' : ''}`}>
        {/* Message Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 break-words ${
            isUser
              ? 'bg-climora-600 text-white'
              : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200'
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div>
              <FormattedText text={message.content} />
              <ReadAloudButton text={message.content} language={message.response?.language} />
            </div>
          )}
        </div>

        {/* Extended response details (only for assistant) */}
        {!isUser && message.response && (
          <ResponseDetails response={message.response} />
        )}

        {/* Timestamp */}
        <p className={`text-xs mt-1 ${isUser ? 'text-right' : 'text-left'} text-slate-400 dark:text-slate-500`}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
    <div className="text-sm whitespace-pre-wrap break-words leading-relaxed" lang="auto">
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
  const t = uiText(response.language)
  const riskFactors = response.risk_assessment?.risk_factors ?? []
  const recommendations = response.recommendations ?? []
  const sources = response.sources ?? []
  const agentsUsed = response.agents_used ?? []
  return (
    <div className="mt-3 space-y-3" lang={response.language || 'en'}>
      {/* Risk Assessment */}
      {response.risk_assessment && response.risk_assessment.risk_level !== 'unknown' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{t.riskAssessment}</span>
            </div>
            <RiskBadge level={response.risk_assessment.risk_level} lang={response.language} />
          </div>

          {/* Risk Factors */}
          {riskFactors.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">{t.riskFactors}</p>
              <div className="flex flex-wrap gap-2">
                {riskFactors.map((factor, idx) => (
                  <span
                    key={idx}
                    className="text-xs bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 px-2 py-0.5 rounded-full break-words"
                  >
                    {factor.replace(/-/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Risk Explanation */}
          {response.risk_assessment.explanation && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 leading-relaxed break-words">
              {response.risk_assessment.explanation}
            </p>
          )}
        </div>
      )}

      {/* Detailed Analysis (collapsible) */}
      {response.detailed_analysis && (
        <details className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl">
          <summary className="px-4 py-3 cursor-pointer text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl">
            {t.detailedAnalysis}
          </summary>
          <div className="px-4 pb-3">
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed break-words">{response.detailed_analysis}</p>
          </div>
        </details>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="w-4 h-4 text-climora-500" />
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{t.recommendations}</span>
          </div>
          <ul className="space-y-2.5">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <PriorityBadge priority={rec.priority} lang={response.language} />
                <div>
                  <span className="text-xs text-slate-700 dark:text-slate-200 font-medium break-words">{rec.action}</span>
                  {rec.explanation && (
                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 break-words">{rec.explanation}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <ExternalLink className="w-4 h-4 text-blue-500" />
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{t.evidenceSources}</span>
            <span className="text-xs text-slate-400 dark:text-slate-500">({sources.length})</span>
          </div>
          <ul className="space-y-2">
            {sources.map((source, idx) => (
              <li key={idx} className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2 min-w-0">
                  <span className="text-xs text-slate-400 dark:text-slate-500 shrink-0">{idx + 1}.</span>
                  <div className="min-w-0">
                    {source.source_url ? (
                      <a
                        href={source.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium break-all"
                      >
                        {source.source_name}
                      </a>
                    ) : (
                      <span className="text-xs text-slate-700 dark:text-slate-200 font-medium">{source.source_name}</span>
                    )}
                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 line-clamp-3 break-words">
                      {source.content_snippet.length > 220
                        ? `${source.content_snippet.slice(0, 220)}...`
                        : source.content_snippet}
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
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 dark:text-slate-500 px-1">
        {response.confidence_score !== null && response.confidence_score !== undefined && (
          <div className="flex items-center gap-1">
            <Shield className="w-3 h-3" />
            <span>{t.confidence}: {Math.round(response.confidence_score * 100)}%</span>
          </div>
        )}
        {response.processing_time_ms && (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>{(response.processing_time_ms / 1000).toFixed(1)}s</span>
          </div>
        )}
        {agentsUsed.length > 0 && (
          <span>{agentsUsed.length} {t.agents}</span>
        )}
      </div>

      {/* Disclaimer */}
      {response.disclaimer && (
        <p className="text-xs text-slate-400 dark:text-slate-500 italic px-1">{response.disclaimer}</p>
      )}
    </div>
  )
}

function RiskBadge({ level, lang }: { level: string; lang?: string }) {
  const t = uiText(lang)
  const config: Record<string, { bg: string; text: string; dot: string }> = {
    low: { bg: 'bg-green-100 dark:bg-green-900/40', text: 'text-green-700 dark:text-green-300', dot: 'bg-green-500' },
    moderate: { bg: 'bg-yellow-100 dark:bg-yellow-900/40', text: 'text-yellow-700 dark:text-yellow-300', dot: 'bg-yellow-500' },
    high: { bg: 'bg-orange-100 dark:bg-orange-900/40', text: 'text-orange-700 dark:text-orange-300', dot: 'bg-orange-500' },
    critical: { bg: 'bg-red-100 dark:bg-red-900/40', text: 'text-red-700 dark:text-red-300', dot: 'bg-red-500' },
    unknown: { bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-600 dark:text-slate-300', dot: 'bg-slate-400' },
  }

  const c = config[level] || config.unknown

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${c.bg} ${c.text}`}>
      <span className={`w-2 h-2 rounded-full ${c.dot}`}></span>
      {t.risk[level] ?? t.risk.unknown}
    </span>
  )
}

function PriorityBadge({ priority, lang }: { priority: string; lang?: string }) {
  const t = uiText(lang)
  const colors: Record<string, string> = {
    immediate: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
    'short-term': 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    'long-term': 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800',
  }

  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium shrink-0 ${colors[priority] || 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700'}`}>
      {t.priority[priority] ?? priority}
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


function ReadAloudButton({ text, language }: { text: string; language?: string }) {
  const t = uiText(language)
  const [isLoading, setIsLoading] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)

  const handleReadAloud = async () => {
    if (isPlaying) return

    setIsLoading(true)
    try {
      const audioUrl = await textToSpeech(text, language)
      setIsLoading(false)
      setIsPlaying(true)

      const audio = new Audio(audioUrl)
      audio.play().catch(() => {
        setIsPlaying(false)
        URL.revokeObjectURL(audioUrl)
      })
      audio.onended = () => {
        setIsPlaying(false)
        URL.revokeObjectURL(audioUrl)
      }
      audio.onerror = () => {
        setIsPlaying(false)
        URL.revokeObjectURL(audioUrl)
      }
    } catch {
      setIsLoading(false)
      setIsPlaying(false)
    }
  }

  return (
    <button
      onClick={handleReadAloud}
      disabled={isLoading || isPlaying}
      className="mt-2 flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 hover:text-climora-600 transition-colors disabled:opacity-50"
      aria-label={t.readAloud}
    >
      {isLoading ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : (
        <Volume2 className="w-3 h-3" />
      )}
      <span>{isPlaying ? t.playing : isLoading ? t.generating : t.readAloud}</span>
    </button>
  )
}
