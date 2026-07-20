<script setup lang="ts">
import { onMounted } from 'vue'

import AnalysisHistory from './components/AnalysisHistory.vue'
import AnalysisResult from './components/AnalysisResult.vue'
import RequirementForm from './components/RequirementForm.vue'
import { useAnalysis } from './composables/useAnalysis'

const {
  current,
  history,
  loading,
  historyLoading,
  error,
  analyze,
  loadHistory,
  selectAnalysis,
} = useAnalysis()

onMounted(loadHistory)
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <a class="brand" href="#" aria-label="freelance-agent 首页">
        <span>FA</span>
        <div>
          <strong>freelance-agent</strong>
          <small>需求分析与报价助手</small>
        </div>
      </a>
      <p>从客户原话到可执行方案</p>
    </header>

    <main>
      <section class="hero">
        <p class="eyebrow">Freelance Intelligence</p>
        <h1>先看清需求，<br /><em>再决定接不接。</em></h1>
        <p class="hero-copy">提取范围、识别风险、估算报价，并生成一段可以直接发给客户的回复。</p>
      </section>

      <div class="workspace-grid">
        <div class="primary-column">
          <RequirementForm :loading="loading" @submit="analyze" />
          <p v-if="error" class="global-error" role="alert">{{ error }}</p>
          <AnalysisResult v-if="current" :analysis="current" />
          <section v-else class="empty-result">
            <span>01 → 04</span>
            <h2>四步显式流水线</h2>
            <p>Requirement → Technical → Quote → Reply</p>
          </section>
        </div>
        <AnalysisHistory
          :items="history"
          :selected-id="current?.id"
          :loading="historyLoading"
          @select="selectAnalysis"
        />
      </div>
    </main>
  </div>
</template>

