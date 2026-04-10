# -*- coding: utf-8 -*-
"""ERP 현재고현황 전체 리스트 — 규칙서(config/erp-inventory-rules.md) 적용
핵심: 품목을 리스트에서 제거하지 않음! 장비유형(r[9])만 수정.
JS recalcAll()이 장비유형 기반으로 사용예정/수량/금액을 동적 계산함.
추가: 프로젝트 제외 키워드(개조/개발/판매/무상 등)에 걸리는 품목 → 비제외 프로젝트로 변경
"""
import sys, io, json, re
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r'C:\MES\wta-agents\reports\김근형'

# --- 제외 품목 (규칙 2-1~2-3: 사용예정에서 제외, 리스트 유지) ---
# JSON 파일 의존성 제거 — 품목코드 직접 정의

# 규칙 2-1: CS성 품목 (49+48+3건)
CS_TYPE = {
    'LCP070-RT-400L-20-H', 'CRBH8016A', '50-02-56-0', 'MSMF012L1T1', '67-03-39-0',
    '07-40-92-1', 'HTBN300S5M-100', 'RBC110', 'PTV100C4-4E2R-DC24SR', '67-03-41-0',
    'A-VP-16-80', '54-06-47-2', 'Film0.8', 'LWLG9C1R80B', 'ZP2-TB20MBN-H5',
    'HAR_PVD_CIRCLE', 'SLNHRN8-40-8', '67-03-37-0', '60-99-25-0', '626ZZ',
    '67-99-01-0', '6806ZZ', 'PCSS-8-30-A-RCE', '50-05-39-0', 'PK543AW-T10',
    '67-03-36-0', '605ZZ', '07-70-15-0', 'LCP12-100Q', '67-03-38-0',
    '51-03-10-0', 'PTV-100-5B4', 'LHFRWMF13', '60-99-06-1', '67-03-53-1',
    '07-01-006-0', '67-99-06-0', 'AJ-N2', 'IG32-MM20W-E(24V)', '50-05-42-0',
    '67-99-08-0', '60-99-08-1', 'SY3140-5LZ', 'AFB80X80C', 'MLG12-C2-R130',
    'P1083320-012', '6803ZZ', 'LHFS8',
}
CS_ONLY = {
    'R1T-LC', '92-00-58-1', 'CRD514-K', 'MHKL2-20D', 'MXH10-50Z',
    'PHRC070-R-500-20-H-S', 'CKR20-145EndBlock', 'LP070-RT-200L-10B-L',
    'HTPA22S3M100-A-P8', '67-00-28-0', 'SLCG5-10', 'ZPT08UN-A5',
    'ZT610-P1083320-056', 'SLCG5-15', 'LMH10', '110XI4-RB-P1006072',
    '92-02-16-2', '50-05-57-0', 'E-ELGH15-450-B2', '50-03-14-5',
    'CDJP2B6-10D-B', '67-03-51-1', 'MXH10-20Z', 'MGJ10-10', '23-00-19-3',
    'LWLG9B-C2-R105', 'Film0.65', '07-22-004-1', 'PPY-20',
    'PTV100C4-4E2C-DC24SR', 'CDQ2B16-20DZ', 'ZPT08BN-A5', '50-05-56-0',
    '67-00-111-0', '01-107-37-1', '07-22-003-1', '101-03-39-1',
    '110XI4-RB-P1006073', '110XI4-MB-P1006066', '50-05-47-0', '50-01-53-0',
    'MR85ZZ', 'FGS15049-150', 'Film45', '67-03-32-2', 'Film8-5u',
    'ZP3-T02US-A3', 'LCO40CD-W12',
}
CS_ADDITIONAL = {'MADHT1505BA1', 'RLHW-70-37', 'MBDHT2510BA1'}

