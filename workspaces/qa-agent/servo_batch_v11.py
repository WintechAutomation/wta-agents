#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
servo_batch_v11.py — 4_servo 43건 전체 파이프라인 배치 (SKILL.md v1.1)
task_id: tq-qa-agent-acbf75

단계:
  P0: Docling 파싱 + 임베딩 → reports/manuals-v2/poc/{file_id}/chunks.jsonl
  P1: pgvector UPSERT → manual.documents_v2
  P2: GraphRAG 추출 → Neo4j (800자+200 슬라이딩, qwen3.5:35b-a3b)
  P3: MRR 평가 (3쿼리/파일)
  P4: 파일별 JSON 저장

State: reports/manuals-v2/state/servo_batch_qa_state.json
Log:   reports/manuals-v2/state/servo_batch_qa.log
"""
import os, sys, json, re, time, hashlib, traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# ── Paths ─────────────────────────────────────────────────────────────────────
WORK_ROOT   = Path(r'C:\MES\wta-agents')
REPORTS     = WORK_ROOT / 'reports' / 'manuals-v2'
POC_ROOT    = REPORTS / 'poc'
STATE_DIR   = REPORTS / 'state'
EVAL_DIR    = REPORTS / 'eval'
STATE_PATH  = STATE_DIR / 'servo_batch_qa_state.json'
LOG_PATH    = STATE_DIR / 'servo_batch_qa.log'
BATCH_JSON  = REPORTS / 'batch_report_qa_servo.json'
BATCH_HTML  = WORK_ROOT / 'dashboard' / 'uploads' / 'batch_report_qa_servo.html'

STATE_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ── SKILL v1.1 constants ──────────────────────────────────────────────────────
WINDOW_SIZE    = 800
WINDOW_OVERLAP = 200
MIN_WINDOW_LEN = 50
EMBED_DIM      = 2000
EMBED_URL      = 'http://182.224.6.147:11434/api/embed'
EMBED_MODEL    = 'qwen3-embedding:8b'
LLM_URL        = 'http://182.224.6.147:11434/api/generate'
LLM_PARAMS     = {
    'model': 'qwen3.5:35b-a3b',
    'stream': False, 'think': False,
    'options': {'num_predict': 4096, 'temperature': 0},
}
LLM_TIMEOUT    = 300
NEO4J_URI      = 'bolt://localhost:7688'
NEO4J_USER     = 'neo4j'
_NEO4J_ENV     = Path(r'C:\MES\wta-agents\workspaces\research-agent\neo4j-poc.env')


def _read_neo4j_pass() -> str:
    try:
        for line in _NEO4J_ENV.read_text(encoding='utf-8').splitlines():
            if line.startswith('NEO4J_AUTH=neo4j/'):
                return line.split('/', 1)[1].strip()
    except Exception:
        pass
    return 'WtaPoc2026!Graph'


NEO4J_PASS     = _read_neo4j_pass()
TEAM           = 'qa-agent'
RUN_ID         = f'run-{datetime.now(KST).strftime("%Y%m%d-%H%M%S")}'

VALID_ENTITY_TYPES = {
    'Equipment', 'Component', 'Parameter', 'Alarm', 'Process',
    'Section', 'Figure', 'Table', 'Diagram', 'Specification', 'Manual', 'SafetyRule',
}
VALID_REL_TYPES = {
    'PART_OF', 'HAS_PARAMETER', 'SPECIFIES', 'CAUSES', 'RESOLVES',
    'CONNECTS_TO', 'REQUIRES', 'BELONGS_TO', 'REFERENCES',
    'DEPICTS', 'DOCUMENTS', 'WARNS',
}

MANUALS_V2_EXTRACT_PROMPT = """다음 산업 장비 매뉴얼 텍스트에서 엔티티와 관계를 추출하세요.

## 엔티티 타입 (12종)
- Equipment: 장비/기기 (로봇, 인버터, 서보, 센서, PLC 등)
- Component: 부품/구성요소 (모터, 엔코더, 퓨즈, 커넥터, 단자대 등)
- Parameter: 파라미터/설정값 코드 (C1-01, H4-02, Pr.7 등 코드 반드시 포함)
- Alarm: 알람/에러코드 (oC, AL.16, E401, OV 등 코드 반드시 포함)
- Process: 절차/작업/공정 (배선, 설치, 점검, 튜닝, 초기화, 교체 등)
- Section: 문서 섹션/챕터 (제목 단위)
- Figure: 그림/다이어그램 (배선도, 회로도, 외형도 등)
- Table: 표 (파라미터 표, 사양 표, 알람 일람표 등)
- Diagram: 도식/블록도 (제어 블록도, 시퀀스 다이어그램 등)
- Specification: 사양/규격 수치 (정격전압 200V, 최대토크 47Nm 등)
- Manual: 매뉴얼 문서 자체
- SafetyRule: 안전규정/경고 ("전원 차단 후 5분 대기" 등)

## 관계 타입 (12종)
- PART_OF: Component가 Equipment의 부품
- HAS_PARAMETER: Equipment가 Parameter를 가짐
- SPECIFIES: Specification이 Equipment/Component를 규정
- CAUSES: Alarm 발생 시 Process 유발
- RESOLVES: Process가 Alarm을 해결
- CONNECTS_TO: Equipment/Component 간 물리적 연결
- REQUIRES: Process에 필요한 Equipment/Component
- BELONGS_TO: Figure/Table이 Section에 속함
- REFERENCES: Section이 Figure/Table을 참조
- DEPICTS: Figure가 Equipment/Component를 도식
- DOCUMENTS: Manual이 Equipment/Process를 기술
- WARNS: SafetyRule이 Process/Equipment에 적용

## 추출 규칙
1. 엔티티 id는 영문 snake_case
2. name은 원문 표기 그대로 (한국어/영어/일어)
3. properties에 model, mfr, unit, code 등 있으면 포함
4. 관계는 반드시 추출된 엔티티 id 사이에서만 생성
5. 텍스트에 명시적 근거가 없는 관계는 생성하지 않음
6. 엔티티가 0개여도 빈 배열로 응답, 에러 메시지 금지

## 응답 형식 (JSON만, 다른 텍스트 없이)
{
  "entities": [
    {"id": "eng_snake_case", "name": "표시명", "type": "Equipment", "properties": {"model": "V1000", "mfr": "Yaskawa"}}
  ],
  "relations": [
    {"source": "entity_id1", "target": "entity_id2", "type": "HAS_PARAMETER"}
  ]
}

