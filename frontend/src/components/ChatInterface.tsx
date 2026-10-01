import { useState, useRef, useEffect } from 'react'
import { Send, MapPin, Loader2, Mic, MicOff, Volume2 } from 'lucide-react'
import ChatMessage from './ChatMessage'
import { sendQuery, sendVoiceQuery, getAudioUrl, ChatResponse } from '../api/climoraApi'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  response?: ChatResponse
  timestamp: Date
}

interface ChatInterfaceProps {
  initialMessages?: Message[]
  initialSessionId?: string | null
  defaultLanguage?: string
  defaultLocation?: string
  userType?: string
  displayName?: string
  alertsEnabled?: boolean
  onNewConversation?: (id: string, query: string, messages: Message[]) => void
  onUpdateConversation?: (id: string, messages: Message[]) => void
}

/** ID generation with a fallback for non-secure contexts where crypto.randomUUID is unavailable. */
function newId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch {
    // fall through to fallback below
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${Math.random().toString(36).slice(2, 10)}`
}

export default function ChatInterface({
  initialMessages = [],
  initialSessionId = null,
  defaultLanguage = 'en',
  defaultLocation = '',
  userType = 'individual',
  displayName = '',
  alertsEnabled = false,
  onNewConversation,
  onUpdateConversation,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [location, setLocation] = useState(defaultLocation)
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId)
  const [isPlayingAudio, setIsPlayingAudio] = useState(false)
  const [speechLang, setSpeechLang] = useState<string>(defaultLanguage)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  // Mirror of messages for parent callbacks — avoids stale-closure history loss
  // when a voice auto-submit races a typed submit.
  const messagesRef = useRef<Message[]>(initialMessages)
  // Last voice transcript already submitted — prevents re-submitting a stale
  // transcript when the mic is toggled again.
  const lastVoiceSubmit = useRef('')

  // Pick up settings changes made while a chat is open.
  useEffect(() => {
    setSpeechLang(defaultLanguage)
  }, [defaultLanguage])
  useEffect(() => {
    setLocation(defaultLocation)
  }, [defaultLocation])

  // Stop any playing audio when switching conversations (component unmounts).
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  // Speech recognition hook
  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    clearTranscript,
    isSupported: isSpeechSupported,
    error: speechError,
  } = useSpeechRecognition()

  // When speech recognition produces a transcript, put it in the input
  useEffect(() => {
    if (transcript) {
      setInput(transcript)
    }
  }, [transcript])

  // Auto-submit when speech recognition finishes with a transcript.
  // Guarded by lastVoiceSubmit + clearTranscript so toggling the mic again
  // never re-submits a stale transcript.
  useEffect(() => {
    if (!isListening && transcript && transcript.trim() && transcript !== lastVoiceSubmit.current) {
      lastVoiceSubmit.current = transcript
      submitVoiceQuery(transcript)
      clearTranscript()
    }
  }, [isListening])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const submitQuery = async (query: string) => {
    if (!query.trim() || isLoading) return

    const userMessage: Message = {
      id: newId(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    }

    messagesRef.current = [...messagesRef.current, userMessage]
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await sendQuery({
        query,
        location: location || undefined,
        user_type: userType,
        session_id: sessionId || undefined,
        language: speechLang,   // answer language (a Sinhala/Tamil query overrides this)
      })

      setSessionId(response.session_id)

      const assistantMessage: Message = {
        id: newId(),
        role: 'assistant',
        content: response.summary,
        response,
        timestamp: new Date(),
      }

      messagesRef.current = [...messagesRef.current, assistantMessage]
      const updatedMessages = messagesRef.current
      setMessages(prev => [...prev, assistantMessage])
      maybeNotifyAlerts(response)

      // Notify parent about new/updated conversation
      if (!sessionId && onNewConversation) {
        onNewConversation(response.session_id, query, updatedMessages)
      } else if (sessionId && onUpdateConversation) {
        onUpdateConversation(sessionId, updatedMessages)
      }
    } catch (error) {
      const errorMessage: Message = {
        id: newId(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
      }
      messagesRef.current = [...messagesRef.current, errorMessage]
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await submitQuery(input)
  }

  const submitVoiceQuery = async (query: string) => {
    if (!query.trim() || isLoading) return

    const userMessage: Message = {
      id: newId(),
      role: 'user',
      content: `🎤 ${query}`,
      timestamp: new Date(),
    }

    messagesRef.current = [...messagesRef.current, userMessage]
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const result = await sendVoiceQuery({
        query,
        location: location || undefined,
        user_type: userType,
        session_id: sessionId || undefined,
        language: speechLang,
      })

      const response = result.response
      setSessionId(response.session_id)

      const assistantMessage: Message = {
        id: newId(),
        role: 'assistant',
        content: response.summary,
        response,
        timestamp: new Date(),
      }

      messagesRef.current = [...messagesRef.current, assistantMessage]
      const updatedMessages = messagesRef.current
      setMessages(prev => [...prev, assistantMessage])
      maybeNotifyAlerts(response)

      if (!sessionId && onNewConversation) {
        onNewConversation(response.session_id, query, updatedMessages)
      } else if (sessionId && onUpdateConversation) {
        onUpdateConversation(sessionId, updatedMessages)
      }

      // Auto-play audio response
      if (result.audio_url) {
        playAudio(getAudioUrl(result.audio_url))
      }
    } catch (error) {
      const errorMessage: Message = {
        id: newId(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your voice query.',
        timestamp: new Date(),
      }
      messagesRef.current = [...messagesRef.current, errorMessage]
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const playAudio = (url: string) => {
    if (audioRef.current) {
      audioRef.current.pause()
    }
    const audio = new Audio(url)
    audioRef.current = audio
    setIsPlayingAudio(true)
    audio.play().catch(() => setIsPlayingAudio(false))
    audio.onended = () => setIsPlayingAudio(false)
    audio.onerror = () => setIsPlayingAudio(false)
  }

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      setIsPlayingAudio(false)
    }
  }

  const handleSuggestionClick = (text: string) => {
    submitQuery(text)
  }

  // Browser notification when the user opted into severe-weather alerts and
  // the pipeline assessed high or critical risk. Never throws.
  const maybeNotifyAlerts = (response: ChatResponse) => {
    if (!alertsEnabled) return
    const level = response.risk_assessment?.risk_level
    if (level !== 'high' && level !== 'critical') return
    try {
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        new Notification(`Climora AI — ${level === 'critical' ? 'Critical' : 'High'} risk detected`, {
          body: response.summary.slice(0, 140),
        })
      }
    } catch {
      // Notifications must never break the chat flow.
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <WelcomeScreen
            displayName={displayName}
            onSuggestionClick={handleSuggestionClick}
            location={location}
            onLocationChange={setLocation}
          />
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map(message => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-climora-100 flex items-center justify-center shrink-0">
                  <Loader2 className="w-4 h-4 text-climora-600 animate-spin" />
                </div>
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-500 dark:text-slate-400">Analyzing climate data</span>
                    <span className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-climora-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-climora-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-climora-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Retrieving evidence, assessing risk, generating recommendations...</p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-4">
        <div className="max-w-3xl mx-auto">
          {/* Listening indicator */}
          {isListening && (
            <div className="flex items-center gap-2 mb-2 px-2">
              <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
              <span className="text-xs text-red-600 dark:text-red-400 font-medium">Listening... speak now</span>
              <button
                onClick={stopListening}
                className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 ml-auto"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Audio playing indicator */}
          {isPlayingAudio && (
            <div className="flex items-center gap-2 mb-2 px-2">
              <Volume2 className="w-3 h-3 text-climora-600 animate-pulse" />
              <span className="text-xs text-climora-600 font-medium">Playing response...</span>
              <button
                onClick={stopAudio}
                className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 ml-auto"
              >
                Stop
              </button>
            </div>
          )}

          {/* Speech error */}
          {speechError && (
            <p className="text-xs text-red-500 mb-2 px-2">{speechError}</p>
          )}

          {/* Location input */}
          <div className="flex items-center gap-2 mb-2">
            <MapPin className="w-4 h-4 text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="Your location (optional, e.g. Colombo, Sri Lanka)"
              className="text-sm text-slate-600 dark:text-slate-300 bg-transparent border-none outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500 w-full"
            />
          </div>

          {/* Query input with mic and send */}
          <form onSubmit={handleSubmit} className="flex items-end gap-2">
            {/* Language selector + Mic button */}
            {isSpeechSupported && (
              <div className="flex items-center">
                <select
                  value={speechLang}
                  onChange={e => setSpeechLang(e.target.value)}
                  className="text-xs bg-slate-100 dark:bg-slate-800 border-none rounded-l-xl px-2 py-3 text-slate-600 dark:text-slate-300 focus:outline-none cursor-pointer h-[48px]"
                  disabled={isLoading || isListening}
                  aria-label="Select language (speech input and answers)"
                  title="Language for voice input and answers"
                >
                  <option value="en">EN</option>
                  <option value="si">සි</option>
                  <option value="ta">த</option>
                </select>
                <button
                  type="button"
                  onClick={isListening ? stopListening : () => startListening(speechLang)}
                  disabled={isLoading}
                  className={`p-3 rounded-r-xl transition-colors h-[48px] ${
                    isListening
                      ? 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/60'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                  aria-label={isListening ? 'Stop listening' : 'Start voice input'}
                >
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              </div>
            )}

            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              placeholder={isListening ? "Listening..." : "Ask about weather, floods, drought, cyclones in Sri Lanka..."}
              className="flex-1 resize-none rounded-xl border border-slate-300 dark:border-slate-600 bg-transparent px-4 py-3 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-climora-500 focus:border-transparent min-h-[48px] max-h-[120px]"
              rows={1}
              disabled={isLoading || isListening}
            />

            {/* Send button */}
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="p-3 bg-climora-600 text-white rounded-xl hover:bg-climora-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              aria-label="Send message"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </form>

          <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 text-center">
            Climora AI supports English, සිංහල, and தமிழ் — speak or type in any language.
          </p>
        </div>
      </div>
    </div>
  )
}

