# Module Rules: Web đặt món QR cho khách (/order/<token>)

> Paths: `leescoffee_pos/leescoffee_pos/api/customer_order_api.py` (API khách + job dọn đơn),
> `doctype/mypos_order_qr/` (mã QR), `doctype/sepay/sepay.py` (`_verify_sepay_key`),
> `api/pos_api.py` (`_pricing_preview` dùng chung), `hooks.py` (`scheduler_events`),
> `fixtures/custom_field.json` (`order_channel` thêm `QR`, `qr_source`, `guest_session`).
> Giai đoạn 1 (backend) làm 2026-11-14, **đã test Pass** (self-test 65/65; `d64e1d7`, `948d1bc`, `99fdf30`, `17b5d85`, `fa4844e`). Giai đoạn 2 (frontend `/order`) làm 2026-11-14 (§8): "Đơn của tôi" theo khách + giỏ localStorage **đã test Pass** (`4e9629b`, `fbbc4ac`); phần còn lại chờ test.
> Self-test bench console: `.claude/docs/order_qr_selftest.py`; lịch sử đơn theo khách + giỏ: `.claude/docs/order_history_selftest.py`
> (`run_order_history_selftest()`, tự gọi lại bộ cũ).

## 1. Luồng

1. Admin tạo `MYPOS Order QR` (Desk): chọn Branch → `token` tự sinh (`secrets.token_urlsafe(18)`, 24 ký tự,
   không sửa được), `order_url = get_url("/order/<token>")`, nút "In mã QR" (SVG qua `pyqrcode` có sẵn của
   Frappe; không có thì chỉ hiện URL). Thu hồi: bỏ chọn `enabled` (chặn cả phiên đang mở).
2. Khách quét → `get_shop(qr_token)` (thương hiệu từ Branch, `is_open`) → `login(qr_token, mobile, customer_name)`.
3. `get_menu` → `preview` → `create_order(order_type)` → `create_payment_qr` → khách chuyển khoản
   → `sepay_webhook` (đã xác thực API key) submit đơn → hook `on_submit` đặt `Chưa làm` → Kitchen.
4. Khách poll `get_my_orders` (5 giây, chỉ khi còn đơn đang xử lý) / `get_order` (3 giây ở màn thanh toán): `stage` = `awaiting_payment` | `expired` | `queued`
   (Chưa làm) | `ready` (Đã làm → banner "mời đến quầy nhận") | `done`.

## 2. Quyết định đã chốt (Van, 2026-11-14)

