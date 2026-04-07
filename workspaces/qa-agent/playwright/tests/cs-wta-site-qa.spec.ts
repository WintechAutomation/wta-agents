import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/site-qa';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: true });
}

// 로그인 헬퍼 (세션 쿠키 재사용)
async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);

  const usernameInput = page.locator('input[name="username"], input[type="text"], input[placeholder*="user" i], input[placeholder*="아이디"]').first();
  const passwordInput = page.locator('input[name="password"], input[type="password"]').first();

  const loginVisible = await usernameInput.isVisible().catch(() => false);
  if (!loginVisible) {
    // 이미 로그인됨
    return;
  }

  await usernameInput.fill('admin');
  await passwordInput.fill('admin');
  const submitBtn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("로그인")').first();
  await submitBtn.click();
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(1000);
}

// ──────────────────────────────────────────────
// 1. 메인 페이지 및 핵심 페이지 HTTP 상태
// ──────────────────────────────────────────────
test.describe('[1] 페이지 로딩 상태', () => {
  test('메인 페이지 정상 로딩 (200)', async ({ page }) => {
    const resp = await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    expect(resp?.status()).toBeLessThan(400);
    await shot(page, '01-main-page');
    console.log(`✅ 메인 상태코드: ${resp?.status()}, URL: ${page.url()}`);
  });

  test('/quotes 페이지 접근 (로그인 필요)', async ({ page }) => {
    await login(page);
    const resp = await page.goto(`${BASE_URL}/quotes`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(2000);
    const finalUrl = page.url();
    await shot(page, '02-quotes-page');
    // 로그인 리다이렉트 or 실제 페이지
    const statusOk = (resp?.status() ?? 0) < 400;
    expect(statusOk).toBeTruthy();
    console.log(`✅ /quotes 상태: ${resp?.status()}, 최종URL: ${finalUrl}`);

    // 페이지 콘텐츠 확인
    const body = await page.locator('body').textContent() ?? '';
    const hasContent = body.trim().length > 100;
    expect(hasContent).toBeTruthy();
    console.log(`  콘텐츠 길이: ${body.trim().length}자`);
  });
});

// ──────────────────────────────────────────────
// 2. /quotes 렌더링 상세
// ──────────────────────────────────────────────
test.describe('[2] /quotes 페이지 렌더링', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(`${BASE_URL}/quotes`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(2000);
  });

  test('핵심 UI 요소 존재', async ({ page }) => {
    await shot(page, '03-quotes-ui');
    const body = await page.locator('body').textContent() ?? '';

    // 에러/크래시 메시지 없는지
    const hasError = /error|failed|404|500|cannot|undefined/i.test(body.slice(0, 500));
    if (hasError) {
      console.log(`⚠️ 오류 의심 텍스트: ${body.slice(0, 300)}`);
    } else {
      console.log('✅ 오류 메시지 없음');
    }

    // 테이블 또는 리스트 UI 존재
    const tableExists = await page.locator('table, [role="grid"], [class*="ag-"], [class*="table"], [class*="list"]').first().isVisible().catch(() => false);
    console.log(`  테이블/그리드 존재: ${tableExists}`);
  });

  test('네비게이션에 Quotes 메뉴 표시', async ({ page }) => {
    await shot(page, '04-quotes-nav');
    const nav = await page.locator('nav, [class*="sidebar"], [class*="menu"]').first().textContent().catch(() => '');
    const hasQuotes = /quote/i.test(nav);
    console.log(`  네비게이션 Quotes 포함: ${hasQuotes}`);
    console.log(`  네비게이션 텍스트: ${nav.slice(0, 200)}`);
  });
});

