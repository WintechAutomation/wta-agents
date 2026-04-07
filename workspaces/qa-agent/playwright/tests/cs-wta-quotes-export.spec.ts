import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/quotes-export';

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

test('견적서 내보내기 기능 검증', async ({ page, context }) => {
  await login(page);

  // 강제 새로고침
  await page.goto(`${BASE_URL}/quotes`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.evaluate(() => location.reload());
  await page.waitForLoadState('domcontentloaded').catch(() => {});
  await page.waitForTimeout(2000);
  await shot(page, '01-quotes-page');
  console.log(`URL: ${page.url()}`);

  // 견적 목록 확인
  const rows = page.locator('tbody tr, [class*="row"]:not([class*="header"])');
  const rowCount = await rows.count();
  console.log(`견적 행 수: ${rowCount}`);

  if (rowCount === 0) {
    // 빈 상태면 페이지 텍스트 확인
    const bodyText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ').slice(0, 300);
    console.log(`페이지 텍스트: ${bodyText}`);
    await shot(page, '01-no-rows');
    console.log('⚠️ 견적 행 없음');
    return;
  }

  // 첫 번째 견적 클릭 (상세 펼침)
  const firstRow = rows.first();
  const rowText = (await firstRow.textContent() ?? '').replace(/\s+/g, ' ').slice(0, 100);
  console.log(`첫 번째 견적: "${rowText}"`);
  await firstRow.click();
  await page.waitForTimeout(1500);
  await shot(page, '02-quote-expanded');

  // 견적서 내보내기 버튼 탐색
  const exportSelectors = [
    'button:has-text("견적서 내보내기")',
    'button:has-text("내보내기")',
    'button:has-text("Export")',
    'button:has-text("Print")',
    'button:has-text("PDF")',
    'a:has-text("내보내기")',
    'a:has-text("Export")',
    '[aria-label*="export" i]',
    '[aria-label*="print" i]',
    'button[title*="export" i]',
    'button[title*="내보내기"]',
  ];

  let exportBtn = null;
  for (const sel of exportSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      const text = await el.textContent().catch(() => '') ?? '';
      console.log(`✅ 내보내기 버튼 발견 (${sel}): "${text.trim()}"`);
      exportBtn = el;
      break;
    }
  }

  if (!exportBtn) {
    // 상세 영역에서 버튼 전체 목록
    console.log('내보내기 버튼 미발견 — 상세 영역 버튼 목록:');
    const allBtns = await page.locator('button:visible').all();
    for (const btn of allBtns) {
      const t = await btn.textContent().catch(() => '') ?? '';
      const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
      if (t.trim() || aria) console.log(`  "${t.trim()}" [${aria}]`);
    }
    await shot(page, '02-no-export-btn');
    return;
  }

  // 새 창 열림 감지
  const [newPage] = await Promise.all([
    context.waitForEvent('page', { timeout: 5000 }).catch(() => null),
    exportBtn.click(),
  ]);

  if (newPage) {
    // 새 창에서 검증
    await newPage.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
    await newPage.waitForTimeout(2000);
    await shot(newPage, '03-export-new-page');
    console.log(`✅ 새 창 열림: ${newPage.url()}`);

    const exportText = (await newPage.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    console.log(`새 창 텍스트(앞500): ${exportText.slice(0, 500)}`);

    // 필수 요소 확인
    const checks = {
      '회사정보(WTA/윈텍)': /wta|wintech|윈텍|wintec/i.test(exportText),
      '고객사 정보': /customer|고객|client/i.test(exportText),
      '품목 테이블': /item|품목|product|quantity|수량/i.test(exportText),
      '금액/합계': /total|합계|amount|금액|price|단가/i.test(exportText),
      '견적서 제목': /quote|견적|quotation/i.test(exportText),
    };
    for (const [key, result] of Object.entries(checks)) {
      console.log(`${result ? '✅' : '❌'} ${key}: ${result}`);
    }

    await newPage.close();
  } else {
    // 새 창 없음 — 같은 페이지 변화 확인
    await page.waitForTimeout(2000);
    await shot(page, '03-export-same-page');
    console.log('새 창 미열림 — 같은 페이지 변화 확인');

    const afterText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    const hasExportContent = /wta|wintech|윈텍|quote|견적서|합계|total/i.test(afterText);
    console.log(`현재 페이지 견적서 콘텐츠: ${hasExportContent}`);

    // iframe 확인 (프린트 미리보기)
    const frames = page.frames();
    console.log(`iframe 수: ${frames.length}`);
    for (const frame of frames) {
      const frameText = (await frame.locator('body').textContent().catch(() => '')) ?? '';
      if (frameText.trim().length > 100) {
        console.log(`  frame(${frame.url()}): "${frameText.replace(/\s+/g,' ').slice(0,200)}"`);
      }
    }
  }
});
