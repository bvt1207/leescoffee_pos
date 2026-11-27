# Tài liệu MYPOS

## Kiến trúc (tóm tắt)

- ERPNext là nền: giữ nguyên DocType lõi (`POS Invoice`, `POS Profile`, `POS Opening/Closing Entry`, `Customer`, `Item`, `Mode of Payment`...).
  Giao dịch quầy là **`POS Invoice`**; đóng ca ERPNext tự gộp sang `Sales Invoice` (POS Invoice Merge Log).
- App chỉ mở rộng: DocType mới tiền tố `MYPOS` (module `MYPOS`), Custom Field trên DocType chuẩn (fixtures), hook `doc_events`,
  API whitelisted (`mypos/mypos/api/`), frontend React riêng (`pos/`).
- Trạng thái pha chế nằm ở Custom Field `custom_kitchen_status` (không dùng field `status` gốc), chỉ đặt khi đơn đã Paid.
- `Branch` là nguồn cấu hình DUY NHẤT (thương hiệu, SePay, company); chi nhánh lấy từ `POS Profile.branch`.

## Cấu trúc thư mục

```text
mypos/                      gốc app (gốc repo GitHub)
├── pyproject.toml, README.md, CLAUDE.md
├── docs/                   tài liệu (file này)
├── pos/                    frontend React + Vite (build ra mypos/public/pos, mypos/public/order)
└── mypos/                  package Python
    ├── hooks.py, modules.txt ("MYPOS"), patches.txt
    ├── setup/              install.py (after_install, after_migrate), roles.py (PERMS: nguồn chuẩn quyền)
    ├── fixtures/           custom_field.json, property_setter.json, role.json
    ├── desktop_icon/       4 Desktop Icon
    ├── public/             js/ (form Desk), images/, pos/ + order/ (output build, không commit)
    ├── www/                pos.html/.py (/pos/*), mypos_order.html/.py (/order/<token>)
    ├── selfcheck/          script tự kiểm (docs/testing.md)
    └── mypos/              module "MYPOS"
        ├── api/            pos_api, customer_order_api, customer_display_api, order_status_api
        ├── doctype/        DocType MYPOS * + package hook (pos_invoice_hooks, pos_shift_hooks, pos_profile_hooks, sepay, branch_config)
        ├── workspace/      4 workspace theo vai trò
        └── sidebar/mypos/  Sidebar "MYPOS" (trùng tên module)
```

## Hướng dẫn

| File | Nội dung |
|---|---|
| [install.md](install.md) | Cài trên bench mới, cấu hình sau cài (checklist), kiểm nhanh |
| [deploy.md](deploy.md) | Triển khai thật: socket.io, nginx, gunicorn, Redis, host_name, treo TV |
| [testing.md](testing.md) | Chạy script tự kiểm bằng `bench execute` |
| [code-standards.md](code-standards.md) | Quy ước đặt tên, DocType JSON, hook, import path |

## Quy tắc nghiệp vụ (`rules/`)

| File | Phần |
|---|---|
| [branch.md](rules/branch.md) | Branch: cấu hình duy nhất, POS Profile bắt buộc Branch, checklist cấu hình cửa hàng |
| [pos_profile.md](rules/pos_profile.md) | Khách vãng lai theo POS Profile |
| [roles.md](rules/roles.md) | 3 role POS, bảng quyền, mở / đóng ca, hủy đơn, phân quyền màn POS và API |
| [pos_invoice_hooks.md](rules/pos_invoice_hooks.md) | Custom Field POS Invoice, trạng thái thanh toán / pha chế, thẻ bàn |
| [menu.md](rules/menu.md) | MYPOS Menu, giá, Item Group, ảnh món |
| [options.md](rules/options.md) | Tùy chọn món động, phụ thu topping, CTKM theo tổng qty |
| [sepay.md](rules/sepay.md) | VietQR + webhook SePay |
| [order-qr.md](rules/order-qr.md) | Web đặt món QR của khách, bảo mật phiên |
| [customer_display.md](rules/customer_display.md) | Màn khách `/pos/customer`, MYPOS Banner |
| [order_status.md](rules/order_status.md) | Màn theo dõi đơn `/pos/status` (treo TV) |
| [realtime.md](rules/realtime.md) | Phiên bản thay đổi theo POS Profile, realtime socket.io |
| [workspace.md](rules/workspace.md) | Workspace / Sidebar / Desktop Icon |

Ghi chú: các file `rules/` giữ lịch sử quyết định theo ngày và mã commit của repo phát triển gốc; mã commit đó không có trong repo này.
