import { useEffect, useState } from 'react'
import { MessageSquare, Plus, Clock, Trash2, Crown, X } from 'lucide-react'
import { getUsage } from '../api/climoraApi'
import { onUsageChanged } from '../usageBus'

export interface Conversation {
  id: string
  title: string
  timestamp: Date
}

interface SidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  currentPlan: string
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
  onViewPlans: () => void
  onClose: () => void
}

export default function Sidebar({
  conversations,
  activeConversationId,
  currentPlan,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  onViewPlans,
  onClose,
}: SidebarProps) {
  const [used, setUsed] = useState<number | null>(null)
  const [limit, setLimit] = useState<number | null>(null)

  // Live daily quota from the backend - refreshes when the plan changes,
  // the moment any query completes, and every minute as a fallback.
  // Hidden when offline.
  useEffect(() => {
    let cancelled = false
    const load = () => {
      getUsage()
        .then(data => {
          if (!cancelled) {
            setUsed(data.used_today)
            setLimit(data.daily_limit)
          }
        })
        .catch(() => {
          if (!cancelled) {
            setUsed(null)
            setLimit(null)
          }
        })
    }
    load()
    const off = onUsageChanged(load)
    const timer = setInterval(load, 60000)
    return () => {
      cancelled = true
      off()
      clearInterval(timer)
    }
  }, [currentPlan])

  const percent = used !== null && limit !== null && limit > 0
    ? Math.min(100, Math.round((used / limit) * 100))
    : null
  const lowQuota = percent !== null && percent >= 80

  return (
    <aside className="fixed md:static inset-y-0 left-0 z-40 w-64 max-w-[85vw] bg-white dark:bg-slate-900 text-slate-700 dark:text-white border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0">
      {/* New Chat Button */}
      <div className="p-4 flex items-center gap-2">
        <button
          onClick={onNewChat}
          className="flex items-center justify-center gap-2 flex-1 px-4 py-2.5 bg-climora-600 hover:bg-climora-700 rounded-xl transition-colors font-medium text-sm text-white"
        >
          <Plus className="w-4 h-4" />
          New Climate Query
        </button>
        <button
          onClick={onClose}
          className="md:hidden p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5 text-slate-500 dark:text-slate-300" />
        </button>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto px-3">
        {conversations.length > 0 && (
          <>
            <div className="flex items-center gap-2 px-2 py-2 text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wide">
              <Clock className="w-3 h-3" />
              Recent
            </div>

            <div className="space-y-1">
              {conversations.map(conv => (
                <ConversationItem
                  key={conv.id}
                  title={conv.title}
                  active={conv.id === activeConversationId}
                  onClick={() => onSelectConversation(conv.id)}
                  onDelete={() => onDeleteConversation(conv.id)}
                />
              ))}
            </div>
          </>
        )}

        {conversations.length === 0 && (
          <div className="px-3 py-8 text-center">
            <p className="text-xs text-slate-400 dark:text-slate-500">No conversations yet.</p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Ask a climate question to get started.</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
        <button
          onClick={onViewPlans}
          className="block w-full px-3 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-xl transition-colors text-left"
          aria-label={`View plans. ${percent !== null ? `${percent}% of daily queries used.` : ''}`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-medium text-slate-700 dark:text-slate-200">
              <Crown className="w-3.5 h-3.5 text-amber-500" />
              {currentPlan === 'free' ? 'Free plan' : `${currentPlan[0].toUpperCase()}${currentPlan.slice(1)} plan`}
            </span>
            {percent !== null ? (
              <span className={`text-xs font-semibold ${lowQuota ? 'text-amber-600 dark:text-amber-400' : 'text-slate-400 dark:text-slate-500'}`}>
                {percent}%
              </span>
            ) : (
              <span className="text-xs text-slate-400 dark:text-slate-500">Upgrade</span>
            )}
          </div>
          {percent !== null && limit !== null && limit > 0 ? (
            <>
              <div className="h-1.5 mt-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden" role="progressbar"
                aria-valuenow={used ?? 0} aria-valuemin={0} aria-valuemax={limit}
                aria-label="Daily query usage">
                <div
                  className={`h-full rounded-full transition-all ${lowQuota ? 'bg-amber-500' : 'bg-climora-500'}`}
                  style={{ width: `${percent}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1.5">
                {used} / {limit} queries today{lowQuota ? ' - upgrade for more' : ''}
              </p>
            </>
          ) : (
            <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1">
              {limit === 0 ? 'Unlimited queries' : 'View plans & pricing'}
            </p>
          )}
        </button>
        <div className="text-xs text-slate-400 dark:text-slate-500 text-center">
          Climora AI v0.1.0
        </div>
      </div>
    </aside>
  )
}

function ConversationItem({
  title,
  active,
  onClick,
  onDelete,
}: {
  title: string
  active: boolean
  onClick: () => void
  onDelete: () => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      className={`group flex items-center justify-between w-full px-3 py-2 rounded-xl text-sm transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-climora-500 ${
        active
          ? 'bg-climora-50 dark:bg-slate-800 text-climora-800 dark:text-slate-100 font-medium'
          : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <MessageSquare className="w-4 h-4 shrink-0" />
        <span className="truncate">{title}</span>
      </div>
      <button
        onClick={e => {
          e.stopPropagation()
          onDelete()
        }}
        className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-opacity"
        aria-label="Delete conversation"
      >
        <Trash2 className="w-3 h-3 text-slate-400" />
      </button>
    </div>
  )
}
