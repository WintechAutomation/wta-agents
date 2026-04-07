import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/inventory-final';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function loginAndOpenAddForm(page: Page) {
  // 캐시 우회 hard reload
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
  // 캐시 새로고침 (Ctrl+Shift+R 효과)
  await page.goto(`${BASE_URL}/inventory?tab=stock`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  await shot(page, '00-inventory-loaded');

  // 재고 등록 버튼 클릭
  const addBtn = page.locator('button').filter({ hasText: /Add Stock|재고 등록|재고등록/i }).first();
  console.log(`재고 등록 버튼 가시성: ${await addBtn.isVisible().catch(() => false)}`);
  await addBtn.click();
  await page.waitForTimeout(2000);
  await shot(page, '01-form-opened');

  // 폼 상단 모드 버튼 확인
  const modeBtns = await page.locator('button:visible').all();
  console.log('현재 보이는 버튼 목록:');
  for (const btn of modeBtns) {
    const t = await btn.textContent().catch(() => '') ?? '';
    if (t.trim()) console.log(`  버튼: "${t.trim()}"`);
  }
}

test('[1] ERP 검색 모드 자동완성', async ({ page }) => {
  await loginAndOpenAddForm(page);

  // "ERP 검색" 모드 버튼 클릭
  const erpModeBtn = page.locator('button').filter({ hasText: /ERP\s*검색|ERP Search/i }).first();
  const erpModeBtnVisible = await erpModeBtn.isVisible().catch(() => false);
  console.log(`"ERP 검색" 모드 버튼 가시성: ${erpModeBtnVisible}`);

  if (erpModeBtnVisible) {
    await erpModeBtn.click();
    await page.waitForTimeout(1000);
    await shot(page, '02-erp-mode-selected');
  } else {
    // 텍스트로 찾기
    const allBtns = await page.locator('button:visible').all();
    console.log('모드 버튼 재탐색:');
    for (const btn of allBtns) {
      const t = await btn.textContent().catch(() => '') ?? '';
      if (/erp|마스터|직접|master|select|manual/i.test(t)) {
        console.log(`  후보: "${t.trim()}"`);
      }
    }
  }

  // 초록색 or ERP 검색 input 찾기
  const erpInputSelectors = [
    'input[placeholder*="ERP" i]',
    'input[placeholder*="item code" i]',
    'input[placeholder*="검색" i]',
    'input[placeholder*="search" i]',
    'input[class*="green"]',
    'input[class*="emerald"]',
    'input[class*="erp"]',
  ];

  let erpInput = null;
  for (const sel of erpInputSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      const ph = await el.getAttribute('placeholder') ?? '';
      const cls = (await el.getAttribute('class') ?? '').slice(0, 80);
      console.log(`✅ ERP input (${sel}): ph="${ph}" cls="${cls}"`);
      erpInput = el;
      break;
    }
  }

  if (!erpInput) {
    // 모든 visible input 재목록
    const allInputs = await page.locator('input:visible').all();
    console.log(`visible input 목록 (${allInputs.length}개):`);
    for (const inp of allInputs) {
      const ph = await inp.getAttribute('placeholder') ?? '';
      const cls = (await inp.getAttribute('class') ?? '').slice(0,60);
      console.log(`  ph="${ph}" cls="${cls}"`);
    }
    await shot(page, '02-no-erp-input');
    return;
  }

  // 2글자 입력 후 드롭다운 대기
  await erpInput.click();
  await erpInput.fill('in');
  console.log('2글자 "in" 입력 완료, 드롭다운 대기...');
  await page.waitForTimeout(2000);
  await shot(page, '03-erp-typed');

  // 드롭다운 탐색 (광범위)
  const dropSelectors = [
    '[role="listbox"]', '[role="option"]',
    '[class*="suggest"]', '[class*="autocomplete"]',
    '[class*="dropdown"]', '[class*="combobox"]',
    '[class*="option"]', '[class*="result"]',
    '[class*="list"]',
    'ul:not([class*="nav"]):not([class*="menu"])',
  ];

  let dropFound = false;
  for (const sel of dropSelectors) {
    const els = page.locator(sel);
    const cnt = await els.count();
    for (let i = 0; i < Math.min(cnt, 5); i++) {
      const el = els.nth(i);
      if (!await el.isVisible().catch(() => false)) continue;
      const bbox = await el.boundingBox().catch(() => null);
      if (!bbox || bbox.width < 100 || bbox.height < 20) continue;
      const text = await el.textContent().catch(() => '') ?? '';
      if (text.trim().length < 3) continue;
      console.log(`✅ 드롭다운(${sel})[${i}]: bbox=${Math.round(bbox.width)}x${Math.round(bbox.height)} "${text.replace(/\s+/g,' ').slice(0,200)}"`);
      dropFound = true;
    }
    if (dropFound) break;
  }

  if (!dropFound) {
    // input 주변 DOM 탐색 (부모 3단계)
    const nearbyHTML = await erpInput.evaluate((el) => {
      let node: Element | null = el.parentElement;
      for (let i = 0; i < 3 && node; i++) node = node.parentElement;
      return node?.innerHTML ?? '';
    }).catch(() => '');
    console.log(`input 주변 DOM(앞800): ${nearbyHTML.replace(/\s+/g,' ').slice(0, 800)}`);
    console.log('⚠️ 드롭다운 미발견');
  }
});

