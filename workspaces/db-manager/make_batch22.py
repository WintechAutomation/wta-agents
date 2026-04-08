import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch22 = [
  {
    "page_id": "9508928918",
    "title": "(국문, OKE)- 5-1-4. 라벨 공급",
    "entities": [
      {"id": "proc_LabelSupplyOKE", "name": "라벨 공급 (OKE 5-1-4)", "type": "Process", "properties": {
        "section": "5-1-4", "customer": "OKE",
        "steps": [
          "라벨 공급 위치 이동",
          "컨베어 하단 레버 당겨 해제",
          "컨베어 90도 이동",
          "컨베어 위 도어 오픈",
          "라벨기를 라벨 공급 수월한 위치로 이동 (고정 레버 조작)",
          "일반 라벨 또는 봉인 라벨 교체"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508929581",
    "title": "(국문, OKE)- 5-4-3. 수량 검사",
    "entities": [
      {"id": "proc_QtyInspectionOKE", "name": "수량 검사 (OKE 5-4-3)", "type": "Process", "properties": {
        "section": "5-4-3", "customer": "OKE",
        "steps": [
          "조명 밝기 설정",
          "제품 패턴 설정 (패턴 생성 → 포인트 시계방향 추가)",
          "원점 설정",
          "등록",
          "검출 테스트",
          "다중 패턴 필요 시 + 버튼으로 추가 패턴 등록",
          "저장"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9509142733",
    "title": "Pallet 작업 위치",
    "entities": [
      {"id": "comp_PalletWorkPositions", "name": "Pallet 작업 위치 파라미터", "type": "Component", "properties": {
        "calib_pos": "WORKING_ORG - 20 (팔레트 상부 카메라 캘리브레이션 시)",
        "extract_pallet": "PALLET축 취출부 가이드 진입 위치",
        "extract_palz": "팔레트 공급 상태에서 4개 렛치 정상 복귀 높이",
        "load_pallet": "PALLET축 공급부 가이드 진입 위치",
        "load_palz": "팔레트가 들리는 PAL_Z 위치",
        "clamp_pos": "LODING PALLET 위치의 -2 값 / 팔레트 클램핑 PAL_Z 위치",
        "H1X_center": "H1X 그리퍼 3개 반전기 정중앙 위치",
        "H1X_cam_avoid": "팔레트 상부 카메라 촬상 시 H1X 회피 위치",
        "head_out_search": "HeadOutForSearch < MiddlePos.MiddlePositionH1 - 10",
        "passline_3jaw": "H1 3jaw 그리퍼 passline",
        "pickup_z_3jaw_vert": "H1 3jaw 수직 작업 팔레트 픽업 Z",
        "pickup_z_3jaw_horiz": "H1 3jaw 수평 작업 팔레트 픽업 Z",
        "passline_other": "H1 3jaw 아닌 그리퍼 passline"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507149351",
    "title": "エラー状況の処置 - DIJET包装機 #1（日本語）",
    "entities": [
      {"id": "proc_ErrorHandlingDIJET1JP", "name": "에러 상황 조치 DIJET 포장기 #1 (일본어)", "type": "Process", "properties": {
        "language": "Japanese",
        "lot_mismatch": "운전 시작 시 Lot 수량 불일치 → 예: 재설정 / 아니오: 자동운전 정지",
        "error_reset_steps": [
          "HMI 원점복귀",
          "라벨쪽 케이스/흡착 라벨 전부 제거",
          "피더축 양끝 케이스 4개 제거",
          "적재설정 → 작업중 케이스 취출 → 제품 검출쪽 케이스 2개 제거 (제품은 팔레트 복귀)",
          "팔레트 취출 버튼 → 취출 후 공급부 복귀",
          "케이스 커버 공급부 케이스 제거",
          "그리퍼 픽업 제품 제거"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508920498",
    "title": "PVD 센서조작 매뉴얼",
    "entities": [
      {"id": "proc_PVDSensorSetup", "name": "PVD 센서 조작 (E3NX-FA)", "type": "Process", "properties": {
        "init": "센서 설정 이상 시 공정 초기화 후 재설정",
        "product_spacer_sensor": "제품/스페이서 공급 감지 — 검출체 있음=막대에 제품or스페이서 걸침, 없음=막대공급상태",
        "rod_sensor": "막대 공급 감지 — 검출체 있음=막대 공급, 없음=막대 없음",
        "ld_mode": "L/D 선택: Light ON / Dark ON",
        "smart_tuning": "Smart Tuning으로 자동 감도 설정",
        "value_setting": "Value Setting으로 수동 임계값 설정",
        "rot_pickup_sensor": "ROT축 그리퍼 픽업 실패 감지 — 막대 끝단 미감지, 막대 최상단 옆쪽 감지 위치 세팅"
      }},
      {"id": "comp_E3NX_FA_Amp", "name": "E3NX-FA 센서 앰프", "type": "Component", "properties": {
        "manufacturer": "Omron",
        "model": "E3NX-FA"
      }}
    ],
    "relations": [
      {"source": "proc_PVDSensorSetup", "target": "comp_E3NX_FA_Amp", "type": "MAINTAINS"}
    ]
  },
  {
    "page_id": "9509142822",
    "title": "Tray 작업 위치",
    "entities": [
      {"id": "comp_TrayWorkPositions", "name": "Tray 작업 위치 파라미터", "type": "Component", "properties": {
        "tray_standby": "TRAY축 대기 위치 (트레이 센서 미감지, 엘리베이터 간섭 없는 위치)",
        "drawer_standby": "DRAWER 대기 위치 (대부분 0 position)",
        "drawer_receive": "엘리베이터에서 트레이 판 공급 받는 DRAWER 위치",
        "drawer_before_guide": "드로워 가이드가 트레이 판과 닿기 직전 위치 (엘리베이터 문 충돌 주의)",
        "drawer_transfer": "DRAWER가 TRAY축에 트레이 판 전달하는 위치",
        "drawer_full_in": "트레이 판이 TRAY축 가이드 끝까지 닿는 위치 (이 위치보다 Drawer가 크면 엘리베이터 이동 불가)",
        "drawer_extract": "DRAWER가 엘리베이터로 트레이 판 취출하는 위치",
        "h2cam_avoid": "H2CAM 트레이 끝 단 촬상 시 간섭 없는 H2X 위치",
        "passline_3jaw_h2": "H2 3jaw 그리퍼 passline",
        "pickup_z_3jaw_vert": "H2 3jaw 수직 작업 트레이 픽업 Z (코드 미사용 확인됨)",
        "place_z_3jaw_horiz": "H2 3jaw 수평 작업 트레이 적재 기준 Z",
        "elv_a_org": "엘리베이터 A 원점 위치 1층"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508933601",
    "title": "Zebra Printer 초기설정 매뉴얼",
    "entities": [
      {"id": "proc_ZebraPrinterInitSetup", "name": "Zebra Printer 초기설정", "type": "Process", "properties": {
        "tcp_timeout": "프린터 IP 접속 → 비밀번호 1234 → 네트워크 구성 → TCP/IP → 시간초과값 300 확인/추가",
        "head_close_action": "레버 닫을 때 / 전원 재시작 시 동작없음 설정",
        "ip_setup": "IP 입력 → 유선 IP 프로토콜 영구 → 네트워크 재설정 → 전원 Off/On",
        "ribbon_setting": "봉인라벨 사용 시 리본 사용/미사용 설정",
        "label_position": "유닛별 라벨 나오는 위치 조정 (기 조정된 경우 건들지 않음)",
        "driver": "Zebra Setup Utilities로 모델에 맞는 프린터 드라이버 설치",
        "driver_settings": "인쇄 기본 설정 → 고급 설치 → 프린터 설정 사용 체크"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507153769",
    "title": "-(한글 버전)-  7-2. 보수 점검 요령",
    "entities": [
      {"id": "proc_MaintenanceCheckKO", "name": "보수 점검 요령 (한글 7-2)", "type": "Process", "properties": {
        "section": "7-2", "language": "Korean"
      }},
      {"id": "comp_MaintenanceSchedule", "name": "보수 점검 항목 및 주기", "type": "Component", "properties": {
        "regulator_filter": "Regulator 필터 청소 — 상시 / 필터 엘리먼트 교환 2년 또는 압력강하 0.1MPa 전",
        "filter_model": "SMC AW30-03B-A, AFM30-03-A, AW40-04B-A, AFM40-04-A",
        "reject_conveyor": "벨트 마모/편심 확인 — 정기 2회/년 / Misumi HTBN230S5M-100",
        "insert_transfer_2jaw": "Gripper 그립 실패/동작 이상 — 상시 / Pisco CHM08BC03C",
        "insert_transfer_belt": "벨트 마모/편심, Grease 주입 — 정기 1회/년 / NSK AS2 Grease",
        "reversal_unit": "회전 구동 이상/소음 — 정기 1회/년 / Misumi HTBN320S5M-100",
        "case_cover_stocker": "Cylinder 동작/끼임 — 상시 / SMC CDM2L20-150Z-M9BL",
        "case_magazine": "벨트 마모/편심 — 정기 1회/년",
        "case_index": "이상 시 LM Guide/Ball Screw Grease — 정기 1회/년",
        "labeling_attacher": "회전 이상 — 정기 1회/년 / Misumi HTBN201S3M-100",
        "unloading_conveyor": "구동 이상 — 정기 1회/년 / Misumi HTBN255S3M-100",
        "robot_axes": "LM/Screw Grease 주입 — 정기 1회/년 / LPK 로봇, NSK AS2 Grease"
      }}
    ],
    "relations": [
      {"source": "proc_MaintenanceCheckKO", "target": "comp_MaintenanceSchedule", "type": "DOCUMENTS"}
    ]
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch22_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch22, f, ensure_ascii=False, indent=2)
for item in batch22:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch22)}')
