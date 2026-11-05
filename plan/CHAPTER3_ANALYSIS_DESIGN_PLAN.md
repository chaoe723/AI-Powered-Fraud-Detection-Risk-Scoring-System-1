# Plan phân việc — Chương 3: Phân tích và Thiết kế Hệ thống

> Tham khảo cấu trúc Chương 3 khóa luận mẫu (Website đọc tin tức tích hợp chatbot AI — NEU 2025).
> Áp dụng cho đề tài: **AI-Powered Fraud Detection & Risk Scoring System**.
> Team: 3 vai như `plan/TEAM_COORDINATION_PLAN_CORE_BE_FE.md` — **Core/ML**, **Backend**, **Frontend** (+ 1 người làm Leader hợp nhất, có thể kiêm nhiệm).
> Nguồn sự thật khi viết: `plan/API_CONTRACT.md`, `backend/storage.py`, `backend/api_v1.py`, `frontend/src/pages/*`.

---

## 1. Ánh xạ đầu mục tham khảo → chương của mình

| Khóa luận mẫu | Chương của mình (đề xuất) | Nội dung chính | Owner chính |
|---|---|---|---|
| 3.1.1 Biểu đồ ca sử dụng | 3.1.1 Mô hình hóa yêu cầu chức năng | Biểu đồ chức năng, Use Case tổng quát, phân rã theo tác nhân, bảng đặc tả UC + bảng dữ liệu chức năng | Core + BE + FE |
| 3.1.2 Biểu đồ hoạt động | 3.1.2 Mô hình hóa nghiệp vụ | Activity diagram cho từng chức năng chính (2 lane: Người dùng / Hệ thống) | BE + FE + Core |
| 3.1.3 Phân tích cấu trúc | 3.1.3 Phân tích cấu trúc | Class diagram: Analysis, TransactionRow, Storage, ModelService, RiskScoring, DataPipeline + class FE | BE + Core |
| 3.1.4 Phân tích hành vi | 3.1.4 Phân tích hành vi | Sequence diagram các luồng chính (upload/job, truy vấn, scoring nội bộ) | BE + Core |
| 3.2.1 Giao diện người dùng | 3.2.1 Thiết kế giao diện người dùng | 5 màn hình: Upload, History, Dashboard, Transactions, Transaction Detail | FE |
| 3.2.2 Giao diện admin | 3.2.2 Thiết kế giao diện quản trị | Quản lý phiên phân tích (xóa), thông tin model/threshold (`/model/meta`), threshold_profile | BE + Core |
| 3.3.1 Môi trường phát triển | 3.3.1 Môi trường phát triển | Windows, VS Code, Python venv, Node.js | BE |
| 3.3.2 Cơ sở dữ liệu | 3.3.2 Xây dựng cơ sở dữ liệu | Bảng `analyses`, `transactions` (từ `backend/storage.py`) | BE |
| 3.3.3 Ngôn ngữ và công nghệ | 3.3.3 Ngôn ngữ và công nghệ | Python/FastAPI/Pydantic/SQLAlchemy, React+Vite+TS, scikit-learn (RF + Isolation Forest), SQLite, Power BI | Core |
| 3.3.4 Cài đặt các chức năng | 3.3.4 Cài đặt các chức năng | Ảnh chụp chạy thật + mô tả cách hiện thực từng chức năng | FE + BE |

**Tác nhân của hệ thống mình (chốt trước khi vẽ):**
1. **Người phân tích (Analyst)** — upload, xem kết quả, xuất báo cáo.
2. **Hệ thống AI (ML Engine)** — tác nhân nội bộ: pipeline → RF/IF → risk scoring → decision.
3. **Quản trị viên (Admin)** — quản lý phiên phân tích, xem model meta/threshold *(nếu nhóm chốt không có UI admin riêng thì gộp vào vai Analyst phần "quản lý", ghi rõ trong mục 3.2.2)*.

