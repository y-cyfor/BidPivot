<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { listProjects } from '#/api/bid';
import { createLossAnalysis, getLossAnalysis, listLossAnalyses, saveToKnowledge } from '#/api/lossAnalysis';

import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  message,
  Row,
  Select,
  Spin,
  Tag,
} from 'ant-design-vue';

interface ProjectOption {
  id: string;
  title: string;
}

interface LossReason {
  category: string;
  point: string;
  score: number;
  description: string;
}

interface LossImprovement {
  for_reason: string;
  suggestion: string;
  best_practice?: string;
}

interface LossStrategy {
  tech_direction?: string;
  pricing_strategy?: string;
  qualification?: string;
  summary?: string;
}

interface LossAnalysisResult {
  reasons?: LossReason[];
  improvements?: LossImprovement[];
  strategy?: LossStrategy;
}

interface LossAnalysis {
  id: string;
  project_id?: string;
  created_at: string;
  analysis_result?: LossAnalysisResult;
}

const analyses = ref<LossAnalysis[]>([]);
const projects = ref<ProjectOption[]>([]);
const selectedAnalysis = ref<LossAnalysis | null>(null);
const loading = ref(false);
const uploading = ref(false);
const file = ref<File | null>(null);
const selectedProjectId = ref<string | undefined>(undefined);
const dialogVisible = ref(false);

async function loadAnalyses() {
  loading.value = true;
  try {
    const res = (await listLossAnalyses()) as { data?: LossAnalysis[] };
    analyses.value = res.data || [];
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function loadProjects() {
  try {
    const res = (await listProjects()) as { data: { items?: ProjectOption[] } };
    projects.value = res.data.items || [];
  } catch (e) {
    console.error(e);
  }
}

async function handleUpload() {
  if (!file.value) return;
  uploading.value = true;
  try {
    await createLossAnalysis(file.value, selectedProjectId.value || undefined);
    file.value = null;
    selectedProjectId.value = undefined;
    dialogVisible.value = false;
    message.success('分析任务已创建');
    await loadAnalyses();
  } catch (e) {
    message.error('分析失败');
  } finally {
    uploading.value = false;
  }
}

async function handleViewDetail(id: string) {
  try {
    const res = (await getLossAnalysis(id)) as { data: LossAnalysis };
    selectedAnalysis.value = res.data;
  } catch (e) {
    console.error(e);
  }
}

async function handleSaveToKnowledge(id: string) {
  try {
    await saveToKnowledge(id);
    message.success('已保存到知识库');
  } catch (e) {
    message.error('保存失败');
  }
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  file.value = target.files?.[0] || null;
}

onMounted(() => {
  loadAnalyses();
  loadProjects();
});
</script>

<template>
  <Page title="丢标分析" description="上传评标结果，AI 分析丢标原因并归类">
    <Row :gutter="20">
      <!-- Left: Upload + Analysis List -->
      <Col :span="8">
        <!-- Upload Card -->
        <Card title="上传评标结果" size="small" class="mb-4">
          <Form layout="vertical">
            <Form.Item label="评标结果文件">
              <input type="file" class="w-full text-sm" @change="handleFileChange" />
            </Form.Item>
            <Form.Item label="关联标书（可选）">
              <Select
                v-model:value="selectedProjectId"
                placeholder="不关联"
                allow-clear
                style="width: 100%"
              >
                <Select.Option v-for="p in projects" :key="p.id" :value="p.id">
                  {{ p.title }}
                </Select.Option>
              </Select>
            </Form.Item>
            <Button
              type="primary"
              :loading="uploading"
              :disabled="!file"
              style="width: 100%"
              @click="handleUpload"
            >
              {{ uploading ? '分析中...' : '开始分析' }}
            </Button>
          </Form>
        </Card>

        <!-- Analysis List Card -->
        <Card title="分析记录" size="small">
          <Spin :spinning="loading">
            <div v-if="analyses.length">
              <div
                v-for="a in analyses"
                :key="a.id"
                class="cursor-pointer rounded-md px-3 py-2.5 transition-colors"
                :class="selectedAnalysis?.id === a.id ? 'bg-blue-50' : 'hover:bg-gray-50'"
                @click="handleViewDetail(a.id)"
              >
                <div class="text-sm">
                  {{ new Date(a.created_at).toLocaleDateString() }}
                </div>
                <div class="mt-0.5 text-xs text-gray-400">
                  {{ a.project_id ? '已关联标书' : '未关联' }}
                </div>
              </div>
            </div>
            <Empty v-else description="暂无分析" :image-style="{ height: '60px' }" />
          </Spin>
        </Card>
      </Col>

      <!-- Right: Analysis Detail -->
      <Col :span="16">
        <Card v-if="selectedAnalysis" size="small">
          <template #title>
            <div class="flex items-center justify-between">
              <span>分析结果</span>
              <Button type="link" @click="handleSaveToKnowledge(selectedAnalysis.id)">
                保存到知识库
              </Button>
            </div>
          </template>

          <div v-if="selectedAnalysis.analysis_result">
            <!-- Reasons -->
            <div v-if="selectedAnalysis.analysis_result.reasons" class="mb-6">
              <h4 class="mb-2 font-medium">原因总结</h4>
              <Card
                v-for="(r, i) in selectedAnalysis.analysis_result.reasons"
                :key="i"
                size="small"
                class="mb-2 bg-red-50"
              >
                <div class="flex justify-between">
                  <span class="text-sm font-medium">{{ r.category }} - {{ r.point }}</span>
                  <Tag color="error">{{ r.score }}</Tag>
                </div>
                <p class="mt-1 text-sm text-gray-600">{{ r.description }}</p>
              </Card>
            </div>

            <!-- Improvements -->
            <div v-if="selectedAnalysis.analysis_result.improvements" class="mb-6">
              <h4 class="mb-2 font-medium">改进建议</h4>
              <Card
                v-for="(imp, i) in selectedAnalysis.analysis_result.improvements"
                :key="i"
                size="small"
                class="mb-2 bg-blue-50"
              >
                <div class="text-sm font-medium">{{ imp.for_reason }}</div>
                <p class="mt-1 text-sm text-gray-600">{{ imp.suggestion }}</p>
                <p v-if="imp.best_practice" class="mt-1 text-sm text-blue-600">
                  最佳实践: {{ imp.best_practice }}
                </p>
              </Card>
            </div>

            <!-- Strategy -->
            <div v-if="selectedAnalysis.analysis_result.strategy">
              <h4 class="mb-2 font-medium">投标策略</h4>
              <Card size="small" class="bg-green-50">
                <Descriptions :column="1" bordered size="small">
                  <Descriptions.Item label="技术方向">
                    {{ selectedAnalysis.analysis_result.strategy.tech_direction }}
                  </Descriptions.Item>
                  <Descriptions.Item label="报价策略">
                    {{ selectedAnalysis.analysis_result.strategy.pricing_strategy }}
                  </Descriptions.Item>
                  <Descriptions.Item label="资质补充">
                    {{ selectedAnalysis.analysis_result.strategy.qualification }}
                  </Descriptions.Item>
                </Descriptions>
                <p class="mt-3 text-sm text-gray-700">
                  {{ selectedAnalysis.analysis_result.strategy.summary }}
                </p>
              </Card>
            </div>
          </div>
        </Card>

        <Card v-else size="small">
          <Empty description="选择左侧分析记录查看详情" />
        </Card>
      </Col>
    </Row>
  </Page>
</template>
