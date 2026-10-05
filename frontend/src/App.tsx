import { useState, useCallback, useEffect, useRef } from 'react'
import { CheckCircle2, X } from 'lucide-react'
import ChatInterface, { Message } from './components/ChatInterface'
import Sidebar, { Conversation } from './components/Sidebar'
import Header from './components/Header'
import AgentMesh from './components/AgentMesh'
import type { AgentStreamEvent } from './api/climoraApi'
import PlansModal from './components/PlansModal'
import CheckoutModal, { CheckoutResult } from './components/CheckoutModal'
import SettingsView from './components/SettingsView'
import { AppSettings, applyTheme, loadSettings, saveSettings } from './settings'
import { FALLBACK_PLANS, Plan, Subscription, addLocation, clearSubscription, loadLocations, loadPlan, loadSubscription, removeLocation, savePlan, saveSubscription } from './plans'
import { getPlans, setApiPlan, verifyCheckoutSession } from './api/climoraApi'
import { notifyUsageChanged } from './usageBus'

interface ConversationData {
  conversation: Conversation
  messages: Message[]
  sessionId: string | null
  meshInteractions?: MeshInteraction[]
}

export interface MeshInteraction {
  id: string
  agent: string
  outcome: string
}

const STORAGE_KEY = 'climora-conversations'
const ACTIVE_CONVERSATION_KEY = 'climora-active-conversation'
const EMPTY_MESH_INTERACTIONS: MeshInteraction[] = []

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
        meshInteractions: Array.isArray(data.meshInteractions)
          ? data.meshInteractions.filter(
              item => item && typeof item.agent === 'string' && typeof item.outcome === 'string',
            )
          : [],
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
  // Live state for the Agent Mesh panel.
  const [isProcessing, setIsProcessing] = useState(false)
  const [meshEvent, setMeshEvent] = useState<AgentStreamEvent | null>(null)
  const [meshSeq, setMeshSeq] = useState(0)
  const [pendingMeshInteractions, setPendingMeshInteractions] = useState<MeshInteraction[]>([])

  const handleAgentEvent = useCallback((event: AgentStreamEvent) => {
    setMeshEvent(event)
    setMeshSeq(s => s + 1)
    if (event.type === 'pipeline_start') {
      setPendingMeshInteractions([])
      return
    }
    if (event.type !== 'agent_start' && event.type !== 'agent_end') return

    setPendingMeshInteractions(previous => {
      const agent = event.agent
      if (!agent) return previous
      const outcome = event.type === 'agent_start' ? 'in-flight' : (event.outcome || 'success')
      const existing = previous.findIndex(item => item.agent === agent)
      const next = existing < 0
        ? [...previous, { id: `${agent}-${Date.now()}`, agent, outcome }]
        : previous.map((item, index) => index === existing ? { ...item, outcome } : item)
      if (JSON.stringify(previous) === JSON.stringify(next)) return previous
      return next
    })
  }, [])

  const [plansOpen, setPlansOpen] = useState(false)
  const [settings, setSettings] = useState<AppSettings>(loadSettings)
  const [plan, setPlan] = useState<string>(loadPlan)
  const [plans, setPlans] = useState<Plan[]>(FALLBACK_PLANS)
  const [savedLocations, setSavedLocations] = useState<string[]>(loadLocations)
  const [subscription, setSubscription] = useState<Subscription | null>(loadSubscription)
  const [checkout, setCheckout] = useState<{ plan: Plan; annual: boolean } | null>(null)
  const [paymentNotice, setPaymentNotice] = useState<string | null>(null)
  const checkoutVerificationStarted = useRef(false)
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

  useEffect(() => {
    if (!activeConversationId) return
    setConversationsData(conversations => {
      const current = conversations.get(activeConversationId)
      if (!current || JSON.stringify(current.meshInteractions || EMPTY_MESH_INTERACTIONS) === JSON.stringify(pendingMeshInteractions)) {
        return conversations
      }
      const updated = new Map(conversations)
      updated.set(activeConversationId, { ...current, meshInteractions: pendingMeshInteractions })
      return updated
    })
  }, [activeConversationId, pendingMeshInteractions])

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
    if (planId === 'free') {
      // Downgrade cancels any demo subscription.
      setSubscription(null)
      clearSubscription()
    }
    // New quota applies immediately — refresh every usage display.
    notifyUsageChanged()
  }, [])

  const handleCheckoutSuccess = useCallback((result: CheckoutResult) => {
    if (!checkout) return
    const sub: Subscription = {
      planId: checkout.plan.id,
      cycle: result.cycle,
      startedAt: new Date().toISOString(),
      receipt: result.receipt,
    }
    saveSubscription(sub)
    setSubscription(sub)
    setPlan(checkout.plan.id)
    savePlan(checkout.plan.id)
    setApiPlan(checkout.plan.id)
    notifyUsageChanged()
    setCheckout(null)
  }, [checkout])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sessionId = params.get('session_id')
    if (params.get('checkout') !== 'success' || !sessionId || checkoutVerificationStarted.current) return
    checkoutVerificationStarted.current = true

    verifyCheckoutSession(sessionId)
      .then(result => {
        const selectedPlan = planById(plans, result.plan_id)
        const sub: Subscription = {
          planId: selectedPlan.id,
          cycle: result.billing_cycle,
          startedAt: new Date().toISOString(),
          receipt: result.session_id,
        }
        saveSubscription(sub)
        setSubscription(sub)
        setPlan(selectedPlan.id)
        savePlan(selectedPlan.id)
        setApiPlan(selectedPlan.id)
        notifyUsageChanged()
        setPaymentNotice(`${selectedPlan.name} plan activated successfully. Your new benefits are now available.`)
        window.history.replaceState({}, document.title, window.location.pathname)
      })
      .catch(error => {
        console.error('Unable to verify Stripe checkout:', error)
        setPaymentNotice('Payment was received, but we could not verify the plan yet. Please refresh and try again.')
        window.history.replaceState({}, document.title, window.location.pathname)
      })
  }, [plans])

  // Attach the commercial plan to every API request (quota enforcement).
  useEffect(() => {
    setApiPlan(plan)
  }, [plan])

  const conversations = Array.from(conversationsData.values())
    .map(d => d.conversation)
    .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())

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
    setPendingMeshInteractions([])
    setView('chat')
    closeSidebarOnMobile()
  }, [])

  const handleNewConversation = useCallback((id: string, firstQuery: string, messages: Message[]) => {
    const title = firstQuery.length > 35 ? firstQuery.slice(0, 35) + '...' : firstQuery
    const newData: ConversationData = {
      conversation: { id, title, timestamp: new Date() },
      messages,
      sessionId: id,
      meshInteractions: pendingMeshInteractions,
    }
    setConversationsData(prev => {
      const updated = new Map(prev)
      updated.set(id, newData)
      return updated
    })
    setActiveConversationId(id)
  }, [pendingMeshInteractions])

  const handleUpdateConversation = useCallback((id: string, messages: Message[]) => {
    setConversationsData(prev => {
      const updated = new Map(prev)
      const existing = updated.get(id)
      if (existing) {
        updated.set(id, {
          ...existing,
          messages,
          conversation: { ...existing.conversation, timestamp: new Date() },
        })
      }
      return updated
    })
  }, [])

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id)
    setPendingMeshInteractions(conversationsData.get(id)?.meshInteractions || [])
    setView('chat')
    closeSidebarOnMobile()
  }, [conversationsData])

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
  const activeMeshInteractions = activeData?.meshInteractions || (
    validActiveId ? EMPTY_MESH_INTERACTIONS : pendingMeshInteractions
  )

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
        {paymentNotice && (
          <div
            className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/60 px-4"
            role="presentation"
            onClick={() => setPaymentNotice(null)}
          >
            <div
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="payment-notice-title"
              className="relative w-full max-w-sm rounded-2xl border border-emerald-200 bg-white p-6 text-center shadow-2xl dark:border-emerald-800 dark:bg-slate-900"
              onClick={event => event.stopPropagation()}
            >
              <button
                type="button"
                aria-label="Close payment notification"
                onClick={() => setPaymentNotice(null)}
                className="absolute right-5 top-5 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
              <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-emerald-500" />
              <h2 id="payment-notice-title" className="text-lg font-semibold text-slate-900 dark:text-white">
                {paymentNotice.includes('successfully') ? 'Payment successful' : 'Payment verification'}
              </h2>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{paymentNotice}</p>
              <button
                type="button"
                onClick={() => setPaymentNotice(null)}
                className="mt-5 rounded-xl bg-climora-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-climora-700"
              >
                Close
              </button>
            </div>
          </div>
        )}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <main className="flex-1 min-w-0 overflow-hidden">
            {view === 'settings' ? (
              <SettingsView
                settings={settings}
                onChange={handleChangeSettings}
                plan={plan}
                subscription={subscription}
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
                onProcessingChange={setIsProcessing}
                onAgentEvent={handleAgentEvent}
              />
            )}
          </main>
          {view === 'chat' && (
            <AgentMesh
              active={isProcessing}
              event={meshEvent}
              seq={meshSeq}
              initialInteractions={activeMeshInteractions}
            />
          )}
        </div>
      </div>

      <PlansModal
        open={plansOpen}
        currentPlan={plan}
        onSelectPlan={handleSelectPlan}
        onCheckout={(p, annual) => setCheckout({ plan: p, annual })}
        onClose={() => setPlansOpen(false)}
      />

      <CheckoutModal
        open={checkout !== null}
        plan={checkout?.plan ?? null}
        annual={checkout?.annual ?? false}
        onSuccess={handleCheckoutSuccess}
        onClose={() => setCheckout(null)}
      />
    </div>
  )
}

export default App
