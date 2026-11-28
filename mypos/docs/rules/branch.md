# Module Rules: Branch — nguồn cấu hình duy nhất

> Paths: `mypos/mypos/doctype/branch_config/branch_config.py`,
> `mypos/mypos/api/pos_api.py` (`_get_pos_profile`, `get_pos_config`).
> Branch là nguồn cấu hình DUY NHẤT (thương hiệu, SePay, company); app không có DocType Settings riêng.

## 1. Field trên Branch (Custom Field, `fixtures/custom_field.json`)

| Nhóm | Field |
|------|-------|
| SePay | `sepay_enabled`, `sepay_webhook_secret` (Password, Secret HMAC webhook), `sepay_va_account`, `sepay_bank_code` |
| Thương hiệu | `brand_name`, `brand_logo`, `brand_phone`, `brand_address` (`brand_banner` đã bỏ 2026-11-25, §4) |
| Công ty | `company` (Link → Company, label "Công ty", không bắt buộc, `in_standard_filter`) |

- Không fallback sang bất kỳ DocType nào khác. Field rỗng → trả `""`.
- Đọc bằng `branch.get("<field>")` để không lỗi nếu Custom Field chưa migrate.

## 2. Xác định chi nhánh

- Có POS Invoice / POS Profile → `POS Profile.branch`.
- **Quy tắc 1 — POS Profile đang bật bắt buộc có Branch** (2026-11-25, ĐÃ TEST PASS `check_branch_profile` 19/19, `pos_profile_hooks._check_branch`): thiếu → chặn lưu
  ("… đang bật nhưng chưa gán Chi nhánh …"); profile đã tắt (`disabled = 1`) thì lưu được.
- **Quy tắc 2 — mỗi Branch tối đa MỘT POS Profile đang bật** (2026-11-25, cùng hàm): profile đang bật, có Branch, mà đã có profile
  khác đang bật cùng Branch → **chặn lưu**, thông báo nêu tên profile đang chiếm Branch + cách xử lý (tắt profile kia, chọn Branch khác,
  hoặc tắt profile này). Profile đã tắt lưu thoải mái, kể cả cùng Branch. Bật lại profile đã tắt cũng đi qua kiểm tra này.
  - **Lý do:** web QR `/order` chỉ biết **Branch** (`MYPOS Order QR` không có field POS Profile) → từ Branch phải ra đúng MỘT profile
    (kho, Price List / menu, ca, owner đơn để đóng ca gom đúng). Hai profile cùng Branch làm đơn QR rơi vào profile tùy ca đang mở.
  - Không đặt `reqd` trong fixture, không patch, không tự sửa dữ liệu: profile đang vi phạm chỉ bị chặn ở **lần lưu kế tiếp**.
    Kiểm tra trước (bench console, chỉ đọc):
    ``frappe.db.sql("select branch, group_concat(name) from `tabPOS Profile` where disabled = 0 group by branch having count(*) > 1")``
  - Self-test cần profile tạm cùng Branch với profile thật: đặt `prof.flags.mypos_allow_shared_branch = True` trong code
    (`mypos/selfcheck/*_check.py`); cờ không đặt được qua Desk / API.
  - **Mở rộng nhiều tầng sau này** (vd. nhiều quầy / khu vực trong một chi nhánh): thêm field `pos_profile` (Link) trên `MYPOS Order QR`
    để mỗi mã QR trỏ thẳng profile; `customer_order_api` lấy profile từ mã QR thay vì từ Branch; khi đó nới quy tắc 2 (cho nhiều
    profile đang bật cùng Branch nếu mọi mã QR của Branch đã chọn profile). Chưa làm.
- Không có (gọi `get_default_branch()` hoặc `_get_pos_profile()` không truyền branch) →
  `branch_config.resolve_pos_profile_name()` (2026-11-25):
  1. User nằm trong "Applicable for Users" của ít nhất một POS Profile **đang bật** → profile đầu tiên (`default = 1` trước, rồi tên
     A→Z). Profile đó thiếu `branch` → throw "POS Profile X của bạn chưa được gán chi nhánh…", **không** rơi sang profile khác
     (trước đây lặng lẽ dùng profile duy nhất có Branch — sai kho, giá, ca).
  2. User không thuộc profile đang bật nào (vd. Administrator / System Manager): đúng **một** POS Profile đang bật có `branch`.
  3. Còn lại → `frappe.throw`.
