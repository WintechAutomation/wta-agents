import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/inventory-qa3';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: true });
}

async function loginAndGotoInventory(page: Page) {
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
  await page.goto(`${BASE_URL}/inventory?tab=stock`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForTimeout(2000);
}

test('[1] Add Stock 폼 상세 분석', async ({ page }) => {
  await loginAndGotoInventory(page);
  await shot(page, '00-before-click');

  // input 목록 (클릭 전)
  const beforeInputs = await page.locator('input:visible').count();
  console.log(`클릭 전 visible input 수: ${beforeInputs}`);

  await page.locator('button').filter({ hasText: /Add Stock/i }).first().click();
  await page.waitForTimeout(2000);
  await shot(page, '01-after-add-stock');

  // input 목록 (클릭 후)
  const afterInputs = await page.locator('input:visible').all();
  console.log(`클릭 후 visible input 수: ${afterInputs.length}`);
  for (const inp of afterInputs) {
    const ph = await inp.getAttribute('placeholder').catch(() => '') ?? '';
    const name = await inp.getAttribute('name').catch(() => '') ?? '';
    const type = await inp.getAttribute('type').catch(() => '') ?? '';
    const val = await inp.inputValue().catch(() => '') ?? '';
    console.log(`  input: name="${name}" type="${type}" ph="${ph}" val="${val}"`);
  }

  // 페이지 내 label 목록
  const labels = await page.locator('label:visible').all();
  console.log(`\nlabel 목록:`);
  for (const lbl of labels) {
    const t = await lbl.textContent().catch(() => '') ?? '';
    if (t.trim()) console.log(`  label: "${t.trim()}"`);
  }

  // ERP 검색 input 찾기
  const erpInput = page.locator('input[placeholder*="item code" i], input[placeholder*="ERP" i], input[placeholder*="품목" i]').first();
  if (await erpInput.isVisible().catch(() => false)) {
    const ph = await erpInput.getAttribute('placeholder') ?? '';
    console.log(`\n✅ [1] ERP 검색 input 발견: ph="${ph}"`);
    await erpInput.fill('insert');
    await page.waitForTimeout(1500);
    await shot(page, '01-erp-search-typed');
    // 드롭다운/결과 탐색
    const resultCandidates = [
      '[class*="suggest"]', '[class*="autocomplete"]', '[role="listbox"]',
      '[class*="option"]', '[class*="dropdown"]', '[class*="result"]',
      'ul[class*="list"]', '[class*="combobox"]',
    ];
    for (const sel of resultCandidates) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        const t = await el.textContent().catch(() => '') ?? '';
        console.log(`  ERP 결과 (${sel}): "${t.replace(/\s+/g,' ').slice(0,200)}"`);
        break;
      }
    }
    // 그래도 안 나오면 새로 나타난 요소 확인
    const newVisible = await page.locator('[class*="search"], [class*="item-list"], [class*="erp"]').all();
    for (const el of newVisible) {
      if (await el.isVisible().catch(() => false)) {
        const t = await el.textContent().catch(() => '') ?? '';
        if (t.trim().length > 5) console.log(`  신규요소: "${t.replace(/\s+/g,' ').slice(0,150)}"`);
      }
    }
    await erpInput.clear();
  } else {
    console.log('⚠️ ERP 검색 input 미발견');
  }

  // 사진 업로드 확인 — hidden file input 포함
  console.log('\n--- [2] 사진 업로드 ---');
  const allFileInputs = await page.locator('input[type="file"]').all();
  console.log(`file input 총 수 (hidden 포함): ${allFileInputs.length}`);
  for (const fi of allFileInputs) {
    const accept = await fi.getAttribute('accept').catch(() => '') ?? '';
    const name = await fi.getAttribute('name').catch(() => '') ?? '';
    console.log(`  file input: name="${name}" accept="${accept}"`);
  }

  // 이미지/업로드 관련 버튼/div
  const uploadEls = await page.locator('[class*="upload"], [class*="photo"], [class*="image"], [class*="dropzone"], button:has-text("사진"), button:has-text("이미지"), label:has(input[type="file"])').all();
  for (const el of uploadEls) {
    if (!await el.isVisible().catch(() => false)) continue;
    const t = await el.textContent().catch(() => '') ?? '';
    const cls = (await el.getAttribute('class').catch(() => '') ?? '').slice(0, 80);
    console.log(`  업로드 UI: text="${t.trim().slice(0,60)}" cls="${cls}"`);
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
});

test('[3] QR 모달 canvas/img 분석', async ({ page }) => {
  await loginAndGotoInventory(page);
  await page.waitForTimeout(1500);

  // canvas 클릭 전 수
  const canvasBefore = await page.locator('canvas').count();
  console.log(`QR 클릭 전 canvas 수: ${canvasBefore}`);

  const qrBtn = page.locator('button[title*="QR" i]').first();
  await qrBtn.click();
  await page.waitForTimeout(2000);
  await shot(page, '03-after-qr-click');

  const canvasAfter = await page.locator('canvas').count();
  const svgAfter = await page.locator('svg').count();
  console.log(`QR 클릭 후 canvas: ${canvasAfter}, svg: ${svgAfter}`);

  // 새로 나타난 요소 탐색
  const overlays = await page.locator('[style*="position: fixed"], [style*="position:fixed"], [class*="overlay"], [class*="backdrop"]').all();
  for (const ov of overlays) {
    if (!await ov.isVisible().catch(() => false)) continue;
    const bbox = await ov.boundingBox().catch(() => null);
    const t = await ov.textContent().catch(() => '') ?? '';
    console.log(`overlay: ${JSON.stringify(bbox)} text="${t.replace(/\s+/g,' ').slice(0,150)}"`);
  }

  // z-index 높은 요소 (모달 가능성)
  const allDivs = await page.locator('div').all();
  for (const div of allDivs) {
    if (!await div.isVisible().catch(() => false)) continue;
    const zIndex = await div.evaluate((el) => window.getComputedStyle(el).zIndex).catch(() => 'auto');
    if (parseInt(zIndex) > 100) {
      const bbox = await div.boundingBox().catch(() => null);
      if (!bbox || bbox.width < 100) continue;
      const t = await div.textContent().catch(() => '') ?? '';
      const cls = (await div.getAttribute('class').catch(() => '') ?? '').slice(0, 80);
      console.log(`high-z(${zIndex}): ${Math.round(bbox.width)}x${Math.round(bbox.height)} cls="${cls}" text="${t.replace(/\s+/g,' ').slice(0,150)}"`);
    }
  }

  // canvas 위치 및 크기
  const canvases = await page.locator('canvas').all();
  for (let i = 0; i < canvases.length; i++) {
    const bbox = await canvases[i].boundingBox().catch(() => null);
    const visible = await canvases[i].isVisible().catch(() => false);
    console.log(`canvas[${i}]: visible=${visible} bbox=${JSON.stringify(bbox)}`);
  }
});
