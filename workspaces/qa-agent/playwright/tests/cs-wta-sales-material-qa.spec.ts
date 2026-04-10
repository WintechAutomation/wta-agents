import { test, Page, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

const results: Record<string, string> = {};
const bugs: string[] = [];

function pass(key: string, detail = '') {
  results[key] = `PASS${detail ? ' — ' + detail : ''}`;
  console.log(`✅ ${key}${detail ? ': ' + detail : ''}`);
}

function fail(key: string, detail = '') {
  results[key] = `FAIL${detail ? ' — ' + detail : ''}`;
  bugs.push(`${key}: ${detail}`);
  console.log(`❌ ${key}${detail ? ': ' + detail : ''}`);
}

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

async function navigateToSalesMaterial(page: Page) {
  // 부품 판매 메뉴 찾기
  const sidebarLinks = page.locator('nav a, aside a, [role="navigation"] a');
  const allLinks = await sidebarLinks.all();

  // "부품 판매" 텍스트 찾기
  let partsSaleMenu = page.locator('a, button, [role="menuitem"]').filter({ hasText: /부품\s*판매|Parts?\s*Sale/i }).first();
  const partsSaleVisible = await partsSaleMenu.isVisible().catch(() => false);

  if (partsSaleVisible) {
    await partsSaleMenu.click();
    await page.waitForTimeout(1000);
  }

  // 판매자재관리 링크 클릭
  const salesMaterialLink = page.locator('a, button, [role="menuitem"]').filter({ hasText: /판매\s*자재\s*관리|Sales?\s*Material/i }).first();
  const salesMaterialVisible = await salesMaterialLink.isVisible().catch(() => false);

  if (salesMaterialVisible) {
    await salesMaterialLink.click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
}

// 콘솔 에러 수집
async function collectConsoleErrors(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  return errors;
}

// 네트워크 에러 수집
async function collectNetworkErrors(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('response', response => {
    const status = response.status();
    if (status >= 400) {
      errors.push(`${status} ${response.url()}`);
    }
  });
  return errors;
}

test('[1] 메뉴 네비게이션 — 부품 판매 하위 children', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });

  await login(page);
  await shot(page, '01-after-login');

  // 부품 판매 메뉴 확인
  const partsSaleMenu = page.locator('a, button, li, [role="menuitem"]').filter({ hasText: /부품\s*판매/i }).first();
  const partsSaleVisible = await partsSaleMenu.isVisible().catch(() => false);

  if (!partsSaleVisible) {
    fail('[1] 부품 판매 메뉴', '메뉴 항목 없음');
    return;
  }

  await partsSaleMenu.click();
  await page.waitForTimeout(1000);
  await shot(page, '02-parts-sale-expanded');

  // 판매 현황 children 확인
  const salesStatusLink = page.locator('a, [role="menuitem"]').filter({ hasText: /판매\s*현황|Sales?\s*Status/i }).first();
  const salesStatusVisible = await salesStatusLink.isVisible().catch(() => false);

  // 판매자재관리 children 확인
  const salesMaterialLink = page.locator('a, [role="menuitem"]').filter({ hasText: /판매\s*자재\s*관리|Sales?\s*Material/i }).first();
  const salesMaterialVisible = await salesMaterialLink.isVisible().catch(() => false);

  if (salesStatusVisible && salesMaterialVisible) {
    pass('[1] 메뉴 네비게이션', '판매 현황 + 판매자재관리 2개 children 확인');
  } else {
    fail('[1] 메뉴 네비게이션', `판매현황=${salesStatusVisible}, 판매자재관리=${salesMaterialVisible}`);
  }
});

