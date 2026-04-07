"""
wmx_license 테이블에 매칭 컬럼 추가 및 프로젝트 매칭 데이터 업데이트
실행: py db-write-wmx-match.py
"""
import os
import sys
import psycopg2

def load_mes_password():
    env_path = "C:/MES/backend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    return None

# 1단계: 컬럼 추가
ADD_COLUMNS = """
ALTER TABLE hardware.wmx_license
    ADD COLUMN IF NOT EXISTS matched_project_id   INTEGER,
    ADD COLUMN IF NOT EXISTS matched_project_name VARCHAR(300),
    ADD COLUMN IF NOT EXISTS match_type           VARCHAR(20),
    ADD COLUMN IF NOT EXISTS match_confidence     VARCHAR(10);
"""

# 2단계: exact_erp 매칭 UPDATE
# erp_project_code가 일치하는 경우 — 1:1 정확 매칭
UPDATE_EXACT = """
UPDATE hardware.wmx_license w
SET
    matched_project_id   = p.id,
    matched_project_name = p.name,
    match_type           = 'exact_erp',
    match_confidence     = 'high'
FROM public.api_project p
WHERE p.erp_project_code = w.project_number
  AND w.project_number IS NOT NULL;
"""

# 3단계: fuzzy_name 매칭 UPDATE
# exact 미매칭 행 중 업체명+장비명 유사 매칭
# 1:N 과매칭 해소: pg_trgm similarity로 가장 유사도 높은 프로젝트 1건만 선택
# similarity(p.name, w.equipment_name) + similarity(p.customer_name, w.company_name) 합산 최고값
UPDATE_FUZZY = """
UPDATE hardware.wmx_license w
SET
    matched_project_id   = sub.project_id,
    matched_project_name = sub.project_name,
    match_type           = 'fuzzy_name',
    match_confidence     = CASE
        WHEN sub.total_sim >= 0.6 THEN 'medium'
        ELSE 'low'
    END
FROM (
    SELECT DISTINCT ON (w2.id)
        w2.id AS wmx_id,
        p.id  AS project_id,
        p.name AS project_name,
        similarity(p.name, w2.equipment_name)
            + COALESCE(similarity(p.customer_name, w2.company_name), 0) AS total_sim
    FROM hardware.wmx_license w2
    JOIN public.api_project p
      ON p.name ILIKE '%' || w2.equipment_name || '%'
      AND (
            p.customer_name ILIKE '%' || w2.company_name || '%'
            OR w2.company_name ILIKE '%' || p.customer_name || '%'
          )
    WHERE w2.match_type IS NULL
      AND w2.equipment_name IS NOT NULL
      AND w2.company_name IS NOT NULL
      AND length(w2.equipment_name) >= 3
      AND length(w2.company_name) >= 2
      AND length(p.customer_name) >= 2
    ORDER BY w2.id, total_sim DESC
) sub
WHERE w.id = sub.wmx_id;
"""

STATS_SQL = """
SELECT
    match_type,
    match_confidence,
    COUNT(*) AS cnt
FROM hardware.wmx_license
GROUP BY match_type, match_confidence
ORDER BY match_type NULLS LAST, match_confidence;
"""

def main():
    password = load_mes_password()
    if not password:
        print("[오류] MES DB 비밀번호를 찾을 수 없습니다.")
        sys.exit(1)

    conn = psycopg2.connect(
        host="localhost", port=55432, user="postgres",
        password=password, dbname="postgres"
    )
    conn.autocommit = False

    try:
        cur = conn.cursor()

        print("[1단계] 컬럼 추가...")
        cur.execute(ADD_COLUMNS)
        conn.commit()
        print("  → matched_project_id / matched_project_name / match_type / match_confidence 추가 완료")

        print("[2단계] exact_erp 매칭 UPDATE...")
        cur.execute(UPDATE_EXACT)
        exact_cnt = cur.rowcount
        conn.commit()
        print(f"  → exact_erp 매칭: {exact_cnt}건")

        print("[3단계] fuzzy_name 매칭 UPDATE (pg_trgm similarity)...")
        cur.execute(UPDATE_FUZZY)
        fuzzy_cnt = cur.rowcount
        conn.commit()
        print(f"  → fuzzy_name 매칭: {fuzzy_cnt}건")

        print("[통계]")
        cur.execute(STATS_SQL)
        rows = cur.fetchall()
        total = 0
        for match_type, confidence, cnt in rows:
            label = match_type or "미매칭"
            conf  = confidence or "-"
            print(f"  {label} / {conf}: {cnt}건")
            total += cnt
        print(f"  합계: {total}건")

    except Exception as e:
        conn.rollback()
        print(f"[오류] {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
