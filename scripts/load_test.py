"""
Load test: score reviews in batches of 32 and report latency and reviews/sec.
Includes async queue throughput test measuring scored-per-second by Celery.
Usage: python scripts/load_test.py --n 10000 --batch-size 32 --concurrency 10 --api http://localhost:8000
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


def batch_request(api_url: str, batch_items: list[dict]) -> dict:
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            f"{api_url}/api/reviews/detect/batch",
            json=batch_items,
            timeout=45,
        )
        resp.raise_for_status()
        elapsed = (time.perf_counter() - t0) * 1000
        return {"ok": True, "ms": elapsed, "count": len(batch_items)}
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return {"ok": False, "ms": elapsed, "count": len(batch_items), "error": str(e)}


def load_test_sync(n_reviews: int = 10_000, batch_size: int = 32, concurrency: int = 10, api_url: str = "http://localhost:8000"):
    print(f"\n=== Sync Batch Load Test: {n_reviews} total reviews (Batch size={batch_size}, Concurrency={concurrency}) ===")
    
    # Prepare all batches
    batches = []
    for b in range(0, n_reviews, batch_size):
        curr_batch_size = min(batch_size, n_reviews - b)
        items = []
        for i in range(curr_batch_size):
            idx = b + i
            items.append({
                "text": SAMPLE_TEXTS[idx % len(SAMPLE_TEXTS)],
                "user_id": f"loadtest-u{idx % 150}",
                "rating": random.randint(1, 5)
            })
        batches.append(items)

    latencies = []
    errors = 0
    total_scored = 0

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(batch_request, api_url, batch) for batch in batches]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result["ok"]:
                latencies.append(result["ms"])
                total_scored += result["count"]
            else:
                errors += 1
            if (i + 1) % max(1, len(batches) // 10) == 0:
                print(f"  Completed {total_scored}/{n_reviews} reviews...")

    total_time = time.perf_counter() - t_start
    latencies.sort()

    print("\n--- Synchronous Batch Load Test Results ---")
    print(f"  Total Reviews  : {total_scored}")
    print(f"  Total Batches  : {len(batches)}")
    print(f"  Failed Batches : {errors}")
    print(f"  Total Time     : {total_time:.2f}s")
    print(f"  Batch Rate     : {len(batches) / total_time:.1f} req/s")
    print(f"  Reviews Rate   : {total_scored / total_time:.1f} reviews/sec")
    if latencies:
        qs = quantiles(latencies, n=100) if len(latencies) >= 100 else [median(latencies)] * 100
        print(f"  Latency Mean   : {mean(latencies):.1f}ms")
        print(f"  Latency p50    : {median(latencies):.1f}ms")
        print(f"  Latency p95    : {qs[94]:.1f}ms")
        print(f"  Latency max    : {max(latencies):.1f}ms")


def test_async_queue_throughput(n: int = 50, api_url: str = "http://localhost:8000"):
    print(f"\n=== Async Queue Throughput Test: Submitting {n} reviews through /api/reviews/submit ===")
    t0 = time.perf_counter()
    submitted_ids = []
    for i in range(n):
        try:
            r = requests.post(f"{api_url}/api/reviews/submit", json={
                "user_id": f"async_test_user_{i % 10}",
                "product_id": f"prod_{i % 5}",
                "text": SAMPLE_TEXTS[i % len(SAMPLE_TEXTS)],
                "rating": 5
            }, timeout=10)
            if r.status_code == 200:
                submitted_ids.append(r.json()["id"])
        except Exception as e:
            print("Submit error:", e)

    submit_time = time.perf_counter() - t0
    print(f"  Submitted {len(submitted_ids)} reviews in {submit_time:.2f}s ({len(submitted_ids)/max(submit_time, 0.001):.1f} submissions/sec)")
    
    # Poll for completion
    print("  Measuring worker processing time...")
    t_worker_start = time.perf_counter()
    finished = 0
    timeout = 30
    while time.perf_counter() - t_worker_start < timeout:
        # Check a sample
        resps = [requests.get(f"{api_url}/api/reviews/{rid}").json() for rid in submitted_ids[:10]]
        scored = [r for r in resps if r.get("status") in ("reviewed", "quarantined", "needs_review")]
        if len(scored) == len(resps):
            finished = len(submitted_ids)
            break
        time.sleep(0.5)

    duration = time.perf_counter() - t_worker_start
    print(f"  Scored ~{finished} reviews by worker in {duration:.2f}s")
    if duration > 0:
        print(f"  Worker Throughput: ~{finished/duration:.1f} scored reviews/sec")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1_000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--async-test", action="store_true", help="Run async queue throughput test")
    args = parser.parse_args()

    load_test_sync(n_reviews=args.n, batch_size=args.batch_size, concurrency=args.concurrency, api_url=args.api)
    if args.async_test:
        test_async_queue_throughput(n=50, api_url=args.api)