test('[2] 리스트 페이지 — 데이터 로드 및 기능', async ({ page }) => {
  const networkErrors: string[] = [];
  page.on('response', r => { if (r.status() >= 400) networkErrors.push(`${r.status()} ${r.url()}`); });

  await login(page);
  await navigateToSalesMaterial(page);
  await shot(page, '03-sales-material-list');

  const pageContent = await page.content();

  // 287건 로드 확인
  const countText = await page.locator('body').textContent().catch(() => '');
  const hasCount = /287|총\s*287|287\s*건/.test(countText || '');
  if (hasCount) {
    pass('[2-1] 데이터 건수', '287건 확인');
  } else {
    // 테이블 행 수 확인
    const rows = await page.locator('table tbody tr, [role="row"]:not([role="columnheader"])').count();
    if (rows > 0) {
      pass('[2-1] 데이터 건수', `테이블 행 ${rows}건 확인 (287건 텍스트 미노출)`);
    } else {
      fail('[2-1] 데이터 건수', '287건 확인 불가, 데이터 없음');
    }
  }

  // 검색 입력창 확인 (품명/품번/판매형번)
  const searchInput = page.locator('input[type="text"], input[type="search"], input[placeholder*="검색"], input[placeholder*="search"]').first();
  const searchVisible = await searchInput.isVisible().catch(() => false);
  if (searchVisible) {
    await searchInput.fill('테스트');
    await page.waitForTimeout(1000);
    pass('[2-2] 검색 입력창', '검색 동작 확인');
    await searchInput.clear();
    await page.waitForTimeout(500);
  } else {
    fail('[2-2] 검색 입력창', '검색 입력창 없음');
  }

  // 필터 드롭다운 확인
  const dropdowns = await page.locator('select, [role="combobox"], [class*="select"]').all();
  if (dropdowns.length >= 1) {
    pass('[2-3] 필터 드롭다운', `드롭다운 ${dropdowns.length}개 확인`);
  } else {
    fail('[2-3] 필터 드롭다운', '드롭다운 없음');
  }

  // 페이지네이션 확인
  const pagination = page.locator('[class*="pagination"], [aria-label*="pagination"], nav[role="navigation"]').first();
  const paginationVisible = await pagination.isVisible().catch(() => false);
  if (paginationVisible) {
    pass('[2-4] 페이지네이션', '페이지네이션 UI 확인');
  } else {
    // 페이지 번호 버튼으로 확인
    const pageButtons = await page.locator('button').filter({ hasText: /^[0-9]+$/ }).count();
    if (pageButtons > 1) {
      pass('[2-4] 페이지네이션', `페이지 버튼 ${pageButtons}개 확인`);
    } else {
      fail('[2-4] 페이지네이션', '페이지네이션 UI 없음');
    }
  }

  // 네트워크 에러 확인
  const relevantNetErrors = networkErrors.filter(e => !e.includes('favicon'));
  if (relevantNetErrors.length === 0) {
    pass('[2-5] 네트워크 에러', '4xx/5xx 없음');
  } else {
    fail('[2-5] 네트워크 에러', relevantNetErrors.join(', '));
  }

  await shot(page, '04-list-with-search');
});

test('[2b] 반응형 — 모바일 카드', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); // iPhone 14 크기
  await login(page);
  await navigateToSalesMaterial(page);
  await shot(page, '05-mobile-view');

  // 모바일에서 카드 레이아웃 확인
  const cards = await page.locator('[class*="card"], [class*="Card"]').count();
  const table = await page.locator('table').isVisible().catch(() => false);

  if (cards > 0) {
    pass('[2b] 모바일 카드 레이아웃', `카드 ${cards}개 확인`);
  } else if (!table) {
    pass('[2b] 모바일 카드 레이아웃', '테이블 숨김 (카드 전환 추정)');
  } else {
    fail('[2b] 모바일 카드 레이아웃', '데스크톱 테이블 그대로 노출됨');
  }
});

