import { useState, useCallback, useEffect } from 'react'
import ChatInterface, { Message } from './components/ChatInterface'
import Sidebar, { Conversation } from './components/Sidebar'
import Header from './components/Header'
import SettingsModal from './components/SettingsModal'
import PlansModal from './components/PlansModal'
import { AppSettings, loadSettings, saveSettings } from './settings'
import { loadPlan, savePlan } from './plans'
import { setApiPlan } from './api/climoraApi'

interface ConversationData {
  conversation: Conversation
  messages: Message[]
  sessionId: string | null
}

const STORAGE_KEY = 'climora-conversations'
const ACTIVE_CONVERSATION_KEY = 'climora-active-conversation'

function loadConversations(): Map<string, ConversationData> {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return new Map()

    const entries: unknown = JSON.parse(saved)
    if (!Array.isArray(entries)) return new Map()

    const result = new Map<string, ConversationData>()
    for (const entry of entries) {
      if (!Array.isArray(entry) || entry.length !== 2) continue
      const [id, data] = entry as [unknown, Partial<ConversationData>]
      if (typeof id !== 'string' || !data || typeof data !== 'object') continue
      if (!data.conversation || !Array.isArray(data.messages)) continue
      const timestamp = new Date(data.conversation.timestamp)
      if (Number.isNaN(timestamp.getTime())) continue
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
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [plansOpen, setPlansOpen] = useState(false)
  const [settings, setSettings] = useState<AppSettings>(loadSettings)
  const [plan, setPlan] = useState<string>(loadPlan)
  const [conversationsData, setConversationsData] = useState<Map<string, ConversationData>>(loadConversations)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_CONVERSATION_KEY)
    } catch {
      return null
    }
  })

  useEffect(() => {
    persist(STORAGE_KEY, JSON.stringify(Array.from(conversationsData.entries())))
  }, [conversationsData])

  useEffect(() => {
    persist(ACTIVE_CONVERSATION_KEY, activeConversationId)
  }, [activeConversationId])

  const handleSaveSettings = useCallback((next: AppSettings) => {
    setSettings(next)
    saveSettings(next)
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

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null)
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
    setSettingsOpen(false)
  }, [])

  // Get messages for active conversation
  const activeData = validActiveId ? conversationsData.get(validActiveId) : null
  const activeMessages = activeData?.messages || []
  const activeSessionId = activeData?.sessionId || null

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      {sidebarOpen && (
        <Sidebar
          conversations={conversations}
          activeConversationId={validActiveId}
          currentPlan={plan}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onViewPlans={() => setPlansOpen(true)}
        />
      )}

      {/* Main Content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        <main className="flex-1 overflow-hidden">
          <ChatInterface
            key={validActiveId || 'new'}
            initialMessages={activeMessages}
            initialSessionId={activeSessionId}
            defaultLanguage={settings.language}
            defaultLocation={settings.location}
            userType={settings.userType}
            onNewConversation={handleNewConversation}
            onUpdateConversation={handleUpdateConversation}
          />
        </main>
      </div>

      <SettingsModal
        open={settingsOpen}
        settings={settings}
        currentPlan={plan}
        onSave={handleSaveSettings}
        onClose={() => setSettingsOpen(false)}
        onClearHistory={handleClearHistory}
        onViewPlans={() => setPlansOpen(true)}
      />

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
