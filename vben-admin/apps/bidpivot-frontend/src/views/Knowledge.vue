<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  createDirectory,
  deleteDirectory,
  deleteDocument,
  getDocument,
  listDirectories,
  listDocuments,
  publishDocument,
  reindexDocument,
  searchKnowledge,
  uploadDocument,
} from '#/api/knowledge';

import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  message,
  Modal,
  Pagination,
  Row,
  Select,
  Spin,
  Table,
  Tag,
} from 'ant-design-vue';
import {
  DeleteOutlined,
  EyeOutlined,
  FolderAddOutlined,
  FolderOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue';

interface Directory {
  id: string;
  name: string;
  scope: string;
  parent_id: string | null;
  created_at: string;
}
interface Document {
  id: string;
  title: string;
  file_type: string;
  status: string;
  directory_id: string;
  scope: string;
  content_text?: string;
  created_at: string;
  updated_at: string;
}
interface SearchResultItem {
  chunk_text: string;
  document_id: string;
  document_title: string;
  score: number;
  metadata: Record<string, any>;
}

const route = useRoute();
const isGlobal = computed(() => route.path.includes('global'));
const scope = computed(() => (isGlobal.value ? 'global' : 'personal'));

const directories = ref<Directory[]>([]);
const documents = ref<Document[]>([]);
const selectedDirId = ref<string | null>(null);
const loading = ref(false);
const total = ref(0);
const pageSkip = ref(0);
const pageSize = 20;
const currentPage = ref(1);

const showCreateDir = ref(false);
const newDirName = ref('');
const showUpload = ref(false);
const uploadForm = ref({ title: '', directoryId: '', file: null as File | null });
const viewingDoc = ref<Document | null>(null);
const searchQuery = ref('');
const searchResults = ref<SearchResultItem[]>([]);
const searchLoading = ref(false);

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 100, align: 'center' as const },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100, align: 'center' as const },
  { title: '上传时间', dataIndex: 'created_at', key: 'created_at', width: 180, align: 'center' as const },
  { title: '操作', key: 'action', width: 240, align: 'center' as const, fixed: 'right' as const },
];

function formatDate(dateStr: string) {
  return dateStr ? new Date(dateStr).toLocaleString('zh-CN') : '';
}

function statusColor(status: string) {
  return status === 'published' ? 'green' : 'default';
}

function statusLabel(status: string) {
  return status === 'published' ? '已发布' : '草稿';
}

async function fetchDirectories() {
  try {
    const res = (await listDirectories(scope.value)) as { data?: Directory[] };
    directories.value = res.data || [];
  } catch (e) {
    console.error(e);
    message.error('加载目录失败');
  }
}

async function fetchDocuments() {
  loading.value = true;
  try {
    const res = (await listDocuments(
      scope.value,
      selectedDirId.value || undefined,
      pageSkip.value,
      pageSize,
    )) as { data?: { items?: Document[]; total?: number } };
    documents.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch (e) {
    console.error(e);
    message.error('加载文档失败');
  } finally {
    loading.value = false;
  }
}

function handleCreateDir() {
  if (!newDirName.value.trim()) return;
  Modal.confirm({
    title: '新建目录',
    content: `确定创建目录「${newDirName.value.trim()}」？`,
    okText: '确定',
    cancelText: '取消',
    async onOk() {
      try {
        await createDirectory(scope.value, newDirName.value.trim());
        newDirName.value = '';
        showCreateDir.value = false;
        message.success('目录创建成功');
        await fetchDirectories();
      } catch (e) {
        console.error(e);
        message.error('创建目录失败');
      }
    },
  });
}

async function handleDeleteDir(id: string) {
  Modal.confirm({
    title: '删除目录',
    content: '确定删除该目录？删除后目录下的文档将不再归类。',
    okText: '确定删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await deleteDirectory(scope.value, id);
        if (selectedDirId.value === id) selectedDirId.value = null;
        message.success('目录已删除');
        await fetchDirectories();
        await fetchDocuments();
      } catch (e) {
        console.error(e);
        message.error('删除目录失败');
      }
    },
  });
}

function handleUploadFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  uploadForm.value.file = target.files?.[0] || null;
}

async function handleUpload() {
  if (!uploadForm.value.file || !uploadForm.value.title || !uploadForm.value.directoryId) {
    message.warning('请填写完整信息并选择文件');
    return;
  }
  try {
    await uploadDocument(
      scope.value,
      uploadForm.value.file,
      uploadForm.value.directoryId,
      uploadForm.value.title,
    );
    showUpload.value = false;
    uploadForm.value = { title: '', directoryId: '', file: null };
    message.success('文档上传成功');
    await fetchDocuments();
  } catch (e) {
    console.error(e);
    message.error('上传文档失败');
  }
}

async function handleViewDoc(id: string) {
  try {
    const res = (await getDocument(scope.value, id)) as { data: Document };
    viewingDoc.value = res.data;
  } catch (e) {
    console.error(e);
    message.error('获取文档详情失败');
  }
}

