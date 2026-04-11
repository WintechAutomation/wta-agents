import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://mes-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/mes-user-mgmt';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(800);
  const userInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="아이디"], input[placeholder*="user" i]').first();
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill('account');
    await page.locator('input[type="password"]').first().fill('test1234');
    await page.locator('button[type="submit"], button').filter({ hasText: /로그인|Login|확인/i }).first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
}

test('사용자관리 페이지 구조 파악', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/system/user-management`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(3000);
  await shot(page, '00-user-mgmt-structure');

  // 버튼 목록
  const allBtns = await page.locator('button:visible').allTextContents();
  console.log(`버튼 목록: ${allBtns.map(t => t.trim()).filter(t => t).join(' | ')}`);

  // 테이블 구조 확인
  const tableRows = await page.locator('table tbody tr').count();
  const agRows = await page.locator('.ag-row, [class*="ag-row"]').count();
  const gridRows = await page.locator('[role="row"]').count();
  console.log(`table tbody tr: ${tableRows}`);
  console.log(`ag-grid rows: ${agRows}`);
  console.log(`role=row: ${gridRows}`);

  // body text 일부
  const bodyText = await page.locator('body').textContent().catch(() => '');
  console.log(`페이지 텍스트(300자): ${bodyText?.slice(0, 300)}`);

  // 편집 버튼 탐색
  const editBtns = await page.locator('button').filter({ hasText: /편집|수정|Edit/i }).allTextContents();
  console.log(`편집 버튼: ${editBtns.join(', ')}`);

  // role=row 구조 확인 (AG Grid)
  if (gridRows > 0) {
    console.log(`\nrole=row 행들 (최대 3개):`);
    for (let i = 0; i < Math.min(gridRows, 3); i++) {
      const rowText = await page.locator('[role="row"]').nth(i).textContent().catch(() => '');
      console.log(`  row[${i}]: ${rowText?.slice(0, 100)}`);
    }
  }
});
