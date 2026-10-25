import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { blankBrief, useProject } from '../state/ProjectContext'
import type { BusinessBrief } from '../types'
import { MarketResearch } from '../components/MarketResearch'
import { Badge, Button, Card, ErrorBanner, Field, Input, PageHeader, Textarea } from '../components/ui'

export function BusinessPage() {
  const { project, createProject, refreshProject, refreshProjects, run, busy, error, clearError } = useProject()
  const location = useLocation()
  const navigate = useNavigate()
  const newBusiness = new URLSearchParams(location.search).has('new') || !project
  const [brief, setBrief] = useState<BusinessBrief>(blankBrief(''))
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    setBrief(newBusiness ? blankBrief('') : structuredClone(project!.brief)); setSaved(false)
  }, [project?.id, newBusiness])
  const set = <K extends keyof BusinessBrief>(key: K, value: BusinessBrief[K]) => { setSaved(false); setBrief(b => ({ ...b, [key]: value })) }
  return <div>
    <PageHeader title={newBusiness ? 'Set up your business' : 'Business information'} body="Tell the AI agents about your business. Your product research, storefront and campaign plans will use this information." actions={<Link to="/settings"><Button variant="secondary">Connect Shopify & Meta</Button></Link>} />
    {error && <ErrorBanner message={error} onDismiss={clearError} />}
    <Card>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={async e => {
        e.preventDefault()
        const ok = await run('save-business', async () => {
          if (newBusiness) await createProject({ name: brief.business_name.trim(), brief })
          else { await api.updateBrief(project!.id, brief); await refreshProject(); await refreshProjects() }
        })
        if (ok) { setSaved(true); navigate('/business', { replace: true }) }
      }}>
        <Field label="Business name"><Input required maxLength={120} value={brief.business_name} onChange={e => set('business_name', e.target.value)} placeholder="Your business name" /></Field>
        <Field label="Industry"><Input required value={brief.industry} onChange={e => set('industry', e.target.value)} placeholder="e.g. Home and living" /></Field>
        <div className="sm:col-span-2"><Field label="Products or niche"><Input required value={brief.niche} onChange={e => set('niche', e.target.value)} placeholder="What do you sell or want to research?" /></Field></div>
        <Field label="Target market"><Input required value={brief.target_market} onChange={e => set('target_market', e.target.value)} /></Field>
        <Field label="Currency"><Input required minLength={3} maxLength={8} value={brief.currency} onChange={e => set('currency', e.target.value.toUpperCase())} /></Field>
        <div className="sm:col-span-2"><Field label="Target audience"><Textarea required value={brief.target_audience} onChange={e => set('target_audience', e.target.value)} placeholder="Who buys your products?" /></Field></div>
        <Field label="Campaign budget"><Input required type="number" min={0.01} step="0.01" value={brief.budget || ''} onChange={e => set('budget', Number(e.target.value))} /></Field>
        <Field label="Brand personality"><Input value={brief.brand_personality} onChange={e => set('brand_personality', e.target.value)} placeholder="e.g. practical, warm, trustworthy" /></Field>
        <Field label="Preferred price minimum"><Input type="number" min={0} step="0.01" value={brief.preferred_price_min ?? ''} onChange={e => set('preferred_price_min', e.target.value === '' ? null : Number(e.target.value))} /></Field>
        <Field label="Preferred price maximum"><Input type="number" min={brief.preferred_price_min ?? 0} step="0.01" value={brief.preferred_price_max ?? ''} onChange={e => set('preferred_price_max', e.target.value === '' ? null : Number(e.target.value))} /></Field>
        <div className="sm:col-span-2"><Field label="Constraints" hint="Separate entries with commas, such as no electronics, lightweight only."><Input value={brief.constraints.join(', ')} onChange={e => set('constraints', e.target.value.split(',').map(s => s.trim()))} /></Field></div>
        <div className="sm:col-span-2"><Field label="Additional business information"><Textarea value={brief.notes} onChange={e => set('notes', e.target.value)} /></Field></div>
        <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
          <Button type="submit" busy={busy === 'save-business'}>{newBusiness ? 'Create business workspace' : 'Save business information'}</Button>
          {saved && <Badge tone="green">Business information saved</Badge>}
          {!newBusiness && <Link to="/products" className="text-sm font-semibold text-brand">Continue to products →</Link>}
        </div>
        {!newBusiness && <p className="sm:col-span-2 text-xs text-muted">Changing business information clears outputs based on the previous brief. Regenerate them after saving.</p>}
      </form>
    </Card>
    {!newBusiness && <MarketResearch />}
  </div>
}
