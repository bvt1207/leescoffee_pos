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

## 3. Việc cần xem và chỉnh sửa (theo ưu tiên — CHỈ LÀ KẾ HOẠCH, chờ Van duyệt rồi mới sửa code)

### A. (CAO, bảo mật) `sepay_webhook` chưa xác thực `sepay_api_key`
- **File/hàm:** `leescoffee_pos/leescoffee_pos/doctype/sepay/sepay.py::sepay_webhook()` (`allow_guest=True`);
  helper mới `_verify_sepay_key(invoice)` (đặt trong `sepay.py`); có thể dùng lại logic lấy branch
  trong `branch_config.py::get_va_bank_config()`.
- **Rủi ro hiện tại:** ai biết `payment_code` (in trên QR/nội dung chuyển khoản) và số tiền là có thể
  POST webhook giả → đơn bị submit thành Paid, đi vào pha chế mà không có tiền thật.
- **Kế hoạch:**
  1. `_verify_sepay_key(invoice)`: `invoice.pos_profile` → `POS Profile.branch` → đọc key bằng
     `get_decrypted_password("Branch", branch, "sepay_api_key", raise_exception=False)`.
  2. Đọc header `frappe.request.headers.get("Authorization")`, yêu cầu dạng `Apikey <key>`;
     so bằng `hmac.compare_digest(received, expected)`. Thiếu header / sai / Branch chưa có key
     → `raise frappe.PermissionError`.
  3. Gọi **ngay sau khi tìm được invoice** (sau bước khớp `payment_code`, trước idempotent/số tiền).
  4. Thêm `except frappe.PermissionError: raise` **trước** `except Exception` để lỗi đi thẳng
     (HTTP 403), không bị nuốt thành `frappe.throw("Lỗi xử lý webhook SePay...")`.
  5. Chống xử lý lặp theo `transaction_ref`: nếu đã có POS Invoice khác mang cùng
     `transaction_ref = transaction_id` → trả `already_processed`, không submit lại.
- **Cần xác minh:** định dạng header chính xác theo tài liệu/cấu hình SePay. Frappe có tự xử lý
  header `Authorization` với scheme lạ trước khi vào hàm không (chưa kiểm chứng; test ở TC2–TC4).
- **Test (Postman + bench console):**
  - TC1: không gửi header `Authorization` → 403, invoice vẫn Draft.
  - TC2: `Authorization: Apikey sai` → 403, invoice vẫn Draft, có Error Log.
  - TC3: key đúng → Paid, `docstatus=1`, `payment_status="Đã thanh toán"`.
  - TC4: gửi lại TC3 → `already_processed: true`, không submit lại.
  - Console: `frappe.utils.password.get_decrypted_password("Branch", "<branch>", "sepay_api_key")` khớp key bên SePay.
- **Sau khi sửa:** đổi API key (cả Branch lẫn SePay) nếu key từng lộ (commit, ảnh chụp, log).

### B. (TRUNG BÌNH) `payment_status` không nhất quán
- **Chuẩn đề xuất:** `Chưa thanh toán` (mặc định khi tạo) → `Đang chờ` (đã sinh QR) →
  `Đã thanh toán` (webhook hoặc tiền mặt) / `Hủy`.
- **Mọi nơi ĐẶT giá trị:**
  - Fixture Custom Field `POS Invoice.payment_status`: Select, default `Chưa thanh toán`.
  - `sepay.py::generate_qr_for_invoice` dòng 71 đặt `"Chưa thanh toán"` (→ nên là `"Đang chờ"`);
    dòng 51 và 86 trả về giá trị này.
  - `sepay.py::sepay_webhook` dòng 283 đặt `"Đã thanh toán"`.
  - `api/pos_api.py::pay_cash` **không đặt** → đơn tiền mặt Paid nhưng `payment_status` vẫn
    `Chưa thanh toán` (cần quyết: đặt `Đã thanh toán` trong `pay_cash`).
  - `"Hủy"`: không chỗ nào đặt (`cancel_draft_order` xóa hẳn đơn).
- **Mọi nơi ĐỌC giá trị:**
  - `sepay.py` dòng 207 (`Đã thanh toán` → idempotent), dòng 215 (`Hủy` → lỗi).
  - `api/pos_api.py::cancel_draft_order` dòng 656 (`Đang chờ` → cần `force`).
  - `api/pos_api.py` dòng 546 (`get_orders`), 599 (`get_order_detail`), 637 (`pay_cash`) trả về frontend.
  - `pos/src/pages/Orders.tsx` dòng 132, 141 (chặn hủy/hiện cảnh báo QR), 177 (tag "Chờ QR").
  - `pos/src/types.ts` dòng 73, 104, 133 (`payment_status: string`).
- **Rủi ro hiện tại:** tag "Chờ QR" không bao giờ hiện; hủy được đơn đã sinh QR mà không cần
  `force` → có thể xóa đơn khách đã chuyển tiền (webhook đến sau sẽ không tìm thấy đơn).
- **Test:** TC1 sinh QR → `payment_status="Đang chờ"`, Orders hiện "Chờ QR"; TC2 hủy đơn đó
  không `force` → bị chặn; TC3 `pay_cash` → `Đã thanh toán`; TC4 reload Orders → giữ nguyên.

