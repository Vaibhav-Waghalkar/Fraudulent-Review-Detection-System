# ReviewGuard: Fraudulent Review Detection System

ReviewGuard is an enterprise fraud detection platform that identifies fake and malicious product reviews in real time using a fusion of fine-tuned transformer representations (DistilBERT), user velocity heuristics, multi-document transactional persistence in MongoDB, and Redis caching.

---

## 1. System Architecture

- **Inference Engine**: DistilBERT sequence embeddings fused with scaled velocity and heuristic features via an INT8 quantized ONNX runtime (`models/fusion_model_quantized.onnx`).
- **Persistence & Replication**: MongoDB replica set (`rs0`) with multi-document ACID transactions, compound indexes on `user_id`, `created_at`, `status`, and `score`, and audit logging.
- **Caching & Broker**: Redis for sub-millisecond caching of review scores, velocity counter tracking, and Celery task broker.
- **Worker Infrastructure**: Celery worker (`--pool=solo` on Windows) and Celery beat for automated hourly Kolmogorov-Smirnov drift detection.
- **Dashboard**: React 18 SPA built with Vite, TanStack React Query, Lucide icons, and Recharts, styled under strict warm-editorial design constraints.

---

## 2. Setup and Installation

### Prerequisites
- Python 3.11 in a virtual environment (`.venv`)
- Docker & Docker Compose
- Node.js (v18+) and npm

### Step 1: Clone and Configure Environment
```bash
git clone <repo-url>
cd "Fraudulent Review Detection System"

# Activate Python 3.11 virtual environment
.\.venv\Scripts\Activate.ps1

# Create environment configuration
cp .env.example .env
```

### Step 2: Start Infrastructure
```bash
docker compose up -d mongo1 redis
```
MongoDB replica set `rs0` initializes on port `27017` and Redis starts on port `6379`.

### Step 3: Install Python Dependencies & PyTorch CUDA
```bash
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Step 4: Install Dashboard Dependencies
```bash
cd dashboard
npm install
cd ..
```

---

## 3. Training & ML Pipeline

Execute the pipeline in sequential order:

```bash
# 1. Generate 50k synthetic reviews dataset
python ml/generate_data.py

# 2. Extract features and fit Scaler
python ml/preprocess.py

# 3. Fine-tune transformer + fusion head on NVIDIA GPU
python ml/train.py

# 4. Export PyTorch graph to FP32 ONNX
python ml/export_onnx.py

# 5. Quantize ONNX model to INT8
python ml/quantize.py

# 6. Benchmark latency, memory, and accuracy
python ml/benchmark.py
```

### Model Performance Metrics
- **Dataset Size**: 50,000 reviews (40,000 train, 5,000 validation, 5,000 test)
- **Class Balance**: 5.0% fraud prevalence (47,500 genuine, 2,500 fraudulent)
- **SMOTE Balancing**: Rebalanced 38,000:2,000 training partition to 38,000:38,000 balanced distribution.
- **Validation AUC-ROC**: 1.0000 | **Validation Fraud F1**: 1.0000
- **Test AUC-ROC**: 1.0000 | **Test Fraud F1**: 1.0000
- **Robustness Check**: Synthetic fraud patterns (burst velocity, extreme rating mismatch, repetitive sentiment keywords) are distinct, resulting in separable classification boundaries.
- **Baseline Reference Scores**: 40,000 baseline scores saved to `models/reference_scores.npy`.

---

## 4. Benchmarks

### FP32 vs. INT8 ONNX Engine

| Model Variant | File Size | Reduction | Val AUC | Test AUC | Batch 1 Latency (p50) | Batch 10 Latency (p50) | Batch 32 Latency (p50) | Batch 100 Latency (p50) |
|---|---|---|---|---|---|---|---|---|
| **FP32 ONNX** | 266.4 MB | Baseline | 1.0000 | 1.0000 | 125.04 ms | 782.16 ms | 3,584.09 ms | 6,198.30 ms |
| **INT8 ONNX** | 67.0 MB | **74.9%** | 1.0000 | 1.0000 | **7.42 ms** | **71.07 ms** | **223.75 ms** | **1,574.41 ms** |

### Live Batch API Endpoint Latency (`/api/reviews/detect/batch`)
Target: Average latency <= 200 ms.

| Batch Size | Measured Latency (Mean) | Status | Notes |
|---|---|---|---|
| **Batch 1** | 30.05 ms | **PASS** | Meets <= 200ms threshold |
| **Batch 10** | 76.37 ms | **PASS** | Meets <= 200ms threshold |
| **Batch 32** | 161.84 ms | **PASS** | Meets <= 200ms threshold |
| **Batch 100** | 368.33 ms | **FAIL** | CPU bound (12 threads). Dynamic padding tuned. Requires GPU execution provider for <= 200ms at batch 100. |

---

## 5. Running the Application

### 1. Start FastAPI Backend
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Interactive API Documentation (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

### 2. Start Celery Worker & Beat
```bash
# Worker (use solo pool on Windows)
celery -A app.workers.celery_app worker --loglevel=info --pool=solo

