"""
부적합 보고서 등록 스크립트 — db-manager 에이전트 전용
슬랙 메시지에서 파싱된 데이터를 api_nonconformancereport 테이블에 INSERT

사용법:
  python nc-insert.py              # 예시 10개 데이터 일괄 등록
  python nc-insert.py --dry-run    # DB 저장 없이 파싱 결과만 출력
"""
import sys
import os
import json
from datetime import date, datetime, timezone, timedelta

# Windows 콘솔 인코딩 강제 UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KST = timezone(timedelta(hours=9))

def get_db_password():
    env_path = "C:/MES/backend/.env"
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("DB_PASSWORD not found in .env")


def get_next_report_number(cur):
    """오늘 날짜 기준 다음 report_number 생성 (NCyymmXXXX 형식)"""
    today = datetime.now(KST)
    prefix = f"NC{today.strftime('%y%m')}"
    cur.execute(
        "SELECT MAX(report_number) FROM api_nonconformancereport WHERE report_number LIKE %s",
        (f"{prefix}%",)
    )
    row = cur.fetchone()
    if row[0]:
        last_seq = int(row[0][len(prefix):])
        return f"{prefix}{last_seq + 1:04d}"
    return f"{prefix}0001"


def insert_nc_report(cur, data: dict, dry_run: bool = False) -> str:
    """단일 부적합 보고서 INSERT. report_number 반환."""
    report_number = get_next_report_number(cur)
    now = datetime.now(KST)

    params = {
        "report_number": report_number,
        "title": data["title"],
        "nonconformance_type": data["nonconformance_type"],
        "part_no": data.get("part_no", ""),
        "unit_no": data.get("unit_no", ""),
        "start_date": data.get("start_date", now.date()),
        "related_department": data.get("related_department", ""),
        "importance": data["importance"],
        "is_duplicate": data.get("is_duplicate", False),
        "description": data["description"],
        "cause_analysis": data.get("cause_analysis", ""),
        "action_plan": data.get("action_plan", ""),
        "action_result": data.get("action_result", ""),
        "attachment_info": json.dumps(data.get("attachment_info", {})),
        "purchase_request_number": data.get("purchase_request_number", ""),
        "created_at": now,
        "updated_at": now,
    }

    sql = """
        INSERT INTO api_nonconformancereport (
            report_number, title, nonconformance_type, part_no, unit_no,
            start_date, related_department, importance, is_duplicate,
            description, cause_analysis, action_plan, action_result,
            attachment_info, purchase_request_number, created_at, updated_at
        ) VALUES (
            %(report_number)s, %(title)s, %(nonconformance_type)s, %(part_no)s, %(unit_no)s,
            %(start_date)s, %(related_department)s, %(importance)s, %(is_duplicate)s,
            %(description)s, %(cause_analysis)s, %(action_plan)s, %(action_result)s,
            %(attachment_info)s, %(purchase_request_number)s, %(created_at)s, %(updated_at)s
        ) RETURNING id
    """

    if dry_run:
        print(f"  [DRY-RUN] report_number={report_number}")
        print(f"    title={params['title']}")
        print(f"    type={params['nonconformance_type']}, importance={params['importance']}")
        print(f"    part_no={params['part_no']}, unit_no={params['unit_no']}")
        return report_number

    cur.execute(sql, params)
    row = cur.fetchone()
    print(f"  등록 완료: id={row[0]}, report_number={report_number}")
    return report_number


