# Module Rules: Role & quyền POS

> Paths: `mypos/setup/roles.py` (bảng `ROLES`, `PERMS`),
> `mypos/fixtures/role.json`, `hooks.py` (`fixtures` Role, `after_install`).

## 1. Ba role của app

| Role | desk_access | Dùng cho |
|------|-------------|----------|
| `POS CASHIER` | 1 | Thu ngân: mở/đóng ca, /pos, Orders |
| `POS KITCHEN` | 1 | Pha chế: vào `/desk`, thấy icon "MYPOS Kitchen" → `/pos/kitchen` |
| `POS MANAGER` | 1 | Quản lý cửa hàng |

**KITCHEN `desk_access = 1` (quyết định chủ dự án, 2026-11-17):** để pha chế đăng nhập và vào màn Pha chế từ Desk
như các role khác. Quyền vẫn tối thiểu: chỉ Read `MYPOS Menu`, `MYPOS Buzzer`, `MYPOS Option Group` (§2); API bán
hàng bị chặn ở backend (§8). `role.json` + `ROLES` đặt sẵn 1.

Role ERPNext gán **kèm** cho user MANAGER (không tạo trong code, gán tay khi tạo user):
`Auditor`, `Sales User`, `Sales Manager`, `Stock User`.

## 2. Bảng quyền (permlevel 0; S=Select R=Read W=Write C=Create Sub=Submit)

Không cấp Cancel / Delete / Amend.

| DocType | CASHIER | KITCHEN | MANAGER |
|---------|---------|---------|---------|
| POS Opening Entry | S R W C Sub + Only If Creator | — | S R W C Sub |
| POS Closing Entry | S R W C Sub + Only If Creator | — | S R W C Sub |
| POS Profile | S R | — | S R W C |
| MYPOS Menu | R | R | S R W C |
| MYPOS Buzzer | R | R | S R W C |
| Account | R | — | S R W C |
| Customer | R | — | S R W C |
| Item | R | — | S R W C |
| POS Invoice | S R W C Sub | — | S R W C Sub + Report |
| POS Invoice Merge Log | S R W C Sub | — | S R W C Sub |
| Sales Invoice | S R W C Sub | — | S R W C Sub |
| Address | R | — | R W C |
| Contact | R | — | R W C |
| Branch | — | — | S R W C |
| MYPOS Option Group | R | R | R W C |
| MYPOS Order QR | R | — | S R W C |
| MYPOS Banner | R | — | S R W C |

Nguồn sự thật là `PERMS` trong patch; sửa bảng này thì sửa cả patch.

### 2b. Mở / đóng ca (2026-11-20) — ĐÃ TEST PASS trên bench DEV (`a97d530`, script `check_shift_owner` PASS sau `e8da9f1`)

- Quy tắc ở `doctype/pos_shift_hooks/pos_shift_hooks.py` (doc_events `before_validate`, `before_submit`, `on_submit` của
  `POS Opening Entry` và `POS Closing Entry`; `before_validate` chạy trước validate của ERPNext nên thông báo tiếng Việt hiện trước):
  - Mở ca: Cashier (`user`) = người thao tác **và** thuộc Applicable for Users của POS Profile (danh sách rỗng cũng chặn).
    Đã có ca Open của profile → "Ca của {tên} tại {profile} chưa đóng".
  - Đóng ca: Cashier của phiếu = Cashier của ca (ERPNext gom đơn theo `owner == closing.user`); chỉ đóng ca của chính mình.
  - Manager (`_pos_roles` → POS MANAGER / System Manager / Administrator) mở/đóng thay; Cashier vẫn phải thuộc Applicable for Users;
    `on_submit` ghi comment "Mở ca thay / Đóng ca thay … bởi …" (đóng thay: comment cả trên ca).
  - KITCHEN / role khác: chặn.
- `pos_api._ensure_opening_entry` (tự mở ca khi tạo đơn) đi qua cùng hook; lỗi giờ nối thêm lý do gốc. QR không tạo ca
  (`_as_user(shift.user)` → thấy ca sẵn có).
- Form Desk: `public/js/pos_opening_entry.js` (`doctype_js`): Cashier tự điền = người đăng nhập, khóa với người không phải quản lý.
- **Only If Creator** (`if_owner`) cho CASHIER trên 2 DocType (`mypos/setup/roles.py`):
  Cashier chỉ thấy ca / phiếu đóng ca do mình tạo. Ca MANAGER mở thay → Cashier không thấy trên Desk → MANAGER đóng thay.
  /pos, QR, `validate_pos_opening_entry` của ERPNext dùng `get_all` → không ảnh hưởng; gộp hóa đơn khi đóng ca không đổi.
