// Typed API client for the CommercePilot AI backend.
//
// The base URL comes from the VITE_API_BASE_URL environment variable:
//   - Local development: leave it unset (empty). Requests go to same-origin
//     /api and the Vite dev server proxies them to FastAPI on 127.0.0.1:8000.
//   - Production: set VITE_API_BASE_URL to the deployed backend origin
//     (e.g. https://commercepilot-ai.onrender.com) with NO trailing slash.
// The browser never hard-codes localhost; the only localhost reference in the
// project is the Vite dev proxy target, which is server-side dev config.

import type {
  AnalysisResult, AssistantReply, ScenarioInput, BusinessBrief, CampaignPlan, IntegrationStatus,
  Product, Project, ProjectSummary, ResearchRequest, ResearchResult, StoreDesign,
  StoreEditResponse, WebsiteSpec, WorkflowResult,
} from '../types'

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

// Deployed backend origin, stripped of trailing slashes. Empty string means
// "same-origin" (development proxy).
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'content-type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError(0, API_BASE
      ? `Backend unreachable at ${API_BASE}. Is the API service running?`
      : 'Backend unreachable. Is the API server running on port 8000?')
  }
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('text/html')) {
    // An HTML response for an /api path means the base URL is wrong (the
    // frontend host answered instead of the backend).
    throw new ApiError(res.status,
      `API base URL looks wrong: ${API_BASE || '(empty - same-origin)'} returned an HTML page for ${path}. ` +
      'Set VITE_API_BASE_URL to the deployed backend origin.')
  }
  if (!res.ok) {
    let detail: unknown = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? body
    } catch { /* keep default */ }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => request<{ status: string; llm_mode: string; projects: number }>('/api/health'),

  products: (category?: string) =>
    request<{ is_sample_data: boolean; disclaimer: string; count: number; products: Product[] }>(
      `/api/products${category ? `?category=${encodeURIComponent(category)}` : ''}`,
    ),

  research: (req: ResearchRequest) => post<ResearchResult>('/api/research', req),

  listProjects: () => request<{ count: number; projects: ProjectSummary[] }>('/api/projects'),
  createProject: (payload: { name?: string; example?: boolean; brief?: BusinessBrief }) =>
    post<Project>('/api/projects', payload),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  deleteProject: (id: string) => request<{ deleted: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
  updateBrief: (id: string, brief: BusinessBrief) => post<Project>(`/api/projects/${id}/brief`, { brief }),

  selectProduct: (id: string, productId: string) =>
    post<Project>(`/api/projects/${id}/select-product`, { product_id: productId }),
  resetProduct: (id: string) => post<Project>(`/api/projects/${id}/reset-product`),

  generateStore: (id: string, payload?: { design?: Partial<StoreDesign>; extra_instructions?: string }) =>
    post<WebsiteSpec>(`/api/projects/${id}/generate-store`, payload ?? {}),
  editStore: (id: string, prompt: string) =>
    post<StoreEditResponse>(`/api/projects/${id}/edit-store`, { prompt }),
  resetStore: (id: string) => post<{ reset: boolean; spec?: WebsiteSpec }>(`/api/projects/${id}/reset-store`),

  generateCampaign: (id: string, payload?: { objective?: string; budget?: number; duration_days?: number }) =>
    post<CampaignPlan>(`/api/projects/${id}/generate-campaign`, payload ?? {}),
  updateCampaign: (
    id: string,
    payload: { budget?: number; allocations?: { label: string; amount: number; purpose?: string }[]; status?: string },
  ) =>
    request<CampaignPlan>(`/api/projects/${id}/campaign`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  simulateCampaign: (id: string) => post<NonNullable<CampaignPlan['simulation']>>(`/api/projects/${id}/campaign/simulate`),

  analyze: (
    id: string,
    payload?: {
      actuals?: { ad_spend?: number; clicks?: number; conversions?: number; customers?: number; revenue?: number }
      best?: ScenarioInput
      base?: ScenarioInput
      conservative?: ScenarioInput
    },
  ) => post<AnalysisResult>(`/api/projects/${id}/analyze`, payload ?? {}),

  runWorkflow: (id: string, payload?: { auto_select?: boolean; mode?: 'sample' | 'live' | 'both'; force?: boolean }) =>
    post<WorkflowResult>(`/api/projects/${id}/run-workflow`, payload ?? {}),
  report: (id: string, refresh = false) =>
    request<Project['report']>(`/api/projects/${id}/report${refresh ? '?refresh=true' : ''}`),

  assistant: (id: string, message: string) => post<AssistantReply>(`/api/projects/${id}/assistant`, { message }),

  integrations: () => request<IntegrationStatus>('/api/integrations/status'),
  saveMetaCredentials: (payload: { access_token: string; ad_account_id: string; app_id?: string; app_secret?: string }) =>
    post<{ saved: boolean; verified: boolean; detail: string; status: string }>('/api/integrations/meta/credentials', payload),
  verifyMeta: () => post<{ verified: boolean; detail: string }>('/api/integrations/meta/verify'),
  saveShopifyCredentials: (payload: { shop_domain: string; admin_token: string }) =>
    post<{ saved: boolean; verified: boolean; detail: string }>('/api/integrations/shopify/credentials', payload),
  shopifySync: (limit = 10) => post<{ ok: boolean; detail?: string; count?: number; products?: unknown[] }>('/api/integrations/shopify/sync'),

  storeExportUrl: (id: string) => `${API_BASE}/api/projects/${id}/store/export`,
}

export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail
    if (typeof d === 'string') return d
    if (d && typeof d === 'object' && 'message' in (d as Record<string, unknown>)) {
      return String((d as Record<string, unknown>).message)
    }
    if (Array.isArray(d)) {
      return d
        .map((i) => {
          const loc = (i as { loc?: string[] }).loc
          const msg = (i as { msg?: string }).msg
          return `${loc?.join('.') ?? 'input'}: ${msg ?? 'invalid'}`
        })
        .join('; ')
    }
    return `Request failed (HTTP ${err.status})`
  }
  return err instanceof Error ? err.message : 'Unexpected error'
}

export type { ScenarioInput } from '../types'
