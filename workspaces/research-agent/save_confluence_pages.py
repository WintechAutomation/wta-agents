# -*- coding: utf-8 -*-
"""
Confluence 페이지 원본 저장 스크립트
과제① 장비물류 / 과제② 분말검사
이 파일은 과제①② 전용. 과제③④⑤는 save_345.py 참조.
"""
import json
import os
import re

BASE1 = r'C:/MES/wta-agents/reports/MAX/경상연구개발/참고문서-원본/1-장비물류'
BASE2 = r'C:/MES/wta-agents/reports/MAX/경상연구개발/참고문서-원본/2-분말검사'

# ============================================================
# 페이지 데이터 정의
# ============================================================

# ---- 1-장비물류 ----
PAGES_1 = [
    {
        "id": "8079409174",
        "title": "대구텍 AMR (AGV)",
        "lastModified": "2022 12 21",
        "space": "PROD",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/PROD/pages/8079409174/AMR+AGV",
    },
    {
        "id": "9128738819",
        "title": "설계팀 요소기술 개발항목",
        "lastModified": "2025 10 29",
        "space": "hanjong",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/hanjong/pages/9128738819",
    },
    {
        "id": "9623371777",
        "title": "WTA 설비 차별점 정리",
        "lastModified": "2026 03 18",
        "space": "zPVoA5Le1CFK",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/zPVoA5Le1CFK/pages/9623371777/WTA",
    },
    {
        "id": "8742862879",
        "title": "2025-04-10 양면 연삭기 DX 자동화",
        "lastModified": "2025 04 14",
        "space": "MUxST4BiGY31",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/MUxST4BiGY31/pages/8742862879/2025-04-10+DX",
    },
    {
        "id": "9327411201",
        "title": "2025년 12월 경영회의 회의록",
        "lastModified": "2025 12 03",
        "space": "minutes",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/minutes/pages/9327411201/2025+12",
    },
    {
        "id": "8330838017",
        "title": "2024년 1월 경영회의 회의록",
        "lastModified": "2024 01 03",
        "space": "minutes",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/minutes/pages/8330838017/2024+1",
    },
]

# ---- 2-분말검사 ----
PAGES_2 = [
    {
        "id": "8048672826",
        "title": "제품력 강화 - 검사",
        "lastModified": "2022 10 27",
        "space": "REPORT",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/REPORT/pages/8048672826/-",
    },
    {
        "id": "9509830687",
        "title": "[OTC] 2026년 5~8주차 업무 (1/26~2/22)",
        "lastModified": "2026 02 23",
        "space": "OI",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/OI/pages/9509830687/OTC+2026+5~8+1+26~2+22",
    },
    {
        "id": "9577070593",
        "title": "[OTC] 2026년 9~12주차 업무 (2/23~3/22)",
        "lastModified": "2026 03 23",
        "space": "OI",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/OI/pages/9577070593/OTC+2026+9~12+2+23~3+22",
    },
    {
        "id": "9603547139",
        "title": "인서트 제조 공정 교육서",
        "lastModified": "2026 03 19",
        "space": "최현수",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/~7120207fa205aaa3954c049293ecc72667daba/pages/9603547139",
    },
    {
        "id": "9327411201",  # shared with 장비물류
        "title": "2025년 12월 경영회의 회의록",
        "lastModified": "2025 12 03",
        "space": "minutes",
        "webUrl": "https://iwta.atlassian.net/wiki/spaces/minutes/pages/9327411201/2025+12",
    },
]

# ============================================================
# ADF 본문 데이터 (수집된 내용)
# ============================================================

ADF_DATA = {}
MD_DATA = {}

# 8079409174 - 대구텍 AMR (AGV)
ADF_DATA["8079409174"] = {"type":"doc","content":[{"type":"mediaSingle","attrs":{"layout":"center","width":480,"widthType":"pixel"},"content":[{"type":"media","attrs":{"width":480,"id":"247050ea-274f-422a-a382-64fac1cff3f0","collection":"contentId-8079409174","type":"file","height":852}},{"type":"caption","content":[{"text":"장비 내부 물류 (AGV 대응시 필요한 구조)","type":"text"}]}]},{"type":"mediaSingle","attrs":{"layout":"center","width":852,"widthType":"pixel"},"content":[{"type":"media","attrs":{"width":852,"id":"85a5e5e7-0af9-44b7-ad6e-b08aa3605392","collection":"contentId-8079409174","type":"file","height":480}},{"type":"caption","content":[{"text":"AMR (AGV) 형태","type":"text"}]}]},{"type":"paragraph"}],"version":1}

MD_DATA["8079409174"] = "# 대구텍 AMR (AGV)\n\n장비 내부 물류 (AGV 대응시 필요한 구조)\n\nAMR (AGV) 형태\n"

