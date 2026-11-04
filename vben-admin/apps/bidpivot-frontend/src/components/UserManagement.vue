<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { createUser, deleteUser, listUsers, resetPassword } from '#/api/admin';

import { Button, Input, message, Modal, Select, Space, Table, Tag } from 'ant-design-vue';

interface UserItem {
  id: string;
  username: string;
  role: string;
  total_tokens?: number;
  last_login?: string;
  created_at?: string;
}

const users = ref<UserItem[]>([]);
const total = ref(0);
const showCreate = ref(false);
const newUser = ref({ username: '', password: '', role: 'user' });

function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail || fallback;
}

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '角色', key: 'role', width: 120 },
  { title: '总 Token', key: 'total_tokens', width: 120 },
  { title: '最后登录', key: 'last_login', width: 180 },
  { title: '操作', key: 'action', width: 180 },
];

async function loadUsers() {
  try {
    const res = (await listUsers()) as { data: { items?: UserItem[]; total?: number } };
    users.value = res.data.items || [];
    total.value = res.data.total || 0;
  } catch (e) {
    console.error(e);
  }
}

async function handleCreate() {
  try {
    await createUser(newUser.value);
    showCreate.value = false;
    newUser.value = { username: '', password: '', role: 'user' };
    message.success('用户创建成功');
    await loadUsers();
  } catch (e: unknown) {
    message.error(errorDetail(e, '创建失败'));
  }
}

async function handleDelete(id: string) {
  Modal.confirm({
    title: '删除用户',
    content: '确定删除此用户？',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await deleteUser(id);
        users.value = users.value.filter((u) => u.id !== id);
        message.success('删除成功');
      } catch (e) {
        message.error('删除失败');
      }
    },
  });
}

async function handleResetPassword(userId: string) {
  Modal.confirm({
    title: '重置密码',
    content: '确定重置此用户的密码？',
    okText: '确定',
    cancelText: '取消',
    async onOk() {
      try {
        const res = (await resetPassword(userId)) as { data?: { password?: string } };
        const password = res.data?.password || '';
        Modal.success({
          title: '密码已重置',
          content: `新密码：${password}（请立即告知用户并提醒修改）`,
        });
      } catch (e) {
        message.error('重置失败');
      }
    },
  });
}

onMounted(loadUsers);
</script>

<template>
  <div>
    <div class="mb-4 flex justify-end">
      <Button type="primary" @click="showCreate = true">创建用户</Button>
    </div>

    <Table :columns="columns" :data-source="users" row-key="id" :pagination="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'role'">
          <Tag :color="record.role === 'admin' ? 'blue' : 'default'">
            {{ record.role === 'admin' ? '管理员' : '用户' }}
          </Tag>
        </template>
        <template v-if="column.key === 'total_tokens'">
          {{ record.total_tokens?.toLocaleString() || 0 }}
        </template>
        <template v-if="column.key === 'last_login'">
          {{ record.last_login ? new Date(record.last_login).toLocaleString() : '未登录' }}
        </template>
        <template v-if="column.key === 'action'">
          <Space>
            <Button type="link" size="small" @click="handleResetPassword(record.id)">
              重置密码
            </Button>
            <Button type="link" danger size="small" @click="handleDelete(record.id)">
              删除
            </Button>
          </Space>
        </template>
      </template>
    </Table>

    <Modal v-model:open="showCreate" title="创建用户" @ok="handleCreate">
      <div class="space-y-4 py-2">
        <Input v-model:value="newUser.username" placeholder="用户名" />
        <Input.Password v-model:value="newUser.password" placeholder="密码" />
        <Select v-model:value="newUser.role" style="width: 100%">
          <Select.Option value="user">用户</Select.Option>
          <Select.Option value="admin">管理员</Select.Option>
        </Select>
      </div>
    </Modal>
  </div>
</template>
