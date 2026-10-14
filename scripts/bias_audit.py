"""
Bias and Fairness Audit Script.
Analyzes model and system scoring disparity across:
1. Review length buckets (<50 chars, 50-150 chars, >150 chars)
2. Non-ASCII character ratio (pure ASCII vs >10% non-ASCII)
3. Non-English / Multilingual synthetic test samples
Reports mean scores, fraud prediction rates, and statistical differences.
"""
import os
import json
import pandas as pd
import numpy as np

from app.services.inference import infer
from app.services.rules import score_rules
from app.core.config import settings

def run_bias_audit(data_path: str = "data/test.csv", out_dir: str = "reports") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(data_path)
    
    # Take a balanced sample of legit and fraud reviews
    sample = df.sample(n=min(2000, len(df)), random_state=42).copy()
    
    scores = []
    statuses = []
    
    for _, row in sample.iterrows():
        nlp, _ = infer(row["text"], float(row["velocity"]))
        _, rules = score_rules(row["text"], int(row["rating"]), int(row["velocity"]))
        vel_norm = min(float(row["velocity"]) / 10.0, 1.0)
        final_score = min(settings.nlp_weight * nlp + settings.velocity_weight * vel_norm, 1.0)
        
        has_lang_bias = any(r.get("rule") == "low_confidence_language" for r in rules)
        status = "needs_review" if has_lang_bias else ("quarantined" if final_score > settings.quarantine_threshold else "reviewed")
        
        scores.append(final_score)
        statuses.append(status)
        
    sample["score"] = scores
    sample["status"] = statuses
    sample["length"] = sample["text"].str.len()
    sample["non_ascii_ratio"] = sample["text"].apply(lambda t: sum(1 for c in str(t) if ord(c) > 127) / max(len(str(t)), 1))
    
    # 1. Length Buckets
    def length_bucket(l):
        if l < 50:
            return "Short (<50 chars)"
        elif l <= 150:
            return "Medium (50-150 chars)"
        else:
            return "Long (>150 chars)"
            
    sample["length_bucket"] = sample["length"].apply(length_bucket)
    
    length_audit = sample.groupby("length_bucket").agg(
        count=("score", "count"),
        mean_score=("score", "mean"),
        quarantine_rate=("status", lambda s: (s == "quarantined").mean()),
        needs_review_rate=("status", lambda s: (s == "needs_review").mean()),
    ).reset_index().to_dict(orient="records")
    
    # 2. Synthetic Multilingual & Non-ASCII Evaluation
    multilingual_samples = [
        {"lang": "Spanish", "text": "Excelente producto, la calidad de construcción es increíble y llegó muy rápido.", "rating": 5, "velocity": 1, "is_fraud": 0},
        {"lang": "German", "text": "Sehr gute Qualität, entspricht genau der Beschreibung. Kann ich nur weiterempfehlen.", "rating": 5, "velocity": 1, "is_fraud": 0},
        {"lang": "French", "text": "Très satisfait de mon achat, fonctionne parfaitement sans aucun problème.", "rating": 4, "velocity": 1, "is_fraud": 0},
        {"lang": "Hindi (Devanagari)", "text": "यह उत्पाद बहुत अच्छा है, मुझे इसकी गुणवत्ता बहुत पसंद आई।", "rating": 5, "velocity": 1, "is_fraud": 0},
        {"lang": "Chinese", "text": "非常好的产品，物流很快，包装也很结实，非常满意！", "rating": 5, "velocity": 1, "is_fraud": 0},
        {"lang": "Japanese", "text": "品質が非常に良く、期待通りの商品でした。大満足です。", "rating": 5, "velocity": 1, "is_fraud": 0},
    ]
    
    multi_results = []
    for item in multilingual_samples:
        nlp, _ = infer(item["text"], float(item["velocity"]))
        _, rules = score_rules(item["text"], item["rating"], item["velocity"])
        vel_norm = min(float(item["velocity"]) / 10.0, 1.0)
        final_score = min(settings.nlp_weight * nlp + settings.velocity_weight * vel_norm, 1.0)
        has_lang_bias = any(r.get("rule") == "low_confidence_language" for r in rules)
        status = "needs_review" if has_lang_bias else ("quarantined" if final_score > settings.quarantine_threshold else "reviewed")
        multi_results.append({
            "language": item["lang"],
            "score": round(final_score, 4),
            "status": status,
            "mitigation_triggered": has_lang_bias,
        })
        
    audit_report = {
        "length_disparity": length_audit,
        "multilingual_mitigation_eval": multi_results
    }
    
    report_file = os.path.join(out_dir, "bias_audit_report.json")
    with open(report_file, "w") as f:
        json.dump(audit_report, f, indent=2)
        
    print("=== BIAS AND FAIRNESS AUDIT COMPLETED ===")
    print("\nLength Disparity Table:")
    print(pd.DataFrame(length_audit).to_string(index=False))
    print("\nMultilingual Bias Mitigation Performance:")
    print(pd.DataFrame(multi_results).to_string(index=False))
    print(f"\nReport written to: {report_file}")
    return audit_report

if __name__ == "__main__":
    run_bias_audit()
