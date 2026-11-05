 ## Plan triển khai train với Kaggle dataset

  ### Giai đoạn 1: Chuẩn hóa dữ liệu

  Tạo adapter riêng:

  Kaggle CSV → backend transaction schema

  Mapping:

  trans_num              → transaction_id
  cc_num                 → card_id/account_id
  trans_date_trans_time  → transaction_time
  amt                    → amount
  merchant               → merchant_id
  category               → merchant_category
  lat/long               → customer_location
  merch_lat/long         → merchant_location
  is_fraud               → label

  Xử lý bảo mật:

  - Hash cc_num.
  - Không dùng first, last, street làm feature.
  - Bỏ Unnamed: 0.
  - Giữ trans_num chỉ làm ID.
  - Chuẩn hóa datetime, amount và category.

  ### Giai đoạn 2: Tạo feature chống False Positive

  Tất cả feature lịch sử phải dùng dữ liệu trước giao dịch hiện tại.

  Theo từng card_id:

  card_txn_count_5m
  card_txn_count_1h
  card_txn_count_24h
  card_amount_sum_1h
  card_amount_sum_24h
  card_avg_amount_7d
  amount_vs_card_avg
  amount_zscore_card
  time_since_last_transaction
  is_new_merchant
  is_new_city
  is_new_state
  merchant_count_24h
  category_count_24h

  Feature thời gian:

  hour
  day_of_week
  is_weekend
  is_night
  hour_sin
  hour_cos

  Feature địa lý:

  distance_from_home
  distance_from_last_transaction
  distance_to_merchant
  impossible_travel

  Feature merchant:

  merchant_fraud_rate_history
  merchant_txn_count
  category_fraud_rate_history

  Các fraud-rate feature phải dùng rolling history hoặc chỉ tính trên train, không dùng toàn bộ dataset.

  ### Giai đoạn 3: Chia dữ liệu đúng

  Dataset đã có train/test theo thời gian:

  fraudTrain.csv → train + validation
  fraudTest.csv  → final test

  Trong fraudTrain.csv:

  60% đầu → train
  20% tiếp → validation
  20% cuối → validation phụ

  Giữ nguyên:

  fraudTest.csv → test cuối cùng

  Không random split toàn bộ dữ liệu.

  Mục tiêu là mô phỏng:

  Dữ liệu quá khứ → dự đoán giao dịch tương lai

  ### Giai đoạn 4: Xây baseline

  Train các baseline để có mốc so sánh:

  1. Logistic Regression với class_weight="balanced".
  2. Random Forest hiện tại.
  3. HistGradientBoosting hoặc LightGBM.
  4. Isolation Forest cho anomaly score.

  Không dùng SMOTE trước khi chia dữ liệu. Nếu cần oversampling, chỉ thực hiện trong train split và phải kiểm tra
  leakage.

  ### Giai đoạn 5: Chọn model chính

  Ưu tiên:

  Gradient Boosting/LightGBM + engineered features

  Nếu không thêm dependency:

  Random Forest + feature history

  Model có thể gồm hai nhánh:

  Supervised fraud probability
  +
  Unsupervised anomaly score

  Sau đó kết hợp:

  final_risk_score =
      0.75 * fraud_probability
    + 0.25 * anomaly_score

  Tỷ lệ này sẽ được tune trên validation, không cố định vĩnh viễn.

  ### Giai đoạn 6: Tối ưu threshold

  Không dùng threshold 0.5.

  Tính Precision-Recall curve và chọn nhiều operating point:

  High Recall mode:
  - Recall mục tiêu: 70%
  - Dùng cho cảnh báo rộng

  Balanced mode:
  - Precision tối thiểu: 25-30%
  - Dùng cho manual review

  Strict mode:
  - Precision tối thiểu: 40-50%
  - Dùng cho block/chặn giao dịch

  API có thể trả thêm:

  {
    "fraud_probability": 0.73,
    "risk_score": 81.4,
    "risk_level": "High",
    "decision": "manual_review",
    "threshold_profile": "balanced"
  }

  ### Giai đoạn 7: Đánh giá đầy đủ

  Bắt buộc xuất:

  TP
  TN
  FP
  FN
  Accuracy
  Precision
  Recall
  Specificity
  F1
  F2
  ROC-AUC
  PR-AUC
  Log Loss
  Brier Loss
  FDR@1%
  FDR@5%
  FDR@10%
  Recall@Precision 30%

  Đánh giá riêng theo:

  merchant category
  amount bucket
  hour
  city/state
  card
  fraud type nếu có

  ### Giai đoạn 8: Đánh giá theo chi phí

  Tạo cấu hình:

  cost:
    false_negative: 100
    false_positive: 2
    true_positive_review: 1
    manual_review: 1

  Tính:

  total_cost =
      FN * cost_false_negative
    + FP * cost_false_positive
    + TP * cost_true_positive_review

  Chọn threshold có tổng chi phí thấp nhất, thay vì chỉ tối ưu F1.

  ### Giai đoạn 9: Lưu artifact

  Lưu:

  fraud_model.joblib
  feature_schema.json
  thresholds.json
  metrics.json
  training_config.json

  Ví dụ:

  {
    "model_version": "kaggle-v1",
    "dataset": "kartik2112/fraud-detection",
    "decision_threshold": 0.28,
    "feature_count": 35,
    "pr_auc": 0.31,
    "recall": 0.72,
    "precision": 0.29
  }

  ### Giai đoạn 10: Kiểm thử backend

  Test:

  - Predict một giao dịch.
  - Predict batch CSV.
  - Dữ liệu category mới.
  - Dữ liệu thiếu field.
  - Amount âm.
  - Timestamp sai.
  - Card chưa từng xuất hiện.
  - Card có lịch sử dài.
  - Giao dịch liên tiếp bất thường.
  - Model load đúng feature schema.
  - API dùng đúng threshold profile.

  ### Tiêu chí đạt

  Bản train đầu tiên được xem là đạt nếu:

  PR-AUC tốt hơn baseline hiện tại 0.1572
  Precision tối thiểu khoảng 25% ở một operating point
  Recall tối thiểu khoảng 60%
  FDR@5% giảm so với model hiện tại
  Không có temporal leakage
  Không dùng raw PII
  API test pass toàn bộ

  Thứ tự triển khai nên là:

  Adapter dataset
  → Hash card ID
  → Feature lịch sử
  → Temporal split
  → Baseline
  → Train model chính
  → Tune threshold/cost
  → Evaluate
  → Lưu artifact
  → Tích hợp FastAPI
  → Test end-to-end