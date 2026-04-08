import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch9 = [
  {
    "page_id": "9508927690",
    "title": "(국문, OKE)- 4-2-7-1. 운영 이력 - 검색",
    "entities": [
      {"id": "proc_OpHistorySearch", "name": "운영 이력 검색", "type": "Process", "properties": {
        "section": "4-2-7-1",
        "steps": "메인화면 → 운영 이력 선택 → 기간 설정 → 검색 타입 선택 → 검색 실행"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508931502",
    "title": "MDB 파일 압축",
    "entities": [
      {"id": "proc_MDBCompact", "name": "MDB 파일 압축 및 복구", "type": "Process", "properties": {
        "tool": "Microsoft Access",
        "steps": "MDB 파일 열기 → 데이터베이스 도구 → 데이터베이스 압축 및 복구",
        "auto_compact": "파일 → 옵션 → 현재 데이터베이스 → 닫을 때 압축 체크"
      }},
      {"id": "comp_MDBFile", "name": "MDB 파일 (Inspection.mdb)", "type": "Component", "properties": {
        "issue": "사용할수록 용량 증가",
        "path": "D:\\WintechAutomation\\WMI\\Data\\Inspection.mdb"
      }}
    ],
    "relations": [
      {"source": "proc_MDBCompact", "target": "comp_MDBFile", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9508913261",
    "title": "WMXMonitor 설치",
    "entities": [
      {"id": "tool_WMXMonitor", "name": "WMXMonitor", "type": "Tool", "properties": {
        "install": "빌드 또는 WMXMonitor/Files/WMXMonitor.zip 압축 해제",
        "config_file": "Option.ini",
        "config_path": "빌드폴더/Option.ini",
        "settings": "Hide Console(콘솔 표시 여부), EnginePath"
      }},
      {"id": "proc_WMXMonitorInstall", "name": "WMXMonitor 설치", "type": "Process", "properties": {
        "steps": "빌드 또는 zip 해제 → Option.ini 복사 → Option.ini 수정"
      }}
    ],
    "relations": [
      {"source": "proc_WMXMonitorInstall", "target": "tool_WMXMonitor", "type": "USES_TOOL"}
    ]
  },
  {
    "page_id": "9508931431",
    "title": "LiveChart Gear 인증 방법",
    "entities": [
      {"id": "tool_LiveChartGear", "name": "LiveChart Gear", "type": "Tool", "properties": {
        "auth_type": "PC별 Activation Code 인증",
        "steps": "첨부 파일 실행 → 웹페이지 로그인 → Activation Code 복사 → 인증 완료",
        "account": "software@iwta.co.kr (내부 소프트웨어 관리 계정)"
      }},
      {"id": "proc_LiveChartAuth", "name": "LiveChart Gear 인증", "type": "Process", "properties": {
        "note": "PC마다 인증코드 다름"
      }}
    ],
    "relations": [
      {"source": "proc_LiveChartAuth", "target": "tool_LiveChartGear", "type": "USES_TOOL"}
    ]
  },
  {
    "page_id": "9508928500",
    "title": "(국문, OKE)- 4-2-9-4. 케이스 관리 - 복사",
    "entities": [
      {"id": "proc_CaseCopyOKE2", "name": "케이스 복사 (OKE 4-2-9-4)", "type": "Process", "properties": {
        "section": "4-2-9-4",
        "customer": "OKE"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507159057",
    "title": "5-4-4. 혼입 적재 티칭",
    "entities": [
      {"id": "proc_MixedLoadTeaching", "name": "혼입 적재 티칭", "type": "Process", "properties": {
        "section": "5-4-4",
        "entry": "메인화면 → 시스템 설정 → User Option 탭",
        "method": "Vision 티칭",
        "detect_type": "혼입검출 1번: CB형상 비교 (칩브레이커 수 비교)"
      }},
      {"id": "comp_MixedLoadParams", "name": "혼입 적재 설정 파라미터", "type": "Component", "properties": {
        "param": "혼입적재 일치 허용값 (%)",
        "description": "이미지와 일치율이 설정값 이상이면 동일 제품으로 인식"
      }}
    ],
    "relations": [
      {"source": "proc_MixedLoadTeaching", "target": "comp_MixedLoadParams", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507152400",
    "title": "-(한글 버전)- 5-1-2. 케이스 준비",
    "entities": [
      {"id": "proc_CasePrepKO", "name": "케이스 준비 (한글)", "type": "Process", "properties": {"section": "5-1-2", "language": "Korean"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508913307",
    "title": "WMXMonitor - Database",
    "entities": [
      {"id": "comp_WMXMonitorDB", "name": "WMXMonitor 데이터베이스 (datas.db)", "type": "Component", "properties": {
        "path": "WMXMonitor/datas.db",
        "format": "SQLite"
      }},
      {"id": "tool_SQLiteBrowser", "name": "SQLite Database Browser", "type": "Tool", "properties": {
        "exe": "SQLiteDatabaseBrowserPortable.exe",
        "purpose": "WMXMonitor DB 조회"
      }},
      {"id": "proc_WMXMonitorDBView", "name": "WMXMonitor DB 확인", "type": "Process", "properties": {
        "steps": "SQLiteDatabaseBrowserPortable.exe 실행 → 데이터베이스 열기 → WMXMonitor/datas.db 선택"
      }}
    ],
    "relations": [
      {"source": "proc_WMXMonitorDBView", "target": "comp_WMXMonitorDB", "type": "INVOLVES_COMPONENT"},
      {"source": "proc_WMXMonitorDBView", "target": "tool_SQLiteBrowser", "type": "USES_TOOL"},
      {"source": "tool_WMXMonitor", "target": "comp_WMXMonitorDB", "type": "USES_TOOL"}
    ]
  }
]

with open('entities/batch9_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch9, f, ensure_ascii=False, indent=2)
for item in batch9:
    with open(f'entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch9)}')
