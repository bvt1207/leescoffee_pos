# Module Rules: Màn theo dõi đơn cho khách (/pos/status, treo TV)

> Paths: `leescoffee_pos/leescoffee_pos/api/order_status_api.py`, `pos/src/pages/OrderStatus.tsx`,
> `pos/src/components/status/StatusColumn.tsx`, `pos/src/styles/status-board.css`, `pos/src/main.tsx` (render độc lập),
> `pos/src/lib/api.ts` (`getOrderStatus*`), `pos/src/lib/changes.ts` (export `REALTIME_EVENT`).
> Làm 2026-11-27 — **CHỜ TEST** trên bench DEV. Kiểm tra: `.claude/docs/order_status_check.py` (`check_order_status(...)`).
> Treo TV: `.claude/docs/deploy.md` §4.

## 1. Quy tắc

- **Chỉ đọc**: không nút, không âm thanh, không link. Click / chạm không làm gì (trừ ô chọn POS Profile của quản lý).
- Route `/pos/status` qua rule `/pos/<path:app_path>` sẵn có; `main.tsx` render độc lập như `/pos/customer` (không AppHeader /
  PosProvider / toast thu ngân / hàng chờ). Chưa đăng nhập → `www/pos.py` chặn Guest, giống `/pos/kitchen`.
- Không đụng logic pha chế, thẻ bàn, thông báo thu ngân, màn khách, `/order`. Hàm cũ `get_status_board_orders` / `get_status_board`
  để nguyên (tồn đọng §6).

## 2. Điều kiện đơn (bám màn Pha chế `get_kitchen_orders`)

`docstatus = 1`, `status = "Paid"`, `pos_profile` = profile đang hiện, và:

| Cột | `custom_kitchen_status` | Sắp xếp (cũ nhất ở trên) |
|---|---|---|
| Trái "Đang chuẩn bị" | Chưa làm | `creation` (khớp thứ tự màn Pha chế) |
| Phải "Sẵn sàng nhận món" | Đã làm | `kitchen_done_at` (lúc bấm "Đã làm"), thiếu → `creation` (quyết định Van Q1) |

Không hiện: Đã hoàn thành, Khách không nhận, Không thực hiện được, Cancelled (docstatus 2), Draft, trả hàng (`status = Return`),
đơn đã gộp khi đóng ca (Consolidated — màn Pha chế cũng không hiện). Không thêm trường thời điểm thanh toán.

## 3. Quyền và POS Profile (`_resolve_profile`)

- Role POS bất kỳ (`_require_pos_role`): Cashier / Kitchen → `resolve_pos_profile_name(require_membership=True)` — cùng hàm và cùng lỗi
  `NO_PROFILE_MEMBERSHIP_MSG` với màn Pha chế; `pos_profile` client gửi bị **bỏ qua**.
- Quản lý (`_pos_roles().manager`: POS MANAGER / System Manager / Administrator): gửi `pos_profile` → kiểm tồn tại + đang bật; không gửi →
  `resolve_pos_profile_name()`. Config trả `profiles` (mọi profile đang bật); giao diện hiện ô chọn khi ≥ 2 profile, nhớ ở
  `localStorage["mypos_status_profile"]`, ô ẩn cùng con trỏ.
- Tài khoản treo TV: POS KITCHEN riêng (quyết định Van Q2-a). Về kỹ thuật vẫn gọi được API "Chưa làm → Đã làm" → chưa phải tài khoản chỉ đọc
  tuyệt đối; role POS DISPLAY ghi ở tồn đọng.

## 4. Dữ liệu trả (rút gọn ở SERVER)

| API (`order_status_api`) | Trả về | Khi gọi |
|---|---|---|
| `get_order_status_config(pos_profile)` | `{profile, profiles, brand: {name, logo}}` (brand từ Branch của profile, không phone / address) | mở màn, đổi profile, mỗi 5 phút |
| `get_order_status_changes(pos_profile)` | `{profile, v}` — chỉ đọc Redis + cache profile (`STATUS_CACHE_PREFIX`) | poll phiên bản |
| `get_order_status_board(pos_profile)` | `{profile, v, preparing[], ready[], more: {preparing, ready}}` | mở, khi `v` đổi, lưới an toàn |

