import { ref } from 'vue'

import { deleteCase, getCase, listCases } from '../api/cases'
import type { HistoricalCase } from '../types/case'

export function useCases() {
  const items = ref<HistoricalCase[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const warnings = ref<string[]>([])

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const result = await listCases()
      items.value = result.items
      total.value = result.total
      warnings.value = result.warnings || []
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '历史案例加载失败'
    } finally {
      loading.value = false
    }
  }

  async function remove(id: string) {
    await deleteCase(id)
    await load()
  }

  return { items, total, loading, error, warnings, load, remove, getCase }
}

