# Module Rules: SePay Integration — MYPOS

> Paths: `mypos/mypos/doctype/sepay/sepay.py`,
> helper ở `mypos/mypos/doctype/branch_config/branch_config.py`.
> Đã đối chiếu với code ngày 2026-10-27.

## 1. Quản lý cấu hình SePay

- **Chỉ ở `Branch`** (Custom Field, fixtures): `sepay_enabled` (Check), `sepay_api_key` (Password),
  `sepay_va_account` (Data), `sepay_bank_code` (Data).
- **Mỗi chi nhánh/doanh nghiệp một bộ riêng**: một API key, một VA, một mã ngân hàng.
  Chi nhánh lấy từ `POS Invoice.pos_profile` → `POS Profile.branch`.

### Mục đích `sepay_api_key`

- `sepay_webhook` là `allow_guest=True` (SePay gọi vào không có phiên đăng nhập ERPNext), nên
  ERPNext cần API key để **xác thực webhook thật sự đến từ SePay**.
- SePay gửi header `Authorization: Apikey <key>`; ERPNext so với `sepay_api_key` của Branch
  của invoice (đọc bằng `get_decrypted_password` vì field kiểu Password).
- Key ở Branch **phải trùng** key cấu hình webhook bên SePay.
- **Đã kiểm tra key (2026-11-14, đã test Pass)**: `_verify_sepay_key(invoice)` gọi ngay sau khi khớp
  `payment_code`; nhận header `Authorization: Apikey <key>` hoặc `?key=<key>` trên URL webhook; sai/thiếu → 403
  (`PermissionError` không bị bọc) + Error Log. Branch chưa có key → mọi webhook bị từ chối.
  Chống xử lý lặp theo `transaction_ref`. Chi tiết + lưu ý 401 của Frappe: `order-qr.md` §3.
  Error Log theo đúng lý do (2026-11-25, vẫn 403): "SePay webhook: đơn không có POS Profile" / "… POS Profile thiếu Branch" /
  "… Branch chưa cấu hình API key" / "… sai hoặc thiếu API key" (key gửi kèm sai hoặc không có).
- **Chỉ đọc Branch** cho SePay config (branding cũng chỉ đọc Branch — xem `branch.md`).
- **Không dùng** `merchant_code`, `secret_key`, `env`, `callback_url` (đã loại bỏ).

Helper trong `branch_config.py`:

- `get_sepay_config(branch_name=None)` → `{enabled, api_key, va_account, bank_code}`.
- `get_va_bank_config(invoice_name)` → `{va_account, bank_code, branch}`; ném lỗi nếu Branch
  tắt SePay hoặc thiếu VA/bank code.
- `get_sepay_qr_url(va_account, bank_code, amount, payment_code)` → URL ảnh VietQR.

## 2. `generate_qr_for_invoice(invoice_name)` (whitelisted)

POS frontend gọi qua `api/pos_api.py::generate_qr`.

1. Nếu invoice **đã có `payment_code`** → trả lại mã cũ + QR URL dựng lại, `idempotent: True`.
2. Lấy VA + bank code của chi nhánh qua `get_va_bank_config(invoice_name)`.
3. Sinh `payment_code = POS-{invoice_name}-{YYYYMMDD}-{6 hex}`.
4. Dựng VietQR URL theo `invoice.grand_total`.
5. Lưu vào invoice: `payment_code`, `payment_status = "Đang chờ"` (2026-11-25; trước `"Chưa thanh toán"`), xóa `transaction_ref`
   và `sepay_payment_log`; chỉ `save()` — invoice **vẫn Draft**.
6. Trả `{invoice_name, payment_code, qr_url, amount, payment_status, idempotent}`.

## 3. Webhook `sepay_webhook()` (`allow_guest=True`)

Payload theo format SePay: `content`/`code`, `transferAmount`, `id`/`referenceCode`,
`transferType`, `gateway`, `transactionDate`.

1. Thiếu JSON / thiếu `content` / `transferAmount <= 0` → ném lỗi.
2. `transferType` có giá trị khác `"in"` → trả `{success: False}` (bỏ qua giao dịch tiền ra).
3. Tìm đơn `docstatus` 0, 1 **hoặc 2** (`_find_invoice_by_code`, thêm 2 từ 2026-11-23): (a) `payment_code = content` khớp chính xác
   (cột có `search_index`, fixture 2026-11-14); (b) dự phòng: so mã chuẩn hóa bằng SQL (bỏ `- . / _` và
   khoảng trắng, viết hoa) chỉ trong đơn tạo 30 ngày gần nhất, `LIMIT 2`; khớp ≥ 2 đơn → log, coi như không thấy.
4. Không khớp → `log_error` + ném lỗi. Khớp → **xác thực API key** (`_verify_sepay_key`) TRƯỚC mọi nhánh sau.
4b. Đơn đã submit (docstatus 1): **không bao giờ xác nhận lại.** `already_processed` CHỈ khi
   `payment_status = "Đã thanh toán"` VÀ `transaction_ref == id` (id khác rỗng) → `{success, already_processed, invoice_name}`.
   Còn lại (giao dịch thứ hai cùng mã, đơn đã thu tiền mặt) → Error Log "SePay: giao dịch cho đơn đã submit, cần đối soát",
   trả `{success: True, needs_review: True, message}` (không `already_processed`, không invoice_name/dữ liệu khách).
