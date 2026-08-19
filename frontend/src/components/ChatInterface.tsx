import { useState, useRef, useEffect } from 'react'
import { Send, MapPin, Loader2 } from 'lucide-react'
import ChatMessage from './ChatMessage'
import { sendQuery, ChatResponse } from '../api/climoraApi'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  response?: ChatResponse
  timestamp: Date
}

export default function ChatInterface({ onNewConversation }: { onNewConversation?: (id: string, query: string) => void }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [location, setLocation] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const submitQuery = async (query: string) => {
    if (!query.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await sendQuery({
        query,
        location: location || undefined,
        session_id: sessionId || undefined,
      })

      setSessionId(response.session_id)

      // Notify parent about new conversation (first message only)
      if (!sessionId && onNewConversation) {
        onNewConversation(response.session_id, query)
      }

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.summary,
        response,
        timestamp: new Date(),
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please check if the backend server is running on http://localhost:8000.',
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await submitQuery(input)
  }

  const handleSuggestionClick = (text: string) => {
    submitQuery(text)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <WelcomeScreen
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
                <div className="bg-white border border-slate-200 rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-500">Analyzing climate data</span>
                    <span className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-climora-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-climora-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-climora-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Retrieving evidence, assessing risk, generating recommendations...</p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-200 bg-white px-4 py-4">
        <div className="max-w-3xl mx-auto">
          {/* Location input */}
          <div className="flex items-center gap-2 mb-2">
            <MapPin className="w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="Your location (optional, e.g. Colombo, Sri Lanka)"
              className="text-sm text-slate-600 bg-transparent border-none outline-none placeholder:text-slate-400 w-full"
            />
          </div>

          {/* Query input */}
          <form onSubmit={handleSubmit} className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              placeholder="Ask about climate risks, weather patterns, or environmental concerns..."
              className="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-climora-500 focus:border-transparent min-h-[48px] max-h-[120px]"
              rows={1}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="p-3 bg-climora-600 text-white rounded-xl hover:bg-climora-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              aria-label="Send message"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </form>

          <p className="text-xs text-slate-400 mt-2 text-center">
            Climora AI provides climate information for awareness. For emergencies, contact local authorities.
          </p>
        </div>
      </div>
    </div>
  )
}

interface WelcomeScreenProps {
  onSuggestionClick: (text: string) => void
  location: string
  onLocationChange: (val: string) => void
}

function WelcomeScreen({ onSuggestionClick, location, onLocationChange }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 bg-climora-100 rounded-2xl flex items-center justify-center mb-6">
        <span className="text-3xl">🌍</span>
      </div>
      <h2 className="text-2xl font-semibold text-slate-800 mb-2">
        Welcome to Climora AI
      </h2>
      <p className="text-slate-500 max-w-md mb-4">
        Your AI-powered climate intelligence assistant. Ask about climate risks,
        weather patterns, environmental concerns, or preparedness guidance.
      </p>

      {/* Location prompt on welcome screen */}
      <div className="flex items-center gap-2 mb-6 px-4 py-2 bg-white border border-slate-200 rounded-lg w-full max-w-sm">
        <MapPin className="w-4 h-4 text-climora-500" />
        <input
          type="text"
          value={location}
          onChange={e => onLocationChange(e.target.value)}
          placeholder="Enter your location first..."
          className="text-sm text-slate-600 bg-transparent border-none outline-none placeholder:text-slate-400 w-full"
        />
      </div>

      <p className="text-xs text-slate-400 mb-4">Try one of these queries:</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg">
        <SuggestionCard
          text="What are the flood risks in Colombo?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="How is climate change affecting agriculture in South Asia?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="What should I prepare for during monsoon season?"
          onClick={onSuggestionClick}
        />
        <SuggestionCard
          text="Assess drought risk for the Dry Zone in Sri Lanka"
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
      className="px-4 py-3 text-left text-sm text-slate-600 bg-white border border-slate-200 rounded-xl hover:border-climora-300 hover:bg-climora-50 transition-colors cursor-pointer"
    >
      {text}
    </button>
  )
}
