---
title: Cơ sở lý thuyết mô hình và quy trình làm sạch, chuẩn hoá dữ liệu
date: 2026-09-15
tags:
  - machine-learning
  - fraud-detection
  - data-preprocessing
  - documentation
aliases:
  - Fraud Model Theory & Preprocessing Pipeline
---

# Cơ sở lý thuyết mô hình và quy trình làm sạch, chuẩn hoá dữ liệu

> [!abstract] Tổng quan kiến trúc
> Hệ thống áp dụng mô hình phân loại có giám sát **Random Forest** kết hợp phát hiện bất thường không giám sát **Isolation Forest** để tạo điểm đánh giá đa chiều. Điểm số được hiệu chuẩn qua **Platt Scaling (Logistic Regression)** và tối ưu hóa theo ma trận chi phí nghiệp vụ.

---

## 1. Phạm vi hệ thống

Hệ thống đánh giá từng giao dịch qua xác suất gian lận (`fraud_probability`) và tín hiệu bất thường (`anomaly`, `anomaly_score`), sau đó **Risk Engine** tính toán `risk_score`, gán `risk_level` và đưa ra quyết định nghiệp vụ (`allow`, `manual_review` hoặc `block`).

### Công thức tính điểm rủi ro

$$	ext{risk\_score} = \min\Big(100, \maxig(0, 100 	imes [0.75 	imes 	ext{fraud\_probability} + 0.25 	imes \max(	ext{anomaly\_score}, 	ext{anomaly})]ig)\Big)$$

> [!important] Quy định về vai trò mô hình
> - **Random Forest Classifier**: Là mô hình phân loại chính của API phục vụ inference.
> - **Isolation Forest**: Phục vụ phát hiện bất thường không giám sát.
> - **Logistic Regression**: Chỉ dùng để hiệu chỉnh xác suất (Platt scaling) và làm mô hình cơ sở trong script benchmark.
> - **HistGradientBoosting**: Được dùng trong script benchmark đối sánh.
> - *Tuyệt đối không ghi nhận Logistic Regression là mô hình phân loại chính.*

---

## 2. Cơ sở lý thuyết các mô hình

### 2.1. Random Forest Classifier – Mô hình chính
Random Forest là mô hình học có giám sát gồm tập hợp nhiều cây quyết định (*ensemble of Decision Trees*). Mỗi cây học trên một mẫu ngẫu nhiên có hoàn lại (*bootstrap*) và tại mỗi nút phân nhánh chỉ xét một tập con ngẫu nhiên các thuộc tính.

Dự đoán xác suất cuối cùng là trung bình xác suất từ $T$ cây quyết định:

$$\hat{p}(y=1 \mid x) = rac{1}{T}\sum_{t=1}^{T}\hat{p}_t(y=1 \mid x)$$

**Thiết lập trong mã nguồn:**
- `n_estimators=250`: Rừng gồm 250 cây giúp giảm thiểu phương sai dự báo.
- `min_samples_leaf=2`: Hạn chế tình trạng quá khớp (overfitting) trên dữ liệu lá đơn lẻ.
- `random_state=42`: Cố định tính tái lập của kết quả thực nghiệm.
- `class_weight="balanced_subsample"`: Điều chỉnh trọng số lớp tỷ lệ nghịch với tần suất xuất hiện trong từng mẫu bootstrap, giải quyết bài toán mất cân bằng lớp trầm trọng (imbalanced class).

> [!note] Lựa chọn đặc trưng đầu vào
> - Bao gồm các đặc trưng số và `merchant_category` (được mã hóa qua one-hot encoding).
> - Thuộc tính `merchant_id` thô bị loại khỏi one-hot do lực lượng giá trị (cardinality) quá lớn gây bùng nổ số chiều; các đặc trưng tổng hợp lịch sử giao dịch theo merchant vẫn được tính toán và lưu giữ.

### 2.2. Isolation Forest – Phát hiện bất thường
Isolation Forest là mô hình học không giám sát. Các cây cách ly (iTree) chia cắt ngẫu nhiên một thuộc tính và ngưỡng chia. Điểm dữ liệu càng ít lần phân nhánh để bị cô lập thì càng mang tính bất thường cao.

$$	ext{Anomaly Score} \propto rac{1}{\mathbb{E}[h(x)]}$$

- **Tập mẫu:** Huấn luyện trên tối đa 200.000 dòng đại diện của các đặc trưng số.
- **Cấu hình:** `contamination="auto"`, `random_state=42`.
- **Chuẩn hóa:** Giá trị `score_samples` được đổi dấu và chuẩn hóa về dải $[0, 1]$ qua percentile 1% và 99% của tập huấn luyện.
- **Cờ cảnh báo:** Nhãn ngoại lai `-1` kích hoạt cờ `anomaly=True`. Tín hiệu này đóng vai trò phòng vệ, phát hiện các hình thái gian lận hoàn toàn mới.

