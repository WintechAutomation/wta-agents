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
  const userInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="아이디"], input[placeholder*="user" i]').first();
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill('account');
    await page.locator('input[type="password"]').first().fill('test1234');
    await page.locator('button[type="submit"], button').filter({ hasText: /로그인|Login|확인/i }).first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

// ─────────────────────────────────────────────
// [1] 협력업체정보 — 통계 카드 NaN 없음
// ─────────────────────────────────────────────
test('[1] 협력업체정보 — 통계 카드 NaN 없음', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warn') consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
  });

  await login(page);
  await page.goto(`${BASE_URL}/production/partner-management`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await shot(page, '01-partner-management');

  const bodyText = await page.locator('body').textContent().catch(() => '');

  // NaN 여부 확인
  const hasNaN = /\bNaN\b/.test(bodyText || '');
  if (hasNaN) {
    fail('[1-1] NaN 버그', `페이지에 "NaN" 텍스트 존재`);
    // NaN이 있는 요소 찾기
    const nanEls = await page.locator(':text("NaN")').allTextContents().catch(() => []);
    console.log(`NaN 요소: ${nanEls.join(', ')}`);
  } else {
    pass('[1-1] NaN 버그 수정', '"NaN" 텍스트 없음');
  }

  // 통계 카드 4종 확인 (숫자 표시 여부)
  // 일반적으로 카드에 숫자(정수)가 표시됨
  const statCards = page.locator('[class*="card"], [class*="Card"], [class*="stat"], [class*="Stat"]');
  const cardCount = await statCards.count();
  console.log(`통계 카드 수: ${cardCount}`);

  if (cardCount >= 4) {
    let nanInCards = 0;
    let validNumbers = 0;
    for (let i = 0; i < Math.min(cardCount, 8); i++) {
      const cardText = await statCards.nth(i).textContent().catch(() => '');
      if (/\bNaN\b/.test(cardText || '')) {
        nanInCards++;
      }
      if (/\d+/.test(cardText || '')) {
        validNumbers++;
      }
      console.log(`  카드[${i}]: "${cardText?.replace(/\s+/g, ' ').trim().slice(0, 60)}"`);
    }
    if (nanInCards === 0) {
      pass('[1-2] 통계 카드 NaN 없음', `${Math.min(cardCount, 8)}개 카드 확인`);
    } else {
      fail('[1-2] 통계 카드', `${nanInCards}개 카드에 NaN 존재`);
    }
    if (validNumbers > 0) {
      pass('[1-3] 통계 카드 숫자 표시', `${validNumbers}개 카드에 숫자 확인`);
    }
  } else {
    // 다른 방식으로 통계 요소 찾기
    const numericEls = await page.locator('h2, h3, p, span').filter({ hasText: /^\d+$/ }).allTextContents().catch(() => []);
    console.log(`숫자만 표시된 요소: ${numericEls.slice(0, 10).join(', ')}`);
    if (numericEls.length > 0) {
      pass('[1-2] 통계 수치 표시', `숫자 요소 ${numericEls.length}개 확인`);
    } else {
      warn('[1-2] 통계 카드', `카드 ${cardCount}개 (4개 미만), 숫자 요소도 없음`);
    }
  }

  // 콘솔 에러
  const errCount = consoleErrors.filter(e => e.includes('[error]')).length;
  if (errCount === 0) pass('[1-4] 콘솔 에러', '없음');
  else warn('[1-4] 콘솔 에러', `${errCount}건: ${consoleErrors.slice(0, 3).join(' | ')}`);
});

// ─────────────────────────────────────────────
// [2] 스케줄러 관리 — 서브라우트 탭 동기화
// ─────────────────────────────────────────────

const SCHEDULER_ROUTES = [
  { url: '/system/scheduler-management', label: '스케줄러 메인' },
  { url: '/scheduler-management/jobs', label: 'Jobs 탭' },
  { url: '/scheduler-management/logs', label: 'Logs 탭' },
  { url: '/scheduler-management/settings', label: 'Settings 탭' },
];

