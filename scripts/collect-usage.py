"""Claude Code 토큰 사용량 수집 → 대시보드 /api/usage 전송
10분마다 APScheduler(jobs.json)로 실행.
"""
import glob
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

DASHBOARD_URL = "http://localhost:5555/api/usage"
JSONL_PATTERN = os.path.join(os.path.expanduser("~"), ".claude", "projects", "**", "*.jsonl")

# Sonnet 4.6 가격 (USD/token)
PRICE_INPUT          = 3.00   / 1_000_000   # $3/MTok
PRICE_OUTPUT         = 15.00  / 1_000_000   # $15/MTok
PRICE_CACHE_CREATE   = 3.75   / 1_000_000   # $3.75/MTok
PRICE_CACHE_READ     = 0.30   / 1_000_000   # $0.30/MTok

# 일일 토큰 한도 (MAX Plan 기준 대략값, 정확한 한도 없을 경우 표시용)
TOKENS_LIMIT = 0  # 0 = unknown


def kst_today_prefix() -> str:
    """오늘 날짜 KST 기준 ISO prefix (YYYY-MM-DD)"""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime("%Y-%m-%d")


def collect_today_usage() -> dict:
    """오늘 JSONL 파일에서 assistant 사용량 합산 (requestId 기준 최종 레코드만)"""
    today = kst_today_prefix()
    files = glob.glob(JSONL_PATTERN, recursive=True)

    # requestId → 최종 usage (output_tokens 가장 큰 레코드)
    best: dict[str, dict] = {}

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 오늘 레코드만
                    ts = rec.get("timestamp", "")
                    if not ts.startswith(today):
                        continue

                    # assistant 타입만
                    if rec.get("type") != "assistant":
                        continue

                    msg = rec.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    usage = msg.get("usage")
                    if not isinstance(usage, dict):
                        continue

                    rid = rec.get("requestId", "")
                    out = usage.get("output_tokens", 0)

                    # 같은 requestId면 output_tokens 가장 높은 것만 유지
                    if rid not in best or out > best[rid].get("output_tokens", 0):
                        best[rid] = {
                            "input_tokens":          usage.get("input_tokens", 0),
                            "output_tokens":         out,
                            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                            "cache_read_tokens":     usage.get("cache_read_input_tokens", 0),
                        }
        except Exception:
            pass

    # 합산
    total_input   = sum(v["input_tokens"]          for v in best.values())
    total_output  = sum(v["output_tokens"]          for v in best.values())
    total_cc      = sum(v["cache_creation_tokens"]  for v in best.values())
    total_cr      = sum(v["cache_read_tokens"]      for v in best.values())

    tokens_used = total_input + total_output + total_cc + total_cr
    cost = (
        total_input  * PRICE_INPUT +
        total_output * PRICE_OUTPUT +
        total_cc     * PRICE_CACHE_CREATE +
        total_cr     * PRICE_CACHE_READ
    )

    kst = timezone(timedelta(hours=9))
    return {
        "tokens_used":  tokens_used,
        "tokens_limit": TOKENS_LIMIT,
        "cost":         round(cost, 6),
        "period":       today,
        "updated_at":   datetime.now(kst).isoformat(),
        # 상세 (참고용, 대시보드 무시 가능)
        "_detail": {
            "input": total_input,
            "output": total_output,
            "cache_create": total_cc,
            "cache_read": total_cr,
            "requests": len(best),
        },
    }


def main():
    payload = collect_today_usage()
    detail  = payload.pop("_detail")

    print(f"[collect-usage] 기간={payload['period']} "
          f"토큰={payload['tokens_used']:,} "
          f"비용=${payload['cost']:.4f} "
          f"요청수={detail['requests']}")

    try:
        r = requests.post(DASHBOARD_URL, json=payload, timeout=5)
        if r.status_code == 200 and r.json().get("ok"):
            print(f"[collect-usage] 대시보드 전송 완료")
        else:
            print(f"[collect-usage] 대시보드 응답 이상: {r.status_code} {r.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[collect-usage] 전송 실패: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
