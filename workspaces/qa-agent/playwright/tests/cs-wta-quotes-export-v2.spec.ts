import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/quotes-export-v2';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: true });
}

async function login(page: Page) {
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
}

test('견적서 내보내기 v2', async ({ page, context }) => {
  await login(page);
  await page.goto(`${BASE_URL}/quotes`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForTimeout(2000);
  await shot(page, '01-quotes-loaded');

  // ── 견적 목록 구조 파악 ──
  const tableRows = page.locator('table tbody tr');
  const tableRowCount = await tableRows.count();
  console.log(`table tbody tr 수: ${tableRowCount}`);

  // 테이블 구조 외 다른 목록 형태
  const listItems = page.locator('[class*="quote-item"], [class*="quote-row"], [class*="list-item"]');
  const listCount = await listItems.count();
  console.log(`list-item 형태 수: ${listCount}`);

  // 메인 컨텐츠 영역 버튼/클릭 가능 요소
  const mainContent = page.locator('main, [class*="content"], [class*="main"]').first();
  const clickables = await mainContent.locator('[class*="cursor-pointer"], tr, li[class*="item"]').all();
  console.log(`main 내 클릭 가능 요소 수: ${clickables.length}`);

  // 페이지 전체 텍스트로 견적 데이터 확인
  const bodyText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
  const hasQuoteData = /quote|견적|quotation/i.test(bodyText);
  console.log(`견적 관련 텍스트 존재: ${hasQuoteData}`);

  // 첫 번째 클릭 가능한 행 선택
  let clicked = false;
  if (tableRowCount > 0) {
    const firstRow = tableRows.first();
    const rowText = (await firstRow.textContent() ?? '').replace(/\s+/g, ' ').slice(0, 80);
    console.log(`첫 번째 행 텍스트: "${rowText}"`);
    await firstRow.click();
    await page.waitForTimeout(1500);
    clicked = true;
  } else if (clickables.length > 0) {
    await clickables[0].click();
    await page.waitForTimeout(1500);
    clicked = true;
  } else {
    // cursor-pointer 가진 div 탐색
    const cursorEls = await page.locator('[class*="cursor-pointer"]').all();
    console.log(`cursor-pointer 요소 수: ${cursorEls.length}`);
    for (let i = 0; i < Math.min(cursorEls.length, 5); i++) {
      const el = cursorEls[i];
      if (!await el.isVisible().catch(() => false)) continue;
      const bbox = await el.boundingBox().catch(() => null);
      if (!bbox || bbox.width < 200) continue;
      const t = (await el.textContent().catch(() => '') ?? '').replace(/\s+/g,' ').slice(0, 80);
      console.log(`  cursor-pointer[${i}]: ${Math.round(bbox.width)}x${Math.round(bbox.height)} "${t}"`);
    }
    if (cursorEls.length > 0) {
      // 넓은 요소 클릭
      for (const el of cursorEls) {
        if (!await el.isVisible().catch(() => false)) continue;
        const bbox = await el.boundingBox().catch(() => null);
        if (bbox && bbox.width > 400) {
          await el.click();
          await page.waitForTimeout(1500);
          clicked = true;
          break;
        }
      }
    }
  }

  await shot(page, '02-after-click');
  if (!clicked) {
    console.log('⚠️ 클릭 가능한 견적 행 없음');
    return;
  }

  // ── 상세 펼침 후 내보내기 버튼 탐색 ──
  // 새로 나타난 버튼 확인 (견적서 내보내기, Export 등)
  const allVisibleBtns = await page.locator('button:visible').all();
  console.log(`\n클릭 후 visible 버튼 전체:`);
  for (const btn of allVisibleBtns) {
    const t = (await btn.textContent().catch(() => '') ?? '').trim();
    const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
    const title = await btn.getAttribute('title').catch(() => '') ?? '';
    if (t || aria || title) console.log(`  "${t}" aria="${aria}" title="${title}"`);
  }

  // 내보내기 버튼 — 정확한 텍스트 매칭
  const exportCandidates = [
    '견적서 내보내기', '내보내기', 'Export Quote', 'Export', 'Download',
    'Print Quote', '출력', '인쇄', 'PDF',
  ];
  let exportBtn = null;
  for (const text of exportCandidates) {
    // exact 매칭 우선, 그 다음 contains
    const exactEl = page.locator(`button:text-is("${text}")`).first();
    if (await exactEl.isVisible().catch(() => false)) {
      console.log(`✅ 내보내기 버튼 exact (${text})`);
      exportBtn = exactEl;
      break;
    }
    const containsEl = page.locator(`button`).filter({ hasText: new RegExp(`^${text}$`, 'i') }).first();
    if (await containsEl.isVisible().catch(() => false)) {
      const t = await containsEl.textContent().catch(() => '') ?? '';
      console.log(`✅ 내보내기 버튼 contains ("${text}"): "${t.trim()}"`);
      exportBtn = containsEl;
      break;
    }
  }

  if (!exportBtn) {
    console.log('⚠️ 내보내기 버튼 미발견');
    await shot(page, '02-no-export-btn');
    return;
  }

  // ── 버튼 클릭 → 새 창 또는 페이지 변화 ──
  const [newPage] = await Promise.all([
    context.waitForEvent('page', { timeout: 5000 }).catch(() => null),
    exportBtn.click(),
  ]);
  await page.waitForTimeout(2000);
  await shot(page, '03-after-export-click');

  if (newPage) {
    await newPage.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
    await newPage.waitForTimeout(2000);
    await shot(newPage, '04-export-new-window');
    console.log(`✅ 새 창 URL: ${newPage.url()}`);

    const exportText = (await newPage.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    console.log(`새 창 텍스트(앞600): ${exportText.slice(0, 600)}`);

    const checks: Record<string, boolean> = {
      '회사정보(WTA/윈텍)': /wta|wintech|윈텍|wintec/i.test(exportText),
      '고객사 정보': /customer|고객|client|company/i.test(exportText),
      '품목 테이블': /item|품목|product|quantity|수량|part/i.test(exportText),
      '금액/합계': /total|합계|amount|금액|price|단가|subtotal/i.test(exportText),
      '견적서 제목': /quote|견적|quotation/i.test(exportText),
    };
    let passCount = 0;
    for (const [key, result] of Object.entries(checks)) {
      console.log(`${result ? '✅' : '❌'} ${key}`);
      if (result) passCount++;
    }
    console.log(`\n종합: ${passCount}/${Object.keys(checks).length}개 항목 확인`);
    await newPage.close();
  } else {
    // 같은 페이지에서 인쇄 미리보기/모달 확인
    await shot(page, '04-same-page-after-export');
    const afterText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    const modals = await page.locator('[role="dialog"], [class*="modal"], [class*="print"]').all();
    console.log(`모달/다이얼로그 수: ${modals.length}`);
    for (const m of modals) {
      if (!await m.isVisible().catch(() => false)) continue;
      const t = (await m.textContent().catch(() => '') ?? '').replace(/\s+/g, ' ');
      console.log(`  모달 텍스트: "${t.slice(0, 200)}"`);
    }
    const hasExportContent = /wta|wintech|윈텍|견적서|quotation|합계|total/i.test(afterText);
    console.log(`현재 페이지 견적서 콘텐츠: ${hasExportContent}`);
  }
});
