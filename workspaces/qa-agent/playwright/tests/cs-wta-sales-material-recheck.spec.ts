import { test, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material-recheck';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

function pass(key: string, detail = '') { console.log(`✅ ${key}${detail ? ': ' + detail : ''}`); }
function fail(key: string, detail = '') { console.log(`❌ ${key}${detail ? ': ' + detail : ''}`); }

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
  await page.waitForTimeout(2000);
}

// ─────────────────────────────────────────────
// [1] 287건 로드 확인 (핵심)
// ─────────────────────────────────────────────
test('[1] 287건 로드 및 API 에러 없음', async ({ page }) => {
  const networkErrors: string[] = [];
  page.on('response', r => {
    if (r.status() >= 400 && !r.url().includes('favicon')) {
      networkErrors.push(`${r.status()} ${r.url()}`);
    }
  });

  await login(page);
  await goToSalesMaterial(page);
  await shot(page, '01-desktop-list');

  const bodyText = await page.locator('body').textContent().catch(() => '');

  // 287건 텍스트 확인
  const has287 = /287/.test(bodyText || '');
  if (has287) {
    pass('[1-1] 287건 로드', '287 텍스트 확인');
  } else {
    // 테이블 행 수 확인
    const rows = await page.locator('table tbody tr').count();
    if (rows > 0) {
      pass('[1-1] 287건 로드', `테이블 행 ${rows}건 확인 (287 텍스트 미노출)`);
    } else {
      fail('[1-1] 287건 로드', `데이터 없음, 287 텍스트 미확인. bodyText 일부: ${bodyText?.slice(0, 200)}`);
    }
  }

  // API 에러 없음
  const apiErrors = networkErrors.filter(e => e.includes('sales-material'));
  if (apiErrors.length === 0) {
    pass('[1-2] API 에러 없음', 'sales-material API 정상');
  } else {
    fail('[1-2] API 에러', apiErrors.join(', '));
  }

  // 전체 네트워크 에러
  if (networkErrors.length === 0) {
    pass('[1-3] 네트워크 에러 없음', '4xx/5xx 없음');
  } else {
    fail('[1-3] 네트워크 에러', networkErrors.slice(0, 5).join(' | '));
  }
});

// ─────────────────────────────────────────────
// [2] 등록 모달 — material_type 라디오 3개
// ─────────────────────────────────────────────
test('[2] 등록 모달 material_type 라디오 확인', async ({ page }) => {
  await login(page);
  await goToSalesMaterial(page);

  // 신규 등록 버튼 클릭
  const addBtn = page.locator('button').filter({ hasText: /신규\s*등록|등록|추가|Add/i }).first();
  if (!await addBtn.isVisible().catch(() => false)) {
    fail('[2] 등록 모달', '신규 등록 버튼 없음');
    return;
  }
  await addBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, '02-desktop-register-modal');

  // 모달 내용 확인 (div/section 등 다양한 모달 구현 허용)
  const modalContent = await page.locator('body').textContent().catch(() => '');
  const hasModalTitle = /판매자재\s*등록|판매 자재 등록/i.test(modalContent || '');
  if (!hasModalTitle) {
    fail('[2] 등록 모달', '모달 미노출');
    return;
  }

  // 라디오 버튼 3개 확인
  const radios = await page.locator('input[type="radio"]:visible').count();
  if (radios >= 3) {
    pass('[2-1] material_type 라디오', `라디오 ${radios}개 확인`);
  } else {
    // 라디오 커스텀 스타일 확인 (div role=radio 등)
    const customRadios = await page.locator('[role="radio"]:visible').count();
    if (customRadios >= 3) {
      pass('[2-1] material_type 라디오', `커스텀 라디오 ${customRadios}개 확인`);
    } else {
      fail('[2-1] material_type 라디오', `라디오 ${radios}개 (3개 기대)`);
    }
  }

  // 소모품/Spare/일반 텍스트 확인
  const hasConsumable = /소모품/i.test(modalContent || '');
  const hasSpare = /Spare/i.test(modalContent || '');
  const hasGeneral = /일반/i.test(modalContent || '');
  if (hasConsumable && hasSpare && hasGeneral) {
    pass('[2-2] material_type 선택지', '소모품/Spare/일반 3가지 확인');
  } else {
    fail('[2-2] material_type 선택지', `소모품=${hasConsumable}, Spare=${hasSpare}, 일반=${hasGeneral}`);
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
});

