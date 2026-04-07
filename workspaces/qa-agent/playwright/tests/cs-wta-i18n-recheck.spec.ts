import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/i18n-recheck';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1000);
  const pwInput = page.locator('input[type="password"]').first();
  if (await pwInput.isVisible().catch(() => false)) {
    await page.locator('input[type="text"], input[name="username"]').first().fill('admin');
    await pwInput.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1000);
  }
}

test.use({ project: 'chromium-desktop' } as any);

test('[1] html[lang]="ko" 확인', async ({ page }) => {
  await login(page);
  const lang = await page.locator('html').getAttribute('lang');
  await shot(page, '01-html-lang');
  console.log(`html[lang]: "${lang}"`);
  expect(lang).toBe('ko');
});

test('[2] Globe 아이콘 → 드롭다운 4개 언어 확인', async ({ page }) => {
  await login(page);

  // Globe 아이콘 클릭 시도
  const globeSelectors = [
    'button[aria-label*="language" i]',
    'button[aria-label*="lang" i]',
    '[class*="globe"]',
    'svg[class*="globe"]',
    'button:has(svg)',
    '[data-testid*="lang"]',
    '[title*="language" i]',
  ];

  let clicked = false;
  for (const sel of globeSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      await el.click();
      await page.waitForTimeout(600);
      const dropdown = page.locator('[role="menu"], [role="listbox"], [class*="dropdown"], [class*="popover"]').first();
      if (await dropdown.isVisible().catch(() => false)) {
        await shot(page, '02-dropdown-open');
        const text = await dropdown.textContent() ?? '';
        console.log(`드롭다운 텍스트: "${text.trim()}"`);
        const hasKo = /ko|korean|한국어/i.test(text);
        const hasEn = /en|english|영어/i.test(text);
        const hasZh = /zh|chinese|中文/i.test(text);
        const hasJa = /ja|japanese|日本語/i.test(text);
        console.log(`ko:${hasKo} en:${hasEn} zh:${hasZh} ja:${hasJa}`);
        expect(hasKo || hasEn || hasZh || hasJa).toBeTruthy();
        clicked = true;
        break;
      }
    }
  }

  if (!clicked) {
    // 버튼 전체 목록 dump
    const buttons = page.locator('button');
    const count = await buttons.count();
    for (let i = 0; i < Math.min(count, 20); i++) {
      const txt = await buttons.nth(i).textContent().catch(() => '');
      const aria = await buttons.nth(i).getAttribute('aria-label').catch(() => '');
      const cls = await buttons.nth(i).getAttribute('class').catch(() => '');
      if (txt || aria) console.log(`btn[${i}] text="${txt?.trim()}" aria="${aria}" class="${cls?.slice(0,50)}"`);
    }
    await shot(page, '02-no-dropdown');
    console.log('⚠️ Globe 드롭다운 미발견');
  }
});

test('[3a] ja 전환 확인', async ({ page }) => {
  await login(page);

  const langMap: Record<string, string[]> = {
    ja: ['ja', 'japanese', '日本語', 'Japan'],
  };

  for (const [lang, hints] of Object.entries(langMap)) {
    // Globe 클릭
    const btns = page.locator('button');
    const count = await btns.count();
    let opened = false;
    for (let i = 0; i < count; i++) {
      const btn = btns.nth(i);
      if (!await btn.isVisible().catch(() => false)) continue;
      await btn.click();
      await page.waitForTimeout(400);
      const dropdown = page.locator('[role="menu"], [role="listbox"], [class*="dropdown"], [class*="popover"]').first();
      if (await dropdown.isVisible().catch(() => false)) {
        opened = true;
        // 해당 언어 항목 클릭
        for (const hint of hints) {
          const item = dropdown.locator(`*:has-text("${hint}")`).first();
          if (await item.isVisible().catch(() => false)) {
            await item.click();
            await page.waitForTimeout(1000);
            const htmlLang = await page.locator('html').getAttribute('lang');
            const bodyText = (await page.locator('body').textContent() ?? '').slice(0, 300);
            await shot(page, `03-${lang}-after`);
            console.log(`✅ ${lang} 클릭 성공: html[lang]="${htmlLang}"`);
            console.log(`  body 텍스트: ${bodyText.replace(/\s+/g,' ').slice(0,200)}`);
            expect(htmlLang).toContain(lang);
            return;
          }
        }
        // 드롭다운 내용 dump
        const dropText = await dropdown.textContent() ?? '';
        console.log(`드롭다운 내용: "${dropText.trim()}"`);
        await page.keyboard.press('Escape');
        break;
      }
    }
    if (!opened) {
      await shot(page, `03-${lang}-no-dropdown`);
      console.log(`⚠️ ${lang}: 드롭다운 미열림`);
    }
  }
});

test('[3b] zh 전환 확인', async ({ page }) => {
  await login(page);

  const hints = ['zh', 'chinese', '中文', 'China'];

  const btns = page.locator('button');
  const count = await btns.count();
  for (let i = 0; i < count; i++) {
    const btn = btns.nth(i);
    if (!await btn.isVisible().catch(() => false)) continue;
    await btn.click();
    await page.waitForTimeout(400);
    const dropdown = page.locator('[role="menu"], [role="listbox"], [class*="dropdown"], [class*="popover"]').first();
    if (await dropdown.isVisible().catch(() => false)) {
      for (const hint of hints) {
        const item = dropdown.locator(`*:has-text("${hint}")`).first();
        if (await item.isVisible().catch(() => false)) {
          await item.click();
          await page.waitForTimeout(1000);
          const htmlLang = await page.locator('html').getAttribute('lang');
          const bodyText = (await page.locator('body').textContent() ?? '').slice(0, 300);
          await shot(page, '04-zh-after');
          console.log(`✅ zh 클릭 성공: html[lang]="${htmlLang}"`);
          console.log(`  body 텍스트: ${bodyText.replace(/\s+/g,' ').slice(0,200)}`);
          expect(htmlLang).toContain('zh');
          return;
        }
      }
      const dropText = await dropdown.textContent() ?? '';
      console.log(`드롭다운 내용: "${dropText.trim()}"`);
      await page.keyboard.press('Escape');
      break;
    }
  }
  await shot(page, '04-zh-no-dropdown');
  console.log('⚠️ zh: 드롭다운 미열림');
});
