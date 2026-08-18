import { Menu, Globe, Settings } from 'lucide-react'

interface HeaderProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

export default function Header({ sidebarOpen, onToggleSidebar }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          <Menu className="w-5 h-5 text-slate-600" />
        </button>
        <div className="flex items-center gap-2">
          <Globe className="w-6 h-6 text-climora-600" />
          <h1 className="text-xl font-semibold text-slate-800">Climora AI</h1>
        </div>
        <span className="px-2 py-0.5 text-xs font-medium bg-climora-100 text-climora-700 rounded-full">
          Beta
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
          aria-label="Settings"
        >
          <Settings className="w-5 h-5 text-slate-600" />
        </button>
      </div>
    </header>
  )
}
