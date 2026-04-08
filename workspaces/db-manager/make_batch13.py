import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch13 = [
  {
    "page_id": "9508927331",
    "title": "(국문, OKE)- 4-2-3-3. 팔레트 관리 - 삭제",
    "entities": [
      {"id": "proc_PalletDeleteOKE", "name": "팔레트 삭제 (OKE 4-2-3-3)", "type": "Process", "properties": {"section": "4-2-3-3", "customer": "OKE", "warning": "삭제된 팔레트 복원 불가"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508921183",
    "title": "Hardware Org 탭 설정 (하드웨어 원점)",
    "entities": [
      {"id": "proc_HardwareOrgSetting", "name": "하드웨어 원점(Hardware Org) 탭 설정", "type": "Process", "properties": {
        "menu": "WTA HMI → 시스템 변수 설정 → Hardware Org 탭"
      }},
      {"id": "comp_HardwareOrgAxes", "name": "Hardware Org 축별 원점 설정", "type": "Component", "properties": {
        "X": "도어 쪽으로 끝까지 밀기",
        "CAMERA": "도어 쪽으로 끝까지 밀기",
        "PALLET": "취출부 쪽으로 끝까지 밀기",
        "Z": "축속도 1%, 상승하여 Disable되는 높이",
        "R": "센서 호밍",
        "PAL_Z": "팔레트 윗면이 옆 가이드 높이와 같아지는 높이",
        "ROT": "스페이서 픽업 방향으로 끝까지 밀기",
        "ROT_CLAMP": "센서 호밍 후 원점",
        "TURN_Z": "센서 호밍 + HomeShiftDistance",
        "INDEX_ELV": "가장 긴 막대를 작업위치로 놓고 RotClamp에서 상부 Clamp 지그 위로 7mm 올라오는 높이"
      }},
      {"id": "comp_HardwareOrgValues", "name": "Hardware Org 실측값", "type": "Component", "properties": {
        "X": 875232, "Z": -205075, "PALLET": -6501672, "PAL_Z": 3828960,
        "CAMERA": 601648, "ROT": 1056264, "ROT_CLAMP": 51702809,
        "TURN_Z": 958399, "EV_CENTER": -27819228, "INDEX_ELV": 18013597,
        "SPACER": -1262472, "GR1Z": 575, "GR2Z": 848
      }}
    ],
    "relations": [
      {"source": "proc_HardwareOrgSetting", "target": "comp_HardwareOrgAxes", "type": "INVOLVES_COMPONENT"},
      {"source": "proc_HardwareOrgSetting", "target": "comp_HardwareOrgValues", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9508930142",
    "title": "(국문, OKE)- 5-5-5. 라벨링",
    "entities": [
      {"id": "proc_LabelingOKE", "name": "라벨링 (OKE 5-5-5)", "type": "Process", "properties": {"section": "5-5-5", "customer": "OKE"}}
    ],
    "relations": []
  },
  {
    "page_id": "9507153596",
    "title": "-(한글 버전)- 5-5-5. 라벨링",
    "entities": [
      {"id": "proc_LabelingKO", "name": "라벨링 (한글 5-5-5)", "type": "Process", "properties": {"section": "5-5-5", "language": "Korean"}}
    ],
    "relations": []
  },
  {
    "page_id": "9509143058",
    "title": "카메라 FOV 설정",
    "entities": [
      {"id": "proc_CameraFOVSetup", "name": "카메라 FOV 설정", "type": "Process", "properties": {
        "cameras": "PALLET TOP, TRAY TOP, BOT Cam",
        "method": "스틸자 촬영 → 그림판에서 mm당 픽셀 수 확인 → 10/픽셀수 = FOV",
        "example": "10mm=304픽셀 → FOV=0.0328947"
      }},
      {"id": "comp_PalletTopCamera", "name": "팔레트 상부 카메라 (PALLET TOP)", "type": "Component", "properties": {"calib_method": "스틸자 이미지 촬영 후 픽셀/mm 계산"}},
      {"id": "comp_BotCamera", "name": "하부 카메라 (BOT Cam)", "type": "Component", "properties": {"fixture": "Vac Tool로 스틸자 고정 후 촬영"}},
      {"id": "comp_FOVCalibDataGeneral", "name": "CalibrationData.xml (FOV)", "type": "Component", "properties": {"purpose": "카메라별 FOV 값 저장"}}
    ],
    "relations": [
      {"source": "proc_CameraFOVSetup", "target": "comp_PalletTopCamera", "type": "INVOLVES_COMPONENT"},
      {"source": "proc_CameraFOVSetup", "target": "comp_BotCamera", "type": "INVOLVES_COMPONENT"},
      {"source": "proc_CameraFOVSetup", "target": "comp_FOVCalibDataGeneral", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9508931832",
    "title": "WEyes 매뉴얼",
    "entities": [
      {"id": "tool_WEyes", "name": "WEyes", "type": "Tool", "properties": {
        "purpose": "CCTV 모니터링 및 녹화 관리",
        "exe": "WEyes.exe",
        "password": "7111",
        "background": "백그라운드 실행 (트레이 아이콘)"
      }},
      {"id": "proc_WEyesSetup", "name": "WEyes 초기 설정", "type": "Process", "properties": {
        "steps": "CCTV IP 설정(SADP) → ID/PW 설정(admin/iwta7111) → WEyes.exe 실행",
        "config": "해상도 720P, 시간동기화, 녹화 실시간 설정, SD카드 포맷"
      }},
      {"id": "comp_CCTV", "name": "CCTV", "type": "Component", "properties": {"ip_setup": "SADP 툴 사용", "account": "admin (내부 CCTV 계정)"}}
    ],
    "relations": [
      {"source": "proc_WEyesSetup", "target": "tool_WEyes", "type": "USES_TOOL"},
      {"source": "proc_WEyesSetup", "target": "comp_CCTV", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507153526",
    "title": "-(한글 버전)- 5-5-4. Inkjet 마킹",
    "entities": [
      {"id": "proc_InkjetMarkingKO", "name": "Inkjet 마킹 (한글 5-5-4)", "type": "Process", "properties": {"section": "5-5-4", "language": "Korean"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508930072",
    "title": "(국문, OKE)- 5-5-4. Inkjet 마킹",
    "entities": [
      {"id": "proc_InkjetMarkingOKE", "name": "Inkjet 마킹 (OKE 5-5-4)", "type": "Process", "properties": {"section": "5-5-4", "customer": "OKE"}}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch13_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch13, f, ensure_ascii=False, indent=2)
for item in batch13:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch13)}')
