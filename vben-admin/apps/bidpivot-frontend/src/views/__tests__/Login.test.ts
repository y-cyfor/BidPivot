import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Antd from 'ant-design-vue'
import Login from '../Login.vue'

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

// Mock auth API
const mockGetCaptcha = vi.fn().mockResolvedValue({
  data: {
    captcha_id: 'test-captcha-id',
    image_base64: 'dGVzdA==',
  },
})
const mockLoginFn = vi.fn().mockResolvedValue({
  data: {
    token: 'test-token',
    user: { id: 1, username: 'admin' },
  },
})
vi.mock('#/api/auth', () => ({
  getCaptcha: (...args: unknown[]) => mockGetCaptcha(...args),
  login: (...args: unknown[]) => mockLoginFn(...args),
}))

function mountLogin() {
  return mount(Login, {
    global: {
      plugins: [createPinia(), Antd],
    },
  })
}

describe('Login', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders login title correctly', () => {
    const wrapper = mountLogin()
    const title = wrapper.find('.login-title')
    expect(title.exists()).toBe(true)
    expect(title.text()).toBe('BidPivot 登录')
  })

  it('has username input field', () => {
    const wrapper = mountLogin()
    const usernameInput = wrapper.find('input[placeholder="请输入用户名"]')
    expect(usernameInput.exists()).toBe(true)
  })

  it('has password input field', () => {
    const wrapper = mountLogin()
    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.exists()).toBe(true)
  })

  it('has captcha input field', () => {
    const wrapper = mountLogin()
    const captchaInput = wrapper.find('input[placeholder="请输入验证码"]')
    expect(captchaInput.exists()).toBe(true)
  })

  it('has submit button with correct text', () => {
    const wrapper = mountLogin()
    const button = wrapper.find('button[type="submit"]')
    expect(button.exists()).toBe(true)
    // Ant Design Vue inserts a space between CJK characters, so normalize whitespace
    expect(button.text().replace(/\s/g, '')).toContain('登录')
  })

  it('calls getCaptcha on mount', async () => {
    mountLogin()
    await flushPromises()
    expect(mockGetCaptcha).toHaveBeenCalledTimes(1)
  })

  it('displays captcha image after loading', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    const captchaImg = wrapper.find('img.captcha-img')
    expect(captchaImg.exists()).toBe(true)
    expect(captchaImg.attributes('src')).toContain('data:image/png;base64,')
  })

  it('binds username input to form data', async () => {
    const wrapper = mountLogin()
    const usernameInput = wrapper.find('input[placeholder="请输入用户名"]')
    await usernameInput.setValue('testuser')
    expect((usernameInput.element as HTMLInputElement).value).toBe('testuser')
  })

  it('binds password input to form data', async () => {
    const wrapper = mountLogin()
    const passwordInput = wrapper.find('input[type="password"]')
    await passwordInput.setValue('testpass')
    expect((passwordInput.element as HTMLInputElement).value).toBe('testpass')
  })
})
