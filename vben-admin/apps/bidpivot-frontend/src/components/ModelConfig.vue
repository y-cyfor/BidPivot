<script setup lang="ts">
import type { ModelConfigCreate, ModelConfigUpdate } from '#/types/openapi';

import { onMounted, ref } from 'vue';

import { createModelConfig, getModelConfigs, updateModelConfig } from '#/api/admin';

import {
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Spin,
  Switch,
  Tag,
} from 'ant-design-vue';

interface ModelConfigItem {
  id: string;
  type: string;
  provider_name: string;
  api_base: string;
  model_name: string;
  parameters?: {
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
  } | null;
  is_active: boolean;
  _api_key: string;
}

const configs = ref<ModelConfigItem[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const creating = ref(false);
const newConfig = ref<ModelConfigCreate & { api_key: string }>({
  type: 'llm',
  provider_name: 'openai_compatible',
  api_base: '',
  api_key: '',
  model_name: '',
  parameters: { temperature: 0.3, top_p: 0.9, max_tokens: 4096 },
  is_active: true,
});

function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail || fallback;
}

async function loadConfigs() {
  loading.value = true;
  try {
    const res = (await getModelConfigs()) as { data?: ModelConfigItem[] };
    configs.value = (res.data || []).map((item) => ({ ...item, _api_key: '' }));
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  if (!newConfig.value.api_base || !newConfig.value.model_name) {
    message.warning('请填写 API 地址与模型名称');
    return;
  }
  creating.value = true;
  try {
    const payload = { ...newConfig.value };
    if (payload.type === 'embedding') {
      delete payload.parameters;
    }
    await createModelConfig(payload);
    message.success('创建成功');
    showCreate.value = false;
    newConfig.value = {
      type: 'llm',
      provider_name: 'openai_compatible',
      api_base: '',
      api_key: '',
      model_name: '',
      parameters: { temperature: 0.3, top_p: 0.9, max_tokens: 4096 },
      is_active: true,
    };
    await loadConfigs();
  } catch (e: unknown) {
    message.error(errorDetail(e, '创建失败'));
  } finally {
    creating.value = false;
  }
}

async function handleSave(config: ModelConfigItem) {
  try {
    const payload: ModelConfigUpdate = {
      api_base: config.api_base,
      model_name: config.model_name,
      parameters: config.parameters,
      is_active: config.is_active,
    };
    if (config._api_key) {
      payload.api_key = config._api_key;
    }
    await updateModelConfig(config.id, payload);
    config._api_key = '';
    message.success('保存成功');
    await loadConfigs();
  } catch (e) {
    message.error('保存失败');
  }
}

onMounted(loadConfigs);
</script>

<template>
  <div>
    <div class="mb-4 flex justify-end">
      <Button type="primary" @click="showCreate = true">新增模型配置</Button>
    </div>

    <Spin :spinning="loading">
      <div v-for="config in configs" :key="config.id" class="mb-4">
        <Card>
          <template #title>
            <div class="flex items-center justify-between">
              <div>
                <span class="font-medium">{{ config.provider_name }}</span>
                <Tag class="ml-2">{{ config.type }}</Tag>
              </div>
              <Tag :color="config.is_active ? 'success' : 'default'">
                {{ config.is_active ? '启用' : '禁用' }}
              </Tag>
            </div>
          </template>

          <Row :gutter="16">
            <Col :span="12">
              <div class="mb-2 text-sm font-medium text-gray-700">API 地址</div>
              <Input v-model:value="config.api_base" />
            </Col>
            <Col :span="12">
              <div class="mb-2 text-sm font-medium text-gray-700">模型名称</div>
              <Input v-model:value="config.model_name" />
            </Col>
          </Row>

          <Row :gutter="16" class="mt-4">
            <Col :span="16">
              <div class="mb-2 text-sm font-medium text-gray-700">API Key</div>
              <Input.Password
                v-model:value="config._api_key"
                placeholder="留空则不修改"
                autocomplete="new-password"
              />
            </Col>
            <Col :span="8">
              <div class="mb-2 text-sm font-medium text-gray-700">启用</div>
              <Switch v-model:checked="config.is_active" />
            </Col>
          </Row>

          <Row v-if="config.parameters" :gutter="16" class="mt-4">
            <Col :span="8">
              <div class="mb-2 text-sm font-medium text-gray-700">温度</div>
              <InputNumber
                v-model:value="config.parameters.temperature"
                :step="0.1"
                :min="0"
                :max="2"
                style="width: 100%"
              />
            </Col>
            <Col :span="8">
              <div class="mb-2 text-sm font-medium text-gray-700">Top-p</div>
              <InputNumber
                v-model:value="config.parameters.top_p"
                :step="0.1"
                :min="0"
                :max="1"
                style="width: 100%"
              />
            </Col>
            <Col :span="8">
              <div class="mb-2 text-sm font-medium text-gray-700">最大 Token</div>
              <InputNumber v-model:value="config.parameters.max_tokens" style="width: 100%" />
            </Col>
          </Row>

          <div class="mt-4 flex justify-end">
            <Button type="primary" @click="handleSave(config)">保存</Button>
          </div>
        </Card>
      </div>

      <div v-if="!loading && configs.length === 0" class="py-8 text-center text-gray-400">
        暂无模型配置，请点击右上角新增
      </div>
    </Spin>

    <Modal
      v-model:open="showCreate"
      title="新增模型配置"
      :confirm-loading="creating"
      :mask-closable="false"
      ok-text="创建"
      cancel-text="取消"
      @ok="handleCreate"
    >
      <div class="space-y-3 py-2">
        <Select v-model:value="newConfig.type" style="width: 100%">
          <Select.Option value="llm">大语言模型（LLM）</Select.Option>
          <Select.Option value="embedding">向量模型（Embedding）</Select.Option>
        </Select>
        <Input v-model:value="newConfig.provider_name" placeholder="Provider，如 openai_compatible" />
        <Input v-model:value="newConfig.api_base" placeholder="API 地址，如 http://localhost:11434/v1" />
        <Input v-model:value="newConfig.model_name" placeholder="模型名称，如 qwen2.5:72b" />
        <Input.Password
          v-model:value="newConfig.api_key"
          placeholder="API Key（本地模型可留空）"
          autocomplete="new-password"
        />
      </div>
    </Modal>
  </div>
</template>
