// Marketing Studio body: campaign brief, editable budget allocations, creatives,
// the labelled DEMO simulation and an optional actuals form for measurement.
//
// Budget arithmetic is mirrored from the backend rules on purpose: the inputs
// are validated here for instant feedback, and the server validates again on
// save, so a tampered request cannot store a broken allocation either.

import { useEffect, useState } from 'react'
import { api, errorText } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, Field, Input, SectionTitle, Select, WarningList } from './ui'
import { BudgetDonut } from './Charts'

export function CampaignPlanner() {
  const { project, run, refreshProject, busy } = useProject()
  const [objective, setObjective] = useState('sales')
  const [budget, setBudget] = useState(0)
  const [duration, setDuration] = useState(14)
  const [allocations, setAllocations] = useState<{ label: string; amount: number; purpose: string }[]>([])
  const [allocError, setAllocError] = useState<string | null>(null)
  const [actuals, setActuals] = useState({ ad_spend: '', clicks: '', conversions: '', customers: '', revenue: '' })

  const plan = project?.campaign ?? null

  // Default the budget to the brief's campaign budget.
  useEffect(() => {
    if (project?.brief?.budget) setBudget(project.brief.budget)
  }, [project?.brief?.budget])

  // Load a newly generated or reloaded plan into the editable rows.
  useEffect(() => {
    if (plan) {
      setAllocations(plan.allocations.map((a) => ({ ...a })))
      setObjective(plan.objective)
      setBudget(plan.budget)
      setDuration(plan.duration_days)
    }
  }, [plan?.created_at]) // eslint-disable-line react-hooks/exhaustive-deps

  // The budget split must match the campaign budget to the paisa/cent.
  const total = allocations.reduce((s, a) => s + (Number(a.amount) || 0), 0)
  const diff = total - budget
  const valid = Math.abs(diff) < 0.005 && allocations.length > 0 && allocations.every((a) => a.amount >= 0)

  const generate = () =>
    run('generate-campaign', async () => {
      if (!project) return
      await api.generateCampaign(project.id, { objective, budget, duration_days: duration })
      await refreshProject()
    })

  const saveAllocations = () => {
    if (!valid || !project) {
      setAllocError(`Allocations must sum to the budget exactly (currently ${total.toFixed(0)} vs ${budget.toFixed(0)}).`)
      return
    }
    setAllocError(null)
    run('save-budget', async () => {
      await api.updateCampaign(project.id, { budget, allocations })
      await refreshProject()
    })
  }

  // Scale every allocation to the budget, then put the rounding remainder on
  // the largest line so the total lands exactly on the budget.
  const normalize = () => {
    if (!allocations.length) return
    const scaling = budget / (total || 1)
    const rounded = allocations.map((a) => ({ ...a, amount: Math.round(a.amount * scaling) }))
    const drift = budget - rounded.reduce((s, a) => s + a.amount, 0)
    const biggest = rounded.reduce((mi, a, i, arr) => (a.amount > arr[mi].amount ? i : mi), 0)
    rounded[biggest] = { ...rounded[biggest], amount: rounded[biggest].amount + drift }
    setAllocations(rounded)
  }

  // Simulation only projects spend/revenue from the stored assumptions; it is
  // labelled DEMO and never contacts Meta.
  const analyzeWithActuals = () =>
    run('analyze-actuals', async () => {
      if (!project) return
      const payload = Object.fromEntries(
        Object.entries(actuals)
          .filter(([, v]) => v !== '')
          .map(([k, v]) => [k, Number(v)]),
      )
      await api.analyze(project.id, { actuals: payload })
      await refreshProject()
    })

  if (!project) return null

  return (
    <div className="space-y-5">
      {/* ------------------------------------------------------------- setup */}
      <Card>
        <SectionTitle
          title="Campaign brief"
          subtitle="Uses the SAME product, audience and budget stored in the project."
          right={<Badge tone="neutral">Campaign plan</Badge>}
        />
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Objective">
            <Select value={objective} onChange={(e) => setObjective(e.target.value)}>
              <option value="sales">Sales / conversions</option>
              <option value="traffic">Traffic</option>
              <option value="leads">Leads</option>
              <option value="retargeting">Retargeting</option>
            </Select>
          </Field>
          <Field label={`Budget (${project.brief.currency})`}>
            <Input type="number" min={0} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
          </Field>
          <Field label="Duration (days)">
            <Input type="number" min={1} max={180} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
          </Field>
          <div className="flex items-end">
            <Button busy={busy === 'generate-campaign'} onClick={generate} disabled={!project.selected_product || budget <= 0 || !!busy} className="w-full">
              {plan ? 'Regenerate plan' : 'Generate campaign plan'}
            </Button>
          </div>
        </div>
        {project.selected_product && (
          <p className="mt-3 text-xs text-muted">
            Product: <span className="font-medium text-ink">{project.selected_product.title}</span>
            {' · '}Price {project.brief.currency} {project.selected_product.observed_price?.toLocaleString() ?? '—'}
            {project.selected_product.estimated_cost != null && (
              <> · Est. cost {project.selected_product.estimated_cost.toLocaleString()}</>
            )}
          </p>
        )}
      </Card>

      {!plan && (
        <p className="text-sm text-muted">Generate a campaign plan to see creatives, budget allocation and testing strategy.</p>
      )}

      {plan && (
        <>
          {/* ------------------------------------------------------- creatives */}
          <Card>
            <SectionTitle
              title="Creative concepts"
              subtitle={plan.generation_mode === 'llm' ? 'Copy written with a configured LLM' : 'Earlier copy — regenerate with your configured model'}
              right={<Badge tone="amber">Draft · not published</Badge>}
            />
            <div className="grid gap-4 md:grid-cols-3">
              {plan.creatives.map((c) => (
                <div key={c.name} className="rounded-xl border border-line bg-mist/50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-accent-dark">{c.name}</p>
                  <p className="mt-1 text-xs text-muted">{c.angle}</p>
                  <p className="mt-2 font-display text-[15px] font-semibold text-ink">{c.headline}</p>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink/80">{c.primary_text}</p>
                  <span className="mt-3 inline-block rounded-lg bg-brand px-3 py-1 text-xs font-semibold text-white">{c.cta}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Audience hypotheses</p>
                <ul className="list-disc space-y-1 pl-4 text-[13px] text-ink/85">
                  {plan.audience_hypotheses.map((a, i) => (<li key={i}>{a}</li>))}
                </ul>
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Testing strategy</p>
                <ol className="list-decimal space-y-1 pl-4 text-[13px] text-ink/85">
                  {plan.testing_strategy.map((a, i) => (<li key={i}>{a}</li>))}
                </ol>
              </div>
            </div>
            <div className="mt-4">
              <WarningList items={plan.risks_and_assumptions} title="Risks & assumptions" />
            </div>
          </Card>

          {/* --------------------------------------------------------- budget */}
          <Card>
            <SectionTitle
              title="Budget allocation"
              subtitle={`Must sum exactly to ${plan.currency} ${budget.toLocaleString()} — validated server-side.`}
              right={valid ? <Badge tone="green">sums correctly</Badge> : <Badge tone="red">must equal budget</Badge>}
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3">
                {allocations.map((a, i) => (
                  <div key={a.label} className="grid grid-cols-[1fr_120px] items-center gap-3">
                    <div>
                      <p className="text-sm font-medium text-ink">{a.label}</p>
                      {a.purpose && <p className="text-xs text-muted">{a.purpose}</p>}
                    </div>
                    <Input
                      type="number"
                      min={0}
                      value={a.amount}
                      onChange={(e) => setAllocations((rows) => rows.map((r, j) => (j === i ? { ...r, amount: Number(e.target.value) } : r)))}
                    />
                  </div>
                ))}
                <div className="flex items-center justify-between rounded-lg bg-mist px-3 py-2 text-sm">
                  <span className="text-muted">Total allocated</span>
                  <span className={`font-semibold tabular-nums ${valid ? 'text-brand' : 'text-danger'}`}>
                    {plan.currency} {total.toLocaleString()}
                    {!valid && <span className="ml-2 text-xs">({diff > 0 ? '+' : ''}{diff.toFixed(0)})</span>}
                  </span>
                </div>
                {allocError && <p className="text-xs text-danger">{allocError}</p>}
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={normalize} size="sm">Auto-balance to budget</Button>
                  <Button onClick={saveAllocations} variant="primary" size="sm">Save allocation</Button>
                </div>
              </div>
              <div>
                <BudgetDonut allocations={allocations} currency={plan.currency} />
              </div>
            </div>
          </Card>

          {/* Measured campaign inputs */}
          <Card>
            <SectionTitle title="Real campaign numbers (optional)" subtitle="When you have real data from an ad account, enter it and the analyst computes actual CPA and conversion rate." />
            <div className="grid gap-3 md:grid-cols-5">
              {(['ad_spend', 'clicks', 'conversions', 'customers', 'revenue'] as const).map((k) => (
                <Field key={k} label={k.replace('_', ' ')}>
                  <Input type="number" min={0} value={actuals[k]} placeholder="—" onChange={(e) => setActuals((a) => ({ ...a, [k]: e.target.value }))} />
                </Field>
              ))}
              <div className="flex items-end">
                <Button variant="secondary" onClick={analyzeWithActuals} className="w-full">Update KPIs</Button>
              </div>
            </div>
            {project.analysis && (
              <p className="mt-3 text-xs text-muted">
                Current KPIs — CPA: <span className="font-semibold text-ink">{project.analysis.kpis.cpa ?? 'no data'}</span>,
                conversion rate: <span className="font-semibold text-ink">{project.analysis.kpis.conversion_rate_pct != null ? `${project.analysis.kpis.conversion_rate_pct}%` : 'no data'}</span>
                {' '}<span className="opacity-70">({project.analysis.kpis.source})</span>
              </p>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
