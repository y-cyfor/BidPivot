import type {
  ApiResponse_ProjectDetailResponse,
  ApiResponse_ProjectListResponse,
  ApiResponse_ProjectResponse,
} from '#/types/openapi'

import client from './client'

export function createProject(data: { title: string; industry_tags?: string[] }): Promise<ApiResponse_ProjectResponse> {
  return client.post('/projects', data) as unknown as Promise<ApiResponse_ProjectResponse>
}

export function listProjects(skip = 0, limit = 20): Promise<ApiResponse_ProjectListResponse> {
  return client.get('/projects', { params: { skip, limit } }) as unknown as Promise<ApiResponse_ProjectListResponse>
}

export function getProject(id: string): Promise<ApiResponse_ProjectDetailResponse> {
  return client.get(`/projects/${id}`) as unknown as Promise<ApiResponse_ProjectDetailResponse>
}

export function generateOutline(projectId: string) {
  return client.post(`/bid/${projectId}/generate-outline`)
}

export function generateFull(projectId: string) {
  return client.post(`/bid/${projectId}/generate-full`)
}

export function deleteProject(id: string) {
  return client.delete(`/projects/${id}`)
}

export function saveDocument(projectId: string, contentHtml: string, contentJson: Record<string, unknown>): Promise<ApiResponse_ProjectDetailResponse> {
  return client.put(`/projects/${projectId}/document`, {
    content_html: contentHtml,
    content_json: contentJson,
  }) as unknown as Promise<ApiResponse_ProjectDetailResponse>
}

export function exportProject(projectId: string, format: 'docx' | 'pdf' | 'md' = 'docx', template?: string) {
  return client.get(`/export/${projectId}`, {
    params: { format, ...(template ? { template } : {}) },
    responseType: 'blob',
  })
}

export function saveOutline(projectId: string, outline: Record<string, unknown>) {
  return client.put(`/bid/${projectId}/outline`, outline)
}

export function generateFullAsync(projectId: string) {
  return client.post(`/bid/${projectId}/generate-full`)
}

export function getCheckReport(projectId: string) {
  return client.get(`/bid/${projectId}/check-report`)
}

export function cancelGeneration(projectId: string) {
  return client.post(`/bid/${projectId}/cancel`)
}
