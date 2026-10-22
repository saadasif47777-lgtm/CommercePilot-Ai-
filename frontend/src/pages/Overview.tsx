// Landing page and project dashboard.
//
// Two states share this file:
//   * no project open -> the welcome screen that creates the example or a blank
//     project (and lists existing ones);
//   * project open    -> workflow progress, brief, execution log and quick links.

import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, ErrorBanner, FadeIn, PageHeader, SectionTitle, SkeletonCards, Stat } from '../components/ui'
import { ExecutionTimeline, RunWorkflowButton, RetryStepButton, WorkflowSteps } from '../components/WorkflowPanel'

// Where the "recommended next action" link points for each workflow step.
const NEXT_LINK: Record<string, string> = {
  research: '/products', select: '/products', store: '/store', campaign: '/marketing', analyze: '/analytics',
}

export function OverviewPage() {
  const { project, projects, loading, error, createProject, run, clearError, integrations } = useProject()

  const startExample = () =>
    run('create-example', async () => {
      await createProject({ example: true })
    })

  const startBlank = () =>
    run('create-blank', async () => {
      await createProject({ name: 'My commerce project' })
    })

  if (loading && !project) return <div className="py-10"><SkeletonCards count={3} /></div>

  /* ------------------------------------------------- empty state / welcome */
  if (!project) {
    return (
      <div>
        <PageHeader
          eyebrow="CommercePilot AI"
          title="Build a business plan with working AI agents — in one workspace"
          body="Discover products with real web evidence, generate an interactive storefront, plan a campaign and validate the economics. Every agent hands its output to the next."
        />
        {error && <ErrorBanner message={error} onDismiss={clearError} />}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="rounded-2xl border border-line bg-paper p-8 shadow-soft"
        >
          <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <h2 className="font-display text-xl font-semibold">Start a Commerce Project</h2>
              <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted">
                The fastest path is the seeded example: a Pakistani skincare brand (Noor Glow) with a
                PKR 30,000 test budget. You can edit everything afterwards — or start blank.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Button size="lg" busy={false} onClick={startExample}>
                  Start a Commerce Project
                </Button>
                <Button size="lg" variant="secondary" onClick={startBlank}>Start blank</Button>
              </div>
              <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ['Product Hunter', 'live web + sample data'],
                  ['Store Architect', 'interactive storefront'],
                  ['Marketing Studio', 'campaign + budget'],
                  ['Business Analyst', 'tested calculations'],
                ].map(([t, s]) => (
                  <div key={t} className="rounded-lg border border-line bg-mist/60 p-3">
                    <p className="text-[13px] font-semibold text-ink">{t}</p>
                    <p className="mt-0.5 text-xs text-muted">{s}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl bg-brand p-6 text-white">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">8-step workflow</p>
              <ol className="mt-3 space-y-1.5 text-[13px] leading-relaxed text-white/85">
                {['Create a project', 'Enter the business brief', 'Research products', 'Review & select a product', 'Generate the storefront', 'Create the marketing campaign', 'Analyse business performance', 'Read the consolidated report'].map((s, i) => (
                  <li key={s}>{i + 1}. {s}</li>
                ))}
              </ol>
              <p className="mt-4 text-xs text-white/60">
                Demo data is labelled throughout. Meta &amp; Shopify integrations are shown as Not Connected.
              </p>
            </div>
          </div>
        </motion.div>

        {projects.length > 0 && (
          <div className="mt-8">
            <SectionTitle title="Existing projects" subtitle="Pick up where you left off — projects persist in SQLite." />
            <div className="grid gap-3 md:grid-cols-3">
              {projects.slice(0, 6).map((p) => (
                <ProjectTile key={p.id} id={p.id} name={p.name} updated={p.updated_at} steps={p.steps} example={p.is_example} />
              ))}
            </div>
          </div>
        )}

        {integrations && (
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <IntegrationMini name="AI model" status={integrations.llm.status} note={integrations.llm.status === 'connected' ? integrations.llm.model : 'fallback mode'} />
            <IntegrationMini name="Live web search" status={integrations.web_search.status} note={integrations.web_search.provider} />
            <IntegrationMini name="Meta Marketing API" status={integrations.meta.status} note="not published — demo only" />
            <IntegrationMini name="Shopify Admin API" status={integrations.shopify.status} note="preview works standalone" />
          </div>
        )}
      </div>
    )
  }

  /* --------------------------------------------------------- dashboard */
  // Derived progress values: how far the workflow got and what is next.
  const steps = Object.values(project.steps)
  const doneCount = steps.filter((s) => s.status === 'success').length
  const failed = steps.find((s) => s.status === 'error')
  const nextStep = steps.find((s) => s.status !== 'success')
  const unit = project.analysis?.unit_economics

  return (
    <div>
      <PageHeader
        eyebrow={project.is_example ? 'Example project · fictional brand' : 'Project'}
        title={project.name}
        body={`${project.brief.industry || project.brief.niche || 'Brief pending'} · ${project.brief.target_market} · budget ${project.brief.currency} ${project.brief.budget.toLocaleString()}`}
        actions={<RunWorkflowButton />}
      />

      {error && <ErrorBanner message={error} onDismiss={clearError} onRetry={() => run('retry', async () => undefined)} />}

      {/* Progress bar animates to the ratio of successful steps. */}
      <div className="mb-6 h-1.5 overflow-hidden rounded-full bg-mist-2">
        <motion.div className="h-full rounded-full bg-accent" initial={{ width: 0 }} animate={{ width: `${(doneCount / steps.length) * 100}%` }} transition={{ duration: 0.6 }} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-5">
          <FadeIn>
            <Card>
              <SectionTitle
                title="Workflow progress"
                subtitle={`${doneCount} of ${steps.length} steps complete`}
                right={failed ? <RetryStepButton stepId={failed.id} /> : nextStep ? <Badge tone="amber">next: {nextStep.title}</Badge> : <Badge tone="green">all steps complete</Badge>}
              />
              <WorkflowSteps />
              {nextStep && NEXT_LINK[nextStep.id] && (
                <div className="mt-4 flex items-center gap-2 rounded-lg bg-mist px-4 py-3 text-sm">
                  <span className="text-muted">Recommended next action:</span>
                  <Link to={NEXT_LINK[nextStep.id]} className="font-semibold text-brand underline-offset-2 hover:underline">
                    {nextStep.title} →
                  </Link>
                </div>
              )}
            </Card>
          </FadeIn>

          <FadeIn delay={0.05}>
            <Card>
              <SectionTitle title="Business brief" subtitle="Shared context every agent reads and updates." right={<Link to="/settings" className="text-xs font-semibold text-brand hover:underline">Edit in Settings</Link>} />
              <div className="grid gap-3 sm:grid-cols-2">
                <BriefRow label="Business" value={project.brief.business_name || '—'} />
                <BriefRow label="Niche" value={project.brief.niche || project.brief.industry || '—'} />
                <BriefRow label="Audience" value={project.brief.target_audience || '—'} />
                <BriefRow label="Budget" value={`${project.brief.currency} ${project.brief.budget.toLocaleString()}`} />
              </div>
            </Card>
          </FadeIn>

          <FadeIn delay={0.1}>
            <Card>
              <SectionTitle title="Agent execution log" subtitle="Each run records inputs, outputs, warnings and timing." />
              <ExecutionTimeline />
            </Card>
          </FadeIn>
        </div>

        <div className="space-y-5">
          <FadeIn delay={0.05}>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Product" value={project.selected_product ? '✓' : '—'} sub={project.selected_product?.title.slice(0, 32) || 'not selected'} tone={project.selected_product ? 'good' : 'neutral'} />
              <Stat label="Storefront" value={project.store_spec ? `${project.store_spec.sections.length}` : '—'} sub={project.store_spec ? 'sections generated' : 'not generated'} tone={project.store_spec ? 'good' : 'neutral'} />
              <Stat label="Break-even ROAS" value={unit?.break_even_roas ?? '—'} sub={unit?.break_even_roas ? 'gross-profit basis' : 'needs analysis'} tone={unit?.break_even_roas ? 'good' : 'neutral'} />
              <Stat label="Campaign" value={project.campaign ? `${(project.campaign.budget / 1000).toFixed(0)}k` : '—'} sub={project.campaign ? `${project.campaign.objective} · draft` : 'not planned'} tone={project.campaign ? 'good' : 'neutral'} />
            </div>
          </FadeIn>

          <FadeIn delay={0.1}>
            <Card>
              <SectionTitle title="Quick actions" />
              <div className="grid gap-2">
                <QuickAction to="/products" label="Research products" desc="Live web search + sample catalogue" />
                <QuickAction to="/store" label="Generate storefront" desc="Structured spec → interactive preview" />
                <QuickAction to="/marketing" label="Plan campaign" desc="Creatives, budget validation, DEMO simulation" />
                <QuickAction to="/analytics" label="Analyse profitability" desc="Margins, break-even ROAS, scenarios" />
              </div>
            </Card>
          </FadeIn>

          {/* Report summary: next actions plus the provenance of each number. */}
          {project.report && (
            <FadeIn delay={0.15}>
              <Card>
                <SectionTitle title="Report highlights" right={<Link to="/analytics" className="text-xs font-semibold text-brand hover:underline">open analytics</Link>} />
                <ul className="space-y-1.5 text-[13px] text-ink/85">
                  {project.report.next_actions.slice(0, 3).map((a, i) => (
                    <li key={i} className="flex gap-2"><span className="text-accent-dark">→</span>{a}</li>
                  ))}
                </ul>
                <div className="mt-3 space-y-1">
                  {project.report.data_provenance.map((p, i) => (
                    <p key={i} className="text-xs text-muted">• {p}</p>
                  ))}
                </div>
              </Card>
            </FadeIn>
          )}
        </div>
      </div>
    </div>
  )
}

function BriefRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-mist/70 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-ink">{value}</p>
    </div>
  )
}

