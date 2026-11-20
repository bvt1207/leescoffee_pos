# Module Rules: Role & quyền POS

> Paths: `leescoffee_pos/patches/v1_create_pos_roles.py` (bảng `ROLES`, `PERMS`),
> `leescoffee_pos/fixtures/role.json`, `hooks.py` (`fixtures` Role, `after_install`).

## 1. Ba role của app

| Role | desk_access | Dùng cho |
|------|-------------|----------|
| `POS CASHIER` | 1 | Thu ngân: mở/đóng ca, /pos, Orders |
| `POS KITCHEN` | 1 | Pha chế: vào `/desk`, thấy icon `leescoffee_pos`, bấm POS → `/pos` tự chuyển `/pos/kitchen` |
| `POS MANAGER` | 1 | Quản lý cửa hàng |

**KITCHEN `desk_access = 1` (quyết định Van, 2026-11-17):** để pha chế đăng nhập và vào màn Pha chế từ Desk
như các role khác. Quyền vẫn tối thiểu: chỉ Read `MYPOS Menu`, `MYPOS Buzzer`, `MYPOS Option Group` (§2); API bán
hàng bị chặn ở backend (§8). Site cũ: patch `v1_kitchen_desk_access` bật role lên 1 và lưu lại user có role KITCHEN
đang là Website User (để thành System User); cài mới: `role.json` + `ROLES` đã là 1.

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
| POS Invoice | S R W C Sub | — | S R W C Sub |
| POS Invoice Merge Log | S R W C Sub | — | S R W C Sub |
| Sales Invoice | S R W C Sub | — | S R W C Sub |
| Address | R | — | R W C |
| Contact | R | — | R W C |
| Branch | — | — | S R W C |
| MYPOS Option Group | R | R | R W C |
| MYPOS Order QR | R | — | S R W C |
| MYPOS Order Cancel Log | — | — | S R W (chỉ bỏ cờ "Cần đối soát"; log do hệ thống ghi) |

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
- **Only If Creator** (`if_owner`) cho CASHIER trên 2 DocType (patch `v1_create_pos_roles`, nhãn `#2026-11-20 cashier-if-owner`):
  Cashier chỉ thấy ca / phiếu đóng ca do mình tạo. Ca MANAGER mở thay → Cashier không thấy trên Desk → MANAGER đóng thay.
  /pos, QR, `validate_pos_opening_entry` của ERPNext dùng `get_all` → không ảnh hưởng; gộp hóa đơn khi đóng ca không đổi.
- Rủi ro: POS Profile chưa khai Applicable for Users → không ai mở được ca; MANAGER bán ở /pos phải có trong danh sách để tự mở ca.
- Kiểm tra: `.claude/docs/shift_owner_check.py` (`check_shift_owner(...)`, profile + user tạm, rollback).

### 2c. Đóng ca khi còn Draft, hủy đơn có lý do (2026-11-20) — ĐÃ TEST PASS trên bench DEV (`c892469`)

- `pos_shift_hooks._check_closing` chặn đóng ca khi còn Draft của POS Profile (`order_cancel.closing_blockers`: kênh khác QR — mọi đơn;
  QR — chỉ đơn còn trong 15 phút), liệt kê tối đa 10 mã. Đơn đã thanh toán (pha chế chưa xong) không chặn.
- **Đóng ca bắt buộc** (`pos_api.force_close_shift(opening_entry, reason)`, nút trên form POS Opening Entry — `public/js/pos_opening_entry.js`):
  chỉ manager, lý do bắt buộc; hủy MỌI Draft (log "Đóng ca" / "Hủy khi đóng ca", ghi chú = lý do) rồi tạo + submit phiếu đóng ca trong một
  giao dịch; comment lý do trên phiếu đóng ca. CASHIER gọi → PermissionError.
- `cancel_draft_order(invoice_name, force, reason, note)`: Orders luôn gửi lý do (Khách đổi ý / Đặt nhầm / Khách không lấy / Khác + ghi chú);
  `reason=None` (giao diện cũ) vẫn hủy, log "Không ghi lý do (giao diện cũ)".
- Mọi đường hủy (tay, job, đóng ca) qua `order_cancel.cancel_draft_with_log` → `MYPOS Order Cancel Log` (đơn bị xóa nên Comment không giữ được).
- Kiểm tra: `.claude/docs/draft_cancel_check.py` (`check_draft_cancel(...)`).

### 2d. Đóng ca chặn đơn đã thanh toán chưa giao (2026-11-20, CHỜ VAN TEST)

- Chặn đóng ca thêm đơn Paid của ca còn "Chưa làm" (chưa pha chế) / "Đã làm" (chưa giao) — `kitchen_status.shift_open_orders`,
  thông báo theo nhóm (tối đa 10 mã + "và N đơn khác").
- `force_close_shift`: ngoài hủy Draft, đơn dở → "Đã đóng ca chưa xử lý" (`needs_review`, comment, không xóa); savepoint, lỗi trước khi gộp
  hóa đơn → hoàn tác. Lưu ý: ERPNext `create_merge_logs` tự commit khi submit phiếu đóng ca và tự rollback toàn bộ nếu gộp lỗi.