# 규칙 2-2: Cell Press 제외 (44건)
CELL_PRESS = {
    'AUT8-25', 'EX-13B', 'TIL-50-G-3W', 'WLHM6', 'C-PLSBWRK10-30',
    'NKOSC5-10-16', 'PSFGW10-52-M4-N4-LKC', '22-19-33-1', 'AJKTNF4-20',
    'BYH6065', 'HSP0320-2BN37R24LINK', '22-19-33-0', 'C-HBGA20-27', 'BSW12',
    'EZI-SPEED60H30CR100P', 'E-LBHM6UU', 'Q4BCX05D04B', 'SIO-26P', 'PSFG6-94',
    '22-52-16-0', 'FWZJM-D15-V8-P5-H10', 'GDS-65-ASS-EUS-75', 'SPWF4',
    'CSH-SUS-M3-75', 'BYGSR660', '07-70-26-0', 'PSFG6-50',
    'FWZJM-D12-V8-P5-H7', 'EX-22A', '6804ZZ', 'BSPO5-20', 'AFTC7',
    'E-MSMD61N-2M', 'KG-GR-30C', 'CLPH-SS-050R', 'CAMERA_IO-5M', 'CX-491',
    'RTLC40-S-105MM', '22-19-20-0', 'ZAPP-2S(연결형)', 'GDS-65-BSS-EUS-75',
    'C-MLG12-82', 'KES6-25',
    'EZI-EC-42M-A',  # 단, EXCLUDE_WHITELIST에서 복원됨
}

# 규칙 2-3: Plan Only (78건)
PLAN_ONLY = {
    'RLDW-164-123-1C', 'WBF130X86-S24W', 'JPNGA3-P4-B2-R2', 'EzT2-EC-42M',
    'UR20-FBC-MOD-TCP-V2', 'ZL112-SP01', 'KH-RS-14N', 'PPY-8', 'BYGAO26-250',
    '21-26-97-3', 'UR20-FBC-MOD-TCP-ECO', '98-06-13-0', 'FT-A11', '97-08-01-0',
    'RS013019010', '98-13-01-0', 'WRH80X51-S24W', '97-08-03-0', 'BLDCMOTOR',
    'MDDLN45BE', 'EZM-60L-A-D', 'CSD5-10BX1', '67-99-04-0', '97-08-02-0',
    '99-14-54-2', 'MXS6-20', '97-32-09-2', '21-26-26-4', 'TSD-V50',
    'TC-N-PT-100', '97-08-06-0', '96-03-11-0', 'STBK평40-7575', 'KTM-3M-30S-D2',
    'EZM2-42XL-A', 'PHRC120-L-600-40-H-S', 'BLDC_DRIVER_CABL', '99-14-54-0',
    'MYR-3D', 'SPACER-6-5-7', 'SA-1H20S', 'DCBK3030', '98-14-54-0',
    'ZS-20-5A', '07-00-15-0', '97-08-04-0', '50-03-50-0', '99-50-01-0',
    'KW-885S', 'PPY-6', 'DS-2CD2455FWD-I', 'K14613055', '67-99-07-0',
    '67-03-54-1', '67-03-48-2', '51-06-21-1', '97-08-05-0', '99-14-54-1',
    '67-99-05-0', 'BLDC_WIRE_KB2419', 'D-M9B', '13-00-15-0', '51-06-20-1',
    '50-02-28-0', '98-10-01-0', 'JOT-4-6', '67-99-09-0', 'S6I06GD',
    '97-05-01-0', '67-99-10-0', '07-20-003-4', 'SMR-06V-B', 'RBC17',
    'K14613340', 'EZI-IO-EC-I8O8N-E', '50-03-41-0', '50-05-44-0', '51-06-12-3',
}

# 3년 경과 제외 (2026-04-09)
EXPIRED = {'MDDLN45BL', 'E2E-C04S12-WC-C1', '110XI4300DPI+REWIND', 'NUVO-8108GC-XL'}

# 규칙 2-10: 대구텍 키엔스검사자동화 전용 품목 제외 (34건, 2026-04-10 김근형 지시)
DAEGU_KEYENCE = {
    '02-142-25-0', 'ACMC-76SS', 'ACMC-76SSB', 'BRW8', 'BYCS1223-240-316',
    'CDQSB12-35DC', 'CORO-15', 'E-PMXRM10', 'EE-SX-952-W',
    'GL-75-ARF-SUNS', 'GL-75-BSF-SUNS', 'HDR0801D3C5T-102', 'HDR0802D3C5T-257',
    'HOSVA2-B-20-2-D1', 'HSP0450-4BN50R22LINK', 'HTBN186S3M-60', 'HTBN234S3M-60',
    'HTBN237S3M-60', 'HXNN3-2', 'IV-121T', 'KQ2S06-02NS1',
    'LHFC-N10', 'LHFRMF16', 'LVB8-20', 'LVN8', 'LWLG9C2R204S1_Rail',
    'MDDLN55BL', 'MK2TB20-10L-M9BL', 'MS15.XXMK_1300MM', 'MS15.XXMK_800MM',
    'SENCF3-140', 'USB3.0-AMAF-3M', 'VQ21A1-5GZ-C6', 'byhs5065-118',
}