### 2.3. Logistic Regression – Baseline và Platt Scaling
Logistic Regression mô hình hóa log-odds của xác suất gian lận theo tổ hợp tuyến tính:

$$\log\left(rac{p}{1-p}ight) = eta_0 + \sum_{i=1}^{k}eta_i x_i \quad \Longrightarrow \quad p = rac{1}{1 + e^{-z}}$$

- **Trong `benchmark_models.py`:** Đóng vai trò mô hình chuẩn (baseline) kết hợp `class_weight="balanced"` và `StandardScaler`.
- **Trong pipeline chính:** Chỉ thực hiện **Platt scaling** — nhận giá trị logit của xác suất thô từ Random Forest để học lại trên một cửa sổ hiệu chuẩn thời gian riêng biệt. Giúp xác suất đầu ra phản ánh chính xác rủi ro thực tế.

### 2.4. HistGradientBoosting – Mô hình benchmark
Thuật toán xây dựng tuần tự các cây quyết định bằng cách gom các biến liên tục thành các giỏ giá trị rời rạc (histogram bins, thường là 256 bins), tăng tốc huấn luyện đáng kể trên dữ liệu quy mô lớn.
- Thiết lập: `max_iter=200`, `learning_rate=0.08`, `max_leaf_nodes=31`, có tăng trọng số lớp thiểu số.
- Đóng vai trò đối sánh offline, chưa được đóng gói lên API production.

### 2.5. Phân chia dữ liệu, hiệu chỉnh và ngưỡng chi phí
Dữ liệu được sắp xếp nghiêm ngặt theo trục thời gian `transaction_time` trước khi phân tách:
- **60% đầu:** Huấn luyện mô hình Random Forest & Isolation Forest.
- **20% kế tiếp:** Hiệu chuẩn xác suất (Platt Scaling).
- **20% sau:** Tối ưu hóa lựa chọn ngưỡng phân loại (Threshold tuning).
- **Tập kiểm tra độc lập (`fraudTest.csv`):** Đánh giá hiệu năng cuối cùng (out-of-time evaluation). Tuyệt đối không dùng k-fold ngẫu nhiên nhằm triệt tiêu hiện tượng rò rỉ dữ liệu tương lai (*temporal leakage*).

> [!tip] Ngưỡng tối ưu hóa chi phí (Cost-optimal Threshold)
> Hệ thống lưu cấu hình đa ngưỡng (`high_recall`, `balanced`, `strict`, `cost_optimal`). Ngưỡng chi phí được xác định bằng cách tối thiểu hóa hàm tổn thất kinh tế:
> 
> $$	ext{Cost} = 100 	imes 	ext{FN} + 2 	imes 	ext{FP} + 1 	imes 	ext{TP}$$
> 
> *(Việc bỏ lọt một gian lận FN gây thiệt hại đắt gấp 50 lần so với việc báo nhầm FP).*

---

## 3. Quy trình làm sạch và chuẩn hoá dữ liệu

```
[Raw Kaggle CSV]
       │
       ▼
[adapt_kaggle()] ──► Đổi tên cột, Drop PII, SHA-256 cc_num -> account_id
       │
       ▼
[Data Validation] ──► Ép kiểu datetime (raise on error), Ép kiểu amount/toạ độ
       │
       ▼
[Missing & Categorical] ──► Trim text, Fill 'unknown' cho trường tuỳ chọn
       │
       ▼
[Feature Engineering] ──► log(amount), relative rolling card 7d, sin/cos hour, one-hot
       │
       ▼
[Finite Check] ──► Dừng pipeline nếu còn sót NaN / inf
```

### 3.1. Chuẩn hoá schema và loại bỏ PII
- **Chuẩn hóa schema qua `adapt_kaggle()`:**
  - `trans_num` $ightarrow$ `transaction_id`
  - `cc_num` $ightarrow$ `account_id`
  - `trans_date_trans_time` $ightarrow$ `transaction_time`
  - `amt` $ightarrow$ `amount`
  - `merchant` $ightarrow$ `merchant_id`
  - `category` $ightarrow$ `merchant_category`
  - `is_fraud` $ightarrow$ `label`
  - Ánh xạ các cột tọa độ; tự động loại bỏ cột phát sinh `Unnamed:*`.
- **Loại bỏ PII bảo mật:** Xóa bỏ hoàn toàn các trường `first`, `last`, `street`, `dob`, `job`, `zip`. Riêng số thẻ tín dụng `cc_num` được băm bằng thuật toán SHA-256 để tạo thành `account_id`, bảo toàn khả năng liên kết lịch sử mà không lưu số thẻ gốc.

