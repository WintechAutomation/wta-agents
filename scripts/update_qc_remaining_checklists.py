"""나머지 납기내 체크리스트 보완 (PVD, CVD, 검사기).

nc-manager 검토 반영:
- 실측값 기록칸 추가
- NC 이력 기반 항목 추가
- 최종 판정 섹션 보강
"""
import os

REPORTS_DIR = 'C:/MES/wta-agents/reports/qa-agent'

# 파일별 NC 추가 항목 정의
FILE_NC_ADDITIONS = {
    'KRKKOHS20005_한국야금_PVD_로딩_#5,#6_(선제작)_출하검사체크리스트.md': {
        'nc_note': 'NC #734, #736, #743, #747, #796 반영',
        'additions': {
            '기능 검사': [
                {
                    'no': 'NC-A',
                    'item': '이콘함·전장박스 개폐 작업 공간 확인',
                    'spec': '성인 손 진입 가능 공간 확보',
                    'remark': 'NC #796 미조치 — 출하 전 반드시 확인',
                },
                {
                    'no': 'NC-B',
                    'item': '픽업 툴 R축 전 범위 간섭 확인',
                    'spec': '전 구간 구동 시 센서/도그 간섭 없을 것',
                    'remark': 'NC #747',
                },
                {
                    'no': 'NC-D',
                    'item': '팔레트 Z축 모터 사양 실물 확인',
                    'spec': '발주서 대비 토크/rpm 사양 일치',
                    'remark': 'NC #734',
                },
            ],
            '외관 검사': [
                {
                    'no': 'NC-C',
                    'item': '덕트 탭 위치·규격 도면 Rev 최신 확인',
                    'spec': 'ERP 승인도 최신 Rev 적용 여부',
                    'remark': 'NC #743',
                },
                {
                    'no': 'NC-E',
                    'item': '주요 조립 홀탭 위치 도면 대비 실측',
                    'spec': '위치 공차 이내',
                    'remark': 'NC #736',
                },
            ],
        },
        'special_notice': '⚠️ **D-4 긴급**: NC #796 (PAL 이콘함 작업공간) 3/26 등록 미조치 — 출하 전 반드시 조치 완료 확인',
    },
    'KRKKOHS10004_한국야금_CVD_#4_출하검사체크리스트.md': {
        'nc_note': 'NC 이력 없음 — 표준 체크리스트 적용',
        'additions': {},
        'special_notice': '',
    },
    'KRWTAHIM2501_다인정공_F1_#1_(#25-1)_딥러닝_출하검사체크리스트.md': {
        'nc_note': 'NC #287 반영',
        'additions': {
            '기능 검사': [
                {
                    'no': 'NC-A',
                    'item': 'JIG CHANGE 케이블 길이·커넥터 상태 확인',
                    'spec': '피복 손상 없이 전 케이블 고정, 커넥터 정상 체결',
                    'remark': 'NC #287 — JIG 케이블 하네스화',
                },
            ],
        },
        'special_notice': '',
    },
    'KRKTGHIM0001_대구텍_검사기_F2_#1_출하검사체크리스트.md': {
        'nc_note': 'NC 이력 없음 — 표준 체크리스트 적용',
        'additions': {},
        'special_notice': '',
    },
}


def process_file(fname, nc_info):
    fpath = os.path.join(REPORTS_DIR, fname)
    with open(fpath, encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    current_section = ''
    nc_added = set()
    additions = nc_info.get('additions', {})

    i = 0
    while i < len(lines):
        line = lines[i]

        # 섹션 헤더 추적
        if line.startswith('## '):
            current_section = line[3:].strip()

        # 테이블 헤더에 실측값 추가
        if line.startswith('| No |') and '실측값' not in line and '판정 |' in line:
            line = line.replace('| 판정 |', '| 실측값 | 판정 |')
            new_lines.append(line)
            i += 1
            continue

        # 구분선 처리
        if line.startswith('|----') and new_lines and '실측값' in new_lines[-1] and '---------|' not in line:
            line = line.replace('|:----:|', '|---------|:----:|')
            if '|:----:|' not in line and line.endswith('------|'):
                line = line[:-len('------|')] + '---------|:----:|'
            new_lines.append(line)
            i += 1
            continue

        # 데이터 행 처리
        if line.startswith('| ') and '☐ |' in line and '| | ☐ |' not in line:
            line = line.replace('| ☐ |', '| | ☐ |')
            new_lines.append(line)
            i += 1
            # 섹션 끝에 NC 항목 추가
            if i < len(lines) and (lines[i].strip() == '' or lines[i].startswith('## ') or lines[i] == '---'):
                for add in additions.get(current_section, []):
                    key = f'{current_section}_{add["no"]}'
                    if key not in nc_added:
                        nc_added.add(key)
                        new_lines.append(
                            f'| {add["no"]} | {add["item"]} | {add["spec"]} | {add["remark"]} | | ☐ |'
                        )
            continue

        new_lines.append(line)
        i += 1

    # 최종 판정 섹션 교체
    final_idx = None
    for idx, l in enumerate(new_lines):
        if l.strip() == '## 최종 판정':
            final_idx = idx
            break

    special = nc_info.get('special_notice', '')
    review_note = f'> **검토 이력**: nc-manager 교차 검수 완료 (2026-03-29) — {nc_info["nc_note"]}'

    new_final = ['', '## 최종 판정', '']
    if special:
        new_final += [special, '']
    new_final += [
        '| 항목 | 내용 |',
        '|------|------|',
        '| 검사일 |  |',
        '| 검사자 |  |',
        '| 확인자 (품질팀) |  |',
        '| 판정 | ☐ 합격  ☐ 조건부합격  ☐ 불합격 |',
        '| 불합격 사유 |  |',
        '| 특이사항 / 조치 내용 |  |',
        '',
        '---',
        '',
        review_note,
    ]

    if final_idx is not None:
        new_lines = new_lines[:final_idx] + new_final
    else:
        new_lines += new_final

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    added_count = sum(len(v) for v in additions.values())
    print(f'완료: {fname} (NC 추가 {added_count}항목)')


for fname, nc_info in FILE_NC_ADDITIONS.items():
    try:
        process_file(fname, nc_info)
    except Exception as e:
        print(f'오류 {fname}: {e}')

print('\n납기내 전체 8건 체크리스트 보완 완료')
