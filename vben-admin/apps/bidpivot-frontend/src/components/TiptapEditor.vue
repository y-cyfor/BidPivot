<script setup lang="ts">
import { watch, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Highlight from '@tiptap/extension-highlight'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import { Modal } from 'ant-design-vue'

const TraceHighlight = Highlight.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      source: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute('data-source'),
        renderHTML: (attributes: Record<string, any>) =>
          attributes.source ? { 'data-source': attributes.source } : {},
      },
    }
  },
})

const props = withDefaults(defineProps<{
  modelValue: string
  editable?: boolean
}>(), {
  editable: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit.configure({ heading: { levels: [1, 2, 3, 4] } }),
    TraceHighlight.configure({ multicolor: false }),
    Placeholder.configure({ placeholder: '开始编辑标书内容...' }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    Underline,
  ],
  onUpdate: ({ editor }) => {
    emit('update:modelValue', editor.getHTML())
  },
})

function handleEditorClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  const mark = target?.closest('mark[data-source]') as HTMLElement | null
  if (!mark) return
  Modal.info({
    title: '数字来源',
    content: mark.getAttribute('data-source') || '未标注来源',
  })
}


watch(() => props.modelValue, (newVal) => {
  if (editor.value && newVal !== editor.value.getHTML()) {
    editor.value.commands.setContent(newVal, { emitUpdate: false })
  }
})

watch(() => props.editable, (newVal) => {
  editor.value?.setEditable(newVal)
})

onBeforeUnmount(() => editor.value?.destroy())

function toggleBold() { editor.value?.chain().focus().toggleBold().run() }
function toggleItalic() { editor.value?.chain().focus().toggleItalic().run() }
function toggleUnderline() { editor.value?.chain().focus().toggleUnderline().run() }
function toggleStrike() { editor.value?.chain().focus().toggleStrike().run() }
function toggleHighlight() { editor.value?.chain().focus().toggleHighlight().run() }
function setHeading(level: 1 | 2 | 3 | 4) { editor.value?.chain().focus().toggleHeading({ level }).run() }
function toggleBulletList() { editor.value?.chain().focus().toggleBulletList().run() }
function toggleOrderedList() { editor.value?.chain().focus().toggleOrderedList().run() }
function setTextAlign(align: 'left' | 'center' | 'right') { editor.value?.chain().focus().setTextAlign(align).run() }
function undo() { editor.value?.chain().focus().undo().run() }
function redo() { editor.value?.chain().focus().redo().run() }
function isActive(name: string) { return editor.value?.isActive(name) ?? false }
function isActiveAlign(align: string) { return editor.value?.isActive({ textAlign: align }) ?? false }
</script>

