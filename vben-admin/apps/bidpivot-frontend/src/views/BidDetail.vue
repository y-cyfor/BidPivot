<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  cancelGeneration,
  generateFullAsync,
  generateOutline,
  getProject,
  saveDocument,
  saveOutline,
} from '#/api/bid';
import type { ProjectDetailResponse } from '#/types/openapi';

import { createWsTicket } from '#/api/conversation';
import {
  diffVersions,
  listVersions,
  restoreVersion,
} from '#/api/conversation';
import ChatPanel from '#/components/ChatPanel.vue';
import ExportButton from '#/components/ExportButton.vue';
import GenerationProgress from '#/components/GenerationProgress.vue';
import OutlineEditor from '#/components/OutlineEditor.vue';
import TiptapEditor from '#/components/TiptapEditor.vue';
import { useGenerationWebSocket } from '#/composables/useWebSocket';

import {
  Alert,
  Button,
  Card,
  Empty,
  message,
  Spin,
  Select,
  Tabs,
  Tag,
} from 'ant-design-vue';
import {
  CommentOutlined,
  EditOutlined,
  FileTextOutlined,
  HistoryOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from '@ant-design/icons-vue';

const route = useRoute();
const router = useRouter();
const projectId = route.params.id as string;

interface OutlineSection {
  id: string;
  title: string;
  description: string;
  agent_role: string;
  dependencies: string[];
  content?: string;
  status?: string;
}

interface Outline {
  sections: OutlineSection[];
}

interface GeneratedSection {
  title?: string;
  content?: string;
}

interface GeneratedDocument {
  [key: string]: GeneratedSection | undefined;
  _merged?: GeneratedSection;
}

interface CheckReport {
  [key: string]: unknown;
  score?: number;
  summary?: string;
  failed?: unknown[];
  missing?: unknown[];
  passed?: unknown[];
  raw?: string;
}

interface VersionItem {
  id: string;
  version_number?: number;
  created_at: string;
  created_by?: string;
  instruction?: string;
}

const project = ref<ProjectDetailResponse | null>(null);
const outline = ref<Outline>({ sections: [] });
const document = ref<GeneratedDocument | null>(null);
const checkReport = ref<CheckReport | null>(null);
const editorContent = ref('');
const lastSavedHtml = ref('');
const loading = ref(false);
const generating = ref(false);
const cancelling = ref(false);
const saving = ref(false);
const pageLoading = ref(false);
const error = ref('');
const taskId = ref<string | null>(null);
const selectedText = ref('');
const activeTab = ref('editor');
const versions = ref<VersionItem[]>([]);
const diffFrom = ref<string>();
const diffTo = ref<string>();
const diffText = ref('');
const versionLoading = ref(false);

const ws = useGenerationWebSocket({
  getTicket: async (tid: string) => {
    const res = (await createWsTicket(projectId, tid)) as { data: { ticket: string } };
    return res.data.ticket;
  },
});

const statusMap: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  outline_firming: { label: '大纲确认中', color: 'warning' },
  generating: { label: '生成中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  partial: { label: '部分完成', color: 'warning' },
  cancelled: { label: '已取消', color: 'default' },
  failed: { label: '失败', color: 'error' },
};

const statusInfo = computed(() => {
  const status = project.value?.status;
  return status
    ? statusMap[status] || { label: status || '未知', color: 'default' }
    : { label: '未知', color: 'default' };
});

function buildHtmlFromDocument(doc: GeneratedDocument | null): string {
  if (!doc) return '';
  if (doc._merged) return doc._merged.content || '';
  let html = '';
  for (const key in doc) {
    if (key.startsWith('_')) continue;
    const section = doc[key];
    if (!section) continue;
    html += `<h2>${section.title || ''}</h2>`;
    html += section.content || '';
  }
  return html;
}

async function loadProject(silent = false) {
  if (!silent) pageLoading.value = true;
  try {
    const res = await getProject(projectId);
    const data = res.data;
    if (!data) throw new Error('项目不存在');
    project.value = data;
    outline.value = (data.outline_json as unknown as Outline) || { sections: [] };
    document.value = (data.full_document_json as unknown as GeneratedDocument) || null;
    checkReport.value = (data.check_report as unknown as CheckReport) || null;
    if (data.content_html) {
      editorContent.value = data.content_html;
      lastSavedHtml.value = data.content_html;
    } else if (data.full_document_json) {
      editorContent.value = buildHtmlFromDocument(
        data.full_document_json as unknown as GeneratedDocument,
      );
    }
  } catch {
    if (!silent) {
      error.value = '加载项目失败';
      message.error('加载项目失败');
    }
  } finally {
    if (!silent) pageLoading.value = false;
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

let finishing = false;

async function finishGeneration(totalSections = 0) {
  if (finishing) return;
  finishing = true;
  try {
    stopPolling();
    if (totalSections) ws.totalSections.value = totalSections;
    await loadProject(true);
    ws.isComplete.value = true;
    generating.value = false;
    activeTab.value = 'editor';
    const failedCount = Object.values(ws.sectionStatuses.value).filter((status) => status === 'failed').length;
    if (failedCount > 0) {
      message.warning(`标书生成完成，但有 ${failedCount} 个段落失败，请检查`);
    } else {
      message.success('标书生成完成');
    }
  } finally {
    finishing = false;
  }
}

watch(
  () => ws.isComplete.value,
  (complete) => {
    if (complete) void finishGeneration();
  },
);

watch(
  () => ws.generationFailed.value,
  (failed) => {
    if (!failed) return;
    stopPolling();
    generating.value = false;
    error.value = '标书生成失败，请查看生成日志后重试';
    message.error(error.value);
  },
);

watch(
  () => ws.generationCancelled.value,
  (cancelled) => {
    if (!cancelled) return;
    stopPolling();
    generating.value = false;
    cancelling.value = false;
    if (project.value) project.value.status = 'cancelled';
    message.info('生成任务已取消');
  },
);

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => {
    void (async () => {
      await loadProject(true);
      if (project.value?.status === 'completed' || project.value?.status === 'partial') {
        await finishGeneration();
      } else if (project.value?.status === 'cancelled') {
        stopPolling();
        generating.value = false;
        message.info('生成任务已取消');
      } else if (project.value?.status === 'failed') {
        stopPolling();
        generating.value = false;
        error.value = '标书生成失败，请查看日志后重试';
        message.error(error.value);
      }
    })();
  }, 3000);
}


function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail || fallback;
}