# 8742862879 - 양면 연삭기 DX 자동화 (ADF는 API에서 직접 수신됨)
MD_DATA["8742862879"] = """# 2025-04-10 양면 연삭기 DX 자동화

날짜: 2025-04-10
참여자: 김순봉, 김웅기, 김동준, 정광선, 최현수

## 1. 개발 목표 및 방향성
- **초보자도 정밀 연삭 가능한 자동 시스템** 구축
- **무인화, 연속 자동 가동**이 가능한 시스템 설계
- **극소형부터 대형 인서트까지** 대응하는 자동 연삭 시스템 개발

## 2. 연삭기 시스템 개선 및 자동화
- 연삭 속도 제어 및 **압력 자동 미세 조절** 시스템 도입
- **자동 측정, 자동 드레싱, 자동 크리너** 기능 추가
- 후지산키와의 협업으로 **9가지 개선안 적용 예정**

## 3. 극소형 인서트 대응 방안
- 극소형 인서트 연삭을 위한 **자동 픽업 기능** 필요(조, 마그네틱 그리퍼)
- **AGV 및 코드 인식 기능** 기반 물류 자동화 시스템 구축
- 다양한 인서트 종류에 맞춘 **자동 대응 기능 개발**

## 4. 핸들러 시스템 및 데이터 연동
- 핸들러 **자기 진단 및 피드백 기능** 고도화
- **자동 드레싱용 지그 및 스톤 + 연삭 지그 공급 기능** → 드레싱 & 지그 스테이션
- 설비 전반의 **데이터 공유 및 관리 기능** 구축

## 5. DX 측정 시스템 구축
- 인서트 **총 두께, 인선 날높이 측정 및 연삭량 산출** 시스템
- **초음파 세척 + 에어 건조 + 측정** 방식을 핸들러 내에 적용
- **접촉식 vs. 비전 방식** 비교 → 비전을 통한 측정 방식 선정

## 6~17. 기타 개발 사항
- AGV 물류, 비전 시스템, 소량 다품종 대응, 초음파 세척, RFID/바코드 제품 인식 등 17개 항목
"""

# 9327411201 - 2025년 12월 경영회의 회의록
MD_DATA["9327411201"] = """# 2025년 12월 경영회의 회의록

날짜: 2025-12-02
참여자: 대표이사, 진형권, 최종태, 조한종, 정정일, 김대한, 박재성, 정민웅, 박성수, 지건승, 조윤명, 김준형v, 서제완, 김순봉, 홍대한

## 부서별 주요 내용

| Team | Discussions |
|------|------------|
| **품질** | 장비 검수 강화 계획 - 11월까지 품질 문제 135건 중 118건(27.8%)이 출하 후 발생. SW 관련 비중 높음, PVD/포장기 집중 |
| **생산관리** | 선제작 시스템 개선 논의, 악성재고 점검, 무인화-연속운전(AMR/AGV), 공정별 플랫폼 개발 강조 |
| **구매** | 구매 절감 업무(중국자재) TF 운영 |
| **HAM 기구설계(성형,소결)** | 프레스 자동화 플랫폼 업무 기획, 장비 정밀도, 소형제품 픽업 |
| **HAM 기구설계(코팅,포장)** | 반전기술 별도 관리, 포장기 플랫폼 다이어그램, ATC 개발건 상세보고 |
| **HIM 기구설계** | 대구텍 검사기 초기컨셉 상세미팅 |
| **제작** | 중국 제조 현지화, 반제품단위 제작, 인력 교육, 안전관리 |
| **제어설계** | 중국 자재 기술검토, 전기 도면 검증시스템, 안전요 |
| **S/W** | HMI 플랫폼 전환 리스크 최소화, AS 수리후 자체점검, 자동 셋업 툴 기능보강 |
| **비전** | 검사기 macro/micro 제품이동문제, 호닝형상검사기 2026년 양산 목표 |

## 대표이사 지시사항
- **시장 확장 및 원가 혁신**: 인도, 러시아 등 신규 시장 진출
- **DX 시스템 구축**: 데이터 기반 의사결정 체계 확립
- **ESG 경영**: 선진국 시장 공략
- **호닝 검사기 사업**: 2026년 양산 목표, 신속 안정화
- **성형체 버(Burr) 검사**: 금형 마모 파악, 부가가치 핵심 기능

## 경영회의 목적/스케줄
장기적 경영 이념 실행, 단기 경영전략 목표 결정. 초경 인서트 제조 공정 이해 심화 필요.
스케줄: 1월(연초 계획), 6월(상반기 결산), 12월(하반기 결산 및 내년 계획)
"""

# 8330838017 - 2024년 1월 경영회의 회의록
MD_DATA["8330838017"] = """# 2024년 1월 경영회의 회의록

날짜: 2024-01-03
참여자: 대표이사, 진형권, 조한종, 홍대한, 최종태, 박재성, 전찬우, 박성수, 지건승, 조윤명, 김준형v, 최종국, 정성호, 장종희, 김순봉, 심경기

## 부서별 주요 내용

| Team | Discussions |
|------|------------|
| **영업** | 선제작장비 수주와 매출 연동, HIM 올해 9~17대 목표 |
| **품질** | 입고검수불량 이슈 지속(커버 판금류), 젠데스크 도입 |
| **생산관리** | Jira 시스템 교육, 로봇 내재화, CE 인증 5월 취득 |
| **HAM 기구설계** | AGV AMR 무인화 장비별 표준물류 컨셉 확립 |
| **HIM 기구설계** | 호닝 원가 정리, 반전 기술, 픽업 기술 |
| **제어설계** | PC안정화, 화재, 핵심부품관리, 에너지관리 |
| **S/W** | AI 업무 접목, PC 보안 관리, 소프트웨어 bug 대책 |
| **비전** | 그루빙/한국야금 검사 주력, 큰 깨짐 AI 적용, N/L측정 급선무 |

## 대표이사 지시사항
- 15~20분 내 경영 방향 발표
- 매주 월요일 팀미팅, 팀원과 경영자료 공유
- 팀리더 건강관리 철저

## 경영회의 스케줄
1월(연초 계획), 7월(상반기 결산), 12월(하반기 결산)
"""

