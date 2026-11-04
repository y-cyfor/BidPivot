import client from './client'

export function sendConversationMessage(
  projectId: string,
  instruction: string,
  currentHtml: string,
  selectedText?: string,
) {
  return client.post(`/bid/${projectId}/conversation`, {
    instruction,
    current_html: currentHtml,
    selected_text: selectedText || null,
  }, {
    responseType: 'text',
  })
}

export function listVersions(projectId: string) {
  return client.get(`/bid/${projectId}/versions`)
}

export function diffVersions(projectId: string, fromId: string, toId: string) {
  return client.get(`/bid/${projectId}/versions/diff`, {
    params: { from_id: fromId, to_id: toId },
  })
}

export function restoreVersion(projectId: string, versionId: string) {
  return client.post(`/bid/${projectId}/versions/${versionId}/restore`)
}

export function createWsTicket(projectId: string, taskId: string) {
  return client.post('/ws/ticket', { project_id: projectId, task_id: taskId })
}
