# Module Rules: Branch — nguồn cấu hình duy nhất

> Paths: `leescoffee_pos/leescoffee_pos/doctype/branch_config/branch_config.py`,
> `leescoffee_pos/leescoffee_pos/api/pos_api.py` (`_get_pos_profile`, `get_pos_config`).
> Từ 2026-11-08: code **không còn đọc `Leescoffee POS Settings`** (DocType đã xóa: patch `patches/v1_remove_pos_settings.py`).

## 1. Field trên Branch (Custom Field, `fixtures/custom_field.json`)

| Nhóm | Field |
|------|-------|
| SePay | `sepay_enabled`, `sepay_api_key` (Password), `sepay_va_account`, `sepay_bank_code` |
| Thương hiệu | `brand_name`, `brand_logo`, `brand_phone`, `brand_address` (`brand_banner` đã bỏ 2026-11-25, §4) |
| Công ty | `company` (Link → Company, label "Công ty", không bắt buộc, `in_standard_filter`) |

- Không fallback sang bất kỳ DocType nào khác. Field rỗng → trả `""`.
- Đọc bằng `branch.get("<field>")` để không lỗi nếu Custom Field chưa migrate.

## 2. Xác định chi nhánh

- Có POS Invoice / POS Profile → `POS Profile.branch`.
- **POS Profile đang bật bắt buộc có Branch** (2026-11-25, `pos_profile_hooks._check_branch`): thiếu → chặn lưu ("… đang bật nhưng chưa
  gán Chi nhánh …"); profile đã tắt thì lưu được. Chi nhánh đã có profile đang bật khác → cảnh báo cam (không chặn). Không đặt `reqd`
  trong fixture, không patch: dữ liệu cũ chỉ bị chặn ở lần lưu kế tiếp.
- Không có (gọi `get_default_branch()` hoặc `_get_pos_profile()` không truyền branch) →
  `branch_config.resolve_pos_profile_name()` (2026-11-25):
  1. User nằm trong "Applicable for Users" của ít nhất một POS Profile **đang bật** → profile đầu tiên (`default = 1` trước, rồi tên
     A→Z). Profile đó thiếu `branch` → throw "POS Profile X của bạn chưa được gán chi nhánh…", **không** rơi sang profile khác
     (trước đây lặng lẽ dùng profile duy nhất có Branch — sai kho, giá, ca).
  2. User không thuộc profile đang bật nào (vd. Administrator / System Manager): đúng **một** POS Profile đang bật có `branch`.
  3. Còn lại → `frappe.throw`.
- `_get_pos_profile(branch_name)` (dùng cho web QR `customer_order_api._profile`) → `pos_api._branch_profile_name`: chi nhánh có
  ≥ 2 profile đang bật → profile **đang mở ca** đầu tiên theo tên A→Z, không có thì profile đầu theo tên (trước đây `get_value`
  không sắp xếp). Một profile → không thêm truy vấn. Không có profile → throw.
  - Hệ quả: nếu các profile cùng chi nhánh dùng Price List khác nhau, menu `/order` đổi theo ca đang mở. Khuyến nghị: mỗi chi nhánh
    MỘT profile đang bật (profile thử nghiệm: tắt hoặc gán Branch test riêng).
- `pos_api.get_buzzers`: profile thiếu Branch → throw (không lọc rỗng = thẻ mọi chi nhánh).

## 3. Kiểm tra company

- `get_pos_config` trả thêm `warnings: [str]`. Nếu `Branch.company` có giá trị và khác
  `POS Profile.company` → thêm 1 cảnh báo + `frappe.log_error`. **Không throw** (hóa đơn dùng
  `POS Profile.company`, kế toán vẫn đúng; throw sẽ chặn cả màn /pos).
- Frontend hiện chưa hiển thị `warnings` (không sửa .tsx ở task này).

## 4. Banner: không còn ở Branch (2026-11-25)

- Custom Field `Branch.brand_banner` đã bỏ (fixture + patch `v1_remove_brand_banner`: in + Error Log "MYPOS: sao lưu brand_banner trước
  khi xóa" danh sách ảnh đang dùng, không xóa File). `get_brand_info` / `get_branch_config` không còn khóa banner.
- Ảnh đầu trang đăng nhập `/order` = **MYPOS Banner public đầu tiên** của POS Profile chi nhánh (`mypos_banner.active_banners`,
  dùng chung bộ lọc với màn khách, `customer_display.md` §4). Ảnh private bị bỏ qua ở `/order` (khách là Guest).

## 5. Checklist cấu hình 1 cửa hàng (UAT)

**Branch**
- [ ] `company` (Công ty) = `POS Profile.company`
- [ ] `brand_name`, `brand_logo` (file **public**), `brand_phone`, `brand_address`
- [ ] `sepay_enabled` = 1, `sepay_va_account`, `sepay_bank_code`, `sepay_api_key` (trùng key cấu hình bên SePay; thiếu key → webhook
      và đặt món QR không chạy)

**POS Profile** (mỗi chi nhánh **một** profile đang bật)
- [ ] `company`, `warehouse`, `selling_price_list` (phải có `MYPOS Menu` cùng Price List), `currency`
- [ ] **`branch`** (bắt buộc khi profile đang bật)
- [ ] `custom_walk_in_customer` — Khách vãng lai (Customer không SĐT, không Loyalty Program; `pos_profile.md` §5)
- [ ] Payments: mode tiền mặt + mode chuyển khoản (`type = Bank`, có tài khoản)
- [ ] `income_account` (phụ thu topping; trống → `Company.default_income_account`)
- [ ] Applicable for Users: mọi thu ngân + quản lý bán hàng; mỗi user `default` ở đúng một profile

**Dữ liệu theo chi nhánh / profile**
- [ ] `MYPOS Buzzer` (thẻ bàn) gắn Branch
- [ ] `MYPOS Order QR` gắn Branch (in mã QR từ form)
- [ ] `MYPOS Menu` theo Price List của profile
- [ ] `MYPOS Banner` (trống `pos_profile` = mọi profile) — **ảnh phải là file public** (bỏ chọn "Is Private"): ảnh private không hiện ở
      `/order`; ngang 16:9 (`customer_display.md` §4)
- [ ] User Permission `POS Profile` cho từng quản lý (nếu nhiều chi nhánh)

Kiểm nhanh (bench console, chỉ đọc):
`frappe.get_all("POS Profile", fields=["name", "branch", "disabled", "custom_walk_in_customer", "selling_price_list"])`