function QuickAction({ to, label, desc }: { to: string; label: string; desc: string }) {
  return (
    <Link to={to} className="group flex items-center justify-between rounded-lg border border-line bg-paper px-4 py-3 transition-colors hover:border-brand/40">
      <span>
        <span className="block text-sm font-semibold text-ink">{label}</span>
        <span className="block text-xs text-muted">{desc}</span>
      </span>
      <span className="text-muted transition-transform group-hover:translate-x-0.5">→</span>
    </Link>
  )
}

function ProjectTile({ id, name, updated, steps, example }: { id: string; name: string; updated: string; steps: Record<string, string>; example: boolean }) {
  const { selectProject } = useProject()
  const done = Object.values(steps).filter((s) => s === 'success').length
  return (
    <button onClick={() => selectProject(id)} className="rounded-xl border border-line bg-paper p-4 text-left shadow-soft transition-shadow hover:shadow-lift">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink">{name}</p>
        {example && <Badge tone="amber">example</Badge>}
      </div>
      <p className="mt-1 text-xs text-muted">{done}/7 steps · updated {new Date(updated).toLocaleString()}</p>
    </button>
  )
}

function IntegrationMini({ name, status, note }: { name: string; status: string; note: string }) {
  const connected = status === 'connected'
  return (
    <div className="rounded-xl border border-line bg-paper p-4">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-semibold text-ink">{name}</p>
        {connected ? <Badge tone="green" pulse>connected</Badge> : <Badge tone="neutral">not connected</Badge>}
      </div>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  )
}
