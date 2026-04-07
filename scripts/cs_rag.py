"""cs_rag.py — CS RAG 파이프라인 (Claude API 직접, 스트리밍).

cs-api-direct.py의 함수를 재사용하며, Claude 스트리밍 호출을 추가한 모듈.
slack-bot의 /api/chat-stream 엔드포인트에서 import하여 사용.

사용:
    from cs_rag import search_and_build_context, stream_claude_answer

    ctx = search_and_build_context(query, top_k=10)
    for event in stream_claude_answer(query, ctx["context"]):
        # event: ("chunk", text) | ("done", meta) | ("error", msg)
        ...
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

# cs-api-direct 모듈 함수 재사용 (모듈명 하이픈 때문에 importlib 사용)
import importlib.util
_CS_DIRECT = Path(__file__).parent / "cs-api-direct.py"
_spec = importlib.util.spec_from_file_location("cs_api_direct", _CS_DIRECT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

combined_search = _mod.combined_search
_build_context = _mod._build_context
_get_api_key = _mod._get_api_key
SYSTEM_PROMPT = _mod.SYSTEM_PROMPT
CLAUDE_API_URL = _mod.CLAUDE_API_URL
ANTHROPIC_API_VERSION = _mod.ANTHROPIC_API_VERSION

# 모델 및 max_tokens (환경변수로 override 가능)
CS_MODEL = os.environ.get("CS_MODEL", "claude-haiku-4-5-20251001")
CS_MAX_TOKENS = int(os.environ.get("CS_MAX_TOKENS", "1500"))


def search_and_build_context(query: str, top_k: int = 10) -> dict:
    """벡터 검색 + 컨텍스트 조립. Returns {context, search_result, fallback}.

    임베딩/검색 실패 시 fallback=True 세팅, context는 빈 안내 문자열.
    """
    try:
        search_result = combined_search(query, top_k)
        context = _build_context(search_result)
        return {"context": context, "search_result": search_result, "fallback": False}
    except Exception as e:
        # 임베딩 서버 타임아웃/DB 장애 등 → 컨텍스트 없이 진행
        return {
            "context": "(벡터 검색을 사용할 수 없습니다. 일반 지식으로 답변하되 확실하지 않으면 '확인이 필요합니다'라고 명시해주세요.)",
            "search_result": None,
            "fallback": True,
            "fallback_reason": str(e)[:200],
        }


def stream_claude_answer(question: str, context: str):
    """Claude API 스트리밍 호출 — 제너레이터.

    Yields:
        ("chunk", text): 답변 텍스트 조각
        ("done", meta_dict): 완료 (input_tokens, output_tokens, model, time_sec 포함)
        ("error", message): 오류
    """
    api_key = _get_api_key()
    user_message = (
        f"다음은 고객/직원의 CS 질문입니다:\n\n"
        f"질문: {question}\n\n"
        f"아래는 벡터 검색으로 찾은 관련 자료입니다:\n\n"
        f"{context}\n\n"
        f"위 자료를 근거로 질문에 답변해주세요."
    )

    payload = {
        "model": CS_MODEL,
        "max_tokens": CS_MAX_TOKENS,
        "stream": True,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    t0 = time.time()
    input_tokens = 0
    output_tokens = 0

    try:
        with requests.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            if resp.status_code != 200:
                body = resp.text[:300]
                yield ("error", f"Claude API {resp.status_code}: {body}")
                return

            current_event = None
            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                line = raw_line.strip()
                if not line:
                    current_event = None
                    continue
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    etype = obj.get("type") or current_event
                    if etype == "content_block_delta":
                        delta = obj.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield ("chunk", text)
                    elif etype == "message_start":
                        usage = obj.get("message", {}).get("usage", {})
                        input_tokens = usage.get("input_tokens", 0)
                    elif etype == "message_delta":
                        usage = obj.get("usage", {})
                        if "output_tokens" in usage:
                            output_tokens = usage["output_tokens"]
                    elif etype == "message_stop":
                        pass
                    elif etype == "error":
                        err = obj.get("error", {})
                        yield ("error", f"{err.get('type','unknown')}: {err.get('message','')}")
                        return
    except requests.exceptions.Timeout:
        yield ("error", "Claude API timeout")
        return
    except Exception as e:
        yield ("error", f"Claude stream error: {e}")
        return

    elapsed = round(time.time() - t0, 2)
    yield ("done", {
        "model": CS_MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "time_sec": elapsed,
    })
