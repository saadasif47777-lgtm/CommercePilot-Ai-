import { useState } from 'react'
import { useProject } from '../state/ProjectContext'
import { request, errorText } from '../services/api'
import type { MarketIntelligence } from '../types'
import { Button, Card, ErrorBanner, SectionTitle } from './ui'

export function MarketResearch() {
  const { project, refreshProject } = useProject()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!project) return null
  const result = project.market_intelligence
  return <Card className="mt-5">
    <SectionTitle title="Live market & competitor discovery" subtitle="Find current sources for your saved niche and location before choosing your positioning." right={<Button busy={busy} onClick={async () => {
      setBusy(true); setError('')
      try { await request<MarketIntelligence>(`/api/projects/${project.id}/market-intelligence`, { method: 'POST', body: '{}' }); await refreshProject() }
      catch (err) { setError(errorText(err)) } finally { setBusy(false) }
    }}>{result ? 'Refresh live sources' : 'Find live competitors'}</Button>} />
    {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
    {!result ? <p className="text-sm text-muted">Save your business information first. Compare positioning, visible pricing, photography and customer policies; then use those findings in your brief.</p> : <>
      <p className="text-xs text-muted">{result.provider} · checked {new Date(result.checked_at).toLocaleString()} · {result.query}</p>
      {result.warning && <p role="status" className="mt-2 text-sm text-warn">{result.warning}</p>}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">{result.sources.map(source => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-line p-4 hover:border-brand"><p className="text-sm font-semibold text-brand">{source.title} ↗</p><p className="mt-1 break-all text-xs text-muted">{new URL(source.url).hostname}</p><p className="mt-2 text-sm">{source.snippet}</p></a>)}</div>
      <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm">{result.review_steps.map(step => <li key={step}>{step}</li>)}</ol>
      {!!result.recommendations?.length && <div className="mt-5 space-y-3"><h3 className="font-semibold">Recommendations from the visible evidence</h3>{result.recommendations.map((item, i) => <div key={i} className="rounded-lg bg-mist p-4"><p className="text-sm font-semibold">{item.suggestion}</p><p className="mt-2 text-sm text-muted">Evidence: {item.evidence}</p>{result.sources[item.source_index] && <a className="mt-2 block text-xs text-brand underline" href={result.sources[item.source_index].url} target="_blank" rel="noopener noreferrer">Check supporting source ↗</a>}</div>)}</div>}
      <p className="mt-3 text-xs text-muted">{result.limitations}</p>
    </>}
  </Card>
}
