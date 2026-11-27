# Checklist kiểm tay sau khi cài / cập nhật MYPOS

Làm SAU khi: cài (`install.md` §2), cấu hình tay (`install.md` §3), script đọc-chỉ PASS (`testing.md`).
Mỗi tài khoản dùng một cửa sổ ẩn danh riêng. `<SITE_URL>` = địa chỉ mở site (vd. `http://localhost:8000`).
Ghi PASS / FAIL vào cột cuối; FAIL thì chép thông báo lỗi + mã đơn.

## A. Workspace, Desktop Icon, Sidebar theo role

Chi tiết: `deploy.md` §5. User test KHÔNG có role `Workspace Manager`.

| # | Tài khoản | Mong đợi | PASS / FAIL |
|---|---|---|---|
| A1 | Administrator | 4 Desktop Icon MYPOS (Cashier, Kitchen, Manager, Admin); sidebar MYPOS 4 mục, không có mục DocType lẻ | |
| A2 | POS MANAGER | Chỉ icon / workspace Manager; card Shift & Cash, Order Handling, Menu & Promotions, QR & Display | |
| A3 | POS CASHIER | Chỉ icon / workspace Cashier (Open MYPOS, Customer Display, Order Status, Shift) | |
| A4 | POS KITCHEN | Chỉ icon Kitchen → mở `/pos/kitchen`; mở `/pos` tự chuyển `/pos/kitchen` | |

## B. Bán hàng tại quầy

| # | Khu vực | Thao tác | Mong đợi | PASS / FAIL |
|---|---|---|---|---|
| B1 | Bán món | Cashier mở `/pos`, chọn món có tùy chọn (đường / đá / topping), Mang đi, không chọn khách, Tạo đơn | Tự chuyển Orders, mở sẵn đơn Draft; tổng = tổng ở giỏ (CTKM + phụ thu); khách hiện "Khách lẻ" | |
| B2 | Thanh toán tiền mặt | Orders → thu tiền mặt đơn B1 | Đơn Paid; Desk: `payment_status` = Đã thanh toán, Trạng thái pha chế = Chưa làm | |
| B3 | Kitchen | Tài khoản KITCHEN `/pos/kitchen`: đơn B2 ở tab Chưa làm → "Đã làm" | Đơn rời màn KITCHEN; máy Cashier: toast + chấm đỏ cạnh "Pha chế" (≤ 15 giây) | |
| B4 | Kết thúc đơn | Cashier → Pha chế, tab Đã làm → "Đã hoàn thành" | Đơn sang tab Đã hoàn thành, chấm đỏ giảm | |
| B5 | Thẻ bàn | Tại quán, chọn thẻ số 1, tạo đơn; đơn thứ hai chọn lại thẻ 1 | Đơn 2 bị chặn "Thẻ bàn số … đang giữ cho đơn …"; sau khi đơn 1 Đã hoàn thành (hoặc hủy) thẻ 1 chọn lại được | |
| B6 | Hủy đơn | Orders → Draft → Hủy, lý do "Đặt nhầm" | Đơn Cancelled, `custom_cancel_reason` = "Thủ công: Đặt nhầm"; thẻ bàn (nếu có) trả lại | |

## C. Thanh toán chuyển khoản + SePay giả lập

Cần Branch: `sepay_enabled`, `sepay_va_account`, `sepay_bank_code`, `sepay_api_key`.

| # | Thao tác | Mong đợi | PASS / FAIL |
|---|---|---|---|
| C1 | Tạo đơn Draft → "QR" ở Orders | Hiện VietQR; `payment_status` = Đang chờ; thẻ "Chờ QR"; Desk: đọc `payment_code`, `rounded_total` (hoặc `grand_total`) | |
| C2 | Gửi webhook giả (lệnh dưới) | Trả `success: true`; đơn Paid, `payment_status` = Đã thanh toán, Chưa làm | |
| C3 | Gửi lại đúng lệnh C2 | `already_processed: true`, đơn không đổi | |
| C4 | Gửi với key sai | HTTP 403, Error Log "SePay webhook: sai hoặc thiếu API key" | |

