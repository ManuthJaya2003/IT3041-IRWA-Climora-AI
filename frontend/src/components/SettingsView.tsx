import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft, Bell, Check, Crown, Download, Info, Lock, Palette,
  Search, Shield, SlidersHorizontal, Trash2, User, Sun, Moon, Monitor, FlaskConical, MapPin, X,
} from 'lucide-react'
import { AppSettings, LANGUAGES, RETENTION_OPTIONS, Theme, USER_TYPES } from '../settings'
import { getUsage, UsageDto } from '../api/climoraApi'
import { Subscription } from '../plans'
import { onUsageChanged } from '../usageBus'

type SectionId = 'general' | 'appearance' | 'personalization' | 'notifications' | 'data' | 'subscription' | 'about'

const SECTIONS: Array<{ id: SectionId; label: string; icon: typeof Bell; keywords: string }> = [
  { id: 'general', label: 'General', icon: SlidersHorizontal, keywords: 'general language location region default' },
  { id: 'appearance', label: 'Appearance', icon: Palette, keywords: 'appearance theme dark light mode display' },
  { id: 'personalization', label: 'Personalization', icon: User, keywords: 'personalization name profile user type farmer student' },
  { id: 'notifications', label: 'Notifications', icon: Bell, keywords: 'notifications alerts browser push severe weather test' },
  { id: 'data', label: 'Data & privacy', icon: Shield, keywords: 'data privacy export download history retention delete clear' },
  { id: 'subscription', label: 'Subscription', icon: Crown, keywords: 'subscription plan billing quota usage premium pricing' },
  { id: 'about', label: 'About', icon: Info, keywords: 'about version info help' },
]