test('[2] 스케줄러 관리 — 서브라우트 탭 동기화', async ({ page }) => {
  await login(page);

  for (const route of SCHEDULER_ROUTES) {
    // 직접 URL 접근
    await page.goto(`${BASE_URL}${route.url}`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    await page.waitForTimeout(1500);

    const currentUrl = page.url();
    const shotName = `02-scheduler-${route.url.replace(/\//g, '-').replace(/^-/, '')}`;
    await shot(page, shotName);

    // 리다이렉트 여부
    if (!currentUrl.includes('scheduler') && !currentUrl.includes('system')) {
      fail(`[2] ${route.label}`, `리다이렉트됨: ${currentUrl}`);
      continue;
    }

    const bodyText = await page.locator('body').textContent().catch(() => '');

    // 활성 탭 확인
    const activeTabs = await page.locator('[role="tab"][aria-selected="true"], [class*="active"][role="tab"], [class*="tab"][class*="active"], button[class*="selected"]').allTextContents().catch(() => []);
    const allTabs = await page.locator('[role="tab"], [class*="tab-item"], [class*="tabItem"]').allTextContents().catch(() => []);

    console.log(`\n${route.label} (${route.url}):`);
    console.log(`  현재 URL: ${currentUrl}`);
    console.log(`  전체 탭: ${allTabs.map(t => t.trim()).filter(t => t).join(', ')}`);
    console.log(`  활성 탭: ${activeTabs.map(t => t.trim()).filter(t => t).join(', ')}`);

    if (allTabs.length === 0) {
      // tab 방식이 아닌 다른 네비게이션 방식 확인
      const navItems = await page.locator('nav a, [class*="nav"] a, [class*="sidebar"] a').allTextContents().catch(() => []);
      console.log(`  nav 항목: ${navItems.slice(0, 10).join(', ')}`);

      if (/스케줄|scheduler|job|log/i.test(bodyText || '')) {
        pass(`[2] ${route.label}`, '스케줄러 페이지 접근 확인');
      } else if (currentUrl.includes('login')) {
        warn(`[2] ${route.label}`, '로그인 페이지로 리다이렉트 (권한 없음)');
      } else {
        warn(`[2] ${route.label}`, '탭 UI 없음');
      }
      continue;
    }

    // URL 경로에 따른 탭 활성화 확인
    const urlSegment = route.url.split('/').pop() || '';
    const isActive = activeTabs.some(t =>
      t.toLowerCase().includes(urlSegment.toLowerCase()) ||
      (urlSegment === 'scheduler-management' && activeTabs.length > 0)
    );

    if (isActive) {
      pass(`[2] ${route.label}`, `활성 탭: ${activeTabs[0]?.trim()}`);
    } else if (activeTabs.length > 0) {
      warn(`[2] ${route.label}`, `활성 탭 "${activeTabs[0]?.trim()}"가 URL "${urlSegment}"와 불일치`);
    } else {
      warn(`[2] ${route.label}`, '활성 탭 감지 불가');
    }
  }
});

// ─────────────────────────────────────────────
// [2b] 스케줄러 탭 클릭 → URL 변경 확인
// ─────────────────────────────────────────────
test('[2b] 스케줄러 탭 클릭 — URL 동기화', async ({ page }) => {
  await login(page);

  // 메인 URL로 접근
  const mainUrl = `${BASE_URL}/system/scheduler-management`;
  await page.goto(mainUrl, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, '03-scheduler-main');

  const currentUrl = page.url();
  console.log(`스케줄러 메인 URL: ${currentUrl}`);

  if (currentUrl.includes('login')) {
    warn('[2b] 스케줄러 접근', '로그인 리다이렉트 (권한 없음 또는 라우트 미존재)');
    return;
  }

  const tabs = await page.locator('[role="tab"], [class*="tab-item"], [class*="tabItem"], button[class*="tab"]').all();
  console.log(`탭 수: ${tabs.length}`);

  if (tabs.length < 2) {
    warn('[2b] 스케줄러 탭', `탭 ${tabs.length}개 (2개 이상 기대)`);
    // 페이지 내용 확인
    const bodyText = await page.locator('body').textContent().catch(() => '');
    console.log(`페이지 내용 일부: ${bodyText?.slice(0, 300)}`);
    return;
  }

  // 두 번째 탭 클릭
  const secondTab = tabs[1];
  const secondTabText = await secondTab.textContent().catch(() => '');
  await secondTab.click();
  await page.waitForTimeout(1000);

  const afterClickUrl = page.url();
  console.log(`탭 클릭 후 URL: ${afterClickUrl}`);
  await shot(page, '04-scheduler-tab-clicked');

  if (afterClickUrl !== currentUrl) {
    pass('[2b] 탭 클릭 URL 변경', `${currentUrl} → ${afterClickUrl}`);
  } else {
    warn('[2b] 탭 클릭 URL 변경', `URL 변경 없음 (${afterClickUrl})`);
  }

  // 탭 텍스트 확인
  const activeTab = await page.locator('[role="tab"][aria-selected="true"]').first().textContent().catch(() => '');
  if (activeTab) pass('[2b] 탭 활성화', `"${activeTab.trim()}" 활성`);
});
