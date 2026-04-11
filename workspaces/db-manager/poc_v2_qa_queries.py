"""
manual.documents_v2 QA 검증 — pgvector 검색 5건 + 부가 쿼리 3건
임베딩: Qwen3-Embedding-8B (182.224.6.147:11434), 2000dim 슬라이싱
"""
import json
import time
import psycopg2
import psycopg2.extras
import urllib.request

QWEN_URL = "http://182.224.6.147:11434/api/embed"
QWEN_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000
DB = dict(host="localhost", port=55432, user="postgres",
          password="your-super-secret-and-long-postgres-password", dbname="postgres")


def embed(text: str) -> list[float]:
    body = json.dumps({"model": QWEN_MODEL, "input": text, "keep_alive": "10m"}).encode()
    req = urllib.request.Request(QWEN_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        vec = json.loads(r.read())["embeddings"][0]
    return vec[:EMBED_DIM]


def vec_literal(v):
    return "[" + ",".join(format(float(x), ".6g") for x in v) + "]"


QUERIES = [
    {
        "id": "Q1",
        "q": "V1000 서보 전원 결선도",
        "filter": "(category IN ('5_inverter','1_robot')) AND (mfr='Yaskawa' OR content ILIKE '%V1000%')",
        "select": "file_id, chunk_id, mfr, model, lang, section_path, LEFT(content, 200) AS preview, "
                  "jsonb_array_length(COALESCE(figure_refs,'[]'::jsonb)) AS figs",
    },
    {
        "id": "Q2",
        "q": "에러코드 E401 원인과 복구 방법",
        "filter": "content ~* 'E\\s*401|에러\\s*401|E401'",
        "select": "file_id, chunk_id, mfr, model, lang, doctype, LEFT(content, 300) AS preview, "
                  "jsonb_array_length(COALESCE(figure_refs,'[]'::jsonb)) AS figs",
    },
    {
        "id": "Q3",
        "q": "Mitsubishi CR 컨트롤러 초기 셋업 절차",
        "filter": "category='1_robot' AND mfr='Mitsubishi' AND doctype ILIKE '%setup%'",
        "select": "file_id, chunk_id, mfr, model, lang, doctype, section_path, LEFT(content, 300) AS preview, "
                  "figure_refs->0->>'storage_path' AS fig0_path, "
                  "figure_refs->0->>'vlm_description' AS fig0_vlm",
    },
    {
        "id": "Q4",
        "q": "pick and place 로봇 최대 가반중량",
        "filter": "category='1_robot' AND doctype ILIKE '%spec%'",
        "select": "file_id, chunk_id, mfr, model, lang, LEFT(content, 300) AS preview, "
                  "jsonb_array_length(COALESCE(figure_refs,'[]'::jsonb)) AS figs, "
                  "jsonb_array_length(COALESCE(table_refs,'[]'::jsonb)) AS tbls",
    },
    {
        "id": "Q5",
        "q": "CC-Link 국번 설정 방법",
        "filter": "content ILIKE '%CC-Link%' OR content ILIKE '%CCLink%'",
        "select": "file_id, chunk_id, mfr, model, lang, doctype, LEFT(content, 300) AS preview, "
                  "figure_refs->0->>'vlm_description' AS fig0_vlm, inline_refs",
    },
]


def run_search(cur, q):
    t0 = time.time()
    qvec = embed(q["q"])
    embed_ms = (time.time() - t0) * 1000

    vlit = vec_literal(qvec)
    # %를 %%로 이스케이프 (psycopg2 placeholder 충돌 방지)
    filt = q['filter'].replace('%', '%%')
    sel = q['select'].replace('%', '%%')
    sql = f"""
    SELECT {sel},
           1 - (embedding <=> %s::vector) AS similarity
    FROM manual.documents_v2
    WHERE {filt}
    ORDER BY embedding <=> %s::vector
    LIMIT 5
    """
    t1 = time.time()
    cur.execute(sql, (vlit, vlit))
    rows = cur.fetchall()
    search_ms = (time.time() - t1) * 1000

    return rows, embed_ms, search_ms


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    results = {"searches": {}, "stats": {}}

    for q in QUERIES:
        print(f"\n=== {q['id']}: {q['q']} ===")
        try:
            rows, em_ms, sr_ms = run_search(cur, q)
            print(f"  embed={em_ms:.0f}ms  search={sr_ms:.0f}ms  hits={len(rows)}")
            clean_rows = []
            for i, r in enumerate(rows, 1):
                d = dict(r)
                sim = float(d.pop("similarity"))
                print(f"  [{i}] {d.get('file_id')}/{d.get('chunk_id')} sim={sim:.4f} mfr={d.get('mfr')} lang={d.get('lang','-')}")
                d["similarity"] = round(sim, 4)
                # JSON 직렬화 보호
                for k, v in list(d.items()):
                    if isinstance(v, (dict, list)):
                        pass
                clean_rows.append(d)
            results["searches"][q["id"]] = {
                "query": q["q"],
                "filter": q["filter"],
                "embed_ms": round(em_ms, 1),
                "search_ms": round(sr_ms, 1),
                "hits": clean_rows,
            }
        except Exception as e:
            print(f"  ERROR: {e}")
            results["searches"][q["id"]] = {"query": q["q"], "error": str(e)}

    # --- 부가 쿼리 3건 ---
    print("\n=== V1. category 통계 ===")
    cur.execute("""
    SELECT category, COUNT(*) AS chunks,
      SUM(jsonb_array_length(COALESCE(figure_refs,'[]'::jsonb))) AS fig_refs,
      SUM(jsonb_array_length(COALESCE(table_refs,'[]'::jsonb))) AS tbl_refs
    FROM manual.documents_v2 GROUP BY category ORDER BY category
    """)
    v1 = [dict(r) for r in cur.fetchall()]
    for r in v1:
        print(f"  {r}")
    results["stats"]["V1_category"] = v1

    print("\n=== V2. missing storage ===")
    cur.execute("""
    SELECT COUNT(*) AS chunks_with_missing_storage
    FROM manual.documents_v2,
         jsonb_array_elements(figure_refs) AS fr
    WHERE fr->>'storage_path' IS NULL OR fr->>'image_url' IS NULL
    """)
    v2 = dict(cur.fetchone())
    print(f"  {v2}")
    results["stats"]["V2_missing_storage"] = v2

    print("\n=== V3. VLM coverage ===")
    cur.execute("""
    SELECT
      SUM(CASE WHEN fr->>'vlm_description' IS NOT NULL AND fr->>'vlm_description' <> '' THEN 1 ELSE 0 END) AS with_vlm,
      COUNT(*) AS total_figs
    FROM manual.documents_v2,
         jsonb_array_elements(figure_refs) AS fr
    """)
    v3 = dict(cur.fetchone())
    if v3["total_figs"]:
        v3["pct"] = round(100 * v3["with_vlm"] / v3["total_figs"], 2)
    print(f"  {v3}")
    results["stats"]["V3_vlm_coverage"] = v3

    conn.close()

    with open("C:/MES/wta-agents/workspaces/db-manager/poc_v2_qa_results.json",
              "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print("\nsaved: poc_v2_qa_results.json")


if __name__ == "__main__":
    main()