```bash
curl -s -X POST "<SITE_URL>/api/method/mypos.mypos.doctype.sepay.sepay.sepay_webhook" \
  -H "Content-Type: application/json" -H "Authorization: Apikey <sepay_api_key của Branch>" \
  -d '{"content": "<payment_code>", "transferAmount": <số tiền>, "id": "TEST-0001", "transferType": "in", "gateway": "TEST"}'
```

Bị 401 trước khi vào hàm (Frappe chặn header lạ) → bỏ header, thêm `?key=<sepay_api_key>` vào URL (`rules/order-qr.md` §3).

## D. Web đặt món QR `/order/<token>`

Cần: một ca đang mở của POS Profile chi nhánh; `MYPOS Order QR` của Branch; `host_name` đúng (`deploy.md` §3).

| # | Thao tác | Mong đợi | PASS / FAIL |
|---|---|---|---|
| D1 | Mở `order_url` của MYPOS Order QR (cửa sổ ẩn danh / điện thoại) | Logo + tên quán từ Branch, banner MYPOS Banner (nếu có) | |
| D2 | Đăng nhập SĐT + tên, chọn món, giỏ, Đặt món | Màn thanh toán: VietQR + đếm ngược 15 phút | |
| D3 | Webhook giả như C2 với `payment_code` của đơn QR | Điện thoại: đã thanh toán → "Đơn của tôi" Đang chuẩn bị; Orders / Kitchen có chip "QR" | |
| D4 | Kitchen "Đã làm" đơn QR | Điện thoại: banner "mời đến quầy nhận" + rung / bíp; Cashier KHÔNG nhận toast cho đơn QR | |
| D5 | Không có ca mở → mở lại `/order/<token>` | "Quán chưa mở bán" | |

## E. Màn hiển thị

| # | Khu vực | Thao tác | Mong đợi | PASS / FAIL |
|---|---|---|---|---|
| E1 | Customer Display | Cùng tài khoản Cashier, tab / máy khác mở `/pos/customer`; thêm món ở `/pos` | Màn khách hiện món + tổng (server tính); giỏ rỗng → banner | |
| E2 | Customer Display | Sinh QR cho đơn → thanh toán (tiền mặt hoặc C2) | Hiện VietQR → "Thanh toán thành công" (phải thu 0) → về banner | |
| E3 | `/pos/status` | Tài khoản TV (POS KITCHEN riêng) mở `/pos/status` | Cột trái Chưa làm, cột phải Đã làm; chỉ mã ngắn + tên rút gọn + món, không SĐT / tiền | |
| E4 | `/pos/status` | Đổi trạng thái ở màn Pha chế | TV đổi ≤ 1 giây (chấm xanh, socket) / ≤ 5 giây (chấm vàng) | |

## F. Đóng ca

| # | Thao tác | Mong đợi | PASS / FAIL |
|---|---|---|---|
| F1 | Còn Draft hoặc đơn Paid Chưa làm / Đã làm → POS Closing Entry, Submit | Bị chặn, liệt kê mã đơn theo nhóm | |
| F2 | Xử lý hết (hủy / Đã hoàn thành / "Xử lý đơn" trên Desk) → đóng ca lại | Submit được; POS Invoice của ca thành Consolidated, có Sales Invoice gộp | |
| F3 | Cashier B đóng ca của Cashier A | Bị chặn; POS MANAGER đóng thay được (comment "Đóng ca thay") | |

## G. Job nền

| # | Thao tác | Mong đợi | PASS / FAIL |
|---|---|---|---|
| G1 | `bench --site <site> scheduler status` | enabled (nếu không: `bench --site <site> enable-scheduler`) | |
| G2 | Đơn QR Draft không thanh toán, chờ > 20 phút | Tự Cancelled, lý do "Tự động (QR hết hạn): …" | |
