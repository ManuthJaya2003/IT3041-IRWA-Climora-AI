import { useEffect, useState } from 'react'
import {
  ArrowLeft, Bell, Check, Crown, Download, Info, Palette,
  Shield, SlidersHorizontal, Trash2, User, Sun, Moon, Monitor,
} from 'lucide-react'
import { AppSettings, LANGUAGES, RETENTION_OPTIONS, Theme, USER_TYPES } from '../settings'
import { getUsage, UsageDto } from '../api/climoraApi'

type SectionId = 'general' | 'appearance' | 'personalization' | 'notifications' | 'data' | 'subscription' | 'about'

const SECTIONS: Array<{ id: SectionId; label: string; icon: typeof Bell }> = [
  { id: 'general', label: 'General', icon: SlidersHorizontal },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'personalization', label: 'Personalization', icon: User },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'data', label: 'Data & privacy', icon: Shield },
  { id: 'subscription', label: 'Subscription', icon: Crown },
  { id: 'about', label: 'About', icon: Info },
]

interface SettingsViewProps {
  settings: AppSettings
  onChange: (patch: Partial<AppSettings>) => void
  plan: string
  conversationCount: number
  onExportHistory: () => void
  onClearHistory: () => void
  onViewPlans: () => void
  onBack: () => void
}

