import { useState, useCallback, useRef, useEffect } from 'react'

/* Minimal Web Speech API types — not included in TypeScript's DOM lib. */
interface SpeechRecognitionAlternative {
  transcript: string
  confidence: number
}
interface SpeechRecognitionResult {
  isFinal: boolean
  length: number
  [index: number]: SpeechRecognitionAlternative
}
interface SpeechRecognitionResultList {
  length: number
  [index: number]: SpeechRecognitionResult
}
interface SpeechRecognitionEvent extends Event {
  resultIndex: number
  results: SpeechRecognitionResultList
}
interface SpeechRecognitionErrorEvent extends Event {
  error: string
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  lang: string
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
interface SpeechRecognitionCtor {
  new (): SpeechRecognitionInstance
}
declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
}

interface SpeechRecognitionHook {
  isListening: boolean
  transcript: string
  startListening: (lang?: string) => void
  stopListening: () => void
  clearTranscript: () => void
  isSupported: boolean
  error: string | null
}

// Language codes for Web Speech API
export const SPEECH_LANGUAGES = {
  en: 'en-US',
  si: 'si-LK',
  ta: 'ta-LK',
} as const

/**
 * Hook for browser-based speech recognition (Web Speech API).
 * Pass a language code to startListening for better accuracy.
 */
export function useSpeechRecognition(): SpeechRecognitionHook {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)

  // Check browser support
  const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition

  const isSupported = !!SpeechRecognitionAPI

  const startListening = useCallback((lang: string = 'en') => {
    if (!SpeechRecognitionAPI) {
      setError('Speech recognition not supported in this browser. Use Chrome or Edge.')
      return
    }

    setError(null)
    setTranscript('')

    const recognition = new SpeechRecognitionAPI()
    recognitionRef.current = recognition

    // Config
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    // Set language based on user selection
    const speechLang = SPEECH_LANGUAGES[lang as keyof typeof SPEECH_LANGUAGES] || 'en-US'
    recognition.lang = speechLang

    recognition.onstart = () => {
      setIsListening(true)
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = ''
      let interimTranscript = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          finalTranscript += result[0].transcript
        } else {
          interimTranscript += result[0].transcript
        }
      }

      setTranscript(finalTranscript || interimTranscript)
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      setIsListening(false)
      if (event.error === 'no-speech') {
        setError('No speech detected. Please try again.')
      } else if (event.error === 'not-allowed') {
        setError('Microphone access denied. Please allow microphone access.')
      } else {
        setError(`Speech recognition error: ${event.error}`)
      }
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognition.start()
  }, [SpeechRecognitionAPI])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }, [])

  const clearTranscript = useCallback(() => {
    setTranscript('')
  }, [])

  // Stop recognition if the component unmounts mid-listen.
  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.stop()
      } catch {
        // Already stopped — safe to ignore.
      }
      recognitionRef.current = null
    }
  }, [])

  return {
    isListening,
    transcript,
    startListening,
    stopListening,
    clearTranscript,
    isSupported,
    error,
  }
}
