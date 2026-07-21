<script setup lang="ts">
import type { HistoricalCase } from '../types/case'

defineProps<{ item: HistoricalCase }>()
defineEmits<{ close: [] }>()
</script>

<template>
  <aside class="case-detail" aria-label="历史案例详情">
    <div class="panel-title"><h2>{{ item.project_number }}</h2><button @click="$emit('close')">关闭</button></div>
    <p>{{ item.original_requirement }}</p>
    <dl>
      <dt>核心功能</dt><dd>{{ item.core_features.join('、') }}</dd>
      <dt>成交结果</dt><dd>{{ item.is_won ? `已成交 ¥${item.final_deal_price?.toLocaleString('zh-CN')}` : '未成交' }}</dd>
      <dt>经验总结</dt><dd>{{ item.lessons_learned }}</dd>
    </dl>
  </aside>
</template>

