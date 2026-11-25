# Module Rules: Workspace Creation Standard — Leescoffee POS

> Quy trình chuẩn để tạo Workspace Frappe cho app Leescoffee POS.

## 1. Vị trí file chuẩn

```
leescoffee_pos/workspace/[workspace_name]/[workspace_name].json
```

Ví dụ: `leescoffee_pos/workspace/leescoffee_pos/leescoffee_pos.json`

## 2. Cấu trúc JSON bắt buộc

```json
{
    "doctype": "Workspace",
    "name": "[Workspace Name]",
    "module": "Leescoffee POS",
    "public": 1,
    "icon": "[frappe-icon-name]",
    "color": "#[hex-color]",
    "is_standard": 1,
    "links": [
        {
            "link_to": "[DocType Name]",
            "link_type": "DocType",
            "type": "Link",
            "label": "[Hiển thị tên]",
            "hidden": 0
        }
    ]
}
```

### Các trường quan trọng

| Trường | Giá trị mẫu | Ghi chú |
|--------|-------------|---------|
| `doctype` | `"Workspace"` | Bắt buộc, đúng chữ |
| `name` | `"Leescoffee POS"` | Tên hiển thị trên Desk |
| `module` | `"Leescoffee POS"` | Phải khớp chính xác module của các DocType (xem §7) |
| `public` | `1` | Hiển thị cho tất cả user |
| `icon` | `"menu"` | Tên icon Frappe (không cần prefix) |
| `color` | `"#16828A"` | Màu hex, brand của app |
| `is_standard` | `1` | Để export fixture được |
| `links[].link_to` | `"POS Profile"` | DocType đích |
| `links[].link_type` | `"DocType"` | Loại link |
| `links[].type` | `"Link"` | Kiểu hiển thị |
| `links[].label` | `"POS Profile"` | Tên hiển thị |
| `links[].hidden` | `0` | `0` = hiển thị, `1` = ẩn |

## 3. Thêm vào Fixtures (hooks.py)

Để Workspace được cài đặt tự động khi `bench install-app`:

```python
fixtures = [
    # ... existing fixtures ...
    {"dt": "Workspace", "filters": [["name", "=", "[Workspace Name]"]]},
]
```

Ví dụ cho Leescoffee POS:
```python
{"dt": "Workspace", "filters": [["name", "=", "Leescoffee POS"]]},
```

## 4. Lệnh cần chạy thủ công trên bench thật

Sau khi commit code và copy sang bench thật:

```bash
cd frappe-benchver16
bench --site <site-name> migrate
bench --site <site-name> export-fixtures
```

> `export-fixtures` sẽ sinh file JSON trong `leescoffee_pos/fixtures/` — commit file này.

## 5. Tái sử dụng cho Workspace khác

Để tạo Workspace mới (ví dụ: "Leescoffee Kitchen"):

1. Tạo thư mục: `leescoffee_pos/workspace/leescoffee_kitchen/`
2. Tạo file: `leescoffee_kitchen.json` theo cấu trúc mục 2
3. Thêm fixture vào `hooks.py` (mục 3)
4. Chạy lệnh mục 4

## 6. Lưu ý

