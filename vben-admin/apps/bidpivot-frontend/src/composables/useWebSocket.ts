import { onUnmounted, ref } from 'vue'

export interface WsEvent {
  type: string
  section_id?: string
  agent?: string
  content?: string
  status?: string
  token?: string
  var_name?: string
  value?: string
  source?: string
  batch?: number
  completed?: string[]
  total_sections?: number
  failed_sections?: string[]
  partial?: boolean
  message?: string
  tool?: string
  args?: Record<string, any>
  result_summary?: string
  timestamp?: string
}

interface WsOptions {
  /** Request a fresh single-use ticket, used on (re)connect. */
  getTicket?: (taskId: string) => Promise<string>
}

export function useGenerationWebSocket(options: WsOptions = {}) {
  const events = ref<WsEvent[]>([])
  const sectionStatuses = ref<Record<string, string>>({})
  const thinkingChains = ref<Record<string, WsEvent[]>>({})
  const overallProgress = ref(0)
  const totalSections = ref(0)
  const isConnected = ref(false)
  const isComplete = ref(false)
  const generationFailed = ref(false)
  const generationCancelled = ref(false)

  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  const MAX_RECONNECT = 5
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let currentTaskId = ''
  let currentTicket = ''
  let manualClose = false

  function connect(taskId: string, ticket: string) {
    currentTaskId = taskId
    currentTicket = ticket
    manualClose = false
    reconnectAttempts = 0
    open()
  }

  function open() {
    if (!currentTaskId || !currentTicket) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/generation/${currentTaskId}?ticket=${encodeURIComponent(currentTicket)}`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      isConnected.value = true
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const data: WsEvent = JSON.parse(event.data)
        events.value.push(data)

        switch (data.type) {
          case 'section_status':
            if (data.section_id && data.status) {
              sectionStatuses.value[data.section_id] = data.status
              if (data.status === 'completed') {
                overallProgress.value++
              }
            }
            break

          case 'thinking':
          case 'tool_call':
            if (data.section_id) {
              if (!thinkingChains.value[data.section_id]) {
                thinkingChains.value[data.section_id] = []
              }
              thinkingChains.value[data.section_id]!.push(data)
            }
            break

          case 'generation_complete':
            totalSections.value = data.total_sections || 0
            isComplete.value = true
            break

          case 'generation_failed':
            generationFailed.value = true
            break

          case 'generation_cancelled':
            generationCancelled.value = true
            break

          case 'error':
            if (data.section_id) {
              sectionStatuses.value[data.section_id] = 'failed'
            }
            break
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = async () => {
      isConnected.value = false
      if (manualClose || isComplete.value || reconnectAttempts >= MAX_RECONNECT) {
        return
      }
      reconnectAttempts++
      const delay = Math.min(1000 * 2 ** reconnectAttempts, 30000)
      reconnectTimer = setTimeout(async () => {
        if (options.getTicket) {
          try {
            currentTicket = await options.getTicket(currentTaskId)
          } catch {
            return
          }
        }
        open()
      }, delay)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    manualClose = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
  }

  onUnmounted(disconnect)

  return {
    events,
    sectionStatuses,
    thinkingChains,
    overallProgress,
    totalSections,
    isConnected,
    isComplete,
    generationFailed,
    generationCancelled,
    connect,
    disconnect,
  }
}
