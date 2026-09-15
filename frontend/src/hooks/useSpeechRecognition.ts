import { useState, useCallback, useRef } from 'react'

interface SpeechRecognitionHook {
  isListening: boolean
  transcript: string
  startListening: (lang?: string) => void
  stopListening: () => void
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
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  // Check browser support
  const SpeechRecognitionAPI =
    (window as unknown as { SpeechRecognition?: typeof SpeechRecognition })?.SpeechRecognition ||
    (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition })?.webkitSpeechRecognition

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

  return {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported,
    error,
  }
}
