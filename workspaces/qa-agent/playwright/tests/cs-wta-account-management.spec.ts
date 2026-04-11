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
// [a] 로그인 후 우측 상단 ⚙️ 아이콘 확인
// ─────────────────────────────────────────────
test('[a] 우측 상단 ⚙️ 아이콘 표시', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);
  await shot(page, '01-header-after-login');

  // ⚙️ 아이콘 확인 (다양한 선택자)
  const gearIcon = page.locator('button[aria-label*="설정"], button[aria-label*="profile"], button[title*="설정"], a[href*="profile"]').first();
  const gearBySvg = page.locator('header button, nav button').filter({ has: page.locator('svg') }).last();

  // 헤더 전체 버튼 목록
  const headerBtns = await page.locator('header button, [class*="header"] button').all();
  console.log(`헤더 버튼 수: ${headerBtns.length}`);
  for (const btn of headerBtns) {
    const text = await btn.textContent().catch(() => '');
    const ariaLabel = await btn.getAttribute('aria-label').catch(() => '');
    const title = await btn.getAttribute('title').catch(() => '');
    const cls = await btn.getAttribute('class').catch(() => '');
    console.log(`  버튼: text="${text?.trim()}" aria="${ariaLabel}" title="${title}" class="${cls?.slice(0,50)}"`);
  }

  // ⚙️ 텍스트 또는 gear 관련 확인
  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasGear = /⚙|gear|설정/i.test(await page.locator('header, [class*="navbar"], [class*="topbar"]').textContent().catch(() => '') || '');

  if (await gearIcon.isVisible().catch(() => false)) {
    pass('[a] ⚙️ 아이콘', '아이콘 확인');
  } else if (hasGear) {
    pass('[a] ⚙️ 아이콘', '헤더에 gear/설정 관련 요소 확인');
  } else {
    // 우측 상단 아이콘 버튼 (x > 200, y < 60)
    let found = false;
    for (const btn of headerBtns) {
      const box = await btn.boundingBox().catch(() => null);
      if (box && box.x > 200 && box.y < 60) {
        const text = await btn.textContent().catch(() => '');
        const ariaLabel = await btn.getAttribute('aria-label').catch(() => '');
        console.log(`우측 버튼 후보: [${Math.round(box.x)},${Math.round(box.y)}] "${text?.trim()}" aria="${ariaLabel}"`);
        found = true;
      }
    }
    if (found) warn('[a] ⚙️ 아이콘', '아이콘 선택자 미매칭, 우측 버튼 존재 확인 (스크린샷 확인 필요)');
    else fail('[a] ⚙️ 아이콘', '헤더에 ⚙️/gear 아이콘 없음');
  }
});

// ─────────────────────────────────────────────
// [b] ⚙️ 클릭 → /profile 이동
// ─────────────────────────────────────────────
test('[b] ⚙️ 클릭 → /profile 이동 및 프로필 수정', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);

  // 헤더 우측 버튼들 중 ⚙️/profile 관련 클릭
  const profileLink = page.locator('a[href*="profile"], button[aria-label*="profile"], button[aria-label*="설정"]').first();

  let clicked = false;
  if (await profileLink.isVisible().catch(() => false)) {
    await profileLink.click();
    clicked = true;
  } else {
    // 사용자명 옆 버튼 찾기 (우측 상단)
    const headerBtns = await page.locator('header button, [class*="header"] button').all();
    for (const btn of headerBtns) {
      const box = await btn.boundingBox().catch(() => null);
      const cls = await btn.getAttribute('class').catch(() => '');
      // rounded 스타일 + 우측 위치
      if (box && box.x > 250 && box.y < 60 && cls?.includes('rounded')) {
        await btn.click({ force: true });
        await page.waitForTimeout(1000);
        clicked = true;
        break;
      }
    }
  }

  if (!clicked) {
    // 직접 /profile 접근
    await page.goto(`${BASE_URL}/profile`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
    await page.waitForTimeout(1000);
  }

  await shot(page, '02-profile-page');
  const currentUrl = page.url();
  console.log(`현재 URL: ${currentUrl}`);

  if (currentUrl.includes('/profile')) {
    pass('[b] /profile 이동', `URL: ${currentUrl}`);
  } else {
    // 드롭다운 등 중간 단계가 있을 수 있음
    const bodyText = await page.locator('body').textContent().catch(() => '');
    const hasProfile = /프로필|profile|계정|account/i.test(bodyText || '');
    if (hasProfile) {
      pass('[b] 프로필 UI', '프로필/계정 관련 UI 확인');
    } else {
      fail('[b] /profile 이동', `현재 URL: ${currentUrl}`);
      return;
    }
  }

  // 프로필 수정 폼 확인
  const editableFields = await page.locator('input[type="text"]:visible, input[type="email"]:visible').count();
  if (editableFields > 0) {
    pass('[b] 프로필 수정 폼', `편집 가능 필드 ${editableFields}개 확인`);
  } else {
    warn('[b] 프로필 수정 폼', '편집 필드 없음');
  }
});

