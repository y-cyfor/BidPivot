import client from '../client';

/**
 * 获取当前登录用户信息（BidPivot 后端）。
 */
export async function getUserInfoApi() {
  const res = (await client.get('/auth/me')) as unknown as {
    data: { id: string; username: string; role: string };
  };
  const user = res.data;
  return {
    userId: user.id,
    username: user.username,
    realName: user.username,
    roles: [user.role],
    avatar: '',
  };
}
