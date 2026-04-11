import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://mes-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/mes-qa';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}
function pass(k: string, d = '') { console.log(`✅ ${k}${d ? ': ' + d : ''}`); }
function fail(k: string, d = '') { console.log(`❌ ${k}${d ? ': ' + d : ''}`); }
function warn(k: string, d = '') { console.log(`⚠️  ${k}${d ? ': ' + d : ''}`); }

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(800);
  const userInput = page.locator('input[type="text"], input[name="username"]').first();
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill('account');
    await page.locator('input[type="password"]').first().fill('test1234');
    await page.locator('button[type="submit"], button').filter({ hasText: /로그인|Login/i }).first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

test('스케줄러 서브라우트 탭 직접 접근 검증', async ({ page }) => {
  await login(page);

  // 먼저 메인 접근해서 실제 탭 목록 + URL 확인
  await page.goto(`${BASE_URL}/system/scheduler-management`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, '05-scheduler-tabs-discovery');

  const tabs = await page.locator('[role="tab"]').all();
  console.log(`\n탭 목록 (${tabs.length}개):`);

  // 각 탭 클릭해서 URL 수집
  const tabRoutes: { label: string; url: string }[] = [];
  for (const tab of tabs) {
    const label = (await tab.textContent().catch(() => '')).trim();
    await tab.click();
    await page.waitForTimeout(600);
    const url = page.url();
    tabRoutes.push({ label, url });
    console.log(`  "${label}" → ${url}`);
  }

  // 각 서브라우트 직접 접근 → 해당 탭 활성화 확인
  console.log('\n서브라우트 직접 접근 테스트:');
  let passCount = 0;
  let failCount = 0;

  for (const { label, url } of tabRoutes) {
    // 직접 URL 접근 (홈에서 다시)
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15_000 });
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    await page.waitForTimeout(1200);

    const currentUrl = page.url();
    const shotName = `06-scheduler-direct-${label.replace(/[\s\/]/g, '-')}`;
    await shot(page, shotName);

    // 활성 탭 확인
    const activeTab = await page.locator('[role="tab"][aria-selected="true"]').first().textContent().catch(() => '');
    const allActiveTabs = await page.locator('[role="tab"][aria-selected="true"]').allTextContents().catch(() => []);

    if (!currentUrl.includes('login') && activeTab?.trim() === label) {
      pass(`직접접근 "${label}"`, `활성탭 "${activeTab?.trim()}" ✓`);
      passCount++;
    } else if (!currentUrl.includes('login') && allActiveTabs.some(t => t.trim() === label)) {
      pass(`직접접근 "${label}"`, `활성탭 일치 ✓`);
      passCount++;
    } else if (currentUrl.includes('login')) {
      fail(`직접접근 "${label}"`, `로그인 리다이렉트 (URL: ${url})`);
      failCount++;
    } else if (!activeTab?.trim()) {
      warn(`직접접근 "${label}"`, `활성탭 감지 불가 (현재URL: ${currentUrl})`);
    } else {
      fail(`직접접근 "${label}"`, `활성탭 "${activeTab?.trim()}" ≠ 기대 "${label}"`);
      failCount++;
    }
  }

  console.log(`\n최종: ${passCount}/${tabRoutes.length} PASS, ${failCount} FAIL`);

  if (failCount === 0 && passCount > 0) {
    pass('스케줄러 탭 동기화', `전체 ${tabRoutes.length}개 탭 서브라우트 정상`);
  } else if (failCount > 0) {
    fail('스케줄러 탭 동기화', `${failCount}개 탭 URL 불일치`);
  }
}, { timeout: 90_000 });