- Mỗi dòng **chỉ** `{code, name, label, at}`. Không có tên hóa đơn đầy đủ, mã / tên đầy đủ / SĐT khách, tiền, món, ghi chú.
- `code` = `short_order_code`: cùng quy tắc `shortOrderNo` (cụm số cuối, "#00088") của tem ly / Pha chế / toast thu ngân.
- `name` = `short_call_name(customer_name)`: từ cuối của tên, giữ dấu, cắt `NAME_MAX = 12` ký tự (+ "…"); "" khi tên trống, từ cuối có
  ≥ `NAME_DIGIT_LIMIT = 4` chữ số (tránh lộ SĐT), hoặc khách vãng lai của profile (`walk_in_by_profile`) → TV chỉ hiện mã.
- `label`: "Mang đi" / "Tại quán" / "Thẻ bàn {số}" (Dine In có thẻ; số qua `_set_buzzer_numbers`, một truy vấn).
- Mỗi cột tối đa `MAX_ROWS = 60` dòng chi tiết; phần vượt chỉ trả số đếm `more`.
- Cache profile cho poll: khóa `mypos_user_profile:status:<user>:<profile chọn>` 300 giây — cùng tiền tố `change_feed.PROFILE_CACHE_PREFIX`
  nên lưu / xóa POS Profile (`clear_profile_cache`) xóa luôn.

## 5. Cập nhật + hiển thị (`OrderStatus.tsx`)

- Dùng lại cơ chế phiên bản (`realtime.md`): nghe `mypos_pos_changed` {p, v} (lọc `p` = profile đang hiện), poll `get_order_status_changes`
  `CHANGE_POLL_MS` (4 giây) khi không có socket / `REALTIME_POLL_MS` (30 giây) khi có; tải danh sách chỉ khi `v` khác lần tải trước.
- **Lưới an toàn** `STATUS_SAFETY_REFRESH_MS = 60000` (quyết định Van Q3, cấu hình ở đầu `OrderStatus.tsx`): tải lại dù `v` không đổi — bắt thay
  đổi không đi qua hook (vd. [Inference] ERPNext gộp đơn khi đóng ca bằng SQL / `set_value`, không tăng phiên bản).
- Tab hiện lại / có mạng lại (`online`) / socket nối lại → tải ngay một lần. Lỗi → giữ danh sách cuối, poll giãn tối đa 30 giây.
- Chấm trạng thái góc phải: xanh = socket kết nối, lần gọi gần nhất OK; vàng = không socket (đang poll) hoặc lỗi < 30 giây; đỏ = lỗi liên tục
  ≥ `STALE_AFTER_MS` (30 giây).
- Số request / phút khi KHÔNG có thay đổi: không socket 15 (`changes`, chỉ Redis) + 1 (lưới an toàn) = 16; có socket 2 + 1 = 3.
  Có thay đổi: thêm đúng 1 `get_order_status_board`. Config: 1 mỗi 5 phút.
- Không cuộn: mỗi cột 3 bậc chiều cao dòng (`ROW_VH` trong `StatusColumn.tsx`, khớp `.pos-sb-col--t0/1/2` trong CSS); chọn bậc lớn nhất chứa
  hết; bậc nhỏ nhất (mã ≈ 40px ở 1080p) vẫn không đủ → hiện vừa chỗ + "+ N đơn nữa". Cột phải rộng 55%, chữ lớn hơn, nền `--pos-primary`.
- Chuyển động ≤ 300ms: dòng mới hiện dần, dòng đổi chỗ / sang cột kia trượt (FLIP, Web Animations), dòng rời màn mờ dần 260ms;
  `prefers-reduced-motion` → không hiệu ứng. Con trỏ ẩn sau 3 giây không di chuột (`CURSOR_HIDE_MS`).

## 6. Tồn đọng

- Role **POS DISPLAY** chỉ xem `/pos/status` (Q2-b): cần fixture `role.json` + patch quyền + migrate.
- `pos_invoice_hooks.get_status_board_orders` / `pos_api.get_status_board` (cũ): trả tên khách đầy đủ, không lọc POS Profile, không kiểm role.
  Frontend không còn nơi gọi (chỉ khai báo `api.getStatusBoard` trong `lib/api.ts`). Nên bỏ hoặc chuyển sang `order_status_api` ở task sau.
- Chưa có banner / âm thanh (ngoài phạm vi).
