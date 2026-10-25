// Project History: every saved project, its step status and the audit trail.
// Deleting is confirmed in a modal because it removes the project and all of
// its research, storefront, campaign and analysis from the database.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '../state/ProjectContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Modal, PageHeader, SectionTitle } from '../components/ui'
import { ExecutionTimeline } from '../components/WorkflowPanel'

// Human-readable labels for the workflow step ids stored on each project.
const STEP_LABELS: [string, string][] = [
  ['brief', 'Brief'], ['research', 'Research'], ['select', 'Product'],
  ['store', 'Store'], ['campaign', 'Campaign'], ['analyze', 'Analysis'], ['report', 'Report'],
]

export function HistoryPage() {
  const { projects, project, selectProject, removeProject, createProject, createBlankProject, busy, error, clearError, run } = useProject()
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null)
  const navigate = useNavigate()

  const openProject = (id: string) => selectProject(id)

  // Same real-project flow as the top bar: blank project, then its brief.
  const addProject = () => navigate('/business?new=1')

  // "Duplicate" creates a fresh project with a similar name; it intentionally
  // does not copy research or designs, so no stale results are carried over.
  const duplicate = (id: string) => {
    const source = projects.find((p) => p.id === id)
    run('duplicate', async () => {
      if (!source) return
      await createProject({ name: `${source.name} (copy)`, brief: { ...source.brief, business_name: `${source.brief.business_name} (copy)` } })
    })
  }

  return (
    <div>
      <PageHeader
        title="Project History"
        body="Your saved projects and their results are kept in your workspace database. Open one to continue exactly where you left off."
        actions={
          <Button busy={busy === 'new-project'} onClick={addProject}>
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
            Add New Project
          </Button>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          body="Add a new project and enter its business brief to start the 8-step workflow."
          action={<Button onClick={addProject} busy={busy === 'new-project'}>Add New Project</Button>}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {projects.map((p) => (
            <Card key={p.id} hover>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1 basis-[220px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-display text-base font-semibold text-ink">{p.name}</h3>
                    {p.is_example && <Badge tone="amber">example</Badge>}
                    {p.id === project?.id && <Badge tone="green">open</Badge>}
                  </div>
                  <p className="mt-0.5 text-xs text-muted">
                    {p.brief?.business_name} · {p.brief?.currency} {p.brief?.budget?.toLocaleString()} · updated {new Date(p.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex max-w-full flex-wrap gap-1.5">
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
