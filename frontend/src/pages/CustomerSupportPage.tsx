import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, ErrorBanner, Field, Input, PageHeader, SectionTitle, Textarea } from '../components/ui'
import { errorText } from '../services/api'
import { supportApi, type ChatTurn, type SupportReply, type SupportSettings, type SupportStatus, type SyncProgress } from '../services/support'

const defaults: SupportSettings = {
  enabled: false, assistant_name: 'Shop assistant', welcome: 'Hi! How can I help you find a product or answer a store question?',
  accent: '#174A38', support_email: '', allowed_origins: [], faqs: [],
}

export function CustomerSupportPage() {
  const [status, setStatus] = useState<SupportStatus | null>(null)
  const [settings, setSettings] = useState<SupportSettings>(defaults)
  const [origins, setOrigins] = useState('')
  const [snippet, setSnippet] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [progress, setProgress] = useState<SyncProgress | null>(null)
  const mounted = useRef(true)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<(ChatTurn & { reply?: SupportReply })[]>([])
  const conversation = useRef<HTMLDivElement>(null)

  useEffect(() => {
    mounted.current = true
    supportApi.status().then(data => {
      if (!mounted.current) return
      setStatus(data); setSettings(data.settings); setOrigins(data.settings.allowed_origins.join('\n'))
    }).catch(err => { if (mounted.current) setError(errorText(err)) })
    supportApi.install().then(data => { if (mounted.current) setSnippet(data.snippet) }).catch(err => { if (mounted.current) setError(errorText(err)) })
    return () => { mounted.current = false }
  }, [])
  useEffect(() => { conversation.current?.scrollTo({ top: conversation.current.scrollHeight, behavior: 'smooth' }) }, [turns])

  const update = <K extends keyof SupportSettings>(key: K, value: SupportSettings[K]) => setSettings(current => ({ ...current, [key]: value }))
  async function perform(label: string, action: () => Promise<void>) {
    setBusy(label); setError(''); setNotice('')
    try { await action() } catch (err) { if (mounted.current) setError(errorText(err)) }
    finally { if (mounted.current) setBusy('') }
  }
  async function sync(resume = false) {
    await perform('sync', async () => {
      let next: SyncProgress = resume && status?.pending
        ? { ...status.pending, complete: false, products: 0, policies: 0 }
        : await supportApi.startSync()
      setProgress(next)
      while (!next.complete && mounted.current) {
        next = await supportApi.nextPage(next.sync_id)
        if (mounted.current) setProgress(next)
      }
      if (mounted.current) {
        setStatus(await supportApi.status()); setTurns([])
        setNotice(`Synced ${next.products} published products and ${next.policies} policies. Test an answer, then enable storefront chat and save.`)
      }
    })
    if (mounted.current) supportApi.status().then(setStatus).catch(() => {})
  }
  async function send(text: string) {
    if (!text.trim() || busy) return
    await perform('chat', async () => {
      const reply = await supportApi.preview(text.trim(), turns.map(({ role, content }) => ({ role, content })))
      setTurns(current => [...current, { role: 'user', content: text.trim() }, { role: 'assistant', content: reply.answer, reply }])
      setMessage('')
    })
  }
  return <div>
    <PageHeader title="Customer support" body="Help shoppers find the right product and understand your store’s policies, directly on Shopify." actions={<Link to="/settings"><Button variant="secondary">Shopify connection</Button></Link>} />
    {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
    {notice && <div role="status" className="mb-5 rounded-xl border border-accent/30 bg-accent/10 p-4 text-sm text-brand">{notice}</div>}
    <div className="grid items-start gap-5 xl:grid-cols-[1fr_1fr]">
      <div className="space-y-5">
        <Card>
          <SectionTitle title="1. Sync store knowledge" right={<Badge tone={status?.ready ? 'green' : 'amber'}>{status?.ready ? 'Ready to answer' : 'Needs sync'}</Badge>} />
          <p className="text-sm text-muted">Connect Shopify with <code>read_products</code> and <code>read_legal_policies</code> access. Sync imports published online products, prices, links and your actual store policies.</p>
          {status?.shop && <p className="mt-3 font-semibold">{status.shop.name} <span className="font-normal text-muted">· {status.shop.domain}</span></p>}
          <div className="my-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-mist p-3"><p className="text-2xl font-semibold">{status?.counts.product ?? 0}</p><p className="text-xs text-muted">Published products</p></div>
            <div className="rounded-lg bg-mist p-3"><p className="text-2xl font-semibold">{status?.counts.policy ?? 0}</p><p className="text-xs text-muted">Store policies</p></div>
          </div>
          <p className="text-xs text-muted">{status?.synced_at ? `Last synced: ${new Date(status.synced_at).toLocaleString()}` : 'No completed sync yet.'}</p>
          {status?.reason && <p className="mt-2 text-sm text-warn">{status.reason}</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button disabled={!!busy} busy={busy === 'sync'} onClick={() => sync()}>Sync Shopify knowledge</Button>
            {status?.pending && <Button variant="secondary" disabled={!!busy} onClick={() => sync(true)}>Resume sync</Button>}
          </div>
          {progress && <p role="status" className="mt-3 text-sm text-muted">{progress.complete ? 'Sync complete' : 'Syncing'} · {progress.scanned} products checked · {progress.pages} pages</p>}
          <p className="mt-3 text-xs text-muted">Refresh at least every {status?.knowledge_hours ?? 24} hours. Chat pauses when knowledge expires. Price and availability are confirmed on the product page.</p>
        </Card>
        <Card>
          <SectionTitle title="2. Make it yours" />
          <form className="space-y-4" onSubmit={event => { event.preventDefault(); perform('save', async () => {
            const data = await supportApi.save({ ...settings, allowed_origins: origins.split('\n').map(value => value.trim()).filter(Boolean) })
            setStatus(data); setSettings(data.settings); setNotice('Support settings saved.'); setTurns([])
          }) }}>
            <Field label="Assistant name"><Input required maxLength={60} value={settings.assistant_name} onChange={e => update('assistant_name', e.target.value)} /></Field>
            <Field label="Welcome message"><Textarea required maxLength={300} rows={3} value={settings.welcome} onChange={e => update('welcome', e.target.value)} /></Field>
            <div className="grid gap-3 sm:grid-cols-[1fr_110px]">
              <Field label="Customer support email" hint="Shown when a shopper needs personal help or an answer is missing."><Input type="email" maxLength={200} value={settings.support_email} onChange={e => update('support_email', e.target.value)} placeholder="support@your-store.com" /></Field>
              <Field label="Chat color"><Input type="color" value={settings.accent} onChange={e => update('accent', e.target.value)} className="h-11" /></Field>
            </div>
            <Field label="Additional storefront origins" hint="One HTTPS origin per line. Your synced Shopify and primary store domains are already allowed."><Textarea rows={2} value={origins} onChange={e => setOrigins(e.target.value)} placeholder="https://www.your-store.com" /></Field>
            <label className="flex cursor-pointer items-center gap-3 rounded-lg bg-mist p-3 text-sm"><input type="checkbox" checked={settings.enabled} disabled={!status?.ready && !settings.enabled} onChange={e => update('enabled', e.target.checked)} />Enable storefront chat</label>
            <Button type="submit" disabled={!!busy || !status} busy={busy === 'save'}>Save support settings</Button>
          </form>
        </Card>
        <Card>
          <SectionTitle title="Extra store FAQs" subtitle="Add answers specific to your business. Save settings after editing." />
          {settings.faqs.length === 0 && <p className="mb-3 text-sm text-muted">Add details that are not in Shopify policies, such as gift wrapping or product care.</p>}
          <div className="space-y-4">{settings.faqs.map((faq, index) => <div key={index} className="space-y-3 rounded-lg border border-line p-3">
            <Field label={`FAQ ${index + 1} question`}><Input maxLength={200} value={faq.question} onChange={e => update('faqs', settings.faqs.map((item, i) => i === index ? { ...item, question: e.target.value } : item))} /></Field>
            <Field label={`FAQ ${index + 1} answer`}><Textarea maxLength={2000} rows={3} value={faq.answer} onChange={e => update('faqs', settings.faqs.map((item, i) => i === index ? { ...item, answer: e.target.value } : item))} /></Field>
            <Button size="sm" variant="ghost" onClick={() => update('faqs', settings.faqs.filter((_, i) => i !== index))}>Remove FAQ {index + 1}</Button>
          </div>)}</div>
          <Button className="mt-3" variant="secondary" disabled={settings.faqs.length >= 20 || !!busy} onClick={() => update('faqs', [...settings.faqs, { question: '', answer: '' }])}>Add store FAQ</Button>
        </Card>
      </div>
      <div className="space-y-5">
        <Card>
          <SectionTitle title="3. Try a customer conversation" right={<Badge tone="blue">AI preview</Badge>} />
          <p className="mb-4 text-sm text-muted">Test saved settings before enabling the widget. Answers use your configured AI model and synced store knowledge.</p>
          <div className="overflow-hidden rounded-xl border border-line">
            <div className="px-4 py-3 font-semibold text-white" style={{ backgroundColor: settings.accent }}>{settings.assistant_name}</div>
            <div ref={conversation} role="log" aria-label="Support preview conversation" className="max-h-[500px] min-h-[220px] space-y-3 overflow-y-auto bg-mist p-4">
              <div className="mr-6 rounded-xl bg-paper p-3 text-sm">{settings.welcome}</div>
              {turns.map((turn, index) => <div key={index} className={`rounded-xl p-3 text-sm ${turn.role === 'user' ? 'ml-6 bg-brand text-white' : 'mr-2 bg-paper'}`}>
                <p className="whitespace-pre-wrap">{turn.content}</p>
                {turn.reply && <ReplyDetails reply={turn.reply} />}
              </div>)}
              {busy === 'chat' && <p role="status" className="text-xs text-muted">Thinking…</p>}
            </div>
            <form className="flex gap-2 bg-paper p-3" onSubmit={event => { event.preventDefault(); send(message) }}>
              <Input aria-label="Preview customer message" maxLength={1000} value={message} onChange={e => setMessage(e.target.value)} placeholder="Ask about a product or return policy" disabled={!status?.ready || !!busy} />
              <Button type="submit" disabled={!status?.ready || !message.trim() || !!busy} busy={busy === 'chat'}>Send</Button>
            </form>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {['What is your return policy?', 'Help me find a product'].map(text => <button key={text} className="rounded-full border border-line px-3 py-1.5 text-xs hover:bg-mist disabled:opacity-40" disabled={!status?.ready || !!busy} onClick={() => send(text)}>{text}</button>)}
            <button className="px-2 text-xs text-muted underline" disabled={!!busy} onClick={() => setTurns([])}>Clear preview</button>
          </div>
        </Card>
        <Card>
          <SectionTitle title="4. Add to Shopify" right={<Badge tone={status?.settings.enabled && status.ready ? 'green' : 'neutral'}>{status?.settings.enabled && status.ready ? 'Chat enabled' : 'Chat paused'}</Badge>} />
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>Sync knowledge, save your support contact and enable storefront chat.</li>
            <li>In Shopify, open Online Store → Themes → Customize. Add a Custom Liquid section to your footer and paste this code. Save the theme.</li>
            <li>Open the store on desktop and mobile. Test a product question, a policy question and an order question.</li>
          </ol>
          <Textarea className="mt-4 font-mono text-xs" rows={4} aria-label="Shopify chat installation code" value={snippet || 'Installation code will appear when server configuration is available.'} readOnly />
          <Button className="mt-3" variant="secondary" disabled={!snippet} onClick={() => perform('copy', async () => { await navigator.clipboard.writeText(snippet); setNotice('Installation code copied.') })}>Copy installation code</Button>
          <p className="mt-3 text-xs text-muted">The widget floats above your storefront and works without customer login. This installation supports online store pages. Personal orders, refunds and cancellations go to your support contact.</p>
        </Card>
      </div>
    </div>
  </div>
}

function ReplyDetails({ reply }: { reply: SupportReply }) {
  return <>
    {reply.products.map(product => <a key={product.id} href={product.url} target="_blank" rel="noopener noreferrer" className="mt-3 flex gap-3 rounded-lg border border-line p-3 hover:bg-mist">
      {product.image && <img src={product.image} alt={product.title} className="h-14 w-14 rounded object-cover" loading="lazy" />}
      <div><p className="font-semibold text-brand">{product.title} ↗</p><p className="mt-1">{product.price !== product.max_price ? 'From ' : ''}{product.currency} {product.price}</p><p className="mt-1 text-[11px] text-muted">Confirm current price and availability on the product page.</p></div>
    </a>)}
    {reply.sources.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{reply.sources.map((source, index) => source.url ? <a key={index} href={source.url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand underline">{source.title} ↗</a> : <Badge key={index}>{source.title}</Badge>)}</div>}
    {reply.needs_human && reply.support_email && <a className="mt-3 inline-block text-brand underline" href={`mailto:${reply.support_email}`}>Contact store support</a>}
  </>
}
