# Module Rules: Web đặt món QR cho khách (/order/<token>)

> Paths: `leescoffee_pos/leescoffee_pos/api/customer_order_api.py` (API khách + job dọn đơn),
> `doctype/mypos_order_qr/` (mã QR), `doctype/sepay/sepay.py` (`_verify_sepay_key`),
> `api/pos_api.py` (`_pricing_preview` dùng chung), `hooks.py` (`scheduler_events`),
> `fixtures/custom_field.json` (`order_channel` thêm `QR`, `qr_source`, `guest_session`).
> Giai đoạn 1 (backend) làm 2026-11-14, **chưa test trên bench**. Giai đoạn 2 (frontend `/order`) chưa làm.
> Self-test bench console: `.claude/docs/order_qr_selftest.py`.

## 1. Luồng

1. Admin tạo `MYPOS Order QR` (Desk): chọn Branch → `token` tự sinh (`secrets.token_urlsafe(18)`, 24 ký tự,
   không sửa được), `order_url = get_url("/order/<token>")`, nút "In mã QR" (SVG qua `pyqrcode` có sẵn của
   Frappe; không có thì chỉ hiện URL). Thu hồi: bỏ chọn `enabled` (chặn cả phiên đang mở).
2. Khách quét → `get_shop(qr_token)` (thương hiệu từ Branch, `is_open`) → `login(qr_token, mobile, customer_name)`.
3. `get_menu` → `preview` → `create_order(order_type)` → `create_payment_qr` → khách chuyển khoản
   → `sepay_webhook` (đã xác thực API key) submit đơn → hook `on_submit` đặt `Chưa làm` → Kitchen.
4. Khách poll `get_my_orders` / `get_order` 5 giây: `stage` = `awaiting_payment` | `expired` | `queued`
   (Chưa làm) | `ready` (Đã làm → banner "mời đến quầy nhận") | `done`.

## 2. Quyết định đã chốt (Van, 2026-11-14)

| Chủ đề | Quy tắc |
|---|---|
| Kênh | `POS Invoice.order_channel = "QR"`, `qr_source` = mã QR, `guest_session` = sid phiên |
| Chi nhánh | Branch của mã QR → `pos_api._get_pos_profile(branch)` (không dùng user đăng nhập) |
| Menu | `Leescoffee Menu` có `price_list = POS Profile.selling_price_list` (Menu không có field branch). POS Profile thiếu Price List → không đặt được |
| Ca POS | Cần POS Opening Entry `Open` của POS Profile (bất kỳ thu ngân). Không có → "Quán chưa mở bán". Không tự mở ca |
| Owner đơn | Tạo đơn/sinh QR chạy dưới user của ca đang mở (`_as_user`), để POS Closing Entry gom được đơn (ERPNext lọc theo owner — [Unverified] cho v16, test 9a kiểm tra) |
| Thẻ rung | Đơn QR Dine In **không** có buzzer. Hook/`confirm_pickup` đã bỏ qua khi `buzzer` rỗng |
| Thanh toán | Chỉ chuyển khoản: Mode of Payment `type = Bank` có tài khoản (ưu tiên mode trong POS Profile). Branch phải bật SePay + VA + mã NH + **API key** |
| Hết hạn | Sau `PAY_WINDOW_MINUTES = 15`: khách không thấy/không sinh QR. Job xóa sau `DRAFT_DELETE_MINUTES = 60` (webhook chuyển khoản trễ vẫn khớp) |
| Loyalty | **Không đổi điểm** (`redeem_points > 0` → lỗi). Chỉ hiện điểm + hạng của chính khách. Tích điểm do ERPNext như đơn thường |
| Giá/CTKM/tùy chọn | Server tính lại bằng `_normalize_items`, `_build_invoice`, `_pricing_preview` (dùng chung với POS). Client chỉ gửi `item_code`, `qty`, `options` |

## 3. Mô hình bảo mật

- **Token phiên**: `base64url(payload).base64url(HMAC-SHA256)`; payload `{sid, c: customer, q: mã QR, b: branch,
  n: tên hiển thị, exp}`; khóa = SHA-256(`"mypos-guest-session|" + encryption_key` của site). Hạn 12 giờ
  (`SESSION_TTL_SECONDS`). Thu hồi: cache `mypos_guest_sid:<sid>` (logout xóa). Mỗi lần gọi kiểm tra: chữ ký,
  hạn, cache, mã QR còn bật + đúng branch, Customer còn bật. Sai → `PermissionError` "Phiên đặt món đã hết hạn".
  [Unverified] Xóa Redis cache (vd. restart redis) làm mọi khách phải đăng nhập lại.
