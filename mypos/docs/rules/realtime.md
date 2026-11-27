# Module Rules: Giảm tải poll — phiên bản thay đổi theo POS Profile (+ realtime giai đoạn 3)

> Paths: `doctype/pos_invoice_hooks/change_feed.py`, `api/pos_api.py` (`get_pos_changes`, `get_orders_shift`, `_set_buzzer_numbers`,
> `get_kitchen_orders`), `doctype/branch_config/branch_config.py` (`resolve_pos_profile_name(require_membership)`), `hooks.py` (`on_change`),
> `pos/src/lib/changes.ts`, `lib/serve.ts`, `pages/Kitchen.tsx`, `pages/Orders.tsx`, `components/BuzzerPicker.tsx`.
> Giai đoạn 1 + 2 làm 2026-11-25 — **ĐÃ TEST PASS trên bench DEV (`86b6cb2`)**. Kiểm tra: `mypos/selfcheck/poll_load_check.py` (`check_poll_load(...)`).
> Triển khai thật (socket.io, nginx, gunicorn): `mypos/selfcheck/deploy.md`.

## 1. Quy tắc

- Màn POS **không** tải lại danh sách theo nhịp cố định nữa. Server giữ **phiên bản thay đổi** mỗi POS Profile (Redis); client hỏi phiên bản
  (rẻ, chỉ đọc Redis) và **chỉ tải danh sách khi phiên bản đổi**, cộng lưới an toàn định kỳ.
- Không đổi nghiệp vụ: trạng thái pha chế, thẻ bàn, thông báo thu ngân, màn khách giữ nguyên. Ngoại lệ đã duyệt: D1 (§4).
- Không sót đơn: thiếu khóa Redis → khởi tạo số ngẫu nhiên → client thấy khác → tải lại; lỗi mạng → lưới an toàn vẫn chạy; tab hiện lại → hỏi ngay.

## 2. Server

- Khóa `mypos_chg:<pos_profile>` (theo site, không TTL). `change_feed.bump(profile)` = INCR **sau commit** (`frappe.db.after_commit`;
  rollback → không tăng). Self-test: `frappe.flags.mypos_chg_immediate = True` → tăng ngay.
- Nơi tăng:
  | Nguồn | Cách |
  |---|---|
  | POS Invoice: insert, save, submit, cancel, update_after_submit, `db_set` (vd. `_resolve_consolidated`, `on_submit` đặt Chưa làm) | doc_events `on_change` (Frappe v16.30 gọi ở cuối `run_post_save_methods` và trong `db_set`) |
  | Hủy Draft (`order_cancel.cancel_draft`, tay / job) | gọi `bump` trực tiếp (`set_value` không chạy hook) |
  | POS Opening Entry, POS Closing Entry | doc_events `on_change` (thông tin ca ở Orders) |
- Đổi dữ liệu bằng `frappe.db.set_value` / SQL ở nơi khác (vd. [Inference] ERPNext gộp đơn khi đóng ca) có thể không tăng → lưới an toàn
  (60 giây; hàng chờ thu ngân 120 giây). Code mới ghi POS Invoice bằng `set_value` / SQL **phải** gọi `change_feed.bump(pos_profile)`.
- `pos_api.get_pos_changes()` → `{profile, v}`: role POS bất kỳ; POS Profile của user lấy từ cache `mypos_user_profile:<user>` (300 giây,
  xóa khi lưu / xóa POS Profile: doc_events `on_update`, `on_trash`) → lần 2+ không truy vấn DB.
- `pos_api.get_orders_shift(limit)` → `{drafts, paid, summary}` (= 3 request cũ của Orders, Ca hiện tại).
- Số thẻ bàn: `_set_buzzer_numbers(rows)` một truy vấn cho cả danh sách (`get_orders`, `get_kitchen_orders`; trước: 1 truy vấn / đơn).

## 3. Client (`lib/changes.ts`)

- `useChangeFeedPoller` gắn một lần ở `App`: poll `get_pos_changes` với chu kỳ = nhỏ nhất của các màn đang đăng ký; không màn nào → không poll.
  `usePolling`: không chồng request, dừng khi tab ẩn, backoff khi lỗi (tối đa 30 giây).
- `usePosRefresh(load, {enabled, intervalMs, safetyMs, key})`: tải khi mở / đổi `key`, khi phiên bản đổi, và mỗi `safetyMs`; không chồng
  (đang chạy → chạy thêm đúng một lần).

| Màn | Trước | Sau (không socket) |
|---|---|---|
| Pha chế | `get_kitchen_orders` mỗi 5 giây | `get_pos_changes` mỗi **4 giây** (D3) + danh sách khi đổi + 60 giây |
| Orders, Ca hiện tại | 3 request mỗi 10 giây | `get_orders_shift` (1 request) khi đổi + 60 giây; chu kỳ phiên bản 4 giây |
| Orders, chi tiết đơn | `get_order_detail` mỗi 10 giây | khi đổi / chọn đơn + 60 giây |
| Hàng chờ thu ngân (CASHIER) | `get_serve_queue` mỗi 15 giây | phiên bản mỗi 15 giây (4 giây nếu đang ở Orders / Pha chế) + hàng chờ khi đổi + 120 giây |
| Chọn thẻ bàn (modal mở) | `get_buzzers` mỗi 5 giây | phiên bản 4 giây + `get_buzzers` khi đổi + 60 giây |
| Màn khách `/pos/customer`, `/order` | không đổi ở giai đoạn 1 + 2 | — |

