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

# CS 전용 분류 품목 (사용자 지정) — 부서장/김근형 지시 (2026-04-10~)
# 카테고리별 분류 (CS 필터 시 그룹 표시)
CS_CATEGORIES = {
    '기본': [
        # 부서장 1차 (2026-04-10)
        'MCDHT3520BA1', 'DTP7-D2', 'MADHT1505BA1',
        # 부서장 2차 (2026-04-10)
        'MDDHT5540BA1', 'MBDHT2510BA1', '110XI4600DPI+REWIND',
        'NUVO-6002-I5-V1', 'MEDLN83BL', 'NUVO-6002-I5-V5',
        'CSD5-01BX1', 'MSME5AZS1T', 'MSMD082S1S', 'MSMD042S1S',
        'MSMD5AZS1T', 'LCP050-RT-600L-10B-N', 'PK543AW-T10',
        'LCP070-RT-400L-20-H', 'CSD5-08BX1', 'CRD507-KD',
        'CSMT-08BQ1ANT3', 'DTP7-D2-CABLE-5M', 'MBDHT2510BL1',
        'MSME152S1G', 'CSD5-15BX1', 'MSME022S1S', 'MSMD042S1T',
        'CSMT-10BQ1ANT3', 'CSMT-02BQ1ABT3', 'CSD5-02BX1',
        'CSMT-10BQ1ABT3', 'CSD5-04BX1', 'MSMD082S1T',
        'RSMS-15BQ1ASK3', 'CSMT-02BQ1ANT3', 'CSD5-10BX1',
    ],
    '선삭조명': [
        # 부서장 제거 (2026-04-10): WCDRL150-S24W, WCRDRL130-S24W
        'WRH80X51-S24W',   # 10ea (대문자 X)
        'WBF130X86-S24W',  # 20ea
        'WBF65X35-S24W',   # 10ea
    ],
    '밀링조명': [
        # 부서장 제거 (2026-04-10):
        # 'WCDRL150-S48W', 'WRRDRL130-S48W', 'WSSL125X102-S24W', 'WBFL130X86-S24G'
        'WBFL65X35-S24G',   # 등록만 (erp_data 없음, 김근형 요청)
    ],
}
CS_USER_ITEMS = sorted({cd for items in CS_CATEGORIES.values() for cd in items})
# 품목코드 → 카테고리 역방향 매핑
CS_ITEM_CATEGORY = {cd: cat for cat, items in CS_CATEGORIES.items() for cd in items}

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
    'WBF65X35-S24W',  # Cell Press 전용 (2026-04-10 김근형 지시)
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

# 소결체챔퍼검사기 전용 제외 (2026-04-10 김근형 지시: 검사기 분류 불가)
CHAMFER_INSPECT = {'OR-Y4C0-XMX00'}

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
exclude_cds = CS_TYPE | CS_ONLY | CS_ADDITIONAL | CELL_PRESS | PLAN_ONLY | EXPIRED | DAEGU_KEYENCE | CHAMFER_INSPECT

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

# 프로젝트명 → 장비유형 매핑 (JS EQUIP_PLAN_DEFAULT 키와 일치)
def extract_equip_from_project(proj_name):
    """프로젝트명에서 장비유형 추출 (JS EQUIP_PLAN 키와 매칭)"""
    if not proj_name:
        return []
    types = []
    if 'PVD' in proj_name: types.append('PVD')
    if 'CVD' in proj_name: types.append('CVD')
    if '검사기' in proj_name: types.append('검사기')
    if '프레스' in proj_name: types.append('프레스')
    if '포장기' in proj_name: types.append('포장기')
    if '소결' in proj_name: types.append('소결')
    if '호닝' in proj_name: types.append('호닝형상')
    if 'CBN' in proj_name: types.append('CBN')
    if '마스크' in proj_name: types.append('마스크자동기')
    return types

# 전용 프로젝트 키워드 (이 프로젝트만 있는 품목은 사용예정 제외)
DEDICATED_PJT_KWS = ['Cell', '키엔스', '챔퍼검사기']

