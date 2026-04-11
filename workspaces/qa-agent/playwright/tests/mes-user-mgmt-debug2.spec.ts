import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://mes-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/mes-user-mgmt';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

test('로그인 + 사용자관리 라우트 탐색', async ({ page }) => {
  // 1. 로그인 페이지 직접 접근
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(2000);
  await shot(page, 'd2-01-login');
  console.log(`로그인 페이지 URL: ${page.url()}`);
  const loginText = await page.locator('body').textContent().catch(() => '');
  console.log(`로그인 페이지 텍스트(200): ${loginText?.slice(0, 200)}`);

  // input 확인
  const inputs = await page.locator('input').all();
  for (const inp of inputs) {
    const type = await inp.getAttribute('type').catch(() => '');
    const name = await inp.getAttribute('name').catch(() => '');
    const visible = await inp.isVisible().catch(() => false);
    console.log(`  input: type="${type}" name="${name}" visible=${visible}`);
  }

  // 2. 로그인 시도
  const userInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="아이디"], input[placeholder*="user" i], input:not([type="password"])').first();
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill('account');
    await page.locator('input[type="password"]').first().fill('test1234');
    await shot(page, 'd2-02-login-filled');

    const submitBtn = page.locator('button[type="submit"], button').filter({ hasText: /로그인|Login|확인/i }).first();
    console.log(`로그인 버튼 visible: ${await submitBtn.isVisible().catch(() => false)}`);
    await submitBtn.click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(2000);
  } else {
    console.log('로그인 input 없음');
  }

  await shot(page, 'd2-03-after-login');
  console.log(`로그인 후 URL: ${page.url()}`);
  const afterText = await page.locator('body').textContent().catch(() => '');
  console.log(`로그인 후 텍스트(300): ${afterText?.slice(0, 300)}`);

  // 3. 사이드바/메뉴에서 사용자관리 링크 탐색
  const navLinks = await page.locator('nav a, aside a, [class*="sidebar"] a, [class*="nav"] a').allTextContents();
  console.log(`\n메뉴 링크들: ${navLinks.map(t => t.trim()).filter(t => t).join(' | ')}`);

  // 사용자관리 링크 찾기
  const userMgmtLink = page.locator('a, button').filter({ hasText: /사용자\s*관리|User\s*Manage|Users/i }).first();
  const hasUserMgmtLink = await userMgmtLink.isVisible().catch(() => false);
  console.log(`사용자관리 링크 존재: ${hasUserMgmtLink}`);

  // 4. /system/users 또는 /settings/users 시도
  const routes = ['/system/user-management', '/system/users', '/settings/users', '/users'];
  for (const route of routes) {
    await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
    await page.waitForTimeout(1500);
    const currentUrl = page.url();
    const text = await page.locator('body').textContent().catch(() => '');
    console.log(`\n라우트 ${route}:`);
    console.log(`  실제 URL: ${currentUrl}`);
    console.log(`  텍스트(150): ${text?.slice(0, 150)}`);
    if (!currentUrl.includes('/login') && text && text.trim().length > 50) {
      console.log(`  ✅ 유효한 라우트`);
      await shot(page, `d2-route-${route.replace(/\//g, '-')}`);
      break;
    }
  }
});
