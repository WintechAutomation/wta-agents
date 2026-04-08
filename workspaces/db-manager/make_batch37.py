import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch37 = [
  {
    "page_id": "9508983592",
    "title": "KUNBUS 사내 테스트",
    "entities": [
      {"id": "proc_KUNBUSInternalTest", "name": "KUNBUS 사내 테스트", "type": "Process", "properties": {
        "description": "KUNBUS Gateway EtherCAT 사내 테스트 절차",
        "hardware_note": "테스트 물품 위치: 제어팀"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507144690",
    "title": "Labeling",
    "entities": [
      {"id": "proc_Labeling_Overview", "name": "라벨링 작업 위치 설정 개요", "type": "Process", "properties": {
        "description": "라벨링 작업 위치 파라미터 개요"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508922777",
    "title": "원점 설정 매뉴얼 [Loading]",
    "entities": [
      {"id": "proc_LoadingHomeSetup", "name": "원점 설정 - Loading 축", "type": "Process", "properties": {
        "steps": [
          "WMXServer Motion Manager에서 X/CAMERA 축 Disable",
          "두 축 모두 (-) 방향으로 끝까지 밀기",
          "시스템 설정 → Hardware Org에서 해당 축 확인 버튼 → 즉시 적용",
          "Z축을 Motion Manager에서 1% 속도로 천천히 상승 → Limit 지점까지",
          "Hardware Org에서 Z축 확인 및 즉시 적용"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924274",
    "title": "작업위치 - [Loading 전용]",
    "entities": [
      {"id": "comp_LoadingWorkPositions", "name": "Loading 전용 작업 위치 파라미터", "type": "Component", "properties": {
        "description": "Loading 전용 작업 위치 파라미터 설정"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508931792",
    "title": "MDB 파일 Read시 조건식 데이터 에러관련",
    "entities": [
      {"id": "issue_MDBFileError", "name": "MDB 파일 조건식 데이터 에러 (일어/중국어 환경)", "type": "Issue", "properties": {
        "symptom": "윈도우 언어를 일본어/중국어로 변경 시 Inspection.mdb 읽기 오류 '조건식의 데이터 형식이 일치하지 않습니다.'",
        "cause": "mdb 파일의 날짜 형식 언어 불일치",
        "resolution": "중국 수출 장비의 Inspection.mdb 파일을 가져와 적용"
      }}
    ],
    "relations": [
      {"source": "issue_MDBFileError", "target": "issue_MDBFileError", "type": "RESOLVED_BY"}
    ]
  },
  {
    "page_id": "9508982499",
    "title": "MMC 테스트 내용",
    "entities": [
      {"id": "proc_MMCTest", "name": "MMC 테스트 (청소 프레스)", "type": "Process", "properties": {
        "limit_check": "청소 프레스 안에서 리미트 정확히 되는지 이동 확인",
        "movement_check": "금형툴 충분히 닦는 넓이 이동 확인 (25mm 지름)",
        "single_tool_total": "전수 측정 시 청소 후 버림 처리 → 이후 정상 측정 확인",
        "single_tool_intermit": "간헐 측정 시 청소 후 버림 처리 → 이후 정상 측정 확인",
        "no_discard_total": "버림 없는 전수 측정 정상 확인",
        "no_discard_intermit": "버림 없는 간헐 측정 정상 확인"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508916724",
    "title": "MXB2712 펌웨어 업데이트",
    "entities": [
      {"id": "proc_MXB2712FirmwareUpdate", "name": "MXB2712 펌웨어 업데이트", "type": "Process", "properties": {
        "equipment": "MXB2712",
        "description": "MXB2712 펌웨어 업데이트 절차"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508983250",
    "title": "측면 디버링(NEW) 교육 보고서",
    "entities": [
      {"id": "manual_SideDeburringNew", "name": "측면 디버링(NEW) 교육 보고서", "type": "Manual", "properties": {
        "contents": [
          "측면 디버링 구조 및 위치/구성/이동방향/원점",
          "환경 설정 및 파라미터 설정 방법",
          "기능 설정/해제/변경 방법",
          "티칭 방법 및 Jog 동작",
          "E-STOP 상태에서 연결 실패 조치",
          "브러시 교체 방법"
        ]
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch37_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch37, f, ensure_ascii=False, indent=2)
for item in batch37:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch37)}')
