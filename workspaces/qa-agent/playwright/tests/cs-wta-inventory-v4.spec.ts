import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/inventory-v4';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function loginAndHardRefresh(page: Page) {
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

  // Ctrl+Shift+R 강제 새로고침 (캐시 무효화)
  await page.goto(`${BASE_URL}/inventory?tab=stock`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('R');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await page.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(2000);
}

test('재고현황 4차 검증 — 사진 업로드 + ERP 검색', async ({ page }) => {
  await loginAndHardRefresh(page);
  await shot(page, '00-page-loaded');
  console.log(`현재 URL: ${page.url()}`);

  // === 재고 등록 폼 열기 ===
  const addBtn = page.locator('button').filter({ hasText: /Add Stock|재고 등록|재고등록/i }).first();
  console.log(`Add Stock 버튼: ${await addBtn.isVisible().catch(() => false)}`);
  await addBtn.click();
  await page.waitForTimeout(2000);
  await shot(page, '01-form-just-opened');

  // === [2] 사진 업로드: 폼 열리자마자 확인 (모드 선택 전) ===
  console.log('\n=== [2] 사진 업로드 (모드 선택 전) ===');

  // file input (hidden 포함 전체)
  const fileInputAll = await page.locator('input[type="file"]').count();
  console.log(`file input 총 수: ${fileInputAll}`);
  if (fileInputAll > 0) {
    const inputs = await page.locator('input[type="file"]').all();
    for (const fi of inputs) {
      const accept = await fi.getAttribute('accept') ?? '';
      const name = await fi.getAttribute('name') ?? '';
      const visible = await fi.isVisible().catch(() => false);
      console.log(`  ✅ file input: name="${name}" accept="${accept}" visible=${visible}`);
    }
  }

  // "부품 사진" 텍스트 탐색
  const photoTextEl = page.locator('*').filter({ hasText: /부품 사진|사진 추가|photo|image upload/i }).first();
  if (await photoTextEl.isVisible().catch(() => false)) {
    const t = await photoTextEl.textContent() ?? '';
    console.log(`✅ 사진 관련 텍스트: "${t.replace(/\s+/g,' ').slice(0,100)}"`);
  }

  // label 중 사진 관련
  const labels = await page.locator('label:visible').all();
  for (const lbl of labels) {
    const t = await lbl.textContent().catch(() => '') ?? '';
    if (/사진|photo|image/i.test(t)) {
      console.log(`✅ 사진 label: "${t.trim()}"`);
    }
  }

  // 업로드 관련 div/button 탐색
  for (const sel of ['[class*="photo"]', '[class*="upload"]', '[class*="dropzone"]', 'button:has-text("사진")']) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      const t = await el.textContent().catch(() => '') ?? '';
      console.log(`✅ 업로드 UI (${sel}): "${t.trim().slice(0,60)}"`);
    }
  }

  // 폼 내 전체 텍스트로 최종 확인
  const pageText = (await page.locator('body').textContent() ?? '').replace(/\s+/g,' ');
  const hasPhoto = /부품 사진|사진 추가/i.test(pageText);
  console.log(`본문 "부품 사진"/"사진 추가" 포함: ${hasPhoto}`);
  if (hasPhoto) {
    const idx = pageText.search(/부품 사진|사진 추가/i);
    console.log(`  → ...${pageText.slice(Math.max(0, idx - 20), idx + 80)}...`);
  }

  // === [3] ERP 검색 모드 클릭 ===
  console.log('\n=== [3] ERP 검색 자동완성 ===');
  const erpBtn = page.locator('button').filter({ hasText: /ERP\s*(검색|Search)/i }).first();
  if (await erpBtn.isVisible().catch(() => false)) {
    await erpBtn.click();
    await page.waitForTimeout(1000);
    await shot(page, '02-erp-mode');
  }

  const erpInput = page.locator('input[placeholder*="ERP" i], input[placeholder*="item code" i]').first();
  if (!await erpInput.isVisible().catch(() => false)) {
    console.log('⚠️ ERP input 미발견');
    return;
  }

  // 2글자 입력
  await erpInput.click();
  await erpInput.fill('in');
  await page.waitForTimeout(2500); // 2.5초 대기
  await shot(page, '03-erp-typed-wait');

  // 드롭다운 탐색
  const dropSelectors = [
    '[role="listbox"]', '[role="option"]',
    '[class*="suggest"]', '[class*="autocomplete"]', '[class*="dropdown"]',
    '[class*="option"]', '[class*="result"]', '[class*="list"]',
    'ul li:visible',
  ];
  let dropFound = false;
  for (const sel of dropSelectors) {
    const els = page.locator(sel);
    const cnt = await els.count();
    for (let i = 0; i < Math.min(cnt, 3); i++) {
      const el = els.nth(i);
      if (!await el.isVisible().catch(() => false)) continue;
      const bbox = await el.boundingBox().catch(() => null);
      if (!bbox || bbox.width < 100) continue;
      const text = await el.textContent().catch(() => '') ?? '';
      if (text.trim().length < 3) continue;
      console.log(`✅ 드롭다운(${sel})[${i}]: "${text.replace(/\s+/g,' ').slice(0,200)}"`);
      dropFound = true;
    }
    if (dropFound) break;
  }

  // 빨간색 에러 메시지 탐색
  const errorSelectors = [
    '[class*="error"]', '[class*="red"]', '[class*="danger"]',
    '[class*="alert"]', 'p[class*="text-red"]', 'span[class*="text-red"]',
    '.text-red-500', '.text-red-600', '[role="alert"]',
  ];
  for (const sel of errorSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      const t = await el.textContent().catch(() => '') ?? '';
      if (t.trim()) console.log(`⚠️ 에러 메시지(${sel}): "${t.trim().slice(0,100)}"`);
    }
  }

  if (!dropFound) {
    // Search 버튼 클릭 시도 (버튼 방식일 수 있음)
    const searchBtn = page.locator('button').filter({ hasText: /^Search$/i }).first();
    if (await searchBtn.isVisible().catch(() => false)) {
      console.log('Search 버튼 발견, 클릭 시도...');
      await searchBtn.click();
      await page.waitForTimeout(1500);
      await shot(page, '04-after-search-btn');

      for (const sel of dropSelectors) {
        const el = page.locator(sel).first();
        if (await el.isVisible().catch(() => false)) {
          const bbox = await el.boundingBox().catch(() => null);
          if (!bbox || bbox.width < 100) continue;
          const text = await el.textContent().catch(() => '') ?? '';
          if (text.trim().length < 3) continue;
          console.log(`✅ Search 버튼 후 결과(${sel}): "${text.replace(/\s+/g,' ').slice(0,200)}"`);
          dropFound = true;
          break;
        }
      }
      // 에러 메시지 재확인
      for (const sel of errorSelectors) {
        const el = page.locator(sel).first();
        if (await el.isVisible().catch(() => false)) {
          const t = await el.textContent().catch(() => '') ?? '';
          if (t.trim()) console.log(`에러 메시지(${sel}): "${t.trim().slice(0, 100)}"`);
        }
      }
    }
    if (!dropFound) console.log('⚠️ ERP 검색 결과 미표시');
  }
});