- Rủi ro: POS Profile chưa khai Applicable for Users → không ai mở được ca; MANAGER bán ở /pos phải có trong danh sách để tự mở ca.
- Kiểm tra: `mypos/selfcheck/shift_owner_check.py` (`check_shift_owner(...)`, profile + user tạm, rollback).

### 2c. Đóng ca khi còn Draft, hủy đơn có lý do — ĐÃ TEST PASS trên bench DEV (`c892469`; đổi cách hủy 2026-11-23, `0553fd2`)

- `pos_shift_hooks._check_closing` chặn đóng ca khi còn Draft của POS Profile (`order_cancel.closing_blockers`: kênh khác QR — mọi đơn;
  QR — chỉ đơn còn trong 15 phút), liệt kê tối đa 10 mã. **Không còn "Đóng ca bắt buộc"** (2026-11-23): quản lý xử lý TỪNG đơn rồi mới đóng ca.
- **Hủy Draft = đơn chuyển `Cancelled` (docstatus 2), KHÔNG xóa** (2026-11-23). Một hàm cho mọi đường hủy:
  `doctype/pos_invoice_hooks/order_cancel.py::cancel_draft(invoice_name, reason, source, note)` — khóa dòng (`FOR UPDATE`), kiểm docstatus 0 +
  không phải trả hàng, `frappe.db.set_value` docstatus 2 / status "Cancelled" (save() không đổi được 0 → 2) + bảng con docstatus 2, Comment
  "Hủy đơn: … Bởi …". Lý do lưu ở Custom Field `custom_cancel_reason` (read only, hiện khi docstatus 2) theo tiền tố:
  `Thủ công: <lý do>[ — <ghi chú>]`, `Tự động (QR hết hạn): QR hết hạn không thanh toán`, `Tự động (quá 2 giờ): Tự hủy quá 2 giờ`.
  - [Inference, đọc mã ERPNext] Hook `on_cancel` không chạy nhưng không cần: Draft chưa có GL / tồn kho / điểm; tồn giữ chỗ POS và đóng ca chỉ lấy docstatus 1.
- `pos_api.cancel_draft_order(invoice_name, force, reason, note)` (Orders luôn gửi lý do: Khách đổi ý / Đặt nhầm / Khách không lấy / Khác + ghi chú;
  `reason=None` → "Không ghi lý do (giao diện cũ)"). Job `order_cancel.auto_cancel_stale_drafts` (cron `*/5`) dùng cùng hàm.
- Đã bỏ (2026-11-23, không có trong app này): DocType `MYPOS Order Cancel Log`, Report `MYPOS Review Queue`, Custom Field `needs_review`,
  trạng thái "Đã đóng ca chưa xử lý".
- Kiểm tra: `mypos/selfcheck/draft_cancel_check.py` (`check_draft_cancel(...)`).

### 2d. Đóng ca chặn đơn đã thanh toán chưa giao (2026-11-20) — ĐÃ TEST PASS trên bench DEV (`2325990`; bỏ phần đóng ca bắt buộc 2026-11-23)

- Chặn đóng ca thêm đơn Paid của ca còn "Chưa làm" (chưa pha chế) / "Đã làm" (chưa giao) — `kitchen_status.shift_open_orders`,
  thông báo theo nhóm (tối đa 10 mã + "và N đơn khác"). Quy tắc không đổi sau 2026-11-23.
- `resolve_open_order(invoice_name, outcome, reason, note)`: CASHIER / MANAGER / System Manager / Administrator (`_require_sale_role`); KITCHEN bị chặn.
  Mỗi đơn một lý do — **không còn** `resolve_open_orders` (hàng loạt), `force_close_shift`.
- Kiểm tra: `mypos/selfcheck/open_orders_check.py` (`check_open_orders(...)`).

### 2e. Quản lý xử lý đơn dở trên Desk (đơn giản hóa 2026-11-23) — ĐÃ TEST PASS trên bench DEV (`0553fd2`) — máy POS không đổi

