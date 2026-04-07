import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Read base64 images
b64 = {}
for name in ['image1.jpeg', 'image2.jpeg', 'image5.jpeg']:
    with open(f'C:/MES/wta-agents/reports/MAX/template-images/{name}.b64', 'r') as f:
        b64[name] = f.read().strip()

cover_bg = f"data:image/jpeg;base64,{b64['image2.jpeg']}"
content_bg = f"data:image/jpeg;base64,{b64['image1.jpeg']}"
ending_bg = f"data:image/jpeg;base64,{b64['image5.jpeg']}"

html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Docs팀 매뉴얼 RAG AI 성과 보고</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'맑은 고딕','Malgun Gothic',-apple-system,sans-serif;background:#e8e8e8;color:#333}}
.slide-wrap{{max-width:1100px;margin:0 auto;padding:20px}}

.slide{{background:#fff;border-radius:4px;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.15);display:flex;flex-direction:column;aspect-ratio:16/9;margin-bottom:24px}}
.slide-num{{position:absolute;bottom:10px;right:28px;font-size:11px;color:#999;font-weight:600}}

.cover{{background:url('{cover_bg}') center/cover no-repeat;justify-content:center;align-items:flex-start;padding:80px;overflow:hidden}}
.cover h1{{font-size:34px;font-weight:700;color:#333;line-height:1.3;margin-bottom:10px}}
.cover .sub{{font-size:18px;color:#666;margin-bottom:28px;line-height:1.5}}
.cover .meta{{font-size:14px;color:#888;line-height:1.8}}

.content-slide{{background:url('{content_bg}') center/cover no-repeat;padding:0;overflow:hidden}}
.content-slide .s-header{{height:64px;display:flex;align-items:center;padding-left:40px;flex-shrink:0}}
.content-slide .s-title{{font-size:25px;font-weight:700;color:#000;margin:11px 0 0 0;padding-left:calc(2em + 25px)}}
.content-slide .s-body{{padding:32px 44px 28px 44px;flex:1;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;gap:12px}}
.content-slide .s-body>*{{flex-shrink:0}}

.ending{{background:url('{ending_bg}') center/cover no-repeat;justify-content:center;align-items:center;text-align:center;padding:80px;overflow:hidden}}

.slide p{{font-size:16px;line-height:1.7;color:#444;margin-bottom:6px}}
.slide li{{font-size:14px;line-height:1.7;color:#444;margin-bottom:2px}}
.slide strong{{color:#222;font-weight:700}}
.hl{{color:#CC0000;font-weight:700}}

.box{{background:#f8f8f8;border:1px solid #e0e0e0;border-radius:8px;padding:14px 18px;margin:0}}
.box.red{{border-left:4px solid #CC0000}}
.box.green{{border-left:4px solid #2E7D32}}
.box.blue{{border-left:4px solid #1565C0}}
.box.orange{{border-left:4px solid #E65100}}
.box h4{{font-size:15px;font-weight:700;margin-bottom:6px;color:#222}}
.box p{{font-size:13px;margin-bottom:2px;line-height:1.6}}
.box ul{{padding-left:18px;margin-top:4px}}
.box li{{font-size:13px;line-height:1.6}}

.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:0}}
.g4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin:0}}

.big{{text-align:center;padding:10px 8px;background:#f8f8f8;border-radius:8px;border:1px solid #e0e0e0}}
.big .num{{font-size:32px;font-weight:900;line-height:1}}
.big .num.red{{color:#CC0000}}
.big .num.green{{color:#2E7D32}}
.big .num.blue{{color:#1565C0}}
.big .num.orange{{color:#E65100}}
.big .label{{font-size:11px;color:#666;margin-top:4px;font-weight:600}}
.big .sub{{font-size:10px;color:#999;margin-top:1px}}

.vs{{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;margin:0}}
.vs-col{{padding:14px 16px}}
.vs-col.bad{{background:#FFF5F5;border-right:1px solid #e0e0e0}}
.vs-col.good{{background:#F0FFF0}}
.vs-col h5{{font-size:14px;font-weight:700;margin-bottom:6px}}
.vs-col.bad h5{{color:#C62828}}
.vs-col.good h5{{color:#2E7D32}}
.vs-col ul{{padding-left:16px}}
.vs-col li{{font-size:13px;line-height:1.65;margin-bottom:1px}}

.flow{{display:flex;align-items:center;justify-content:space-between;gap:6px;margin:0}}
.flow-node{{flex:1;background:#fff;border:2px solid #CC0000;border-radius:8px;padding:8px 6px;text-align:center}}
.flow-node .t{{font-size:12px;font-weight:700;color:#222;margin-bottom:2px}}
.flow-node .d{{font-size:10px;color:#888;line-height:1.4}}
.flow-arrow{{color:#CC0000;font-size:18px;font-weight:700}}

.title-line{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:0;padding-bottom:8px;border-bottom:2px solid #CC0000}}
.title-line .lead{{font-size:15px;color:#222;font-weight:700}}
.title-line .date{{font-size:11px;color:#888}}

.sample-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0}}
.sample-card{{background:#f8f8f8;border:1px solid #e0e0e0;border-radius:8px;padding:16px 18px;position:relative}}
.sample-card .badge{{position:absolute;top:10px;right:12px;font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px}}
.sample-card .badge.auto{{background:#E8F5E9;color:#2E7D32}}
.sample-card .type{{font-size:11px;color:#CC0000;font-weight:700;margin-bottom:4px}}
.sample-card h5{{font-size:14px;font-weight:700;color:#222;margin-bottom:6px}}
.sample-card p{{font-size:12px;color:#666;line-height:1.6;margin-bottom:2px}}
.sample-card .toc{{font-size:11px;color:#888;line-height:1.5;margin-top:4px;padding-left:14px}}

.ppt-bar{{max-width:1100px;margin:0 auto;padding:12px 20px 0;display:flex;justify-content:flex-end}}
.ppt-btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 18px;background:#CC0000;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none;font-family:inherit}}
.ppt-btn:hover{{background:#a00}}

.footer{{text-align:center;padding:16px;color:#999;font-size:10px}}
@media print{{.slide{{break-inside:avoid;page-break-inside:avoid;box-shadow:none}}.ppt-bar{{display:none}}}}
</style>
</head>
<body>

<div class="ppt-bar">
  <a class="ppt-btn" href="https://mes-wta.com/api/export/docs-rag-achievement-3p-pptx" download>PPT</a>
</div>

<div class="slide-wrap">

<!-- 표지 -->
<div class="slide cover">
  <h1>매뉴얼 RAG AI 구축 성과 보고</h1>
  <div class="sub">수작업 매뉴얼 관리에서 AI 자동 생성 · 의미 검색 체계로의 전환</div>
  <div class="meta">
    (주)윈텍오토메이션 생산관리팀 (AI운영팀)<br>
    2026년 4월 월간회의<br>
    CONFIDENTIAL
  </div>
  <div class="slide-num">01</div>
</div>

<!-- 1. 배경 + 전환 -->
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">추진 배경 & AS-IS / TO-BE 전환</div></div>
  <div class="s-body">
    <div class="title-line">
      <div class="lead">수작업 매뉴얼 관리 → AI 자동 생성 체계로 전환</div>
      <div class="date">2026-04 · (주)윈텍오토메이션 생산관리팀(AI운영팀)</div>
    </div>
    <p>장비 사용자 매뉴얼·안전 스티커·제품 데이터시트·CS 응대 기록을 <strong class="hl">담당자 개인이 수작업</strong>으로 관리해 왔으며, AI가 학습하여 <strong class="hl">자동 생성·의미 검색·다국어 대응</strong>하는 체계로 전환을 완료했습니다.</p>
    <div class="vs">
      <div class="vs-col bad">
        <h5>AS-IS (수작업 중심)</h5>
        <ul>
          <li>담당자 1명이 장비별 매뉴얼 직접 작성 — <strong>수일~수주</strong> 소요</li>
          <li>PDF·Word 파일 개인 PC/공유폴더 분산 저장, <strong>파일명</strong> 검색 의존</li>
          <li>부품 사양·품명 변경 시 <strong>수동 갱신</strong> 필요</li>
          <li>번역은 외주 또는 수작업, 영/중 매뉴얼 별도 관리</li>
          <li>CS 응대 시 엔지니어에게 <strong>재문의 → 회신 대기</strong></li>
          <li>담당자 편차·퇴사 시 개인 지식 소실</li>
        </ul>
      </div>
      <div class="vs-col good">
        <h5>TO-BE (RAG AI 체계)</h5>
        <ul>
          <li>유사 장비·부품 매뉴얼 기반 <strong>초안 즉시 자동 생성</strong></li>
          <li>PostgreSQL pgvector 중앙 저장, <strong>자연어 질의</strong> 가능</li>
          <li>한·영·중 <strong>동일 벡터 공간</strong> 통합 검색, 언어 변환 자동화</li>
          <li>슬랙 #cs 봇이 과거 이력 기반 <strong>1차 자동 답변</strong></li>
          <li>부품·사양 변경 시 신규 문서만 재임베딩 → <strong>일관성 유지</strong></li>
          <li>전 직원·해외법인·신입 사원 <strong>동일 수준 조회</strong></li>
        </ul>
      </div>
    </div>
    <div class="box red">
      <h4>전환 성과 요약</h4>
      <p>· 매뉴얼 작성·CS 응대 <strong class="hl">업무 리드타임 단축</strong>, 담당자 의존도 감소 · 직원 개인 경험 → <strong class="hl">회사 벡터 자산</strong>으로 축적, 다국어·해외법인 동시 대응</p>
    </div>
  </div>
  <div class="slide-num">02</div>
</div>

<!-- 2. RAG 구조 + 성과 핵심 -->
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">RAG 시스템 구조 & 핵심 성과</div></div>
  <div class="s-body">
    <div class="flow">
      <div class="flow-node"><div class="t">원문</div><div class="d">PDF·DOCX·HTML</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-node"><div class="t">Docling 파싱</div><div class="d">텍스트·표·이미지</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-node"><div class="t">청킹·벡터화</div><div class="d">Qwen3-Embedding-8B</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-node"><div class="t">pgvector</div><div class="d">PostgreSQL</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-node"><div class="t">AI 답변</div><div class="d">의미 검색+LLM</div></div>
    </div>
    <div class="g4">
      <div class="big"><div class="num red">1,482</div><div class="label">학습 문서</div><div class="sub">매뉴얼+CS 이력</div></div>
      <div class="big"><div class="num green">389K+</div><div class="label">벡터 청크</div><div class="sub">3개 테이블 합산</div></div>
      <div class="big"><div class="num blue">2,000</div><div class="label">임베딩 차원</div><div class="sub">멀티링궐 통일</div></div>
      <div class="big"><div class="num orange">91%</div><div class="label">임베딩 진행률</div><div class="sub">부품 매뉴얼</div></div>
    </div>
    <div class="g3">
      <div class="box green">
        <h4>부품 매뉴얼 (외부)</h4>
        <p>· 파싱 <strong class="hl">892 / 892</strong> 완료 (100%)</p>
        <p>· 임베딩 <strong>810 / 892</strong> (91%) — 265,635 청크</p>
        <p>· 로봇·서보·센서·HMI·PLC 8개 카테고리</p>
        <p>· 테이블: <strong>manual.documents</strong></p>
      </div>
      <div class="box green">
        <h4>CS 이력</h4>
        <p>· 임베딩 <strong class="hl">3,318 / 3,318</strong> 완료 (100%)</p>
        <p>· 슬랙 #cs 봇 실전 투입, 고객 질의 자동 매칭</p>
        <p>· 엔지니어 회신 초안 즉시 생성</p>
        <p>· 테이블: <strong>csagent.vector_embeddings</strong></p>
      </div>
      <div class="box orange">
        <h4>WTA 자체 매뉴얼</h4>
        <p>· 수집 <strong>590</strong> 완료, 파싱 <strong>321/590</strong> (54%)</p>
        <p>· 120,084 청크 확보, Docling 고품질 파서</p>
        <p>· 4~5월 내 파싱 100% 목표</p>
        <p>· 테이블: <strong>manual.wta_documents</strong></p>
      </div>
    </div>
    <p style="font-size:11px;color:#888;text-align:right;margin:0">인프라: PostgreSQL pgvector · 임베딩 Qwen3-Embedding-8B · 파서 Docling</p>
  </div>
  <div class="slide-num">03</div>
</div>

<!-- 3. 활용 + 향후 -->
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">실 업무 활용 & 향후 계획</div></div>
  <div class="s-body">
    <div class="g2">
      <div class="box red">
        <h4>현재 활용 중 (실운영)</h4>
        <ul>
          <li><strong>CS 자동 응대</strong> — 슬랙 #cs 봇이 고객 질의에 1차 답변, 엔지니어는 검수·보완만</li>
          <li><strong>매뉴얼 초안 생성</strong> — 유사 장비·부품 매뉴얼 기반 자동 작성 → 편집 후 릴리스</li>
          <li><strong>사내 지식 검색</strong> — 전 직원 자연어 질의, 신규 입사자 온보딩 단축</li>
          <li><strong>다국어 대응</strong> — 해외 7개국 60+ 고객사, 한·영·중 통합 검색</li>
          <li><strong>부품 사양 조회</strong> — 로봇·서보·센서·HMI·PLC 전 카테고리 즉시 확인</li>
        </ul>
      </div>
      <div class="box blue">
        <h4>향후 계획 (2026 2Q 로드맵)</h4>
        <ul>
          <li><strong>4월</strong>: 부품 매뉴얼 임베딩 100% 완료 (잔여 82개)</li>
          <li><strong>4~5월</strong>: WTA 자체 매뉴얼 파싱 100% (321→590개)</li>
          <li><strong>5월</strong>: QC 체크리스트 벡터화 착수</li>
          <li><strong>5월</strong>: 안전 스티커·경고 라벨 표준화 템플릿 학습</li>
          <li><strong>6월</strong>: Confluence·Jira RAG 3단계 파이프라인 통합</li>
          <li><strong>6월</strong>: 매뉴얼 자동 생성 파이프라인 안정화</li>
        </ul>
      </div>
    </div>
    <div class="box orange">
      <h4>부서장 확인·승인 요청</h4>
      <p>· 임베딩 서버(Qwen3-Embedding-8B) <strong class="hl">이중화</strong> 필요성 검토 — 현재 단일 서버 의존</p>
      <p>· 장비 매뉴얼 AI 초안 → 최종 검수 프로세스 <strong class="hl">공식 워크플로우 확정</strong></p>
      <p>· QC 체크리스트 벡터화 범위 확정 — 출하검사 기준서 포함 여부</p>
    </div>
  </div>
  <div class="slide-num">04</div>
</div>

<!-- 4. 매뉴얼 견본 -->
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">실제 생성된 매뉴얼 견본</div></div>
  <div class="s-body">
    <p style="font-size:14px;color:#666;margin-bottom:8px">RAG 시스템으로 자동 파싱·구조화된 매뉴얼 사례 — 원문 PDF에서 텍스트·표·이미지를 추출하고 벡터 임베딩까지 완료된 문서</p>
    <div class="sample-grid">
      <div class="sample-card">
        <span class="badge auto">AI 자동 파싱</span>
        <div class="type">부품 매뉴얼 — 로봇</div>
        <h5>Mitsubishi RH-F 셋업 가이드 (KO)</h5>
        <p>106페이지, 이미지 15장 추출, 265,635 청크 중 포함</p>
        <div class="toc">· 설치 및 배선 · 원점 조정 · 좌표계 설정<br>· 안전 기능 · 보수 점검 · 에러 코드표</div>
      </div>
      <div class="sample-card">
        <span class="badge auto">AI 자동 파싱</span>
        <div class="type">부품 매뉴얼 — 센서</div>
        <h5>Keyence IL-030 통신 매뉴얼 (KO)</h5>
        <p>통신 프로토콜·배선도·파라미터 설정 자동 구조화</p>
        <div class="toc">· RS-232C 배선 · 명령어 일람<br>· 응답 포맷 · 에러 처리 · 연결 사례</div>
      </div>
      <div class="sample-card">
        <span class="badge auto">AI 자동 파싱</span>
        <div class="type">WTA 자체 매뉴얼 — 안전</div>
        <h5>PVD 로딩장비 리스크 어세스먼트</h5>
        <p>안전 진단 체크시트 172항목 + RA 평가표 6건 위험요인 구조화</p>
        <div class="toc">· 기계·전기 안전 체크 · 화재·폭발 대책<br>· 노동위생 · 리스크 S×P×F 평가</div>
      </div>
      <div class="sample-card">
        <span class="badge auto">AI 자동 생성</span>
        <div class="type">CS 이력 — 자동 답변</div>
        <h5>슬랙 #cs 봇 자동 응대 사례</h5>
        <p>3,318건 CS 이력 학습 기반, 고객 질의에 1차 답변 즉시 생성</p>
        <div class="toc">· 부품 사양 질의 → 스펙 즉시 제공<br>· 에러코드 → 원인·조치 자동 매칭<br>· 다국어(한·영·중) 질의 동시 대응</div>
      </div>
    </div>
    <div class="box green" style="margin-top:4px">
      <p style="font-size:13px"><strong>파싱 품질</strong>: Docling 엔진으로 표·수식·다단 레이아웃 정확 추출 | <strong>벡터 검색 정확도</strong>: cosine similarity 기반 Top-5 매칭, 기술 용어 정밀 대응</p>
    </div>
  </div>
  <div class="slide-num">05</div>
</div>

<!-- 엔딩 -->
<div class="slide ending"></div>

</div>

<div class="footer">(주)윈텍오토메이션 생산관리팀(AI운영팀) · 2026-04 · CONFIDENTIAL</div>

</body>
</html>'''

with open('C:/MES/wta-agents/reports/MAX/docs-rag-achievement-3p.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'저장 완료: {len(html):,} bytes')
print(f'base64 이미지 수: {html.count("data:image/jpeg;base64,")}')