Số request khi KHÔNG có thay đổi: Pha chế 12 → 15/phút nhưng là request đọc Redis thay cho truy vấn DB; thu ngân ở màn Bán 4 → 4/phút
(+ 0,5/phút lưới an toàn); Orders 18 → 15/phút (cũng chỉ đọc Redis). Có thay đổi: thêm đúng 1 request danh sách mỗi màn.

## 4. D1 — Pha chế chỉ đơn của POS Profile user thuộc về (chủ dự án, 2026-11-25)

- `get_kitchen_orders` lọc `pos_profile = resolve_pos_profile_name(require_membership=not manager)` (trước: mọi chi nhánh).
- User **không phải quản lý** không thuộc "Applicable for Users" của POS Profile đang bật nào → lỗi `NO_PROFILE_MEMBERSHIP_MSG`
  ("Tài khoản … chưa thuộc POS Profile đang bật nào (bảng "Applicable for Users") …"). `get_pos_config` báo cùng lỗi cho user **chỉ có**
  POS KITCHEN. Quản lý / Administrator: theo `resolve_pos_profile_name` thường (nhiều chi nhánh → phải thuộc một profile).
- Cấu hình: thêm mọi tài khoản pha chế vào Applicable for Users của profile chi nhánh (`branch.md` §5). KITCHEN vẫn không mở ca được
  (`pos_shift_hooks`), không có quyền DocType mới.

## 5. Giai đoạn 3 — realtime (2026-11-25, ĐÃ TEST PASS trên bench DEV `4fbb595`)

- `change_feed._incr` gọi thêm `frappe.publish_realtime("mypos_pos_changed", {"p": profile, "v": <phiên bản>}, room="all")` sau commit
  (D2-i: phòng `all` = mọi System User đang kết nối; payload KHÔNG có dữ liệu đơn / khách / tiền). Lỗi socket chỉ bỏ qua.
- `lib/changes.ts`: nghe sự kiện qua `lib/realtime.ts`, so `p` với profile của mình → đặt phiên bản mới ngay. Socket đang kết nối → poll phiên bản
  **30 giây**; mất kết nối → **4 giây**; `connect` lại → hỏi ngay. `realtime.ts` trả trạng thái kết nối.
- Màn khách: poll 30 giây khi socket kết nối, 3 giây khi không (`CustomerDisplay.tsx`, `REALTIME_POLL_SECONDS`).
- Code: `change_feed._publish` (room truyền rõ `get_site_room()`: trong job nền Frappe mặc định gửi vào phòng task), `lib/realtime.ts`
  (`onStatus` kết nối / mất kết nối), `lib/changes.ts` (`REALTIME_POLL_MS = 30000`, lọc `p` theo profile từ `get_pos_changes`).
- Kiểm: `check_poll_load` mục 2d (sự kiện, phòng, payload chỉ {p, v}).
- Ca kiểm: có socket (cập nhật ≤ 1 giây), tắt socketio (≤ 5 giây), restart, tab ẩn / hiện.

**Khi nào chuyển sang phòng theo POS Profile:** (a) một site phục vụ **nhiều doanh nghiệp khác nhau** (tên POS Profile của doanh nghiệp này
đến được user doanh nghiệp khác); hoặc (b) nhiều profile + tổng sự kiện lớn (ước lượng > ~50 profile hoặc > ~5 sự kiện/giây toàn site,
[Inference]) làm mỗi màn nhận phần lớn sự kiện thừa. Cách làm: publish với `doctype="POS Profile", docname=<profile>` (phòng
`doc:POS Profile/<profile>`); client `socket.emit("doc_subscribe", "POS Profile", profile)`; Frappe kiểm `frappe.has_permission` trước khi cho vào
phòng (`apps/frappe/realtime/handlers.js`, đã đọc v16.30) → KITCHEN cần quyền Read POS Profile (hiện không có, `roles.md` §2) hoặc app tự viết
handler phòng riêng (`apps/<app>/realtime/handlers.js`, nằm ngoài package trong repo này).

## 6. socket.io trên DEV (đã kiểm 2026-11-25)

- `bench start` (Procfile có `socketio: bench socketio`), node nghe **9001** (`socketio_port`), web có `DEV_SERVER=true` → client kết nối
  `http://<host trang>:9001/<site>`.
- Từ Windows: `127.0.0.1:9001` **không phản hồi**, `localhost:9001` / `[::1]:9001` OK (node nghe `::`, WSL2 chỉ chuyển cổng này qua IPv6
  loopback). → Mở site bằng **`http://localhost:8001`** (đăng nhập lại vì cookie theo host), hoặc bật `networkingMode=mirrored` trong `.wslconfig`.
- Kiểm (PowerShell): `curl.exe -s "http://localhost:9001/socket.io/?EIO=4&transport=polling"` → bắt đầu bằng `0{"sid":`. DevTools → Network → WS:
  `socket.io/?EIO=4&transport=websocket` trạng thái 101.
