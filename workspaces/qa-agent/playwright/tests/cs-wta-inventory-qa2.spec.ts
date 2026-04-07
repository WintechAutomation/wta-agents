import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/inventory-qa2';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
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

test('[1+2] ERP 검색 + 사진 업로드 — Add Stock 폼', async ({ page }) => {
  await loginAndGotoInventory(page);
  await shot(page, '01-inventory-page');

  // 페이지 내 모든 버튼 목록 확인
  const allBtns = await page.locator('button').all();
  const btnInfos: string[] = [];
  for (const btn of allBtns) {
    if (!await btn.isVisible().catch(() => false)) continue;
    const text = await btn.textContent().catch(() => '') ?? '';
    const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
    btnInfos.push(`"${text.trim()}" [${aria}]`);
  }
  console.log(`페이지 버튼 목록: ${btnInfos.join(' | ')}`);

  // Add Stock 버튼 클릭 (텍스트 매칭)
  const addBtn = page.locator('button').filter({ hasText: /Add Stock|재고등록|재고 등록/i }).first();
  const addVisible = await addBtn.isVisible().catch(() => false);
  console.log(`Add Stock 버튼 가시성: ${addVisible}`);

  if (!addVisible) {
    console.log('❌ Add Stock 버튼 미발견');
    await shot(page, '01-no-add-btn');
    return;
  }

  await addBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, '01-after-click');

  // 열린 컨테이너 탐색 (dialog, sheet, drawer, panel 등)
  const containerSelectors = [
    '[role="dialog"]',
    '[role="complementary"]',
    '[class*="sheet"]',
    '[class*="drawer"]',
    '[class*="modal"]',
    '[class*="panel"]',
    '[class*="form"]',
    '[class*="slide"]',
    'aside',
  ];

  let container: import('@playwright/test').Locator | null = null;
  for (const sel of containerSelectors) {
    const el = page.locator(sel).last(); // last 사용 (여러 개일 수 있음)
    if (await el.isVisible().catch(() => false)) {
      const bbox = await el.boundingBox().catch(() => null);
      if (bbox && bbox.width > 200) {
        console.log(`컨테이너 발견: ${sel} (${Math.round(bbox.width)}x${Math.round(bbox.height)})`);
        container = el;
        break;
      }
    }
  }

  if (!container) {
    console.log('⚠️ 폼 컨테이너 미발견 — 페이지 전체에서 폼 탐색');
    // 페이지 전체에서 input 탐색
    container = page.locator('body');
  }

  await shot(page, '01-form-state');

  // --- ERP 검색 확인 ---
  console.log('\n--- [1] ERP 검색 확인 ---');
  const allInputs = await container.locator('input, textarea, select').all();
  for (const inp of allInputs) {
    if (!await inp.isVisible().catch(() => false)) continue;
    const ph = await inp.getAttribute('placeholder').catch(() => '') ?? '';
    const name = await inp.getAttribute('name').catch(() => '') ?? '';
    const type = await inp.getAttribute('type').catch(() => '') ?? '';
    const cls = (await inp.getAttribute('class').catch(() => '') ?? '').slice(0, 60);
    console.log(`  input: name="${name}" type="${type}" ph="${ph}" cls="${cls}"`);
  }

  // ERP 검색 특이 UI (검색 버튼, 드롭다운 등)
  const erpKeywords = ['ERP', '품목코드', '품목명', 'part number', 'item'];
  for (const kw of erpKeywords) {
    const el = container.locator(`*:has-text("${kw}")`).first();
    if (await el.isVisible().catch(() => false)) {
      const tag = await el.evaluate((e) => e.tagName).catch(() => '');
      const text = await el.textContent().catch(() => '') ?? '';
      console.log(`✅ ERP 관련 텍스트 발견: "${kw}" → <${tag}> "${text.trim().slice(0,80)}"`);
    }
  }

  // 검색 가능한 input 찾아서 타이핑
  const searchInput = container.locator('input[placeholder*="검색" i], input[placeholder*="search" i], input[placeholder*="ERP" i], input[placeholder*="품목" i]').first();
  if (await searchInput.isVisible().catch(() => false)) {
    await searchInput.fill('insert');
    await page.waitForTimeout(1000);
    await shot(page, '01-erp-typed');
    const suggest = page.locator('[class*="suggest"], [class*="autocomplete"], [role="listbox"], [class*="option"], [class*="dropdown"]').first();
    if (await suggest.isVisible().catch(() => false)) {
      const t = await suggest.textContent() ?? '';
      console.log(`✅ ERP 검색 자동완성: "${t.replace(/\s+/g,' ').slice(0,200)}"`);
    } else {
      console.log('⚠️ 자동완성 드롭다운 미표시');
    }
  }

  // --- 사진 업로드 확인 ---
  console.log('\n--- [2] 사진 업로드 확인 ---');
  const fileInputs = await container.locator('input[type="file"]').all();
  console.log(`file input 수: ${fileInputs.length}`);
  for (const fi of fileInputs) {
    const accept = await fi.getAttribute('accept').catch(() => '') ?? '';
    const name = await fi.getAttribute('name').catch(() => '') ?? '';
    console.log(`✅ file input: name="${name}" accept="${accept}"`);
  }

  const uploadSelectors = [
    'button:has-text("사진")', 'button:has-text("이미지")', 'button:has-text("Upload")',
    'button:has-text("업로드")', '[class*="upload"]', '[class*="dropzone"]', '[class*="image-upload"]',
  ];
  for (const sel of uploadSelectors) {
    const el = container.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      const text = await el.textContent().catch(() => '') ?? '';
      console.log(`✅ 업로드 UI (${sel}): "${text.trim()}"`);
    }
  }

  await shot(page, '02-photo-check');
  await page.keyboard.press('Escape');
});

