import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch28 = [
  {
    "page_id": "9509145780",
    "title": "4. エラー措置マニュアル (미쯔비시 CVD 일본어)",
    "entities": [
      {"id": "proc_ErrorHandleCVD1JP", "name": "에러 조치 매뉴얼 미쯔비시 CVD (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "steps": [
          "장비 정지",
          "원점복귀 실행",
          "그리퍼가 제품 픽업 상태 시 제품 취출",
          "화면 팔레트 적재 수량과 실제 수량 확인 및 일치시킴",
          "화면 트레이 수량과 실제 적재 수량 확인 및 일치시킴",
          "운전 재개"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507152194",
    "title": "-(한글 버전)- 5. 작업 순서",
    "entities": [
      {"id": "proc_WorkOrderKO", "name": "작업 순서 (한글 5)", "type": "Process", "properties": {
        "section": "5", "language": "Korean",
        "description": "자동 작업 순서 개요 페이지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153924",
    "title": "한국야금 포장 5호기 사용자 메뉴얼",
    "entities": [
      {"id": "manual_KoriaMetalPkg5", "name": "한국야금 포장 5호기 사용자 메뉴얼", "type": "Manual", "properties": {
        "customer": "한국야금",
        "equipment": "포장 5호기",
        "description": "한국야금 포장 5호기 사용자 메뉴얼 목차 페이지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507158017",
    "title": "5. 작업 순서",
    "entities": [
      {"id": "proc_WorkOrder_5", "name": "작업 순서 (5)", "type": "Process", "properties": {
        "section": "5",
        "description": "자동 작업 순서 개요"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508934768",
    "title": "5. 테스트 환경 구축",
    "entities": [
      {"id": "proc_OPCUATestEnvSetup", "name": "OPC UA 테스트 환경 구축", "type": "Process", "properties": {
        "sdk_source": "OPC UA Development - Unified Automation (unified-automation.com)",
        "downloads": [
          "NET based OPC UA Client/Server/PubSub SDK Bundle v4.0.1",
          "UaModeler (OPC UA 모델 설계 도구)",
          "UaExpert (클라이언트 도구)",
          "OPC UA C++ Demo Server"
        ],
        "steps": [
          "4개 파일 다운로드 → 압축 해제 후 설치 (OS 환경에 맞게)",
          "UA Demo Server 실행 → URL 더블클릭으로 Server URL 확인",
          "UaExpert 실행"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507152205",
    "title": "-(한글 버전)- 5-1. 자동 작업 준비 - 도구 준비",
    "entities": [
      {"id": "proc_AutoWorkPrepToolsKO", "name": "자동 작업 준비 - 도구 준비 (한글 5-1)", "type": "Process", "properties": {
        "section": "5-1", "language": "Korean",
        "steps": [
          "팔레트 공급 위치에 작업 팔레트 공급",
          "케이스 공급 위치에 케이스 공급",
          "커버 공급 위치에 커버 공급",
          "라벨기에 라벨 공급",
          "그리퍼 확인 및 장착",
          "잉크젯 마킹기 소모품 및 시작 상태 확인"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507158028",
    "title": "5-1. 자동 작업 준비 - 도구 준비",
    "entities": [
      {"id": "proc_AutoWorkPrepTools_5_1", "name": "자동 작업 준비 - 도구 준비 (5-1)", "type": "Process", "properties": {
        "section": "5-1",
        "steps": [
          "팔레트 공급 위치에 작업 팔레트 공급",
          "케이스 공급 위치에 케이스 공급",
          "커버 공급 위치에 커버 공급",
          "라벨기에 라벨 공급",
          "그리퍼 확인 및 장착",
          "잉크젯 마킹기 소모품 및 시작 상태 확인"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507152334",
    "title": "-(한글 버전)- 5-1-1. 팔레트 준비",
    "entities": [
      {"id": "proc_PalletPrepKO", "name": "팔레트 준비 (한글 5-1-1)", "type": "Process", "properties": {
        "section": "5-1-1", "language": "Korean",
        "steps": [
          "팔레트 공급 위치로 이동",
          "팔레트를 표시 위치에 공급 (최대 15단)"
        ],
        "max_stack": "15단"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch28_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch28, f, ensure_ascii=False, indent=2)
for item in batch28:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch28)}')
