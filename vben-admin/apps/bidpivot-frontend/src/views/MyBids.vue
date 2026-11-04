<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import { deleteProject, listProjects } from '#/api/bid';

import {
  Button,
  Card,
  Col,
  Input,
  message,
  Modal,
  Pagination,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
} from 'ant-design-vue';

const router = useRouter();

interface ProjectRow {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

const projects = ref<ProjectRow[]>([]);
const total = ref(0);
const loading = ref(false);
const searchQuery = ref('');
const statusFilter = ref<string | undefined>(undefined);
const pageSkip = ref(0);
const pageSize = 20;
const currentPage = ref(1);

const statusMap: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  outline_firming: { label: '大纲确认中', color: 'processing' },
  generating: { label: '生成中', color: 'warning' },
  completed: { label: '已完成', color: 'success' },
  partial: { label: '部分完成', color: 'warning' },
  cancelled: { label: '已取消', color: 'default' },
  failed: { label: '失败', color: 'error' },
};

const filteredProjects = computed(() => {
  let list = projects.value;
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter((p) => p.title.toLowerCase().includes(q));
  }
  if (statusFilter.value) {
    list = list.filter((p) => p.status === statusFilter.value);
  }
  return list;
});

const stats = computed(() => ({
  total: total.value,
  completed: projects.value.filter((p) => p.status === 'completed').length,
  generating: projects.value.filter((p) => p.status === 'generating').length,
}));

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '状态', key: 'status', width: 140 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 280, fixed: 'right' as const },
];

async function loadProjects() {
  loading.value = true;
  try {
    const res = await listProjects(pageSkip.value, pageSize);
    projects.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch {
    message.error('加载标书列表失败');
  } finally {
    loading.value = false;
  }
}

async function handleDelete(id: string) {
  Modal.confirm({
    title: '删除标书',
    content: '确定删除此标书？此操作不可恢复。',
    okText: '删除',
    cancelText: '取消',
    okType: 'danger',
    async onOk() {
      try {
        await deleteProject(id);
        projects.value = projects.value.filter((p) => p.id !== id);
        message.success('删除成功');
      } catch {
        message.error('删除失败');
      }
    },
  });
}

onMounted(loadProjects);
</script>

<template>
  <Page title="我的标书" description="管理您创建的所有标书">
    <template #extra>
      <Button type="primary" @click="router.push('/bid/create')">
        新建标书
      </Button>
    </template>

    <!-- Stats -->
    <Row :gutter="16" class="mb-4">
      <Col :span="8">
        <Card>
          <Statistic title="总数" :value="stats.total" />
        </Card>
      </Col>
      <Col :span="8">
        <Card>
          <Statistic title="已完成" :value="stats.completed" />
        </Card>
      </Col>
      <Col :span="8">
        <Card>
          <Statistic title="生成中" :value="stats.generating" />
        </Card>
      </Col>
    </Row>

    <!-- Search & Filter -->
    <Row :gutter="12" class="mb-4">
      <Col :span="16">
        <Input v-model:value="searchQuery" placeholder="搜索标书..." allow-clear />
      </Col>
      <Col :span="8">
        <Select
          v-model:value="statusFilter"
          placeholder="全部状态"
          allow-clear
          style="width: 100%"
        >
          <Select.Option value="draft">草稿</Select.Option>
          <Select.Option value="outline_firming">大纲确认中</Select.Option>
          <Select.Option value="generating">生成中</Select.Option>
          <Select.Option value="completed">已完成</Select.Option>
          <Select.Option value="failed">失败</Select.Option>
        </Select>
      </Col>
    </Row>

    <!-- Table -->
    <Card>
      <Table
        :columns="columns"
        :data-source="filteredProjects"
        :loading="loading"
        :pagination="false"
        row-key="id"
        :scroll="{ x: 900 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <Tag :color="statusMap[record.status]?.color ?? 'default'">
              {{ statusMap[record.status]?.label ?? record.status }}
            </Tag>
          </template>
          <template v-if="column.key === 'created_at'">
            {{ new Date(record.created_at).toLocaleString() }}
          </template>
          <template v-if="column.key === 'action'">
            <Space>
              <Button type="link" size="small" @click="router.push(`/bid/${record.id}`)">
                查看
              </Button>
              <Button
                v-if="record.status === 'completed'"
                type="link"
                size="small"
                @click="router.push(`/bid/${record.id}`)"
              >
                继续对话
              </Button>
              <Button type="link" danger size="small" @click="handleDelete(record.id)">
                删除
              </Button>
            </Space>
          </template>
        </template>
      </Table>

      <div v-if="total > pageSize" class="flex justify-end pt-4">
        <Pagination
          v-model:current="currentPage"
          :page-size="pageSize"
          :total="total"
          show-size-changer
          @change="(page: number) => { pageSkip = (page - 1) * pageSize; loadProjects(); }"
        />
      </div>
    </Card>
  </Page>
</template>
