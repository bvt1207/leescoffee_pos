---
name: branding-fallback-branch-vs-settings
description: Branding ưu tiên Branch, fallback Settings (đã làm trong get_brand_info); SePay config thì KHÔNG fallback
metadata:
  type: feedback
---

**Trạng thái (đối chiếu code 2026-10-27): đã triển khai** trong
`leescoffee_pos/leescoffee_pos/doctype/branch_config/branch_config.py::get_brand_info()`:
`name`, `logo`, `banner`, `phone`, `address` lấy từ field `brand_*` của Branch trước, rỗng thì lấy từ `Leescoffee POS Settings`.

**Phạm vi fallback — dễ nhầm:**
- **Branding**: Branch → fallback Settings (giữ nguyên).
- **SePay** (`sepay_enabled`, `sepay_api_key`, `sepay_va_account`, `sepay_bank_code`): **chỉ Branch, không fallback Settings**.
  Dòng "không còn fallback Settings" ở CLAUDE.md §7 chỉ nói về SePay.

**Why:** Branding là cấu hình theo chi nhánh, nhưng không phải chi nhánh nào cũng có logo/tên riêng nên cần mặc định chung. Tài khoản nhận tiền thì phải đúng của từng chi nhánh, không được dùng mặc định.

**How to apply:**
- Frontend/hóa đơn cần branding → gọi `get_brand_info()` (qua `get_pos_config`), không đọc thẳng Settings.
- Không hardcode giá trị branding nào (tên "Lee's Coffee", logo, banner) vào code/template/asset.
- Chưa xác minh: CLAUDE.md §1b ghi Banner field đã bị xóa khỏi Settings, nhưng `get_brand_info()` vẫn đọc `settings.brand_banner`. Cần kiểm tra trên bench.
