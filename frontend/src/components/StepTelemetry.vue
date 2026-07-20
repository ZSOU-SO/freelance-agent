<script setup lang="ts">
import type { StepTelemetry } from '../types/analysis'

defineProps<{ steps: StepTelemetry[]; totalDurationMs: number }>()

const stageNames: Record<string, string> = {
  requirement: '需求提取',
  technical: '技术分析',
  quote: '报价计算',
  reply: '客户回复',
}
</script>

<template>
  <details class="telemetry-panel">
    <summary>执行详情 · {{ totalDurationMs.toFixed(1) }} ms</summary>
    <ol>
      <li v-for="step in steps" :key="step.step">
        <div>
          <strong>{{ stageNames[step.step] || step.step }}</strong>
          <span>{{ step.duration_ms.toFixed(1) }} ms</span>
        </div>
        <p>
          {{ step.execution_mode === 'agent' ? 'Agent' : '本地规则' }}
          <em v-if="step.fallback_used">· 已降级</em>
        </p>
        <code v-if="step.error">{{ step.error }}</code>
      </li>
    </ol>
  </details>
</template>

