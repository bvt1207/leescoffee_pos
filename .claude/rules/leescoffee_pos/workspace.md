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
    "module": "Leescoffee Pos",
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
| `module` | `"Leescoffee Pos"` | Module của app (viết hoa "Pos") |
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

- **Không hardcode** branding Lee's Coffee — dùng tên chung ("Leescoffee POS") hoặc cấu hình từ Settings
- Workspace chỉ gom shortcut, không chứa logic nghiệp vụ
- `is_standard: 1` bắt buộc để fixture hoạt động
- Icon lấy từ [Frappe Icons](https://frappeframework.com/docs/user/en/desk/icons) (ví dụ: `menu`, `coffee`, `table`, `kitchen`)