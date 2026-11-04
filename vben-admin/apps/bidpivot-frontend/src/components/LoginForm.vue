<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { useAccessStore } from '@vben/stores';

import { getCaptcha, login } from '#/api/auth';
import { useAuthStore } from '#/store/auth';

import { Button, Form, Input, message } from 'ant-design-vue';

const emit = defineEmits<{ success: [] }>();

const auth = useAuthStore();
const accessStore = useAccessStore();

const loginForm = ref({
  username: '',
  password: '',
  captcha_code: '',
});

const captchaId = ref('');
const captchaImage = ref('');
const loading = ref(false);

async function refreshCaptcha() {
  try {
    const res = (await getCaptcha()) as {
      data: { captcha_id: string; image_base64: string };
    };
    captchaId.value = res.data.captcha_id;
    captchaImage.value = `data:image/png;base64,${res.data.image_base64}`;
  } catch {
    message.error('获取验证码失败');
  }
}

async function handleLogin() {
  loading.value = true;
  try {
    const res = (await login({
      username: loginForm.value.username,
      password: loginForm.value.password,
      captcha_id: captchaId.value,
      captcha_code: loginForm.value.captcha_code,
    })) as {
      data: {
        token: string;
        refresh_token: string;
        user: { id: string; username: string; role: string };
      };
    };
    auth.setTokens(res.data.token, res.data.refresh_token);
    auth.setUserInfo({
      userId: res.data.user.id,
      username: res.data.user.username,
      realName: res.data.user.username,
      roles: [res.data.user.role],
      avatar: '',
    });
    accessStore.setLoginExpired(false);
    message.success('登录成功');
    emit('success');
  } catch {
    await refreshCaptcha();
    loginForm.value.captcha_code = '';
  } finally {
    loading.value = false;
  }
}

onMounted(refreshCaptcha);
</script>

<template>
  <Form :model="loginForm" layout="vertical" @finish="handleLogin">
    <Form.Item
      label="用户名"
      name="username"
      :rules="[{ required: true, message: '请输入用户名' }]"
    >
      <Input
        v-model:value="loginForm.username"
        placeholder="请输入用户名"
        autocomplete="username"
        aria-label="用户名"
      />
    </Form.Item>
    <Form.Item
      label="密码"
      name="password"
      :rules="[{ required: true, message: '请输入密码' }]"
    >
      <Input.Password
        v-model:value="loginForm.password"
        placeholder="请输入密码"
        autocomplete="current-password"
        aria-label="密码"
      />
    </Form.Item>
    <Form.Item
      label="验证码"
      name="captcha_code"
      :rules="[{ required: true, message: '请输入验证码' }]"
    >
      <div class="captcha-row">
        <Input
          v-model:value="loginForm.captcha_code"
          placeholder="请输入验证码"
          :maxlength="4"
          autocomplete="off"
          aria-label="验证码"
        />
        <img
          :src="captchaImage"
          class="captcha-img"
          alt="验证码"
          role="button"
          tabindex="0"
          aria-label="验证码图片，点击刷新"
          @click="refreshCaptcha"
          @keydown.enter="refreshCaptcha"
        />
      </div>
    </Form.Item>
    <Form.Item>
      <Button type="primary" :loading="loading" html-type="submit" style="width: 100%">
        登录
      </Button>
    </Form.Item>
  </Form>
</template>

<style scoped>
.captcha-row {
  display: flex;
  gap: 10px;
}
.captcha-img {
  height: 32px;
  cursor: pointer;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
}
</style>