async function handleGenerateOutline() {
  loading.value = true;
  error.value = '';
  try {
    const res = (await generateOutline(projectId)) as { data: { sections?: OutlineSection[] } };
    const sections = (res.data.sections || []).map((s, i) => ({
      id: s.id || `s${i + 1}`,
      title: s.title || '',
      description: s.description || '',
      agent_role: s.agent_role || '技术方案',
      dependencies: s.dependencies || [],
    }));
    outline.value = { sections };
    if (project.value) project.value.status = 'outline_firming';
    message.success('大纲生成成功');
  } catch (e: unknown) {
    error.value = errorDetail(e, '大纲生成失败');
    message.error(error.value);
  } finally {
    loading.value = false;
  }
}

async function handleSaveOutline() {
  try {
    await saveOutline(projectId, (outline.value || { sections: [] }) as unknown as Record<string, unknown>);
    message.success('大纲已保存');
  } catch {
    error.value = '大纲保存失败';
    message.error('大纲保存失败');
  }
}

async function handleStartGeneration() {
  generating.value = true;
  error.value = '';
  try {
    await handleSaveOutline();
    const res = (await generateFullAsync(projectId)) as { data: { task_id: string } };
    const newTaskId = res.data.task_id;
    taskId.value = newTaskId;
    if (project.value) project.value.status = 'generating';
    activeTab.value = 'progress';
    startPolling();
    const ticketRes = (await createWsTicket(projectId, newTaskId)) as {
      data: { ticket: string };
    };
    ws.connect(newTaskId, ticketRes.data.ticket);
  } catch (e: unknown) {
    error.value = errorDetail(e, '启动生成失败');
    message.error(error.value);
    generating.value = false;
  }
}

async function handleCancel() {
  cancelling.value = true;
  try {
    await cancelGeneration(projectId);
    message.success('已提交取消请求');
  } catch (e: unknown) {
    message.error(errorDetail(e, '取消失败'));
    cancelling.value = false;
  }
}

async function handleSave() {
  if (!editorContent.value.trim() && document.value) {
    message.warning('当前文档内容为空，已取消保存');
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    await saveDocument(
      projectId,
      editorContent.value,
      (document.value || {}) as unknown as Record<string, unknown>,
    );
    lastSavedHtml.value = editorContent.value;
    message.success('保存成功');
  } catch (e: unknown) {
    error.value = errorDetail(e, '保存失败');
    message.error(error.value);
  } finally {
    saving.value = false;
  }
}

let autosaveTimer: ReturnType<typeof setInterval> | null = null;

async function autosave() {
  if (generating.value || saving.value) return;
  if (!editorContent.value || editorContent.value === lastSavedHtml.value) return;
  try {
    await saveDocument(
      projectId,
      editorContent.value,
      (document.value || {}) as unknown as Record<string, unknown>,
    );
    lastSavedHtml.value = editorContent.value;
  } catch {
    // Autosave failures are surfaced by the next manual save.
  }
}

