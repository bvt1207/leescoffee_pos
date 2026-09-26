---
name: branding-fallback-branch-vs-settings
description: Khi làm Branch, thêm field thương hiệu tương tự ở Branch, ưu tiên branding theo Branch trước, fallback về Settings
metadata:
  type: feedback
---

Sau này khi làm DocType **Branch** (hoặc bất kỳ entity nào liên quan đến chi nhánh), cần thêm các field thương hiệu tương tự như ở `Leescoffee POS Settings`:
- `brand_name`, `brand_logo`, `brand_banner`, `brand_phone`, `brand_address`

**Why:** Branding (tên quán, logo, banner) là dữ liệu cấu hình theo chi nhánh — mỗi chi nhánh có thể có logo/banners khác nhau. Tuy nhiên không phải chi nhánh nào cũng cần riêng, nên cần fallback về Settings chung.

**How to apply:**
- Logic ưu tiên: **Branch branding trước** (nếu Branch có giá trị), **fallback về Settings** (nếu Branch không có).
- Khi frontend POS hoặc hóa đơn cần branding, gọi API/DocType Settings/Branch theo thứ tự này.
- Không hardcode bất kỳ giá trị branding nào (tên "Lee's Coffee", logo, banner) vào code/template/asset — luôn đọc từ DocType.