- **Không hardcode** branding Lee's Coffee — dùng tên chung ("Leescoffee POS") hoặc cấu hình từ Branch
- Workspace chỉ gom shortcut, không chứa logic nghiệp vụ
- `is_standard: 1` bắt buộc để fixture hoạt động
- Icon lấy từ [Frappe Icons](https://frappeframework.com/docs/user/en/desk/icons) (ví dụ: `menu`, `coffee`, `table`, `kitchen`)

## 7. Workspace theo vai trò, tiền tố MYPOS (2026-11-25) — ĐÃ TEST PASS trên bench DEV (`8f2e389`)

Bốn workspace, module vẫn `Leescoffee POS`, mỗi file `leescoffee_pos/leescoffee_pos/workspace/<scrub(name)>/<scrub(name)>.json`
(`standard: 1`, `public: 1`, `app: leescoffee_pos`). Route Desk = `/desk/<slug(name)>`.

| Workspace → route | `roles` | Shortcuts | Cards (Card Break → link) |
|---|---|---|---|
| MYPOS Cashier → `/desk/mypos-cashier` | POS CASHIER, System Manager | Open MYPOS (`/pos`), MYPOS Customer Display (`/pos/customer`) | Shift: POS Opening Entry, POS Closing Entry |
| MYPOS Kitchen → `/desk/mypos-kitchen` | POS KITCHEN, System Manager | MYPOS Kitchen Screen (`/pos/kitchen`) | — |
| MYPOS Manager → `/desk/mypos-manager` | POS MANAGER, System Manager | Open MYPOS, Draft Orders, Unserved Orders | Shift & Cash (Opening, Closing, POS Invoice Merge Log); Order Handling (POS Invoice, MYPOS Buzzer); Menu & Promotions (MYPOS Menu, MYPOS Option Group, Pricing Rule, Promotional Scheme); QR & Display (MYPOS Order QR, MYPOS Banner) |
| MYPOS Admin → `/desk/mypos-admin` | System Manager | Open MYPOS, Draft Orders, Unserved Orders, MYPOS Kitchen Screen, MYPOS Customer Display | Branch Setup (Branch, POS Profile, Customer, User Permission); Shift & Cash; Order Handling; Menu & Promotions (+ Loyalty Program); QR & Display; Troubleshooting (Error Log, Notification Log) |

Số dòng sau migrate: Workspace Link Cashier 3 / Kitchen 0 / Manager 15 / Admin 24; Workspace Shortcut 2 / 1 / 3 / 5; Has Role 2 / 2 / 2 / 1.

- **Quy tắc hiển thị (đã đọc mã Frappe v16.49 / v16.61):** workspace hiện khi module hiển thị với user (Read ít nhất 1 DocType module,
  roles.md §4) VÀ user có một role trong `roles`. Mọi workspace giới hạn role đều kèm `System Manager` (Administrator có mọi role).
  User có role `Workspace Manager` thấy MỌI workspace (không dùng user đó để test). Link DocType trong card ẩn khi thiếu quyền Read
  (vd. Pricing Rule / Promotional Scheme chỉ hiện cho MANAGER có thêm Sales Manager; Loyalty Program chỉ ở Admin, quyết định Van D4).
- **Shortcut URL** luôn mở tab mới (`shortcut_widget.js`). **Shortcut DocType** luôn đếm `frappe.db.count` theo `stats_filter` và
  dùng nó làm bộ lọc danh sách (`frappe.route_options`). Draft Orders: `docstatus = 0`. Unserved Orders: `docstatus = 1`,
  `is_return = 0`, `custom_kitchen_status in (Chưa làm, Đã làm)` ([Unverified] toán tử `in` qua route_options — test tay).
- **Mô tả card**: `Workspace Link.description` (Card Break), có ở v16.49 và v16.50+.
- **Sidebar Desk** (phụ thuộc phiên bản Frappe, ship cả hai; mỗi file trơ ở phiên bản kia):
  - Frappe ≥ 16.50: `leescoffee_pos/leescoffee_pos/sidebar/mypos/mypos.json` (DocType `Sidebar`, name/title "MYPOS", 4 item Workspace:
    Cashier / Kitchen / Manager / Admin). Sidebar item loại Workspace tự lọc theo `roles` của workspace.
  - Frappe < 16.50: `leescoffee_pos/workspace_sidebar/mypos.json` (Workspace Sidebar "MYPOS", cùng 4 item).
- **Desktop Icon** (`leescoffee_pos/desktop_icon/mypos_*.json`, External, có `roles` = role chính + System Manager):
  MYPOS Cashier → `/desk/mypos-cashier`, MYPOS Kitchen → `/pos/kitchen`, MYPOS Manager → `/desk/mypos-manager`,
  MYPOS Admin → `/desk/mypos-admin` (chỉ System Manager).
- **Đổi tên `leescoffee_pos` → MYPOS Admin**: không dùng `rename_doc` (nội dung lấy từ file; route cũ hỏng trong mọi cách). File cũ đã xóa khỏi
  repo; patch `v1_mypos_workspaces` xóa workspace / Desktop Icon / Workspace Sidebar cũ `leescoffee_pos` khi đủ 4 workspace mới.
  Bookmark `/desk/leescoffee_pos`, `/app/leescoffee_pos` không còn dùng được → dùng icon hoặc route mới.

Quy tắc khi sửa JSON workspace:

- `link_count` của Card Break = số dòng `type: Link` ngay sau nó.
- `card_name` / `shortcut_name` trong `content` phải khớp chính xác `label` của Card Break / shortcut.
- Mỗi lần sửa phải **tăng `modified`**, nếu không migrate bỏ qua file. Không đổi `creation`, `name`.
- **Workspace Link trùng:** [đã đọc mã v16.61] import file xóa doc cũ cùng mọi dòng con rồi insert lại, nên import không tự sinh dòng trùng
  (nguyên nhân bản trùng trước đây chưa xác định). Patch `v1_mypos_workspaces` (post_model_sync, idempotent) so số dòng con với file,
  lệch → `import_file_by_path(force=True)`. Không xóa Workspace Link bằng patch post_model_sync (chạy SAU khi file đã nạp).
  Muốn áp lại: đổi nhãn `#...` của dòng patch trong `patches.txt`.
- **Dự phòng xóa tay** (trước migrate, console), rồi migrate để nạp lại:
  `for n in ["MYPOS Cashier","MYPOS Kitchen","MYPOS Manager","MYPOS Admin"]: frappe.db.delete("Workspace Link", {"parent": n, "parenttype": "Workspace"})`
  → `frappe.db.commit()`; sau migrate kiểm số dòng như bảng trên.
- Tùy chỉnh workspace trên Desk (Custom Workspace ở v16.50+) có thể đè roles / nội dung file; patch chỉ in cảnh báo, không xóa.

Lịch sử: workspace `leescoffee_pos` cũ có 1 card "MYPOS Setup" (tên trước đó "Lee's Coffee Setup") gom mọi link + shortcut POS, `roles: []`.