- Không còn Report "MYPOS Review Queue", cờ `needs_review`, job nhắc mỗi giờ. Quản lý dùng **list view chuẩn của POS Invoice**:
  - Bộ lọc chuẩn: POS Profile (Property Setter fixture `POS Invoice-pos_profile-in_standard_filter`), Trạng thái pha chế
    (`custom_kitchen_status`, `in_standard_filter`), "Có tiền về sau khi hủy" (`custom_late_payment`).
  - 3 nút "Lọc nhanh" (`pos_invoice_list.js`, `doctype_list_js`) **đã bỏ 2026-11-26** (chủ dự án quyết định): dùng bộ lọc chuẩn ở trên.
- Form POS Invoice (`public/js/pos_invoice.js`, chỉ manager): Draft → nút **"Hủy đơn"** (lý do; "Khác" bắt buộc ghi chú; đơn "Đang chờ" QR phải tích
  xác nhận → `force=1`) → `pos_api.cancel_draft_order`. Đơn đã thu tiền đang rỗng / Chưa làm / Đã làm → nút **"Xử lý đơn"** (Đã hoàn thành /
  Không thực hiện được / Khách không nhận, lý do bắt buộc) → `pos_api.resolve_open_order`.
  - Đơn Paid → `kitchen_status.set_terminal` (save → hook nhả thẻ bàn). Đơn đã gộp (Consolidated) → `pos_api._resolve_consolidated`
    (chỉ manager, `db_set`, comment, `PosInvoiceHooks.release_buzzer`).
- Thông báo (Notification Log) còn MỘT loại: tiền về sau khi đơn đã hủy (`sepay.md` §3) → quản lý của chi nhánh (`profile_managers`: user bật +
  role POS MANAGER + thuộc Applicable for Users), không có ai → mọi POS MANAGER.
- Phân chi nhánh trên Desk: User Permission `Allow = POS Profile` cho từng manager (cấu hình, không code). [Inference, đọc mã] /pos dùng
  `get_all` / `qb` nên không bị User Permission ảnh hưởng.

## 3. Cơ chế cài đặt

- **`mypos/setup/roles.py` (`ROLES`, `PERMS`) là NGUỒN CHUẨN** quyền của 3 role MYPOS. Sửa quyền = sửa `PERMS` rồi `bench migrate`.
- **Role**: fixture `fixtures/role.json` (filter `name in [3 role]`) **và** `setup_roles_and_permissions` tự tạo nếu thiếu.
  Hàm không đổi `desk_access` của role đã có. Lưu ý: sync fixture khi migrate ghi lại `desk_access` theo `role.json` (giống bảng §1).
- **Quyền**: CHỈ qua `setup_roles_and_permissions` (`add_permission` + `update_permission_property`).
  **Không dùng fixture `Custom DocPerm`**: khi DocType có bất kỳ dòng Custom DocPerm nào, Frappe bỏ DocPerm chuẩn → fixture chỉ chứa
  3 role sẽ làm role ERPNext khác mất quyền trên site mới; và tên dòng fixture khác tên dòng hàm tạo → nhân bản.
- Gọi từ `mypos/setup/install.py`:
  - `after_install` (site cài mới; `install-app` không chạy patch): lỗi được ném ra.
  - `after_migrate` (mỗi lần `bench migrate`): lỗi từng bước ghi Error Log "MYPOS: …" + in `[mypos_roles] LỖI`, **không** làm migrate thất bại.
- Idempotent, **chỉ thêm**: DocType chưa có Custom DocPerm → `setup_custom_perms` một lần (chép DocPerm chuẩn); thiếu dòng
  (parent, role, permlevel 0) → `add_permission`; cờ trong `PERMS` đang 0 → bật. Không tắt cờ, không xóa dòng nào (kể cả dòng admin thêm tay,
  dòng trùng — dòng trùng chỉ được in cảnh báo), không đụng DocType ngoài `PERMS`, không đụng User Permission. Không thiếu gì → không ghi DB.
- Chạy tay: `bench --site <site> execute mypos.setup.roles.setup_roles_and_permissions` (kết quả in ra terminal: dòng `[mypos_roles] …`).

## 4. Quy tắc module

Mỗi role phải có quyền **Read ít nhất một DocType module `MYPOS`** (MYPOS Menu/MYPOS Buzzer)
thì user không phải Administrator mới vào được các workspace MYPOS của module (`allowed_modules`).
Chữ module phải khớp chính xác `MYPOS` (`docs/code-standards.md` §1).

## 5. Workspace / Desktop Icon / Workspace Sidebar

