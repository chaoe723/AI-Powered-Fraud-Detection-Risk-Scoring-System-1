from pathlib import Path
from threading import Lock
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import api_v1, storage
from .model_service import FraudModel
from .data_pipeline import adapt_kaggle
from .risk_scoring import score
from .schemas import BatchPrediction, HealthResponse, Prediction, Transaction

MODEL_PATH = Path(__file__).parent / "artifacts" / "fraud_model.joblib"


def _cors_origins() -> list[str]:
    raw = os.getenv("FRAUD_CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


async def lifespan(app: FastAPI):
    storage.init_db()
    # A queued/processing job from a previous process can never resume.
    storage.mark_stale_jobs_failed()
    yield


app = FastAPI(title="Fraud Detection API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_compatible_model():
    if not MODEL_PATH.exists(): return FraudModel()
    loaded = FraudModel.load(MODEL_PATH)
    # Do not boot an artifact produced by the pre-Kaggle feature pipeline.
    expected = __import__("backend.model_service", fromlist=["CATEGORICAL"]).CATEGORICAL
    schema = getattr(loaded, "feature_schema", {})
    if schema.get("features") != __import__("backend.data_pipeline", fromlist=["FEATURE_COLUMNS"]).FEATURE_COLUMNS or schema.get("categorical") != expected:
        return FraudModel()
    return loaded
model = load_compatible_model()
live_state = model.prediction_state()
live_state_lock = Lock()

# v1 (upload/analysis jobs) shares the same loaded artifact instance.
api_v1.bind_model(model)
app.include_router(api_v1.v1_router)
api_v1.install_v1_error_handlers(app)


def make_prediction_from_result(transaction: Transaction, result: pd.Series, profile: str = "cost_optimal") -> Prediction:
    probability = float(result.fraud_probability)
    anomaly = bool(result.anomaly)
    threshold = float(getattr(model, "thresholds", {}).get(profile, getattr(model, "decision_threshold", .5)))
    reasons = []
    if anomaly: reasons.append("anomalous_transaction_pattern")
    if transaction.amount >= 3000: reasons.append("high_transaction_amount")
    if probability >= threshold: reasons.append("high_model_probability")
    risk = score(probability, anomaly, transaction.amount, anomaly_score=float(result.get("anomaly_score", 0)), threshold=threshold, profile=profile, reasons=reasons)
    return Prediction(user_id=transaction.user_id, fraud_probability=round(probability, 4), anomaly=anomaly, **risk)

def make_prediction(transaction: Transaction, profile: str = "cost_optimal") -> Prediction:
    if not model.loaded:
        raise HTTPException(status_code=503, detail="model is not trained")
    frame = pd.DataFrame([transaction.model_dump()])
    # Keep online velocity/history features alive across requests in this
    # process.  The state is label-free after training and protected because
    # FeatureState is mutable.
    with live_state_lock:
        result = model.predict(frame, state=live_state).iloc[0]
    return make_prediction_from_result(transaction, result, profile)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=model.loaded)


@app.post("/predict", response_model=Prediction)
def predict(transaction: Transaction, threshold_profile: str = Query("cost_optimal", pattern="^(high_recall|balanced|strict|cost_optimal)$")) -> Prediction:
    return make_prediction(transaction, threshold_profile)


@app.post("/predict/batch", response_model=BatchPrediction)
async def predict_batch(file: UploadFile, threshold_profile: str = Query("cost_optimal", pattern="^(high_recall|balanced|strict|cost_optimal)$")) -> BatchPrediction:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="only CSV files are supported")
    try:
        frame = pd.read_csv(file.file)
        if "trans_num" in frame.columns or "cc_num" in frame.columns:
            frame = adapt_kaggle(frame)
        transactions = [Transaction(**row) for row in frame.to_dict(orient="records")]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid CSV: {exc}") from exc
    if not model.loaded:
        raise HTTPException(status_code=503, detail="model is not trained")
    raw = pd.DataFrame([transaction.model_dump() for transaction in transactions])
    with live_state_lock:
        results = model.predict(raw, state=live_state)
    predictions = []
    for transaction, (_, result) in zip(transactions, results.iterrows()):
        predictions.append(make_prediction_from_result(transaction, result, threshold_profile))
    return BatchPrediction(count=len(predictions), predictions=predictions)