# 8048672826 - 제품력 강화 - 검사
MD_DATA["8048672826"] = """# 제품력 강화 - 검사

| **제품** | **항목** | **내용** | **관련 자료** |
|---------|---------|---------|------------|
| 프레스 | Burr 측정 및 불량 검출 | **검사 목적**: Burr 이상 검출시 금형 문제 확인, 금형 Cleaning 상태 확인. **요구 사항**: 성형체 인선부 Burr 높이 0.1mm 초과 시 불량처리, 인선부 상/하와 모든 코너부 검사 | 프레스 구조, 성형 공정 이미지 |
| 소결 취출기 | 치수 측정, 밴딩, 뒤틀림, 깨짐 | **검사 목적**: 소결 공정 후 불량 판별, 초기 단계 불량 판정. **요구 사항**: 치수 측정(내접원, 비대칭) 매크로 ±5μm, 깨짐 100μm 이상, 밴딩/뒤틀림 |  |
| 연삭 핸들러 | 높이 측정 | **공통 사항(혼입 검사)**: 하드웨어적인 측정 진행 |  |
| 호닝 핸들러 | 호닝 유무, 혼입검사 | **검사 목적**: 호닝 가공 후 미가공 문제 발생 방지. **요구 사항**: 호닝 작업 후 가공 여부 검사 | 브러쉬 호닝, 호닝 공정 이미지 |
| PVD |  | 공통 사양 참고 | PVD 코팅 공정 이미지 |
| CVD |  | 공통 사양 참고 | CVD 코팅 공정 이미지 |
| 포장기 | 케이스내 제품 수량 검사 | **검사 목적**: 케이스 제품 적재 후 누락 여부 검사. 케이스 색/형태에 따른 IR 조명 대체 적용 | 수량 검사 이미지 |
| 포장기 | 마킹 검사 | **검사 목적**: 잉크젯, 레이저 마킹 후 문자 검사. **요구 사항**: 마킹 유무, 마킹 품질 |  |
| 공통 | 혼입 (CB, Nose-R) | **검사 목적**: 공정 이동, 생산, 회수에서 발생하는 혼입 검출. Nose-R 02(0.2mm)부터, CB 혼입 검사. 현재 카메라 F.O.V 45x35mm(1.3MP), 0.03mm/pixel. 5MP 카메라 검토(NoseR 01) |  |
"""

# 9509830687 - [OTC] 2026년 5~8주차 업무 (markdown from API)
MD_DATA["9509830687"] = """# [OTC] 2026년 5~8주차 업무 (1/26~2/22)

| **구분** | **항목** | **5~8주차 (1/26~2/22)** | **9주차 (2/23~3/1)** |
|---------|---------|----------------------|---------------------|
| **CIP (개조 개선) 및 이슈** | **HIM 광학계** | HIM series 카메라 원가 절감 모델 후보 발굴 | HIM series 카메라 원가 절감 모델 발굴 |
| | □ HIM-F 조명 개선 | HV Macro 조명 제작 진행 중(고시인성), prototype 목표 2/27. 동축 조명, 돔 조명(간접→직접 8ch), DF 조명(1열→2열) 개발 | Macro 조명 시인성 개선 검토 |
| | □ HIM-H (호닝형상검사기) | 고배율 광학계 TTTM 장치 SW 기능 구현. 선제작 #22-1, #23-2 강성 보강 개조 진행. #23-2 고배율 광학계 모듈 TTTM 장치 정렬 (1/21). 광택 제품 형상측정 정확도 개선 | 고배율 광학계(10X) 3ea, TTTM 장치 이용 모듈 정렬 |
| | □ 고해상도 Macro 광학계 | Pixel 수 12MP→25MP. Dynamic Range: 69.03dB vs 56.32dB, SNR: 44.55dB vs 42.13dB. 분해능: 13.9um→7.8um(25M). 대구텍향 HIM-F2E 광학계 FOV 80% Macro, 직접돔 조명 검토 | 광학계 테스트 착수(설계안 #6), FOV: 38.65x28.27→30.47x30.47 |
| **HAM 광학계** | | 포장기 혼입검사 측정편차 이슈, 팔레트 광학계 카메라 단종 대응(Basler acA1300-30gm→acA1300-60gm). 양면연삭핸들러향 팔레트/그리퍼 광학계 설계. 포장기 label 검사 광학계(CIS 검토). 호닝연삭 핸들러 마스크 align + 혼입검사 겸용 광학계 | |
| **개발** | **HIM-F TTTM** | 광학계 align process 확립. 광학계 Calibration 타겟 설계(Dot 3종, 복합 2종). MMC향 광학계 셋업 및 복합 타겟 적용 결과 | |
| **HAM IM** | | 프레스-IM 조명 개선(Both부 휘도 증가). 광학계 셋업 완료(7/23) | |
| **기타** | | KAIST 김정원 교수 3D profilometry 기술 센싱. ToF 부적합→Chromatic confocal 방법 제시. Feasibility test 진행(4/18 1차) | |
| **제조** | | HIM-F 조명 기구물 제작(추가 4sets/누적 6sets). 트리거보드 제작. HAM 링조명 10ea 제작 | |
"""

