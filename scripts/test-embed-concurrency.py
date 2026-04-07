"""test-embed-concurrency.py -- 동시 임베딩 성능 테스트.

8채널 동시 요청, 배치 사이즈별 처리량/에러율 측정.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict

import requests

EMBED_URL = "http://182.224.6.147:11434/api/embed"
TEXTS_PER_CHANNEL = 100

# 더미 텍스트 (실제 매뉴얼 스타일)
DUMMY_TEXTS = [
    f"서보 드라이브 파라미터 {i}: 전자 기어비 설정 방법. "
    f"분자값을 {1000+i}으로, 분모값을 {500+i}으로 설정하면 펄스당 이동량이 결정됩니다. "
    f"속도 제어 모드에서 가감속 시간은 {10+i}ms로 설정하고 토크 제한은 {100+i}%입니다."
    for i in range(TEXTS_PER_CHANNEL)
]


@dataclass
class ChannelResult:
    channel_id: int
    batch_size: int
    total_texts: int
    success_count: int
    error_count: int
    error_500_count: int
    total_time: float
    avg_batch_time: float
    throughput: float  # texts/sec


def run_channel(channel_id: int, batch_size: int) -> ChannelResult:
    """단일 채널: 100개 텍스트를 배치 단위로 임베딩."""
    texts = DUMMY_TEXTS.copy()
    success = 0
    errors = 0
    errors_500 = 0
    batch_times = []

    start = time.time()
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        payload = {"model": "qwen3-embedding:8b", "input": batch}
        t0 = time.time()
        try:
            resp = requests.post(EMBED_URL, json=payload, timeout=120)
            elapsed = time.time() - t0
            batch_times.append(elapsed)
            if resp.status_code == 200:
                data = resp.json()
                emb_count = len(data.get("embeddings", []))
                if emb_count == len(batch):
                    success += len(batch)
                else:
                    errors += len(batch) - emb_count
                    success += emb_count
            elif resp.status_code >= 500:
                errors_500 += 1
                errors += len(batch)
            else:
                errors += len(batch)
        except Exception:
            errors += len(batch)

    total_time = time.time() - start
    avg_batch = sum(batch_times) / len(batch_times) if batch_times else 0
    throughput = success / total_time if total_time > 0 else 0

    return ChannelResult(
        channel_id=channel_id,
        batch_size=batch_size,
        total_texts=len(texts),
        success_count=success,
        error_count=errors,
        error_500_count=errors_500,
        total_time=round(total_time, 2),
        avg_batch_time=round(avg_batch, 3),
        throughput=round(throughput, 1),
    )


def run_test(num_channels: int, batch_size: int) -> list[ChannelResult]:
    """N채널 동시 실행."""
    results = []
    with ProcessPoolExecutor(max_workers=num_channels) as executor:
        futures = {
            executor.submit(run_channel, ch, batch_size): ch
            for ch in range(num_channels)
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: r.channel_id)
    return results


def main():
    print("=" * 70)
    print("동시 임베딩 성능 테스트")
    print(f"서버: {EMBED_URL}")
    print(f"채널당 텍스트: {TEXTS_PER_CHANNEL}개")
    print("=" * 70)

    # 워밍업
    print("\n[워밍업] 단일 요청...")
    resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": ["warmup"]}, timeout=30)
    print(f"  Status: {resp.status_code}")

    all_results = []

    # 테���트 매트릭스: 채널 수 x 배치 사이즈
    channel_counts = [1, 2, 4, 8]
    batch_sizes = [64, 128, 256]

    for batch_size in batch_sizes:
        for num_ch in channel_counts:
            label = f"채널={num_ch}, 배치={batch_size}"
            total_texts = num_ch * TEXTS_PER_CHANNEL
            print(f"\n--- {label} (총 {total_texts}개) ---")

            start = time.time()
            results = run_test(num_ch, batch_size)
            wall_time = time.time() - start

            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)
            total_500 = sum(r.error_500_count for r in results)
            total_throughput = total_success / wall_time if wall_time > 0 else 0
            avg_channel_time = sum(r.total_time for r in results) / len(results)

            print(f"  Wall time:    {wall_time:.1f}s")
            print(f"  성공:          {total_success}/{total_texts}")
            print(f"  에러:          {total_errors} (500에러: {total_500})")
            print(f"  총 처리량:     {total_throughput:.0f} texts/s")
            print(f"  채널 평균:     {avg_channel_time:.1f}s")

            # 채널별 상세
            for r in results:
                status = "OK" if r.error_count == 0 else f"ERR={r.error_count}"
                print(f"    ch{r.channel_id}: {r.throughput} t/s, {r.total_time}s, {status}")

            all_results.append({
                "channels": num_ch,
                "batch_size": batch_size,
                "wall_time": round(wall_time, 1),
                "total_success": total_success,
                "total_errors": total_errors,
                "error_500": total_500,
                "throughput": round(total_throughput, 0),
            })

    # 요약
    print("\n" + "=" * 70)
    print("요약 (채널 x 배치 → 처리량)")
    print(f"{'채널':>4} {'배치':>4} {'시간':>6} {'성공':>6} {'에러':>4} {'500':>4} {'처리량':>8}")
    print("-" * 42)
    for r in all_results:
        print(f"{r['channels']:>4} {r['batch_size']:>4} {r['wall_time']:>5.1f}s "
              f"{r['total_success']:>5} {r['total_errors']:>4} {r['error_500']:>4} "
              f"{r['throughput']:>7.0f}/s")

    # 최적 조합
    best = max(all_results, key=lambda r: r["throughput"] if r["total_errors"] == 0 else 0)
    if best["total_errors"] == 0:
        print(f"\n최적 (에러 0): 채널={best['channels']}, 배치={best['batch_size']}, "
              f"처리량={best['throughput']}/s")
    else:
        best_any = max(all_results, key=lambda r: r["throughput"])
        print(f"\n최고 처리량: 채널={best_any['channels']}, 배치={best_any['batch_size']}, "
              f"처리량={best_any['throughput']}/s (에러 {best_any['total_errors']})")

    # 결과 저장
    with open("C:/MES/wta-agents/data/embed-concurrency-test.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("\n결과 저장: data/embed-concurrency-test.json")


if __name__ == "__main__":
    main()