def is_dedicated_project(proj_name):
    """전용 프로젝트인지 판단 (Cell Press, 키엔스, 챔퍼검사기 등)"""
    if not proj_name:
        return False
    return any(kw in proj_name for kw in DEDICATED_PJT_KWS)

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
        # 전용 프로젝트(Cell, 키엔스, 챔퍼검사기) 제외
        if is_dedicated_project(pjt):
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
no_recent_po = 0
handler_recovered = 0

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
    # 단, MCA210T/MAD111T에 핸들러 외 다른 장비 발주이력이 3년내 있으면 그 장비유형 적용
    if (isinstance(equip, list) and equip == ['핸들러']) or \
       (isinstance(equip, str) and equip.strip() == '핸들러'):
        # 다른 장비 프로젝트 탐색
        alt_proj = find_alt_project(item_cd)
        if alt_proj:
            extracted = extract_equip_from_project(alt_proj)
            # 핸들러 제외
            extracted = [e for e in extracted if e != '핸들러']
            if extracted:
                row[9] = extracted
                row[8] = alt_proj
                handler_recovered += 1
                continue
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

    # 프로젝트 결정: MCA210T/MAD111T 기준 (erp_data 프로젝트명 대신)
    # 장비유형이 있는 품목만 대상
    cur_equip = row[9]
    if cur_equip and cur_equip != []:
        alt = find_alt_project(item_cd)
        if alt:
            if alt != proj:
                row[8] = alt
                proj_changed += 1
        else:
            # MCA210T/MAD111T에 3년내 유효 프로젝트 없음 → 사용예정 제외
            row[9] = []
            no_recent_po += 1

    # 규칙 2-5: 프로젝트 예외 미배정 — 장비유형 원본 유지

print(f'제외(사용예정 비움): {exclude_applied}건, 핸들러 단독: {handler_excluded}건, 핸들러 제거: {handler_removed}건')
print(f'장비유형 오버라이드: {equip_overridden}건, 프로젝트 오버라이드: {proj_overridden}건')
print(f'프로젝트 변경(MCA210T/MAD111T 기준): {proj_changed}건')
print(f'3년내 유효발주 없어 사용예정 제외: {no_recent_po}건')
print(f'핸들러 단독 → 다른 장비유형 복구: {handler_recovered}건')
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

# 초기화/CSV 내보내기 버튼 제거 (2026-04-10 부서장 지시)
new_html = re.sub(r'<button[^>]*onclick="resetEquipPlan\(\)"[^>]*>초기화</button>\s*', '', new_html)
new_html = re.sub(r'<button[^>]*onclick="exportCSV\(\)"[^>]*>CSV 내보내기</button>\s*', '', new_html)

# "매칭되지않은 재고" 버튼 추가 (10년 버튼 오른쪽, 2026-04-10 부서장 지시)
# 장비유형 미배정 품목 수 계산
unmatched_count = sum(1 for r in data if not r[9] or r[9] == [])
unmatched_btn = f'<button class="filter-btn" data-st="unmatched" onclick="setSt(\'unmatched\')" title="어떤 장비유형에도 배정되지 못한 품목입니다.&#10;- 규칙으로 제외된 품목 (CS성/Cell Press/핸들러 등)&#10;- 3년내 유효 발주(MCA210T/MAD111T)가 없는 품목&#10;- BOM에 장비 배정이 없는 자재" style="background:#fff3e0;border-color:#e65100;color:#e65100;">매칭되지않은 재고 ({unmatched_count:,})</button>'
# CS 재고 필터 버튼
cs_count = len(CS_USER_ITEMS)
cs_btn = f'<button class="filter-btn" data-st="cs" onclick="setSt(\'cs\')" title="CS용 자재로 분류된 품목입니다.&#10;고객 사이트 유지보수/교체용 재고로 별도 관리됩니다." style="background:#ffebee;border-color:#c62828;color:#c62828;">CS 재고 ({cs_count:,})</button>'
# 기존 unmatched/cs 버튼 잔재 제거 후 삽입
new_html = re.sub(r'<button[^>]*data-st="unmatched"[^>]*>매칭되지않은 재고[^<]*</button>\s*', '', new_html)
new_html = re.sub(r'<button[^>]*data-st="cs"[^>]*>CS 재고[^<]*</button>\s*', '', new_html)
new_html = new_html.replace(
    '</button>\n    <span class="result-count"',
    f'</button>\n    {unmatched_btn}\n    {cs_btn}\n    <span class="result-count"'
)

# 3년/5년/10년 버튼에 툴팁 추가 (2026-04-10 부서장 지시)
new_html = re.sub(
    r'<button class="filter-btn active" data-st="all" onclick="setSt\(\'all\'\)">전체',
    '<button class="filter-btn active" data-st="all" onclick="setSt(\'all\')" title="전체 재고 품목입니다.">전체',
    new_html
)
new_html = re.sub(
    r'<button class="filter-btn" data-st="3y" onclick="setSt\(\'3y\'\)">3년',
    '<button class="filter-btn" data-st="3y" onclick="setSt(\'3y\')" title="최근 3년 이내(2023-01-01 이후) 입고된 품목입니다.&#10;가장 최근에 사용/구매된 활성 재고입니다.">3년',
    new_html
)
new_html = re.sub(
    r'<button class="filter-btn" data-st="5y" onclick="setSt\(\'5y\'\)">5년',
    '<button class="filter-btn" data-st="5y" onclick="setSt(\'5y\')" title="3~5년 전(2021-01-01 ~ 2022-12-31) 입고된 품목입니다.&#10;사용 빈도가 낮아진 재고입니다.">5년',
    new_html
)
new_html = re.sub(
    r'<button class="filter-btn" data-st="10y" onclick="setSt\(\'10y\'\)">10년',
    '<button class="filter-btn" data-st="10y" onclick="setSt(\'10y\')" title="5년 이상(2021-01-01 이전) 입고된 품목입니다.&#10;장기 미사용 재고로 처분/재활용 검토 대상입니다.">10년',
    new_html
)

