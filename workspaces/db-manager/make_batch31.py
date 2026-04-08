import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch31 = [
  {
    "page_id": "9507159569",
    "title": "7. 유지보수",
    "entities": [
      {"id": "proc_Maintenance_7", "name": "유지보수 (7)", "type": "Process", "properties": {
        "section": "7",
        "description": "장비 유지보수 절차 개요"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153758",
    "title": "-(한글 버전)- 7-1. 보수점검",
    "entities": [
      {"id": "proc_MaintenanceCheckKO2", "name": "보수점검 (한글 7-1)", "type": "Process", "properties": {
        "section": "7-1", "language": "Korean",
        "description": "부품 및 자재의 장기 트러블 방지를 위한 보수점검 및 소모품 교환 설명",
        "check_types": "상시 점검 / 월별 정기 / 년별 정기",
        "check_body": "외관(상처/파손/변형 없을 것) — 상시",
        "check_noise": "기계적 이상 소음 없을 것 — 상시"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507159580",
    "title": "7-1. 보수점검",
    "entities": [
      {"id": "proc_MaintenanceCheck_7_1", "name": "보수점검 (7-1)", "type": "Process", "properties": {
        "section": "7-1",
        "description": "부품 및 자재 보수점검 및 소모품 교환",
        "check_types": "상시 / 월별 / 년별",
        "check_body": "외관 이상 없을 것 — 상시",
        "check_noise": "이상 소음 없을 것 — 상시"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507159591",
    "title": "7-2. 보수 점검 요령",
    "entities": [
      {"id": "proc_MaintenanceTips_7_2", "name": "보수 점검 요령 (7-2)", "type": "Process", "properties": {
        "section": "7-2",
        "regulator_filter": "Air 필터 불순물 발생 시 Drain Cock 눌러 제거 또는 탈착 후 제거",
        "filter_replace": "필터 엘리먼트 교환 주기: 사용 후 2년 또는 압력 강하 발생 시",
        "note": "보수 부품은 7-3 보수부품 참조"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153913",
    "title": "-(한글 버전)- 7-3. 보수 부품",
    "entities": [
      {"id": "comp_SpareParts_KO", "name": "보수 부품 목록 (한글 7-3)", "type": "Component", "properties": {
        "section": "7-3", "language": "Korean",
        "reject_conveyor_belt": "HTBN230S5M-100 (Misumi)",
        "reject_belt2": "TT12BK-60W-2070L (우양피엘텍)",
        "insert_transfer_belt": "RPP8-L3300-W30(OPEN) x2 (우양피엘텍)",
        "gripper_cylinder": "CHM08BC03C x12 (Pisco)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507160000",
    "title": "7-3. 보수 부품",
    "entities": [
      {"id": "comp_SpareParts_7_3", "name": "보수 부품 목록 (7-3)", "type": "Component", "properties": {
        "section": "7-3",
        "conveyor_timing_belt1": "HTUN276S3M-100 (Misumi)",
        "conveyor_timing_belt2": "S5M-110W-1000L(OPEN) (우양피엘텍)",
        "insert_transfer_belt1": "RPP8-L1700-W30(OPEN) (우양피엘텍)",
        "insert_transfer_belt2": "RPP8-L2700-W30(OPEN) (우양피엘텍)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508981494",
    "title": "AGV",
    "entities": [
      {"id": "equip_AGV_Overview", "name": "AGV (자동 운반 장치) 개요", "type": "Equipment", "properties": {
        "description": "AGV 장비 개요 페이지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508981483",
    "title": "물류 위치 (AGV 세팅 방법 포함)",
    "entities": [
      {"id": "proc_AGVPositionSetup", "name": "물류 위치 및 AGV 세팅", "type": "Process", "properties": {
        "description": "AGV 세팅 방법 포함 물류 위치 설정"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch31_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch31, f, ensure_ascii=False, indent=2)
for item in batch31:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch31)}')
