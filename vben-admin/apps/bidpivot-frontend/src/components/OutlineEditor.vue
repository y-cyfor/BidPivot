<script setup lang="ts">
import { computed, ref } from 'vue';

import { Button, Card, Checkbox, Col, Input, Row, Select, Tag } from 'ant-design-vue';
import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons-vue';

interface OutlineSection {
  id: string;
  title: string;
  description: string;
  agent_role: string;
  dependencies: string[];
}

const props = defineProps<{
  modelValue: { sections: OutlineSection[] };
}>();

const emit = defineEmits<{
  'update:modelValue': [value: { sections: OutlineSection[] }];
}>();

const selectedId = ref<string | null>(null);

const sections = computed({
  get: () => props.modelValue.sections || [],
  set: (val) => emit('update:modelValue', { sections: val }),
});

const selectedSection = computed<OutlineSection | null>(
  () => sections.value.find((s) => s.id === selectedId.value) || null,
);

const agentRoles = ['商务报价', '技术方案', '实施计划', '售后服务', '资质合规'];

const roleColors: Record<string, string> = {
  商务报价: 'green',
  技术方案: 'blue',
  实施计划: 'orange',
  售后服务: 'purple',
  资质合规: 'default',
};

function selectSection(id: string) {
  selectedId.value = id;
}

function updateSelected(key: string, value: unknown) {
  if (!selectedSection.value) return;
  const idx = sections.value.findIndex((s) => s.id === selectedId.value);
  if (idx === -1) return;
  const updated = [...sections.value];
  const item = updated[idx];
  if (item) {
    updated[idx] = { ...item, [key]: value };
    sections.value = updated;
  }
}

function addSection() {
  const newId = `s${Date.now()}`;
  sections.value = [
    ...sections.value,
    {
      id: newId,
      title: '新段落',
      description: '',
      agent_role: '技术方案',
      dependencies: [],
    },
  ];
  selectedId.value = newId;
}

function removeSection(id: string) {
  sections.value = sections.value.filter((s) => s.id !== id);
  sections.value = sections.value.map((s) => ({
    ...s,
    dependencies: s.dependencies.filter((d) => d !== id),
  }));
  if (selectedId.value === id) selectedId.value = null;
}

function toggleDependency(targetId: string) {
  if (!selectedSection.value) return;
  const current = selectedSection.value.dependencies;
  const deps = current.includes(targetId)
    ? current.filter((d) => d !== targetId)
    : [...current, targetId];
  updateSelected('dependencies', deps);
}

function moveSection(id: string, direction: 'down' | 'up') {
  const idx = sections.value.findIndex((s) => s.id === id);
  if (idx === -1) return;
  const newIdx = direction === 'up' ? idx - 1 : idx + 1;
  if (newIdx < 0 || newIdx >= sections.value.length) return;
  const updated = [...sections.value];
  const item1 = updated[idx];
  const item2 = updated[newIdx];
  if (item1 && item2) {
    updated[idx] = item2;
    updated[newIdx] = item1;
    sections.value = updated;
  }
}
</script>

<template>
  <div class="h-[500px]">
    <Row :gutter="16" class="h-full">
      <!-- Left: Section List -->
      <Col :span="8" class="h-full">
        <Card size="small" class="flex h-full flex-col">
          <template #title>
            <div class="flex items-center justify-between">
              <span class="text-sm font-semibold">大纲结构</span>
              <Button type="link" size="small" @click="addSection">
                <PlusOutlined />
                添加段落
              </Button>
            </div>
          </template>

          <div class="flex-1 overflow-y-auto">
            <div
              v-for="(section, idx) in sections"
              :key="section.id"
              class="group flex cursor-pointer items-center gap-2 rounded px-3 py-2 transition-colors"
              :class="
                selectedId === section.id
                  ? 'bg-blue-50 ring-1 ring-blue-300'
                  : 'hover:bg-gray-50'
              "
              @click="selectSection(section.id)"
            >
              <span class="w-6 text-xs text-gray-400">{{ idx + 1 }}</span>
              <span class="flex-1 truncate text-sm">{{ section.title }}</span>
              <Tag :color="roleColors[section.agent_role] || 'default'" class="text-xs">
                {{ section.agent_role }}
              </Tag>
              <div class="hidden gap-1 group-hover:flex">
                <Button
                  type="text"
                  size="small"
                  @click.stop="moveSection(section.id, 'up')"
                >
                  <ArrowUpOutlined />
                </Button>
                <Button
                  type="text"
                  size="small"
                  @click.stop="moveSection(section.id, 'down')"
                >
                  <ArrowDownOutlined />
                </Button>
                <Button
                  type="text"
                  danger
                  size="small"
                  @click.stop="removeSection(section.id)"
                >
                  <DeleteOutlined />
                </Button>
              </div>
            </div>

            <div
              v-if="!sections.length"
              class="py-8 text-center text-sm text-gray-400"
            >
              点击"添加段落"开始编辑大纲
            </div>
          </div>
        </Card>
      </Col>

      <!-- Right: Edit Section -->
      <Col :span="16" class="h-full">
        <Card size="small" class="flex h-full flex-col">
          <div v-if="selectedSection" class="flex-1 overflow-y-auto">
            <div class="mb-4 text-sm font-semibold">编辑段落</div>

            <div class="mb-4">
              <div class="mb-1 text-sm font-medium text-gray-700">标题</div>
              <Input
                :value="selectedSection.title"
                @input="
                  updateSelected('title', ($event.target as HTMLInputElement).value)
                "
              />
            </div>

            <div class="mb-4">
              <div class="mb-1 text-sm font-medium text-gray-700">描述</div>
              <Input.TextArea
                :value="selectedSection.description"
                :rows="4"
                @input="
                  updateSelected(
                    'description',
                    ($event.target as HTMLTextAreaElement).value,
                  )
                "
              />
            </div>

            <div class="mb-4">
              <div class="mb-1 text-sm font-medium text-gray-700">Agent 角色</div>
              <Select
                :value="selectedSection.agent_role"
                style="width: 100%"
                @change="(val: unknown) => updateSelected('agent_role', val)"
              >
                <Select.Option v-for="role in agentRoles" :key="role" :value="role">
                  {{ role }}
                </Select.Option>
              </Select>
            </div>

            <div>
              <div class="mb-1 text-sm font-medium text-gray-700">依赖段落</div>
              <div class="max-h-32 overflow-y-auto">
                <div
                  v-for="s in sections.filter((s) => s.id !== selectedSection!.id)"
                  :key="s.id"
                  class="py-1"
                >
                  <Checkbox
                    :checked="selectedSection.dependencies.includes(s.id)"
                    @change="toggleDependency(s.id)"
                  >
                    {{ s.title }}
                  </Checkbox>
                </div>
              </div>
            </div>
          </div>

          <div
            v-else
            class="flex h-full items-center justify-center text-gray-400"
          >
            选择左侧段落进行编辑
          </div>
        </Card>
      </Col>
    </Row>
  </div>
</template>
