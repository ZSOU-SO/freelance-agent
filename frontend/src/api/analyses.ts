import type { AnalysisListResponse, AnalysisResponse } from '../types/analysis'

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
      message = body.detail || message
    } catch {
      // Keep the status-based message for non-JSON failures.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function createAnalysis(requirementText: string): Promise<AnalysisResponse> {
  return request('/analyses', {
    method: 'POST',
    body: JSON.stringify({ requirement_text: requirementText }),
  })
}

export function listAnalyses(limit = 20, offset = 0): Promise<AnalysisListResponse> {
  return request(`/analyses?limit=${limit}&offset=${offset}`)
}