**Đảo quyết định 2026-11-12 (`roles: []`) — chủ dự án duyệt 2026-11-25, ĐÃ TEST PASS (`8f2e389`):** mỗi vai trò có workspace riêng, giới hạn bằng
`Workspace.roles`; mọi workspace giới hạn role kèm thêm `System Manager` để System Manager / Administrator luôn thấy tất cả mà không cần
role POS. Desktop Icon cũng có `roles` tương ứng. Chi tiết, route, sidebar: `workspace.md` §7.

| Workspace / Desktop Icon | roles |
|---|---|
| MYPOS Cashier | POS CASHIER, System Manager |
| MYPOS Kitchen | POS KITCHEN, System Manager |
| MYPOS Manager | POS MANAGER, System Manager |
| MYPOS Admin | System Manager |

- Không cấp thêm quyền DocType nào (`PERMS` không đổi). Link thiếu quyền Read tự ẩn: MANAGER không có Loyalty Program (quyết định chủ dự án);
  Pricing Rule / Promotional Scheme chỉ hiện khi user MANAGER được gán thêm `Sales Manager` (§1).
- User có role `Workspace Manager` thấy mọi workspace (Frappe), kể cả workspace không thuộc vai trò.
- Không đặt `Role.home_page` (quyết định chủ dự án 2026-11-25: dễ xung đột khi user nhiều role).

## 6. Role đã tạo tay trên site

- Để patch hợp nhất (không xóa tay): patch chỉ bổ sung cờ thiếu.
- Xóa Role → mất Custom DocPerm + Has Role của role đó (user mất role). Nếu buộc xóa: `bench backup` trước.

## 7. Phân quyền màn POS (UI + API pha chế) — ĐÃ LÀM, đã test Pass (`2be2ae8`)

| Role | Menu thấy | Tab Pha chế thấy | Được chuyển |
|---|---|---|---|
| POS MANAGER (+ System Manager, Administrator) | Bán món, Đơn hàng, Pha chế | Chưa làm, Đã làm, Đã hoàn thành | Chưa làm→Đã làm, Đã làm→Đã hoàn thành |
| POS CASHIER | Bán món, Đơn hàng, Pha chế | Đã làm, Đã hoàn thành | Đã làm→Đã hoàn thành |
| POS KITCHEN | Pha chế | Chưa làm, Đã hoàn thành (chỉ xem) | Chưa làm→Đã làm |

- **Nguồn duy nhất**: hằng ở đầu `api/pos_api.py`: `NAV_BY_ROLE`, `KITCHEN_TABS_BY_ROLE`,
  `KITCHEN_TRANSITIONS_BY_ROLE` (khóa `manager`/`cashier`/`kitchen`). Đổi quyền chỉ sửa ở đây.
- `_pos_roles()` → `{manager, cashier, kitchen}`; nhiều role = **hợp quyền**.
- `get_pos_config` trả `roles`, `nav`, `kitchen_tabs`, `kitchen_transitions`; frontend chỉ đọc
  các khóa này (`lib/pos-context.tsx`: `navOf`, `kitchenTabsOf`, `kitchenTransitionsOf`), không tự suy từ role.
- **Chặn thật ở backend**: `get_kitchen_orders` (status ngoài quyền → `PermissionError`; không truyền
  status → chỉ trả tab được phép), `set_kitchen_status` (sai bước → `ValidationError`, đúng bước nhưng
  sai role → `PermissionError`). User không có role POS (và không phải System Manager/Administrator)
  → `PermissionError`; frontend hiện thông báo, `nav` rỗng.
- "Đã hoàn thành" chỉ lấy `posting_date = nowdate()` ở backend (Chưa làm / Đã làm lấy mọi ngày).
- Frontend: `AppHeader` ẩn mục theo `nav`; `App.tsx` chuyển hướng mục không được phép sang mục đầu
  tiên được phép (KITCHEN mở `/pos`, `/pos/orders` → `/pos/kitchen`); `Kitchen.tsx` tab theo
  `kitchen_tabs`, nút chỉ hiện khi bước nằm trong `kitchen_transitions`, tab mặc định = tab đầu tiên được phép.

### 7a. Màn theo dõi đơn `/pos/status` (treo TV, 2026-11-27) — ĐÃ TEST PASS (`c4ee619`)

