import type { BudgetRange, DurationEstimate, RiskCategory, RiskItem } from './analysis'

export type CaseRagStatus = 'not_run' | 'matched' | 'empty_library' | 'no_match' | 'failed'

export interface HistoricalCasePayload {
  project_number: string
  project_type: string
  original_requirement: string
  core_features: string[]
  client_budget: BudgetRange | null
  suggested_quote: BudgetRange
  final_deal_price: number | null
  estimated_duration: DurationEstimate
  actual_duration_days: number | null
  risks: RiskItem[]
  is_won: boolean
  lessons_learned: string
}

export interface HistoricalCase extends HistoricalCasePayload {
  id: string
  created_at: string
  updated_at: string
}

export interface HistoricalCaseListResponse {
  items: HistoricalCase[]
  total: number
  limit: number
  offset: number
  warnings: string[]
}

export interface AgentCaseImpact {
  agent: 'TechnicalAgent' | 'QuoteAgent'
  project_number: string
  summary: string
}

export interface SimilarCaseMatch {
  case: Omit<HistoricalCase, 'original_requirement' | 'updated_at'>
  similarity: number
  text_score: number
  feature_score: number
  project_type_score: number
  risk_score: number
  matched_signals: string[]
  matched_terms: string[]
  used_by_agents: string[]
  impacts: AgentCaseImpact[]
}

export interface CaseRagResult {
  status: CaseRagStatus
  retrieval_mode: string
  min_similarity: number
  matches: SimilarCaseMatch[]
  used_by_agents: string[]
  impact_summary: string[]
  candidate_count: number
  highest_similarity?: number | null
  warning?: string | null
  error?: string | null
}

export const riskCategories: RiskCategory[] = [
  'payment',
  'hardware',
  'third_party_platform',
  'urgent_delivery',
]

