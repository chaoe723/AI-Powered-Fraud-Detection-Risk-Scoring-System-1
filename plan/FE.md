# FRONTEND PLAN — Fraud Detection & Risk Scoring

> FE = Presentation Layer (lớp 1) theo sơ đồ KLTN. Chỉ giao tiếp với BE qua `plan/API_CONTRACT.md`.
> FE **không tự tính** fraud probability/risk score — mọi con số đến từ BE.

---

## Phase FE-0: Scaffold

```text
cd <repo-root>
npm create vite@latest frontend -- --template react-ts
cd frontend
npm i react-router-dom @tanstack/react-query recharts
npm i -D tailwindcss vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] Tailwind setup (v4: `@import "tailwindcss"` trong CSS + plugin Vite)
- [ ] `vite.config.ts`: proxy dev `/api` → `http://localhost:8000`
- [ ] TanStack Query provider (`QueryClientProvider`), Router provider

## Cấu trúc thư mục

```text
frontend/src/
├── api/
│   ├── client.ts          # fetch wrapper: base /api/v1, error envelope §5, timeout
│   └── analyses.ts        # hàm gọi từng endpoint §4 contract
├── types/
│   └── api.ts             # TS types mirror 100% API_CONTRACT.md (Analysis, Transaction, Summary, ErrorCode...)
├── constants/
│   └── risk.ts            # enum risk_level/decision/threshold_profile + màu + label tiếng Việt
├── components/
│   ├── RiskBadge.tsx      # pill màu theo risk_level
│   ├── DecisionBadge.tsx
│   ├── StatCard.tsx
│   ├── ChartCard.tsx      # khung biểu đồ Recharts
│   └── states/            # Loading.tsx, EmptyState.tsx, ErrorState.tsx (nhận ErrorCode)
├── pages/
│   ├── UploadPage.tsx             # /
│   ├── HistoryPage.tsx            # /analyses
│   ├── DashboardPage.tsx          # /analyses/:id
│   ├── TransactionsPage.tsx       # /analyses/:id/transactions
│   └── TransactionDetailPage.tsx  # /analyses/:id/transactions/:txnId
├── hooks/
│   ├── useAnalysis.ts     # polling: refetchInterval 1500ms khi status queued|processing
│   └── useTransactions.ts # giữ filter/sort/page trong URL search params
└── App.tsx / main.tsx
```

## Phase FE-1: Types + API client

- [ ] `types/api.ts`: viết tay mirror contract — `Analysis`, `Summary`, `Transaction`, `Paginated<T>`, `ApiError` với `error.code` là union các ErrorCode §5
- [ ] `client.ts`: parse envelope `{"error":{code,message}}` → throw `ApiError` có type; network lỗi → `NETWORK_ERROR`
- [ ] Quy tắc: field optional luôn có fallback khi render (`—`, `0`); **bỏ qua field lạ** (không crash khi BE thêm field mới)

## Phase FE-2: Pages

### UploadPage (`/`)
- Drag-drop hoặc chọn file `.csv/.xlsx`; select `threshold_profile` (5 giá trị enum, default `cost_optimal`)
- Submit → `POST /analyses` (202) → điều hướng sang `DashboardPage` của id mới → polling tự chạy
- Client-side chặn trước khi gửi: đuôi file sai, > 20MB (hiện lỗi ngay, không gọi API)
- Loading nút submit; lỗi từ BE hiện bằng ErrorState đúng `error.code`

### HistoryPage (`/analyses`)
- Bảng analyses: filename, status (badge), row_count, threshold_profile, created_at
- Row click → DashboardPage; nút Delete (confirm) → `DELETE` → invalidate query
- Empty state: chưa có phân tích nào → CTA về Upload

### DashboardPage (`/analyses/:id`) — màn hình chính theo sơ đồ PDF
- Khi `queued|processing`: skeleton + progress "Đang xử lý x/row_count"
- Khi `failed`: ErrorState kèm `error` message
- Khi `completed`, hiển thị:
  - **StatCards**: total transactions, flagged rate (%), avg risk score, avg fraud probability, labeled fraud rate (ẩn/`—` khi null)
  - **Risk distribution** (donut, 4 mức màu) + **Decision distribution** (bar)
  - **Fraud trends** (line/area chart theo `trends[].date`: transactions vs flagged)
  - **Device breakdown** + **Country breakdown** (horizontal bar, top 10)
  - CTA: "Xem giao dịch rủi ro cao" → TransactionsPage sort `risk_score desc`
  - Nút Export (csv/xlsx) → mở link `GET .../export`

### TransactionsPage (`/analyses/:id/transactions`)
- Bảng: transaction_id, time, amount, country, device, fraud_probability (%), risk_score, RiskBadge, DecisionBadge
- Filter: risk_level, decision (dropdown); search box `q` (debounce 300ms); sort theo cột (amount/risk_score/fraud_probability/time)
- Phân trang server-side (page, page_size) — đồng bộ vào URL search params (shareable link, back/forward hoạt động)
- Row click → TransactionDetailPage

### TransactionDetailPage (`/analyses/:id/transactions/:txnId`) — màn hình "Why?" theo PDF
- Header: **Risk: 87/100** to + RiskBadge + DecisionBadge
- Mục **Why?**: map `reasons[]` → câu tiếng Việt:
  - `high_model_probability` → "Xác suất gian lận cao (≥ ngưỡng của profile)"
  - `anomalous_transaction_pattern` → "Mẫu giao dịch bất thường (Isolation Forest)"
  - `high_transaction_amount` → "Số tiền lớn bất thường (≥ 3.000)"
- Bảng thuộc tính đầy đủ từ detail response (gồm các cột optional gốc)
- Nút back về danh sách

## Phase FE-3: Test & hoàn thiện

- [ ] Vitest: test `client.ts` (parse envelope, ApiError), RiskBadge, và 1 trang có mock (TransactionsPage render theo contract JSON mẫu)
- [ ] ESLint pass, build pass
- [ ] Kiểm tra mọi page có đủ 3 trạng thái loading/empty/error
- [ ] Smoke E2E với BE thật: upload `fraud_dashboard_dataset.csv` → dashboard → list → detail → export

## Quy ước UI

| risk_level | Màu |
|---|---|
| `low` | green |
| `medium` | amber |
| `high` | orange |
| `critical` | red |

- `decision`: `allow` green / `manual_review` amber / `block` red
- Tiền tệ & số: format `Intl.NumberFormat("vi-VN")`; percent 2 chữ số
- Không hardcode ngưỡng 80/60/30 — chỉ dựa vào `risk_level` BE trả

## Lệnh kiểm tra

```text
cd frontend
npm run lint
npx vitest run
npm run build
```

## Definition of Done (FE)

- 5 pages hoàn chỉnh theo contract §4, types khớp 100%
- Polling hoạt động: upload xong thấy dashboard tự cập nhật khi job xong
- Mọi lỗi BE hiển thị đúng `error.code` (không white-screen)
- lint + test + build pass; smoke E2E thành công