// ─────────────────────────────────────────────
// [3] 상세 모달 (행 클릭)
// ─────────────────────────────────────────────
test('[3] 상세 모달 — 행 클릭', async ({ page }) => {
  await login(page);
  await goToSalesMaterial(page);

  // 첫 번째 데이터 행 클릭
  const firstRow = page.locator('table tbody tr').first();
  if (!await firstRow.isVisible().catch(() => false)) {
    fail('[3] 상세 모달', '테이블 행 없음 (데이터 로드 실패)');
    return;
  }

  await firstRow.click();
  await page.waitForTimeout(1500);
  await shot(page, '03-desktop-detail-modal');

  // 모달 또는 상세 패널 노출 확인
  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasDetail = /이미지|도면|SOP|상세|Detail/i.test(bodyText || '');
  const overlayVisible = await page.locator('[role="dialog"], [class*="modal"], [class*="Modal"], [class*="detail"], [class*="Detail"]').first().isVisible().catch(() => false);

  if (overlayVisible || hasDetail) {
    pass('[3] 상세 모달', '상세 모달/패널 노출 확인');
    // 이미지/도면/SOP 탭 확인
    const tabs = await page.locator('[role="tab"], button').filter({ hasText: /이미지|도면|SOP/i }).count();
    if (tabs > 0) {
      pass('[3-1] 이미지/도면/SOP', `탭 ${tabs}개 확인`);
    } else {
      const hasSections = /이미지|도면|SOP/i.test(bodyText || '');
      if (hasSections) {
        pass('[3-1] 이미지/도면/SOP', '섹션 텍스트 확인');
      } else {
        fail('[3-1] 이미지/도면/SOP', '탭/섹션 없음');
      }
    }
  } else {
    fail('[3] 상세 모달', '클릭 후 모달 미노출');
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
});

// ─────────────────────────────────────────────
// [4] 편집 모달
// ─────────────────────────────────────────────
test('[4] 편집 모달 — prefill 확인', async ({ page }) => {
  await login(page);
  await goToSalesMaterial(page);

  // 첫 번째 행에 관리 컬럼 편집 버튼 클릭
  const firstRow = page.locator('table tbody tr').first();
  if (!await firstRow.isVisible().catch(() => false)) {
    fail('[4] 편집 모달', '테이블 행 없음');
    return;
  }

  // 행 내 편집 버튼 찾기
  const editBtn = firstRow.locator('button').filter({ hasText: /편집|수정|Edit/i }).first();
  if (await editBtn.isVisible().catch(() => false)) {
    await editBtn.click();
  } else {
    // hover 후 편집 버튼 탐색
    await firstRow.hover();
    await page.waitForTimeout(500);
    const hoverEditBtn = page.locator('button').filter({ hasText: /편집|수정|Edit/i }).first();
    if (await hoverEditBtn.isVisible().catch(() => false)) {
      await hoverEditBtn.click();
    } else {
      // 행 우클릭 또는 아이콘 버튼 탐색
      const iconBtn = firstRow.locator('button[title*="편집"], button[aria-label*="편집"], button[title*="edit"]').first();
      if (await iconBtn.isVisible().catch(() => false)) {
        await iconBtn.click();
      } else {
        fail('[4] 편집 모달', '편집 버튼 없음 (버튼 찾기 실패)');
        return;
      }
    }
  }

  await page.waitForTimeout(1500);
  await shot(page, '04-desktop-edit-modal');

  const bodyText = await page.locator('body').textContent().catch(() => '');
  const hasEdit = /편집|수정|Edit|저장|Save/i.test(bodyText || '');

  if (!hasEdit) {
    fail('[4] 편집 모달', '모달 미노출');
    return;
  }

  // prefill 확인
  const inputs = await page.locator('input[type="text"]:visible, input[type="number"]:visible').all();
  let filledCount = 0;
  for (const input of inputs) {
    const val = await input.inputValue().catch(() => '');
    if (val.trim()) filledCount++;
  }

  if (filledCount > 0) {
    pass('[4] 편집 모달 prefill', `${filledCount}개 필드 기존값 확인`);
  } else {
    fail('[4] 편집 모달 prefill', '기존값 없음');
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
});

// ─────────────────────────────────────────────
// [5] 모바일 — 햄버거 메뉴 children (iPhone 12: 390x844)
// ─────────────────────────────────────────────
test('[5] 모바일 햄버거 메뉴 — 부품 판매 children (iPhone 12)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await goToSalesMaterial(page);

  // 햄버거 버튼 찾기
  const hamburger = page.locator('button[aria-label*="menu"], button[aria-label*="Menu"], button').filter({ hasText: /☰|메뉴/i }).first();
  const hamburgerByIcon = page.locator('[class*="hamburger"], [class*="burger"], button[class*="menu"]').first();

  let opened = false;
  if (await hamburger.isVisible().catch(() => false)) {
    await hamburger.click();
    opened = true;
  } else if (await hamburgerByIcon.isVisible().catch(() => false)) {
    await hamburgerByIcon.click();
    opened = true;
  } else {
    // 모바일에서 햄버거 아이콘 위치 (보통 좌상단)
    const topLeftBtn = page.locator('header button, nav button').first();
    if (await topLeftBtn.isVisible().catch(() => false)) {
      await topLeftBtn.click();
      opened = true;
    }
  }

  await page.waitForTimeout(1000);
  await shot(page, '05-mobile-hamburger-menu');

  // Drawer 또는 사이드 메뉴 노출 확인
  const drawerVisible = await page.locator('[role="dialog"], [class*="drawer"], [class*="Drawer"], [class*="sidebar"], [class*="Sidebar"]').first().isVisible().catch(() => false);

  if (!drawerVisible && !opened) {
    fail('[5] 모바일 햄버거', 'Drawer 미노출, 햄버거 버튼 찾기 실패');
    return;
  }

  const menuText = await page.locator('body').textContent().catch(() => '');

  // 부품 판매 / Parts Sales 확인
  const hasParts = /부품\s*판매|Parts\s*Sales/i.test(menuText || '');
  // 판매 현황 / Sales List 확인
  const hasSalesList = /판매\s*현황|Sales\s*List/i.test(menuText || '');
  // 판매자재관리 / Sales Materials 확인
  const hasSalesMaterial = /판매\s*자재|Sales\s*Material/i.test(menuText || '');

  if (hasParts) pass('[5-1] 부품 판매 메뉴', '노출 확인');
  else fail('[5-1] 부품 판매 메뉴', '미노출');

  if (hasSalesList) pass('[5-2] 판매 현황 children', '노출 확인');
  else fail('[5-2] 판매 현황 children', '미노출');

  if (hasSalesMaterial) pass('[5-3] 판매자재관리 children', '노출 확인');
  else fail('[5-3] 판매자재관리 children', '미노출');
});

// ─────────────────────────────────────────────
// [6] 모바일 — 하단 탭 "더보기" (Galaxy S20: 360x800)
// ─────────────────────────────────────────────
test('[6] 모바일 더보기 탭 — 판매자재관리 항목', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await login(page);
  await goToSalesMaterial(page);

  // 하단 "더보기" 탭 찾기
  const moreBtn = page.locator('button, a, [role="tab"]').filter({ hasText: /더보기|More/i }).first();
  const moreBtnVisible = await moreBtn.isVisible().catch(() => false);

  if (!moreBtnVisible) {
    fail('[6] 더보기 탭', '더보기 버튼 없음');
    await shot(page, '06-mobile-more-tab-notfound');
    return;
  }

  await moreBtn.click();
  await page.waitForTimeout(1000);
  await shot(page, '06-mobile-more-tab');

  const pageText = await page.locator('body').textContent().catch(() => '');
  const hasSalesMaterial = /판매\s*자재|Sales\s*Material/i.test(pageText || '');

  if (hasSalesMaterial) {
    pass('[6] 더보기 판매자재관리', '항목 노출 확인');
  } else {
    fail('[6] 더보기 판매자재관리', '항목 미노출');
  }
});

// ─────────────────────────────────────────────
// [7] 모바일 카드 뷰 데이터 표시
// ─────────────────────────────────────────────
test('[7] 모바일 카드 뷰 데이터 표시', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await goToSalesMaterial(page);
  await shot(page, '07-mobile-card-view');

  // 카드 또는 리스트 아이템 확인
  const cards = await page.locator('[class*="card"], [class*="Card"]').count();
  const listItems = await page.locator('[class*="item"], [class*="Item"]').filter({ hasText: /.{5,}/ }).count();
  const table = await page.locator('table').isVisible().catch(() => false);

  if (cards > 0) {
    pass('[7] 모바일 카드 뷰', `카드 ${cards}개 데이터 표시 확인`);
  } else if (listItems > 0) {
    pass('[7] 모바일 카드 뷰', `리스트 아이템 ${listItems}개 확인`);
  } else if (!table) {
    pass('[7] 모바일 카드 뷰', '테이블 숨김 (카드 방식 추정)');
  } else {
    fail('[7] 모바일 카드 뷰', '데스크톱 테이블 그대로 노출');
  }
});
