import { useEffect, useRef, useState } from 'react'
import type { AgentStreamEvent } from '../api/climoraApi'

/**
 * AgentMesh
 * ---------
 * A live visualisation of the Climora AI multi-agent pipeline, driven by REAL
 * agent-communication events streamed from the backend (see streamQuery / the
 * `/chat/query/stream` SSE endpoint).
 *
 * An edge between the orchestrator hub and a specialist lights up *only while*
 * that agent is actually being communicated with — i.e. between its real
 * `agent_start` and `agent_end` events. When the pipeline finishes (communication
 * stops), all active edges clear and the mesh returns to an idle state showing
 * nothing in flight.
 */

export interface AgentMeshProps {
  /** True while a query is being processed by the pipeline. */
  active: boolean
  /**
   * The latest real pipeline event from the backend stream. Each new event
   * (identified by `seq`) advances the mesh state. Null when idle.
   */
  event?: AgentStreamEvent | null
  /** Monotonic counter so repeated identical events still trigger an update. */
  seq?: number
}

interface AgentNode {
  key: string
  label: string
  initial: string
  x: number
  y: number
  color: string
}

// Layout: orchestrator hub center-right, six specialists arranged around it.
const NODES: AgentNode[] = [
  { key: 'orchestrator', label: 'Orchestrator', initial: 'O', x: 150, y: 70, color: '#22c55e' },
  { key: 'security_agent', label: 'Security', initial: 'S', x: 40, y: 70, color: '#a78bfa' },
  { key: 'nlp_agent', label: 'NLP', initial: 'N', x: 95, y: 30, color: '#a78bfa' },
  { key: 'ir_agent', label: 'Retrieval', initial: 'I', x: 95, y: 120, color: '#38bdf8' },
  { key: 'analysis_agent', label: 'Analysis', initial: 'A', x: 40, y: 165, color: '#fbbf24' },
  { key: 'verification_agent', label: 'Verify', initial: 'V', x: 95, y: 205, color: '#f472b6' },
  { key: 'recommendation_agent', label: 'Recommend', initial: 'R', x: 150, y: 165, color: '#34d399' },
]

const NODE_BY_KEY = Object.fromEntries(NODES.map(n => [n.key, n])) as Record<string, AgentNode>
const LABEL_BY_KEY: Record<string, string> = Object.fromEntries(NODES.map(n => [n.key, n.label]))
const SPECIALISTS = NODES.filter(n => n.key !== 'orchestrator')

interface LogEntry {
  id: string
  agent: string
  outcome: string // in-flight | success | fallback | error
}

const OUTCOME_STYLE: Record<string, string> = {
  'in-flight': 'text-slate-400',
  success: 'text-emerald-400',
  fallback: 'text-amber-400',
  error: 'text-red-400',
}

