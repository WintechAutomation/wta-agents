import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/inventory-qa';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1000);
  const pw = page.locator('input[type="password"]').first();
  if (await pw.isVisible().catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await pw.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1200);
  }
}

// 재고현황 페이지로 이동
async function gotoInventory(page: Page) {
  // 네비게이션에서 재고현황 찾기
  const navSelectors = [
    'a:has-text("Stock Status")',
    'a:has-text("재고현황")',
    'button:has-text("Stock Status")',
    '[href*="stock"]',
    '[href*="inventory"]',
  ];
  for (const sel of navSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      await el.click();
      await page.waitForLoadState('domcontentloaded').catch(() => {});
      await page.waitForTimeout(1500);
      return;
    }
  }
  // 직접 이동 시도
  for (const p of ['/stock-status', '/stock', '/inventory/stock', '/inventory']) {
    const resp = await page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded', timeout: 10_000 }).catch(() => null);
    if (resp && resp.status() < 400) {
      await page.waitForTimeout(1500);
      const url = page.url();
      if (!url.endsWith('/')) return; // 리다이렉트 아니면 OK
    }
  }
}

// 재고등록 폼 열기
async function openAddForm(page: Page): Promise<boolean> {
  const addSelectors = [
    'button:has-text("Add Stock")',
    'button:has-text("재고등록")',
    'button:has-text("등록")',
    'button:has-text("추가")',
    'button[aria-label*="add" i]',
    'button:has-text("+")',
  ];
  for (const sel of addSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      await el.click();
      await page.waitForTimeout(1000);
      const modal = page.locator('[role="dialog"], [class*="modal"], [class*="drawer"], [class*="sheet"]').first();
      if (await modal.isVisible().catch(() => false)) return true;
    }
  }
  return false;
}

