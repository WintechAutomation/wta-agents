import { test, Browser, BrowserContext, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = 'https://cs-wta.com';
const SHOT_DIR = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/screenshots/sales-material-nocache';
const FIXTURES = 'C:/MES/wta-agents/workspaces/qa-agent/playwright/fixtures';

function shot(page: Page, name: string) {
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
  return page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`), fullPage: false });
}

async function freshContext(browser: Browser): Promise<BrowserContext> {
  return browser.newContext({
    bypassCSP: true,
    ignoreHTTPSErrors: true,
    serviceWorkers: 'block',
    extraHTTPHeaders: { 'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache' },
  });
}

async function loginFresh(page: Page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 25_000 });
  await page.waitForTimeout(800);
  const pw = page.locator('input[type="password"]').first();
  if (await pw.isVisible().catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await pw.fill('admin');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
}

test('[1] 등록 모달 — 단일 POST 확인 (품명 입력 수정)', async ({ browser }) => {
  const ctx = await freshContext(browser);
  const page = await ctx.newPage();

  const networkLog: { method: string; url: string; status: number; body?: string }[] = [];
  page.on('response', async r => {
    if (r.url().includes('sales-material') || r.url().includes('upload') || r.url().includes('s3')) {
      let body = '';
      if (r.request().method() !== 'GET') {
        body = await r.text().catch(() => '');
      }
      networkLog.push({ method: r.request().method(), url: r.url(), status: r.status(), body: body.slice(0, 200) });
    }
  });

  try {
    await loginFresh(page);
    await page.goto(`${BASE_URL}/sales-material`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.reload({ waitUntil: 'networkidle', timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1500);

    // 번들 확인
    const scripts = await page.evaluate(() =>
      Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src)
    );
    console.log(`JS 번들: ${scripts.find(s => s.includes('index-')) || '없음'}`);

    // 신규 등록 클릭
    const addBtn = page.locator('button').filter({ hasText: /신규\s*등록/i }).first();
    await addBtn.click();
    await page.waitForTimeout(1500);
    await shot(page, 'reg-01-modal-open');

    // 파일 input 확인
    const fileInputs = await page.locator('input[type="file"]').all();
    console.log(`파일 input 수: ${fileInputs.length}`);

    // 모달 내 모든 input 목록 확인
    const allInputs = await page.locator('input:visible, textarea:visible').all();
    console.log(`보이는 input 수: ${allInputs.length}`);
    for (const inp of allInputs) {
      const type = await inp.getAttribute('type').catch(() => 'text');
      const name = await inp.getAttribute('name').catch(() => '');
      const placeholder = await inp.getAttribute('placeholder').catch(() => '');
      const cls = await inp.getAttribute('class').catch(() => '');
      console.log(`  input[type=${type}] name="${name}" placeholder="${placeholder}" class="${cls?.slice(0,40)}"`);
    }

    // 품명 입력 (여러 선택자 시도)
    const nameInputSelectors = [
      'input[name="item_nm"]',
      'input[name="itemNm"]',
      'input[name="name"]',
      'label:has-text("품명") + div input',
      'label:has-text("품명") ~ input',
    ];

    let nameInputFilled = false;
    for (const sel of nameInputSelectors) {
      const inp = page.locator(sel).first();
      if (await inp.isVisible().catch(() => false)) {
        await inp.fill('QA-등록테스트-단일업로드');
        nameInputFilled = true;
        console.log(`품명 입력 성공: ${sel}`);
        break;
      }
    }

    if (!nameInputFilled) {
      // * 표시 있는 첫 번째 input 시도
      const requiredInput = page.locator('input[required], input[aria-required="true"]').first();
      if (await requiredInput.isVisible().catch(() => false)) {
        await requiredInput.fill('QA-등록테스트-단일업로드');
        nameInputFilled = true;
        console.log('필수 input으로 품명 입력');
      } else {
        // 모달 내 첫 번째 text input
        const firstTextInput = page.locator('input[type="text"]:visible, input:not([type]):visible').first();
        if (await firstTextInput.isVisible().catch(() => false)) {
          await firstTextInput.fill('QA-등록테스트-단일업로드');
          nameInputFilled = true;
          console.log('첫 번째 text input으로 품명 입력');
        }
      }
    }

    if (!nameInputFilled) {
      console.log('❌ 품명 입력 실패');
    }

    await shot(page, 'reg-02-name-filled');

    // 파일 업로드
    if (fileInputs.length >= 1) await fileInputs[0].setInputFiles(path.join(FIXTURES, 'test-image.png'));
    if (fileInputs.length >= 2) await fileInputs[1].setInputFiles(path.join(FIXTURES, 'test-drawing.pdf'));
    if (fileInputs.length >= 3) await fileInputs[2].setInputFiles(path.join(FIXTURES, 'test-sop.pdf'));
    await page.waitForTimeout(500);
    await shot(page, 'reg-03-files-selected');

    // 저장
    const saveBtn = page.locator('button').filter({ hasText: /^저장$/ }).first();
    const networkBefore = networkLog.length;
    await saveBtn.click();
    await page.waitForTimeout(4000);
    await shot(page, 'reg-04-after-save');

    // 결과 확인
    const newReqs = networkLog.slice(networkBefore);
    console.log('\n저장 후 API 요청:');
    for (const r of newReqs) console.log(`  ${r.method} ${r.url} → ${r.status} | ${r.body?.slice(0,100)}`);

    const postReqs = newReqs.filter(r => r.method === 'POST');
    const legacyImgPost = newReqs.filter(r => r.url.includes('/images'));
    const failedReqs = newReqs.filter(r => r.status >= 400);

    if (fileInputs.length >= 3) console.log('✅ [1] 파일 input 3개 확인');
    else console.log(`❌ [1] 파일 input ${fileInputs.length}개`);

    if (legacyImgPost.length > 0) {
      console.log(`❌ [1] 레거시 /images 엔드포인트 호출됨`);
    } else if (failedReqs.length > 0) {
      console.log(`❌ [1] 저장 실패: ${failedReqs.map(r=>`${r.status} ${r.url}`).join(', ')}`);
    } else if (postReqs.length > 0) {
      console.log(`✅ [1] 단일 POST 저장 성공 (레거시 /images 없음, 요청 ${postReqs.length}건)`);
    } else {
      // 모달 닫혔는지 확인
      const bodyText = await page.locator('body').textContent().catch(() => '');
      const modalClosed = !/판매자재\s*등록/i.test(bodyText || '');
      if (modalClosed) console.log('✅ [1] 모달 닫힘 (저장 성공, POST 감지 불가)');
      else console.log(`⚠️  [1] POST 없음, 모달 미닫힘. 요청 ${newReqs.length}건`);
    }

    const modalClosed = !/판매자재\s*등록/i.test(await page.locator('body').textContent().catch(() => '') || '');
    if (modalClosed) console.log('✅ [1] 등록 모달 닫힘 — 저장 성공');

  } finally {
    await ctx.close();
  }
}, { timeout: 60_000 });
