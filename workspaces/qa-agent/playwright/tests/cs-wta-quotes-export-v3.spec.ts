import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/quotes-export-v3';

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

test('견적서 내보내기 v3', async ({ page, context }) => {
  await login(page);
  await page.goto(`${BASE_URL}/quotes`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForTimeout(2000);
  await shot(page, '01-quotes-loaded');

  // 첫 번째 카드의 체브론(▼) 버튼 클릭 → 상세 펼침
  // lucide-chevron-down 아이콘이 있는 버튼
  const chevronBtns = page.locator('button:has(svg.lucide-chevron-down), button:has([class*="chevron-down"])');
  const chevronCount = await chevronBtns.count();
  console.log(`체브론 버튼 수: ${chevronCount}`);

  if (chevronCount === 0) {
    // 카드 자체 클릭 (텍스트 제목 영역)
    const cards = page.locator('[class*="border"][class*="rounded"], [class*="card"]').filter({ hasText: /xlsx|견적|quote/i });
    const cardCount = await cards.count();
    console.log(`카드 수: ${cardCount}`);
    if (cardCount > 0) {
      await cards.first().click();
      await page.waitForTimeout(1500);
    }
  } else {
    await chevronBtns.first().click();
    await page.waitForTimeout(1500);
  }

  await shot(page, '02-card-expanded');

  // 상세 펼침 후 버튼 전체 목록
  const allBtns = await page.locator('button:visible').all();
  console.log('펼침 후 버튼 목록:');
  for (const btn of allBtns) {
    const t = (await btn.textContent().catch(() => '') ?? '').trim();
    const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
    const title = await btn.getAttribute('title').catch(() => '') ?? '';
    const cls = (await btn.getAttribute('class').catch(() => '') ?? '').slice(0, 60);
    if (t || aria || title) console.log(`  text="${t}" aria="${aria}" title="${title}" cls="${cls}"`);
  }

  // 내보내기 버튼 정밀 탐색
  const exportPatterns = [
    /^견적서 내보내기$/,
    /^내보내기$/,
    /^Export$/i,
    /^Export Quote$/i,
    /^Download$/i,
    /^PDF$/i,
    /^출력$/,
    /^인쇄$/,
  ];

  let exportBtn = null;
  for (const pattern of exportPatterns) {
    const btn = page.locator('button').filter({ hasText: pattern }).first();
    if (await btn.isVisible().catch(() => false)) {
      const t = (await btn.textContent().catch(() => '') ?? '').trim();
      console.log(`✅ 내보내기 버튼 발견: "${t}"`);
      exportBtn = btn;
      break;
    }
  }

  // 패턴 미발견 시 icon 버튼 탐색 (export/download 관련 SVG)
  if (!exportBtn) {
    const iconBtns = page.locator('button:has(svg.lucide-download), button:has(svg.lucide-file-down), button:has(svg.lucide-file-text), button:has(svg.lucide-printer), button:has(svg.lucide-external-link)');
    const iconCount = await iconBtns.count();
    console.log(`아이콘 버튼 후보 수: ${iconCount}`);
    for (let i = 0; i < iconCount; i++) {
      const btn = iconBtns.nth(i);
      if (!await btn.isVisible().catch(() => false)) continue;
      const t = (await btn.textContent().catch(() => '') ?? '').trim();
      const title = await btn.getAttribute('title').catch(() => '') ?? '';
      const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
      console.log(`  아이콘버튼[${i}]: text="${t}" title="${title}" aria="${aria}"`);
      if (!exportBtn) exportBtn = btn; // 첫 번째 아이콘 버튼 사용
    }
  }

  if (!exportBtn) {
    console.log('❌ 내보내기 버튼 미발견 — 추가 확인:');
    // 링크(a 태그) 탐색
    const links = await page.locator('a:visible').all();
    for (const lnk of links) {
      const t = (await lnk.textContent().catch(() => '') ?? '').trim();
      const href = await lnk.getAttribute('href').catch(() => '') ?? '';
      if (/export|print|download|내보내기|출력/i.test(t + href)) {
        console.log(`  링크: text="${t}" href="${href}"`);
      }
    }
    await shot(page, '02-no-export-found');
    return;
  }

  // 내보내기 클릭 → 새 창 또는 페이지 변화
  console.log('\n내보내기 버튼 클릭...');
  const [newPage] = await Promise.all([
    context.waitForEvent('page', { timeout: 6000 }).catch(() => null),
    exportBtn.click(),
  ]);
  await page.waitForTimeout(2500);
  await shot(page, '03-after-export-click');

  if (newPage) {
    await newPage.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
    await newPage.waitForTimeout(2500);
    await shot(newPage, '04-export-new-window');
    console.log(`✅ 새 창 URL: ${newPage.url()}`);

    const exportText = (await newPage.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    console.log(`새 창 텍스트(앞800):\n${exportText.slice(0, 800)}`);

    const checks: Record<string, boolean> = {
      '견적서 제목': /quote|견적|quotation/i.test(exportText),
      '회사정보(WTA/윈텍)': /wta|wintech|윈텍|wintec|(주)윈텍/i.test(exportText),
      '고객사 정보': /customer|고객|client|company|교세라|한국야금|와이지원/i.test(exportText),
      '품목 테이블': /item|품목|product|quantity|수량|part|단가/i.test(exportText),
      '금액/합계': /total|합계|amount|금액|price|subtotal|₩|원/i.test(exportText),
    };

    let passCount = 0;
    for (const [key, result] of Object.entries(checks)) {
      console.log(`${result ? '✅' : '❌'} ${key}`);
      if (result) passCount++;
    }
    console.log(`\n종합: ${passCount}/${Object.keys(checks).length}개 항목 확인`);
    await newPage.close();
  } else {
    // 같은 페이지 변화 확인
    await shot(page, '04-same-page-state');
    const afterText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    const modals = await page.locator('[role="dialog"]:visible, [class*="modal"]:visible').all();
    if (modals.length > 0) {
      for (const m of modals) {
        const t = (await m.textContent().catch(() => '') ?? '').replace(/\s+/g, ' ');
        console.log(`모달 내용(앞300): "${t.slice(0, 300)}"`);
      }
    }
    const hasExport = /wta|wintech|윈텍|견적서|quotation|합계|total/i.test(afterText);
    console.log(`같은 페이지 견적서 콘텐츠: ${hasExport}`);
    console.log('⚠️ 새 창 미열림');
  }
});
