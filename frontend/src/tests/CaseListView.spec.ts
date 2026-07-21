import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseListView from '../views/CaseListView.vue'


const listCases = vi.fn()
const deleteCase = vi.fn()
const getCase = vi.fn()

vi.mock('../api/cases', () => ({
  listCases: (...args: unknown[]) => listCases(...args),
  deleteCase: (...args: unknown[]) => deleteCase(...args),
  getCase: (...args: unknown[]) => getCase(...args),
}))

const record = {
  id: 'case-id',
  project_number: 'CASE-001',
  project_type: 'web_app',
  original_requirement: '在线刷题网站',
  core_features: ['题库', '答题'],
  client_budget: null,
  suggested_quote: { min_amount: 10000, max_amount: 20000, currency: 'CNY' },
  final_deal_price: 15000,
  estimated_duration: { min_days: 10, max_days: 15, explanation: '估算' },
  actual_duration_days: 16,
  risks: [],
  is_won: true,
  lessons_learned: '先确认题目格式',
  created_at: '2026-07-21T00:00:00Z',
  updated_at: '2026-07-21T00:00:00Z',
}

function mountView() {
  return mount(CaseListView, {
    global: {
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('CaseListView', () => {
  beforeEach(() => {
    listCases.mockReset()
    deleteCase.mockReset()
    listCases.mockResolvedValue({
      items: [record], total: 1, limit: 20, offset: 0, warnings: [],
    })
  })

  it('renders historical cases with commercial and delivery fields', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('CASE-001')
    expect(wrapper.text()).toContain('web_app')
    expect(wrapper.text()).toContain('¥10,000–¥20,000')
    expect(wrapper.text()).toContain('已成交')
    expect(wrapper.text()).toContain('10–15 个工作日')
  })

  it('shows an actionable empty state', async () => {
    listCases.mockResolvedValue({
      items: [], total: 0, limit: 20, offset: 0, warnings: [],
    })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无历史案例')
    expect(wrapper.text()).toContain('新增案例')
  })

  it('keeps analysis navigation when the case library is unavailable', async () => {
    listCases.mockRejectedValue(new Error('历史案例库暂不可用'))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('历史案例库暂不可用')
    expect(wrapper.text()).toContain('返回需求分析')
  })

  it('confirms deletion and refreshes the list', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    deleteCase.mockResolvedValue(undefined)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-test="delete-case"]').trigger('click')
    await flushPromises()

    expect(deleteCase).toHaveBeenCalledWith('case-id')
    expect(listCases).toHaveBeenCalledTimes(2)
  })
})
