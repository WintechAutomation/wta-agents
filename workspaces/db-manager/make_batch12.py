import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch12 = [
  {
    "page_id": "9508928330",
    "title": "(국문, OKE)- 4-2-9-1. 케이스 관리 - 추가",
    "entities": [
      {"id": "proc_CaseAddOKE", "name": "케이스 추가 (OKE 4-2-9-1)", "type": "Process", "properties": {"section": "4-2-9-1", "customer": "OKE"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508933734",
    "title": "Zebra Label Printer (신형프린터) 업체용 Manual",
    "entities": [
      {"id": "proc_ZebraNewConfig", "name": "Zebra 신형 프린터 설정", "type": "Process", "properties": {
        "steps": "홈 메뉴 버튼 → OK(설정) → 어둡기(글씨 진함) 조정 → 인쇄 속도 조정 → 티어 오프 조정",
        "note": "인쇄 속도 너무 빠르면 글씨 불명확"
      }},
      {"id": "equip_ZebraNewPrinter", "name": "Zebra 신형 라벨 프린터", "type": "Equipment", "properties": {"manufacturer": "Zebra", "type": "신형 라벨 프린터"}}
    ],
    "relations": [
      {"source": "proc_ZebraNewConfig", "target": "equip_ZebraNewPrinter", "type": "MAINTAINS"}
    ]
  },
  {
    "page_id": "9508927728",
    "title": "(국문, OKE)- 4-2-7-2. 운영 이력 - 저장",
    "entities": [
      {"id": "proc_OpHistorySave", "name": "운영 이력 저장 (OKE 4-2-7-2)", "type": "Process", "properties": {"section": "4-2-7-2", "customer": "OKE"}}
    ],
    "relations": []
  },
  {
    "page_id": "9507152786",
    "title": "-(한글 버전)- 5-2. 자동 작업 준비",
    "entities": [
      {"id": "proc_AutoWorkPrepKO", "name": "자동 작업 준비 (한글)", "type": "Process", "properties": {"section": "5-2", "language": "Korean"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508928396",
    "title": "(국문, OKE)- 4-2-9-2. 케이스 관리 - 수정",
    "entities": [
      {"id": "proc_CaseEditOKE", "name": "케이스 수정 (OKE 4-2-9-2)", "type": "Process", "properties": {"section": "4-2-9-2", "customer": "OKE"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508980154",
    "title": "#기본 C타입 픽업/적재 테스트 (Vac툴, 2Jaw툴, 특수툴)",
    "entities": [
      {"id": "proc_CTypePickupTest", "name": "C타입 픽업/적재 테스트", "type": "Process", "properties": {
        "description": "기본 적재 작업 가능 여부 테스트",
        "prep": "C12 인서트 준비 + 모델 설정에서 카본 플레이트/인서트 형상 확인"
      }},
      {"id": "comp_CTypeToolConfig", "name": "C타입 툴 설정", "type": "Component", "properties": {
        "2jaw": "작업 그리퍼 → 2 jaw그립 반전 기능 → OFF (ON = MGT 테스트 전용)",
        "vacuum": "작업 그리퍼 → Vacuum"
      }},
      {"id": "comp_C12Insert", "name": "C12 인서트 (테스트 소재)", "type": "Component", "properties": {"purpose": "C타입 픽업 테스트 소재"}}
    ],
    "relations": [
      {"source": "proc_CTypePickupTest", "target": "comp_CTypeToolConfig", "type": "INVOLVES_COMPONENT"},
      {"source": "proc_CTypePickupTest", "target": "comp_C12Insert", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507159203",
    "title": "5-5-2. 케이스 공급",
    "entities": [
      {"id": "proc_CaseSupply_5_5_2", "name": "케이스 공급 5-5-2", "type": "Process", "properties": {"section": "5-5-2"}}
    ],
    "relations": []
  },
  {
    "page_id": "9507159419",
    "title": "5-5-5. 라벨링",
    "entities": [
      {"id": "proc_Labeling_5_5_5", "name": "라벨링 5-5-5", "type": "Process", "properties": {
        "section": "5-5-5",
        "steps": "적재설정 선택 → 제품 추가 → 케이스 공급 → 라벨링 실행 → 완료(케이스 배출 위치 적재)"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch12_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch12, f, ensure_ascii=False, indent=2)
for item in batch12:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch12)}')
