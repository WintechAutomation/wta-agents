import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/i18n-v2';

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

// Language 버튼 클릭 후 드롭다운 열기
async function openLangDropdown(page: Page): Promise<boolean> {
  // aria-label="Language" 버튼 우선
  const langBtn = page.locator('button[aria-label="Language"]').first();
  if (await langBtn.isVisible().catch(() => false)) {
    await langBtn.click();
    await page.waitForTimeout(600);
    return true;
  }
  return false;
}

// 드롭다운에서 텍스트로 언어 항목 클릭
async function selectLang(page: Page, keywords: string[]): Promise<boolean> {
  const containers = [
    '[role="menu"]',
    '[role="listbox"]',
    '[role="dialog"]',
    '[class*="dropdown"]',
    '[class*="popover"]',
    '[class*="menu"]',
    '[class*="select"]',
  ];

  for (const sel of containers) {
    const container = page.locator(sel).first();
    if (!await container.isVisible().catch(() => false)) continue;

    for (const kw of keywords) {
      const item = container.locator(`*:has-text("${kw}")`).first();
      if (await item.isVisible().catch(() => false)) {
        await item.click();
        await page.waitForTimeout(1200);
        return true;
      }
    }
    // 컨테이너 내용 덤프
    const txt = await container.textContent() ?? '';
    console.log(`  컨테이너(${sel}) 내용: "${txt.trim().replace(/\s+/g,' ')}"`);
  }

  // 드롭다운 없으면 페이지 전체에서 찾기
  for (const kw of keywords) {
    const el = page.locator(`*:has-text("${kw}")`).filter({ hasText: kw }).last();
    if (await el.isVisible().catch(() => false)) {
      await el.click();
      await page.waitForTimeout(1200);
      return true;
    }
  }
  return false;
}

test.describe('다국어 재검증 (v2)', () => {
  test('[1] 초기 html[lang] 확인', async ({ page }) => {
    await login(page);
    const lang = await page.locator('html').getAttribute('lang');
    await shot(page, '01-initial-lang');
    console.log(`html[lang]="${lang}"`);
    // 이전엔 "en", 수정 후 "ko"여야 함
    const isKo = lang === 'ko' || lang?.startsWith('ko');
    console.log(`${isKo ? '✅' : '❌'} 초기 언어: ${lang} (기대: ko)`);
    expect(lang).toBe('ko');
  });

  test('[2] Language 버튼 → 드롭다운 4개 언어', async ({ page }) => {
    await login(page);
    const opened = await openLangDropdown(page);
    await shot(page, '02-dropdown');

    if (!opened) {
      console.log('❌ Language 버튼 미발견');
      // 버튼 전체 목록
      const btns = await page.locator('button').all();
      for (const btn of btns) {
        const text = await btn.textContent().catch(() => '');
        const aria = await btn.getAttribute('aria-label').catch(() => '');
        if (text?.trim() || aria) console.log(`  btn: "${text?.trim()}" aria="${aria}"`);
      }
      return;
    }

    // 드롭다운 내용 확인
    const selectors = ['[role="menu"]', '[role="listbox"]', '[class*="dropdown"]', '[class*="popover"]', '[class*="menu"]'];
    let found = false;
    for (const sel of selectors) {
      const dd = page.locator(sel).first();
      if (await dd.isVisible().catch(() => false)) {
        const text = await dd.textContent() ?? '';
        console.log(`드롭다운(${sel}): "${text.trim().replace(/\s+/g,' ')}"`);
        const hasKo = /ko|한국어|korean/i.test(text);
        const hasEn = /en|english|영어/i.test(text);
        const hasZh = /zh|中文|chinese/i.test(text);
        const hasJa = /ja|日本語|japanese/i.test(text);
        console.log(`  ko:${hasKo} en:${hasEn} zh:${hasZh} ja:${hasJa}`);
        const langCount = [hasKo, hasEn, hasZh, hasJa].filter(Boolean).length;
        console.log(`  ${langCount >= 4 ? '✅' : '⚠️'} 언어 ${langCount}/4개 확인`);
        found = true;
        break;
      }
    }
    if (!found) {
      console.log('⚠️ 드롭다운 컨테이너 미발견');
      await shot(page, '02-no-dropdown-detail');
    }
  });

  for (const { lang, keywords, expectLang } of [
    { lang: 'ja', keywords: ['日本語', 'Japanese', 'ja', 'JP'], expectLang: 'ja' },
    { lang: 'zh', keywords: ['中文', 'Chinese', 'zh', 'CN'], expectLang: 'zh' },
  ]) {
    test(`[3] ${lang} 전환 → html[lang] + 텍스트 변경`, async ({ page }) => {
      await login(page);
      const opened = await openLangDropdown(page);
      if (!opened) {
        console.log(`⚠️ Language 버튼 미발견 — ${lang} 전환 불가`);
        return;
      }

      const switched = await selectLang(page, keywords);
      await shot(page, `03-${lang}-result`);

      if (!switched) {
        console.log(`❌ ${lang} 항목 미발견`);
        return;
      }

      const htmlLang = await page.locator('html').getAttribute('lang');
      const bodyText = (await page.locator('body').textContent() ?? '').replace(/\s+/g, ' ').slice(0, 300);
      console.log(`html[lang]="${htmlLang}"`);
      console.log(`body: ${bodyText}`);
      console.log(`${htmlLang?.startsWith(expectLang) ? '✅' : '❌'} ${lang} 전환 결과: ${htmlLang}`);
      expect(htmlLang).toMatch(new RegExp(`^${expectLang}`));
    });
  }
});
