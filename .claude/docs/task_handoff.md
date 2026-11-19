# Task Handoff — Leescoffee POS

> Cập nhật 2026-11-14 (web đặt món QR giai đoạn 1). Mục nào không ghi "đã test" là **chưa xác minh trên bench**.
> Đọc file này đầu phiên mới.

## 0d. Bỏ chấm thẻ món + CTKM hiện sẵn trong giỏ (2026-11-19, chỉ frontend) — CHỜ VAN TEST
- `MenuGrid.tsx`: bỏ chấm `.pos-menu-card__dot`. `CartPanel.tsx`: chip CTKM dưới tóm tắt ("Giảm 5% · tên", "+N", dòng tặng "Tặng · tên"),
  bỏ nhãn ngắn "−5%" + tooltip; chân giỏ thêm dòng tên chương trình dưới "Khuyến mãi". `global.css`.
- [Unverified] Dòng tặng có `rules` hay không tùy ERPNext ghi `pricing_rules` trên dòng tặng; không có → chip chỉ "Tặng".
- `npx tsc --noEmit` sạch; chưa thử trên trình duyệt.

## 0c. Bỏ OptionModal + nhập số lượng trực tiếp trong giỏ (2026-11-19, chỉ frontend) — ĐÃ TEST PASS trên bench DEV (`3e9e7cd`)
- Món 1 size có tùy chọn: thêm thẳng giỏ (mặc định), dòng tự mở chip; xóa `components/OptionModal.tsx` (**xóa tay trên bench**).
  Lý do: thêm 1 bước bấm; chỉnh tùy chọn ở một chỗ (giỏ). `ItemModalFrame` chỉ còn SizeModal dùng (bỏ `footer` + CSS chân giá).
- Giỏ: `QtyInput` gõ số lượng (1–999, Enter/rời ô áp dụng, Esc hủy, sai → về số cũ); `store/cart.ts` thêm `setQty`, `MAX_LINE_QTY`.
- `npx tsc --noEmit` sạch; chưa thử trên trình duyệt.

## 0b. Lưới món /pos + tab Item Group (2026-11-19) — ĐÃ TEST PASS trên bench DEV (`9b611ed`; hành vi OptionModal đã thay ở 0c)
- Backend tối thiểu (Van duyệt): `mypos_menu.py` thêm khóa `item_group` vào payload món (cùng truy vấn Item đã có). /order không nhận khóa này (`_public_menu`).
- Frontend: `MenuGrid.tsx` (tab nhóm sticky, tìm toàn bộ, thẻ ảnh + tên + chấm), `SizeModal.tsx` (hàng giá), mới `ItemModalFrame.tsx`,
  `OptionModal.tsx`, `OptionChips.tsx` (CartPanel dùng chung), `store/menuFilter.ts`; `types.ts`, `global.css`.
- Hành vi mới: món 1 size có tùy chọn mở `OptionModal` thay vì thêm thẳng giỏ. Chi tiết: skill `pos-ui`, `rules/leescoffee_pos/menu.md` §6–7.
- `npx tsc --noEmit` sạch; chưa thử trên trình duyệt.

## 0a. Làm gọn Cart Panel /pos (2026-11-19, chỉ frontend) — ĐÃ TEST PASS trên bench DEV (`3077eec`)
- Sửa `pos/src/components/CartPanel.tsx`, `pos/src/pages/POS.tsx`, `pos/src/styles/global.css`. Không đổi backend, logic giỏ/giá/CTKM/điểm/topping.
- Dòng món thu gọn (tóm tắt 1 dòng + stepper + giá), 1 dòng mở chip, bấm ngoài thu; chip gọn (mặt 30px, vùng chạm 44px);
  chân giỏ cố định (ghi chú + đổi điểm gập, tổng, cảnh báo, Tạo đơn); chỉ danh sách món cuộn; 1024px giữ 2 cột.
- Chi tiết: skill `pos-ui` (`layout.md` mục Giỏ hàng, `states.md` CartPanel). `npx tsc --noEmit` sạch; Van đã test trên bench DEV: Pass.
- [Inference] Màn 768px cao, Dine In + khách có điểm + đủ dòng KM/phụ thu/đổi điểm + cảnh báo: vùng danh sách món còn rất thấp (ước tính ~1 dòng) — cần Van kiểm tra.

## 0. Web đặt món QR cho khách (2026-11-14)
- **Giai đoạn 1 (backend) — ĐÃ TEST PASS 2026-11-14** (self-test 65/65; `d64e1d7`, `948d1bc`, `99fdf30`, `17b5d85`, `fa4844e`). Rule: `rules/leescoffee_pos/order-qr.md`.
  Self-test: `.claude/docs/order_qr_selftest.py` (`run_order_qr_selftest()`).
  Gồm cả mục A (webhook xác thực API key) — sau khi deploy phải điền `sepay_api_key` ở Branch và
  cấu hình bên SePay khớp key, nếu không mọi webhook bị 403.
