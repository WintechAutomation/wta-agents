# -*- coding: utf-8 -*-
"""
페이지 자동 분할 JavaScript를 HTML에 추가
- 각 .page의 .page-body 높이가 최대치 초과 시 자동으로 새 페이지를 만들어 내용 이동
"""

JS_SCRIPT = """
<script>
(function() {
  function repaginate() {
    var MM_TO_PX = 96 / 25.4;
    var PAGE_H = 297 * MM_TO_PX;   // 약 1122px
    var MARGIN = 8 * MM_TO_PX;     // page margin top+bottom
    var AVAIL = PAGE_H - MARGIN;   // body에 사용 가능한 픽셀

    var changed = true;
    var MAX_ITER = 30;
    var iter = 0;

    while (changed && iter < MAX_ITER) {
      changed = false;
      iter++;

      var pages = document.querySelectorAll('.page');
      for (var pi = 0; pi < pages.length; pi++) {
        var page = pages[pi];
        // cover-page, back-cover 건너뜀
        if (page.querySelector('.cover-page, .back-cover') ||
            page.classList.contains('cover-page')) continue;

        var header = page.querySelector('.page-header');
        var footer = page.querySelector('.page-footer');
        var body   = page.querySelector('.page-body');
        if (!body) continue;

        var headerH = header ? header.offsetHeight : 0;
        var footerH = footer ? footer.offsetHeight : 0;
        var maxBodyH = AVAIL - headerH - footerH;

        if (body.scrollHeight <= maxBodyH + 2) continue;

        // 자식 요소를 쌓으면서 초과 지점 찾기
        var children = Array.from(body.children);
        if (children.length <= 1) continue;

        var cumH = 0;
        var splitIdx = -1;
        for (var ci = 0; ci < children.length; ci++) {
          var ch = children[ci].offsetHeight;
          if (cumH + ch > maxBodyH && ci > 0) {
            splitIdx = ci;
            break;
          }
          cumH += ch;
        }
        if (splitIdx < 1) continue;

        // 새 페이지 생성 (현재 페이지 구조 복사)
        var newPage = document.createElement('div');
        newPage.className = page.className;

        // 헤더 복사
        if (header) newPage.appendChild(header.cloneNode(true));

        // 새 page-body 생성 — 나머지 자식 이동
        var newBody = document.createElement('div');
        newBody.className = body.className;
        for (var ci2 = splitIdx; ci2 < children.length; ci2++) {
          newBody.appendChild(children[ci2]);
        }
        newPage.appendChild(newBody);

        // 푸터 복사
        if (footer) newPage.appendChild(footer.cloneNode(true));

        // 현재 페이지 다음에 삽입
        page.parentNode.insertBefore(newPage, page.nextSibling);

        changed = true;
        break; // DOM 변경 후 재순회
      }
    }

    console.log('페이지 분할 완료. 반복:', iter, '회, 최종 페이지 수:', document.querySelectorAll('.page').length);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      setTimeout(repaginate, 300);
    });
  } else {
    setTimeout(repaginate, 300);
  }
})();
</script>
"""

src = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

if '<script>' in html and 'repaginate' in html:
    print("이미 페이지 분할 스크립트가 존재합니다.")
else:
    html = html.replace('</body>', JS_SCRIPT + '\n</body>')
    with open(src, 'w', encoding='utf-8') as f:
        f.write(html)
    print("페이지 자동 분할 스크립트 추가 완료.")
