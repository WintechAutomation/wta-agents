import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch18 = [
  {
    "page_id": "9508926946",
    "title": "(국문, OKE)- 4-2-2-1.  제품모델 관리 - 추가",
    "entities": [
      {"id": "proc_ModelAddOKE", "name": "제품모델 추가 (OKE 4-2-2-1)", "type": "Process", "properties": {
        "section": "4-2-2-1", "customer": "OKE",
        "steps": "모델 관리 선택 → 모델 추가 → 이름/파라미터 설정 → 저장",
        "note": "모델 이름은 제공된 Sheet 내용과 일치해야 함"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508933090",
    "title": "Videojet 1510",
    "entities": [
      {"id": "equip_Videojet1510", "name": "Videojet 1510 잉크젯 마킹기", "type": "Equipment", "properties": {
        "manufacturer": "Videojet",
        "model": "1510",
        "comm": "TCP/IP"
      }},
      {"id": "proc_Videojet1510Setup", "name": "Videojet 1510 설정", "type": "Process", "properties": {
        "tcp_ip": "TCP/IP SETTING",
        "reverse": "마킹 꺼꾸로 나올 때 → 메시지 변수 → 반전 켜기",
        "upside_down": "마킹 뒤집힐 때 → 메시지 변수 → 역전 켜기",
        "font_size": "코드에서 Font Num 제어 (00=7hi, 01=9hi, 02=12hi, 03=16hi, 05=34hi, 06=5hi)",
        "position": "HORC(4)=가로위치, VERC(3)=세로위치; 마킹기 자체 설정 의미없음 — 프로그램이 제어",
        "global_offset": "전체 x,y 위치 변경은 HMI 모델별 Offset 설정"
      }},
      {"id": "issue_VideojetGutterError", "name": "Videojet 1510 거터 오류", "type": "Issue", "properties": {
        "symptom": "거터 오류 발생",
        "fix": "마킹기 노즐부 청소 (장갑 착용 → 빨간색 부분 비커에 뒤집어 넣기 → 액체 세척액 분사 → 헝겊으로 닦기 → 재조립)"
      }}
    ],
    "relations": [
      {"source": "proc_Videojet1510Setup", "target": "equip_Videojet1510", "type": "MAINTAINS"},
      {"source": "issue_VideojetGutterError", "target": "proc_Videojet1510Setup", "type": "RESOLVED_BY"}
    ]
  },
  {
    "page_id": "9507153286",
    "title": "-(한글 버전)-  5-5-1. 팔레트 공급 / 취출",
    "entities": [
      {"id": "proc_PalletSupplyExtractKO", "name": "팔레트 공급/취출 (한글 5-5-1)", "type": "Process", "properties": {
        "section": "5-5-1", "language": "Korean",
        "steps": "적재설정 선택 → 제품 추가 → 팔레트 공급 → 팔레트 공급 실행 → 공급 완료(작업 위치 이동) → 팔레트 취출 실행 → 취출 완료(취출 위치 이동)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9509142990",
    "title": "R축 원점 세팅",
    "entities": [
      {"id": "proc_RAxisHomeSetting", "name": "R축 원점 세팅", "type": "Process", "properties": {
        "target": "H2R1~R3 축",
        "steps": [
          "H2X축 그리퍼를 2Jaw 툴로 변경 후 Axis Parameter 클릭",
          "H2R1~R3 HomeShiftDistance를 모두 0으로 변경",
          "Save to File → WMXParameters.xml로 저장",
          "WMXServer 재부팅 후 Motion Manager에서 H2R1~3 Home Start",
          "하부 카메라로 각 축을 평행하게 R축 세팅",
          "돌아간 값만큼 HomeShiftDistance로 재설정 후 저장",
          "WMXServer 재부팅 후 Home Start → 세 그리퍼 평행 원점 확인"
        ]
      }},
      {"id": "comp_WMXParametersXml", "name": "WMXParameters.xml", "type": "Component", "properties": {
        "path": "WMXServer/Datas/WMXParameters.xml",
        "field": "HomeShiftDistance (R축 원점 오프셋)"
      }}
    ],
    "relations": [
      {"source": "proc_RAxisHomeSetting", "target": "comp_WMXParametersXml", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9508929832",
    "title": "(국문, OKE)- 5-5-1. 팔레트 공급 / 취출",
    "entities": [
      {"id": "proc_PalletSupplyExtractOKE", "name": "팔레트 공급/취출 (OKE 5-5-1)", "type": "Process", "properties": {
        "section": "5-5-1", "customer": "OKE",
        "steps": "적재설정 선택 → 제품 추가 → 팔레트 공급(저장소) → 팔레트 공급 실행 → 완료(작업 위치) → 취출 실행 → 완료(취출 위치)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508913501",
    "title": "WMXServer Parameter Check 기능폼",
    "entities": [
      {"id": "tool_WMXParamCheck", "name": "WMXServer Parameter Check 기능폼", "type": "Tool", "properties": {
        "purpose": "WMX 파라미터 XML 파일과 컨트롤러 설정 비교/확인",
        "how_to_open": "WMXServer → Axis Parameters 탭 → Parameters 탭 → Parameters Check 버튼",
        "tabs": "Param(파라미터 정보), Message(이상 파라미터 정보)",
        "diff_highlight": "차이 있는 [Axis]축 및 파라미터 붉은색 하이라이트",
        "xml_replace": "붉은 원 클릭 → WMXParameters.xml 선택 → Xml path 변경 확인",
        "source_options": "Controller(컨트롤러에서 읽기), Xml(option)(임의 XML 파일)"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9507159109",
    "title": "5-5-1. 팔레트 공급 / 취출",
    "entities": [
      {"id": "proc_PalletSupplyExtract_5_5_1", "name": "팔레트 공급/취출 5-5-1", "type": "Process", "properties": {
        "section": "5-5-1",
        "steps": "적재설정 선택 → 제품 추가 → 팔레트 공급 → 공급 실행 → 공급 완료 → 취출 실행 → 취출 완료"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508980461",
    "title": "#SPM 테스트",
    "entities": [
      {"id": "proc_SPMTest2", "name": "SPM 테스트 (분당 작업수량 측정)", "type": "Process", "properties": {
        "purpose": "장비 SPM(분당 작업수량) 측정",
        "spec_check": "사양서에서 요구 SPM 확인 (최고 속도 기준)",
        "model_setup": "테스트 모델 생성 - 제품 적재 촘촘하게 (SPM 변동폭 최소화)",
        "speed_steps": "10 이하 시작 → 안정성 확보 후 10→30→50→80→100% 점진 상승",
        "z_axis_offset": "프레스 Z축=기본패스라인+10, 저울A/B=+15, 플레이트=+20",
        "record": "요구 SPM 이상 시 최고 수치 + 평균 수치 함께 기록",
        "sampling_caution": "샘플링 티칭 미실시 또는 Z축 높이 오설정 시 샘플링 컨베이어 충돌 주의"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch18_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch18, f, ensure_ascii=False, indent=2)
for item in batch18:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch18)}')