async function handleDeleteDoc(id: string) {
  Modal.confirm({
    title: '删除文档',
    content: '确定删除该文档？删除后不可恢复。',
    okText: '确定删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await deleteDocument(scope.value, id);
        message.success('文档已删除');
        await fetchDocuments();
      } catch (e) {
        console.error(e);
        message.error('删除文档失败');
      }
    },
  });
}

async function handleReindex(id: string) {
  try {
    await reindexDocument(scope.value, id);
    message.success('重新索引成功');
  } catch (e) {
    console.error(e);
    message.error('重新索引失败');
  }
}

async function handlePublish(id: string) {
  try {
    await publishDocument(id);
    message.success('文档已发布');
    await fetchDocuments();
  } catch (e) {
    console.error(e);
    message.error('发布失败');
  }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = [];
    return;
  }
  searchLoading.value = true;
  try {
    const res = (await searchKnowledge(scope.value, searchQuery.value.trim())) as {
      data?: SearchResultItem[];
    };
    searchResults.value = res.data || [];
  } catch (e) {
    console.error(e);
    message.error('搜索失败');
  } finally {
    searchLoading.value = false;
  }
}

function handlePageChange(page: number) {
  currentPage.value = page;
  pageSkip.value = (page - 1) * pageSize;
  fetchDocuments();
}

function handleShowAllDocs() {
  selectedDirId.value = null;
}

watch(selectedDirId, () => {
  pageSkip.value = 0;
  currentPage.value = 1;
  fetchDocuments();
});

watch(scope, () => {
  selectedDirId.value = null;
  pageSkip.value = 0;
  currentPage.value = 1;
  searchResults.value = [];
  searchQuery.value = '';
  fetchDirectories();
  fetchDocuments();
});

onMounted(() => {
  fetchDirectories();
  fetchDocuments();
});
</script>