# dateFilter 함수 전체를 깨끗한 버전으로 교체 (멱등)
clean_date_filter = '''function dateFilter(dt) {
  if (stFilter === 'all') return true;
  const d = dt || '';
  if (stFilter === '3y') return d >= '2023-01-01';
  if (stFilter === '5y') return d >= '2021-01-01' && d < '2023-01-01';
  if (stFilter === '10y') return d < '2021-01-01';
  if (stFilter === 'unmatched') return true;
  if (stFilter === 'cs') return true;
  return true;
}'''
new_html = re.sub(
    r"function dateFilter\(dt\) \{[\s\S]*?\n\}",
    clean_date_filter,
    new_html
)

# applyFilters의 filter 콜백 첫 줄을 깨끗하게 교체 (멱등)
new_html = re.sub(
    r"filtered = DATA\.filter\(r => \{\s*\n\s*if \([^\n]*?\n",
    "filtered = DATA.filter(r => {\n    if (stFilter === 'unmatched') { if (r[9] && r[9] !== '') return false; } else if (stFilter === 'cs') { if (!CS_ITEMS.has(r[1])) return false; } else { if (!dateFilter(r[7])) return false; }\n",
    new_html
)

# CS 필터 시 카테고리별 정렬 + 프로젝트열에 카테고리명 표시
# applyFilters의 doSort() 호출 직전에 CS 분기 추가 (멱등)
new_html = re.sub(r"\s*if \(stFilter === 'cs'\) \{ filtered\.sort[\s\S]*?\}\)\s*; \}\s*", '', new_html)
cs_sort_block = """
  if (stFilter === 'cs') { filtered.sort((a, b) => { const ca = CS_CATEGORY[a[1]] || ''; const cb = CS_CATEGORY[b[1]] || ''; if (ca !== cb) return ca.localeCompare(cb, 'ko'); return (b[4]||0) - (a[4]||0); }); renderRows(filtered); return; }
"""
new_html = new_html.replace(
    "  doSort();\n  renderRows(filtered);\n}\n\nfunction setSt",
    cs_sort_block + "  doSort();\n  renderRows(filtered);\n}\n\nfunction setSt"
)

# renderRows에서 CS 필터 시 프로젝트 컬럼에 카테고리 배지 표시
new_html = new_html.replace(
    "let pjt = r[8] || '-';",
    "let pjt = r[8] || '-'; if (stFilter === 'cs' && CS_CATEGORY[r[1]]) { pjt = '[' + CS_CATEGORY[r[1]] + '] ' + (r[8] || ''); }"
)

# 합계행: CSS + JS 인라인 모두 regex로 폰트 크기 통일 (멱등)
TFOOT_FONT = '13pt'
# CSS tfoot td 폰트
new_html = re.sub(
    r'tfoot td \{([^}]*)\}',
    lambda m: 'tfoot td {' + (re.sub(r'font-size:\s*\d+pt;?\s*', '', m.group(1)) + f' font-size: {TFOOT_FONT};') + '}',
    new_html
)
# JS const ts 폰트
new_html = re.sub(
    r"const ts = 'font-weight:700;font-size:\d+pt;",
    f"const ts = 'font-weight:700;font-size:{TFOOT_FONT};",
    new_html
)
# JS 합계행 인라인 font-size (예정금액/남는금액 셀)
new_html = re.sub(
    r"font-weight:700;font-size:\d+pt;background:#e8f5e9;",
    f"font-weight:700;font-size:{TFOOT_FONT};background:#e8f5e9;",
    new_html
)
new_html = re.sub(
    r"font-weight:700;font-size:\d+pt;background:#fff3e0;",
    f"font-weight:700;font-size:{TFOOT_FONT};background:#fff3e0;",
    new_html
)
# 합계행 빈 셀 colspan 합침 (사용예정/남는금액 영역)
new_html = re.sub(
    r"<td style=\"' \+ ts \+ '\"></td>' \+\n\s*'    '<td style=\"' \+ ts \+ '\"></td>' \+\n\s*'    '<td class=\"right\" style=\"",
    "<td colspan=\"2\" style=\"background:#e8f5e9;border-top:2px solid #2e7d32;' + ts + '\"></td>' +\n    '<td class=\"right\" style=\"",
    new_html
)

