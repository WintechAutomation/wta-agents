/**
 * HTML -> PDF 변환 스크립트 (Playwright page.pdf)
 *
 * 사용법:
 *   node html-to-pdf.mjs <html_path> <out_path>
 *
 * 동작 방식:
 *   1. 로컬 HTTP 서버에서 HTML 파일 서빙
 *   2. Playwright headless Chromium으로 접속
 *   3. .slide 요소를 개별 페이지로 분리하여 PDF 생성
 *   4. 배경 이미지, CSS 스타일 100% 유지
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
  console.error('Usage: node html-to-pdf.mjs <html_path> <out_path>');
  process.exit(1);
}

const absHtmlPath = path.resolve(htmlPath);
const absOutPath = path.resolve(outPath);
const htmlDir = path.dirname(absHtmlPath);
const htmlFilename = path.basename(absHtmlPath);

// 간단한 정적 파일 서버
function createServer(rootDir) {
  return http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const filePath = path.join(rootDir, decodeURIComponent(url.pathname));

    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = {
      '.html': 'text/html', '.css': 'text/css',
      '.js': 'application/javascript', '.mjs': 'application/javascript',
      '.json': 'application/json',
      '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg',
      '.png': 'image/png', '.gif': 'image/gif', '.svg': 'image/svg+xml',
      '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
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

    // 페이지 로드
    await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    console.log('Page loaded');

    // .slide 요소들을 각각 1페이지로 출력하는 CSS 주입
    // PPT 다운로드 버튼(.ppt-bar), 푸터(.footer) 숨기기
    // 각 .slide를 정확히 16:9 비율 1페이지로 맞춤
    await page.evaluate(() => {
      const style = document.createElement('style');
      style.textContent = `
        @media print {
          @page {
            size: 13.333in 7.5in;
            margin: 0;
          }
          body {
            margin: 0 !important;
            padding: 0 !important;
            background: #fff !important;
          }
          .ppt-bar, .footer, .pdf-bar, script {
            display: none !important;
          }
          .slide-wrap {
            max-width: none !important;
            margin: 0 !important;
            padding: 0 !important;
          }
          .slide {
            break-inside: avoid !important;
            break-after: page !important;
            page-break-inside: avoid !important;
            page-break-after: always !important;
            box-shadow: none !important;
            border-radius: 0 !important;
            margin: 0 !important;
            width: 13.333in !important;
            height: 7.5in !important;
            aspect-ratio: auto !important;
          }
          .slide:last-child {
            break-after: auto !important;
            page-break-after: auto !important;
          }
        }
      `;
      document.head.appendChild(style);
    });

    // PDF 생성 (16:9 landscape, 배경 포함)
    await page.pdf({
      path: absOutPath,
      width: '13.333in',
      height: '7.5in',
      printBackground: true,
      margin: { top: 0, right: 0, bottom: 0, left: 0 },
    });

    const sizeKB = (fs.statSync(absOutPath).size / 1024).toFixed(0);
    console.log(`PDF saved: ${absOutPath} (${sizeKB}KB)`);

  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(2);
  } finally {
    if (browser) await browser.close();
    server.close();
  }
}

main();
