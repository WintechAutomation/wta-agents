"""Claude Code 토큰 사용량 수집 → 대시보드 /api/usage 전송
10분마다 APScheduler(jobs.json)로 실행.

데이터 소스: ~/.claude/projects/**/*.jsonl (type=assistant 레코드)
- /usage CLI 명령: 인터랙티브 TUI 전용, subprocess 불가
- Anthropic REST API: /v1/usage 없음
- claude.ai OAuth API: 403 (클라이언트 토큰 접근 불가)
- JSONL 파싱이 유일한 방법
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
PRICE_INPUT        = 3.00  / 1_000_000   # $3/MTok
PRICE_OUTPUT       = 15.00 / 1_000_000   # $15/MTok
PRICE_CACHE_CREATE = 3.75  / 1_000_000   # $3.75/MTok
PRICE_CACHE_READ   = 0.30  / 1_000_000   # $0.30/MTok

# Claude Max 플랜 주간 토큰 한도 (부서장 /usage 77% 기준 역산)
# 1.06B / 0.77 ≈ 1.38B
WEEKLY_TOKENS_LIMIT = 1_380_000_000


def kst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def week_range_kst() -> tuple[str, str]:
    """이번 주 월요일~일요일 날짜 범위 (KST, UTC ISO prefix 기준)"""
    now = kst_now()
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def aggregate_usage(date_prefixes: list[str]) -> dict:
    """주어진 날짜 prefix 목록 범위의 JSONL에서 usage 집계.
    requestId 기준 중복 제거 (output_tokens 최대값 유지).
    """
    files = glob.glob(JSONL_PATTERN, recursive=True)
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

                    ts = rec.get("timestamp", "")
                    # 날짜 범위 필터
                    if not any(ts.startswith(d) for d in date_prefixes):
                        continue

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

                    if rid not in best or out > best[rid].get("output_tokens", 0):
                        best[rid] = {
                            "input":    usage.get("input_tokens", 0),
                            "output":   out,
                            "cc":       usage.get("cache_creation_input_tokens", 0),
                            "cr":       usage.get("cache_read_input_tokens", 0),
                        }
        except Exception:
            pass

    ti = sum(v["input"]  for v in best.values())
    to = sum(v["output"] for v in best.values())
    tc = sum(v["cc"]     for v in best.values())
    tr = sum(v["cr"]     for v in best.values())

    cost = ti * PRICE_INPUT + to * PRICE_OUTPUT + tc * PRICE_CACHE_CREATE + tr * PRICE_CACHE_READ
    return {
        "tokens": ti + to + tc + tr,
        "cost":   round(cost, 6),
        "requests": len(best),
        "detail": {"input": ti, "output": to, "cache_create": tc, "cache_read": tr},
    }


def date_range_prefixes(start: str, end: str) -> list[str]:
    """'YYYY-MM-DD' 범위의 모든 날짜 prefix 목록 생성"""
    from datetime import date
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    prefixes = []
    cur = s
    while cur <= e:
        prefixes.append(cur.isoformat())
        cur += timedelta(days=1)
    return prefixes


def main():
    now = kst_now()
    today = now.strftime("%Y-%m-%d")
    week_start, week_end = week_range_kst()

    # 오늘 집계
    daily = aggregate_usage([today])
    # 주간 집계
    week_prefixes = date_range_prefixes(week_start, week_end)
    weekly = aggregate_usage(week_prefixes)

    period_str = f"{week_start} ~ {week_end}"

    print(f"[collect-usage] 오늘={today} 토큰={daily['tokens']:,} 비용=${daily['cost']:.4f} 요청={daily['requests']}")
    print(f"[collect-usage] 주간={period_str} 토큰={weekly['tokens']:,} 비용=${weekly['cost']:.4f} 요청={weekly['requests']}")

    payload = {
        "tokens_used":          daily["tokens"],
        "tokens_limit":         0,           # API/CLI 조회 불가, unknown
        "cost":                 daily["cost"],
        "period":               today,
        "updated_at":           now.isoformat(),
        # 주간 데이터
        "weekly_tokens":        weekly["tokens"],
        "weekly_cost":          weekly["cost"],
        "weekly_period":        period_str,
        # 주간 한도 대비 잔여율
        "weekly_limit":          WEEKLY_TOKENS_LIMIT,
        "session_remaining_pct": round((1 - weekly["tokens"] / WEEKLY_TOKENS_LIMIT) * 100, 1),
    }

    try:
        r = requests.post(DASHBOARD_URL, json=payload, timeout=5)
        if r.status_code == 200 and r.json().get("ok"):
            print("[collect-usage] 대시보드 전송 완료")
        else:
            print(f"[collect-usage] 대시보드 응답 이상: {r.status_code} {r.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[collect-usage] 전송 실패: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
