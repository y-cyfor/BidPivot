<script setup lang="ts">
import { useRouter } from 'vue-router';

import LoginForm from '#/components/LoginForm.vue';

const router = useRouter();
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">BidPivot 登录</h1>
      <LoginForm @success="router.push('/')" />
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f0f2f5;
}
.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
.login-title {
  text-align: center;
  margin-bottom: 30px;
  color: #000000d9;
}
</style>
