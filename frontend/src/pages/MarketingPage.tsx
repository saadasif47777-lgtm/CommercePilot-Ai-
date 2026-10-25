// Agent C — Marketing Studio.
//
// The page itself is thin: it shows the Meta integration status (always honest
// about not being connected) and hands the actual planning UI to
// CampaignPlanner, which owns budget validation, creatives and the simulation.

import { useProject } from '../state/ProjectContext'
import { Badge, Card, EmptyState, ErrorBanner, PageHeader } from '../components/ui'
import { CampaignPlanner } from '../components/CampaignPlanner'

export function MarketingPage() {
  const { project, error, clearError, integrations } = useProject()
  const meta = integrations?.meta

  return (
    <div>
      <PageHeader
        eyebrow="Agent C"
        title="Marketing Studio"
        body="Campaign plans use the same stored product, audience and budget as every other agent. Create AI campaign copy and validate your budget. Add measured performance to evaluate results."
        actions={<Badge tone={meta?.status === 'connected' ? 'green' : 'neutral'}>Meta: {meta?.status === 'connected' ? 'verified' : meta?.status === 'configured_unverified' ? 'verify connection' : 'not connected'}</Badge>}
      />
      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {/* Connection status banner: no campaign is ever published from here. */}
      {meta && (
        <Card className="mb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">Meta integration status</p>
              <p className="mt-0.5 text-xs text-muted">
                {meta.status === 'not_connected'
                  ? 'Connect Meta in Connections & AI to verify your account and read measured performance.'
                  : 'Your account is configured. Verify it in Connections & AI and read performance reports there.'}
              </p>
            </div>
            <a href="/settings"><Badge tone="neutral">configure in Settings →</Badge></a>
          </div>
        </Card>
      )}

      {!project?.selected_product ? (
        <EmptyState title="Select a product to plan your campaign" body="Set up your business, then select or import a product in Products." />
      ) : (
        <CampaignPlanner key={project.id} />
      )}
    </div>
  )
}
