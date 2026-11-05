# Data Model Schema cho Fraud Detection

Tài liệu định nghĩa dữ liệu cần có để huấn luyện hệ thống phát hiện giao dịch gian lận.

## 1. Raw transaction fields

| Field | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `transaction_id` | string | ID duy nhất giao dịch |
| `account_id` | string | ID tài khoản đã hash/tokenize |
| `card_id` | string | ID thẻ đã hash/tokenize |
| `transaction_time` | datetime | Thời điểm giao dịch |
| `amount` | float | Số tiền giao dịch |
| `currency` | string | Loại tiền |
| `merchant_id` | string | ID merchant |
| `merchant_category` | category | Nhóm merchant |
| `payment_method` | category | Visa, Mastercard, Wallet... |
| `channel` | category | POS, ATM, Web, Mobile |
| `device_id` | string | ID thiết bị đã hash |
| `device_type` | category | Mobile, Desktop, Tablet |
| `ip_address` | string | IP đã hash hoặc thông tin network |
| `country` | category | Quốc gia giao dịch |
| `city` | category | Thành phố |
| `latitude` / `longitude` | float | Vị trí nếu có |
| `is_international` | boolean | Giao dịch quốc tế |
| `authentication_type` | category | OTP, 3DS, PIN, biometric |
| `authentication_result` | category | Success, Failed |
| `beneficiary_id` | string | Người nhận đã hash, áp dụng chuyển khoản |

Bộ field tối thiểu:

```text
transaction_id, account_id, transaction_time, amount, currency,
merchant_category, payment_method, channel, device_id, country,
authentication_result
```

## 2. Historical and behavioral features

Đây là nhóm quan trọng nhất để giảm False Positive. Feature phải được tính từ lịch sử trước giao dịch hiện tại, không dùng dữ liệu tương lai.

| Feature | Ý nghĩa |
|---|---|
| `user_txn_count_5m` | Số giao dịch của user trong 5 phút trước |
| `user_txn_count_1h` | Số giao dịch trong 1 giờ trước |
| `user_txn_count_24h` | Số giao dịch trong 24 giờ trước |
| `user_amount_sum_1h` | Tổng tiền giao dịch trong 1 giờ |
| `user_amount_sum_24h` | Tổng tiền trong 24 giờ |
| `user_avg_amount_7d` | Amount trung bình của user trong 7 ngày |
| `amount_vs_user_avg` | Amount hiện tại / amount trung bình |
| `amount_zscore_user` | Mức độ bất thường so với user |
| `time_since_last_txn` | Thời gian từ giao dịch trước |
| `is_new_device` | Thiết bị mới của user |
| `is_new_country` | Quốc gia mới của user |
| `is_new_merchant` | Merchant mới của user |
| `device_change_count_30d` | Số lần đổi thiết bị trong 30 ngày |
| `country_change_count_30d` | Số lần đổi quốc gia |
| `failed_auth_count_1h` | Số lần xác thực thất bại |
| `merchant_txn_count_24h` | Số giao dịch tại merchant trong 24 giờ |
| `account_age_days` | Tuổi tài khoản |
| `beneficiary_age_days` | Thời gian beneficiary tồn tại |
| `is_night` / `is_weekend` | Giao dịch ban đêm / cuối tuần |
| `impossible_travel` | Di chuyển địa lý không hợp lý |
| `distance_from_last_txn` | Khoảng cách so với giao dịch trước |

## 3. Label/target

Label là kết quả cần dự đoán, không được đưa trực tiếp vào feature:

```text
is_fraud: 0 = hợp lệ, 1 = gian lận
```

Nên lưu thêm `fraud_type`, `label_source`, `label_time` và `label_confidence`.

Các field chỉ xuất hiện sau điều tra chỉ được dùng để tạo label, không được train:

```text
chargeback_status
manual_review_result
fraud_confirmed_by_bank
investigation_result
```

## 4. Training metadata

| Field | Ý nghĩa |
|---|---|
| `event_time` | Thời điểm giao dịch thực tế |
| `label_time` | Thời điểm có kết luận fraud |
| `dataset_version` | Phiên bản dữ liệu |
| `source_system` | Nguồn dữ liệu |
| `split` | train/validation/test |
| `feature_generated_at` | Thời điểm tạo feature |

## 5. JSON mẫu

```json
{
  "transaction_id": "txn_001",
  "account_id": "account_hash_001",
  "transaction_time": "2025-05-01T14:30:00",
  "amount": 1250.5,
  "currency": "VND",
  "merchant_id": "merchant_123",
  "merchant_category": "electronics",
  "payment_method": "Visa",
  "channel": "Mobile",
  "device_id": "device_hash_001",
  "device_type": "Mobile",
  "country": "Vietnam",
  "authentication_result": "Success",
  "user_txn_count_1h": 3,
  "user_amount_sum_24h": 3200,
  "user_avg_amount_7d": 450,
  "amount_vs_user_avg": 2.78,
  "time_since_last_txn": 1800,
  "is_new_device": false,
  "is_new_country": false,
  "is_fraud": 0,
  "label_time": "2025-05-03T10:00:00"
}
```

## 6. Phân biệt thuật ngữ

- **Field**: Cột dữ liệu, ví dụ `amount`.
- **Feature**: Dữ liệu model sử dụng; có thể là raw field hoặc field tính toán, ví dụ `amount_vs_user_avg`.
- **Label/target**: Kết quả cần dự đoán, ví dụ `is_fraud`.
- **Tag**: Nhãn mô tả/phân nhóm, ví dụ `fraud_type = account_takeover`.

## 7. Ưu tiên để giảm False Positive

```text
user history
transaction velocity
device/location behavior
```

## 8. Chia train/validation/test

Nên chia theo thời gian để mô phỏng dự đoán tương lai:

```text
60% dữ liệu đầu: train
20% tiếp theo: validation
20% cuối: test
```

Không nên random split khi các giao dịch có liên hệ theo user hoặc thời gian vì có thể gây temporal leakage.