export default function SettingsView({
  settings,
  onChange,
  plan,
  conversationCount,
  onExportHistory,
  onClearHistory,
  onViewPlans,
  onBack,
}: SettingsViewProps) {
  const [section, setSection] = useState<SectionId>('general')
  const [usage, setUsage] = useState<UsageDto | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)
  const [notifPermission, setNotifPermission] = useState<string>(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
  )

  useEffect(() => {
    let cancelled = false
    getUsage().then(data => {
      if (!cancelled) setUsage(data)
    }).catch(() => {
      // Offline — usage panel simply stays hidden.
    })
    return () => {
      cancelled = true
    }
  }, [])

  const requestNotifPermission = async () => {
    try {
      const result = await Notification.requestPermission()
      setNotifPermission(result)
    } catch {
      // ignore — status text already reflects reality
    }
  }

  // Turning alerts on doubles as the permission gesture, so the browser
  // prompt appears immediately instead of failing silently later.
  const handleAlertsToggle = async (v: boolean) => {
    onChange({ alertsEnabled: v })
    if (v && typeof Notification !== 'undefined' && Notification.permission === 'default') {
      await requestNotifPermission()
    }
  }

  const ActiveIcon = SECTIONS.find(s => s.id === section)?.icon ?? SlidersHorizontal

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 sm:px-6 py-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <button
          onClick={onBack}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          aria-label="Back to chat"
        >
          <ArrowLeft className="w-5 h-5 text-slate-600 dark:text-slate-300" />
        </button>
        <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Settings</h1>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 flex flex-col md:flex-row gap-6">
          {/* Section nav */}
          <nav className="md:w-52 shrink-0 flex md:flex-col gap-1 overflow-x-auto" aria-label="Settings sections">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setSection(id)}
                aria-current={section === id ? 'page' : undefined}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm whitespace-nowrap transition-colors ${
                  section === id
                    ? 'bg-climora-100 dark:bg-climora-900/40 text-climora-800 dark:text-climora-200 font-medium'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </button>
            ))}
          </nav>

          {/* Content */}
          <div className="flex-1 min-w-0 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 sm:p-6">
            <div className="flex items-center gap-2 mb-5">
              <ActiveIcon className="w-5 h-5 text-climora-600" />
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {SECTIONS.find(s => s.id === section)?.label}
              </h2>
            </div>

            {section === 'general' && (
              <div className="space-y-5">
                <Field label="Answer language" hint="Sinhala / Tamil queries are always answered in that language.">
                  <select
                    value={settings.language}
                    onChange={e => onChange({ language: e.target.value as AppSettings['language'] })}
                    className={selectCls}
                  >
                    {LANGUAGES.map(l => (
                      <option key={l.value} value={l.value}>{l.label}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Default location" hint="Prefilled for every new chat. You can still override it per message.">
                  <input
                    type="text"
                    value={settings.location}
                    onChange={e => onChange({ location: e.target.value })}
                    onBlur={e => onChange({ location: e.target.value.trim() })}
                    placeholder="e.g. Colombo, Sri Lanka"
                    className={selectCls}
                  />
                </Field>
              </div>
            )}

            {section === 'appearance' && (
              <div className="space-y-3">
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Choose how Climora looks. System follows your device setting.
                </p>
                <div className="grid grid-cols-3 gap-3">
                  {([
                    { value: 'light', label: 'Light', icon: Sun },
                    { value: 'dark', label: 'Dark', icon: Moon },
                    { value: 'system', label: 'System', icon: Monitor },
                  ] as Array<{ value: Theme; label: string; icon: typeof Sun }>)
                    .map(({ value, label, icon: Icon }) => {
                      const active = settings.theme === value
                      return (
                        <button
                          key={value}
                          onClick={() => onChange({ theme: value })}
                          aria-pressed={active}
                          className={`flex flex-col items-center gap-2 rounded-xl border px-3 py-4 text-sm transition-colors ${
                            active
                              ? 'border-climora-500 bg-climora-50 dark:bg-climora-900/30 text-climora-800 dark:text-climora-200 font-medium'
                              : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-climora-300'
                          }`}
                        >
                          <Icon className="w-5 h-5" />
                          {label}
                          {active && <Check className="w-4 h-4 text-climora-600" />}
                        </button>
                      )
                    })}
                </div>
              </div>
            )}

            {section === 'personalization' && (
              <div className="space-y-5">
                <Field label="Display name" hint="Used to greet you on the home screen. Stored only in this browser.">
                  <input
                    type="text"
                    value={settings.displayName}
                    onChange={e => onChange({ displayName: e.target.value.slice(0, 40) })}
                    onBlur={e => onChange({ displayName: e.target.value.trim() })}
                    placeholder="e.g. Nimal"
                    className={selectCls}
                  />
                </Field>
                <Field label="I am a…" hint="Recommendations are tailored to your role (farmer, student, business…).">
                  <select
                    value={settings.userType}
                    onChange={e => onChange({ userType: e.target.value })}
                    className={selectCls}
                  >
                    {USER_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </Field>
              </div>
            )}

            {section === 'notifications' && (
              <div className="space-y-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Severe-weather alerts</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      Show a browser notification when a response assesses high or critical risk.
                    </p>
                  </div>
                  <Toggle
                    checked={settings.alertsEnabled}
                    onChange={handleAlertsToggle}
                    label="Severe-weather alerts"
                  />
                </div>
                <div className="flex items-center justify-between gap-4 border-t border-slate-100 dark:border-slate-800 pt-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Browser permission</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      Status: <span className="font-medium">{notifPermission}</span>
                    </p>
                  </div>
                  {notifPermission !== 'granted' && notifPermission !== 'unsupported' && (
                    <button
                      onClick={requestNotifPermission}
                      className="px-3 py-1.5 text-sm font-medium bg-climora-600 text-white rounded-lg hover:bg-climora-700 transition-colors shrink-0"
                    >
                      Enable
                    </button>
                  )}
                </div>
                {notifPermission === 'denied' && (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    Permission was denied — allow notifications in your browser's site settings to use alerts.
                  </p>
                )}
              </div>
            )}

            {section === 'data' && (
              <div className="space-y-5">
                <Field label="Keep chat history for" hint="Older conversations are removed from this browser automatically.">
                  <select
                    value={settings.retentionDays}
                    onChange={e => onChange({ retentionDays: Number(e.target.value) })}
                    className={selectCls}
                  >
                    {RETENTION_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </Field>
                <div className="flex items-center justify-between gap-4 border-t border-slate-100 dark:border-slate-800 pt-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Export my data</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      Download all {conversationCount} conversation{conversationCount === 1 ? '' : 's'} as JSON.
                    </p>
                  </div>
                  <button
                    onClick={onExportHistory}
                    disabled={conversationCount === 0}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 rounded-lg hover:border-climora-400 hover:bg-climora-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 shrink-0"
                  >
                    <Download className="w-4 h-4" />
                    Export
                  </button>
                </div>
                <div className="border-t border-slate-100 dark:border-slate-800 pt-4">
                  {confirmClear ? (
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-slate-600 dark:text-slate-300 flex-1">Delete all conversations?</p>
                      <button
                        onClick={() => { onClearHistory(); setConfirmClear(false) }}
                        className="px-3 py-1.5 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setConfirmClear(false)}
                        className="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
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
              </div>
            )}

            {section === 'subscription' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                      Current plan: <span className="capitalize">{plan}</span>
                    </p>
                    {usage ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        {usage.used_today}{usage.daily_limit > 0 ? ` / ${usage.daily_limit}` : ' (unlimited)'} queries used today
                      </p>
                    ) : (
                      <p className="text-xs text-slate-400 mt-0.5">Usage unavailable offline.</p>
                    )}
                  </div>
                  <button
                    onClick={onViewPlans}
                    className="px-3 py-1.5 text-sm font-medium bg-climora-600 text-white rounded-lg hover:bg-climora-700 transition-colors shrink-0"
                  >
                    Manage plan
                  </button>
                </div>
                {usage && usage.daily_limit > 0 && (
                  <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden" role="progressbar"
                    aria-valuenow={usage.used_today} aria-valuemin={0} aria-valuemax={usage.daily_limit}
                    aria-label="Daily query usage">
                    <div
                      className="h-full bg-climora-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (usage.used_today / usage.daily_limit) * 100)}%` }}
                    />
                  </div>
                )}
              </div>
            )}

            {section === 'about' && (
              <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
                <p><span className="font-semibold text-slate-800 dark:text-slate-100">Climora AI v0.1.0</span> — Sri Lanka's AI-powered climate intelligence assistant.</p>
                <p>Multi-agent pipeline (security → NLP → retrieval → analysis → verification → recommendations) over live weather data and curated climate evidence, in English, Sinhala and Tamil.</p>
                <p className="text-xs text-slate-400">Responses are for awareness only — for emergencies contact local authorities. Conversations stay in this browser unless you export them.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

const selectCls =
  'w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2.5 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500'

function Field({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
        {label}
      </label>
      {children}
      <p className="text-xs text-slate-400 mt-1.5">{hint}</p>
    </div>
  )
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${checked ? 'bg-climora-600' : 'bg-slate-300 dark:bg-slate-600'}`}
    >
      <span
        className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${checked ? 'left-[22px]' : 'left-0.5'}`}
      />
    </button>
  )
}
