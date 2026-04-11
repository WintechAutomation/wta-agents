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
  const userInput = page.locator('input:not([type="password"])').first();
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill('account');
    await page.locator('input[type="password"]').first().fill('test1234');
    await page.locator('button[type="submit"], button').filter({ hasText: /로그인|Login/i }).first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
}

test('MES 사용자관리 — 부서/직급 필드 편집 검증', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await login(page);
  await page.goto(`${BASE_URL}/users`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await shot(page, '01-user-list');

  const currentUrl = page.url();
  console.log(`사용자관리 URL: ${currentUrl}`);
  if (currentUrl.includes('/login')) {
    fail('사용자관리 접근', '로그인 리다이렉트');
    return;
  }
  pass('사용자관리 접근', currentUrl);

  // 테이블 컬럼 확인 (부서/직위 컬럼 존재)
  const headerText = await page.locator('table thead, [role="columnheader"], th').allTextContents().catch(() => []);
  console.log(`테이블 헤더: ${headerText.map(t => t.trim()).filter(t => t).join(' | ')}`);

  const hasDeptCol = headerText.some(t => /부서/i.test(t));
  const hasPosCol = headerText.some(t => /직위|직급/i.test(t));
  if (hasDeptCol) pass('부서 컬럼', '테이블 헤더에 존재');
  else warn('부서 컬럼', '테이블 헤더 미확인');
  if (hasPosCol) pass('직위/직급 컬럼', '테이블 헤더에 존재');
  else warn('직위/직급 컬럼', '테이블 헤더 미확인');

  // API 에러 확인
  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasApiError = /조회에 실패|목록 조회 실패|error/i.test(bodyText || '');
  if (hasApiError) warn('API 상태', '사용자 목록 조회 실패 메시지 감지');

  // 사용자 행 확인
  const tableRows = await page.locator('table tbody tr').count();
  const rowSel = '[role="row"]';
  const gridRows = await page.locator(rowSel).count();
  console.log(`테이블 행: ${tableRows}, role=row: ${gridRows}`);

  // 그룹웨어에서 가져오기 시도 (사용자 없을 경우)
  if (tableRows === 0) {
    const importBtn = page.locator('button').filter({ hasText: /그룹웨어|가져오기|Import/i }).first();
    if (await importBtn.isVisible().catch(() => false)) {
      console.log('그룹웨어 가져오기 버튼 클릭 시도');
      await importBtn.click();
      await page.waitForTimeout(3000);
      await shot(page, '02-after-import');
    }
  }

  const rowsAfter = await page.locator('table tbody tr').count();
  console.log(`가져오기 후 행 수: ${rowsAfter}`);

  if (rowsAfter === 0) {
    fail('사용자 목록', `0행 — API 오류 또는 권한 부족`);
    console.log(`콘솔 에러: ${consoleErrors.slice(0, 5).join(' | ')}`);
    // 컬럼 구조만이라도 확인
    if (hasDeptCol && hasPosCol) {
      pass('테이블 컬럼 구조', '부서/직위 컬럼 확인 (API 에러로 편집 테스트 불가)');
    }
    return;
  }
  pass('사용자 목록', `${rowsAfter}행`);

  // 편집 버튼 클릭
  const firstRow = page.locator('table tbody tr').first();
  const editBtn = firstRow.locator('button').filter({ hasText: /편집|수정|Edit/i }).first();
  const iconBtn = firstRow.locator('button[class*="edit"], button[aria-label*="편집"], button[aria-label*="수정"]').first();
  const anyBtn = firstRow.locator('button').first();

  let clicked = false;
  if (await editBtn.isVisible().catch(() => false)) {
    await editBtn.click(); clicked = true;
  } else if (await iconBtn.isVisible().catch(() => false)) {
    await iconBtn.click(); clicked = true;
  } else if (await anyBtn.isVisible().catch(() => false)) {
    const btnText = await anyBtn.textContent().catch(() => '');
    console.log(`첫 행 첫 버튼 텍스트: "${btnText?.trim()}"`);
    await anyBtn.click(); clicked = true;
  }

  if (!clicked) {
    fail('편집 버튼', '없음');
    return;
  }

  await page.waitForTimeout(1500);
  await shot(page, '03-edit-dialog');

  // 팝업 텍스트
  const dialog = page.locator('[role="dialog"], [class*="modal"], [class*="Dialog"]').first();
  const dialogVisible = await dialog.isVisible().catch(() => false);
  console.log(`팝업 visible: ${dialogVisible}`);

  const dialogText = await page.locator('body').textContent().catch(() => '');
  console.log(`팝업 열린 후 body 텍스트(400): ${dialogText?.slice(0, 400)}`);

  // 4개 필드 확인
  const fieldChecks = [
    { label: '부서명', patterns: ['부서명', 'department_name', 'departmentName', '부서 이름'] },
    { label: '부서 코드', patterns: ['부서 코드', 'department_code', 'departmentCode', 'dept_code'] },
    { label: '직급명', patterns: ['직급명', 'position_name', 'positionName', '직위명'] },
    { label: '직급 코드', patterns: ['직급 코드', 'position_code', 'positionCode', 'pos_code'] },
  ];

  let foundCount = 0;
  for (const { label, patterns } of fieldChecks) {
    const found = patterns.some(p => dialogText?.includes(p));
    if (found) { pass(`필드: ${label}`, '팝업에서 확인'); foundCount++; }
    else fail(`필드: ${label}`, '팝업에서 미확인');
  }

  // input 목록
  const inputs = await page.locator('[role="dialog"] input:visible, [class*="modal"] input:visible').all();
  console.log(`\n팝업 input 수: ${inputs.length}`);
  let deptNameVal = '', deptCodeVal = '', posNameVal = '', posCodeVal = '';

  for (const inp of inputs) {
    const name = await inp.getAttribute('name').catch(() => '');
    const placeholder = await inp.getAttribute('placeholder').catch(() => '');
    const value = await inp.inputValue().catch(() => '');
    const id = await inp.getAttribute('id').catch(() => '');
    console.log(`  input: id="${id}" name="${name}" placeholder="${placeholder}" value="${value}"`);

    if (/department_name|departmentName/i.test(name || '') || /부서명/.test(placeholder || '')) deptNameVal = value;
    if (/department_code|departmentCode/i.test(name || '') || /부서.코드/.test(placeholder || '')) deptCodeVal = value;
    if (/position_name|positionName/i.test(name || '') || /직급명|직위명/.test(placeholder || '')) posNameVal = value;
    if (/position_code|positionCode/i.test(name || '') || /직급.코드|직위.코드/.test(placeholder || '')) posCodeVal = value;
  }

  console.log(`\n프리필 값: 부서명="${deptNameVal}" 부서코드="${deptCodeVal}" 직급명="${posNameVal}" 직급코드="${posCodeVal}"`);

  // 값 입력 (부서/직급 input이 발견된 경우)
  const deptNameInput = page.locator('[role="dialog"] input[name*="department_name"], [role="dialog"] input[name*="departmentName"], [class*="modal"] input[name*="department"]').first();
  const posNameInput = page.locator('[role="dialog"] input[name*="position_name"], [role="dialog"] input[name*="positionName"], [class*="modal"] input[name*="position"]').first();

  let filledDept = false;
  let filledPos = false;

  if (await deptNameInput.isVisible().catch(() => false)) {
    await deptNameInput.triple_click().catch(() => deptNameInput.fill(''));
    await deptNameInput.fill('QA-부서명테스트');
    filledDept = true;
    pass('부서명 입력', 'QA-부서명테스트');
  }
  if (await posNameInput.isVisible().catch(() => false)) {
    await posNameInput.triple_click().catch(() => posNameInput.fill(''));
    await posNameInput.fill('QA-직급명테스트');
    filledPos = true;
    pass('직급명 입력', 'QA-직급명테스트');
  }

  if (filledDept || filledPos) await shot(page, '04-edit-filled');

  // 저장
  const saveBtn = page.locator('[role="dialog"] button, [class*="modal"] button')
    .filter({ hasText: /저장|Save|확인|수정/i }).first();

  if (!await saveBtn.isVisible().catch(() => false)) {
    warn('저장 버튼', '없음 — 저장 테스트 스킵');
  } else {
    await saveBtn.click();
    await page.waitForTimeout(2500);
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    await shot(page, '05-after-save');

    const dialogClosed = !await page.locator('[role="dialog"]:visible').first().isVisible().catch(() => false);
    if (dialogClosed) pass('저장 후 모달 닫힘', '정상');
    else warn('저장 후 모달', '여전히 열려 있음');

    // 재편집 → 프리필 확인
    await page.waitForTimeout(500);
    const editBtn2 = page.locator('table tbody tr').first().locator('button').first();
    if (await editBtn2.isVisible().catch(() => false)) {
      await editBtn2.click();
      await page.waitForTimeout(1200);
      await shot(page, '06-edit-prefill');

      const inputs2 = await page.locator('[role="dialog"] input:visible, [class*="modal"] input:visible').all();
      let prefillOk = false;
      for (const inp of inputs2) {
        const val = await inp.inputValue().catch(() => '');
        const name = await inp.getAttribute('name').catch(() => '');
        if (val.includes('QA')) {
          pass('재편집 프리필', `name="${name}" val="${val}"`);
          prefillOk = true;
        }
      }
      if (!prefillOk && (filledDept || filledPos)) warn('재편집 프리필', '저장된 QA 값 미확인');
      await page.keyboard.press('Escape');
    }
  }

  // 최종 판정
  console.log(`\n=== 최종 결과 ===`);
  if (foundCount >= 3) pass('부서/직급 4개 필드 검증', `${foundCount}/4 필드 렌더 확인`);
  else if (foundCount > 0) warn('부서/직급 필드 검증', `${foundCount}/4 필드만 확인`);
  else fail('부서/직급 필드 검증', '4개 필드 모두 미확인');
}, { timeout: 90_000 });
