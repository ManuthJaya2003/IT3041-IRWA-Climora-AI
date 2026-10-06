export type AnswerLanguage = 'en' | 'si' | 'ta'
export type Theme = 'light' | 'dark' | 'system'

export interface AppSettings {
  language: AnswerLanguage
  location: string
  userType: string
  displayName: string
  theme: Theme
  alertsEnabled: boolean
  /** Chat-history retention in days. 0 = keep forever. */
  retentionDays: number
}

export const DEFAULT_SETTINGS: AppSettings = {
  language: 'en',
  location: '',
  userType: 'individual',
  displayName: '',
  theme: 'system',
  alertsEnabled: false,
  retentionDays: 0,
}

export const LANGUAGES: Array<{ value: AnswerLanguage; label: string }> = [
  { value: 'en', label: 'English' },
  { value: 'si', label: 'සිංහල (Sinhala)' },
  { value: 'ta', label: 'தமிழ் (Tamil)' },
]

export const USER_TYPES: Array<{ value: string; label: string }> = [
  { value: 'individual', label: 'Individual' },
  { value: 'student', label: 'Student' },
  { value: 'farmer', label: 'Farmer' },
  { value: 'business', label: 'Business' },
  { value: 'organization', label: 'Organization' },
  { value: 'institution', label: 'Institution' },
  { value: 'traveller', label: 'Traveller / Tourist' },
]

export const RETENTION_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 0, label: 'Keep forever' },
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
]

const SETTINGS_KEY = 'climora-settings'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Merge stored settings over defaults so older saved versions keep working. */
export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    const parsed: unknown = JSON.parse(raw)
    if (!isRecord(parsed)) return { ...DEFAULT_SETTINGS }
    const language = parsed.language === 'si' || parsed.language === 'ta' ? parsed.language : 'en'
    const location = typeof parsed.location === 'string' ? parsed.location : ''
    const userType = USER_TYPES.some(t => t.value === parsed.userType)
      ? (parsed.userType as string)
      : DEFAULT_SETTINGS.userType
    const displayName = typeof parsed.displayName === 'string'
      ? parsed.displayName.slice(0, 40)
      : ''
    const theme: Theme = parsed.theme === 'light' || parsed.theme === 'dark' ? parsed.theme : 'system'
    const alertsEnabled = parsed.alertsEnabled === true
    const retentionDays = RETENTION_OPTIONS.some(o => o.value === parsed.retentionDays)
      ? (parsed.retentionDays as number)
      : DEFAULT_SETTINGS.retentionDays
    return { language, location, userType, displayName, theme, alertsEnabled, retentionDays }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveSettings(settings: AppSettings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
  } catch {
    // Private-mode / quota errors must never crash the app.
  }
}

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-color-scheme: dark)').matches
}

/** Apply the theme to <html> so Tailwind's `dark:` variants take effect. */
export function applyTheme(theme: Theme): void {
  const dark = theme === 'dark' || (theme === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', dark)
}
