## Đơn giản hóa 16 diagram Chương 3 (tối giản mạnh)

**Vấn đề:** 16 diagram là block ```mermaid``` inline trong `docs/chapter3/03_phan_tich_thiet_ke.md`, render ra PNG quá chi tiết và lệch dọc (h3_10: 888×5492, h3_22: 558×2628, h3_01: 912×2470).

**Mục tiêu:** mỗi diagram còn 4–6 khối chính, label 1 dòng, ảnh cân đối (cao ≤ ~2× rộng). Không đổi tên file/caption → không phải sửa text khác trong md.

### 1. Viết lại 16 block mermaid trong md (giữ theme Times New Roman hiện có)
- **h3_01 (chức năng):** root + 2 nhóm; nhóm Analyst gộp 9 box → 4 (Quản lý phiên, Chạy & theo dõi, Tra cứu + Why?, Xuất kết quả); Admin còn 2.
- **h3_02 (use case tổng quát):** actor nối thẳng vào 2 package (không nối từng UC) → hết rối dây; giữ 10 UC label ngắn bên trong.
- **h3_03/04/05 (use case phân rã):** 4–5 UC/diagram, bỏ include thừa.
- **h3_06→10 (activity):** 5–7 node mỗi diagram; 3 diamond validate gộp thành 1 "File hợp lệ?"; các nhãn lỗi gộp 1 node "Hiện lỗi (400/413/422)".
- **h3_11 (class):** 13 class → 5 (FE Pages, API v1, FraudModel, DataPipeline, Storage/Analysis), mỗi class 2–4 thành viên chính.
- **h3_12/13/14 (sequence):** bỏ lifeline không dùng (vd. FraudModel trong h3_12), còn 3–4 participant, 5–8 message, gộp alt/loop.
- **h3_15 (navigation):** rút về 5 node màn hình chính.
- **h3_22 (ERD):** mỗi bảng còn ~5 trường (PK/FK + quan trọng nhất); thử `direction LR` cho 2 bảng nằm ngang, nếu mermaid không hỗ trợ thì giữ dọc nhưng thấp.

### 2. Render lại PNG (ghi đè, cùng tên file)
- Script tạm (python) trích từng block mermaid từ md → `tmp_shots/mmd/*.mmd` → render bằng `npx -y @mermaid-js/mermaid-cli -i … -o docs/chapter3/diagrams/….png -b white -s 2` (scale 2x cho nét in; Chrome for Testing đã có sẵn cache, chỉ cần tải package npm — đường này đã chạy thành công hôm nay).

### 3. Kiểm tra
- PIL check kích thước mọi PNG (tỉ lệ hợp lý), Read từng ảnh xác nhận nội dung + không bị cụt; render lại ảnh còn xấu.
- Chạy judge trên bộ PNG cuối để nghiệm thu hình ảnh.

### 4. Kết thúc
- Refresh `chapter3_full.zip` (md + diagrams + screenshots).
- Commit local "Simplify chapter 3 diagrams" (push lên remote chaoe723 vẫn đang bị 403 chờ bạn cấp quyền — sẽ đẩy khi có quyền).