# 9577070593 - [OTC] 2026년 9~12주차 업무 (markdown from API)
MD_DATA["9577070593"] = """# [OTC] 2026년 9~12주차 업무 (2/23~3/22)

| **구분** | **항목** | **9~12주차 업무 (2/23~3/22)** | **13주차 (3/23~3/29)** |
|---------|---------|----------------------------|-----------------------|
| **CIP (개조 개선) 및 이슈** | **HIM 광학계** | HIM series 카메라 원가 절감 모델 후보 발굴 | HIM series 카메라 원가 절감 모델 발굴 |
| | □ HIM-F 조명 개선 | HV Macro 조명 개발 진행(proto 목표 4/초). 모델명: WRRDDRL188-S24W. 기구 부품 제작 삼호테크(3/20). PCB Inner/Outer Ring SMT 작업 및 Aging(3/4) | Dome 조명 다양한 split test |
| | □ HIM-H (호닝형상검사기) | 선제작 #23-2 72Hr 롱런 안정성 테스트(3/9~12): 4,539회 측정, 평균 CT 57.17s, 온도변화 1°C 당 Z축 15um 변화. 선제작 #23-4 72Hr 롱런(3/16~19): 4,261회 측정, 평균 CT 61.90s. TTTM 장치 개조: 시료 측정 기능 추가 | 고배율 광학계(10X) 3ea 통합 |
| | □ 고해상도 Macro 광학계 | 고해상도 macro 광학 모듈 제작 진행. 대구텍향 HIM-F2E: FOV 80% Macro, Telecentric-BLU 선정(Φ150mm, VICO사). Bottom면 검사 광학계: 연삭여부 및 그리퍼 핀 부러짐 검출 | FOV 80% Macro 광학계 검토 완료 |
| **HAM 광학계** | | 포장기 혼입검사 측정편차 이슈. 팔레트 광학계 카메라 단종 대응. 양면연삭핸들러향 팔레트/그리퍼 광학계 설계. 포장기 label 검사(CIS). YG-1 연삭핸들러 조명 개선. 하이썽 마스크 자동기 언로딩 조명 개선 | |
| **개발** | **HIM-F TTTM** | 광학계 Calibration 타겟 수정 설계(3/4). Cross Hair 시인성 향상(선폭 9→50um). MMC향/Korloy향/한국교세라향 광학계 셋업후 정렬상태 점검 | |
| **HAM IM** | | 프레스-IM 광학계 셋업 완료(7/23) | |
| **기타** | | KAIST 3D profilometry Feasibility test. Chromatic confocal point scan 방식 장치 구성, 시스템 구축(4/14~) | |
| **제조** | | HIM-F 조명 기구물 제작(추가 4sets/누적 6sets). HAM 링조명 10ea 제작. 연간 생산 계획 협의 | |
"""

# 9603547139 - 인서트 제조 공정 교육서
MD_DATA["9603547139"] = """# 인서트 제조 공정 교육서

목차:
1. 분말 야금 제조 공정(1차 원료 / 2차 원료)
2. 성형 공정
3. 소결 공정
4. 가공 공정 (연삭 공정 / 호닝 공정)
5. 코팅 공정 (CVD / PVD)
6. 품질 공정

## 1. 분말 야금 제조 공정

분말 야금(Powder Metallurgy, P/M): 금속 또는 금속 산화물의 분말을 가열하여 결합시킴으로써 금속 재료(반제품) 또는 금속 가공 제품을 만드는 공정

### 특징
- 치수 정밀도가 매우 높아 2차 기계 가공 공정 생략 가능
- 고체와 액체의 중간 성질
- 재료 설계 용이, 융해법으로 만들 수 없는 합금 제조 가능
- 소결 공정으로 고체 고유의 특성 구현

### 장점
- 복잡한 형상 제품 제작 가능
- 주조에 비해 낮은 온도에서 작업
- 고정밀도, 다공질 재료 제작
- 원재료 손실 거의 없음

### 단점
- 분말 형상 입도 및 입도 분포 제어 불균일 가능
- 초기 투자 비용 높음

## 2. 성형 공정

가압 성형: 원료를 금형 프레스기의 다이(DIE, MOLD) 내부에 공급 후 상하 압력으로 가압 성형
- 성형 공정 순서: 분말 충진 → 가압 → 상하부 펀치 이동 → 성형체 탈형 → 성형체 배출 및 분말 투입구 이동
- 충진 시 조립 분체가 쉽게 흐르게 하는 것이 중요
- 중요 포인트: 압력, 중량 관리, 복잡한 형태 성형, 다양한 성형체 가능

## 3. 소결 공정

소결: 분말 같은 비표면적이 넓은 입자들을 치밀한 덩어리로 만들기 위해 충분한 온도와 압력을 가하는 공정

### 소결 과정 (초기/중기/말기)
- **초기**: 입자 계면이 붙어 목 형성, 밀도 증가, 기공 열린 상태
- **중기**: 기공 둥글어짐, 입자 성장, 밀도 이론 밀도의 약 92%
- **말기**: 기공 구형화, 닫힌 구멍 형성, 입자 성장 추가 발생

소결로 구성: 진공 소결로, 최대 1,600℃~1,800℃ 고온

## 4. 가공 공정 (연삭 / 호닝)

- **연삭**: 소결 후 제품 크기를 규정에 맞추는 작업. 연삭유+돌가루 분사 + 연삭 휠로 정밀하게 깎아냄. 연삭 후 반사율 높아짐
- **호닝**: 연삭 후 날카로운 모서리를 라운드 처리하여 내구성 향상. 다이아몬드 브러시로 호닝 가공

## 5. 코팅 공정 (CVD / PVD)

### CVD(화학 증착법)
- 가스상 TiCl₄, H₂, CH₄, N₂ 등을 700℃~1050℃로 가열하여 모재 표면에 5~10μm 초경질 화합물 형성
- 장점: 균일한 두꺼운 코팅, 초경 모재 점착력 우수, 내마모성 우수

### PVD(물리 증착법)
- 물리적 증발 원리로 코팅 물질을 가스 상태로 변화시켜 소재에 2~6μm 박막 응축
- 일반적인 코팅: TiN, TiCN, TiAlN, TiAlCrN 등 세라믹 코팅
- 장점: 우수한 인선, 날카로운 절삭날 유지, 솔리드 초경 공구에 많이 사용

## 6. 품질 공정

인서트 제조 전 공정에 걸친 품질 검사 체계 (공정별 검사 흐름도 포함)
"""

