<script setup lang="ts">
import { ref } from 'vue';

import { exportProject } from '#/api/bid';

import { Button, Dropdown, Input, InputNumber, message, Modal } from 'ant-design-vue';
import { DownloadOutlined, SettingOutlined } from '@ant-design/icons-vue';

const props = defineProps<{ projectId: string }>();
const exporting = ref(false);
const showSettings = ref(false);
const template = ref({
  font_name: 'SimSun',
  font_size: 12,
  margin_top: 2.54,
  margin_bottom: 2.54,
  margin_left: 3.17,
  margin_right: 3.17,
});

async function handleExport(format: 'docx' | 'pdf' | 'md') {
  exporting.value = true;
  try {
    const templateJson = format === 'md' ? undefined : JSON.stringify(template.value);
    const res = (await exportProject(props.projectId, format, templateJson)) as unknown as Blob;
    const url = window.URL.createObjectURL(new Blob([res]));
    const a = document.createElement('a');
    a.href = url;
    a.download = `标书.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch {
    message.error('导出失败');
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <Dropdown>
    <Button :loading="exporting">
      <DownloadOutlined />
      {{ exporting ? '导出中...' : '导出' }}
    </Button>
    <template #overlay>
      <Dropdown.Menu>
        <Dropdown.Item @click="handleExport('docx')">导出为 DOCX</Dropdown.Item>
        <Dropdown.Item @click="handleExport('pdf')">导出为 PDF</Dropdown.Item>
        <Dropdown.Item @click="handleExport('md')">导出为 Markdown</Dropdown.Item>
        <Dropdown.Item @click="showSettings = true">
          <SettingOutlined />
          排版设置
        </Dropdown.Item>
      </Dropdown.Menu>
    </template>
  </Dropdown>

  <Modal v-model:open="showSettings" title="导出排版设置" :footer="null" :width="520">
    <div class="space-y-4 py-2">
      <div>
        <div class="mb-1 text-sm text-gray-700">正文字体</div>
        <Input v-model:value="template.font_name" placeholder="SimSun" />
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <div class="mb-1 text-sm text-gray-700">字号（pt）</div>
          <InputNumber v-model:value="template.font_size" :min="8" :max="24" style="width: 100%" />
        </div>
        <div>
          <div class="mb-1 text-sm text-gray-700">上边距（cm）</div>
          <InputNumber v-model:value="template.margin_top" :step="0.1" style="width: 100%" />
        </div>
        <div>
          <div class="mb-1 text-sm text-gray-700">下边距（cm）</div>
          <InputNumber v-model:value="template.margin_bottom" :step="0.1" style="width: 100%" />
        </div>
        <div>
          <div class="mb-1 text-sm text-gray-700">左边距（cm）</div>
          <InputNumber v-model:value="template.margin_left" :step="0.1" style="width: 100%" />
        </div>
        <div>
          <div class="mb-1 text-sm text-gray-700">右边距（cm）</div>
          <InputNumber v-model:value="template.margin_right" :step="0.1" style="width: 100%" />
        </div>
      </div>
      <div class="flex justify-end gap-2">
        <Button @click="showSettings = false">关闭</Button>
        <Button type="primary" :loading="exporting" @click="handleExport('docx')">
          按此设置导出 DOCX
        </Button>
      </div>
    </div>
  </Modal>
</template>
