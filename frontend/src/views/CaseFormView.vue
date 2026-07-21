<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { createCase, getCase, updateCase } from '../api/cases'
import CaseForm from '../components/CaseForm.vue'
import type { HistoricalCase, HistoricalCasePayload } from '../types/case'

const route = useRoute()
const router = useRouter()
const initial = ref<HistoricalCase | null>(null)
const loading = ref(false)
const error = ref('')
const caseId = typeof route.params.id === 'string' ? route.params.id : ''

onMounted(async () => {
  if (!caseId) return
  loading.value = true
  try { initial.value = await getCase(caseId) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '案例加载失败' }
  finally { loading.value = false }
})

async function save(payload: HistoricalCasePayload) {
  loading.value = true
  error.value = ''
  try {
    if (caseId) await updateCase(caseId, payload)
    else await createCase(payload)
    await router.push('/cases')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '案例保存失败'
  } finally { loading.value = false }
}
</script>

<template>
  <main class="case-page narrow-page">
    <div class="page-heading"><div><p class="eyebrow">Case Library</p><h1>{{ caseId ? '编辑案例' : '新增案例' }}</h1></div></div>
    <p v-if="error" class="global-error" role="alert">{{ error }}</p>
    <CaseForm :initial="initial" :loading="loading" @submit="save" @cancel="router.push('/cases')" />
  </main>
</template>

