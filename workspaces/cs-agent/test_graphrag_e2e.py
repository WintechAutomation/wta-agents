"""CS GraphRAG E2E 테스트 — 샘플 질문 5건 검증."""
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from cs_pipeline import run

SAMPLE_QUERIES = [
    "디버링 설정 변경 방법",
    "인서트 위치 보정 어떻게 해",
    "Polygon Tool 영역 지정 방법",
    "파스텍 E-004 에러 원인",
    "AGV 원점 설정 절차",
]


def test_query(q: str) -> dict:
    print(f"\n{'='*70}")
    print(f"질문: {q}")
    print("=" * 70)

    try:
        result = run(q)
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"query": q, "error": str(e)}

    gr = result["graph_result"]
    print(f"키워드: {gr.get('keywords', [])}")
    print(f"엔티티: {gr.get('node_count', 0)}개, 관계: {gr.get('rel_count', 0)}개")
    print(f"needs_dbmanager: {result['needs_dbmanager']}")
    print(f"rag_source: {result['rag_source']}")

    top3 = result["rag_results"][:3]
    print(f"\n상위 3개 엔티티:")
    for i, n in enumerate(top3, 1):
        labels = ",".join(n.get("labels", []))
        print(f"  {i}. [{labels}] {n.get('name', '')}")
        desc = n.get("properties", {}).get("description", "")
        if desc:
            print(f"     {desc[:150]}")

    return {
        "query": q,
        "node_count": gr.get("node_count", 0),
        "rel_count": gr.get("rel_count", 0),
        "needs_dbmanager": result["needs_dbmanager"],
        "top_entities": [n.get("name", "") for n in top3],
    }


if __name__ == "__main__":
    results = [test_query(q) for q in SAMPLE_QUERIES]
    print(f"\n{'='*70}")
    print("[요약]")
    print("=" * 70)
    for r in results:
        if "error" in r:
            print(f"❌ {r['query']}: {r['error']}")
        else:
            mark = "✅" if r["node_count"] >= 1 else "⚠"
            print(f"{mark} {r['query']:35s} → {r['node_count']}노드 {r['rel_count']}관계 / 폴백필요={r['needs_dbmanager']}")
