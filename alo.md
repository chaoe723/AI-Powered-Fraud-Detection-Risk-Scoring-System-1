# Giải thích "mô hình lai" của hệ thống

Tài liệu này trả lời câu hỏi: *"Hệ thống nói có 2 mô hình, vậy 2 mô hình đó là thuật toán nào, đặc điểm và thông số ra sao?"* — đồng thời làm rõ khái niệm **mô hình lai (hybrid model)** để tránh hiểu nhầm khi báo cáo.

## 1. "Mô hình lai" là gì?

**Mô hình lai không phải là tên một thuật toán.** Logistic Regression, Random Forest, Isolation Forest… mới là tên thuật toán. "Mô hình lai" là cách gọi một **kiến trúc hệ thống** kết hợp đầu ra của nhiều mô hình khác loại để ra một quyết định chung.

Trong phát hiện gian lận, cách lai phổ biến nhất (và hệ thống này đang dùng) là ghép:

| Thành phần | Loại học | Vai trò |
|---|---|---|
| Random Forest | Có giám (cần nhãn fraud) | Bắt các pattern gian lận **đã biết** trong dữ liệu lịch sử → xác suất fraud |
| Isolation Forest | Không giám (không cần nhãn) | Bắt giao dịch **lạ, chưa từng thấy** so với tổng thể → điểm bất thường |

Lý do phải lai: mô hình có giám chỉ phát hiện được những hình thái đã xuất hiện trong tập huấn luyện. Kẻ gian lận liên tục đổi chiêu, nên cần thêm một lớp không giám để đặt cờ với mọi điểm bất thường kể cả khi chưa có nhãn. Mô hình lai vì thế là **pipeline ghép 2 thuật toán**, không phải một thuật toán mới — khi trình bày nên nói "hệ thống kết hợp 2 mô hình" hoặc "kiến trúc hybrid 2 tầng".

## 2. Hai thuật toán chính

### 2.1. Random Forest Classifier — học có giám (mô hình chính)

**Nguyên lý:** ensemble theo kiểu bagging gồm nhiều cây quyết định. Mỗi cây được huấn luyện trên một mẫu bootstrap (lấy ngẫu nhiên có hoàn lại) và tại mỗi nút chỉ xét một tập con thuộc tính ngẫu nhiên. Xác suất dự đoán cuối là trung bình các cây:

$$\hat{p}(y=1 \mid x) = \frac{1}{T}\sum_{t=1}^{T}\hat{p}_t(y=1 \mid x)$$

**Thông số trong code** (`backend/model_service.py:35`):

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| `n_estimators` | 250 | Số lượng cây trong rừng |
| `min_samples_leaf` | 2 | Mỗi lá tối thiểu 2 mẫu → chống overfit |
| `class_weight` | `balanced_subsample` | Cân bằng trọng số lớp do fraud rất hiếm, tránh thiên lệch về lớp "hợp lệ" |
| `random_state` | 42 | Cố định seed để kết quả tái lập được |
| `n_jobs` | 2 (env `FRAUD_RF_THREADS`) | Số luồng huấn luyện trên Windows |

**Đầu vào:** 34 đặc trưng được engineer theo trình tự thời gian từ lịch sử giao dịch (tần suất, số tiền trung bình, khoảng cách thời gian… — xem `backend/data_pipeline.py:21`). `merchant_category` được one-hot; `merchant_id` thô bị loại khỏi one-hot vì quá nhiều giá trị (dễ nổ chiều và overfit), các đặc trưng lịch sử theo merchant vẫn giữ.

### 2.2. Isolation Forest — học không giám (phát hiện bất thường)

**Nguyên lý:** xây rừng cây tách ngẫu nhiên (chọn ngẫu nhiên một thuộc tính rồi chọn ngẫu nhiên một ngưỡng cắt giữa min và max của thuộc tính đó). Điểm nào càng bị **cô lập sớm** — tức có độ dài đường đi trung bình từ gốc đến lá $E[h(x)]$ nhỏ — thì càng khác thường so với đám đông. Điểm bất thường:

$$s(x, n) = 2^{-\frac{E[h(x)]}{c(n)}}$$

