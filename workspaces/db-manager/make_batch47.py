import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch47 = [
  {
    "page_id": "9508928636",
    "title": "(국문, OKE)- 5. 작업 순서",
    "entities": [
      {"id": "manual_OKEWorkOrder_KO", "name": "OKE 작업 순서 (5장, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "description": "OKE 장비 작업 순서 개요"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508929821",
    "title": "(국문, OKE)- 5-5. 수동 작업",
    "entities": [
      {"id": "proc_OKEManualWork_KO", "name": "OKE 수동 작업 (5-5, 국문)", "type": "Process", "properties": {
        "language": "Korean",
        "description": "각 작업 공정별 동작 테스트 수행 기능"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508930195",
    "title": "(국문, OKE)- 6. 에러 알람",
    "entities": [
      {"id": "manual_OKEErrorAlarm_KO", "name": "OKE 에러 알람 (6장, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "format": "No.□□□: 오류 메시지 형식 (3자리 에러 코드)",
        "error_codes": [
          "001: 프로그램 이미 실행 중 → 재실행 또는 PC 재부팅",
          "002: 운영이력 DB 파일 없음 → 윈텍오토메이션 문의",
          "027: 정보 손상 → 윈텍오토메이션 문의",
          "028: 정보 없음 → 윈텍오토메이션 문의",
          "128: 제어기 미연결 → MMI 재실행 또는 픽업 장치 메인 전원 리셋"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508930292",
    "title": "(국문, OKE)- 7. 유지보수",
    "entities": [
      {"id": "manual_OKEMaintenance_KO", "name": "OKE 유지보수 (7장, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "description": "OKE 장비 유지보수 목차"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508930303",
    "title": "(국문, OKE)- 7-1. 보수점검",
    "entities": [
      {"id": "manual_OKEInspection_KO", "name": "OKE 보수점검 (7-1, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "inspection_items": [
          "본체 외관: 상처/파손/변형 없을 것 (상시)",
          "이상 음: 기계적 이상 소음 없을 것 (상시)",
          "Air 압력 저하: Regulator 확인 및 청소 (상시)",
          "Pallet Feeder Unit 진동: Bolt 풀림/부품 마모 확인 (연 1회)",
          "Cableveyor 처짐/부하 확인 (연 1회)"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508930314",
    "title": "(국문, OKE)- 7-2. 보수 점검 요령",
    "entities": [
      {"id": "manual_OKEInspectionTips_KO", "name": "OKE 보수 점검 요령 (7-2, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "regulator_filter": "Air 필터 불순물 발생 시 Drain Cock으로 제거. 필터 엘리먼트 2년 또는 압력강하 0.1MPa 전 교환",
        "pneumatic_unit": "PISCO PAFR302-15A, PAF302D-15A"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508930952",
    "title": "(국문, OKE)- 7-3. 보수 부품",
    "entities": [
      {"id": "manual_OKESpareparts_KO", "name": "OKE 보수 부품 목록 (7-3, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "parts": [
          "Timing Belt S5M-25W-3300L(OPEN): Pallet Feeder Unit, 우양피엘텍",
          "Timing Belt HTBN320S5M-150: Pallet Feeder Unit, Misumi",
          "Timing Belt RPP8-L2100-W30(OPEN): Insert Transfer Unit, 우양피엘텍",
          "3 Jaw Gripper Pin Ø1.0 (50-01-04-0 x6): WTA",
          "3 Jaw Gripper Pin Ø0.8 (50-01-31-0 x6): WTA",
          "2 Jaw Gripper Pin 50-03-06-2 x4: WTA",
          "2 Jaw Gripper Pin 50-03-33-0 x2: WTA"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508931030",
    "title": "PVD 에러조치 사항 매뉴얼",
    "entities": [
      {"id": "manual_PVDErrorHandling", "name": "PVD 에러조치 사항 매뉴얼", "type": "Manual", "properties": {
        "equipment": "PVD",
        "description": "PVD 에러 발생 시 조치 사항 매뉴얼"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch47_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch47, f, ensure_ascii=False, indent=2)
for item in batch47:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch47)}')
