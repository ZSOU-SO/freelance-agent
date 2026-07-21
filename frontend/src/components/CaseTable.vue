<script setup lang="ts">
import type { HistoricalCase } from '../types/case'

defineProps<{ items: HistoricalCase[] }>()
const emit = defineEmits<{ view: [item: HistoricalCase]; remove: [item: HistoricalCase] }>()

function money(min: number, max: number) {
  return `¥${min.toLocaleString('zh-CN')}–¥${max.toLocaleString('zh-CN')}`
}
</script>

<template>
  <div class="case-table-wrap">
    <table class="case-table">
      <thead><tr><th>编号 / 类型</th><th>报价</th><th>工期</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td><strong>{{ item.project_number }}</strong><small>{{ item.project_type }}</small></td>
          <td>{{ money(item.suggested_quote.min_amount, item.suggested_quote.max_amount) }}</td>
          <td>{{ item.estimated_duration.min_days }}–{{ item.estimated_duration.max_days }} 个工作日</td>
          <td>{{ item.is_won ? '已成交' : '未成交' }}</td>
          <td class="case-actions">
            <button type="button" @click="emit('view', item)">详情</button>
            <RouterLink :to="`/cases/${item.id}/edit`">编辑</RouterLink>
            <button data-test="delete-case" type="button" @click="emit('remove', item)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

