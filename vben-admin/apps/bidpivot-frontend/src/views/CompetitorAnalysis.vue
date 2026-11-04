<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  createCompetitor,
  deleteCompetitor,
  deleteCompetitorDoc,
  listCompetitorDocs,
  listCompetitors,
  runAnalysis,
  uploadCompetitorDoc,
} from '#/api/competitor';

import {
  Button,
  Card,
  Checkbox,
  Divider,
  Empty,
  Form,
  Input,
  message,
  Modal,
  Select,
  Table,
  Tag,
} from 'ant-design-vue';
import {
  BarChartOutlined,
  DeleteOutlined,
  PlusOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue';

interface Competitor {
  id: string;
  name: string;
  industry?: string;
}

interface CompetitorDocument {
  id: string;
  title: string;
  file_type_tag?: string;
}

interface CompetitorAnalysis {
  id: string;
  report_content?: string;
}

const competitors = ref<Competitor[]>([]);
const selectedId = ref<string | null>(null);
const documents = ref<CompetitorDocument[]>([]);
const analyses = ref<CompetitorAnalysis[]>([]);

const showCreate = ref(false);
const createLoading = ref(false);
const newComp = ref({ name: '', industry: '', description: '' });

const showUpload = ref(false);
const uploadLoading = ref(false);
const uploadForm = ref({ title: '', fileTypeTag: '', file: null as File | null });

const analysisType = ref('competitor_vs_competitor');
const selectedCompetitorIds = ref<string[]>([]);
const analysisResult = ref('');
const analyzing = ref(false);

async function loadCompetitors() {
  try {
    const res = (await listCompetitors()) as { data?: Competitor[] };
    competitors.value = res.data || [];
  } catch (e) {
    console.error(e);
    message.error('加载竞品列表失败');
  }
}

async function loadDocuments() {
  if (!selectedId.value) return;
  try {
    const res = (await listCompetitorDocs(selectedId.value)) as { data?: CompetitorDocument[] };
    documents.value = res.data || [];
  } catch (e) {
    console.error(e);
    message.error('加载竞品资料失败');
  }
}

async function handleCreate() {
  if (!newComp.value.name.trim()) {
    message.warning('请输入公司名称');
    return;
  }
  createLoading.value = true;
  try {
    await createCompetitor(newComp.value);
    showCreate.value = false;
    newComp.value = { name: '', industry: '', description: '' };
    message.success('竞品公司创建成功');
    await loadCompetitors();
  } catch (e) {
    message.error('创建失败');
  } finally {
    createLoading.value = false;
  }
}

async function handleDelete(id: string) {
  Modal.confirm({
    title: '确认删除',
    content: '确定删除该竞品公司？删除后不可恢复。',
    okText: '确定',
    cancelText: '取消',
    okType: 'danger',
    async onOk() {
      try {
        await deleteCompetitor(id);
        if (selectedId.value === id) {
          selectedId.value = null;
          documents.value = [];
        }
        message.success('删除成功');
        await loadCompetitors();
      } catch (e) {
        message.error('删除失败');
      }
    },
  });
}

async function handleUpload() {
  if (!uploadForm.value.file || !selectedId.value) return;
  uploadLoading.value = true;
  try {
    await uploadCompetitorDoc(
      selectedId.value,
      uploadForm.value.file,
      uploadForm.value.title,
      uploadForm.value.fileTypeTag,
    );
    showUpload.value = false;
    uploadForm.value = { title: '', fileTypeTag: '', file: null };
    message.success('资料上传成功');
    await loadDocuments();
  } catch (e) {
    message.error('上传失败');
  } finally {
    uploadLoading.value = false;
  }
}

async function handleDeleteDocument(docId: string) {
  if (!selectedId.value) return;
  Modal.confirm({
    title: '确认删除',
    content: '确定删除该资料？',
    okText: '确定',
    cancelText: '取消',
    okType: 'danger',
    async onOk() {
      try {
        await deleteCompetitorDoc(selectedId.value!, docId);
        message.success('资料删除成功');
        await loadDocuments();
      } catch (e) {
        message.error('删除资料失败');
      }
    },
  });
}

async function handleAnalyze() {
  analyzing.value = true;
  analysisResult.value = '';
  try {
    const res = (await runAnalysis({
      analysis_type: analysisType.value,
      competitor_ids: selectedCompetitorIds.value,
    })) as { data: CompetitorAnalysis };
    analysisResult.value = res.data.report_content || '分析完成';
    analyses.value.unshift(res.data);
    message.success('分析完成');
  } catch (e) {
    message.error('分析失败');
  } finally {
    analyzing.value = false;
  }
}

function selectCompetitor(id: string) {
  selectedId.value = id;
  loadDocuments();
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  uploadForm.value.file = target.files?.[0] || null;
}

const documentColumns = [
  { title: '资料标题', dataIndex: 'title', key: 'title' },
  { title: '类型标签', dataIndex: 'file_type_tag', key: 'file_type_tag' },
  { title: '操作', key: 'action', width: 100 },
];

onMounted(loadCompetitors);
</script>

<template>
  <Page title="竞品分析" description="管理竞品公司资料，进行差异化分析">
    <template #extra>
      <Button type="primary" @click="showCreate = true">
        <PlusOutlined />
        添加竞品公司
      </Button>
    </template>

    <!-- Main layout: sidebar + content -->
    <div class="flex gap-5">
      <!-- Left sidebar: competitor list -->
      <Card class="w-[280px] flex-shrink-0">
        <template #title>
          <span class="font-semibold">竞品公司</span>
        </template>
        <Empty v-if="competitors.length === 0" description="暂无竞品公司" :image-style="{ height: '40px' }" />
        <div v-else class="flex flex-col gap-1">
          <div
            v-for="comp in competitors"
            :key="comp.id"
            class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2.5 transition-colors"
            :class="selectedId === comp.id ? 'bg-blue-50' : 'hover:bg-gray-50'"
            @click="selectCompetitor(comp.id)"
          >
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium text-gray-800">{{ comp.name }}</div>
              <div class="mt-0.5 text-xs text-gray-400">{{ comp.industry }}</div>
            </div>
            <Button
              type="text"
              danger
              size="small"
              class="opacity-0 transition-opacity hover:opacity-100"
              @click.stop="handleDelete(comp.id)"
            >
              <DeleteOutlined />
            </Button>
          </div>
        </div>
      </Card>

      <!-- Right content area -->
      <div class="flex min-w-0 flex-1 flex-col gap-5">
        <!-- Documents section -->
        <Card v-if="selectedId">
          <template #title>
            <div class="flex items-center justify-between">
              <span>竞品资料</span>
              <Button type="link" @click="showUpload = true">
                <UploadOutlined />
                上传资料
              </Button>
            </div>
          </template>
          <Table
            :data-source="documents"
            :columns="documentColumns"
            :pagination="false"
            row-key="id"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'file_type_tag'">
                <Tag>{{ record.file_type_tag }}</Tag>
              </template>
              <template v-if="column.key === 'action'">
                <Button type="link" danger size="small" @click="handleDeleteDocument(record.id)">
                  删除
                </Button>
              </template>
            </template>
          </Table>
        </Card>

        <!-- Placeholder when no competitor selected -->
        <Card v-else>
          <Empty description="请在左侧选择竞品公司查看详情" />
        </Card>

        <!-- Analysis section -->
        <Card>
          <template #title>
            <div class="flex items-center justify-between">
              <span>差异化分析</span>
              <Button
                type="primary"
                :loading="analyzing"
                :disabled="selectedCompetitorIds.length < 1"
                @click="handleAnalyze"
              >
                <BarChartOutlined />
                {{ analyzing ? '分析中...' : '开始分析' }}
              </Button>
            </div>
          </template>

          <Form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
            <Form.Item label="分析类型">
              <Select v-model:value="analysisType" style="width: 240px">
                <Select.Option value="competitor_vs_competitor">竞品间对比</Select.Option>
                <Select.Option value="our_vs_competitor">我方 vs 竞品</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item label="选择竞品">
              <Checkbox.Group v-model:value="selectedCompetitorIds">
                <Checkbox v-for="comp in competitors" :key="comp.id" :value="comp.id">
                  {{ comp.name }}
                </Checkbox>
              </Checkbox.Group>
            </Form.Item>
          </Form>

          <div v-if="analysisResult" class="mt-4">
            <Divider orientation="left">分析结果</Divider>
            <div class="rounded-lg bg-gray-50 p-4 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {{ analysisResult }}
            </div>
          </div>
        </Card>
      </div>
    </div>

    <!-- Create competitor dialog -->
    <Modal
      v-model:open="showCreate"
      title="添加竞品公司"
      :width="480"
      :mask-closable="false"
      :confirm-loading="createLoading"
      ok-text="创建"
      cancel-text="取消"
      @ok="handleCreate"
    >
      <Form :model="newComp" :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <Form.Item label="公司名称" required>
          <Input v-model:value="newComp.name" placeholder="请输入公司名称" />
        </Form.Item>
        <Form.Item label="行业">
          <Input v-model:value="newComp.industry" placeholder="请输入所属行业" />
        </Form.Item>
        <Form.Item label="简介">
          <Input.TextArea v-model:value="newComp.description" :rows="3" placeholder="请输入公司简介" />
        </Form.Item>
      </Form>
    </Modal>

    <!-- Upload document dialog -->
    <Modal
      v-model:open="showUpload"
      title="上传竞品资料"
      :width="480"
      :mask-closable="false"
      :confirm-loading="uploadLoading"
      :ok-button-props="{ disabled: !uploadForm.title || !uploadForm.fileTypeTag || !uploadForm.file }"
      ok-text="上传"
      cancel-text="取消"
      @ok="handleUpload"
    >
      <Form :model="uploadForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <Form.Item label="资料标题" required>
          <Input v-model:value="uploadForm.title" placeholder="请输入资料标题" />
        </Form.Item>
        <Form.Item label="类型标签" required>
          <Input v-model:value="uploadForm.fileTypeTag" placeholder="如：定价策略、客户案例" />
        </Form.Item>
        <Form.Item label="选择文件" required>
          <input type="file" class="text-sm" @change="handleFileChange" />
        </Form.Item>
      </Form>
    </Modal>
  </Page>
</template>