với $c(n)$ là độ dài đường đi trung bình của cây tìm kiếm nhị phân không thành công trên $n$ mẫu. $s$ tiến tới 1 là bất thường, tiến tới 0 là bình thường.

**Thông số trong code** (`backend/model_service.py:79-89`):

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| `contamination` | `"auto"` | Không giả định trước tỷ lệ bất thường, tự lấy ngưỡng từ dữ liệu |
| `random_state` | 42 | Seed tái lập |
| Số dòng huấn luyện | tối đa 200.000 dòng đại diện | Mỗi cây iForest vốn chỉ học trên mẫu con nhỏ, lấy mẫu đủ đại diện mà không phải giữ cả ma trận hàng triệu dòng trong memory |
| Tập đặc trưng | chỉ các cột số | Bỏ cột one-hot |
| Chuẩn hoá điểm | percentile 1%–99% của tập train, clip về [0, 1] | Điểm ra có ý nghĩa so sánh với nền tham chiếu |

Nhãn `-1` từ `anomaly.predict()` tạo cờ `anomaly=True`; tín hiệu này **bổ sung** cho Random Forest chứ không thay thế xác suất fraud.

## 3. Logistic Regression — không phải mô hình chính

Đây là chỗ dễ nhầm nhất. Logistic Regression chỉ xuất hiện ở hai vai trò phụ:

1. **Hiệu chỉnh xác suất (Platt scaling)** — `backend/model_service.py:108`: một Logistic Regression 1 biến (`solver="lbfgs"`, `max_iter=200`) được fit trên **logit của xác suất thô từ Random Forest** để ánh xạ lại thành xác suất chuẩn hơn, dùng được cho ngưỡng và quyết định chi phí. Nó không học từ đặc trưng giao dịch, chỉ "sửa thang" đầu ra:

$$p_{\text{calibrated}} = \sigma(\alpha \cdot \text{logit}(p_{\text{RF}}) + \beta)$$

2. **Baseline so sánh** — `scripts/benchmark_models.py:46`: `StandardScaler + LogisticRegression(max_iter=300, class_weight="balanced")` được chạy cạnh Random Forest và HistGradientBoosting để chứng minh Random Forest tốt hơn.

Vì vậy **không được ghi** mô hình là "lai giữa hồi quy logistic và isolation forest". Cặp lai đúng là **Random Forest + Isolation Forest**.

## 4. Cơ chế ghép hai mô hình (tầng fusion)

Luồng xử lý một giao dịch:

```
Giao dịch
   │
   ▼
Feature engineering (34 đặc trưng, chỉ dùng quá khứ — backend/data_pipeline.py)
   │
   ├──────────────► Random Forest ──► xác suất fraud ──► Platt scaling
   │                                                      │
   └──────────────► Isolation Forest ──► anomaly_score ──┤
                                                          ▼
                          risk_score = 100 × [0.75 × p + 0.25 × max(anomaly_score, anomaly)]
                                                          │
                                                          ▼
                                    risk_level + quyết định (allow / manual_review / block)
```

Công thức và quy tắc ở `backend/risk_scoring.py:6`:

- `risk_score = 100 × [0.75 × fraud_probability + 0.25 × max(anomaly_score, anomaly)]`, giới hạn trong 0–100.
- Xác suất (trọng số 0.75) là tín hiệu chính; bất thường và số tiền đột biến cộng thêm tín hiệu giải thích được (0.25).
- Mức rủi ro: Low (<30), Medium (30–<60), High (60–<80), Critical (≥80).
- Quyết định: xác suất ≥ ngưỡng (mặc định `decision_threshold = 0.14`, `backend/model_service.py:38`) → `manual_review` (hoặc `block` ở profile `strict`); dưới ngưỡng → `allow`.

## 5. Chỉ số đo lường hiện tại

Số liệu lấy trực tiếp từ artifact trong `backend/artifacts/` (model version `kaggle-v5`, dataset Kaggle credit card fraud).

