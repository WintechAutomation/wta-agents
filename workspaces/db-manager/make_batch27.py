import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch27 = [
  {
    "page_id": "9507157393",
    "title": "4-2-9-1. 케이스 관리 - 추가",
    "entities": [
      {"id": "proc_CaseAdd_4_2_9_1", "name": "케이스 관리 - 추가 (4-2-9-1)", "type": "Process", "properties": {
        "section": "4-2-9-1",
        "steps": [
          "메인화면에서 케이스 관리 선택",
          "케이스 추가",
          "이름 및 파라미터 설정 (원점 설정은 4-2-9-5 참고)",
          "저장"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507151954",
    "title": "-(한글 버전)- 4-2-9-2. 케이스 관리 - 수정",
    "entities": [
      {"id": "proc_CaseEditKO", "name": "케이스 관리 - 수정 (한글 4-2-9-2)", "type": "Process", "properties": {
        "section": "4-2-9-2", "language": "Korean",
        "steps": [
          "메인화면에서 케이스 관리 선택",
          "수정할 케이스 선택",
          "파라미터 수정 (이름 변경 시 해당 케이스 사용 모델도 변경 필요)",
          "저장"
        ],
        "caution": "케이스 이름 변경 시 해당 케이스를 사용하는 모델도 변경 필요"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507157459",
    "title": "4-2-9-2. 케이스 관리 - 수정",
    "entities": [
      {"id": "proc_CaseEdit_4_2_9_2", "name": "케이스 관리 - 수정 (4-2-9-2)", "type": "Process", "properties": {
        "section": "4-2-9-2",
        "steps": [
          "메인화면에서 케이스 관리 선택",
          "수정할 케이스 선택",
          "파라미터 수정 (이름 변경 시 모델도 변경 필요)",
          "저장"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507152010",
    "title": "-(한글 버전)- 4-2-9-3. 케이스 관리 - 삭제",
    "entities": [
      {"id": "proc_CaseDeleteKO", "name": "케이스 관리 - 삭제 (한글 4-2-9-3)", "type": "Process", "properties": {
        "section": "4-2-9-3", "language": "Korean",
        "steps": [
          "메인화면에서 케이스 관리 선택",
          "삭제할 케이스 선택",
          "삭제 실행"
        ],
        "caution": "삭제된 케이스는 복원 불가"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507152096",
    "title": "-(한글 버전)- 4-2-9-5. 케이스 관리 - 원점설정",
    "entities": [
      {"id": "proc_CaseOriginSetKO", "name": "케이스 관리 - 원점설정 (한글 4-2-9-5)", "type": "Process", "properties": {
        "section": "4-2-9-5", "language": "Korean",
        "steps": [
          "메인화면에서 케이스 관리 선택",
          "적재 설정에서 케이스 공급",
          "원점 설정할 케이스 선택",
          "케이스 원점 설정 실행",
          "자동운전 실행 → [예] 클릭",
          "중앙위치 설정 → [Yes] 클릭",
          "케이스 시작 Point 설정 (카메라를 시작점 중앙에 위치)",
          "케이스 종료 Point 설정 (카메라를 종료점 중앙에 위치)"
        ],
        "note": "Feeder1, Feeder2 각각 케이스 있는 상태에서 시작점/종료점 1개씩 설정 (총 4번)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507157601",
    "title": "4-2-9-5. 케이스 관리 - 원점설정",
    "entities": [
      {"id": "proc_CaseOriginSet_4_2_9_5", "name": "케이스 관리 - 원점설정 (4-2-9-5)", "type": "Process", "properties": {
        "section": "4-2-9-5",
        "steps": [
          "메인화면에서 케이스 관리 선택",
          "적재 설정에서 케이스 공급",
          "원점 설정할 케이스 선택",
          "케이스 원점 설정 실행",
          "자동운전 실행 → [예]",
          "중앙위치 설정 → [Yes]",
          "케이스 시작 Point 설정",
          "케이스 종료 Point 설정"
        ],
        "note": "Feeder1, Feeder2 각각 총 4번 설정"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9509144540",
    "title": "4. 에러 상황 조치 매뉴얼 - 미쯔비시 CVD #1",
    "entities": [
      {"id": "proc_ErrorHandleCVD1", "name": "에러 상황 조치 - 미쯔비시 CVD #1", "type": "Process", "properties": {
        "equipment": "미쯔비시 CVD #1",
        "steps": [
          "CVD 장비 정지",
          "CVD 장비 원점복귀 실행",
          "그리퍼에 물린 제품 제거",
          "화면 팔레트 적재 수량 확인 및 현재 수량과 일치시킴",
          "화면 트레이 수량 확인 및 현재 트레이 적재 수량과 일치시킴",
          "CVD 장비 재시작"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508934743",
    "title": "4. OPC UA 라이브러리",
    "entities": [
      {"id": "comp_OPCUALibrary", "name": "OPC UA .NET 라이브러리", "type": "Component", "properties": {
        "name_official": "OPC Foundation .NET Standard Library",
        "source": "OPC Foundation 공식 제공",
        "nuget": "OPCFoundation.NetStandard.Opc.Ua",
        "platform": ".NET Standard 2.0 이상, .NET Framework 및 .NET Core 모두 지원",
        "features": "서버/클라이언트 API, 보안/인증/암호화, OPC UA 핵심 기능 전체 지원",
        "pros": "공식 라이브러리 신뢰성/안정성, 크로스 플랫폼, 오픈소스",
        "lang": "C# 권장"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch27_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch27, f, ensure_ascii=False, indent=2)
for item in batch27:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch27)}')
