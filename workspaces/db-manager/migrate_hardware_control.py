"""
hardware 스키마 변경 + 제어팀 체크리스트 템플릿 INSERT
실행: python migrate_hardware_control.py
"""
import psycopg2
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = {}
with open('C:/MES/backend/.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

conn = psycopg2.connect(host='localhost', port=55432,
    dbname=env.get('DB_NAME', 'postgres'),
    user=env.get('DB_USER', 'postgres'),
    password=env.get('DB_PASSWORD', ''))
cur = conn.cursor()

print("=" * 60)
print("1단계: hardware 스키마 컬럼 추가")
print("=" * 60)

# ── hardware.axis 컬럼 12개 추가 ──────────────────────────────
axis_cols = [
    ("axis_index",       "INTEGER",          "축 순서 번호"),
    ("actuator_type",    "VARCHAR(50)",       "액추에이터 종류 (Linear/Rotary/Pneumatic 등)"),
    ("stroke_positive",  "NUMERIC(10,2)",     "정방향 행정 거리 (mm)"),
    ("stroke_negative",  "NUMERIC(10,2)",     "부방향 행정 거리 (mm)"),
    ("load_ratio",       "NUMERIC(6,2)",      "부하율 (%)"),
    ("regen_load_ratio", "NUMERIC(6,2)",      "회생 부하율 (%)"),
    ("stiffness",        "INTEGER",           "강성 설정값"),
    ("dwell_time",       "NUMERIC(8,2)",      "DWELL 시간 (ms)"),
    ("m_time",           "NUMERIC(8,2)",      "M-time (ms)"),
    ("vel_actual",       "INTEGER",           "실측 속도"),
    ("acc_actual",       "INTEGER",           "실측 가속도"),
    ("dec_actual",       "INTEGER",           "실측 감속도"),
]
for col, dtype, comment in axis_cols:
    try:
        cur.execute(f"ALTER TABLE hardware.axis ADD COLUMN IF NOT EXISTS {col} {dtype}")
        cur.execute(f"COMMENT ON COLUMN hardware.axis.{col} IS %s", (comment,))
        print(f"  ✅ hardware.axis.{col} ({dtype})")
    except Exception as e:
        print(f"  ❌ hardware.axis.{col}: {e}")
conn.commit()

# ── hardware.equipment 컬럼 2개 추가 ─────────────────────────
equip_cols = [
    ("inter_phase_voltage", "VARCHAR(100)", "상간 전압 측정값 (예: R-S 220V / R-T 220V / S-T 220V)"),
    ("power_consumption",   "NUMERIC(8,2)", "소비 전력 (kW)"),
]
for col, dtype, comment in equip_cols:
    try:
        cur.execute(f"ALTER TABLE hardware.equipment ADD COLUMN IF NOT EXISTS {col} {dtype}")
        cur.execute(f"COMMENT ON COLUMN hardware.equipment.{col} IS %s", (comment,))
        print(f"  ✅ hardware.equipment.{col} ({dtype})")
    except Exception as e:
        print(f"  ❌ hardware.equipment.{col}: {e}")
conn.commit()

# ── hardware.camera 컬럼 6개 추가 ────────────────────────────
camera_cols = [
    ("lens_model",        "VARCHAR(200)", "렌즈 모델명"),
    ("working_distance",  "NUMERIC(8,2)", "작동 거리 WD (mm)"),
    ("fov",               "VARCHAR(100)", "시야각 FOV (예: 12mm x 9mm)"),
    ("glass_type",        "VARCHAR(100)", "GLASS 종류"),
    ("vision_controller", "VARCHAR(200)", "비전 컨트롤러 모델"),
    ("vision_license",    "VARCHAR(200)", "비전 소프트웨어 라이선스 정보"),
]
for col, dtype, comment in camera_cols:
    try:
        cur.execute(f"ALTER TABLE hardware.camera ADD COLUMN IF NOT EXISTS {col} {dtype}")
        cur.execute(f"COMMENT ON COLUMN hardware.camera.{col} IS %s", (comment,))
        print(f"  ✅ hardware.camera.{col} ({dtype})")
    except Exception as e:
        print(f"  ❌ hardware.camera.{col}: {e}")
conn.commit()

# ── hardware.pc 컬럼 1개 추가 ────────────────────────────────
try:
    cur.execute("ALTER TABLE hardware.pc ADD COLUMN IF NOT EXISTS os VARCHAR(100)")
    cur.execute("COMMENT ON COLUMN hardware.pc.os IS '운영체제 버전 (예: Windows 10 Pro 64bit)'")
    print(f"  ✅ hardware.pc.os (VARCHAR(100))")
except Exception as e:
    print(f"  ❌ hardware.pc.os: {e}")
conn.commit()

# ── hardware.controller 컬럼 1개 추가 ────────────────────────
try:
    cur.execute("ALTER TABLE hardware.controller ADD COLUMN IF NOT EXISTS error_code_range VARCHAR(100)")
    cur.execute("COMMENT ON COLUMN hardware.controller.error_code_range IS '에러 코드 범위 (예: 3000~3999)'")
    print(f"  ✅ hardware.controller.error_code_range (VARCHAR(100))")
except Exception as e:
    print(f"  ❌ hardware.controller.error_code_range: {e}")
conn.commit()

# ── hardware.transformer 신규 테이블 ─────────────────────────
print()
print("신규 테이블 생성...")
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hardware.transformer (
            id               BIGSERIAL PRIMARY KEY,
            equipment_id     BIGINT NOT NULL REFERENCES hardware.equipment(id) ON DELETE CASCADE,
            model            VARCHAR(200) NOT NULL,
            manufacturer     VARCHAR(100),
            ratio            VARCHAR(100),
            capacity_kva     NUMERIC(8,2),
            primary_voltage  VARCHAR(50),
            secondary_voltage VARCHAR(50),
            description      TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("COMMENT ON TABLE hardware.transformer IS '트랜스(변압기) 사양'")
    print("  ✅ hardware.transformer 생성")
except Exception as e:
    print(f"  ❌ hardware.transformer: {e}")
conn.commit()

# ── hardware.lighting 신규 테이블 ────────────────────────────
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hardware.lighting (
            id               BIGSERIAL PRIMARY KEY,
            equipment_id     BIGINT NOT NULL REFERENCES hardware.equipment(id) ON DELETE CASCADE,
            lighting_type    VARCHAR(100),
            lighting_model   VARCHAR(200),
            manufacturer     VARCHAR(100),
            channel_count    INTEGER,
            description      TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("COMMENT ON TABLE hardware.lighting IS '비전 조명 장치 사양'")
    print("  ✅ hardware.lighting 생성")
except Exception as e:
    print(f"  ❌ hardware.lighting: {e}")
conn.commit()

# ============================================================
print()
print("=" * 60)
print("2단계: 체크리스트 카테고리 및 템플릿 INSERT")
print("=" * 60)

# ── api_producttype: 제어팀_공통 확인/생성 ───────────────────
cur.execute("SELECT id FROM api_producttype WHERE name = '제어팀_공통'")
row = cur.fetchone()
if row:
    CONTROL_PRODUCT_TYPE_ID = row[0]
    print(f"  ⬜ 이미 존재: api_producttype 제어팀_공통 (id={CONTROL_PRODUCT_TYPE_ID})")
else:
    cur.execute("""
        INSERT INTO api_producttype (name, is_active, created_at, updated_at)
        VALUES ('제어팀_공통', true, NOW(), NOW()) RETURNING id
    """)
    CONTROL_PRODUCT_TYPE_ID = cur.fetchone()[0]
    print(f"  ✅ api_producttype 제어팀_공통 → id={CONTROL_PRODUCT_TYPE_ID}")
conn.commit()

# ── api_checklistcategory: C06~C10 INSERT ────────────────────
categories = [
    ('turn_on_power_system',   'TurnOn_전원계통'),
    ('sw_pc_system_setup',     '소프트웨어_PC시스템설정'),
    ('sw_hardware_device',     '소프트웨어_하드웨어장치설정'),
    ('sw_operation_check',     '소프트웨어_동작확인'),
    ('sw_preshipment_setting', '소프트웨어_출하전설정'),
]
cat_ids = {}
for value, label in categories:
    cur.execute("SELECT id FROM api_checklistcategory WHERE value = %s", (value,))
    row = cur.fetchone()
    if row:
        cat_ids[value] = row[0]
        print(f"  ⬜ 이미 존재: {value} (id={row[0]})")
    else:
        cur.execute("""
            INSERT INTO api_checklistcategory (value, label, is_active, created_at, updated_at)
            VALUES (%s, %s, true, NOW(), NOW()) RETURNING id
        """, (value, label))
        new_id = cur.fetchone()[0]
        cat_ids[value] = new_id
        print(f"  ✅ 추가: {value} → id={new_id}")
conn.commit()

# inspection_method id=6 (육안)
IM_VISUAL = 6

# ── api_checklistitemtemplate: department='control' INSERT ───
# 기존 항목 중복 방지
cur.execute("SELECT item_name FROM api_checklistitemtemplate WHERE department = 'control'")
existing = set(r[0] for r in cur.fetchall())

def insert_item(category_value, item_name, description, result_input, seq, is_req=True):
    if item_name in existing:
        print(f"    ⬜ 이미 존재: {item_name}")
        return
    cat_id = cat_ids.get(category_value)
    cur.execute("""
        INSERT INTO api_checklistitemtemplate
        (department, item_name, item_description,
         item_description_image_path, item_description_image_url,
         inspection_criteria_type, inspection_criteria_text,
         inspection_criteria_image_path, inspection_criteria_image_url,
         result_input_method, sequence,
         is_required, is_active, category_id, inspection_method_id,
         product_type_id, created_at, updated_at)
        VALUES (%s, %s, %s, '', '', 'text', %s, '', '', %s, %s, %s, true, %s, %s, %s, NOW(), NOW())
    """, ('control', item_name, description, description, result_input, seq, is_req, cat_id, IM_VISUAL, CONTROL_PRODUCT_TYPE_ID))
    existing.add(item_name)

# ── C06: TurnOn_전원계통 (18건) ───────────────────────────────
print("\n  [C06] TurnOn_전원계통")
turn_on_items = [
    (1,  "메인전원스위치 동작",        "메인 전원 스위치 투입 시 정상 동작 확인"),
    (2,  "트랜스 설치 상태",           "트랜스 설치 및 결선 상태 육안 확인"),
    (3,  "메인차단기 동작",            "메인 차단기 투입/차단 동작 확인"),
    (4,  "노이즈필터/CP 설치",         "노이즈필터 및 CP(서킷프로텍터) 설치 상태 확인"),
    (5,  "SMPS 출력전압",              "SMPS 출력 전압 정상 여부 확인"),
    (6,  "MC 동작",                    "마그네틱 컨택터(MC) 동작 확인"),
    (7,  "전원분배블럭 결선",          "전원 분배 블럭 결선 상태 확인"),
    (8,  "Servo Drive 전원",           "서보 드라이브 전원 투입 및 초기화 확인"),
    (9,  "PC콘센트 전원",              "PC용 콘센트 전원 공급 확인"),
    (10, "R축 Drive 전원",             "R축 서보 드라이브 전원 및 통신 확인"),
    (11, "I/O모듈 전원",               "I/O 모듈 전원 투입 및 LED 상태 확인"),
    (12, "릴레이 동작",                "릴레이 동작 상태 육안 확인"),
    (13, "DC 전원",                    "DC 24V 전원 공급 상태 확인"),
    (14, "접지바/스톱바 설치",         "접지바 및 스톱바 설치 상태 확인"),
    (15, "PC 자재 확인",               "PC 및 주변 자재 설치 상태 확인"),
    (16, "PDU/저울 전원",              "PDU 및 저울 전원 공급 확인"),
    (17, "Interface 결선",             "인터페이스 커넥터 결선 상태 확인"),
    (18, "이콘단자대 결선",            "이콘(ECON) 단자대 결선 및 체결 상태 확인"),
]
for seq, name, desc in turn_on_items:
    insert_item('turn_on_power_system', name, desc, 'pass_fail', seq)
print(f"    → {len(turn_on_items)}건 처리")
conn.commit()

# ── C07: 소프트웨어_PC시스템설정 (17건) ──────────────────────
print("\n  [C07] 소프트웨어_PC시스템설정")
pc_setup_items = [
    (1,  "BIOS 설정",                  "BIOS VT-d/SpeedStep/부팅타입 설정 확인"),
    (2,  "OS 파티션/설정",             "하드디스크 파티션(C:D: 50%), 시스템속성, 전원 설정 확인"),
    (3,  "UPS(PowerChute) 설정",       "PowerChute 런타임/알림/감도 설정 확인"),
    (4,  "Touchmonitor 설정",          "eGalaxTouch COM Port 연결 및 터치 설정 확인"),
    (5,  "Splashtop SOS 설치",         "Splashtop SOS 원격접속 프로그램 설치 확인"),
    (6,  "LibreOffice 설치",           "LibreOffice 설치 확인"),
    (7,  "Adobe Reader 설치",          "Adobe Reader 설치 확인"),
    (8,  "CCTV(HIK Vision) 설정",      "SADPTool 설치, IP/PW/해상도/녹화 설정 확인"),
    (9,  "VNC Server 설치",            "VNC Server 원격 접속 프로그램 설치 확인"),
    (10, "TP(UPDD) 설정",              "UPDD 터치패널 모니터 매핑 및 캘리브레이션 설정 확인"),
    (11, "Basler Pylon SDK 설치",      "pylon Viewer 카메라 SDK 설치 확인"),
    (12, "VisionPro 설치",             "Cognex VisionPro QuickBuild 설치 확인"),
    (13, "Soft Servo(WMX) 설정",       "WMX 라이선스 입력, RTXTcpip.ini 슬롯 설정, RTX 업데이트 확인"),
    (14, "Serial Mouse 해제",          "Com Port Plug and Play Blocker로 시리얼 마우스 비활성화"),
    (15, "Font 설치",                  "Setup 폴더 폰트 파일 Windows Fonts 복사 확인"),
    (16, "Weidmuller IO 설정",         "Weidmuller I/O 필드버스 에러 시 Hold last value 설정 확인"),
    (17, "시작 프로그램 설정",         "WMXSleepRun 자동 실행 설정 확인"),
]
for seq, name, desc in pc_setup_items:
    insert_item('sw_pc_system_setup', name, desc, 'pass_fail', seq)
print(f"    → {len(pc_setup_items)}건 처리")
conn.commit()

# ── C08: 소프트웨어_하드웨어장치설정 (7건) ───────────────────
print("\n  [C08] 소프트웨어_하드웨어장치설정")
hw_device_items = [
    (1, "MXB 2712 펌웨어",         "SDO Access 버전 확인 및 ENI 파일 로드 후 축 동작 확인"),
    (2, "스테핑 모터 SW 설정",     "CRD/CVD 드라이버 STEP각 및 DIP_SWITCH 설정 확인"),
    (3, "V1000 인버터 파라미터",   "V1000 인버터 B1/C1/D1/H1/H2 파라미터 설정 확인"),
    (4, "WMX 버전 및 설정",        "WMX 버전, 리미트 재읽기, 서보/유닛 ID 순서 확인"),
    (5, "Panasonic 회생저항",      "서보 드라이브별 회생저항 용량 및 저항값 확인"),
    (6, "Tower Lamp 동작",         "삼색등 적/황/녹 순서 및 버저 동작 확인"),
    (7, "높이측정센서(MOXA) 설정", "MOXA TXD/RXD/FG 배선, 딥스위치 1번 ON, 커넥터 체결 확인"),
]
for seq, name, desc in hw_device_items:
    insert_item('sw_hardware_device', name, desc, 'pass_fail', seq)
print(f"    → {len(hw_device_items)}건 처리")
conn.commit()

# ── C09: 소프트웨어_동작확인 (17건) ──────────────────────────
print("\n  [C09] 소프트웨어_동작확인")
op_check_items = [
    (1,  "저울 설정 확인",             "프레스 제조사에 맞는 저울 설정값 확인"),
    (2,  "저울 통신 상태 점검",        "Indicator 통신(CC-Link/RS-232C) 정상 동작 확인"),
    (3,  "저울 캘리브레이션",          "저울 캘리브레이션 진행 및 결과 확인"),
    (4,  "저울 센서 위치 조정",        "저울 센서 위치 3600/4000 기준 확인"),
    (5,  "에어디버링 저울 떨림 확인",  "에어 디버링 작동 시 저울 떨림양 측정 (g)"),
    (6,  "100% 구동 저울 떨림 확인",   "장비 100% 구동 중 저울 떨림양 측정 (g)"),
    (7,  "툴 교체 동작 확인",          "프레스→저울 이동 및 Station 핀 상태 육안 확인"),
    (8,  "원점복귀 반복 위치 확인",    "5회 이상 원점 복귀 후 위치 변화 없음 확인"),
    (9,  "그립/언그립 동작",           "그립·언그립(흡착) 정상 동작 확인"),
    (10, "그립 레귤레이터 압력",       "그립/언그립 레귤레이터 압력 조정 (기준 0.2MPa)"),
    (11, "진공 센서 조정",             "진공 센서 P2 최대치 및 정상 동작 확인"),
    (12, "E-STOP 동작 확인",           "전면/후면/TP E-STOP 스위치 동작 확인"),
    (13, "도어 센서 동작 확인",        "전체 도어 센서 동작 시 장비 일시정지 확인"),
    (14, "엘리베이터 도어 Lock",       "자동 운전 중 엘리베이터 도어 Lock 정상 동작 확인"),
    (15, "X축 위험 센서 동작",         "X축 위험 위치에서 Press 신호 미출력 확인"),
    (16, "SPM 체크",                   "순간/평균 SPM 측정 (저울 포함/미포함)"),
    (17, "Vision FOV 측정",            "상부/하부 FOV 측정 및 캘리브레이션 진행"),
]
for seq, name, desc in op_check_items:
    insert_item('sw_operation_check', name, desc, 'pass_fail', seq)
print(f"    → {len(op_check_items)}건 처리")
conn.commit()

# ── C10: 소프트웨어_출하전설정 (15건) ────────────────────────
print("\n  [C10] 소프트웨어_출하전설정")
preshipment_items = [
    (1,  "모델 파일 정상 로드",        "신규 모델 파일 생성→티칭→다른 모델 로드→재로드 정상 확인"),
    (2,  "WMI 재시작 알람 없음",       "WMI 재시작 시 재티칭 관련 알람 미발생 확인"),
    (3,  "인터페이스 ON 설정",         "출하 전 인터페이스 ON으로 설정"),
    (4,  "출하 언어 설정",             "출하 국가에 맞는 언어 설정"),
    (5,  "도어 센서 사용 켜기",        "출하 전 도어 센서 사용 활성화"),
    (6,  "저울 센서 사용 켜기",        "출하 전 저울 센서 사용 활성화"),
    (7,  "에러박스 티칭 기능 끄기",    "출하 전 에러박스 티칭 기능 비활성화"),
    (8,  "장비 명칭 설정",             "출하 전 장비 명칭(번호) 설정"),
    (9,  "인터페이스 입출력 확인",     "프레스 제조사별 인터페이스 입출력 신호 확인"),
    (10, "Safety Position 설정",       "Safety Position 파라미터 설정 완료"),
    (11, "리미트 설정",                "소프트 리미트 설정 완료"),
    (12, "소모품 리스트 확인",         "PC/서보드라이브/UPS 배터리 소모품 등록 및 타이머 초기화"),
    (13, "환경설정 파라미터 검토",     "환경설정 파라미터 업체 요구사항 불일치 항목 삭제"),
    (14, "티칭 이미지 확인",           "티칭 이미지 및 항목 수 업체 사양 일치 확인"),
    (15, "레이아웃 도면 확인",         "레이아웃 도면 파일 첨부 및 축 위치 기준값 설정"),
]
for seq, name, desc in preshipment_items:
    insert_item('sw_preshipment_setting', name, desc, 'pass_fail', seq)
print(f"    → {len(preshipment_items)}건 처리")
conn.commit()

# ── 최종 집계 ─────────────────────────────────────────────────
print()
print("=" * 60)
print("완료 집계")
print("=" * 60)
cur.execute("""
    SELECT c.label, COUNT(t.id) as cnt
    FROM api_checklistitemtemplate t
    JOIN api_checklistcategory c ON c.id = t.category_id
    WHERE t.department = 'control'
    GROUP BY c.label, c.value
    ORDER BY c.value
""")
total = 0
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}건")
    total += row[1]
print(f"  총 {total}건")

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'hardware' ORDER BY table_name")
tables = [r[0] for r in cur.fetchall()]
print(f"\nhardware 스키마 테이블 수: {len(tables)}개")
print(f"  {', '.join(tables)}")

cur.close()
conn.close()
print("\n✅ 마이그레이션 완료")
