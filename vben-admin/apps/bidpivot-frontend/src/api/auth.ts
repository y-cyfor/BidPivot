import client from './client'

export function getCaptcha() {
  return client.get('/auth/captcha')
}

export function login(data: { username: string; password: string; captcha_id: string; captcha_code: string }) {
  return client.post('/auth/login', data)
}

export function refreshToken(refreshTokenValue: string) {
  return client.post('/auth/refresh', { refresh_token: refreshTokenValue })
}

export function logout(refreshTokenValue?: string) {
  return client.post('/auth/logout', { refresh_token: refreshTokenValue || null })
}

export function getMe() {
  return client.get('/auth/me')
}
