import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch35 = [
  {
    "page_id": "9507145988",
    "title": "DIJET 포장기 #1 작업 절차서",
    "entities": [
      {"id": "manual_DIJET1WorkProcedure", "name": "DIJET 포장기 #1 작업 절차서", "type": "Manual", "properties": {
        "equipment": "DIJET 포장기 #1",
        "description": "작업 절차서 목차 페이지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507147970",
    "title": "DIJET梱包機 #1 作業マニュアル書",
    "entities": [
      {"id": "manual_DIJET1WorkManualJP", "name": "DIJET 포장기 #1 작업 매뉴얼서 (일본어)", "type": "Manual", "properties": {
        "equipment": "DIJET 포장기 #1",
        "language": "Japanese",
        "description": "작업 매뉴얼서 목차 (일본어)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508933227",
    "title": "Domino",
    "entities": [
      {"id": "equip_Domino", "name": "Domino 잉크젯 마킹기", "type": "Equipment", "properties": {
        "manufacturer": "Domino",
        "description": "Domino 마킹기 관련 페이지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508978763",
    "title": "DX150P → MXB2712 교체 매뉴얼",
    "entities": [
      {"id": "proc_DX150P_MXB2712Replace", "name": "DX150P → MXB2712 교체 절차", "type": "Process", "properties": {
        "equipment_ref": "아크시스 프레스 1호기 기준",
        "reuse_items": "CMD 하네스(D-SUB 케이블), 이더켓 케이블(노란색 LAN), 전원선(파랑/초록 UL선)",
        "wiring": "전원: 1P/1N 24V, 접지. Up/Us 24V → 1P24, Up/Us 0V → 1N24, PE → PE_MXB2712",
        "steps": [
          "기존 DX150P 위치에 MXB2712 부착",
          "기존 자재 재사용 배선 연결",
          "신규 배선 추가 연결"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508919765",
    "title": "EZI SERVO 회전 방향 수정",
    "entities": [
      {"id": "proc_EZIServoRotationFix", "name": "EZI SERVO 회전 방향 수정", "type": "Process", "properties": {
        "steps": [
          "ECConfigurator 실행 → Advanced Funcs 진입 → 수정할 SERVO 클릭",
          "SDO Access Write: Index=607e, SubIndex=00, Size=1, Value=128(CW) 또는 0(CCW) → Write 클릭",
          "SDO Access Write: Index=1010, SubIndex=01, Size=4, Value=65766173 → Write 클릭 (설정 저장)"
        ],
        "value_CW": "128 (시계방향)",
        "value_CCW": "0 (반시계방향)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508919342",
    "title": "EZI SERVO E-STOP 설정",
    "entities": [
      {"id": "proc_EZIServoEStopSetup", "name": "EZI SERVO E-STOP 설정", "type": "Process", "properties": {
        "steps": [
          "ECConfigurator 실행 → Advanced Funcs 진입 → 수정할 SERVO 클릭",
          "SDO Access Write: Index=2040, SubIndex=02, Size=1, Value=1 → Write 클릭",
          "SDO Access Write: Index=1010, SubIndex=01, Size=4, Value=65766173 → Write 클릭 (저장)"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508917278",
    "title": "EZI SERVO II Plus-E 세팅 관련 매뉴얼",
    "entities": [
      {"id": "manual_EZIServoIIPlusE", "name": "EZI SERVO II Plus-E 세팅 매뉴얼", "type": "Manual", "properties": {
        "equipment": "EZI SERVO II Plus-E",
        "description": "EZI SERVO II Plus-E 세팅 매뉴얼 목차"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9509146098",
    "title": "#작업 위치 설정(F1 검사기)",
    "entities": [
      {"id": "proc_F1InspectorWorkPosSetup", "name": "작업 위치 설정 (F1 검사기)", "type": "Process", "properties": {
        "purpose": "장비 자동 운전 시 각 동작의 기본 위치 설정",
        "method": "해당 위치로 축 이동 → [READ] 버튼 → [SAVE] 버튼",
        "note": "코드에서 사용 위치 확인 후 작업. 비슷한 장비 코드 복사 시 미사용 위치 포함될 수 있으므로 코드 확인 필수"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch35_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch35, f, ensure_ascii=False, indent=2)
for item in batch35:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch35)}')
