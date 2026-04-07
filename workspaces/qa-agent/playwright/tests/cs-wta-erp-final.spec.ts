import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/erp-final';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

test('ERP 검색 자동완성 최종 검증', async ({ page }) => {
  // 로그인
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(800);
  const pw = page.locator('input[type="password"]').first();
  if (await pw.isVisible().catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await pw.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1200);
  }

  // 강제 새로고침 (캐시 무효화)
  await page.goto(`${BASE_URL}/inventory?tab=stock`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.evaluate(() => { location.reload(); });
  await page.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(2000);

  // Add Stock 클릭
  await page.locator('button').filter({ hasText: /Add Stock/i }).first().click();
  await page.waitForTimeout(1500);

  // ERP Search 모드 클릭
  await page.locator('button').filter({ hasText: /ERP\s*(검색|Search)/i }).first().click();
  await page.waitForTimeout(800);
  await shot(page, '01-erp-mode');

  // ERP input 확인
  const erpInput = page.locator('input[placeholder*="ERP" i], input[placeholder*="item code" i], input[placeholder*="Search ERP" i]').first();
  const ph = await erpInput.getAttribute('placeholder').catch(() => '');
  console.log(`ERP input placeholder: "${ph}"`);

  // 네트워크 요청 모니터링
  const apiRequests: string[] = [];
  page.on('request', (req) => {
    if (req.url().includes('/api/') || req.url().includes('erp') || req.url().includes('item')) {
      apiRequests.push(`${req.method()} ${req.url()}`);
    }
  });
  page.on('response', (res) => {
    if (res.url().includes('/api/') || res.url().includes('erp') || res.url().includes('item')) {
      apiRequests.push(`→ ${res.status()} ${res.url()}`);
    }
  });

  // 2글자 입력
  await erpInput.click();
  await erpInput.fill('in');
  await page.waitForTimeout(3000); // 넉넉히 3초 대기
  await shot(page, '02-after-typing');
  console.log(`\n네트워크 요청 (입력 후):\n${apiRequests.join('\n') || '  없음'}`);

  // 드롭다운/결과 탐색 (최대한 광범위)
  const allVisible = await page.locator('*:visible').all();
  let dropFound = false;

  // bbox 기준: input 아래에 새로 생긴 요소
  const inputBox = await erpInput.boundingBox().catch(() => null);
  if (inputBox) {
    for (const el of allVisible) {
      const bbox = await el.boundingBox().catch(() => null);
      if (!bbox) continue;
      // input 바로 아래 (y > input.y + input.height, x 근접)
      if (bbox.y > inputBox.y + inputBox.height - 5 &&
          bbox.y < inputBox.y + inputBox.height + 300 &&
          bbox.width > 150) {
        const text = await el.textContent().catch(() => '') ?? '';
        const cls = (await el.getAttribute('class').catch(() => '') ?? '').slice(0, 80);
        if (text.trim().length > 3) {
          console.log(`  후보 요소: bbox=(${Math.round(bbox.x)},${Math.round(bbox.y)},${Math.round(bbox.width)}x${Math.round(bbox.height)}) cls="${cls}" text="${text.replace(/\s+/g,' ').slice(0,120)}"`);
          if (/item|part|insert|code|erp/i.test(text)) {
            console.log(`✅ ERP 검색 결과 발견!`);
            dropFound = true;
          }
        }
      }
    }
  }

  // 에러/결과 메시지 탐색
  for (const sel of [
    '[class*="error"]', '.text-red-500', '.text-red-600',
    '[role="alert"]', '[class*="alert"]',
    '[class*="empty"]', '[class*="no-result"]',
  ]) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      const t = await el.textContent().catch(() => '') ?? '';
      if (t.trim() && t.trim() !== 'Logout') {
        console.log(`메시지(${sel}): "${t.trim().slice(0,100)}"`);
      }
    }
  }

  // 입력 후 DOM 스냅샷 (input 컨테이너 주변)
  const nearbyHTML = await erpInput.evaluate((el) => {
    let node: Element | null = el;
    for (let i = 0; i < 4; i++) node = node?.parentElement ?? node;
    return node?.innerHTML ?? '';
  }).catch(() => '');
  console.log(`\ninput 주변 DOM(앞1000):\n${nearbyHTML.replace(/\s+/g,' ').slice(0, 1000)}`);

  if (!dropFound) {
    console.log('⚠️ ERP 검색 결과 미표시');
  }
});