- **Giai đoạn 2 (frontend `/order`) — code xong 2026-11-14, CHỜ VAN TEST.** Chi tiết: `order-qr.md` §8.
  Trang shell tên `mypos_order` (không phải `order` — trùng trang của ERPNext). Build: `npm run build` (cả POS + order).
- **Sửa hiệu năng `/order`** (debounce preview, poll có điều kiện, `poll.ts`) — `a1d75c9`, chờ Van test.
- **"Đơn của tôi" lưu theo khách + giỏ localStorage + Thoát/F5** (2026-11-15) — ĐÃ TEST PASS (`4e9629b`, `fbbc4ac`).
  Backend: `get_my_orders` theo Customer + branch (active/history), `cart_key`, rate `orders_mobile`/`orders_ip`.
  Frontend: `cart.ts` (lưu giỏ), `OrderApp.tsx`, `MyOrdersPanel.tsx`. Self-test: `.claude/docs/order_history_selftest.py`
  (`run_order_history_selftest()` — dán `order_qr_selftest.py` trước, hàm tự chạy lại bộ cũ). Rule: `order-qr.md` §3, §4, §8.
- Tồn đọng: OTP → đổi điểm; Web Push; xem `order-qr.md` §7.

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
| `get_order_detail` trả thêm `size` từng món (`_size_labels`: 1 truy vấn gộp, Item Variant Attribute "Size", `abbr` → fallback `attribute_value`; món thường = "") | Đã test (`5d10359`) |
| In hóa đơn (`ReceiptModal`, khổ 80mm): chỉ đơn đã thanh toán; sau `pay_cash` / QR Paid tự sang tab Đã thanh toán và mở modal **bắt buộc** in (không ×/Đóng/Esc/nền; "Bỏ qua in" có xác nhận chỉ hiện sau lần bấm In đầu); in lại từ panel chi tiết bằng modal thường | Đã test (`7f1246c`) |
| Màn Pha chế, tab Chưa làm: nút "In i/n" in 1 tem/ly (`CupLabels`, khổ `--pos-label-width/height` mặc định 50x30mm); nút "In phiếu" in phiếu pha chế tổng (`ReceiptModal kind="kitchen"`); "Đã làm" khóa tới khi đã in tem hoặc phiếu | Đã test (`680e169`) |

