import type { ModelConfigCreate, ModelConfigUpdate, UserUpdateAdmin } from '#/types/openapi'

import client from './client'

export function getModelConfigs(type?: string) {
  return client.get('/admin/models/config', { params: type ? { type } : {} })
}

export function createModelConfig(data: ModelConfigCreate) {
  return client.post('/admin/models/config', data)
}

export function updateModelConfig(configId: string, data: ModelConfigUpdate) {
  return client.put(`/admin/models/config/${configId}`, data)
}

export function listUsers(skip = 0, limit = 50) {
  return client.get('/admin/users', { params: { skip, limit } })
}

export function createUser(data: { username: string; password: string; role: string }) {
  return client.post('/admin/users', data)
}

export function updateUser(userId: string, data: UserUpdateAdmin) {
  return client.put(`/admin/users/${userId}`, data)
}

export function resetPassword(userId: string) {
  return client.post(`/admin/users/${userId}/reset-password`, {})
}

export function deleteUser(userId: string) {
  return client.delete(`/admin/users/${userId}`)
}

export function listAuditLogs(skip = 0, limit = 50) {
  return client.get('/admin/audit-logs', { params: { skip, limit } })
}

export function listGenerationLogs(skip = 0, limit = 50) {
  return client.get('/admin/generation-logs', { params: { skip, limit } })
}

export function getTokenStats(userId?: string) {
  return client.get('/admin/token-stats', { params: userId ? { user_id: userId } : {} })
}
