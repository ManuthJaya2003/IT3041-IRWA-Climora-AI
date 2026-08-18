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

export default function ChatInterface() {
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    const query = input
    setInput('')
    setIsLoading(true)

    try {
      const response = await sendQuery({
        query,
        location: location || undefined,
        session_id: sessionId || undefined,
      })

      setSessionId(response.session_id)

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
        content: 'Sorry, I encountered an error processing your request. Please check if the backend server is running.',
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <WelcomeScreen />
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map(message => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Analyzing climate data...</span>
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
              placeholder="Your location (optional)"
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
              <Send className="w-4 h-4" />
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

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 bg-climora-100 rounded-2xl flex items-center justify-center mb-6">
        <span className="text-3xl">🌍</span>
      </div>
      <h2 className="text-2xl font-semibold text-slate-800 mb-2">
        Welcome to Climora AI
      </h2>
      <p className="text-slate-500 max-w-md mb-8">
        Your AI-powered climate intelligence assistant. Ask about climate risks,
        weather patterns, environmental concerns, or preparedness guidance.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg">
        <SuggestionCard text="What are the flood risks in my area this week?" />
        <SuggestionCard text="How is climate change affecting agriculture in South Asia?" />
        <SuggestionCard text="What should I prepare for during monsoon season?" />
        <SuggestionCard text="Assess drought risk for the Dry Zone in Sri Lanka" />
      </div>
    </div>
  )
}

function SuggestionCard({ text }: { text: string }) {
  return (
    <button className="px-4 py-3 text-left text-sm text-slate-600 bg-white border border-slate-200 rounded-xl hover:border-climora-300 hover:bg-climora-50 transition-colors">
      {text}
    </button>
  )
}
