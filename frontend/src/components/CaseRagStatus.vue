<script setup lang="ts">
import type { CaseRagStatus } from '../types/case'

defineProps<{ status: CaseRagStatus; retrievalMode: string }>()

const labels: Record<CaseRagStatus, string> = {
  not_run: '未执行检索',
  matched: '已匹配',
  empty_library: '案例库为空',
  no_match: '无高分匹配',
  failed: '检索失败',
}
</script>

<template>
  <span class="case-rag-status" :data-status="status">
    {{ retrievalMode === 'local_bm25' ? '本地 BM25' : retrievalMode }} · {{ labels[status] }}
  </span>
</template>

