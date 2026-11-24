# Module Rules: Màn hình khách (/pos/customer) + MYPOS Banner

> Paths: `leescoffee_pos/leescoffee_pos/api/customer_display_api.py`, `doctype/mypos_banner/`,
> `pos/src/pages/CustomerDisplay.tsx`, `pos/src/components/customer/BannerCarousel.tsx`, `pos/src/lib/realtime.ts`,
> `www/pos.py` + `www/pos.html` (`POS_CONFIG.realtime`). Làm 2026-11-24 — **ĐÃ TEST PASS trên bench DEV** (`d13b37c`, `4d06ddd`).
> Kiểm tra: `.claude/docs/customer_display_check.py` (`check_customer_display(pos_profile, <mã VARIANT>, mode, price_list)`).

## 1. Quy tắc

- Màn khách **chỉ hiển thị**: không nút / input / link (chạm lần đầu chỉ để bật toàn màn hình). Quyết định Van: chạy trên
  **thiết bị riêng**, đăng nhập **cùng tài khoản thu ngân**; POS Profile theo `resolve_pos_profile_name()`.
- Mỗi lúc một đơn: đơn mà thu ngân đang thao tác. Không hardcode thương hiệu: logo / tên từ Branch, ảnh từ `MYPOS Banner`.
- **Tiền luôn do server tính**: giỏ = kết quả `_pricing_preview` (CTKM theo tổng qty, phụ thu topping, đổi điểm); đơn đã tạo =
  đọc lại POS Invoice. "Phải thu" = `rounded_total or grand_total`, Paid → 0. Frontend không tự cộng tiền.
- Hiển thị: "Tạm tính" = giá gốc + phụ thu; "Khuyến mãi" = `total_discount_rules`; "Đổi N điểm" = `loyalty_discount`; Tổng cộng.
  Thành tiền dòng đã gồm phụ thu. Khách vãng lai → "Khách lẻ" (cờ `is_walk_in`), không lộ tên Customer.

## 2. Trạng thái (Redis cache `mypos_cdisplay:<user>`, TTL 12 giờ)

`{v (mốc ms), phase: idle|cart|order|qr|paid, pos_profile, invoice?, cart?, qr?, paid_at?}`

| Sự kiện | Nơi ghi | phase |
|---|---|---|
| Sửa giỏ | `pos_api.preview_pricing(display=1)` → `touch_cart` (không thêm request, frontend POS gửi `display: 1`) | cart |
| Giỏ về rỗng | `set_customer_display("idle")` — chỉ áp khi đang `cart`/`idle` (không xóa đơn vừa tạo) | idle |
| Tạo đơn | `create_draft_order` → `touch_order` (sau commit) | order |
| Chọn đơn Draft ở Orders | `set_customer_display("order", invoice)` — đơn cùng POS Profile, docstatus 0, không trả hàng; bỏ qua đơn QR | order |
| Sinh QR | `pos_api.generate_qr` → `touch_order(qr=...)` | qr |
| Paid (tiền mặt / webhook) | hook `on_submit` → `touch_paid`: chỉ user (owner / người thao tác) đang hiện đúng đơn | paid |
| Hủy Draft (tay / job) | `order_cancel.cancel_draft` → `touch_cancelled` | idle |

- Điểm móc bọc `_safe` (lỗi chỉ Error Log, không chặn bán hàng / thanh toán); ghi từ hook đi qua `frappe.db.after_commit`
  (cache không theo giao dịch: tránh báo Paid khi submit bị rollback).
- Web đặt món QR (`customer_order_api`) dùng hàm nội bộ, **không** đi qua các điểm móc → không làm nhảy màn khách.
- `get_customer_display_state(since)`: `since == v` → `{v, unchanged}` (chỉ đọc cache). State khác POS Profile hiện tại → idle.

## 3. Realtime

- `frappe.publish_realtime("mypos_customer_display", {"v"}, user=<user>)`; màn khách nghe qua `socket.io-client`
  (namespace `/<site>`, path `/socket.io`, cookie phiên). dev server → cổng `socketio_port`, production → cùng origin.
- Poll dự phòng 3 giây (`order/poll.ts::usePolling`); socket lỗi vẫn đúng, chỉ chậm tối đa 3 giây.
- [Unverified] Phần kết nối socket chưa kiểm riêng trên v16 (test Pass có thể đến từ poll). Cần tiến trình `socketio` của bench.
- `pos/package.json` có `socket.io-client`: sau khi copy phải `npm install` trong `pos/` rồi mới `npm run build`.

## 4. MYPOS Banner

- Field: `title`, `image` (Attach Image), `enabled`, `sort_order`, `pos_profile` (**trống = mọi POS Profile**, quyết định Van),
  `valid_from` / `valid_upto`, `description` (nội bộ). Lọc: enabled + profile + hiệu lực; sắp `sort_order`, rồi `creation`.
- `validate`: hiệu lực từ > đến → chặn; ảnh private → cảnh báo (không chặn).
- Quyền: MANAGER S R W C, CASHIER R, KITCHEN không (patch `v1_create_pos_roles` `#2026-11-24 mypos-banner`). Không dữ liệu mẫu.
- Hướng dẫn ảnh: ngang 16:9 (khuyến nghị 1920×1080, ≤ 500 KB, JPG/WebP), file public. Ở trang 1 banner chiếm ~2/3 trái,
  ảnh cắt theo khung (`object-fit: cover`) → để nội dung chính ở giữa ảnh.

## 5. Hằng số (một nơi)

`BANNER_SECONDS = 5` (BannerCarousel), `PAID_HOLD_SECONDS = 5`, `POLL_SECONDS = 3`, `CONFIG_REFRESH_MINUTES = 5` (CustomerDisplay),
`STATE_TTL_SECONDS = 12 giờ` (customer_display_api).

## 6. Tồn đọng

- Màn khách chưa có số thẻ bàn / loại đơn; chưa có âm thanh khi thanh toán xong.
- QR dựng theo `grand_total`, "phải thu" theo `rounded_total or grand_total` (lệch có sẵn, `order-qr.md` §7).
