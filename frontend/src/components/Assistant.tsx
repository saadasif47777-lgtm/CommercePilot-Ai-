import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorText } from '../services/api'
import { advisor, type AdvisorProfile, type AdvisorReply, type AdvisorSession, type BudgetPlan, type PendingAction } from '../services/advisor'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, ErrorBanner, Field, Input, SectionTitle, Select, Textarea } from './ui'

const SUGGESTIONS = ['How do I get started?', 'Review my business idea', 'Help me manage my budget', 'How do ads work here?']

export function AssistantChat() {
  const { project, refreshProject, loading } = useProject()
  const [useWorkspace, setUseWorkspace] = useState(true)
  const projectId = useWorkspace ? project?.id ?? null : null
  const [session, setSession] = useState<AdvisorSession | null>(null)
  const [input, setInput] = useState('')
  const [pendingText, setPendingText] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [epoch, setEpoch] = useState(0)
  const version = useRef(0)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (loading) return
    const current = ++version.current
    setSession(null); setBusy(true); setError(''); setPendingText('')
    advisor.session(projectId).then(result => { if (version.current === current) setSession(result) })
      .catch(err => { if (version.current === current) setError(errorText(err)) })
      .finally(() => { if (version.current === current) setBusy(false) })
    return () => { version.current++ }
  }, [projectId, loading, epoch])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [session?.messages, pendingText])
  async function send(message: string, updates?: Partial<AdvisorProfile>, action?: PendingAction['action']) {
    if (!session || busy || (!message.trim() && !updates && !action)) return
    const current = version.current
    setBusy(true); setError(''); setPendingText(action ? `Confirm: ${session.pending_action?.label}` : message)
    try {
      const result = await advisor.chat(session.session_token, message.trim(), updates, action)
      if (current !== version.current) return
      setSession(result); setInput('')
      if (action && projectId) await refreshProject()
    } catch (err) { if (current === version.current) setError(errorText(err)) }
    finally { if (current === version.current) { setBusy(false); setPendingText('') } }
  }
  function reset() {
    try { sessionStorage.removeItem(advisor.storageKey(projectId)) } catch { /* storage is optional */ }
    setEpoch(value => value + 1)
  }
  return <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,.8fr)]">
    <Card padded={false} className="flex h-[min(860px,calc(100dvh-120px))] min-h-[440px] flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-4 sm:px-5">
        <div><p className="font-semibold text-ink">Your business guide</p><p className="text-xs text-muted">Ideas, setup, budgets and a sensible next step.</p></div>
        <Button variant="ghost" size="sm" disabled={busy} onClick={reset}>New conversation</Button>
        {project && <Select aria-label="Assistant context" className="text-xs" value={useWorkspace ? 'project' : 'general'} disabled={busy} onChange={event => setUseWorkspace(event.target.value === 'project')}><option value="project">Use {project.name}</option><option value="general">Plan a separate idea</option></Select>}
        {!project && <Badge tone="green">Start here · no project needed</Badge>}
      </div>
      <div role="log" aria-label="AI assistant conversation" aria-live="polite" className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-5">
        <div className="mr-5 rounded-2xl bg-mist p-4 text-sm leading-relaxed">{session?.welcome || 'Welcome to CommercePilot. Tell me what you want to sell, where you want to sell it, and your budget—or ask me where to start.'}</div>
        {session?.messages.map((message, index) => <div key={index} className={`rounded-2xl p-4 text-sm leading-relaxed ${message.role === 'user' ? 'ml-7 bg-brand text-white' : 'mr-1 bg-mist sm:mr-5'}`}><p className="whitespace-pre-wrap break-words">{message.text}</p>{message.response && <ReplyDetails reply={message.response} />}</div>)}
        {pendingText && <div className="ml-7 rounded-2xl bg-brand p-4 text-sm text-white">{pendingText}</div>}
        {busy && <p role="status" className="text-sm text-muted">{session ? 'Thinking through your question…' : 'Opening your conversation…'}</p>}
        {session?.pending_action && <div className="rounded-xl border border-accent/40 bg-accent/10 p-4 text-sm"><p>Ready when you are. This will update the selected workspace.</p><p className="mb-3 mt-2 text-xs">{session.pending_action.description}</p><Button disabled={busy} onClick={() => send('', undefined, session.pending_action!.action)}>{session.pending_action.label}</Button><p className="mt-2 text-xs text-muted">Campaign generation creates a draft for review. It does not publish or spend ad money.</p></div>}
        <div ref={endRef} />
      </div>
      {error && <div className="px-4"><ErrorBanner message={error} onDismiss={() => setError('')} />{!session && <Button variant="secondary" onClick={() => setEpoch(value => value + 1)}>Retry opening chat</Button>}</div>}
      <div className="border-t border-line px-4 py-3">
        <div className="mb-3 flex flex-wrap gap-1.5">{[...SUGGESTIONS, ...(projectId ? ['Show me the report'] : [])].map(suggestion => <button key={suggestion} disabled={busy || !session} onClick={() => send(suggestion)} className="rounded-full border border-line px-2.5 py-1.5 text-[11px] text-muted transition-colors hover:border-brand/40 hover:text-brand disabled:opacity-40">{suggestion}</button>)}</div>
        <form className="flex items-end gap-2" onSubmit={event => { event.preventDefault(); send(input) }}>
          <Textarea aria-label="Message AI assistant" rows={2} maxLength={2000} value={input} placeholder="Ask a question, share your idea, or tell me your budget and location…" disabled={busy || !session} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(input) } }} className="min-h-[76px] resize-none" />
          <Button type="submit" busy={busy && !!session} disabled={!session || !input.trim()}>Send</Button>
        </form>
        <p className="mt-2 text-[11px] text-muted">Enter to send · Shift + Enter for a new line. Conversations expire after 24 hours. Keep credentials and payment details out of chat.</p>
      </div>
    </Card>
    <div className="min-w-0 space-y-5">
      {session && <><BudgetDetails budget={session.budget} /><PlanningDetails profile={session.profile} busy={busy} onApply={updates => send('Please review my idea and budget using these planning details.', updates)} /></>}
      <Card><SectionTitle title="Build your next step" /><p className="text-sm text-muted">Explore a niche, confirm the numbers, and prepare a campaign you can review. You stay in control of whether and when to advertise.</p><div className="mt-4 flex flex-wrap gap-2"><Link to="/business"><Button size="sm" variant="secondary">Business setup</Button></Link><Link to="/marketing"><Button size="sm" variant="secondary">Marketing Studio</Button></Link></div></Card>
    </div>
  </div>
}

