// Agent B — Store Architect.
//
// Generates a structured storefront specification and renders it as a live,
// interactive preview (desktop or mobile width). Section toggles and the design
// panel edit the stored spec through the API; the exported HTML is produced from
// the same spec, so preview and download can never drift apart.

import { useState } from 'react'
import { api } from '../services/api'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, PageHeader, SectionTitle } from '../components/ui'
import { StorefrontPreview } from '../components/StorefrontPreview'
import { DesignPanel } from '../components/DesignPanel'

export function StoreArchitectPage() {
  const { project, run, busy, error, refreshProject, clearError } = useProject()
  const [device, setDevice] = useState<'desktop' | 'mobile'>('desktop')
  const spec = project?.store_spec?.generation_mode === 'llm' && !project.store_spec.product?.is_sample_data ? project.store_spec : null

  const generate = () =>
    run('generate-store', async () => {
      if (!project) return
      await api.generateStore(project.id)
      await refreshProject()
    })

  const reset = () =>
    run('reset-store', async () => {
      if (!project) return
      await api.resetStore(project.id)
      await refreshProject()
    })

  // Section visibility is changed through the same natural-language endpoint
  // the design panel uses, keeping one code path for spec mutations.
  const sectionToggle = (type: string) =>
    run('toggle-section', async () => {
      if (!project || !spec) return
      const prompt = spec.sections.find((s) => s.type === type)?.visible
        ? `hide ${type.replace('_', ' ')}`
        : `show ${type.replace('_', ' ')}`
      await api.editStore(project.id, prompt)
      await refreshProject()
    })

  return (
    <div>
      <PageHeader
        eyebrow="Agent B"
        title="Store Architect"
        body="A structured design specification is generated from your brief and selected product, then rendered as a genuinely interactive storefront. Natural-language edits update the spec — arbitrary generated code is never executed."
        actions={
          <>
            {/* Export is a plain download link to the backend renderer. */}
            {spec && (
              <Button variant="secondary" onClick={() => run('export-store', () => api.downloadStore(project!.id, 'storefront.html'))}>Export HTML</Button>
            )}
            {spec && <Button variant="secondary" onClick={reset}>Reset design</Button>}
            <Button busy={busy === 'generate-store'} onClick={generate} disabled={!project?.selected_product}>
              {spec ? 'Regenerate design' : 'Generate storefront'}
            </Button>
          </>
        }
      />

      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {!project?.selected_product ? (
        <EmptyState
          title="Select a product first"
          body="The Store Architect builds the storefront around the product stored in the project. Pick one in Product Hunter (or run the workflow)."
        />
      ) : !spec ? (
        <EmptyState
          title="No storefront yet"
          body={`Generate a storefront for “${project.selected_product.title}” — it will use your product information and AI copy in a responsive design.`}
          action={<Button busy={busy === 'generate-store'} onClick={generate}>Generate storefront</Button>}
        />
      ) : (
        /* Preview on the left, editing controls on the right. */
        <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
          <div>
            <Card padded={false} className="overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
                <div className="flex items-center gap-2">
                  <Badge tone="green" pulse>live preview</Badge>
                  <span className="text-xs text-muted">
                    {spec.brand_name} · {spec.design.hero_style} hero · {spec.design.card_style} cards · {spec.generation_mode === 'llm' ? 'LLM copy' : 'template copy'}
                  </span>
                </div>
                <div className="flex rounded-lg border border-line p-0.5">
                  {(['desktop', 'mobile'] as const).map((dev) => (
                    <button
                      key={dev}
                      onClick={() => setDevice(dev)}
                      className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${device === dev ? 'bg-brand text-white' : 'text-muted hover:text-ink'}`}
                    >
                      {dev === 'desktop' ? 'Desktop' : 'Mobile'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="bg-mist p-4">
                <div className="overflow-hidden rounded-lg border border-line bg-paper">
                  <StorefrontPreview spec={spec} device={device} />
                </div>
                <p className="mt-2 text-[11px] text-muted">
                  Interactive: try the catalog search, add items to the cart and change quantities. Checkout must be configured in your commerce platform before accepting orders.
                </p>
              </div>
            </Card>

            <div className="mt-4">
              <SectionTitle title="Sections" subtitle="Toggle sections on or off — changes are stored in the specification." />
              <div className="flex flex-wrap gap-2">
                {spec.sections.map((s) => (
                  <button
                    key={s.type}
                    onClick={() => sectionToggle(s.type)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                      s.visible ? 'border-brand/40 bg-brand/5 text-brand' : 'border-line bg-paper text-muted'
                    }`}
                  >
                    {s.type.replace('_', ' ')} {s.visible ? '✓' : '· hidden'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <DesignPanel />
          </div>
        </div>
      )}
    </div>
  )
}
