// Workflow controls and progress display.
//
// `WorkflowSteps` renders the seven stored steps, `RunWorkflowButton` starts the
// orchestrator and `ExecutionTimeline` shows the audit log of every agent run.

import { useState } from 'react'
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
            <p className="text-sm font-medium text-ink">
              {i + 1}. {step.title}
              {step.status === 'success' && <Badge tone="green">done</Badge>}
              {step.status === 'error' && <Badge tone="red">failed</Badge>}
              {step.status === 'waiting' && <Badge tone="amber">awaiting selection</Badge>}
            </p>
            {step.message && <p className="mt-0.5 truncate text-xs text-muted">{step.message}</p>}
          </div>
        </motion.div>
      ))}
    </div>
  )
}

export function RunWorkflowButton({ mode }: { mode?: 'sample' | 'live' | 'both' }) {
  const { project, run, refreshProject, busy } = useProject()
  const [runMode, setRunMode] = useState<'sample' | 'live' | 'both'>(mode ?? 'both')
  if (!project) return null

  const started = Object.values(project.steps).some((s) => s.status === 'success')

  const execute = async (force: boolean) => {
    await run('workflow', async () => {
      await api.runWorkflow(project.id, { auto_select: true, mode: runMode, force })
      await refreshProject()
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={runMode} onChange={(e) => setRunMode(e.target.value as typeof runMode)} className="w-auto py-1.5 text-xs">
        <option value="both">Live search + sample data</option>
        <option value="live">Live search only</option>
        <option value="sample">Sample data only (fast)</option>
      </Select>
      <Button busy={busy === 'workflow'} onClick={() => execute(false)}>
        {started ? 'Continue Workflow' : 'Run Full Commerce Workflow'}
      </Button>
      {started && (
        <Button variant="secondary" size="md" busy={busy === 'workflow'} onClick={() => execute(true)} title="Re-run every step with the current brief">
          Re-run all steps
        </Button>
      )}
    </div>
  )
}

export function RetryStepButton({ stepId, label }: { stepId: string; label?: string }) {
  const { project, run, refreshProject } = useProject()
  if (!project) return null

  const retry = async () => {
    await run(`retry-${stepId}`, async () => {
      if (stepId === 'research') {
        await api.runWorkflow(project.id, { mode: 'both', force: false })
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
