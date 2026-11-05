# Kế hoạch phát triển các giai đoạn tiếp theo

## Mục tiêu

Chuyển prototype thành hệ thống web năm lớp có thể upload dữ liệu, phân tích giao dịch, hiển thị dashboard và lưu lịch sử kết quả.

## Định hướng theo kiến trúc KLTN

Presentation → Application/API → Data Processing → ML & Risk Engine → Data Storage.

## Phase 0 — Chuẩn hóa baseline

- Cập nhật README, version dataset/artifact và thời điểm train.
- Lưu baseline metric, lệnh quick validation và full evaluation.
- Hoàn thiện tài liệu lý thuyết, tiền xử lý và quy trình chạy lại.
- Bảo đảm quick validation và test hiện tại chạy thành công.

## Phase 1 — Data quality

- Tạo data contract dạng Markdown/JSON.
- Kiểm tra cột bắt buộc, kiểu dữ liệu, miền giá trị và missing rate.
- Phát hiện duplicate theo `transaction_id` và khóa nghiệp vụ.
- Kiểm tra timestamp lỗi, giao dịch tương lai và thứ tự thời gian.
- Báo cáo số dòng bị loại, lý do và tỷ lệ ảnh hưởng.
- Quy định xử lý outlier `amount`; không xóa fraud chỉ vì số tiền lớn.
- Bổ sung test cho missing, duplicate, invalid timestamp và invalid amount.

## Phase 2 — Feature engineering

- Đưa `device`, `country`, `payment_method` vào feature khi dữ liệu đủ tin cậy.
- Chuẩn hóa tên `card_*`/`account_*` và khóa history.
- Bổ sung feature failed-authentication nếu có nguồn dữ liệu.
- Kiểm tra missing coordinate, temporal leakage và state continuity.
- Tạo feature dictionary và ablation report.

## Phase 3 — Model và đánh giá

- Tuning bằng validation theo thời gian.
- Đánh giá calibration bằng Brier score, log loss và reliability curve.
- Đánh giá threshold theo fraud rate, review capacity và expected cost.
- Đối chiếu Logistic Regression (Fraud Probability) với Isolation Forest (Anomaly Score).
- Báo cáo precision, recall, F1/F2, PR-AUC, FDR và segment performance.
- Không dùng final test để chọn model hoặc threshold.

## Phase 4 — API hardening

- Chuẩn hóa JSON/CSV error response.
- Giới hạn kích thước file và số dòng batch.
- Xử lý CSV rỗng, thiếu/thừa cột và encoding khác nhau.
- Thêm endpoint model metadata/threshold.
- Bảo đảm batch giữ thứ tự input.
- Tách online state khỏi artifact, thêm reset state có kiểm soát.
- Logging request id, latency, row count và lỗi; không ghi PII.

## Phase 5 — Stateful production

- Snapshot/restore cho demo; Redis hoặc database cho production.
- Định nghĩa ordering, idempotency, giao dịch đến trễ và atomic update.
- Quy định retention các cửa sổ lịch sử.
- Test restart, duplicate request, out-of-order event và nhiều worker.

## Phase 6 — Explainability

- Trả về feature quan trọng/reason code cho analyst.
- Tài liệu riêng cho `risk_score`, `fraud_probability`, `decision`.
- Đánh giá feature importance và SHAP khi cần.
- Ghi audit record kèm threshold profile.

## Phase 7 — Dashboard, monitoring và triển khai

- Đồng bộ tên cột dashboard với API/artifact.
- Bổ sung KPI, bộ lọc, phân bố risk score và bảng giao dịch high-risk.
- Theo dõi drift, nhãn trễ, calibration và điều kiện retraining.
- Lưu model registry, deployment checklist, rollback procedure và smoke test.
- Tách cấu hình bằng environment variables; kiểm tra artifact khi startup.
