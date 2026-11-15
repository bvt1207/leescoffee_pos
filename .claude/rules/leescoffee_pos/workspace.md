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

## 7. Workspace hiện có: `leescoffee_pos`

File: `leescoffee_pos/leescoffee_pos/workspace/leescoffee_pos/leescoffee_pos.json`
(`name`/`title`/`label` = `leescoffee_pos`, `module` = `Leescoffee POS`).

- **Quy tắc module:** chữ `module` của mọi DocType/Workspace phải **khớp chính xác** `Leescoffee POS` (như `modules.txt`, Module Def). Lệch chữ → user không phải Administrator bị PermissionError khi vào `/desk/leescoffee_pos`, vì `allowed_modules` lấy từ `module` của các DocType user có quyền Read.

- 1 card "MYPOS Setup" (đổi từ "Lee's Coffee Setup" 2026-11-15; `link_count: 8`, `modified` 2026-11-15 15:00), thứ tự link: Branch, POS Profile,
  POS Opening Entry, POS Closing Entry, MYPOS Menu, MYPOS Buzzer, MYPOS Option Group, MYPOS Order QR.
  Sau migrate: `Workspace Link` của `leescoffee_pos` = **9 dòng** (8 Link + 1 Card Break).
- 1 shortcut `POS` (type URL, `/pos`). Workspace Sidebar chỉ có dòng Home.

Quy tắc khi sửa JSON workspace:

- `link_count` của Card Break = số dòng `type: Link` ngay sau nó.
- `card_name` trong `content` phải khớp chính xác `label` của Card Break.
- Mỗi lần sửa phải **tăng `modified`**, nếu không migrate bỏ qua file. Không đổi `creation`, `name`.
- Nạp lại workspace có thể **nhân bản** dòng `Workspace Link` (Van ghi nhận trên bench) → xóa
  trước khi migrate:
  `frappe.db.delete("Workspace Link", {"parent": "leescoffee_pos", "parenttype": "Workspace"}); frappe.db.commit()`
  rồi kiểm tra `frappe.db.count("Workspace Link", {"parent": "leescoffee_pos"})` = số Link + số Card Break.
