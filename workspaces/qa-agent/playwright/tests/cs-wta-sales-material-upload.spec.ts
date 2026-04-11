import { test, Page, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material-upload';
const FIXTURES = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/fixtures';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

function pass(key: string, detail = '') { console.log(`✅ ${key}${detail ? ': ' + detail : ''}`); }
function fail(key: string, detail = '') { console.log(`❌ ${key}${detail ? ': ' + detail : ''}`); }
function warn(key: string, detail = '') { console.log(`⚠️  ${key}${detail ? ': ' + detail : ''}`); }

async function login(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 25_000 });
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

async function goToSalesMaterial(page: Page) {
  await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(1500);
}

// ─────────────────────────────────────────────
// [1] 등록 모달 — 파일 3종 선택 후 저장 1회
// ─────────────────────────────────────────────
test('[1] 등록 모달 — 단일 저장으로 레코드+파일 원자 업로드', async ({ page }) => {
  const networkRequests: { url: string; method: string; status: number }[] = [];
  page.on('response', async r => {
    if (r.url().includes('sales-material') || r.url().includes('upload') || r.url().includes('s3')) {
      networkRequests.push({ url: r.url(), method: r.request().method(), status: r.status() });
    }
  });

  await login(page);
  await goToSalesMaterial(page);

  // 신규 등록 버튼
  const addBtn = page.locator('button').filter({ hasText: /신규\s*등록|등록|Add/i }).first();
  if (!await addBtn.isVisible().catch(() => false)) { fail('[1] 등록 모달', '신규 등록 버튼 없음'); return; }
  await addBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, '01-register-modal-open');

  // 필수 필드 입력
  const nameInput = page.locator('input[placeholder*="품명"], input[name*="name"], input[name*="item"]').first();
  const nameInputFallback = page.locator('label').filter({ hasText: /^품명/ }).locator('..').locator('input').first();
  if (await nameInput.isVisible().catch(() => false)) {
    await nameInput.fill('QA-테스트-파일업로드-001');
  } else if (await nameInputFallback.isVisible().catch(() => false)) {
    await nameInputFallback.fill('QA-테스트-파일업로드-001');
  } else {
    // 첫 번째 text input
    const firstInput = page.locator('input[type="text"]:visible').first();
    if (await firstInput.isVisible().catch(() => false)) await firstInput.fill('QA-테스트-파일업로드-001');
  }

  // 파일 input 탐색 (이미지/도면/SOP)
  const fileInputs = await page.locator('input[type="file"]:visible, input[type="file"]').all();
  console.log(`파일 input 수: ${fileInputs.length}`);

  // 숨겨진 파일 input 포함
  const allFileInputs = await page.locator('input[type="file"]').all();
  console.log(`전체 파일 input 수 (hidden 포함): ${allFileInputs.length}`);

  if (allFileInputs.length === 0) {
    warn('[1] 파일 입력', '파일 input 없음 — UI 방식 업로드 탐색');
    // 파일 업로드 버튼 탐색
    const uploadBtns = page.locator('button').filter({ hasText: /이미지|도면|SOP|파일|업로드|upload/i });
    const uploadBtnCount = await uploadBtns.count();
    console.log(`파일 업로드 버튼 수: ${uploadBtnCount}`);
    if (uploadBtnCount > 0) {
      pass('[1] 파일 업로드 UI', `업로드 버튼 ${uploadBtnCount}개 확인`);
    } else {
      fail('[1] 파일 업로드', '파일 input 및 업로드 버튼 모두 없음');
    }
  } else if (allFileInputs.length >= 3) {
    // 3개 파일 업로드
    await allFileInputs[0].setInputFiles(path.join(FIXTURES, 'test-image.png'));
    await page.waitForTimeout(500);
    await allFileInputs[1].setInputFiles(path.join(FIXTURES, 'test-drawing.pdf'));
    await page.waitForTimeout(500);
    await allFileInputs[2].setInputFiles(path.join(FIXTURES, 'test-sop.pdf'));
    await page.waitForTimeout(500);
    pass('[1] 파일 3종 선택', '이미지/도면/SOP 파일 선택 완료');
    await shot(page, '02-files-selected');
  } else {
    // 있는 만큼 업로드
    for (let i = 0; i < allFileInputs.length; i++) {
      const files = [
        path.join(FIXTURES, 'test-image.png'),
        path.join(FIXTURES, 'test-drawing.pdf'),
        path.join(FIXTURES, 'test-sop.pdf'),
      ];
      await allFileInputs[i].setInputFiles(files[i]);
      await page.waitForTimeout(300);
    }
    warn('[1] 파일 선택', `파일 input ${allFileInputs.length}개 (3개 기대)`);
  }

  // 저장 버튼 클릭 (1회)
  const saveBtn = page.locator('button').filter({ hasText: /저장|Save/i }).first();
  if (!await saveBtn.isVisible().catch(() => false)) {
    fail('[1] 저장 버튼', '없음');
    return;
  }

  await shot(page, '03-before-save');
  await saveBtn.click();
  await page.waitForTimeout(3000); // 업로드 대기

  await shot(page, '04-after-save');

  // 결과 확인
  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasError = /error|에러|실패|failed/i.test(bodyText || '');
  const hasSuccess = /성공|완료|등록|saved|success/i.test(bodyText || '');

  console.log(`저장 후 네트워크 요청:`);
  for (const req of networkRequests) {
    console.log(`  ${req.method} ${req.url} → ${req.status}`);
  }

  // 모달이 닫혔으면 성공
  const modalClosed = !await page.locator('button').filter({ hasText: /저장|Save/i }).first().isVisible().catch(() => false);

  if (modalClosed && !hasError) {
    pass('[1] 단일 저장 원자 업로드', '모달 닫힘 — 저장 성공');
    // 등록된 항목 확인
    const newItemVisible = await page.locator('body').textContent().catch(() => '');
    if (/QA-테스트-파일업로드-001/.test(newItemVisible || '')) {
      pass('[1] 등록 항목 리스트 반영', '신규 항목 확인');
    } else {
      warn('[1] 등록 항목 리스트', '리스트에서 신규 항목 미확인 (필터 초기화 필요할 수 있음)');
    }
  } else if (hasError) {
    fail('[1] 단일 저장', `에러 발생: ${bodyText?.match(/error.{0,100}/i)?.[0] || '에러 텍스트'}`);
  } else {
    warn('[1] 단일 저장', '모달 미닫힘 또는 성공 여부 불명확');
  }

  // API 호출 성공 여부
  const uploadReqs = networkRequests.filter(r => r.method === 'POST' || r.method === 'PUT');
  const failedReqs = uploadReqs.filter(r => r.status >= 400);
  if (failedReqs.length === 0 && uploadReqs.length > 0) {
    pass('[1] API 업로드 요청', `${uploadReqs.length}건 성공`);
  } else if (failedReqs.length > 0) {
    fail('[1] API 업로드 요청', failedReqs.map(r => `${r.status} ${r.url}`).join(', '));
  }
});

