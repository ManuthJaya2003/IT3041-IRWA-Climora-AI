import { Menu, Globe, Settings } from 'lucide-react'

interface HeaderProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
  onOpenSettings: () => void
}

export default function Header({ sidebarOpen, onToggleSidebar, onOpenSettings }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-3 sm:px-6 py-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          <Menu className="w-5 h-5 text-slate-600 dark:text-slate-300" />
        </button>
        <div className="flex items-center gap-2 min-w-0">
          <Globe className="w-6 h-6 text-climora-600 shrink-0" />
          <h1 className="text-lg sm:text-xl font-semibold text-slate-800 dark:text-slate-100 truncate">Climora AI</h1>
        </div>
        <span className="hidden sm:inline px-2 py-0.5 text-xs font-medium bg-climora-100 dark:bg-climora-900/50 text-climora-700 dark:text-climora-300 rounded-full shrink-0">
          Beta
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onOpenSettings}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          aria-label="Settings"
        >
          <Settings className="w-5 h-5 text-slate-600 dark:text-slate-300" />
        </button>
      </div>
    </header>
  )
}
