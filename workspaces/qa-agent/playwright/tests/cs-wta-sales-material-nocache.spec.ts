import { test, Browser, BrowserContext, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { chromium } from '@playwright/test';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material-nocache';
const FIXTURES = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/fixtures';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

function pass(k: string, d = '') { console.log(`✅ ${k}${d ? ': ' + d : ''}`); }
function fail(k: string, d = '') { console.log(`❌ ${k}${d ? ': ' + d : ''}`); }
function warn(k: string, d = '') { console.log(`⚠️  ${k}${d ? ': ' + d : ''}`); }

/** 완전 새 컨텍스트 생성 — 캐시/쿠키 없음 */
async function freshContext(browser: Browser): Promise<BrowserContext> {
  return browser.newContext({
    bypassCSP: true,
    ignoreHTTPSErrors: true,
    // 캐시 완전 비활성화
    serviceWorkers: 'block',
    extraHTTPHeaders: {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
    },
  });
}

async function loginFresh(page: Page) {
  // hard-reload 방식으로 접근
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

async function hardGoto(page: Page, url: string) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  // 캐시 무효화 hard-reload (Ctrl+Shift+R 효과)
  await page.evaluate(() => {
    performance.clearResourceTimings();
  });
  await page.reload({ waitUntil: 'networkidle', timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(1500);
}

// ─────────────────────────────────────────────
// [1] 등록 모달 — 파일 input 3개 + 단일 저장
// ─────────────────────────────────────────────
test('[1] 등록 모달 — 캐시 무효화 후 파일 input 3개 + 단일 저장', async ({ browser }) => {
  const ctx = await freshContext(browser);
  const page = await ctx.newPage();

  const networkLog: { method: string; url: string; status: number }[] = [];
  page.on('response', async r => {
    const url = r.url();
    if (url.includes('sales-material') || url.includes('upload') || url.includes('s3')) {
      networkLog.push({ method: r.request().method(), url: r.url(), status: r.status() });
    }
  });

  try {
    await loginFresh(page);
    await hardGoto(page, `${BASE_URL}/sales-material`);
    await shot(page, '01-list-nocache');

    // 현재 JS 번들 확인 (캐시 무효화 여부)
    const scripts = await page.evaluate(() =>
      Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src)
    );
    const mainBundle = scripts.find(s => s.includes('index-') || s.includes('main-'));
    console.log(`로드된 JS 번들: ${mainBundle || '확인 불가'}`);

    // 신규 등록 버튼
    const addBtn = page.locator('button').filter({ hasText: /신규\s*등록|등록/i }).first();
    if (!await addBtn.isVisible().catch(() => false)) { fail('[1]', '신규 등록 버튼 없음'); return; }
    await addBtn.click();
    await page.waitForTimeout(1500);
    await shot(page, '02-register-modal-nocache');

    // 파일 input 개수 확인 (핵심)
    const fileInputs = await page.locator('input[type="file"]').all();
    console.log(`파일 input 수: ${fileInputs.length}`);

    // 안내 문구 확인 (구 버전에는 있음)
    const modalText = await page.locator('body').textContent().catch(() => '');
    const hasLegacyMsg = /먼저 저장하면/.test(modalText || '');
    console.log(`레거시 안내문("먼저 저장하면...") 존재: ${hasLegacyMsg}`);

    if (hasLegacyMsg) {
      fail('[1] 등록 모달 단일 업로드', '레거시 "먼저 저장하면..." 안내문 여전히 존재 — 캐시 문제 또는 배포 미적용');
      return;
    }

    if (fileInputs.length >= 3) {
      pass('[1] 파일 input 3개', `${fileInputs.length}개 확인`);
    } else if (fileInputs.length > 0) {
      warn('[1] 파일 input', `${fileInputs.length}개 (3개 기대)`);
    } else {
      // 업로드 버튼/영역 확인
      const uploadBtns = await page.locator('button').filter({ hasText: /이미지|도면|SOP|업로드/i }).count();
      console.log(`파일 업로드 버튼: ${uploadBtns}개`);
      if (uploadBtns > 0) {
        warn('[1] 파일 업로드', `파일 input 없음, 업로드 버튼 ${uploadBtns}개`);
      } else {
        fail('[1] 파일 업로드', '파일 input 및 업로드 UI 모두 없음');
      }
    }

    // 필수 필드 + 파일 입력 후 저장
    // 품명 입력
    const nameInput = page.locator('input[type="text"]:visible').first();
    await nameInput.fill('QA-캐시테스트-001');
    await page.waitForTimeout(300);

    // 파일 업로드
    if (fileInputs.length >= 1) await fileInputs[0].setInputFiles(path.join(FIXTURES, 'test-image.png'));
    if (fileInputs.length >= 2) await fileInputs[1].setInputFiles(path.join(FIXTURES, 'test-drawing.pdf'));
    if (fileInputs.length >= 3) await fileInputs[2].setInputFiles(path.join(FIXTURES, 'test-sop.pdf'));
    await page.waitForTimeout(500);
    await shot(page, '03-register-files-selected');

    const saveBtn = page.locator('button').filter({ hasText: /저장/i }).first();
    const networkBefore = networkLog.length;
    await saveBtn.click();
    await page.waitForTimeout(3000);
    await shot(page, '04-register-after-save');

    // 저장 후 네트워크 확인
    const newReqs = networkLog.slice(networkBefore);
    console.log('\n등록 저장 후 API 요청:');
    for (const r of newReqs) console.log(`  ${r.method} ${r.url} → ${r.status}`);

    const postReqs = newReqs.filter(r => r.method === 'POST');
    const legacyImgPost = newReqs.filter(r => r.url.includes('/images'));
    const failedReqs = newReqs.filter(r => r.status >= 400);

    if (legacyImgPost.length > 0) {
      fail('[1] 단일 저장', `레거시 /images 엔드포인트 호출됨 → ${legacyImgPost.map(r => r.url).join(', ')}`);
    } else if (failedReqs.length > 0) {
      fail('[1] 단일 저장', failedReqs.map(r => `${r.status} ${r.url}`).join(', '));
    } else if (postReqs.length > 0) {
      pass('[1] 단일 저장 원자 업로드', `POST ${postReqs.length}건 성공 (레거시 /images 없음)`);
    } else {
      warn('[1] 단일 저장', `POST 요청 없음, 전체 요청: ${newReqs.length}건`);
    }

    // 모달 닫혔는지 확인
    const modalClosed = !/판매자재\s*등록/i.test(await page.locator('body').textContent().catch(() => '') || '');
    if (modalClosed) pass('[1] 모달 닫힘', '저장 성공');
    else warn('[1] 모달', '저장 후 모달 미닫힘');

  } finally {
    await ctx.close();
  }
}, { timeout: 60_000 });

// ─────────────────────────────────────────────
// [2] 편집 모달 — PUT 200 확인
// ─────────────────────────────────────────────
test('[2] 편집 모달 — 캐시 무효화 후 PUT 200 확인', async ({ browser }) => {
  const ctx = await freshContext(browser);
  const page = await ctx.newPage();

  const networkLog: { method: string; url: string; status: number }[] = [];
  page.on('response', async r => {
    if (r.url().includes('sales-material') || r.url().includes('upload') || r.url().includes('s3')) {
      networkLog.push({ method: r.request().method(), url: r.url(), status: r.status() });
    }
  });

  try {
    await loginFresh(page);
    await hardGoto(page, `${BASE_URL}/sales-material`);

    const firstRow = page.locator('table tbody tr').first();
    if (!await firstRow.isVisible().catch(() => false)) { fail('[2]', '테이블 행 없음'); return; }

    // 파란 편집 버튼 (파란색 = text-blue-600)
    const editBtn = firstRow.locator('button.text-blue-600, button[class*="blue"]').first();
    if (await editBtn.isVisible().catch(() => false)) {
      await editBtn.click({ force: true });
    } else {
      // 첫 번째 아이콘 버튼 (편집)
      const iconBtns = await firstRow.locator('button').all();
      if (iconBtns.length > 0) await iconBtns[0].click({ force: true });
    }
    await page.waitForTimeout(1500);
    await shot(page, '05-edit-modal-nocache');

    const modalText = await page.locator('body').textContent().catch(() => '');
    if (!/편집/i.test(modalText || '')) { fail('[2]', '편집 모달 미노출'); return; }
    pass('[2] 편집 모달', '노출 확인');

    // 파일 input 확인
    const fileInputs = await page.locator('input[type="file"]').all();
    console.log(`편집 모달 파일 input: ${fileInputs.length}개`);
    if (fileInputs.length >= 1) {
      pass('[2] 편집 파일 input', `${fileInputs.length}개 확인`);
    }

    // 기존 파일 표시 확인
    const fileLinks = await page.locator('a[href*="s3"], a[href*="storage"], a[href*="amazonaws"], img[src*="s3"]').count();
    const existingIndicator = await page.locator('[class*="existing"], [class*="current"]').count();
    console.log(`기존 파일: 링크=${fileLinks}, 기존표시=${existingIndicator}`);
    if (fileLinks > 0 || existingIndicator > 0) {
      pass('[2] 기존 파일 표시', `링크 ${fileLinks}개 확인`);
    }

    // 신규 파일 추가
    if (fileInputs.length >= 1) {
      await fileInputs[0].setInputFiles(path.join(FIXTURES, 'test-image.png'));
      await page.waitForTimeout(500);
      await shot(page, '06-edit-new-file-nocache');
    }

    // 저장
    const saveBtn = page.locator('button').filter({ hasText: /저장/i }).first();
    const networkBefore = networkLog.length;
    await saveBtn.click();
    await page.waitForTimeout(3000);
    await shot(page, '07-edit-after-save-nocache');

    // API 요청 확인
    const newReqs = networkLog.slice(networkBefore);
    console.log('\n편집 저장 후 API 요청:');
    for (const r of newReqs) console.log(`  ${r.method} ${r.url} → ${r.status}`);

    const putReq = newReqs.find(r => r.method === 'PUT' && r.url.includes('sales-material'));
    const legacyImgPost = newReqs.filter(r => r.url.includes('/images'));

    if (legacyImgPost.length > 0) {
      fail('[2] 편집 저장', `레거시 /images 엔드포인트 호출됨`);
    } else if (putReq) {
      if (putReq.status === 200) {
        pass('[2] PUT 200', `PUT ${putReq.url} → ${putReq.status}`);
      } else {
        fail('[2] PUT 에러', `${putReq.status} ${putReq.url}`);
      }
    } else {
      warn('[2] PUT 요청', `PUT 미감지, 요청목록: ${newReqs.map(r=>r.method).join(',')}`);
    }

    const modalClosed = !/판매자재\s*편집/i.test(await page.locator('body').textContent().catch(() => '') || '');
    if (modalClosed) pass('[2] 편집 모달 닫힘', '저장 성공');
    else warn('[2] 편집 모달', '저장 후 미닫힘');

  } finally {
    await ctx.close();
  }
}, { timeout: 60_000 });

// ─────────────────────────────────────────────
// [3] 모바일 2종 (새 컨텍스트)
// ─────────────────────────────────────────────
test('[3] 모바일 iPhone 12 — 캐시 무효화', async ({ browser }) => {
  const ctx = await freshContext(browser);
  const page = await ctx.newPage();
  await page.setViewportSize({ width: 390, height: 844 });

  try {
    await loginFresh(page);
    await hardGoto(page, `${BASE_URL}/sales-material`);
    await shot(page, '08-mobile-iphone-nocache');

    const bodyText = await page.locator('body').textContent().catch(() => '');
    const has287 = /287/.test(bodyText || '');
    if (has287) pass('[3-1] iPhone 287건', '확인');
    else fail('[3-1] iPhone 287건', '미확인');

    const addBtn = page.locator('button').filter({ hasText: /신규\s*등록/i }).first();
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(1200);
      await shot(page, '09-mobile-register-nocache');

      const afterText = await page.locator('body').textContent().catch(() => '');
      const hasModal = /판매자재\s*등록/i.test(afterText || '');
      const hasLegacy = /먼저 저장하면/.test(afterText || '');
      const fileInputs = await page.locator('input[type="file"]').count();

      if (hasLegacy) {
        fail('[3-2] 모바일 등록 모달', '레거시 안내문 존재');
      } else if (hasModal) {
        pass('[3-2] 모바일 등록 모달', `노출 확인, 파일input=${fileInputs}개`);
      }
      await page.keyboard.press('Escape');
    } else {
      fail('[3-1] 모바일 등록 버튼', '없음');
    }
  } finally {
    await ctx.close();
  }
}, { timeout: 60_000 });

test('[4] 모바일 Galaxy S20 — 캐시 무효화', async ({ browser }) => {
  const ctx = await freshContext(browser);
  const page = await ctx.newPage();
  await page.setViewportSize({ width: 360, height: 800 });

  const errors: string[] = [];
  page.on('response', r => {
    if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`);
  });

  try {
    await loginFresh(page);
    await hardGoto(page, `${BASE_URL}/sales-material`);
    await shot(page, '10-mobile-galaxy-nocache');

    const bodyText = await page.locator('body').textContent().catch(() => '');
    const has287 = /287/.test(bodyText || '');
    if (has287) pass('[4] Galaxy S20 287건', '확인');
    else fail('[4] Galaxy S20 287건', '미확인');

    if (errors.length === 0) pass('[4] 네트워크 에러', '없음');
    else fail('[4] 네트워크 에러', errors.slice(0, 3).join(' | '));
  } finally {
    await ctx.close();
  }
}, { timeout: 60_000 });
