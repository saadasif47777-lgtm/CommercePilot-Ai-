import { useEffect, useState } from 'react'
import { api, errorText } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, ErrorBanner, Field, Input, PageHeader, SectionTitle, Textarea, WarningList } from '../components/ui'
import type { BusinessBrief } from '../types'

export function SettingsPage() {
  const { project, integrations, run, refreshProject, error, clearError, busy } = useProject()
  const [brief, setBrief] = useState<BusinessBrief | null>(null)
  const [saved, setSaved] = useState(false)
  const [metaToken, setMetaToken] = useState('')
  const [metaAccount, setMetaAccount] = useState('')
  const [shopDomain, setShopDomain] = useState('')
  const [shopToken, setShopToken] = useState('')
  const [integrationMsg, setIntegrationMsg] = useState<string | null>(null)
  const [health, setHealth] = useState<{ status: string; llm_mode: string; projects: number } | null>(null)

  useEffect(() => {
    if (project?.brief) setBrief(JSON.parse(JSON.stringify(project.brief)))
  }, [project?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  const saveBrief = () => {
    if (!project || !brief) return
    setSaved(false)
    run('save-brief', async () => {
      await api.updateBrief(project.id, brief)
      await refreshProject()
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    })
  }

  const set = <K extends keyof BusinessBrief>(key: K, value: BusinessBrief[K]) =>
    setBrief((b) => (b ? { ...b, [key]: value } : b))

  const connectMeta = () =>
    run('meta-creds', async () => {
      const res = await api.saveMetaCredentials({ access_token: metaToken, ad_account_id: metaAccount })
      setIntegrationMsg(`Meta: ${res.detail} (verified: ${res.verified ? 'yes' : 'no'})`)
      setMetaToken('')
    }).then((ok) => { if (!ok) setIntegrationMsg(errorText(error)) })

  const connectShopify = () =>
    run('shopify-creds', async () => {
      const res = await api.saveShopifyCredentials({ shop_domain: shopDomain, admin_token: shopToken })
      setIntegrationMsg(`Shopify: ${res.detail} (verified: ${res.verified ? 'yes' : 'no'})`)
      setShopToken('')
    })

  return (
    <div>
      <PageHeader
        title="Settings & Integrations"
        body="Business brief (shared project context), service connection status and server-side credential storage. Secrets are stored outside the repository and never returned to this page."
      />
      {error && <ErrorBanner message={error} onDismiss={clearError} />}
      {integrationMsg && <div className="mb-4 rounded-lg border border-line bg-mist px-4 py-3 text-sm text-ink">{integrationMsg}</div>}

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        {/* ------------------------------------------------------------ brief */}
        <Card>
          <SectionTitle
            title="Business brief"
            subtitle="Every agent reads this shared context — update it once, use it everywhere."
            right={saved ? <Badge tone="green">saved</Badge> : undefined}
          />
          {!brief ? (
            <p className="text-sm text-muted">Select a project to edit its brief.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Business name"><Input value={brief.business_name} onChange={(e) => set('business_name', e.target.value)} /></Field>
              <Field label="Industry"><Input value={brief.industry} onChange={(e) => set('industry', e.target.value)} /></Field>
              <div className="sm:col-span-2"><Field label="Niche"><Input value={brief.niche} onChange={(e) => set('niche', e.target.value)} /></Field></div>
              <Field label="Target market"><Input value={brief.target_market} onChange={(e) => set('target_market', e.target.value)} /></Field>
              <Field label="Currency"><Input value={brief.currency} onChange={(e) => set('currency', e.target.value.toUpperCase())} /></Field>
              <div className="sm:col-span-2">
                <Field label="Target audience"><Textarea value={brief.target_audience} onChange={(e) => set('target_audience', e.target.value)} /></Field>
              </div>
              <Field label="Campaign budget"><Input type="number" min={0} value={brief.budget} onChange={(e) => set('budget', Number(e.target.value))} /></Field>
              <Field label="Brand personality"><Input value={brief.brand_personality} placeholder="e.g. premium yet warm" onChange={(e) => set('brand_personality', e.target.value)} /></Field>
              <Field label="Preferred price min"><Input type="number" min={0} value={brief.preferred_price_min ?? ''} onChange={(e) => set('preferred_price_min', e.target.value === '' ? null : Number(e.target.value))} /></Field>
              <Field label="Preferred price max"><Input type="number" min={0} value={brief.preferred_price_max ?? ''} onChange={(e) => set('preferred_price_max', e.target.value === '' ? null : Number(e.target.value))} /></Field>
              <div className="sm:col-span-2">
                <Field label="Constraints" hint="Comma separated — the hunter filters matching products out.">
                  <Input value={brief.constraints.join(', ')} onChange={(e) => set('constraints', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />
                </Field>
              </div>
              <div className="sm:col-span-2"><Field label="Notes"><Textarea value={brief.notes} onChange={(e) => set('notes', e.target.value)} /></Field></div>
              <div className="sm:col-span-2 flex items-center gap-3">
                <Button onClick={saveBrief} busy={busy === 'save-brief'}>Save brief</Button>
                <p className="text-xs text-muted">Saving resets downstream steps so nothing looks stale-but-green.</p>
              </div>
            </div>
          )}
        </Card>

        {/* ----------------------------------------------------- integrations */}
        <div className="space-y-5">
          {integrations && (
            <>
              <Card>
                <SectionTitle title="Integration status" />
                <div className="space-y-3">
                  <IntegrationRow name={integrations.llm.provider} status={integrations.llm.status} detail={integrations.llm.detail} />
                  <IntegrationRow name={integrations.web_search.provider} status={integrations.web_search.status} detail={integrations.web_search.detail} />
                  <IntegrationRow name={integrations.storage.provider + ' (projects)'} status={integrations.storage.status} detail={integrations.storage.detail} />
                </div>
                {health && (
                  <p className="mt-3 text-xs text-muted">Backend health: {health.status} · mode {health.llm_mode} · {health.projects} projects stored</p>
                )}
              </Card>

              <Card>
                <SectionTitle title="Meta Marketing API" right={<Badge tone={integrations.meta.status === 'not_connected' ? 'neutral' : 'amber'}>{integrations.meta.status === 'not_connected' ? 'Not connected' : 'Configured (unverified)'}</Badge>} />
                <p className="text-xs text-muted">{integrations.meta.note}</p>
                <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-muted">
                  {integrations.meta.missing_configuration.length
                    ? integrations.meta.missing_configuration.map((m) => <li key={m}>missing: {m}</li>)
                    : <li>credentials stored server-side</li>}
                </ul>
                <div className="mt-3 grid gap-3">
                  <Field label="Access token" hint="Stored in backend/.secrets (git-ignored). Never sent to the browser after saving.">
                    <Input type="password" value={metaToken} placeholder="EAAG…" onChange={(e) => setMetaToken(e.target.value)} />
                  </Field>
                  <Field label="Ad account id"><Input value={metaAccount} placeholder="act_123456789" onChange={(e) => setMetaAccount(e.target.value)} /></Field>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={connectMeta} disabled={!metaToken || !metaAccount}>Save &amp; verify</Button>
                    <Button size="sm" variant="secondary" onClick={() => run('meta-verify', async () => {
                      const r = await api.verifyMeta()
                      setIntegrationMsg(`Meta verify: ${r.verified ? 'valid' : 'not valid'} — ${r.detail}`)
                    })}>Verify existing</Button>
                  </div>
                </div>
                <div className="mt-3 rounded-lg bg-mist p-3 text-[11px] leading-relaxed text-muted">
                  <p className="font-semibold text-ink">Setup instructions</p>
                  <ol className="mt-1 list-decimal space-y-0.5 pl-4">
                    {integrations.meta.setup_instructions.map((s) => (<li key={s}>{s}</li>))}
                  </ol>
                </div>
              </Card>

              <Card>
                <SectionTitle title="Shopify Admin API" right={<Badge tone={integrations.shopify.status === 'not_connected' ? 'neutral' : 'amber'}>{integrations.shopify.status === 'not_connected' ? 'Not connected' : 'Configured (unverified)'}</Badge>} />
                <p className="text-xs text-muted">
                  The storefront preview works independently of Shopify. Connect to read your catalog — this prototype never publishes themes or modifies the live store.
                </p>
                <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-muted">
                  {integrations.shopify.missing_configuration.length
                    ? integrations.shopify.missing_configuration.map((m) => <li key={m}>missing: {m}</li>)
                    : <li>credentials stored server-side</li>}
                </ul>
                <div className="mt-3 grid gap-3">
                  <Field label="Store domain"><Input value={shopDomain} placeholder="your-store.myshopify.com" onChange={(e) => setShopDomain(e.target.value)} /></Field>
                  <Field label="Admin token" hint="Storefront API tokens do NOT grant admin access."><Input type="password" value={shopToken} onChange={(e) => setShopToken(e.target.value)} /></Field>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={connectShopify} disabled={!shopDomain || !shopToken}>Save &amp; verify</Button>
                    <Button size="sm" variant="secondary" onClick={() => run('shopify-sync', async () => {
                      const r = await api.shopifySync(5)
                      setIntegrationMsg(`Shopify sync: ${r.ok ? `${r.count} products` : r.detail}`)
                    })}>Test catalog read</Button>
                  </div>
                </div>
              </Card>
            </>
          )}

          <Card>
            <SectionTitle title="Data & labelling policy" />
            <WarningList
              title="How this prototype labels itself"
              items={[
                'Sample/demo product data comes from backend/data/sample_products.json and is labelled on every surface.',
                'Live web search results keep their source URLs; cost, demand and competition stay “unknown” when not evidenced.',
                'Campaign simulations are labelled DEMO — NOT PUBLISHED, with the assumptions shown.',
                'No LLM is configured in fallback mode: copy is template-generated and says so.',
              ]}
            />
          </Card>
        </div>
      </div>
    </div>
  )
}

function IntegrationRow({ name, status, detail }: { name: string; status: string; detail: string }) {
  const connected = status === 'connected'
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-line bg-mist/50 px-3 py-2.5">
      <div>
        <p className="text-[13px] font-semibold text-ink">{name}</p>
        <p className="text-xs text-muted">{detail}</p>
      </div>
      {connected ? <Badge tone="green" pulse>connected</Badge> : <Badge tone="neutral">not connected</Badge>}
    </div>
  )
}