### 3.2. Kiểm tra dữ liệu bắt buộc và ép kiểu
- **Trường dữ liệu bắt buộc:** `transaction_id`, `account_id`, `transaction_time`, `amount`, `merchant_id`, `merchant_category`. Nếu ID bị rỗng hoặc chỉ có khoảng trắng, bản ghi sẽ bị loại bỏ.
- **Thời gian:** Sử dụng `pd.to_datetime(..., errors="raise")`. Định dạng sai hoặc rỗng sẽ kích hoạt lỗi dừng pipeline lập tức.
- **Số tiền:** Ép kiểu bằng `pd.to_numeric(..., errors="coerce")` và kiểm tra tính hữu hạn. Loại bỏ giá trị không phải số, NaN hoặc $\pm\infty$.
- **Tọa độ địa lý:** Ép kiểu số thực; nếu lỗi chuyển về `NaN`. Khi thiếu một tọa độ, hàm khoảng cách Haversine trả về `0` như một cơ chế chịu lỗi kỹ thuật (fault-tolerance), không phải phép nội suy vị trí.

### 3.3. Xử lý categorical và missing values
- Cắt tỉa khoảng trắng (trim) trên `merchant_id`, `merchant_category`, thành phố và bang.
- Điền `"unknown"` cho các trường tùy chọn bị khuyết để tránh phát sinh chuỗi `"nan"`. Không tự động điền giá trị cho trường khóa.
- Sau trích xuất đặc trưng, toàn bộ biến số phải vượt qua kiểm tra tính hữu hạn (`np.isfinite`). Bất kỳ lỗi nào sẽ dừng pipeline và hiển thị rõ tên cột.

### 3.4. Biến đổi và mã hoá đặc trưng (Feature Engineering)
Pipeline chính không sử dụng Min-Max hay StandardScaler toàn cục. Các biến đổi bao gồm:
1. $	ext{amount\_log} = \ln(1 + \max(	ext{amount}, 0))$: Giảm độ lệch phải của phân phối số tiền.
2. $	ext{amount\_vs\_card\_avg}$ và $	ext{amount\_zscore\_card}$: Chuẩn hóa tương đối theo cửa sổ trượt lịch sử 7 ngày của chính thẻ đó.
3. $	ext{hour\_sin}$, $	ext{hour\_cos}$: Mã hóa tuần hoàn giờ trong ngày nhằm duy trì tính liên tục (23:59 và 00:01).
4. `merchant_category`: Mã hóa One-hot với cờ `handle_unknown="ignore"`.
5. **Đặc trưng tích lũy lịch sử:** Tính toán nghiêm ngặt theo trình tự thời gian từ các giao dịch xảy ra trước giao dịch hiện tại, ngăn ngừa rò rỉ thông tin tương lai.

---

## 4. Hạn chế hiện tại và hướng nâng cấp

> [!warning] Hạn chế trong mã nguồn hiện hành
> - **Chưa có Deduplication tổng quát:** Chưa kiểm soát trùng lặp bản ghi theo `transaction_id` trên quy mô lớn.
> - **Không loại bỏ ngoại lai số tiền:** Giao dịch giá trị đột biến được giữ nguyên nhằm phục vụ mô hình học tín hiệu gian lận.
> - **Không nội suy số khuyết:** Không áp dụng mean/median imputation cho biến số; dữ liệu lỗi bị từ chối, tọa độ thiếu gán khoảng cách bằng 0.

### Hướng phát triển đề xuất
- [ ] Bổ sung module xác thực tính duy nhất của `transaction_id` và chính sách xử lý bản ghi trùng lặp.
- [ ] Kiểm tra miền giá trị hợp lệ của vĩ độ $[-90, 90]$ và kinh độ $[-180, 180]$.
- [ ] Thêm cờ phân loại `missing_location` thay vì luôn quy ước khoảng cách về 0.
- [ ] Theo dõi và thiết lập ngưỡng cảnh báo tỷ lệ dữ liệu khuyết thiếu (missing rate) theo thời gian thực.

---

## 5. Bảng đối chiếu hiện trạng code và báo cáo

| Hạng mục nội dung | Thực tế triển khai trong mã nguồn |
| :--- | :--- |
| **Mô hình chính** | Random Forest (250 cây, `min_samples_leaf=2`, `class_weight="balanced_subsample"`). |
| **Anomaly Detection** | Isolation Forest trên đặc trưng số (tối đa 200.000 mẫu, chuẩn hóa percentile 1%-99%). |
| **Calibration** | Logistic Regression (Platt scaling) trên cửa sổ thời gian riêng biệt. |
| **Benchmark** | Logistic Regression (StandardScaler) và HistGradientBoosting (chạy offline). |
| **Làm sạch dữ liệu** | `adapt_kaggle()` chuẩn hóa schema, drop PII, SHA-256 thẻ, ép kiểu chặt `datetime`/`numeric`. |
| **Biến đổi đặc trưng** | $\log(1+	ext{amount})$, chuẩn hóa rolling 7 ngày theo thẻ, mã hóa tuần hoàn `sin/cos`, One-Hot category. |
| **Chưa triển khai** | Khử trùng lặp tổng quát, loại trừ outlier số tiền, nội suy mean/median cho biến số. |
