<script lang="ts" setup>
import { computed, onErrorCaptured } from 'vue';

import { useAntdDesignTokens } from '@vben/hooks';
import { preferences, usePreferences } from '@vben/preferences';

import { App, ConfigProvider, message, theme } from 'ant-design-vue';

import { antdLocale } from '#/locales';

defineOptions({ name: 'App' });

onErrorCaptured((error) => {
  console.error('Unhandled UI error:', error);
  message.error('页面发生错误，请刷新后重试');
  return false;
});

const { isDark } = usePreferences();
const { tokens } = useAntdDesignTokens();

const tokenTheme = computed(() => {
  const algorithm = isDark.value
    ? [theme.darkAlgorithm]
    : [theme.defaultAlgorithm];

  // antd 紧凑模式算法
  if (preferences.app.compact) {
    algorithm.push(theme.compactAlgorithm);
  }

  return {
    algorithm,
    token: tokens,
  };
});
</script>

<template>
  <ConfigProvider :locale="antdLocale" :theme="tokenTheme">
    <App>
      <RouterView />
    </App>
  </ConfigProvider>
</template>

<style>
:focus-visible {
  outline: 2px solid #1677ff;
  outline-offset: 2px;
}
</style>
