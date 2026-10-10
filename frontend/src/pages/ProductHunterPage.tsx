import { useMemo, useState } from 'react'
import { api, errorText } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader, SectionTitle, Select, SkeletonCards, WarningList } from '../components/ui'
import { ProductCard, ProductTable } from '../components/ProductCards'
import type { Product } from '../types'

const CATEGORIES = ['', 'skincare', 'home accessories', 'fashion accessories', 'fitness', 'electronics accessories']
type SortKey = 'score' | 'price_asc' | 'price_desc' | 'margin' | 'confidence'

export function ProductHunterPage() {
  const { project, run, busy, error, refreshProject, clearError } = useProject()
  const brief = project?.brief

  const [niche, setNiche] = useState('')
  const [mode, setMode] = useState<'sample' | 'live' | 'both'>('both')
  const [priceMin, setPriceMin] = useState<string>('')
  const [priceMax, setPriceMax] = useState<string>('')
  const [constraints, setConstraints] = useState('')
  const [view, setView] = useState<'cards' | 'table'>('cards')
  const [sort, setSort] = useState<SortKey>('score')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'sample' | 'live'>('all')
  const [localError, setLocalError] = useState<string | null>(null)

  const research = project?.research ?? null

  const search = () =>
    run('research', async () => {
      if (!project) return
      setLocalError(null)
      try {
        await api.research({
          niche: niche || brief?.niche || brief?.industry || 'trending products',
          market: brief?.target_market || 'Pakistan',
          audience: brief?.target_audience,
          budget: brief?.budget,
          price_min: priceMin ? Number(priceMin) : brief?.preferred_price_min ?? null,
          price_max: priceMax ? Number(priceMax) : brief?.preferred_price_max ?? null,
          constraints: constraints ? constraints.split(',').map((s) => s.trim()).filter(Boolean) : [],
          mode,
          limit: 12,
        })
        await api.runWorkflow(project.id, { mode, auto_select: false }).catch(() => undefined)
        await refreshProject()
      } catch (err) {
        setLocalError(errorText(err))
      }
    })

  const filtered = useMemo(() => {
    if (!research) return [] as Product[]
    let rows = [...research.products]
    if (categoryFilter) rows = rows.filter((p) => p.category === categoryFilter)
    if (sourceFilter !== 'all') rows = rows.filter((p) => (sourceFilter === 'live' ? p.source !== 'sample' : p.source === 'sample'))
    const confRank = { high: 3, medium: 2, low: 1 } as const
    rows.sort((a, b) => {
      switch (sort) {
        case 'price_asc': return (a.observed_price ?? Infinity) - (b.observed_price ?? Infinity)
        case 'price_desc': return (b.observed_price ?? 0) - (a.observed_price ?? 0)
        case 'margin': return (b.margin_pct ?? -1) - (a.margin_pct ?? -1)
        case 'confidence': return confRank[b.confidence] - confRank[a.confidence]
        default: return (b.score ?? -1) - (a.score ?? -1)
      }
    })
    return rows
  }, [research, sort, categoryFilter, sourceFilter])

  const select = (id: string) =>
    run('select-product', async () => {
      if (!project) return
      await api.selectProduct(project.id, id)
      await refreshProject()
    })

  const saveCmp = (id: string) =>
    run('save-product', async () => {
      if (!project) return
      await api.saveProduct(project.id, id)
      await refreshProject()
    })

  const reject = (id: string) =>
    run('reject-product', async () => {
      if (!project) return
      await api.rejectProduct(project.id, id)
      await refreshProject()
    })

  const [manualOpen, setManualOpen] = useState(false)
  const [manual, setManual] = useState({ title: '', observed_price: '', observed_cost: '', description: '', target_audience: '' })
  const [manualPreview, setManualPreview] = useState<{ unit_economics: Record<string, number | null>; contribution_economics: Record<string, unknown> } | null>(null)

  const previewManual = () =>
    run('manual-compare', async () => {
      if (manual.title.trim().length < 2) { setLocalError('Product title is too short.'); return }
      const body: Record<string, unknown> = {
        title: manual.title.trim(),
        currency: brief?.currency ?? 'PKR',
        description: manual.description,
      }
      if (manual.observed_price) body.observed_price = Number(manual.observed_price)
      if (manual.observed_cost) body.observed_cost = Number(manual.observed_cost)
      if (manual.target_audience) body.target_audience = manual.target_audience
      const res = await api.manualCompare(body)
      setManualPreview({ unit_economics: res.analysis.unit_economics, contribution_economics: res.analysis.contribution_economics })
    })

  const saveManual = () =>
    run('manual-product', async () => {
      if (!project) return
      if (manual.title.trim().length < 2) { setLocalError('Product title is too short.'); return }
      const body: Record<string, unknown> = {
        title: manual.title.trim(),
        currency: brief?.currency ?? 'PKR',
        description: manual.description,
      }
      if (manual.observed_price) body.observed_price = Number(manual.observed_price)
      if (manual.observed_cost) body.observed_cost = Number(manual.observed_cost)
      if (manual.target_audience) body.target_audience = manual.target_audience
      await api.manualProduct(project.id, body)
      setManualOpen(false)
      setManualPreview(null)
      setManual({ title: '', observed_price: '', observed_cost: '', description: '', target_audience: '' })
      await refreshProject()
    })

  const searchLive = useMemo(() => filtered.filter((p) => p.source !== 'sample'), [filtered])
  const searchSample = useMemo(() => filtered.filter((p) => p.source === 'sample'), [filtered])

  return (
    <div>
      <PageHeader
        eyebrow="Agent A"
        title="Product Hunter"
        body="Ranks candidates with a transparent, configurable scoring function. Live results keep their source URLs; missing evidence is marked unknown — never invented."
        actions={research && <Badge tone={research.contains_live_results ? 'blue' : 'amber'}>{research.contains_live_results ? 'live + sample' : 'sample data'}</Badge>}
      />

      {(error || localError) && <ErrorBanner message={localError ?? error ?? ''} onDismiss={() => { setLocalError(null); clearError() }} />}

      {/* ------------------------------------------------------------ inputs */}
      <Card className="mb-5">
        <div className="grid gap-4 md:grid-cols-5">
          <div className="md:col-span-2">
            <Field label="Niche" hint={brief ? `From brief: ${brief.niche || brief.industry}` : 'Used for the live search query'}>
              <Input value={niche} placeholder={brief?.niche || 'e.g. vitamin c serum'} onChange={(e) => setNiche(e.target.value)} />
            </Field>
          </div>
          <Field label="Research mode" hint="Live = real web search (DuckDuckGo)">
            <Select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="both">Live search + sample data</option>
              <option value="live">Live search only</option>
              <option value="sample">Sample data only</option>
            </Select>
          </Field>
          <Field label={`Price ${brief?.currency ?? 'PKR'} min`}>
            <Input type="number" min={0} value={priceMin} placeholder={brief?.preferred_price_min ? String(brief.preferred_price_min) : 'any'} onChange={(e) => setPriceMin(e.target.value)} />
          </Field>
          <Field label="Price max">
            <Input type="number" min={0} value={priceMax} placeholder={brief?.preferred_price_max ? String(brief.preferred_price_max) : 'any'} onChange={(e) => setPriceMax(e.target.value)} />
          </Field>
        </div>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-[240px] flex-1">
            <Field label="Constraints (comma separated)" hint='e.g. "no electronics, no bulky"'>
              <Input value={constraints} placeholder="optional" onChange={(e) => setConstraints(e.target.value)} />
            </Field>
          </div>
          <Button busy={busy === 'research'} onClick={search}>
            {research ? 'Re-run research' : 'Run Product Hunter'}
          </Button>
          <Button variant="secondary" onClick={() => setManualOpen((o) => !o)}>
            {manualOpen ? 'Close' : 'Enter product manually'}
          </Button>
        </div>
        {manualOpen && (
          <div className="mt-4 rounded-xl border border-line bg-mist p-4">
            <p className="mb-3 text-xs text-muted">
              When web research is unavailable: enter the product and its economics yourself.
              Records are labelled <span className="font-semibold">manually entered</span> — nothing pretends to be
              machine-researched. Numbers you type drive Beta and Gamma working from the same data.
            </p>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <Field label="Product name"><Input value={manual.title} onChange={(e) => setManual({ ...manual, title: e.target.value })} placeholder="e.g. Herbal hair oil 100ml" /></Field>
              <Field label="Selling price"><Input type="number" min={0} value={manual.observed_price} onChange={(e) => setManual({ ...manual, observed_price: e.target.value })} placeholder="2500" /></Field>
              <Field label="Unit cost"><Input type="number" min={0} value={manual.observed_cost} onChange={(e) => setManual({ ...manual, observed_cost: e.target.value })} placeholder="1200" /></Field>
              <div className="md:col-span-2"><Field label="Description (optional)"><Input value={manual.description} onChange={(e) => setManual({ ...manual, description: e.target.value })} placeholder="what it is, key benefit" /></Field></div>
            </div>
            {manualPreview && (
              <p className="mt-3 text-xs text-muted">
                Economics preview: gross profit/unit = {manualPreview.unit_economics.gross_profit_per_unit ?? 'no data'} ·
                margin {' '}
                {manualPreview.unit_economics.gross_margin_pct ?? 'no data'}% · break-even ROAS =
                {' '}{manualPreview.unit_economics.break_even_roas ?? 'undefined'}. Nothing is saved until
                you confirm.
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <Button size="sm" variant="secondary" busy={busy === 'manual-compare'} onClick={previewManual}>Check economics first</Button>
              <Button size="sm" busy={busy === 'manual-product'} onClick={saveManual}>Save & select this product</Button>
            </div>
          </div>
        )}
      </Card>

      {busy === 'research' && <SkeletonCards count={3} />}

      {!research && busy !== 'research' && (
        <EmptyState
          title="No research yet"
          body="Run the Product Hunter to get a ranked shortlist with scores, evidence and source URLs. Sample data is clearly labelled; live results link to their sources."
          action={<Button onClick={search}>Run Product Hunter</Button>}
        />
      )}

      {research && (
        <>
          <SectionTitle
            title={`Ranked shortlist · ${filtered.length} products`}
            subtitle={`Query: “${research.query}” · ${research.elapsed_ms}ms${research.sources.length ? ` · ${research.sources.length} live sources` : ''}`}
            right={
              <div className="flex flex-wrap items-center gap-2">
                <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="w-auto py-1.5 text-xs">
                  {CATEGORIES.map((c) => (<option key={c} value={c}>{c || 'All categories'}</option>))}
                </Select>
                <Select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value as typeof sourceFilter)} className="w-auto py-1.5 text-xs">
                  <option value="all">All sources</option>
                  <option value="sample">Sample only</option>
                  <option value="live">Live only</option>
                </Select>
                <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="w-auto py-1.5 text-xs">
                  <option value="score">Sort: score</option>
                  <option value="margin">Sort: margin</option>
                  <option value="price_asc">Sort: price ↑</option>
                  <option value="price_desc">Sort: price ↓</option>
                  <option value="confidence">Sort: confidence</option>
                </Select>
                <Button size="sm" variant="secondary" onClick={() => setView(view === 'cards' ? 'table' : 'cards')}>
                  {view === 'cards' ? 'Table view' : 'Card view'}
                </Button>
              </div>
            }
          />

          {research.warnings.length > 0 && <div className="mb-4"><WarningList items={research.warnings} title="Research notes" /></div>}
          {searchSample.length > 0 && searchLive.length > 0 && view === 'cards' && (
            <p className="mb-3 text-xs text-muted">
              {searchSample.length} sample rows (demonstration data) · {searchLive.length} live web results (evidence-only, weakly scored).
            </p>
          )}

          {view === 'cards' ? (
            filtered.length === 0 ? (
              <EmptyState title="No products match the filters" body="Loosen the category or source filter, or re-run research with a wider price range." />
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {filtered.map((p) => (
                  <ProductCard key={p.id} product={p} currency={brief?.currency ?? 'PKR'} selected={project?.selected_product?.id === p.id} onSelect={() => select(p.id)} onSave={saveCmp} onReject={reject} />
                ))}
              </div>
            )
          ) : (
            <ProductTable products={filtered} currency={brief?.currency ?? 'PKR'} selectedId={project?.selected_product?.id} onSelect={select} />
          )}

          {research.sources.length > 0 && (
            <div className="mt-5 rounded-xl border border-line bg-paper p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">Live sources seen in this run</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {research.sources.map((s) => (
                  <span key={s} className="rounded-full border border-line bg-mist px-2.5 py-1 text-[11px] text-muted">{s}</span>
                ))}
              </div>
            </div>
          )}

          {project?.selected_product && (
            <div className="mt-5 rounded-xl border border-accent/40 bg-accent/5 p-4 text-sm">
              <span className="font-semibold text-ink">Selected for this project:</span> {project.selected_product.title}
              <span className="ml-2 text-xs text-muted">(flows into Store Architect, Marketing and Analytics)</span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
