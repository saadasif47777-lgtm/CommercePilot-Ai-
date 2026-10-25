// Agent A — Product Hunter.
//
// Runs the research step, then lets the user filter/sort the ranked shortlist
// and pick the product that flows into the store, campaign and analysis. A
// manual-entry panel exists for the case where web search is unavailable; those
// rows are labelled "manually entered" so they are never mistaken for evidence.

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorText, request } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader, SectionTitle, Select, SkeletonCards, WarningList } from '../components/ui'
import { ProductCard, ProductTable } from '../components/ProductCards'
import type { Product } from '../types'
import { MarketResearch } from '../components/MarketResearch'

const CATEGORIES = ['', 'skincare', 'home accessories', 'fashion accessories', 'fitness', 'electronics accessories']
// Sort keys exposed in the UI; `score` is the backend's weighted rank.
type SortKey = 'score' | 'price_asc' | 'price_desc' | 'margin' | 'confidence'

export function ProductHunterPage() {
  const { project, run, busy, error, refreshProject, clearError } = useProject()
  const brief = project?.brief

  const [niche, setNiche] = useState('')
  const [productUrl, setProductUrl] = useState('')
  const [urlMessage, setUrlMessage] = useState('')
  const mode = 'live' as const
  const [priceMin, setPriceMin] = useState<string>('')
  const [priceMax, setPriceMax] = useState<string>('')
  const [constraints, setConstraints] = useState('')
  const [view, setView] = useState<'cards' | 'table'>('cards')
  const [sort, setSort] = useState<SortKey>('score')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'sample' | 'live'>('all')
  const [localError, setLocalError] = useState<string | null>(null)

  const research = project?.research ?? null
  const [sellingPrice, setSellingPrice] = useState('')
  const [supplierCost, setSupplierCost] = useState('')
  useEffect(() => {
    const matchesCurrency = !project?.selected_product?.currency || project.selected_product.currency === project.brief.currency
    setSellingPrice(matchesCurrency ? String(project?.selected_product?.observed_price ?? '') : '')
    setSupplierCost(String(project?.selected_product?.observed_cost ?? project?.selected_product?.estimated_cost ?? ''))
  }, [project?.selected_product?.id])

  // Research request: the niche falls back to the brief so one click works even
  // on a brand new project. After a successful search the project is reloaded
  // so the shared store contains the new candidates.
  const search = () =>
    run('research', async () => {
      if (!project) return
      setLocalError(null)
      try {
        await api.projectResearch(project.id, {
          currency: brief?.currency,
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
        await refreshProject()
      } catch (err) {
        setLocalError(errorText(err))
      }
    })

  // Filtering and sorting happen client-side on the returned list: the backend
  // order is preserved as the default (highest score first).
  const filtered = useMemo(() => {
    if (!research) return [] as Product[]
    let rows = research.products.filter(p => !p.is_sample_data && p.page_kind !== 'collection')
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

  // Curation actions. Each one updates the project, so the selected product is
  // instantly available to the downstream agents.
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

  // Manual product entry (offline fallback), including a dry-run economics
  // preview so the user sees the numbers before anything is saved.
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
        actions={<Link to="/settings"><Button variant="secondary">Import from Shopify</Button></Link>}
      />

      {(error || localError) && <ErrorBanner message={localError ?? error ?? ''} onDismiss={() => { setLocalError(null); clearError() }} />}
      <Card className="mb-5"><SectionTitle title="Research an individual product URL" subtitle="Open a collection result, choose a specific item, and paste its public HTTPS product link here. Accessible structured details are saved to your library." /><form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); run('import-url', async () => { if (!project) return; setUrlMessage(''); await request(`/api/projects/${project.id}/products/from-url`, { method: 'POST', body: JSON.stringify({ url: productUrl }) }); await refreshProject(); setUrlMessage('Product details saved to your library. Review the source, select the product and confirm your own economics.') }) }}><div className="min-w-0 flex-1"><Field label="Individual product URL"><Input type="url" required value={productUrl} onChange={e => setProductUrl(e.target.value)} placeholder="https://brand.com/products/ceramic-vase" /></Field></div><Button type="submit" disabled={!project || !!busy} busy={busy === 'import-url'}>Read & save product</Button></form>{urlMessage && <p role="status" className="mt-3 text-sm text-brand">{urlMessage}</p>}<p className="mt-3 text-xs text-muted">Restricted pages, login walls and JavaScript-only pricing may need manual entry or Shopify import. Supplier costs are never inferred from a retailer's price.</p></Card>
      <Card className="mb-5">
        <SectionTitle title="Your product library" subtitle="Saved to this project's database. Save candidates to compare; select one to use in your storefront, campaign and analytics." />
        <div className="grid gap-3 sm:grid-cols-2">{(project?.saved_products ?? []).map(p => <div key={p.id} className="rounded-lg border border-line p-3"><p className="font-semibold">{p.title}</p><p className="mt-1 text-xs text-muted">{p.source} · {p.currency} {p.observed_price ?? 'price needs confirmation'}</p>{p.source_url && <a className="mt-2 block text-sm text-brand underline" href={p.source_url} target="_blank" rel="noopener noreferrer">View original source ↗</a>}<Button size="sm" variant="secondary" disabled={!!busy} onClick={() => select(p.id)} className="mt-3">{project?.selected_product?.id === p.id ? 'Currently selected' : 'Use this product'}</Button></div>)}</div>
        {!project?.saved_products?.length && <p className="text-sm text-muted">No saved candidates yet. Use “Save to compare” on a result below. The active product is separate from this saved collection.</p>}
      </Card>
      <details className="mb-5 rounded-xl border border-line bg-paper p-4"><summary className="cursor-pointer font-semibold">How research sources and ranking work</summary><p className="mt-2 text-sm text-muted">Live search discovers public listings and preserves their original links. A listing is not proof of demand, sales or supplier reliability. Confirm currency, product details and supplier cost before selection. Shopify and manually entered products are labelled separately. Saved candidates remain in your library when you run a new search.</p><MarketResearch /></details>

      {/* ------------------------------------------------------------ inputs */}
      <Card className="mb-5">
        <div className="grid gap-4 md:grid-cols-5">
          <div className="md:col-span-2">
            <Field label="Niche" hint={brief ? `From brief: ${brief.niche || brief.industry}` : 'Used for the live search query'}>
              <Input value={niche} placeholder={brief?.niche || 'e.g. vitamin c serum'} onChange={(e) => setNiche(e.target.value)} />
            </Field>
          </div>
          <Field label="Research source"><Input value="Live web search" readOnly /></Field>
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
          <Button busy={busy === 'research'} onClick={search} disabled={!project || !!busy}>
            {research ? 'Re-run research' : 'Run Product Hunter'}
          </Button>
          <Button variant="secondary" disabled={!project} onClick={() => setManualOpen((o) => !o)}>
            {manualOpen ? 'Close' : 'Enter product manually'}
          </Button>
        </div>
        {manualOpen && (
          <div className="mt-4 rounded-xl border border-line bg-mist p-4">
            <p className="mb-3 text-xs text-muted">
              When web research is unavailable: enter the product and its economics yourself.
              Records are labelled <span className="font-semibold">manually entered</span> — nothing pretends to be
              machine-researched. Your prices and costs are used by the store, campaign and analyst.
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

      {!project && <Link to="/business?new=1" className="mb-4 block text-sm font-semibold text-brand">Set up your business to research products →</Link>}
      {project?.selected_product && <Card className="mb-5">
        <SectionTitle title="Selected product economics" subtitle={project.selected_product.title + ' · ' + project.brief.currency} />
        <form className="flex flex-wrap items-end gap-3" onSubmit={e => {
          e.preventDefault()
          run('save-economics', async () => {
            await api.updateEconomics(project.id, { observed_price: Number(sellingPrice), observed_cost: Number(supplierCost), currency: project.brief.currency })
            await refreshProject()
          })
        }}>
          <Field label="Selling price"><Input required type="number" min="0.01" step="0.01" value={sellingPrice} onChange={e => setSellingPrice(e.target.value)} /></Field>
          <Field label="Supplier cost per unit"><Input required type="number" min="0" step="0.01" value={supplierCost} onChange={e => setSupplierCost(e.target.value)} /></Field>
          <Button type="submit" disabled={!!busy} busy={busy === 'save-economics'}>Save prices & costs</Button>
          <Link to="/store" className="py-2 text-sm font-semibold text-brand">Continue to storefront →</Link>
        </form>
        <p className="mt-3 text-xs text-muted">Use confirmed values in your business currency. Saving clears outputs that used the previous values.</p>
      </Card>}
      {busy === 'research' && <SkeletonCards count={3} />}

      {!research && busy !== 'research' && (
        <EmptyState
          title="No research yet"
          body="Run the Product Hunter to get a ranked shortlist with scores, evidence and source URLs. Live results link to their sources."
          action={<Button onClick={search}>Run Product Hunter</Button>}
        />
      )}          {/* Results: card view for browsing, table view for comparing numbers. */}
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
                  <option value="live">Web and imported products</option>
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
          {research.products.some(p => p.page_kind === 'collection') && <Card className="mb-5"><SectionTitle title="Collection sources — choose an individual item" subtitle="These pages contain many listings, so they are kept separate from product candidates and have no single price or product score." /><div className="grid gap-3 sm:grid-cols-2">{research.products.filter(p => p.page_kind === 'collection').map(p => <a key={p.id} href={p.source_url || undefined} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-line p-4 text-sm text-brand"><strong>{p.title} ↗</strong><p className="mt-2 text-muted">Open this collection, choose one item, then paste its product URL above.</p></a>)}</div></Card>}
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
