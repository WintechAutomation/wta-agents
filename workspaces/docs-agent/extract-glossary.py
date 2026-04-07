"""파싱된 매뉴얼 338개 파일에서 기술 용어를 추출하여 glossary.json 업데이트."""
import os
import re
import json
from collections import Counter

PARSED_DIR = r"C:\MES\wta-agents\data\wta_parsed"
GLOSSARY_FILE = r"C:\MES\wta-agents\config\glossary.json"

# ── 1) 파싱된 파일 전체 텍스트 수집 ──
all_text = []
file_count = 0
for fname in os.listdir(PARSED_DIR):
    if fname.endswith(".md"):
        fpath = os.path.join(PARSED_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            all_text.append(text)
            file_count += 1
        except Exception:
            pass

combined = "\n".join(all_text)
print(f"Loaded {file_count} files, {len(combined):,} chars")

# ── 2) 기술 용어 후보 추출 ──
# 영문 기술 용어 패턴
en_terms = Counter()
en_patterns = [
    r'\b(PVD|CVD|HIM|CNC|PLC|HMI|MCB|UPS|SMPS|ERP|MES|AGV|AMR)\b',
    r'\b(servo|motor|encoder|sensor|actuator|cylinder|valve|solenoid)\b',
    r'\b(gripper|chuck|collet|spindle|arbor|mandrel|turret)\b',
    r'\b(pallet|spacer|pole|magazine|hopper|feeder|conveyor|elevator)\b',
    r'\b(vacuum|pneumatic|hydraulic|compressor|regulator|filter)\b',
    r'\b(coating|sputtering|deposition|etching|annealing|sintering|tempering|hardening|quenching)\b',
    r'\b(grinding|honing|lapping|polishing|pressing|brazing|welding)\b',
    r'\b(insert|carbide|tungsten|cobalt|substrate|target)\b',
    r'\b(vision|camera|lens|lighting|inspection|measurement)\b',
    r'\b(belt|pulley|gear|bearing|bushing|shaft|coupling|flange)\b',
    r'\b(inverter|breaker|fuse|transformer|contactor|relay|thermocouple)\b',
    r'\b(coolant|nozzle|chiller|heater|lubricant|grease)\b',
    r'\b(robot|manipulator|handler|loader|unloader|sorter|packer)\b',
    r'\b(jig|fixture|clamp|stopper|guide|rail|slide|block)\b',
    r'\b(Mitsubishi|Keyence|Fanuc|Siemens|Omron|SMC|Festo|IAI|Cognex)\b',
    r'\b(MELSEC|GOT|GX\s*Works|iQ\-R|FX\d|Q\d+)\b',
    r'\b(Ethernet|PROFINET|CC-Link|DeviceNet|Modbus|RS-?232|RS-?485)\b',
    r'\b(torque|tension|pressure|temperature|humidity|flow|speed|rpm|feed\s*rate)\b',
    r'\b(alarm|error|interlock|emergency|safety|E-?stop)\b',
    r'\b(origin|home|teaching|jog|manual|auto|semi-auto|cycle)\b',
]

for pattern in en_patterns:
    for m in re.finditer(pattern, combined, re.IGNORECASE):
        term = m.group(0).strip()
        # 정규화: 소문자
        en_terms[term.lower()] += 1

# 한글 기술 용어 패턴
ko_terms = Counter()
ko_patterns = [
    r'(서보|모터|엔코더|센서|액추에이터|실린더|밸브|솔레노이드)',
    r'(그리퍼|척|콜렛|스핀들|아버|맨드릴|터렛)',
    r'(팔레트|스페이서|봉|매거진|호퍼|피더|컨베이어|엘리베이터)',
    r'(진공|공압|유압|컴프레서|레귤레이터|필터)',
    r'(코팅|스퍼터링|증착|에칭|어닐링|소결|템퍼링|경화|퀜칭)',
    r'(연삭|호닝|래핑|폴리싱|프레스|브레이징|용접)',
    r'(인서트|초경|텅스텐|코발트|기재|타겟)',
    r'(비전|카메라|렌즈|조명|검사|측정|불량|부적합)',
    r'(벨트|풀리|기어|베어링|부싱|샤프트|커플링|플랜지)',
    r'(인버터|차단기|퓨즈|변압기|접촉기|릴레이|열전대)',
    r'(냉각수|노즐|칠러|히터|윤활유|그리스)',
    r'(로봇|매니퓰레이터|핸들러|로더|언로더|소터|패커)',
    r'(지그|고정구|클램프|스토퍼|가이드|레일|슬라이드|블록)',
    r'(토크|장력|압력|온도|습도|유량|속도|이송속도)',
    r'(알람|에러|인터록|비상정지|안전|원점|티칭|조그|수동|자동|반자동|사이클)',
    r'(다이아몬드|CBN|세라믹|서멧|질화물|탄화물|산화물)',
    r'(외경|내경|공차|진원도|조도|평탄도|동심도|직각도)',
    r'(주축|이송축|공구대|심압대|방진구|척킹)',
    r'(터치스크린|디스플레이|제어반|분전반|조작반)',
    r'(흡착|이젝터|진공패드|흡착패드)',
    r'(스크류|볼스크류|LM가이드|리니어|액추에이터)',
    r'(마킹|레이저|각인|바코드|QR코드|트레이서빌리티)',
]

for pattern in ko_patterns:
    for m in re.finditer(pattern, combined):
        ko_terms[m.group(0)] += 1

print(f"\nEnglish terms found: {len(en_terms)}")
print(f"Korean terms found: {len(ko_terms)}")

# 상위 출력
print("\n── Top English terms ──")
for t, c in en_terms.most_common(50):
    print(f"  {t}: {c}")

print("\n── Top Korean terms ──")
for t, c in ko_terms.most_common(50):
    print(f"  {t}: {c}")

# ── 3) 파일명에서 장비 유형 추출 ──
equipment_types = Counter()
for fname in os.listdir(PARSED_DIR):
    # 장비 유형 키워드
    for kw in ["PVD", "CVD", "Honing", "Press", "Grinding", "Sintering", "Packing",
                "Inspection", "Robot", "Loader", "Unloader", "Sorter", "Handler",
                "Laser", "Marking", "Vision", "Keyence", "Insert"]:
        if kw.lower() in fname.lower():
            equipment_types[kw] += 1

print("\n── Equipment types from filenames ──")
for t, c in equipment_types.most_common():
    print(f"  {t}: {c}")
