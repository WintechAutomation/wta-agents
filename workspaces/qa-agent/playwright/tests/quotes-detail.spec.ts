import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const QUOTES_URL = `${BASE_URL}/quotes`;
const QA_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/2026-03-31_quotes-page-qa/screenshots';

async function shot(page: Page, name: string) {
  const filepath = path.join(QA_DIR, `${name}.png`);
  await page.screenshot({ path: filepath, fullPage: true });
}

async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.locator('input[placeholder="Username"]').fill('qa-test');
  await page.locator('input[type="password"]').fill('qa-test-2026!');
  await page.locator('button:has-text("Sign In")').click();
  await page.waitForURL((url) => !url.pathname.includes('login'), { timeout: 10_000 }).catch(() => {});
  await page.waitForLoadState('networkidle');
  await page.goto(QUOTES_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
}

test.describe('견적서 페이지 상세 QA', () => {

  test('3-상세. 정렬 버튼 6개 동작', async ({ page }) => {
    await login(page);

    // 정렬 버튼: 견적일, CS번호, 고객사, 금액, 회사, 연도
    const sortLabels = ['견적일', 'CS번호', '고객사', '금액', '회사', '연도'];
    const results: string[] = [];

    for (const label of sortLabels) {
      const btn = page.locator(`button:has-text("${label}")`).first();
      const visible = await btn.isVisible().catch(() => false);
      if (visible) {
        await btn.click();
        await page.waitForTimeout(400);
        results.push(`✅ ${label} 정렬 클릭`);
      } else {
        results.push(`⚠️ ${label} 버튼 미발견`);
      }
    }

    console.log(results.join('\n'));
    await shot(page, '03-sort-all');
  });

  test('4-상세. 검색 버튼 클릭 후 필터링 확인', async ({ page }) => {
    await login(page);

    const searchInput = page.locator('input[placeholder*="검색"]').first();
    await searchInput.fill('교세라');

    const searchBtn = page.locator('button:has-text("검색")').first();
    if (await searchBtn.isVisible().catch(() => false)) {
      await searchBtn.click();
      await page.waitForTimeout(1000);
    }

    await shot(page, '04-search-교세라');
    const bodyText = await page.locator('body').textContent() ?? '';
    const hasKeyword = bodyText.includes('교세라');
    console.log(`✅ "교세라" 검색 결과 포함: ${hasKeyword}`);
  });

  test('5-상세. 편집 아이콘 클릭 (SVG 버튼)', async ({ page }) => {
    await login(page);
    await shot(page, '05-before-edit-icon');

    // SVG 연필 아이콘 버튼 — 각 항목 오른쪽에 위치
    // aria-label 또는 title 속성으로 탐색
    const editIcon = page.locator('button svg, [class*="edit"] svg, button[title*="수정"], button[title*="edit"]').first();
    
    // 더 넓은 범위로 버튼 탐색
    const allButtons = page.locator('button');
    const count = await allButtons.count();
    console.log(`전체 버튼 수: ${count}`);

    // 각 버튼의 class/aria 확인
    for (let i = 0; i < Math.min(count, 30); i++) {
      const btn = allButtons.nth(i);
      const cls = await btn.getAttribute('class') ?? '';
      const aria = await btn.getAttribute('aria-label') ?? '';
      const title = await btn.getAttribute('title') ?? '';
      const text = (await btn.textContent() ?? '').trim().slice(0, 20);
      if (cls || aria || title) {
        console.log(`버튼[${i}]: class="${cls.slice(0,50)}" aria="${aria}" title="${title}" text="${text}"`);
      }
    }
  });

  test('5-상세2. 편집 모달 열기', async ({ page }) => {
    await login(page);

    // 첫 번째 항목에서 편집 아이콘 찾기 (마우스오버 후 나타날 수 있음)
    const firstItem = page.locator('[class*="quote"], [class*="item"], [class*="card"]').first();
    
    if (await firstItem.isVisible().catch(() => false)) {
      await firstItem.hover();
      await page.waitForTimeout(500);
      await shot(page, '05-hover-state');
    }

    // 연필 아이콘 (Pencil/Edit icon SVG) 버튼들 중 첫 번째
    // Lucide/Heroicons 연필 아이콘은 보통 path d="M..." 포함
    const pencilBtns = page.locator('button').filter({ has: page.locator('svg') });
    const pCount = await pencilBtns.count();
    console.log(`SVG 포함 버튼 수: ${pCount}`);

    if (pCount > 0) {
      // 편집 버튼 (연필)이 보통 삭제 버튼 바로 앞에 있음
      // 리스트 항목당 2개 아이콘 버튼이 있을 것으로 예상
      const editBtn = pencilBtns.first();
      await editBtn.click();
      await page.waitForTimeout(1000);
      await shot(page, '05-after-edit-click');

      const modal = page.locator('[role="dialog"]').first();
      if (await modal.isVisible().catch(() => false)) {
        console.log('✅ 편집 모달 열림');
        const fields = await modal.locator('input, select, textarea').count();
        console.log(`  필드 수: ${fields}`);
        await shot(page, '05-modal-open');
        await page.keyboard.press('Escape');
      } else {
        console.log('⚠️ 모달 미열림 — 다른 동작 발생');
      }
    }
  });

  test('8-상세. 무한 스크롤 또는 전체 목록 확인', async ({ page }) => {
    await login(page);

    // 초기 항목 수
    const initialItems = await page.locator('[class*="quote-"], [class*="QuoteItem"], [class*="quote_"]').count();
    console.log(`초기 항목(커스텀 클래스): ${initialItems}`);

    // 스크롤 다운
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await shot(page, '08-scroll-bottom');

    // 스크롤 후 항목 수
    const afterItems = await page.locator('[class*="quote-"], [class*="QuoteItem"], [class*="quote_"]').count();
    console.log(`스크롤 후 항목: ${afterItems}`);

    // 페이지 하단 정보
    const bottomText = await page.evaluate(() => {
      const body = document.body.innerText;
      return body.slice(-500);
    });
    console.log(`페이지 하단 텍스트: ${bottomText.slice(0, 200)}`);
  });

  test('9-10-상세. 반응형 스크린샷', async ({ page }) => {
    // 데스크탑
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await shot(page, '09-desktop-1440');
    console.log('✅ 1440px 데스크탑');

    // 태블릿
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await shot(page, '09-tablet-768');
    console.log('✅ 768px 태블릿');

    // 모바일
    await page.setViewportSize({ width: 375, height: 812 });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await shot(page, '10-mobile-375');
    console.log('✅ 375px 모바일');
  });

});
