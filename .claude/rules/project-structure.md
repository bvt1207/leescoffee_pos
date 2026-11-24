# Project Structure — Leescoffee POS

> Chuyển nguyên văn từ CLAUDE.md §10 ngày 2026-11-14 (CLAUDE.md chỉ còn tham chiếu). Cập nhật file này
> sau khi Van duyệt task (CLAUDE.md mục 9). Bản cây rút gọn cũ của file này trùng nội dung nên được thay bằng cây đầy đủ dưới đây.

> Đã đối chiếu với đĩa ngày 2026-11-14. Chỉ cập nhật sau khi Van duyệt task (mục 9, bước 3).
> Lưu ý: `PROJECTPOS/leescoffee_pos/` chính là **package Python** của app (chứa
> `hooks.py`, `modules.txt`); repo này không có `pyproject.toml`. Trên bench thật nó
> tương ứng `frappe-benchver16/apps/leescoffee_pos/leescoffee_pos/`.

```text
PROJECTPOS/                        # git repo
├── .claude/
│   ├── CLAUDE.md                  # file này — bộ não dự án
│   ├── CLAUDE.local.md            # ghi chú riêng
│   ├── memory.md                  # index memory (trỏ tới PROJECTPOS/memory/)
│   ├── settings.json, settings.local.json
│   ├── agents/                    # chưa dùng
│   ├── docs/
│   │   ├── task_handoff.md        # bàn giao giữa các phiên
│   │   ├── order_qr_selftest.py   # script bench console tự kiểm tra web đặt món QR
│   │   ├── order_history_selftest.py  # self-test lịch sử đơn theo khách + giỏ
│   │   ├── mypos_rename_check.py  # kiểm tra đổi tên MYPOS Menu/Menu Item/Buzzer
│   │   ├── kitchen_desk_check.py  # kiểm tra KITCHEN vào Desk + chặn API bán hàng theo role
│   │   ├── surcharge_check.py     # kiểm tra phụ thu topping (dòng Actual, sau CTKM)
│   │   ├── orders_shift_check.py  # Orders: Ca hiện tại / Lịch sử (get_orders, get_orders_summary)
│   │   ├── shift_owner_check.py   # mở/đóng ca của chính mình, MANAGER thao tác thay, Only If Creator
│   │   ├── legacy_options_check.py  # options '[]' vs NULL, cột đường/đá cũ không tự điền
│   │   ├── draft_cancel_check.py  # chặn đóng ca khi còn Draft, hủy = Cancelled + lý do, job tự hủy, tiền về sau hủy
│   │   ├── open_orders_check.py   # đóng ca chặn đơn đã thanh toán chưa giao, trạng thái kết thúc có lý do
│   │   ├── table_card_check.py    # thẻ bàn: giữ / nhả theo đơn, hàng chờ thông báo thu ngân (get_serve_queue)
│   │   ├── customer_display_check.py  # màn khách /pos/customer: banner theo POS Profile, chặn KITCHEN, giỏ/đơn/paid/hủy, cô lập user
│   │   ├── walk_in_customer_check.py  # khách vãng lai theo POS Profile: chặn khi chưa cấu hình, is_walk_in, validate profile
│   │   └── reference/             # ảnh tham khảo UI (URY POS, website)
│   ├── rules/
│   │   ├── code-standards.md, project-structure.md, session-management.md
│   │   └── leescoffee_pos/        # branch.md, menu.md, options.md, order-qr.md, pos_invoice_hooks.md,
│   │                              # pos_profile.md, roles.md, sepay.md, workspace.md, customer_display.md
│   └── skills/
│       ├── frontend-design/
│       └── pos-ui/                # SKILL.md, layout.md, states.md, references/, examples/
├── memory/
│   └── memory_note_branding_fallback.md
├── package.json, package-lock.json   # node_modules/ không commit
└── leescoffee_pos/                # package Python của app
    ├── __init__.py
    ├── hooks.py                   # doc_events, website_route_rules (/pos/*), scheduler_events, fixtures
    ├── modules.txt                # "Leescoffee POS" (phải khớp module DocType/Workspace, mục 5)
    ├── patches.txt, patches/      # v1_rename_mypos_doctypes.py (pre_model_sync); v1_remove_pos_settings.py,
    │                              # v1_create_pos_roles.py, v1_kitchen_desk_access.py,
    │                              # v1_clear_legacy_option_default.py, v1_kitchen_outcomes.py,
    │                              # v1_simplify_cancel_review.py, v1_table_card_cleanup.py (post_model_sync)
    ├── config/, templates/
    ├── desktop_icon/leescoffee_pos.json
    ├── workspace_sidebar/leescoffee_pos.json
    ├── fixtures/custom_field.json, role.json, property_setter.json  # property_setter: lọc chuẩn POS Profile trên list POS Invoice
    ├── public/
    │   ├── images/logo.svg
    │   ├── js/pos_opening_entry.js  # doctype_js: form POS Opening Entry (Cashier tự điền + khóa)
    │   ├── js/pos_profile.js      # doctype_js: form POS Profile (Khách vãng lai chỉ gợi ý Customer đang bật)
    │   ├── js/pos_invoice.js      # doctype_js: form POS Invoice (nút "Hủy đơn" / "Xử lý đơn" cho quản lý)
    │   ├── js/pos_invoice_list.js # doctype_list_js: 3 nút "Lọc nhanh" trên list POS Invoice (quản lý)
    │   └── pos/                   # output build Vite (pos.js, pos.css) — sinh khi build
    ├── www/
    │   ├── pos.html               # trang /pos, nạp /assets/leescoffee_pos/pos/pos.js
    │   └── pos.py
    ├── pos/                       # frontend React + Vite (TSX)
    │   ├── package.json, tsconfig.json, vite.config.ts, pos.html, README.md
    │   └── src/
    │       ├── main.tsx (/pos/customer render độc lập), App.tsx, types.ts
    │       ├── pages/             # POS.tsx, Orders.tsx, Kitchen.tsx, Table.tsx (stub), CustomerDisplay.tsx (màn khách)
    │       ├── components/        # AppHeader, MenuGrid (tab Item Group), SizeModal + ItemModalFrame,
    │       │                      # CartPanel + OptionChips (chip tùy chọn), CustomerPicker, BuzzerPicker, QrModal,
    │       │                      # ReceiptModal (hóa đơn / phiếu pha chế), CupLabels (tem ly), customer/BannerCarousel (màn khách)
    │       ├── store/             # cart.ts, search.ts, menuFilter.ts, orderFilter.ts, serveQueue.ts (hàng chờ thông báo thu ngân) (zustand)
    │       ├── lib/               # api.ts, pos-context.tsx, print.ts (window.print + @page tạm), format.ts (ngày giờ, mã đơn),
    │       │                      # serve.ts (poll get_serve_queue 15 giây cho CASHIER, toast + bíp),
    │       │                      # realtime.ts (socket.io-client của Frappe, dùng cho màn khách)
    │       └── styles/global.css
    └── leescoffee_pos/            # module "Leescoffee POS"
        ├── api/
        │   ├── pos_api.py         # whitelisted API cho màn POS/Orders/Kitchen
        │   ├── customer_order_api.py  # API khách (allow_guest + token phiên) cho web đặt món QR + job dọn đơn
        │   └── customer_display_api.py  # màn hình khách /pos/customer: trạng thái theo user (Redis) + banner
        ├── workspace/leescoffee_pos/leescoffee_pos.json
        └── doctype/
            ├── mypos_buzzer/              # thẻ bàn (đổi từ thẻ rung 2026-11-23; tên cũ leescoffee_buzzer)
            ├── mypos_menu/                # menu theo Price List (tên cũ leescoffee_menu)
            ├── mypos_menu_item/           # child table của Menu (tên cũ leescoffee_menu_item)
            ├── mypos_option_group/        # nhóm tùy chọn món + option_resolver.py
            ├── mypos_option_value/        # bảng con: giá trị tùy chọn
            ├── mypos_option_target/       # bảng con: áp dụng cho Item / Item Group
            ├── mypos_order_qr/            # mã QR đặt món theo Branch (.json, .py, .js)
            ├── mypos_banner/              # ảnh banner màn khách (theo POS Profile, trống = mọi profile)
            ├── pos_invoice_hooks/         # doc_events cho POS Invoice + status board; kitchen_status.py (trạng thái pha chế, đơn dở của ca);
            │                              # order_cancel.py (hủy Draft = Cancelled + lý do, mốc hết hạn, job tự hủy)
            ├── pos_shift_hooks/           # doc_events POS Opening/Closing Entry: chỉ ca của chính mình, MANAGER thay
            ├── pos_profile_hooks/         # khách vãng lai theo POS Profile: helper đọc field + validate khi lưu profile
            ├── sepay/                     # sinh VietQR + webhook SePay
            └── branch_config/             # helper cấu hình Branch (SePay, branding, company)
```