interface WelcomeScreenProps {
  displayName: string
  onSuggestionClick: (text: string) => void
  location: string
  onLocationChange: (val: string) => void
}

function WelcomeScreen({ displayName, onSuggestionClick, location, onLocationChange }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 bg-climora-100 rounded-2xl flex items-center justify-center mb-6">
        <span className="text-3xl" aria-hidden="true">🌍</span>
      </div>
      <h2 className="text-2xl font-semibold text-slate-800 dark:text-slate-100 mb-2">
        {displayName ? `Welcome back, ${displayName}` : 'Welcome to Climora AI'}
      </h2>
      <p className="text-slate-500 dark:text-slate-400 max-w-md mb-4">
        Sri Lanka's AI-powered climate intelligence assistant. Ask about weather conditions,
        flood and drought risks, cyclones, landslides, and climate preparedness
        for any location in Sri Lanka.
      </p>

      {/* Location prompt on welcome screen */}
      <div className="flex items-center gap-2 mb-6 px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg w-full max-w-sm">
        <MapPin className="w-4 h-4 text-climora-500" />
        <input
          type="text"
          value={location}
          onChange={e => onLocationChange(e.target.value)}
          placeholder="Enter your location first..."
          className="text-sm text-slate-600 dark:text-slate-300 bg-transparent border-none outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500 w-full"
        />
      </div>

      <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">Try one of these queries:</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg">
        <SuggestionCard
          text="What is the current weather in Colombo?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="Is there a flood risk in Kandy right now?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="කොළඹ මෝසම් වර්ෂාවට සූදානම් වන්නේ කෙසේද?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="අනුරාධපුරයේ නියං අවදානම තක්සේරු කරන්න"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="நுவரெலியாவில் நிலச்சரிவு அபாயம் உள்ளதா?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="திருகோணமலையில் சூறாவளி ஆபத்து என்ன?"
          onClick={onSuggestionClick}
        />
      </div>
    </div>
  )
}

function SuggestionCard({ text, onClick }: { text: string; onClick: (text: string) => void }) {
  return (
    <button
      onClick={() => onClick(text)}
      className="px-4 py-3 text-left text-sm text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-climora-300 hover:bg-climora-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
    >
      {text}
    </button>
  )
}
