import { test, Page } from '@playwright/test';
import * as fs from 'fs';

const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material-recheck';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: `${SHOT_DIR}/${name}.png`, fullPage: false });
}

async function login(page: Page) {
  await page.goto('https://cs-wta.com', { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(1000);
  const pw = page.locator('input[type="password"]').first();
  if (await pw.isVisible().catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await pw.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

test('mobile hamburger menu — Parts Sales children', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.goto('https://cs-wta.com/sales-material', { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(2000);
  await shot(page, '05-mobile-before-hamburger');

  // 실제 모바일 햄버거 버튼: md:hidden 클래스 포함 버튼 (viewport 내 좌상단)
  const hamburgerBtn = page.locator('button.rounded-lg.p-2').filter({ hasText: '' }).first();

  // viewport 안에 있는 좌상단 버튼 찾기 (x>=0, y<60)
  const allBtns = await page.locator('button:visible').all();
  let hamburger = null;
  for (const btn of allBtns) {
    const box = await btn.boundingBox().catch(() => null);
    if (box && box.x >= 0 && box.x < 60 && box.y < 60) {
      const cls = await btn.getAttribute('class').catch(() => '');
      console.log(`후보 햄버거 버튼: [${Math.round(box.x)},${Math.round(box.y)}] class="${cls}"`);
      if (cls?.includes('md:hidd') || cls?.includes('p-2')) {
        hamburger = btn;
        break;
      }
      if (!hamburger) hamburger = btn; // fallback
    }
  }

  if (!hamburger) {
    console.log('❌ 햄버거 버튼 없음');
    await shot(page, '05-mobile-hamburger-notfound');
    return;
  }

  await hamburger.click({ force: true });
  await page.waitForTimeout(1200);
  await shot(page, '05-mobile-hamburger-opened');

  const bodyText = await page.locator('body').textContent().catch(() => '');

  const hasParts = /부품\s*판매|Parts\s*Sales/i.test(bodyText || '');
  const hasSalesList = /판매\s*현황|Sales\s*List/i.test(bodyText || '');
  const hasSalesMaterial = /판매\s*자재|Sales\s*Material/i.test(bodyText || '');

  console.log(`부품판매=${hasParts}, 판매현황=${hasSalesList}, 판매자재관리=${hasSalesMaterial}`);

  if (hasParts) console.log('✅ [5-1] 부품 판매 메뉴 노출');
  else console.log('❌ [5-1] 부품 판매 메뉴 미노출');

  if (hasSalesList) console.log('✅ [5-2] 판매 현황 children 노출');
  else console.log('❌ [5-2] 판매 현황 children 미노출');

  if (hasSalesMaterial) console.log('✅ [5-3] 판매자재관리 children 노출');
  else console.log('❌ [5-3] 판매자재관리 children 미노출');

  // Parts Sales 클릭하여 children 확장
  if (!hasSalesList || !hasSalesMaterial) {
    const partsBtn = page.locator('button, a').filter({ hasText: /Parts\s*Sales|부품\s*판매/i }).first();
    if (await partsBtn.isVisible().catch(() => false)) {
      await partsBtn.click();
      await page.waitForTimeout(800);
      await shot(page, '05-mobile-parts-expanded');
      const bodyText2 = await page.locator('body').textContent().catch(() => '');
      const sl2 = /판매\s*현황|Sales\s*List/i.test(bodyText2 || '');
      const sm2 = /판매\s*자재|Sales\s*Material/i.test(bodyText2 || '');
      console.log(`확장 후 — 판매현황=${sl2}, 판매자재관리=${sm2}`);
      if (sl2) console.log('✅ [5-2] 판매 현황 children 노출 (확장 후)');
      if (sm2) console.log('✅ [5-3] 판매자재관리 children 노출 (확장 후)');
    }
  }
}, { timeout: 60_000 });
