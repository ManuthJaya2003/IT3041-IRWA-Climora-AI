import { useState, useCallback } from 'react'
import ChatInterface, { Message } from './components/ChatInterface'
import Sidebar, { Conversation } from './components/Sidebar'
import Header from './components/Header'

interface ConversationData {
  conversation: Conversation
  messages: Message[]
  sessionId: string | null
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [conversationsData, setConversationsData] = useState<Map<string, ConversationData>>(new Map())
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)

  const conversations = Array.from(conversationsData.values()).map(d => d.conversation)

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

  // Get messages for active conversation
  const activeData = activeConversationId ? conversationsData.get(activeConversationId) : null
  const activeMessages = activeData?.messages || []
  const activeSessionId = activeData?.sessionId || null

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      {sidebarOpen && (
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
        />
      )}

      {/* Main Content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
        <main className="flex-1 overflow-hidden">
          <ChatInterface
            key={activeConversationId || 'new'}
            initialMessages={activeMessages}
            initialSessionId={activeSessionId}
            onNewConversation={handleNewConversation}
            onUpdateConversation={handleUpdateConversation}
          />
        </main>
      </div>
    </div>
  )
}

export default App