function ReplyDetails({ reply }: { reply: AdvisorReply }) {
  return <>
    {reply.strengths.length > 0 && <div className="mt-4"><p className="font-semibold text-brand">Potential strengths</p><ul className="mt-1 list-disc space-y-1 pl-4">{reply.strengths.map((strength, index) => <li key={index}>{strength}</li>)}</ul></div>}
    {reply.risks.length > 0 && <div className="mt-4 space-y-2"><p className="font-semibold">Risks & what to do</p>{reply.risks.map((risk, index) => <div key={index} className="rounded-lg border border-line bg-paper/70 p-3"><p className="font-semibold">{risk.factor}</p><p className="mt-1 text-muted">{risk.explanation}</p><p className="mt-1"><span className="font-medium">Next move: </span>{risk.mitigation}</p></div>)}</div>}
    {reply.next_steps.length > 0 && <div className="mt-4 space-y-2">{reply.next_steps.map((step, index) => <Link key={index} to={step.route} className="block rounded-lg border border-brand/15 bg-paper px-3 py-2 hover:border-brand/50"><p className="font-semibold text-brand">{step.title} →</p><p className="mt-0.5 text-xs text-muted">{step.explanation}</p></Link>)}</div>}
    {reply.questions.length > 0 && <div className="mt-4"><p className="font-semibold">To tailor this to you</p><ul className="mt-1 list-disc space-y-1 pl-4">{reply.questions.map((question, index) => <li key={index}>{question}</li>)}</ul></div>}
    {reply.references.length > 0 && <div className="mt-3 flex flex-wrap gap-3 text-[11px]">{reply.references.map(reference => <a key={reference.url} href={reference.url} target="_blank" rel="noopener noreferrer" className="text-brand underline">{reference.title} ↗</a>)}</div>}
  </>
}