| Chủ đề | Quy tắc |
|---|---|
| Kênh | `POS Invoice.order_channel = "QR"`, `qr_source` = mã QR, `guest_session` = sid phiên |
| Chi nhánh | Branch của mã QR → `pos_api._get_pos_profile(branch)` (không dùng user đăng nhập) |
| Menu | `Leescoffee Menu` có `price_list = POS Profile.selling_price_list` (Menu không có field branch). POS Profile thiếu Price List → không đặt được |
| Ca POS | Cần POS Opening Entry `Open` của POS Profile (bất kỳ thu ngân). Không có → "Quán chưa mở bán". Không tự mở ca |
| Owner đơn | Tạo đơn/sinh QR chạy dưới user của ca đang mở (`_as_user`), để POS Closing Entry gom được đơn (`pos_closing_entry.get_invoices` lọc `owner == user` — đã đọc mã ERPNext 17-dev; chỉ gom POS Invoice khi `POS Settings.invoice_type = "POS Invoice"`; self-test 9a/9b) |
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
- **Quyền xem đơn (2026-11-15)**:
  - `get_my_orders` lọc theo **khách** (`customer` của phiên) + **chi nhánh** (`qr_source` thuộc các mã QR của
    branch trong phiên) + `order_channel = QR`, không theo sid → đơn không mất khi Thoát / đăng nhập lại.
    - `active`: đơn Draft **còn hạn và đúng sid** của phiên hiện tại (đơn chờ thanh toán có `payment_code` chỉ
      phiên tạo ra nó thấy); đơn đã thanh toán Chưa làm/Đã làm trong `ACTIVE_PAID_HOURS = 24` giờ.
    - `history`: đơn đã thanh toán còn lại trong `HISTORY_DAYS = 30` ngày, tối đa `HISTORY_LIMIT = 30`, mới nhất trước
      (gồm Đã hoàn thành và đơn đã thanh toán quá 24 giờ chưa hoàn thành). Không trả đơn trả hàng, Draft hết hạn/phiên khác.
    - Mỗi đơn có `group: active|history`; bản tối thiểu: mã đơn, giờ tạo, loại đơn, trạng thái, món + options, tổng tiền
      (`order_note`, `kitchen_status` để rỗng). Không bao giờ trả SĐT, mã Customer, `payment_code`, SePay, điểm chi tiết.
  - `get_order`, `create_payment_qr` vẫn theo **sid** (`_own_invoice`): chỉ phiên tạo đơn xem/sinh QR được.
  - Không thuộc phạm vi hoặc không tồn tại → cùng lỗi "Không tìm thấy đơn". Đăng nhập không trả mã Customer /
    tên đã lưu (hiện tên khách vừa nhập).
  - `cart_key` (login, get_me) = HMAC(khách + mã QR) rút gọn: khóa lưu giỏ ở localStorage, không lộ mã Customer/SĐT.
- **Dữ liệu trả khách**: không có API key, VA, POS Profile, tài khoản kế toán, tên Pricing Rule (chỉ `title`),
  `price_list`, warehouse. Client không chọn được warehouse/uom/rate.
- **Giới hạn tần suất** (`RATE_LIMITS`, bộ đếm Redis `mypos_rl:*`): get_shop 60/phút/IP; login 10/10 phút/IP
  và 5/10 phút/SĐT; tạo khách mới 3/giờ/IP; tạo đơn 6/10 phút/phiên + 20/10 phút/IP; sinh QR 20/10 phút/phiên;
  đọc 120/phút/phiên; `get_my_orders` thêm 60/phút/SĐT (`orders_mobile`, SĐT của Customer) + 300/phút/IP
  (`orders_ip`, rộng vì nhiều khách chung wifi quán). Tối đa `MAX_OPEN_DRAFTS = 2` đơn chờ thanh toán còn hạn mỗi phiên; ≤ 30 dòng, qty 1–20.
- **Chống dò**: token QR 144 bit; lỗi QR sai/tắt dùng chung một thông báo.
- **Webhook SePay** (`sepay._verify_sepay_key`): key nhận từ header `Authorization: Apikey <key>` **hoặc**
  `?key=<key>` trên URL webhook, so `Branch.sepay_api_key` của đơn bằng `hmac.compare_digest`. Sai/thiếu →
  403 + Error Log. Thêm chống xử lý lặp theo `transaction_ref`.
  [Unverified] Frappe có thể trả 401 trước khi vào hàm khi header `Authorization` có 2 phần với scheme lạ
  (`validate_auth`). Nếu SePay kiểu "API Key" bị 401 → cấu hình SePay "Không chứng thực" + URL
  `.../sepay_webhook?key=<key>` (key nằm trong URL: không chia sẻ URL, đổi key nếu lộ).

## 4. Hạn chế "không OTP" (ghi rõ trong báo cáo)

Ai biết SĐT của khách khác có thể đăng nhập thay họ: thấy **điểm + hạng** của khách đó, đặt đơn (phải tự trả
tiền) dưới tên họ — đơn tích điểm cho họ — và **từ 2026-11-15 xem được lịch sử đơn QR 30 ngày của họ tại chi nhánh
đó** (đánh đổi để đơn không mất khi đăng nhập lại). Không đổi được điểm, không thấy/không trả hộ đơn chờ thanh toán
của phiên khác.