- Mọi role POS xem được, KHÔNG nằm trong `NAV_BY_ROLE` (không có mục menu màn /pos; mở thẳng URL trên TV). Không có thao tác.
  Lối tắt Desk (2026-11-27): shortcut "Order Status" ở cả 4 workspace MYPOS (Cashier / Kitchen / Manager / Admin), hiển thị theo `roles` có sẵn
  của workspace, không đổi quyền (`workspace.md` §7).
- Cashier / Kitchen: profile mình thuộc (cùng lỗi màn Pha chế). MANAGER / System Manager / Administrator: chọn profile đang bật.
- Tài khoản TV: POS KITCHEN riêng (quyết định chủ dự án 2026-11-27); vẫn gọi được API "Chưa làm → Đã làm" → chưa chỉ đọc tuyệt đối. Role POS DISPLAY
  để sau. Chi tiết: `order_status.md`, `mypos/selfcheck/deploy.md` §4.

### 7b. Thông báo thu ngân khi đơn "Đã làm" (thẻ bàn, 2026-11-23) — ĐÃ TEST PASS trên bench DEV (`f2236b4`, `3736f85`, `4712d68`)

- API `pos_api.get_serve_queue()`: `_require_sale_role` (KITCHEN bị chặn); đơn của `resolve_pos_profile_name()` của người gọi (không gửi chéo chi nhánh),
  docstatus 1, Paid, không trả hàng, `custom_kitchen_status = "Đã làm"`, `order_channel != "QR"`; trả số thẻ bàn, tên khách ("" nếu khách vãng lai của POS Profile) + `is_walk_in`,
  số món, 2 món đầu, `waiting_seconds`.
- Frontend: `lib/serve.ts::useServeQueuePoller` gắn một lần ở `App.tsx`, **chỉ khi user có role POS CASHIER** (`config.roles.cashier`). Từ 2026-11-25
  (ĐÃ TEST PASS `86b6cb2`, `realtime.md`): hỏi phiên bản thay đổi (`get_pos_changes`, chỉ đọc Redis) mỗi 15 giây, chỉ gọi `get_serve_queue` khi phiên bản đổi
  + lưới an toàn 120 giây (trước: `get_serve_queue` mỗi 15 giây),
  dừng khi tab ẩn; store `store/serveQueue.ts`.
  - Đơn mới vào hàng chờ → toast "Bàn 07 sẵn sàng phục vụ" / "#00066 · Gọi khách lấy món" + 2 tiếng bíp (`order/alert.ts`). Toast **chỉ hiển thị**
    (không bấm, không điều hướng), tự tắt 8 giây.
  - **Toast dùng chung (2026-11-27, ĐÃ TEST PASS `f5bd875`)**: `store/toasts.ts` + `components/ToastStack.tsx` (gắn một lần ở App) cho Bán món /
    Đơn hàng / Pha chế: một cột, tối đa 3 (cũ nhất tắt trước), cùng `key` → thay nội dung (một sự kiện một toast), tự xuống dòng. Trước đó toast
    Pha chế + toast hàng chờ cùng vị trí cố định → đè / cắt chữ; và sự kiện realtime về trước khi `refreshServeQueue([đơn])` loại trừ đơn của chính
    máy → toast trùng. Màn Pha chế gọi `useServeQueue.mute([đơn])` TRƯỚC khi gửi "Đã làm" (`unmute` nếu lỗi; hạn 60 giây).
  - Màn Pha chế tab "Đã hoàn thành": món tóm tắt 1–2 dòng (không tùy chọn / tem / ghi chú); Chưa làm / Đã làm đủ chi tiết.
  - Chấm đỏ + số cạnh mục **"Pha chế"** = số đơn "Đã làm" kênh tại quầy (Mang đi + Tại quán, **không tính QR** → có thể nhỏ hơn số ở tab "Đã làm"
    của màn Pha chế khi có đơn QR).
  - Kết thúc đơn = nút "Đã hoàn thành" ở màn Pha chế (tab Đã làm) như luồng chuẩn; **không có bước "Đã phục vụ" riêng** (đã bỏ tab "Chờ phục vụ"
    ở Orders, 2026-11-23). Màn Pha chế bỏ đơn khỏi store ngay sau khi chuyển thành công (`dropItems`, không thêm request); thay đổi từ máy khác
    (hủy, quản lý xử lý) cập nhật ở lần poll kế.
  - Máy vừa bấm "Đã làm" chỉ hiện toast xác nhận của màn Pha chế (`refreshServeQueue([tên đơn])` không báo trùng).