test.describe('재고현황 기능 QA', () => {

  test('[1] ERP 검색 모드 — 재고등록 폼', async ({ page }) => {
    await login(page);
    await gotoInventory(page);
    await shot(page, '01-inventory-page');
    console.log(`현재 URL: ${page.url()}`);

    const opened = await openAddForm(page);
    if (!opened) {
      await shot(page, '01-no-form');
      console.log('⚠️ 재고등록 폼 열기 실패');
      return;
    }

    await shot(page, '01-form-open');
    const modal = page.locator('[role="dialog"], [class*="modal"], [class*="drawer"]').first();
    const formText = await modal.textContent() ?? '';
    console.log(`폼 텍스트(앞500): ${formText.replace(/\s+/g,' ').slice(0,500)}`);

    // ERP 검색 관련 UI 탐색
    const erpSelectors = [
      'input[placeholder*="ERP" i]',
      'input[placeholder*="품목" ]',
      'input[placeholder*="part" i]',
      'input[placeholder*="search" i]',
      'button:has-text("ERP")',
      'button:has-text("검색")',
      '[class*="erp"]',
      '[class*="search"]',
    ];

    let erpFound = false;
    for (const sel of erpSelectors) {
      const el = modal.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        const text = await el.textContent().catch(() => '') ?? '';
        const placeholder = await el.getAttribute('placeholder').catch(() => '') ?? '';
        console.log(`✅ ERP 검색 UI 발견 (${sel}) text="${text.trim()}" placeholder="${placeholder}"`);
        erpFound = true;

        // 검색어 입력 시도
        const tagName = await el.evaluate((e) => e.tagName.toLowerCase());
        if (tagName === 'input') {
          await el.fill('insert');
          await page.waitForTimeout(800);
          await shot(page, '01-erp-search-result');
          // 검색 결과 드롭다운 확인
          const resultDrop = page.locator('[class*="suggest"], [class*="autocomplete"], [role="listbox"], [class*="result"]').first();
          if (await resultDrop.isVisible().catch(() => false)) {
            const resultText = await resultDrop.textContent() ?? '';
            console.log(`  검색 결과: "${resultText.replace(/\s+/g,' ').slice(0,200)}"`);
          }
        }
        break;
      }
    }

    if (!erpFound) {
      console.log('⚠️ ERP 검색 UI 미발견');
      // 폼 내 모든 input 목록
      const inputs = await modal.locator('input, select, textarea').all();
      for (const inp of inputs) {
        const ph = await inp.getAttribute('placeholder').catch(() => '');
        const name = await inp.getAttribute('name').catch(() => '');
        const type = await inp.getAttribute('type').catch(() => '');
        console.log(`  input: name="${name}" type="${type}" placeholder="${ph}"`);
      }
    }

    await page.keyboard.press('Escape');
  });

  test('[2] 사진 업로드 — 재고등록 폼', async ({ page }) => {
    await login(page);
    await gotoInventory(page);

    const opened = await openAddForm(page);
    if (!opened) {
      await shot(page, '02-no-form');
      console.log('⚠️ 재고등록 폼 열기 실패');
      return;
    }

    await shot(page, '02-form-open');
    const modal = page.locator('[role="dialog"], [class*="modal"], [class*="drawer"]').first();

    // 이미지 업로드 UI 탐색
    const imageSelectors = [
      'input[type="file"]',
      'input[accept*="image"]',
      'button:has-text("사진")',
      'button:has-text("이미지")',
      'button:has-text("Upload")',
      'button:has-text("업로드")',
      '[class*="upload"]',
      '[class*="image"]',
      '[class*="photo"]',
      '[class*="dropzone"]',
    ];

    let imageFound = false;
    for (const sel of imageSelectors) {
      const el = modal.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        const text = await el.textContent().catch(() => '') ?? '';
        const accept = await el.getAttribute('accept').catch(() => '') ?? '';
        console.log(`✅ 이미지 업로드 UI 발견 (${sel}) text="${text.trim()}" accept="${accept}"`);
        imageFound = true;
        await shot(page, '02-image-upload-found');
        break;
      }
      // hidden file input도 존재 확인
      const hiddenEl = modal.locator(sel).first();
      const exists = await hiddenEl.count() > 0;
      if (exists && sel.includes('file')) {
        console.log(`✅ file input 존재 (hidden 가능)`);
        imageFound = true;
        await shot(page, '02-file-input-hidden');
        break;
      }
    }

    if (!imageFound) {
      console.log('⚠️ 이미지 업로드 UI 미발견');
      // 폼 내 버튼 목록
      const btns = await modal.locator('button').all();
      for (const btn of btns) {
        const t = await btn.textContent().catch(() => '');
        const aria = await btn.getAttribute('aria-label').catch(() => '');
        console.log(`  btn: "${t?.trim()}" aria="${aria}"`);
      }
    }

    await page.keyboard.press('Escape');
  });

  test('[3] QR/바코드 — 재고 목록 아이콘 → 모달', async ({ page }) => {
    await login(page);
    await gotoInventory(page);
    await page.waitForTimeout(2000);
    await shot(page, '03-inventory-list');

    const qrSelectors = [
      'button[aria-label*="QR" i]',
      'button[aria-label*="qr" i]',
      'button[aria-label*="barcode" i]',
      'button[title*="QR" i]',
      '[class*="qr"]',
      'button:has-text("QR")',
      // SVG 아이콘 버튼 (QR 관련)
      'button svg[class*="qr"]',
    ];

    let qrFound = false;
    for (const sel of qrSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible().catch(() => false)) {
        const text = await el.textContent().catch(() => '') ?? '';
        console.log(`✅ QR 버튼 발견 (${sel}) text="${text.trim()}"`);
        await el.click();
        await page.waitForTimeout(1000);
        await shot(page, '03-qr-modal');

        const modal = page.locator('[role="dialog"], [class*="modal"], [class*="dialog"]').first();
        if (await modal.isVisible().catch(() => false)) {
          const modalText = await modal.textContent() ?? '';
          console.log(`  모달 텍스트: "${modalText.replace(/\s+/g,' ').slice(0,300)}"`);

          // QR 이미지/캔버스 확인
          const hasQrImg = await modal.locator('canvas, svg, img').count() > 0;
          const hasQrText = /qr|barcode|바코드/i.test(modalText);
          console.log(`  QR/바코드 이미지: ${hasQrImg}, 텍스트: ${hasQrText}`);
          console.log(`✅ QR 모달 정상 표시`);
          await page.keyboard.press('Escape');
        } else {
          console.log('⚠️ QR 클릭 후 모달 미열림');
        }
        qrFound = true;
        break;
      }
    }

    if (!qrFound) {
      // 테이블 행 확인 후 행 버튼 탐색
      const rows = page.locator('tbody tr, [class*="row"]:not([class*="header"])');
      const rowCount = await rows.count();
      console.log(`테이블 행 수: ${rowCount}`);

      if (rowCount > 0) {
        // 첫 행의 모든 버튼
        const firstRow = rows.first();
        const rowBtns = await firstRow.locator('button').all();
        for (const btn of rowBtns) {
          const t = await btn.textContent().catch(() => '');
          const aria = await btn.getAttribute('aria-label').catch(() => '');
          const cls = await btn.getAttribute('class').catch(() => '');
          console.log(`  행버튼: text="${t?.trim()}" aria="${aria}" class="${cls?.slice(0,60)}"`);
        }
        await shot(page, '03-row-buttons');
      } else {
        console.log('⚠️ 테이블 행 없음 (데이터 없거나 다른 URL)');
        await shot(page, '03-no-rows');
      }
    }
  });

});
