# Cơ sở lý thuyết mô hình và quy trình làm sạch, chuẩn hoá dữ liệu

## 1. Phạm vi hệ thống

Hệ thống đánh giá từng giao dịch qua xác suất gian lận (`fraud_probability`) và tín hiệu bất thường (`anomaly`, `anomaly_score`), sau đó risk engine sinh `risk_score`, `risk_level` và quyết định `allow`, `manual_review` hoặc `block`.

Điểm rủi ro hiện được tính theo công thức \(risk\_score = 100\times[0,75\times fraud\_probability + 0,25\times\max(anomaly\_score, anomaly)]\), sau đó chặn trong khoảng 0–100. Mức rủi ro là Low (<30), Medium (30–<60), High (60–<80) và Critical (≥80).

Artifact đang triển khai dùng **Random Forest Classifier** là mô hình phân loại chính và **Isolation Forest** để phát hiện bất thường. **Logistic Regression** được dùng để hiệu chỉnh xác suất theo Platt scaling, đồng thời Logistic Regression và HistGradientBoosting được chạy ở script benchmark. Vì vậy không được ghi Logistic Regression là mô hình chính.

## 2. Cơ sở lý thuyết các mô hình

### 2.1. Random Forest Classifier – mô hình chính

Random Forest là mô hình học có giám sát gồm nhiều cây quyết định. Mỗi cây học trên một mẫu bootstrap và tại mỗi nút chỉ xét một tập con ngẫu nhiên các thuộc tính. Dự đoán cuối là trung bình xác suất từ các cây:

\[
\hat p(y=1\mid x)=\frac{1}{T}\sum_{t=1}^{T}\hat p_t(y=1\mid x)
\]

Trong code, Random Forest dùng 250 cây (`n_estimators=250`), `min_samples_leaf=2`, `random_state=42` và `class_weight="balanced_subsample"`. Trọng số lớp làm giảm thiên lệch về lớp không gian lận trong dữ liệu mất cân bằng. Mô hình cây phù hợp với quan hệ phi tuyến giữa tần suất giao dịch, số tiền, thời gian và địa lý; không yêu cầu chuẩn hoá z-score mọi biến số.

Đầu vào gồm các đặc trưng số và `merchant_category` được one-hot encoding. `merchant_id` thô bị loại khỏi one-hot vì có lực lượng giá trị lớn, dễ làm tăng chiều và quá khớp; các đặc trưng lịch sử theo merchant vẫn được giữ.

### 2.2. Isolation Forest – phát hiện bất thường

Isolation Forest là mô hình không giám sát. Các cây tách ngẫu nhiên một thuộc tính và ngưỡng tách; một điểm càng cần ít lần tách để bị cô lập thì càng bất thường. Do đó, độ dài đường đi trung bình (E[h(x)]) càng nhỏ thì anomaly score càng cao.

Code huấn luyện Isolation Forest trên tối đa 200.000 dòng đại diện của các đặc trưng số, với `contamination="auto"` và `random_state=42`. `score_samples` được đổi dấu và chuẩn hoá về 0–1 bằng percentile 1% và 99% của điểm huấn luyện. Nhãn -1 tạo cờ `anomaly=True`. Tín hiệu này bổ sung cho Random Forest, không thay thế xác suất gian lận.

### 2.3. Logistic Regression – baseline và Platt scaling

Logistic Regression mô hình hoá log-odds của xác suất gian lận:

\[
\log\frac{p}{1-p}=\beta_0+\sum_{i=1}^{k}\beta_ix_i,
\qquad p=\frac{1}{1+e^{-z}}
\]

Trong `benchmark_models.py`, đây là baseline với `class_weight="balanced"` và `StandardScaler`. Trong luồng chính, Logistic Regression chỉ thực hiện Platt scaling: nhận logit của xác suất Random Forest thô rồi học lại trên cửa sổ calibration theo thời gian. Nhờ đó xác suất trả về đáng tin cậy hơn để dùng ngưỡng và chi phí nghiệp vụ.

### 2.4. HistGradientBoosting – mô hình benchmark

HistGradientBoosting xây dựng tuần tự các cây, mỗi cây mới giảm sai số còn lại của các cây trước. Histogram giúp gom các giá trị liên tục thành bin để huấn luyện nhanh trên dữ liệu lớn. Benchmark dùng `max_iter=200`, `learning_rate=0.08`, `max_leaf_nodes=31` và tăng trọng số lớp gian lận. Mô hình này chỉ để so sánh, chưa chạy ở API.

### 2.5. Chia dữ liệu, hiệu chỉnh và chọn ngưỡng

Dữ liệu được sắp theo `transaction_time`: 60% đầu để huấn luyện, 20% kế tiếp để calibration, 20% sau để chọn threshold; `fraudTest.csv` dùng đánh giá cuối. Không random split, giúp mô phỏng dự báo giao dịch tương lai và hạn chế temporal leakage.

Hệ thống lưu các ngưỡng `high_recall`, `balanced`, `strict`, `cost_optimal`, thay vì cố định 0,5. Ngưỡng theo chi phí tối thiểu hoá (100\times FN + 2\times FP + 1\times TP), vì bỏ sót gian lận đắt hơn cảnh báo nhầm. Chỉ số nên báo cáo: Precision, Recall, F1/F2, ROC-AUC, PR-AUC, Log loss, Brier loss và FDR/top-k.

