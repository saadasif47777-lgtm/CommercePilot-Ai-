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
        body="Campaign plans use the same stored product, audience and budget as every other agent. Performance figures are illustrative assumptions — nothing is promised and nothing is published."
        actions={<Badge tone="red">Meta Marketing API — not connected</Badge>}
      />
      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {meta && (
        <Card className="mb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">Meta integration status</p>
              <p className="mt-0.5 text-xs text-muted">
                {meta.status === 'not_connected'
                  ? 'This prototype plans campaigns locally. Publishing requires authorized Meta Marketing API credentials and explicit human approval.'
                  : 'Credentials stored server-side (unverified). Publishing still requires explicit approval.'}
              </p>
            </div>
            <a href="/settings"><Badge tone="neutral">configure in Settings →</Badge></a>
          </div>
        </Card>
      )}

      {!project ? (
        <EmptyState title="No project selected" body="Select or create a project to plan a campaign." />
      ) : (
        <CampaignPlanner />
      )}
    </div>
  )
}
