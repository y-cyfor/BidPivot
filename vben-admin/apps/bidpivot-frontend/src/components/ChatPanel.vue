<script setup lang="ts">
import { nextTick, ref } from 'vue';

import { sendConversationMessage } from '#/api/conversation';

import { Button, Card, Input } from 'ant-design-vue';

const props = defineProps<{
  projectId: string;
  currentHtml: string;
  selectedText?: string;
}>();

const emit = defineEmits<{
  contentUpdate: [html: string];
}>();

interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  timestamp: Date;
}

const messages = ref<ChatMessage[]>([]);
const instruction = ref('');
const sending = ref(false);
const streamingPreview = ref('');
const messagesContainer = ref<HTMLElement | null>(null);

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

async function handleSend() {
  if (!instruction.value.trim() || sending.value) return;

  const userMsg: ChatMessage = {
    role: 'user',
    content: instruction.value,
    timestamp: new Date(),
  };
  messages.value.push(userMsg);
  scrollToBottom();

  const currentInstruction = instruction.value;
  instruction.value = '';
  sending.value = true;
  streamingPreview.value = '';

  try {
    const res = (await sendConversationMessage(
      props.projectId,
      currentInstruction,
      props.currentHtml,
      props.selectedText,
    )) as unknown as string | { data?: string };

    const text = typeof res === 'string' ? res : res.data || '';
    const lines = text.split('\n');
    let modifiedHtml = '';
    let streamed = '';
    let errorMessage = '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'token') {
            streamed += data.content || '';
            streamingPreview.value = streamed;
          } else if (data.type === 'content') {
            modifiedHtml = data.content;
          } else if (data.type === 'error') {
            errorMessage = data.content || '修改失败';
          }
        } catch {
          // ignore malformed SSE frames
        }
      }
    }

    if (errorMessage) {
      messages.value.push({
        role: 'assistant',
        content: errorMessage,
        timestamp: new Date(),
      });
    } else if (modifiedHtml) {
      emit('contentUpdate', modifiedHtml);
      messages.value.push({
        role: 'assistant',
        content: '已完成修改',
        timestamp: new Date(),
      });
    } else {
      messages.value.push({
        role: 'assistant',
        content: '修改完成，但未返回新内容',
        timestamp: new Date(),
      });
    }
  } catch (e: unknown) {
    messages.value.push({
      role: 'assistant',
      content: `修改失败: ${(e as Error).message || '未知错误'}`,
      timestamp: new Date(),
    });
  } finally {
    sending.value = false;
    scrollToBottom();
  }
}
</script>

<template>
  <Card title="AI 对话修改" class="flex h-96 flex-col">
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4">
      <div v-if="!messages.length" class="py-8 text-center text-sm text-gray-400">
        输入修改指令，AI 将帮你修改标书内容
      </div>
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="mb-3 flex"
        :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[80%] rounded-lg px-3 py-2 text-sm"
          :class="
            msg.role === 'user'
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-800'
          "
        >
          {{ msg.content }}
        </div>
      </div>
      <div v-if="streamingPreview" class="mb-3 flex justify-start">
        <div class="max-w-[80%] whitespace-pre-wrap rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-800">
          {{ streamingPreview }}
        </div>
      </div>
    </div>

    <div class="border-t p-4">
      <div class="flex gap-2">
        <Input
          v-model:value="instruction"
          placeholder="输入修改指令..."
          :disabled="sending"
          @pressEnter="handleSend"
        />
        <Button type="primary" :loading="sending" :disabled="!instruction.trim()" @click="handleSend">
          发送
        </Button>
      </div>
      <p v-if="selectedText" class="mt-1 text-xs text-gray-500">
        已选中 {{ selectedText.length }} 个字
      </p>
    </div>
  </Card>
</template>
