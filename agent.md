# Agent instructions for this project

## Project context

This is an AI fraud detection and risk scoring system using the Kaggle fraud dataset.

- Main data: `data/kaggle/extracted/fraudTrain.csv` and `fraudTest.csv`.
- `cc_num` must be hashed; do not use raw PII such as `first`, `last`, `street`, `dob`, `job`, or `zip`.
- Preserve temporal ordering. Do not use random split or future labels in history features.
- Current temporal split: `fraudTrain.csv` 60% fit, 20% calibration, 20% threshold selection; `fraudTest.csv` is final test only.
- Stateful history and fixed anomaly score reference are part of the current pipeline.

## Model decision

- Production model: Random Forest.
- Fallback model: HistGradientBoosting.
- Baseline: Logistic Regression.
- Decision rationale is stored in `backend/artifacts/model_selection.json`.
- Current model has 34 engineered features.
- Raw `merchant_id` is excluded from one-hot encoding because it is high-cardinality; merchant history/count/rate features carry its signal.
- Primary metrics are PR-AUC, Precision, Recall, F1/F2, FDR and expected cost. Accuracy alone is not sufficient because fraud is below 1% of transactions.

## Fast validation workflow

After changing feature, model, threshold or evaluation logic, run these in order:

```powershell
python -m py_compile backend\app.py backend\data_pipeline.py backend\model_service.py scripts\train_model.py scripts\evaluate_model.py scripts\benchmark_models.py
python -m pytest -q
.\run_tuned.bat quick
```

`quick` runs an end-to-end 5,000-row pipeline.

Use progressively larger runs only after quick passes:

```powershell
.\run_tuned.bat 20000
.\run_tuned.bat 50000
.\run_tuned.bat 500000
.\run_tuned.bat full
```

If only evaluation/API logic changed and the existing artifact is valid:

```powershell
.\run_tuned.bat resume 5000
```

`resume` skips installation and training. It uses the existing `backend/artifacts/fraud_model.joblib`.

## Outputs

- `backend/artifacts/metrics.json`: training/validation metrics.
- `backend/artifacts/benchmark.json`: model comparison.
- `backend/artifacts/training_config.json`: split metadata, time ranges and fraud rates.
- `backend/artifacts/thresholds.json`: operating thresholds.
- `backend/artifacts/model_selection.json`: production model decision.
- `tuned_pipeline.log`: batch progress and errors.

## Implementation rules

- Keep progress output visible with `python -u` and `flush=True` for long operations.
- On Windows, use `n_jobs=1` for sklearn models because worker creation can fail with `WinError 5`.
- Keep anomaly training bounded to a representative sample for large datasets.
- Do not overwrite or delete user data, datasets, or artifacts without explicit instruction.
- When an artifact schema changes, retrain before testing API prediction.
- After implementation, run tests and at least a quick end-to-end check.
