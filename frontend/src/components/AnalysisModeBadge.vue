<script setup lang="ts">
import type { AnalysisMode } from '../types/analysis'

defineProps<{ mode: AnalysisMode }>()
</script>

<template>
  <span class="mode-badge" :class="`mode-${mode}`">
    <span class="mode-dot" />
    {{ mode === 'agents' ? 'AI Agents 分析' : '本地规则分析' }}
  </span>
</template>