Giảm thiểu: dữ liệu trả tối thiểu (không SĐT, mã Customer, `payment_code`, ghi chú, điểm chi tiết); giới hạn 30 ngày /
30 đơn / theo chi nhánh; rate limit đăng nhập 5 lần/10 phút/SĐT + 10/10 phút/IP và `get_my_orders` 60/phút/SĐT.

**Khi có OTP (SMS/Zalo)**: bắt OTP khi đăng nhập từ thiết bị mới → mới cho xem lịch sử + bật đổi điểm; có thể nới
lịch sử (> 30 ngày, nhiều chi nhánh). Trước đó: **chỉ bật đổi điểm khi có OTP.**

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
- Index: `get_my_orders` lọc `customer` + `order_channel` + `qr_source` + `creation`; [Unverified] cột `customer` của
  POS Invoice có index sẵn của ERPNext — kiểm bằng `SHOW INDEX FROM ``tabPOS Invoice``` nếu chậm.
- Hai lần đăng nhập cùng SĐT mới đồng thời có thể tạo 2 Customer (không khóa); tần suất đã giới hạn.
- QR SePay dựng theo `grand_total`, webhook so `rounded_total or grand_total` (lệch có sẵn, task_handoff §2).

## 8. Frontend `/order/<token>` (giai đoạn 2)

- **Route**: `hooks.website_route_rules` `/order/<path:app_path>` → trang `mypos_order`
  (`www/mypos_order.html` + `.py`). **Không đặt tên trang `order`**: ERPNext đã có `templates/pages/order`
  (dùng cho `/orders/<name>`). Shell có `<meta name="referrer" content="no-referrer">` (token QR nằm trên URL,
  không lộ qua Referer khi tải ảnh VietQR bên ngoài) và `noindex`. CSRF token chỉ in khi trình duyệt đang đăng nhập Desk.
- **Build riêng**: `pos/vite.order.config.ts` → `public/order/order.js` + `order.css` (1 file js + 1 css cố định,
  `inlineDynamicImports`, `cssCodeSplit: false`, `publicDir: false`). `npm run build` build cả POS lẫn order;
  `build:order` / `dev:order` chỉ app khách. `public/order/` không commit (giống `public/pos/`).
- **Mã nguồn** `pos/src/order/`: `OrderApp.tsx` (điều phối), `api.ts` (client `customer_order_api`, lỗi
  `PermissionError` = phiên hết hạn → về đăng nhập), `session.ts` (localStorage `mypos_order_session:<qrToken>`),
  `cart.ts` (zustand, khóa dòng = item_code + options chuẩn hóa, qty ≤ 20), `alert.ts` (rung + bíp Web Audio,
  mở khóa ở lần chạm đầu), `format.ts`, `types.ts`, `order.css` (`.qo-*`, `@import ../styles/tokens.css`),
  `components/`: `LoginView`, `OrderTypePicker`, `MenuView`, `ItemSheet`, `CartSheet`, `PaymentView`,
  `MyOrdersPanel`, `ReadyBanner`, `Sheet`, `BrandHeader`.
- **Dùng lại**: `lib/options.ts` (defaultOptions, toggleOption, missingRequired, normalizeOptions,
  formatOptions/formatCartOptions), `lib/api.ts::extractError`, token `--pos-*` (tách ra `styles/tokens.css`,
  `global.css` `@import` lại). Không import component nhân viên (MenuGrid/CartPanel gắn store + API nhân viên).
- **Giỏ lưu localStorage (2026-11-15)**: `cart.ts` (`attachCartStorage`, `discardCart`, `pruneCart`), khóa
  `mypos_order_cart:<qrToken>:<cart_key>`, `{v, savedAt, lines, note}`. Khôi phục sau F5 / đóng-mở tab / đăng nhập
  lại cùng thiết bị. Xóa khi: Thoát chủ động, tạo đơn thành công, quá 12 giờ kể từ lần sửa cuối. Phiên hết hạn: chỉ
  bỏ khỏi bộ nhớ, giữ bản lưu. Nạp menu → bỏ dòng có món không còn trong menu (giá luôn do preview tính lại).
  Không lưu giỏ lên server. Phiên cũ chưa có `cartKey` → lấy từ `get_me`.