# Periodic Beat Scheduler (hourly drift check)
celery -A app.workers.celery_app beat --loglevel=info
```

### 3. Start Frontend Dashboard
```bash
cd dashboard
npm run dev -- --host 127.0.0.1 --port 5173
```
Dashboard available at [http://127.0.0.1:5173](http://127.0.0.1:5173).

---

## 6. Drift Detection Demonstration

To simulate model drift and test the Kolmogorov-Smirnov detection alert:

```bash
python scripts/simulate_drift.py
```

### Real Execution Output:
```text
Simulating drift with 1000 reviews...
Reference scores loaded: 40000 samples (mean=0.0385)
Production scores computed: 1000 samples (mean=0.7483)

=== Two-Sample Kolmogorov-Smirnov Test ===
KS statistic: 0.7449
p-value:      0.0000000000000000
Threshold:    p < 0.05

DRIFT DETECTED! Score distribution has significantly diverged.
[ALERT EMAIL] Drift detected: KS stat=0.7449, p-value=0.000000
[ALERT SLACK] Drift alert: p-value=0.000000 < 0.05 threshold
Drift record saved to DB: 6acf5a980a9d6ac380cb7f92
```

---

## 7. Load Test Results (10,000 Reviews)

The load testing utility evaluated 10,000 HTTP review submissions against `/api/reviews/detect/batch`:

```bash
python scripts/load_test.py --n 10000 --concurrency 20 --api http://127.0.0.1:8000
```

### Real Results:
- **Total Requests**: 10,000
- **Successful Requests**: 10,000 (100.0%)
- **Errors**: 0 (0.00%)
- **Total Execution Time**: 631.79 s
- **System Throughput**: 15.8 req/s
- **Latency Mean**: 1,263.1 ms
- **Latency p50**: 1,362.9 ms
- **Latency p95**: 2,829.0 ms

---

## 8. Test Suite and Coverage

Run the automated test suite with coverage reporting:

```bash
pytest --cov=app --cov-report=term-missing
```

### Test Summary:
- **Total Tests Passed**: 62
- **Failures / Errors**: 0
- **Overall Code Coverage**: **89%** (Target: 80%+)
- **Test Modules Covered**: `test_api.py`, `test_inference.py`, `test_rules.py`, `test_drift.py`, `test_database.py`, `test_coverage_boost.py`.

---

## 9. Design System & Dashboard Compliance

The moderator dashboard strictly implements the following design requirements:
- **Color Palette**: Background `#F6F4EF`, Surface `#FFFFFF`, Text `#1B1B1A`, Border `#E3DFD6`, Accent `#2F5D50`, Danger `#B23A2E`.
- **Typography**: IBM Plex Sans (body, headings) and IBM Plex Mono (IDs, scores, code tokens).
- **Prohibited Patterns**: Zero gradients, zero purple hues, zero pill buttons (max radius 6px), zero emojis (pure Lucide SVG icons), zero em dashes, zero animated cursor effects, and zero placeholder counters.
- **Screenshots**: Saved in `docs/screenshots/`:
  - `reviews.png`: Review queue with filters and pagination
  - `review_detail.png`: Review inspection, rule breakdown, and audit log
  - `review_detail_lime.png`: On-demand LIME token attributions
  - `drift.png`: KS statistic and drift history visualization

---

## 10. Sample API Responses

Sample JSON payloads for all 9 API routes are saved in `docs/sample_responses/`:
1. `health_sample.json`: `/health` service status
2. `submit_review_sample.json`: POST `/api/reviews/submit`
3. `get_review_sample.json`: GET `/api/reviews/{id}`
4. `batch_detect_sample.json`: POST `/api/reviews/detect/batch`
5. `list_reviews_sample.json`: GET `/api/reviews` with pagination
6. `explain_review_sample.json`: GET `/api/reviews/{id}/explain` (LIME explanation)
7. `override_review_sample.json`: POST `/api/reviews/{id}/override`
8. `drift_status_sample.json`: GET `/api/drift/status`
9. `webhook_sample.json`: POST `/api/reviews/webhook` with HMAC signature validation

---

## 11. Assumptions, Bias Audit, and Limitations

### Assumptions
1. **Synthetic Separability**: Synthetic reviews generated using rule templates exhibit distinct syntactic markers and burst user velocities, creating high class separability. Real-world fraud text is significantly subtler and adversarial.
2. **Review Length Distribution**: Model input is truncated to 128 tokens for ONNX inference to maintain CPU throughput. Reviews exceeding 128 words rely primarily on early text tokens for NLP classification.
3. **Single Store Context**: Velocity counters are scoped by `user_id` in Redis without cross-store federation.

### Bias Audit
1. **Short Review False Positives**: Brief positive feedback ("Great!", "Works well", "Five stars") can trigger generic-text rules if user velocity is elevated.
2. **Sentiment Polarization**: Highly polarized negative reviews from frustrated legitimate customers may receive elevated rule scores if sentiment variance is high.
3. **Language Diversity**: The model is trained solely on English text. Non-English reviews or mixed-language reviews will exhibit degraded embeddings and must be handled via fallback rule pipelines.

### Limitations
1. **Batch 100 CPU Latency**: At 100 reviews per batch, CPU inference latency averages 368.33 ms, failing the strict 200 ms target. Production workloads with batch sizes >= 100 require GPU deployment (CUDA / TensorRT) or worker horizontal scaling.
2. **LIME Computation Latency**: LIME generates 500 perturbed samples per explanation, requiring 1.5 to 3.0 seconds per review on CPU.
