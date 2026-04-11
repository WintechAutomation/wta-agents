import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/cs-account-mgmt';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}
function pass(k: string, d = '') { console.log(`✅ ${k}${d ? ': ' + d : ''}`); }
function fail(k: string, d = '') { console.log(`❌ ${k}${d ? ': ' + d : ''}`); }
function warn(k: string, d = '') { console.log(`⚠️  ${k}${d ? ': ' + d : ''}`); }

async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(800);
  const pw = page.locator('input[type="password"]').first();
  if (await pw.isVisible().catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await pw.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

// ─────────────────────────────────────────────
// [a+b] ⚙️ 클릭 → 드롭다운 또는 /profile 이동
// ─────────────────────────────────────────────
test('[a+b] ⚙️ 아이콘 클릭 → 프로필 이동', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);

  // "내 프로필" aria-label 버튼 (title="내 프로필")
  const gearBtn = page.locator('button[title="내 프로필"], button[aria-label="내 프로필"]').first();
  const gearBtnVisible = await gearBtn.isVisible().catch(() => false);
  console.log(`⚙️ 버튼 가시성: ${gearBtnVisible}`);

  if (!gearBtnVisible) {
    fail('[a] ⚙️ 아이콘', '버튼 없음');
    return;
  }
  pass('[a] ⚙️ 아이콘', 'title="내 프로필" 버튼 확인');
  await shot(page, 'ab-01-before-click');

  await gearBtn.click();
  await page.waitForTimeout(1200);
  await shot(page, 'ab-02-after-gear-click');

  const afterUrl = page.url();
  console.log(`⚙️ 클릭 후 URL: ${afterUrl}`);

  // /profile 이동 확인
  if (afterUrl.includes('/profile')) {
    pass('[b] /profile 이동', `URL: ${afterUrl}`);
    await shot(page, 'ab-03-profile-page');
  } else {
    // 드롭다운 메뉴 확인
    const dropdown = page.locator('[role="menu"], [class*="dropdown"], [class*="popover"]').first();
    const dropdownVisible = await dropdown.isVisible().catch(() => false);
    const bodyText = await page.locator('body').textContent().catch(() => '');
    const hasProfileMenu = /프로필|profile|계정 설정|account/i.test(bodyText || '');

    if (dropdownVisible || hasProfileMenu) {
      pass('[b] 드롭다운 메뉴', '프로필 관련 메뉴 표시');
      // 드롭다운에서 프로필 링크 찾기
      const profileLink = page.locator('[role="menuitem"], [class*="menu"] a, [class*="dropdown"] a').filter({ hasText: /프로필|profile/i }).first();
      if (await profileLink.isVisible().catch(() => false)) {
        await profileLink.click();
        await page.waitForTimeout(1000);
        await shot(page, 'ab-03-profile-from-menu');
        const profileUrl = page.url();
        if (profileUrl.includes('/profile')) {
          pass('[b] 드롭다운 → /profile', `URL: ${profileUrl}`);
        } else {
          warn('[b] /profile 이동', `드롭다운에서 링크 클릭 후 URL: ${profileUrl}`);
        }
      }
    } else {
      fail('[b] /profile 이동', `클릭 후 URL: ${afterUrl} (profile 없음)`);
    }
  }
});

// ─────────────────────────────────────────────
// [b-2] /profile 직접 접근 → 프로필 수정 폼
// ─────────────────────────────────────────────
test('[b-2] /profile 직접 접근 및 수정 폼 확인', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/profile`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);
  await shot(page, 'b2-01-profile-direct');

  const currentUrl = page.url();
  console.log(`URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    fail('[b-2] /profile 접근', '로그인 리다이렉트');
    return;
  }
  if (!currentUrl.includes('/profile')) {
    fail('[b-2] /profile 접근', `URL 불일치: ${currentUrl}`);
    return;
  }
  pass('[b-2] /profile 접근', 'URL 확인');

  const pageText = await page.locator('body').textContent().catch(() => '');

  // 수정 가능 필드
  const textInputs = await page.locator('input[type="text"]:visible, input[type="email"]:visible').count();
  if (textInputs > 0) pass('[b-2] 프로필 수정 필드', `${textInputs}개 확인`);
  else warn('[b-2] 프로필 수정 필드', '없음');

  // 저장 버튼
  const saveBtn = page.locator('button').filter({ hasText: /저장|save|update|수정/i }).first();
  if (await saveBtn.isVisible().catch(() => false)) pass('[b-2] 저장 버튼', '확인');
  else warn('[b-2] 저장 버튼', '없음');
});