## 3. Làm sạch và chuẩn hoá dữ liệu đã thực hiện trong code

### 3.1. Chuẩn hoá schema và loại PII

`adapt_kaggle()` chuẩn hoá cột Kaggle: `trans_num → transaction_id`, `cc_num → account_id`, `trans_date_trans_time → transaction_time`, `amt → amount`, `merchant → merchant_id`, `category → merchant_category`, `is_fraud → label`; đồng thời map các cột toạ độ. Cột `Unnamed:*` sinh từ index CSV bị bỏ.

Các cột PII `first`, `last`, `street`, `dob`, `job`, `zip` bị loại. `cc_num` được băm SHA-256 thành `account_id`: vẫn liên kết được lịch sử giao dịch của một thẻ nhưng không giữ số thẻ gốc.

### 3.2. Kiểm tra dữ liệu bắt buộc và ép kiểu

Các trường bắt buộc: `transaction_id`, `account_id`, `transaction_time`, `amount`, `merchant_id`, `merchant_category`. ID rỗng/chỉ có khoảng trắng bị từ chối. `transaction_time` dùng `pd.to_datetime(..., errors="raise")`; timestamp sai hoặc thiếu làm pipeline dừng. `amount` dùng `pd.to_numeric(..., errors="coerce")` rồi kiểm tra phải hữu hạn; giá trị không phải số, thiếu, `NaN` và vô cực bị từ chối.

Toạ độ khách hàng/merchant cũng được ép kiểu số; giá trị lỗi thành `NaN`. Khi thiếu một toạ độ, hàm tính khoảng cách trả 0 để pipeline không sinh giá trị không hữu hạn. Đây là cơ chế chịu lỗi, không phải nội suy vị trí.

### 3.3. Làm sạch categorical và missing values

`merchant_id`, `merchant_category`, thành phố và bang được chuyển về chuỗi và xoá khoảng trắng đầu/cuối. Giá trị thiếu hoặc rỗng của trường không bắt buộc được điền `"unknown"`, tránh xuất hiện chuỗi `"nan"`. Trường bắt buộc không tự điền, nhằm tránh tạo lịch sử giao dịch sai. Sau feature engineering, code kiểm tra toàn bộ feature số phải hữu hạn; nếu còn `NaN`/`inf` thì dừng và nêu tên cột lỗi.

### 3.4. Biến đổi và mã hoá cho mô hình

Random Forest và Isolation Forest của pipeline chính không dùng Min–Max hay StandardScaler toàn bộ dữ liệu. Các biến đổi đang có gồm:

- `amount_log = log(1 + max(amount, 0))`: giảm lệch phải của số tiền.
- `amount_vs_card_avg` và `amount_zscore_card`: chuẩn hoá tương đối theo lịch sử 7 ngày của chính thẻ, không phải toàn bộ dataset.
- `hour_sin`, `hour_cos`: mã hoá tuần hoàn của giờ, để 23 giờ và 0 giờ không bị xem là cách xa nhau.
- `merchant_category`: one-hot encoding; category chưa gặp được xử lý an toàn bằng `handle_unknown="ignore"`.
- `StandardScaler` chỉ áp dụng cho Logistic Regression trong benchmark, không có trong API/model chính.

Feature lịch sử được tính theo thứ tự thời gian và chỉ dùng các giao dịch trước giao dịch hiện tại. Khi dự đoán/calibration, nhãn tương lai không được dùng để tạo feature.

## 4. Hạn chế hiện tại và hướng bổ sung

Code hiện **chưa có deduplication tổng quát** theo `transaction_id`. Code cũng **không loại outlier số tiền**: giao dịch rất lớn có thể là tín hiệu gian lận nên được giữ để mô hình đánh giá. Không có nội suy mean/median cho trường số bắt buộc; amount lỗi bị từ chối, còn toạ độ thiếu đi qua quy tắc khoảng cách bằng 0.

Phần hướng phát triển nên đề xuất: kiểm tra unique `transaction_id` và chính sách giữ/từ chối bản ghi trùng; kiểm tra miền hợp lệ của amount và latitude/longitude; theo dõi tỷ lệ missing theo cột; thêm cờ `missing_location` thay vì luôn quy khoảng cách thiếu về 0. Không nên mô tả các bước này là đã triển khai.

## 5. Bảng đối chiếu code–báo cáo

| Nội dung | Thực tế trong code |
| --- | --- |
| Mô hình chính | Random Forest 250 cây, `balanced_subsample` |
| Anomaly detection | Isolation Forest trên feature số |
| Calibration | Logistic Regression (Platt scaling) theo temporal window |
| Benchmark | Logistic Regression, Random Forest, HistGradientBoosting |
| Làm sạch | Mapping schema, ép kiểu, trim text, `unknown`, hash account, kiểm tra trường bắt buộc |
| Biến đổi | log amount, feature tương đối theo lịch sử thẻ, sin/cos giờ, one-hot category |
| Chưa có | Deduplication tổng quát, quy tắc loại outlier, imputation số tổng quát |
