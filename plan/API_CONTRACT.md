# API CONTRACT — Ràng buộc Backend ↔ Frontend

> **File này là hợp đồng duy nhất** giữa BE và FE. Mọi thay đổi phải cập nhật here trước, code sau.
> Phiên bản: `v1.0.0-draft` — chốt trước khi code Phase 2 (BE) và Phase 3 (FE).

---

## 1. Quy ước chung

| Mục | Quy ước |
|---|---|
| Base URL | `http://localhost:8000` (dev). FE dev server proxy `/api` → BE qua `vite.config.ts` |
| Content type | Request/response JSON (UTF-8), trừ upload (`multipart/form-data`) và export (file stream) |
| Timestamp | ISO 8601, ví dụ `2024-03-15T10:30:00` |
| Pagination | `page` bắt đầu từ 1, `page_size` mặc định 20, tối đa 100. Response luôn dạng `{items, total, page, page_size}` |
| Danh sách hợp lệ | FE chỉ được gọi các endpoint trong file này. FE **không tự tính** risk score/threshold — mọi điểm số do BE trả |
| Unknown fields | FE phải bỏ qua field lạ; field mới trên BE luôn thêm dạng optional |
| OpenAPI | BE expose `/docs` — nguồn truth khi sinh types, nhưng API_CONTRACT.md là bản chốt |

### Quy tắc versioning

- `/api/v1`: chỉ được **thêm field optional**, không rename, không xóa field đã công bố.
- Breaking change → mở `/api/v2`, `/api/v1` sống tiếp tối thiểu đến hết demo KLTN.
- Legacy endpoints (Phần 3) đóng băng: sửa lỗi thì được, đổi shape thì không.

---

## 2. Enums & hằng số dùng chung

> ⚠️ **Lưu ý quan trọng:** core hiện trả `risk_level` viết hoa (`"Critical"`). Ở **tầng `/api/v1`, BE chuẩn hóa về lowercase** trước khi trả FE. Legacy giữ nguyên viết hoa.

| Enum | Giá trị | Ghi chú |
|---|---|---|
| `risk_level` (v1) | `low` \| `medium` \| `high` \| `critical` | Ngưỡng: `>=80 critical`, `>=60 high`, `>=30 medium`, `<30 low` (theo `risk_scoring.py`) |
| `risk_level` (legacy) | `Low` \| `Medium` \| `High` \| `Critical` | Chỉ xuất hiện ở endpoint legacy Phần 3 |
| `decision` | `allow` \| `manual_review` \| `block` | `block` chỉ xuất hiện khi `threshold_profile=strict` |
| `job_status` | `queued` \| `processing` \| `completed` \| `failed` | Vòng đời analysis job |
| `threshold_profile` | `high_recall` \| `balanced` \| `strict` \| `cost_optimal` | Mặc định `cost_optimal` |
| `sort` (transactions) | `amount` \| `risk_score` \| `fraud_probability` \| `transaction_time` | Kèm `order=asc\|desc`, mặc định `risk_score` + `desc` |
| `reasons[]` | `high_model_probability` \| `anomalous_transaction_pattern` \| `high_transaction_amount` | `high_transaction_amount` khi `amount >= 3000` (hardcode hiện tại, BE có thể configurize sau — vẫn là string enum này) |

---

