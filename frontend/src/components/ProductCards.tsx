import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge, Button } from './ui'
import type { Product, ScoreFactor } from '../types'

export function money(value: number | null | undefined, currency = 'PKR'): string {
  if (value === null || value === undefined) return '—'
  return `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

export function SourceBadge({ product }: { product: Product }) {
  if (product.source === 'live') return <Badge tone="blue">live web result</Badge>
  if (product.source === 'merged') return <Badge tone="blue">merged (sample + live)</Badge>
  return <Badge tone="amber">sample data</Badge>
}

export function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-muted">not scored</span>
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-mist-2">
        <motion.div
          className="h-full rounded-full bg-accent"
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, score)}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
      <span className="text-sm font-semibold tabular-nums text-ink">{score.toFixed(1)}</span>
    </div>
  )
}

export function ScoreBreakdown({ factors, coverage }: { factors: ScoreFactor[]; coverage?: number | null }) {
  return (
    <div className="rounded-lg border border-line bg-mist/60 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        Scoring breakdown
        {coverage !== null && coverage !== undefined && (
          <span className="ml-2 font-normal normal-case tracking-normal">
            (evidence coverage {(coverage * 100).toFixed(0)}%)
          </span>
        )}
      </p>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-muted">
            <th className="pb-1 font-medium">Factor</th>
            <th className="pb-1 font-medium">Weight</th>
            <th className="pb-1 font-medium">Score</th>
            <th className="pb-1 font-medium">Adds</th>
          </tr>
        </thead>
        <tbody>
          {factors.map((f) => (
            <tr key={f.factor} className="border-t border-line/60 align-top">
              <td className="py-1.5 pr-2 font-medium capitalize text-ink">{f.factor.replace('_', ' ')}</td>
              <td className="py-1.5 pr-2 tabular-nums text-muted">{(f.weight * 100).toFixed(0)}%</td>
              <td className="py-1.5 pr-2 tabular-nums">
                {f.raw_score === null ? <span className="text-muted">unknown</span> : f.raw_score.toFixed(0)}
              </td>
              <td className="py-1.5 pr-2 tabular-nums">
                {f.contribution === null ? <span className="text-muted">—</span> : `+${f.contribution.toFixed(1)}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {factors.some((f) => f.raw_score === null) && (
        <p className="mt-2 text-[11px] leading-relaxed text-muted">
          Unknown factors are excluded and remaining weights renormalised — missing evidence is never invented.
        </p>
      )}
    </div>
  )
}