# 전체 제외 Set 통합
exclude_cds = CS_TYPE | CS_ONLY | CS_ADDITIONAL | CELL_PRESS | PLAN_ONLY | EXPIRED | DAEGU_KEYENCE

# --- MCA210T 발주이력 로드 (프로젝트 변경용) ---
import os
mca_path = f'{base}/MCA210T_발주현황_10년.json'
mca_by_item = {}
if os.path.exists(mca_path):
    with open(mca_path, 'r', encoding='utf-8') as f:
        mca_data = json.load(f)
    for r in mca_data['items']:
        cd = r['item_cd']
        if cd not in mca_by_item:
            mca_by_item[cd] = []
        mca_by_item[cd].append({
            'po_no': r.get('po_no', ''),
            'po_dt': r.get('po_dt', ''),
            'pjt_name': r.get('pjt_name', ''),
            'po_qty': r.get('po_unit_qty', 0),
        })
    for cd in mca_by_item:
        mca_by_item[cd].sort(key=lambda x: x['po_dt'], reverse=True)
    print(f'MCA210T 발주이력: {len(mca_data["items"])}건 → {len(mca_by_item)}개 품목 로드')

# --- MAD111T 재고감안 이력 로드 (프로젝트/장비 판단에 활용) ---
mad_path = f'{base}/MAD111T_재고감안_10년.json'
mad_by_item = {}
if os.path.exists(mad_path):
    with open(mad_path, 'r', encoding='utf-8') as f:
        mad_data = json.load(f)
    for r in mad_data['items']:
        cd = r['item_cd']
        if cd not in mad_by_item:
            mad_by_item[cd] = []
        mad_by_item[cd].append({
            'po_no': r.get('adv_no', ''),
            'po_dt': r.get('adv_dt', ''),
            'pjt_name': r.get('pjt_name', ''),
            'po_qty': r.get('adv_qty', 0),
        })
    for cd in mad_by_item:
        mad_by_item[cd].sort(key=lambda x: x['po_dt'], reverse=True)
    print(f'MAD111T 재고감안: {len(mad_data["items"])}건 → {len(mad_by_item)}개 품목 로드')

# JS EXCLUDE_PJT 키워드 (recalcAll에서 사용예정 제외하는 키워드)
JS_EXCLUDE_PJT = ['개발', '판매', '무상', '교체', '개조', '부품', '수리', '소모품', '소모성']
cutoff_3y = datetime(2023, 3, 1)  # 3년+1개월 여유 (경계선 품목 누락 방지)

# 규칙 2-12: 부품교체 CS건 감지 키워드 (프로젝트명에 장비+부품 키워드 → CS성)
EQUIP_KWS = ['검사기', 'PVD', 'CVD', '프레스', '포장기', '소결', '호닝', '연삭', '그라인더']
PART_KWS = ['볼스크류', '스크류', '모터', '실린더', '센서', '벨트', '베어링', '기어',
            '밸브', '스핀들', '그리퍼', '척', '노즐', '필터', '커플링', '엔코더', '브레이크',
            '컨베이어', '로봇', '카메라', '렌즈', '조명', '케이블', '커넥터', 'PCB',
            'Jig', '지그', '치구', '가이드', '레일', 'LM', '리니어']

def is_part_replacement_cs(proj_name):
    """프로젝트명이 '장비 + 부품' 패턴인 부품교체 CS건인지 판단"""
    if not proj_name:
        return False
    has_equip = any(kw in proj_name for kw in EQUIP_KWS)
    has_part = any(kw in proj_name for kw in PART_KWS)
    return has_equip and has_part