<template>
  <div class="tiptap-editor border rounded-lg overflow-hidden">
    <div v-if="editable" class="flex flex-wrap items-center gap-1 p-2 bg-gray-50 border-b">
      <button @click="toggleBold" :class="['p-1.5 rounded hover:bg-gray-200', isActive('bold') ? 'bg-gray-200' : '']" title="粗体">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/><path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/></svg>
      </button>
      <button @click="toggleItalic" :class="['p-1.5 rounded hover:bg-gray-200', isActive('italic') ? 'bg-gray-200' : '']" title="斜体">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="4" x2="10" y2="4"/><line x1="14" y1="20" x2="5" y2="20"/><line x1="15" y1="4" x2="9" y2="20"/></svg>
      </button>
      <button @click="toggleUnderline" :class="['p-1.5 rounded hover:bg-gray-200', isActive('underline') ? 'bg-gray-200' : '']" title="下划线">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3v7a6 6 0 0 0 6 6 6 6 0 0 0 6-6V3"/><line x1="4" y1="21" x2="20" y2="21"/></svg>
      </button>
      <button @click="toggleStrike" :class="['p-1.5 rounded hover:bg-gray-200', isActive('strike') ? 'bg-gray-200' : '']" title="删除线">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4H9a3 3 0 0 0-3 3v0a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3v0a3 3 0 0 1-3 3H8"/><line x1="4" y1="12" x2="20" y2="12"/></svg>
      </button>
      <div class="w-px h-5 bg-gray-300 mx-1"></div>
      <select @change="setHeading(Number(($event.target as HTMLSelectElement).value) as 1|2|3|4)" class="text-sm border rounded px-2 py-1 bg-white">
        <option value="" disabled selected>标题</option>
        <option value="1">H1</option><option value="2">H2</option><option value="3">H3</option><option value="4">H4</option>
      </select>
      <div class="w-px h-5 bg-gray-300 mx-1"></div>
      <button @click="toggleBulletList" :class="['p-1.5 rounded hover:bg-gray-200', isActive('bulletList') ? 'bg-gray-200' : '']" title="无序列表">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1" fill="currentColor"/><circle cx="4" cy="12" r="1" fill="currentColor"/><circle cx="4" cy="18" r="1" fill="currentColor"/></svg>
      </button>
      <button @click="toggleOrderedList" :class="['p-1.5 rounded hover:bg-gray-200', isActive('orderedList') ? 'bg-gray-200' : '']" title="有序列表">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><text x="4" y="8" font-size="7" fill="currentColor">1</text><text x="4" y="14" font-size="7" fill="currentColor">2</text><text x="4" y="20" font-size="7" fill="currentColor">3</text></svg>
      </button>
      <div class="w-px h-5 bg-gray-300 mx-1"></div>
      <button @click="setTextAlign('left')" :class="['p-1.5 rounded hover:bg-gray-200', isActiveAlign('left') ? 'bg-gray-200' : '']" title="左对齐">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="15" y2="12"/><line x1="3" y1="18" x2="18" y2="18"/></svg>
      </button>
      <button @click="setTextAlign('center')" :class="['p-1.5 rounded hover:bg-gray-200', isActiveAlign('center') ? 'bg-gray-200' : '']" title="居中">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="6" y1="12" x2="18" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>
      </button>
      <button @click="setTextAlign('right')" :class="['p-1.5 rounded hover:bg-gray-200', isActiveAlign('right') ? 'bg-gray-200' : '']" title="右对齐">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="6" y1="18" x2="21" y2="18"/></svg>
      </button>
      <div class="w-px h-5 bg-gray-300 mx-1"></div>
      <button @click="toggleHighlight" :class="['p-1.5 rounded hover:bg-gray-200', isActive('highlight') ? 'bg-yellow-200' : '']" title="数字高亮">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 22h20L12 2z"/><path d="M12 8v4"/><circle cx="12" cy="16" r="0.5" fill="currentColor"/></svg>
      </button>
      <div class="flex-1"></div>
      <button @click="undo" class="p-1.5 rounded hover:bg-gray-200" title="撤销">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 10h10a5 5 0 0 1 5 5v0a5 5 0 0 1-5 5H8"/><polyline points="7 14 3 10 7 6"/></svg>
      </button>
      <button @click="redo" class="p-1.5 rounded hover:bg-gray-200" title="重做">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10H11a5 5 0 0 0-5 5v0a5 5 0 0 0 5 5h5"/><polyline points="17 14 21 10 17 6"/></svg>
      </button>
    </div>
    <EditorContent :editor="editor" class="prose prose-sm sm:prose max-w-none p-6 min-h-[400px] focus:outline-none" @click="handleEditorClick" />
  </div>
</template>

<style scoped>
.tiptap-editor :deep(.tiptap) { outline: none; min-height: 400px; }
.tiptap-editor :deep(.tiptap p.is-editor-empty:first-child::before) { content: attr(data-placeholder); float: left; color: #adb5bd; pointer-events: none; height: 0; }
.tiptap-editor :deep(.tiptap mark) { background-color: #fef08a; padding: 0.125rem 0.25rem; border-radius: 0.25rem; cursor: pointer; }
.tiptap-editor :deep(.tiptap h1) { font-size: 1.875rem; font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.75rem; }
.tiptap-editor :deep(.tiptap h2) { font-size: 1.5rem; font-weight: 600; margin-top: 1.25rem; margin-bottom: 0.625rem; }
.tiptap-editor :deep(.tiptap h3) { font-size: 1.25rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; }
.tiptap-editor :deep(.tiptap h4) { font-size: 1.125rem; font-weight: 600; margin-top: 0.75rem; margin-bottom: 0.5rem; }
.tiptap-editor :deep(.tiptap ul) { list-style-type: disc; padding-left: 1.5rem; margin: 0.5rem 0; }
.tiptap-editor :deep(.tiptap ol) { list-style-type: decimal; padding-left: 1.5rem; margin: 0.5rem 0; }
.tiptap-editor :deep(.tiptap blockquote) { border-left: 3px solid #d1d5db; padding-left: 1rem; margin: 0.5rem 0; color: #6b7280; }
.tiptap-editor :deep(.tiptap pre) { background-color: #f3f4f6; border-radius: 0.375rem; padding: 0.75rem 1rem; font-family: monospace; font-size: 0.875rem; overflow-x: auto; }
.tiptap-editor :deep(.tiptap hr) { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }
</style>