- User chỉ có KITCHEN, MANAGER / Administrator không có role POS CASHIER: không poll, không toast, không chấm đỏ.

**Tồn đọng:**
- Toast "Đã báo quầy …" ở màn Pha chế chỉ hiện trên máy bấm nút; máy thu ngân nhận thông báo sau tối đa 15 giây (poll).
- KITCHEN không thấy tab "Đã làm": bấm "Đã làm" xong đơn biến mất khỏi màn hình họ cho tới khi giao món.

## 8. Phân quyền các API còn lại — CHƯA làm (task sau, dùng `frappe.only_for`)

API hiện dùng `frappe.get_all` / `ignore_permissions=True` nên role chưa chặn được việc gọi API.

| Hàm | Đề xuất role |
|-----|--------------|
| `pos_api.get_pos_config` | KITCHEN, CASHIER, MANAGER |
| `pos_api.get_menu_items` | KITCHEN, CASHIER, MANAGER |
| `pos_api.get_buzzers` | CASHIER, MANAGER |
| `pos_api.search_customers` | CASHIER, MANAGER |
| `pos_api.get_customer_loyalty` | CASHIER, MANAGER |
| `pos_api.create_customer` | CASHIER, MANAGER |
| `pos_api.create_draft_order` | **ĐÃ LÀM** (2026-11-17): `_require_sale_role` — CASHIER, MANAGER, System Manager, Administrator |
| `pos_api.preview_pricing` | CASHIER, MANAGER |
| `pos_api.get_orders` | **ĐÃ LÀM** (2026-11-20): `_require_sale_role`; `scope="history"` chỉ MANAGER (`_order_scope`) |
| `pos_api.get_orders_summary` | **ĐÃ LÀM** (2026-11-20): như `get_orders`; `old_drafts` chỉ tính cho MANAGER |
| `pos_api.get_order_detail` | KITCHEN, CASHIER, MANAGER (KITCHEN cần để in tem / phiếu pha chế) |
| `pos_api.pay_cash` | **ĐÃ LÀM** (2026-11-17): `_require_sale_role` |
| `pos_api.cancel_draft_order` | **ĐÃ LÀM** (2026-11-17): `_require_sale_role`; chưa làm: `force=1` chỉ MANAGER. Hủy = Cancelled + lý do (2026-11-23) |
| `pos_api.generate_qr` | CASHIER, MANAGER |
| `pos_api.get_serve_queue` | **ĐÃ LÀM** (2026-11-23): `_require_sale_role`, lọc POS Profile của người gọi (§7b). `confirm_pickup` đã bỏ |
| `pos_api.get_status_board` | KITCHEN, CASHIER, MANAGER |
| `pos_api.get_kitchen_orders` | ĐÃ LÀM (§7) — lọc theo `KITCHEN_TABS_BY_ROLE` |
| `pos_api.set_kitchen_status` | ĐÃ LÀM (§7) — theo `KITCHEN_TRANSITIONS_BY_ROLE`; đơn đã kết thúc → từ chối (2026-11-20) |
| `pos_api.resolve_open_order` | **ĐÃ LÀM** (2026-11-20): `_require_sale_role` (§2d); đơn đã gộp chỉ manager. `resolve_open_orders`, `force_close_shift` đã bỏ 2026-11-23 |
| `pos_invoice_hooks.get_status_board_orders` | KITCHEN, CASHIER, MANAGER |
| `sepay.generate_qr_for_invoice` | CASHIER, MANAGER |
| `sepay.sepay_webhook` | Guest (giữ) — đã xác thực API key Branch (2026-11-14, `order-qr.md` §3) |
| `customer_display_api.*` | **ĐÃ LÀM** (2026-11-24): `_require_sale_role`, chỉ trạng thái của chính user + POS Profile của người gọi (`customer_display.md`) |
| `customer_order_api.*` | Guest — kiểm tra token phiên khách, không dùng role (`order-qr.md`) |
| `order_status_api.*` (màn theo dõi đơn `/pos/status`) | **ĐÃ LÀM** (2026-11-27, test Pass `c4ee619`): `_require_pos_role` (KITCHEN, CASHIER, MANAGER); Cashier / Kitchen chỉ profile mình thuộc (`require_membership`), quản lý chọn profile; chỉ đọc, dữ liệu rút gọn (`order_status.md`) |

`get_pos_config` được gọi lúc tải mọi màn /pos kể cả Kitchen, nên phải cho KITCHEN.