4c. Đơn đã hủy (docstatus 2, 2026-11-23 — ĐÃ TEST PASS `0553fd2`): `_record_late_payment` — khóa dòng; `transaction_id` đã có trong
   `custom_late_payment_ref` → trả cùng phản hồi, không ghi thêm (idempotent). Ngược lại: `custom_late_payment = 1`, nối mã vào `custom_late_payment_ref`
   (≤ 140 ký tự), nối giao dịch vào `sepay_payment_log` (50 mục cuối), Comment "Tiền về sau khi hủy…", Error Log, `notify_profile_managers(...,
   fallback_all=True)`. Trả `{success: True, needs_review: True, message}`. Không thanh toán lại / không mở lại đơn. Không có `transaction_id` → không chống trùng được.
5. Đơn Draft: **luôn đi tiếp** (khớp số tiền → ghi payments → submit). Không có nhánh trả sớm nào cho Draft.
   `id` đã nằm ở `transaction_ref` của đơn khác chỉ ghi Error Log "SePay: transaction_id đã có trên đơn khác".
   (Lỗi 2026-11-14, LCNH-00279: nhánh cũ "id đã dùng ở đơn khác → already_processed" làm đơn Draft không được
   thanh toán; nhánh "payment_status = Đã thanh toán → already_processed" cũng đã bỏ cho Draft.)
   `payment_status == "Hủy"` → ném lỗi.
6. Kiểm tra số tiền: `|transferAmount − (rounded_total or grand_total)| ≤ 0.01`, lệch → log + ném lỗi.
7. Lấy `mode_of_payment` từ `invoice.payments` (dòng khớp số tiền, không có thì dòng đầu
   tiên có mode). Xóa hết `payments`, append 1 dòng `{mode_of_payment, amount}`.
8. Set `transaction_ref = id/referenceCode` (`payment_status = "Đã thanh toán"` do hook `before_submit` ghi khi submit,
   2026-11-25 — `pos_invoice_hooks.md` §2.0),
   append log vào `sepay_payment_log` (JSON, giữ 50 entry cuối).
9. `save()` → `submit()` **trong `_as_system_user()`** (Administrator, try/finally trả lại user cũ = Guest).
   Lý do: webhook chạy bằng Guest, `set_missing_values` → `get_party_account` → `account_perm_check`
   không bị `ignore_permissions` bỏ qua (lỗi thật 2026-11-14). Chỉ bước này chạy quyền cao, SAU xác thực
   key + khớp đơn + khớp số tiền; hook `on_submit` (kitchen status, buzzer, Loyalty Point Entry, đổi điểm)
   nằm trong cùng phạm vi. Không cấp quyền Account cho Guest/role nào.
   → ERPNext tự set `status = "Paid"`, `docstatus = 1`
   (kéo theo `on_submit` hook: kitchen status `Chưa làm`, buzzer `Đang dùng`).
10. Trả `{success, message, invoice_name, payment_code, transaction_id, amount,
    mode_of_payment, invoice_status, docstatus, payment_status}`.

**Webhook KHÔNG tạo Payment Entry**: đặt lại `payments` của invoice (1 dòng, đúng số tiền)
rồi `save()` và `submit()` — dùng luồng `POS Invoice.payments` gốc của ERPNext.
Lỗi bất kỳ được bọc lại thành `"Lỗi xử lý webhook SePay: ..."` + `log_error`.

## 4. Kết quả test (Postman + ngrok, đã Pass)

- Invoice chuyển `status="Paid"`, `docstatus=1`, `payment_status="Đã thanh toán"`.
- `mode_of_payment` lấy đúng từ POS Invoice (không hardcode).
- Gọi lại webhook cùng `payment_code` → `{success: true, already_processed: true}`
  (không lỗi 417, không submit lại).

## 5. Điểm code chưa khớp tài liệu / chờ quyết định (chưa sửa code)

- ~~Webhook chưa xác thực API key~~ — đã sửa 2026-11-14 (§1), đã test Pass.
- ~~`payment_status` lệch giá trị (`generate_qr` ghi "Chưa thanh toán", Orders / Desk kiểm "Đang chờ")~~ — đã sửa 2026-11-25:
  `generate_qr` ghi "Đang chờ" → thẻ "Chờ QR" ở Orders + bước xác nhận khi hủy đơn đang chờ chuyển khoản (/pos, Desk) bắt đầu chạy.
- `update_sepay_payment_log()` còn trong file nhưng webhook không gọi (webhook tự ghi log).

## 6. Fixtures

- Custom Field `POS Invoice.payment_code`, `payment_status`, `transaction_ref`,
  `sepay_payment_log` nằm trong `fixtures/custom_field.json` (filter `dt = POS Invoice` trong `hooks.py`).