## 3. Legacy endpoints (đóng băng — hiện trạng đã có)

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/health` | → `{status, model_loaded}` |
| POST | `/predict` | Body: Transaction JSON. Query: `threshold_profile`. Response `risk_level` **viết hoa**, lỗi dạng FastAPI mặc định `{"detail": "..."}` |
| POST | `/predict/batch` | Upload CSV thôi (chưa hỗ trợ Excel), trả `{count, predictions[]}` |

FE **không dùng** các endpoint này trong sản phẩm; chúng chỉ phục vụ test tích hợp và tương thích ngược.

---

## 4. v1 Endpoints

### 4.1. `POST /api/v1/analyses` — Upload & tạo job phân tích

Request `multipart/form-data`:

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `file` | file | ✓ | `.csv` hoặc `.xlsx`, ≤ 20MB, ≤ 100.000 dòng |
| `threshold_profile` | string | ✗ | Mặc định `cost_optimal` |

Response `202 Accepted` — Analysis object khi `status=queued`:

```json
{
  "id": 1,
  "filename": "transactions.csv",
  "status": "queued",
  "row_count": null,
  "processed_rows": 0,
  "threshold_profile": "balanced",
  "error": null,
  "summary": null,
  "created_at": "2026-09-18T10:00:00",
  "completed_at": null
}
```

Lỗi: `UNSUPPORTED_FORMAT` (400), `FILE_TOO_LARGE` (413), `ROW_LIMIT_EXCEEDED` (413), `INVALID_FILE` (422), `MODEL_NOT_LOADED` (503).

> File upload **không** giữ nguyên trên server sau khi xử lý xong; kết quả nằm trong DB.

### 4.2. `GET /api/v1/analyses` — Lịch sử phân tích

Query: `page`, `page_size`.

```json
{
  "items": [ { "id": 2, "filename": "kaggle_test.xlsx", "status": "completed", "...": "..." } ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

Sắp xếp mặc định `created_at` giảm dần. Item bên trong dùng đúng Analysis object ở 4.1 (có thể bỏ `summary` cho nhẹ — BE quyết định, FE phải xử lý được cả hai).

### 4.3. `GET /api/v1/analyses/{id}` — Trạng thái job + Dashboard summary

**Endpoint duy nhất FE dùng để polling.** Khi `status` là `queued|processing|failed` → `summary: null`, `error` có message nếu `failed`. Khi `completed` → `summary` đầy đủ:

```json
{
  "id": 1,
  "status": "completed",
  "row_count": 10000,
  "processed_rows": 10000,
  "summary": {
    "total_transactions": 10000,
    "flagged_transactions": 342,
    "flagged_rate": 0.0342,
    "labeled_fraud_rate": null,
    "fraud_probability_avg": 0.071,
    "risk_score_avg": 12.4,
    "amount_total": 1234567.89,
    "risk_distribution": { "low": 8123, "medium": 1211, "high": 512, "critical": 154 },
    "decision_distribution": { "allow": 9658, "manual_review": 300, "block": 42 },
    "trends": [
      { "date": "2024-03-01", "transactions": 320, "flagged": 11, "avg_risk_score": 10.2 }
    ],
    "device_breakdown": [
      { "device": "mobile", "transactions": 5100, "flagged": 200, "fraud_probability_avg": 0.08 }
    ],
    "country_breakdown": [
      { "country": "US", "transactions": 4300, "flagged": 180, "fraud_probability_avg": 0.09 }
    ]
  }
}
```

- `flagged_rate` = tỷ lệ giao dịch có `decision != "allow"`.
- `labeled_fraud_rate` = tỷ lệ `is_fraud=1` nếu file upload có cột nhãn, ngược lại `null`. FE hiển thị "—" khi null.
- `trends` group theo ngày (`transaction_time`), `device_breakdown`/`country_breakdown` lấy top 10.

Lỗi: `ANALYSIS_NOT_FOUND` (404).

### 4.4. `GET /api/v1/analyses/{id}/transactions` — Bảng giao dịch

Query:

| Param | Kiểu | Mặc định |
|---|---|---|
| `page`, `page_size` | int | 1 / 20 |
| `risk_level` | enum §2 | — (lọc) |
| `decision` | enum §2 | — (lọc) |
| `q` | string | — (search `transaction_id`, `user_id`, `country`, `device`) |
| `sort` | enum §2 | `risk_score` |
| `order` | `asc` \| `desc` | `desc` |

```json
{
  "items": [
    {
      "transaction_id": "txn_001",
      "user_id": 100,
      "transaction_time": "2024-03-15T10:30:00",
      "amount": 1200.5,
      "payment_method": "credit",
      "device": "mobile",
      "country": "US",
      "fraud_probability": 0.87,
      "anomaly": true,
      "risk_score": 87.0,
      "risk_level": "critical",
      "decision": "manual_review",
      "reasons": ["high_model_probability", "anomalous_transaction_pattern"]
    }
  ],
  "total": 10000,
  "page": 1,
  "page_size": 20
}
```

Lỗi: `ANALYSIS_NOT_FOUND` (404), `ANALYSIS_NOT_COMPLETED` (409).

### 4.5. `GET /api/v1/analyses/{id}/transactions/{transaction_id}` — Chi tiết ("Why?")

Trả Transaction object như 4.4 **kèm object `raw`** chứa đủ field gốc của dòng upload (các cột optional như `merchant_category`, `customer_city`, `is_fraud`... nếu có, đã sanitize NaN→null) + `analysis_id`, `threshold_profile`. FE render màn hình detail: Risk score/100, level, decision, và mục **Why?** liệt kê `reasons` (map mã → câu tiếng Việt ở FE).

Lỗi: `ANALYSIS_NOT_FOUND` (404), `TRANSACTION_NOT_FOUND` (404), `ANALYSIS_NOT_COMPLETED` (409).

### 4.6. `GET /api/v1/analyses/{id}/export` — Xuất kết quả

Query: `format=csv|xlsx` (mặc định `csv`). Response `200` là file stream kèm `Content-Disposition`. Chỉ export khi `status=completed`.

Lỗi: `ANALYSIS_NOT_FOUND` (404), `ANALYSIS_NOT_COMPLETED` (409), `UNSUPPORTED_FORMAT` (400).

### 4.7. `DELETE /api/v1/analyses/{id}` — Xóa phân tích

Xóa analysis + toàn bộ transactions con. Response `204 No Content`. Lỗi: `ANALYSIS_NOT_FOUND` (404).

### 4.8. `GET /api/v1/model/meta` — Thông tin model

```json
{
  "model_loaded": true,
  "model_version": "kaggle-v5",
  "schema_version": 2,
  "feature_count": 34,
  "thresholds": {
    "high_recall": 0.072,
    "balanced": 0.0048,
    "strict": 0.010,
    "cost_optimal": 0.0246
  },
  "metrics": {
    "pr_auc": 0.96,
    "roc_auc": 0.998,
    "recall": 0.72,
    "precision": 0.80
  }
}
```

Giá trị đọc từ `backend/artifacts/*.json` (`thresholds.json`, `metrics.json`, `evaluation_metrics.json`, `feature_schema.json`). `metrics` gồm `pr_auc`/`roc_auc`/`recall`/`precision` từ `evaluation_metrics.json` (fallback `metrics.json`). Khi `model_loaded=false` vẫn trả 200 để FE hiển thị cảnh báo.

---

## 5. Error envelope (chỉ áp dụng `/api/v1`)

Mọi lỗi 4xx/5xx của v1 trả thống nhất:

```json
{
  "error": {
    "code": "ANALYSIS_NOT_FOUND",
    "message": "Analysis 99 does not exist"
  }
}
```

| Code | HTTP | Khi nào |
|---|---|---|
| `UNSUPPORTED_FORMAT` | 400 | File không phải `.csv`/`.xlsx`, hoặc `format` export sai |
| `FILE_TOO_LARGE` | 413 | File > 20MB |
| `ROW_LIMIT_EXCEEDED` | 413 | > 100.000 dòng |
| `INVALID_FILE` | 422 | Parse lỗi, CSV rỗng, thiếu cột bắt buộc |
| `VALIDATION_ERROR` | 422 | Query/body sai kiểu |
| `ANALYSIS_NOT_FOUND` | 404 | ID không tồn tại |
| `TRANSACTION_NOT_FOUND` | 404 | transaction_id không thuộc analysis |
| `ANALYSIS_NOT_COMPLETED` | 409 | Đọc transactions/export khi job chưa xong |
| `MODEL_NOT_LOADED` | 503 | Artifact chưa sẵn sàng |

Legacy endpoints giữ nguyên dạng lỗi mặc định của FastAPI (`{"detail": ...}`).

---

## 6. Input CSV/Excel schema

**Cột bắt buộc** (thiếu → `INVALID_FILE`):

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `amount` | float > 0 | |
| `transaction_time` | datetime | ISO hoặc định dạng parse được bởi pandas |

**Cột tùy chọn** (thiếu sẽ được default như `schemas.py`): `user_id`, `age`, `payment_method`, `device`, `country`, `transaction_id`, `account_id`, `merchant_id`, `merchant_category`, `customer_lat/long`, `merchant_lat/long`, `city`, `state`.

**Cột nhãn** (không đưa vào feature, chỉ dùng thống kê): `is_fraud`.

**Mapping Kaggle adapter** (đã có sẵn `adapt_kaggle`, tự nhận diện qua cột `trans_num`/`cc_num`): `trans_num→transaction_id`, `cc_num→account_id`, `trans_date_trans_time→transaction_time`, `amt→amount`, `merchant→merchant_id`, `category→merchant_category`, `lat/long→customer_lat/long`, `merch_lat/merch_long→merchant_lat/long`.

---

## 7. Ràng buộc hai bên

1. **BE:** không đổi/xóa field trong file này mà không cập nhật contract + báo FE; field mới luôn optional.
2. **FE:** luôn render được khi thiếu field optional (fallback `—`/`0`); không hardcode ngưỡng risk; mã `reasons` map label ở FE, BE chỉ trả mã.
3. **Test chốt hạ:** BE phải có integration test cho từng endpoint ở §4; FE mock response đúng mẫu JSON trong file này khi BE chưa xong.
4. Mọi PR chạm contract phải kèm thay đổi trong file này (không có contract-first thì không merge).