- **Cô lập dữ liệu**: chỉ đọc đơn `guest_session = sid` + `order_channel = QR`. Không thuộc phiên hoặc không tồn
  tại → cùng lỗi "Không tìm thấy đơn". Đăng nhập không trả mã Customer / tên đã lưu (hiện tên khách vừa nhập).
- **Dữ liệu trả khách**: không có API key, VA, POS Profile, tài khoản kế toán, tên Pricing Rule (chỉ `title`),
  `price_list`, warehouse. Client không chọn được warehouse/uom/rate.
- **Giới hạn tần suất** (`RATE_LIMITS`, bộ đếm Redis `mypos_rl:*`): get_shop 60/phút/IP; login 10/10 phút/IP
  và 5/10 phút/SĐT; tạo khách mới 3/giờ/IP; tạo đơn 6/10 phút/phiên + 20/10 phút/IP; sinh QR 20/10 phút/phiên;
  đọc 120/phút/phiên. Tối đa `MAX_OPEN_DRAFTS = 2` đơn chờ thanh toán còn hạn mỗi phiên; ≤ 30 dòng, qty 1–20.
- **Chống dò**: token QR 144 bit; lỗi QR sai/tắt dùng chung một thông báo.
- **Webhook SePay** (`sepay._verify_sepay_key`): key nhận từ header `Authorization: Apikey <key>` **hoặc**
  `?key=<key>` trên URL webhook, so `Branch.sepay_api_key` của đơn bằng `hmac.compare_digest`. Sai/thiếu →
  403 + Error Log. Thêm chống xử lý lặp theo `transaction_ref`.
  [Unverified] Frappe có thể trả 401 trước khi vào hàm khi header `Authorization` có 2 phần với scheme lạ
  (`validate_auth`). Nếu SePay kiểu "API Key" bị 401 → cấu hình SePay "Không chứng thực" + URL
  `.../sepay_webhook?key=<key>` (key nằm trong URL: không chia sẻ URL, đổi key nếu lộ).

## 4. Hạn chế "không OTP" (ghi rõ trong báo cáo)

Ai biết SĐT của khách khác có thể đăng nhập thay họ: thấy **điểm + hạng** của khách đó và đặt đơn (phải tự trả
tiền) dưới tên họ — đơn tích điểm cho họ. Không thấy được đơn cũ của họ (chỉ đơn của phiên mình), không đổi
được điểm. **Bật đổi điểm chỉ khi có OTP.**

## 5. Job dọn đơn

`customer_order_api.cleanup_expired_qr_orders` (cron `*/5 * * * *`): `docstatus = 0`, `order_channel = QR`,
`creation` < now − 60 phút, `payment_status != "Đã thanh toán"`; đọc lại docstatus ngay trước khi xóa;
commit từng đơn; lỗi → rollback + Error Log. Idempotent. Không đụng đơn submit hay đơn kênh POS.

## 6. Màn nhân viên

- `get_orders`, `get_kitchen_orders` trả thêm `order_channel` (`get_order_detail` đã có) → giai đoạn 2 hiện chip "QR".
- Không đổi phân quyền. Thu ngân vẫn hủy được đơn QR Draft / thu tiền mặt ở Orders (nếu khách ra quầy).

## 7. Tồn đọng

- OTP (SMS/Zalo) → mở đổi điểm cho kênh QR.
- Web Push khi khách đóng tab (giai đoạn này chỉ poll khi tab mở).
- Khách chuyển khoản sau khi đơn đã bị xóa (> 60 phút) → webhook "không tìm thấy đơn" (Error Log), xử lý tay.
- Ca đóng giữa lúc đơn QR đang chờ: đơn Draft thuộc owner ca cũ; webhook vẫn submit được ([Unverified] ERPNext
  có chặn submit khi ca của owner đã đóng hay không — cần test trên bench).
- Hai lần đăng nhập cùng SĐT mới đồng thời có thể tạo 2 Customer (không khóa); tần suất đã giới hạn.
- QR SePay dựng theo `grand_total`, webhook so `rounded_total or grand_total` (lệch có sẵn, task_handoff §2).