<template>
  <div class="p-4">
    <div class="mb-4">
      <h1 class="text-lg font-semibold">{{ isGlobal ? '全局知识库' : '我的知识库' }}</h1>
      <p class="text-sm text-gray-500">管理知识库文档，支持检索与向量化</p>
    </div>
    <!-- Search Bar -->
    <div class="mb-4">
      <Input.Search
        v-model:value="searchQuery"
        placeholder="搜索知识库..."
        size="large"
        @search="handleSearch"
      />
    </div>

    <!-- Search Results -->
    <Card v-if="searchResults.length" size="small" class="mb-4">
      <template #title>
        <div class="flex items-center justify-between">
          <span>搜索结果 ({{ searchResults.length }})</span>
          <Button type="link" @click="searchResults = []">关闭</Button>
        </div>
      </template>
      <Spin :spinning="searchLoading">
        <div class="max-h-[400px] overflow-y-auto">
          <div
            v-for="(r, idx) in searchResults"
            :key="idx"
            class="border-b border-gray-100 py-3 last:border-b-0"
          >
            <div class="mb-2 flex gap-2">
              <Tag color="blue">{{ r.document_title || '未知文档' }}</Tag>
              <Tag>相似度: {{ (r.score * 100).toFixed(1) }}%</Tag>
            </div>
            <p class="m-0 text-xs text-gray-500 leading-relaxed line-clamp-3">
              {{ r.chunk_text }}
            </p>
          </div>
        </div>
      </Spin>
    </Card>

    <!-- Main Content -->
    <Row :gutter="20">
      <!-- Left: Directory Panel -->
      <Col :span="6">
        <Card size="small" class="h-full">
          <template #title>
            <div class="flex items-center justify-between">
              <span>
                <FolderOutlined class="mr-1" />
                目录
              </span>
              <Button type="link" size="small" @click="showCreateDir = !showCreateDir">
                <FolderAddOutlined />
                新建
              </Button>
            </div>
          </template>

          <!-- Create Directory Inline -->
          <div v-if="showCreateDir" class="mb-3 border-b border-gray-100 pb-3">
            <div class="flex gap-2">
              <Input
                v-model:value="newDirName"
                placeholder="目录名称"
                size="small"
                @pressEnter="handleCreateDir"
              />
              <Button size="small" type="primary" @click="handleCreateDir">确定</Button>
            </div>
            <Button size="small" type="link" class="mt-1" @click="showCreateDir = false">
              取消
            </Button>
          </div>

          <!-- All Documents option -->
          <div
            class="flex cursor-pointer items-center justify-between rounded px-3 py-2 text-sm transition-colors"
            :class="selectedDirId === null ? 'bg-blue-50 font-medium text-blue-500' : 'text-gray-600 hover:bg-gray-50'"
            @click="handleShowAllDocs"
          >
            <span>全部文档</span>
            <Tag>{{ total }}</Tag>
          </div>

          <!-- Directory Tree -->
          <div v-if="directories.length" class="directory-tree">
            <div
              v-for="dir in directories"
              :key="dir.id"
              class="flex cursor-pointer items-center justify-between rounded px-3 py-2 text-sm transition-colors"
              :class="selectedDirId === dir.id ? 'bg-blue-50 font-medium text-blue-500' : 'text-gray-600 hover:bg-gray-50'"
              @click="selectedDirId = dir.id"
            >
              <span class="truncate">{{ dir.name }}</span>
              <Button
                type="link"
                danger
                size="small"
                @click.stop="handleDeleteDir(dir.id)"
              >
                <DeleteOutlined />
              </Button>
            </div>
          </div>

          <Empty v-if="!directories.length && !showCreateDir" :image="null" description="暂无目录" />
        </Card>
      </Col>

      <!-- Right: Documents Panel -->
      <Col :span="18">
        <Card size="small" class="h-full">
          <template #title>
            <div class="flex items-center justify-between">
              <span>文档列表</span>
              <Button type="primary" @click="showUpload = true">
                <UploadOutlined />
                上传文档
              </Button>
            </div>
          </template>

          <Table
            :columns="columns"
            :data-source="documents"
            :loading="loading"
            :pagination="false"
            :scroll="{ x: 800 }"
            row-key="id"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <Button type="link" @click="handleViewDoc(record.id)">
                  {{ record.title }}
                </Button>
              </template>
              <template v-if="column.key === 'status'">
                <Tag :color="statusColor(record.status)">
                  {{ statusLabel(record.status) }}
                </Tag>
              </template>
              <template v-if="column.key === 'created_at'">
                {{ formatDate(record.created_at) }}
              </template>
              <template v-if="column.key === 'action'">
                <Button type="link" size="small" @click="handleViewDoc(record.id)">
                  <EyeOutlined />
                  查看
                </Button>
                <Button type="link" size="small" @click="handleReindex(record.id)">
                  <ReloadOutlined />
                  重建索引
                </Button>
                <Button
                  v-if="isGlobal && record.status !== 'published'"
                  type="link"
                  size="small"
                  @click="handlePublish(record.id)"
                >
                  发布
                </Button>
                <Button type="link" danger size="small" @click="handleDeleteDoc(record.id)">
                  <DeleteOutlined />
                  删除
                </Button>
              </template>
            </template>
            <template #emptyText>
              <Empty :image="null" description="暂无文档" />
            </template>
          </Table>

          <!-- Pagination -->
          <div v-if="total > pageSize" class="flex justify-end pt-4">
            <Pagination
              v-model:current="currentPage"
              :page-size="pageSize"
              :total="total"
              @change="handlePageChange"
            />
          </div>
        </Card>
      </Col>
    </Row>

    <!-- Upload Modal -->
    <Modal
      v-model:open="showUpload"
      title="上传文档"
      :width="500"
      :mask-closable="false"
      destroy-on-close
      @cancel="showUpload = false"
    >
      <Form :model="uploadForm" layout="vertical">
        <Form.Item label="标题" required>
          <Input v-model:value="uploadForm.title" placeholder="请输入文档标题" allow-clear />
        </Form.Item>
        <Form.Item label="目录" required>
          <Select v-model:value="uploadForm.directoryId" placeholder="请选择目录">
            <Select.Option v-for="dir in directories" :key="dir.id" :value="dir.id">
              {{ dir.name }}
            </Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="文件" required>
          <input type="file" accept=".pdf,.doc,.docx,.txt,.md,.xlsx,.xls,.ppt,.pptx" @change="handleUploadFileChange" />
        </Form.Item>
      </Form>
      <template #footer>
        <Button @click="showUpload = false">取消</Button>
        <Button
          type="primary"
          :disabled="!uploadForm.title || !uploadForm.directoryId || !uploadForm.file"
          @click="handleUpload"
        >
          上传
        </Button>
      </template>
    </Modal>

    <!-- Document Detail Modal -->
    <Modal
      :open="!!viewingDoc"
      :title="viewingDoc?.title || '文档详情'"
      :width="700"
      destroy-on-close
      :footer="null"
      @cancel="viewingDoc = null"
    >
      <template v-if="viewingDoc">
        <Descriptions :column="3" bordered size="small" class="mb-4">
          <Descriptions.Item label="类型">{{ viewingDoc.file_type }}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag :color="statusColor(viewingDoc.status)">
              {{ statusLabel(viewingDoc.status) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {{ formatDate(viewingDoc.updated_at) }}
          </Descriptions.Item>
        </Descriptions>
        <div
          v-if="viewingDoc.content_text"
          class="max-h-[50vh] overflow-y-auto rounded-lg bg-gray-50 p-4 text-sm text-gray-600 leading-relaxed whitespace-pre-wrap"
        >
          {{ viewingDoc.content_text }}
        </div>
        <Empty v-else :image="null" description="暂无解析内容" />
      </template>
    </Modal>
  </div>
</template>
