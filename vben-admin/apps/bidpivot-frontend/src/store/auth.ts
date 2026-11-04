import { defineStore } from 'pinia';

import { useAccessStore, useUserStore } from '@vben/stores';

interface BasicUserInfo {
  [key: string]: unknown;
  avatar?: string;
  realName: string;
  roles?: string[];
  userId: string;
  username: string;
}

interface AuthState {
  loginLoading: boolean;
  token: string | null;
  refreshToken: string | null;
  userInfo: BasicUserInfo | null;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('token'),
    refreshToken: localStorage.getItem('refresh_token'),
    userInfo: null,
    loginLoading: false,
  }),

  actions: {
    setTokens(newToken: string, newRefreshToken: string) {
      this.token = newToken;
      this.refreshToken = newRefreshToken;
      localStorage.setItem('token', newToken);
      localStorage.setItem('refresh_token', newRefreshToken);
      // 同步设置到 Vben Admin 的 accessStore
      const accessStore = useAccessStore();
      accessStore.setAccessToken(newToken);
    },

    setToken(newToken: string) {
      this.token = newToken;
      localStorage.setItem('token', newToken);
      const accessStore = useAccessStore();
      accessStore.setAccessToken(newToken);
    },

    setUserInfo(userInfo: BasicUserInfo | null) {
      this.userInfo = userInfo;
      // 同步设置到 Vben Admin 的 userStore
      if (userInfo) {
        const userStore = useUserStore();
        userStore.setUserInfo({
          userId: userInfo.userId,
          username: userInfo.username,
          realName: userInfo.realName,
          roles: userInfo.roles || [],
          avatar: userInfo.avatar || '',
        });
      }
    },

    async fetchUserInfo() {
      if (!this.token) return null;
      try {
        const { getMe } = await import('#/api/auth');
        const res = (await getMe()) as {
          data: { id: string; username: string; role: string };
        };
        const user = res.data;
        this.setUserInfo({
          userId: user.id,
          username: user.username,
          realName: user.username,
          roles: [user.role],
          avatar: '',
        });
        return this.userInfo;
      } catch {
        await this.logout();
        return null;
      }
    },

    async authLogin(params: {
      captcha_code: string;
      captcha_id: string;
      password: string;
      username: string;
    }) {
      this.loginLoading = true;
      try {
        const { login } = await import('#/api/auth');
        const res = (await login(params)) as unknown as {
          code: number;
          data: {
            token: string;
            refresh_token: string;
            user: { id: string; username: string; role: string };
          };
        };
        // 后端返回格式: { code: 200, data: { token, refresh_token, user }, message: "..." }
        if (res.code === 200) {
          this.setTokens(res.data.token, res.data.refresh_token);
          this.setUserInfo({
            userId: res.data.user.id,
            username: res.data.user.username,
            realName: res.data.user.username,
            roles: [res.data.user.role],
            avatar: '',
          });
          return true;
        }
        return false;
      } catch (error: unknown) {
        console.error('Login failed:', error);
        return false;
      } finally {
        this.loginLoading = false;
      }
    },

    async logout() {
      const refreshTokenValue = this.refreshToken;
      try {
        const { logout } = await import('#/api/auth');
        await logout(refreshTokenValue || undefined);
      } catch {
        // Local logout must succeed even when the API is unreachable.
      }
      this.token = null;
      this.refreshToken = null;
      this.userInfo = null;
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      // 同步清除 Vben Admin 的 accessStore
      const accessStore = useAccessStore();
      accessStore.setAccessToken(null);
      accessStore.setIsAccessChecked(false);
    },
  },
});