# ── 슬랙 메시지 예시 10개 → 파싱된 데이터 ──────────────────────────────
SAMPLE_DATA = [
    {
        "title": "알루미늄 프레임 치수 초과 (LOT: AL-2603-047)",
        "nonconformance_type": "receiving_error",
        "part_no": "AL-2603-047",
        "unit_no": "3라인",
        "importance": "medium",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "3라인 조장 보고. 오늘 입고된 알루미늄 프레임 (LOT: AL-2603-047) 치수 확인 결과 "
            "규격보다 +0.3mm 초과. 전수검사 필요."
        ),
    },
    {
        "title": "샤프트 직경 불량 — WO-2603-112",
        "nonconformance_type": "machining_defect",
        "part_no": "WO-2603-112",
        "unit_no": "가공",
        "importance": "high",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "WO-2603-112 작업 중 가공된 샤프트 직경이 도면 Ø25h7 대비 0.05mm 언더로 측정됨. "
            "수량 12개 전량 격리 조치."
        ),
    },
    {
        "title": "도장 들뜸 외관불량 — MF-300",
        "nonconformance_type": "machining_defect",
        "part_no": "MF-300",
        "unit_no": "도장",
        "importance": "low",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "도장 공정에서 MF-300 배치 도장 들뜸 현상 3개 확인. 사진 첨부 예정."
        ),
    },
    {
        "title": "볼트 토크 부족 — 4호기 조립",
        "nonconformance_type": "assembly_defect",
        "part_no": "",
        "unit_no": "4호기",
        "importance": "high",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "4호기 조립 중 볼트 토크값 미달. 규격 50Nm 대비 45Nm에서 더 이상 조여지지 않음. "
            "나사산 불량 의심. 현재 작업 중지 상태."
        ),
    },
    {
        "title": "도면 Rev 불일치 — 2라인",
        "nonconformance_type": "design_defect",
        "part_no": "",
        "unit_no": "2라인",
        "importance": "medium",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "2라인 작업 도면 Rev.B와 실제 부품 구멍 위치 불일치. "
            "최신 도면 Rev.C 존재 여부 확인 요청."
        ),
    },
    {
        "title": "PCB기판 납땜 불량 — LOT#260315",
        "nonconformance_type": "receiving_error",
        "part_no": "PCB-LOT#260315",
        "unit_no": "입고검사",
        "importance": "high",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "입고검사 결과: 공급사 A사 PCB기판 LOT#260315 200개 중 5개 납땜 불량 발견. "
            "불량률 2.5%. 반품 처리 예정."
        ),
    },
    {
        "title": "홀 피치 불량 — 프레스 금형 교체 후",
        "nonconformance_type": "machining_defect",
        "part_no": "",
        "unit_no": "프레스",
        "importance": "high",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "프레스 금형 교체 후 첫 샘플 홀 피치가 스펙 대비 0.2mm 틀어짐. "
            "금형 재조정 필요. 공정 홀딩 조치."
        ),
    },
    {
        "title": "출하품 포장 긁힘 — WTA-2025 납품품",
        "nonconformance_type": "machining_defect",
        "part_no": "WTA-2025",
        "unit_no": "출하",
        "importance": "low",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "출하 전 최종 검사 중 WTA-2025 프로젝트 납품품 포장 긁힘 발견. "
            "내부 손상 없음. 재포장 여부 판단 요청."
        ),
    },
    {
        "title": "PCB 쇼트 발생 — PCB-0328-003",
        "nonconformance_type": "assembly_defect",
        "part_no": "PCB-0328-003",
        "unit_no": "테스트라인",
        "importance": "high",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "테스트 라인 전기 점검 중 PCB-0328-003 쇼트 발생. "
            "해당 배치 15개 전량 격리 조치. 원인 파악 중."
        ),
    },
    {
        "title": "용접비드 불균일 — 용접 공정",
        "nonconformance_type": "machining_defect",
        "part_no": "",
        "unit_no": "용접",
        "importance": "medium",
        "related_department": "생산팀",
        "start_date": date(2026, 3, 28),
        "description": (
            "용접 공정 오늘 작업분 용접비드 외관 불균일. "
            "인장시험 미실시 상태. 용접조건 변경 여부 확인 필요."
        ),
    },
]


def main():
    dry_run = "--dry-run" in sys.argv

    import psycopg2
    pw = get_db_password()
    conn = psycopg2.connect(host="localhost", port=55432, user="postgres", password=pw, dbname="postgres")

    if dry_run:
        print("=== DRY-RUN 모드: DB에 저장하지 않습니다 ===\n")
        conn.set_session(readonly=True, autocommit=True)
    else:
        print(f"=== 부적합 보고서 {len(SAMPLE_DATA)}건 등록 시작 ===\n")

    try:
        cur = conn.cursor()
        report_numbers = []

        for i, data in enumerate(SAMPLE_DATA, 1):
            print(f"[{i:02d}] {data['title']}")
            rn = insert_nc_report(cur, data, dry_run=dry_run)
            report_numbers.append(rn)

        if not dry_run:
            conn.commit()
            print(f"\n총 {len(report_numbers)}건 등록 완료")
            print("등록된 report_numbers:", report_numbers)
        else:
            print(f"\n총 {len(report_numbers)}건 (DRY-RUN)")

    except Exception as e:
        if not dry_run:
            conn.rollback()
        print(f"\n[오류] {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
