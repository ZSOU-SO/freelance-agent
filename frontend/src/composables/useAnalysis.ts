import { ref } from 'vue'

import { createAnalysis, listAnalyses } from '../api/analyses'
import type { AnalysisResponse } from '../types/analysis'


export function useAnalysis() {
  const current = ref<AnalysisResponse | null>(null)
  const history = ref<AnalysisResponse[]>([])
  const loading = ref(false)
  const historyLoading = ref(false)
  const error = ref('')

  async function analyze(requirementText: string) {
    loading.value = true
    error.value = ''
    try {
      const result = await createAnalysis(requirementText)
      current.value = result
      history.value = [result, ...history.value.filter((item) => item.id !== result.id)]
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '分析失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  async function loadHistory() {
    historyLoading.value = true
    try {
      history.value = (await listAnalyses()).items
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '历史记录加载失败'
    } finally {
      historyLoading.value = false
    }
  }

  function selectAnalysis(analysis: AnalysisResponse) {
    current.value = analysis
    error.value = ''
  }

  return {
    current,
    history,
    loading,
    historyLoading,
    error,
    analyze,
    loadHistory,
    selectAnalysis,
  }
}

