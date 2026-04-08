// 프로젝트 데이터를 직접 graph.fromJSON()으로 로드 + 스크린샷
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => consoleLogs.push(`[ERROR] ${err.message}`));

  console.log('1. 페이지 로드...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);

  // __welec 전역 객체 확인
  const welecCheck = await page.evaluate(() => {
    const w = window.__welec;
    if (!w) return { found: false };
    return {
      found: true,
      hasGraph: !!w.graph,
      hasPaper: !!w.paper,
      hasCommands: !!w.commands,
      graphCells: w.graph && w.graph.getCells ? w.graph.getCells().length : -1,
    };
  });
  console.log('2. __welec 상태:', JSON.stringify(welecCheck));

  if (!welecCheck.found) {
    console.log('ERROR: __welec 전역 객체 없음 — SchematicCanvas가 마운트되지 않았습니다');
    await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-no-welec.png' });
    await browser.close();
    return;
  }

  // 3. API에서 Motor Control Test 프로젝트 데이터 가져오기
  console.log('3. API에서 프로젝트 데이터 로드...');
  const loadResult = await page.evaluate(async () => {
    try {
      // 프로젝트 목록에서 Motor Control Test 찾기
      const listRes = await fetch('/api/projects');
      const listData = await listRes.json();
      const projects = listData.projects || listData;
      const mct = projects.find((p) => p.name === 'Motor Control Test');
      if (!mct) return { error: 'Motor Control Test 프로젝트 없음', projects: projects.map(p => p.name) };

      // 프로젝트 상세 데이터
      const detailRes = await fetch(`/api/projects/${mct.id}`);
      const data = await detailRes.json();
      const sheets = data.sheets || [];
      if (sheets.length === 0) return { error: 'sheets 없음', projectId: mct.id };

      const graphJson = sheets[0].graph_json;
      const cellCount = graphJson?.cells?.length || 0;

      // 직접 graph.fromJSON 호출
      const w = window.__welec;
      if (w && w.commands) {
        w.commands.loadGraphJson(graphJson);
      }

      // 결과 확인
      const elements = w.graph.getElements().length;
      const links = w.graph.getLinks().length;
      return {
        success: true,
        projectId: mct.id,
        cellCount,
        afterLoad: { elements, links },
        sheetName: sheets[0].name
      };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log('   로드 결과:', JSON.stringify(loadResult, null, 2));

  await page.waitForTimeout(2000);

  // 4. 렌더링 상태 확인
  const renderState = await page.evaluate(() => {
    const svgs = document.querySelectorAll('svg');
    let modelIds = 0;
    let overlays = 0;
    let rects = 0;
    let jointElements = 0;
    svgs.forEach(svg => {
      modelIds += svg.querySelectorAll('[model-id]').length;
      overlays += svg.querySelectorAll('.welec-overlay').length;
      rects += svg.querySelectorAll('rect').length;
      jointElements += svg.querySelectorAll('.joint-element').length;
    });

    const w = window.__welec;
    const graphCells = w?.graph?.getCells?.()?.length ?? -1;

    return { modelIds, overlays, rects, jointElements, graphCells };
  });
  console.log('4. 렌더링 상태:', JSON.stringify(renderState));

  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-direct-load.png' });
  console.log('5. 스크린샷 저장 완료');

  // 에러 로그
  const errors = consoleLogs.filter(l => l.includes('ERROR') || l.includes('error') || l.includes('Error'));
  if (errors.length > 0) {
    console.log('\n=== 에러 로그 ===');
    errors.slice(0, 15).forEach(e => console.log(e));
  }

  console.log('\n=== 완료 ===');
  await browser.close();
})().catch(e => { console.error('Script Error:', e.message); process.exit(1); });
