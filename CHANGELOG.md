# Tổng hợp những gì đã thực hiện

Dưới đây là tóm tắt các công việc chính đã được triển khai trong dự án **AI-Powered Fraud Detection & Risk Scoring System**:

## 0. MVP web app đầy đủ (2026-10-04)
- **API v1 (`backend/api_v1.py`)**: 8 endpoint theo `plan/API_CONTRACT.md` — upload file tạo job phân tích (202), lịch sử, trạng thái + summary, bảng giao dịch (filter/search/sort/phân trang), chi tiết "Why?", export CSV/XLSX, xóa phân tích, model meta. Lỗi trả envelope thống nhất `{"error": {code, message}}`.
- **Storage (`backend/storage.py`)**: SQLite qua SQLAlchemy 2 (`data/app.db`, override bằng `FRAUD_DB_PATH`), 2 bảng `analyses`/`transactions`, sweep job dở dang khi restart.
- **Job phân tích bất đồng bộ**: mỗi analysis dùng `FeatureState()` riêng, chấm theo chunk 5.000 dòng theo thứ tự thời gian, summary (trends theo ngày, top-10 device/country, phân bố risk/decision, labeled fraud rate) tính 1 lần khi hoàn tất.
- **Frontend (`frontend/`)**: React 18 + Vite + TypeScript + Tailwind v4 + TanStack Query + Recharts. 5 trang: Upload (drag-drop, validate client-side), Lịch sử, Dashboard (5 StatCards, donut risk, bar decision, line trends, top-10 device/country, export), Danh sách giao dịch (filter/search debounce/sort/phân trang đồng bộ URL), Chi tiết "Why?" (risk /100, badges, reasons tiếng Việt, thuộc tính đầy đủ).
- **Khác**: CORS qua `FRAUD_CORS_ORIGINS`, proxy dev `/api` → cổng 8000, openpyxl cho `.xlsx`, 11 test v1 + 14 test FE (vitest) đều pass, smoke E2E thật với file 300 dòng.

## 1. Cấu trúc Backend (FastAPI)
- **`backend/app.py`**: Xây dựng API endpoint chính sử dụng FastAPI, bao gồm các route `/predict` (dự đoán giao dịch đơn) và `/predict/batch` (dự đoán hàng loạt qua file CSV).
- **`backend/data_pipeline.py`**: Triển khai quy trình tiền xử lý dữ liệu (preprocessing) và kỹ thuật đặc trưng (feature engineering). Hỗ trợ tự động điều chỉnh các cột dữ liệu từ Kaggle.
- **`backend/model_service.py`**: Quản lý mô hình học máy bao gồm **Random Forest** (phân loại gian lận) và **Isolation Forest** (phát hiện dị thường).
- **`backend/risk_scoring.py`**: Triển khai logic tính điểm rủi ro (risk score), phân loại mức độ rủi ro (low/medium/high) và quyết định xử lý (allow/review/block).
- **`backend/schemas.py`**: Định nghĩa các mô hình dữ liệu Pydantic cho request và response.
- **`backend/artifacts/`**: Lưu trữ các mô hình đã huấn luyện, ngưỡng quyết định và các metric dưới dạng JSON.

## 2. Công cụ hỗ trợ (CLI Scripts)
- **`scripts/train_model.py`**: Script để huấn luyện mô hình từ dữ liệu thô, hỗ trợ tham số `--max-rows` để chạy nhanh.
- **`scripts/generate_training_data.py`**: Tạo dữ liệu huấn luyện từ các file CSV gốc.
- **`scripts/evaluate_model.py`**: Đánh giá hiệu suất mô hình qua các chỉ số phân loại.
- **`scripts/show_report.py`**: Hiển thị báo cáo chi tiết về kết quả huấn luyện.
- **`scripts/benchmark_models.py`**: So sánh hiệu năng giữa các mô hình ứng viên.

## 3. Kiểm thử (Testing)
- **`tests/test_backend.py`**: Viết bộ kiểm thử (Pytest) để đảm bảo API và logic hoạt động ổn định.

## 4. Tích hợp và Triển khai
- Tích hợp **Power BI Dashboard** để trực quan hóa dữ liệu gian lận và xu hướng giao dịch.
- Cung cấp các file batch script (`run_all.bat`, `run_tuned.bat`) để chạy toàn bộ quy trình tự động hóa trên Windows.
- Triển khai logic "Stateful" cho các đặc trưng velocity/history.
- Xây dựng hệ thống **Threshold Profiles** (high_recall, balanced, strict, cost_optimal) để tùy chỉnh độ nhạy của rủi ro.
