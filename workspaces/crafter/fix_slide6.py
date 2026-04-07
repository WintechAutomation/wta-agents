# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

old_slide6 = """<!-- SLIDE 6: 부적합 자동 등록 -->
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">부적합 자동 등록 프로세스</div></div>
  <div class="s-body">
    <p>슬랙 #부적합 채널에서 직원이 보고하면, AI가 자동으로 구조화하여 MES에 등록합니다.</p>
    <div class="flow">
      <div class="flow-box" style="border-color:#1565C0"><strong style="color:#1565C0">① 직원 보고</strong><br><span style="font-size:12px">#부적합에 자유 형식 작성</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#E65100"><strong style="color:#E65100">② AI 파싱</strong><br><span style="font-size:12px">장비·모델·증상 자동 분류</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#2E7D32"><strong style="color:#2E7D32">③ MES 등록</strong><br><span style="font-size:12px">부적합 테이블 자동 INSERT</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#CC0000"><strong style="color:#CC0000">④ 알림</strong><br><span style="font-size:12px">담당자 자동 알림</span></div>
    </div>
    <div class="box green">
      <h4>도입 효과</h4>
    </div>
    <table>
      <tr><th>항목</th><th>기존</th><th>AI 적용 후</th><th>개선율</th></tr>
      <tr><td>등록 소요시간</td><td>5~10분 (수동)</td><td><strong>30초 이내 (자동)</strong></td><td><span class="hl">95% 단축</span></td></tr>
      <tr><td>누락률</td><td>20~30% 추정</td><td><strong>0% (전수 등록)</strong></td><td><span class="hl">100% 개선</span></td></tr>
      <tr><td>데이터 표준화</td><td>담당자별 상이</td><td><strong>100% 표준 양식</strong></td><td><span class="hl">완전 표준화</span></td></tr>
      <tr><td>축적 데이터</td><td>684건 (부적합 보고서)</td><td><strong>지속 자동 누적</strong></td><td>실시간 축적</td></tr>
    </table>
  </div>
  <div class="slide-num">05</div>
</div>"""

new_slide6 = """<!-- SLIDE 6: CS 응답 품질 개선 파이프라인 -->
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">CS 응답 품질 개선 파이프라인</div></div>
  <div class="s-body">
    <p>엔지니어 피드백을 통해 <strong class="hl">응답할수록 정확해지는 자기학습 구조</strong>를 구현합니다.</p>
    <div class="flow">
      <div class="flow-box" style="border-color:#1565C0"><strong style="color:#1565C0">① 질문 접수</strong><br><span style="font-size:11px">#cs 채널 고객/직원 질문</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#7B1FA2"><strong style="color:#7B1FA2">② AI 응답</strong><br><span style="font-size:11px">벡터DB RAG 기반 생성</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#E65100"><strong style="color:#E65100">③ 엔지니어 검증</strong><br><span style="font-size:11px">정확/부정확 피드백</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#2E7D32"><strong style="color:#2E7D32">④ 세션 기록</strong><br><span style="font-size:11px">JSONL 보정 데이터 축적</span></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box" style="border-color:#CC0000"><strong style="color:#CC0000">⑤ 재임베딩</strong><br><span style="font-size:11px">검증된 응답 벡터DB 저장</span></div>
    </div>
    <div class="g2">
      <div class="box blue">
        <h4>자기학습 사이클</h4>
        <p>• 부정확 응답 → 엔지니어가 보정된 정답 입력</p>
        <p>• 보정 세션을 <strong>cs-sessions.jsonl</strong>에 기록</p>
        <p>• 검증된 세션만 선별 재임베딩 → 벡터DB 갱신</p>
        <p>• 다음 유사 질문 시 <strong class="hl">검증된 답변 우선 검색</strong></p>
      </div>
      <div class="box green">
        <h4>핵심 효과</h4>
        <p>• 운영할수록 <strong>응답 정확도 지속 향상</strong></p>
        <p>• 엔지니어 검증 데이터만 학습 — <strong>품질 보장</strong></p>
        <p>• JSONL 기반 전수 추적 — 언제/누가/무엇을 보정했는지 기록</p>
        <p>• 반복 패턴 자동 추출 → <strong>스킬화</strong> 가능</p>
      </div>
    </div>
  </div>
  <div class="slide-num">05</div>
</div>"""

if old_slide6 in html:
    html = html.replace(old_slide6, new_slide6)
    print("Slide 6 replaced successfully")
else:
    print("ERROR: old slide 6 not found!")
    # Debug
    idx = html.find('부적합 자동 등록 프로세스')
    if idx >= 0:
        print(f"Found title at index {idx}")
        print(repr(html[idx-200:idx+200]))

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