| Đổi điểm Loyalty (backend): `create_draft_order(redeem_points)` → giảm thẳng Grand Total (`apply_discount_on="Grand Total"`, `discount_amount = điểm × conversion_factor`, field `POS Invoice.redeemed_points`); `on_submit` gọi `_record_redemption` ghi Loyalty Point Entry âm (hạn = posting_date + `expiry_duration`, mặc định 365); API `get_customer_loyalty(customer, order_total)`. Không dùng `redeem_loyalty_points` gốc, giữ `allow_partial_payment = 0` | Đã test (`f58d68b`, `63b8126`) |
| Đổi điểm Loyalty (UI `/pos`): chip hạng + điểm dưới ô khách, ô "Dùng điểm" trong giỏ (stepper 0..`max_redeem_points` theo tổng giỏ, gọi lại `get_customer_loyalty` trễ 300ms), Tạm tính / Giảm / Còn phải trả; gửi `redeem_points`; hóa đơn in dòng "Giảm giá đổi điểm" (`get_order_detail` thêm `discount_amount`, `redeemed_points`) | Đã test (`fbd6745`) |
| CTKM tự áp (backend): `create_draft_order` bật Pricing Rule (`ignore_pricing_rule = 0`, không ép rate) qua `_build_invoice` (dựng trong bộ nhớ: `set_missing_values` + `calculate_taxes_and_totals`); điểm đổi tối đa tính trên tổng sau luật; API `preview_pricing` (không ghi DB); `get_order_detail` thêm `price_list_rate`, `discount_percentage`, `pricing_rules` | Đã test (`88ebf01`) |
| Workspace `leescoffee_pos`: card "Lee's Coffee Setup" thêm Branch, POS Opening Entry, POS Closing Entry (`link_count` 6, `modified` 2026-11-08 15:00) — xóa `Workspace Link` trước khi migrate (rule `workspace.md` §7) | Đã test (`724e2dc`) |
| Workspace `leescoffee_pos`: card "Lee's Coffee Setup" thêm link MYPOS Option Group (`link_count` 7, `modified` 2026-11-13 15:00); xóa `Workspace Link` trước khi migrate | Đã test (`eb9903e`) |
| Workspace `leescoffee_pos`: card "Lee's Coffee Setup" thêm link MYPOS Order QR (`link_count` 8, `modified` 2026-11-15 10:00); xóa `Workspace Link` trước khi migrate, kỳ vọng 9 dòng | Đã test (`ce9a16e`) |
| Đổi tên DocType `Leescoffee Menu`/`Menu Item`/`Buzzer` → `MYPOS Menu`/`MYPOS Menu Item`/`MYPOS Buzzer` (nhánh `refactor/rename-mypos-doctypes`, patch `v1_rename_mypos_doctypes` pre_model_sync, workspace `modified` 2026-11-15 12:00); kiểm tra `.claude/docs/mypos_rename_check.py` | Đã test (`fb935d7`, `0b35c20`, `c78d4e4`) |
| Workspace `leescoffee_pos`: đổi tên card "Lee's Coffee Setup" → "MYPOS Setup" (`label` Card Break + `card_name` trong `content`, `modified` 2026-11-15 15:00); xóa `Workspace Link` trước khi migrate, kỳ vọng 9 dòng | Đã test (`94e1055`) |
| Tùy chọn món động giai đoạn 3 (UI `pos/src`): chip tùy chọn ở giỏ (`lib/options.ts`, khóa giỏ item+options, mặc định, chặn nhóm bắt buộc), gửi `options` cho preview/tạo đơn, hiển thị `options` ở Orders/Kitchen/hóa đơn/phiếu/tem; bỏ đường/đá cứng (rule `options.md` §8) | Đã test (`2f1d629`) |
| Màu loại đơn: token `--pos-takeaway-*` (xanh dương) / `--pos-dinein-*` (xanh lá ngọc), `OrderTypeChip` dùng chung ở Orders (thẻ + chi tiết) và Kitchen; thẻ Pha chế thêm viền trái theo loại đơn (viền trên vẫn là thời gian chờ) | Đã test (`528c104`) |
| Thống nhất module `Leescoffee POS` cho 3 DocType JSON (Menu, Menu Item, Buzzer; thêm `modified` 2026-11-08 16:00) — sửa PermissionError của user thường ở `/desk/leescoffee_pos` | Đã test (`f32640d`) |
| 3 role `POS CASHIER`/`POS KITCHEN`/`POS MANAGER`: fixture `role.json`, quyền qua patch `v1_create_pos_roles` + `after_install` (không fixture Custom DocPerm); bảng quyền + role ERPNext đi kèm MANAGER ở `rules/leescoffee_pos/roles.md` | Đã test (`b4fa3f4`) |
| POS MANAGER thêm quyền Branch (S R W C); chạy lại patch bằng nhãn `#` trong `patches.txt` | Đã test (`2caf0df`) |
| Phân quyền màn POS theo role: `get_pos_config` trả `roles`/`nav`/`kitchen_tabs`/`kitchen_transitions`; `get_kitchen_orders`, `set_kitchen_status` chặn theo role; "Đã hoàn thành" chỉ hôm nay (backend); frontend ẩn menu/tab/nút, KITCHEN tự về `/pos/kitchen` (rule `roles.md` §7) | Đã test (`2be2ae8`) |
| Tùy chọn món động giai đoạn 1+2 (backend): DocType `MYPOS Option Group`/`Value`/`Target`, Custom Field `POS Invoice Item.options`, quyền; `get_menu_items` trả `option_groups`, `_normalize_items` kiểm tra `options`, `get_order_detail`/`get_kitchen_orders` trả `options` (rule `options.md`). Giai đoạn 3 (UI) chưa làm | Đã test (`12137bd`) |
| CTKM tính theo tổng qty mỗi mã trong hóa đơn (`_apply_rules_on_total_qty`: hóa đơn tạm 1 dòng/mã rồi chép luật sang các dòng thật); không dùng `is_cumulative`/`mixed_conditions`; luật tặng sản phẩm chưa gộp | Đã test (`5b17b6c`) |
| POS KITCHEN `desk_access = 1` (role.json, `ROLES`, patch `v1_kitchen_desk_access`: bật role + lưu lại user KITCHEN đang Website User); `_require_sale_role` chặn `create_draft_order`/`pay_cash`/`cancel_draft_order` cho role ngoài CASHIER/MANAGER/System Manager/Administrator; self-test cũ bỏ qua ca POS nếu người mở ca thiếu role; script `.claude/docs/kitchen_desk_check.py` | Đã test (`3abc40f`, bench DEV) |
| Phụ thu topping giai đoạn 1 (backend): `extra_price` hiện trên form (≥ 0), `option_groups`/`options` có giá, `_apply_option_surcharge` = 1 dòng Taxes and Charges kiểu Actual (sau CTKM, idempotent, tài khoản POS Profile → Company), `total_surcharge` ở preview/chi tiết đơn; quy tắc `options.md` §9; script `.claude/docs/surcharge_check.py`. Giai đoạn 2 (UI) chưa làm | Đã test (`c97f685`, bench DEV: script + self-test + đóng ca) |
| Phụ thu topping giai đoạn 2 (UI `/pos` + `/order`): chip "+giá", giá dòng giỏ gồm phụ thu, dòng "Phụ thu topping" từ preview, Orders/hóa đơn/"Đơn của tôi" kèm giá tùy chọn; Kitchen/tem chỉ tên (`options.md` §9b) | Đã test (`cabdabe`, bench DEV) |