interface SettingsViewProps {
  settings: AppSettings
  onChange: (patch: Partial<AppSettings>) => void
  plan: string
  subscription: Subscription | null
  /** Max saved locations for the current plan (0 = unlimited). */
  locationLimit: number
  /** History cap in days for the current plan (0 = unlimited). */
  planHistoryDays: number
  savedLocations: string[]
  /** Returns an error message when the add is rejected, else null. */
  onAddLocation: (name: string) => string | null
  onRemoveLocation: (name: string) => void
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
  subscription,
  locationLimit,
  planHistoryDays,
  savedLocations,
  onAddLocation,
  onRemoveLocation,
  conversationCount,
  onExportHistory,
  onClearHistory,
  onViewPlans,
  onBack,
}: SettingsViewProps) {
  const [section, setSection] = useState<SectionId>('general')
  const [query, setQuery] = useState('')
  const [usage, setUsage] = useState<UsageDto | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)
  const [testSent, setTestSent] = useState(false)
  const [notifPermission, setNotifPermission] = useState<string>(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported',
  )

  const notifApi = typeof Notification !== 'undefined'
  const isSecure = typeof window !== 'undefined' && !!window.isSecureContext
  const alertsLocked = plan === 'free'

  // Search filters the section list; jump to the first match.
  const visibleSections = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return SECTIONS
    return SECTIONS.filter(
      s => s.label.toLowerCase().includes(q) || s.keywords.includes(q),
    )
  }, [query])

  useEffect(() => {
    if (!visibleSections.some(s => s.id === section) && visibleSections.length > 0) {
      setSection(visibleSections[0].id)
    }
  }, [visibleSections, section])

  // Escape returns to chat (unless a modal dialog is open on top).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector('[role="dialog"]')) onBack()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onBack])

  useEffect(() => {
    let cancelled = false
    const loadUsage = () => {
      getUsage().then(data => {
        if (!cancelled) setUsage(data)
      }).catch(() => {
        // Offline — usage panel simply stays hidden.
      })
    }
    loadUsage()
    const off = onUsageChanged(loadUsage)
    return () => {
      cancelled = true
      off()
    }
  }, [plan])

  const requestNotifPermission = async () => {
    try {
      const result = await Notification.requestPermission()
      setNotifPermission(result)
      return result
    } catch {
      return notifPermission
    }
  }

  // Turning alerts on doubles as the permission gesture, so the browser
  // prompt appears immediately instead of failing silently later.
  const handleAlertsToggle = async (v: boolean) => {
    onChange({ alertsEnabled: v })
    if (v && notifApi && Notification.permission === 'default') {
      await requestNotifPermission()
    }
  }

  const sendTestNotification = async () => {
    if (!notifApi) return
    try {
      if (Notification.permission === 'default') {
        await requestNotifPermission()
      }
      if (Notification.permission === 'granted') {
        new Notification('Climora AI — test alert', {
          body: 'Notifications are working. High or critical risk responses will alert you here.',
        })
        setTestSent(true)
      }
    } catch {
      setTestSent(false)
    }
  }

  const ActiveIcon = SECTIONS.find(s => s.id === section)?.icon ?? SlidersHorizontal

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950">
      {/* Top bar */}
      <div className="px-4 sm:px-6 py-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
            aria-label="Back to chat"
          >
            <ArrowLeft className="w-5 h-5 text-slate-600 dark:text-slate-300" />
          </button>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-100 leading-tight">Settings</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">Manage your Climora experience</p>
          </div>
        </div>
        <div className="flex justify-center mt-3">
          <div className="relative w-full max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="search"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search settings…"
              aria-label="Search settings"
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 pl-9 pr-3 py-2 text-base sm:text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 flex flex-col md:flex-row gap-6">
          {/* Section nav */}
          <nav className="md:w-52 shrink-0 flex md:flex-col gap-1 overflow-x-auto pb-1" aria-label="Settings sections">
            {visibleSections.map(({ id, label, icon: Icon }) => (
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
            {visibleSections.length === 0 && (
              <p className="text-sm text-slate-400 px-3 py-2">No settings match “{query}”.</p>
            )}
          </nav>

          {/* Content */}
          <div className="flex-1 min-w-0 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 sm:p-6 h-fit">
            <div className="flex items-center gap-2 mb-1">
              <ActiveIcon className="w-5 h-5 text-climora-600" />
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {SECTIONS.find(s => s.id === section)?.label}
              </h2>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">{SECTION_SUBTITLES[section]}</p>

            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {section === 'general' && (
                <>
                  <Row label="Answer language" hint="Sinhala / Tamil queries are always answered in that language.">
                    <select
                      value={settings.language}
                      onChange={e => onChange({ language: e.target.value as AppSettings['language'] })}
                      className={selectCls}
                      aria-label="Answer language"
                    >
                      {LANGUAGES.map(l => (
                        <option key={l.value} value={l.value}>{l.label}</option>
                      ))}
                    </select>
                  </Row>
                  <Row label="Default location" hint="Prefilled for every new chat. You can still override it per message.">
                    <input
                      type="text"
                      value={settings.location}
                      onChange={e => onChange({ location: e.target.value })}
                      onBlur={e => onChange({ location: e.target.value.trim() })}
                      placeholder="e.g. Colombo, Sri Lanka"
                      className={selectCls}
                      aria-label="Default location"
                    />
                  </Row>
                  <div className="py-4">
                    <SavedLocations
                      locations={savedLocations}
                      limit={locationLimit}
                      onAdd={onAddLocation}
                      onRemove={onRemoveLocation}
                      onViewPlans={onViewPlans}
                    />
                  </div>
                </>
              )}

              {section === 'appearance' && (
                <div className="py-4">
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
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
                <>
                  <Row label="Display name" hint="Used to greet you on the home screen. Stored only in this browser.">
                    <input
                      type="text"
                      value={settings.displayName}
                      onChange={e => onChange({ displayName: e.target.value.slice(0, 40) })}
                      onBlur={e => onChange({ displayName: e.target.value.trim() })}
                      placeholder="e.g. Nimal"
                      className={selectCls}
                      aria-label="Display name"
                    />
                  </Row>
                  <Row label="I am a…" hint="Recommendations are tailored to your role (farmer, student, business…).">
                    <select
                      value={settings.userType}
                      onChange={e => onChange({ userType: e.target.value })}
                      className={selectCls}
                      aria-label="User type"
                    >
                      {USER_TYPES.map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </Row>
                </>
              )}

              {section === 'notifications' && (
                alertsLocked ? (
                  <div className="py-4 flex items-start gap-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-4">
                    <Lock className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Premium feature</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        Severe-weather alerts are available on Premium and above.
                      </p>
                      <button
                        onClick={onViewPlans}
                        className="mt-2 px-3 py-1.5 text-sm font-medium bg-climora-600 text-white rounded-lg hover:bg-climora-700 transition-colors"
                      >
                        View plans
                      </button>
                    </div>
                  </div>
                ) : (
                <>
                  <Row label="Severe-weather alerts" hint="Notify me when a response assesses high or critical risk.">
                    <div className="flex sm:justify-end">
                      <Toggle
                        checked={settings.alertsEnabled}
                        onChange={handleAlertsToggle}
                        label="Severe-weather alerts"
                      />
                    </div>
                  </Row>
                  <div className="py-4 space-y-3">
                    <StatusLine label="Browser support" value={notifApi ? 'Available' : 'Not supported in this browser'} ok={notifApi} />
                    <StatusLine
                      label="Connection"
                      value={isSecure ? 'Secure (HTTPS / localhost)' : 'Not secure — use HTTPS or localhost'}
                      ok={isSecure}
                    />
                    <StatusLine label="Permission" value={notifPermission} ok={notifPermission === 'granted'} />
                    <div className="flex flex-wrap gap-2 pt-1">
                      {notifApi && isSecure && notifPermission !== 'granted' && (
                        <button
                          onClick={requestNotifPermission}
                          className="px-3 py-1.5 text-sm font-medium bg-climora-600 text-white rounded-lg hover:bg-climora-700 transition-colors"
                        >
                          Enable notifications
                        </button>
                      )}
                      {notifApi && isSecure && notifPermission === 'granted' && (
                        <button
                          onClick={sendTestNotification}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 rounded-lg hover:border-climora-400 hover:bg-climora-50 dark:hover:bg-slate-800 transition-colors"
                        >
                          <FlaskConical className="w-4 h-4" />
                          Send test notification
                        </button>
                      )}
                    </div>
                    {testSent && (
                      <p className="text-xs text-climora-700 dark:text-climora-300">
                        Test sent — check your system notifications tray.
                      </p>
                    )}
                    {notifPermission === 'denied' && (
                      <p className="text-xs text-amber-600 dark:text-amber-400">
                        Permission was denied — allow notifications in your browser's site settings to use alerts.
                      </p>
                    )}
                  </div>
                </>
                )
              )}

              {section === 'data' && (
                <>
                  <Row
                    label="Keep chat history for"
                    hint={planHistoryDays > 0
                      ? `Your ${plan} plan keeps up to ${planHistoryDays} days. You can shorten this further.`
                      : 'Older conversations are removed from this browser automatically.'}
                  >
                    <select
                      value={settings.retentionDays}
                      onChange={e => onChange({ retentionDays: Number(e.target.value) })}
                      className={selectCls}
                      aria-label="History retention"
                    >
                      {RETENTION_OPTIONS.map(o => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </Row>
                  <Row
                    label="Export my data"
                    hint={`Download all ${conversationCount} conversation${conversationCount === 1 ? '' : 's'} as JSON.`}
                  >
                    <div className="flex sm:justify-end">
                      <button
                        onClick={onExportHistory}
                        disabled={conversationCount === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 rounded-lg hover:border-climora-400 hover:bg-climora-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
                      >
                        <Download className="w-4 h-4" />
                        Export
                      </button>
                    </div>
                  </Row>
                  <div className="py-4">
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
                </>
              )}

              {section === 'subscription' && (
                <div className="py-4 space-y-4">
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
                  {subscription && subscription.planId === plan && plan !== 'free' && (
                    <div className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2">
                      {subscription.cycle === 'annual' ? 'Annual' : 'Monthly'} billing · started{' '}
                      {new Date(subscription.startedAt).toLocaleDateString()} · receipt{' '}
                      <span className="font-mono">{subscription.receipt}</span>{' '}
                      <span className="text-slate-400">(demo checkout — no charge)</span>
                    </div>
                  )}
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
                <div className="py-4 space-y-3 text-sm text-slate-600 dark:text-slate-300">
                  <p><span className="font-semibold text-slate-800 dark:text-slate-100">Climora AI v0.1.0</span> — Sri Lanka's AI-powered climate intelligence assistant.</p>
                  <p>Multi-agent pipeline (security → NLP → retrieval → analysis → verification → recommendations) over live weather data and curated climate evidence, in English, Sinhala and Tamil.</p>
                  <p className="text-xs text-slate-400">Responses are for awareness only — for emergencies contact local authorities. Conversations stay in this browser unless you export them.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const SECTION_SUBTITLES: Record<SectionId, string> = {
  general: 'Language and location defaults for new chats.',
  appearance: 'Light, dark, or follow your device.',
  personalization: 'Make Climora address you and your role.',
  notifications: 'Get pinged when risk is high. Diagnose issues here.',
  data: 'Retention, export, and deletion of your conversations.',
  subscription: 'Your plan and daily query usage.',
  about: 'What Climora AI is and how it works.',
}

const selectCls =
  'w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2.5 text-base sm:text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500'

/** Label + description on the left, control on the right (stacked on mobile). */
function Row({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="sm:flex sm:items-center sm:justify-between sm:gap-6 py-4">
      <div className="sm:max-w-[55%]">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{hint}</p>
      </div>
      <div className="mt-2.5 sm:mt-0 sm:w-64 shrink-0">{children}</div>
    </div>
  )
}

function SavedLocations({ locations, limit, onAdd, onRemove, onViewPlans }: {
  locations: string[]
  limit: number
  onAdd: (name: string) => string | null
  onRemove: (name: string) => void
  onViewPlans: () => void
}) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = () => {
    const err = onAdd(draft)
    setError(err)
    if (!err) setDraft('')
  }

  const full = limit > 0 && locations.length >= limit

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Saved locations</p>
        <p className="text-xs text-slate-400">
          {limit > 0 ? `${locations.length} / ${limit} used` : `${locations.length} saved (unlimited)`}
        </p>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
        Quick picks for the chat location box. Limits follow your plan.
      </p>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={draft}
            onChange={e => { setDraft(e.target.value); setError(null) }}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); submit() } }}
            placeholder={full ? 'Limit reached — upgrade for more' : 'e.g. Galle, Sri Lanka'}
            aria-label="Add a saved location"
            disabled={full}
            className="w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 pl-9 pr-3 py-2 text-base sm:text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
        <button
          onClick={submit}
          disabled={full}
          className="px-3 py-2 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add
        </button>
      </div>
      {full && (
        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1.5">
          Location limit reached.{' '}
          <button onClick={onViewPlans} className="font-medium underline hover:no-underline">
            Upgrade for more
          </button>
        </p>
      )}
      {error && (
        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1.5">
          {error}{' '}
          <button onClick={onViewPlans} className="font-medium underline hover:no-underline">
            View plans
          </button>
        </p>
      )}
      {locations.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {locations.map(loc => (
            <span
              key={loc}
              className="inline-flex items-center gap-1.5 text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 pl-2.5 pr-1.5 py-1 rounded-full"
            >
              {loc}
              <button
                onClick={() => onRemove(loc)}
                className="p-0.5 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                aria-label={`Remove ${loc}`}
              >
                <X className="w-3 h-3 text-slate-400" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function StatusLine({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span className={`inline-flex items-center gap-1.5 font-medium ${ok ? 'text-climora-700 dark:text-climora-300' : 'text-amber-600 dark:text-amber-400'}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-climora-500' : 'bg-amber-500'}`} />
        {value}
      </span>
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