**Danh mục Use Case nền (10 UC — điều chỉnh sau khi P0 chốt):**
- UC01 Upload file giao dịch (CSV/XLSX)
- UC02 Chạy phiên phân tích (job async, chọn `threshold_profile`)
- UC03 Theo dõi tiến độ phân tích (polling)
- UC04 Xem lịch sử phiên phân tích
- UC05 Xóa phiên phân tích
- UC06 Xem dashboard thống kê
- UC07 Xem danh sách giao dịch (lọc / tìm kiếm / phân trang)
- UC08 Xem chi tiết giao dịch + giải thích "Why?"
- UC09 Xuất kết quả CSV/XLSX
- UC10 Xem thông tin model (artifact, metrics, thresholds)

---

## 2. Quy ước chung (P0 phải chốt trước khi ai đó bắt tay vẽ)

- **Công cụ vẽ:** draw.io (file `.drawio` commit kèm PNG xuất 2x) hoặc PlantUML — chọn 1, cả nhóm dùng chung.
- **Cấu trúc thư mục đầu ra:**
  ```text
  docs/chapter3/
  ├── 03_phan_tich_thiet_ke.md      # bản hợp nhất chương
  ├── diagrams/                     # *.drawio + *.png (đặt tên theo hình)
  └── specs/                        # uc0X_<ten>.md (bảng đặc tả từng UC)
  ```
- **Đánh số hình/bảng:** Hình 3.x / Bảng 3.y, đánh theo thứ tự xuất hiện, ghi vào file `docs/chapter3/figures_index.md` do Leader giữ.
- **Template đặc tả UC** (9 trường, bám mẫu): Mã UC, Tên UC, Tác nhân, Mô tả, Sự kiện kích hoạt, Tiền điều kiện, Luồng sự kiện chính (STT / Thực hiện bởi / Hành động), Luồng sự kiện thay thế, Hậu điều kiện. Mỗi UC kèm 1 **bảng dữ liệu chức năng**: STT, Trường dữ liệu, Mô tả, Bắt buộc, Điều kiện hợp lệ, Ví dụ.
- **Activity diagram:** 2 lane `Người dùng | Hệ thống`, nút bắt đầu đặc, kết thúc viền đỏ, điều kiện `[Yes]/[No]`.
- **Sequence diagram:** mẫu boundary-control-entity như khóa luận mẫu, đổi tên lane cho đúng code: `UI Page → API Client → BE Router → Service → Storage/Model`.
- **Thuật ngữ tiếng Việt thống nhất:** "giao dịch", "phiên phân tích", "xác suất gian lận", "điểm rủi ro", "mức rủi ro" (low/medium/high/critical), "quyết định" (allow/review/block). File `docs/chapter3/glossary.md`.

---

## 3. Chia task

### Giai đoạn 0 — Chuẩn bị (Owner: Leader, ~0.5 ngày)

| Task | Nội dung | Đầu ra | Xong khi |
|---|---|---|---|
| **P0.1** | Chốt danh mục chức năng + tác nhân + 10 UC nền từ `API_CONTRACT.md`; nhóm duyệt | Danh sách UC chốt trong file này (mục 1) | Cả 3 bên đồng ý, không thêm bớt lẻ tẻ về sau |
| **P0.2** | Chốt công cụ vẽ, template UC, thư mục `docs/chapter3/`, đánh số hình, glossary | Khởi tạo thư mục + template mẫu `specs/uc01_upload.md` (làm mẫu) | Các bên copy template được ngay |

### Giai đoạn 1 — 3.1.1 Mô hình hóa yêu cầu chức năng

| Task | Owner | Nội dung | Đầu ra | Xong khi | Phụ thuộc |
|---|---|---|---|---|---|
| **T1** | Core | Biểu đồ chức năng tổng thể (phân nhánh theo tác nhân: Analyst / Admin / Hệ thống AI) | `diagrams/h3_1_bieu_do_chuc_nang` | Đủ mọi chức năng trong danh sách UC, không sót màn hình FE nào | P0 |
| **T2** | BE | Use Case tổng quát (1 hình) + Use Case phân rã theo tác nhân (3 hình: analyst, admin, hệ thống AI), có `<<include>>/<<extend>>` đúng chỗ (VD: "Chạy phân tích" include "Theo dõi tiến độ") | 4 hình UC | Mỗi tác nhân có ảnh riêng; quan hệ include/extend hợp lý | T1 |
| **T3** | FE **4 UC**: UC01, UC06, UC07, UC08; BE **4 UC**: UC02, UC03, UC09, UC10; Core **2 UC**: UC04, UC05 + rà soát luồng thay thế kỹ thuật | 10 bảng đặc tả UC + 10 bảng dữ liệu chức năng | Đúng template 9 trường; mỗi UC ≥ 1 luồng thay thế (thiếu trường, sai định dạng file, job failed, file rỗng…); dữ liệu trường lấy đúng `schemas.py`/form FE | P0, T2 |

