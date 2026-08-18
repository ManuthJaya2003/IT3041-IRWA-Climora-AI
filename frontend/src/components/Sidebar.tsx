import { MessageSquare, Plus, Clock } from 'lucide-react'

export default function Sidebar() {
  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col">
      {/* New Chat Button */}
      <div className="p-4">
        <button className="flex items-center gap-2 w-full px-4 py-2.5 bg-climora-600 hover:bg-climora-700 rounded-lg transition-colors font-medium text-sm">
          <Plus className="w-4 h-4" />
          New Climate Query
        </button>
      </div>

      {/* Recent Conversations */}
      <div className="flex-1 overflow-y-auto px-3">
        <div className="flex items-center gap-2 px-2 py-2 text-xs font-medium text-slate-400 uppercase">
          <Clock className="w-3 h-3" />
          Recent
        </div>

        {/* Placeholder conversations */}
        <div className="space-y-1">
          <ConversationItem
            title="Flood risk in Colombo area"
            active={true}
          />
          <ConversationItem
            title="Drought conditions for farming"
            active={false}
          />
          <ConversationItem
            title="Monsoon season preparation"
            active={false}
          />
        </div>
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

function ConversationItem({ title, active }: { title: string; active: boolean }) {
  return (
    <button
      className={`flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-left transition-colors ${
        active
          ? 'bg-slate-700 text-white'
          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
      }`}
    >
      <MessageSquare className="w-4 h-4 shrink-0" />
      <span className="truncate">{title}</span>
    </button>
  )
}
