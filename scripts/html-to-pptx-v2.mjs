/**
 * HTML -> PPTX v2 변환 스크립트 (dom-to-pptx + Playwright)
 *
 * 사용법:
 *   node html-to-pptx-v2.mjs <html_path> <out_path>
 *
 * 동작 방식:
 *   1. 로컬 HTTP 서버에서 HTML 파일 서빙
 *   2. Playwright headless Chromium으로 접속
 *   3. dom-to-pptx를 inject하여 .slide 요소들을 PPTX로 변환
 *   4. PPTX 바이너리를 파일로 저장
 */
import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const htmlPath = process.argv[2];
const outPath = process.argv[3];

if (!htmlPath || !outPath) {
  console.error('Usage: node html-to-pptx-v2.mjs <html_path> <out_path>');
  process.exit(1);
}

const absHtmlPath = path.resolve(htmlPath);
const absOutPath = path.resolve(outPath);
const htmlDir = path.dirname(absHtmlPath);
const htmlFilename = path.basename(absHtmlPath);

// dom-to-pptx 번들 경로 확인
const bundleCheck = path.join(__dirname, 'node_modules', 'dom-to-pptx', 'dist', 'dom-to-pptx.bundle.js');
if (!fs.existsSync(bundleCheck)) {
  console.error('dom-to-pptx dist not found. Run: npm install dom-to-pptx');
  process.exit(1);
}

// dom-to-pptx 번들 파일 경로
function findDomToPptxBundle() {
  // browser 필드: bundle.js (IIFE, 글로벌 변수 등록)
  return path.join(__dirname, 'node_modules', 'dom-to-pptx', 'dist', 'dom-to-pptx.bundle.js');
}

// 간단한 정적 파일 서버
function createServer(rootDir) {
  return http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    let filePath = path.join(rootDir, decodeURIComponent(url.pathname));

    // dom-to-pptx 번들 서빙
    if (url.pathname === '/__dom-to-pptx.js') {
      const bundlePath = findDomToPptxBundle();
      if (bundlePath && fs.existsSync(bundlePath)) {
        const content = fs.readFileSync(bundlePath);
        res.writeHead(200, { 'Content-Type': 'application/javascript' });
        res.end(content);
        return;
      }
      res.writeHead(404);
      res.end('dom-to-pptx bundle not found');
      return;
    }

    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = {
      '.html': 'text/html',
      '.css': 'text/css',
      '.js': 'application/javascript',
      '.mjs': 'application/javascript',
      '.json': 'application/json',
      '.jpeg': 'image/jpeg',
      '.jpg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif',
      '.svg': 'image/svg+xml',
      '.woff': 'font/woff',
      '.woff2': 'font/woff2',
      '.ttf': 'font/ttf',
    };

    const contentType = mimeTypes[ext] || 'application/octet-stream';
    const content = fs.readFileSync(filePath);
    res.writeHead(200, {
      'Content-Type': contentType,
      'Access-Control-Allow-Origin': '*',
    });
    res.end(content);
  });
}

