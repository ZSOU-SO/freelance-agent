import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CaseForm from '../components/CaseForm.vue'


describe('CaseForm', () => {
  it('normalizes arrays and integer amounts before submit', async () => {
    const wrapper = mount(CaseForm)
    await wrapper.get('[data-test="project-number"]').setValue('case-001')
    await wrapper.get('[data-test="project-type"]').setValue('web_app')
    await wrapper.get('[data-test="requirement"]').setValue('开发刷题网站')
    await wrapper.get('[data-test="features"]').setValue('题库, 答题, 题库,  ')
    await wrapper.get('[data-test="quote-min"]').setValue('10000')
    await wrapper.get('[data-test="quote-max"]').setValue('20000')
    await wrapper.get('[data-test="duration-min"]').setValue('10')
    await wrapper.get('[data-test="duration-max"]').setValue('15')
    await wrapper.get('[data-test="lessons"]').setValue('先确认题目格式')
    await wrapper.get('form').trigger('submit')

    const emitted = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>
    expect(emitted.project_number).toBe('CASE-001')
    expect(emitted.core_features).toEqual(['题库', '答题'])
    expect((emitted.suggested_quote as { min_amount: number }).min_amount).toBe(10000)
    expect(emitted.is_won).toBe(false)
    expect(emitted.final_deal_price).toBeNull()
  })

  it('requires deal price for a won case and emits actual duration', async () => {
    const wrapper = mount(CaseForm)
    await wrapper.get('[data-test="project-number"]').setValue('CASE-001')
    await wrapper.get('[data-test="project-type"]').setValue('web_app')
    await wrapper.get('[data-test="requirement"]').setValue('开发刷题网站')
    await wrapper.get('[data-test="features"]').setValue('题库')
    await wrapper.get('[data-test="quote-min"]').setValue('10000')
    await wrapper.get('[data-test="quote-max"]').setValue('20000')
    await wrapper.get('[data-test="duration-min"]').setValue('10')
    await wrapper.get('[data-test="duration-max"]').setValue('15')
    await wrapper.get('[data-test="lessons"]').setValue('经验')
    await wrapper.get('[data-test="is-won"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('成交案例必须填写最终成交价')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.get('[data-test="deal-price"]').setValue('15000')
    await wrapper.get('[data-test="actual-duration"]').setValue('16')
    await wrapper.get('form').trigger('submit')
    const emitted = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>
    expect(emitted.final_deal_price).toBe(15000)
    expect(emitted.actual_duration_days).toBe(16)
  })
})

