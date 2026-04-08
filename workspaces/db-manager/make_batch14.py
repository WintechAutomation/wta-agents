import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch14 = [
  {
    "page_id": "9507159349",
    "title": "5-5-4. Inkjet 마킹",
    "entities": [
      {"id": "proc_InkjetMarking_5_5_4", "name": "Inkjet 마킹 5-5-4", "type": "Process", "properties": {
        "section": "5-5-4",
        "steps": "적재설정 선택 → 제품 추가 → 팔레트 공급 → 마킹 실행 → 마킹 완료(제품 꺼내 마킹 확인)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508927207",
    "title": "(국문, OKE)- 4-2-3-1. 팔레트 관리 - 추가",
    "entities": [
      {"id": "proc_PalletAddOKE", "name": "팔레트 추가 (OKE 4-2-3-1)", "type": "Process", "properties": {
        "section": "4-2-3-1", "customer": "OKE",
        "steps": "팔레트 관리 선택 → 팔레트 추가 → 이름/파라미터 설정 → 저장",
        "note": "팔레트 원점 설정은 별도 참고 페이지 확인"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508984750",
    "title": "AND 저울 설정 매뉴얼",
    "entities": [
      {"id": "tool_ANDRsCom", "name": "A&D RsCom 프로그램", "type": "Tool", "properties": {
        "manufacturer": "A&D Company, Limited",
        "version": "Ver.4.01",
        "download": "www.andk.co.kr 기술자료 Win-CT 설치",
        "purpose": "저울 RS232C 통신 설정 및 커맨드 전송"
      }},
      {"id": "equip_ANDScale", "name": "A&D 저울 (단중 측정)", "type": "Equipment", "properties": {
        "manufacturer": "A&D",
        "comm": "RS232C (COM11, Baud 2400, Parity E, Length 7, Stop 1, CR/LF)"
      }},
      {"id": "proc_ANDScaleSetup", "name": "A&D 저울 설정", "type": "Process", "properties": {
        "cmd_S_SI": "안정화된 저울값 읽기",
        "cmd_Q": "즉시 저울값 읽기(안정화 무시)",
        "cmd_SIR": "스트림(연속) 모드",
        "cmd_C": "SIR 모드 취소",
        "cmd_PRT": "현재 커맨드 모드 확인",
        "cmd_PR00": "커맨드 모드를 전체허용으로 변경",
        "note": "인디게이터(HW/SW) 사용 시 반드시 SIR 모드로 설정",
        "caution": "현재 모드가 Pr:03이면 S 모드 사용 불가 → PR:00으로 변경 필요"
      }}
    ],
    "relations": [
      {"source": "proc_ANDScaleSetup", "target": "tool_ANDRsCom", "type": "USES_TOOL"},
      {"source": "proc_ANDScaleSetup", "target": "equip_ANDScale", "type": "MAINTAINS"}
    ]
  },
  {
    "page_id": "9508927275",
    "title": "(국문, OKE)- 4-2-3-2. 팔레트 관리 - 수정",
    "entities": [
      {"id": "proc_PalletEditOKE", "name": "팔레트 수정 (OKE 4-2-3-2)", "type": "Process", "properties": {
        "section": "4-2-3-2", "customer": "OKE",
        "steps": "팔레트 관리 선택 → 수정할 팔레트 선택 → 파라미터 수정 → 저장",
        "warning": "팔레트 이름 변경 시 해당 팔레트를 사용하는 모델도 변경 필요"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508985492",
    "title": "Press 축 틀어짐 각도 보정",
    "entities": [
      {"id": "proc_PressAxisAngleCalib", "name": "Press 축 틀어짐 각도 보정", "type": "Process", "properties": {
        "tool": "Top Live (시스템 설정)",
        "feeder_y_p1": "돌기 플레이트 첫번째 위치 X:318.3706 Y:0 FeederY:97.5617",
        "feeder_y_p2": "마지막 위치 X:319.7706 Y:0 FeederY:377.3317",
        "feeder_y_result": "SystemData.xml > FeederYAngle",
        "y_axis_p1": "돌기 첫번째 위치 X:319.8206 Y:22.6782 FeederY:400",
        "y_axis_p2": "Y축 마지막 위치 X:319.0206 Y:302.283 FeederY:400",
        "y_axis_result": "SystemData.xml > YAngle",
        "steps": "TP/WMX Motion으로 위치 이동 → 보정 엑셀 P1/P2 입력 → 각도 계산 → SystemData.xml에 입력"
      }},
      {"id": "comp_SystemDataXml", "name": "SystemData.xml (Press 각도 설정)", "type": "Component", "properties": {
        "path": "D:/WintechAutomation/WMI/Data/SystemData.xml",
        "fields": "FeederYAngle, YAngle"
      }}
    ],
    "relations": [
      {"source": "proc_PressAxisAngleCalib", "target": "comp_SystemDataXml", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9508927572",
    "title": "(국문, OKE)- 4-2-6-1. 입출력 - 반복 동작 테스트",
    "entities": [
      {"id": "proc_IORepeatTestOKE", "name": "입출력 반복 동작 테스트 (OKE 4-2-6-1)", "type": "Process", "properties": {
        "section": "4-2-6-1", "customer": "OKE",
        "condition": "정지 중에만 실행 가능",
        "steps": "입출력 선택 → 작성 → 프로그램 추가 → 프로그램 선택 → 시퀀스 설정 화면 이동 → 입출력 Drag&Drop 추가 → ON/OFF 설정 → 딜레이(Timer) 추가 → 반복 횟수 입력 → 시작/정지"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508979516",
    "title": "#도어 센서 및 IO 확인",
    "entities": [
      {"id": "proc_DoorSensorIOCheck", "name": "도어 센서 및 IO 확인", "type": "Process", "properties": {
        "purpose": "장비 가동 시 도어 상태 정확한 모니터링 보장",
        "door_types": "일반 도어, 샘플링 취출 도어(옵션), 도킹 커버 도어(옵션)",
        "sensor_count": "4~6개",
        "steps": [
          "장비 조립 센서 위치/수량 확인",
          "Signal/Input.csv 파일에서 도어 센서 key 확인",
          "Input.csv와 코드의 key 명칭 일치 여부 검사",
          "HMI 시스템 설정 → Door 센서 모니터링 ON",
          "원점복귀/운전 시작 시 정지 메시지 확인",
          "입출력 → ETC에서 각 도어 신호 확인"
        ]
      }},
      {"id": "comp_DoorSensorConfig", "name": "도어 센서 설정 (Input.csv)", "type": "Component", "properties": {
        "path": "D:/WintechAutomation/WMI/Data/Signal/Input.csv",
        "note": "MAIN_DOOR_OPEN_5 등 Input.csv에 없는 key는 코드에 있어도 실행되지 않음"
      }},
      {"id": "issue_DoorSensorMismatch", "name": "도어 센서 설정 불일치 이슈", "type": "Issue", "properties": {
        "symptom": "센서 설정이 실제 조립 센서와 다를 경우 비정상 동작 우려",
        "fix": "Input.csv/Output.csv key 확인 및 수정, 또는 WMXServer 파일 복사"
      }},
      {"id": "issue_ATCVacuumProblem", "name": "ATC 진공 문제", "type": "Issue", "properties": {
        "fix": "Input.csv/Output.csv 확인 후 메인 공압/진공 압력 확인"
      }}
    ],
    "relations": [
      {"source": "proc_DoorSensorIOCheck", "target": "comp_DoorSensorConfig", "type": "INVOLVES_COMPONENT"},
      {"source": "issue_DoorSensorMismatch", "target": "proc_DoorSensorIOCheck", "type": "RESOLVED_BY"},
      {"source": "issue_ATCVacuumProblem", "target": "proc_DoorSensorIOCheck", "type": "RESOLVED_BY"}
    ]
  },
  {
    "page_id": "9508928776",
    "title": "(국문, OKE)- 5-1-1. 팔레트 준비",
    "entities": [
      {"id": "proc_PalletPrepOKE", "name": "팔레트 준비 (OKE 5-1-1)", "type": "Process", "properties": {
        "section": "5-1-1", "customer": "OKE",
        "steps": "팔레트 공급 위치로 이동 → 팔레트를 표시 위치에 공급",
        "max_stack": "최대 15단"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch14_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch14, f, ensure_ascii=False, indent=2)
for item in batch14:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch14)}')
