# Module Rules: Workspace / Sidebar / Desktop Icon — MYPOS

> Paths: `mypos/mypos/workspace/` (4 workspace), `mypos/mypos/sidebar/mypos/mypos.json` (Sidebar "MYPOS"),
> `mypos/desktop_icon/mypos_*.json` (4 Desktop Icon). Không dùng fixture cho Workspace: file JSON chuẩn của module (`standard: 1`)
> được Frappe nạp khi install / migrate.

## 1. Phiên bản Frappe

App yêu cầu Frappe ≥ 16.50 (`pyproject.toml` → `[tool.bench.frappe-dependencies]`). Bench thử: frappe / erpnext 16.61.0.

## 2. Bốn workspace theo vai trò

Module `MYPOS`, mỗi file `mypos/mypos/workspace/<scrub(name)>/<scrub(name)>.json`
(`standard: 1`, `public: 1`, `app: mypos`). Route Desk = `/desk/<slug(name)>`.

| Workspace → route | `roles` | Shortcuts | Cards (Card Break → link) |
|---|---|---|---|
| MYPOS Cashier → `/desk/mypos-cashier` | POS CASHIER, System Manager | Open MYPOS (`/pos`), Customer Display (`/pos/customer`), Order Status (`/pos/status`) | Shift: POS Opening Entry, POS Closing Entry |
| MYPOS Kitchen → `/desk/mypos-kitchen` | POS KITCHEN, System Manager | Kitchen Screen (`/pos/kitchen`), Order Status (`/pos/status`) | — |
| MYPOS Manager → `/desk/mypos-manager` | POS MANAGER, System Manager | Open MYPOS, Order Status | Shift & Cash (Opening, Closing, POS Invoice Merge Log); Order Handling (POS Invoice, MYPOS Buzzer); Menu & Promotions (MYPOS Menu, MYPOS Option Group, Pricing Rule, Promotional Scheme); QR & Display (MYPOS Order QR, MYPOS Banner) |
| MYPOS Admin → `/desk/mypos-admin` | System Manager | Open MYPOS, Kitchen Screen, Customer Display, Order Status | Branch Setup (Branch, POS Profile, Customer, User Permission); Shift & Cash; Order Handling; Menu & Promotions (+ Loyalty Program); QR & Display; Troubleshooting (Error Log, Notification Log) |

Số dòng sau migrate: Workspace Link Cashier 3 / Kitchen 0 / Manager 15 / Admin 24; Workspace Shortcut 3 / 2 / 2 / 4 (2026-11-26: bỏ Draft Orders, Unserved Orders ở Manager / Admin;
2026-11-27: thêm "Order Status" ở cả 4, bỏ tiền tố "MYPOS" ở nhãn shortcut — chỉ "Open MYPOS" giữ nguyên); Has Role 2 / 2 / 2 / 1.

- **Quy tắc hiển thị (đã đọc mã Frappe v16.49 / v16.61):** workspace hiện khi module hiển thị với user (Read ít nhất 1 DocType module,
  roles.md §4) VÀ user có một role trong `roles`. Mọi workspace giới hạn role đều kèm `System Manager` (Administrator có mọi role).
  User có role `Workspace Manager` thấy MỌI workspace (không dùng user đó để test). Link DocType trong card ẩn khi thiếu quyền Read
  (vd. Pricing Rule / Promotional Scheme chỉ hiện cho MANAGER có thêm Sales Manager; Loyalty Program chỉ ở Admin, quyết định chủ dự án D4).
- **Shortcut màn hình:** "Order Status" → `/pos/status` (màn theo dõi đơn treo TV, `order_status.md`) đứng cuối nhóm shortcut
  ở mọi workspace MYPOS. Nhãn shortcut không lặp tiền tố "MYPOS" (đã nằm trong workspace MYPOS; nhãn dài bị Desk cắt chữ): "Kitchen Screen",
  "Customer Display", "Order Status"; "Open MYPOS" giữ nguyên. Kiểm: `mypos/selfcheck/workspace_shortcut_check.py` (`check_workspace_shortcuts()`, chỉ đọc).
- **Shortcut URL** luôn mở tab mới (`shortcut_widget.js`). **Shortcut DocType** luôn đếm `frappe.db.count` theo `stats_filter` và
  dùng nó làm bộ lọc danh sách (`frappe.route_options`). Hiện không còn shortcut DocType nào (Draft Orders / Unserved Orders đã bỏ
  2026-11-26, chủ dự án quyết định; xem đơn qua card Order Handling → POS Invoice + bộ lọc chuẩn).
