import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AnalysisResult from '../components/AnalysisResult.vue'
import type { AnalysisResponse } from '../types/analysis'


const localResult: AnalysisResponse = {
  id: 'analysis-1',
  created_at: '2026-07-20T08:00:00Z',
  requirement_text: '开发商城',
  analysis_mode: 'local_fallback',
  fallback_occurred: false,
  requirement: {
    project_type: 'ecommerce',
    features: ['payment'],
    client_budget: null,
    desired_deadline: null,
    risk_signals: ['third_party_platform'],
    missing_information: ['请确认预算'],
  },
  technical_solution: {
    frontend: ['Vue 3'],
    backend: ['FastAPI'],
    database: ['SQLite'],
    deployment: ['Docker'],
    integrations: ['支付平台 API'],
    architecture: '前后端分离',
    deliverables: ['源代码'],
  },
  quote: {
    pricing: {
      min_amount: 24000,
      max_amount: 42000,
      currency: 'CNY',
      calculation_items: [],
    },
    explanation: '依据本地规则',
    assumptions: ['不含税'],
    payment_terms: '40/40/20',
  },
  estimated_duration: {
    min_days: 20,
    max_days: 35,
    explanation: '标准工期',
    raw_text: null,
  },
  risks: [{
    category: 'third_party_platform',
    severity: 'medium',
    reason: '依赖平台审核',
    evidence: '微信支付',
  }],
  recommendation: {
    should_accept: true,
    verdict: 'conditional',
    reasons: ['先确认平台资质'],
  },
  follow_up_questions: ['请确认预算'],
  client_reply: '您好，项目可以承接。',
  telemetry: {
    total_duration_ms: 8.2,
    steps: [
      {
        step: 'requirement',
        execution_mode: 'local_fallback',
        duration_ms: 1.2,
        fallback_used: false,
        error: null,
      },
    ],
  },
}


describe('AnalysisResult', () => {
  it('shows the required local fallback notice', () => {
    const wrapper = mount(AnalysisResult, { props: { analysis: localResult } })
    expect(wrapper.text()).toContain('本地规则分析，未调用大模型')
  })

  it('renders quote, duration, risks, and reply', () => {
    const wrapper = mount(AnalysisResult, { props: { analysis: localResult } })
    expect(wrapper.text()).toContain('¥24,000')
    expect(wrapper.text()).toContain('20–35 个工作日')
    expect(wrapper.text()).toContain('依赖平台审核')
    expect(wrapper.text()).toContain('您好，项目可以承接。')
  })

  it('shows a partial fallback warning for an agents run', () => {
    const wrapper = mount(AnalysisResult, {
      props: {
        analysis: { ...localResult, analysis_mode: 'agents', fallback_occurred: true },
      },
    })
    expect(wrapper.text()).toContain('部分步骤已自动降级')
  })

  it('keeps the normal result visible when case retrieval failed', () => {
    const wrapper = mount(AnalysisResult, {
      props: {
        analysis: {
          ...localResult,
          case_rag: {
            status: 'failed', retrieval_mode: 'local_bm25', min_similarity: 0.25,
            matches: [], used_by_agents: [], impact_summary: [], candidate_count: 0,
            error: '检索失败',
          },
        },
      },
    })
    expect(wrapper.text()).toContain('历史案例检索失败')
    expect(wrapper.text()).toContain('¥24,000')
    expect(wrapper.text()).toContain('您好，项目可以承接。')
  })

  it('handles a phase one record without case_rag', () => {
    const wrapper = mount(AnalysisResult, { props: { analysis: localResult } })
    expect(wrapper.text()).toContain('该记录未执行案例检索')
  })
})
