import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch8 = [
  {
    "page_id": "9508926296",
    "title": "(국문, OKE)- 3-4. 장비 구조 및 공정도",
    "entities": [
      {"id": "comp_CaseUnloadConveyor", "name": "Case Unloading Conveyor Unit (13)", "type": "Component", "properties": {"unit_no": 13, "function": "케이스 취출 컨베이어"}},
      {"id": "comp_VisionUnit_14_2", "name": "Ink Marking Vision (14-2)", "type": "Component", "properties": {"unit_no": "14-2", "function": "잉크 마킹 비전 검사"}},
      {"id": "comp_VisionUnit_14_3", "name": "Quantity Detection Vision (14-3)", "type": "Component", "properties": {"unit_no": "14-3", "function": "수량 검출 비전"}},
      {"id": "comp_InkMarkingUnit", "name": "Ink Marking Unit (15-1)", "type": "Component", "properties": {"unit_no": "15-1"}},
      {"id": "comp_LaserMarkingUnit", "name": "Laser Marking Unit (15-2)", "type": "Component", "properties": {"unit_no": "15-2"}},
      {"id": "equip_OKE_ProcessStruct", "name": "OKE 설비 공정 구조도", "type": "Equipment", "properties": {"customer": "OKE", "section": "3-4"}}
    ],
    "relations": [
      {"source": "equip_OKE_ProcessStruct", "target": "comp_CaseUnloadConveyor", "type": "USES_COMPONENT"},
      {"source": "equip_OKE_ProcessStruct", "target": "comp_VisionUnit_14_2", "type": "USES_COMPONENT"},
      {"source": "equip_OKE_ProcessStruct", "target": "comp_VisionUnit_14_3", "type": "USES_COMPONENT"},
      {"source": "equip_OKE_ProcessStruct", "target": "comp_InkMarkingUnit", "type": "USES_COMPONENT"},
      {"source": "equip_OKE_ProcessStruct", "target": "comp_LaserMarkingUnit", "type": "USES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507152748",
    "title": "-(한글 버전)- 5-1-7. 그리퍼 종류",
    "entities": [
      {"id": "comp_GripperByHole", "name": "제품 홀 전용 그리퍼 (Ø3.5~Ø5.5)", "type": "Component", "properties": {"spec": "Ø3.5~Ø5.5 전용"}},
      {"id": "comp_GripperMGT", "name": "MGT 전용 그리퍼", "type": "Component", "properties": {"type": "MGT"}},
      {"id": "comp_GripperHead1", "name": "Head1 전용 그리퍼", "type": "Component", "properties": {"type": "Head1"}},
      {"id": "comp_GripperHead2", "name": "Head2 전용 그리퍼", "type": "Component", "properties": {"type": "Head2"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508913431",
    "title": "WMX Server 슬레이브 연결확인 초기설정",
    "entities": [
      {"id": "proc_WMXSlaveConnCheck", "name": "WMX Server 슬레이브 연결 확인 초기설정", "type": "Process", "properties": {"steps": "WMXServer → Setup→EcConfigurator 실행 → 슬레이브 정상 연결 상태 Export Def."}},
      {"id": "tool_EcConfigurator", "name": "EcConfigurator", "type": "Tool", "properties": {"access": "WMXServer → Setup 탭 → EcConfigurator 실행", "function": "슬레이브 연결 Export/비교"}},
      {"id": "issue_SlaveMissing", "name": "EtherCAT 슬레이브 누락 오류", "type": "Issue", "properties": {"error": "[Error] User define not match. Defined [Slave 6] not found", "code": "EC_MasterStart Failed: ret=0x17000000"}},
      {"id": "tool_RtxServer", "name": "RtxServer", "type": "Tool", "properties": {"function": "EtherCAT 슬레이브 로그 확인"}}
    ],
    "relations": [
      {"source": "proc_WMXSlaveConnCheck", "target": "tool_EcConfigurator", "type": "USES_TOOL"},
      {"source": "issue_SlaveMissing", "target": "proc_WMXSlaveConnCheck", "type": "RESOLVED_BY"},
      {"source": "issue_SlaveMissing", "target": "tool_RtxServer", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507144149",
    "title": "Magazine",
    "entities": [
      {"id": "comp_EmptyCaseTRS", "name": "EMPTY_CASE_TRS 축", "type": "Component", "properties": {"function": "각 매거진 중앙으로 이동"}},
      {"id": "comp_LowerCylinder", "name": "하부 실린더", "type": "Component", "properties": {"operation": "상승하여 중앙 정렬 확인"}},
      {"id": "proc_MagazinePositionSet", "name": "매거진 위치 설정", "type": "Process", "properties": {"steps": "EMPTY_CASE_TRS를 매거진 중앙으로 이동 → 하부 실린더 상승으로 중앙 확인 → 값 입력 → 즉시 적용"}}
    ],
    "relations": [
      {"source": "proc_MagazinePositionSet", "target": "comp_EmptyCaseTRS", "type": "INVOLVES_COMPONENT"},
      {"source": "proc_MagazinePositionSet", "target": "comp_LowerCylinder", "type": "INVOLVES_COMPONENT"}
    ]
  },
  {
    "page_id": "9507158261",
    "title": "5-1-3. 커버 준비",
    "entities": [
      {"id": "proc_CoverPrep_5_1_3", "name": "커버 준비 5-1-3", "type": "Process", "properties": {"section": "5-1-3", "steps": "커버 공급 위치 이동 → 도어 열고 커버 공급"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508926111",
    "title": "(국문, OKE)- 2-1. 위험 표기 참고 사항",
    "entities": [
      {"id": "comp_DangerLabels_OKE", "name": "OKE 설비 위험 표기 라벨", "type": "Component", "properties": {"customer": "OKE", "section": "2-1"}}
    ],
    "relations": []
  },
  {
    "page_id": "9507152058",
    "title": "-(한글 버전)- 4-2-9-4. 케이스 관리 - 복사",
    "entities": [
      {"id": "proc_CaseCopyKO", "name": "케이스 복사 (한글)", "type": "Process", "properties": {"section": "4-2-9-4", "language": "Korean"}}
    ],
    "relations": []
  },
  {
    "page_id": "9508929190",
    "title": "(국문, OKE)- 5-1-7. 그리퍼 종류",
    "entities": [
      {"id": "comp_GripperOKE_ByHole", "name": "제품 홀 전용 그리퍼 OKE (Ø3.5~Ø5.5)", "type": "Component", "properties": {"customer": "OKE", "spec": "Ø3.5~Ø5.5"}},
      {"id": "comp_GripperOKE_MGT", "name": "MGT 전용 그리퍼 (OKE)", "type": "Component", "properties": {"customer": "OKE", "type": "MGT"}},
      {"id": "comp_GripperOKE_Head1", "name": "Head1 전용 그리퍼 (OKE)", "type": "Component", "properties": {"customer": "OKE", "type": "Head1"}},
      {"id": "comp_GripperOKE_Head2", "name": "Head2 전용 그리퍼 (OKE)", "type": "Component", "properties": {"customer": "OKE", "type": "Head2"}}
    ],
    "relations": []
  }
]

with open('entities/batch8_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch8, f, ensure_ascii=False, indent=2)
for item in batch8:
    with open(f'entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch8)}')