- **Mô tả card**: `Workspace Link.description` (Card Break), có ở v16.49 và v16.50+.
- **Sidebar Desk — DocType `Sidebar` theo module** (Frappe 16.61, schema + mã nguồn đã đối chiếu trên bench mới):
  - File: `mypos/mypos/sidebar/mypos/mypos.json` = `<module path>/sidebar/<scrub(title)>/<scrub(title)>.json`
    (`convert_fixtures.export_path`). `bench migrate` nạp file này qua `IMPORTABLE_DOCTYPES` (quét từng module của app).
  - Định dạng giống `convert_fixtures.write_export`: `"doctype": "Sidebar"`, `name` = `title` = **"MYPOS"** (Sidebar đặt tên theo
    `title`, trùng tên module), `module` "MYPOS", `header_icon` "milestone", `app` "mypos", `standard` 1, `items` = các `Sidebar Item`
    (`parentfield` items, `parenttype` Sidebar, `idx`) chỉ gồm trường có giá trị; `json.dumps(indent=1, sort_keys=True)` + xuống dòng cuối.
    Không có `for_user`, `merged_from`, `creation` / `modified`.
  - 4 mục (thứ tự = thứ tự hiển thị), `type` Link, `link_type` Workspace (mục Workspace tự lọc theo `roles` của workspace):

    | idx | label | link_to | icon |
    |---|---|---|---|
    | 1 | Cashier | MYPOS Cashier | receipt |
    | 2 | Kitchen | MYPOS Kitchen | computer |
    | 3 | Manager | MYPOS Manager | chart |
    | 4 | Admin | MYPOS Admin | settings |

  - Mục có `route_options` (trừ Page / URL) phải chuyển thành `filters` (`sidebar.options_as_filters`); 4 mục hiện tại không có.
  - **Không còn** `workspace_sidebar/` (Workspace Sidebar cấp app: bản 16.61 đã bỏ nạp) và **không còn mẹo "sidebar rỗng trùng tên
    module"** của bản cũ: sidebar chính đã tên "MYPOS" = tên module.
  - Mục tiêu: sidebar MYPOS chỉ có 4 mục workspace (thấy theo role), không có mục DocType lẻ (MYPOS Option Group / Order QR / Menu).
    Kiểm: `mypos.selfcheck.sidebar_check.check_sidebar` + kiểm tay 4 tài khoản (`deploy.md` §5). Dự phòng khi 16.61 vẫn sinh mục thừa
    hoặc không nạp Sidebar: `deploy.md` §5.2.
- **Desktop Icon** (`mypos/desktop_icon/mypos_*.json`, cấp package, cùng chỗ với bản cũ): nạp bằng hàm riêng
  `frappe.desk.doctype.desktop_icon.desktop_icon.import_desktop_icon_fixtures(app_name)` (gọi từ `frappe/model/sync.py`), KHÔNG qua
  `IMPORTABLE_DOCTYPES`. [Unverified] Thư mục / quy ước tên file mà hàm này đọc ở 16.61 chưa đối chiếu mã; bản cũ (bench DEV) đã test Pass với file ở
  `<package>/desktop_icon/<scrub(name)>.json`. Mỗi icon: `app` "mypos", `icon_type` App, `link_type` External, `roles` = role chính + System Manager,
  logo `/assets/mypos/images/logo.svg`: MYPOS Cashier → `/desk/mypos-cashier`, MYPOS Kitchen → `/pos/kitchen`,
  MYPOS Manager → `/desk/mypos-manager`, MYPOS Admin → `/desk/mypos-admin` (chỉ System Manager).

## 3. Quy tắc khi sửa JSON workspace

- `link_count` của Card Break = số dòng `type: Link` ngay sau nó.
- `card_name` / `shortcut_name` trong `content` phải khớp chính xác `label` của Card Break / shortcut.
- Mỗi lần sửa phải **tăng `modified`**, nếu không migrate bỏ qua file. Không đổi `creation`, `name`.
- **Workspace Link trùng:** [đã đọc mã v16.61] import file xóa doc cũ cùng mọi dòng con rồi insert lại, nên import không tự sinh dòng trùng.
  Nếu thấy lệch so với bảng số dòng ở §2: xóa tay rồi migrate để nạp lại:
  `for n in ["MYPOS Cashier","MYPOS Kitchen","MYPOS Manager","MYPOS Admin"]: frappe.db.delete("Workspace Link", {"parent": n, "parenttype": "Workspace"})`
  → `frappe.db.commit()`; sau migrate kiểm bằng `mypos.selfcheck.workspace_shortcut_check.check_workspace_shortcuts`.
- Tùy chỉnh workspace trên Desk (Custom Workspace) có thể đè roles / nội dung file.
- Không hardcode thương hiệu quán trong workspace: tên chung "MYPOS", thương hiệu lấy từ Branch.
