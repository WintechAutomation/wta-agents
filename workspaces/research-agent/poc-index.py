"""
포장혼입검사 7페이지 LightRAG 인덱싱 → Neo4j 적재
LLM: Ollama gemma4:12b (182.224.6.147:11434)
Embedding: Ollama qwen3-embedding:8b
"""
import sys, os, asyncio, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
import numpy as np

# Neo4j 환경변수 설정 (env 파일에서 읽기)
env_file = Path("C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env")
for line in env_file.read_text().splitlines():
    if line.startswith("NEO4J_AUTH=neo4j/"):
        pw = line.split("/", 1)[1].strip()
        break

os.environ["NEO4J_URI"] = "bolt://localhost:7688"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = pw

OLLAMA_BASE = "http://182.224.6.147:11434"
LLM_MODEL = "gemma4:12b"      # 없으면 qwen3-vl:8b 사용
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2048

WORKING_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/poc-working")
WORKING_DIR.mkdir(exist_ok=True)
TXT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts")


async def ollama_llm(prompt, system_prompt=None, history_messages=[], **kwargs):
    """Ollama LLM 호출"""
    import aiohttp
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history_messages:
        messages.append(msg)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096},
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            data = await resp.json()
            return data["message"]["content"]


async def ollama_embed(texts: list[str]) -> np.ndarray:
    """Ollama 임베딩"""
    import aiohttp
    results = []
    async with aiohttp.ClientSession() as session:
        for text in texts:
            payload = {"model": EMBED_MODEL, "input": text}
            async with session.post(
                f"{OLLAMA_BASE}/api/embed",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                data = await resp.json()
                emb = data.get("embeddings", [[]])[0]
                # 2048차원으로 패딩/슬라이싱
                if len(emb) > EMBED_DIM:
                    emb = emb[:EMBED_DIM]
                elif len(emb) < EMBED_DIM:
                    emb = emb + [0.0] * (EMBED_DIM - len(emb))
                results.append(emb)
    return np.array(results, dtype=np.float32)


async def check_ollama_model():
    """LLM 모델 가용성 확인"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{OLLAMA_BASE}/api/tags") as resp:
            data = await resp.json()
            models = [m["name"] for m in data.get("models", [])]
            print(f"사용 가능 Ollama 모델: {models[:8]}")
            if LLM_MODEL not in models:
                # fallback
                for fallback in ["qwen3-vl:8b", "gemma4:e4b", "gemma4:e2b", "qwen2.5-coder:32b"]:
                    if fallback in models:
                        print(f"  {LLM_MODEL} 없음 → {fallback} 사용")
                        return fallback
            return LLM_MODEL


async def main():
    global LLM_MODEL

    print("=== Ollama 연결 확인 ===")
    LLM_MODEL = await check_ollama_model()
    print(f"LLM: {LLM_MODEL}")

    # aiohttp 설치 확인
    try:
        import aiohttp
    except ImportError:
        print("aiohttp 설치 중...")
        os.system("pip install aiohttp -q")
        import aiohttp

    print("\n=== LightRAG 초기화 ===")
    from lightrag import LightRAG
    from lightrag.utils import EmbeddingFunc

    rag = LightRAG(
        working_dir=str(WORKING_DIR),
        llm_model_func=ollama_llm,
        embedding_func=EmbeddingFunc(
            embedding_dim=EMBED_DIM,
            max_token_size=8192,
            func=ollama_embed,
        ),
        graph_storage="Neo4JStorage",
        kv_storage="JsonKVStorage",
        vector_storage="NanoVectorDBStorage",
        doc_status_storage="JsonDocStatusStorage",
        llm_model_max_async=1,
        embedding_func_max_async=1,
        max_parallel_insert=1,
        entity_extract_max_gleaning=1,
    )
    await rag.initialize_storages()
    print("Neo4j 연결 완료 (bolt://localhost:7688)")

    txt_files = sorted(TXT_DIR.glob("*.txt"))
    print(f"\n총 {len(txt_files)}개 파일 인덱싱 시작\n")

    for i, txt_file in enumerate(txt_files, 1):
        text = txt_file.read_text(encoding="utf-8")
        print(f"[{i}/{len(txt_files)}] {txt_file.name[:60]} ({len(text):,}자)")
        try:
            await rag.ainsert(text)
            print(f"  -> 완료")
        except Exception as e:
            print(f"  -> 오류: {e}")
        await asyncio.sleep(1)

    print("\n=== 인덱싱 완료 ===")
    await rag.finalize_storages()

    # Neo4j 적재 결과 확인
    print("\n=== Neo4j 노드/관계 수 확인 ===")
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver("bolt://localhost:7688", auth=("neo4j", pw))
    with driver.session() as session:
        node_count = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        labels = [r["label"] for r in session.run("CALL db.labels() YIELD label RETURN label")]
        print(f"노드: {node_count}개, 관계: {rel_count}개")
        print(f"레이블: {labels}")
    driver.close()


if __name__ == "__main__":
    asyncio.run(main())