- **Đăng xuất / F5**: "Thoát" = `logout` (thu hồi sid) + xóa phiên + xóa giỏ đã lưu, không đụng đơn server.
  F5 / đóng tab không thu hồi phiên: token còn hạn trong `mypos_order_session:<qrToken>` tự đăng nhập lại.
- **"Đơn của tôi"**: `MyOrdersPanel` 2 vùng "Đang xử lý" / "Lịch sử (30 ngày)", mỗi vùng có trạng thái rỗng. Vào lại
  (F5 / đăng nhập) mà có đơn active → tự mở panel 1 lần. Banner sẵn sàng chỉ cho đơn `ready` thuộc nhóm active.
  Poll 5 giây chỉ khi có đơn active, tab hiện, không ở PaymentView.
- **Luồng**: get_shop → LoginView → chọn Mang đi/Tại quán (lưu trong phiên, đổi được ở giỏ) → MenuView (tab nhóm,
  tìm kiếm) → ItemSheet (size, chip option, số lượng) → CartSheet (preview trễ 400ms, CTKM, điểm/hạng, ghi chú)
  → create_order → PaymentView (create_payment_qr, đếm ngược theo `expires_in` của server, poll get_order 3 giây)
  → Paid → mở "Đơn của tôi".
- **Theo dõi**: OrderApp poll `get_my_orders` (điều kiện ở mục "Nhịp gọi API"). Đơn chuyển sang
  `ready` (pha chế bấm "Đã làm") → `ReadyBanner` + rung/bíp; "Đã hiểu" lưu mã đơn vào
  `mypos_order_ready_ack:<qrToken>` để không báo lại. Mở lại trang khi đơn đang `ready` chưa xác nhận → vẫn báo.
- **Nhịp gọi API (sửa hiệu năng 2026-11-14)**: mọi poll qua `order/poll.ts::usePolling` (1 chuỗi setTimeout, không
  chồng request, dừng khi tab ẩn, backoff ×2 tới 30 giây khi lỗi, abort khi unmount). `get_my_orders` poll 5 giây
  **chỉ khi** còn đơn `awaiting_payment`/`queued`/`ready` và không ở PaymentView; PaymentView poll `get_order` 3 giây,
  dừng khi hết hạn/đã trả. Preview: debounce 350ms theo khóa chuỗi `JSON(item_code, qty, options)` — ghi chú và loại
  đơn không gọi lại; AbortController bỏ kết quả cũ. `OrderApp` chỉ subscribe `lines` của giỏ (gõ ghi chú không render
  lại menu); `Sheet` không chạy lại effect focus mỗi render. Mọi API đọc dùng chung `read_session` 120/phút/phiên.
- **Backend thêm**: `expires_in` (giây còn lại) trong `_orders_payload` và `create_payment_qr` — client không phụ
  thuộc đồng hồ máy khách.
- **Màn nhân viên**: `ChannelChip` (`components/OrderTypeChip.tsx`, `.pos-tag--qr`, token `--pos-qr-*`) ở Orders
  (thẻ + chi tiết) và Kitchen; đơn QR không hiện "Thẻ #—" ở chi tiết Orders; hóa đơn / phiếu pha chế in
  "Kênh: QR · tên khách" thay dòng thẻ rung.
- **Tồn đọng**: chưa build/chạy thử trên máy dev (thư mục `pos/` chưa `npm install`, chỉ chạy `tsc` sạch);
  ảnh món là file private thì khách (Guest) không xem được — dùng ảnh public; Web Push khi đóng tab.