async function main() {
  console.log(`HTML: ${absHtmlPath}`);
  console.log(`OUT:  ${absOutPath}`);

  // 서버 시작
  const server = createServer(htmlDir);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const pageUrl = `http://127.0.0.1:${port}/${htmlFilename}`;
  console.log(`Server: ${pageUrl}`);

  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 1280, height: 720 },
    });

    // 페이지 로드 (domcontentloaded: DOM 파싱 완료 시 진행, 외부 리소스 대기 안 함)
    await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    // 이미지/폰트 등 외부 리소스 로딩 대기
    await page.waitForTimeout(3000);
    console.log('Page loaded');

    // === 이미지 전처리: 외부 URL → base64 data URI ===
    // dom-to-pptx는 외부 URL 이미지를 fetch할 수 없고 (CORS),
    // CSS background-image도 처리하지 못하므로:
    // 1. 모든 외부 URL을 Node.js에서 미리 다운로드 → base64 캐시 구축
    // 2. CSS background-image → absolute <img> 태그로 변환 (base64 src)
    // 3. 기존 <img> 태그의 외부 src도 base64로 교체

    // Step 1: 브라우저에서 모든 이미지 URL 수집
    const allImageUrls = await page.evaluate(() => {
      const urls = new Set();
      // CSS background-image URLs
      document.querySelectorAll('.slide').forEach(slide => {
        const bgImg = getComputedStyle(slide).backgroundImage;
        if (bgImg && bgImg !== 'none') {
          const m = bgImg.match(/url\(["']?([^"')]+)["']?\)/);
          if (m && !m[1].startsWith('data:')) urls.add(m[1]);
        }
      });
      // img tag src URLs
      document.querySelectorAll('.slide img').forEach(img => {
        if (img.src && !img.src.startsWith('data:')) urls.add(img.src);
      });
      return Array.from(urls);
    });
    console.log(`Found ${allImageUrls.length} external image URLs`);

    // Step 2: Node.js에서 이미지 다운로드 → base64 변환 (CORS 우회)
    const urlToBase64 = {};
    for (const url of allImageUrls) {
      try {
        const resp = await fetch(url);
        if (!resp.ok) { console.warn(`  SKIP ${url} (${resp.status})`); continue; }
        const buf = Buffer.from(await resp.arrayBuffer());
        const ext = url.split('.').pop().split('?')[0].toLowerCase();
        const mime = { jpeg: 'image/jpeg', jpg: 'image/jpeg', png: 'image/png', gif: 'image/gif', svg: 'image/svg+xml', webp: 'image/webp' }[ext] || 'image/png';
        urlToBase64[url] = `data:${mime};base64,${buf.toString('base64')}`;
        console.log(`  OK ${url} (${(buf.length / 1024).toFixed(0)}KB)`);
      } catch (e) {
        console.warn(`  FAIL ${url}: ${e.message}`);
      }
    }

    // Step 3: 브라우저 DOM에 적용 — background → img 변환 + 모든 src 교체
    const converted = await page.evaluate((base64Map) => {
      let bgCount = 0, imgCount = 0;

      // 3a. CSS background-image → absolute <img> 태그
      document.querySelectorAll('.slide').forEach(slide => {
        const bgImg = getComputedStyle(slide).backgroundImage;
        if (!bgImg || bgImg === 'none') return;
        const m = bgImg.match(/url\(["']?([^"')]+)["']?\)/);
        if (!m) return;
        const dataUri = base64Map[m[1]];
        if (!dataUri) return;
        const img = document.createElement('img');
        img.src = dataUri;
        img.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;pointer-events:none;';
        slide.insertBefore(img, slide.firstChild);
        Array.from(slide.children).forEach((child, i) => {
          if (i === 0) return;
          if (child.style) child.style.position = child.style.position || 'relative';
          if (child.style) child.style.zIndex = child.style.zIndex || '1';
        });
        slide.style.backgroundImage = 'none';
        bgCount++;
      });

      // 3b. 기존 img 태그 src 교체
      document.querySelectorAll('.slide img').forEach(img => {
        if (img.src.startsWith('data:')) return;
        const dataUri = base64Map[img.src];
        if (dataUri) { img.src = dataUri; imgCount++; }
      });

      return { bgCount, imgCount };
    }, urlToBase64);
    console.log(`Converted ${converted.bgCount} backgrounds + ${converted.imgCount} img tags to base64`);

    // dom-to-pptx 라이브러리 inject
    const bundlePath = findDomToPptxBundle();
    if (!bundlePath) {
      throw new Error('dom-to-pptx bundle not found');
    }
    const bundleContent = fs.readFileSync(bundlePath, 'utf-8');
    await page.evaluate(bundleContent);
    console.log('dom-to-pptx injected');

    // 변환 실행 - .slide 요소들을 찾아서 PPTX 생성
    const pptxBuffer = await page.evaluate(async () => {
      // dom-to-pptx가 전역에 등록되었는지 확인
      const lib = window.domToPptx || window.DomToPptx;
      const exportFn = lib?.exportToPptx || lib?.default?.exportToPptx;

      if (!exportFn) {
        // 글로벌 exportToPptx 직접 확인
        if (typeof exportToPptx === 'function') {
          const slides = document.querySelectorAll('.slide');
          if (slides.length === 0) throw new Error('No .slide elements found');
          const blob = await exportToPptx(Array.from(slides), {
            skipDownload: true,
            layout: 'LAYOUT_16x9',
          });
          const buf = await blob.arrayBuffer();
          return Array.from(new Uint8Array(buf));
        }
        // 사용 가능한 글로벌 변수 나열
        const globals = Object.keys(window).filter(k =>
          k.toLowerCase().includes('pptx') || k.toLowerCase().includes('dom') || k.toLowerCase().includes('export')
        );
        throw new Error(`exportToPptx not found. Related globals: ${globals.join(', ')}`);
      }

      const slides = document.querySelectorAll('.slide');
      if (slides.length === 0) throw new Error('No .slide elements found');

      console.log(`Found ${slides.length} slides`);

      const blob = await exportFn(Array.from(slides), {
        skipDownload: true,
        layout: 'LAYOUT_16x9',
      });

      const buf = await blob.arrayBuffer();
      return Array.from(new Uint8Array(buf));
    });

    // 파일 저장
    const buffer = Buffer.from(pptxBuffer);
    fs.writeFileSync(absOutPath, buffer);
    const sizeKB = (buffer.length / 1024).toFixed(0);
    console.log(`PPTX saved: ${absOutPath} (${sizeKB}KB)`);

  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(2);
  } finally {
    if (browser) await browser.close();
    server.close();
  }
}

main();
