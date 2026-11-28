# Module Rules: Khách vãng lai theo POS Profile

> Paths: `mypos/mypos/doctype/pos_profile_hooks/pos_profile_hooks.py` (nguồn DUY NHẤT đọc field),
> `fixtures/custom_field.json` (`POS Profile-custom_walk_in_customer`), `public/js/pos_profile.js`,
> `api/pos_api.py`, `api/customer_order_api.py` (`_find_customer`). **Không có patch**.
> Làm 2026-11-24 — **ĐÃ TEST PASS trên bench DEV** (`2d400c7`, `4c2f7cf`: bỏ patch tự gán). Kiểm tra: `mypos/selfcheck/walk_in_customer_check.py` (`check_walk_in_customer(...)`).

## 1. Quy tắc

- Custom Field `POS Profile.custom_walk_in_customer` ("Khách vãng lai", Link → Customer, sau `branch`, không bắt buộc ở DocType).
- Người cấu hình **tự tạo Customer** rồi chọn vào field. **Không patch / hook / seed / fixture nào tự điền giá trị** cho field
  (fixture `default: ""`), code không tự tạo Customer, không có tên Customer cố định nào. Nhiều profile được dùng chung một Customer.
- Self-test (`mypos/selfcheck/*_check.py`) tự tạo Customer tạm `ZZTEST WI ...` (gán cho profile tạm hoặc truyền rõ khi tạo đơn) và tự xóa.
- Field chuẩn `POS Profile.customer` của ERPNext (khách mặc định của màn POS gốc) **không được đọc**; `get_pos_config` vẫn trả khóa `customer` cũ.
- Đơn tại quầy không chọn khách (`create_draft_order`, `preview_pricing` qua `_resolve_customer(profile, customer)`) → khách vãng lai của
  POS Profile; chưa cấu hình → lỗi "POS Profile chưa cấu hình Khách vãng lai. Vui lòng nhờ quản lý cấu hình." (`WALK_IN_MISSING_MSG`).
  Chọn khách thật thì vẫn tạo đơn được.

## 1b. Mode of Payment theo POS Profile (2026-11-28)

- NGUỒN DUY NHẤT: bảng **Payments** của POS Profile (`pos_api._profile_payment_modes`). Thứ tự: dòng **Default** trước, rồi thứ tự dòng.
  Không lấy mode ngoài profile (kể cả "Cash" có sẵn của ERPNext), không sắp theo tên. Mode tắt / thiếu tài khoản cho công ty -> lỗi rõ.
- `get_pos_config.payment_modes` = mode của profile; `create_draft_order` / `preview_pricing` không truyền mode -> mode Default; truyền mode ngoài
  profile -> lỗi "không thuộc POS Profile".
- "Thu tiền mặt" (`pay_cash`): đặt dòng thanh toán = mode **Cash** đầu tiên của profile. Sinh QR / webhook SePay: mode **Bank** đầu tiên của
  profile (`set_invoice_payment_mode`). /order: `_transfer_mode` = mode Bank của profile. Ưu tiên giữa nhiều mode cùng loại = thứ tự dòng
  (white-label, không viết cứng tên mode). Profile thiếu mode loại cần -> lỗi rõ (/order: thông báo chung cho khách + Error Log).
- Lý do: trước đây mode lấy theo tên trên toàn công ty -> đơn mọi chi nhánh ghi "Cash" / "Cash - <abbr>" (lỗi thử bán 2026-11-28).
- Kiểm tra: `selfcheck/payment_mode_check.py` (`check_payment_modes`).

## 2. Validate khi lưu POS Profile (`doc_events["POS Profile"]["validate"]`)

| Điều kiện | Mức |
|---|---|
| Profile đang bật, `branch` trống (2026-11-25) | Chặn (`branch.md` §2) |
| Profile đang bật, Branch đã có profile khác đang bật (2026-11-25) | Chặn (`branch.md` §2 quy tắc 2); profile đã tắt thì lưu được |
| Customer không tồn tại | Chặn |
| Customer disabled | Chặn |
| Customer có Loyalty Program | Chặn (khách vãng lai không tích điểm) |
| Customer có `mobile_number` | Cảnh báo (msgprint) — vẫn lưu |

## 3. Cờ `is_walk_in` (server tính, giao diện không so tên Customer)

- Tính theo **POS Profile của chính đơn** (`mark_walk_in` / `is_walk_in` / `walk_in_by_profile`): `get_orders`, `get_order_detail`,
  `get_kitchen_orders` (đơn mọi profile), `get_serve_queue` (kèm `customer_name = ""`), `get_status_board_orders`.
- Khách vãng lai của profile B trên đơn của profile A → `is_walk_in = False` (là khách thường của đơn đó).
- Frontend: `lib/format.ts::customerLabel` → "Khách lẻ" (Orders thẻ + chi tiết, hóa đơn khách); tem ly in mã ngắn đơn; toast thu ngân
  dùng số bàn / mã ngắn (không đổi). `get_pos_config.profile.walk_in_configured = false` → banner ở /pos + chặn Tạo đơn khi chưa chọn khách.

## 4. Loyalty / tìm khách / QR

- `_loyalty_info(customer, company, total, walk_in)` → `None` cho khách vãng lai (không hiện điểm, không đổi điểm).
- `search_customers` loại khách vãng lai của **mọi** POS Profile.
- Web QR: `_find_customer` bỏ qua khách vãng lai; SĐT chỉ khớp khách vãng lai → lỗi (`order-qr.md` §2).
- Mở ca (`pos_shift_hooks.opening_before_validate`): profile chưa cấu hình → cảnh báo, **không chặn**.
- [Unverified] ERPNext "Auto Opt In" của Loyalty Program có thể tự gán chương trình cho Customer khi lập hóa đơn — script kiểm ca 5d.
- Đóng ca / gộp đơn: không sửa code. [Inference] ERPNext gộp theo Customer trong ca của một profile → mỗi profile có Sales Invoice riêng
  cho khách vãng lai của mình (kiểm tay).

## 5. Hướng dẫn admin

1. Customer → New: tên tùy ý (vd. "Khách lẻ - <chi nhánh>"), Customer Group `Individual`, **không** SĐT, **không** Loyalty Program.
2. POS Profile của chi nhánh → "Khách vãng lai" → chọn Customer vừa tạo → Save.
3. Kiểm: /pos không còn banner "chưa cấu hình Khách vãng lai"; tạo đơn không chọn khách được.

## 6. Migrate / bench mới

- Field chỉ đến từ fixture `custom_field.json` (nạp cuối migrate / khi install-app). Không có patch: không code nào chạy trong migrate
  đọc field (hook `validate` dùng `doc.get`, chỉ chạy khi lưu POS Profile; API chỉ chạy lúc dùng).
- Bench mới / UAT: sau migrate mọi POS Profile để trống → /pos chặn đơn không chọn khách cho tới khi cấu hình tay (§5).
- Liệt kê POS Profile chưa cấu hình (bench console, chỉ đọc):
  `frappe.get_all("POS Profile", filters=[["custom_walk_in_customer", "is", "not set"]], fields=["name", "branch", "disabled"])`
