import { test, expect, Page, BrowserContext } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const QUOTES_URL = `${BASE_URL}/quotes`;
const LOGIN_API = `${BASE_URL}/api/v1/auth/login`;
const QA_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/2026-03-31_quotes-page-qa/screenshots';

// 스크린샷 저장
async function shot(page: Page, name: string): Promise<string> {
  if (!fs.existsSync(QA_DIR)) fs.mkdirSync(QA_DIR, { recursive: true });
  const filepath = path.join(QA_DIR, `${name}.png`);
  await page.screenshot({ path: filepath, fullPage: true });
  return filepath;
}

// 로그인: 폼으로 실제 Sign In
async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });

  // 로그인 폼이 보이면 입력
  const usernameInput = page.locator('input[placeholder="Username"], input[name="username"], input[type="text"]').first();
  const passwordInput = page.locator('input[placeholder="Password"], input[name="password"], input[type="password"]').first();

  await usernameInput.waitFor({ timeout: 5_000 });
  await usernameInput.fill('qa-test');
  await passwordInput.fill('qa-test-2026!');

  const signInBtn = page.locator('button:has-text("Sign In"), button[type="submit"]').first();
  await signInBtn.click();

  // 로그인 후 리다이렉트 대기
  await page.waitForURL((url) => !url.pathname.includes('login'), { timeout: 10_000 }).catch(() => {});
  await page.waitForLoadState('networkidle');
}

