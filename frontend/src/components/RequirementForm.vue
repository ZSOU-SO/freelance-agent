<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ loading: boolean }>()
const emit = defineEmits<{ submit: [requirementText: string] }>()

const requirementText = ref('')
const validationError = ref('')

function submit() {
  const normalized = requirementText.value.trim()
  if (!normalized) {
    validationError.value = '请输入客户需求'
    return
  }
  validationError.value = ''
  emit('submit', normalized)
}
</script>

<template>
  <form class="requirement-form" @submit.prevent="submit">
    <div class="field-heading">
      <label for="requirement-text">客户需求</label>
      <span>{{ requirementText.length }}/20000</span>
    </div>
    <textarea
      id="requirement-text"
      v-model="requirementText"
      :disabled="loading"
      maxlength="20000"
      rows="8"
      placeholder="粘贴客户发来的原始需求，例如：需要开发一个带微信支付的小程序，预算 5 万，希望四周上线……"
      @input="validationError = ''"
    />
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-footer">
      <p>系统会提取范围、工期和风险，并生成报价与回复建议。</p>
      <button type="submit" :disabled="loading">
        <span v-if="loading" class="spinner" aria-hidden="true" />
        {{ loading ? '正在分析…' : '开始分析' }}
      </button>
    </div>
  </form>
</template>

