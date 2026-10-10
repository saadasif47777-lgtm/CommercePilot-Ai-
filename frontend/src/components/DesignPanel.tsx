import { useState } from 'react'
import { api, errorText } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, Field, Input, Select } from './ui'
import type { StoreDesign } from '../types'

const PRESETS: { label: string; patch: Partial<StoreDesign> }[] = [
  { label: 'Emerald brand', patch: { primary_color: '#0F3D2E', accent_color: '#2ECC71', background: '#FFFFFF', surface: '#F5F6F5' } },
  { label: 'Luxury ink & gold', patch: { primary_color: '#0B0B0B', accent_color: '#C9A227', background: '#FBFAF7', surface: '#F2EFE8', font_heading: 'serif', radius: 4, density: 'airy', card_style: 'elevated' } },
  { label: 'Warm terracotta', patch: { primary_color: '#3E2C23', accent_color: '#D08C60', background: '#FBF7F2', surface: '#F4EDE4' } },
  { label: 'Nordic minimal', patch: { primary_color: '#10243E', accent_color: '#4C7DF0', background: '#FFFFFF', surface: '#F3F5F7', card_style: 'minimal', radius: 8 } },
]

export function DesignPanel() {
  const { project, run, refreshProject } = useProject()
  const [prompt, setPrompt] = useState('')
  const [applied, setApplied] = useState<string[]>([])
  const [unmatched, setUnmatched] = useState<string | null>(null)
  if (!project?.store_spec) return null
  const spec = project.store_spec
  const d = spec.design

  const applyDesign = async (patch: Partial<StoreDesign>) => {
    await run('regen-design', async () => {
      await api.generateStore(project.id, { design: patch })
      await refreshProject()
    })
  }

  const sendPrompt = async () => {
    if (!prompt.trim()) return
    await run('edit-prompt', async () => {
      const res = await api.editStore(project.id, prompt.trim())
      setApplied(res.applied_changes)
      setUnmatched(res.unmatched ? res.message : null)
      if (!res.unmatched) setPrompt('')
      await refreshProject()
    })
  }

  return (
    <div className="space-y-4">
      {/* ---------------------------------------------------- natural language */}
      <Card>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Natural-language editing</p>
        <p className="mt-1 text-xs text-muted">
          Edits update the structured website specification — no generated code is executed.
        </p>
        <div className="mt-3 flex gap-2">
          <Input
            value={prompt}
            placeholder="e.g. Make this store look more luxurious"
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendPrompt()}
          />
          <Button onClick={sendPrompt} disabled={!prompt.trim()}>Apply</Button>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {['Make this store look more luxurious', 'Use an editorial split-screen hero', 'Make the product cards more minimal', 'Improve the mobile layout', 'Add a subtle reveal animation', 'Use a stronger typography hierarchy'].map((s) => (
            <button key={s} onClick={() => setPrompt(s)} className="rounded-full border border-line bg-mist px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-brand/40 hover:text-ink">
              {s}
            </button>
          ))}
        </div>
        {applied.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-brand">
            {applied.map((a, i) => (<li key={i}>✓ {a}</li>))}
          </ul>
        )}
        {unmatched && <p className="mt-3 rounded-lg bg-mist p-3 text-xs text-muted">{unmatched}</p>}
      </Card>

      {/* ----------------------------------------------------------- presets */}
      <Card>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Presets</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyDesign(p.patch)}
              className="flex items-center gap-2 rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-medium transition-colors hover:border-brand/40"
            >
              <span className="h-3.5 w-3.5 rounded-full border border-line" style={{ background: p.patch.primary_color }} />
              <span className="h-3.5 w-3.5 rounded-full border border-line" style={{ background: p.patch.accent_color }} />
              {p.label}
            </button>
          ))}
        </div>
      </Card>

      {/* ---------------------------------------------------------- controls */}
      <Card>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">Fine-tuning</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Primary colour">
            <Input type="color" value={d.primary_color} onChange={(e) => applyDesign({ primary_color: e.target.value })} className="h-9 p-1" />
          </Field>
          <Field label="Accent colour">
            <Input type="color" value={d.accent_color} onChange={(e) => applyDesign({ accent_color: e.target.value })} className="h-9 p-1" />
          </Field>
          <Field label="Heading font">
            <Select value={d.font_heading} onChange={(e) => applyDesign({ font_heading: e.target.value as StoreDesign['font_heading'] })}>
              <option value="serif">Serif (editorial)</option>
              <option value="sans">Sans (clean)</option>
              <option value="display">Display (bold)</option>
            </Select>
          </Field>
          <Field label="Body font">
            <Select value={d.font_body} onChange={(e) => applyDesign({ font_body: e.target.value as StoreDesign['font_body'] })}>
              <option value="sans">Sans</option>
              <option value="serif">Serif</option>
              <option value="system">System</option>
            </Select>
          </Field>
          <Field label="Border radius">
            <Select value={String(d.radius)} onChange={(e) => applyDesign({ radius: Number(e.target.value) })}>
              {[0, 4, 8, 14, 20, 28].map((r) => (<option key={r} value={r}>{r}px</option>))}
            </Select>
          </Field>
          <Field label="Layout density">
            <Select value={d.density} onChange={(e) => applyDesign({ density: e.target.value as StoreDesign['density'] })}>
              <option value="compact">Compact</option>
              <option value="comfortable">Comfortable</option>
              <option value="airy">Airy</option>
            </Select>
          </Field>
          <Field label="Hero style">
            <Select value={d.hero_style} onChange={(e) => applyDesign({ hero_style: e.target.value as StoreDesign['hero_style'] })}>
              <option value="split">Split</option>
              <option value="editorial_split">Editorial split</option>
              <option value="centered">Centered</option>
              <option value="boxed">Boxed</option>
              <option value="minimal">Minimal</option>
            </Select>
          </Field>
          <Field label="Product cards">
            <Select value={d.card_style} onChange={(e) => applyDesign({ card_style: e.target.value as StoreDesign['card_style'] })}>
              <option value="bordered">Bordered</option>
              <option value="elevated">Elevated</option>
              <option value="minimal">Minimal</option>
            </Select>
          </Field>
          <Field label="Animation intensity">
            <Select value={d.animation} onChange={(e) => applyDesign({ animation: e.target.value as StoreDesign['animation'] })}>
              <option value="none">None</option>
              <option value="subtle">Subtle</option>
              <option value="moderate">Moderate</option>
            </Select>
          </Field>
        </div>
      </Card>

      {/* ------------------------------------------------------- edit history */}
      {spec.edit_history.length > 1 && (
        <Card>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Edit history</p>
          <ul className="space-y-1.5 text-xs text-muted">
            {[...spec.edit_history].reverse().map((h, i) => (
              <li key={i} className="flex gap-2">
                <Badge tone={i === 0 ? 'green' : 'neutral'}>{i === 0 ? 'latest' : 'earlier'}</Badge>
                <span>{h.change}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
