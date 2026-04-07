"""gen_qc_checklists.py — 제작 중 프로젝트별 출하검사 체크리스트 MD 생성."""
import json
import os

with open('C:/MES/wta-agents/data/qc_checklists/checklist_items_full.json', encoding='utf-8') as f:
    raw = json.load(f)

machine_alias = {
    '프레스핸들러': '1. Press Handler',
    'PVD': '6. PVD Machine',
    '호닝형상검사기': '8. 호닝형상 검사기',
    '소결취출기': '2. Sintering Machine',
    '리팔레팅': '12. Repalleting',
    '연삭핸들러': '3. Grinding Handler',
    'CVD': '5. CVD Machine',
    '포장기': '9. Packing Machine',
    '검사기': '7. Insert Inspection',
}

projects = [
    ('KRWTAHIM2201', '[선제작] 호닝형상검사기 #22-1', 'WTA', '호닝형상검사기', 'in_progress', '2023-02-24'),
    ('KRWTAHS42302', '스탈리연삭핸들러 (언로딩)', 'WTA', '리팔레팅', 'in_progress', '2023-08-21'),
    ('KRWTAHS42301', '스탈리연삭핸들러 (로딩)', 'WTA', '리팔레팅', 'in_progress', '2023-09-15'),
    ('KRWTAHS32401', '[선제작] 소결취출기 #24-1 (VE)', 'WTA', '소결취출기', 'in_progress', '2024-10-10'),
    ('KRWTAHIM2304', '[선제작] 호닝형상검사기 #23-4', 'WTA', '호닝형상검사기', 'in_progress', '2024-12-31'),
    ('KRWTAHIM2302', '[선제작] 호닝형상검사기 #23-2', 'WTA', '호닝형상검사기', 'in_progress', '2024-12-31'),
    ('KRWTAHS22501', '[선제작] PVD 로딩 #25-1', 'WTA', 'PVD', 'in_progress', '2025-08-29'),
    ('KRWTAHPL2501', '[선제작] 포장기 #25-1 (교세라CN)', 'WTA', '포장기', 'in_progress', '2025-08-29'),
    ('KRWTAHS22301', '[선제작] PVD 로딩 #23-1', 'WTA', 'PVD', 'in_progress', '2025-09-22'),
    ('KRWTAHS22302', '[선제작] PVD 언로딩 #23-2', 'WTA', 'PVD', 'in_progress', '2026-01-29'),
    ('KRWTAHG2201', '연삭기핸들러', 'WTA', '연삭핸들러', 'in_progress', '2026-01-30'),
    ('JPJMOHS20001', '몰디노 PVD-L #1', '몰디노', 'PVD', 'in_progress', '2026-03-16'),
    ('KRKTGHS20001', '대구텍 PVD-UL #1 (개조)', '대구텍', 'PVD', 'in_progress', '2026-03-23'),
    ('KRKKOHS20005', '한국야금 PVD 로딩 #5,#6 (선제작)', '한국야금', 'PVD', 'in_progress', '2026-04-02'),
    ('JPJMOHP0001', '몰디노 프레스 #1 (Kob, 20t, 환봉)', '몰디노', '프레스핸들러', 'in_progress', '2026-04-06'),
    ('CNCMAHP0012', '메이써루이 프레스 #12~14', '메이써루이', '프레스핸들러', 'in_progress', '2026-05-04'),
    ('KRKKOHS10004', '한국야금 CVD #4', '한국야금', 'CVD', 'in_progress', '2026-05-08'),
    ('CNCZUHP0004', '쑤저우 신루이 프레스 #4~5', '신루이', '프레스핸들러', 'in_progress', '2026-05-12'),
    ('KRWTAHIM2501', '다인정공 F1 #1 (#25-1)_딥러닝', '다인정공', '검사기', 'in_progress', '2026-05-27'),
    ('KRKKOHP4001', '한국야금 프레스 #40t-1 (Kob, 40t)', '한국야금', '프레스핸들러', 'in_progress', '2026-05-28'),
    ('KRKTGHIM0001', '대구텍 검사기 F2 #1', '대구텍', '검사기', 'in_progress', '2026-09-02'),
    ('HS3ME02308003', '하이썽 소결취출기 #2 (#23-5)', '깐조우 하이썽', '소결취출기', 'on_hold', '2026-03-25'),
    ('CNCGSHP0010', '하이썽 프레스 핸들러 #10', '깐조우 하이썽', '프레스핸들러', 'setting_up', '2026-02-04'),
    ('CNCGSHP0009', '하이썽 프레스 핸들러 #9', '깐조우 하이썽', '프레스핸들러', 'setup', '2026-02-04'),
]