# --- 수동 오버라이드 (김근형님 확인) ---
# 장비유형 수정
EQUIP_OVERRIDE = {
    '55348': ['호닝형상'],  # 호닝형상 전용 품목, 검사기 분류 오류 수정
    '50-01-07-0': ['PVD', '검사기', '포장기', '프레스'],  # 김근형님 직접 지정 (CVD 제외)
}
# 프로젝트 수동 지정 (multi_project에 없거나 cutoff 경계선)
PROJ_OVERRIDE = {
    'MSMF042L1T2': '아크시스 프레스 #2 (Kob,NSX2-25A)',  # 2023-04-05 발주, cutoff 경계선
    # 대구텍 키엔스 범용 부품 → 비제외 프로젝트로 변경 (2026-04-10)
    '4080ENDCAP': '몰디노 리팔레팅 #1',
    '50-02-55-0': '사천신공 2jaw Gripper(MGT)',
    'HXN6-2': '한국야금 검사기 F1 (선제작#1)',
    'LVBM20-50': '한국야금 소결 #4',
    'ZFC54-B': 'MMC 기후 프레스 #1',
}
# 제외 목록에서 빼야 할 품목 (범용 부품이 잘못 제외된 경우)
EXCLUDE_WHITELIST = {
    'EZI-EC-42M-A',  # Cell Press 제외에 잘못 포함, 실제 CVD/PVD/검사기/소결/포장기 범용
}

def find_alt_project(item_cd):
    """JS 제외 키워드에 안 걸리는 3년내 최신 프로젝트 찾기 (MCA210T+MAD111T)"""
    po_history = []
    # MCA210T 발주이력
    if item_cd in mca_by_item:
        po_history.extend(mca_by_item[item_cd])
    # MAD111T 재고감안 이력
    if item_cd in mad_by_item:
        po_history.extend(mad_by_item[item_cd])
    if not po_history:
        return None
    # 날짜 역순 정렬 (최신순)
    po_history.sort(key=lambda x: x.get('po_dt', ''), reverse=True)
    for po in po_history:
        pjt = po.get('pjt_name', '')
        po_dt = po.get('po_dt', '')
        if any(kw in pjt for kw in JS_EXCLUDE_PJT):
            continue
        # 공용자재/비프로젝트도 제외
        if any(kw in pjt for kw in ['공용자재', '비프로젝트', '미배정']):
            continue
        # 부품교체 CS건 프로젝트도 제외
        if is_part_replacement_cs(pjt):
            continue
        try:
            dt = datetime.strptime(po_dt[:10], '%Y-%m-%d')
            if dt >= cutoff_3y:
                return pjt
        except:
            pass
    return None

# --- 원본 데이터 + HTML 템플릿 로드 ---
# erp_data.json에서 원본 데이터 로드
with open(f'{base}/erp_data.json', 'r', encoding='utf-8') as f:
    erp_raw = json.load(f)
data = erp_raw['data']

