import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { api, errorText } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, Input } from './ui'
import type { AssistantReply } from '../types'

interface ChatMsg { role: 'user' | 'assistant'; text: string; reply?: AssistantReply }

const SUGGESTIONS = [
  'Find products for vitamin c serum',
  'Run the full commerce workflow',
  'Make the store more luxurious',
  'Draft a marketing campaign',
  'Analyse profitability',
  'Show me the report',
]

export function AssistantChat() {
  const { project, refreshProject } = useProject()
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      role: 'assistant',
      text: "I'm the CommercePilot assistant. I execute real agent actions on your project — I don't fake replies. Try: 'find products for <niche>', 'make the store more luxurious', 'draft a marketing campaign', 'analyse profitability' or 'run the full commerce workflow'.",
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || busy) return
    if (!project) {
      setError('Open or create a project first — the assistant works on the shared project context.')
      return
    }
    setInput('')
    setError(null)
    setMessages((m) => [...m, { role: 'user', text: message }])
    setBusy(true)
    try {
      const reply = await api.assistant(project.id, message)
      setMessages((m) => [...m, { role: 'assistant', text: reply.reply, reply }])
      await refreshProject()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card padded={false} className="flex h-[min(680px,calc(100vh-260px))] flex-col">
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <div>
          <p className="text-sm font-semibold text-ink">Commerce assistant</p>
          <p className="text-xs text-muted">
            {project ? `Working on: ${project.name}` : 'No project selected'} · actions run real backend agents
          </p>
        </div>
        <Badge tone="green" pulse>connected to agents</Badge>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === 'user' ? 'bg-brand text-white' : 'bg-mist text-ink'
              }`}
            >
              {m.text}
              {m.reply?.applied && m.reply.applied.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-brand">
                  {m.reply.applied.map((a, j) => (<li key={j}>✓ {a}</li>))}
                </ul>
              )}
              {m.reply?.intent && m.reply.intent !== 'unknown' && (
                <p className="mt-1.5 text-[10px] uppercase tracking-wide opacity-60">intent: {m.reply.intent}</p>
              )}
            </div>
          </motion.div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl bg-mist px-4 py-3">
              <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-brand" />
              <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-brand" style={{ animationDelay: '0.2s' }} />
              <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-brand" style={{ animationDelay: '0.4s' }} />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && <p className="border-t border-red-100 bg-red-50 px-5 py-2 text-xs text-danger">{error}</p>}

      <div className="border-t border-line px-5 py-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} className="rounded-full border border-line bg-paper px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-brand/40 hover:text-ink">
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={input}
            placeholder={project ? 'Ask the assistant to research, build, edit, plan or analyse…' : 'Select a project first'}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send(input)}
          />
          <Button busy={busy} onClick={() => send(input)} disabled={!input.trim()}>Send</Button>
        </div>
      </div>
    </Card>
  )
}
