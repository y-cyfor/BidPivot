import axios from 'axios'
import { message } from 'ant-design-vue'

const LOGIN_PATH = '/auth/login'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null
  try {
    // Use a bare axios call so this request never re-enters the interceptor.
    const response = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
    const data = response.data?.data
    if (!data?.token) return null
    localStorage.setItem('token', data.token)
    localStorage.setItem('refresh_token', data.refresh_token)
    return data.token
  } catch {
    return null
  }
}

function redirectToLogin() {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  if (window.location.pathname !== LOGIN_PATH) {
    window.location.href = LOGIN_PATH
  }
}

client.interceptors.response.use(
  (response) => {
    // 返回后端统一响应体，由调用方读取 code/data
    return response.data
  },
  async (error) => {
    const config: any = error.config || {}
    const url: string = config.url || ''
    const isAuthRequest = url.includes('/auth/login') || url.includes('/auth/refresh')

    if (error.response?.status === 401 && !isAuthRequest && !config._retry) {
      config._retry = true
      const newToken = await refreshAccessToken()
      if (newToken) {
        config.headers = { ...(config.headers || {}), Authorization: `Bearer ${newToken}` }
        return client(config)
      }
      redirectToLogin()
    }

    if (error.response) {
      const { data } = error.response
      if (data?.detail) {
        message.error(data.detail)
      } else if (data?.message) {
        message.error(data.message)
      }
    } else {
      message.error('网络错误，请稍后重试')
    }

    return Promise.reject(error)
  }
)

export default client
