<script lang="ts" setup>
import { useRouter } from 'vue-router';

import LoginForm from '#/components/LoginForm.vue';

defineOptions({ name: 'Login' });

const router = useRouter();
</script>

<template>
  <LoginForm @success="router.push('/')" />
</template>
