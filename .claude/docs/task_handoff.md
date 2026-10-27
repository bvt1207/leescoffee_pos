# Task Handoff — Leescoffee POS

> Cập nhật 2026-10-27. Mục nào không ghi "đã test" là **chưa xác minh trên bench**.
> Đọc file này đầu phiên mới.

## 1. Mục tiêu hiện tại
Hoàn thiện frontend POS (React/TSX, CSS thuần + biến `--pos-*`, không MUI/Tailwind,
không hardcode branding — lấy từ `get_pos_config` → `get_brand_info()`), sẵn sàng demo.

## 2. Đã xong
| Thành phần | Trạng thái |
|---|---|
| Route `/pos/*` (`website_route_rules` → `www/pos.html`), build Vite → `public/pos/pos.js, pos.css` | Đã test |
| Nút POS trong Workspace | Đã test |
| Tạo đơn Draft (`create_draft_order`) → tự chuyển `/pos/orders` mở đúng đơn | Đã test |
| Chọn / tạo khách (`CustomerPicker`, `search_customers`, `create_customer`) | Van làm trên bench, đã đồng bộ |
| Đường/Đá theo món + ghi chú đơn (`sugar`/`ice` trên POS Invoice Item, `order_note`) | Van làm trên bench, đã đồng bộ |
| Trang Orders mới (tab Chưa thanh toán / Đã thanh toán, chi tiết đơn) + hủy đơn Draft (`cancel_draft_order`, có `force`) | Van làm trên bench, đã đồng bộ |
| Màn Pha chế `/pos/kitchen` (`get_kitchen_orders`, `set_kitchen_status` đi từng bước) | Van làm trên bench, đã đồng bộ |
| Chọn thẻ rung Dine In (`BuzzerPicker`, `get_buzzers` có `available`/`used_by`, `_assign_buzzer`) — mỗi thẻ 1 đơn chưa hoàn thành | Van làm trên bench, đã đồng bộ |
| Toast 5 giây ở màn Pha chế (bấm để đóng sớm) | Van làm trên bench, đã đồng bộ |

Commit đồng bộ: `475127a` (API), `084a317` (frontend), `993066e` (skill pos-ui), `59a576b` (rule thẻ rung).

## 3. Việc còn lại (theo thứ tự đề xuất)
1. Test `pay_cash` (thu tiền mặt tại quầy) trên bench.
2. Test QR SePay qua `/pos` (`generate_qr` → webhook submit đơn). Lưu ý: `generate_qr_for_invoice`
   ghi `payment_status = "Chưa thanh toán"`, còn Orders/`cancel_draft_order` kiểm tra `"Đang chờ"` (xem `rules/leescoffee_pos/sepay.md` §5).
3. Nút "Khách đã lấy" cho Take Away (hiện `confirm_pickup` chỉ xử lý buzzer Dine In).
4. Toast realtime (hiện Kitchen poll 5 giây; cân nhắc `frappe.publish_realtime`/socket.io).
5. Dọn kiểu `MenuItem`: `api.getMenuItems` đang trả `unknown[]`, nên dùng type `MenuItem` trong `types.ts`.
6. Dọn đơn Draft cũ còn tồn (đang giữ thẻ rung theo quy tắc "đang giữ").

## 4. Quyết định đang chờ Van
- `on_submit` hook còn bỏ qua khi thẻ đã `Đang dùng` (không ném lỗi) — có siết lại không.
- CLAUDE.md §3 ghi reset thẻ khi khách nhận món, code reset khi bếp `Đã hoàn thành` — sửa §3 theo quy tắc mới?
- Webhook SePay chưa xác thực API key.

## 5. Quy ước bắt buộc
- Giữ tên `leescoffee_pos` cho app/package/assets (`/assets/leescoffee_pos/...`).
- Không sửa: `modules.txt`, `workspace/leescoffee_pos.json`, `workspace_sidebar/leescoffee_pos.json`, `desktop_icon/`, fixtures DocType trong `hooks.py`.
- `pos/` nằm ở `leescoffee_pos/pos/` (cạnh `hooks.py`); `api/` và `doctype/` nằm trong `leescoffee_pos/leescoffee_pos/`.
- Vite `outDir: ../public/pos/` (output `pos.js`, `pos.css` tên cố định).
- Mỗi lần nạp Workspace phải xóa Workspace Link cũ để khỏi nhân bản dòng.

## 6. Vấn đề đã biết
| Vấn đề | Ghi chú |
|---|---|
| Module `Leescoffee POS` (modules.txt, Workspace) vs `Leescoffee Pos` (DocType JSON) | Giữ nguyên, chỉ ghi chú (CLAUDE.md §5) |
| Một số món (vd. `Americano`) chưa có `Item Price` trong Price List | Nhập giá trong Desk |

## 7. Cách chạy trên bench (Van tự làm — giữ nguyên lệnh cũ)
```bash
# 1) Copy code PROJECTPOS → frappe-benchver16/apps/leescoffee_pos (copy tay)
# 2) Build frontend
cd frappe-benchver16/apps/leescoffee_pos/pos
npm install && npm run build      # → public/pos/pos.js + pos.css
# 3) Build app Frappe
cd frappe-benchver16
bench --site <site> build
# 4) Restart
bench restart
```
> Chưa xác minh: trong repo này `pos/` nằm cạnh `hooks.py` (trong package). Nếu bench
> có thêm 1 cấp `apps/leescoffee_pos/leescoffee_pos/`, đường dẫn bước 2 là `.../leescoffee_pos/leescoffee_pos/pos`.