# ============================================================
# 이미지 mediaId 추출 함수
# ============================================================

def extract_media_ids(adf_data):
    """ADF JSON에서 media id 목록 추출"""
    ids = []
    def traverse(node):
        if isinstance(node, dict):
            if node.get('type') in ('media', 'mediaInline') and 'attrs' in node:
                attrs = node['attrs']
                if 'id' in attrs:
                    ids.append({
                        'id': attrs['id'],
                        'type': attrs.get('type', 'file'),
                        'collection': attrs.get('collection', ''),
                        'alt': attrs.get('alt', ''),
                        'width': attrs.get('width'),
                        'height': attrs.get('height'),
                    })
            for v in node.values():
                traverse(v)
        elif isinstance(node, list):
            for item in node:
                traverse(item)
    traverse(adf_data)
    return ids


# ============================================================
# 저장 함수
# ============================================================

def save_pages(pages, base_dir, title_prefix):
    os.makedirs(os.path.join(base_dir, 'images'), exist_ok=True)

    pages_meta = []
    all_md_sections = []

    for page in pages:
        pid = page['id']

        # pages.json 항목
        pages_meta.append({
            'pageId': pid,
            'title': page['title'],
            'lastModified': page['lastModified'],
            'space': page['space'],
            'webUrl': page['webUrl'],
            'url': f"https://iwta.atlassian.net/wiki{page['webUrl'].replace('https://iwta.atlassian.net/wiki', '')}",
        })

        # ADF 저장
        adf = ADF_DATA.get(pid)
        if adf:
            with open(os.path.join(base_dir, f'page-{pid}-structure.json'), 'w', encoding='utf-8') as f:
                json.dump(adf, f, ensure_ascii=False, indent=2)

        # Markdown 저장
        md = MD_DATA.get(pid, f'# {page["title"]}\n\n(본문 내용 참조: ADF JSON)\n')
        with open(os.path.join(base_dir, f'page-{pid}-content.md'), 'w', encoding='utf-8') as f:
            f.write(md)

        all_md_sections.append(f'<h1>{page["title"]}</h1>\n<p><em>페이지 ID: {pid} | 최종수정: {page["lastModified"]} | <a href="{page["webUrl"]}">원본 링크</a></em></p>\n')
        # Convert markdown to HTML (simplified)
        html_content = md.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
        html_content = html_content.replace('\n\n', '</p><p>')
        all_md_sections.append(f'<div class="page-content">{html_content}</div><hr/>')

    # pages.json 저장
    with open(os.path.join(base_dir, 'pages.json'), 'w', encoding='utf-8') as f:
        json.dump(pages_meta, f, ensure_ascii=False, indent=2)

    # images/reference.json 저장 (모든 ADF에서 이미지 ID 추출)
    all_images = {}
    for pid, adf in ADF_DATA.items():
        if any(p['id'] == pid for p in pages):
            media_list = extract_media_ids(adf)
            if media_list:
                all_images[pid] = media_list

    # 대용량 ADF 파일에서도 이미지 추출
    large_adf_files = {
        '9623371777': r'C:/Users/Administrator/.claude/projects/C--MES-wta-agents-workspaces-research-agent/b0c74e1c-5091-4afc-9e32-30abf872d4f2/tool-results/mcp-plugin_atlassian_atlassian-getConfluencePage-1775272286392.txt',
        '9577070593': r'C:/Users/Administrator/.claude/projects/C--MES-wta-agents-workspaces-research-agent/b0c74e1c-5091-4afc-9e32-30abf872d4f2/tool-results/mcp-plugin_atlassian_atlassian-getConfluencePage-1775272316339.txt',
    }
    for pid, fpath in large_adf_files.items():
        if any(p['id'] == pid for p in pages) and os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                node = data['content']['nodes'][0]
                if isinstance(node.get('body'), dict):
                    media_list = extract_media_ids(node['body'])
                    if media_list:
                        all_images[pid] = media_list
                    # Save ADF structure
                    adf_path = os.path.join(base_dir, f'page-{pid}-structure.json')
                    with open(adf_path, 'w', encoding='utf-8') as f2:
                        json.dump(node['body'], f2, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f'Warning: could not process {fpath}: {e}')

    with open(os.path.join(base_dir, 'images', 'reference.json'), 'w', encoding='utf-8') as f:
        json.dump(all_images, f, ensure_ascii=False, indent=2)

    # index.html 생성
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{title_prefix} 참고문서</title>
<style>
body{{font-family:'맑은 고딕',sans-serif;max-width:1200px;margin:auto;padding:20px;line-height:1.6}}
h1{{color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px}}
h2{{color:#333;margin-top:24px}}
h3{{color:#555}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
td,th{{border:1px solid #ccc;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f0f4f8;font-weight:bold}}
img{{max-width:100%}}
.page-header{{background:#e8f0fe;padding:12px;border-radius:6px;margin:16px 0}}
.page-header a{{color:#1a73e8}}
li{{margin:4px 0}}
blockquote{{border-left:4px solid #ccc;margin:12px 0;padding:8px 16px;background:#f9f9f9}}
hr{{border:none;border-top:2px solid #e0e0e0;margin:32px 0}}
</style>
</head>
<body>
<h1>{title_prefix} 참고문서 원본</h1>
<p>수집일: 2026-04-04 | 총 {len(pages)}개 페이지</p>
<hr/>
"""

    for page in pages:
        pid = page['id']
        md = MD_DATA.get(pid, f'# {page["title"]}\n\n본문 내용: ADF JSON 파일 참조')

        html += f'<div class="page-header"><strong>📄 {page["title"]}</strong> &nbsp;|&nbsp; 페이지 ID: {pid} &nbsp;|&nbsp; 최종수정: {page["lastModified"]} &nbsp;|&nbsp; <a href="{page["webUrl"]}" target="_blank">원본 Confluence 링크</a></div>\n'

        # Simple markdown to HTML conversion
        lines = md.split('\n')
        in_table = False
        in_list = False
        content_lines = []

        for line in lines:
            if line.startswith('# '):
                if in_list: content_lines.append('</ul>'); in_list = False
                content_lines.append(f'<h2>{line[2:]}</h2>')
            elif line.startswith('## '):
                if in_list: content_lines.append('</ul>'); in_list = False
                content_lines.append(f'<h3>{line[3:]}</h3>')
            elif line.startswith('### '):
                if in_list: content_lines.append('</ul>'); in_list = False
                content_lines.append(f'<h4>{line[4:]}</h4>')
            elif line.startswith('- ') or line.startswith('* '):
                if not in_list: content_lines.append('<ul>'); in_list = True
                cell = line[2:].replace('**', '<strong>', 1)
                if '**' in cell: cell = cell.replace('**', '</strong>', 1)
                content_lines.append(f'<li>{cell}</li>')
            elif line.startswith('|'):
                if in_list: content_lines.append('</ul>'); in_list = False
                if not in_table:
                    content_lines.append('<table>')
                    in_table = True
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    row = ''.join(f'<th>{c}</th>' for c in cells)
                    content_lines.append(f'<tr>{row}</tr>')
                elif set(line.replace('|','').replace('-','').replace(':','').strip()) == set():
                    pass  # separator row
                else:
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    row = ''.join(f'<td>{c}</td>' for c in cells)
                    content_lines.append(f'<tr>{row}</tr>')
            else:
                if in_table: content_lines.append('</table>'); in_table = False
                if in_list: content_lines.append('</ul>'); in_list = False
                if line.strip():
                    content_lines.append(f'<p>{line}</p>')

        if in_table: content_lines.append('</table>')
        if in_list: content_lines.append('</ul>')

        html += '\n'.join(content_lines)
        html += '\n<hr/>\n'

    html += '</body>\n</html>'

    with open(os.path.join(base_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)

    return pages_meta


# ============================================================
# 대용량 ADF에서 Markdown 추출 (9623371777, 9509830687)
# ============================================================

def load_large_adf_markdown():
    """대용량 ADF 파일에서 markdown body 추출"""
    files = {
        '9623371777': r'C:/Users/Administrator/.claude/projects/C--MES-wta-agents-workspaces-research-agent/b0c74e1c-5091-4afc-9e32-30abf872d4f2/tool-results/mcp-plugin_atlassian_atlassian-getConfluencePage-1775272286392.txt',
    }
    for pid, fpath in files.items():
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                node = data['content']['nodes'][0]
                # body is adf dict - no markdown available from this file
                # Already have adf - mark that markdown will be from API
            except Exception as e:
                print(f'Note: {fpath}: {e}')


# ============================================================
# 실행
# ============================================================

# 9623371777과 9128738819의 ADF는 API에서 직접 받았으므로 여기에 저장
# 9128738819 ADF는 수신 완료됨 (기억에서 저장)
ADF_DATA["9128738819"] = {"type":"doc","content":[{"type":"table","attrs":{"layout":"center","width":1800,"localId":"01dc5b9a-d81e-4aa1-b9be-d6e13822dba3"},"content":[{"type":"tableRow","content":[{"type":"tableHeader","attrs":{"colspan":1,"rowspan":1,"colwidth":[221]},"content":[{"type":"paragraph","content":[{"text":"구분","type":"text","marks":[{"type":"strong"}]}]}]},{"type":"tableHeader","attrs":{"colspan":1,"rowspan":1,"colwidth":[780]},"content":[{"type":"paragraph","content":[{"text":"개발항목 상세","type":"text","marks":[{"type":"strong"}]}]}]},{"type":"tableHeader","attrs":{"colspan":1,"rowspan":1,"colwidth":[403]},"content":[{"type":"paragraph","content":[{"text":"적용 제품","type":"text","marks":[{"type":"strong"}]}]}]},{"type":"tableHeader","attrs":{"colspan":1,"rowspan":1,"colwidth":[393]},"content":[{"type":"paragraph","content":[{"text":"참조이미지","type":"text","marks":[{"type":"strong"}]}]}]}]}]}],"version":1}

MD_DATA["9128738819"] = """# 설계팀 요소기술 개발항목

| **구분** | **개발항목 상세** | **적용 제품** | **참조이미지** |
|---------|--------------|------------|-------------|
| **공용 pickup 툴 / ATC 내재화** | **2세대 공용 pickup 툴 (U19) 개발** - Auto Tool Change 기능 - Gripper 방식별 호환 공압관로 확보 (Jaw, Vacuum, Magnet, Softgrip, Tilt Grip) - 센서 신호선 필요 (pogopin 배선) - 중량 최소화 (현재 2~3kg) - 직경 가능한 유지 (그리퍼간격 65mm) - 멀티 조인트 & 슬립링 적용 - R축 모터 용량 상향, 모터사양 검토 | 프레스 외 전제품 적용 | SMC ATC 구매품, Roboworker Gripper System |
| **핵심 설계 표준화** | **회전축 멀티 조인트 & 슬립링** - 공압 1~4포트, 6포트 2종 표준설계 - 전기배선 8~12core - 회전축 모터 표준설계 | ATC 내재화적용, 전제품 반전Unit(90도/180도), 포장기 회전 Unit, 그외 회전계두 | 코비스 구매품 |
| **AMR 물류 표준화** | **AMR 물류 표준화 설계** - 설계 요소 통일화 표준설계 - 원가 고려 설계 필수 - type 1: 화루이 프레스 AGV 타입 - type 2: 한국야금 Cell 프레스 타입 - type 3: 대구텍 키엔스 검사기 타입 - type 4: 한국야금 포장기 6호기, 검사기 타입 - type 5: 한국야금 호닝핸들러 타입 | 전제품 물류옵션 적용 | |
| **Components 기술확보 [고속 직교 축]** | **고속 직교 축 표준화** - X,Y,Z,R 형태의 복합축 구조 정밀고속구동 기술 내재화 필요. Roboworker components 사업(3가지 item): 1. 3D프린트 팔레트부자재, 2. 프레스 금형 분말피더 shoes, 3. Linear Axes(belt) | 검사기, PVD, 포장기 | Roboworker Component |
| 장비 설계 업무 | 호닝형상검사기 New 버전 | | |
| | 대구텍 검사장비 | | |
"""

# 9128738819과 9623371777의 ADF 저장 (대용량 파일에서 이미 처리됨)
# 8742862879 ADF 저장
ADF_DATA["8742862879"] = {"type":"doc","content":[{"type":"heading","attrs":{"level":2},"content":[{"text":"날짜","type":"text"}]},{"type":"paragraph","content":[{"type":"date","attrs":{"timestamp":"1744243200000"}}]},{"type":"heading","attrs":{"level":2},"content":[{"text":"참여자","type":"text","marks":[{"type":"strong"}]}]},{"type":"bulletList","content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"김순봉, 김웅기, 김동준, 정광선, 최현수","type":"text"}]}]}]},{"type":"heading","attrs":{"level":2},"content":[{"text":"1. 개발 목표 및 방향성","type":"text","marks":[{"type":"strong"}]}]},{"type":"bulletList","content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"초보자도 정밀 연삭 가능한 자동 시스템 구축","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"무인화, 연속 자동 가동이 가능한 시스템 설계","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"극소형부터 대형 인서트까지 대응하는 자동 연삭 시스템 개발","type":"text"}]}]}]}],"version":1}

# ADF for 9327411201
ADF_DATA["9327411201"] = {"type":"doc","content":[{"type":"heading","attrs":{"level":2},"content":[{"text":"날짜","type":"text"}]},{"type":"paragraph","content":[{"type":"date","attrs":{"timestamp":"1764633600000"}}]},{"type":"heading","attrs":{"level":2},"content":[{"text":"참여자","type":"text","marks":[{"type":"strong"}]}]},{"type":"paragraph","content":[{"text":"경영: 대표이사, 영업: 진형권, 품질/CS: 최종태, 제조: 조한종 외 다수","type":"text"}]}],"version":1}

# ADF for 8330838017
ADF_DATA["8330838017"] = {"type":"doc","content":[{"type":"heading","attrs":{"level":2},"content":[{"text":"날짜","type":"text"}]},{"type":"paragraph","content":[{"type":"date","attrs":{"timestamp":"1704240000000"}}]},{"type":"heading","attrs":{"level":2},"content":[{"text":"참여자","type":"text","marks":[{"type":"strong"}]}]},{"type":"paragraph","content":[{"text":"대표이사, 진형권, 조한종, 홍대한, 최종태, 박재성 외 다수","type":"text"}]}],"version":1}

# ADF for 8048672826
ADF_DATA["8048672826"] = {"type":"doc","content":[{"type":"table","attrs":{"layout":"full-width","localId":"36170fd6-cdd3-46fa-b358-191f01d7883a"},"content":[{"type":"tableRow","content":[{"type":"tableHeader","content":[{"type":"paragraph","content":[{"text":"제품","type":"text","marks":[{"type":"strong"}]}]}]},{"type":"tableHeader","content":[{"type":"paragraph","content":[{"text":"항목","type":"text","marks":[{"type":"strong"}]}]}]},{"type":"tableHeader","content":[{"type":"paragraph","content":[{"text":"내용","type":"text","marks":[{"type":"strong"}]}]}]},{"type":"tableHeader","content":[{"type":"paragraph","content":[{"text":"관련 자료","type":"text","marks":[{"type":"strong"}]}]}]}]}]}],"version":1}

# ADF for 9509830687 (markdown available from API, ADF in large file)
ADF_DATA["9509830687"] = {"type":"doc","content":[{"type":"paragraph","content":[{"text":"[OTC] 2026년 5~8주차 업무. ADF 상세 내용은 Confluence 원본 참조.","type":"text"}]}],"version":1}

# ADF for 9603547139 (received directly from API)
# Already have it - will save in the loop

print("Saving 1-장비물류 pages...")
meta1 = save_pages(PAGES_1, BASE1, "과제① 장비물류")
print(f"  Saved {len(meta1)} pages")

print("Saving 2-분말검사 pages...")
meta2 = save_pages(PAGES_2, BASE2, "과제② 분말검사")
print(f"  Saved {len(meta2)} pages")

# 대용량 ADF 파일 처리 (9623371777)
adf_file_1 = r'C:/Users/Administrator/.claude/projects/C--MES-wta-agents-workspaces-research-agent/b0c74e1c-5091-4afc-9e32-30abf872d4f2/tool-results/mcp-plugin_atlassian_atlassian-getConfluencePage-1775272286392.txt'
if os.path.exists(adf_file_1):
    with open(adf_file_1, 'r', encoding='utf-8') as f:
        data = json.load(f)
    node = data['content']['nodes'][0]
    if isinstance(node.get('body'), dict):
        # Save ADF to 1-장비물류
        with open(os.path.join(BASE1, 'page-9623371777-structure.json'), 'w', encoding='utf-8') as f:
            json.dump(node['body'], f, ensure_ascii=False, indent=2)
        print("  Saved large ADF for 9623371777 to 1-장비물류")

# 대용량 ADF 파일 처리 (9577070593)
adf_file_2 = r'C:/Users/Administrator/.claude/projects/C--MES-wta-agents-workspaces-research-agent/b0c74e1c-5091-4afc-9e32-30abf872d4f2/tool-results/mcp-plugin_atlassian_atlassian-getConfluencePage-1775272316339.txt'
if os.path.exists(adf_file_2):
    with open(adf_file_2, 'r', encoding='utf-8') as f:
        data = json.load(f)
    node = data['content']['nodes'][0]
    if isinstance(node.get('body'), dict):
        with open(os.path.join(BASE2, 'page-9577070593-structure.json'), 'w', encoding='utf-8') as f:
            json.dump(node['body'], f, ensure_ascii=False, indent=2)
        print("  Saved large ADF for 9577070593 to 2-분말검사")

# 9603547139 ADF 저장 (API에서 직접 수신됨)
# The full ADF was received in the API call, save it now
adf_9603 = {"type":"doc","content":[{"type":"paragraph","attrs":{"localId":"f4dc79425fcf"}},{"type":"bulletList","attrs":{"localId":"6ab07cd1eaab"},"content":[{"type":"listItem","attrs":{"localId":"a69fbf2f9663"},"content":[{"type":"paragraph","attrs":{"localId":"6be49850436b"},"content":[{"text":"인서트 제조 공정 교육서","type":"text"}]}]}]},{"type":"orderedList","attrs":{"localId":"93d83f02-d095-4e49-9f75-d3d7d1098182","order":1},"content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"분말 야금 제조 공정(1차 원료 / 2차 원료)","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"성형 공정","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"소결 공정","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"가공 공정 (연삭 공정 / 호닝 공정)","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"코팅 공정 (CVD / PVD)","type":"text"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"text":"품질 공정","type":"text"}]}]}]}],"version":1}

with open(os.path.join(BASE2, 'page-9603547139-structure.json'), 'w', encoding='utf-8') as f:
    json.dump(adf_9603, f, ensure_ascii=False, indent=2)
print("  Saved ADF for 9603547139 to 2-분말검사")

# 9509830687의 ADF도 대용량 파일에 있을 경우 별도 처리 불필요 (markdown으로 대체)
# (mcp-plugin_atlassian_atlassian-getConfluencePage-1775272314985.txt 는 9577070593 파일임)
# 실제로는 두 파일 모두 이미 처리됨

print()
print("=== 저장 완료 ===")
print(f"1-장비물류: {BASE1}")
print(f"2-분말검사: {BASE2}")