// ─────────────────────────────────────────────
// [d] Settings → 사이드바 계정 관리 메뉴
// ─────────────────────────────────────────────
test('[d] Settings 사이드바 → 계정 관리 메뉴 접근', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);

  // Settings 사이드바 메뉴 클릭
  const settingsLink = page.locator('nav a, aside a').filter({ hasText: /^Settings$|^설정$/i }).first();
  if (!await settingsLink.isVisible().catch(() => false)) {
    fail('[d] 설정 메뉴', '사이드바에 없음');
    return;
  }
  await settingsLink.click();
  await page.waitForTimeout(1200);
  await shot(page, 'd-01-settings-page');

  const settingsUrl = page.url();
  console.log(`설정 페이지 URL: ${settingsUrl}`);

  // /settings/users 또는 계정 관리 메뉴 확인
  const pageText = await page.locator('body').textContent().catch(() => '');
  const hasAccountMenu = /계정\s*관리|Account\s*Manage|User\s*Manage|사용자\s*관리/i.test(pageText || '');

  if (hasAccountMenu) {
    pass('[d] 계정 관리 메뉴', '설정 페이지에서 확인');
  } else {
    // /settings/users 직접 접근 확인
    await page.goto(`${BASE_URL}/settings/users`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
    await page.waitForTimeout(1000);
    await shot(page, 'd-02-settings-users');
    const usersUrl = page.url();
    if (!usersUrl.includes('/login') && (usersUrl.includes('/settings/users') || usersUrl.includes('account'))) {
      pass('[d] /settings/users 접근', `URL: ${usersUrl}`);
    } else {
      fail('[d] 계정 관리', `URL: ${usersUrl}`);
    }
  }
});

// ─────────────────────────────────────────────
// [e-2] 사용자 생성/수정 상세 확인
// ─────────────────────────────────────────────
test('[e-2] /settings/users 생성 모달 확인', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/settings/users`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, 'e2-01-users-page');

  // "+ 새 계정" 버튼 (스크린샷에서 확인됨)
  const createBtns = await page.locator('button').allTextContents();
  console.log(`버튼 목록: ${createBtns.map(t=>t.trim()).filter(t=>t).join(', ')}`);

  const newAccountBtn = page.locator('button').filter({ hasText: /새\s*계정|New\s*Account|Create|생성|추가/i }).first();
  const plusBtn = page.locator('button[class*="blue"], a[class*="blue"]').filter({ hasText: /\+|새|new|add/i }).first();

  let createBtn = null;
  if (await newAccountBtn.isVisible().catch(() => false)) {
    createBtn = newAccountBtn;
  } else if (await plusBtn.isVisible().catch(() => false)) {
    createBtn = plusBtn;
  } else {
    // 우측 상단 + 버튼 찾기
    const allBtns = await page.locator('button:visible').all();
    for (const btn of allBtns) {
      const text = await btn.textContent().catch(() => '');
      const box = await btn.boundingBox().catch(() => null);
      if (text?.includes('+') || text?.includes('새')) {
        console.log(`생성 버튼 후보: "${text?.trim()}" at [${box?.x},${box?.y}]`);
        createBtn = btn;
        break;
      }
    }
  }

  if (!createBtn) {
    fail('[e-2] 생성 버튼', '없음');
    return;
  }

  await createBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, 'e2-02-create-modal');

  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasForm = /아이디|username|이름|name|이메일|email|비밀번호|password/i.test(bodyText || '');
  if (hasForm) {
    pass('[e-2] 사용자 생성 모달', '폼 확인');
    // 필드 목록
    const inputs = await page.locator('input:visible').all();
    for (const inp of inputs) {
      const placeholder = await inp.getAttribute('placeholder').catch(() => '');
      const label = await inp.getAttribute('name').catch(() => '');
      console.log(`  input: name="${label}" placeholder="${placeholder}"`);
    }
  } else {
    fail('[e-2] 사용자 생성 모달', '폼 없음');
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // 수정 모달 확인
  const editBtn = page.locator('table tbody tr').first().locator('button[class*="blue"], button').nth(0);
  if (await editBtn.isVisible().catch(() => false)) {
    await editBtn.click({ force: true });
    await page.waitForTimeout(1200);
    await shot(page, 'e2-03-edit-modal');
    const editText = await page.locator('body').textContent().catch(() => '');
    if (/수정|편집|edit|저장|save/i.test(editText || '')) {
      pass('[e-2] 사용자 수정 모달', '확인');
    }
    await page.keyboard.press('Escape');
  }
});
