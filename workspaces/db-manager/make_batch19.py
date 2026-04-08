import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch19 = [
  {
    "page_id": "9507153438",
    "title": "-(한글 버전)-  5-5-3. 커버 조립",
    "entities": [
      {"id": "proc_CoverAssemblyKO", "name": "커버 조립 (한글 5-5-3)", "type": "Process", "properties": {
        "section": "5-5-3", "language": "Korean",
        "steps": "적재설정 선택 → 제품 추가 → 커버 공급(저장소) → 케이스 취출부에 케이스 공급 → 커버 조립 실행(FEEDER1=좌, FEEDER2=우) → 완료(반전기 위치에 케이스 위치)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508981778",
    "title": "플레이트 기울임각 보정(Plate tilting Angle) 기능 설명",
    "entities": [
      {"id": "proc_PlateTiltingAngle", "name": "플레이트 기울임각 보정 (PlateTiltingAngle)", "type": "Process", "properties": {
        "purpose": "AGV MGT 작업 취출 시 무너짐 방지 — 클램프 방향에 맞춰 MGT 배열",
        "config_field": "PlateTiltingAngle (시스템 설정 파일 — CorrectAngle은 0이어야 함)",
        "env_setting": "환경설정에서 보정값 추가 가능",
        "final_angle": "최종 보정값 = PlateTiltingAngle + 환경설정 보정값",
        "square_plate_limit": "사각판: +-15도까지만 보정 (충돌 우려)",
        "round_plate": "원형판: 전 방향 보정 가능",
        "note": "PlateTiltingAngle=0이면 환경설정에서 변수 자동 숨김"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508929984",
    "title": "(국문, OKE)- 5-5-3. 커버 조립",
    "entities": [
      {"id": "proc_CoverAssemblyOKE", "name": "커버 조립 (OKE 5-5-3)", "type": "Process", "properties": {
        "section": "5-5-3", "customer": "OKE",
        "steps": "적재설정 → 제품 추가 → 커버 공급 → 케이스 공급 → 커버 조립 실행 → 완료(반전기 위치)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508934843",
    "title": "6. OPC UA 테스트",
    "entities": [
      {"id": "proc_OPCUATest", "name": "OPC UA 통신 테스트", "type": "Process", "properties": {
        "server": "Unified Automation .NET SDK → Ua Demo Server",
        "client_lib": "OPC Foundation .NET Standard Library (무료, NuGet: OPCFoundation.NetStandard.Opc.Ua)",
        "client_name": "WTAClient",
        "config_file": "Opc.Ua.Client.Config.xml",
        "steps": [
          "서버 실행 후 EndPoint URL 확인",
          "Visual Studio → 콘솔 프로젝트 → NuGet 설치",
          "Opc.Ua 네임스페이스 선언",
          "클라이언트 초기화 (이름, URI, 보안 설정)",
          "서버 EndPoint 주소 입력 및 세션 생성",
          "노드 값 읽어오기 및 콘솔 출력"
        ],
        "cert_note": "인증/암호화 방식 추가 시 Rejected Certificates에서 수동 승인 필요"
      }},
      {"id": "comp_OPCUAServer", "name": "OPC UA 서버 (Ua Demo Server)", "type": "Component", "properties": {
        "sdk": "Unified Automation .NET SDK"
      }}
    ],
    "relations": [
      {"source": "proc_OPCUATest", "target": "comp_OPCUAServer", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507159261",
    "title": "5-5-3. 커버 조립",
    "entities": [
      {"id": "proc_CoverAssembly_5_5_3", "name": "커버 조립 5-5-3", "type": "Process", "properties": {
        "section": "5-5-3",
        "steps": "적재설정 → 제품 추가 → 커버 공급 → 케이스 공급 → 커버 조립 실행 → 완료(반전기 위치)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508929102",
    "title": "(국문, OKE)- 5-1-6. 잉크젯 마킹기 준비",
    "entities": [
      {"id": "proc_InkjetMarkingPrepOKE", "name": "잉크젯 마킹기 준비 (OKE 5-1-6)", "type": "Process", "properties": {
        "section": "5-1-6", "customer": "OKE",
        "steps": "마킹기 위치 이동 → 도어 오픈 → 마킹기 전원 ON → 분사 시퀀스 시작(재생 버튼)",
        "cartridge": "Make-Up/Ink Cartridge 교체 필요 시 도어 오픈 후 교체",
        "power_off": "전원 버튼 5초 누름"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508931064",
    "title": "ROT 그리퍼 작업위치 셋팅방법",
    "entities": [
      {"id": "proc_ROTGripperWorkPosSetup", "name": "ROT 그리퍼 작업위치 셋팅", "type": "Process", "properties": {
        "step1_title": "막대 중심 얼라인 (ROT_A, ROT_B)",
        "step1": "ROT_A에서 G1 그리퍼와 막대 얼라인 확인; 불일치 시 ROT축 조정 → ROT_A로 저장; 불가 시 볼트 느슨하게 후 그리퍼 위치 조절",
        "step2_title": "스페이서 픽업위치 (G2)",
        "step2": "원점복귀 → 스페이서 감지 실린더 얼라인 확인 → ROT_A 이동 → G2Z 하강하여 스페이서 홀 중심 확인; 불일치 시 기구물 4개 볼트 조정",
        "step3_title": "반전기 픽업위치 (G1)",
        "step3": "원점복귀 → ROT_B 이동 → Turn_X/Y축을 G1 작업위치로 이동 → G1Z 하강하여 센터링핀 중심 얼라인 확인; 불일치 시 Turn_X/Y 조정 후 작업위치 재설정"
      }},
      {"id": "comp_ROTAxis", "name": "ROT 축 (ROT_A, ROT_B 포지션)", "type": "Component", "properties": {
        "ROT_A": "G1 그리퍼 막대 중심 작업위치",
        "ROT_B": "G2 그리퍼 및 G1 반전기 작업위치"
      }}
    ],
    "relations": [
      {"source": "proc_ROTGripperWorkPosSetup", "target": "comp_ROTAxis", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9508929023",
    "title": "(국문, OKE)- 5-1-5. 그리퍼 확인",
    "entities": [
      {"id": "proc_GripperCheckOKE", "name": "그리퍼 확인 및 교체 (OKE 5-1-5)", "type": "Process", "properties": {
        "section": "5-1-5", "customer": "OKE",
        "steps": [
          "그리퍼 확인 위치로 이동",
          "도어 오픈",
          "HEAD1(좌)/HEAD2(우) 하단 그리퍼 확인",
          "공압 SHUT 차단",
          "기존 툴 분리",
          "핀에 맞게 신규 툴 장착",
          "툴 체결 후 공압 OPEN"
        ]
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch19_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch19, f, ensure_ascii=False, indent=2)
for item in batch19:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch19)}')
