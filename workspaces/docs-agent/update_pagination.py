# -*- coding: utf-8 -*-
"""
페이지 자동 분할 JavaScript 업데이트
- 제목(h1/h2/h3)이 페이지 끝에 고아로 남으면 제목도 다음 페이지로 이동
"""
import re

OLD_SCRIPT_PATTERN = r'<script>\s*\(function\(\).*?repaginate.*?</script>'

NEW_JS = """
<script>
(function() {
  // 제목 요소 태그명 (다음 내용과 함께 있어야 하는 요소)
  var HEADING_TAGS = ['H1','H2','H3','H4'];

  function isHeading(el) {
    return HEADING_TAGS.indexOf(el.tagName) !== -1;
  }

  function repaginate() {
    var MM_TO_PX = 96 / 25.4;
    var PAGE_H   = 297 * MM_TO_PX;   // 약 1122px
    var MARGIN   = 8  * MM_TO_PX;    // page 상하 margin
    var AVAIL    = PAGE_H - MARGIN;

    var changed = true;
    var MAX_ITER = 50;
    var iter = 0;

    while (changed && iter < MAX_ITER) {
      changed = false;
      iter++;

      var pages = document.querySelectorAll('.page');
      for (var pi = 0; pi < pages.length; pi++) {
        var page = pages[pi];
        // cover-page, back-cover 건너뜀
        if (page.querySelector('.back-cover') ||
            page.classList.contains('cover-page')) continue;

        var header = page.querySelector('.page-header');
        var footer = page.querySelector('.page-footer');
        var body   = page.querySelector('.page-body');
        if (!body) continue;

        var headerH = header ? header.offsetHeight : 0;
        var footerH = footer ? footer.offsetHeight : 0;
        var maxBodyH = AVAIL - headerH - footerH;

        if (body.scrollHeight <= maxBodyH + 2) continue;

        var children = Array.from(body.children);
        if (children.length <= 1) continue;

        // 분할 지점 탐색
        var cumH = 0;
        var splitIdx = -1;
        for (var ci = 0; ci < children.length; ci++) {
          var elH = children[ci].offsetHeight;
          if (cumH + elH > maxBodyH && ci > 0) {
            splitIdx = ci;
            break;
          }
          cumH += elH;
        }
        if (splitIdx < 1) continue;

        // 분할 지점 앞 요소가 제목이면 제목도 다음 페이지로 (고아 제목 방지)
        while (splitIdx > 1 && isHeading(children[splitIdx - 1])) {
          splitIdx--;
        }

        // 새 페이지 생성
        var newPage = document.createElement('div');
        newPage.className = page.className;

        if (header) newPage.appendChild(header.cloneNode(true));

        var newBody = document.createElement('div');
        newBody.className = body.className;
        for (var ci2 = splitIdx; ci2 < children.length; ci2++) {
          newBody.appendChild(children[ci2]);
        }
        newPage.appendChild(newBody);

        if (footer) newPage.appendChild(footer.cloneNode(true));

        page.parentNode.insertBefore(newPage, page.nextSibling);
        changed = true;
        break;
      }
    }

    console.log('페이지 분할 완료. 반복:', iter, '회, 최종 페이지 수:', document.querySelectorAll('.page').length);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { setTimeout(repaginate, 300); });
  } else {
    setTimeout(repaginate, 300);
  }
})();
</script>
"""

src = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

# 기존 스크립트 제거
html_new = re.sub(OLD_SCRIPT_PATTERN, '', html, flags=re.DOTALL)

# 새 스크립트 삽입
if 'repaginate' not in html_new:
    html_new = html_new.replace('</body>', NEW_JS + '\n</body>')
    with open(src, 'w', encoding='utf-8') as f:
        f.write(html_new)
    print("페이지 분할 스크립트(제목 보호 포함) 업데이트 완료.")
else:
    print("스크립트 제거 실패 - 수동 확인 필요")
