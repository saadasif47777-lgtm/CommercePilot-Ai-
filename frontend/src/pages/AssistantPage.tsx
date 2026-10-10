import { useProject } from '../state/ProjectContext'
import { AssistantChat } from '../components/Assistant'
import { Card, PageHeader, SectionTitle } from '../components/ui'
import { ExecutionTimeline, WorkflowSteps } from '../components/WorkflowPanel'

export function AssistantPage() {
  const { project } = useProject()
  return (
    <div>
      <PageHeader
        eyebrow="Agent workspace"
        title="AI Commerce Assistant"
        body="One conversational entry point to the four agents. Every reply comes from a real backend action on the shared project context — nothing here is simulated."
      />
      <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]">
        <AssistantChat />
        <div className="space-y-5">
          {project && (
            <Card>
              <SectionTitle title="Project context" subtitle={project.name} />
              <WorkflowSteps compact />
            </Card>
          )}
          <Card>
            <SectionTitle title="Recent agent runs" />
            <ExecutionTimeline limit={6} />
          </Card>
        </div>
      </div>
    </div>
  )
}
