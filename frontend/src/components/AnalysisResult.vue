<script setup lang="ts">
import AnalysisModeBadge from './AnalysisModeBadge.vue'
import SimilarCasesPanel from './SimilarCasesPanel.vue'
import StepTelemetry from './StepTelemetry.vue'
import type { AnalysisResponse, RiskCategory, RiskSeverity } from '../types/analysis'
import type { CaseRagResult } from '../types/case'

const props = defineProps<{ analysis: AnalysisResponse }>()

const notRunCaseRag: CaseRagResult = {
  status: 'not_run',
  retrieval_mode: 'local_bm25',
  min_similarity: 0.25,
  matches: [],
  used_by_agents: [],
  impact_summary: [],
  candidate_count: 0,
}

const riskLabels: Record<RiskCategory, string> = {
  payment: '支付风险',
  hardware: '硬件风险',
  third_party_platform: '第三方平台',
  urgent_delivery: '紧急交付',
}

const severityLabels: Record<RiskSeverity, string> = {
  low: '低',
  medium: '中',
  high: '高',
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>

<template>
  <article class="analysis-result">
    <header class="result-header">
      <div>
        <p class="eyebrow">分析完成</p>
        <h2>{{ analysis.requirement.project_type }}</h2>
      </div>
      <AnalysisModeBadge :mode="analysis.analysis_mode" />
    </header>

    <p v-if="analysis.analysis_mode === 'local_fallback'" class="notice local-notice">
      本地规则分析，未调用大模型
    </p>
    <p v-else-if="analysis.fallback_occurred" class="notice fallback-notice">
      部分步骤已自动降级，详细原因见执行详情。
    </p>

    <section class="metric-grid">
      <div class="metric quote-metric">
        <span>建议报价（税前）</span>
        <strong>
          {{ formatCurrency(analysis.quote.pricing.min_amount) }}–{{ formatCurrency(analysis.quote.pricing.max_amount) }}
        </strong>
        <p>{{ analysis.quote.explanation }}</p>
      </div>
      <div class="metric">
        <span>预计工期</span>
        <strong>{{ analysis.estimated_duration.min_days }}–{{ analysis.estimated_duration.max_days }} 个工作日</strong>
        <p>{{ analysis.estimated_duration.explanation }}</p>
      </div>
      <div class="metric recommendation-metric" :data-verdict="analysis.recommendation.verdict">
        <span>接单建议</span>
        <strong>{{ analysis.recommendation.should_accept ? '建议承接' : '暂不承接' }}</strong>
        <p>{{ analysis.recommendation.reasons.join('；') }}</p>
      </div>
    </section>

    <section class="result-section">
      <h3>功能范围</h3>
      <div class="tag-list">
        <span v-for="feature in analysis.requirement.features" :key="feature">{{ feature }}</span>
        <span v-if="!analysis.requirement.features.length" class="muted">待进一步确认</span>
      </div>
    </section>

    <section class="result-section">
      <h3>技术方案</h3>
      <p>{{ analysis.technical_solution.architecture }}</p>
      <dl class="tech-grid">
        <div><dt>前端</dt><dd>{{ analysis.technical_solution.frontend.join(' / ') }}</dd></div>
        <div><dt>后端</dt><dd>{{ analysis.technical_solution.backend.join(' / ') }}</dd></div>
        <div><dt>数据库</dt><dd>{{ analysis.technical_solution.database.join(' / ') }}</dd></div>
        <div><dt>部署</dt><dd>{{ analysis.technical_solution.deployment.join(' / ') }}</dd></div>
      </dl>
    </section>

    <section class="result-section">
      <h3>风险识别</h3>
      <div v-if="analysis.risks.length" class="risk-list">
        <div v-for="risk in analysis.risks" :key="risk.category" class="risk-item">
          <span :class="`severity-${risk.severity}`">{{ severityLabels[risk.severity] }}</span>
          <div>
            <strong>{{ riskLabels[risk.category] }}</strong>
            <p>{{ risk.reason }}</p>
          </div>
        </div>
      </div>
      <p v-else class="muted">暂未识别到规则风险。</p>
    </section>

    <section class="result-section">
      <h3>需要追问</h3>
      <ol v-if="analysis.follow_up_questions.length" class="question-list">
        <li v-for="question in analysis.follow_up_questions" :key="question">{{ question }}</li>
      </ol>
      <p v-else class="muted">当前信息足够进入方案确认。</p>
    </section>

    <SimilarCasesPanel :result="props.analysis.case_rag || notRunCaseRag" />

    <section class="result-section reply-section">
      <h3>客户回复建议</h3>
      <p>{{ analysis.client_reply }}</p>
    </section>

    <StepTelemetry
      :steps="analysis.telemetry.steps"
      :total-duration-ms="analysis.telemetry.total_duration_ms"
    />
  </article>
</template>
