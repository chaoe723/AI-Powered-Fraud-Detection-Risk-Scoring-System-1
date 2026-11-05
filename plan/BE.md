# BACKEND PLAN — Fraud Detection & Risk Scoring

> Bám sát `plan/API_CONTRACT.md` (bản chốt). Core (lớp 3 + 4) **đã xong**: pipeline, Random Forest + Isolation Forest, risk scoring, artifact đã train.
> Việc còn lại là **lớp 2 (API v1 + async job)** và **lớp 5 (Data Storage)**.

---

## Hiện trạng đã có (không đụng vào)

- `backend/data_pipeline.py` — preprocessing, feature engineering, `adapt_kaggle`, `FeatureState`
- `backend/model_service.py` — `FraudModel` (`predict(frame, state=...)`), load artifact từ `backend/artifacts/`
- `backend/risk_scoring.py` — risk score/level/decision
- `backend/schemas.py` — Pydantic models
- `backend/app.py` — legacy: `GET /health`, `POST /predict`, `POST /predict/batch`
- `tests/test_backend.py` — pytest hiện tại

---

## Phase BE-1: Dependencies + cấu hình

- [ ] `requirements.txt` thêm: `sqlalchemy>=2,<3`, `openpyxl>=3.1,<4` (đọc `.xlsx`), `alembic` **không cần** (SQLite create_all đủ cho KLTN)
- [ ] `.gitignore` thêm `data/*.db` (DB đặt ở `data/app.db`, thư mục `data/` đã có sẵn)
- [ ] CORS middleware trong `app.py`, origin đọc từ env `FRAUD_CORS_ORIGINS` (mặc định `http://localhost:5173`)

## Phase BE-2: Storage layer (lớp 5)

File mới **`backend/storage.py`**:

- Engine SQLite tại `data/app.db`, `check_same_thread=False`, `create_all` khi startup.
- 2 bảng:

```text
analyses
  id              PK autoincrement
  filename        str
  status          str  (queued|processing|completed|failed)
  row_count       int|null      (số dòng đọc được từ file)
  processed_rows  int  (số dòng score thành công)
  threshold_profile str
  error           str|null
  summary_json    text|null     (summary §4.3 của contract, tính 1 lần khi completed)
  created_at      datetime
  completed_at    datetime|null

transactions
  id               PK autoincrement
  analysis_id      FK -> analyses.id, index (analysis_id, risk_level)
  transaction_id   str|null
  user_id          int
  transaction_time datetime
  amount           float
  payment_method   str
  device           str
  country          str
  fraud_probability float
  anomaly          bool
  risk_score       float
  risk_level       str   (lowercase chuẩn v1)
  decision         str
  reasons_json     text
  raw_json         text  (cột optional gốc của dòng upload, phục vụ detail §4.5)
```

Helper functions: `create_analysis`, `set_status`, `bulk_insert_transactions`, `get_analysis`, `list_analyses`, `query_transactions(analysis_id, filters...)`, `get_transaction`, `delete_analysis`, `save_summary`.

## Phase BE-3: API v1 router

File mới **`backend/api_v1.py`** (`APIRouter`), mount vào `app.py` — 8 endpoint đúng §4 contract:

- [ ] `POST /analyses` — validate size (20MB)/format/row cap (100k); tạo row `queued`; đọc file bằng `pandas.read_csv`/`read_excel` + `adapt_kaggle` nếu Kaggle; lưu `row_count`; đẩy background job; trả 202
- [ ] `GET /analyses` — phân trang, `created_at` desc
- [ ] `GET /analyses/{id}` — status + summary (polling endpoint)
- [ ] `GET /analyses/{id}/transactions` — filter `risk_level`/`decision`, search `q`, `sort`/`order`, phân trang; 409 nếu chưa completed
- [ ] `GET /analyses/{id}/transactions/{transaction_id}` — detail từ `raw_json` + kết quả; "Why?" = `reasons`
- [ ] `GET /analyses/{id}/export?format=csv|xlsx` — stream file từ DB
- [ ] `DELETE /analyses/{id}` — cascade, 204
- [ ] `GET /model/meta` — đọc `backend/artifacts/*.json`

Chuẩn hóa & serializer:

- **Convert `risk_level` viết hoa → lowercase** ở tầng v1 (`"Critical"→"critical"`); legacy giữ nguyên.
- Custom exception handler: mọi lỗi v1 trả envelope `{"error": {"code", "message"}}` §5. Legacy không đổi (`{"detail"}`).
- Giữ `labeled_fraud_rate=null` khi file không có cột `is_fraud`.

## Phase BE-4: Async job + hardening

- [ ] Background job = hàm **sync def** (FastAPI chạy trong threadpool, không block event loop): `queued → processing → completed|failed`, ghi `error` khi fail.
- [ ] **Mỗi analysis dùng `FeatureState()` riêng** (offline scoring) — KHÔNG dùng `live_state` chung của `/predict` để tránh race và làm bẩn velocity online.
- [ ] Batch score theo chunk 5.000 dòng để giới hạn RAM; `processed_rows` cập nhật định kỳ.
- [ ] Summary tính 1 lần khi completed → `summary_json` (trends group theo ngày, top-10 device/country, distributions).
- [ ] Export sinh từ DB (không đọc lại file gốc).
- [ ] Logging: request path, analysis_id, latency, row count — **không log PII**.

## Phase BE-5: Tests

Mở rộng `tests/test_backend.py` (fixture: model thật đã có trong repo + CSV nhỏ tạo tại cmd):

- [ ] Upload CSV happy path → poll `GET /{id}` đến `completed` → có summary đúng shape contract
- [ ] Upload `.xlsx` (tạo bằng openpyxl trong test)
- [ ] Kaggle-format CSV đi qua `adapt_kaggle`
- [ ] Transactions: filter `risk_level`, `decision`, search `q`, sort, phân trang
- [ ] Detail trả đủ `raw_json` fields + `reasons`
- [ ] Export csv + xlsx, kiểm content-type
- [ ] DELETE → 204, GET sau đó → 404
- [ ] Lỗi: format sai 400, file giả mạo 422, analysis 404, transactions trước khi hoàn tất 409
- [ ] Regression: legacy `/health`, `/predict`, `/predict/batch` **không đổi hành vi** (risk_level vẫn viết hoa)
- [ ] v1 trả `risk_level` lowercase toàn bộ

---

## Lệnh kiểm tra

```text
python -m py_compile backend/*.py
python -m pytest -q
python -m uvicorn backend.app:app --reload
```

## Definition of Done (BE)

- 8 endpoint v1 hoạt động đúng contract §4, error envelope §5
- Job async: restart server giữa chừng không crash (job `processing` cũ bị đánh dấu `failed` khi startup — stale job sweep)
- Legacy không đổi
- Toàn bộ test pass
- `plan/API_CONTRACT.md` khớp 100% với code thực tế
