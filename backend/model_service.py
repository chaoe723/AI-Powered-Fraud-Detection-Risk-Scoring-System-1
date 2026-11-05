from __future__ import annotations
from pathlib import Path
from time import perf_counter
from typing import Iterable
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from joblib import parallel_backend
from .data_pipeline import FEATURE_COLUMNS, FeatureState, build_features

# merchant_id is intentionally excluded from one-hot encoding: it is a
# high-cardinality identifier. Its historical/count features remain numeric.
CATEGORICAL = ["merchant_category"]
NUMERICAL = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL and c != "merchant_id"]

def _rf_threads() -> int:
    try:
        return max(1, int(os.getenv("FRAUD_RF_THREADS", "2")))
    except ValueError:
        return 2

RF_THREADS = _rf_threads()

def build_classifier(n_jobs: int = RF_THREADS) -> Pipeline:
    # Keep preprocessing single-worker. The threading backend is intended
    # only for the forest; parallel ColumnTransformer jobs trigger WinError 5
    # on some Windows Python installations.
    transform = ColumnTransformer([("numeric", "passthrough", NUMERICAL), ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)], n_jobs=1)
    return Pipeline([("features", transform), ("model", RandomForestClassifier(n_estimators=250, random_state=42, class_weight="balanced_subsample", n_jobs=n_jobs, min_samples_leaf=2, verbose=2))])

class FraudModel:
    def __init__(self, classifier=None, anomaly=None, decision_threshold=0.14, thresholds=None, feature_schema=None):
        self.classifier, self.anomaly = classifier, anomaly
        self.decision_threshold = float(decision_threshold)
        self.thresholds = thresholds or {}
        self.feature_schema = feature_schema or {"schema_version": 2, "features": FEATURE_COLUMNS, "categorical": CATEGORICAL, "numerical": NUMERICAL, "excluded_raw_identifiers": ["merchant_id"]}
        self.feature_state = None
        self.anomaly_score_bounds = (0.0, 1.0)
        self.probability_calibrator = None

    @property
    def loaded(self): return self.classifier is not None and self.anomaly is not None

    def fit(self, rows: pd.DataFrame, labels: Iterable[int], progress: bool = False) -> "FraudModel":
        labels = np.asarray(list(labels), dtype=int)
        print(f"      preparing {len(rows):,} rows and {len(FEATURE_COLUMNS)} features...", flush=True) if progress else None
        self.feature_state = FeatureState()
        features = build_features(rows, labels, progress=progress, state=self.feature_state)
        started = perf_counter()
        print(f"      fitting supervised Random Forest (Windows-safe threading, {RF_THREADS} workers)...", flush=True) if progress else None
        try:
            # Threading avoids Windows loky/process permission issues while
            # preserving the same forest size, sampling, and random seed.
            with parallel_backend("threading", n_jobs=RF_THREADS):
                self.classifier = build_classifier(RF_THREADS).fit(features, labels)
        except (PermissionError, OSError) as exc:
            # Some managed Windows installations deny the thread-pool pipe.
            # Fall back automatically so training remains reliable and the
            # model configuration/quality is unchanged.
            if RF_THREADS <= 1:
                raise
            print("      threading unavailable on this Windows session; falling back to single worker.", flush=True)
            try:
                self.classifier = build_classifier(1).fit(features, labels)
            except MemoryError as memory_exc:
                raise MemoryError("Random Forest training ran out of memory. Raw merchant_id is excluded from one-hot encoding; set FRAUD_RF_THREADS=1 or reduce --max-rows.") from memory_exc
        except MemoryError as exc:
            raise MemoryError("Random Forest training ran out of memory. Raw merchant_id is excluded from one-hot encoding; set FRAUD_RF_THREADS=1 or reduce --max-rows.") from exc
        print(f"      Random Forest done in {perf_counter() - started:.1f}s", flush=True) if progress else None
        # Isolation Forest needs only a representative sample because each tree
        # already trains on small random sub-samples. This avoids holding a
        # million-row training matrix in every parallel worker.
        anomaly_rows = min(200_000, len(features))
        anomaly_features = features[NUMERICAL].iloc[:anomaly_rows]
        started = perf_counter()
        print(f"      fitting Isolation Forest on {anomaly_rows:,}/{len(features):,} rows...", flush=True) if progress else None
        try:
            self.anomaly = IsolationForest(contamination="auto", random_state=42, n_jobs=1, verbose=1).fit(anomaly_features)
        except MemoryError as exc:
            raise MemoryError("Isolation Forest training ran out of memory. Reduce the training row limit.") from exc
        reference_scores = -self.anomaly.score_samples(anomaly_features)
        self.anomaly_score_bounds = tuple(float(x) for x in np.percentile(reference_scores, [1, 99]))
        print(f"      Isolation Forest done in {perf_counter() - started:.1f}s", flush=True) if progress else None
        return self

    def prediction_state(self):
        state = getattr(self, "feature_state", None)
        return state.clone() if state is not None else FeatureState()

    def fit_probability_calibrator(self, labels: Iterable[int], probability: np.ndarray) -> None:
        """Fit a small Platt (sigmoid) calibrator on a time-held-out window.

        The classifier remains unchanged.  This only makes the returned
        probability more meaningful for threshold and cost decisions.
        """
        y = np.asarray(list(labels), dtype=int)
        p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
        if len(np.unique(y)) < 2:
            self.probability_calibrator = None
            return
        logits = np.log(p / (1.0 - p)).reshape(-1, 1)
        self.probability_calibrator = LogisticRegression(solver="lbfgs", max_iter=200).fit(logits, y)

    def calibrate_probability(self, probability: np.ndarray) -> np.ndarray:
        calibrator = getattr(self, "probability_calibrator", None)
        p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
        if calibrator is None:
            return p
        logits = np.log(p / (1.0 - p)).reshape(-1, 1)
        return calibrator.predict_proba(logits)[:, 1]

    def predict(self, rows: pd.DataFrame, progress: bool = False, state: FeatureState | None = None,
                include_anomaly: bool = True) -> pd.DataFrame:
        """Score transactions.

        ``include_anomaly=False`` is intended for offline classification
        evaluation.  It avoids the second Isolation Forest pass while keeping
        fraud probabilities exactly the same.  The API continues to use the
        default because it exposes the anomaly/risk fields to callers.
        """
        if not self.loaded: raise RuntimeError("model is not loaded")
        if progress: print(f"      preparing evaluation features for {len(rows):,} rows...", flush=True)
        state = self.prediction_state() if state is None else state
        features = build_features(rows, progress=progress, state=state)
        if progress: print("      calculating fraud probabilities...", flush=True)
        probability = self.classifier.predict_proba(features)[:, 1]
        probability = self.calibrate_probability(probability)
        if not include_anomaly:
            if progress: print("      anomaly scoring skipped (classification metrics only).", flush=True)
            return pd.DataFrame({"fraud_probability": probability})
        if progress: print("      calculating anomaly scores...", flush=True)
        anomaly_score = -self.anomaly.score_samples(features[NUMERICAL])
        low, high = getattr(self, "anomaly_score_bounds", (0.0, 1.0))
        anomaly_score = np.clip((anomaly_score-low)/(high-low+1e-9), 0, 1)
        return pd.DataFrame({"fraud_probability": probability, "anomaly": self.anomaly.predict(features[NUMERICAL]) == -1, "anomaly_score": anomaly_score})

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(path).with_suffix(Path(path).suffix + ".tmp")
        joblib.dump(self, temporary)
        temporary.replace(path)

    @classmethod
    def load(cls, path: str | Path) -> "FraudModel": return joblib.load(path)