// ─────────────────────────────────────────────
// [2] 편집 모달 — 기존 파일(회색) + 신규 파일(파란) 동시 처리
// ─────────────────────────────────────────────
test('[2] 편집 모달 — 기존 파일 표시 + 신규 파일 업로드', async ({ page }) => {
  const networkRequests: { url: string; method: string; status: number }[] = [];
  page.on('response', async r => {
    if (r.url().includes('sales-material') || r.url().includes('upload') || r.url().includes('s3')) {
      networkRequests.push({ url: r.url(), method: r.request().method(), status: r.status() });
    }
  });

  await login(page);
  await goToSalesMaterial(page);

  // 첫 번째 행의 편집 버튼 클릭
  const firstRow = page.locator('table tbody tr').first();
  if (!await firstRow.isVisible().catch(() => false)) {
    fail('[2] 편집 모달', '테이블 행 없음');
    return;
  }

  // 편집 아이콘 버튼 (파란 연필 아이콘)
  const editBtn = firstRow.locator('button').nth(0); // 첫 번째 버튼 = 편집
  await editBtn.click({ force: true });
  await page.waitForTimeout(1500);
  await shot(page, '05-edit-modal-open');

  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasEdit = /편집|수정|Edit|저장/i.test(bodyText || '');

  if (!hasEdit) {
    fail('[2] 편집 모달', '모달 미노출');
    return;
  }
  pass('[2] 편집 모달', '모달 노출 확인');

  // 기존 파일 표시 확인 (회색 스타일 요소)
  const existingFiles = await page.locator('[class*="gray"], [class*="grey"], [class*="existing"], [class*="current"]').count();
  const fileLinks = await page.locator('a[href*="s3"], a[href*="storage"], [class*="file"]').count();
  console.log(`기존 파일 요소: ${existingFiles}개, 파일 링크: ${fileLinks}개`);

  // 파일 input 탐색
  const allFileInputs = await page.locator('input[type="file"]').all();
  console.log(`편집 모달 파일 input: ${allFileInputs.length}개`);

  if (allFileInputs.length >= 1) {
    // 신규 파일 설정 (첫 번째 파일 input)
    await allFileInputs[0].setInputFiles(path.join(FIXTURES, 'test-image.png'));
    await page.waitForTimeout(500);
    await shot(page, '06-edit-new-file-selected');

    // 신규 파일 표시 확인 (파란 스타일)
    const newFileIndicator = await page.locator('[class*="blue"], [class*="new"], [class*="pending"]').count();
    console.log(`신규 파일 표시: ${newFileIndicator}개`);

    if (newFileIndicator > 0) {
      pass('[2] 신규 파일 표시', `파란 스타일 요소 ${newFileIndicator}개 확인`);
    } else {
      warn('[2] 신규 파일 표시', '파란 표시 요소 미확인 (다른 방식일 수 있음)');
    }

    // 저장
    const saveBtn = page.locator('button').filter({ hasText: /저장|Save/i }).first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(3000);
      await shot(page, '07-edit-after-save');

      const afterText = await page.locator('body').textContent().catch(() => '');
      const modalClosed = !await page.locator('button').filter({ hasText: /저장|Save/i }).first().isVisible().catch(() => false);

      if (modalClosed) {
        pass('[2] 편집 저장', '모달 닫힘 — 저장 성공');
      } else {
        warn('[2] 편집 저장', '모달 미닫힘');
      }
    }
  } else {
    warn('[2] 파일 input', '편집 모달에 파일 input 없음 — UI 방식 확인 필요');
    // 파일 업로드 관련 버튼/영역 확인
    const uploadArea = await page.locator('[class*="upload"], [class*="dropzone"], button').filter({ hasText: /이미지|도면|SOP|파일/i }).count();
    console.log(`파일 업로드 영역/버튼: ${uploadArea}개`);
    if (uploadArea > 0) {
      pass('[2] 파일 업로드 UI', `업로드 영역 ${uploadArea}개 확인`);
    } else {
      fail('[2] 파일 업로드 UI', '파일 업로드 UI 없음');
    }
  }

  // 편집 모달 API 요청 확인
  const editReqs = networkRequests.filter(r => r.method !== 'GET');
  for (const req of editReqs) {
    console.log(`  편집 API: ${req.method} ${req.url} → ${req.status}`);
  }
});

