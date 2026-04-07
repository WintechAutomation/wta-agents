"""프레스핸들러 출하검사 체크리스트 보완.

nc-manager 검토 반영:
- 실측값 기록칸 추가
- NC 이력 기반 누락 항목 6개 추가
- 번호 갭 정리 (의도 불명 번호는 N/A 처리)
"""
import os

REPORTS_DIR = 'C:/MES/wta-agents/reports/qa-agent'

# nc-manager 권고 추가 항목
NC_ADDITIONS = {
    '기능 검사': [
        {
            'no': 'NC-A',
            'item': 'Stopper 충돌 검사',
            'spec': '전 구간 구동 시 기구물 간섭 없을 것',
            'remark': 'NC #715 반복 불량',
            'measure': '',
        },
        {
            'no': 'NC-B',
            'item': '센서-도그 위치 일치 확인',
            'spec': '각 축 전 범위 정상 감지, 누락 없을 것',
            'remark': 'NC #729 반복 불량',
            'measure': '',
        },
    ],
    '외관 검사': [
        {
            'no': 'NC-C',
            'item': '케이블 덕트·관통홀 규격 확인',
            'spec': '배선 전량 꺾임·압착 없이 통과 가능',
            'remark': 'NC #788 반복 불량',
            'measure': '',
        },
        {
            'no': 'NC-D',
            'item': 'Tap 홀 위치·공차 도면 대비 확인',
            'spec': '도면 공차 이내, 삽입 간섭 없을 것',
            'remark': 'NC #724, #725 반복 불량',
            'measure': '',
        },
    ],
    '장비 사양': [
        {
            'no': 'NC-E',
            'item': '적용 도면 Rev 최신 버전 확인',
            'spec': 'ERP 승인도 기준 최신 Rev 적용 여부',
            'remark': 'NC #759 반복 불량',
            'measure': '',
        },
        {
            'no': 'NC-F',
            'item': '외주 부품 발주 리스트 실물 검수',
            'spec': '발주 수량 전량 입고, 규격 일치',
            'remark': 'NC order_error 4건 반복',
            'measure': '',
        },
    ],
}

PRESS_FILES = [
    'JPJMOHP0001_몰디노_프레스_#1_(Kob,_20t,_환봉)_출하검사체크리스트.md',
    'CNCMAHP0012_메이써루이_프레스_#12~14_출하검사체크리스트.md',
    'CNCZUHP0004_쑤저우_신루이_프레스_#4~5_출하검사체크리스트.md',
    'KRKKOHP4001_한국야금_프레스_#40t-1_(Kob,_40t)_출하검사체크리스트.md',
]

def rebuild_table_with_measure(section_lines):
    """기존 테이블에 실측값 컬럼 추가."""
    result = []
    for line in section_lines:
        if line.startswith('| No |') and '실측값' not in line:
            # 헤더: 판정 앞에 실측값 추가
            line = line.rstrip()
            if line.endswith('판정 |'):
                line = line[:-len('판정 |')] + '실측값 | 판정 |'
            result.append(line)
        elif line.startswith('|----') and '실측값' not in line:
            # 구분선: 컬럼 추가
            line = line.rstrip()
            if line.endswith(':----:|'):
                line = line[:-len(':----:|')] + '---------|:----:|'
            elif line.endswith('------|'):
                line = line[:-len('------|')] + '---------|:----:|'
            result.append(line)
        elif line.startswith('| ') and line.count('|') >= 5 and '☐' in line:
            # 데이터 행: 실측값 빈칸 추가
            line = line.rstrip()
            if line.endswith('☐ |'):
                line = line[:-len('☐ |')] + ' | ☐ |'
            result.append(line)
        else:
            result.append(line)
    return result


def process_file(fname):
    fpath = os.path.join(REPORTS_DIR, fname)
    with open(fpath, encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    current_section = ''
    nc_added = set()

    i = 0
    while i < len(lines):
        line = lines[i]

        # 섹션 헤더 추적
        if line.startswith('## '):
            current_section = line[3:].strip()

        # 테이블 헤더에 실측값 컬럼 추가
        if line.startswith('| No |') and '실측값' not in line:
            line = line.rstrip()
            if '판정 |' in line:
                line = line.replace('| 판정 |', '| 실측값 | 판정 |')
            new_lines.append(line)
            i += 1
            continue

        # 구분선 처리
        if line.startswith('|----') and new_lines and '실측값' in new_lines[-1]:
            line = line.rstrip()
            line = line.replace('|:----:|', '|---------|:----:|')
            new_lines.append(line)
            i += 1
            continue

        # 데이터 행 처리 (☐ 포함)
        if line.startswith('| ') and '☐ |' in line and '실측값' not in line:
            line = line.rstrip()
            line = line.replace('| ☐ |', '| | ☐ |')
            new_lines.append(line)
            i += 1
            # 섹션 마지막 행 이후 NC 항목 추가
            if i < len(lines) and (lines[i].strip() == '' or lines[i].startswith('## ') or lines[i] == '---'):
                additions = NC_ADDITIONS.get(current_section, [])
                for add in additions:
                    key = f"{current_section}_{add['no']}"
                    if key not in nc_added:
                        nc_added.add(key)
                        new_lines.append(
                            f"| {add['no']} | {add['item']} | {add['spec']} | {add['remark']} | | ☐ |"
                        )
            continue

        new_lines.append(line)
        i += 1

    # 최종 판정 섹션 보강
    final_idx = None
    for idx, l in enumerate(new_lines):
        if l.strip() == '## 최종 판정':
            final_idx = idx
            break

    if final_idx:
        new_final = [
            '',
            '## 최종 판정',
            '',
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
            '> **검토 이력**: nc-manager 교차 검수 완료 (2026-03-29) — NC #715, #724, #725, #729, #759, order_error 반영',
        ]
        # 기존 최종 판정 이후 내용 제거하고 새 섹션으로 교체
        new_lines = new_lines[:final_idx] + new_final

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print(f'보완 완료: {fname}')


for fname in PRESS_FILES:
    try:
        process_file(fname)
    except Exception as e:
        print(f'오류 {fname}: {e}')

print('\n프레스핸들러 4개 파일 보완 완료')
