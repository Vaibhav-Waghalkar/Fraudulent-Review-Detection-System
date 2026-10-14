"""
Load test: score 10k reviews and report latency and throughput.
Usage: python scripts/load_test.py --n 10000 --concurrency 20 --api http://localhost:8000
"""
import argparse
import concurrent.futures
import random
import sys
import time
from pathlib import Path
from statistics import mean, median, quantiles

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_TEXTS = [
    "Great product, exactly as described. Very happy with my purchase.",
    "Terrible quality. Broke after one use. Do not buy!",
    "AMAZING!!! BEST EVER!!! Buy now!!! Limited offer!!!",
    "Decent for the price. Nothing special but gets the job done.",
    "Arrived quickly and well packaged. Works as expected.",
    "Five stars all the way! Tell everyone to get this!",
    "Returned it. Product does not match description.",
    "Good value. Would buy again.",
]


def single_request(api_url: str, i: int) -> dict:
    text = SAMPLE_TEXTS[i % len(SAMPLE_TEXTS)]
    user_id = f"loadtest-user-{i % 100}"
    rating = random.randint(1, 5)

    t0 = time.perf_counter()
    try:
        resp = requests.post(
            f"{api_url}/api/reviews/detect/batch",
            json=[{"text": text, "user_id": user_id, "rating": rating}],
            timeout=30,
        )
        resp.raise_for_status()
        elapsed = (time.perf_counter() - t0) * 1000
        return {"ok": True, "ms": elapsed}
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return {"ok": False, "ms": elapsed, "error": str(e)}


def load_test(n: int = 10_000, concurrency: int = 20, api_url: str = "http://localhost:8000"):
    print(f"Load test: n={n}, concurrency={concurrency}, api={api_url}")
    latencies = []
    errors = 0

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_request, api_url, i) for i in range(n)]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result["ok"]:
                latencies.append(result["ms"])
            else:
                errors += 1
            if (i + 1) % 1000 == 0:
                print(f"  Completed {i+1}/{n}...")

    total_time = time.perf_counter() - t_start
    latencies.sort()

    print("\n=== Load Test Results ===")
    print(f"  Total requests : {n}")
    print(f"  Successful     : {len(latencies)}")
    print(f"  Errors         : {errors}")
    print(f"  Total time     : {total_time:.2f}s")
    print(f"  Throughput     : {n / total_time:.1f} req/s")
    if latencies:
        qs = quantiles(latencies, n=100)
        print(f"  Latency mean   : {mean(latencies):.1f}ms")
        print(f"  Latency p50    : {median(latencies):.1f}ms")
        print(f"  Latency p95    : {qs[94]:.1f}ms")
        print(f"  Latency p99    : {qs[98]:.1f}ms")
        print(f"  Latency max    : {max(latencies):.1f}ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10_000)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    load_test(n=args.n, concurrency=args.concurrency, api_url=args.api)