function BudgetDetails({ budget }: { budget: BudgetPlan }) {
  const amount = (value: number | null) => value == null ? 'Not known yet' : `${budget.currency || ''} ${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return <Card>
    <SectionTitle title="Your budget plan" right={<Badge tone={budget.status === 'provisional' ? 'green' : 'amber'}>{({ provisional: 'Planning estimate', needs_details: 'A few details needed', hold_paid_ads: 'Prepare before ads', overcommitted: 'Review commitments' })[budget.status]}</Badge>} />
    {budget.allocations.length > 0 ? <>
      <p className="mb-3 text-2xl font-semibold">{amount(budget.total_budget)}</p><p className="mb-3 text-xs text-muted">{budget.scope === 'business' ? 'Whole-business budget' : 'Advertising preparation & test budget'} · {budget.timeframe_days} day planning window</p>
      <table className="w-full text-sm"><caption className="sr-only">Calculated budget allocation</caption><thead><tr className="border-b border-line text-left text-xs text-muted"><th className="pb-2 font-normal">Purpose</th><th className="pb-2 text-right font-normal">Amount</th></tr></thead><tbody>{budget.allocations.map(row => <tr key={row.label} className="border-b border-line/60"><td className="py-2 pr-3">{row.label}</td><td className="py-2 text-right tabular-nums">{amount(row.amount)}</td></tr>)}</tbody><tfoot><tr><th className="pt-3 text-left">Total</th><th className="pt-3 text-right tabular-nums">{amount(budget.total_budget)}</th></tr></tfoot></table>
      <p className="mt-4 text-sm">Ad-test daily average: <span className="font-semibold">{amount(budget.daily_ad_test_average)}</span></p>
    </> : <p className="text-sm text-muted">{budget.status === 'overcommitted' ? `Your commitments exceed the available budget by ${amount(budget.shortfall ?? null)}. Reduce costs before planning ads.` : 'Tell me your budget, currency and whether it covers the whole business or advertising. I’ll help split it into practical steps.'}</p>}
    <dl className="mt-4 space-y-2 border-t border-line pt-4 text-xs"><div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">Contribution per order</dt><dd>{amount(budget.unit_economics.contribution_per_order)}</dd></div><div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">Break-even acquisition cost</dt><dd>{amount(budget.unit_economics.break_even_cpa)}</dd></div><div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">Break-even ROAS</dt><dd>{budget.unit_economics.break_even_roas == null ? 'Not known yet' : `${budget.unit_economics.break_even_roas}×`}</dd></div></dl>
    {budget.scenario && <div className="mt-4 rounded-lg bg-mist p-3 text-xs"><p>{budget.scenario.label}</p><p className="mt-2">{budget.scenario.clicks} clicks · {budget.scenario.expected_orders} illustrative orders · revenue {amount(budget.scenario.revenue)}</p></div>}
    <details className="mt-4 border-t border-line pt-3 text-xs"><summary className="cursor-pointer font-medium">Assumptions & checks</summary><ul className="mt-2 list-disc space-y-2 pl-4 text-muted">{[...budget.assumptions, ...budget.warnings].map((note, index) => <li key={index}>{note}</li>)}</ul></details>
  </Card>
}

function PlanningDetails({ profile, busy, onApply }: { profile: AdvisorProfile; busy: boolean; onApply: (value: Partial<AdvisorProfile>) => void }) {
  const [draft, setDraft] = useState<AdvisorProfile>(profile)
  useEffect(() => setDraft(profile), [profile])
  const set = <K extends keyof AdvisorProfile>(key: K, value: AdvisorProfile[K]) => setDraft(current => ({ ...current, [key]: value }))
  const numeric = (key: keyof AdvisorProfile, label: string, min = 0) => <Field label={label}><Input aria-label={label} type="number" min={min} step="any" value={draft[key] == null ? '' : String(draft[key])} onChange={event => setDraft(current => ({ ...current, [key]: event.target.value === '' ? null : Number(event.target.value) }))} /></Field>
  return <Card>
    <SectionTitle title="Planning details" subtitle="Share these in chat or fill them in here. You can start with just an idea." />
    <form className="space-y-3" onSubmit={event => { event.preventDefault(); onApply(draft) }}>
      <div className="grid grid-cols-2 gap-3">{numeric('budget', 'Available budget')}<Field label="Currency"><Input aria-label="Planning currency" maxLength={3} placeholder="PKR" value={draft.currency || ''} onChange={event => {
        const currency = event.target.value.toUpperCase() || null
        setDraft(current => ({ ...current, ...(current.currency && current.currency !== currency ? { budget: null, fixed_costs: null, selling_price: null, product_cost: null, other_costs_per_order: null, assumed_cpc: null } : {}), currency }))
      }} /></Field></div>
      <Field label="This budget covers"><Select aria-label="Budget scope" value={draft.budget_scope || ''} onChange={event => set('budget_scope', event.target.value as AdvisorProfile['budget_scope'] || null)}><option value="">Please choose</option><option value="business">The whole business</option><option value="advertising">Advertising preparation & testing</option></Select></Field>
      <Field label="Product or niche"><Input aria-label="Planning niche" maxLength={200} value={draft.niche || ''} placeholder="What do you want to sell?" onChange={event => set('niche', event.target.value || null)} /></Field>
      <Field label="Target location"><Input aria-label="Planning location" maxLength={150} value={draft.location || ''} placeholder="City / country you plan to serve" onChange={event => set('location', event.target.value || null)} /></Field>
      <Field label="Target audience"><Input aria-label="Planning audience" maxLength={400} value={draft.audience || ''} onChange={event => set('audience', event.target.value || null)} placeholder="Who is most likely to buy?" /></Field>
      <details><summary className="cursor-pointer py-2 text-sm font-medium text-brand">Costs, readiness & optional scenario</summary><div className="mt-2 space-y-3">
        <Field label="Business model"><Select aria-label="Planning business model" value={draft.business_model || ''} onChange={event => set('business_model', event.target.value as AdvisorProfile['business_model'] || null)}><option value="">Not decided</option><option value="physical">Physical products</option><option value="dropshipping">Dropshipping</option><option value="digital">Digital products</option><option value="service">Services</option></Select></Field>
        {numeric('timeframe_days', 'Planning period in days', 1)}{numeric('fixed_costs', 'Committed fixed costs')}{numeric('selling_price', 'Selling price per order', 0.01)}{numeric('product_cost', 'Product cost per order')}{numeric('other_costs_per_order', 'Other costs per order')}
        <p className="text-xs text-muted">Other costs include shipping, packaging, payment fees and a returns allowance. Leave unknown amounts blank; enter zero only when you have confirmed it.</p>
        {(['store_ready', 'tracking_ready'] as const).map(key => <Field key={key} label={key === 'store_ready' ? 'Store & checkout ready?' : 'Conversion tracking ready?'}><Select aria-label={key === 'store_ready' ? 'Store readiness' : 'Tracking readiness'} value={draft[key] === null ? '' : String(draft[key])} onChange={event => set(key, event.target.value === '' ? null : event.target.value === 'true')}><option value="">Not confirmed</option><option value="true">Yes</option><option value="false">Needs setup</option></Select></Field>)}
        {numeric('assumed_cpc', 'Your assumed cost per click', 0.01)}{numeric('assumed_conversion_pct', 'Your assumed conversion rate (%)', 0.01)}
        <p className="text-xs text-muted">CPC and conversion assumptions are optional. They produce an illustration, not a sales forecast.</p>
      </div></details>
      <Button type="submit" disabled={busy}>Review my plan</Button>
      <p className="text-[11px] text-muted">These details belong to this conversation. Use Business information or Products to change saved workspace facts.</p>
    </form>
  </Card>
}
