import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SimilarCasesPanel from '../components/SimilarCasesPanel.vue'
import StepTelemetry from '../components/StepTelemetry.vue'
import type { CaseRagResult } from '../types/case'


const matched: CaseRagResult = {
  status: 'matched',
  retrieval_mode: 'local_bm25',
  min_similarity: 0.25,
  candidate_count: 3,
  highest_similarity: 0.8123,
  used_by_agents: ['TechnicalAgent', 'QuoteAgent'],
  impact_summary: ['参考实际工期上调最大工期'],
  matches: [{
    case: {
      id: 'case-id', project_number: 'CASE-QUIZ', project_type: 'web_app',
      core_features: ['题库', '答题'],
      client_budget: { min_amount: 8000, max_amount: 12000, currency: 'CNY' },
      suggested_quote: { min_amount: 10000, max_amount: 20000, currency: 'CNY' },
      final_deal_price: 15000,
      estimated_duration: { min_days: 10, max_days: 15, explanation: '估算' },
      actual_duration_days: 18,
      risks: [{ category: 'third_party_platform', severity: 'medium', reason: '平台限制' }],
      is_won: true,
      lessons_learned: '先确认题目格式', created_at: '2026-07-21T00:00:00Z',
    },
    similarity: 0.8123, text_score: 0.8, feature_score: 1,
    project_type_score: 1, risk_score: 0,
    matched_signals: ['project_type', 'feature:题库'], matched_terms: ['题库'],
    used_by_agents: ['TechnicalAgent', 'QuoteAgent'],
    impacts: [
      { agent: 'TechnicalAgent', project_number: 'CASE-QUIZ', summary: '参考实际工期上调最大工期' },
      { agent: 'QuoteAgent', project_number: 'CASE-QUIZ', summary: '规则报价未改变' },
    ],
  }],
}

describe('SimilarCasesPanel', () => {
  it('renders scores, used agents, matching signals, and impact', () => {
    const wrapper = mount(SimilarCasesPanel, { props: { result: matched } })
    expect(wrapper.text()).toContain('本地 BM25')
    expect(wrapper.text()).toContain('CASE-QUIZ')
    expect(wrapper.text()).toContain('81%')
    expect(wrapper.text()).toContain('TechnicalAgent')
    expect(wrapper.text()).toContain('feature:题库')
    expect(wrapper.text()).toContain('客户预算')
    expect(wrapper.text()).toContain('¥8,000')
    expect(wrapper.text()).toContain('third_party_platform')
    expect(wrapper.text()).toContain('规则报价未改变')
  })

  it.each([
    ['empty_library', '暂无历史案例'],
    ['no_match', '未找到达到阈值的相似案例'],
    ['failed', '历史案例检索失败'],
    ['not_run', '该记录未执行案例检索'],
  ] as const)('renders %s as a non-blocking state', (status, message) => {
    const wrapper = mount(SimilarCasesPanel, {
      props: { result: { ...matched, status, matches: [] } },
    })
    expect(wrapper.text()).toContain(message)
  })

  it('shows local retrieval telemetry independently from analysis mode', () => {
    const wrapper = mount(StepTelemetry, {
      props: {
        totalDurationMs: 5,
        steps: [{
          step: 'case_retrieval', execution_mode: 'local_retrieval',
          duration_ms: 1.2, fallback_used: false, status: 'matched', warning: null, error: null,
        }],
      },
    })
    expect(wrapper.text()).toContain('相似案例检索')
    expect(wrapper.text()).toContain('本地 BM25')
    expect(wrapper.text()).toContain('matched')
  })
})