Commit đồng bộ: `475127a` (API), `084a317` (frontend), `993066e` (skill pos-ui), `59a576b` (rule thẻ rung).

**Giới hạn đã biết của đổi điểm Loyalty:**
- Dòng âm không chia theo từng dòng tích như `redeem_against` của ERPNext: khi dòng tích cũ hết hạn trước dòng âm, số dư bị trừ thêm (có thể âm). Muốn chính xác cần tách dòng âm FIFO theo dòng tích (task riêng).
- Mức đổi tối đa tính theo `qty × rate` (trước thuế cộng thêm, nếu có).
- Lệch có sẵn: QR SePay dựng theo `grand_total`, webhook so `rounded_total` — lỗi nếu hai số khác nhau do làm tròn.

**Giới hạn đã biết của chức năng in:**
- `afterprint` xảy ra cả khi bấm Hủy trong hộp thoại in → modal bắt buộc vẫn báo "Đã in hóa đơn thành công" và "Đã làm" vẫn mở khóa.
- Trạng thái "đã in" ở màn Pha chế chỉ nằm trong state, tải lại trang là mất.
- QR Paid được phát hiện theo chu kỳ poll 10 giây của Orders; rời trang Orders trước khi tiền về thì không bật modal bắt buộc (vẫn in lại tay được).
- Thẻ ở màn Pha chế chưa hiện size (`get_kitchen_orders` không trả size); tem và phiếu có size vì lấy từ `get_order_detail`.
- `@page size` được `lib/print.ts` chèn tạm cho từng lần in (80mm cho hóa đơn/phiếu, khổ tem cho tem); khổ giấy thật vẫn phụ thuộc driver máy in.

## 3. Việc cần xem và chỉnh sửa (theo ưu tiên — CHỈ LÀ KẾ HOẠCH, chờ Van duyệt rồi mới sửa code)

### A. (CAO, bảo mật) `sepay_webhook` chưa xác thực `sepay_api_key` — ĐÃ XỬ LÝ 2026-11-14, đã test Pass (self-test 8c–8n: sai/thiếu key 403, idempotent, save/submit dưới Administrator; `99fdf30`, `17b5d85`)
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

### D. ĐÃ XỬ LÝ (2026-11-08) `brand_banner` / bỏ Leescoffee POS Settings
- Van sửa trên bench: `get_brand_info()` chỉ đọc Branch bằng `branch.get(...)` (hết `AttributeError`).
- Giai đoạn 1 (Đã test Pass — `1b92c1a`, `b041c8e`): Branch là nguồn cấu hình duy nhất, thêm Custom Field
  `Branch-company`, `get_default_branch()` lấy từ POS Profile (`resolve_pos_profile_name`),
  `get_pos_config` trả `warnings` khi lệch company. Rule: `.claude/rules/leescoffee_pos/branch.md`.
- **Giai đoạn 2 (Đã test Pass — `b2e1614`):** xóa thư mục `doctype/leescoffee_pos_settings/`, dòng
  fixture `DocType = Leescoffee POS Settings` ở `hooks.py`, patch xóa DocType + bản ghi Single
  (`tabSingles`) + Workspace Link còn sót trên DB.

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
- Phân quyền các API `pos_api` còn lại theo role (`frappe.only_for`) — đề xuất từng hàm ở `rules/leescoffee_pos/roles.md` §8, chưa làm.
- Duyệt kế hoạch A–C trước khi sửa code.
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
| Toast "Mời khách…" chỉ hiện trên máy bấm nút; thu ngân khác máy thấy đơn sau chu kỳ 5 giây. KITCHEN không thấy tab "Đã làm" nên đơn biến mất khỏi màn họ tới khi giao | Chờ realtime (roles.md §7) |
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