- `_get_pos_profile(branch_name)` (dùng cho web QR `customer_order_api._profile`) → `pos_api._branch_profile_name`: phòng thủ cho
  dữ liệu cũ vi phạm quy tắc 2 — chi nhánh có ≥ 2 profile đang bật → profile **đang mở ca** đầu tiên theo tên A→Z, không có thì profile
  đầu theo tên (trước đây `get_value` không sắp xếp). Một profile → không thêm truy vấn. Không có profile → throw.
- `pos_api.get_buzzers`: profile thiếu Branch → throw (không lọc rỗng = thẻ mọi chi nhánh).

## 3. Kiểm tra company

- `get_pos_config` trả thêm `warnings: [str]`. Nếu `Branch.company` có giá trị và khác
  `POS Profile.company` → thêm 1 cảnh báo + `frappe.log_error`. **Không throw** (hóa đơn dùng
  `POS Profile.company`, kế toán vẫn đúng; throw sẽ chặn cả màn /pos).
- Frontend hiện chưa hiển thị `warnings` (không sửa .tsx ở task này).

## 4. Banner: không còn ở Branch (2026-11-25)

- Custom Field `Branch.brand_banner` đã bỏ (không có trong fixture). `get_brand_info` / `get_branch_config` không còn khóa banner.
- Banner đầu trang `/order` (carousel) = **các MYPOS Banner public** của POS Profile chi nhánh, tối đa 8 (`mypos_banner.active_banners`,
  dùng chung bộ lọc với màn khách, `customer_display.md` §4). Ảnh private bị bỏ qua ở `/order` (khách là Guest).

## 5. Checklist cấu hình 1 cửa hàng (UAT)

**Branch**
- [ ] `company` (Công ty) = `POS Profile.company`
- [ ] `brand_name`, `brand_logo` (file **public**), `brand_phone`, `brand_address`
- [ ] `sepay_enabled` = 1, `sepay_va_account`, `sepay_bank_code`, `sepay_webhook_secret` (= Secret Key HMAC-SHA256 của webhook bên SePay, `sepay.md` §1; thiếu secret → webhook
      và đặt món QR không chạy)

**POS Profile** (mỗi chi nhánh **một** profile đang bật — bắt buộc, §2 quy tắc 2; profile thử nghiệm: tắt hoặc gán Branch test riêng)
- [ ] `company`, `warehouse`, `selling_price_list` (phải có `MYPOS Menu` cùng Price List), `currency`
- [ ] **`branch`** (bắt buộc khi profile đang bật)
- [ ] `custom_walk_in_customer` — Khách vãng lai (Customer không SĐT, không Loyalty Program; `pos_profile.md` §5)
- [ ] Payments: mode tiền mặt + mode chuyển khoản (`type = Bank`, có tài khoản)
- [ ] `income_account` (phụ thu topping; trống → `Company.default_income_account`)
- [ ] Applicable for Users: mọi thu ngân + quản lý bán hàng **+ mọi tài khoản pha chế (POS KITCHEN)**; mỗi user `default` ở đúng một profile
      (từ 2026-11-25 màn Pha chế chỉ hiện đơn của profile user thuộc về; pha chế không thuộc profile nào → lỗi "chưa thuộc POS Profile
      đang bật nào", `realtime.md` §4)

**Dữ liệu theo chi nhánh / profile**
- [ ] `MYPOS Buzzer` (thẻ bàn) gắn Branch
- [ ] `MYPOS Order QR` gắn Branch (in mã QR từ form)
- [ ] `MYPOS Menu` theo Price List của profile
- [ ] `MYPOS Banner` (trống `pos_profile` = mọi profile) — **ảnh phải là file public** (bỏ chọn "Is Private"): ảnh private không hiện ở
      `/order`; ngang 16:9 (`customer_display.md` §4)
- [ ] User Permission `POS Profile` cho từng quản lý (nếu nhiều chi nhánh)

Kiểm nhanh (bench console, chỉ đọc):
`frappe.get_all("POS Profile", fields=["name", "branch", "disabled", "custom_walk_in_customer", "selling_price_list"])`