# HTML 템플릿 (기존 생성 파일에서 JS/레이아웃 재사용)
src_html = f'{base}/ERP_현재고_구매진행_전체.html'
with open(src_html, 'r', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const data = (\[\[.+?\]\]);', html, re.DOTALL)
if not m:
    print("ERROR: data array not found in template HTML")
    sys.exit(1)
print(f'전체 데이터: {len(data)}건')

# --- 규칙 적용 (리스트에서 제거하지 않음, 장비유형만 수정) ---
handler_removed = 0
handler_excluded = 0
exclude_applied = 0
proj_changed = 0
part_cs_changed = 0
part_cs_excluded = 0

equip_overridden = 0
proj_overridden = 0

for row in data:
    item_cd = row[1]
    equip = row[9]
    proj = row[8] if row[8] else ''

    # 수동 장비유형 오버라이드 (제외보다 먼저)
    if item_cd in EQUIP_OVERRIDE:
        row[9] = EQUIP_OVERRIDE[item_cd]
        equip = row[9]
        equip_overridden += 1

    # 수동 프로젝트 오버라이드
    if item_cd in PROJ_OVERRIDE:
        row[8] = PROJ_OVERRIDE[item_cd]
        proj = row[8]
        proj_overridden += 1

    # 제외 화이트리스트 (잘못 제외된 범용 품목 복원)
    if item_cd in EXCLUDE_WHITELIST:
        pass  # 제외 건너뜀, 장비유형 유지
    # 제외 품목 → 장비유형 빈배열 (JS가 사용예정 0 처리)
    elif item_cd in exclude_cds:
        row[9] = []
        exclude_applied += 1
        continue

    # 규칙 1-4: 핸들러 단독 → 장비유형 빈배열
    if isinstance(equip, list) and equip == ['핸들러']:
        row[9] = []
        handler_excluded += 1
        continue
    if isinstance(equip, str) and equip.strip() == '핸들러':
        row[9] = []
        handler_excluded += 1
        continue

    # 규칙 1-4: 핸들러 제거 (복합 등록)
    if isinstance(equip, list) and '핸들러' in equip:
        new_equip = [e for e in equip if e != '핸들러']
        if not new_equip:
            row[9] = []
            handler_excluded += 1
            continue
        row[9] = new_equip
        handler_removed += 1

    # 규칙 1-6: 연삭핸들러 형식 수정
    if isinstance(equip, str) and '연삭핸들러' in equip:
        row[9] = ['연삭핸들러']

    # 프로젝트 제외 키워드 또는 공용자재(미배정) → 비제외 프로젝트로 변경
    needs_proj_change = False
    if proj and any(kw in proj for kw in JS_EXCLUDE_PJT):
        needs_proj_change = True
    if proj and '공용자재' in proj:
        needs_proj_change = True
    if needs_proj_change:
        cur_equip = row[9]
        if cur_equip and cur_equip != []:
            alt = find_alt_project(item_cd)
            if alt:
                row[8] = alt
                proj_changed += 1

    # 규칙 2-12: 부품교체 CS건 감지 → 범용은 프로젝트 변경, 전용은 제외
    proj = row[8] if row[8] else ''  # 위에서 변경됐을 수 있으므로 재확인
    if proj and is_part_replacement_cs(proj):
        cur_equip = row[9]
        if cur_equip and cur_equip != []:
            alt = find_alt_project(item_cd)
            if alt:
                row[8] = alt
                part_cs_changed += 1
            else:
                # 3년 이내 비CS 프로젝트 없음 → CS성 제외
                row[9] = []
                part_cs_excluded += 1

    # 규칙 2-5: 프로젝트 예외 미배정 — 장비유형 원본 유지

print(f'제외(사용예정 비움): {exclude_applied}건, 핸들러 단독: {handler_excluded}건, 핸들러 제거: {handler_removed}건')
print(f'장비유형 오버라이드: {equip_overridden}건, 프로젝트 오버라이드: {proj_overridden}건')
print(f'프로젝트 변경(자동): {proj_changed}건')
print(f'부품교체CS 프로젝트 변경: {part_cs_changed}건, 부품교체CS 제외: {part_cs_excluded}건')
print(f'전체 건수 유지: {len(data)}건')

# 재고금액 내림차순 정렬
data.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)

# Re-number
for i, row in enumerate(data):
    row[0] = i + 1

# --- 다수 장비 범용 품목 수집 (JS 프로젝트 필터링 건너뛸 품목) ---
multi_equip_items = set()
for row in data:
    equip = row[9]
    if isinstance(equip, list) and len(equip) >= 2:
        multi_equip_items.add(row[1])
print(f'다수 장비 범용 품목 (JS 필터링 제외): {len(multi_equip_items)}건')

# --- 전체 리스트 HTML ---
data_str = json.dumps(data, ensure_ascii=False)
new_html = html.replace(m.group(0), f'const data = {data_str};')
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 (규칙 적용)</title>'
)

# JS 패치: 다수 장비 범용 품목은 프로젝트 기반 필터링 건너뜀
multi_equip_js = json.dumps(sorted(multi_equip_items), ensure_ascii=False)
js_patch_old = '// 프로젝트명에서 장비유형 추출 → BOM 유형과 교차 (실제 사용처만 반영)'
js_patch_new = f'const MULTI_EQUIP = new Set({multi_equip_js});\n    // 프로젝트명에서 장비유형 추출 → BOM 유형과 교차 (다수 장비 범용 품목 제외)'
new_html = new_html.replace(js_patch_old, js_patch_new)

