import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch46 = [
  {
    "page_id": "9508927486",
    "title": "(국문, OKE)- 4-2-4. 환경설정",
    "entities": [
      {"id": "manual_OKEConfig_KO", "name": "OKE 환경설정 화면 (4-2-4, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "sections": [
          "기본 작업 설정: 기본 속도 및 동작 파라미터",
          "케이스 파라미터 설정",
          "팔레트 작업 설정",
          "취출 파라미터 설정"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508927551",
    "title": "(국문, OKE)- 4-2-6. 입출력",
    "entities": [
      {"id": "manual_OKEIO_KO", "name": "OKE 입출력 화면 (4-2-6, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "features": [
          "번호 보기: 전장 넘버링으로 표시 전환",
          "분류: 유닛별 입출력 표시",
          "입력 모니터: 입력 상태 모니터링",
          "출력 모니터: 출력 상태 모니터링 및 제어 (파손 가능성 없는 상태에서만)",
          "입출력 반복 동작 테스트: 간단한 시퀀스 반복 구동"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508927666",
    "title": "(국문, OKE)- 4-2-7. 운영 이력",
    "entities": [
      {"id": "manual_OKEOperationHistory_KO", "name": "OKE 운영 이력 화면 (4-2-7, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "features": [
          "기간 설정: 검색 기간 설정",
          "기록 타입 선택",
          "검색/저장",
          "검색 결과 리스트 및 그래프 형태 표시"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508927776",
    "title": "(국문, OKE)- 4-2-8. 캘리브레이션",
    "entities": [
      {"id": "manual_OKECalibration_KO", "name": "OKE 캘리브레이션 화면 (4-2-8, 국문)", "type": "Manual", "properties": {
        "language": "Korean",
        "purpose": "카메라와 그리퍼 위치 교정. 그리퍼 픽업/케이스 적재 문제 발생 시 필요",
        "features": [
          "항목 선택: 그리퍼/HEAD/CASE",
          "팔레트/케이스 캘리브레이션",
          "카메라 라이브: 비전 카메라 라이브 화면",
          "캘리브레이션 실행 상태 실시간 표시"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508927802",
    "title": "(국문, OKE)- 4-2-8-1. 팔레트에서 카메라와 그리퍼간 위치 보정",
    "entities": [
      {"id": "proc_OKEPalletCamGripCalib_KO", "name": "OKE 팔레트 카메라-그리퍼 위치 보정 (4-2-8-1, 국문)", "type": "Process", "properties": {
        "language": "Korean",
        "equipment": "캘리브레이션 지그 2개, 캘리브레이션 플레이트",
        "steps": [
          "원점 복귀",
          "캘리브레이션 화면 → HEAD1 → HEAD2 전환",
          "START 버튼으로 TP 실행 → X2G1/X2G2 그립 상태로 변경",
          "그리퍼 공압 확인 (0.1~0.2 MPa)",
          "캘리브레이션 지그 2개 그립",
          "On the Pallet 버튼 클릭"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508927963",
    "title": "(국문, OKE)- 4-2-8-2. HEAD1, HEAD2간 위치 보정",
    "entities": [
      {"id": "proc_OKEHeadCalib_KO", "name": "OKE HEAD1-HEAD2 위치 보정 (4-2-8-2, 국문)", "type": "Process", "properties": {
        "language": "Korean",
        "note": "현재 미사용 기능"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508928022",
    "title": "(국문, OKE)- 4-2-8-4. 케이스에서의 카메라와 그리퍼간 위치 보정",
    "entities": [
      {"id": "proc_OKECaseCamGripCalib_KO", "name": "OKE 케이스 카메라-그리퍼 위치 보정 (4-2-8-4, 국문)", "type": "Process", "properties": {
        "language": "Korean",
        "equipment": "캘리브레이션 지그 2개, 캘리브레이션 플레이트",
        "steps": [
          "원점 복귀",
          "케이스 공급 (바닥면이 보이도록 뒤집어 넣기)",
          "캘리브레이션 화면 진입",
          "HEAD → HEAD1 설정",
          "START 버튼 TP 실행 → X1G1/X2G2 그립 상태로 변경",
          "그리퍼 공압 0.1~0.2 MPa 확인"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508928175",
    "title": "(국문, OKE)- 4-2-8-5. 캘리브레이션 비전 티칭 방법",
    "entities": [
      {"id": "proc_OKEVisionTeaching_KO", "name": "OKE 캘리브레이션 비전 티칭 (4-2-8-5, 국문)", "type": "Process", "properties": {
        "language": "Korean",
        "steps": [
          "조명 조정 → JIG 비전 패턴 설정",
          "패턴1 클릭 → [R](Round) 클릭",
          "하늘색 원 드래그로 JIG보다 약간 크게 조정",
          "원점 클릭 → X,Y축(ㄴ 모양)이 원 가운데 위치 확인",
          "등록 버튼 → 이미지 생성 확인",
          "검출 버튼 → Score 점수 표시 확인",
          "저장 버튼 → 비전 티칭 종료"
        ]
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch46_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch46, f, ensure_ascii=False, indent=2)
for item in batch46:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch46)}')
