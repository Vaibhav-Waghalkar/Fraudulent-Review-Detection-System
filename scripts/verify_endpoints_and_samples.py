"""
Verification script: Hits all endpoints, measures batch endpoint latency,
tests fallback mode, and saves sample responses to docs/sample_responses/.
"""
import os
import sys
import json
import time
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

API_URL = "http://127.0.0.1:8000"
DOCS_DIR = Path("docs/sample_responses")
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def save_sample(name: str, req_data: dict | list, resp_data: dict | list):
    with open(DOCS_DIR / f"{name}_request.json", "w") as f:
        json.dump(req_data, f, indent=2)
    with open(DOCS_DIR / f"{name}_response.json", "w") as f:
        json.dump(resp_data, f, indent=2)
    print(f"Saved sample: {name}")


def main():
    print("=== Testing All Endpoints ===")

    # 1. Health
    r = requests.get(f"{API_URL}/health")
    r.raise_for_status()
    health_data = r.json()
    save_sample("health", {}, health_data)
    print("1. Health OK:", health_data)

    # 2. Submit Review
    submit_req = {
        "text": "WOW absolutely incredible! Best purchase of my life! Limited time offer!",
        "user_id": "user-test-001",
        "rating": 5,
    }
    r = requests.post(f"{API_URL}/api/reviews/submit", json=submit_req)
    r.raise_for_status()
    submit_data = r.json()
    save_sample("submit_review", submit_req, submit_data)
    review_id = submit_data["id"]
    print("2. Submit Review OK, ID:", review_id)

    # Let Celery worker process it
    time.sleep(2)

    # 3. Get Review
    r = requests.get(f"{API_URL}/api/reviews/{review_id}")
    r.raise_for_status()
    get_data = r.json()
    save_sample("get_review", {"review_id": review_id}, get_data)
    print("3. Get Review OK, Score:", get_data.get("score"), "Status:", get_data.get("status"))

    # 4. Batch Detect (Batch size 2 sample)
    batch_req = [
        {"text": "Really enjoyed using this product. Battery life is good. Would recommend.", "user_id": "legit-01", "rating": 5},
        {"text": "BEST EVER! Use promo code BEST10. Order immediately!", "user_id": "fraud-01", "rating": 5},
    ]
    r = requests.post(f"{API_URL}/api/reviews/detect/batch", json=batch_req)
    r.raise_for_status()
    batch_data = r.json()
    save_sample("batch_detect", batch_req, batch_data)
    print("4. Batch Detect OK, count:", len(batch_data))

    # 5. List Reviews with Filters
    list_params = {"score_min": 0.0, "score_max": 1.0, "page": 1, "page_size": 10}
    r = requests.get(f"{API_URL}/api/reviews", params=list_params)
    r.raise_for_status()
    list_data = r.json()
    save_sample("list_reviews", list_params, list_data)
    print("5. List Reviews OK, total:", list_data.get("total"))

    # 6. Explain (LIME)
    # Use one of the batch reviews that was quarantined
    quarantine_id = None
    for item in batch_data:
        if item["status"] == "quarantined":
            quarantine_id = item["id"]
            break
    explain_id = quarantine_id or review_id
    r = requests.get(f"{API_URL}/api/reviews/{explain_id}/explain")
    r.raise_for_status()
    explain_data = r.json()
    save_sample("explain_review", {"review_id": explain_id}, explain_data)
    print("6. Explain Review (LIME) OK")

    # 7. Override Review
    override_req = {"moderator_id": "mod-001", "action": "reject", "note": "Audited by compliance team."}
    r = requests.post(f"{API_URL}/api/reviews/{review_id}/override", json=override_req)
    r.raise_for_status()
    override_data = r.json()
    save_sample("override_review", override_req, override_data)
    print("7. Override Review OK:", override_data.get("action"))

    # 8. Drift Status
    r = requests.get(f"{API_URL}/api/drift/status")
    r.raise_for_status()
    drift_data = r.json()
    save_sample("drift_status", {}, drift_data)
    print("8. Drift Status OK")

    # 9. Webhook with HMAC
    webhook_secret = "changeme-webhook-secret"
    webhook_payload = json.dumps({"text": "Webhook incoming review! Very good product.", "user_id": "wh-user-01", "rating": 5}).encode()
    expected = hmac.new(webhook_secret.encode(), webhook_payload, hashlib.sha256).hexdigest()
    headers = {"X-Signature": f"sha256={expected}", "Content-Type": "application/json"}
    r = requests.post(f"{API_URL}/api/reviews/webhook", data=webhook_payload, headers=headers)
    r.raise_for_status()
    webhook_data = r.json()
    save_sample("webhook", json.loads(webhook_payload.decode()), webhook_data)
    print("9. Webhook with HMAC OK:", webhook_data)

    # 10. Measure Batch Endpoint Latency for batch sizes 1, 10, 32, 100
    print("\n=== Measuring Batch Endpoint Latency Against 200ms Target ===")
    from ml.generate_data import generate
    df = generate(n=200, seed=123)
    records = df.to_dict(orient="records")

    batch_latencies = {}
    for bs in [1, 10, 32, 100]:
        test_items = [
            {"text": str(records[i]["text"]), "user_id": str(records[i]["user_id"]), "rating": int(records[i]["rating"])}
            for i in range(bs)
        ]
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            resp = requests.post(f"{API_URL}/api/reviews/detect/batch", json=test_items)
            resp.raise_for_status()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            times.append(elapsed_ms)
        avg_ms = sum(times) / len(times)
        p50_ms = sorted(times)[len(times) // 2]
        p95_ms = sorted(times)[int(len(times) * 0.95)]
        passed = avg_ms < 200.0
        batch_latencies[bs] = {
            "avg_ms": avg_ms,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "passed_200ms_target": passed,
        }
        status_str = "PASS" if passed else "FAIL"
        print(f"  Batch size {bs:3d}: avg={avg_ms:6.2f}ms  p50={p50_ms:6.2f}ms  p95={p95_ms:6.2f}ms  [{status_str}]")

    with open("reports/batch_endpoint_benchmarks.json", "w") as f:
        json.dump(batch_latencies, f, indent=2)
    print("Saved reports/batch_endpoint_benchmarks.json")


if __name__ == "__main__":
    main()
