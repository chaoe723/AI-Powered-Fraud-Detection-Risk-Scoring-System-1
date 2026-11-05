"""API v1 (class 2): upload file -> async analysis job -> dashboard data.

Bound by plan/API_CONTRACT.md. Legacy endpoints in app.py stay untouched;
this router only adds /api/v1/* plus the unified error envelope, so a legacy
response and a v1 response can never be confused by the frontend.
"""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Form, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import storage
from .data_pipeline import FeatureState, adapt_transaction
from .risk_scoring import score
from .schemas import Transaction

API_PREFIX = "/api/v1"
v1_router = APIRouter(prefix=API_PREFIX)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ROWS = 100_000
CHUNK_SIZE = 5_000
HIGH_AMOUNT_REASON_THRESHOLD = 3000.0
RISK_LEVELS = ("low", "medium", "high", "critical")
DECISIONS = ("allow", "manual_review", "block")
THRESHOLD_PROFILES = ("high_recall", "balanced", "strict", "cost_optimal")
SORT_FIELDS = ("amount", "risk_score", "fraud_probability", "transaction_time")
ARTIFACT_DIR = Path(__file__).parent / "artifacts"

# Bound by app.py at startup so the job reuses the already-loaded legacy model
# instance (loading the joblib artifact twice would double memory for nothing).
_model_holder: dict = {}


def bind_model(model: Any) -> None:
    _model_holder["model"] = model


def get_model() -> Any:
    return _model_holder.get("model")


class ApiV1Error(Exception):
    """Error that must reach the frontend as the unified envelope of contract §5."""

    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


_HTTP_ERROR_CODES = {
    400: "UNSUPPORTED_FORMAT",
    404: "ANALYSIS_NOT_FOUND",
    409: "ANALYSIS_NOT_COMPLETED",
    413: "FILE_TOO_LARGE",
    422: "INVALID_FILE",
    503: "MODEL_NOT_LOADED",
}


def install_v1_error_handlers(app: Any) -> None:
    def envelope(code: str, message: str) -> dict:
        return {"error": {"code": code, "message": message}}

    @app.exception_handler(ApiV1Error)
    async def handle_api_v1_error(request: Request, exc: ApiV1Error) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=envelope(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.startswith(API_PREFIX):
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
            )
            return JSONResponse(status_code=422, content=envelope("VALIDATION_ERROR", details))
        return JSONResponse(status_code=422, content=jsonable_encoder({"detail": exc.errors()}))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if request.url.path.startswith(API_PREFIX):
            code = _HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
            message = exc.detail if isinstance(exc.detail, str) else "request failed"
            return JSONResponse(status_code=exc.status_code, content=envelope(code, message), headers=exc.headers)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #

def analysis_to_dict(row: storage.Analysis, *, include_summary: bool = True) -> dict:
    data = {
        "id": row.id,
        "filename": row.filename,
        "status": row.status,
        "row_count": row.row_count,
        "processed_rows": row.processed_rows,
        "threshold_profile": row.threshold_profile,
        "error": row.error,
        "summary": None,
        "created_at": row.created_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
    if include_summary and row.summary_json:
        data["summary"] = json.loads(row.summary_json)
    return data


def transaction_to_dict(row: storage.TransactionRow) -> dict:
    return {
        "transaction_id": row.transaction_id,
        "user_id": row.user_id,
        "transaction_time": row.transaction_time.isoformat(),
        "amount": row.amount,
        "payment_method": row.payment_method,
        "device": row.device,
        "country": row.country,
        "fraud_probability": round(row.fraud_probability, 4),
        "anomaly": bool(row.anomaly),
        "risk_score": round(row.risk_score, 2),
        "risk_level": row.risk_level,
        "decision": row.decision,
        "reasons": json.loads(row.reasons_json),
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (np.bool_, np.integer)):
        return value.item()
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, pd.Series, np.ndarray)):
        return [_jsonable(item) for item in value]
    return str(value)


def _require_completed(analysis_id: int) -> storage.Analysis:
    analysis = storage.get_analysis(analysis_id)
    if analysis is None:
        raise ApiV1Error("ANALYSIS_NOT_FOUND", f"Analysis {analysis_id} does not exist", 404)
    if analysis.status != "completed":
        raise ApiV1Error("ANALYSIS_NOT_COMPLETED", f"Analysis {analysis_id} is {analysis.status}", 409)
    return analysis


# --------------------------------------------------------------------------- #
# Analysis job (runs in the threadpool via BackgroundTasks, sync on purpose)
# --------------------------------------------------------------------------- #

