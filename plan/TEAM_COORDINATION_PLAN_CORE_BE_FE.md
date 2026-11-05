# Kế hoạch phối hợp Core, Backend và Frontend

> **Phiên bản này thay thế** `TEAM_COORDINATION_PLAN_CORE_BE_FE.md` ở gốc repo.
> Hợp đồng API chốt: **`plan/API_CONTRACT.md`** — mọi tranh chấp về endpoint/field nhìn vào file đó trước tiên.
> Kế hoạch chi tiết từng bên: `plan/BE.md`, `plan/FE.md`.

## 1. Kiến trúc phối hợp

Năm lớp theo KLTN: Presentation (FE) → Application/API (BE) → Data Processing (Core) → ML & Risk Engine (Core) → Data Storage (BE/SQLite).

```text
FE (React+Vite+TS)  ──HTTP /api/v1──▶  BE (FastAPI)  ──▶  Core (pipeline + model)
                                           │
                                           ▼
                                      SQLite data/app.db  (analyses, transactions)
```

- Frontend chỉ giao tiếp qua `/api/v1`; không gọi trực tiếp core, không tự tính điểm số.
- Backend điều phối: nhận file, quản lý job async, persist kết quả, trả summary/detail theo contract.
- Core sở hữu xử lý dữ liệu + model + artifact; BE chỉ **gọi**, không sửa logic core.

## 2. Phân công

- **Core/ML:** dữ liệu, feature, model, threshold, artifact. Không đổi `FEATURE_COLUMNS`/artifact khi chưa báo BE.
- **Backend:** FastAPI, `/api/v1` router, async job, SQLite storage, error envelope, integration tests.
- **Frontend:** UI 5 màn hình (Upload, History, Dashboard, Transactions, Detail), API client, types TS, mock khi BE chưa xong.

Mỗi bên làm branch riêng, merge qua Pull Request.

## 3. Ownership file

| Nhóm | Sở hữu (được sửa tự do) | Chỉ đọc |
|---|---|---|
| Core/ML | `backend/data_pipeline.py`, `backend/model_service.py`, `backend/risk_scoring.py`, `scripts/`, `backend/artifacts/` | `plan/*` |
| Backend | `backend/app.py`, `backend/api_v1.py` (mới), `backend/storage.py` (mới), `backend/schemas.py`, `tests/`, `requirements.txt`, `.gitignore` | `backend/artifacts/` |
| Frontend | `frontend/**` | `plan/API_CONTRACT.md` |
| Dùng chung | `plan/API_CONTRACT.md`, `plan/BE.md`, `plan/FE.md`, `README.md`, `CHANGELOG.md` | — |

File dùng chung phải thống nhất owner của PR trước khi merge.

## 4. API contract (tóm tắt — chi tiết xem `plan/API_CONTRACT.md`)

- **v1 (FE dùng):** `POST /api/v1/analyses` (upload async) → poll `GET /api/v1/analyses/{id}` → `GET .../transactions` (list/filter/search) → `GET .../transactions/{tid}` (detail + Why?) → `GET .../export`; thêm `GET /api/v1/analyses` (history), `DELETE /api/v1/analyses/{id}`, `GET /api/v1/model/meta`.
- **Legacy (đóng băng, FE không dùng):** `GET /health`, `POST /predict`, `POST /predict/batch`.
- Response do BE tính: `fraud_probability`, `anomaly`, `risk_score`, `risk_level` (v1: lowercase `low|medium|high|critical`), `decision`, `reasons`, `threshold_profile`.
- Lỗi v1: envelope `{"error": {"code", "message"}}`; legacy giữ `{"detail"}` mặc định FastAPI.

## 5. Quy tắc tích hợp

- Contract-first: đổi contract trước, đổi code sau; PR chạm contract phải cập nhật `plan/API_CONTRACT.md`.
- BE không đổi/xóa field đã công bố; field mới luôn optional. FE bỏ qua field lạ, fallback khi thiếu.
- Core báo trước khi đổi feature schema hay thay artifact; BE phải load lại được artifact (đã có check schema khi boot).
- Job async: mỗi analysis dùng `FeatureState()` riêng — không đụng `live_state` của legacy `/predict`.
- Test: BE dùng model thật + fixture CSV nhỏ; FE dùng mock response đúng JSON mẫu trong contract khi BE chưa xong.
- Không commit: dữ liệu Kaggle thô, PII, `data/*.db`, secret, file tạm.

## 6. Definition of done

- **Core:** artifact load được, schema khớp code, metric/threshold lưu trong `backend/artifacts/*.json`, test pass.
- **Backend:** 8 endpoint v1 đúng contract, job async ổn định (stale job bị đánh dấu failed khi restart), legacy không đổi, integration tests pass.
- **Frontend:** 5 pages, polling hoạt động, đủ loading/empty/error states, hiển thị đúng risk_level/decision/reasons (map tiếng Việt ở FE), lint/test/build pass.
- **PR:** cập nhật tài liệu/changelog, ghi rõ dependency, chạy đúng bộ test của phạm vi.

## 7. Lệnh kiểm tra

```text
# Backend
python -m py_compile backend/*.py
python -m pytest -q
python -m uvicorn backend.app:app --reload

# Frontend
cd frontend
npm run lint
npx vitest run
npm run build

# Smoke E2E
# 1. Chạy BE (lệnh trên)  2. Chạy FE: npm run dev  3. Upload fraud_dashboard_dataset.csv → dashboard → detail → export
```