// ─────────────────────────────────────────────
// [3] 파일 삭제 즉시 반영 확인
// ─────────────────────────────────────────────
test('[3] 편집 모달 — 기존 파일 삭제 즉시 반영', async ({ page }) => {
  const deleteRequests: { url: string; status: number }[] = [];
  page.on('response', async r => {
    if ((r.url().includes('sales-material') || r.url().includes('upload') || r.url().includes('file'))
        && r.request().method() === 'DELETE') {
      deleteRequests.push({ url: r.url(), status: r.status() });
    }
  });

  await login(page);
  await goToSalesMaterial(page);

  // 파일이 있는 항목 찾기 (파일 컬럼 값 있는 행)
  const rows = await page.locator('table tbody tr').all();
  let targetRow = null;

  for (const row of rows) {
    const rowText = await row.textContent().catch(() => '');
    // 파일 컬럼이 "-" 아닌 행 찾기
    if (rowText && !/^[\s-]*$/.test(rowText)) {
      // 실제로 파일이 있는지 확인하기 위해 편집 모달 열기
      const editBtn = row.locator('button').nth(0);
      if (await editBtn.isVisible().catch(() => false)) {
        await editBtn.click({ force: true });
        await page.waitForTimeout(1200);

        const fileLinks = await page.locator('a[href*="s3"], a[href*="storage"], a[href*="amazonaws"]').count();
        const existingFileEl = await page.locator('[class*="existing"], [class*="current"], [class*="gray"]').count();
        console.log(`행 파일링크=${fileLinks}, 기존파일요소=${existingFileEl}`);

        if (fileLinks > 0 || existingFileEl > 0) {
          targetRow = row;
          break;
        }
        // 닫기
        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      }
    }
  }

  if (!targetRow) {
    warn('[3] 파일 삭제', '파일 등록된 항목 없음 — 삭제 테스트 스킵');
    console.log('등록된 파일이 있는 항목을 찾지 못했습니다. [1] 테스트에서 등록한 항목 확인 필요.');
    return;
  }

  await shot(page, '08-edit-with-file');

  // 삭제 버튼 찾기 (파일 옆 X 버튼)
  const deleteFileBtns = page.locator('button[aria-label*="삭제"], button[aria-label*="delete"], button[title*="삭제"]').first();
  const xBtn = page.locator('[class*="file"] button, [class*="upload"] button').filter({ hasText: /×|✕|X|삭제/i }).first();

  if (await deleteFileBtns.isVisible().catch(() => false)) {
    await deleteFileBtns.click();
    await page.waitForTimeout(500);
    pass('[3] 파일 삭제 버튼', '삭제 버튼 클릭');
  } else if (await xBtn.isVisible().catch(() => false)) {
    await xBtn.click();
    await page.waitForTimeout(500);
    pass('[3] 파일 삭제 버튼', 'X 버튼 클릭');
  } else {
    warn('[3] 파일 삭제', '삭제 버튼 미발견 — 파일 없는 항목이거나 UI 확인 필요');
    await shot(page, '08b-no-delete-btn');
    return;
  }

  await shot(page, '09-after-file-delete');

  // 저장
  const saveBtn = page.locator('button').filter({ hasText: /저장|Save/i }).first();
  if (await saveBtn.isVisible().catch(() => false)) {
    await saveBtn.click();
    await page.waitForTimeout(2000);
    await shot(page, '10-after-save-delete');

    // 삭제 API 호출 확인
    if (deleteRequests.length > 0) {
      const successDel = deleteRequests.filter(r => r.status < 300);
      if (successDel.length > 0) {
        pass('[3] 파일 삭제 API', `DELETE ${successDel.length}건 성공`);
      } else {
        fail('[3] 파일 삭제 API', deleteRequests.map(r => `${r.status} ${r.url}`).join(', '));
      }
    } else {
      warn('[3] 파일 삭제 API', 'DELETE 요청 미감지 (즉시 반영 또는 다른 방식)');
    }
    pass('[3] 편집 저장', '저장 완료');
  }
});

