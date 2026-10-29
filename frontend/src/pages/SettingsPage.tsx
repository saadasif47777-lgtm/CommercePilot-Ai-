import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, ErrorBanner, Field, Input, PageHeader, SectionTitle } from '../components/ui'

export function SettingsPage() {
  const { project, integrations, run, refreshIntegrations, refreshProject, busy, error, clearError } = useProject()
  const [metaToken, setMetaToken] = useState('')
  const [metaAccount, setMetaAccount] = useState('')
  const [domain, setDomain] = useState('')
  const [shopToken, setShopToken] = useState('')
  const [message, setMessage] = useState('')
  const [catalog, setCatalog] = useState<Awaited<ReturnType<typeof api.shopifySync>> | null>(null)
  const [insights, setInsights] = useState<Awaited<ReturnType<typeof api.metaInsights>> | null>(null)

  const perform = (label: string, action: () => Promise<void>) => run(label, async () => {
    setMessage(''); await action(); await refreshIntegrations()
  })
  return <div>
    <PageHeader title="Connections & AI" body="Connect the accounts you use. Credentials are sent securely to your server and never returned to this page." actions={<Link to="/business"><Button variant="secondary">Business information</Button></Link>} />
    {error && <ErrorBanner message={error} onDismiss={clearError} />}
    {message && <div role="status" className="mb-5 rounded-lg border border-line bg-paper p-4 text-sm">{message}</div>}
    <Card className="mb-5"><SectionTitle title="Connect your workspace" subtitle="Complete setup in order, then use the verification controls to confirm each connection." /><ol className="grid list-decimal gap-3 pl-5 text-sm sm:grid-cols-3"><li><strong>AI & database</strong><p className="mt-1 text-muted">Verify the model request and confirm PostgreSQL is connected.</p></li><li><strong>Shopify knowledge</strong><p className="mt-1 text-muted">Connect your store, load the catalog, then sync products and policies in Customer Support.</p></li><li><strong>Meta reporting</strong><p className="mt-1 text-muted">Use an ads_read token for the correct account. Campaign plans remain drafts for review.</p></li></ol></Card>
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <Card>
        <SectionTitle title="AI generation" right={<ConnectionBadge status={integrations?.llm.status} />} />
        <p className="text-sm text-muted">{integrations?.llm.detail ?? 'Check your server model configuration, then verify the connection.'}</p>
        <p className="mt-2 text-sm">Default model: {integrations?.llm.model || 'Not configured'}</p>
        {Object.entries(integrations?.llm.modules ?? {}).length > 0 && <div className="mt-4 space-y-3 rounded-lg border border-line p-3">
          {Object.entries(integrations?.llm.modules ?? {}).map(([module, route]) => <div key={module} className="flex flex-wrap items-start justify-between gap-2 text-sm">
            <div className="min-w-0 flex-1 basis-[180px]"><p className="font-semibold">{({ marketing: 'Marketing Studio', store_architect: 'Store Architect', product_hunting: 'Product Hunter' } as Record<string, string>)[module] ?? module}</p><p className="mt-1 break-words text-xs text-muted">{route.provider} · {route.model}</p></div>
            <ConnectionBadge status={route.status} />
          </div>)}
        </div>}
        {(integrations?.llm.anthropic || Object.entries(integrations?.llm.modules ?? {}).length > 0) && <div className="mt-4">
          {integrations?.llm.anthropic && <p className="mb-2 text-xs text-muted">Claude available for verification: {integrations.llm.anthropic.model}</p>}
          <Button size="sm" variant="secondary" disabled={!!busy} busy={busy === 'verify-claude'} onClick={() => perform('verify-claude', async () => {
            const result = await api.verifyModel('anthropic'); setMessage('Claude connection verified: ' + result.model)
          })}>Verify Claude connection</Button>
        </div>}
        <Button className="mt-4" disabled={!!busy} busy={busy === 'verify-model'} onClick={() => perform('verify-model', async () => {
          const result = await api.verifyModel(); setMessage('AI connection verified: ' + result.model)
        })}>Verify AI connection</Button>
        <p className="mt-3 text-xs text-muted">Your administrator sets the AI provider and key in the server environment. Verification sends a small model request.</p>
      </Card>
      <Card>
        <SectionTitle title="Workspace status" />
        <p className="text-sm text-muted">Storage: {integrations?.storage.provider ?? 'Checking'} · {integrations?.storage.status ?? 'not checked'}</p>
        <p className="mt-2 text-sm text-muted">Product research: {integrations?.web_search.provider ?? 'Live search'}</p>
        <Button className="mt-4" variant="secondary" disabled={!!busy} onClick={() => perform('refresh-connections', async () => { setMessage('Connection status refreshed.') })}>Refresh status</Button>
        <p className="mt-3 text-xs text-muted">Each connected account belongs to this workspace. Use a separate workspace for an unrelated client.</p>
      </Card>
      <Card>
        <SectionTitle title="Shopify" subtitle="Read your catalog and bring a product into your workspace." right={<ConnectionBadge status={integrations?.shopify.status} />} />
        <form className="space-y-3" onSubmit={e => {
          e.preventDefault()
          perform('connect-shopify', async () => {
            const result = await api.saveShopifyCredentials({ shop_domain: domain.trim(), admin_token: shopToken })
            setShopToken('')
            if (!result.verified) throw new Error(result.detail)
            setMessage('Shopify connected. You can now load your catalog.')
          })
        }}>
          <Field label="Shop domain"><Input required value={domain} placeholder={integrations?.shopify.store_domain || 'your-store.myshopify.com'} onChange={e => setDomain(e.target.value)} /></Field>
          <Field label="Admin API access token" hint="Use read_products; add read_legal_policies for customer support policy sync."><Input required type="password" autoComplete="new-password" value={shopToken} onChange={e => setShopToken(e.target.value)} /></Field>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" busy={busy === 'connect-shopify'} disabled={!!busy}>Connect Shopify</Button>
            <Button variant="secondary" disabled={!!busy} busy={busy === 'catalog'} onClick={() => perform('catalog', async () => {
              const result = await api.shopifySync(50)
              if (!result.ok) throw new Error(result.detail || 'Catalog unavailable')
              setCatalog(result); setMessage('Shopify catalog loaded.')
            })}>Load catalog</Button>
          </div>
        </form>
        <Link to="/support" className="mt-4 inline-block text-sm text-brand underline">Set up Shopify customer support →</Link>
        {catalog && <div className="mt-5 space-y-3">
          <p className="text-xs text-muted">{catalog.count} products · {catalog.currency || 'currency unavailable'}. First 50 products; set supplier costs after importing.</p>
          {!project && <Link to="/business?new=1" className="text-sm text-brand underline">Create a business before importing →</Link>}
          {catalog.products?.map(p => <div key={p.id} className="flex items-center justify-between gap-3 rounded-lg border border-line p-3">
            <div><p className="text-sm font-semibold">{p.title}</p><p className="text-xs text-muted">{catalog.currency} {p.price ?? 'Price unavailable'}</p></div>
            <Button size="sm" disabled={!project || !!busy || p.price == null} onClick={() => perform('import-product', async () => {
              await api.importShopify(project!.id, p.id); await refreshProject(); setMessage(p.title + ' imported and selected. Enter its supplier cost in Products before checking profitability.')
            })}>Import & select</Button>
          </div>)}
        </div>}
      </Card>
      <Card>
        <SectionTitle title="Meta Ads" subtitle="Verify your ad account and read measured account performance." right={<ConnectionBadge status={integrations?.meta.status} />} />
        <form className="space-y-3" onSubmit={e => {
          e.preventDefault()
          perform('connect-meta', async () => {
            const result = await api.saveMetaCredentials({ access_token: metaToken, ad_account_id: metaAccount.trim() })
            setMetaToken('')
            if (!result.verified) throw new Error(result.detail)
            setMessage(result.detail)
          })
        }}>
          <Field label="Ad account ID"><Input required pattern="act_[0-9]+" placeholder="act_123456789" value={metaAccount} onChange={e => setMetaAccount(e.target.value)} /></Field>
          <Field label="Access token" hint="Use a token with ads_read access to this ad account."><Input required type="password" autoComplete="new-password" value={metaToken} onChange={e => setMetaToken(e.target.value)} /></Field>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={!!busy} busy={busy === 'connect-meta'}>Connect Meta</Button>
            <Button variant="secondary" disabled={!!busy} onClick={() => perform('verify-meta', async () => {
              const result = await api.verifyMeta()
              if (!result.verified) throw new Error(result.detail)
              setMessage(result.detail)
            })}>Verify saved account</Button>
            <Button variant="secondary" disabled={!!busy} busy={busy === 'meta-insights'} onClick={() => perform('meta-insights', async () => {
              const result = await api.metaInsights()
              if (!result.ok) throw new Error(result.detail)
              setInsights(result)
            })}>Read last 30 days</Button>
          </div>
        </form>
        {insights && <div className="mt-4">
          <p className="text-xs text-muted">{insights.detail}</p>
          {insights.rows?.map((row, index) => <div key={index} className="mt-3 rounded-lg bg-mist p-4 text-sm">
            <p className="font-semibold">{row.account_name}</p>
            <p className="text-xs text-muted">{row.date_start} – {row.date_stop}</p>
            <p className="mt-2">Spend: {row.account_currency} {row.spend} · Clicks: {row.clicks} · Impressions: {row.impressions}</p>
          </div>)}
        </div>}
        <p className="mt-4 text-xs text-muted">Reporting is read-only. Campaign creation in Marketing Studio produces a plan for review; this connection does not publish or spend money.</p>
      </Card>
    </div>
  </div>
}
function ConnectionBadge({ status }: { status?: string }) {
  return <Badge tone={status === 'connected' ? 'green' : status === 'configured_unverified' ? 'amber' : 'neutral'}>
    {status === 'connected' ? 'Verified' : status === 'configured_unverified' ? 'Needs verification' : 'Not connected'}
  </Badge>
}
