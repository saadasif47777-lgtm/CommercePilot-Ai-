// Conversational entry point to the four agents.
//
// The chat lives in AssistantChat; this page adds the current project context and
// the most recent agent executions so replies can be checked against real runs.

import { AssistantChat } from '../components/Assistant'
import { PageHeader } from '../components/ui'

export function AssistantPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Think it through. Plan your next move."
        title="AI Commerce Assistant"
        body="Get clear answers about CommercePilot, explore the pros and cons of your idea, and build a practical budget around your niche, location and customers."
      />
      <AssistantChat />
    </div>
  )
}
