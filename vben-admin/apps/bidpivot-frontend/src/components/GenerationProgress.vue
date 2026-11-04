<script setup lang="ts">
import { computed } from 'vue';

import type { WsEvent } from '#/composables/useWebSocket';

import { Collapse, Progress, Tag } from 'ant-design-vue';

const props = defineProps<{
  sectionStatuses: Record<string, string>;
  thinkingChains: Record<string, WsEvent[]>;
  overallProgress: number;
  totalSections: number;
  isComplete: boolean;
  outline: { sections: Array<{ id: string; title: string; agent_role: string }> };
}>();

const progressPercent = computed(() => {
  const total = props.outline.sections.length || 1;
  const completed = props.outline.sections.filter(
    (section) => props.sectionStatuses[section.id] === 'completed',
  ).length;
  return Math.min(100, Math.round((completed / total) * 100));
});

const statusLabels: Record<string, string> = {
  pending: '排队中',
  writing: '写作中',
  completed: '已完成',
  failed: '失败',
  waiting: '等待依赖',
};

const statusColors: Record<string, string> = {
  pending: 'default',
  writing: 'processing',
  completed: 'success',
  failed: 'error',
  waiting: 'warning',
};
</script>

<template>
  <div role="status" aria-live="polite" aria-label="标书生成进度">
    <!-- Overall Progress -->
    <div class="mb-6">
      <div class="mb-2 flex justify-between text-sm text-gray-600">
        <span>{{ isComplete ? '生成完成' : '生成中...' }}</span>
        <span>{{ progressPercent }}%</span>
      </div>
      <Progress :percent="progressPercent" :status="isComplete ? 'success' : 'active'" />
    </div>

    <!-- Section List -->
    <Collapse>
      <Collapse.Panel
        v-for="section in outline.sections"
        :key="section.id"
        :header="section.title"
      >
        <template #extra>
          <Tag :color="statusColors[sectionStatuses[section.id] || 'pending']">
            {{ statusLabels[sectionStatuses[section.id] || 'pending'] }}
          </Tag>
        </template>

        <div class="mb-2 text-xs text-gray-500">
          Agent: {{ section.agent_role }}
        </div>

        <div v-if="thinkingChains[section.id]?.length" class="space-y-2">
          <div
            v-for="(event, idx) in thinkingChains[section.id]"
            :key="idx"
            class="text-sm"
          >
            <div
              v-if="event.type === 'thinking'"
              class="rounded-lg bg-blue-50 px-3 py-2 text-blue-800"
            >
              <span class="text-xs text-blue-500">{{ event.agent }}:</span>
              {{ event.content }}
            </div>
            <div
              v-else-if="event.type === 'tool_call'"
              class="rounded-lg bg-amber-50 px-3 py-2 text-amber-800"
            >
              <span class="text-xs text-amber-500">工具调用: {{ event.tool }}</span>
              <div class="mt-1 text-xs">结果: {{ event.result_summary }}</div>
            </div>
          </div>
        </div>

        <div v-else class="py-4 text-center text-sm text-gray-400">
          暂无思考链数据
        </div>
      </Collapse.Panel>
    </Collapse>
  </div>
</template>
