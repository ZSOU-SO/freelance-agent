<script setup lang="ts">
import type { AnalysisResponse } from '../types/analysis'

defineProps<{
  items: AnalysisResponse[]
  selectedId?: string
  loading: boolean
}>()
const emit = defineEmits<{ select: [analysis: AnalysisResponse] }>()

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>

<template>
  <aside class="history-panel">
    <div class="panel-title">
      <h2>分析记录</h2>
      <span>{{ items.length }}</span>
    </div>
    <p v-if="loading" class="muted">正在加载…</p>
    <p v-else-if="!items.length" class="empty-history">完成首次分析后，记录会显示在这里。</p>
    <button
      v-for="item in items"
      :key="item.id"
      class="history-item"
      :class="{ active: item.id === selectedId }"
      type="button"
      @click="emit('select', item)"
    >
      <span>{{ item.requirement_text }}</span>
      <small>{{ formatDate(item.created_at) }} · {{ item.requirement.project_type }}</small>
    </button>
  </aside>
</template>