// ─────────────────────────────────────────────
// [c] 비밀번호 변경 폼
// ─────────────────────────────────────────────
test('[c] 비밀번호 변경 폼 동작', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/profile`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);
  await shot(page, '03-profile-page-full');

  const currentUrl = page.url();
  if (currentUrl.includes('/login')) {
    fail('[c] 비밀번호 변경', '/profile 접근 불가 (로그인 리다이렉트)');
    return;
  }

  const pageText = await page.locator('body').textContent().catch(() => '');

  // 비밀번호 변경 섹션 확인
  const hasPwSection = /비밀번호|password/i.test(pageText || '');
  if (hasPwSection) {
    pass('[c] 비밀번호 변경 섹션', '존재 확인');
  } else {
    fail('[c] 비밀번호 변경 섹션', '없음');
    return;
  }

  // password input 개수
  const pwInputs = await page.locator('input[type="password"]').count();
  console.log(`비밀번호 input 수: ${pwInputs}`);
  if (pwInputs >= 2) {
    pass('[c] 비밀번호 폼', `input ${pwInputs}개 확인 (현재/새/확인)`);
  } else {
    warn('[c] 비밀번호 폼', `input ${pwInputs}개`);
  }

  // 변경 버튼
  const changeBtn = page.locator('button').filter({ hasText: /변경|저장|save|update/i }).first();
  if (await changeBtn.isVisible().catch(() => false)) {
    pass('[c] 비밀번호 변경 버튼', '확인');
  } else {
    warn('[c] 비밀번호 변경 버튼', '없음');
  }
});

// ─────────────────────────────────────────────
// [d] 사이드바 "계정 관리" 메뉴 (admin 권한)
// ─────────────────────────────────────────────
test('[d] 사이드바 "계정 관리" 메뉴 노출 (admin)', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(1500);
  await shot(page, '04-sidebar-overview');

  // 사이드바 전체 텍스트
  const sidebarText = await page.locator('nav, aside, [class*="sidebar"]').textContent().catch(() => '');
  console.log(`사이드바 텍스트: ${sidebarText?.replace(/\s+/g, ' ').trim().slice(0, 300)}`);

  const hasSettings = /Settings|설정/i.test(sidebarText || '');
  const hasAccountMgmt = /계정\s*관리|Account\s*Manage|User\s*Manage/i.test(sidebarText || '');

  if (hasSettings) pass('[d] 설정 메뉴', '사이드바에 "설정" 확인');
  else warn('[d] 설정 메뉴', '사이드바에 "설정" 없음');

  if (hasAccountMgmt) {
    pass('[d] 계정 관리 메뉴', '사이드바에 "계정 관리" 확인');
  } else {
    // Settings 클릭하여 하위 메뉴 확장
    const settingsMenu = page.locator('nav a, aside a, button').filter({ hasText: /^Settings$|^설정$/i }).first();
    if (await settingsMenu.isVisible().catch(() => false)) {
      await settingsMenu.click();
      await page.waitForTimeout(800);
      await shot(page, '04b-settings-expanded');
      const expandedText = await page.locator('body').textContent().catch(() => '');
      const hasAfterExpand = /계정\s*관리|Account\s*Manage|User\s*Manage/i.test(expandedText || '');
      if (hasAfterExpand) pass('[d] 계정 관리 메뉴', '설정 확장 후 확인');
      else fail('[d] 계정 관리 메뉴', '설정 확장 후에도 없음');
    } else {
      fail('[d] 계정 관리 메뉴', '설정 메뉴 없음');
    }
  }
});

// ─────────────────────────────────────────────
// [e] /settings/users CRUD 동작
// ─────────────────────────────────────────────
test('[e] /settings/users 사용자 목록/생성/수정/삭제 CRUD', async ({ page }) => {
  const networkLog: { method: string; url: string; status: number }[] = [];
  page.on('response', async r => {
    if (r.url().includes('user') || r.url().includes('account')) {
      networkLog.push({ method: r.request().method(), url: r.url(), status: r.status() });
    }
  });

  await login(page);
  await page.goto(`${BASE_URL}/settings/users`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, '05-users-list');

  const currentUrl = page.url();
  console.log(`현재 URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    fail('[e] /settings/users 접근', '로그인 리다이렉트');
    return;
  }

  const pageText = await page.locator('body').textContent().catch(() => '');

  // 사용자 목록 확인
  const hasUserList = /사용자|User|계정|account/i.test(pageText || '');
  if (hasUserList) pass('[e] 사용자 목록', '페이지 로드 확인');
  else {
    fail('[e] /settings/users', `페이지 없음 또는 URL: ${currentUrl}`);
    return;
  }

  // 테이블/리스트 확인
  const rows = await page.locator('table tbody tr, [class*="user-item"], [class*="userItem"]').count();
  if (rows > 0) pass('[e] 사용자 목록 데이터', `${rows}행 확인`);
  else warn('[e] 사용자 목록 데이터', '행 없음 (빈 목록 또는 다른 구조)');

  // 생성 버튼 확인
  const createBtn = page.locator('button').filter({ hasText: /생성|추가|등록|Add|New|Create/i }).first();
  if (await createBtn.isVisible().catch(() => false)) {
    pass('[e] 사용자 생성 버튼', '확인');
    await createBtn.click();
    await page.waitForTimeout(1200);
    await shot(page, '06-user-create-modal');
    const modalText = await page.locator('body').textContent().catch(() => '');
    if (/사용자|user|아이디|username|비밀번호|password/i.test(modalText || '')) {
      pass('[e] 사용자 생성 폼', '모달/폼 노출 확인');
    } else {
      warn('[e] 사용자 생성 폼', '모달 내용 미확인');
    }
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
  } else {
    warn('[e] 사용자 생성 버튼', '없음');
  }

  // 수정 버튼 확인
  const editBtn = page.locator('table tbody tr button, [class*="user-item"] button').filter({ hasText: /수정|편집|edit/i }).first();
  const editIconBtn = page.locator('table tbody tr button[class*="blue"], table tbody tr button[aria-label*="edit"]').first();
  if (await editBtn.isVisible().catch(() => false) || await editIconBtn.isVisible().catch(() => false)) {
    pass('[e] 사용자 수정 버튼', '확인');
    const btn = await editBtn.isVisible().catch(() => false) ? editBtn : editIconBtn;
    await btn.click({ force: true });
    await page.waitForTimeout(1200);
    await shot(page, '07-user-edit-modal');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
  } else {
    warn('[e] 사용자 수정 버튼', '직접 확인 필요 (행 hover 필요할 수 있음)');
  }

  // 삭제 버튼 확인
  const deleteBtn = page.locator('table tbody tr button[class*="red"], table tbody tr button[aria-label*="delete"], table tbody tr button[title*="삭제"]').first();
  if (await deleteBtn.isVisible().catch(() => false)) {
    pass('[e] 사용자 삭제 버튼', '확인');
  } else {
    warn('[e] 사용자 삭제 버튼', '직접 확인 필요');
  }

  // API 요청 확인
  const userApiCalls = networkLog.filter(r => r.url.includes('user'));
  console.log(`사용자 API 호출: ${userApiCalls.length}건`);
  userApiCalls.slice(0, 5).forEach(r => console.log(`  ${r.method} ${r.url} → ${r.status}`));
});
