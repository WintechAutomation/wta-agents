import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://mes-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/mes-user-mgmt';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}
function pass(k: string, d = '') { console.log(`✅ ${k}${d ? ': ' + d : ''}`); }
function fail(k: string, d = '') { console.log(`❌ ${k}${d ? ': ' + d : ''}`); }
function warn(k: string, d = '') { console.log(`⚠️  ${k}${d ? ': ' + d : ''}`); }

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(800);
  const userInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="아이디"], input[placeholder*="user" i]').first();
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill('account');
    await page.locator('input[type="password"]').first().fill('test1234');
    await page.locator('button[type="submit"], button').filter({ hasText: /로그인|Login|확인/i }).first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

test('MES 사용자관리 — 부서/직급 필드 편집 검증', async ({ page }) => {
  await login(page);

  // 1. 사용자관리 페이지 접근
  await page.goto(`${BASE_URL}/system/user-management`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(2000);

  const currentUrl = page.url();
  console.log(`사용자관리 URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    fail('사용자관리 접근', '로그인 리다이렉트');
    return;
  }

  await shot(page, '01-user-list');

  // 테이블 행 확인
  const rows = await page.locator('table tbody tr, [class*="table"] [class*="row"]').count();
  console.log(`사용자 목록 행 수: ${rows}`);

  if (rows === 0) {
    fail('사용자 목록', '행 없음');
    return;
  }
  pass('사용자 목록', `${rows}행 확인`);

  // 2. 편집 버튼 클릭
  const editBtn = page.locator('table tbody tr').first()
    .locator('button').filter({ hasText: /편집|수정|Edit|edit/i }).first();
  const editBtnAlt = page.locator('table tbody tr').first()
    .locator('button[class*="edit"], button[aria-label*="edit"], button[aria-label*="수정"]').first();

  let clicked = false;
  if (await editBtn.isVisible().catch(() => false)) {
    await editBtn.click();
    clicked = true;
  } else if (await editBtnAlt.isVisible().catch(() => false)) {
    await editBtnAlt.click();
    clicked = true;
  } else {
    // 첫 행의 버튼들 목록 확인
    const btns = await page.locator('table tbody tr').first().locator('button').allTextContents();
    console.log(`첫 행 버튼 목록: ${btns.map(t => t.trim()).filter(t => t).join(', ')}`);
    // 첫 번째 버튼 클릭 시도
    const firstBtn = page.locator('table tbody tr').first().locator('button').first();
    if (await firstBtn.isVisible().catch(() => false)) {
      await firstBtn.click();
      clicked = true;
    }
  }

  if (!clicked) {
    fail('편집 버튼', '없음');
    return;
  }

  await page.waitForTimeout(1500);
  await shot(page, '02-edit-dialog');

  // 3. 팝업에서 부서/직급 필드 확인
  const dialogText = await page.locator('[role="dialog"], [class*="modal"], [class*="Dialog"]').first().textContent().catch(() => '');
  console.log(`팝업 텍스트 (일부): ${dialogText?.slice(0, 300)}`);

  // 각 필드 확인
  const fieldChecks = [
    { label: '부서명', keys: ['부서명', 'department_name', 'departmentName'] },
    { label: '부서 코드', keys: ['부서 코드', 'department_code', 'departmentCode'] },
    { label: '직급명', keys: ['직급명', 'position_name', 'positionName'] },
    { label: '직급 코드', keys: ['직급 코드', 'position_code', 'positionCode'] },
  ];

  let foundCount = 0;
  for (const { label, keys } of fieldChecks) {
    const found = keys.some(k => dialogText?.includes(k));
    if (found) {
      pass(`필드: ${label}`, '팝업에서 확인');
      foundCount++;
    } else {
      fail(`필드: ${label}`, '팝업에서 미확인');
    }
  }

  // input 확인 (name/placeholder 기반)
  const inputs = await page.locator('[role="dialog"] input:visible, [class*="modal"] input:visible, [class*="Dialog"] input:visible').all();
  console.log(`팝업 내 input 수: ${inputs.length}`);
  const inputDetails: string[] = [];
  for (const inp of inputs) {
    const name = await inp.getAttribute('name').catch(() => '');
    const placeholder = await inp.getAttribute('placeholder').catch(() => '');
    const value = await inp.inputValue().catch(() => '');
    inputDetails.push(`name="${name}" placeholder="${placeholder}" value="${value}"`);
    console.log(`  input: name="${name}" placeholder="${placeholder}" value="${value}"`);
  }

  // 부서/직급 관련 input 찾기
  const deptNameInput = page.locator('[role="dialog"] input[name*="department_name"], [role="dialog"] input[name*="departmentName"], [class*="modal"] input[name*="department_name"]').first();
  const deptCodeInput = page.locator('[role="dialog"] input[name*="department_code"], [role="dialog"] input[name*="departmentCode"], [class*="modal"] input[name*="department_code"]').first();
  const posNameInput = page.locator('[role="dialog"] input[name*="position_name"], [role="dialog"] input[name*="positionName"], [class*="modal"] input[name*="position_name"]').first();
  const posCodeInput = page.locator('[role="dialog"] input[name*="position_code"], [role="dialog"] input[name*="positionCode"], [class*="modal"] input[name*="position_code"]').first();

  // 4. 값 입력 테스트
  const testDeptName = 'QA-부서테스트';
  const testDeptCode = 'QA-DEPT';
  const testPosName = 'QA-직급테스트';
  const testPosCode = 'QA-POS';

  let filledCount = 0;

  if (await deptNameInput.isVisible().catch(() => false)) {
    await deptNameInput.fill(testDeptName);
    filledCount++;
    pass('부서명 입력', testDeptName);
  } else {
    // placeholder 또는 label 기반으로 찾기
    const deptLabelInput = page.locator('label:has-text("부서명"), label:has-text("부서 이름")').first()
      .locator('~ input, ~ div input').first();
    if (await deptLabelInput.isVisible().catch(() => false)) {
      await deptLabelInput.fill(testDeptName);
      filledCount++;
      pass('부서명 입력 (label 기반)', testDeptName);
    } else {
      warn('부서명 input', 'name 기반 선택자 미탐지');
    }
  }

  if (await deptCodeInput.isVisible().catch(() => false)) {
    await deptCodeInput.fill(testDeptCode);
    filledCount++;
    pass('부서 코드 입력', testDeptCode);
  } else {
    warn('부서 코드 input', 'name 기반 선택자 미탐지');
  }

  if (await posNameInput.isVisible().catch(() => false)) {
    await posNameInput.fill(testPosName);
    filledCount++;
    pass('직급명 입력', testPosName);
  } else {
    warn('직급명 input', 'name 기반 선택자 미탐지');
  }

  if (await posCodeInput.isVisible().catch(() => false)) {
    await posCodeInput.fill(testPosCode);
    filledCount++;
    pass('직급 코드 입력', testPosCode);
  } else {
    warn('직급 코드 input', 'name 기반 선택자 미탐지');
  }

  console.log(`\n필드 발견: ${foundCount}/4, 입력 성공: ${filledCount}/4`);
  await shot(page, '03-edit-filled');

  // 5. 저장
  const saveBtn = page.locator('[role="dialog"] button, [class*="modal"] button, [class*="Dialog"] button')
    .filter({ hasText: /저장|Save|확인|수정/i }).first();

  if (!await saveBtn.isVisible().catch(() => false)) {
    fail('저장 버튼', '없음');
    return;
  }

  // 저장 전 첫 행 사용자명 기록
  const firstRowText = await page.locator('table tbody tr').first().textContent().catch(() => '');

  await saveBtn.click();
  await page.waitForTimeout(2000);
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1000);
  await shot(page, '04-after-save-list');

  // 저장 후 목록 확인
  const afterUrl = page.url();
  console.log(`저장 후 URL: ${afterUrl}`);

  const dialogStillOpen = await page.locator('[role="dialog"]:visible, [class*="modal"]:visible').first().isVisible().catch(() => false);
  if (!dialogStillOpen) {
    pass('저장 후 모달 닫힘', '목록으로 복귀');
  } else {
    warn('저장 후 모달', '여전히 열려 있음');
  }

  // 6. 재편집으로 프리필 확인
  await page.waitForTimeout(500);
  const editBtn2 = page.locator('table tbody tr').first()
    .locator('button').filter({ hasText: /편집|수정|Edit|edit/i }).first();
  const editBtnAlt2 = page.locator('table tbody tr').first().locator('button').first();

  let reopened = false;
  if (await editBtn2.isVisible().catch(() => false)) {
    await editBtn2.click();
    reopened = true;
  } else if (await editBtnAlt2.isVisible().catch(() => false)) {
    await editBtnAlt2.click();
    reopened = true;
  }

  if (reopened) {
    await page.waitForTimeout(1200);
    await shot(page, '05-edit-prefill');

    const prefillInputs = await page.locator('[role="dialog"] input:visible, [class*="modal"] input:visible, [class*="Dialog"] input:visible').all();
    let prefillFound = false;
    for (const inp of prefillInputs) {
      const val = await inp.inputValue().catch(() => '');
      const name = await inp.getAttribute('name').catch(() => '');
      if (val && (val.includes('QA') || val.includes('부서') || val.includes('직급'))) {
        pass('프리필 확인', `name="${name}" value="${val}"`);
        prefillFound = true;
      }
    }
    if (!prefillFound) {
      // 값이 있는 모든 input 출력
      for (const inp of prefillInputs) {
        const val = await inp.inputValue().catch(() => '');
        const name = await inp.getAttribute('name').catch(() => '');
        if (val) console.log(`  프리필 input: name="${name}" value="${val}"`);
      }
      warn('프리필', '저장된 부서/직급 값 미확인 (입력 실패했을 수 있음)');
    }
    await page.keyboard.press('Escape');
  }

  // 최종 판정
  if (foundCount >= 3) {
    pass('MES 사용자관리 부서/직급 필드', `${foundCount}/4 필드 렌더 확인`);
  } else if (foundCount > 0) {
    warn('MES 사용자관리 부서/직급 필드', `${foundCount}/4 필드만 확인`);
  } else {
    fail('MES 사용자관리 부서/직급 필드', '4개 필드 모두 미확인');
  }
}, { timeout: 90_000 });
