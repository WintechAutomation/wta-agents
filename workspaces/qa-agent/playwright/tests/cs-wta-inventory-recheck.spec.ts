import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/inventory-recheck';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function loginAndOpenAddForm(page: Page) {
  await page.goto('https://cs-wta.com', { waitUntil: 'domcontentloaded', timeout: 20_000 });
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
  await page.waitForTimeout(1500);
  await page.locator('button').filter({ hasText: /Add Stock/i }).first().click();
  await page.waitForTimeout(1500);
}

test('[1] ERP 검색 자동완성', async ({ page }) => {
  await loginAndOpenAddForm(page);

  const erpInput = page.locator('input[placeholder*="item code" i], input[placeholder*="ERP" i], input[placeholder*="품목" i]').first();
  const visible = await erpInput.isVisible().catch(() => false);
  console.log(`ERP input 가시성: ${visible}`);
  if (!visible) {
    await shot(page, '01-no-erp-input');
    console.log('❌ ERP input 미발견');
    return;
  }

  // 2글자 입력
  await erpInput.fill('in');
  await page.waitForTimeout(1500);
  await shot(page, '01-erp-typed-2chars');

  // 드롭다운 탐색
  const dropSelectors = [
    '[role="listbox"]', '[role="option"]',
    '[class*="suggest"]', '[class*="autocomplete"]',
    '[class*="dropdown"]', '[class*="combobox"]',
    '[class*="option"]', '[class*="result"]',
    'ul li', '[class*="list"] [class*="item"]',
  ];

  let found = false;
  for (const sel of dropSelectors) {
    const els = page.locator(sel);
    const count = await els.count();
    if (count === 0) continue;
    for (let i = 0; i < Math.min(count, 3); i++) {
      const el = els.nth(i);
      if (!await el.isVisible().catch(() => false)) continue;
      const bbox = await el.boundingBox().catch(() => null);
      if (!bbox || bbox.width < 50) continue;
      const text = await el.textContent().catch(() => '') ?? '';
      console.log(`✅ 드롭다운 (${sel})[${i}]: "${text.replace(/\s+/g,' ').slice(0,150)}"`);
      found = true;
    }
    if (found) break;
  }

  if (!found) {
    // 전체 페이지에서 새로 나타난 요소 (input 바로 아래/뒤)
    const erpBox = await erpInput.boundingBox().catch(() => null);
    console.log(`ERP input 위치: ${JSON.stringify(erpBox)}`);

    // input 부모 기준으로 탐색
    const parent = erpInput.locator('..');
    const parentHTML = await parent.evaluate((el) => el.parentElement?.innerHTML ?? '').catch(() => '');
    console.log(`부모 HTML(앞600): ${parentHTML.replace(/\s+/g,' ').slice(0,600)}`);

    await shot(page, '01-no-dropdown-detail');
    console.log('⚠️ 드롭다운 미발견');
  }
});

test('[2] 사진 업로드 파일 다이얼로그', async ({ page }) => {
  await loginAndOpenAddForm(page);
  await shot(page, '02-form-open');

  // file input 전체 탐색 (hidden 포함)
  const fileInputCount = await page.locator('input[type="file"]').count();
  console.log(`file input 총 수: ${fileInputCount}`);

  // 사진 추가 버튼/라벨 탐색
  const uploadSelectors = [
    'button:has-text("사진 추가")',
    'button:has-text("사진")',
    'label:has-text("사진 추가")',
    'label:has-text("사진")',
    'button:has-text("이미지")',
    'label:has(input[type="file"])',
    '[class*="upload"]',
    '[class*="dropzone"]',
    '[class*="photo"]',
    '[class*="image-upload"]',
    // lucide-image 아이콘을 포함하는 버튼
    'button:has(.lucide-image)',
    'button:has(svg)',
  ];

  let uploadEl: import('@playwright/test').Locator | null = null;
  for (const sel of uploadSelectors) {
    const el = page.locator(sel).first();
    if (!await el.isVisible().catch(() => false)) continue;
    const text = await el.textContent().catch(() => '') ?? '';
    const tag = await el.evaluate((e) => e.tagName.toLowerCase()).catch(() => '');
    console.log(`업로드 UI (${sel}): <${tag}> "${text.trim().slice(0,60)}"`);
    uploadEl = el;
    break;
  }

  if (!uploadEl) {
    // 버튼 전체 스캔
    const btns = await page.locator('button:visible').all();
    console.log(`현재 visible 버튼 목록:`);
    for (const btn of btns) {
      const t = await btn.textContent().catch(() => '') ?? '';
      const aria = await btn.getAttribute('aria-label').catch(() => '') ?? '';
      const cls = (await btn.getAttribute('class').catch(() => '') ?? '').slice(0, 60);
      if (t.trim() || aria) console.log(`  "${t.trim()}" [${aria}] ${cls}`);
    }
    await shot(page, '02-no-upload');
    console.log('❌ 사진 업로드 UI 미발견');
    return;
  }

  // 파일 다이얼로그 감지: filechooser 이벤트
  const [fileChooser] = await Promise.all([
    page.waitForEvent('filechooser', { timeout: 3000 }).catch(() => null),
    uploadEl.click(),
  ]);

  await shot(page, '02-after-upload-click');

  if (fileChooser) {
    console.log(`✅ 파일 선택 다이얼로그 열림 (accept: ${fileChooser.isMultiple() ? 'multiple' : 'single'})`);
    await fileChooser.setFiles([]); // 빈 선택으로 닫기
  } else {
    // file input이 숨겨져 있어서 바로 트리거 안 될 수 있음
    // 클릭 후 file input 상태 확인
    const fileInputs = await page.locator('input[type="file"]').all();
    console.log(`클릭 후 file input 수: ${fileInputs.length}`);
    for (const fi of fileInputs) {
      const accept = await fi.getAttribute('accept').catch(() => '') ?? '';
      const name = await fi.getAttribute('name').catch(() => '') ?? '';
      console.log(`  file input: name="${name}" accept="${accept}"`);
    }
    if (fileInputs.length > 0) {
      console.log(`✅ file input 존재 (다이얼로그는 보안상 자동 감지 불가)`);
    } else {
      console.log(`⚠️ 파일 다이얼로그 미감지, file input 없음`);
    }
  }
});
