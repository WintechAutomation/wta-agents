import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch41 = [
  {
    "page_id": "9508916044",
    "title": "Press 전장 자재 리스트",
    "entities": [
      {"id": "comp_PressElecMaterialList", "name": "Press 전장 자재 리스트 (EV/LIFT 타입)", "type": "Component", "properties": {
        "type": "EV, LIFT 타입",
        "part_no": "E01-105",
        "components": [
          "EBS-53C-20A: ELCB 220V",
          "ABS-33C-15A: MCCB 690V",
          "LCP-32FM-10A/7A/5A: CP 250V",
          "NDR-240-24: SMPS 264V",
          "MC-18B-220V: MC 690V",
          "KGE-H4R2R: E-STOP 버튼 250V"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508916382",
    "title": "내몽골 PRS #1,2 디버링, 스테이션 센서 현장 작업",
    "entities": [
      {"id": "proc_MongolPRSDeburring", "name": "내몽골 PRS #1,2 디버링 스테이션 센서 현장 작업", "type": "Process", "properties": {
        "description": "내몽골 PRS 1,2호기 디버링 스테이션 센서 현장 작업"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508916546",
    "title": "ODC 변경 메뉴얼",
    "entities": [
      {"id": "manual_ODCChange", "name": "ODC 변경 메뉴얼", "type": "Manual", "properties": {
        "description": "ODC 변경 절차 매뉴얼"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508917190",
    "title": "PC 및 RTX 환경 설정 메뉴얼 (추가 사항)",
    "entities": [
      {"id": "manual_PCRTXSetupAdditional", "name": "PC 및 RTX 환경 설정 추가 사항", "type": "Manual", "properties": {
        "description": "PC 및 RTX 환경 설정 매뉴얼 추가 사항"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508917289",
    "title": "Software Limit 세팅 방법",
    "entities": [
      {"id": "proc_SoftwareLimitSetup", "name": "Software Limit 세팅 방법", "type": "Process", "properties": {
        "steps": [
          "접속 IP 선택 후 접속",
          "파라미터 목록 → Software Limit Plus/Minus Value 입력 (단위: pulse)",
          "하단 Rom에 저장 클릭 (적용)"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508917345",
    "title": "TP 동작 확인 매뉴얼(Penmount 9036)",
    "entities": [
      {"id": "proc_TPPenmount9036Setup", "name": "TP 동작 확인 (Penmount 9036)", "type": "Process", "properties": {
        "target": "중국 TP 동작 확인",
        "touch_setup": [
          "Setup 프로그램 설치",
          "PenMount Monitor → 제어판 → 새로 전환",
          "PenMount 9000 RS232 생성 확인",
          "다중 모니터 → 터치 인식 지정"
        ],
        "button_led": [
          "mbpoll 실행 → Display HEX",
          "Slave DI:5, Address:1, Length:4, Scan Rate:100",
          "COM PORT 19200 Baud, 8 Data bits, Even Parity, 1 Stop Bit"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508917709",
    "title": "RSF 리니어 축 소음 제거",
    "entities": [
      {"id": "proc_RSFLinearNoiseRemoval", "name": "RSF 리니어 축 소음 제거", "type": "Process", "properties": {
        "target": "대구텍 키엔스 검사기 기준",
        "steps": [
          "축 구동 → 스트로크 중간 위치 → WMX 통신 STOP",
          "기타 → 주파수 특성 진입 → 측정 실행",
          "커서로 주파수 튀는 구간 수치 확인",
          "게인 조정 → 진동 억제 → 적응 필터 모드 '1: 1개 유효'",
          "측정 주파수값을 제3 노치필터 주파수에 기입 후 송신 → ERP 저장",
          "01.004 제1 추력 필터 시정수 50~200 사이 조정 (200 마지노선)",
          "01.014 제2 게인 설정 확인"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508918531",
    "title": "언로딩 PVD 앰프(FX-505-C2) 투광 파워 조절",
    "entities": [
      {"id": "proc_UnloadingPVDAmpPowerAdj", "name": "언로딩 PVD 앰프(FX-505-C2) 투광 파워 조절", "type": "Process", "properties": {
        "equipment": "FX-505-C2 앰프",
        "steps": [
          "빨간색 커버 열기",
          "MODE 키 → Pro 표시 → SET 진입",
          "SET → Pro1 → SET → Pro1PctL 진입",
          "+/- 조작으로 PctL L-P 설정 후 SET 저장",
          "MODE로 원래 화면 복귀"
        ]
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch41_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch41, f, ensure_ascii=False, indent=2)
for item in batch41:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch41)}')
