import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch40 = [
  {
    "page_id": "9507151561",
    "title": "-(한글 버전)- 4-2-8-3. 케이스 원점 설정",
    "entities": [
      {"id": "proc_CaseHomeSetup_KO", "name": "케이스 원점 설정 (한글 버전, 4-2-8-3)", "type": "Process", "properties": {
        "description": "케이스 원점 설정 참조 문서 (4-2-9-5 참고)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507157066",
    "title": "4-2-8-3. 케이스 원점 설정",
    "entities": [
      {"id": "proc_CaseHomeSetup", "name": "케이스 원점 설정 (4-2-8-3)", "type": "Process", "properties": {
        "description": "케이스 원점 설정 참조 문서 (4-2-9-5 참고)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508913250",
    "title": "WMXMonitor",
    "entities": [
      {"id": "tool_WMXMonitor", "name": "WMXMonitor", "type": "Tool", "properties": {
        "description": "WMXMonitor 모니터링 도구"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508914741",
    "title": "SSD 카드 백업 및 복구",
    "entities": [
      {"id": "proc_SSDBackupRestore", "name": "SSD 카드 백업 및 복구", "type": "Process", "properties": {
        "target_pc": "I5-6002 PC 기준 (I5-8003도 동일)",
        "tool": "Acronis True Image",
        "backup_steps": [
          "F12 → 부트매니저 진입",
          "1(Acronis True Image) 입력",
          "백업 → 내 디스크 → 모든 디스크 선택",
          "백업 위치: USB로 지정",
          "파일명 입력 후 진행"
        ],
        "note": "USB가 PC에 읽힌 후 부트매니저 진입 필수"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508914949",
    "title": "SSD 복제",
    "entities": [
      {"id": "proc_SSDClone", "name": "SSD 복제 (Acronis True Image)", "type": "Process", "properties": {
        "target": "삼성 SSD 870 EVO 500GB 기준",
        "steps": [
          "신규 SSD → 컨버터 연결 후 PC USB 연결",
          "Acronis True Image → 디스크 복제 → 자동(권장)",
          "원본: 삼성 SSD, 대상: USB 연결 SSD",
          "재시작 후 복제 진행",
          "TS256GMSA230S로 부팅 확인, 내 PC에서 동일 용량 디스크 2쌍 확인",
          "기존 SSD 제거 후 복제 SSD 체결"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508915217",
    "title": "SSD 포맷",
    "entities": [
      {"id": "proc_SSDFormat", "name": "SSD 포맷 (Acronis)", "type": "Process", "properties": {
        "target": "mSTAT 3TE7 기준",
        "steps": [
          "SSD → 컨버터 연결 후 PC USB 연결",
          "Acronis 백업용 USB로 부팅",
          "도구&유틸리티 → 새로운 디스크 추가 → Generic 디스크 선택",
          "MBR 레이아웃 디스크 초기화 체크",
          "할당되지 않음 확인 후 진행"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508915535",
    "title": "Vision Flying 검출 세팅",
    "entities": [
      {"id": "proc_VisionFlyingSetup", "name": "Vision Flying 검출 세팅", "type": "Process", "properties": {
        "target": "PVD 하부 비전유닛 기준",
        "panasonic_drive": "PANATERM 실행 → X축 접속 → 매개변수 세팅 → 위치 컴페어값 1 기입",
        "wmx_setup": "WMXServer → Setup → Axis Parameter → Panasonic Setup → 서보 CP 재설정",
        "camera_setup": "카메라 연결 포트 확인 → TCP/IPv4 IP주소 수정 ('11' 위치 숫자로 포트 구분)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508915824",
    "title": "TP Enable switch manual",
    "entities": [
      {"id": "manual_TPEnableSwitch", "name": "TP Enable switch 사용설명서", "type": "Manual", "properties": {
        "model": "HP3",
        "dimensions": "1,595mm x 1,673mm x 2,400mm",
        "power": "3상 / 220V / 20A / 60Hz",
        "description": "HP3 모델 설비 사용/설정/조작/관리 설명서"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch40_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch40, f, ensure_ascii=False, indent=2)
for item in batch40:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch40)}')
