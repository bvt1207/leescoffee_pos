# Module Rules: Branch — nguồn cấu hình duy nhất

> Paths: `leescoffee_pos/leescoffee_pos/doctype/branch_config/branch_config.py`,
> `leescoffee_pos/leescoffee_pos/api/pos_api.py` (`_get_pos_profile`, `get_pos_config`).
> Từ 2026-11-08: code **không còn đọc `Leescoffee POS Settings`** (DocType đã xóa: patch `patches/v1_remove_pos_settings.py`).

## 1. Field trên Branch (Custom Field, `fixtures/custom_field.json`)

| Nhóm | Field |
|------|-------|
| SePay | `sepay_enabled`, `sepay_api_key` (Password), `sepay_va_account`, `sepay_bank_code` |
| Thương hiệu | `brand_name`, `brand_logo`, `brand_banner`, `brand_phone`, `brand_address` |
| Công ty | `company` (Link → Company, label "Công ty", không bắt buộc, `in_standard_filter`) |

- Không fallback sang bất kỳ DocType nào khác. Field rỗng → trả `""`.
- Đọc bằng `branch.get("<field>")` để không lỗi nếu Custom Field chưa migrate.

## 2. Xác định chi nhánh

- Có POS Invoice / POS Profile → `POS Profile.branch`.
- Không có (gọi `get_default_branch()` hoặc `_get_pos_profile()` không truyền branch) →
  `branch_config.resolve_pos_profile_name()`:
  1. POS Profile đang bật, có `branch`, mà user hiện tại nằm trong "Applicable for Users"
     (`POS Profile User`), ưu tiên dòng `default = 1`.
  2. Nếu không: đúng **một** POS Profile đang bật có `branch`.
  3. Còn lại → `frappe.throw` (không đoán bừa như `limit=1` trước đây).
- `_get_pos_profile(branch_name)` có truyền branch mà chi nhánh không có POS Profile đang bật → throw.

## 3. Kiểm tra company

- `get_pos_config` trả thêm `warnings: [str]`. Nếu `Branch.company` có giá trị và khác
  `POS Profile.company` → thêm 1 cảnh báo + `frappe.log_error`. **Không throw** (hóa đơn dùng
  `POS Profile.company`, kế toán vẫn đúng; throw sẽ chặn cả màn /pos).
- Frontend hiện chưa hiển thị `warnings` (không sửa .tsx ở task này).
