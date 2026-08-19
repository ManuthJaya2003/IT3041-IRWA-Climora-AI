import { useState, useCallback } from 'react'
import ChatInterface from './components/ChatInterface'
import Sidebar, { Conversation } from './components/Sidebar'
import Header from './components/Header'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [resetKey, setResetKey] = useState(0) // Forces ChatInterface to reset

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null)
    setResetKey(prev => prev + 1)
  }, [])

  const handleNewConversation = useCallback((id: string, firstQuery: string) => {
    // Truncate query for sidebar title
    const title = firstQuery.length > 35 ? firstQuery.slice(0, 35) + '...' : firstQuery
    const newConv: Conversation = {
      id,
      title,
      timestamp: new Date(),
    }
    setConversations(prev => [newConv, ...prev])
    setActiveConversationId(id)
  }, [])

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id)
    // Note: Full conversation loading would require backend persistence
    // For now, selecting just highlights it in the sidebar
  }, [])

  const handleDeleteConversation = useCallback((id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConversationId === id) {
      setActiveConversationId(null)
      setResetKey(prev => prev + 1)
    }
  }, [activeConversationId])

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
            key={resetKey}
            onNewConversation={handleNewConversation}
          />
        </main>
      </div>
    </div>
  )
}

export default App
