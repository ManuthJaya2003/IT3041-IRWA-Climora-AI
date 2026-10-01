import { useState, useCallback, useEffect, useRef } from 'react'
import ChatInterface, { Message } from './components/ChatInterface'
import Sidebar, { Conversation } from './components/Sidebar'
import Header from './components/Header'
import PlansModal from './components/PlansModal'
import SettingsView from './components/SettingsView'
import { AppSettings, applyTheme, loadSettings, saveSettings } from './settings'
import { FALLBACK_PLANS, Plan, addLocation, loadLocations, loadPlan, removeLocation, savePlan } from './plans'
import { getPlans, setApiPlan } from './api/climoraApi'

interface ConversationData {
  conversation: Conversation
  messages: Message[]
  sessionId: string | null
}

const STORAGE_KEY = 'climora-conversations'
const ACTIVE_CONVERSATION_KEY = 'climora-active-conversation'

function loadConversations(retentionDays: number): Map<string, ConversationData> {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return new Map()

    const entries: unknown = JSON.parse(saved)
    if (!Array.isArray(entries)) return new Map()

    const cutoff = retentionDays > 0 ? Date.now() - retentionDays * 86400_000 : 0
    const result = new Map<string, ConversationData>()
    for (const entry of entries) {
      if (!Array.isArray(entry) || entry.length !== 2) continue
      const [id, data] = entry as [unknown, Partial<ConversationData>]
      if (typeof id !== 'string' || !data || typeof data !== 'object') continue
      if (!data.conversation || !Array.isArray(data.messages)) continue
      const timestamp = new Date(data.conversation.timestamp)
      if (Number.isNaN(timestamp.getTime())) continue
      if (cutoff > 0 && timestamp.getTime() < cutoff) continue // retention policy
      result.set(id, {
        conversation: { ...data.conversation, id, timestamp },
        messages: data.messages
          .filter(m => m && typeof m.content === 'string')
          .map(message => ({
            ...message,
            timestamp: new Date(message.timestamp),
          })),
        sessionId: typeof data.sessionId === 'string' ? data.sessionId : null,
      })
    }
    return result
  } catch {
    return new Map()
  }
}

function planById(plans: Plan[], id: string): Plan {
  return plans.find(p => p.id === id) ?? FALLBACK_PLANS[0]
}

/** Plan caps always apply; the user setting can only shorten retention further. 0 = unlimited. */
function effectiveRetention(userDays: number, planDays: number): number {
  if (planDays <= 0) return userDays
  return userDays <= 0 ? planDays : Math.min(userDays, planDays)
}

function pruneMap(prev: Map<string, ConversationData>, days: number): Map<string, ConversationData> {
  if (days <= 0) return prev
  const cutoff = Date.now() - days * 86400_000
  const updated = new Map(prev)
  for (const [id, data] of updated) {
    if (data.conversation.timestamp.getTime() < cutoff) {
      updated.delete(id)
    }
  }
  return updated
}

function persist(key: string, value: string | null) {
  try {
    if (value === null) {
      localStorage.removeItem(key)
    } else {
      localStorage.setItem(key, value)
    }
  } catch {
    // Private-mode / quota errors must never crash the app.
  }
}