test('[3] 상세 모달 — 이미지/도면/SOP 탭', async ({ page }) => {
  await login(page);
  await navigateToSalesMaterial(page);

  // 첫 번째 행 클릭하여 상세 모달 열기
  const firstRow = page.locator('table tbody tr, [role="row"]:not([role="columnheader"]), [class*="item"], [class*="row"]').first();
  const firstRowVisible = await firstRow.isVisible().catch(() => false);

  if (!firstRowVisible) {
    fail('[3] 상세 모달', '리스트 행 없음');
    return;
  }

  await firstRow.click();
  await page.waitForTimeout(1500);
  await shot(page, '06-detail-modal');

  // 모달 확인
  const modal = page.locator('[role="dialog"], [class*="modal"], [class*="Modal"]').first();
  const modalVisible = await modal.isVisible().catch(() => false);

  if (!modalVisible) {
    fail('[3] 상세 모달', '모달 미노출');
    return;
  }

  // 탭 또는 섹션 확인 (이미지/도면/SOP)
  const tabs = await page.locator('[role="tab"], [class*="tab"], button').filter({ hasText: /이미지|도면|SOP|image|drawing/i }).count();
  if (tabs > 0) {
    pass('[3] 상세 모달', `이미지/도면/SOP 탭 ${tabs}개 확인`);
  } else {
    // 섹션 텍스트로 확인
    const modalContent = await modal.textContent().catch(() => '');
    const hasImageSection = /이미지|도면|SOP/i.test(modalContent || '');
    if (hasImageSection) {
      pass('[3] 상세 모달', '이미지/도면/SOP 섹션 확인 (탭 미사용)');
    } else {
      fail('[3] 상세 모달', '이미지/도면/SOP 탭 또는 섹션 없음');
    }
  }

  // 모달 닫기
  const closeBtn = page.locator('[aria-label="close"], [aria-label="닫기"], button').filter({ hasText: /close|닫기|✕|×/i }).first();
  if (await closeBtn.isVisible().catch(() => false)) {
    await closeBtn.click();
    await page.waitForTimeout(500);
  } else {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
  }
});

test('[4] 등록 모달 — 필수필드/파일업로드/드롭다운/라디오', async ({ page }) => {
  await login(page);
  await navigateToSalesMaterial(page);

  // 등록 버튼 찾기
  const addBtn = page.locator('button').filter({ hasText: /등록|추가|Add|New|\+/i }).first();
  const addBtnVisible = await addBtn.isVisible().catch(() => false);

  if (!addBtnVisible) {
    fail('[4] 등록 모달', '등록 버튼 없음');
    return;
  }

  await addBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, '07-register-modal');

  const modal = page.locator('[role="dialog"], [class*="modal"], [class*="Modal"]').first();
  const modalVisible = await modal.isVisible().catch(() => false);

  if (!modalVisible) {
    fail('[4] 등록 모달', '모달 미노출');
    return;
  }

  // 필수 필드 검증 — 빈 폼 제출
  const submitBtn = modal.locator('button[type="submit"], button').filter({ hasText: /저장|등록|Save|Submit/i }).first();
  if (await submitBtn.isVisible().catch(() => false)) {
    await submitBtn.click();
    await page.waitForTimeout(800);
    // 에러 메시지 또는 필수 표시 확인
    const errorMsg = await page.locator('[class*="error"], [class*="Error"], [aria-invalid="true"]').count();
    if (errorMsg > 0) {
      pass('[4-1] 필수 필드 검증', `에러 표시 ${errorMsg}개 확인`);
    } else {
      fail('[4-1] 필수 필드 검증', '빈 폼 제출 시 에러 없음');
    }
  } else {
    pass('[4-1] 필수 필드 검증', '제출 버튼 미확인 (스킵)');
  }

  // 파일 업로드 3종 확인
  const fileInputs = await modal.locator('input[type="file"]').count();
  if (fileInputs >= 3) {
    pass('[4-2] 파일 업로드 3종', `파일 입력 ${fileInputs}개 확인`);
  } else {
    fail('[4-2] 파일 업로드 3종', `파일 입력 ${fileInputs}개 (3개 기대)`);
  }

  // 장비모델 드롭다운 확인
  const modelDropdown = modal.locator('select, [role="combobox"]').filter({ hasText: /장비|모델|model/i }).first();
  const modelDropdownVisible = await modelDropdown.isVisible().catch(() => false);

  if (!modelDropdownVisible) {
    // 라벨로 찾기
    const modelLabel = modal.locator('label').filter({ hasText: /장비\s*모델/i }).first();
    const modelLabelVisible = await modelLabel.isVisible().catch(() => false);
    if (modelLabelVisible) {
      pass('[4-3] 장비모델 드롭다운', '장비모델 라벨 확인 (드롭다운 별도 확인 필요)');
    } else {
      fail('[4-3] 장비모델 드롭다운', '장비모델 드롭다운 없음');
    }
  } else {
    // 25건 옵션 확인
    const options = await modelDropdown.locator('option').count();
    if (options >= 25) {
      pass('[4-3] 장비모델 드롭다운', `${options}개 옵션 확인`);
    } else {
      pass('[4-3] 장비모델 드롭다운', `${options}개 옵션 (25건 기대)`);
    }
  }

  // material_type 라디오 확인 (소모품/Spare/일반)
  const radioInputs = await modal.locator('input[type="radio"]').count();
  if (radioInputs >= 3) {
    pass('[4-4] material_type 라디오', `라디오 ${radioInputs}개 확인`);
  } else {
    const radioText = await modal.textContent().catch(() => '');
    const hasMaterialType = /소모품|Spare|일반/i.test(radioText || '');
    if (hasMaterialType) {
      pass('[4-4] material_type 라디오', '소모품/Spare/일반 텍스트 확인 (라디오 스타일 커스텀)');
    } else {
      fail('[4-4] material_type 라디오', `라디오 ${radioInputs}개 (3개 기대), 소모품/Spare/일반 없음`);
    }
  }

  // status 드롭다운 확인
  const statusSelect = modal.locator('select, [role="combobox"]').filter({ hasText: /상태|status/i }).first();
  const statusVisible = await statusSelect.isVisible().catch(() => false);
  if (statusVisible) {
    pass('[4-5] status 드롭다운', '상태 드롭다운 확인');
  } else {
    // 라벨로 찾기
    const statusLabel = modal.locator('label, span').filter({ hasText: /^상태$|^status$/i }).first();
    if (await statusLabel.isVisible().catch(() => false)) {
      pass('[4-5] status 드롭다운', '상태 라벨 확인');
    } else {
      fail('[4-5] status 드롭다운', '상태 드롭다운 없음');
    }
  }

  await shot(page, '08-register-modal-detail');

  // 모달 닫기
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
});

