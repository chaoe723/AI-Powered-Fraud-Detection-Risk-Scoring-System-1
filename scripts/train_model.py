"""Train the Kaggle model with temporal validation and leakage-safe features."""
from pathlib import Path
import json, sys, argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve, roc_auc_score
from backend.data_pipeline import adapt_kaggle, FEATURE_COLUMNS
from backend.model_service import FraudModel

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / "data" / "kaggle" / "extracted"
ART = ROOT / "backend" / "artifacts"

def threshold_at(y, p, *, recall_target=None, precision_target=None):
    precision, recall, thresholds = precision_recall_curve(y, p)
    valid = np.flatnonzero((recall[:-1] >= recall_target) if recall_target else (precision[:-1] >= precision_target))
    if not len(valid): return .5
    # Thresholds are ascending. For a recall constraint, use the highest
    # threshold that still satisfies the requested recall; this makes the
    # high_recall profile deterministic and prevents an unexpectedly strict
    # threshold selected from a non-monotonic PR curve.
    i = valid[-1] if recall_target else valid[np.argmax(recall[valid])]
    return float(thresholds[i])

def cost_threshold(y, p, fn_cost=100, fp_cost=2, tp_cost=1):
    order = np.argsort(-p, kind="stable")
    sorted_p, sorted_y = p[order], np.asarray(y)[order]
    tp = np.cumsum(sorted_y); fp = np.cumsum(1 - sorted_y); fn = sorted_y.sum() - tp
    costs = fn * fn_cost + fp * fp_cost + tp * tp_cost
    i = int(np.argmin(costs))
    return float(sorted_p[i]), float(costs[i])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true", help="use the small repository demo dataset")
    parser.add_argument("--max-rows", type=int, default=None, help="read only the first N temporal rows from each Kaggle CSV")
    parser.add_argument("--artifact-dir", type=Path, default=ART, help="output directory; use a separate directory for smoke tests")
    args = parser.parse_args()
    output_artifacts = args.artifact_dir
    train_path = KAGGLE / "fraudTrain.csv"
    test_path = KAGGLE / "fraudTest.csv"
    if train_path.exists() and not args.synthetic:
        print(f"Loading Kaggle rows (limit={args.max_rows or 'full'})...", flush=True)
        raw_train = pd.read_csv(train_path, nrows=args.max_rows)
        raw_test_meta = pd.read_csv(test_path, usecols=["trans_date_trans_time", "is_fraud"], nrows=args.max_rows)
        train = adapt_kaggle(raw_train)
        test = raw_test_meta.rename(columns={"trans_date_trans_time": "transaction_time", "is_fraud": "label"})
    else:
        print("Loading demo dataset...", flush=True)
        train = pd.read_csv(ROOT / "data" / "training_data.csv")
        test = train.iloc[int(len(train)*.8):].copy(); train = train.iloc[:int(len(train)*.8)].copy()
    train = train.sort_values("transaction_time", kind="stable").reset_index(drop=True)
    n = len(train)
    fit_end, calibration_end = int(n * .60), int(n * .80)
    fit = train.iloc[:fit_end].copy()
    calibration = train.iloc[fit_end:calibration_end].copy()
    threshold_data = train.iloc[calibration_end:].copy()
    labels = fit["label"] if "label" in fit else fit["is_fraud"]
    print(f"Temporal split: fit={len(fit):,}, calibration={len(calibration):,}, threshold={len(threshold_data):,}", flush=True)
    service = FraudModel().fit(fit.drop(columns=["label", "is_fraud"], errors="ignore"), labels, progress=True)
    calibration_y = calibration["label" if "label" in calibration else "is_fraud"].to_numpy()
    rolling_state = service.prediction_state()
    # First obtain uncalibrated probabilities.  The calibration model is fit
    # only on this temporal holdout and never sees threshold/final-test labels.
    calibration_p_raw = service.predict(calibration.drop(columns=["label", "is_fraud"], errors="ignore"), state=rolling_state)["fraud_probability"].to_numpy()
    service.fit_probability_calibrator(calibration_y, calibration_p_raw)
    calibration_p = service.calibrate_probability(calibration_p_raw)
    threshold_y = threshold_data["label" if "label" in threshold_data else "is_fraud"].to_numpy()
    threshold_p = service.predict(threshold_data.drop(columns=["label", "is_fraud"], errors="ignore"), state=rolling_state)["fraud_probability"].to_numpy()
    cost_optimal, validation_cost = cost_threshold(threshold_y, threshold_p)
    service.thresholds = {"high_recall": threshold_at(threshold_y, threshold_p, recall_target=.95), "balanced": threshold_at(threshold_y, threshold_p, precision_target=.30), "strict": threshold_at(threshold_y, threshold_p, precision_target=.45), "cost_optimal": cost_optimal}
    service.decision_threshold = service.thresholds["balanced"]
    output_artifacts.mkdir(parents=True, exist_ok=True)
    service.save(output_artifacts / "fraud_model.joblib")
    (output_artifacts / "feature_schema.json").write_text(json.dumps(service.feature_schema, indent=2), encoding="utf-8")
    (output_artifacts / "thresholds.json").write_text(json.dumps(service.thresholds, indent=2), encoding="utf-8")
    metrics = {"model_version":"kaggle-v5", "dataset":"kartik2112/fraud-detection", "feature_count":len(FEATURE_COLUMNS), "categorical_features":["merchant_category"], "raw_identifier_excluded_from_model":["merchant_id"], "probability_calibration":"platt_sigmoid_on_temporal_calibration_window", "pr_auc_calibration":float(average_precision_score(calibration_y,calibration_p)), "roc_auc_calibration":float(roc_auc_score(calibration_y,calibration_p)), "pr_auc_threshold":float(average_precision_score(threshold_y,threshold_p)), "roc_auc_threshold":float(roc_auc_score(threshold_y,threshold_p)), "validation_cost":float(validation_cost), "costs":{"false_negative":100,"false_positive":2,"true_positive_review":1}}
    (output_artifacts / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    def time_range(frame):
        times = pd.to_datetime(frame.transaction_time, errors="raise")
        return {"start": times.min().isoformat(), "end": times.max().isoformat(), "rows": len(frame), "fraud_rate": float(frame["label" if "label" in frame else "is_fraud"].mean())}
    (output_artifacts / "training_config.json").write_text(json.dumps({"split":"60/20/20 temporal; fraudTest final", "no_raw_pii":True, "random_split":False, "splits":{"fit":time_range(fit),"calibration":time_range(calibration),"threshold":time_range(threshold_data),"final_test":time_range(test)}}, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
if __name__ == "__main__": main()