### Giai đoạn 2 — 3.1.2 Biểu đồ hoạt động (chạy song song Giai đoạn 1 từ T4 trở đi)

| Task | Owner | Nội dung | Đầu ra | Xong khi | Phụ thuộc |
|---|---|---|---|---|---|
| **T4** | BE | AD: Upload + chạy phân tích async + polling (có nhánh job failed/stale) | `h3_9_ad_upload_analyze` | Có đủ 2 lane, nhánh lỗi, kết thúc đúng | T3 |
| **T5** | FE | AD: Xem dashboard + danh sách giao dịch (lọc/tìm kiếm/phân trang) | `h3_10_ad_dashboard_list` | Phản ánh đúng luồng gọi API v1 | T3 |
| **T6** | FE | AD: Xem chi tiết giao dịch + "Why?" + xuất CSV/XLSX | `h3_11_ad_detail_export` | Có nhánh không tìm thấy giao dịch, export lỗi | T3 |
| **T7** | Core | AD: pipeline chấm điểm nội bộ (đọc file → làm sạch → feature → RF + IF → risk score → decision → lưu SQLite) | `h3_12_ad_scoring_pipeline` | Khớp `data_pipeline.py`/`risk_scoring.py` thực tế | T3 |

### Giai đoạn 3 — 3.1.3 Cấu trúc + 3.1.4 Hành vi

| Task | Owner | Nội dung | Đầu ra | Xong khi | Phụ thuộc |
|---|---|---|---|---|---|
| **T8** | BE + Core (BE vẽ, Core review phần class ML) | Class diagram: entity `Analysis`, `TransactionRow`; class `Storage`, `ApiRouter`, `ModelService`, `DataPipeline`, `RiskScoring`; class FE chính (Pages, ApiClient); quan hệ + đa số đúng (1-n Analysis–Transaction) | `h3_13_class_diagram` | Tên class/trường khớp code, có kiểu dữ liệu chính, có 1-đa đúng chiều | T4 |
| **T9** | BE | SD: Upload → tạo job → poll → hoàn tất (kèm nhánh job failed) | `h3_14_sd_upload_job` | 4 lớp lane đúng quy ước P0 | T8 |
| **T10** | BE | SD: truy vấn danh sách/lọc + chi tiết + export | `h3_15_sd_query_export` | Đúng luồng endpoint v1 | T8 |
| **T11** | Core | SD: scoring nội bộ (Router → ModelService → RF/IF → RiskScoring → Storage) | `h3_16_sd_scoring` | Khớp thứ tự gọi trong `api_v1.py` | T8 |

### Giai đoạn 4 — 3.2 Thiết kế giao diện

| Task | Owner | Nội dung | Đầu ra | Xong khi | Phụ thuộc |
|---|---|---|---|---|---|
| **T12** | FE | 3.2.1: ảnh chụp 5 màn hình (Upload, History, Dashboard, Transactions, Detail) + mô tả bố cục, thành phần, trạng thái (loading/empty/error) | Mục 3.2.1 + 5-6 hình | Ảnh chụp từ bản build thật (`npm run dev`), mô tả đủ trạng thái | FE xong các trang |
| **T13** | BE + Core | 3.2.2: giao diện quản trị — quản lý phiên phân tích (xóa), model meta/threshold; nếu chưa có UI riêng thì mô tả màn hình History vai quản lý + API quản trị | Mục 3.2.2 + 1-2 hình | Nêu rõ ranh giới quyền quản trị, chốt kịch bản demo | T12 |

### Giai đoạn 5 — 3.3 Xây dựng hệ thống

