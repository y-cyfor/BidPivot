// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Current smoke suite. The previous 168 cases targeted the retired Tailwind
 * frontend (/login, old DOM) and could not run against the Vben/Ant Design app.
 */

test.describe('BidPivot smoke', () => {
  test('login page renders with server captcha', async ({ page }) => {
    await page.goto('/auth/login');
    await expect(page.getByText('BidPivot 登录')).toBeVisible();
    await expect(page.locator('img[alt="验证码"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('captcha refreshes on click', async ({ page }) => {
    await page.goto('/auth/login');
    const image = page.locator('img[alt="验证码"]');
    await expect(image).toBeVisible();
    const before = await image.getAttribute('src');
    await image.click();
    await expect
      .poll(async () => image.getAttribute('src'), { timeout: 5000 })
      .not.toBe(before);
  });

  test('unauthenticated navigation redirects to login', async ({ page }) => {
    await page.goto('/bids');
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test('backend health endpoint is up', async ({ request }) => {
    const response = await request.get('http://127.0.0.1:8000/health');
    expect(response.ok()).toBeTruthy();
    expect(await response.json()).toEqual({ status: 'ok' });
  });
});