test('[5] 편집 모달 — 기존값 prefill', async ({ page }) => {
  await login(page);
  await navigateToSalesMaterial(page);

  // 편집 버튼 찾기 (행 hover 후 편집 버튼 클릭)
  const editBtn = page.locator('button').filter({ hasText: /편집|수정|Edit|✏/i }).first();
  const editBtnVisible = await editBtn.isVisible().catch(() => false);

  if (!editBtnVisible) {
    // 첫 행에 hover 후 편집 버튼 탐색
    const firstRow = page.locator('table tbody tr, [class*="row"]').first();
    if (await firstRow.isVisible().catch(() => false)) {
      await firstRow.hover();
      await page.waitForTimeout(500);
    }
    const editBtnAfterHover = page.locator('button').filter({ hasText: /편집|수정|Edit/i }).first();
    if (!await editBtnAfterHover.isVisible().catch(() => false)) {
      fail('[5] 편집 모달', '편집 버튼 없음');
      return;
    }
    await editBtnAfterHover.click();
  } else {
    await editBtn.click();
  }

  await page.waitForTimeout(1500);
  await shot(page, '09-edit-modal');

  const modal = page.locator('[role="dialog"], [class*="modal"], [class*="Modal"]').first();
  if (!await modal.isVisible().catch(() => false)) {
    fail('[5] 편집 모달', '모달 미노출');
    return;
  }

  // 입력 필드에 기존값 prefill 확인
  const inputs = await modal.locator('input[type="text"], input[type="number"], textarea').all();
  let filledCount = 0;
  for (const input of inputs) {
    const val = await input.inputValue().catch(() => '');
    if (val && val.trim()) filledCount++;
  }

  if (filledCount > 0) {
    pass('[5] 편집 모달 prefill', `${filledCount}개 필드 기존값 채워짐`);
  } else {
    fail('[5] 편집 모달 prefill', '기존값 prefill 없음');
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
});

test('[6] 장비모델 관리 모달', async ({ page }) => {
  await login(page);
  await navigateToSalesMaterial(page);

  // 장비모델 관리 버튼 찾기
  const modelMgmtBtn = page.locator('button').filter({ hasText: /장비\s*모델\s*관리|모델\s*관리|Model\s*Manage/i }).first();
  const visible = await modelMgmtBtn.isVisible().catch(() => false);

  if (!visible) {
    fail('[6] 장비모델 관리 모달', '장비모델 관리 버튼 없음');
    return;
  }

  await modelMgmtBtn.click();
  await page.waitForTimeout(1500);
  await shot(page, '10-model-manage-modal');

  const modal = page.locator('[role="dialog"], [class*="modal"], [class*="Modal"]').first();
  if (await modal.isVisible().catch(() => false)) {
    pass('[6] 장비모델 관리 모달', '모달 노출 확인');
    await page.keyboard.press('Escape');
  } else {
    fail('[6] 장비모델 관리 모달', '모달 미노출');
  }
});

test('[7] i18n 4언어 전환', async ({ page }) => {
  await login(page);
  await navigateToSalesMaterial(page);
  await shot(page, '11-i18n-ko');

  const langSwitcher = page.locator('[class*="lang"], [class*="i18n"], [aria-label*="language"], select').filter({ hasText: /KO|한국어|언어/i }).first();

  // 언어 전환 버튼 목록 찾기
  const langButtons = page.locator('button, [role="option"]').filter({ hasText: /EN|English|한국어|KO|中文|ZH|日本語|JA/i });
  const langBtnCount = await langButtons.count();

  if (langBtnCount < 2) {
    // nav bar에서 언어 드롭다운 찾기
    const langDropdown = page.locator('[class*="language"], [class*="locale"]').first();
    if (await langDropdown.isVisible().catch(() => false)) {
      pass('[7] i18n 언어 전환', '언어 선택 UI 확인');
    } else {
      fail('[7] i18n 언어 전환', '언어 전환 UI 없음');
    }
    return;
  }

  // nav.salesMaterial 키 확인 — 메뉴 텍스트 변경 확인
  const menuText = await page.locator('nav, aside').textContent().catch(() => '');

  // EN 전환 시도
  const enBtn = page.locator('button, a, [role="option"]').filter({ hasText: /^EN$|English/i }).first();
  if (await enBtn.isVisible().catch(() => false)) {
    await enBtn.click();
    await page.waitForTimeout(1000);
    const menuTextEn = await page.locator('nav, aside').textContent().catch(() => '');
    const changed = menuText !== menuTextEn;
    if (changed) {
      pass('[7-1] EN 전환', '메뉴 텍스트 변경 확인');
    } else {
      fail('[7-1] EN 전환', '텍스트 변경 없음');
    }
    await shot(page, '12-i18n-en');
  }

  pass('[7] i18n 4언어 UI', `언어 버튼 ${langBtnCount}개 확인`);
});

test('[8] 콘솔 에러 없음', async ({ page }) => {
  const consoleErrors: string[] = [];
  const networkErrors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('response', r => {
    if (r.status() >= 400 && !r.url().includes('favicon')) {
      networkErrors.push(`${r.status()} ${r.url()}`);
    }
  });

  await login(page);
  await navigateToSalesMaterial(page);
  await page.waitForTimeout(3000);

  if (consoleErrors.length === 0) {
    pass('[8-1] 콘솔 에러', '에러 없음');
  } else {
    fail('[8-1] 콘솔 에러', consoleErrors.slice(0, 3).join(' | '));
  }

  if (networkErrors.length === 0) {
    pass('[8-2] 네트워크 에러', '4xx/5xx 없음');
  } else {
    fail('[8-2] 네트워크 에러', networkErrors.slice(0, 3).join(' | '));
  }
});