**Cách đánh giá:** chia dữ liệu theo thời gian 60/20/20 (fit / calibration / chọn ngưỡng) rồi đánh giá cuối trên giai đoạn sau hoàn toàn chưa thấy (`training_config.json`). Không dùng random split để tránh rò rỉ thông tin tương lai (temporal leakage). Đợt đánh giá dưới đây chạy trên 500.000 giao dịch (06–12/2020), trong đó 2.124 giao dịch fraud (tỷ lệ 0,42%).

**Kết quả mô hình production** (`evaluation_metrics.json`, ngưỡng profile `cost_optimal`):

| Chỉ số | Giá trị | Ý nghĩa |
|---|---|---|
| ROC-AUC | 0,9927 | Khả năng phân biệt fraud / hợp lệ gần như hoàn hảo |
| PR-AUC | 0,9280 | Chỉ số quan trọng nhất với dữ liệu lệch nặng như fraud |
| Recall | 95,76% | Bắt được 2.034/2.124 giao dịch fraud, bỏ sót 90 |
| Precision | 50,55% | Trong số bị flag, hơn nửa là thật; còn lại qua review thủ công |
| F1 / F2 | 0,662 / 0,812 | F2 nhấn mạnh ưu tiên recall (bỏ sót tốn hơn oan nhiều) |
| Accuracy / Specificity | 99,58% / 99,60% | Không oan lượng lớn giao dịch hợp lệ |
| Log-loss / Brier | 0,0042 / 0,00083 | Xác suất sau hiệu chỉnh Platt rất đáng tin |

**Ý nghĩa chi phí** (bộ trọng số: bỏ sót 100$, oan nhầm 2$, review thủ công 1$): nếu không có mô hình, 2.124 vụ fraud gây thiệt hại 212.400$; với mô hình, tổng chi phí còn 15.014$ — **giảm ~93%**.

**Benchmark vì sao chọn Random Forest** (`model_selection.json`, cùng đặc trưng và cùng cách chia thời gian):

| Mô hình | PR-AUC | ROC-AUC | Recall@top 1% | Vai trò |
|---|---|---|---|---|
| Random Forest | 0,827 | 0,991 | 86,8% | Production |
| HistGradientBoosting | 0,821 | 0,995 | 87,9% | Fallback nhanh |
| Logistic Regression | 0,323 | 0,975 | 74,9% | Baseline |

Random Forest hơn baseline Logistic Regression khoảng 2,6 lần về PR-AUC — đây là bằng chứng khiến Logistic Regression không thể làm mô hình chính.

Ngoài ra hệ thống lưu 4 profile ngưỡng vận hành (`thresholds.json`): `high_recall` (0,072 — ưu tiên bắt càng nhiều càng tốt), `cost_optimal` (0,025 — mặc định, tối ưu tiền), `strict` (0,010 — nghiêm ngặt, auto block), `balanced` (0,005).

## 6. Tóm tắt một ghi chú

| Câu hỏi | Trả lời |
|---|---|
| 2 mô hình là thuật toán nào? | Random Forest (học có giám) và Isolation Forest (học không giám) |
| Random Forest làm gì? | Dự đoán xác suất gian lận từ 34 đặc trưng lịch sử; 250 cây, `min_samples_leaf=2`, `class_weight=balanced_subsample` |
| Isolation Forest làm gì? | Điểm bất thường không giám bằng nguyên lý cô lập; `contamination=auto`, train 200k dòng số, chuẩn hoá [0,1] |
| Logistic Regression đứng đâu? | Chỉ hiệu chỉnh xác suất (Platt scaling) trên đầu ra RF + làm baseline benchmark, không phải mô hình chính |
| Ghép lại thế nào? | `risk = 100 × (0.75 × p + 0.25 × anomaly)`, chia 4 mức, quá ngưỡng 0.14 thì flag |
| "Mô hình lai" là thuật toán à? | Không — là kiến trúc kết hợp 2 mô hình, không phải một thuật toán mới |
| Hệ thống đang đạt chỉ số nào? | ROC-AUC 0,993; PR-AUC 0,928; recall 95,8% (sót 90/2.124 vụ fraud) trên 500k giao dịch test; giảm ~93% chi phí |
