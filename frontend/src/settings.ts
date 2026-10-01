export type AnswerLanguage = 'en' | 'si' | 'ta'

export interface AppSettings {
  language: AnswerLanguage
  location: string
  userType: string
}

export const DEFAULT_SETTINGS: AppSettings = {
  language: 'en',
  location: '',
  userType: 'individual',
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
]

const SETTINGS_KEY = 'climora-settings'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

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
    return { language, location, userType }
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
