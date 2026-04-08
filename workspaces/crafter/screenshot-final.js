// wELEC 최종 스크린샷 — 프로젝트 데이터를 직접 로드 후 캡처
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  console.log('1. 페이지 로드...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);

  // 2. 초기 화면 스크린샷
  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-final-01-initial.png' });
  console.log('   초기 화면 캡처 완료');

  // 3. Motor Control Test 프로젝트를 직접 로드
  console.log('2. Motor Control Test 프로젝트 로드...');
  const loadResult = await page.evaluate(async () => {
    const listRes = await fetch('/api/projects');
    const listData = await listRes.json();
    const projects = listData.projects || listData;
    const mct = projects.find(p => p.name === 'Motor Control Test');
    if (!mct) return { error: 'Motor Control Test not found' };

    const detailRes = await fetch('/api/projects/' + mct.id);
    const data = await detailRes.json();
    const sheets = data.sheets || [];
    if (sheets.length === 0) return { error: 'no sheets' };

    const graphJson = sheets[0].graph_json;
    const w = window.__welec;
    if (w && w.commands) {
      w.commands.loadGraphJson(graphJson);
    }

    return {
      elements: w.graph.getElements().length,
      links: w.graph.getLinks().length,
      cells: w.graph.getCells().length
    };
  });
  console.log('   로드 결과:', JSON.stringify(loadResult));

  await page.waitForTimeout(1500);

  // 4. 회로 로드 후 스크린샷
  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-final-02-circuit.png' });
  console.log('   회로도 캡처 완료');

  // 5. 심볼 탭 전환
  console.log('3. 심볼 라이브러리...');
  const symbolTab = page.locator('button', { hasText: '심볼' });
  if (await symbolTab.isVisible()) {
    await symbolTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-final-03-symbols.png' });
    console.log('   심볼 라이브러리 캡처 완료');
  }

  // 6. Parts 버튼 클릭
  console.log('4. 부품 관리...');
  const partsBtn = page.locator('button', { hasText: 'Parts' });
  if (await partsBtn.isVisible()) {
    await partsBtn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-final-04-parts.png' });
    console.log('   부품 관리 캡처 완료');
  }

  console.log('\n=== 모든 스크린샷 완료 ===');
  await browser.close();
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
