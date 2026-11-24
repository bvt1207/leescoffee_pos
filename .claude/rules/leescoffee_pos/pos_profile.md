# Module Rules: Khách vãng lai theo POS Profile

> Paths: `leescoffee_pos/leescoffee_pos/doctype/pos_profile_hooks/pos_profile_hooks.py` (nguồn DUY NHẤT đọc field),
> `fixtures/custom_field.json` (`POS Profile-custom_walk_in_customer`), `public/js/pos_profile.js`,
> `patches/v1_walk_in_customer.py`, `api/pos_api.py`, `api/customer_order_api.py` (`_find_customer`).
> Làm 2026-11-24 — **chưa test trên bench**. Kiểm tra: `.claude/docs/walk_in_customer_check.py` (`check_walk_in_customer(...)`).

## 1. Quy tắc

- Custom Field `POS Profile.custom_walk_in_customer` ("Khách vãng lai", Link → Customer, sau `branch`, không bắt buộc ở DocType).
- Người cấu hình **tự tạo Customer** rồi chọn vào field. Code **không tự tạo** Customer, **không có tên Customer cố định** nào
  (chuỗi "Walk-in Customer" chỉ còn trong patch di trú `v1_walk_in_customer`). Nhiều profile được dùng chung một Customer.
- Field chuẩn `POS Profile.customer` của ERPNext (khách mặc định của màn POS gốc) **không được đọc**; `get_pos_config` vẫn trả khóa `customer` cũ.
- Đơn tại quầy không chọn khách (`create_draft_order`, `preview_pricing` qua `_resolve_customer(profile, customer)`) → khách vãng lai của
  POS Profile; chưa cấu hình → lỗi "POS Profile chưa cấu hình Khách vãng lai. Vui lòng nhờ quản lý cấu hình." (`WALK_IN_MISSING_MSG`).
  Chọn khách thật thì vẫn tạo đơn được.

## 2. Validate khi lưu POS Profile (`doc_events["POS Profile"]["validate"]`)

| Điều kiện | Mức |
|---|---|
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

## 6. Patch `v1_walk_in_customer` (post_model_sync)

- Tự tạo Custom Field nếu cột chưa có (fixture nạp SAU patch post_model_sync; cùng định nghĩa, fixture ghi đè y nguyên).
- Profile đang trống: gán Customer "Walk-in Customer" nếu tồn tại, không disabled, không Loyalty Program; ngược lại để trống + in + Error Log
  "Leescoffee POS: POS Profile thiếu Khách vãng lai" liệt kê profile. Không tạo Customer, không sửa hóa đơn. Idempotent.