function handleContentUpdate(html: string) {
  editorContent.value = html;
}

function formatCheckItem(item: unknown): string {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return String(item);
  const record = item as Record<string, unknown>;
  return String(record.point || record.description || record.content || JSON.stringify(item));
}

async function loadVersions() {
  versionLoading.value = true;
  try {
    const res = (await listVersions(projectId)) as { data?: { items?: VersionItem[] } };
    versions.value = res.data?.items || [];
    if (versions.value.length >= 2) {
      diffFrom.value = versions.value[1]?.id;
      diffTo.value = versions.value[0]?.id;
    }
  } catch {
    // Version history is optional; do not block the editor.
  } finally {
    versionLoading.value = false;
  }
}

async function handleDiff() {
  if (!diffFrom.value || !diffTo.value) {
    message.warning('请选择两个版本');
    return;
  }
  try {
    const res = (await diffVersions(projectId, diffFrom.value, diffTo.value)) as {
      data?: { diff?: string };
    };
    diffText.value = res.data?.diff || '';
  } catch {
    message.error('版本对比失败');
  }
}

async function handleRestore(versionId: string) {
  try {
    await restoreVersion(projectId, versionId);
    message.success('已恢复到该版本');
    await loadProject(true);
    await loadVersions();
  } catch {
    message.error('恢复失败');
  }
}

function handleTextSelect() {
  const selection = window.getSelection();
  selectedText.value = selection?.toString() || '';
}

onMounted(() => {
  void loadProject();
  void loadVersions();
  autosaveTimer = setInterval(() => void autosave(), 30000);
});
onUnmounted(() => {
  stopPolling();
  if (autosaveTimer) clearInterval(autosaveTimer);
});
</script>

