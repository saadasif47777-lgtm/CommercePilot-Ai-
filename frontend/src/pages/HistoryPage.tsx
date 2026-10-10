import { useState } from 'react'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Modal, PageHeader, SectionTitle } from '../components/ui'
import { ExecutionTimeline } from '../components/WorkflowPanel'

const STEP_LABELS: [string, string][] = [
  ['brief', 'Brief'], ['research', 'Research'], ['select', 'Product'],
  ['store', 'Store'], ['campaign', 'Campaign'], ['analyze', 'Analysis'], ['report', 'Report'],
]

export function HistoryPage() {
  const { projects, project, selectProject, removeProject, createProject, error, clearError, run } = useProject()
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null)

  const openProject = (id: string) => selectProject(id)

  const duplicate = (id: string) => {
    const source = projects.find((p) => p.id === id)
    run('duplicate', async () => {
      await createProject({ name: `${source?.name ?? 'Project'} (copy)` })
    })
  }

  return (
    <div>
      <PageHeader
        title="Project History"
        body="All projects persist in the local SQLite store and survive restarts. Open one to continue exactly where you left off."
        actions={
          <Button onClick={() => run('new-project', async () => { await createProject({ example: true }) })}>
            New example project
          </Button>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {projects.length === 0 ? (
        <EmptyState title="No projects yet" body="Create an example project to see the full 8-step workflow in action." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {projects.map((p) => (
            <Card key={p.id} hover>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-display text-base font-semibold text-ink">{p.name}</h3>
                    {p.is_example && <Badge tone="amber">example</Badge>}
                    {p.id === project?.id && <Badge tone="green">open</Badge>}
                  </div>
                  <p className="mt-0.5 text-xs text-muted">
                    {p.brief?.business_name} · {p.brief?.currency} {p.brief?.budget?.toLocaleString()} · updated {new Date(p.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <Button size="sm" variant="secondary" onClick={() => openProject(p.id)}>Open</Button>
                  <Button size="sm" variant="ghost" onClick={() => duplicate(p.id)} title="Create an empty copy">Duplicate</Button>
                  <Button size="sm" variant="danger" onClick={() => setConfirmDelete({ id: p.id, name: p.name })}>Delete</Button>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {STEP_LABELS.map(([id, label]) => {
                  const status = p.steps[id]
                  if (!status) return null
                  const tone = status === 'success' ? 'green' : status === 'error' ? 'red' : status === 'running' ? 'amber' : 'neutral'
                  return <Badge key={id} tone={tone}>{label}</Badge>
                })}
              </div>

              <p className="mt-2 text-xs text-muted">
                Product: {p.selected_product ?? '—'} · Campaign: {p.has_campaign ? 'draft saved' : '—'} · Analysis: {p.has_analysis ? 'computed' : '—'}
              </p>
            </Card>
          ))}
        </div>
      )}

      {project && (
        <div className="mt-8">
          <Card>
            <SectionTitle title={`Agent executions — ${project.name}`} subtitle="Full audit trail: inputs, outputs, warnings and errors per run." />
            <ExecutionTimeline limit={20} />
          </Card>
        </div>
      )}

      <Modal open={!!confirmDelete} onClose={() => setConfirmDelete(null)} title="Delete project?">
        <p className="text-sm text-muted">
          “{confirmDelete?.name}” and its research, storefront, campaign and analysis will be permanently removed from the local database.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmDelete(null)}>Cancel</Button>
          <Button
            variant="danger"
            onClick={() => {
              if (confirmDelete) run('delete', async () => { await removeProject(confirmDelete.id) })
              setConfirmDelete(null)
            }}
          >
            Delete project
          </Button>
        </div>
      </Modal>
    </div>
  )
}
