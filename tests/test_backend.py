import csv
import io
import os
import tempfile
import time
from datetime import datetime, timedelta

# The v1 storage layer must stay isolated from the demo database during tests,
# so the path has to be set before backend.app (and its engine) is imported.
_TEST_DB = os.path.join(tempfile.gettempdir(), "fraud_v1_test.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["FRAUD_DB_PATH"] = _TEST_DB

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import storage
from backend.app import app, model
from backend.model_service import FraudModel
from backend.risk_scoring import score
from backend.data_pipeline import adapt_kaggle, build_features

storage.init_db()


def transaction(**overrides):
    value = {"user_id": 1, "age": 35, "amount": 100.0, "payment_method": "Visa", "device": "Mobile", "country": "USA", "transaction_time": datetime(2025, 5, 1, 12).isoformat()}
    value.update(overrides)
    return value


def test_risk_levels_and_bounds():
    result = score(1.0, True, 5000)
    assert result["risk_level"] == "Critical"
    assert 0 <= result["risk_score"] <= 100


def test_unknown_categories_are_supported():
    rows = pd.DataFrame([transaction(payment_method="NewWallet", device="UnknownPhone", country="Narnia")])
    service = FraudModel().fit(pd.DataFrame([transaction(), transaction(user_id=2, amount=4000, country="China")]), [0, 1])
    result = service.predict(rows)
    assert len(result) == 1


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_predict_endpoint():
    response = TestClient(app).post("/predict", json=transaction(amount=4000, country="China"))
    assert response.status_code == 200
    body = response.json()
    assert {"fraud_probability", "anomaly", "risk_score", "risk_level", "reasons"} <= body.keys()


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_batch_endpoint():
    content = "user_id,age,amount,payment_method,device,country,transaction_time\n1,35,100,Visa,Mobile,USA,2025-05-01T12:00:00\n2,70,4500,Crypto,Tablet,China,2025-05-01T02:00:00\n"
    response = TestClient(app).post("/predict/batch", files={"file": ("transactions.csv", content, "text/csv")})
    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_invalid_transaction_is_rejected():
    response = TestClient(app).post("/predict", json=transaction(amount=-1))
    assert response.status_code == 422

def test_kaggle_adapter_hashes_card_and_drops_pii():
    frame = pd.DataFrame([{"trans_num":"abc", "cc_num":"4111111111111111", "trans_date_trans_time":"2019-01-01 00:00:00", "amt":10, "merchant":"m", "category":"c", "lat":1, "long":2, "merch_lat":1.1, "merch_long":2.1, "first":"Secret", "last":"Person", "is_fraud":0}])
    result = adapt_kaggle(frame)
    assert result.account_id.iloc[0] != "4111111111111111"
    assert "first" not in result and "last" not in result


def test_missing_required_numeric_values_are_rejected():
    frame = pd.DataFrame([{"trans_num": "abc", "cc_num": "4111111111111111", "trans_date_trans_time": "2019-01-01 00:00:00", "amt": "not-a-number", "merchant": "m", "category": "c"}])
    with pytest.raises(ValueError, match="amount"):
        adapt_kaggle(frame)


def test_missing_coordinates_do_not_create_nan_features():
    rows = pd.DataFrame([transaction(customer_lat=None, customer_long=None, merchant_lat=None, merchant_long=None)])
    features = build_features(rows)
    assert not features.select_dtypes(include="number").isna().any().any()

def test_history_features_are_prior_only_and_output_order_is_preserved():
    rows = pd.DataFrame([transaction(user_id=1, amount=10, transaction_time="2025-01-01T00:10:00"), transaction(user_id=1, amount=20, transaction_time="2025-01-01T00:00:00")])
    features = build_features(rows)
    assert features.card_txn_count_24h.iloc[0] == 1
    assert features.card_txn_count_24h.iloc[1] == 0

def test_kaggle_batch_endpoint_and_threshold_profile():
    content = "trans_num,cc_num,trans_date_trans_time,amt,merchant,category,lat,long,merch_lat,merch_long,is_fraud\na,123,2019-01-01 00:00:00,10,m,c,36,-81,36.1,-81.1,0\nb,123,2019-01-01 00:10:00,500,m,c,36,-81,36.1,-81.1,1\n"
    response = TestClient(app).post("/predict/batch?threshold_profile=strict", files={"file": ("transactions.csv", content, "text/csv")})
    assert response.status_code == 200
    assert response.json()["predictions"][0]["threshold_profile"] == "strict"


# ---------------------------------------------------------------------------
# API v1 — upload/analysis jobs (plan/API_CONTRACT.md)
# ---------------------------------------------------------------------------

def v1_csv_content(rows: int = 30, with_label: bool = True) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    columns = ["transaction_id", "user_id", "amount", "payment_method", "device", "country", "transaction_time"]
    if with_label:
        columns.append("is_fraud")
    writer.writerow(columns)
    devices, countries, methods = ["Mobile", "Desktop", "Tablet"], ["USA", "UK", "India"], ["Visa", "MasterCard", "Crypto"]
    for index in range(rows):
        row = [
            f"txn_{index:04d}", 100 + index % 5, 50.0 + index * 137.0,
            methods[index % 3], devices[index % 3], countries[index % 3],
            (datetime(2025, 5, 1, 8) + timedelta(minutes=7 * index)).isoformat(),
        ]
        if with_label:
            row.append(1 if index % 25 == 24 else 0)
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def upload_v1(client: TestClient, content: bytes, filename: str = "transactions.csv", profile: str | None = None):
    data = {"threshold_profile": profile} if profile else {}
    return client.post("/api/v1/analyses", files={"file": (filename, content, "text/csv")}, data=data)


def wait_completed(client: TestClient, analysis_id: int, tries: int = 100):
    for _ in range(tries):
        data = client.get(f"/api/v1/analyses/{analysis_id}").json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.05)
    pytest.fail("analysis did not finish in time")


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_upload_csv_completes_with_summary():
    client = TestClient(app)
    created = upload_v1(client, v1_csv_content())
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "queued" and body["summary"] is None
    analysis = wait_completed(client, body["id"])
    assert analysis["status"] == "completed", analysis["error"]
    assert analysis["row_count"] == 30 and analysis["processed_rows"] == 30
    assert analysis["completed_at"] is not None
    summary = analysis["summary"]
    assert summary["total_transactions"] == 30
    assert set(summary["risk_distribution"]) == {"low", "medium", "high", "critical"}
    assert set(summary["decision_distribution"]) == {"allow", "manual_review", "block"}
    assert summary["trends"] and summary["device_breakdown"] and summary["country_breakdown"]
    assert 0 < summary["flagged_rate"] < 1
    assert summary["labeled_fraud_rate"] is not None
    page = client.get(f"/api/v1/analyses/{body['id']}/transactions", params={"page_size": 100}).json()
    assert page["total"] == 30
    assert {item["risk_level"] for item in page["items"]} <= {"low", "medium", "high", "critical"}
    assert all(item["transaction_id"].startswith("txn_") for item in page["items"])


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_upload_xlsx_completes():
    buffer = io.BytesIO()
    pd.DataFrame([
        {"transaction_id": f"x{index}", "user_id": 7, "amount": 100.0 + index * 900,
         "payment_method": "Visa", "device": "Mobile", "country": "USA",
         "transaction_time": datetime(2025, 6, 1, 9) + timedelta(minutes=11 * index)}
        for index in range(6)
    ]).to_excel(buffer, index=False)
    client = TestClient(app)
    response = client.post("/api/v1/analyses", files={"file": ("transactions.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 202
    analysis = wait_completed(client, response.json()["id"])
    assert analysis["status"] == "completed", analysis["error"]
    assert analysis["row_count"] == 6 and analysis["processed_rows"] == 6


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_upload_uses_selected_form_profile():
    client = TestClient(app)
    response = upload_v1(client, v1_csv_content(rows=2), profile="strict")
    assert response.status_code == 202
    analysis = wait_completed(client, response.json()["id"])
    assert analysis["status"] == "completed", analysis["error"]
    assert analysis["threshold_profile"] == "strict"
    invalid = upload_v1(client, v1_csv_content(rows=2), profile="invalid")
    assert invalid.status_code == 422


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_generated_ids_open_distinct_transaction_details():
    client = TestClient(app)
    content = b"user_id,amount,transaction_time\n7,100,2025-05-01T12:00:00\n7,200,2025-05-01T12:01:00\n"
    response = upload_v1(client, content)
    assert response.status_code == 202
    analysis_id = response.json()["id"]
    assert wait_completed(client, analysis_id)["status"] == "completed"
    base = f"/api/v1/analyses/{analysis_id}/transactions"
    items = client.get(base).json()["items"]
    assert len({item["transaction_id"] for item in items}) == 2
    for item in items:
        detail = client.get(f"{base}/{item['transaction_id']}").json()
        assert detail["amount"] == item["amount"]


@pytest.mark.parametrize("ids", [("same", "same"), ("", "valid")])
def test_v1_upload_rejects_ambiguous_transaction_ids(ids):
    client = TestClient(app)
    content = f"transaction_id,amount,transaction_time\n{ids[0]},100,2025-05-01T12:00:00\n{ids[1]},200,2025-05-01T12:01:00\n".encode()
    response = upload_v1(client, content)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FILE"


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_unicode_filename_exports_csv_and_xlsx():
    from urllib.parse import unquote

    client = TestClient(app)
    response = upload_v1(client, v1_csv_content(rows=2), filename='giao_dịch tháng 5.csv')
    analysis_id = response.json()["id"]
    assert wait_completed(client, analysis_id)["status"] == "completed"
    for fmt in ("csv", "xlsx"):
        exported = client.get(f"/api/v1/analyses/{analysis_id}/export", params={"format": fmt})
        assert exported.status_code == 200
        header = exported.headers["content-disposition"]
        assert f'filename=analysis_{analysis_id}_results.{fmt}' in header
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == f'giao_dịch tháng 5_results.{fmt}'
        if fmt == "csv":
            assert len(list(csv.DictReader(io.StringIO(exported.text)))) == 2
        else:
            assert len(pd.read_excel(io.BytesIO(exported.content))) == 2


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_kaggle_csv_goes_through_adapter():
    rows = []
    for index in range(8):
        rows.append({
            "trans_num": f"t{index}", "cc_num": "4111111111111111",
            "trans_date_trans_time": (datetime(2019, 1, 1, 10) + timedelta(minutes=5 * index)).strftime("%Y-%m-%d %H:%M:%S"),
            "amt": 100 + 50 * index, "merchant": "fraud_Kirlin and Sons", "category": "personal_care",
            "lat": 36.0, "long": -81.0, "merch_lat": 36.1, "merch_long": -81.1,
            "is_fraud": 1 if index == 7 else 0,
        })
    buffer = io.StringIO()
    pd.DataFrame(rows).to_csv(buffer, index=False)
    client = TestClient(app)
    response = upload_v1(client, buffer.getvalue().encode("utf-8"), filename="kaggle.csv")
    assert response.status_code == 202
    analysis_id = response.json()["id"]
    analysis = wait_completed(client, analysis_id)
    assert analysis["status"] == "completed", analysis["error"]
    page = client.get(f"/api/v1/analyses/{analysis_id}/transactions", params={"page_size": 100}).json()
    assert {item["transaction_id"] for item in page["items"]} == {f"t{i}" for i in range(8)}


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_transactions_filter_search_sort_pagination():
    client = TestClient(app)
    analysis_id = upload_v1(client, v1_csv_content()).json()["id"]
    wait_completed(client, analysis_id)
    base = f"/api/v1/analyses/{analysis_id}/transactions"
    everything = client.get(base, params={"page_size": 100}).json()
    assert everything["total"] == 30
    critical = client.get(base, params={"risk_level": "critical", "page_size": 100}).json()
    assert all(item["risk_level"] == "critical" for item in critical["items"])
    allowed = client.get(base, params={"decision": "allow", "page_size": 100}).json()
    assert allowed["items"] and all(item["decision"] == "allow" for item in allowed["items"])
    searched = client.get(base, params={"q": "USA", "page_size": 100}).json()
    assert searched["total"] == 10 and all(item["country"] == "USA" for item in searched["items"])
    cheapest = client.get(base, params={"sort": "amount", "order": "asc", "page_size": 3}).json()
    amounts = [item["amount"] for item in cheapest["items"]]
    assert amounts == sorted(amounts)
    page_two = client.get(base, params={"page": 2, "page_size": 5}).json()
    assert page_two["page"] == 2 and len(page_two["items"]) == 5


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_transaction_detail_includes_raw_and_reasons():
    client = TestClient(app)
    analysis_id = upload_v1(client, v1_csv_content()).json()["id"]
    wait_completed(client, analysis_id)
    top = client.get(f"/api/v1/analyses/{analysis_id}/transactions", params={"page_size": 1}).json()["items"][0]
    detail = client.get(f"/api/v1/analyses/{analysis_id}/transactions/{top['transaction_id']}").json()
    assert detail["analysis_id"] == analysis_id and detail["threshold_profile"] == "cost_optimal"
    assert isinstance(detail["reasons"], list) and detail["reasons"]
    assert detail["raw"]["transaction_id"] == top["transaction_id"]
    assert detail["raw"]["country"] == top["country"]
    missing = client.get(f"/api/v1/analyses/{analysis_id}/transactions/txn_9999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "TRANSACTION_NOT_FOUND"


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_export_csv_and_xlsx():
    client = TestClient(app)
    analysis_id = upload_v1(client, v1_csv_content(rows=6)).json()["id"]
    wait_completed(client, analysis_id)
    csv_response = client.get(f"/api/v1/analyses/{analysis_id}/export", params={"format": "csv"})
    assert csv_response.status_code == 200 and "text/csv" in csv_response.headers["content-type"]
    lines = csv_response.text.strip().splitlines()
    assert lines[0].startswith("transaction_id") and len(lines) == 7
    xlsx_response = client.get(f"/api/v1/analyses/{analysis_id}/export", params={"format": "xlsx"})
    assert xlsx_response.status_code == 200
    assert "spreadsheetml" in xlsx_response.headers["content-type"]
    assert xlsx_response.content[:2] == b"PK"
    bad_format = client.get(f"/api/v1/analyses/{analysis_id}/export", params={"format": "json"})
    assert bad_format.status_code == 422 and bad_format.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.skipif(not model.loaded, reason="trained artifact is not available")
def test_v1_delete_analysis_cascades():
    client = TestClient(app)
    analysis_id = upload_v1(client, v1_csv_content(rows=6)).json()["id"]
    wait_completed(client, analysis_id)
    deleted = client.delete(f"/api/v1/analyses/{analysis_id}")
    assert deleted.status_code == 204
    after = client.get(f"/api/v1/analyses/{analysis_id}")
    assert after.status_code == 404 and after.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
    assert client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 404


def test_v1_error_envelopes():
    client = TestClient(app)
    wrong_format = client.post("/api/v1/analyses", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert wrong_format.status_code == 400 and wrong_format.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
    broken = client.post("/api/v1/analyses", files={"file": ("broken.csv", b"not,a,real,csv", "text/csv")})
    assert broken.status_code == 422 and broken.json()["error"]["code"] == "INVALID_FILE"
    missing = client.get("/api/v1/analyses/999999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
    invalid_query = client.get("/api/v1/analyses", params={"page": 0})
    assert invalid_query.status_code == 422 and invalid_query.json()["error"]["code"] == "VALIDATION_ERROR"


def test_v1_transactions_require_completed():
    client = TestClient(app)
    queued_id = storage.create_analysis("pending.csv", "cost_optimal", row_count=5)
    try:
        response = client.get(f"/api/v1/analyses/{queued_id}/transactions")
        assert response.status_code == 409 and response.json()["error"]["code"] == "ANALYSIS_NOT_COMPLETED"
        export = client.get(f"/api/v1/analyses/{queued_id}/export")
        assert export.status_code == 409 and export.json()["error"]["code"] == "ANALYSIS_NOT_COMPLETED"
    finally:
        storage.delete_analysis(queued_id)


def test_stale_jobs_marked_failed_by_sweep():
    stale_id = storage.create_analysis("stale.csv", "balanced", row_count=3)
    try:
        storage.set_status(stale_id, "processing")
        assert storage.mark_stale_jobs_failed() >= 1
        assert storage.get_analysis(stale_id).status == "failed"
        assert "restart" in storage.get_analysis(stale_id).error
    finally:
        storage.delete_analysis(stale_id)


def test_v1_model_meta():
    body = TestClient(app).get("/api/v1/model/meta").json()
    assert body["model_loaded"] is True
    assert set(body["thresholds"]) == {"high_recall", "balanced", "strict", "cost_optimal"}
    assert body["feature_count"] == 34
    assert body["metrics"]["pr_auc"] is not None and body["metrics"]["recall"] is not None


def test_legacy_error_shape_unchanged():
    response = TestClient(app).post("/predict", json=transaction(amount=-1))
    assert response.status_code == 422
    assert "detail" in response.json() and "error" not in response.json()
