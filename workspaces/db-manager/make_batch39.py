import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch39 = [
  {
    "page_id": "9507144967",
    "title": "SideLaser",
    "entities": [
      {"id": "proc_PackingMachineSideLaserSetup", "name": "포장기 사이드 레이저 마킹 설정", "type": "Process", "properties": {
        "driver": "장치관리자에서 Laser Mark Control USB 연결 확인, 미연결 시 DECLaser 폴더 USB드라이버 설치",
        "software": "HMI 실행 중 CWaveWorker.exe 필수 실행. 세팅 테스트는 CWave.exe로 진행",
        "port_check": "CWaveWorker.exe Port No./IP Address == DeviceInfo.xml LASER 태그 설정값",
        "standby_pos": "대기 위치: X1 컨베이어 픽업 위치 동일하게 세팅",
        "x2_conv": "X2 컨베이어 적재 위치와 동일하게 세팅",
        "x1_gripper": "컨베이어 제품을 X1축이 픽업하는 위치 — X2/X1 그리퍼 간격 일치 필요",
        "conveyor_place": "팔레트에서 픽업한 두 제품을 컨베이어 벨트 중앙에 놓는 위치"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507147981",
    "title": "自動作業準備 - 道具準備 - DIJET包装機#1（日本語）",
    "entities": [
      {"id": "proc_AutoWorkPrepDIJET1_JP", "name": "자동 작업 준비 - 도구 준비 DIJET 포장기 #1 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "pallet_supply": "팔레트 공급부 도어 열기 → 팔레트 공급 (최대 15층) → 도어 닫기",
        "pallet_types": "10X10 / 5X10 / 6X6 Pallet",
        "case_supply": "Case Magazine 도어 열기 → 제품 크기 맞는 케이스 공급",
        "magazine_config": "Small Case 6개, Large Case 3개"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507148279",
    "title": "自動作業 - DIJET包装機#1（日本語）",
    "entities": [
      {"id": "proc_AutoWorkDIJET1_JP", "name": "자동 작업 - DIJET 포장기 #1 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "start": "메인화면 운전 시작 버튼",
        "stop_finish": "마무리 정지: 제품 공급 완료 후 정위치 정지",
        "stop_immediate": "즉시 정지: 현재 위치에서 즉시 정지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507148418",
    "title": "ティーチング作業 - DIJET包装機#1（日本語）",
    "entities": [
      {"id": "proc_TeachingWorkDIJET1_JP", "name": "티칭 작업 - DIJET 포장기 #1 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "steps": [
          "조명 밝기 설정 (제품 선명하게)",
          "생성 버튼 → 제품 모서리 시계/반시계 방향 클릭 → 완료",
          "원점 버튼 → X축 방향이 제품 날 방향으로 설정 → 등록",
          "잉크젯 사용 시 원점 X방향을 제품 형상 꼭지점 방향으로",
          "등록 후 제품 검출 이미지 확인, 팔레트 선 검출 시 마스킹 처리"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507148597",
    "title": "手動作業 - DIJET包装機#1（日本語）",
    "entities": [
      {"id": "proc_ManualWorkDIJET1_JP", "name": "수동 작업 - DIJET 포장기 #1 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "menu": "HMI 메인화면 → 적재설정 → 우측 하단 수동 작업 메뉴",
        "pallet_supply": "대기 중 팔레트를 작업 위치로 공급",
        "pallet_extract": "작업 위치 팔레트를 취출 위치로 이동",
        "case_supply": "Magazine → Feeder로 케이스 공급",
        "cover_assembly": "Feeder → 커버 조립 위치 이동 후 케이스 반전기로 취출"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507148890",
    "title": "パレット上でカメラとグリッパー間隔位置校正（日本語）",
    "entities": [
      {"id": "proc_PalletCamGripCalib_JP", "name": "팔레트 카메라-그리퍼 간격 교정 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "purpose": "팔레트 위에서 카메라와 그리퍼 간 거리 측정",
        "precondition": "원점복귀 → 그리퍼 공압 조정(0.1~0.2 MPa) → Head1 그리퍼에 지그 그립",
        "steps": [
          "메인화면 → 캘리브레이션 → 그리퍼/헤드/케이스 선택",
          "Top-1번 선택",
          "그리퍼 높이 티칭"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507149202",
    "title": "ケースの上でカメラとグリッパーの間の位置校正（日本語）",
    "entities": [
      {"id": "proc_CaseCamGripCalib_JP", "name": "케이스 카메라-그리퍼 간격 교정 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "purpose": "케이스 위에서 카메라와 그리퍼 간 거리 측정",
        "precondition": "원점복귀 → 케이스 수동 공급 및 반전 (FD1, FD2) → 공압 0.1~0.2 MPa 조정",
        "steps": [
          "메인화면 → 캘리브레이션 → 그리퍼/헤드/케이스 선택",
          "Top-4번 선택",
          "그리퍼 높이 티칭"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507149440",
    "title": "OKE 사용자 메뉴얼 (쥬쥬쫜스 버전에서 바뀐 부분)",
    "entities": [
      {"id": "manual_OKEUserManualUpdate", "name": "OKE 사용자 메뉴얼 (업데이트 변경사항)", "type": "Manual", "properties": {
        "description": "이전 쥬쥬쫜스 버전 대비 OKE 버전 변경사항"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch39_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch39, f, ensure_ascii=False, indent=2)
for item in batch39:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch39)}')
