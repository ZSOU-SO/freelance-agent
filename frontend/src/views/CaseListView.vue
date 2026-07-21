<script setup lang="ts">
import { onMounted, ref } from 'vue'

import CaseDetail from '../components/CaseDetail.vue'
import CaseTable from '../components/CaseTable.vue'
import { useCases } from '../composables/useCases'
import type { HistoricalCase } from '../types/case'

const { items, total, loading, error, warnings, load, remove } = useCases()
const selected = ref<HistoricalCase | null>(null)

async function confirmRemove(item: HistoricalCase) {
  if (!window.confirm(`确认删除案例 ${item.project_number}？此操作不可恢复。`)) return
  await remove(item.id)
  if (selected.value?.id === item.id) selected.value = null
}

onMounted(load)
</script>

<template>
  <main class="case-page">
    <div class="page-heading">
      <div><p class="eyebrow">Historical Intelligence</p><h1>历史案例</h1><p>用真实项目经验校准技术方案和报价解释。</p></div>
      <RouterLink class="primary-link" to="/cases/new">新增案例</RouterLink>
    </div>
    <p v-if="error" class="global-error" role="alert">{{ error }} · <RouterLink to="/">返回需求分析</RouterLink></p>
    <p v-for="warning in warnings" :key="warning" class="notice fallback-notice">{{ warning }}</p>
    <section class="case-panel">
      <p v-if="loading" class="muted">正在加载案例…</p>
      <div v-else-if="!items.length" class="empty-result"><h2>暂无历史案例</h2><p>新增案例后即可在分析前进行相似检索。</p><RouterLink to="/cases/new">新增案例</RouterLink></div>
      <template v-else><p class="muted">共 {{ total }} 条</p><CaseTable :items="items" @view="selected = $event" @remove="confirmRemove" /></template>
    </section>
    <CaseDetail v-if="selected" :item="selected" @close="selected = null" />
  </main>
</template>

