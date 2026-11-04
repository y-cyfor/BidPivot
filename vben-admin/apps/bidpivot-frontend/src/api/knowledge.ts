import client from './client'

export function listDirectories(scope: 'personal' | 'global') {
  return client.get(`/knowledge/${scope}/directories`)
}

export function createDirectory(scope: 'personal' | 'global', name: string, parentId?: string) {
  return client.post(`/knowledge/${scope}/directories`, { name, parent_id: parentId || null })
}

export function deleteDirectory(scope: 'personal' | 'global', id: string) {
  return client.delete(`/knowledge/${scope}/directories/${id}`)
}

export function uploadDocument(scope: 'personal' | 'global', file: File, directoryId: string, title: string) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('directory_id', directoryId)
  formData.append('title', title)
  return client.post(`/knowledge/${scope}/documents/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function listDocuments(scope: 'personal' | 'global', directoryId?: string, skip = 0, limit = 20) {
  const params: Record<string, any> = { skip, limit }
  if (directoryId) params.directory_id = directoryId
  return client.get(`/knowledge/${scope}/documents`, { params })
}

export function getDocument(scope: 'personal' | 'global', id: string) {
  return client.get(`/knowledge/${scope}/documents/${id}`)
}

export function updateDocument(scope: 'personal' | 'global', id: string, data: { title?: string; content_text?: string }) {
  return client.put(`/knowledge/${scope}/documents/${id}`, data)
}

export function deleteDocument(scope: 'personal' | 'global', id: string) {
  return client.delete(`/knowledge/${scope}/documents/${id}`)
}

export function reindexDocument(scope: 'personal' | 'global', id: string) {
  return client.post(`/knowledge/${scope}/documents/${id}/reindex`)
}

export function publishDocument(id: string) {
  return client.post(`/knowledge/global/documents/${id}/publish`)
}

export function searchKnowledge(scope: 'personal' | 'global', query: string, topK = 10) {
  return client.post(`/knowledge/${scope}/search`, { query, top_k: topK })
}
