<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { getTokenStats, listAuditLogs, listGenerationLogs } from '#/api/admin';

import { Card, Statistic, Table, Tabs } from 'ant-design-vue';

interface AuditLogItem {
  id: string;
  action: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface TokenStat {
  user_id: string;
  username: string;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  session_tokens?: unknown[];
}

interface GenerationLogItem {
  id: string;
  project_title: string;
  username: string;
  status: string;
  final_score?: number;
  duration_seconds?: number;
  start_time?: string;
}

const logs = ref<AuditLogItem[]>([]);
const tokenStats = ref<TokenStat[]>([]);
const generationLogs = ref<GenerationLogItem[]>([]);
const activeTab = ref('logs');

const logColumns = [
  { title: '时间', key: 'created_at', width: 180 },
  { title: '操作', dataIndex: 'action', key: 'action', width: 150 },
  { title: '详情', key: 'details' },
];

const generationColumns = [
  { title: '项目', dataIndex: 'project_title', key: 'project_title' },
  { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '评分', dataIndex: 'final_score', key: 'final_score', width: 80 },
  { title: '耗时(s)', dataIndex: 'duration_seconds', key: 'duration_seconds', width: 100 },
  { title: '开始时间', key: 'start_time', width: 180 },
];

async function loadLogs() {
  try {
    const res = (await listAuditLogs()) as { data: { items?: AuditLogItem[] } };
    logs.value = res.data.items || [];
  } catch (e) {
    console.error(e);
  }
}

async function loadTokenStats() {
  try {
    const res = (await getTokenStats()) as { data?: TokenStat[] };
    tokenStats.value = res.data || [];
  } catch (e) {
    console.error(e);
  }
}

async function loadGenerationLogs() {
  try {
    const res = (await listGenerationLogs()) as { data: { items?: GenerationLogItem[] } };
    generationLogs.value = res.data.items || [];
  } catch (e) {
    console.error(e);
  }
}

onMounted(() => {
  loadLogs();
  loadTokenStats();
  loadGenerationLogs();
});
</script>

<template>
  <div>
    <Tabs v-model:activeKey="activeTab">
      <Tabs.TabPane key="logs" tab="操作日志">
        <Table :columns="logColumns" :data-source="logs" row-key="id" :pagination="false">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'created_at'">
              {{ new Date(record.created_at).toLocaleString() }}
            </template>
            <template v-if="column.key === 'details'">
              {{ record.details ? JSON.stringify(record.details) : '-' }}
            </template>
          </template>
        </Table>
      </Tabs.TabPane>

      <Tabs.TabPane key="generations" tab="生成日志">
        <Table
          :columns="generationColumns"
          :data-source="generationLogs"
          row-key="id"
          :pagination="false"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'start_time'">
              {{ record.start_time ? new Date(record.start_time).toLocaleString() : '-' }}
            </template>
            <template v-if="column.key === 'final_score'">
              {{ record.final_score ?? '-' }}
            </template>
          </template>
        </Table>
      </Tabs.TabPane>

      <Tabs.TabPane key="tokens" tab="Token 统计">
        <div v-for="stat in tokenStats" :key="stat.user_id" class="mb-4">
          <Card size="small">
            <div class="flex items-center justify-between">
              <span class="font-medium">{{ stat.username }}</span>
              <Statistic title="总 Token" :value="stat.total_tokens || 0" :value-style="{ fontSize: '16px' }" />
            </div>
            <div v-if="stat.session_tokens?.length" class="mt-2 text-sm text-gray-500">
              会话数: {{ stat.session_tokens.length }}
            </div>
          </Card>
        </div>
        <div v-if="!tokenStats.length" class="py-8 text-center text-gray-400">
          暂无数据
        </div>
      </Tabs.TabPane>
    </Tabs>
  </div>
</template>
