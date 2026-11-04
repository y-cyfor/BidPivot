<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import { getDashboardStats } from '#/api/dashboard';

import {
  BookOutlined,
  EditOutlined,
  FileTextOutlined,
  GlobalOutlined,
} from '@ant-design/icons-vue';
import { Card, Col, Row, Statistic } from 'ant-design-vue';

const router = useRouter();
const stats = ref({
  projects: 0,
  personal_documents: 0,
  global_documents: 0,
  month_projects: 0,
});

onMounted(async () => {
  try {
    const res = (await getDashboardStats()) as {
      data: {
        projects: number;
        personal_documents: number;
        global_documents: number;
        month_projects: number;
      };
    };
    stats.value = res.data;
  } catch {
    // Keep zeros when the dashboard endpoint is unavailable.
  }
});

const quickLinks = [
  { title: '创作标书', icon: EditOutlined, path: '/bid/create' },
  { title: '我的标书', icon: FileTextOutlined, path: '/bids' },
  { title: '我的知识库', icon: BookOutlined, path: '/knowledge/personal' },
  { title: '全局知识库', icon: GlobalOutlined, path: '/knowledge/global' },
];
</script>

<template>
  <Page title="首页" description="极智标枢-标书智造平台">
    <!-- Stats -->
    <Row :gutter="16" class="mb-6">
      <Col :span="6">
        <Card hoverable>
          <Statistic title="我的标书" :value="stats.projects" />
        </Card>
      </Col>
      <Col :span="6">
        <Card hoverable>
          <Statistic title="知识库文档" :value="stats.personal_documents" />
        </Card>
      </Col>
      <Col :span="6">
        <Card hoverable>
          <Statistic title="全局知识库" :value="stats.global_documents" />
        </Card>
      </Col>
      <Col :span="6">
        <Card hoverable>
          <Statistic title="本月生成" :value="stats.month_projects" />
        </Card>
      </Col>
    </Row>

    <!-- Quick Links -->
    <Card title="快捷入口">
      <Row :gutter="16">
        <Col v-for="link in quickLinks" :key="link.path" :span="6">
          <Card
            hoverable
            class="text-center cursor-pointer transition-transform hover:-translate-y-1"
            @click="router.push(link.path)"
          >
            <component :is="link.icon" class="text-4xl text-blue-500" />
            <div class="mt-2 text-sm">{{ link.title }}</div>
          </Card>
        </Col>
      </Row>
    </Card>
  </Page>
</template>
