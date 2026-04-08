// Motor Control Test 프로젝트 열기 + 심볼 드래그 테스트
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  // 콘솔 로그 수집
  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => consoleLogs.push(`[ERROR] ${err.message}`));

  console.log('1. 페이지 로드...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // 2. Project 다이얼로그로 Motor Control Test 열기
  console.log('2. Motor Control Test 열기...');
  await page.locator('button', { hasText: 'Project' }).click();
  await page.waitForTimeout(1000);

  // 프로젝트 목록에서 Motor Control Test 선택
  const items = await page.locator('div').filter({ hasText: /^Motor Control Test$/ }).all();
  console.log(`   프로젝트 항목 수: ${items.length}`);

  if (items.length > 0) {
    await items[0].click({ force: true });
    await page.waitForTimeout(500);
  }

  // 열기 버튼 있으면 클릭
  const openBtns = await page.locator('button').filter({ hasText: /^열기$/ }).all();
  if (openBtns.length > 0) {
    await openBtns[0].click({ force: true });
  }

  await page.waitForTimeout(3000);

  // 캔버스 상태 확인
  const svgCount = await page.evaluate(() => {
    const svgs = document.querySelectorAll('svg');
    let result = {};
    svgs.forEach((svg, i) => {
      const rects = svg.querySelectorAll('rect');
      const circles = svg.querySelectorAll('circle');
      const lines = svg.querySelectorAll('line');
      const texts = svg.querySelectorAll('text');
      const overlays = svg.querySelectorAll('.welec-overlay');
      result[`svg${i}`] = { rects: rects.length, circles: circles.length, lines: lines.length, texts: texts.length, overlays: overlays.length };
    });
    return { svgCount: svgs.length, details: result };
  });
  console.log('3. SVG 상태:', JSON.stringify(svgCount, null, 2));

  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-circuit-open.png' });
  console.log('   -> 회로 열기 캡처');

  // 4. 심볼 탭으로 전환
  console.log('4. 심볼 탭 전환...');
  await page.locator('button', { hasText: '심볼' }).click();
  await page.waitForTimeout(500);

  // 5. 심볼 드래그앤드롭 테스트 (3상 전원 → 캔버스)
  console.log('5. 심볼 드래그앤드롭 테스트...');
  const symbolItem = page.locator('text=3상 전원').first();
  const canvas = page.locator('div[style*="overflow: hidden"][style*="position: absolute"]').first();

  if (await symbolItem.isVisible() && await canvas.isVisible()) {
    const symBox = await symbolItem.boundingBox();
    const canvasBox = await canvas.boundingBox();

    if (symBox && canvasBox) {
      // 드래그앤드롭
      await page.mouse.move(symBox.x + symBox.width / 2, symBox.y + symBox.height / 2);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + 400, canvasBox.y + 200, { steps: 10 });
      await page.mouse.up();

      await page.waitForTimeout(2000);

      const afterDrag = await page.evaluate(() => {
        const svg = document.querySelector('svg.joint-paper');
        if (!svg) return { found: false };
        const elements = svg.querySelectorAll('.joint-element');
        const overlays = svg.querySelectorAll('.welec-overlay');
        return { found: true, elements: elements.length, overlays: overlays.length };
      });
      console.log('   드래그 후 상태:', JSON.stringify(afterDrag));
    }
  }

  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-after-drag.png' });
  console.log('   -> 드래그 후 캡처');

  // 콘솔 에러 출력
  const errors = consoleLogs.filter(l => l.includes('[ERROR]') || l.includes('error'));
  if (errors.length > 0) {
    console.log('\n=== 콘솔 에러 ===');
    errors.forEach(e => console.log(e));
  }

  console.log('\n=== 완료 ===');
  await browser.close();
})().catch(e => { console.error('Script Error:', e.message); process.exit(1); });
