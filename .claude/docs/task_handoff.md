# Task Handoff — Leescoffee POS

## 1. Mục tiêu hiện tại
Làm UI/UX POS hoàn chỉnh, chuyên nghiệp, không mang giao diện "AI chung chung".
- CSS thuần + CSS variables (design token trong một file) — **không MUI/Tailwind**
- **Không hardcode branding Lee's Coffee** — lấy từ `get_brand_info()` qua API
- Tham khảo bố cục URY POS, phù hợp màn hình cảm ứng

## 2. Trạng thái đã xong & đã test trên bench
| Thành phần | Trạng thái |
|---|---|
| Backend `api/pos_api.py` (`get_pos_config`, `get_menu_items`, `create_draft_order`, `get_orders`, `get_order_detail`, `pay_cash`, `generate_qr`, `confirm_pickup`, `get_status_board`) | ✅ Hoàn tất, đã test |
| Route `/pos` (React + Vite, `website_route_rules` map `/pos/*` → `pos`) | ✅ Hoàn tất, đã test |
| Frontend `leescoffee_pos/pos/` build ra `leescoffee_pos/public/pos/` (`pos.js`, `pos.css`) | ✅ Hoàn tất, đã test |
| Nút POS trong Workspace (Link DocType `POS Profile`) | ✅ Hoàn tất, đã test |
| Tạo đơn Draft từ POS (`create_draft_order`) → tự nhảy sang `/pos/orders` | ✅ Hoàn tất, đã test |

## 3. Các sửa đã đồng bộ từ bench về PROJECTPOS
| Sửa | Đã commit PROJECTPOS? | Ghi chú |
|---|---|---|
| Import `..doctype.<module>.<module>` trong `api/pos_api.py` | ✅ `f31e454` | Branch_config, leescoffee_buzzer, leescoffee_menu, sepay, pos_invoice_hooks |
| `create_draft_order` tự điền `uom`/`stock_uom`/`conversion_factor` từ `Item` | ✅ `f31e454` | Resolve `item_code` từ nhiều alias key, tra `Item` |
| `frappe.get_message(exc)` → `str(exc)` | ✅ `f31e454` | Trong `except` quanh `invoice.insert()` |
| `_ensure_opening_entry` dùng lại phiên đang mở của user (`docstatus=1`, `status=Open`), không lọc ngày | ✅ `f31e454` | Filter `user=frappe.session.user`, `pos_profile`, `status=Open`, `docstatus=1`; có thì trả về luôn |

**Chưa đồng bộ / chưa xác minh:**
- Không có item nào chưa đồng bộ — 4 sửa trên đã đầy đủ. File `hooks.py` (Van tự sửa Workspace fixture) vẫn unstaged, **không commit**.

## 4. Việc còn lại chưa test trên bench
- Thu tiền tại quầy (`pay_cash` flow)
- QR SePay (`generate_qr` → webhook SePay submit đơn)
- Dine In + buzzer (gán buzzer khi tạo đơn, reset khi bếp `Đã hoàn thành` + confirm pickup)
- Reload dữ liệu sau reload trang (đơn đã thanh toán vẫn hiện)

## 5. Quy ước bắt buộc
- **Giữ tên `leescoffee_pos`** cho app/package/assets path (`/assets/leescoffee_pos/...`)
- **Không sửa**: `modules.txt`, `workspace/leescoffee_pos.json`, `workspace_sidebar/leescoffee_pos.json`, `desktop_icon/`
- **Không chạy `bench migrate`** (không có DocType/Custom Field mới)
- `pos/` nằm trong package `leescoffee_pos/` (cùng cấp `doctype/`, `api/`)
- Vite `outDir: ../public/pos/` (output `pos.js`, `pos.css` tên cố định)
- Mỗi lần nạp Workspace phải xóa Workspace Link cũ để khỏi nhân bản dòng

## 6. Vấn đề đã biết (chưa sửa)
| Vấn đề | Mức độ | Ghi chú |
|---|---|---|
| Module `"Leescoffee POS"` (trong `modules.txt`, Workspace) vs `"Leescoffee Pos"` (trong 4 DocType JSON) lệch | Trung bình | Đã migrate chạy được, không chặn. Nếu sửa: đổi `modules.txt` + Workspace JSON + `bench migrate` |
| Món `Americano` (và một số món khác) chưa có `Item Price` trong Price List dùng | Thấp | Test tạo đơn sẽ báo lỗi giá; cần nhập giá trong Desk |

## 7. Việc tiếp theo theo thứ tự
1. Cài skills UI/UX vào `.claude/skills/`
2. Lập kế hoạch thiết kế UI (layout, tokens, component breakdown)
3. Code UI từng trang: `POS.tsx` → `Orders.tsx` → `Table.tsx` (stub)

## 8. Cách chạy trên bench (Van tự làm)
```bash
# 1) Copy code PROJECTPOS → frappe-benchver16/apps/leescoffee_pos (copy tay)

# 2) Build frontend
cd frappe-benchver16/apps/leescoffee_pos/pos
npm install && npm run build      # → leescoffee_pos/public/pos/pos.js + pos.css

# 3) Build app Frappe (sinh asset symlink)
cd frappe-benchver16
bench --site <site> build

# 4) Restart
bench restart
```

---

**Lưu ý:** Mọi mục chưa ghi "đã test" đều là **chưa xác minh**. Session mới đọc file này trước khi bắt đầu.