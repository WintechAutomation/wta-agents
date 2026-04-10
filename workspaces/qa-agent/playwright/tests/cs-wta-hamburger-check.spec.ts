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

test('hamburger button discovery', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.goto('https://cs-wta.com/sales-material', { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(2000);
  await shot(page, 'hb-before-click');

  // 모든 보이는 버튼 목록
  const btns = await page.locator('button:visible').all();
  console.log(`\n총 보이는 버튼: ${btns.length}개`);
  for (const btn of btns) {
    const text = await btn.textContent().catch(() => '');
    const ariaLabel = await btn.getAttribute('aria-label').catch(() => '');
    const cls = await btn.getAttribute('class').catch(() => '');
    const box = await btn.boundingBox().catch(() => null);
    if (box) {
      console.log(`  버튼[${Math.round(box.x)},${Math.round(box.y)}]: text="${text?.trim().substring(0,20)}" aria="${ariaLabel}" class="${cls?.substring(0,40)}"`);
    }
  }

  // 좌상단 버튼 클릭 시도 (y<100, x<100)
  for (const btn of btns) {
    const box = await btn.boundingBox().catch(() => null);
    if (box && box.x < 60 && box.y < 60) {
      console.log(`\n좌상단 버튼 클릭: [${Math.round(box.x)},${Math.round(box.y)}]`);
      await btn.click();
      await page.waitForTimeout(1000);
      await shot(page, 'hb-after-click');

      const bodyText = await page.locator('body').textContent().catch(() => '');
      const hasParts = /부품\s*판매|Parts\s*Sales/i.test(bodyText || '');
      const hasSalesMaterial = /판매\s*자재|Sales\s*Material/i.test(bodyText || '');
      console.log(`클릭 후 — 부품판매=${hasParts}, 판매자재=${hasSalesMaterial}`);
      console.log(`메뉴 텍스트 일부: ${bodyText?.substring(0, 300)}`);
      break;
    }
  }
});