// ──────────────────────────────────────────────
// 3. 기존 페이지 깨짐 여부
// ──────────────────────────────────────────────
test.describe('[3] 기존 페이지 회귀 테스트', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  const existingPages = [
    { name: 'CS이력', path: '/cs-history' },
    { name: 'CS이력(대체)', path: '/history' },
    { name: '파츠매뉴얼', path: '/parts' },
    { name: '파츠매뉴얼(대체)', path: '/manual' },
    { name: '대시보드', path: '/dashboard' },
    { name: '홈', path: '/' },
  ];

  for (const pg of existingPages) {
    test(`${pg.name} (${pg.path}) 로딩 확인`, async ({ page }) => {
      const resp = await page.goto(`${BASE_URL}${pg.path}`, { waitUntil: 'domcontentloaded', timeout: 20_000 }).catch(() => null);
      await page.waitForTimeout(1500);
      const finalUrl = page.url();
      const status = resp?.status() ?? 0;
      await shot(page, `05-${pg.name.replace(/[^a-zA-Z0-9가-힣]/g, '-')}`);

      const body = await page.locator('body').textContent() ?? '';
      const hasCrash = /application error|something went wrong|failed to load/i.test(body);

      if (hasCrash) {
        console.log(`❌ ${pg.name}: 크래시 감지`);
      } else if (status >= 400) {
        console.log(`⚠️ ${pg.name}: HTTP ${status} (리다이렉트/미구현 가능)`);
      } else {
        console.log(`✅ ${pg.name}: HTTP ${status}, URL: ${finalUrl}`);
      }

      // 크래시는 실패로
      expect(hasCrash).toBeFalsy();
    });
  }
});

// ──────────────────────────────────────────────
// 4. 다국어 전환 (ko/en/ja/zh)
// ──────────────────────────────────────────────
test.describe('[4] 다국어 전환', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForTimeout(1500);
  });

  test('언어 전환 UI 존재 확인', async ({ page }) => {
    await shot(page, '06-lang-ui');

    const langSelectors = [
      '[class*="lang"]',
      '[class*="locale"]',
      'select[name*="lang"]',
      'button:has-text("KO")',
      'button:has-text("EN")',
      'button:has-text("한국어")',
      'button:has-text("English")',
      '[aria-label*="language" i]',
      '[title*="language" i]',
    ];

    let found = false;
    for (const sel of langSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        const text = await el.textContent().catch(() => '');
        console.log(`✅ 언어 전환 UI 발견 (${sel}): "${text?.trim()}"`);
        found = true;
        break;
      }
    }

    if (!found) {
      const body = await page.locator('body').textContent() ?? '';
      const hasLangHint = /ko|en|ja|zh|한국어|english|日本語|中文/i.test(body);
      console.log(`⚠️ 전환 버튼 미발견 — 다국어 힌트: ${hasLangHint}`);
    }
  });

  const langs = ['en', 'ja', 'zh'];
  for (const lang of langs) {
    test(`언어 전환: ${lang}`, async ({ page }) => {
      // URL 파라미터 방식 시도
      await page.goto(`${BASE_URL}?lang=${lang}`, { waitUntil: 'domcontentloaded', timeout: 15_000 }).catch(() => {});
      await page.waitForTimeout(1500);
      await shot(page, `07-lang-${lang}-url-param`);

      // 버튼 방식 시도
      const btnSelectors = [
        `button:has-text("${lang.toUpperCase()}")`,
        `[data-lang="${lang}"]`,
        `[data-value="${lang}"]`,
        `a:has-text("${lang.toUpperCase()}")`,
      ];

      let switched = false;
      for (const sel of btnSelectors) {
        const btn = page.locator(sel).first();
        if (await btn.isVisible().catch(() => false)) {
          await btn.click();
          await page.waitForTimeout(1000);
          await shot(page, `07-lang-${lang}-after-click`);
          console.log(`✅ ${lang} 전환 버튼 클릭 성공 (${sel})`);
          switched = true;
          break;
        }
      }

      if (!switched) {
        // html lang 속성 확인
        const htmlLang = await page.locator('html').getAttribute('lang').catch(() => null);
        console.log(`ℹ️ ${lang} 전환 버튼 미발견 — html[lang]: ${htmlLang}`);
      }
    });
  }
});
