import { useState, useCallback, useEffect, useRef } from 'react'
import ChatInterface, { Message } from './components/ChatInterface'
import Sidebar, { Conversation } from './components/Sidebar'
import Header from './components/Header'
import PlansModal from './components/PlansModal'
import SettingsView from './components/SettingsView'
import { AppSettings, applyTheme, loadSettings, saveSettings } from './settings'
import { loadPlan, savePlan } from './plans'
import { setApiPlan } from './api/climoraApi'

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
  const [conversationsData, setConversationsData] = useState<Map<string, ConversationData>>(
    () => loadConversations(loadSettings().retentionDays),
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

  const handleChangeSettings = useCallback((patch: Partial<AppSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...patch }
      saveSettings(next)
      return next
    })
    // Retention changes prune immediately.
    if (patch.retentionDays !== undefined) {
      const days = patch.retentionDays
      if (days > 0) {
        const cutoff = Date.now() - days * 86400_000
        setConversationsData(prev => {
          const updated = new Map(prev)
          for (const [id, data] of updated) {
            if (data.conversation.timestamp.getTime() < cutoff) {
              updated.delete(id)
            }
          }
          return updated
        })
      }
    }
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
