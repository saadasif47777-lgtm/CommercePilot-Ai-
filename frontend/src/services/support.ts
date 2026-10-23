import { request } from './api'

export interface SupportSettings {
  enabled: boolean
  assistant_name: string
  welcome: string
  accent: string
  support_email: string
  allowed_origins: string[]
  faqs: { question: string; answer: string }[]
}
export interface SupportStatus {
  widget_id: string
  settings: SupportSettings
  ready: boolean
  reason: string
  shop?: { name: string; domain: string; currency: string; origins: string[] } | null
  synced_at?: string | null
  knowledge_hours: number
  daily_message_limit: number
  counts: { product?: number; policy?: number }
  allowed_origins: string[]
  pending?: { sync_id: string; pages: number; scanned: number } | null
}
export interface SupportReply {
  answer: string
  products: { id: string; title: string; url: string; price: string; max_price: string; currency: string; image: string }[]
  sources: { title: string; url: string; kind: string }[]
  support_email: string
  synced_at: string
  needs_human: boolean
}
export interface SyncProgress { sync_id: string; complete: boolean; pages: number; scanned: number; products: number; policies: number }
export interface ChatTurn { role: 'user' | 'assistant'; content: string }
const post = <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const supportApi = {
  status: () => request<SupportStatus>('/api/support/status'),
  save: (settings: SupportSettings) => request<SupportStatus>('/api/support/settings', { method: 'PUT', body: JSON.stringify(settings) }),
  startSync: () => post<SyncProgress>('/api/support/sync/start'),
  nextPage: (syncId: string) => post<SyncProgress>('/api/support/sync/next', { sync_id: syncId }),
  preview: (message: string, history: ChatTurn[]) => post<SupportReply>('/api/support/preview', { message, history: history.slice(-8) }),
  install: () => request<{ snippet: string; script_url: string; widget_id: string }>('/api/support/install'),
}
