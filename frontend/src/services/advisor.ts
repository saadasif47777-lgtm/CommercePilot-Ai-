import { ApiError, request } from './api'

export interface AdvisorProfile {
  budget: number | null; budget_scope: 'business' | 'advertising' | null; currency: string | null
  niche: string | null; location: string | null; audience: string | null
  business_model: 'physical' | 'dropshipping' | 'digital' | 'service' | null
  timeframe_days: number | null; fixed_costs: number | null; selling_price: number | null
  product_cost: number | null; other_costs_per_order: number | null
  assumed_cpc: number | null; assumed_conversion_pct: number | null
  store_ready: boolean | null; tracking_ready: boolean | null
}
export interface BudgetPlan {
  currency: string | null; scope: string | null; total_budget: number | null
  status: 'needs_details' | 'provisional' | 'hold_paid_ads' | 'overcommitted'
  allocations: { label: string; amount: number; percent: number | null }[]
  assumptions: string[]; warnings: string[]; missing_information: string[]
  ad_test_budget: number | null; daily_ad_test_average: number | null; timeframe_days: number | null; shortfall?: number
  unit_economics: { gross_profit_per_order: number | null; contribution_per_order: number | null; break_even_cpa: number | null; break_even_roas: number | null; fixed_cost_break_even_orders: number | null }
  scenario: { label: string; clicks: number; expected_orders: number; revenue: number | null; contribution_after_ads: number | null } | null
}
export interface PendingAction { action: 'research' | 'store' | 'campaign' | 'analyze' | 'report'; label: string; description: string; project_id: string; revision: number }
export interface AdvisorReply {
  reply: string; strengths: string[]; risks: { factor: string; explanation: string; mitigation: string }[]
  next_steps: { title: string; explanation: string; route: string }[]; questions: string[]
  budget: BudgetPlan; references: { title: string; url: string }[]; pending_action: PendingAction | null
  action_completed?: boolean
}
export interface AdvisorSession {
  session_token: string; messages: { role: 'user' | 'assistant'; text: string; response?: AdvisorReply }[]
  profile: AdvisorProfile; budget: BudgetPlan; pending_action: PendingAction | null; welcome: string
  guides: { title: string; route: string; description: string }[]
}
const post = <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })
const pendingSessions = new Map<string, Promise<AdvisorSession>>()
export const advisor = {
  storageKey: (projectId: string | null) => `commercepilot.advisor.${projectId || 'welcome'}`,
  session: (projectId: string | null) => {
    const key = advisor.storageKey(projectId)
    const pending = pendingSessions.get(key)
    if (pending) return pending
    const operation = (async () => {
      let token: string | null = null
      try { token = sessionStorage.getItem(key) } catch { /* storage is optional */ }
      let result: AdvisorSession
      try { result = await post<AdvisorSession>('/api/advisor/session', { project_id: projectId, session_token: token }) }
      catch (error) {
        if (!(error instanceof ApiError) || error.status !== 410) throw error
        result = await post<AdvisorSession>('/api/advisor/session', { project_id: projectId })
      }
      try { sessionStorage.setItem(key, result.session_token) } catch { /* storage is optional */ }
      return result
    })().finally(() => pendingSessions.delete(key))
    pendingSessions.set(key, operation)
    return operation
  },
  chat: (token: string, message: string, updates?: Partial<AdvisorProfile>, action?: PendingAction['action']) =>
    post<AdvisorSession>('/api/advisor/chat', { session_token: token, message, ...(updates ? { profile_updates: updates } : {}), ...(action ? { confirmed_action: action } : {}) }),
}