### C. (TRUNG BÌNH) Webhook quét toàn bộ Draft để khớp mã
- **File/hàm:** `sepay.py::sepay_webhook()` bước 3 (`frappe.get_all` mọi POS Invoice Draft có
  `payment_code`, rồi `normalize_code` từng dòng trong Python).
- **Rủi ro:** chậm dần khi Draft cũ tích lũy (liên quan mục E "dọn Draft cũ"); không lỗi đúng/sai.
- **Đề xuất:** tra trực tiếp trong DB theo mã chuẩn hóa, vd. điều kiện
  `UPPER(REPLACE(REPLACE(payment_code,'-',''),' ','')) = %(normalized)s` với `docstatus = 0`,
  `limit 1`. Không thêm Custom Field mới (tránh migrate). Giữ hàm `normalize_code` cho `content`.
  Lưu ý: `normalize_code` bỏ mọi ký tự không phải chữ/số; SQL chỉ bỏ `-` và khoảng trắng — đủ với
  định dạng `POS-{invoice_name}-{YYYYMMDD}-{hex}` nếu naming series chỉ chứa `-`. Cần xác minh naming series.
- **Test:** TC1 webhook mã gốc có `-` → khớp; TC2 nội dung không có `-`/viết thường → vẫn khớp;
  TC3 mã không tồn tại → lỗi "Không tìm thấy POS Invoice", Error Log.

### D. (THẤP) `brand_banner` trong `get_brand_info`
- **File/hàm:** `branch_config.py::get_brand_info()` dòng 95 đọc `settings.brand_banner`;
  `get_branch_config()` dòng 42 đọc `branch.brand_banner`. JSON Settings trong repo **không có**
  field `brand_banner`; Branch vẫn có Custom Field `brand_banner`. Frontend: `types.ts` `banner: string`.
- **Rủi ro (chưa xác minh):** nếu Branch không có banner, biểu thức đọc tới `settings.brand_banner`;
  field không còn trên Settings có thể gây lỗi khi gọi `get_pos_config` → màn POS không load.
- **Test (bench console):** `frappe.get_single("Leescoffee POS Settings").get("brand_banner")`;
  gọi `get_brand_info("<branch không có banner>")` xem có lỗi không. Hướng sửa nếu lỗi: dùng
  `settings.get("brand_banner")` hoặc bỏ hẳn banner.

### E. Đã biết (chưa xếp ưu tiên chi tiết)
- Test thật `pay_cash` và QR SePay qua `/pos`.
- Nút "Khách đã lấy" cho Take Away (`confirm_pickup` hiện chỉ xử lý buzzer Dine In).
- Toast realtime giữa các máy (Kitchen đang poll 5 giây).
- Dọn kiểu `MenuItem` trong `types.ts` (`api.getMenuItems` đang trả `unknown[]`).
- Dọn đơn Draft cũ (đang giữ thẻ rung + làm chậm webhook, mục C).

### F. Refactor frontend `pos/src` (giữ nguyên logic và giao diện)
Kế hoạch đầy đủ đã trình Van ngày 2026-10-31; mỗi bước một commit, Van test rồi mới làm bước sau.
Kiểm tra type: trong `pos/` chạy `../../node_modules/.bin/tsc --noEmit -p . --noUnusedLocals`
(TS 5.9.3 ở `PROJECTPOS/node_modules`, khác bản @types React 18/router 6 trong `pos/package.json`).

| Bước | Nội dung | Trạng thái |
|---|---|---|
| d1 | `global.css`: định dạng, gộp `body` + `.pos-status__badge`, 10 token màu mới, xóa 26 khối của 19 class mồ côi | **Xong — `afe5598`, Van test Pass** |
| d2 | Sắp lại thứ tự mục CSS, gộp các `@media` cùng breakpoint (rủi ro thứ tự cascade) | Chờ duyệt |
| a | Xóa biến/import/action thừa (`ICE_SUGAR`, `get`, `add`, `remove`, `setNote`, `modeOfPayment`), `useEffect` toast lặp ở Kitchen, TODO cũ, thụt lề | Chờ duyệt |
| b | Dọn `types.ts` (`MenuItem` theo API thật, gộp `OrderItem`, `CartLine`, `PosConfig.user?`) | Chờ duyệt |
| c | `lib/format.ts`: `formatMoney`, `typeLabel`, `timeLabel`, `errorMessage` | Chờ duyệt |
| e | Component `Modal`, `Tabs`; tách Orders/Kitchen/CartPanel/CustomerPicker; `useCallback` cho `onClose` | Chờ duyệt |
| f | A11y nhẹ (role/aria cho modal, tab, segmented) | Chờ duyệt |

Quyết định đang chờ cho refactor: (1) bỏ `board` + `getStatusBoard` trong Orders; (2) bỏ alert lỗi
hiện 2 lần ở POS; (3) Modal chung giữ nguyên hành vi hay đồng nhất Esc/khóa cuộn/focus;
(4) backend `get_pos_config` thiếu `user` → menu người dùng không hiện (task backend riêng).

## 4. Quyết định đang chờ Van
- Duyệt kế hoạch A–D trước khi sửa code.
- `on_submit` hook còn bỏ qua khi thẻ đã `Đang dùng` (không ném lỗi) — có siết lại không.

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
