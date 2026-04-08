import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch20 = [
  {
    "page_id": "9508980199",
    "title": "#(제품) MGT 플레이트 적재 테스트(2Jaw)",
    "entities": [
      {"id": "proc_MGTPlateLoadTest", "name": "MGT 플레이트 적재 테스트 (2Jaw)", "type": "Process", "properties": {
        "steps": [
          "MGT 인서트 및 MGT용 플레이트 준비 — 플레이트 MGT홈 사이 간격 확인(실측 또는 설계팀 문의)",
          "HMI에서 MGT 적재용 신규 모델 생성 (카본 플레이트 형상, 적재 간격 설정)",
          "세로 간격 공식: (플레이트 세로길이 - 가장자리여백*2 - 제품두께*줄수) / (줄수-1)",
          "그리퍼 설정: 그립 반전 기능(MGT) ON, 속도 충분히 낮게",
          "티칭 설정 → Offset으로 적재 위치 미세조정",
          "조정 불가 시 높이 센서(레이저) 활용 또는 2Jaw 툴로 X축 직진도 확인"
        ],
        "correct_angle": "플레이트 틀어짐 시 SystemData.CorrectAngle 보정 (대부분 1 미만)",
        "interval_fix": "간격 너무 넓어 설정 불가 시 WinplacerGraphic 속성→빌드→조건부 Mytest 입력"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9509142916",
    "title": "Middle Plate 작업 위치",
    "entities": [
      {"id": "comp_MiddlePlatePositions", "name": "Middle Plate 작업 위치 파라미터", "type": "Component", "properties": {
        "H1X_place": "MIDDLE_PLACE (Pallet 탭) — H1X축 반전부 제품 적재 위치",
        "H1X_y": "TURN_FD — 반전부 적재 Y 위치",
        "H1X_z": "반전부 적재 시 H1 그리퍼 높이",
        "H2X_place": "MIDDLE_PLACE (Tray 탭) — H2X축 제품 픽업 위치(홀 정가운데)",
        "H2X_y": "TURN_FD — 반전부 픽업 Y 위치",
        "H2X_z": "픽업 그리퍼 높이",
        "vertical_load_x": "반전부 Tilting 후 H2 픽업 위치 X",
        "h1_wait": "H2 반전부 작업 중 충돌 방지 H1 대기 위치",
        "h2_wait": "H1 반전부 작업 중 충돌 방지 H2 대기 위치"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507149128",
    "title": "ケース原点設定（日本語）",
    "entities": [
      {"id": "proc_CaseOriginSetJP", "name": "케이스 원점 설정 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "purpose": "케이스에 제품을 넣는 포켓 원점 설정",
        "precondition": "장비 원점복귀, 케이스 수동 공급 (FD1, FD2)",
        "method": "Head/케이스 선택 → Top-3번 → 비전 티칭",
        "10pocket": "케이스 1,2번 포켓 원점 설정 (조명 조정 후 포켓 중심에 카메라 중심 맞춤, 4회)",
        "2pocket": "동일 방법, 4회",
        "restore": "설정 후 케이스 수동 취출 및 레일에서 제거"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508929334",
    "title": "(국문, OKE)- 5-4. 티칭 작업",
    "entities": [
      {"id": "proc_TeachingOKE", "name": "티칭 작업 (OKE 5-4)", "type": "Process", "properties": {
        "section": "5-4", "customer": "OKE",
        "description": "제품에 따라 Vision 검출 설정 및 위치 조정 설정 진행"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508920384",
    "title": "[PVD_언로딩] 작업 가능 조건",
    "entities": [
      {"id": "comp_PVDUnloadingConditions", "name": "PVD 언로딩 작업 가능 조건", "type": "Component", "properties": {
        "gripper_condition": "G1 제품 그립 조건, PG 제품 그립 조건",
        "inverter_condition": "반전기 작업 조건",
        "spring_condition": "스프링 길이 조건",
        "pattern_condition": "패턴 3가지 조건 모두 충족 시 정상 작업 가능",
        "tolerance": "막대 외경과 스프링 내경 사이 공차 제한",
        "jam_issue": "제품과 스프링 끼임 현상 주의"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508933316",
    "title": "Zebra Label Printer Language & IP Setting (中國語)",
    "entities": [
      {"id": "proc_ZebraIPSetupCN", "name": "Zebra 라벨 프린터 언어/IP 설정 (중국어)", "type": "Process", "properties": {
        "language": "Chinese",
        "lang_setup": "SETUP.EXIT → [◀] 버튼으로 언어 선택 → [+]/[-]로 변경 → SETUP.EXIT+[▶] 저장",
        "ip_fixed": "SETUP.EXIT → [◀] IP설정 → [+] 비밀번호 입력(1234) → 永久(영구) 설정",
        "ip_change_steps": "SETUP.EXIT → [◀] IP설정 → 비밀번호 1234 → IP 입력(010.000.000.220) → 서브넷(255.255.255.000) → 게이트웨이(10.000.000.001) → 저장"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508979222",
    "title": "#HMI의 선정과 코드 빌드",
    "entities": [
      {"id": "proc_HMISelectionAndBuild", "name": "HMI 선정 및 코드 빌드", "type": "Process", "properties": {
        "backup_first": "VNC Viewer로 WLauncher/WMI/WMXServer 날짜 폴더로 백업 (WMXServer는 제어팀 담당)",
        "hmi_select_criteria": "장비 타입(컨베이어/엘리베이터), 연동 장비 인터페이스(고바야시/오스트발더/도르스트)",
        "backup_path": "\\\\192.168.1.253\\Project\\1. Project - HMI\\01 Press",
        "apply_path": "D:/WintechAutomation → 동일 폴더 덮어쓰기",
        "code_conveyor": "CNOKEPRS0015 (2단 컨베이어 타입)",
        "code_elevator": "CNHRYPRS1019 (엘리베이터 타입)",
        "build_steps": [
          "주의사항.txt에서 조건부 컴파일 기호값 확인",
          "WMI 속성-빌드: 조건부 컴파일 기호 입력, 출력경로 입력 (\\\\10.0.0.150\\WintechAutomation\\WMI\\)",
          "WMI 속성-디버그: 원격 연결 IP 입력 (전 장비 공통 10.0.0.150)",
          "WMI/BaseLibrary 대상 프레임워크 .NET 4.6 확인",
          "원격 디버거 실행 (D:/WintechAutomation/Setup/17. Remote Debugger/2019/x64)",
          "참조 라이브러리 먼저 빌드 → WMI 빌드 및 F5 실행"
        ],
        "slave_ng_fix": "WLauncher Config.csv Param 개수를 WMXServer EcConfigurator에서 확인 후 변경"
      }},
      {"id": "comp_WLauncherConfigCSV", "name": "WLauncher Config.csv", "type": "Component", "properties": {
        "issue": "SLAVE NG 시 Param 개수 불일치 → WMXServer EcConfigurator 확인 후 수정"
      }}
    ],
    "relations": [
      {"source": "proc_HMISelectionAndBuild", "target": "comp_WLauncherConfigCSV", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507147897",
    "title": "에러 상황 조치 - DIJET 포장기 #1",
    "entities": [
      {"id": "proc_ErrorHandlingDIJET1", "name": "에러 상황 조치 - DIJET 포장기 #1", "type": "Process", "properties": {
        "lot_mismatch": "운전 시작 시 Lot 수량 불일치 → 예: Lot 수량 재설정 / 아니오: 자동운전 정지",
        "error_reset_steps": [
          "HMI 원점복귀",
          "라벨쪽 케이스 및 흡착 라벨 모두 제거",
          "피더축 양끝 케이스 4개 제거",
          "적재 설정 메뉴 → 작업중 케이스 취출 → 취출된 제품 검출쪽 케이스 2개 제거 (제품 있으면 팔레트에 적재)",
          "팔레트 취출 버튼 → 취출 후 팔레트 공급부로 이동",
          "케이스 커버 공급부 케이스 제거",
          "그리퍼에 픽업된 제품 제거"
        ]
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch20_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch20, f, ensure_ascii=False, indent=2)
for item in batch20:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch20)}')
