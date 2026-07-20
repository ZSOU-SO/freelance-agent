import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RequirementForm from '../components/RequirementForm.vue'


describe('RequirementForm', () => {
  it('emits trimmed requirement text', async () => {
    const wrapper = mount(RequirementForm, { props: { loading: false } })
    await wrapper.get('textarea').setValue('  开发商城  ')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')?.[0]).toEqual(['开发商城'])
  })

  it('does not submit a blank requirement', async () => {
    const wrapper = mount(RequirementForm, { props: { loading: false } })
    await wrapper.get('textarea').setValue('   ')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.text()).toContain('请输入客户需求')
  })

  it('disables controls while loading', () => {
    const wrapper = mount(RequirementForm, { props: { loading: true } })
    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })
})