| Task | Owner | Nội dung | Đầu ra | Xong khi | Phụ thuộc |
|---|---|---|---|---|---|
| **T14** | BE | 3.3.1 Môi trường phát triển: HĐH, IDE, runtime, cách chạy local (uvicorn + vite) | Mục 3.3.1 | Có lệnh chạy copy được từ README | — |
| **T15** | BE | 3.3.2 CSDL: 2 bảng `analyses`, `transactions` theo đúng cột/kiểu trong `backend/storage.py`, trình bày dạng bảng STT/Tên trường/Kiểu/Mô tả như mẫu | Mục 3.3.2 + 2 bảng | 100% cột khớp code, không mô tả sai kiểu | — |
| **T16** | Core | 3.3.3 Ngôn ngữ & công nghệ: Python, FastAPI, Pydantic, SQLAlchemy, scikit-learn (RF, Isolation Forest), Joblib, React+Vite+TS, SQLite, Power BI — mỗi cái 1-2 câu vai trò trong hệ thống | Mục 3.3.3 | Đúng danh sách trong `requirements.txt` + `package.json` | — |
| **T17** | FE + BE | 3.3.4 Cài đặt các chức năng: ảnh chụp + mô tả hiện thực từng chức năng (bcrypt/auth nếu có; upload, polling, dashboard, "Why?", export) | Mục 3.3.4 + hình | Mỗi chức năng có ảnh chạy thật + 3-5 câu giải thích kỹ thuật | T12, T14 |

### Giai đoạn 6 — Hợp nhất & QA (Owner: Leader, ~1-1.5 ngày)

| Task | Nội dung | Xong khi |
|---|---|---|
| **T18** | Ghép toàn bộ vào `03_phan_tich_thiet_ke.md`; đánh số lại hình/bảng; lập Danh mục hình, Danh mục bảng | Số hình/bảng liên tục, không trùng, có index |
| **T19** | Review chéo: FE đọc phần BE, BE đọc phần FE, Core đọc cả hai — kiểm tra thuật ngữ, mâu thuẫn giữa diagram và code | Mỗi bên sign-off phần mình bị review |
| **T20** | Kiểm tra format nộp bài: font, tiêu đề, chú thích hình in nghiêng đậm như mẫu, Turnitin-safe (tự viết mô tả, không chép mẫu) | Đạt yêu cầu format của KLTN |

---

## 4. Timeline gợi ý (2 tuần)

```text
Tuần 1
  Ngày 1     : P0.1 + P0.2 (Leader) — họp chốt tác nhân, UC, template
  Ngày 1-2   : T1 (Core), T2 (BE) — song song
  Ngày 2-4   : T3 (FE + BE + Core chia 10 UC theo bảng trên)
  Ngày 3-5   : T4 (BE), T5 (FE), T6 (FE), T7 (Core) — song song
  Ngày 5     : T8 (BE vẽ + Core review)
Tuần 2
  Ngày 6-7   : T9 (BE), T10 (BE), T11 (Core) — song song
  Ngày 6-8   : T12 (FE), T13 (BE+Core)
  Ngày 8-9   : T14 (BE), T15 (BE), T16 (Core), T17 (FE+BE)
  Ngày 9-10  : T18 + T19 + T20 (Leader + review chéo)
```

Milestone giữa kỳ (cuối tuần 1): toàn bộ diagram 3.1 phải có bản nháp để Leader rà trước.

## 5. Lưu ý chống rủi ro

- **Đừng chép ngữ cảnh khóa luận mẫu** (đọc báo, chatbot, nhà báo) — chỉ mượn *cấu trúc đầu mục + format bảng + style vẽ diagram*.
- Mọi diagram phải khớp code hiện có (`API_CONTRACT.md`, `storage.py`) — vẽ xong so tên endpoint/trường một lượt trước khi sign-off.
- Ảnh chụp giao diện chụp **sau** khi FE ổn định CSS, tránh phải chụp lại.
- Mỗi task xong nộp bằng PR vào `docs/chapter3/`, Leader merge; tranh chấp nội dung nhìn `plan/API_CONTRACT.md` trước (giữ nguyên quy tắc contract-first của nhóm).
