"""Benchmark classical classifiers on the same temporal feature matrix."""
from pathlib import Path
import json, sys, time
import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from backend.data_pipeline import adapt_kaggle, build_features, FEATURE_COLUMNS, FeatureState

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "backend" / "artifacts"

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()
    print(f"Loading {args.max_rows or 'all'} temporal rows...", flush=True)
    raw = pd.read_csv(ROOT / "data/kaggle/extracted/fraudTrain.csv", nrows=args.max_rows)
    data = adapt_kaggle(raw).sort_values("transaction_time", kind="stable").reset_index(drop=True)
    labels = data["label"].to_numpy(dtype=int)
    fit_end, calibration_end = int(len(data)*.60), int(len(data)*.80)
    print("Building leakage-safe temporal feature matrices...", flush=True)
    feature_state = FeatureState()
    fit = data.iloc[:fit_end]
    calibration = data.iloc[fit_end:calibration_end]
    threshold = data.iloc[calibration_end:]
    fit_features = build_features(fit.drop(columns=["label"]), fit["label"], progress=True, state=feature_state)
    # At prediction time labels from calibration/threshold are not available
    # to feature engineering.  Carry only label-free history forward.
    build_features(calibration.drop(columns=["label"]), progress=True, state=feature_state)
    threshold_features = build_features(threshold.drop(columns=["label"]), progress=True, state=feature_state)
    x_fit = fit_features.drop(columns=["merchant_category", "merchant_id"])
    x_threshold = threshold_features.drop(columns=["merchant_category", "merchant_id"])
    y_fit, y_threshold = labels[:fit_end], labels[calibration_end:]
    positive_weight = max(1.0, (len(y_fit)-y_fit.sum()) / max(y_fit.sum(), 1))
    models = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, class_weight="balanced", random_state=42)),
        "random_forest": RandomForestClassifier(n_estimators=250, min_samples_leaf=2, class_weight="balanced_subsample", random_state=42, n_jobs=1),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=200, learning_rate=.08, max_leaf_nodes=31, random_state=42),
    }
    results = {}
    for name, model in models.items():
        started = time.perf_counter()
        try:
            if name == "hist_gradient_boosting":
                weights = np.where(y_fit == 1, positive_weight, 1.0)
                model.fit(x_fit, y_fit, sample_weight=weights)
            else:
                model.fit(x_fit, y_fit)
        except (PermissionError, OSError) as exc:
            results[name] = {"status": "unavailable", "error": str(exc)}
            print(f"{name}: unavailable ({exc})", flush=True)
            continue
        fit_seconds = time.perf_counter() - started
        started = time.perf_counter(); probability = model.predict_proba(x_threshold)[:, 1]; predict_seconds = time.perf_counter() - started
        threshold = float(np.quantile(probability, .99))
        predicted = probability >= threshold
        results[name] = {"fit_seconds":round(fit_seconds, 3), "predict_seconds":round(predict_seconds, 3), "threshold_top_1pct":threshold, "pr_auc":float(average_precision_score(y_threshold, probability)), "roc_auc":float(roc_auc_score(y_threshold, probability)), "precision_at_top_1pct":float(precision_score(y_threshold, predicted, zero_division=0)), "recall_at_top_1pct":float(recall_score(y_threshold, predicted, zero_division=0))}
        print(f"{name}: fit={fit_seconds:.1f}s, PR-AUC={results[name]['pr_auc']:.4f}, ROC-AUC={results[name]['roc_auc']:.4f}", flush=True)
    output = {"rows":len(data), "feature_count":len(FEATURE_COLUMNS), "split":"60/20/20 temporal", "label_leakage_safe":True, "threshold_features_use_future_labels":False, "models":results}
    ART.mkdir(exist_ok=True); (ART / "benchmark.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
if __name__ == "__main__": main()
