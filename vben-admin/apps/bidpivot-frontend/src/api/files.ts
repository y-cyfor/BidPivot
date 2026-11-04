import client from './client'

export function uploadFile(file: File, projectId?: string, fileType: string = 'bid') {
  const formData = new FormData()
  formData.append('file', file)
  if (projectId) formData.append('project_id', projectId)
  formData.append('file_type', fileType)
  return client.post('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
