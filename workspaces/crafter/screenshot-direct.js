// 직접 JointJS 그래프에 요소 추가 + 렌더링 확인
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => consoleLogs.push(`[PAGE_ERROR] ${err.message}`));

  console.log('1. 페이지 로드...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // JointJS Paper가 생성되었는지 확인
  const paperCheck = await page.evaluate(() => {
    const svgs = document.querySelectorAll('svg');
    const jointSvg = Array.from(svgs).find(s => s.classList.contains('joint-paper') || s.querySelector('.joint-layers'));
    if (!jointSvg) {
      return { found: false, svgCount: svgs.length, classes: Array.from(svgs).map(s => s.className.baseVal || s.className) };
    }
    return {
      found: true,
      width: jointSvg.getAttribute('width'),
      height: jointSvg.getAttribute('height'),
      children: jointSvg.children.length,
      childTags: Array.from(jointSvg.children).map(c => c.tagName + '.' + (c.className?.baseVal || ''))
    };
  });
  console.log('2. JointJS Paper 상태:', JSON.stringify(paperCheck, null, 2));

  // 모든 SVG 상세 확인
  const allSvgs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('svg')).map((svg, i) => ({
      index: i,
      class: (typeof svg.className === 'string' ? svg.className : svg.className?.baseVal) || '',
      id: svg.id,
      width: svg.getAttribute('width'),
      height: svg.getAttribute('height'),
      parent: svg.parentElement?.tagName + '.' + String(svg.parentElement?.className || '').substring(0, 50),
      childCount: svg.children.length,
    }));
  });
  console.log('3. 모든 SVG:', JSON.stringify(allSvgs, null, 2));

  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-debug-1.png' });

  // 4. Motor Control Test 프로젝트를 API로 직접 fetch 후 그래프에 로드
  console.log('4. API로 프로젝트 데이터 fetch 후 직접 로드...');
  const loadResult = await page.evaluate(async () => {
    try {
      const res = await fetch('/api/projects/proj-1775608605165');
      const data = await res.json();
      const sheets = data.sheets || [];
      if (sheets.length === 0) return { error: 'no sheets' };

      const graphJson = sheets[0].graph_json;
      const cellCount = graphJson?.cells?.length || 0;
      return { cellCount, sheetName: sheets[0].name };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log('   프로젝트 데이터:', JSON.stringify(loadResult));

  // 5. 프로젝트 다이얼로그에서 열기 시도 - 더 정확한 셀렉터
  console.log('5. 프로젝트 열기 시도...');
  await page.locator('button', { hasText: 'Project' }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-debug-2-dialog.png' });

  // 다이얼로그 내부 HTML 확인
  const dialogHtml = await page.evaluate(() => {
    const overlay = document.querySelector('div[style*="position: fixed"]');
    if (!overlay) return 'no overlay found';
    return overlay.innerHTML.substring(0, 2000);
  });
  console.log('6. 다이얼로그 HTML (처음 500자):', dialogHtml.substring(0, 500));

  // Motor Control Test 텍스트를 직접 찾아 클릭
  const allTexts = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const matches = [];
    all.forEach(el => {
      if (el.textContent?.trim() === 'Motor Control Test' && el.children.length === 0) {
        matches.push({ tag: el.tagName, class: el.className, text: el.textContent.trim() });
      }
    });
    return matches;
  });
  console.log('7. "Motor Control Test" 요소들:', JSON.stringify(allTexts));

  // 마지막(가장 하위) 요소 클릭
  if (allTexts.length > 0) {
    const mcElement = page.locator(`${allTexts[allTexts.length - 1].tag}:text-is("Motor Control Test")`).last();
    await mcElement.click({ force: true });
    await page.waitForTimeout(500);

    // 열기 버튼
    const openBtn = page.locator('button:text-is("열기")').first();
    if (await openBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await openBtn.click({ force: true });
      console.log('   열기 클릭 완료');
    } else {
      console.log('   열기 버튼 없음 - 직접 클릭으로 열렸을 수 있음');
    }
  }

  await page.waitForTimeout(3000);

  // 결과 확인
  const finalState = await page.evaluate(() => {
    const svgs = document.querySelectorAll('svg');
    let totalElements = 0;
    let totalOverlays = 0;
    svgs.forEach(svg => {
      totalElements += svg.querySelectorAll('[model-id]').length;
      totalOverlays += svg.querySelectorAll('.welec-overlay').length;
    });
    // 툴바의 프로젝트 이름 확인
    const toolbar = document.querySelector('div[style*="1e293b"]');
    const toolbarText = toolbar?.textContent || '';
    return { totalElements, totalOverlays, toolbarText: toolbarText.substring(0, 200) };
  });
  console.log('8. 최종 상태:', JSON.stringify(finalState));

  await page.screenshot({ path: 'C:/MES/wta-agents/workspaces/crafter/welec-debug-3-final.png' });

  // 에러 출력
  const errors = consoleLogs.filter(l => l.includes('ERROR') || l.includes('error'));
  if (errors.length > 0) {
    console.log('\n=== 에러 로그 ===');
    errors.slice(0, 10).forEach(e => console.log(e));
  }

  console.log('\n=== 완료 ===');
  await browser.close();
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
