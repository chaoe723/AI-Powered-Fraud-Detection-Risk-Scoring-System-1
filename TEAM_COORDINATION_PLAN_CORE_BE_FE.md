# Kế hoạch phối hợp Core, Backend và Frontend

## 1. Kiến trúc phối hợp

Hệ thống được tích hợp theo năm lớp: Presentation, Application/API, Data Processing, ML & Risk Engine và Data Storage. Frontend chỉ giao tiếp qua API; Backend điều phối; Core sở hữu xử lý dữ liệu và mô hình.

## 2. Phân công

- **Core/ML:** dữ liệu, feature, model, threshold và artifact.
- **Backend:** FastAPI, validation, state, API contract và integration.
- **Frontend:** UI, dashboard, API client và hiển thị kết quả.

Mỗi nhóm làm trên branch riêng và merge qua Pull Request.

## 3. Ownership file

| Nhóm | Phạm vi chính |
|---|---|
| Core/ML | `backend/data_pipeline.py`, `backend/model_service.py`, `backend/risk_scoring.py`, `scripts/`, artifact |
| Backend | `backend/app.py`, `backend/schemas.py`, API/integration tests |
| Frontend | `frontend/`, mock data và frontend tests |

README, requirements, changelog, schema và feature schema là file dùng chung; phải thống nhất owner trước khi sửa.

## 4. API contract

Endpoints tối thiểu: `GET /health`, `POST /predict`, `POST /predict/batch`.

Request gồm các trường giao dịch như `user_id`, `age`, `amount`, `payment_method`, `device`, `country`, `transaction_time`.

Response do Backend tính và gồm `fraud_probability`, `anomaly`, `risk_score`, `risk_level`, `reasons`, `decision`, `threshold_profile`. Frontend không tự tính lại điểm hoặc threshold.

## 5. Quy tắc tích hợp

- Backend không đổi/xóa field đã công bố nếu chưa cập nhật contract.
- Field mới nên là optional; Frontend bỏ qua field lạ và có fallback khi thiếu.
- Core thông báo trước khi thay đổi feature schema hoặc artifact.
- Backend dùng mock model/fixture nhỏ cho test; Frontend dùng mock response khi API chưa sẵn sàng.
- Không commit dữ liệu Kaggle thô, PII, secret hoặc file tạm.

## 6. Definition of done

- Core: artifact load được, schema khớp code, metric/threshold được lưu, test và quick validation pass.
- Backend: health/predict/batch hoạt động, lỗi chuẩn hóa, integration tests pass.
- Frontend: kết nối API, loading/empty/error state, hiển thị đúng risk level/decision/reasons.
- PR: cập nhật tài liệu/changelog, ghi dependency và chạy test phù hợp.

## 7. Lệnh kiểm tra

```text
python -m py_compile backend/*.py scripts/*.py
python -m pytest -q
.un_tuned.bat quick

cd frontend
npm run lint
npm test
npm run build
```
