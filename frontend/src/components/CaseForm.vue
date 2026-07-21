<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import type { HistoricalCase, HistoricalCasePayload } from '../types/case'
import { riskCategories } from '../types/case'
import type { RiskCategory, RiskSeverity } from '../types/analysis'

const props = defineProps<{ initial?: HistoricalCase | null; loading?: boolean }>()
const emit = defineEmits<{ submit: [payload: HistoricalCasePayload]; cancel: [] }>()

const error = ref('')
const form = reactive({
  projectNumber: '', projectType: '', requirement: '', features: '',
  budgetMin: '', budgetMax: '', quoteMin: '', quoteMax: '',
  durationMin: '', durationMax: '', actualDuration: '', dealPrice: '',
  risks: '', isWon: false, lessons: '',
})

watch(() => props.initial, (value) => {
  if (!value) return
  form.projectNumber = value.project_number
  form.projectType = value.project_type
  form.requirement = value.original_requirement
  form.features = value.core_features.join(', ')
  form.budgetMin = value.client_budget ? String(value.client_budget.min_amount) : ''
  form.budgetMax = value.client_budget ? String(value.client_budget.max_amount) : ''
  form.quoteMin = String(value.suggested_quote.min_amount)
  form.quoteMax = String(value.suggested_quote.max_amount)
  form.durationMin = String(value.estimated_duration.min_days)
  form.durationMax = String(value.estimated_duration.max_days)
  form.actualDuration = value.actual_duration_days ? String(value.actual_duration_days) : ''
  form.dealPrice = value.final_deal_price !== null ? String(value.final_deal_price) : ''
  form.risks = value.risks.map((risk) => risk.category).join(', ')
  form.isWon = value.is_won
  form.lessons = value.lessons_learned
}, { immediate: true })

function uniqueValues(text: string) {
  return [...new Map(text.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean).map((item) => [item.toLowerCase(), item])).values()]
}

function positiveInteger(value: string) {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? number : null
}

function nonNegativeInteger(value: string) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 0 ? number : null
}

function submit() {
  error.value = ''
  const features = uniqueValues(form.features)
  const quoteMin = nonNegativeInteger(form.quoteMin)
  const quoteMax = nonNegativeInteger(form.quoteMax)
  const durationMin = positiveInteger(form.durationMin)
  const durationMax = positiveInteger(form.durationMax)
  if (!form.projectNumber.trim() || !form.projectType.trim() || !form.requirement.trim() || !features.length || !form.lessons.trim()) {
    error.value = '请完整填写项目编号、类型、需求、功能和经验总结'
    return
  }
  if (quoteMin === null || quoteMax === null || quoteMin > quoteMax || durationMin === null || durationMax === null || durationMin > durationMax) {
    error.value = '请填写正确的报价和工期区间'
    return
  }
  const dealPrice = form.dealPrice === '' ? null : nonNegativeInteger(form.dealPrice)
  if (form.isWon && dealPrice === null) {
    error.value = '成交案例必须填写最终成交价'
    return
  }
  const actualDuration = form.actualDuration === '' ? null : positiveInteger(form.actualDuration)
  const budgetMin = form.budgetMin === '' ? null : nonNegativeInteger(form.budgetMin)
  const budgetMax = form.budgetMax === '' ? null : nonNegativeInteger(form.budgetMax)
  if ((budgetMin === null) !== (budgetMax === null) || (budgetMin !== null && budgetMax !== null && budgetMin > budgetMax)) {
    error.value = '客户预算必须同时填写有效的最低和最高金额'
    return
  }
  const categories = uniqueValues(form.risks).filter((value): value is RiskCategory => riskCategories.includes(value as RiskCategory))
  emit('submit', {
    project_number: form.projectNumber.trim().toUpperCase(),
    project_type: form.projectType.trim().toLowerCase(),
    original_requirement: form.requirement.trim(),
    core_features: features,
    client_budget: budgetMin === null ? null : { min_amount: budgetMin, max_amount: budgetMax!, currency: 'CNY', raw_text: null },
    suggested_quote: { min_amount: quoteMin, max_amount: quoteMax, currency: 'CNY', raw_text: null },
    final_deal_price: form.isWon ? dealPrice : null,
    estimated_duration: { min_days: durationMin, max_days: durationMax, explanation: '历史案例录入值', raw_text: null },
    actual_duration_days: form.isWon ? actualDuration : null,
    risks: categories.map((category) => ({ category, severity: 'medium' as RiskSeverity, reason: '历史案例人工录入' })),
    is_won: form.isWon,
    lessons_learned: form.lessons.trim(),
  })
}
</script>

<template>
  <form class="case-form" @submit.prevent="submit">
    <div class="form-grid">
      <label>项目编号<input data-test="project-number" v-model="form.projectNumber" /></label>
      <label>项目类型<input data-test="project-type" v-model="form.projectType" /></label>
      <label class="wide">原始需求<textarea data-test="requirement" v-model="form.requirement" rows="5" /></label>
      <label class="wide">核心功能（逗号分隔）<input data-test="features" v-model="form.features" /></label>
      <label>客户预算最低<input v-model="form.budgetMin" type="number" min="0" /></label>
      <label>客户预算最高<input v-model="form.budgetMax" type="number" min="0" /></label>
      <label>建议报价最低<input data-test="quote-min" v-model="form.quoteMin" type="number" min="0" /></label>
      <label>建议报价最高<input data-test="quote-max" v-model="form.quoteMax" type="number" min="0" /></label>
      <label>预计最短工期<input data-test="duration-min" v-model="form.durationMin" type="number" min="1" /></label>
      <label>预计最长工期<input data-test="duration-max" v-model="form.durationMax" type="number" min="1" /></label>
      <label class="checkbox"><input data-test="is-won" v-model="form.isWon" type="checkbox" /> 已成交</label>
      <template v-if="form.isWon">
        <label>最终成交价<input data-test="deal-price" v-model="form.dealPrice" type="number" min="0" /></label>
        <label>实际工期<input data-test="actual-duration" v-model="form.actualDuration" type="number" min="1" /></label>
      </template>
      <label class="wide">风险分类（逗号分隔）<input v-model="form.risks" placeholder="payment, hardware" /></label>
      <label class="wide">经验总结<textarea data-test="lessons" v-model="form.lessons" rows="4" /></label>
    </div>
    <p v-if="error" class="global-error" role="alert">{{ error }}</p>
    <div class="form-actions">
      <button type="button" class="secondary-button" @click="emit('cancel')">取消</button>
      <button type="submit" :disabled="loading">{{ loading ? '保存中…' : '保存案例' }}</button>
    </div>
  </form>
</template>