# JS 예정/잔여 금액 계산 수정: 예정금액 ≤ 재고금액, 잔여 = 재고 - 예정 (음수 방지)
new_html = new_html.replace(
    "r[11] = Math.round(useQty * unitP);\n    r[12] = Math.max(0, r[3] - eqQty);\n    r[13] = Math.round(r[12] * unitP);",
    "r[11] = Math.min(Math.round(useQty * unitP), r[4]);\n    r[12] = Math.max(0, r[3] - eqQty);\n    r[13] = Math.max(0, r[4] - r[11]);"
)

# 요약 카드: 총액/예정/잔여/CS 동적 계산 (멱등 regex 패치)
# 1) totalAmt/totalUseAmt/totalRemainAmt/totalCsAmt 계산 블록 전체 교체
# const cards = ... 라인 직전까지를 매치 (앵커 사용)
calc_block = (
    "let totalAmt = 0, totalUseAmt = 0, totalRemainAmt = 0, totalCsAmt = 0;\n"
    "  for (const r of DATA) { totalAmt += (r[4]||0); totalUseAmt += r[11]; if (CS_ITEMS.has(r[1])) totalCsAmt += (r[4]||0); }\n"
    "  totalRemainAmt = totalAmt - totalUseAmt;\n  "
)
new_html = re.sub(
    r"let total[\s\S]*?(?=const cards = document\.querySelectorAll\('\.summary-card'\);)",
    calc_block,
    new_html
)
# 2) cards[1] 중복 라인 모두 제거 후 1줄만 삽입
new_html = re.sub(
    r"(?:\s*if \(cards\[1\]\) \{[^\n]*\})+",
    "\n  if (cards[1]) { cards[1].querySelector('.value').textContent = totalAmt.toLocaleString() + '원'; cards[1].querySelector('.sub-value').textContent = '(약 ' + (totalAmt/100000000).toFixed(1) + '억원)'; }",
    new_html
)
# 3) cards[4] (CS용 자재 총액) 동적 업데이트 라인 추가/갱신
if 'cards[4]' not in new_html:
    new_html = new_html.replace(
        "if (cards[3]) { cards[3].querySelector('.value').textContent = totalRemainAmt.toLocaleString()",
        "if (cards[4]) { cards[4].querySelector('.value').textContent = totalCsAmt.toLocaleString() + '원'; cards[4].querySelector('.sub-value').textContent = '(약 ' + (totalCsAmt/100000000).toFixed(1) + '억원)'; }\n  if (cards[3]) { cards[3].querySelector('.value').textContent = totalRemainAmt.toLocaleString()"
    )

# 4) "예상 잔여 금액" → "예상 잔여 재고금액"
new_html = new_html.replace('<div class="label">예상 잔여 금액</div>', '<div class="label">예상 잔여 재고금액</div>')

# 5) CS용 자재 총액 카드 추가 (오른쪽 끝)
if 'CS용 자재 총액' not in new_html:
    cs_card = '''<div class="summary-card">
      <div class="label">CS용 자재 총액</div>
      <div><span class="value" style="color:#c62828;">0원</span><span class="sub-value">(약 0.0억원)</span></div>
    </div>'''
    new_html = new_html.replace(
        '<div class="label">예상 잔여 재고금액</div>\n      <div><span class="value" style="color:#e65100;">1,602,345,489원</span><span class="sub-value">(약 16.0억원)</span></div>\n    </div>',
        '<div class="label">예상 잔여 재고금액</div>\n      <div><span class="value" style="color:#e65100;">1,602,345,489원</span><span class="sub-value">(약 16.0억원)</span></div>\n    </div>\n    ' + cs_card
    )

# 6) CS_ITEMS Set + CS_CATEGORY 매핑 정의 (HTML 상단에 삽입, 멱등)
cs_items_js = json.dumps(CS_USER_ITEMS, ensure_ascii=False)
cs_category_js = json.dumps(CS_ITEM_CATEGORY, ensure_ascii=False)
cs_def = f'const CS_ITEMS = new Set({cs_items_js});\nconst CS_CATEGORY = {cs_category_js};\n'
# 기존 CS 정의 모두 제거 후 1번만 삽입
new_html = re.sub(r'const CS_ITEMS = new Set\([^)]*\);\s*\n(?:const CS_CATEGORY = [^;]*;\s*\n)?', '', new_html)
new_html = new_html.replace('<script>\nlet DATA = [];', f'<script>\n{cs_def}let DATA = [];')

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