export default function AgentMesh({ active, event, seq }: AgentMeshProps) {
  // Agents with a call currently in flight (agent_start seen, no agent_end yet).
  const [inFlight, setInFlight] = useState<Set<string>>(new Set())
  // Final outcome per agent for the current query: 'success' | 'fallback' | 'error'.
  // Persists for the whole query so fast/parallel calls stay visibly "used"
  // (kills the render race that briefly greyed out quick hand-offs).
  const [outcomes, setOutcomes] = useState<Record<string, string>>({})
  const [log, setLog] = useState<LogEntry[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)

  // Advance mesh state from each REAL streamed event.
  useEffect(() => {
    if (!event) return

    switch (event.type) {
      case 'pipeline_start':
        setInFlight(new Set())
        setOutcomes({})
        setLog([])
        break

      case 'agent_start':
        if (event.agent) {
          const agent = event.agent
          setInFlight(prev => new Set(prev).add(agent))
          // Mark as touched immediately; outcome refined on agent_end.
          setOutcomes(prev => (agent in prev ? prev : { ...prev, [agent]: 'in-flight' }))
          setLog(prev => [
            ...prev.slice(-40),
            { id: `${seq}-${agent}-start`, agent, outcome: 'in-flight' },
          ])
        }
        break

      case 'agent_end':
        if (event.agent) {
          const agent = event.agent
          const outcome = event.outcome || 'success'
          setInFlight(prev => {
            const next = new Set(prev)
            next.delete(agent)
            return next
          })
          setOutcomes(prev => ({ ...prev, [agent]: outcome }))
          // Update the most recent in-flight log entry for this agent.
          setLog(prev => {
            const next = [...prev]
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].agent === agent && next[i].outcome === 'in-flight') {
                next[i] = { ...next[i], outcome }
                break
              }
            }
            return next
          })
        }
        break

      case 'done':
      case 'error':
        // Communication has stopped — clear anything still shown as in flight,
        // but keep the outcome highlights so the last run stays readable.
        setInFlight(new Set())
        break
    }
  }, [seq]) // eslint-disable-line react-hooks/exhaustive-deps

  // When the pipeline is no longer active, ensure nothing lingers as "in flight".
  useEffect(() => {
    if (!active) {
      setInFlight(new Set())
    }
  }, [active])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log])

  const orchestrator = NODE_BY_KEY['orchestrator']
  const anyInFlight = inFlight.size > 0

  // The colour an edge/node should use given its outcome for this query.
  const FALLBACK_COLOR = '#f59e0b' // amber — reached via fallback, not the live agent
  const ERROR_COLOR = '#ef4444'
  const outcomeColor = (node: AgentNode): string => {
    const o = outcomes[node.key]
    if (o === 'fallback') return FALLBACK_COLOR
    if (o === 'error') return ERROR_COLOR
    return node.color // success or in-flight -> the node's own accent
  }

  return (
    <aside className="hidden lg:flex flex-col w-72 shrink-0 bg-slate-950 border-l border-slate-800 text-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
          Agent Mesh
        </h2>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              anyInFlight ? 'bg-green-400 animate-pulse' : active ? 'bg-amber-400' : 'bg-slate-600'
            }`}
          />
          <span className="text-[11px] text-slate-400">
            {anyInFlight ? 'Communicating' : active ? 'Working' : 'Idle'}
          </span>
        </div>
      </div>

      {/* Mesh diagram */}
      <div className="px-3 pt-4 pb-2">
        <svg viewBox="0 0 200 240" className="w-full" role="img" aria-label="Agent interaction mesh">
          <defs>
            <radialGradient id="mesh-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Edges (orchestrator hub -> specialists). Highlighted ONLY while the
              agent is actually being communicated with. */}
          {SPECIALISTS.map(node => {
            const isActive = inFlight.has(node.key)
            const wasUsed = node.key in outcomes
            const color = isActive ? node.color : outcomeColor(node)
            return (
              <g key={node.key}>
                <line
                  x1={orchestrator.x}
                  y1={orchestrator.y}
                  x2={node.x}
                  y2={node.y}
                  stroke={isActive || wasUsed ? color : '#334155'}
                  strokeWidth={isActive ? 2.5 : wasUsed ? 1.5 : 1}
                  strokeOpacity={isActive ? 1 : wasUsed ? 0.65 : 0.25}
                  strokeLinecap="round"
                />
                {isActive && (
                  <circle r="3" fill={node.color}>
                    {/* Ping the dot back and forth to convey ongoing exchange. */}
                    <animate
                      attributeName="cx"
                      values={`${orchestrator.x};${node.x};${orchestrator.x}`}
                      dur="1.1s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="cy"
                      values={`${orchestrator.y};${node.y};${orchestrator.y}`}
                      dur="1.1s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
              </g>
            )
          })}

          {/* Nodes */}
          {NODES.map(node => {
            const isActive = inFlight.has(node.key)
            const isHub = node.key === 'orchestrator'
            const wasUsed = isHub ? Object.keys(outcomes).length > 0 : node.key in outcomes
            // Hub is "hot" whenever any communication happened this query.
            const hot = isActive || (isHub && anyInFlight) || wasUsed
            const strong = isActive || (isHub && anyInFlight)
            const color = isActive ? node.color : isHub ? node.color : outcomeColor(node)
            return (
              <g key={node.key}>
                {strong && <circle cx={node.x} cy={node.y} r="22" fill="url(#mesh-glow)" />}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={isHub ? 15 : 12}
                  fill="#0f172a"
                  stroke={hot ? color : '#334155'}
                  strokeWidth={strong ? 2.5 : hot ? 2 : 1.5}
                  className="transition-all duration-300"
                />
                <text
                  x={node.x}
                  y={node.y + 4}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill={hot ? color : '#64748b'}
                >
                  {node.initial}
                </text>
                <text
                  x={node.x}
                  y={node.y + (isHub ? 30 : 26)}
                  textAnchor="middle"
                  fontSize="7.5"
                  fill={hot ? '#cbd5e1' : '#475569'}
                >
                  {node.label}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Legend — explains node/edge colours */}
        <div className="flex items-center justify-center gap-3 mt-1 text-[9px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400" /> live agent
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" /> fallback
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" /> error
          </span>
        </div>
      </div>

      {/* Interaction log — real hand-offs as they happen */}
      <div className="flex-1 overflow-y-auto px-3 py-2 border-t border-slate-800 min-h-0">
        <p className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase mb-1.5">
          Interactions
        </p>
        {log.length === 0 ? (
          <p className="text-[11px] text-slate-600 italic">
            Ask a question to watch the agents communicate in real time.
          </p>
        ) : (
          <ul className="space-y-1">
            {log.map(entry => (
              <li key={entry.id} className="flex items-center gap-1 text-[10px] leading-tight">
                <span className="text-emerald-400 font-medium">Orchestrator</span>
                <span className="text-slate-600">→</span>
                <span className="text-sky-400 font-medium">{LABEL_BY_KEY[entry.agent] || entry.agent}</span>
                <span className={`ml-auto ${OUTCOME_STYLE[entry.outcome] || 'text-slate-500'}`}>
                  {entry.outcome === 'in-flight' ? '…' : entry.outcome}
                </span>
              </li>
            ))}
            <div ref={logEndRef} />
          </ul>
        )}
      </div>
    </aside>
  )
}