export function ProductCard({
  product,
  currency = 'PKR',
  selected = false,
  onSelect,
}: {
  product: Product
  currency?: string
  selected?: boolean
  onSelect?: () => void
}) {
  const [showDetail, setShowDetail] = useState(false)
  return (
    <motion.div
      layout
      className={`flex flex-col rounded-xl border bg-paper p-4 transition-shadow ${
        selected ? 'border-accent shadow-lift' : 'border-line shadow-soft hover:shadow-lift'
      }`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="ink">{product.category}</Badge>
          <SourceBadge product={product} />
        </div>
        <Badge tone={product.confidence === 'high' ? 'green' : product.confidence === 'medium' ? 'amber' : 'neutral'}>
          {product.confidence} confidence
        </Badge>
      </div>

      <h3 className="font-display text-[15px] font-semibold leading-snug text-ink">{product.title}</h3>
      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{product.description}</p>

      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <div>
          <p className="text-muted">Price</p>
          <p className="font-semibold text-ink">{money(product.observed_price, product.currency ?? currency)}</p>
        </div>
        <div>
          <p className="text-muted">Est. cost</p>
          <p className="font-semibold text-ink">{product.estimated_cost ? money(product.estimated_cost, currency) : 'unknown'}</p>
        </div>
        <div>
          <p className="text-muted">Margin</p>
          <p className="font-semibold text-ink">{product.margin_pct !== null ? `${product.margin_pct.toFixed(0)}%` : 'unknown'}</p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <ScoreBar score={product.score} />
        <span className="text-[11px] capitalize text-muted">
          demand {product.demand_level ?? 'unknown'} · competition {product.competition}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {onSelect && (
          <Button size="sm" variant={selected ? 'accent' : 'primary'} onClick={onSelect}>
            {selected ? 'Selected ✓' : 'Add to Project'}
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => setShowDetail((s) => !s)}>
          {showDetail ? 'Hide evidence' : 'Why this rank?'}
        </Button>
        {product.source_url && (
          <a
            href={product.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-brand underline-offset-2 hover:underline"
          >
            Source ↗
          </a>
        )}
      </div>

      <AnimatePresence>
        {showDetail && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-2">
              <ScoreBreakdown factors={product.score_breakdown} coverage={product.evidence_coverage} />
              <p className="text-xs leading-relaxed text-muted">{product.ranking_reason}</p>
              {product.demand_signals.length > 0 && (
                <div className="rounded-lg border border-line p-3">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Evidence</p>
                  <ul className="space-y-1 text-xs text-ink">
                    {product.demand_signals.slice(0, 4).map((s, i) => (
                      <li key={i} className="flex flex-wrap items-baseline gap-1.5">
                        <span className="font-medium">{s.label}:</span>
                        <span className="text-muted">{s.value}</span>
                        {s.evidence.startsWith('http') ? (
                          <a href={s.evidence} target="_blank" rel="noreferrer noopener" className="text-brand hover:underline">link ↗</a>
                        ) : (
                          <span className="text-muted/70">({s.evidence})</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export function ProductTable({
  products,
  currency = 'PKR',
  selectedId,
  onSelect,
}: {
  products: Product[]
  currency?: string
  selectedId?: string | null
  onSelect?: (id: string) => void
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-paper">
      <table className="w-full min-w-[860px] text-sm">
        <thead>
          <tr className="border-b border-line bg-mist/60 text-left text-xs font-semibold uppercase tracking-wide text-muted">
            <th className="px-4 py-2.5">#</th>
            <th className="px-4 py-2.5">Product</th>
            <th className="px-4 py-2.5">Source</th>
            <th className="px-4 py-2.5 text-right">Price</th>
            <th className="px-4 py-2.5 text-right">Est. cost</th>
            <th className="px-4 py-2.5 text-right">Margin</th>
            <th className="px-4 py-2.5">Score</th>
            <th className="px-4 py-2.5">Confidence</th>
            <th className="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody>
          {products.map((p, i) => (
            <tr key={p.id} className={`border-b border-line/70 last:border-0 ${selectedId === p.id ? 'bg-accent/5' : ''}`}>
              <td className="px-4 py-2.5 text-xs text-muted">{i + 1}</td>
              <td className="px-4 py-2.5">
                <p className="font-medium text-ink">{p.title}</p>
                <p className="text-xs capitalize text-muted">{p.category}</p>
              </td>
              <td className="px-4 py-2.5"><SourceBadge product={p} /></td>
              <td className="px-4 py-2.5 text-right tabular-nums">{money(p.observed_price, p.currency ?? currency)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{p.estimated_cost ? money(p.estimated_cost, currency) : <span className="text-muted">unknown</span>}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{p.margin_pct !== null ? `${p.margin_pct.toFixed(1)}%` : <span className="text-muted">unknown</span>}</td>
              <td className="px-4 py-2.5"><ScoreBar score={p.score} /></td>
              <td className="px-4 py-2.5 text-xs capitalize text-muted">{p.confidence}</td>
              <td className="px-4 py-2.5 text-right">
                {onSelect && (
                  <Button size="sm" variant={selectedId === p.id ? 'accent' : 'secondary'} onClick={() => onSelect(p.id)}>
                    {selectedId === p.id ? 'Selected ✓' : 'Add'}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