<template>
  <Spin :spinning="pageLoading" tip="加载中...">
    <Page :title="project?.title || '标书详情'">
      <template #extra>
        <div class="flex items-center gap-2">
          <Tag v-if="project?.status" :color="statusInfo.color">
            {{ statusInfo.label }}
          </Tag>
          <ExportButton v-if="document || ws.isComplete.value" :project-id="projectId" />
          <Button
            v-if="document || ws.isComplete.value"
            type="primary"
            :icon="h(EditOutlined)"
            :loading="saving"
            @click="handleSave"
          >
            保存
          </Button>
          <Button @click="router.back()">返回</Button>
        </div>
      </template>

      <!-- Error Alert -->
      <Alert
        v-if="error"
        :message="error"
        type="error"
        show-icon
        closable
        class="mb-4"
        @close="error = ''"
      />

      <!-- Step 1: Generate Outline -->
      <Card v-if="!outline" class="mb-4">
        <Empty description="尚未生成大纲">
          <Button type="primary" :loading="loading" @click="handleGenerateOutline">
            {{ loading ? '生成中...' : '生成大纲' }}
          </Button>
        </Empty>
      </Card>

      <!-- Step 2: Edit Outline -->
      <Card v-if="outline && !document && project?.status !== 'generating'" class="mb-4">
        <template #title>
          <div class="flex items-center justify-between">
            <span>编辑大纲</span>
            <Button type="primary" :loading="generating" @click="handleStartGeneration">
              {{ generating ? '启动中...' : '确认大纲，开始生成' }}
            </Button>
          </div>
        </template>
        <OutlineEditor v-model="outline" />
      </Card>

      <!-- Step 3: Generation Progress -->
      <Card v-if="project?.status === 'generating' && !ws.isComplete.value" class="mb-4">
        <template #title>
          <div class="flex items-center justify-between">
            <span>生成进度</span>
            <div class="flex items-center gap-2">
              <Tag :color="ws.isConnected.value ? 'success' : 'error'">
                {{ ws.isConnected.value ? '已连接' : '未连接' }}
              </Tag>
              <Button danger size="small" :loading="cancelling" @click="handleCancel">
                取消生成
              </Button>
            </div>
          </div>
        </template>
        <GenerationProgress
          :section-statuses="ws.sectionStatuses.value"
          :thinking-chains="ws.thinkingChains.value"
          :overall-progress="ws.overallProgress.value"
          :total-sections="ws.totalSections.value"
          :is-complete="ws.isComplete.value"
          :outline="outline"
        />
      </Card>

      <!-- Step 4: Editor with Tabs -->
      <Card v-if="document || ws.isComplete.value">
        <Tabs v-model:activeKey="activeTab">
          <Tabs.TabPane key="editor">
            <template #tab>
              <span>
                <FileTextOutlined />
                标书编辑
              </span>
            </template>
            <div class="min-h-[500px]" @mouseup="handleTextSelect">
              <TiptapEditor v-model="editorContent" />
            </div>
          </Tabs.TabPane>

          <Tabs.TabPane v-if="outline" key="outline">
            <template #tab>
              <span>
                <NodeIndexOutlined />
                大纲视图
              </span>
            </template>
            <OutlineEditor v-model="outline" />
          </Tabs.TabPane>

          <Tabs.TabPane key="progress">
            <template #tab>
              <span>
                <SyncOutlined />
                生成进度
              </span>
            </template>
            <GenerationProgress
              :section-statuses="ws.sectionStatuses.value"
              :thinking-chains="ws.thinkingChains.value"
              :overall-progress="ws.overallProgress.value"
              :total-sections="ws.totalSections.value"
              :is-complete="ws.isComplete.value"
              :outline="outline"
            />
          </Tabs.TabPane>

          <Tabs.TabPane key="check">
            <template #tab>
              <span>
                <SafetyCertificateOutlined />
                合规检查
              </span>
            </template>
            <div v-if="checkReport" class="space-y-4">
              <div class="flex items-center gap-3">
                <span class="text-sm font-medium">总体评分：</span>
                <Tag :color="(checkReport.score ?? 0) >= 80 ? 'success' : 'warning'">
                  {{ checkReport.score ?? '未评分' }}
                </Tag>
              </div>
              <p v-if="checkReport.summary" class="text-sm text-gray-700">
                {{ checkReport.summary }}
              </p>
              <div v-if="checkReport.failed?.length">
                <div class="mb-1 text-sm font-medium text-red-600">不符合项</div>
                <ul class="list-disc pl-5 text-sm">
                  <li v-for="(item, idx) in checkReport.failed" :key="idx">
                    {{ formatCheckItem(item) }}
                  </li>
                </ul>
              </div>
              <div v-if="checkReport.missing?.length">
                <div class="mb-1 text-sm font-medium text-amber-600">缺失项</div>
                <ul class="list-disc pl-5 text-sm">
                  <li v-for="(item, idx) in checkReport.missing" :key="idx">
                    {{ formatCheckItem(item) }}
                  </li>
                </ul>
              </div>
              <div v-if="checkReport.passed?.length">
                <div class="mb-1 text-sm font-medium text-green-600">符合项</div>
                <ul class="list-disc pl-5 text-sm">
                  <li v-for="(item, idx) in checkReport.passed" :key="idx">
                    {{ formatCheckItem(item) }}
                  </li>
                </ul>
              </div>
              <pre
                v-if="checkReport.raw && !checkReport.passed?.length && !checkReport.failed?.length"
                class="whitespace-pre-wrap rounded bg-gray-50 p-3 text-xs text-gray-600"
              >{{ checkReport.raw }}</pre>
            </div>
            <Empty v-else description="暂无检查报告" />
          </Tabs.TabPane>

          <Tabs.TabPane key="versions">
            <template #tab>
              <span>
                <HistoryOutlined />
                版本历史
              </span>
            </template>
            <div class="space-y-4">
              <div class="flex flex-wrap items-center gap-2">
                <Select
                  v-model:value="diffFrom"
                  placeholder="起始版本"
                  style="width: 140px"
                  :options="versions.map((v) => ({ label: `v${v.version_number}`, value: v.id }))"
                />
                <span>→</span>
                <Select
                  v-model:value="diffTo"
                  placeholder="目标版本"
                  style="width: 140px"
                  :options="versions.map((v) => ({ label: `v${v.version_number}`, value: v.id }))"
                />
                <Button :loading="versionLoading" @click="handleDiff">对比</Button>
              </div>
              <pre
                v-if="diffText"
                class="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-3 text-xs"
              >{{ diffText }}</pre>
              <div
                v-for="version in versions"
                :key="version.id"
                class="flex items-center justify-between border-b border-gray-100 py-2 text-sm last:border-b-0"
              >
                <div class="flex flex-col">
                  <span class="font-medium">
                    v{{ version.version_number }} · {{ version.created_by }} ·
                    {{ new Date(version.created_at).toLocaleString() }}
                  </span>
                  <span v-if="version.instruction" class="text-xs text-gray-500">
                    {{ version.instruction }}
                  </span>
                </div>
                <Button size="small" @click="handleRestore(version.id)">恢复此版本</Button>
              </div>
              <Empty v-if="!versions.length" description="暂无版本记录" />
            </div>
          </Tabs.TabPane>

          <Tabs.TabPane key="chat">
            <template #tab>
              <span>
                <CommentOutlined />
                AI 对话修改
              </span>
            </template>
            <div class="mx-auto max-w-[800px]">
              <ChatPanel
                :project-id="projectId"
                :current-html="editorContent"
                :selected-text="selectedText"
                @content-update="handleContentUpdate"
              />
            </div>
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </Page>
  </Spin>
</template>
