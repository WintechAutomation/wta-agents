import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'http://localhost:8100';
const FRONT_URL = 'https://mes-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/mes-health-check';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: true });
}

// MES 로그인 (계정: account)
async function mesLogin(page: Page) {
  await page.goto(`${FRONT_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);

  const usernameInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="아이디"], input[placeholder*="user" i]').first();
  const passwordInput = page.locator('input[type="password"]').first();

  const loginVisible = await usernameInput.isVisible().catch(() => false);
  if (!loginVisible) return; // 이미 로그인됨

  await usernameInput.fill('account');
  await passwordInput.fill('test1234');
  const submitBtn = page.locator('button[type="submit"], button:has-text("로그인")').first();
  await submitBtn.click();
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(1000);
}

test.describe('[MES 헬스체크] 2026-04-01 롤백 이후 점검', () => {

  test('1. 메인 페이지 로딩', async ({ page }) => {
    const resp = await page.goto(FRONT_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    expect(resp?.status()).toBeLessThan(400);
    await shot(page, '01-main');
    console.log(`메인 상태: ${resp?.status()}, URL: ${page.url()}`);
  });

  test('2. 로그인 후 대시보드 접속', async ({ page }) => {
    await mesLogin(page);
    const resp = await page.goto(`${FRONT_URL}/`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(2000);
    await shot(page, '02-dashboard');
    const url = page.url();
    console.log(`대시보드 URL: ${url}`);
    // 로그인 페이지로 리다이렉트되면 실패
    expect(url).not.toContain('/login');
  });

  test('3. 프로젝트 현황 페이지', async ({ page }) => {
    await mesLogin(page);
    await page.goto(`${FRONT_URL}/projects`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(3000);
    await shot(page, '03-projects');
    const url = page.url();
    console.log(`프로젝트 URL: ${url}`);
    expect(url).not.toContain('/login');
  });

  test('4. 수주 목록 페이지', async ({ page }) => {
    await mesLogin(page);
    await page.goto(`${FRONT_URL}/sales/order-management`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(3000);
    await shot(page, '04-orders');
    const url = page.url();
    console.log(`수주 URL: ${url}`);
    expect(url).not.toContain('/login');
  });

  test('5. 원자재 재고 페이지 (ERP 연동)', async ({ page }) => {
    await mesLogin(page);
    await page.goto(`${FRONT_URL}/raw-material-inventory`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(3000);
    await shot(page, '05-raw-inventory');
    const url = page.url();
    console.log(`원자재 재고 URL: ${url}`);
    expect(url).not.toContain('/login');
  });

  test('6. 공수 관리 페이지', async ({ page }) => {
    await mesLogin(page);
    await page.goto(`${FRONT_URL}/labor-hours`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(3000);
    await shot(page, '06-labor-hours');
    const url = page.url();
    console.log(`공수 URL: ${url}`);
    expect(url).not.toContain('/login');
  });

  test('7. CS 이력 관리 페이지', async ({ page }) => {
    await mesLogin(page);
    await page.goto(`${FRONT_URL}/cs/history-management`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(3000);
    await shot(page, '07-cs-history');
    const url = page.url();
    console.log(`CS 이력 URL: ${url}`);
    expect(url).not.toContain('/login');
  });

  test('8. 공지사항 페이지', async ({ page }) => {
    await mesLogin(page);
    await page.goto(`${FRONT_URL}/announcements`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(3000);
    await shot(page, '08-announcements');
    const url = page.url();
    console.log(`공지 URL: ${url}`);
    expect(url).not.toContain('/login');
  });

});