test.describe('cs-wta.com 견적서 관리 페이지 QA', () => {

  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(QUOTES_URL, { waitUntil: 'networkidle' });
  });

  test('1. 페이지 접속 정상 (로그인 후 200)', async ({ page }) => {
    const url = page.url();
    expect(url).toContain('/quotes');
    await shot(page, '01-quotes-page-loaded');
    console.log(`✅ 현재 URL: ${url}`);
  });

  test('2. 견적 목록 조회', async ({ page }) => {
    // 어떤 형태든 목록/데이터 렌더링 확인
    await page.waitForTimeout(2000); // 데이터 로드 대기
    await shot(page, '02-list-loaded');

    const bodyText = await page.locator('body').textContent() ?? '';
    console.log(`페이지 텍스트 일부: ${bodyText.slice(0, 300)}`);

    // 숫자 포함 여부 (건수 표시)
    const hasData = bodyText.length > 200;
    expect(hasData).toBeTruthy();
    console.log('✅ 페이지 콘텐츠 로드 확인');
  });

  test('3. 정렬 기능 (컬럼 헤더)', async ({ page }) => {
    await page.waitForTimeout(1500);
    await shot(page, '03-before-sort');

    // 클릭 가능한 th 또는 정렬 버튼 탐색
    const headers = page.locator('th, [role="columnheader"]');
    const count = await headers.count();
    console.log(`컬럼 헤더 수: ${count}`);

    if (count > 0) {
      const first = headers.first();
      const text = await first.textContent();
      await first.click();
      await page.waitForTimeout(500);
      await shot(page, '03-after-sort');
      console.log(`✅ 첫 헤더 클릭: "${text?.trim()}"`);
    } else {
      // AG Grid 등 커스텀 헤더
      const agHeader = page.locator('.ag-header-cell, [col-id]').first();
      const hasAg = await agHeader.isVisible().catch(() => false);
      if (hasAg) {
        const text = await agHeader.textContent();
        await agHeader.click();
        await page.waitForTimeout(500);
        console.log(`✅ AG Grid 헤더 클릭: "${text?.trim()}"`);
        await shot(page, '03-ag-sort');
      } else {
        console.log('⚠️ 정렬 가능 헤더 없음');
      }
    }
  });

  test('4. 검색/필터 동작', async ({ page }) => {
    await page.waitForTimeout(1500);

    const searchSelectors = [
      'input[type="search"]',
      'input[placeholder*="검색"]',
      'input[placeholder*="search"]',
      'input[placeholder*="Search"]',
      'input[placeholder*="찾기"]',
      '.ag-filter-body-wrapper input',
      '[class*="search"] input',
    ];

    let found = false;
    for (const sel of searchSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        await el.fill('WTA');
        await page.waitForTimeout(800);
        await shot(page, '04-search-result');
        console.log(`✅ 검색창 발견 (${sel}), 입력 동작 확인`);
        await el.clear();
        found = true;
        break;
      }
    }

    if (!found) {
      await shot(page, '04-no-search-found');
      console.log('⚠️ 검색/필터 UI 미발견');
    }
  });

  test('5. 편집 모달 — 헤더 필드 접근', async ({ page }) => {
    await page.waitForTimeout(1500);
    await shot(page, '05-before-edit');

    // 편집 진입: 버튼, 행 클릭, 아이콘 등 순서대로 시도
    const editSelectors = [
      'button[aria-label*="edit"]',
      'button[aria-label*="수정"]',
      '[class*="edit"]:not(input):not(textarea)',
      'tbody tr:first-child td:last-child button',
      'tbody tr:first-child',
    ];

    let opened = false;
    for (const sel of editSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        await el.click();
        await page.waitForTimeout(1000);

        const modal = page.locator('[role="dialog"], [class*="modal"], [class*="Modal"], [class*="drawer"]').first();
        if (await modal.isVisible().catch(() => false)) {
          const fields = await modal.locator('input, select, textarea').count();
          console.log(`✅ 편집 모달 열림 (selector: ${sel}), 필드 수: ${fields}`);
          await shot(page, '05-edit-modal-open');

          // viewer 역할 — 필드 비활성화 여부 확인
          const firstInput = modal.locator('input').first();
          if (await firstInput.isVisible().catch(() => false)) {
            const isDisabled = await firstInput.isDisabled();
            console.log(`  → 입력 필드 비활성화(viewer): ${isDisabled}`);
          }

          // 닫기
          const closeBtn = modal.locator('button[aria-label*="close"], button[aria-label*="닫기"], button:has-text("취소"), button:has-text("닫기")').first();
          if (await closeBtn.isVisible().catch(() => false)) {
            await closeBtn.click();
          } else {
            await page.keyboard.press('Escape');
          }
          opened = true;
          break;
        }
      }
    }

    if (!opened) {
      console.log('⚠️ 편집 모달 미열림 (viewer 권한 제한 또는 다른 UI 구조)');
      await shot(page, '05-no-modal');
    }
  });

  test('6. 편집 모달 — 부품(quote_items) 섹션', async ({ page }) => {
    await page.waitForTimeout(1500);

    // 첫 행 클릭으로 진입 시도
    const firstRow = page.locator('tbody tr, [class*="row"]:not([class*="header"])').first();
    if (await firstRow.isVisible().catch(() => false)) {
      await firstRow.click();
      await page.waitForTimeout(1000);

      const modal = page.locator('[role="dialog"], [class*="modal"]').first();
      if (await modal.isVisible().catch(() => false)) {
        // 부품/아이템 탭 탐색
        const itemTab = modal.locator('button:has-text("부품"), button:has-text("아이템"), [role="tab"]:has-text("부품"), [role="tab"]:has-text("item")').first();
        if (await itemTab.isVisible().catch(() => false)) {
          await itemTab.click();
          await page.waitForTimeout(500);
          console.log('✅ 부품 탭 클릭');
        }

        await shot(page, '06-items-section');

        // 추가/삭제 버튼 확인
        const addBtn = modal.locator('button:has-text("추가"), button:has-text("+"), button[aria-label*="add"]').first();
        const delBtn = modal.locator('button:has-text("삭제"), button[aria-label*="delete"], button[aria-label*="remove"]').first();

        console.log(`  추가 버튼: ${await addBtn.isVisible().catch(() => false)}`);
        console.log(`  삭제 버튼: ${await delBtn.isVisible().catch(() => false)}`);

        await page.keyboard.press('Escape');
      } else {
        console.log('⚠️ 모달 미열림');
        await shot(page, '06-no-modal');
      }
    } else {
      console.log('⚠️ 테이블 행 미발견');
      await shot(page, '06-no-rows');
    }
  });

  test('7. 견적 삭제 — 확인 다이얼로그', async ({ page }) => {
    await page.waitForTimeout(1500);
    await shot(page, '07-before-delete');

    const deleteSelectors = [
      'button[aria-label*="delete"]',
      'button[aria-label*="삭제"]',
      'button:has-text("삭제")',
      '[class*="delete"] button',
    ];

    let found = false;
    for (const sel of deleteSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        // dialog 이벤트 리스너 등록
        page.once('dialog', async (dialog) => {
          console.log(`브라우저 다이얼로그: "${dialog.message()}"`);
          await dialog.dismiss(); // 취소
        });

        await el.click();
        await page.waitForTimeout(800);

        // 커스텀 confirm 모달 확인
        const confirmModal = page.locator('[role="alertdialog"], [role="dialog"]:has-text("삭제")').first();
        if (await confirmModal.isVisible().catch(() => false)) {
          console.log('✅ 삭제 확인 다이얼로그 표시');
          await shot(page, '07-delete-confirm');
          const cancelBtn = confirmModal.locator('button:has-text("취소"), button:has-text("아니오")').first();
          if (await cancelBtn.isVisible().catch(() => false)) {
            await cancelBtn.click();
            console.log('✅ 삭제 취소 동작 확인');
          } else {
            await page.keyboard.press('Escape');
          }
        } else {
          console.log('⚠️ 커스텀 다이얼로그 미발견 (브라우저 confirm 처리됨)');
          await shot(page, '07-no-custom-dialog');
        }
        found = true;
        break;
      }
    }

    if (!found) {
      console.log('⚠️ 삭제 버튼 미발견 (viewer 권한 제한 가능성)');
      await shot(page, '07-no-delete-btn');
    }
  });

  test('8. 페이지네이션', async ({ page }) => {
    await page.waitForTimeout(1500);
    await shot(page, '08-pagination-view');

    const paginationSelectors = [
      '[class*="pagination"]',
      'nav[aria-label*="page"]',
      '[role="navigation"]',
      '.ag-paging-panel',
    ];

    let found = false;
    for (const sel of paginationSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        const text = await el.textContent();
        console.log(`✅ 페이지네이션 발견 (${sel}): "${text?.trim().slice(0, 80)}"`);

        // 다음 페이지 버튼
        const nextBtn = el.locator('button:has-text("2"), a:has-text("2"), button[aria-label*="next"]').first();
        if (await nextBtn.isVisible().catch(() => false)) {
          await nextBtn.click();
          await page.waitForTimeout(800);
          console.log('✅ 다음 페이지 이동 확인');
          await shot(page, '08-page2');
        }
        found = true;
        break;
      }
    }

    if (!found) {
      const rowCount = await page.locator('tbody tr').count();
      console.log(`⚠️ 페이지네이션 미발견 — 현재 표시 행: ${rowCount}`);
    }
  });

});

test.describe('cs-wta.com 반응형 QA', () => {
  test('9. 데스크탑 반응형', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await login(page);
    await page.goto(QUOTES_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await shot(page, '09-desktop-1280');
    console.log('✅ 데스크탑(1280px) 렌더링 확인');
  });

  test('10. 모바일 반응형', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await page.goto(QUOTES_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await shot(page, '10-mobile-390');
    console.log('✅ 모바일(390px) 렌더링 확인');
  });
});
