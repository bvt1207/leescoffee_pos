# CLAUDE.md — app MYPOS

Đọc trước khi sửa code trong repo này.

- Sản phẩm: POS F&B dùng chung (white-label) trên ERPNext v16. **Không hardcode** tên quán, logo, màu thương hiệu: mọi thông tin
  thương hiệu đọc từ `Branch` (chi nhánh của `POS Profile.branch`).
- Kiến trúc, cấu trúc thư mục, mục lục quy tắc: [docs/README.md](docs/README.md).
- Quy ước code (tên DocType / field, module `MYPOS`, checklist DocType JSON, hook, import path `mypos.mypos.*`): [docs/code-standards.md](docs/code-standards.md).
- Quy tắc nghiệp vụ từng phần: `docs/rules/*.md` — đọc file tương ứng trước khi sửa phần đó.
- Cài / cấu hình: [docs/install.md](docs/install.md); triển khai: [docs/deploy.md](docs/deploy.md); script tự kiểm: [docs/testing.md](docs/testing.md).

Nguyên tắc không được vi phạm:

1. Giữ nguyên DocType lõi ERPNext; giao dịch là `POS Invoice`. Chỉ mở rộng bằng DocType `MYPOS *` (module `MYPOS`) hoặc Custom Field
   trên DocType chuẩn (khai báo trong `fixtures` của `hooks.py`, file trong `mypos/fixtures/`).
2. Trạng thái pha chế ở `custom_kitchen_status`, chỉ đặt khi `POS Invoice.status == "Paid"`; không đụng field `status` gốc.
3. Quyền của 3 role MYPOS: CHỈ ở `mypos/setup/roles.py` (`PERMS`), không dùng fixture Custom DocPerm.
4. Code ghi `POS Invoice` bằng `set_value` / SQL phải gọi `change_feed.bump(pos_profile)` (`docs/rules/realtime.md`).
5. Thay đổi cần chạy trên site đang có dữ liệu → viết patch mới trong `mypos/patches/` + `patches.txt`; thiết lập cho site cài mới →
   `mypos/setup/install.py` (`install-app` không chạy patch).
6. Không commit secret (API key SePay, `site_config.json`), không commit output build (`mypos/public/pos`, `mypos/public/order`).
7. Desk dùng màn **Apps** (mặc định Frappe 16.61): ô MYPOS qua hook `add_to_apps_screen` (không khai `route`; điểm đến = mục đầu tiên của
   Sidebar "MYPOS" sau lọc quyền, Sidebar xếp Admin, Manager, Cashier, Kitchen). Không dựa vào lưới Desktop Icon (Frappe đang loại bỏ).

## Trạng thái (2026-11-27)

- Chạy trên frappe / erpnext **16.61.0** (yêu cầu `>=16.50, <17`, không cần HRMS). Bộ selfcheck **23/23 PASS** (2026-11-28, thêm `payment_mode_check`; trước 22/22) trên site mới
  (`mypos.selfcheck.check_everything.check_everything`), gồm 16 test ghi dữ liệu chạy trên "quán thử" `ZZTEST-*` tự dựng / tự dọn.
- Sửa cho ERPNext 16.61: tự mở ca điền `balance_details` (`docs/rules/roles.md` §2b); giữ CTKM theo tổng qty mỗi mã khi lưu đơn bằng hook
  `validate` của POS Invoice (`docs/rules/options.md` §7).
- 2026-11-28: Mode of Payment CHỈ lấy từ bảng Payments của POS Profile (Default trước, rồi thứ tự dòng; tiền mặt = mode Cash,
  QR / webhook / `/order` = mode Bank của profile; thiếu -> lỗi rõ); `get_menu_items` mặc định theo Price List bán của profile
  (`docs/rules/pos_profile.md` §1b, `docs/rules/menu.md` §6).
- 2026-11-28: webhook SePay chỉ nhận chữ ký **HMAC-SHA256** (`X-SePay-Signature` / `X-SePay-Timestamp`, secret ở
  `Branch.sepay_webhook_secret`; bỏ `Authorization: Apikey` / `?key=` vì Frappe 16.61 trả 401 cho header đó), chống phát lại; thêm
  `sepay_hmac_check` → 24 test (`docs/rules/sepay.md` §1). Cần migrate (Custom Field mới).
- Tồn đọng đã biết: MYPOS Menu tra giá cố định VND (`docs/rules/menu.md` §2); role POS DISPLAY cho TV `/pos/status` (`docs/rules/order_status.md` §6);
  sửa dòng rồi Submit thẳng trên Desk (không Save) có thể bị ERPNext tính CTKM theo dòng (`docs/rules/options.md` §7).

## Sau mỗi thay đổi

1. `python -m py_compile` các file sửa; JSON hợp lệ; frontend: `cd pos && npx tsc --noEmit -p . && npm run build`.
2. Trên bench: `bench --site <site> migrate` nếu đổi DocType / fixtures / workspace / sidebar; khởi động lại bench nếu đổi Python / hooks.
3. `bench --site <site> execute mypos.selfcheck.check_everything.check_everything` → bảng PASS / FAIL / SKIP; dọn dữ liệu thử còn sót:
   `zz_test_shop` (`docs/testing.md` §7). Kiểm tay: `docs/checklist.md`.
4. Thêm quy tắc nghiệp vụ mới → cập nhật `docs/rules/*.md` và selfcheck tương ứng (test cũ lệch quy tắc mới phải sửa cùng lúc).