텍스트:
"""

# ── Target files ──────────────────────────────────────────────────────────────
TARGET_FILES = [
    {"file_id": "4_servo_9e9583765b0692ba03b9131976f6529d", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03335_R1_0E.pdf", "mfr": "Panasonic", "model": "SX-DSV03335", "lang": "EN", "doctype": "ParameterManual", "pages": 102},
    {"file_id": "4_servo_154943a48af7f9b97daca085e517ed24", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03307_R2_0E.pdf", "mfr": "Panasonic", "model": "SX-DSV03307", "lang": "JA", "doctype": "Manual", "pages": 329},
    {"file_id": "4_servo_49d4c661e5c4715ea997a4268b8e2958", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\WMX2 C_Sharp 라이브러리 사용법.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "KO", "doctype": "Manual", "pages": 19},
    {"file_id": "4_servo_1ebc2c43af162252f674925fe812cdf1", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\WMX2 설치 매뉴얼(32bit).pdf", "mfr": "Unknown", "model": "WMX2", "lang": "KO", "doctype": "Manual", "pages": 41},
    {"file_id": "4_servo_c66baea20e2c0f5f12e826bf55f597e1", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\WMX2 설치 매뉴얼(64bit).pdf", "mfr": "Unknown", "model": "WMX2", "lang": "KO", "doctype": "Troubleshooting", "pages": 49},
    {"file_id": "4_servo_e2cf4b266b429bec076cf47ba28bb56d", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\WMX2 설치 매뉴얼.pdf", "mfr": "Panasonic", "model": "WMX2", "lang": "KO", "doctype": "SetupGuide", "pages": 32},
    {"file_id": "4_servo_68ef765c37426d11b7b791c27f41425f", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03383_R2_2K_manual.pdf", "mfr": "Panasonic", "model": "SX-DSV03383", "lang": "KO", "doctype": "ParameterManual", "pages": 311},
    {"file_id": "4_servo_ae1a81ff6a710e7eb6925e79db9f7f55", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02473_R1_05E_e_Technical Document - EtherCAT Communication Specifications.pdf", "mfr": "Panasonic", "model": "SX-DSV02473", "lang": "JA", "doctype": "Manual", "pages": 285},
    {"file_id": "4_servo_e15db78dee984fa02ca11ffbed937ce2", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX2_Data_Sheet.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "KO", "doctype": "SetupGuide", "pages": 2},
    {"file_id": "4_servo_43cea7ccfa81f1d06a1b7cf88d7ab718", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX2_Console_Oper.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "EN", "doctype": "MaintenanceManual", "pages": 100},
    {"file_id": "4_servo_e1d6374a83f59f071334c0bb80d66172", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\WMX2_RTX6430_W10 설치 매뉴얼(64bit).pdf", "mfr": "Unknown", "model": "WMX2", "lang": "KO", "doctype": "Troubleshooting", "pages": 47},
    {"file_id": "4_servo_7f0c35a66f6b13df4610366064e193b7", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX2_Parameter.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "EN", "doctype": "MaintenanceManual", "pages": 42},
    {"file_id": "4_servo_925ca7207f2764b7946229c11df34596", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX2_Functions_K.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "EN", "doctype": "MaintenanceManual", "pages": 102},
    {"file_id": "4_servo_8995a29ecc7376d49341f186af6b6356", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\WMXServer 사용 매뉴얼.doc", "mfr": "Unknown", "model": "WMXServer", "lang": "KO", "doctype": "Manual", "pages": 0},
    {"file_id": "4_servo_242d62d77074d6ceec3c516741c59aeb", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02830_R1_00E.pdf", "mfr": "Panasonic", "model": "SX-DSV02830", "lang": "JA", "doctype": "Manual", "pages": 293},
    {"file_id": "4_servo_d7c92d7a241a715dfed2d1a0cd20bf9e", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX2_Functions.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "EN", "doctype": "MaintenanceManual", "pages": 123},
    {"file_id": "4_servo_1eac88b96b48020f1f8ac708822fd529", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX3SetupGuide.pdf", "mfr": "Unknown", "model": "WMX3SetupGuide", "lang": "EN", "doctype": "SetupGuide", "pages": 0},
    {"file_id": "4_servo_41108aa1f5de1a890db52f87d6de074e", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMXManagerManual.pdf", "mfr": "Unknown", "model": "WMXManagerManual", "lang": "KO", "doctype": "Manual", "pages": 7},
    {"file_id": "4_servo_0b856cca288d35d03c4e844adc7d0084", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMXManagerManual_170803_r2.pdf", "mfr": "Unknown", "model": "WMXManagerManual", "lang": "KO", "doctype": "Manual", "pages": 8},
    {"file_id": "4_servo_238dfdd12835bbdf5a1bd1db1138bf93", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX_Parameter_V0.99.pdf", "mfr": "Unknown", "model": "WMX", "lang": "EN", "doctype": "MaintenanceManual", "pages": 42},
    {"file_id": "4_servo_05c3ec5ad1042d40d40d596b3e34236c", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX3SetupGuide_KR.pdf", "mfr": "Unknown", "model": "WMX3SetupGuide", "lang": "KO", "doctype": "SetupGuide", "pages": 0},
    {"file_id": "4_servo_704bea4b696ad51b861a52fcc62d7c4b", "src": r"C:\MES\wta-agents\data\manuals\4_servo\[A5ML]SX-DSV02931_R1_3E_170220.pdf", "mfr": "Panasonic", "model": "A5ML", "lang": "EN", "doctype": "SetupGuide", "pages": 38},
    {"file_id": "4_servo_bed544457dea59074edbdc50a2a47431", "src": r"C:\MES\wta-agents\data\manuals\4_servo\[Manual]_Ezi-SERVOII_EtherCAT_SoftServo_KOR160404.pdf", "mfr": "Unknown", "model": "Ezi-SERVOII", "lang": "KO", "doctype": "Manual", "pages": 28},
    {"file_id": "4_servo_2a9e64d56991f5e9c8c2a360272e6dd2", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX3SetupGuide_JP.pdf", "mfr": "Unknown", "model": "WMX3SetupGuide", "lang": "JA", "doctype": "SetupGuide", "pages": 0},
    {"file_id": "4_servo_86a94ac9054ea96b7e2310a9d80023f0", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03242_R2_1E.pdf", "mfr": "Panasonic", "model": "SX-DSV03242", "lang": "JA", "doctype": "SetupGuide", "pages": 322},
    {"file_id": "4_servo_2599c91e152b8f9f143fbc1d8ea40c7c", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX_Console_Oper_V0.99.pdf", "mfr": "Unknown", "model": "WMX", "lang": "EN", "doctype": "MaintenanceManual", "pages": 94},
    {"file_id": "4_servo_4faf81f278e2841f6ab0dfc79e3edfe1", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX_Functions_v0.99.pdf", "mfr": "Unknown", "model": "WMX", "lang": "EN", "doctype": "MaintenanceManual", "pages": 108},
    {"file_id": "4_servo_2c1dce2e749872ec86ed58274cc333c4", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(Ezi-MOTIONLINK  PlusE) 사용자프로그램(GUI).pdf", "mfr": "Unknown", "model": "Ezi-MOTIONLINK", "lang": "KO", "doctype": "UserManual", "pages": 22},
    {"file_id": "4_servo_d8c857257035d645c90d81f6bc8be961", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(Ezi-MOTIONLINK  PlusE) 포지션테이블 기능편.pdf", "mfr": "Unknown", "model": "Ezi-MOTIONLINK", "lang": "KO", "doctype": "UserManual", "pages": 14},
    {"file_id": "4_servo_77ffcae7056bd0dfd596c0246e8c389a", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX3+Technical+Manual.pdf", "mfr": "Unknown", "model": "WMX3", "lang": "EN", "doctype": "Manual", "pages": 0},
    {"file_id": "4_servo_92f5b2ebd0a01d5b9e6daeda735579e5", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(Ezi-MOTIONLINK PlusE) 본문편.pdf", "mfr": "Unknown", "model": "Ezi-MOTIONLINK", "lang": "KO", "doctype": "ParameterManual", "pages": 40},
    {"file_id": "4_servo_41c91f3c3f5c1c17383ebba90db9777a", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSERVO PlusR) 사용자프로그램(GUI) 기능편.pdf", "mfr": "Unknown", "model": "EziSERVO", "lang": "KO", "doctype": "ParameterManual", "pages": 25},
    {"file_id": "4_servo_94f2a475432d1d5a43ab7f28108d0b2f", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSERVO PlusR) 포지션테이블 기능편.pdf", "mfr": "Unknown", "model": "EziSERVO", "lang": "KO", "doctype": "Manual", "pages": 26},
    {"file_id": "4_servo_193275a16f91ed2346948ab607975829", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(Ezi-MOTIONLINK  PlusE) 통신 기능편.pdf", "mfr": "Unknown", "model": "Ezi-MOTIONLINK", "lang": "KO", "doctype": "ParameterManual", "pages": 113},
    {"file_id": "4_servo_ef50ac0fa574223b9ca437cf5ed64f52", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSERVO PlusR) 본문편.pdf", "mfr": "Unknown", "model": "EziSERVO", "lang": "KO", "doctype": "WiringGuide", "pages": 95},
    {"file_id": "4_servo_938c4a734b7252275b98c36d63cd5d2f", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX2_APIReference.pdf", "mfr": "Unknown", "model": "WMX2", "lang": "EN", "doctype": "MaintenanceManual", "pages": 678},
    {"file_id": "4_servo_a9ab3297e5b68e732efcccd58e73b2b3", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSERVO PlusR) 통신_Ver6 기능편.pdf", "mfr": "Unknown", "model": "EziSERVO", "lang": "KO", "doctype": "ParameterManual", "pages": 134},
    {"file_id": "4_servo_ba9a79825f353390b3c5c248fda07d82", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSTEP PlusR) 본문편.pdf", "mfr": "Unknown", "model": "EziSTEP", "lang": "KO", "doctype": "WiringGuide", "pages": 67},
    {"file_id": "4_servo_053778fe6fe76ffe12f5a9320a99434b", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSTEP PlusR) 포지션테이블 기능편.pdf", "mfr": "Unknown", "model": "EziSTEP", "lang": "KO", "doctype": "Manual", "pages": 22},
    {"file_id": "4_servo_2d20789c2fff3aef499503712ffa1009", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSTEP PlusR) 사용자프로그램(GUI) 기능편.pdf", "mfr": "Unknown", "model": "EziSTEP", "lang": "KO", "doctype": "ParameterManual", "pages": 24},
    {"file_id": "4_servo_59f118e97997de2478a8904177028e02", "src": r"C:\MES\wta-agents\data\manuals\4_servo\WMX_APIReference_v0.99.pdf", "mfr": "Unknown", "model": "WMX", "lang": "EN", "doctype": "MaintenanceManual", "pages": 557},
    {"file_id": "4_servo_9c35ea621532a0b36f20a795a4d7f3ca", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\사용자메뉴얼(EziSTEP PlusR) 통신_Ver6 기능편.pdf", "mfr": "Unknown", "model": "EziSTEP", "lang": "KO", "doctype": "ParameterManual", "pages": 114},
    {"file_id": "4_servo_e3a5e2c4c2fd51ab82db2420bca27cb3", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\편면Panasonic Servo 20160127 (일산 이구스 다이덴).pdf", "mfr": "Unknown", "model": "Panasonic", "lang": "EN", "doctype": "Manual", "pages": 1},
    # --- 추가 21건 (db-manager 재분배, 2026-04-13) ---
    {"file_id": "4_servo_029abc028d543129900ef28597e70229", "src": r"C:\MES\wta-agents\data\manuals\4_servo\Motion-RN001B-CSD5-KO_Firware1.39.pdf", "mfr": "Unknown", "model": "Motion-RN001B-CSD5-K", "lang": "KO", "doctype": "WiringGuide", "pages": 30},
    {"file_id": "4_servo_65e20dbb93080ab98d5c047cc1167f22", "src": r"C:\MES\wta-agents\data\manuals\4_servo\minas-a6_ctlg_e.pdf", "mfr": "Panasonic", "model": "minas-a6", "lang": "EN", "doctype": "Catalog", "pages": 145},
    {"file_id": "4_servo_68f68b18007c352668fd9a01787362dd", "src": r"C:\MES\wta-agents\data\manuals\4_servo\minas-a6_ctlg_kr.pdf", "mfr": "Panasonic", "model": "minas-a6", "lang": "KO", "doctype": "Troubleshooting", "pages": 167},
    {"file_id": "4_servo_ad87315c78defffd9ead986a6f4019e3", "src": r"C:\MES\wta-agents\data\manuals\4_servo\minas-a5b_ctlg_e.pdf", "mfr": "Panasonic", "model": "minas-a5b", "lang": "EN", "doctype": "Catalog", "pages": 2},
    {"file_id": "4_servo_01f9867ec97ed889ce8ae2320b7853bf", "src": r"C:\MES\wta-agents\data\manuals\4_servo\Panasonic Servo.pdf", "mfr": "Panasonic", "model": "Panasonic", "lang": "KO", "doctype": "Manual", "pages": 33},
    {"file_id": "4_servo_8f32d3b79d220e96e17d33fcce89476e", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02473_R4_00E.pdf", "mfr": "Panasonic", "model": "SX-DSV02473", "lang": "JA", "doctype": "Manual", "pages": 294},
    {"file_id": "4_servo_0411096280f06ba8e578af21e29678b9", "src": r"C:\MES\wta-agents\data\manuals\4_servo\PANATERMforA5_ko.pdf", "mfr": "Panasonic", "model": "PANATERMforA5", "lang": "KO", "doctype": "Troubleshooting", "pages": 185},
    {"file_id": "4_servo_d223a0cceaed4e8b5c716364f3b1f427", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\RSACSD7 관련.docx", "mfr": "Unknown", "model": "RSACSD7", "lang": "EN", "doctype": "Manual", "pages": 0},
    {"file_id": "4_servo_e94e4902649c853e192e5f62b198099c", "src": r"C:\MES\wta-agents\data\manuals\4_servo\rtex_cable_r5e.pdf", "mfr": "Panasonic", "model": "rtex", "lang": "EN", "doctype": "EthernetInterface", "pages": 16},
    {"file_id": "4_servo_e5cefa9c8480245d0c7acc7c058f9a0b", "src": r"C:\MES\wta-agents\data\manuals\4_servo\Reference Specifications.pdf", "mfr": "Panasonic", "model": "Reference", "lang": "EN", "doctype": "SetupGuide", "pages": 87},
    {"file_id": "4_servo_e9f8f9765b360d3149213139343e8a2f", "src": r"C:\MES\wta-agents\data\manuals\4_servo\EtherCAT Communication Specifications_unlock.pdf", "mfr": "Panasonic", "model": "EtherCAT", "lang": "JA", "doctype": "Manual", "pages": 294},
    {"file_id": "4_servo_6b9eb011dbfa2cfbd3e179442c1d76f6", "src": "C:\\MES\\wta-agents\\data\\manuals\\4_servo\\SSK_Seminar 2015 (한국어) 2015 0116.pdf", "mfr": "Panasonic", "model": "SSK", "lang": "KO", "doctype": "Manual", "pages": 47},
    {"file_id": "4_servo_e9649d8eb8f24353b3d13932cbbb358d", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02468_J.pdf", "mfr": "Panasonic", "model": "SX-DSV02468", "lang": "JA", "doctype": "SetupGuide", "pages": 74},
    {"file_id": "4_servo_dbccbb6482a73669ab01ce02eea67aed", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02469_R1_05J.pdf", "mfr": "Panasonic", "model": "SX-DSV02469", "lang": "JA", "doctype": "Manual", "pages": 154},
    {"file_id": "4_servo_af63b20c890a6ae0b00ad0800878292f", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02471_R4_0E.pdf", "mfr": "Panasonic", "model": "SX-DSV02471", "lang": "EN", "doctype": "SetupGuide", "pages": 87},
    {"file_id": "4_servo_3d5b637cdf9031387627c1ebf05ccba7", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02828_R1_0E.pdf", "mfr": "Panasonic", "model": "SX-DSV02828", "lang": "JA", "doctype": "SetupGuide", "pages": 80},
    {"file_id": "4_servo_e8fca0f15d48c0daa868dc9c096f92d6", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03002_R3_0E.pdf", "mfr": "Panasonic", "model": "SX-DSV03002", "lang": "EN", "doctype": "SetupGuide", "pages": 88},
    {"file_id": "4_servo_4845a16fd1d22b9304579b963e215ee5", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV02829_R1_00E.pdf", "mfr": "Panasonic", "model": "SX-DSV02829", "lang": "JA", "doctype": "SetupGuide", "pages": 206},
    {"file_id": "4_servo_ee2ccc4c4dba7e34f743e4678e057b53", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03190_R1_0E_170428.pdf", "mfr": "Panasonic", "model": "SX-DSV03190", "lang": "EN", "doctype": "ParameterManual", "pages": 83},
    {"file_id": "4_servo_0e348e406e749a8fd8f71b4042a9be9f", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03241_R2_1E.pdf", "mfr": "Panasonic", "model": "SX-DSV03241", "lang": "JA", "doctype": "Manual", "pages": 248},
    {"file_id": "4_servo_15db0cd9acd1f3e009f3817b3a443ab8", "src": r"C:\MES\wta-agents\data\manuals\4_servo\SX-DSV03306_R2_0E.pdf", "mfr": "Panasonic", "model": "SX-DSV03306", "lang": "JA", "doctype": "SetupGuide", "pages": 246},
]

TOTAL = len(TARGET_FILES)


# ── Logging ────────────────────────────────────────────────────────────────────
def log(msg: str):
    ts = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


# ── State ──────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'task_id': 'tq-qa-agent-acbf75',
        'run_id': RUN_ID,
        'team': TEAM,
        'total': TOTAL,
        'completed': 0,
        'files': {},
        'last_update': datetime.now(KST).isoformat(),
    }


def save_state(state: dict):
    state['last_update'] = datetime.now(KST).isoformat()
    tmp = STATE_PATH.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


def file_state(state: dict, file_id: str) -> dict:
    if file_id not in state['files']:
        state['files'][file_id] = {'status': 'pending', 'chunks': 0, 'windows': 0,
                                    'entities': 0, 'relations': 0, 'nodes': 0, 'mrr': None}
    return state['files'][file_id]


# ── DB helpers ─────────────────────────────────────────────────────────────────
def _read_db_password() -> str:
    pwd = os.environ.get('DB_PASSWORD', '')
    if not pwd:
        env_path = Path(r'C:\MES\backend\.env')
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                if line.startswith('DB_PASSWORD='):
                    pwd = line.split('=', 1)[1].strip()
                    break
    return pwd


def get_db():
    import psycopg2
    return psycopg2.connect(
        host='localhost', port=55432, dbname='postgres',
        user='postgres', password=_read_db_password(),
    )


# ── Embedding ─────────────────────────────────────────────────────────────────
def embed_texts(texts: list[str], batch_size=8) -> list[list[float] | None]:
    """Embed texts with retry. batch_size=8 reduces per-request load."""
    import requests as req
    results = [None] * len(texts)
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for attempt in range(3):
            try:
                resp = req.post(EMBED_URL, json={'model': EMBED_MODEL, 'input': batch}, timeout=300)
                resp.raise_for_status()
                vecs = resp.json().get('embeddings', [])
                for j, vec in enumerate(vecs):
                    if vec and len(vec) >= EMBED_DIM:
                        results[i + j] = vec[:EMBED_DIM]
                break
            except Exception as e:
                log(f'  EMBED_ERR batch {i} attempt {attempt+1}: {e}')
                if attempt < 2:
                    time.sleep(5)
    return results


def embed_text(text: str) -> list[float] | None:
    vecs = embed_texts([text])
    return vecs[0] if vecs else None


# ── Sliding windows ────────────────────────────────────────────────────────────
def build_windows(chunks: list[dict]) -> list[dict]:
    parts = []
    chunk_map = []
    pos = 0
    for ch in chunks:
        content = (ch.get('content') or '').strip()
        if not content:
            continue
        chunk_map.append((pos, ch.get('chunk_id', '')))
        parts.append(content)
        pos += len(content) + 2
    full_text = '\n\n'.join(parts)
    windows = []
    start = 0
    while start < len(full_text):
        end = start + WINDOW_SIZE
        win_text = full_text[start:end]
        if len(win_text) < MIN_WINDOW_LEN:
            break
        remaining = len(full_text) - end
        if 0 < remaining < 300:
            win_text = full_text[start:end + remaining]
            end = len(full_text)
        cids = [cid for (p, cid) in chunk_map if p < end and p + 100 > start]
        windows.append({'idx': len(windows), 'text': win_text, 'chunk_ids': cids})
        start = end - WINDOW_OVERLAP
    return windows


# ── LLM call ──────────────────────────────────────────────────────────────────
def call_llm(text: str) -> dict:
    import requests as req
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
    try:
        from json_repair import repair_json
        HAS_REPAIR = True
    except ImportError:
        HAS_REPAIR = False

    prompt = MANUALS_V2_EXTRACT_PROMPT + text
    payload = dict(LLM_PARAMS)
    payload['prompt'] = prompt
    payload['stream'] = False  # non-streaming; timeout enforced via future

    def _do_req():
        resp = req.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get('response', '')

    # Run in daemon thread; future.result(timeout) is the hard wall-clock limit.
    # executor.shutdown(wait=False) so the orphaned thread doesn't block exit.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='llm_call')
    future = executor.submit(_do_req)
    executor.shutdown(wait=False)
    try:
        raw = future.result(timeout=LLM_TIMEOUT + 30)  # 30s grace beyond socket timeout
    except FutTimeout:
        raise TimeoutError(f'LLM call timed out after {LLM_TIMEOUT + 30}s')

    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return {'entities': [], 'relations': []}
    s = m.group(0)
    try:
        return json.loads(s)
    except Exception:
        if HAS_REPAIR:
            try:
                return json.loads(repair_json(s))
            except Exception:
                pass
        # partial parse entities only
        ents = re.findall(r'\{[^{}]*"id"\s*:\s*"[^"]+[^{}]*\}', s)
        entities = []
        for e in ents:
            try:
                entities.append(json.loads(e))
            except Exception:
                pass
        return {'entities': entities, 'relations': []}


# ── Neo4j MERGE ────────────────────────────────────────────────────────────────
def neo4j_merge(file_id: str, run_id: str, entities: list, relations: list) -> tuple[int, int]:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    node_count, rel_count = 0, 0
    eid_set = set()
    with driver.session() as s:
        for ent in entities:
            etype = ent.get('type', '')
            if etype not in VALID_ENTITY_TYPES:
                continue
            eid = ent.get('id', '')
            if not eid:
                continue
            props = ent.get('properties', {}) or {}
            props['source'] = 'manuals_v2'
            props['_run_id'] = run_id
            props['_file_id'] = file_id
            props['_team'] = TEAM
            props['_id'] = eid
            try:
                s.run(
                    f'MERGE (n:ManualsV2Entity:{etype} {{_id: $_id}}) SET n += $props, n.name = $name',
                    _id=eid, props=props, name=ent.get('name', eid),
                )
                eid_set.add(eid)
                node_count += 1
            except Exception:
                # Constraint violation (duplicate name) — skip this entity
                pass
        for rel in relations:
            rtype = rel.get('type', '')
            if rtype not in VALID_REL_TYPES:
                continue
            src = rel.get('source', '')
            tgt = rel.get('target', '')
            if src not in eid_set or tgt not in eid_set:
                continue
            try:
                s.run(
                    f'MATCH (a:ManualsV2Entity {{_id:$src}}), (b:ManualsV2Entity {{_id:$tgt}}) '
                    f'MERGE (a)-[:{rtype}]->(b)',
                    src=src, tgt=tgt,
                )
                rel_count += 1
            except Exception:
                pass
    driver.close()
    return node_count, rel_count


# ── Docling helpers (inline — no sys.stdout redirect) ─────────────────────────
_INLINE_REF_RE = re.compile(r'(?:그림|Figure|Fig\.?|표|Table)\s*([\d\-\.]+)', re.I)

def _extract_inline_refs(text: str) -> list[str]:
    refs = set()
    for m in _INLINE_REF_RE.finditer(text or ''):
        refs.add(m.group(1))
    return sorted(refs)


def _lazy_docling():
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
    from PIL import Image
    return DocumentConverter, PdfFormatOption, PdfPipelineOptions, InputFormat, HierarchicalChunker, Image


def _parse_pdf(pdf_path: Path, out_dir: Path):
    DocumentConverter, PdfFormatOption, PdfPipelineOptions, InputFormat, _, _ = _lazy_docling()
    pipeline_options = PdfPipelineOptions(
        generate_picture_images=True,
        images_scale=2.0,
        do_ocr=True,
        do_table_structure=True,
    )
    pipeline_options.table_structure_options.do_cell_matching = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    t0 = time.time()
    result = converter.convert(str(pdf_path))
    doc = result.document
    log(f'  Docling 파싱 완료: {time.time()-t0:.1f}s')
    return doc


def _export_images(doc, img_dir: Path, file_id: str) -> list[dict]:
    _, _, _, _, _, Image = _lazy_docling()
    img_dir.mkdir(parents=True, exist_ok=True)
    figures = []
    for idx, (item, _level) in enumerate(doc.iterate_items()):
        if item.__class__.__name__ != 'PictureItem':
            continue
        page_no = getattr(item.prov[0], 'page_no', 0) if item.prov else 0
        bbox = None
        if item.prov and hasattr(item.prov[0], 'bbox'):
            b = item.prov[0].bbox
            bbox = {'l': b.l, 't': b.t, 'r': b.r, 'b': b.b}
        caption = ''
        try:
            caption = item.caption_text(doc=doc) or ''
        except Exception:
            caption = getattr(item, 'caption', '') or ''
        figure_id = f'fig_{page_no:03d}_{idx:03d}'
        img_path = img_dir / f'{figure_id}.png'
        thumb_path = img_dir / f'{figure_id}_thumb.png'
        try:
            pil_img = item.get_image(doc=doc)
            if pil_img is None or pil_img.width < 28 or pil_img.height < 28:
                continue
            pil_img.save(img_path, 'PNG')
            thumb = pil_img.copy()
            thumb.thumbnail((256, 256))
            thumb.save(thumb_path, 'PNG')
        except Exception as e:
            log(f'    이미지 추출 실패 {figure_id}: {e}')
            continue
        figures.append({
            'figure_id': figure_id,
            'caption': caption,
            'page': page_no,
            'bbox': bbox,
        })
    return figures


def _export_tables(doc) -> list[dict]:
    tables = []
    for idx, (item, _level) in enumerate(doc.iterate_items()):
        if item.__class__.__name__ != 'TableItem':
            continue
        page_no = getattr(item.prov[0], 'page_no', 0) if item.prov else 0
        html = ''
        try:
            html = item.export_to_html(doc=doc)
        except Exception:
            pass
        tables.append({'table_id': f'tbl_{page_no:03d}_{idx:03d}', 'page': page_no, 'html': html})
    return tables


def _chunk_document(doc) -> list[dict]:
    _, _, _, _, HierarchicalChunker, _ = _lazy_docling()
    chunker = HierarchicalChunker()
    chunks = list(chunker.chunk(doc))
    out = []
    for i, ch in enumerate(chunks):
        text = ch.text if hasattr(ch, 'text') else str(ch)
        meta = ch.meta if hasattr(ch, 'meta') else None
        section_path = []
        page_start = page_end = None
        try:
            section_path = list(meta.headings or []) if meta else []
        except Exception:
            pass
        try:
            doc_items = meta.doc_items if meta else []
            pages = set()
            for di in doc_items:
                for p in getattr(di, 'prov', []) or []:
                    if hasattr(p, 'page_no'):
                        pages.add(p.page_no)
            if pages:
                page_start = min(pages)
                page_end = max(pages)
        except Exception:
            pass
        out.append({
            'chunk_idx': i,
            'content': text,
            'section_path': section_path,
            'page_start': page_start,
            'page_end': page_end,
            'tokens': len(text.split()),
        })
    return out


def _match_figures_to_chunks(chunks: list[dict], figures: list[dict], tables: list[dict]) -> list[dict]:
    by_page_fig: dict[int, list] = {}
    for f in figures:
        by_page_fig.setdefault(f['page'], []).append(f)
    by_page_tbl: dict[int, list] = {}
    for t in tables:
        by_page_tbl.setdefault(t['page'], []).append(t)
    for ch in chunks:
        ps, pe = ch.get('page_start'), ch.get('page_end')
        fig_refs, tbl_refs = [], []
        if ps is not None and pe is not None:
            for pg in range(ps, pe + 1):
                fig_refs.extend(by_page_fig.get(pg, []))
                tbl_refs.extend(by_page_tbl.get(pg, []))
        ch['figure_refs'] = fig_refs
        ch['table_refs'] = tbl_refs
        ch['inline_refs'] = _extract_inline_refs(ch['content'])
    return chunks


# ── Docling parse (custom file_id) ─────────────────────────────────────────────
def parse_to_chunks(fi: dict) -> list[dict]:
    """Parse a PDF/DOCX and return chunk list. Saves chunks.jsonl in poc/{file_id}/.
    Two-phase: (1) Docling parse → chunks.jsonl (embedding=null),
               (2) embed → update chunks.jsonl.
    Resumable: skips Docling if chunks.jsonl already exists.
    """
    file_id = fi['file_id']
    src = Path(fi['src'])
    out_dir = POC_ROOT / file_id
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = out_dir / 'chunks.jsonl'

    # ── Phase 1: Docling parsing ──────────────────────────────────────────────
    if not (chunks_path.exists() and chunks_path.stat().st_size > 100):
        doc = _parse_pdf(src, out_dir)
        figures = _export_images(doc, out_dir / 'images', file_id)
        tables = _export_tables(doc)
        raw_chunks = _chunk_document(doc)
        raw_chunks = [c for c in raw_chunks
                      if (c.get('content') or '').strip() and
                      len((c['content'] or '').split()) >= 2]
        raw_chunks = _match_figures_to_chunks(raw_chunks, figures, tables)
        log(f'  [{file_id}] chunks={len(raw_chunks)}, figures={len(figures)}, tables={len(tables)}')

        # Save immediately WITHOUT embeddings (crash-safe)
        with open(chunks_path, 'w', encoding='utf-8') as f:
            for i, ch in enumerate(raw_chunks):
                row = {
                    'file_id': file_id,
                    'chunk_id': f'{(ch.get("page_start") or 0):04d}_{i:04d}',
                    'category': '4_servo',
                    'mfr': fi.get('mfr', 'Unknown'),
                    'model': fi.get('model', 'Unknown'),
                    'doctype': fi.get('doctype', 'manual').lower(),
                    'lang': fi.get('lang', 'EN').lower(),
                    'section_path': ch.get('section_path', []),
                    'page_start': ch.get('page_start'),
                    'page_end': ch.get('page_end'),
                    'content': ch['content'],
                    'tokens': ch.get('tokens', 0),
                    'embedding': None,
                    'figure_refs': ch.get('figure_refs', []),
                    'table_refs': ch.get('table_refs', []),
                    'inline_refs': ch.get('inline_refs', []),
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        log(f'  [{file_id}] chunks.jsonl 저장 (embedding=null)')
    else:
        log(f'  [{file_id}] chunks.jsonl 기존 재사용 (Phase1 스킵)')

    # ── Phase 2: Load & embed if any embedding is missing ────────────────────
    chunks = []
    with open(chunks_path, encoding='utf-8') as f:
        for ln in f:
            try:
                chunks.append(json.loads(ln))
            except Exception:
                pass

    missing_idx = [i for i, ch in enumerate(chunks) if ch.get('embedding') is None]
    if missing_idx:
        log(f'  [{file_id}] 임베딩 {len(missing_idx)}/{len(chunks)} 건 처리 중...')
        texts = [chunks[i]['content'] for i in missing_idx]
        vectors = embed_texts(texts)
        for k, i in enumerate(missing_idx):
            chunks[i]['embedding'] = vectors[k]
        # Rewrite chunks.jsonl with embeddings
        with open(chunks_path, 'w', encoding='utf-8') as f:
            for ch in chunks:
                f.write(json.dumps(ch, ensure_ascii=False) + '\n')
        embedded = sum(1 for ch in chunks if ch.get('embedding') is not None)
        log(f'  [{file_id}] 임베딩 완료: {embedded}/{len(chunks)}')

    return chunks


# ── pgvector UPSERT ────────────────────────────────────────────────────────────
def upsert_pgvector(chunks: list[dict]) -> int:
    conn = get_db()
    cur = conn.cursor()
    count = 0
    for ch in chunks:
        emb = ch.get('embedding')
        if emb is None:
            continue
        cur.execute(
            '''INSERT INTO manual.documents_v2
               (file_id, chunk_id, category, mfr, model, doctype, lang,
                section_path, page_start, page_end, content, embedding,
                figure_refs, table_refs, inline_refs)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,%s,%s)
               ON CONFLICT (file_id, chunk_id)
               DO UPDATE SET content=EXCLUDED.content, embedding=EXCLUDED.embedding,
                             mfr=EXCLUDED.mfr, model=EXCLUDED.model''',
            (
                ch['file_id'], ch['chunk_id'], ch.get('category','4_servo'),
                ch.get('mfr',''), ch.get('model',''), ch.get('doctype',''),
                ch.get('lang',''), json.dumps(ch.get('section_path',[])),
                ch.get('page_start'), ch.get('page_end'), ch.get('content',''),
                '[' + ','.join(str(x) for x in emb) + ']',
                json.dumps(ch.get('figure_refs',[])),
                json.dumps(ch.get('table_refs',[])),
                json.dumps(ch.get('inline_refs',[])),
            )
        )
        count += 1
    conn.commit()
    conn.close()
    return count


# ── MRR evaluation ────────────────────────────────────────────────────────────
def eval_mrr(file_id: str, chunks: list[dict]) -> dict:
    """Generate 3 queries from top chunks and evaluate MRR@5."""
    import requests as req

    # Pick top-3 content-rich chunks as query sources
    sorted_chunks = sorted(chunks, key=lambda c: len(c.get('content','') or ''), reverse=True)
    query_chunks = sorted_chunks[:3]

    results = []
    for qch in query_chunks:
        content = (qch.get('content') or '').strip()
        if not content:
            continue
        # Use first sentence as query
        first_sent = re.split(r'[.\n]', content)[0].strip()
        if len(first_sent) < 10:
            first_sent = content[:80].strip()
        query = first_sent
        answer_cid = qch['chunk_id']

        # Embed query
        qvec = embed_text(query)
        if qvec is None:
            results.append({'query': query, 'mrr': 0.0, 'hit': 0, 'retrieved_ids': []})
            continue

        # Search pgvector
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            '''SELECT chunk_id FROM manual.documents_v2
               WHERE file_id = %s
               ORDER BY embedding <=> %s::vector LIMIT 5''',
            (file_id, '[' + ','.join(str(x) for x in qvec) + ']')
        )
        retrieved = [row[0] for row in cur.fetchall()]
        conn.close()

        rr = 0.0
        for rank, rid in enumerate(retrieved, 1):
            if rid == answer_cid:
                rr = 1.0 / rank
                break
        results.append({
            'query': query,
            'answer_chunk_id': answer_cid,
            'retrieved_ids': retrieved,
            'mrr': rr,
            'hit': int(answer_cid in retrieved),
        })

    if not results:
        return {'mrr': 0.0, 'hit_at_5': 0.0, 'precision_at_5': 0.0, 'pass_fail': 'FAIL', 'queries': []}

    avg_mrr = sum(r['mrr'] for r in results) / len(results)
    avg_hit = sum(r['hit'] for r in results) / len(results)
    avg_prec = sum(r['hit'] for r in results) / (len(results) * 5) if results else 0.0
    return {
        'mrr': round(avg_mrr, 4),
        'hit_at_5': round(avg_hit, 4),
        'precision_at_5': round(avg_prec, 4),
        'pass_fail': 'PASS' if avg_mrr >= 0.5 else 'FAIL',
        'queries': results,
    }


# ── Per-file GraphRAG extraction ───────────────────────────────────────────────
def graphrag_for_file(file_id: str, chunks: list[dict], state: dict) -> tuple[int, int, int]:
    """Run GraphRAG for a single file. Returns (total_entities_raw, total_rels_raw, neo4j_nodes)."""
    fstate = file_state(state, file_id)

    # Load or init per-file graphrag checkpoint
    ckpt_path = STATE_DIR / f'graphrag_{file_id}.json'
    if ckpt_path.exists():
        ckpt = json.loads(ckpt_path.read_text(encoding='utf-8'))
    else:
        windows = build_windows(chunks)
        ckpt = {
            'file_id': file_id,
            'run_id': state['run_id'],
            'total_windows': len(windows),
            'completed_windows': 0,
            'entities_raw': 0,
            'rels_raw': 0,
            'neo4j_nodes': 0,
            'windows': [{'idx': w['idx'], 'text': w['text'], 'done': False} for w in windows],
        }
        ckpt_path.write_text(json.dumps(ckpt, ensure_ascii=False), encoding='utf-8')

    total_w = ckpt['total_windows']
    log(f'  [{file_id}] GraphRAG: {ckpt["completed_windows"]}/{total_w} windows')

    for win in ckpt['windows']:
        if win['done']:
            continue
        t0 = time.time()
        try:
            result = call_llm(win['text'])
            entities = result.get('entities', []) or []
            relations = result.get('relations', []) or []
            # Filter valid types
            entities = [e for e in entities if isinstance(e, dict) and e.get('type') in VALID_ENTITY_TYPES]
            relations = [r for r in relations if isinstance(r, dict) and r.get('type') in VALID_REL_TYPES]
            # Neo4j MERGE
            nc, rc = neo4j_merge(file_id, state['run_id'], entities, relations)
            ckpt['entities_raw'] += len(entities)
            ckpt['rels_raw'] += len(relations)
            ckpt['neo4j_nodes'] += nc
            ckpt['completed_windows'] += 1
            win['done'] = True
            elapsed = time.time() - t0
            log(f'    win {win["idx"]}/{total_w}: ents={len(entities)}, rels={len(relations)}, nodes={nc} ({elapsed:.0f}s)')
        except Exception as e:
            log(f'    win {win["idx"]} ERR: {e}')
        # Save checkpoint every 5 windows
        if ckpt['completed_windows'] % 5 == 0:
            ckpt_path.write_text(json.dumps(ckpt, ensure_ascii=False), encoding='utf-8')

    ckpt_path.write_text(json.dumps(ckpt, ensure_ascii=False), encoding='utf-8')
    return ckpt['entities_raw'], ckpt['rels_raw'], ckpt['neo4j_nodes']


# ── Main batch loop ────────────────────────────────────────────────────────────
def main():
    log(f'=== servo_batch_v11 시작 (run_id={RUN_ID}) ===')
    log(f'총 {TOTAL}개 파일')

    state = load_state()
    # Preserve run_id if already set
    if 'run_id' not in state:
        state['run_id'] = RUN_ID

    completed_this_run = 0

    for idx, fi in enumerate(TARGET_FILES):
        file_id = fi['file_id']
        fstate = file_state(state, file_id)

        if fstate['status'] == 'done':
            log(f'[{idx+1}/{TOTAL}] {file_id} — 이미 완료, 스킵')
            continue

        log(f'\n[{idx+1}/{TOTAL}] {file_id} ({fi["model"]}, {fi["pages"]}p) status={fstate["status"]}')
        src_path = Path(fi['src'])

        # ── P0: Parse ──────────────────────────────────────────────────────
        if fstate['status'] in ('pending',):
            if not src_path.exists():
                log(f'  ERR src 없음: {src_path}')
                fstate['status'] = 'skip_no_src'
                save_state(state)
                continue
            fstate['status'] = 'parsing'
            save_state(state)
            try:
                chunks = parse_to_chunks(fi)
                fstate['chunks'] = len(chunks)
                fstate['status'] = 'parsed'
                log(f'  parsed: {len(chunks)} chunks')
                save_state(state)
            except Exception as e:
                log(f'  PARSE ERR: {e}\n{traceback.format_exc()}')
                fstate['status'] = 'parse_err'
                fstate['error'] = str(e)[:200]
                save_state(state)
                continue

        # Load chunks if needed
        chunks_path = POC_ROOT / file_id / 'chunks.jsonl'
        if fstate['status'] in ('parsed', 'pgvector_done', 'graphrag_done', 'evaluating'):
            chunks = []
            if chunks_path.exists():
                with open(chunks_path, encoding='utf-8') as f:
                    for ln in f:
                        try:
                            chunks.append(json.loads(ln))
                        except Exception:
                            pass

        # ── P1: pgvector UPSERT ────────────────────────────────────────────
        if fstate['status'] == 'parsed':
            try:
                inserted = upsert_pgvector(chunks)
                fstate['pgvector_rows'] = inserted
                fstate['status'] = 'pgvector_done'
                log(f'  pgvector: {inserted} rows')
                save_state(state)
            except Exception as e:
                log(f'  PGVECTOR ERR: {e}')
                fstate['status'] = 'pgvector_err'
                fstate['error'] = str(e)[:200]
                save_state(state)
                continue

        # ── P2: GraphRAG ───────────────────────────────────────────────────
        if fstate['status'] == 'pgvector_done':
            fstate['status'] = 'graphrag_running'
            save_state(state)
            try:
                ents, rels, nodes = graphrag_for_file(file_id, chunks, state)
                fstate['entities'] = ents
                fstate['relations'] = rels
                fstate['nodes'] = nodes
                fstate['status'] = 'graphrag_done'
                log(f'  graphrag: ents={ents}, rels={rels}, nodes={nodes}')
                save_state(state)
            except Exception as e:
                log(f'  GRAPHRAG ERR: {e}\n{traceback.format_exc()}')
                fstate['status'] = 'graphrag_err'
                fstate['error'] = str(e)[:200]
                save_state(state)
                continue

        # ── P3: MRR eval ───────────────────────────────────────────────────
        if fstate['status'] == 'graphrag_done':
            fstate['status'] = 'evaluating'
            save_state(state)
            try:
                eval_result = eval_mrr(file_id, chunks)
                fstate['mrr'] = eval_result['mrr']
                fstate['hit_at_5'] = eval_result['hit_at_5']
                fstate['precision_at_5'] = eval_result['precision_at_5']
                fstate['pass_fail'] = eval_result['pass_fail']
                fstate['status'] = 'done'
                log(f'  eval: MRR={eval_result["mrr"]}, pass={eval_result["pass_fail"]}')

                # Save per-file report
                file_report = {
                    'file_id': file_id, 'model': fi['model'], 'mfr': fi['mfr'],
                    'pages': fi['pages'], 'chunks': fstate['chunks'],
                    'entities': fstate['entities'], 'relations': fstate['relations'],
                    'neo4j_nodes': fstate['nodes'],
                    'mrr': eval_result['mrr'], 'hit_at_5': eval_result['hit_at_5'],
                    'pass_fail': eval_result['pass_fail'],
                }
                fr_path = REPORTS / 'qa' / f'{file_id}.json'
                fr_path.parent.mkdir(exist_ok=True)
                fr_path.write_text(json.dumps(file_report, ensure_ascii=False, indent=2), encoding='utf-8')

                state['completed'] = sum(1 for v in state['files'].values() if v['status'] == 'done')
                save_state(state)
                completed_this_run += 1
            except Exception as e:
                log(f'  EVAL ERR: {e}')
                fstate['status'] = 'eval_err'
                fstate['error'] = str(e)[:200]
                save_state(state)
                continue

        # Progress report every 10 completed files
        if completed_this_run > 0 and completed_this_run % 10 == 0:
            done_count = sum(1 for v in state['files'].values() if v['status'] == 'done')
            _report_progress(state, done_count)

    # Final report
    done_count = sum(1 for v in state['files'].values() if v['status'] == 'done')
    log(f'\n=== 배치 완료: {done_count}/{TOTAL} ===')
    generate_batch_report(state)
    _report_complete(state, done_count)


def _report_progress(state: dict, done_count: int):
    """10건마다 MAX에 진행 보고 (send_message via subprocess)."""
    import subprocess
    pct = int(done_count / TOTAL * 100)
    msg = (f'[task:tq-qa-agent-acbf75] 서보 배치 진행 중\n'
           f'{done_count}/{TOTAL}건 완료 ({pct}%)\n'
           f'오류: {sum(1 for v in state["files"].values() if "err" in v["status"])}건')
    log(f'[PROGRESS] {msg}')
    # Write to a temp file for MCP channel (agent reads it)
    prog_path = STATE_DIR / 'servo_batch_progress.txt'
    prog_path.write_text(msg, encoding='utf-8')


def _report_complete(state: dict, done_count: int):
    prog_path = STATE_DIR / 'servo_batch_done.txt'
    avg_mrr = 0.0
    done_files = [v for v in state['files'].values() if v['status'] == 'done' and v.get('mrr') is not None]
    if done_files:
        avg_mrr = sum(v['mrr'] for v in done_files) / len(done_files)
    msg = (f'[task:tq-qa-agent-acbf75] 서보 배치 완료\n'
           f'{done_count}/{TOTAL}건 완료\n'
           f'평균 MRR: {avg_mrr:.4f}\n'
           f'보고서: https://agent.mes-wta.com/api/files/batch_report_qa_servo.html')
    prog_path.write_text(msg, encoding='utf-8')
    log(f'[DONE] {msg}')


def generate_batch_report(state: dict):
    """HTML + JSON batch summary."""
    files_data = []
    for fi in TARGET_FILES:
        fid = fi['file_id']
        fst = state['files'].get(fid, {})
        files_data.append({
            'file_id': fid, 'model': fi['model'], 'mfr': fi['mfr'],
            'pages': fi['pages'], 'lang': fi['lang'],
            'status': fst.get('status', 'pending'),
            'chunks': fst.get('chunks', 0),
            'entities': fst.get('entities', 0),
            'relations': fst.get('relations', 0),
            'nodes': fst.get('nodes', 0),
            'mrr': fst.get('mrr'),
            'pass_fail': fst.get('pass_fail', '-'),
        })

    done = [f for f in files_data if f['status'] == 'done']
    err  = [f for f in files_data if 'err' in f['status']]
    skip = [f for f in files_data if 'skip' in f['status']]
    avg_mrr = sum(f['mrr'] for f in done if f['mrr'] is not None) / len(done) if done else 0.0
    total_nodes = sum(f['nodes'] for f in done)
    total_ents  = sum(f['entities'] for f in done)
    total_rels  = sum(f['relations'] for f in done)

    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')

    # JSON
    batch_json = {
        'task_id': 'tq-qa-agent-acbf75', 'team': TEAM, 'run_id': state.get('run_id', RUN_ID),
        'generated': now_str, 'total': TOTAL, 'done': len(done), 'errors': len(err),
        'skipped': len(skip), 'avg_mrr': round(avg_mrr, 4),
        'total_neo4j_nodes': total_nodes, 'total_entities_raw': total_ents,
        'total_relations_raw': total_rels, 'files': files_data,
    }
    BATCH_JSON.write_text(json.dumps(batch_json, ensure_ascii=False, indent=2), encoding='utf-8')

    # HTML
    rows = ''
    for f in files_data:
        mrr_str = f'{f["mrr"]:.4f}' if f['mrr'] is not None else '-'
        pf_color = '#27ae60' if f['pass_fail'] == 'PASS' else ('#e74c3c' if f['pass_fail'] == 'FAIL' else '#888')
        st_color = '#27ae60' if f['status'] == 'done' else ('#e74c3c' if 'err' in f['status'] else '#e67e22')
        rows += f'''<tr>
          <td style="font-size:11px">{f["file_id"][-12:]}</td>
          <td>{f["mfr"]}</td><td>{f["model"]}</td><td>{f["lang"]}</td>
          <td>{f["pages"]}</td><td>{f["chunks"]}</td>
          <td>{f["entities"]}</td><td>{f["relations"]}</td>
          <td>{f["nodes"]}</td>
          <td style="color:{pf_color};font-weight:bold">{mrr_str}</td>
          <td style="color:{st_color}">{f["status"]}</td>
        </tr>'''

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>4_servo 배치 보고서 — qa-agent</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;margin:0;background:#f5f5f5;color:#333}}
.header{{background:#1a252f;color:#fff;padding:28px 40px}}
.header h1{{margin:0;font-size:20px}}
.header .sub{{font-size:12px;color:#aaa;margin-top:6px}}
.container{{max-width:1200px;margin:30px auto;padding:0 20px}}
.card{{background:#fff;border-radius:8px;padding:24px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.card h2{{font-size:15px;margin:0 0 16px;color:#1a252f;border-bottom:2px solid #3498db;padding-bottom:8px}}
.kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px}}
.kpi{{flex:1;min-width:120px;background:#f8f9fa;border-radius:6px;padding:14px;text-align:center;border-left:4px solid #3498db}}
.kpi .value{{font-size:28px;font-weight:700;color:#3498db}}
.kpi .label{{font-size:11px;color:#888;margin-top:4px}}
.kpi.green{{border-color:#27ae60}}.kpi.green .value{{color:#27ae60}}
.kpi.orange{{border-color:#e67e22}}.kpi.orange .value{{color:#e67e22}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#1a252f;color:#fff;padding:7px 10px;text-align:left}}
td{{padding:7px 10px;border-bottom:1px solid #eee}}
tr:hover td{{background:#f8f9fa}}
.verdict{{font-size:14px;font-weight:700;padding:12px 16px;border-radius:6px;margin-top:12px}}
.verdict.pass{{background:#d5f5e3;color:#1e8449;border-left:4px solid #27ae60}}
.verdict.warn{{background:#fdebd0;color:#a04000;border-left:4px solid #e67e22}}
</style></head>
<body>
<div class="header">
  <h1>4_servo 배치 파이프라인 보고서 (SKILL.md v1.1)</h1>
  <div class="sub">qa-agent | {now_str} | task: tq-qa-agent-acbf75 | run_id: {state.get('run_id',RUN_ID)}</div>
</div>
<div class="container">

<div class="card">
  <h2>전체 요약</h2>
  <div class="kpi-row">
    <div class="kpi"><div class="value">{TOTAL}</div><div class="label">총 파일</div></div>
    <div class="kpi green"><div class="value">{len(done)}</div><div class="label">완료</div></div>
    <div class="kpi orange"><div class="value">{len(err)}</div><div class="label">오류</div></div>
    <div class="kpi"><div class="value">{len(skip)}</div><div class="label">스킵</div></div>
    <div class="kpi green"><div class="value">{avg_mrr:.4f}</div><div class="label">평균 MRR@5</div></div>
    <div class="kpi green"><div class="value">{total_nodes}</div><div class="label">Neo4j 노드</div></div>
    <div class="kpi green"><div class="value">{total_rels}</div><div class="label">총 관계</div></div>
  </div>
  <div class="verdict {'pass' if len(done) >= TOTAL * 0.9 else 'warn'}">
    {'배치 완료' if len(done) == TOTAL else f'{len(done)}/{TOTAL}건 처리'} — 평균 MRR {avg_mrr:.4f}
  </div>
</div>

<div class="card">
  <h2>파일별 결과 ({TOTAL}건)</h2>
  <table>
    <tr><th>file_id(끝12)</th><th>mfr</th><th>model</th><th>lang</th>
        <th>pages</th><th>chunks</th><th>ents</th><th>rels</th>
        <th>nodes</th><th>MRR</th><th>상태</th></tr>
    {rows}
  </table>
</div>

</div></body></html>"""

    BATCH_HTML.parent.mkdir(parents=True, exist_ok=True)
    BATCH_HTML.write_text(html, encoding='utf-8')
    log(f'[REPORT] {BATCH_HTML}')


if __name__ == '__main__':
    main()