function App() {
  const [view, setView] = useState<'chat' | 'settings'>('chat')
  // On phones the sidebar starts closed (it opens as an overlay drawer).
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window === 'undefined' || !window.matchMedia('(max-width: 767px)').matches,
  )
  const [plansOpen, setPlansOpen] = useState(false)
  const [settings, setSettings] = useState<AppSettings>(loadSettings)
  const [plan, setPlan] = useState<string>(loadPlan)
  const [plans, setPlans] = useState<Plan[]>(FALLBACK_PLANS)
  const [savedLocations, setSavedLocations] = useState<string[]>(loadLocations)
  const [conversationsData, setConversationsData] = useState<Map<string, ConversationData>>(
    () => {
      // First load already respects the plan's history cap (live catalogue re-prunes after).
      const s = loadSettings()
      return loadConversations(effectiveRetention(s.retentionDays, planById(FALLBACK_PLANS, loadPlan()).history_days))
    },
  )
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_CONVERSATION_KEY)
    } catch {
      return null
    }
  })

  // Apply theme now and follow OS changes while "System" is selected.
  const themeRef = useRef(settings.theme)
  themeRef.current = settings.theme
  useEffect(() => {
    applyTheme(themeRef.current)
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme(themeRef.current)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  useEffect(() => {
    applyTheme(settings.theme)
  }, [settings.theme])

  useEffect(() => {
    persist(STORAGE_KEY, JSON.stringify(Array.from(conversationsData.entries())))
  }, [conversationsData])

  useEffect(() => {
    persist(ACTIVE_CONVERSATION_KEY, activeConversationId)
  }, [activeConversationId])

  const planDef = planById(plans, plan)
  const locationLimit = planDef.max_saved_locations
  const effectiveDays = effectiveRetention(settings.retentionDays, planDef.history_days)

  // Live plan catalogue for limits (falls back to bundled data offline).
  useEffect(() => {
    let cancelled = false
    getPlans()
      .then(data => {
        if (!cancelled && Array.isArray(data.plans) && data.plans.length > 0) {
          setPlans(data.plans)
        }
      })
      .catch(() => {
        // Offline — FALLBACK_PLANS already in state.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Enforce the effective retention whenever plan, catalogue or setting changes.
  useEffect(() => {
    setConversationsData(prev => pruneMap(prev, effectiveDays))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, plans, settings.retentionDays])

  const handleChangeSettings = useCallback((patch: Partial<AppSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...patch }
      saveSettings(next)
      return next
    })
  }, [])

  const handleAddLocation = useCallback((name: string): string | null => {
    const limit = planById(plans, plan).max_saved_locations
    const { locations, error } = addLocation(savedLocations, name, limit)
    if (!error) setSavedLocations(locations)
    return error
  }, [plan, plans, savedLocations])

  const handleRemoveLocation = useCallback((name: string) => {
    setSavedLocations(prev => removeLocation(prev, name))
  }, [])

  const handleSelectPlan = useCallback((planId: string) => {
    setPlan(planId)
    savePlan(planId)
    setApiPlan(planId)
  }, [])

  // Attach the commercial plan to every API request (quota enforcement).
  useEffect(() => {
    setApiPlan(plan)
  }, [plan])

  const conversations = Array.from(conversationsData.values()).map(d => d.conversation)

  // Drop a stale active id left over from deleted / corrupted history.
  const validActiveId = activeConversationId && conversationsData.has(activeConversationId)
    ? activeConversationId
    : null

  const closeSidebarOnMobile = () => {
    if (window.matchMedia('(max-width: 767px)').matches) {
      setSidebarOpen(false)
    }
  }

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null)
    setView('chat')
    closeSidebarOnMobile()
  }, [])

  const handleNewConversation = useCallback((id: string, firstQuery: string, messages: Message[]) => {
    const title = firstQuery.length > 35 ? firstQuery.slice(0, 35) + '...' : firstQuery
    const newData: ConversationData = {
      conversation: { id, title, timestamp: new Date() },
      messages,
      sessionId: id,
    }
    setConversationsData(prev => {
      const updated = new Map(prev)
      updated.set(id, newData)
      return updated
    })
    setActiveConversationId(id)
  }, [])

  const handleUpdateConversation = useCallback((id: string, messages: Message[]) => {
    setConversationsData(prev => {
      const updated = new Map(prev)
      const existing = updated.get(id)
      if (existing) {
        updated.set(id, { ...existing, messages })
      }
      return updated
    })
  }, [])

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id)
    setView('chat')
    closeSidebarOnMobile()
  }, [])

  const handleDeleteConversation = useCallback((id: string) => {
    setConversationsData(prev => {
      const updated = new Map(prev)
      updated.delete(id)
      return updated
    })
    if (activeConversationId === id) {
      setActiveConversationId(null)
    }
  }, [activeConversationId])

  const handleClearHistory = useCallback(() => {
    setConversationsData(new Map())
    setActiveConversationId(null)
  }, [])

  const handleExportHistory = useCallback(() => {
    try {
      const data = Array.from(conversationsData.values()).map(d => ({
        id: d.conversation.id,
        title: d.conversation.title,
        timestamp: d.conversation.timestamp.toISOString(),
        sessionId: d.sessionId,
        messages: d.messages.map(m => ({
          role: m.role,
          content: m.content,
          timestamp: new Date(m.timestamp).toISOString(),
        })),
      }))
      const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), conversations: data }, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `climora-history-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      // Download failures must never crash the app.
    }
  }, [conversationsData])

  // Get messages for active conversation
  const activeData = validActiveId ? conversationsData.get(validActiveId) : null
  const activeMessages = activeData?.messages || []
  const activeSessionId = activeData?.sessionId || null

  return (
    <div className="flex h-dvh bg-slate-50 dark:bg-slate-950">
      {/* Sidebar (overlay drawer on mobile, static column on desktop) */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-slate-900/50 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <Sidebar
            conversations={conversations}
            activeConversationId={validActiveId}
            currentPlan={plan}
            onNewChat={handleNewChat}
            onSelectConversation={handleSelectConversation}
            onDeleteConversation={handleDeleteConversation}
            onViewPlans={() => setPlansOpen(true)}
            onClose={() => setSidebarOpen(false)}
          />
        </>
      )}

      {/* Main Content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onOpenSettings={() => setView('settings')}
        />
        <main className="flex-1 overflow-hidden">
          {view === 'settings' ? (
            <SettingsView
              settings={settings}
              onChange={handleChangeSettings}
              plan={plan}
              locationLimit={locationLimit}
              planHistoryDays={planDef.history_days}
              savedLocations={savedLocations}
              onAddLocation={handleAddLocation}
              onRemoveLocation={handleRemoveLocation}
              conversationCount={conversations.length}
              onExportHistory={handleExportHistory}
              onClearHistory={handleClearHistory}
              onViewPlans={() => setPlansOpen(true)}
              onBack={() => setView('chat')}
            />
          ) : (
            <ChatInterface
              key={validActiveId || 'new'}
              initialMessages={activeMessages}
              initialSessionId={activeSessionId}
              defaultLanguage={settings.language}
              defaultLocation={settings.location}
              userType={settings.userType}
              displayName={settings.displayName}
              alertsEnabled={settings.alertsEnabled}
              savedLocations={savedLocations}
              onNewConversation={handleNewConversation}
              onUpdateConversation={handleUpdateConversation}
            />
          )}
        </main>
      </div>

      <PlansModal
        open={plansOpen}
        currentPlan={plan}
        onSelectPlan={handleSelectPlan}
        onClose={() => setPlansOpen(false)}
      />
    </div>
  )
}

export default App
