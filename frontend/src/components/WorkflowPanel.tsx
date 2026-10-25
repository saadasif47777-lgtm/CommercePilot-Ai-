// Workflow controls and progress display.
//
// `WorkflowSteps` renders the seven stored steps, `RunWorkflowButton` starts the
// orchestrator and `ExecutionTimeline` shows the audit log of every agent run.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api, errorText } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, SectionTitle, Select } from './ui'
import type { StepState } from '../types'

// Steps in execution order; ids match the keys stored on the project.
const STEP_ORDER = ['brief', 'research', 'select', 'store', 'campaign', 'analyze', 'report']

// Label for the "retry" button, phrased as the action that actually fixes it.
const STEP_ACTIONS: Record<string, string> = {
  brief: 'Fix brief then retry',
  research: 'Re-run research',
  select: 'Select product',
  store: 'Generate store',
  campaign: 'Generate campaign',
  analyze: 'Re-run analysis',
  report: 'Rebuild report',
}

function StepIcon({ status }: { status: StepState['status'] }) {
  if (status === 'success')
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent/15 text-accent-dark">
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
    )
  if (status === 'error')
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 text-danger">
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="3"><path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" /></svg>
      </span>
    )
  if (status === 'running' || status === 'waiting')
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand/10 text-brand">
        <span className="dot-pulse h-2 w-2 rounded-full bg-brand" />
      </span>
    )
  return <span className="flex h-6 w-6 items-center justify-center rounded-full border border-line bg-paper text-[11px] text-muted">{STEP_ORDER.indexOf(status as string) >= 0 ? '' : '·'}</span>
}

// Compact mode is used in the assistant sidebar; the full mode has room for
// per-step messages.
export function WorkflowSteps({ compact = false }: { compact?: boolean }) {
  const { project } = useProject()
  if (!project) return null
  const steps = STEP_ORDER.map((id) => project.steps[id]).filter(Boolean)

  return (
    <div className={compact ? 'space-y-2' : 'space-y-3'}>
      {steps.map((step, i) => (
        <motion.div
          key={step.id}
          initial={{ opacity: 0, x: -4 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.03 }}
          className="flex items-start gap-3"
        >
          <StepIcon status={step.status} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-medium leading-6 text-ink">
              <span>{i + 1}. {step.title}</span>
              {step.status === 'success' && <Badge tone="green">done</Badge>}
              {step.status === 'error' && <Badge tone="red">failed</Badge>}
              {step.status === 'waiting' && <Badge tone="amber">awaiting selection</Badge>}
            </div>
            {step.message && <p className="mt-0.5 truncate text-xs text-muted">{step.message}</p>}
          </div>
        </motion.div>
      ))}
    </div>
  )
}

export function RunWorkflowButton() {
  const { project, run, refreshProject, busy } = useProject()
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  if (!project) return null
  const execute = () => run('workflow', async () => {
    setMessage('')
    await api.validateBrief(project.id)
    let current = await api.getProject(project.id)
    if (!current.selected_product) {
      if (!current.research?.products?.length) await api.projectResearch(current.id, {
        niche: current.brief.niche || current.brief.industry, market: current.brief.target_market,
        audience: current.brief.target_audience, budget: current.brief.budget, mode: 'live',
        constraints: current.brief.constraints, price_min: current.brief.preferred_price_min, price_max: current.brief.preferred_price_max,
      })
      await refreshProject()
      navigate('/products')
      return
    }
    try {
      if (!current.store_spec || current.steps.store.status !== 'success') {
        setMessage('Generating storefront copy…')
        await api.generateStore(current.id)
      }
      current = await api.getProject(current.id)
      if (!current.campaign || current.steps.campaign.status !== 'success') {
        setMessage('Preparing campaign plan…')
        await api.generateCampaign(current.id, { budget: current.brief.budget })
      }
      current = await api.getProject(current.id)
      if (!current.analysis || current.steps.analyze.status !== 'success') {
        setMessage('Calculating economics…')
        await api.analyze(current.id)
      }
      await api.report(current.id, true)
      setMessage('Your results are ready.')
    } finally { await refreshProject() }
  })
  const briefReady = project.brief.business_name.trim() && (project.brief.niche.trim() || project.brief.industry.trim()) && project.brief.budget > 0
  return <div className="flex flex-wrap items-center gap-3">
    <Button busy={busy === 'workflow'} disabled={!!busy} onClick={() => briefReady ? execute() : navigate('/business')}>
      {!briefReady ? 'Complete business information' : project.selected_product ? 'Prepare remaining results' : 'Find & review products'}
    </Button>
    {message && <p role="status" className="text-xs text-muted">{message}</p>}
  </div>
}

export function RetryStepButton({ stepId, label }: { stepId: string; label?: string }) {
  const { project, run, refreshProject } = useProject()
  const navigate = useNavigate()
  if (!project) return null

  const retry = async () => {
    await run(`retry-${stepId}`, async () => {
      if (stepId === 'research') {
        navigate('/products')
        return
      } else if (stepId === 'brief') {
        navigate('/business'); return
      } else if (stepId === 'select') {
        navigate('/products'); return
      } else if (stepId === 'store') {
        await api.generateStore(project.id)
      } else if (stepId === 'campaign') {
        await api.generateCampaign(project.id, { budget: project.brief.budget })
      } else if (stepId === 'analyze') {
        await api.analyze(project.id)
      } else if (stepId === 'report') {
        await api.report(project.id, true)
      }
      await refreshProject()
    })
  }
  return (
    <Button size="sm" variant="secondary" onClick={retry}>
      {label ?? STEP_ACTIONS[stepId] ?? 'Retry'}
    </Button>
  )
}

export function ExecutionTimeline({ limit = 8 }: { limit?: number }) {
  const { project } = useProject()
  if (!project) return null
  const rows = [...project.executions].slice(-limit).reverse()

  if (!rows.length) {
    return <p className="text-sm text-muted">No agent runs recorded yet. Run the workflow to see each agent&apos;s handoffs.</p>
  }

  return (
    <div className="space-y-2.5">
      {rows.map((e) => (
        <div key={e.id} className="flex items-start gap-3 text-sm">
          <span className="mt-0.5">
            {e.status === 'success' && <Badge tone="green">success</Badge>}
            {e.status === 'error' && <Badge tone="red">error</Badge>}
            {e.status === 'skipped' && <Badge tone="neutral">skipped</Badge>}
            {e.status === 'running' && <Badge tone="amber" pulse>running</Badge>}
          </span>
          <div className="min-w-0">
            <p className="font-medium text-ink">{e.agent}</p>
            {e.input_summary && <p className="text-xs text-muted">in: {e.input_summary}</p>}
            {e.output_summary && <p className="text-xs text-muted">out: {e.output_summary}</p>}
            {e.warnings?.slice(0, 1).map((w, i) => (
              <p key={i} className="text-xs text-warn">⚠ {w}</p>
            ))}
            {e.errors?.slice(0, 1).map((w, i) => (
              <p key={i} className="text-xs text-danger">✕ {w}</p>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function WorkflowErrorCard({ error }: { error: { step: string; message: string } }) {
  return (
    <Card className="border-red-200 bg-red-50/50">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-danger">Workflow stopped at: {error.step}</p>
          <p className="mt-1 text-sm text-danger/90">{error.message}</p>
          <p className="mt-2 text-xs text-muted">Earlier steps keep their results — retry just this step below.</p>
        </div>
        <RetryStepButton stepId={error.step} />
      </div>
    </Card>
  )
}

export { errorText }
