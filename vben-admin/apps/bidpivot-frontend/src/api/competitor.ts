import type { CompetitorUpdate } from '#/types/openapi'

import client from './client'

export function listCompetitors() { return client.get('/competitors') }
export function createCompetitor(data: { name: string; industry?: string; description?: string }) { return client.post('/competitors', data) }
export function updateCompetitor(id: string, data: CompetitorUpdate) { return client.put(`/competitors/${id}`, data) }
export function deleteCompetitor(id: string) { return client.delete(`/competitors/${id}`) }
export function uploadCompetitorDoc(competitorId: string, file: File, title: string, fileTypeTag: string) {
  const formData = new FormData()
  formData.append('file', file); formData.append('title', title); formData.append('file_type_tag', fileTypeTag)
  return client.post(`/competitors/${competitorId}/documents`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export function listCompetitorDocs(competitorId: string) { return client.get(`/competitors/${competitorId}/documents`) }
export function deleteCompetitorDoc(competitorId: string, docId: string) { return client.delete(`/competitors/${competitorId}/documents/${docId}`) }
export function runAnalysis(data: { analysis_type: string; competitor_ids: string[] }) { return client.post('/competitors/analyze', data) }
export function listAnalyses() { return client.get('/competitors/analyses/list') }