test('[2] 직접 입력 모드 — 사진 업로드', async ({ page }) => {
  await loginAndOpenAddForm(page);

  // "직접 입력" 모드 버튼 클릭
  const directModeBtn = page.locator('button').filter({ hasText: /직접\s*입력|Manual|Direct/i }).first();
  const directVisible = await directModeBtn.isVisible().catch(() => false);
  console.log(`"직접 입력" 버튼 가시성: ${directVisible}`);

  if (directVisible) {
    await directModeBtn.click();
    await page.waitForTimeout(1500);
    await shot(page, '04-direct-mode');
  }

  // 사진 추가 UI 탐색
  const photoSelectors = [
    'button:has-text("사진 추가")',
    'button:has-text("사진")',
    'label:has-text("사진 추가")',
    'label:has-text("사진")',
    'label:has-text("부품 사진")',
    '*:has-text("부품 사진")',
    '[class*="photo"]',
    '[class*="image"]',
    'label:has(input[type="file"])',
    'input[type="file"]',
  ];

  let photoFound = false;
  for (const sel of photoSelectors) {
    const el = page.locator(sel).first();
    if (!await el.isVisible().catch(() => false)) continue;
    const text = await el.textContent().catch(() => '') ?? '';
    const tag = await el.evaluate((e) => e.tagName.toLowerCase()).catch(() => '');
    const cls = (await el.getAttribute('class') ?? '').slice(0, 80);
    console.log(`✅ 사진 UI (${sel}): <${tag}> "${text.trim().slice(0,80)}" cls="${cls}"`);
    photoFound = true;

    // filechooser 이벤트 감지
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 3000 }).catch(() => null),
      el.click().catch(() => {}),
    ]);
    await shot(page, '05-photo-click');

    if (chooser) {
      console.log(`✅ 파일 다이얼로그 열림! multiple=${chooser.isMultiple()}`);
      await chooser.setFiles([]);
    } else {
      const fileInputs = await page.locator('input[type="file"]').count();
      console.log(`  파일 다이얼로그 미감지, file input 수: ${fileInputs}`);
    }
    break;
  }

  if (!photoFound) {
    // 폼 전체 텍스트 확인
    const formText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ');
    const hasPhotoText = /사진|photo|image|upload/i.test(formText);
    console.log(`폼 내 사진 관련 텍스트: ${hasPhotoText}`);
    if (hasPhotoText) {
      const idx = formText.search(/사진|photo|image/i);
      console.log(`  위치: ...${formText.slice(Math.max(0,idx-30), idx+80)}...`);
    }
    await shot(page, '05-no-photo-ui');
    console.log('⚠️ 사진 업로드 UI 미발견');
  }
});
