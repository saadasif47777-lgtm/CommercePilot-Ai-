import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader, SectionTitle, Stat, WarningList } from '../components/ui'
import { BudgetDonut, ProductComparisonChart, ScenarioChart, SpendLine } from '../components/Charts'

const SCENARIOS = [
  { key: 'conservative', label: 'Conservative' },
  { key: 'base', label: 'Base case' },
  { key: 'best', label: 'Best case' },
] as const

export function AnalyticsPage() {
  const { project, run, busy, error, refreshProject, clearError } = useProject()
  const [actuals, setActuals] = useState({ ad_spend: '', clicks: '', conversions: '', customers: '', revenue: '' })
  const analysis = project?.analysis ?? null
  const [assumptions, setAssumptions] = useState<Record<string, { clicks: number; conversion_rate_pct: number; cpc: number }>>({})

  useEffect(() => {
    if (analysis?.assumptions) setAssumptions(JSON.parse(JSON.stringify(analysis.assumptions)))
  }, [analysis?.generated_at]) // eslint-disable-line react-hooks/exhaustive-deps

  const applyAssumptions = () =>
    run('assumptions', async () => {
      if (!project) return
      await api.analyze(project.id, {
        conservative: assumptions.conservative,
        base: assumptions.base,
        best: assumptions.best,
      })
      await refreshProject()
    })

  const setAssumption = (scenario: string, field: 'clicks' | 'conversion_rate_pct' | 'cpc', value: number) =>
    setAssumptions((a) => ({ ...a, [scenario]: { ...a[scenario], [field]: value } }))

  const [overheads, setOverheads] = useState<Record<string, string>>({ shipping: '', packaging: '', transaction: '', fixed: '' })

  const analyze = () =>
    run('analyze', async () => {
      if (!project) return
      const payload: Record<string, unknown> = {}
      const actualsPayload = Object.fromEntries(
        Object.entries(actuals).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]),
      )
      if (Object.keys(actualsPayload).length) payload.actuals = actualsPayload
      const ohValues = [overheads.shipping, overheads.packaging, overheads.transaction, overheads.fixed]
      if (ohValues.some((v) => v !== '')) {
        payload.overheads = {
          ...(overheads.shipping !== '' ? { shipping_cost_per_unit: Number(overheads.shipping) } : {}),
          ...(overheads.packaging !== '' ? { packaging_cost_per_unit: Number(overheads.packaging) } : {}),
          ...(overheads.transaction !== '' ? { transaction_fee_per_unit: Number(overheads.transaction) } : {}),
          ...(overheads.fixed !== '' ? { fixed_costs: Number(overheads.fixed) } : {}),
        }
      }
      await api.analyze(project.id, payload)
      await refreshProject()
    })

  if (!project) return <EmptyState title="No project selected" body="Select a project to analyse its economics." />

  const unit = analysis?.unit_economics
  const currency = analysis?.currency ?? project.brief.currency
  const compareProducts = (project.research?.products ?? []).filter((p) => p.observed_price && p.estimated_cost)

  return (
    <div>
      <PageHeader
        eyebrow="Agent D"
        title="Business Analytics"
        body="Real deterministic calculations over the values stored in this project. Missing data is reported as missing; break-even ROAS uses gross profit only."
        actions={
          <Button busy={busy === 'analyze'} onClick={analyze} disabled={!project.selected_product}>
            {analysis ? 'Recalculate' : 'Run analysis'}
          </Button>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {!project.selected_product ? (
        <EmptyState title="Select a product first" body="The analyst works from the stored product price and estimated cost." />
      ) : !analysis ? (
        <EmptyState title="No analysis yet" body="Run the Business Analyst to compute unit economics, break-even ROAS and scenarios." action={<Button onClick={analyze}>Run analysis</Button>} />
      ) : (
        <div className="space-y-5">
          {/* ------------------------------------------------------ profit cards */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Gross profit / unit"
              value={unit?.gross_profit_per_unit != null ? `${currency} ${unit.gross_profit_per_unit.toLocaleString()}` : 'unknown'}
              sub={unit?.cost_is_estimate ? 'cost is an estimate' : undefined}
              tone={unit?.gross_profit_per_unit ? 'good' : 'neutral'}
            />
            <Stat
              label="Gross margin"
              value={unit?.gross_margin_pct != null ? `${unit.gross_margin_pct}%` : 'unknown'}
              sub={unit?.gross_margin_pct != null && unit.gross_margin_pct < 40 ? 'thin margin — be careful' : 'before overheads & fees'}
              tone={unit?.gross_margin_pct ? (unit.gross_margin_pct >= 40 ? 'good' : 'bad') : 'neutral'}
            />
            <Stat
              label="Break-even ROAS"
              value={unit?.break_even_roas ?? (unit ? 'undefined' : '—')}
              sub={unit?.break_even_roas ? 'spend that level to break even' : unit ? 'unit loses money before ads' : undefined}
              tone={unit?.break_even_roas ? (unit.break_even_roas <= 2 ? 'good' : 'bad') : 'neutral'}
            />
            <Stat
              label="CPA (measured)"
              value={analysis.kpis.cpa != null ? `${currency} ${analysis.kpis.cpa.toLocaleString()}` : 'no data'}
              sub={analysis.kpis.source}
              tone={analysis.kpis.cpa != null ? 'good' : 'neutral'}
            />
          </div>

          {(() => {
            const contrib = analysis?.contribution_economics as Record<string, unknown> | undefined
            if (!contrib) return null
            const cu = contrib.contribution_per_unit as number | null | undefined
            const beu = contrib.break_even_units as number | null | undefined
            const mu = contrib.markup_pct as number | null | undefined
            return (
              <Card>
                <SectionTitle
                  title="Contribution economics (includes overheads)"
                  subtitle="Adds shipping, packaging and payment fees to the picture; break-even units cover those costs plus fixed ones."
                />
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Stat label="Markup %" value={mu != null ? `${mu}%` : 'no data'} sub="markup = profit / cost (vs margin = profit / price)" tone={mu ? 'good' : 'neutral'} />
                  <Stat
                    label="Contribution / unit"
                    value={cu != null ? `${currency} ${cu.toLocaleString()}` : 'enter overheads'}
                    sub={cu != null && cu <= 0 ? 'negative: no volume makes this profitable' : 'after shipping + packaging + fees'}
                    tone={cu != null ? (cu > 0 ? 'good' : 'bad') : 'neutral'}
                  />
                  <Stat
                    label="Break-even units"
                    value={beu != null ? `${beu} units` : cu != null && cu <= 0 ? 'never' : 'enter fixed costs'}
                    sub={beu != null ? 'fixed costs ÷ contribution per unit' : 'needs fixed costs + overheads'}
                    tone={beu != null ? 'neutral' : 'neutral'}
                  />
                  <Stat
                    label="Per-unit overheads"
                    value={contrib.extra_unit_cost != null ? `${currency} ${Number(contrib.extra_unit_cost).toLocaleString()}` : 'not modelled'}
                    sub="shipping + packaging + transaction fees"
                    tone="neutral"
                  />
                </div>
              </Card>
            )
          })()}

          {analysis.warnings.length > 0 && <WarningList items={analysis.warnings} title="What these numbers do and don't say" />}

          <div className="grid gap-5 lg:grid-cols-2">
            {/* ------------------------------------------------------- scenarios */}
            <Card>
              <SectionTitle
                title="Scenario analysis"
                subtitle="Assumptions are editable and displayed — these are projections, not forecasts."
                right={
                  <Button size="sm" variant="secondary" onClick={applyAssumptions} busy={busy === 'assumptions'}>
                    Apply assumptions
                  </Button>
                }
              />
              <div className="grid gap-3 sm:grid-cols-3">
                {SCENARIOS.map(({ key, label }) => {
                  const a = assumptions[key] ?? analysis.assumptions[key]
                  if (!a) return null
                  return (
                    <div key={key} className="rounded-lg border border-line bg-mist/50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
                      <div className="mt-2 space-y-1.5">
                        <Input
                          type="number" min={0} value={a.clicks}
                          onChange={(e) => setAssumption(key, 'clicks', Number(e.target.value))}
                          className="py-1 text-xs"
                        />
                        <Input
                          type="number" min={0} max={100} step={0.1} value={a.conversion_rate_pct}
                          onChange={(e) => setAssumption(key, 'conversion_rate_pct', Number(e.target.value))}
                          className="py-1 text-xs"
                        />
                        <Input
                          type="number" min={0} value={a.cpc}
                          onChange={(e) => setAssumption(key, 'cpc', Number(e.target.value))}
                          className="py-1 text-xs"
                        />
                      </div>
                      <p className="mt-1.5 text-[10px] text-muted">clicks · CVR% · CPC</p>
                    </div>
                  )
                })}
              </div>
              <div className="mt-4">
                <ScenarioChart analysis={analysis} />
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {SCENARIOS.map(({ key, label }) => {
                  const s = analysis.scenarios[key]
                  if (!s?.available) return null
                  return (
                    <div key={key} className="rounded-lg bg-mist/60 p-3 text-xs">
                      <p className="font-semibold text-ink">{label}</p>
                      <p className="mt-1 text-muted">revenue {currency} {(s.revenue ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                      <p className={s.net_profit != null && s.net_profit >= 0 ? 'text-brand' : 'text-danger'}>
                        net {currency} {(s.net_profit ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </p>
                      <p className="text-muted">ROAS {s.roas != null ? s.roas.toFixed(2) : '—'}</p>
                    </div>
                  )
                })}
              </div>
            </Card>

            {/* ---------------------------------------------------- budget + KPIs */}
            <Card>
              <SectionTitle title="Budget & campaign KPIs" />
              {project.campaign ? (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <Stat label="Budget" value={`${currency} ${analysis.budget_summary.budget?.toLocaleString() ?? '—'}`} />
                    <Stat
                      label="Planned spend"
                      value={`${currency} ${analysis.budget_summary.planned_spend?.toLocaleString() ?? '—'}`}
                      sub={`${analysis.budget_summary.utilization_pct ?? 0}% allocated${analysis.budget_summary.expected_spend != null ? ` · ${currency} ${analysis.budget_summary.expected_spend.toLocaleString()} expected to run` : ''}`}
                    />
                    <Stat label="Remaining" value={`${currency} ${analysis.budget_summary.remaining?.toLocaleString() ?? '—'}`} tone={(analysis.budget_summary.remaining ?? 0) > 0 ? 'good' : 'neutral'} />
                  </div>
                  <div className="mt-3"><BudgetDonut allocations={project.campaign.allocations} currency={currency} /></div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-mist/60 p-3 text-xs">
                      <p className="font-semibold text-ink">Conversion rate</p>
                      <p className="mt-1 text-muted">{analysis.kpis.conversion_rate_pct != null ? `${analysis.kpis.conversion_rate_pct}% (measured)` : 'no data — needs clicks & conversions'}</p>
                    </div>
                    <div className="rounded-lg bg-mist/60 p-3 text-xs">
                      <p className="font-semibold text-ink">KPI targets</p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-3 text-muted">
                        {project.campaign.kpis.slice(0, 3).map((k) => (<li key={k}>{k}</li>))}
                      </ul>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted">No campaign yet — generate one in Marketing Studio to see budget utilization here.</p>
              )}
              <div className="mt-4"><SpendLine analysis={analysis} /></div>
            </Card>
          </div>

          {/* -------------------------------------------------- product comparison */}
          {compareProducts.length > 1 && (
            <Card>
              <SectionTitle title="Product comparison" subtitle="Shortlisted products with known price and estimated cost (sample/demo economics)." />
              <ProductComparisonChart products={compareProducts} currency={currency} />
            </Card>
          )}

          {/* ----------------------------------------------------- recommendations */}
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <SectionTitle title="Recommendations" subtitle="Written from the evidence in this project." />
              <ul className="space-y-2.5 text-sm text-ink/85">
                {analysis.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-2.5">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/15 text-[11px] font-bold text-brand">{i + 1}</span>
                    {r}
                  </li>
                ))}
              </ul>
            </Card>
            <Card>
              <SectionTitle title="Formula notes" subtitle="How each number is computed." />
              <dl className="space-y-2 text-[13px]">
                {Object.entries(analysis.formula_notes).map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-mist/60 px-3 py-2">
                    <dt className="font-semibold capitalize text-ink">{k.replace(/_/g, ' ')}</dt>
                    <dd className="mt-0.5 text-muted">{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3">
                <Badge tone={analysis.analysis_mode === 'llm' ? 'green' : 'neutral'}>
                  calculations: pure Python {analysis.analysis_mode === 'llm' ? '(LLM used for copy only)' : '(no LLM involved)'}
                </Badge>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
