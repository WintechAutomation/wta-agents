"""
Qwen3-Reranker-4B 파싱 로직 드래프트 (manuals-v2 검색 파이프라인용)
- 모델: dengcao/Qwen3-Reranker-4B:Q8_0 (Ollama 로컬)
- 입력: query + 후보 청크 N개
- 출력: score 내림차순으로 정렬된 청크 리스트
- Ollama /api/generate를 사용하며, yes 토큰 logit을 score로 사용한다.

Reranker 흐름 (docs-agent + db-manager 공동 구현):
1) BM25 + Dense(HNSW) RRF로 Top-K (예: K=50) 후보 추출 — db-manager 쪽 SQL
2) 각 후보에 대해 Qwen3-Reranker로 (query, chunk) 쌍 평가 → score
3) score 상위 Top-N (예: N=5) 반환

Qwen3-Reranker 공식 포맷:
  <|im_start|>system
  Judge whether the Document meets the requirements ...
  <|im_end|>
  <|im_start|>user
  <Instruct>: {task}
  <Query>: {query}
  <Document>: {doc}
  <|im_end|>
  <|im_start|>assistant
  <think>

  </think>

(모델은 "yes" 또는 "no"를 생성하며, 해당 logit을 사용)
"""
from __future__ import annotations
import json
import math
import urllib.request
from typing import Iterable

RERANKER_URL = 'http://localhost:11434/api/generate'  # 로컬 Ollama
RERANKER_MODEL = 'dengcao/Qwen3-Reranker-4B:Q8_0'

TASK_DEFAULT = (
    'Given a Korean/English/Japanese technical manual query, retrieve relevant '
    'document passages that answer the query.'
)

PROMPT_TMPL = (
    '<|im_start|>system\n'
    'Judge whether the Document meets the requirements based on the Query and the Instruct provided. '
    'Note that the answer can only be "yes" or "no".'
    '<|im_end|>\n'
    '<|im_start|>user\n'
    '<Instruct>: {task}\n'
    '<Query>: {query}\n'
    '<Document>: {doc}'
    '<|im_end|>\n'
    '<|im_start|>assistant\n<think>\n\n</think>\n\n'
)


def _post_ollama(payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        RERANKER_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def score_pair(query: str, doc: str, task: str = TASK_DEFAULT) -> float:
    """
    단일 (query, doc) 쌍의 relevance score 반환.
    - Ollama는 raw logit 미노출 → 본 드래프트는 logprobs 방식 사용 (option 'logits'은 미지원)
    - 대안 1: 생성된 응답이 'yes' / 'no' 인지 판단 후 0 또는 1 반환
    - 대안 2: num_predict=1 + raw mode 로 top 토큰 확률을 받아 yes/no softmax
    - 본 드래프트는 대안 1을 사용 (가장 호환성 높음). 정밀 스코어링이 필요하면 vLLM 전환 검토.
    """
    prompt = PROMPT_TMPL.format(task=task, query=query, doc=doc)
    payload = {
        'model': RERANKER_MODEL,
        'prompt': prompt,
        'raw': True,        # 모델의 chat template 회피, 수동 포맷 사용
        'stream': False,
        'keep_alive': '10m',
        'options': {
            'temperature': 0.0,
            'num_predict': 2,   # yes/no 한 토큰이면 충분
        },
    }
    try:
        resp = _post_ollama(payload, timeout=60)
    except Exception as e:
        print(f'reranker error: {e}')
        return 0.0
    out = (resp.get('response') or '').strip().lower()
    # yes/no 단순 파싱 (대안 1)
    if out.startswith('yes'):
        return 1.0
    if out.startswith('no'):
        return 0.0
    # 알 수 없는 응답 → 0.5 로 중립 처리
    return 0.5


def rerank(query: str, candidates: Iterable[dict], top_n: int = 5, content_key: str = 'content') -> list[dict]:
    """
    candidates: [{chunk_id, content, ...}, ...]
    각 후보에 대해 score 계산 후 내림차순 정렬, 상위 top_n 반환.
    반환 구조: 원본 dict에 'rerank_score' 필드 추가.
    """
    scored = []
    for c in candidates:
        s = score_pair(query, c.get(content_key, ''))
        c2 = dict(c); c2['rerank_score'] = s
        scored.append(c2)
    scored.sort(key=lambda x: -x['rerank_score'])
    return scored[:top_n]


# ============ 향후 개선 포인트 ============
# 1. Ollama는 yes/no logit 직접 노출 불가 → vLLM + OpenAI 호환 API (logprobs=true) 전환 필요
#    그 경우 score = softmax([logp(yes), logp(no)])[0]  → 0.0~1.0 연속값
# 2. 배치 처리: Ollama는 단일 요청 기반, 병렬 호출로 throughput 개선 (N개 후보 × 2s ≈ K=50 에 100s)
# 3. 쿼리 다국어 지원: query와 document 언어가 다를 때 Instruct 문구에 cross-lingual 명시
# 4. Early exit: RRF 상위 3개의 score가 모두 >=0.9 이면 그대로 반환 (호출 수 절약)


if __name__ == '__main__':
    # self-test (모델 pull 되어있어야 함)
    q = 'CC-Link 통신 설정 방법'
    docs = [
        {'chunk_id': 'a', 'content': 'CC-Link의 국번 설정은 DIP 스위치 1~5번으로 수행한다. 전송속도는...'},
        {'chunk_id': 'b', 'content': '로봇 원점 복귀 시 Z축 브레이크를 먼저 해제한다.'},
        {'chunk_id': 'c', 'content': 'CC-Link IE Field 의 설정 방법: 마스터 국 설정 → 슬레이브 등록 순서로...'},
    ]
    top = rerank(q, docs, top_n=3)
    print(json.dumps(top, ensure_ascii=False, indent=2))
