// wELEC 테스트 도면 스크린샷 캡처
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  const BASE = 'http://localhost:5173';
  const PROJECT_ID = 'proj-1775608605165';

  console.log('1. 메인 페이지 로드...');
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // 초기 화면 스크린샷
  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-01-initial.png' });
  console.log('   -> 초기 화면 캡처 완료');

  // 2. Project 버튼 클릭해서 프로젝트 다이얼로그 열기
  console.log('2. 프로젝트 다이얼로그 열기...');
  const projectBtn = page.locator('button', { hasText: 'Project' });
  if (await projectBtn.isVisible()) {
    await projectBtn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-02-project-dialog.png' });
    console.log('   -> 프로젝트 다이얼로그 캡처');

    // Motor Control Test 프로젝트 클릭 (force로 overlay 무시)
    const testProject = page.locator('text=Motor Control Test').first();
    if (await testProject.isVisible()) {
      await testProject.click({ force: true });
      await page.waitForTimeout(500);
      // "열기" 버튼 클릭
      const openBtn = page.locator('button', { hasText: '열기' }).first();
      if (await openBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await openBtn.click({ force: true });
      }
    }
  }

  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-03-circuit-loaded.png' });
  console.log('3. 회로 로드 완료 캡처');

  // 4. 심볼 탭 클릭
  console.log('4. 심볼 라이브러리 탭...');
  const symbolTab = page.locator('button', { hasText: '심볼' });
  if (await symbolTab.isVisible()) {
    await symbolTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-04-symbol-library.png' });
    console.log('   -> 심볼 라이브러리 캡처');
  }

  // 5. Parts 버튼 클릭
  console.log('5. 부품 관리...');
  const partsBtn = page.locator('button', { hasText: 'Parts' });
  if (await partsBtn.isVisible()) {
    await partsBtn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-05-parts-manager.png' });
    console.log('   -> 부품 관리 캡처');

    // 닫기
    const backBtn = page.locator('button', { hasText: '회로도' });
    if (await backBtn.isVisible()) {
      await backBtn.click();
      await page.waitForTimeout(500);
    }
  }

  console.log('=== 모든 스크린샷 캡처 완료 ===');
  await browser.close();
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
