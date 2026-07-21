<script setup lang="ts">
import CaseRagStatus from './CaseRagStatus.vue'
import type { CaseRagResult } from '../types/case'

defineProps<{ result: CaseRagResult }>()

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

function money(value: number | null | undefined) {
  return value === null || value === undefined ? '未记录' : `¥${value.toLocaleString('zh-CN')}`
}
</script>

<template>
  <section class="result-section similar-cases">
    <div class="similar-heading">
      <h3>相似历史案例</h3>
      <CaseRagStatus :status="result.status" :retrieval-mode="result.retrieval_mode" />
    </div>
    <p v-if="result.status === 'not_run'" class="muted">该记录未执行案例检索。</p>
    <p v-else-if="result.status === 'empty_library'" class="muted">暂无历史案例，本次未使用案例参考。</p>
    <p v-else-if="result.status === 'no_match'" class="muted">未找到达到阈值的相似案例。</p>
    <p v-else-if="result.status === 'failed'" class="notice fallback-notice">历史案例检索失败，本次分析已继续使用原有流程。</p>
    <template v-else>
      <article v-for="match in result.matches" :key="match.case.id" class="similar-card">
        <header><div><strong>{{ match.case.project_number }}</strong><small>{{ match.case.project_type }}</small></div><b>{{ percent(match.similarity) }}</b></header>
        <div class="case-facts">
          <span>功能：{{ match.case.core_features.join('、') }}</span>
          <span>客户预算：{{ match.case.client_budget ? `${money(match.case.client_budget.min_amount)}–${money(match.case.client_budget.max_amount)}` : '未记录' }}</span>
          <span>建议报价：{{ money(match.case.suggested_quote.min_amount) }}–{{ money(match.case.suggested_quote.max_amount) }}</span>
          <span>成交：{{ match.case.is_won ? money(match.case.final_deal_price) : '未成交' }}</span>
          <span>工期：{{ match.case.estimated_duration.min_days }}–{{ match.case.estimated_duration.max_days }} / 实际 {{ match.case.actual_duration_days || '未记录' }}</span>
          <span>风险：{{ match.case.risks.length ? match.case.risks.map((risk) => risk.category).join('、') : '未记录' }}</span>
        </div>
        <div class="tag-list"><span v-for="signal in match.matched_signals" :key="signal">{{ signal }}</span></div>
        <div class="agent-use"><strong v-for="agent in match.used_by_agents" :key="agent">{{ agent }}</strong></div>
        <ul class="impact-list"><li v-for="impact in match.impacts" :key="`${impact.agent}-${impact.summary}`"><b>{{ impact.agent }}</b>：{{ impact.summary }}</li></ul>
      </article>
    </template>
    <p v-if="result.warning" class="notice fallback-notice">{{ result.warning }}</p>
  </section>
</template>