# 프로젝트 필터링 조건에 MULTI_EQUIP 체크 추가
new_html = new_html.replace(
    'if (types.length > 1 && r[8]) {',
    'if (types.length > 1 && r[8] && !MULTI_EQUIP.has(r[1])) {'
)

# 합계행 폰트 크기 확대 (8pt → 11pt)
new_html = new_html.replace(
    "tfoot td { background: #f5f5f5; font-weight: 700; border-top: 2px solid #1a237e; position: sticky; bottom: 0; z-index: 4; }",
    "tfoot td { background: #f5f5f5; font-weight: 700; font-size: 11pt; border-top: 2px solid #1a237e; position: sticky; bottom: 0; z-index: 4; }"
)
new_html = new_html.replace(
    "font-weight:700;font-size:8pt;background:#f5f5f5;border-top:2px solid #1a237e;",
    "font-weight:700;font-size:11pt;background:#f5f5f5;border-top:2px solid #1a237e;"
)

# 네비게이션 버튼 정의 (regex로 기존 버튼 교체)
btn_style = "background:#fff;color:#1a237e;border:none;padding:6px 14px;border-radius:20px;font-size:9pt;cursor:pointer;font-weight:700;font-family:'Malgun Gothic',sans-serif;margin-left:4px;"
nav_full = f'<button onclick="location.href=\'erp_현재고_TOP20\'" style="{btn_style}">TOP 20 &rarr;</button>'
nav_top20 = f'<button onclick="location.href=\'ERP_현재고_구매진행_전체\'" style="{btn_style}">&larr; 전체</button>'

# 기존 네비 버튼 영역 (</div> 바로 앞 버튼들) regex 교체
nav_pattern = re.compile(r'(<button onclick="location\.href=\'[^\']*\'"[^>]*>(?:TOP \d+|&[lr]arr; (?:전체|TOP \d+))[^<]*</button>)+')
new_html = nav_pattern.sub(nav_full, new_html)

outpath = f'{base}/ERP_현재고_구매진행_전체.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(new_html)
print(f'전체 HTML 생성: {outpath}')

# --- TOP 20 리스트 HTML ---
top20 = data[:20]
top20_str = json.dumps(top20, ensure_ascii=False)
top20_html = html.replace(m.group(0), f'const data = {top20_str};')
top20_html = top20_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 TOP 20 (규칙 적용)</title>'
)
top20_html = top20_html.replace(
    '<h1>ERP 현재고현황 및 구매진행현황</h1>',
    '<h1>ERP 현재고현황 및 구매진행현황 TOP 20</h1>'
)

top20_html = nav_pattern.sub(nav_top20, top20_html)

outpath20 = f'{base}/erp_현재고_TOP20.html'
with open(outpath20, 'w', encoding='utf-8') as f:
    f.write(top20_html)
print(f'TOP 20 HTML 생성: {outpath20}')
print(f'TOP 20 재고금액: {top20[0][4]:,} ~ {top20[19][4]:,}')

# --- 적용 확인 ---
print('\n--- 규칙 적용 확인 ---')

# 프로젝트 변경 확인
proj_check = ['ZT610-600DPI+REWIND', 'EZI-EC-42M-A', 'EZI-EC-ALL-42XL-A-R', 'ZT610-300DPI+REWIND', 'HTR1010AC7S-172']
for cd in proj_check:
    for r in data:
        if r[1] == cd:
            print(f'프로젝트변경 #{r[0]} {cd}: proj={r[8][:45]}, 장비={r[9]}')

# 오버라이드 확인
for cd in ['MSMF042L1T2', 'EZI-EC-ALL-42L-A-R', '55348']:
    for r in data:
        if r[1] == cd:
            print(f'확인 #{r[0]} {cd}: proj={r[8][:45]}, 장비={r[9]}')

# 예외 미배정
for cd in ['SS-540A-V1', '55348']:
    for r in data:
        if r[1] == cd:
            print(f'예외 #{r[0]} {cd}: 장비={r[9]}, proj={r[8][:40]}')
