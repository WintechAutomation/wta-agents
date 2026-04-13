import { test, expect, type Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

const FRONT_URL = 'https://mes-wta.com';
const API_URL   = 'https://mes-wta.com/api';
const SHOT_DIR  = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/bom-drawing-upload';
const TEST_UNIT = 'U19-SAA';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: true });
}

async function mesLogin(page: Page) {
  await page.goto(`${FRONT_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForTimeout(800);
  if (!page.url().includes('/login')) return;
  await page.locator('input[placeholder*="아이디"]').fill('account');
  await page.locator('input[type="password"]').fill('test1234');
  await page.locator('button:has-text("로그인")').click();
  await page.waitForURL(url => !url.toString().includes('/login'), { timeout: 15_000 });
  await page.waitForTimeout(500);
}

async function goToBomEditor(page: Page) {
  await mesLogin(page);
  await page.goto(`${FRONT_URL}/design/bom-editor`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForSelector('input[placeholder*="모품목코드"]', { timeout: 20_000 });
  await page.waitForTimeout(500);
}

async function getToken(): Promise<string> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'account', password: 'test1234' }),
  });
  const json = await res.json() as { data?: { access?: string } };
  return json.data?.access ?? '';
}

test.describe('[BOM 편집기] U19-SAA 도면 업로드 E2E', () => {

  // 테스트 타임아웃 90초
  test.setTimeout(90_000);

  test('U19-SAA 도면 업로드 전 과정 검증', async ({ page }) => {
    const token = await getToken();
    expect(token, 'JWT 토큰 획득 실패').toBeTruthy();

    // ── STEP 1: BOM 자품목 목록 조회 ──────────────────────────────
    const bomRes = await fetch(`${API_URL}/erp/bom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ item_code: TEST_UNIT }),
    });
    expect(bomRes.ok, 'BOM API 실패').toBeTruthy();
    const bomJson = await bomRes.json() as {
      success: boolean;
      data?: { bom_items?: Array<{ c_item_cd: string; use_yn: string }> };
    };
    expect(bomJson.success).toBe(true);

    const activeItems = (bomJson.data?.bom_items ?? []).filter(
      it => it.use_yn === 'Y' && it.c_item_cd?.trim() !== ''
    );
    expect(activeItems.length, 'BOM 사용 품목 없음').toBeGreaterThan(0);
    console.log(`STEP1: BOM 사용 품목 ${activeItems.length}건`);

    // ── STEP 2: 도면 없는 품목 선택 ──────────────────────────────
    const itemCodes = activeItems.map(it => it.c_item_cd);
    const checkRes = await fetch(`${API_URL}/design/check-drawings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ item_codes: itemCodes }),
    });
    expect(checkRes.ok).toBeTruthy();
    const checkJson = await checkRes.json() as { success: boolean; data?: Record<string, boolean> };
    const drawingMap = checkJson.data ?? {};

    const noDrawingItem = activeItems.find(it => drawingMap[it.c_item_cd] === false);
    const targetItem = noDrawingItem ?? activeItems[0]; // 없으면 첫 번째로 덮어쓰기 테스트
    const targetItemCode = targetItem.c_item_cd;
    const targetUnitCode = targetItemCode.split('-')[0];
    console.log(`STEP2: 대상 품목 = ${targetItemCode} (도면 없음: ${!!noDrawingItem})`);

    // ── STEP 3: 임시 도면 파일 생성 (tmp 폴더에 파일 넣기) ──────
    // webkitdirectory input은 폴더 경로 전달 필요
    const tmpDir = path.join(os.tmpdir(), `mes-drawing-test-${Date.now()}`);
    fs.mkdirSync(tmpDir, { recursive: true });
    const tmpFile = path.join(tmpDir, `${targetItemCode}.pdf`);
    fs.writeFileSync(tmpFile, `%PDF-1.4\nTest drawing for ${targetItemCode}\n`);
    console.log(`STEP3: 임시 파일 생성 = ${tmpFile}`);

    try {
      // ── STEP 4: BOM 편집기에서 U19-SAA 조회 ─────────────────────
      await goToBomEditor(page);
      await shot(page, '01-bom-editor-init');

      const itemInput = page.locator('input[placeholder*="모품목코드"]').first();
      await itemInput.fill(TEST_UNIT);
      await itemInput.press('Enter');

      await page.waitForFunction(
        () => !document.querySelector('.animate-spin'),
        { timeout: 15_000 }
      ).catch(() => {});
      await page.waitForTimeout(1500);
      await shot(page, '02-bom-loaded');

      await expect(page.locator(`text=${TEST_UNIT}`).first()).toBeVisible({ timeout: 10_000 });
      console.log('STEP4: U19-SAA BOM 조회 성공');

      // ── STEP 5: 알아서 업로드 버튼 → 폴더 주입 ─────────────────
      const uploadBtn = page.locator('button:has-text("알아서 업로드")').first();
      await expect(uploadBtn).toBeVisible({ timeout: 5_000 });
      await expect(uploadBtn).toBeEnabled();

      // webkitdirectory input에 폴더 경로 전달
      const fileInput = page.locator('input[type="file"][multiple]').first();
      await fileInput.setInputFiles(tmpDir);

      // 업로드 완료 대기 (알아서 업로드 버튼 다시 활성화)
      await page.waitForFunction(
        () => {
          const allBtns = Array.from(document.querySelectorAll('button'));
          const btn = allBtns.find(b => b.textContent?.includes('알아서 업로드'));
          return btn !== undefined && !btn.disabled;
        },
        { timeout: 20_000 }
      ).catch(() => {});
      await page.waitForTimeout(1000);
      await shot(page, '03-after-upload');

      await expect(uploadBtn).toBeEnabled({ timeout: 10_000 });
      console.log(`STEP5: 업로드 완료 (${targetItemCode})`);

      // ── STEP 6: API로 DB 반영 확인 ─────────────────────────────
      const verifyRes = await fetch(`${API_URL}/design/check-drawings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ item_codes: [targetItemCode] }),
      });
      const verifyJson = await verifyRes.json() as { success: boolean; data?: Record<string, boolean> };
      console.log(`STEP6: check-drawings = ${JSON.stringify(verifyJson.data)}`);
      expect(verifyJson.success).toBe(true);
      expect(verifyJson.data?.[targetItemCode], `DB에 ${targetItemCode} 도면 미등록`).toBe(true);
      console.log(`STEP6: DB 반영 확인 ✓ (${targetItemCode} = true)`);

      // ── STEP 7: UI 도면 열 ○ 표시 확인 ─────────────────────────
      // 페이지 재조회하여 check-drawings 재실행 후 확인
      await itemInput.fill(TEST_UNIT);
      await itemInput.press('Enter');
      await page.waitForFunction(
        () => !document.querySelector('.animate-spin'),
        { timeout: 15_000 }
      ).catch(() => {});
      await page.waitForTimeout(3000);
      await shot(page, '04-ui-drawing-check');

      const hasCircle = await page.locator('text=○').first().isVisible({ timeout: 5_000 }).catch(() => false);
      console.log(`STEP7: 도면 '○' 표시 여부 = ${hasCircle}`);
      expect(hasCircle, "도면 '○' 셀이 표시되지 않음").toBe(true);
      console.log('STEP7: UI 도면 열 ○ 확인 ✓');

    } finally {
      // ── CLEANUP: 임시 파일 삭제 + DB 도면 삭제 ──────────────────
      if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
      if (fs.existsSync(tmpDir)) fs.rmdirSync(tmpDir);

      try {
        await fetch(`${API_URL}/design/delete-drawing`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            unit_code: targetUnitCode,
            item_code: targetItemCode,
            file_name: `${targetItemCode}.pdf`,
          }),
        });
        console.log(`CLEANUP: 도면 삭제 완료 (${targetItemCode})`);
      } catch (e) {
        console.warn('CLEANUP: 도면 삭제 실패(무시)', e);
      }
    }
  });
});
