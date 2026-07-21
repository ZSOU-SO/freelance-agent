import type {
  HistoricalCase,
  HistoricalCaseListResponse,
  HistoricalCasePayload,
} from '../types/case'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      const detail = body.detail
      message = typeof detail === 'string' ? detail : detail?.message || message
    } catch {
      // Keep the status-based fallback.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function listCases(params: {
  page?: number
  pageSize?: number
  projectType?: string
  isWon?: boolean
  q?: string
} = {}): Promise<HistoricalCaseListResponse> {
  const query = new URLSearchParams({
    page: String(params.page || 1),
    page_size: String(params.pageSize || 20),
  })
  if (params.projectType) query.set('project_type', params.projectType)
  if (params.isWon !== undefined) query.set('is_won', String(params.isWon))
  if (params.q) query.set('q', params.q)
  return request(`/cases?${query}`)
}

export function getCase(id: string): Promise<HistoricalCase> {
  return request(`/cases/${encodeURIComponent(id)}`)
}

export function createCase(payload: HistoricalCasePayload): Promise<HistoricalCase> {
  return request('/cases', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateCase(id: string, payload: HistoricalCasePayload): Promise<HistoricalCase> {
  return request(`/cases/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteCase(id: string): Promise<void> {
  return request(`/cases/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

