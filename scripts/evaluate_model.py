"""Evaluate the saved fraud model with classification and operations metrics."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import argparse
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, confusion_matrix,
    f1_score, log_loss, precision_score, precision_recall_curve, recall_score,
    roc_auc_score,
)

from backend.model_service import FraudModel
from backend.data_pipeline import adapt_kaggle

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--max-rows", type=int, default=None)
parser.add_argument("--include-anomaly", action="store_true", help="Also calculate Isolation Forest scores (slower; not needed for classification metrics).")
parser.add_argument("--profile", choices=("high_recall", "balanced", "strict", "cost_optimal"), default="cost_optimal", help="Threshold profile used for the headline confusion-matrix metrics.")
args = parser.parse_args()
test_path = ROOT / "data" / "kaggle" / "extracted" / "fraudTest.csv"
if test_path.exists():
    print(f"Loading fraudTest.csv (limit={args.max_rows or 'full'})...", flush=True)
    test = adapt_kaggle(pd.read_csv(test_path, nrows=args.max_rows))
    label_column = "label"
else:
    data = pd.read_csv(ROOT / "data" / "training_data.csv")
    data["transaction_time"] = pd.to_datetime(data["transaction_time"])
    data = data.sort_values("transaction_time").reset_index(drop=True)
    test = data.iloc[int(len(data) * 0.80):].copy()
    label_column = "is_fraud"
service = FraudModel.load(ROOT / "backend" / "artifacts" / "fraud_model.joblib")
metrics_path = ROOT / "backend" / "artifacts" / "metrics.json"
model_metadata = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
print(f"Loaded model; evaluating {len(test):,} rows...", flush=True)
y = test[label_column].to_numpy()
features = test.drop(columns=[label_column])
probability = service.predict(features, progress=True, include_anomaly=args.include_anomaly)["fraud_probability"].to_numpy()
print("      predictions complete; calculating metrics...", flush=True)
operating_threshold = float(getattr(service, "thresholds", {}).get(args.profile, service.decision_threshold))
predicted = probability >= operating_threshold
tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
precision = precision_score(y, predicted, zero_division=0)
recall = recall_score(y, predicted, zero_division=0)
f2 = 5 * precision * recall / (4 * precision + recall + 1e-12)

print(f"profile={args.profile} threshold={operating_threshold:.4f}")
print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
print(f"accuracy={accuracy_score(y, predicted):.4f}")
print(f"precision={precision:.4f} recall={recall:.4f}")
print(f"specificity={tn / (tn + fp):.4f} f1={f1_score(y, predicted):.4f} f2={f2:.4f}")
roc_auc = roc_auc_score(y, probability) if len(np.unique(y)) == 2 else float("nan")
print(f"roc_auc={roc_auc:.4f} pr_auc={average_precision_score(y, probability):.4f}")
print(f"log_loss={log_loss(y, probability, labels=[0, 1]):.4f} brier_loss={brier_score_loss(y, probability):.4f}")

precision_curve, recall_curve, thresholds = precision_recall_curve(y, probability)
eligible = np.flatnonzero(precision_curve >= 0.30)
print(f"recall_at_precision_30={recall_curve[eligible].max():.4f}" if len(eligible) else "recall_at_precision_30=unavailable")
for percent in (1, 5, 10):
    k = max(1, int(len(y) * percent / 100))
    top = np.argsort(-probability)[:k]
    top_precision = y[top].mean()
    top_recall = y[top].sum() / y.sum() if y.sum() else 0.0
    print(f"top_{percent}pct: k={k} precision={top_precision:.4f} recall={top_recall:.4f} fdr={1 - top_precision:.4f}")

# Operational threshold: FN is intentionally much more expensive than FP.
costs = {"false_negative": 100, "false_positive": 2, "true_positive_review": 1}
operating = np.unique(np.r_[0.0, probability, 1.0])
order = np.argsort(-probability, kind="stable")
sorted_probability, sorted_y = probability[order], y[order]
tp_curve = np.cumsum(sorted_y)
fp_curve = np.cumsum(1 - sorted_y)
fn_curve = sorted_y.sum() - tp_curve
cost_curve = fn_curve * costs["false_negative"] + fp_curve * costs["false_positive"] + tp_curve * costs["true_positive_review"]
costs_by_threshold = list(zip(cost_curve, sorted_probability))
costs_by_threshold.append((y.sum() * costs["false_negative"], 1.0))
best_cost, best_threshold = min(costs_by_threshold)
print(f"cost_optimal_threshold={best_threshold:.6f} total_cost={best_cost:.0f}")

def operating_metrics(threshold):
    selected = probability >= float(threshold)
    p = precision_score(y, selected, zero_division=0)
    r = recall_score(y, selected, zero_division=0)
    tn_i, fp_i, fn_i, tp_i = confusion_matrix(y, selected, labels=[0, 1]).ravel()
    total = fn_i * costs["false_negative"] + fp_i * costs["false_positive"] + tp_i * costs["true_positive_review"]
    return {"threshold": float(threshold), "tp": int(tp_i), "fp": int(fp_i), "tn": int(tn_i), "fn": int(fn_i), "precision": float(p), "recall": float(r), "f1": float(f1_score(y, selected, zero_division=0)), "cost": float(total)}

profile_metrics = {}
for profile, profile_threshold in getattr(service, "thresholds", {}).items():
    profile_metrics[profile] = operating_metrics(profile_threshold)
print("threshold_profiles=" + json.dumps(profile_metrics, sort_keys=True))

def grouped_metrics(frame, group_values):
    output = {}
    groups = pd.Series(group_values, index=frame.index).astype(str)
    for name in groups.unique():
        mask = groups.to_numpy() == name
        if mask.sum() < 2 or len(np.unique(y[mask])) < 2:
            continue
        output[name] = {"rows": int(mask.sum()), "fraud_rate": float(y[mask].mean()), "pr_auc": float(average_precision_score(y[mask], probability[mask])), "precision": float(precision_score(y[mask], predicted[mask], zero_division=0)), "recall": float(recall_score(y[mask], predicted[mask], zero_division=0))}
    return output

segment_metrics = {}
if "transaction_time" in test.columns:
    segment_metrics["month"] = grouped_metrics(test, pd.to_datetime(test["transaction_time"]).dt.to_period("M").astype(str))
if "amount" in test.columns:
    segment_metrics["amount_band"] = grouped_metrics(test, pd.cut(test["amount"], bins=[-np.inf, 50, 200, 1000, 3000, np.inf], labels=["<=50", "50-200", "200-1000", "1000-3000", ">3000"]))

evaluation = {
    "model_version": model_metadata.get("model_version"), "rows": int(len(y)), "fraud_count": int(y.sum()), "fraud_rate": float(y.mean()),
    "profile": args.profile, "threshold": operating_threshold, "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
    "accuracy": float(accuracy_score(y, predicted)), "precision": float(precision), "recall": float(recall),
    "specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0, "f1": float(f1_score(y, predicted)), "f2": float(f2),
    "roc_auc": None if np.isnan(roc_auc) else float(roc_auc), "pr_auc": float(average_precision_score(y, probability)),
    "log_loss": float(log_loss(y, probability, labels=[0, 1])), "brier_loss": float(brier_score_loss(y, probability)),
    "recall_at_precision_30": float(recall_curve[eligible].max()) if len(eligible) else None,
    "cost_optimal_threshold": float(best_threshold), "cost_optimal_total": float(best_cost),
    "costs": costs, "threshold_profiles": profile_metrics, "segments": segment_metrics,
}
for percent in (1, 5, 10):
    k = max(1, int(len(y) * percent / 100)); top = np.argsort(-probability)[:k]
    evaluation[f"top_{percent}pct"] = {"k": k, "precision": float(y[top].mean()), "recall": float(y[top].sum() / y.sum()) if y.sum() else 0.0, "fdr": float(1 - y[top].mean())}
(ROOT / "backend" / "artifacts" / "evaluation_metrics.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
