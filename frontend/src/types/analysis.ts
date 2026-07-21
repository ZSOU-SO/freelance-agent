import type { AgentCaseImpact, CaseRagResult } from './case'

export type AnalysisMode = 'agents' | 'local_fallback'
export type ExecutionMode = 'agent' | 'local_fallback' | 'local_retrieval' | 'embedding_retrieval'
export type RiskCategory =
  | 'payment'
  | 'hardware'
  | 'third_party_platform'
  | 'urgent_delivery'
export type RiskSeverity = 'low' | 'medium' | 'high'
export type AcceptanceVerdict = 'accept' | 'conditional' | 'reject'

export interface BudgetRange {
  min_amount: number
  max_amount: number
  currency: string
  raw_text?: string | null
}

export interface DurationEstimate {
  min_days: number
  max_days: number
  explanation: string
  raw_text?: string | null
}

export interface RiskItem {
  category: RiskCategory
  severity: RiskSeverity
  reason: string
  evidence?: string | null
}

export interface RequirementResult {
  project_type: string
  features: string[]
  client_budget?: BudgetRange | null
  desired_deadline?: DurationEstimate | null
  risk_signals: string[]
  missing_information: string[]
}

export interface TechnicalSolution {
  frontend: string[]
  backend: string[]
  database: string[]
  deployment: string[]
  integrations: string[]
  architecture: string
  deliverables: string[]
}

export interface CalculationItem {
  code: string
  label: string
  kind: 'base' | 'addition' | 'multiplier'
  min_amount: number
  max_amount: number
  multiplier?: number | null
}

export interface PricingCalculation {
  min_amount: number
  max_amount: number
  currency: 'CNY'
  calculation_items: CalculationItem[]
}

export interface QuoteResult {
  pricing: PricingCalculation
  explanation: string
  assumptions: string[]
  payment_terms: string
  case_impacts?: AgentCaseImpact[]
}

export interface Recommendation {
  should_accept: boolean
  verdict: AcceptanceVerdict
  reasons: string[]
}

export interface StepTelemetry {
  step: string
  execution_mode: ExecutionMode
  duration_ms: number
  fallback_used: boolean
  error?: string | null
  status?: string | null
  warning?: string | null
}

export interface AnalysisResponse {
  id: string
  created_at: string
  requirement_text: string
  analysis_mode: AnalysisMode
  fallback_occurred: boolean
  requirement: RequirementResult
  technical_solution: TechnicalSolution
  quote: QuoteResult
  estimated_duration: DurationEstimate
  risks: RiskItem[]
  recommendation: Recommendation
  follow_up_questions: string[]
  client_reply: string
  telemetry: {
    total_duration_ms: number
    steps: StepTelemetry[]
  }
  case_rag?: CaseRagResult
}

export interface AnalysisListResponse {
  items: AnalysisResponse[]
  total: number
  limit: number
  offset: number
  warnings?: string[]
}