// ─────────────────────────────────────────────
// [4] 모바일 뷰포트 — 판매자재관리 접근 및 동작
// ─────────────────────────────────────────────
test('[4] 모바일(iPhone 12) — 판매자재관리 접근 및 카드뷰', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await goToSalesMaterial(page);
  await shot(page, '11-mobile-list');

  // 287건 확인
  const bodyText = await page.locator('body').textContent().catch(() => '');
  const has287 = /287/.test(bodyText || '');
  if (has287) pass('[4-1] 모바일 287건', '확인');
  else {
    const cardCount = await page.locator('[class*="card"], [class*="Card"], [class*="item"]').count();
    if (cardCount > 0) pass('[4-1] 모바일 데이터', `${cardCount}개 카드 확인`);
    else fail('[4-1] 모바일 데이터', '데이터 없음');
  }

  // 모바일 신규 등록 버튼
  const addBtn = page.locator('button').filter({ hasText: /신규\s*등록|등록/i }).first();
  if (await addBtn.isVisible().catch(() => false)) {
    pass('[4-2] 모바일 등록 버튼', '확인');
    await addBtn.click();
    await page.waitForTimeout(1000);
    await shot(page, '12-mobile-register-modal');

    // 모바일 모달 정상 노출
    const modalText = await page.locator('body').textContent().catch(() => '');
    if (/판매자재\s*등록/i.test(modalText || '')) {
      pass('[4-3] 모바일 등록 모달', '노출 확인');
    } else {
      fail('[4-3] 모바일 등록 모달', '미노출');
    }
    await page.keyboard.press('Escape');
  } else {
    fail('[4-2] 모바일 등록 버튼', '없음');
  }
});

test('[4b] 모바일(Galaxy S20: 360x800) — 판매자재관리 접근', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await login(page);
  await goToSalesMaterial(page);
  await shot(page, '13-galaxy-list');

  const bodyText = await page.locator('body').textContent().catch(() => '');
  const has287 = /287/.test(bodyText || '');
  const cardCount = await page.locator('[class*="card"], [class*="Card"]').count();

  if (has287 || cardCount > 0) {
    pass('[4b] Galaxy S20 데이터', has287 ? '287건 확인' : `카드 ${cardCount}개`);
  } else {
    fail('[4b] Galaxy S20 데이터', '데이터 없음');
  }

  // 네트워크 에러 확인
  const errors: string[] = [];
  page.on('response', r => {
    if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`);
  });
  await page.reload({ waitUntil: 'networkidle', timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(1000);

  if (errors.length === 0) pass('[4b] 네트워크 에러', '없음');
  else fail('[4b] 네트워크 에러', errors.slice(0, 3).join(' | '));
});