def _score_frame_chunk(frame: pd.DataFrame, results: pd.DataFrame, threshold: float, profile: str, raw_records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for position, (_, result) in enumerate(results.iterrows()):
        original = frame.iloc[position]
        amount = float(original.amount)
        probability = float(result.fraud_probability)
        anomaly = bool(result.anomaly)
        reasons = []
        if anomaly:
            reasons.append("anomalous_transaction_pattern")
        if amount >= HIGH_AMOUNT_REASON_THRESHOLD:
            reasons.append("high_transaction_amount")
        if probability >= threshold:
            reasons.append("high_model_probability")
        risk = score(
            probability,
            anomaly,
            amount,
            anomaly_score=float(result.get("anomaly_score", 0.0)),
            threshold=threshold,
            profile=profile,
            reasons=reasons,
        )
        raw = raw_records[position]
        rows.append(
            {
                "transaction_id": raw.get("transaction_id"),
                "user_id": int(original.user_id),
                "transaction_time": original.transaction_time.to_pydatetime(),
                "amount": amount,
                "payment_method": str(original.payment_method),
                "device": str(original.device),
                "country": str(original.country),
                "fraud_probability": probability,
                "anomaly": anomaly,
                "risk_score": float(risk["risk_score"]),
                "risk_level": str(risk["risk_level"]).lower(),
                "decision": str(risk["decision"]),
                "reasons_json": json.dumps(reasons),
                "raw_json": json.dumps(raw, ensure_ascii=False),
            }
        )
    return rows


def compute_summary(rows: list[dict], labels: list[float | None] | None) -> dict:
    frame = pd.DataFrame(rows)
    total = len(frame)
    flagged = (frame["decision"] != "allow").astype(int)
    labeled_fraud_rate = None
    if labels is not None:
        series = pd.Series(labels, dtype="float64").dropna()
        if len(series):
            labeled_fraud_rate = round(float(series.mean()), 6)
    summary = {
        "total_transactions": total,
        "flagged_transactions": int(flagged.sum()),
        "flagged_rate": round(float(flagged.mean()), 6) if total else 0.0,
        "labeled_fraud_rate": labeled_fraud_rate,
        "fraud_probability_avg": round(float(frame["fraud_probability"].mean()), 6),
        "risk_score_avg": round(float(frame["risk_score"].mean()), 4),
        "amount_total": round(float(frame["amount"].sum()), 2),
        "risk_distribution": {level: int((frame["risk_level"] == level).sum()) for level in RISK_LEVELS},
        "decision_distribution": {decision: int((frame["decision"] == decision).sum()) for decision in DECISIONS},
    }
    dates = pd.to_datetime(frame["transaction_time"]).dt.date.astype(str)
    trends = (
        pd.DataFrame({"date": dates, "flagged": flagged, "risk": frame["risk_score"]})
        .groupby("date", sort=True)
        .agg(transactions=("date", "size"), flagged=("flagged", "sum"), avg_risk_score=("risk", "mean"))
        .reset_index()
    )
    summary["trends"] = [
        {
            "date": row.date,
            "transactions": int(row.transactions),
            "flagged": int(row.flagged),
            "avg_risk_score": round(float(row.avg_risk_score), 4),
        }
        for row in trends.itertuples()
    ]
    for key, column in (("device_breakdown", "device"), ("country_breakdown", "country")):
        grouped = (
            pd.DataFrame({"k": frame[column], "flagged": flagged, "p": frame["fraud_probability"]})
            .groupby("k")
            .agg(transactions=("k", "size"), flagged=("flagged", "sum"), fraud_probability_avg=("p", "mean"))
            .reset_index()
            .sort_values("transactions", ascending=False)
            .head(10)
        )
        name = "device" if key == "device_breakdown" else "country"
        summary[key] = [
            {
                name: row.k,
                "transactions": int(row.transactions),
                "flagged": int(row.flagged),
                "fraud_probability_avg": round(float(row.fraud_probability_avg), 6),
            }
            for row in grouped.itertuples()
        ]
    return summary


def run_analysis_job(analysis_id: int, records: list[dict], raw_records: list[dict], labels: list[float | None] | None, threshold_profile: str) -> None:
    try:
        storage.set_status(analysis_id, "processing")
        model = get_model()
        if model is None or not model.loaded:
            raise RuntimeError("model artifact is not loaded")
        frame = pd.DataFrame(records)
        frame["transaction_time"] = pd.to_datetime(frame["transaction_time"])
        # Velocity/history features assume temporal order; score in that order,
        # raw records and labels stay aligned through the same permutation.
        order = frame.sort_values("transaction_time", kind="stable").index
        frame = frame.loc[order].reset_index(drop=True)
        raw_records = [raw_records[position] for position in order]
        if labels is not None:
            labels = [labels[position] for position in order]
        threshold = float(getattr(model, "thresholds", {}).get(threshold_profile, getattr(model, "decision_threshold", 0.5)))
        state = FeatureState()
        scored_rows: list[dict] = []
        processed = 0
        for start in range(0, len(frame), CHUNK_SIZE):
            chunk = frame.iloc[start : start + CHUNK_SIZE]
            results = model.predict(chunk, state=state)
            chunk_rows = _score_frame_chunk(chunk, results, threshold, threshold_profile, raw_records[start : start + CHUNK_SIZE])
            storage.bulk_insert_transactions(analysis_id, chunk_rows)
            scored_rows.extend(chunk_rows)
            processed += len(chunk)
            storage.set_processed_rows(analysis_id, processed)
        summary = compute_summary(scored_rows, labels)
        storage.save_summary(analysis_id, summary)
        storage.set_status(analysis_id, "completed", completed=True)
    except Exception as exc:  # noqa: BLE001 — any failure must land in the job row
        storage.set_status(analysis_id, "failed", error=str(exc)[:2000], completed=True)


# --------------------------------------------------------------------------- #
# Endpoints (contract §4)
# --------------------------------------------------------------------------- #

@v1_router.post("/analyses", status_code=202)
def create_analysis(background: BackgroundTasks, file: UploadFile, threshold_profile: str = Form("cost_optimal", pattern="^(high_recall|balanced|strict|cost_optimal)$")) -> JSONResponse:
    model = get_model()
    if model is None or not model.loaded:
        raise ApiV1Error("MODEL_NOT_LOADED", "model artifact is not loaded", 503)
    name = file.filename or ""
    if not name.lower().endswith((".csv", ".xlsx")):
        raise ApiV1Error("UNSUPPORTED_FORMAT", "only .csv and .xlsx files are supported", 400)
    file.file.seek(0, io.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ApiV1Error("FILE_TOO_LARGE", f"file is {size} bytes, limit is {MAX_UPLOAD_BYTES}", 413)
    try:
        if name.lower().endswith(".xlsx"):
            frame = pd.read_excel(file.file, engine="openpyxl")
        else:
            frame = pd.read_csv(file.file, low_memory=False)
    except Exception as exc:  # noqa: BLE001 — parser differences all mean a bad file
        raise ApiV1Error("INVALID_FILE", f"cannot parse file: {exc}", 422) from exc
    if frame.empty:
        raise ApiV1Error("INVALID_FILE", "file has no data rows", 422)
    if len(frame) > MAX_ROWS:
        raise ApiV1Error("ROW_LIMIT_EXCEEDED", f"file has {len(frame)} rows, limit is {MAX_ROWS}", 413)
    label_source = None
    if "is_fraud" in frame.columns:
        label_source = pd.to_numeric(frame["is_fraud"], errors="coerce")
    elif "label" in frame.columns:
        label_source = pd.to_numeric(frame["label"], errors="coerce")
    try:
        adapted = adapt_transaction(frame)
    except Exception as exc:  # noqa: BLE001
        raise ApiV1Error("INVALID_FILE", f"invalid transactions: {exc}", 422) from exc
    if adapted["transaction_id"].duplicated().any():
        raise ApiV1Error("INVALID_FILE", "transaction_id must be unique within the file", 422)
    records: list[dict] = []
    raw_records: list[dict] = []
    for position, row in enumerate(adapted.to_dict("records")):
        try:
            records.append(Transaction(**row).model_dump())
        except Exception as exc:  # noqa: BLE001
            raise ApiV1Error("INVALID_FILE", f"row {position + 1}: {exc}", 422) from exc
        raw_records.append(_jsonable(row))
    labels = None
    if label_source is not None:
        labels = [None if pd.isna(value) else float(value) for value in label_source.tolist()]
    analysis_id = storage.create_analysis(name, threshold_profile, row_count=len(frame))
    background.add_task(run_analysis_job, analysis_id, records, raw_records, labels, threshold_profile)
    created = storage.get_analysis(analysis_id)
    assert created is not None
    return JSONResponse(status_code=202, content=analysis_to_dict(created, include_summary=False))


@v1_router.get("/analyses")
def list_analyses(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict:
    rows, total = storage.list_analyses(page, page_size)
    return {"items": [analysis_to_dict(row, include_summary=False) for row in rows], "total": total, "page": page, "page_size": page_size}


@v1_router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int) -> dict:
    analysis = storage.get_analysis(analysis_id)
    if analysis is None:
        raise ApiV1Error("ANALYSIS_NOT_FOUND", f"Analysis {analysis_id} does not exist", 404)
    return analysis_to_dict(analysis)


@v1_router.get("/analyses/{analysis_id}/transactions")
def list_transactions(
    analysis_id: int,
    risk_level: str | None = Query(None, pattern="^(low|medium|high|critical)$"),
    decision: str | None = Query(None, pattern="^(allow|manual_review|block)$"),
    q: str | None = Query(None, max_length=128),
    sort: str = Query("risk_score", pattern="^(amount|risk_score|fraud_probability|transaction_time)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    _require_completed(analysis_id)
    rows, total = storage.query_transactions(
        analysis_id, risk_level=risk_level, decision=decision, q=q, sort=sort, order=order, page=page, page_size=page_size
    )
    return {"items": [transaction_to_dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@v1_router.get("/analyses/{analysis_id}/transactions/{transaction_id}")
def get_transaction(analysis_id: int, transaction_id: str) -> dict:
    analysis = _require_completed(analysis_id)
    row = storage.get_transaction(analysis_id, transaction_id)
    if row is None:
        raise ApiV1Error("TRANSACTION_NOT_FOUND", f"Transaction {transaction_id} does not exist in analysis {analysis_id}", 404)
    payload = transaction_to_dict(row)
    payload["analysis_id"] = analysis_id
    payload["threshold_profile"] = analysis.threshold_profile
    payload["raw"] = json.loads(row.raw_json) if row.raw_json else {}
    return payload


EXPORT_COLUMNS = [
    "transaction_id", "user_id", "transaction_time", "amount", "payment_method", "device", "country",
    "fraud_probability", "anomaly", "risk_score", "risk_level", "decision", "reasons",
]


def _export_cell(row: storage.TransactionRow, column: str) -> Any:
    if column == "transaction_time":
        return row.transaction_time.isoformat()
    if column == "reasons":
        return "; ".join(json.loads(row.reasons_json))
    value = getattr(row, column)
    if column == "anomaly":
        return bool(value)
    return value


@v1_router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: int, format: str = Query("csv", pattern="^(csv|xlsx)$")) -> Response:
    analysis = _require_completed(analysis_id)
    stem = Path(analysis.filename or f"analysis_{analysis_id}").stem or f"analysis_{analysis_id}"
    if format == "xlsx":
        buffer = BytesIO()
        frame = pd.DataFrame(
            [{column: _export_cell(row, column) for column in EXPORT_COLUMNS} for row in storage.iter_transactions(analysis_id)],
            columns=EXPORT_COLUMNS,
        )
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="transactions")
        payload = buffer.getvalue()
        return Response(
            content=payload,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}_results.xlsx; filename*=UTF-8''{quote(stem + '_results.xlsx', safe='')}"},
        )

    def generate():
        header = StringIO()
        writer = csv.writer(header)
        writer.writerow(EXPORT_COLUMNS)
        yield header.getvalue()
        for row in storage.iter_transactions(analysis_id):
            line = StringIO()
            writer = csv.writer(line)
            writer.writerow([_export_cell(row, column) for column in EXPORT_COLUMNS])
            yield line.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}_results.csv; filename*=UTF-8''{quote(stem + '_results.csv', safe='')}"},
    )


@v1_router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int) -> Response:
    if not storage.delete_analysis(analysis_id):
        raise ApiV1Error("ANALYSIS_NOT_FOUND", f"Analysis {analysis_id} does not exist", 404)
    return Response(status_code=204)


@v1_router.get("/model/meta")
def model_meta() -> dict:
    def load_json(filename: str) -> dict:
        try:
            return json.loads((ARTIFACT_DIR / filename).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    model = get_model()
    thresholds = load_json("thresholds.json")
    metrics_artifact = load_json("metrics.json")
    evaluation = load_json("evaluation_metrics.json")
    schema = load_json("feature_schema.json")
    features = schema.get("features") or []
    return {
        "model_loaded": bool(model is not None and model.loaded),
        "model_version": metrics_artifact.get("model_version", "untrained"),
        "schema_version": schema.get("schema_version"),
        "feature_count": len(features) or metrics_artifact.get("feature_count"),
        "thresholds": thresholds,
        "metrics": {
            "pr_auc": evaluation.get("pr_auc", metrics_artifact.get("pr_auc_threshold")),
            "roc_auc": evaluation.get("roc_auc", metrics_artifact.get("roc_auc_threshold")),
            "recall": evaluation.get("recall"),
            "precision": evaluation.get("precision"),
        },
    }
