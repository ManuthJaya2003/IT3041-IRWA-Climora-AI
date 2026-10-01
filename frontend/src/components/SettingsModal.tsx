import { useEffect, useState } from 'react'
import { X, Trash2 } from 'lucide-react'
import { AppSettings, LANGUAGES, USER_TYPES } from '../settings'

interface SettingsModalProps {
  open: boolean
  settings: AppSettings
  onSave: (settings: AppSettings) => void
  onClose: () => void
  onClearHistory: () => void
}

export default function SettingsModal({
  open,
  settings,
  onSave,
  onClose,
  onClearHistory,
}: SettingsModalProps) {
  const [draft, setDraft] = useState<AppSettings>(settings)
  const [confirmClear, setConfirmClear] = useState(false)

  // Refresh the draft every time the modal opens.
  useEffect(() => {
    if (open) {
      setDraft(settings)
      setConfirmClear(false)
    }
  }, [open, settings])

  // Close on Escape.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const handleSave = () => {
    onSave({ ...draft, location: draft.location.trim() })
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <div
        className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-slate-800">Settings</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Close settings"
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Answer language */}
        <label className="block text-sm font-medium text-slate-700 mb-1.5" htmlFor="settings-language">
          Answer language
        </label>
        <select
          id="settings-language"
          value={draft.language}
          onChange={e => setDraft({ ...draft, language: e.target.value as AppSettings['language'] })}
          className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-climora-500 mb-4"
        >
          {LANGUAGES.map(l => (
            <option key={l.value} value={l.value}>{l.label}</option>
          ))}
        </select>
        <p className="text-xs text-slate-400 -mt-3 mb-4">
          Sinhala / Tamil queries are always answered in that language.
        </p>

        {/* Default location */}
        <label className="block text-sm font-medium text-slate-700 mb-1.5" htmlFor="settings-location">
          Default location
        </label>
        <input
          id="settings-location"
          type="text"
          value={draft.location}
          onChange={e => setDraft({ ...draft, location: e.target.value })}
          placeholder="e.g. Colombo, Sri Lanka"
          className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500 mb-4"
        />

        {/* User type */}
        <label className="block text-sm font-medium text-slate-700 mb-1.5" htmlFor="settings-usertype">
          I am a…
        </label>
        <select
          id="settings-usertype"
          value={draft.userType}
          onChange={e => setDraft({ ...draft, userType: e.target.value })}
          className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-climora-500 mb-6"
        >
          {USER_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        {/* Danger zone */}
        <div className="border-t border-slate-200 pt-4 mb-5">
          {confirmClear ? (
            <div className="flex items-center gap-2">
              <p className="text-sm text-slate-600 flex-1">Delete all conversations?</p>
              <button
                onClick={() => { onClearHistory(); setConfirmClear(false) }}
                className="px-3 py-1.5 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmClear(false)}
                className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmClear(true)}
              className="flex items-center gap-2 text-sm text-red-600 hover:text-red-700 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Clear all chat history
            </button>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
