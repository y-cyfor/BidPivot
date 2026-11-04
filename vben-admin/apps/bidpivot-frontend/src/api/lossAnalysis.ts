import client from './client'

export function createLossAnalysis(file: File, projectId?: string) {
  const formData = new FormData()
  formData.append('file', file)
  if (projectId) formData.append('project_id', projectId)
  return client.post('/loss-analysis', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export function listLossAnalyses() { return client.get('/loss-analysis') }
export function getLossAnalysis(id: string) { return client.get(`/loss-analysis/${id}`) }
export function saveToKnowledge(id: string) { return client.post(`/loss-analysis/${id}/save-to-knowledge`) }
