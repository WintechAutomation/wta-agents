import json, sys
sys.stdout.reconfigure(encoding='utf-8')

batch43 = [
  {
    "page_id": "9508923276",
    "title": "원점 설정 매뉴얼 [UnLoading]",
    "entities": [
      {"id": "proc_UnloadingHomeSetupManual", "name": "원점 설정 매뉴얼 - UnLoading 축", "type": "Process", "properties": {
        "steps": [
          "WMXServer Motion Manager에서 X/CAMERA 축 Disable",
          "두 축 모두 (-) 방향으로 끝까지 밀기",
          "시스템 설정 → Hardware Org에서 X/CAMERA 축 확인 버튼 → 즉시 적용",
          "Z축을 Motion Manager에서 1% 속도로 천천히 상승 → Limit 지점까지",
          "Hardware Org에서 Z축 확인 및 즉시 적용",
          "Motion Manager에서 ROT축 Disable → 왼쪽 끝(스페이서 취출부)으로 밀기",
          "Hardware Org에서 ROT 확인 및 즉시 적용"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924105",
    "title": "PALLET",
    "entities": [
      {"id": "proc_UnloadingPalletSetup", "name": "UnLoading 팔레트 작업 위치 설정", "type": "Process", "properties": {
        "pal_z_work": "실제 운전 중 작업 위치 — 일반적으로 원점(0)을 작업 높이로 설정",
        "pallet_align": "공급 후 얼라인 위치 — 빈 팔레트 기준 첫 번째 줄과 X축 그리퍼 라인 일치",
        "pallet_supply_pos": "PAL_Z 상승 전 팔레트 공급부 위치 — 클램프 가이드가 적재 가이드보다 바깥쪽 위치 필수",
        "pallet_max_rise": "공급 시 PAL_Z 최대 상승 위치 — 공급 가이드보다 약간 높게, 클램프 가이드와 팔레트 간격 3mm 확인"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924286",
    "title": "ROT",
    "entities": [
      {"id": "proc_ROTClampPositionSetup", "name": "ROT_CLAMP 및 ROT 작업 위치 설정", "type": "Process", "properties": {
        "rot_clamp_positions": [
          "윗단 25mm 열림/아랫단 닫힘 위치",
          "윗단 닫힘/아랫단 25mm 열림 위치",
          "윗단 최대 열림/아랫단 닫힘 위치",
          "윗단 닫힘/아랫단 최대 열림 위치",
          "윗단+아랫단 모두 닫힘 위치",
          "윗단+아랫단 모두 최대 열림 위치"
        ],
        "rot_work_positions": [
          "G1 그리퍼 막대 적재 + G2 그리퍼 스페이서 픽업 위치",
          "G1 그리퍼 제품 반전부 픽업 + G2 그리퍼 스페이서 막대 적재 위치"
        ]
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924565",
    "title": "TURNER",
    "entities": [
      {"id": "proc_TurnerPositionSetup", "name": "TURNER 반전부 작업 위치 설정", "type": "Process", "properties": {
        "passline": "반전부 작업영역 X축 이동 시 간섭 방지용 Z축 기본 상승 위치 (모델별 그리퍼에 따라 다름)",
        "turn_z_centering": "센터링 지그 작업 시 TURN_Z 위치",
        "turn_z_safety": "원점복귀 시 TURN축 회전 간섭 방지용 TURN_Z 상승 위치",
        "turn_z_inversion": "반전 지그 작업 위치 (TURN_Z_UP에서 180도 회전 후 하강 위치)",
        "turn_xy": "팔레트 그리퍼와 센터링 핀이 만나는 TURN_X/TURN_Y 위치"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924704",
    "title": "WASHER",
    "entities": [
      {"id": "comp_Washer", "name": "WASHER (세척기)", "type": "Component", "properties": {
        "description": "WASHER 세척기 작업 위치 설정"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924764",
    "title": "작업위치 - [UnLoading 전용]",
    "entities": [
      {"id": "comp_UnloadingOnlyWorkPositions", "name": "UnLoading 전용 작업 위치 파라미터", "type": "Component", "properties": {
        "description": "UnLoading 전용 작업 위치 파라미터 설정"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508924775",
    "title": "ROT_언로딩",
    "entities": [
      {"id": "proc_ROTUnloadingPositionSetup", "name": "ROT 언로딩 작업 위치 설정", "type": "Process", "properties": {
        "g1_pickup": "G1 그리퍼 막대 제품 픽업 위치 — G2는 스페이서 취출 위치, 회수통 진입 확인",
        "g2_load": "G2 그리퍼 막대 제품 픽업 적재 위치 — G1은 반전기 핀과 동일 점 위치 필수",
        "standby": "X축 간섭/충돌 방지 대기 ROT 위치 (약 20mm 간격)",
        "gz_rise": "ROT 이동 전 간섭 방지 G1Z/G2Z 상승 위치"
      }}
    ],
    "relations": []
  },
  {
    "page_id": "9508925194",
    "title": "TURNER_언로딩",
    "entities": [
      {"id": "proc_TurnerUnloadingPositionSetup", "name": "TURNER 언로딩 작업 위치 설정", "type": "Process", "properties": {
        "passline": "X축 이동 간섭 방지 Z축 기본 위치 (모델/그리퍼별 다름)",
        "turn_z_inversion": "TURN축 180도 회전 시 센터링 핀 서로 눌리지 않는 TURN_Z 위치 — 리미트 직전까지 올린 후 조금씩 하강 확인",
        "gripper_x_z": "팔레트 그리퍼 반전 전/후 픽업 시 X/Z 위치 (툴별, 3jaw 기준 반전핀 1~2mm 돌출)",
        "x_standby": "반전기 회전 시 그리퍼 간섭 방지 X축 대기 위치"
      }}
    ],
    "relations": []
  }
]

prog_path = 'C:/MES/wta-agents/workspaces/db-manager'
with open(f'{prog_path}/entities/batch43_combined.json', 'w', encoding='utf-8') as f:
    json.dump(batch43, f, ensure_ascii=False, indent=2)
for item in batch43:
    with open(f'{prog_path}/entities/cm_{item["page_id"]}.json', 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
print(f'Saved {len(batch43)}')
