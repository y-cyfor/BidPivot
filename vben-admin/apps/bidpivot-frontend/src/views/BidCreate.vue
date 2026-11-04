<script setup lang="ts">
import { ref } from 'vue';
import type { UploadFile } from 'ant-design-vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import { createProject } from '#/api/bid';
import { uploadFile } from '#/api/files';

import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  message,
  Result,
  Select,
  Steps,
  Switch,
  Tag,
  UploadDragger,
} from 'ant-design-vue';
import { InboxOutlined } from '@ant-design/icons-vue';

const router = useRouter();
const currentStep = ref(0);
const loading = ref(false);

const form = ref({
  title: '',
  industry: '',
  industryTags: '',
  useGlobalKnowledge: true,
  usePersonalKnowledge: true,
});

const fileList = ref<UploadFile[]>([]);

function nextStep() {
  if (currentStep.value === 0 && fileList.value.length === 0) {
    message.warning('请先上传招标文件');
    return;
  }
  if (currentStep.value === 1) {
    if (!form.value.title.trim()) {
      message.warning('请输入标书标题');
      return;
    }
  }
  if (currentStep.value < 3) {
    currentStep.value++;
  }
}

function prevStep() {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
}

const industryOptions = [
  { label: 'IT/互联网', value: 'it' },
  { label: '建筑工程', value: 'construction' },
  { label: '政府采购', value: 'government' },
  { label: '医疗健康', value: 'healthcare' },
  { label: '教育培训', value: 'education' },
  { label: '其他', value: 'other' },
];

async function handleSubmit() {
  loading.value = true;
  try {
    const res = await createProject({
      title: form.value.title,
      industry_tags: form.value.industryTags
        ? form.value.industryTags
            .split(',')
            .map((t: string) => t.trim())
            .filter(Boolean)
        : form.value.industry
          ? [form.value.industry]
          : [],
    });
    const projectId = res.data?.id;
    if (!projectId) throw new Error('创建结果缺少项目 ID');
    for (const file of fileList.value) {
      if (file.originFileObj) {
        await uploadFile(file.originFileObj as unknown as File, projectId, 'bid');
      }
    }
    message.success('标书创建成功');
    router.push(`/bid/${projectId}`);
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    message.error(detail || '创建失败，请重试');
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Page title="创作标书" description="上传招标文件，配置选项，开始生成标书">
    <Card>
      <Steps :current="currentStep" status="process" class="mb-8">
        <Steps.Step title="上传招标文件" />
        <Steps.Step title="配置选项" />
        <Steps.Step title="确认信息" />
        <Steps.Step title="开始生成" />
      </Steps>

      <div class="min-h-[300px]">
        <!-- Step 1: Upload bid documents -->
        <div v-if="currentStep === 0">
          <UploadDragger
            v-model:fileList="fileList"
            :before-upload="() => false"
            multiple
            :max-count="5"
            accept=".pdf,.docx,.txt,.md"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p class="ant-upload-hint">
              支持 PDF、Word、TXT、Markdown 文件，最多 5 个文件
            </p>
          </UploadDragger>
        </div>

        <!-- Step 2: Configuration options -->
        <div v-if="currentStep === 1">
          <Form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
            <Form.Item label="标书标题" required>
              <Input
                v-model:value="form.title"
                placeholder="请输入标书标题"
                :maxlength="200"
                show-count
              />
            </Form.Item>
            <Form.Item label="行业类型">
              <Select v-model:value="form.industry" placeholder="请选择行业" allow-clear>
                <Select.Option
                  v-for="item in industryOptions"
                  :key="item.value"
                  :value="item.value"
                >
                  {{ item.label }}
                </Select.Option>
              </Select>
            </Form.Item>
            <Form.Item label="行业标签">
              <Input
                v-model:value="form.industryTags"
                placeholder="多个标签用逗号分隔，如：IT, 建筑, 医疗"
              />
            </Form.Item>
            <Form.Item label="使用全局知识库">
              <Switch v-model:checked="form.useGlobalKnowledge" />
              <span class="ml-3 text-xs text-gray-400">
                启用后将从全局知识库检索相关内容辅助生成
              </span>
            </Form.Item>
            <Form.Item label="使用个人知识库">
              <Switch v-model:checked="form.usePersonalKnowledge" />
              <span class="ml-3 text-xs text-gray-400">
                启用后将从您的个人知识库检索相关内容辅助生成
              </span>
            </Form.Item>
          </Form>
        </div>

        <!-- Step 3: Confirm information -->
        <div v-if="currentStep === 2">
          <Descriptions title="标书信息确认" :column="1" bordered>
            <Descriptions.Item label="标书标题">{{ form.title }}</Descriptions.Item>
            <Descriptions.Item label="行业类型">
              {{ industryOptions.find((o) => o.value === form.industry)?.label || '未选择' }}
            </Descriptions.Item>
            <Descriptions.Item label="行业标签">
              {{ form.industryTags || '无' }}
            </Descriptions.Item>
            <Descriptions.Item label="上传文件数">
              {{ fileList.length }} 个
            </Descriptions.Item>
            <Descriptions.Item label="全局知识库">
              <Tag :color="form.useGlobalKnowledge ? 'success' : 'default'">
                {{ form.useGlobalKnowledge ? '已启用' : '未启用' }}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="个人知识库">
              <Tag :color="form.usePersonalKnowledge ? 'success' : 'default'">
                {{ form.usePersonalKnowledge ? '已启用' : '未启用' }}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </div>

        <!-- Step 4: Start generation -->
        <div v-if="currentStep === 3">
          <Result
            status="success"
            title="配置完成"
            sub-title="确认无误后，点击「开始生成」按钮启动标书自动生成流程"
          >
            <template #extra>
              <Button type="primary" size="large" :loading="loading" @click="handleSubmit">
                开始生成
              </Button>
            </template>
          </Result>
        </div>
      </div>

      <div class="mt-8 text-center">
        <Button v-if="currentStep > 0" class="mr-4" @click="prevStep">上一步</Button>
        <Button v-if="currentStep < 3" type="primary" @click="nextStep">下一步</Button>
      </div>
    </Card>
  </Page>
</template>