checklist_db = {}
for alias_key, folder_key in machine_alias.items():
    items = raw.get(folder_key, [])
    if items:
        checklist_db[alias_key] = items

out_dir = 'C:/MES/wta-agents/reports/qa-agent'
os.makedirs(out_dir, exist_ok=True)

status_label_map = {
    'in_progress': '제작 중',
    'on_hold': '보류',
    'setting_up': '셋업 중',
    'setup': '셋업',
}

files_created = []

for code, name, customer, equip_type, status, due in projects:
    items = checklist_db.get(equip_type, [])
    folder_key = machine_alias.get(equip_type, '')
    machine_std = folder_key.split('. ', 1)[1] if '. ' in folder_key else equip_type
    status_str = status_label_map.get(status, status)

    lines = []
    lines.append(f'# 출하검사 체크리스트 — {name}')
    lines.append('')
    lines.append('## 프로젝트 정보')
    lines.append('')
    lines.append('| 항목 | 내용 |')
    lines.append('|------|------|')
    lines.append(f'| 프로젝트 코드 | {code} |')
    lines.append(f'| 프로젝트명 | {name} |')
    lines.append(f'| 고객사 | {customer} |')
    lines.append(f'| 장비 유형 | {machine_std} |')
    lines.append(f'| 상태 | {status_str} |')
    lines.append(f'| 납기일 | {due} |')
    lines.append('')
    lines.append('---')
    lines.append('')

    if not items:
        lines.append(f'> 장비 유형 **{equip_type}**에 대한 체크리스트 항목 데이터가 없습니다.')
    else:
        cur_cat = ''
        for item in items:
            cat = item.get('category', '')
            if cat and cat != cur_cat:
                cur_cat = cat
                if lines and lines[-1] != '':
                    lines.append('')
                lines.append(f'## {cur_cat}')
                lines.append('')
                lines.append('| No | 항목 | 검사 기준 | 비고 | 판정 |')
                lines.append('|----|------|---------|------|:----:|')
            spec = (item.get('specification') or '').replace('\n', ' ').replace('\r', '')[:80]
            remark = (item.get('remark') or '').replace('\n', ' ')[:40]
            item_name = (item.get('item_name') or '')
            seq = item.get('seq', '')
            lines.append(f'| {seq} | {item_name} | {spec} | {remark} | ☐ |')

        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('## 최종 판정')
        lines.append('')
        lines.append('| 항목 | 내용 |')
        lines.append('|------|------|')
        lines.append('| 검사일 |  |')
        lines.append('| 검사자 |  |')
        lines.append('| 확인자 |  |')
        lines.append('| 판정 | ☐ 합격  ☐ 불합격 |')
        lines.append('| 특이사항 |  |')

    safe_name = name.replace('/', '-').replace('[', '').replace(']', '').replace(' ', '_')
    fname = f'{code}_{safe_name}_출하검사체크리스트.md'
    fpath = os.path.join(out_dir, fname)
    with open(fpath, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines))
    files_created.append((code, name, customer, equip_type, len(items), fname))
    print(f'생성: {fname} ({len(items)}항목)')

# 인덱스 파일
idx_lines = [
    '# 제작 중 프로젝트 출하검사 체크리스트 인덱스',
    '',
    '> 작성일: 2026-03-29  |  총 {}개 프로젝트'.format(len(files_created)),
    '',
    '| 코드 | 프로젝트명 | 고객사 | 장비 유형 | 검사 항목 수 | 파일 |',
    '|------|----------|------|---------|------------|------|',
]
for code, name, customer, equip, cnt, fname in files_created:
    cnt_str = str(cnt) if cnt else '데이터 없음'
    idx_lines.append(f'| {code} | {name} | {customer} | {equip} | {cnt_str} | [{fname}](./{fname}) |')

idx_path = os.path.join(out_dir, '2026-03-29_출하검사체크리스트_인덱스.md')
with open(idx_path, 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(idx_lines))

print(f'\n완료: {len(files_created)}개 파일')
print(f'인덱스: {idx_path}')
