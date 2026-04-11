import { test, Browser, BrowserContext, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material-nocache';
const FIXTURES = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/fixtures';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function freshContext(browser: Browser): Promise<BrowserContext> {
  return browser.newContext({
    bypassCSP: true,
    ignoreHTTPSErrors: true,
    serviceWorkers: 'block',
    extraHTTPHeaders: { 'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache' },
  });
}

async function loginFresh(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(800);
  const pw = page.locator('input[type="password"]').first();
  if (await pw.isVisible().catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await pw.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

test('422 에러 원인 분석', async ({ browser }) => {
  const ctx = await freshContext(browser);
  const page = await ctx.newPage();

  // 콘솔 에러 수집
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warn') {
      consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
    }
  });

  // 422 응답 body 수집
  let putResponseBody = '';
  page.on('response', async r => {
    if (r.url().includes('sales-material') && r.request().method() === 'PUT') {
      try {
        putResponseBody = await r.text();
        console.log(`\nPUT 응답 status: ${r.status()}`);
        console.log(`PUT 응답 body: ${putResponseBody}`);
      } catch (e) {}
    }
    if (r.url().includes('sales-material') || r.url().includes('upload')) {
      console.log(`  ${r.request().method()} ${r.url()} → ${r.status()}`);
    }
  });

  try {
    await loginFresh(page);
    await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.reload({ waitUntil: 'networkidle', timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);

    // 현재 JS 번들 확인
    const scripts = await page.evaluate(() =>
      Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src)
    );
    console.log('\n로드된 스크립트:');
    scripts.forEach(s => console.log(`  ${s}`));

    // 편집 모달 열기
    const firstRow = page.locator('table tbody tr').first();
    const editBtn = firstRow.locator('button').nth(0);
    await editBtn.click({ force: true });
    await page.waitForTimeout(1500);
    await shot(page, 'debug-01-edit-modal');

    // 편집 모달에서 요청 payload 확인
    // 파일 없이 저장 시도 (PUT만 발생)
    const saveBtn = page.locator('button').filter({ hasText: /저장/i }).first();
    await saveBtn.click();
    await page.waitForTimeout(2000);
    await shot(page, 'debug-02-after-save');

    console.log('\n콘솔 에러:');
    consoleErrors.forEach(e => console.log(`  ${e}`));

    if (putResponseBody) {
      console.log(`\n422 에러 상세: ${putResponseBody}`);
    } else {
      console.log('\nPUT 응답 body 없음');
    }

    // 에러 토스트 메시지 확인
    const toastText = await page.locator('[class*="toast"], [class*="Toast"], [role="alert"]').textContent().catch(() => '');
    if (toastText) console.log(`\n에러 토스트: ${toastText}`);

    // 모달 내 에러 메시지
    const errMsgs = await page.locator('[class*="error"], [class*="Error"], [aria-invalid="true"]').allTextContents().catch(() => []);
    if (errMsgs.length) console.log(`\n폼 에러: ${errMsgs.join(', ')}`);

  } finally {
    await ctx.close();
  }
}, { timeout: 60_000 });
