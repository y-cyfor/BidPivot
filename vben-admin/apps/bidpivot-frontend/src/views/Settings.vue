<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Card, Tabs } from 'ant-design-vue';

import AuditLog from '#/components/AuditLog.vue';
import ModelConfig from '#/components/ModelConfig.vue';
import UserManagement from '#/components/UserManagement.vue';

const activeTab = ref('model');
</script>

<template>
  <Page title="系统设置" description="模型配置、用户管理与审计日志">
    <Card>
      <Tabs v-model:activeKey="activeTab">
        <Tabs.TabPane key="model" tab="模型配置">
          <ModelConfig />
        </Tabs.TabPane>
        <Tabs.TabPane key="users" tab="用户管理">
          <UserManagement />
        </Tabs.TabPane>
        <Tabs.TabPane key="audit" tab="审计日志">
          <AuditLog />
        </Tabs.TabPane>
      </Tabs>
    </Card>
  </Page>
</template>
