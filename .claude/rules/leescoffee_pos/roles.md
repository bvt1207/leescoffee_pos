# Module Rules: Role & quyền POS

> Paths: `leescoffee_pos/patches/v1_create_pos_roles.py` (bảng `ROLES`, `PERMS`),
> `leescoffee_pos/fixtures/role.json`, `hooks.py` (`fixtures` Role, `after_install`).

## 1. Ba role của app

| Role | desk_access | Dùng cho |
|------|-------------|----------|
| `POS CASHIER` | 1 | Thu ngân: mở/đóng ca, /pos, Orders |
| `POS KITCHEN` | 0 | Pha chế: chỉ `/pos/kitchen` (không vào Desk) |
| `POS MANAGER` | 1 | Quản lý cửa hàng |

Role ERPNext gán **kèm** cho user MANAGER (không tạo trong code, gán tay khi tạo user):
`Auditor`, `Sales User`, `Sales Manager`, `Stock User`.

## 2. Bảng quyền (permlevel 0; S=Select R=Read W=Write C=Create Sub=Submit)

Không cấp Cancel / Delete / Amend.

| DocType | CASHIER | KITCHEN | MANAGER |
|---------|---------|---------|---------|
| POS Opening Entry | S R W C Sub | — | S R W C Sub |
| POS Closing Entry | S R W C Sub | — | S R W C Sub |
| POS Profile | S R | — | S R W C |
| Leescoffee Menu | R | R | S R W C |
| Leescoffee Buzzer | R | R | S R W C |
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

Nguồn sự thật là `PERMS` trong patch; sửa bảng này thì sửa cả patch.

## 3. Cơ chế cài đặt

- **Role**: fixture `fixtures/role.json` (filter `name in [3 role]`) **và** patch tự tạo nếu
  thiếu (`frappe.db.exists`). Patch không đổi `desk_access` của role đã có. Lưu ý: sync fixture
  khi migrate ghi lại `desk_access` theo `role.json` (giá trị giống bảng §1).
- **Quyền**: CHỈ qua patch `v1_create_pos_roles` (`add_permission` + `update_permission_property`).
  **Không dùng fixture `Custom DocPerm`**: khi DocType có bất kỳ dòng Custom DocPerm nào, Frappe bỏ
  DocPerm chuẩn → fixture chỉ chứa 3 role sẽ làm role ERPNext khác mất quyền trên site mới; và tên
  dòng fixture khác tên dòng patch tạo → nhân bản. `add_permission` tự `setup_custom_perms` trước.
- Patch chỉ **bật** cờ đang 0, không tắt cờ nào; quyền người dùng tự thêm được giữ.
- Site đang chạy: `patches.txt` [post_model_sync] (chạy 1 lần, ghi Patch Log).
- Site cài mới: `hooks.after_install` gọi cùng `execute()` (install-app không chạy patch).
- Muốn áp lại sau khi sửa `PERMS`: đổi nhãn sau `#` của dòng patch trong `patches.txt`
  (vd. `leescoffee_pos.patches.v1_create_pos_roles #2026-11-12 manager-branch`) → migrate chạy lại
  (Patch Log lưu nguyên dòng). Hoặc chạy tay:
  `bench --site <site> execute leescoffee_pos.patches.v1_create_pos_roles.execute`.

## 4. Quy tắc module

Mỗi role phải có quyền **Read ít nhất một DocType module `Leescoffee POS`** (Leescoffee Menu/Buzzer)
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
| `pos_api.create_draft_order` | CASHIER, MANAGER |
| `pos_api.preview_pricing` | CASHIER, MANAGER |
| `pos_api.get_orders` | CASHIER, MANAGER |
| `pos_api.get_order_detail` | KITCHEN, CASHIER, MANAGER (KITCHEN cần để in tem / phiếu pha chế) |
| `pos_api.pay_cash` | CASHIER, MANAGER |
| `pos_api.cancel_draft_order` | CASHIER, MANAGER; `force=1` chỉ MANAGER |
| `pos_api.generate_qr` | CASHIER, MANAGER |
| `pos_api.confirm_pickup` | CASHIER, MANAGER |
| `pos_api.get_status_board` | KITCHEN, CASHIER, MANAGER |
| `pos_api.get_kitchen_orders` | ĐÃ LÀM (§7) — lọc theo `KITCHEN_TABS_BY_ROLE` |
| `pos_api.set_kitchen_status` | ĐÃ LÀM (§7) — theo `KITCHEN_TRANSITIONS_BY_ROLE` |
| `pos_invoice_hooks.get_status_board_orders` | KITCHEN, CASHIER, MANAGER |
| `sepay.generate_qr_for_invoice` | CASHIER, MANAGER |
| `sepay.sepay_webhook` | Guest (giữ) — cần xác thực API key (task_handoff mục A) |

`get_pos_config` được gọi lúc tải mọi màn /pos kể cả Kitchen, nên phải cho KITCHEN.