- `resolve_open_order(s)`: CASHIER / MANAGER / System Manager / Administrator (`_require_sale_role`); KITCHEN bị chặn.
- Kiểm tra: `.claude/docs/open_orders_check.py` (`check_open_orders(...)`).

## 3. Cơ chế cài đặt

- **Role**: fixture `fixtures/role.json` (filter `name in [3 role]`) **và** patch tự tạo nếu
  thiếu (`frappe.db.exists`). Patch không đổi `desk_access` của role đã có. Lưu ý: sync fixture
  khi migrate ghi lại `desk_access` theo `role.json` (giá trị giống bảng §1).
- **Quyền**: CHỈ qua patch `v1_create_pos_roles` (`add_permission` + `update_permission_property`).
  **Không dùng fixture `Custom DocPerm`**: khi DocType có bất kỳ dòng Custom DocPerm nào, Frappe bỏ
  DocPerm chuẩn → fixture chỉ chứa 3 role sẽ làm role ERPNext khác mất quyền trên site mới; và tên
  dòng fixture khác tên dòng patch tạo → nhân bản. `add_permission` tự `setup_custom_perms` trước.
- Patch chỉ **bật** cờ đang 0, không tắt cờ nào; quyền người dùng tự thêm được giữ.
- Chống trùng (2026-11-15): `setup_custom_perms` một lần mỗi DocType; khóa dòng = (parent, role, permlevel 0), khớp
  `update_permission_property`; dọn trùng giữ dòng cũ nhất, xóa dòng sau chỉ khi mọi cột quyền giống hệt (khác quyền → giữ, in ra).
  [Unverified] Trùng role chuẩn ERPNext trên Menu/Buzzer có từ 08/11 — trước khi có patch này (12/11); nguyên nhân chưa xác định.
- Site đang chạy: `patches.txt` [post_model_sync] (chạy 1 lần, ghi Patch Log).
- Site cài mới: `hooks.after_install` gọi cùng `execute()` (install-app không chạy patch).
- Muốn áp lại sau khi sửa `PERMS`: đổi nhãn sau `#` của dòng patch trong `patches.txt`
  (vd. `leescoffee_pos.patches.v1_create_pos_roles #2026-11-12 manager-branch`) → migrate chạy lại
  (Patch Log lưu nguyên dòng). Hoặc chạy tay:
  `bench --site <site> execute leescoffee_pos.patches.v1_create_pos_roles.execute`.

## 4. Quy tắc module

Mỗi role phải có quyền **Read ít nhất một DocType module `Leescoffee POS`** (MYPOS Menu/MYPOS Buzzer)
thì user không phải Administrator mới vào được workspace `leescoffee_pos` (`allowed_modules`).
Chữ module phải khớp chính xác `Leescoffee POS` (CLAUDE.md §5).

## 5. Workspace / Desktop Icon / Workspace Sidebar

Giữ `roles: []` (quyết định của Van, 2026-11-12). Truy cập đã bị chặn theo module; đặt `roles`
dễ chặn nhầm user ERPNext khác.

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

**Tồn đọng:**
- Toast "Mời khách … đến quầy nhận món" chỉ hiện trên máy bấm nút; pha chế và thu ngân khác máy
  thì thu ngân chỉ thấy đơn sau chu kỳ làm mới 5 giây.
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
| `pos_api.cancel_draft_order` | **ĐÃ LÀM** (2026-11-17): `_require_sale_role`; chưa làm: `force=1` chỉ MANAGER |
| `pos_api.generate_qr` | CASHIER, MANAGER |
| `pos_api.confirm_pickup` | CASHIER, MANAGER |
| `pos_api.get_status_board` | KITCHEN, CASHIER, MANAGER |
| `pos_api.get_kitchen_orders` | ĐÃ LÀM (§7) — lọc theo `KITCHEN_TABS_BY_ROLE` |
| `pos_api.set_kitchen_status` | ĐÃ LÀM (§7) — theo `KITCHEN_TRANSITIONS_BY_ROLE`; đơn đã kết thúc → từ chối (2026-11-20) |
| `pos_api.resolve_open_order(s)` | **ĐÃ LÀM** (2026-11-20): `_require_sale_role` (§2d) |
| `pos_api.force_close_shift` | **ĐÃ LÀM** (2026-11-20): chỉ manager (§2c, §2d) |
| `pos_invoice_hooks.get_status_board_orders` | KITCHEN, CASHIER, MANAGER |
| `sepay.generate_qr_for_invoice` | CASHIER, MANAGER |
| `sepay.sepay_webhook` | Guest (giữ) — đã xác thực API key Branch (2026-11-14, `order-qr.md` §3) |
| `customer_order_api.*` | Guest — kiểm tra token phiên khách, không dùng role (`order-qr.md`) |

`get_pos_config` được gọi lúc tải mọi màn /pos kể cả Kitchen, nên phải cho KITCHEN.
