import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch30 = [
  {
    "page_id": "9507158715",
    "title": "5-4. 티칭 작업",
    "entities": [
      {"id": "proc_TeachingWork_5_4", "name": "티칭 작업 (5-4)", "type": "Process", "properties": {
        "section": "5-4",
        "description": "제품에 따라 Vision 검출 설정 및 위치 조정 설정 진행"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153139",
    "title": "-(한글 버전)- 5-4-3. 수량 검사",
    "entities": [
      {"id": "proc_QtyInspectionKO", "name": "수량 검사 Vision 설정 (한글 5-4-3)", "type": "Process", "properties": {
        "section": "5-4-3", "language": "Korean",
        "steps": [
          "조명 밝기 설정 (제품 선명하게 보이도록)",
          "패턴 버튼 클릭 → 생성 버튼 → 포인트 클릭 추가 (시계방향으로 작성)",
          "원점 버튼 클릭",
          "등록 버튼으로 패턴 등록",
          "검출 버튼으로 정상 검출 확인",
          "다중 패턴 필요 시 + 버튼으로 추가 패턴 등록",
          "저장"
        ],
        "note": "포인트는 반드시 시계방향으로 작성"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507158962",
    "title": "5-4-3. 수량 검사",
    "entities": [
      {"id": "proc_QtyInspection_5_4_3", "name": "수량 검사 Vision 설정 (5-4-3)", "type": "Process", "properties": {
        "section": "5-4-3",
        "steps": [
          "조명 밝기 설정",
          "패턴 생성 → 포인트 시계방향 추가",
          "원점 설정",
          "등록",
          "검출 테스트",
          "다중 패턴 필요 시 + 버튼으로 추가 등록",
          "저장"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153275",
    "title": "-(한글 버전)- 5-5. 수동 작업",
    "entities": [
      {"id": "proc_ManualWorkKO", "name": "수동 작업 (한글 5-5)", "type": "Process", "properties": {
        "section": "5-5", "language": "Korean",
        "description": "각 작업 공정별 동작 테스트 수행 기능"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507159098",
    "title": "5-5. 수동 작업",
    "entities": [
      {"id": "proc_ManualWork_5_5", "name": "수동 작업 (5-5)", "type": "Process", "properties": {
        "section": "5-5",
        "description": "각 작업 공정별 동작 테스트 수행"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153649",
    "title": "-(한글 버전)- 6. 에러 알람",
    "entities": [
      {"id": "comp_HMIErrorAlarmKO", "name": "HMI 에러 알람 코드 (한글 6)", "type": "Component", "properties": {
        "section": "6", "language": "Korean",
        "format": "No.□□□ : 오류 메시지 (3자리 에러 코드)",
        "err_001": "프로그램 이미 실행 중 → 재실행 또는 PC 재부팅",
        "err_002": "운영이력 DB 파일 없음 → 윈텍오토메이션 문의",
        "err_027": "정보 손상 → 윈텍오토메이션 문의",
        "err_028": "정보 없음 → 윈텍오토메이션 문의",
        "err_128": "제어기 미연결 → MMI 재실행 또는 메인 전원 리셋",
        "err_132": "I/O 설정 미완료 → 윈텍오토메이션 문의",
        "err_145": "메인 도어 열림 → 도어 닫고 실행",
        "err_221": "제품 검출 실패 → Vision 설정 확인/재설정",
        "err_2001_2002": "팔레트 잠금/해지 실패 → 클램핑 실린더 및 팔레트 적재 상태 확인",
        "err_2003_2004": "팔레트 상승/하강 실패 → 실린더 동작 및 팔레트 상태 확인",
        "err_2010_2011": "팔레트 공급/취출 실패 → 팔레트 감지 센서 상태 확인",
        "err_2013": "공급할 팔레트 없음 → 저장소에 팔레트 공급",
        "err_2014": "취출 팔레트 저장소 만재 → 저장소 팔레트 제거"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507159472",
    "title": "6. 에러 알람",
    "entities": [
      {"id": "comp_HMIErrorAlarm_6", "name": "HMI 에러 알람 코드 (6)", "type": "Component", "properties": {
        "section": "6",
        "format": "No.□□□ : 오류 메시지 (3자리)",
        "err_001": "프로그램 이미 실행 중 → 재실행/PC 재부팅",
        "err_002": "운영이력 DB 없음 → 윈텍오토메이션 문의",
        "err_128": "제어기 미연결 → MMI 재실행/메인 전원 리셋",
        "err_145": "메인 도어 열림 → 도어 닫고 실행",
        "err_221": "제품 검출 실패 → Vision 설정 확인",
        "err_2001_2002": "팔레트 잠금/해지 실패",
        "err_2013": "공급 팔레트 없음 → 팔레트 공급",
        "err_2014": "취출 저장소 만재 → 팔레트 제거"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153747",
    "title": "-(한글 버전)- 7. 유지보수",
    "entities": [
      {"id": "proc_MaintenanceKO", "name": "유지보수 (한글 7)", "type": "Process", "properties": {
        "section": "7", "language": "Korean",
        "description": "장비 유지보수 절차 개요"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch30_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch30, f, ensure_ascii=False, indent=2)
for item in batch30:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch30)}')
