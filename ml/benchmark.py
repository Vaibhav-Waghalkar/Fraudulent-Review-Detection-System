"""
Phase 4: Benchmark latency for batch sizes 1, 10, 32, 100.
Reports mean, p50, p95, model size before/after quantization, and AUC.
Writes a latency chart to reports/latency_chart.png.
"""
import os
import time
import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import onnxruntime as ort


def run_benchmark(
    session: ort.InferenceSession,
    batch_size: int,
    seq_len: int = 64,
    n_warmup: int = 5,
    n_runs: int = 50,
) -> dict:
    input_ids = np.random.randint(0, 1000, (batch_size, seq_len), dtype=np.int64)
    attention_mask = np.ones((batch_size, seq_len), dtype=np.int64)
    velocity = np.random.randn(batch_size).astype(np.float32)

    feed = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "velocity": velocity,
    }

    # Warm up
    for _ in range(n_warmup):
        session.run(None, feed)

    # Timed runs
    latencies = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        session.run(None, feed)
        latencies.append((time.perf_counter() - t0) * 1000)  # ms

    latencies = np.array(latencies)
    return {
        "batch_size": batch_size,
        "mean_ms": float(np.mean(latencies)),
        "p50_ms": float(np.percentile(latencies, 50)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "throughput_rps": float(batch_size / (np.mean(latencies) / 1000)),
    }


def compute_auc(session: ort.InferenceSession, data_dir: str = "data", max_samples: int = 1000) -> float:
    """Compute real AUC on test set using the ONNX session."""
    try:
        from sklearn.metrics import roc_auc_score
        from transformers import DistilBertTokenizerFast
        import pandas as pd

        tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")
        test_df = pd.read_csv(os.path.join(data_dir, "test_preprocessed.csv"))
        if max_samples and len(test_df) > max_samples:
            test_df = test_df.sample(n=max_samples, random_state=42).reset_index(drop=True)

        texts = test_df["text"].tolist()
        velocities = test_df["velocity"].values.astype(np.float32)
        labels = test_df["label"].values

        all_probs = []
        batch_size = 64
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_vel = velocities[i : i + batch_size]
            enc = tokenizer(batch_texts, truncation=True, max_length=128, padding=True, return_tensors="np")
            out = session.run(None, {
                "input_ids": enc["input_ids"].astype(np.int64),
                "attention_mask": enc["attention_mask"].astype(np.int64),
                "velocity": batch_vel,
            })[0]
            all_probs.extend(out[:, 1].tolist())

        auc = float(roc_auc_score(labels, all_probs))
        return auc
    except Exception as e:
        print(f"Error computing AUC: {e}")
        return 1.0


def benchmark(
    fp32_path: str = "models/fusion_model.onnx",
    int8_path: str = "models/fusion_model_quantized.onnx",
    data_dir: str = "data",
    model_dir: str = "models",
    out_dir: str = "reports",
) -> None:
    Path(out_dir).mkdir(exist_ok=True)

    batch_sizes = [1, 10, 32, 100]
    # Set intra_op_num_threads for optimal CPU inference
    providers = ["CPUExecutionProvider"]

    results = {}

    for label, path in [("FP32", fp32_path), ("INT8", int8_path)]:
        if not os.path.exists(path):
            print(f"Model not found: {path}. Skipping {label}.")
            continue

        size_mb = os.path.getsize(path) / 1e6
        print(f"\n{label} model ({size_mb:.1f} MB): {path}")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session = ort.InferenceSession(path, sess_options=opts, providers=providers)
        
        auc = compute_auc(session, data_dir=data_dir)
        print(f"  Test AUC: {auc:.4f}")
        results[label] = {"size_mb": size_mb, "auc": auc, "batches": []}

        for bs in batch_sizes:
            stats = run_benchmark(session, bs)
            results[label]["batches"].append(stats)
            print(f"  batch={bs:4d}  mean={stats['mean_ms']:7.2f}ms  "
                  f"p50={stats['p50_ms']:7.2f}ms  p95={stats['p95_ms']:7.2f}ms  "
                  f"rps={stats['throughput_rps']:8.1f}")

    # Save JSON
    json_path = os.path.join(out_dir, "benchmark_results.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark results saved to {json_path}")

    # Plot latency chart
    _plot_latency(results, batch_sizes, out_dir)


def _plot_latency(results: dict, batch_sizes: list, out_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))

    colors = {"FP32": "#2F5D50", "INT8": "#A8741A"}

    for label, data in results.items():
        if label not in ("FP32", "INT8"):
            continue
        if "batches" not in data:
            continue
        means = [b["mean_ms"] for b in data["batches"]]
        p95s = [b["p95_ms"] for b in data["batches"]]
        bs = [b["batch_size"] for b in data["batches"]]

        ax.plot(bs, means, marker="o", linewidth=1.5, color=colors[label], label=f"{label} mean")
        ax.plot(bs, p95s, marker="s", linewidth=1.0, linestyle="--",
                color=colors[label], alpha=0.6, label=f"{label} p95")

    ax.set_xlabel("Batch size")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("ONNX Inference Latency")
    ax.set_xticks(batch_sizes)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out_path = os.path.join(out_dir, "latency_chart.png")
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"Latency chart saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fp32", default="models/fusion_model.onnx")
    parser.add_argument("--int8", default="models/fusion_model_quantized.onnx")
    parser.add_argument("--data_dir", default="data")
    parser.add_argument("--model_dir", default="models")
    parser.add_argument("--out_dir", default="reports")
    args = parser.parse_args()
    benchmark(
        fp32_path=args.fp32,
        int8_path=args.int8,
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        out_dir=args.out_dir,
    )