test('[3] QR/바코드 모달 확인', async ({ page }) => {
  await loginAndGotoInventory(page);
  await page.waitForTimeout(1500);
  await shot(page, '03-inventory-list');

  // 행 확인
  const rows = page.locator('tbody tr');
  const rowCount = await rows.count();
  console.log(`테이블 행 수: ${rowCount}`);

  // QR 버튼 발견 (title 속성 포함)
  const qrBtn = page.locator('button[title*="QR" i]').first();
  const qrVisible = await qrBtn.isVisible().catch(() => false);
  console.log(`QR 버튼(title): ${qrVisible}`);

  if (!qrVisible) {
    console.log('QR 버튼 미발견 — 행 버튼 목록 탐색');
    if (rowCount > 0) {
      const firstRow = rows.first();
      const rowBtns = await firstRow.locator('button').all();
      for (const btn of rowBtns) {
        const t = await btn.textContent().catch(() => '') ?? '';
        const title = await btn.getAttribute('title').catch(() => '') ?? '';
        const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
        const cls = (await btn.getAttribute('class').catch(() => '') ?? '').slice(0, 60);
        console.log(`  btn: text="${t.trim()}" title="${title}" aria="${aria}"`);
      }
    }
    return;
  }

  // QR 버튼 클릭
  await qrBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, '03-after-qr-click');

  // 모달 탐색 — 더 광범위하게
  const modalSelectors = [
    '[role="dialog"]',
    '[role="alertdialog"]',
    '[class*="modal"]',
    '[class*="dialog"]',
    '[class*="overlay"]',
    '[class*="popup"]',
    '[class*="qr"]',
  ];

  let found = false;
  for (const sel of modalSelectors) {
    const els = page.locator(sel);
    const count = await els.count();
    for (let i = 0; i < count; i++) {
      const el = els.nth(i);
      if (!await el.isVisible().catch(() => false)) continue;
      const bbox = await el.boundingBox().catch(() => null);
      if (!bbox || bbox.width < 100) continue;

      const text = await el.textContent().catch(() => '') ?? '';
      console.log(`모달 후보 (${sel})[${i}]: ${Math.round(bbox.width)}x${Math.round(bbox.height)} | "${text.replace(/\s+/g,' ').slice(0,200)}"`);

      // canvas/svg/img 존재 (QR 이미지)
      const canvasCount = await el.locator('canvas').count();
      const svgCount = await el.locator('svg').count();
      const imgCount = await el.locator('img').count();
      console.log(`  canvas:${canvasCount} svg:${svgCount} img:${imgCount}`);
      found = true;
    }
  }

  if (!found) {
    // 페이지 전체 canvas/svg 확인 (QR 렌더링)
    const canvases = await page.locator('canvas').all();
    const svgs = await page.locator('svg').all();
    console.log(`페이지 전체 canvas: ${canvases.length}, svg: ${svgs.length}`);
    await shot(page, '03-full-page');
  }
});
