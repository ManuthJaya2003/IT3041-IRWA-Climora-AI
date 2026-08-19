import { MessageSquare, Plus, Clock, Trash2 } from 'lucide-react'

export interface Conversation {
  id: string
  title: string
  timestamp: Date
}

interface SidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
}

export default function Sidebar({
  conversations,
  activeConversationId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
}: SidebarProps) {
  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col">
      {/* New Chat Button */}
      <div className="p-4">
        <button
          onClick={onNewChat}
          className="flex items-center gap-2 w-full px-4 py-2.5 bg-climora-600 hover:bg-climora-700 rounded-lg transition-colors font-medium text-sm"
        >
          <Plus className="w-4 h-4" />
          New Climate Query
        </button>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto px-3">
        {conversations.length > 0 && (
          <>
            <div className="flex items-center gap-2 px-2 py-2 text-xs font-medium text-slate-400 uppercase">
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
            <p className="text-xs text-slate-500">No conversations yet.</p>
            <p className="text-xs text-slate-500 mt-1">Ask a climate question to get started.</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-slate-400 text-center">
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
      className={`group flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer ${
        active
          ? 'bg-slate-700 text-white'
          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
      }`}
      onClick={onClick}
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
        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-600 rounded transition-opacity"
        aria-label="Delete conversation"
      >
        <Trash2 className="w-3 h-3 text-slate-400" />
      </button>
    </div>
  )
}
