# Module Rules: SePay Integration — Leescoffee POS

> Paths: `leescoffee_pos/leescoffee_pos/doctype/sepay/sepay.py`,
> helper ở `leescoffee_pos/leescoffee_pos/doctype/branch_config/branch_config.py`.
> Đã đối chiếu với code ngày 2026-10-27.

## 1. Quản lý cấu hình SePay

- **Chỉ ở `Branch`**: `sepay_enabled`, `sepay_api_key`, `sepay_va_account`, `sepay_bank_code`.
- **Không fallback Settings** cho SePay config (branding thì vẫn fallback — xem `memory/memory_note_branding_fallback.md`).
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
5. Lưu vào invoice: `payment_code`, `payment_status = "Chưa thanh toán"`, xóa `transaction_ref`
   và `sepay_payment_log`; chỉ `save()` — invoice **vẫn Draft**.
6. Trả `{invoice_name, payment_code, qr_url, amount, payment_status, idempotent}`.

## 3. Webhook `sepay_webhook()` (`allow_guest=True`)

Payload theo format SePay: `content`/`code`, `transferAmount`, `id`/`referenceCode`,
`transferType`, `gateway`, `transactionDate`.

1. Thiếu JSON / thiếu `content` / `transferAmount <= 0` → ném lỗi.
2. `transferType` có giá trị khác `"in"` → trả `{success: False}` (bỏ qua giao dịch tiền ra).
3. Chuẩn hóa mã (chỉ giữ chữ + số, viết hoa) rồi so `payment_code` của các POS Invoice
   **Draft** (`docstatus = 0`, có `payment_code`) với `content`.
4. Không khớp → `log_error` + ném lỗi.
5. **Idempotent**: `payment_status == "Đã thanh toán"` → trả
   `{success: True, already_processed: True}`. `payment_status == "Hủy"` → ném lỗi.
6. Kiểm tra số tiền: `|transferAmount − (rounded_total or grand_total)| ≤ 0.01`, lệch → log + ném lỗi.
7. Lấy `mode_of_payment` từ `invoice.payments` (dòng khớp số tiền, không có thì dòng đầu
   tiên có mode). Xóa hết `payments`, append 1 dòng `{mode_of_payment, amount}`.
8. Set `payment_status = "Đã thanh toán"`, `transaction_ref = id/referenceCode`,
   append log vào `sepay_payment_log` (JSON, giữ 50 entry cuối).
9. `save()` → `submit()` → ERPNext tự set `status = "Paid"`, `docstatus = 1`
   (kéo theo `on_submit` hook: kitchen status `Chưa làm`, buzzer `Đang dùng`).
10. Trả `{success, message, invoice_name, payment_code, transaction_id, amount,
    mode_of_payment, invoice_status, docstatus, payment_status}`.

**Không tạo Payment Entry** — dùng luồng `POS Invoice.payments` gốc của ERPNext.
Lỗi bất kỳ được bọc lại thành `"Lỗi xử lý webhook SePay: ..."` + `log_error`.

## 4. Kết quả test (Postman + ngrok, đã Pass)

- Invoice chuyển `status="Paid"`, `docstatus=1`, `payment_status="Đã thanh toán"`.
- `mode_of_payment` lấy đúng từ POS Invoice (không hardcode).
- Gọi lại webhook cùng `payment_code` → `{success: true, already_processed: true}`
  (không lỗi 417, không submit lại).

## 5. Điểm code chưa khớp tài liệu / chờ quyết định (chưa sửa code)

- **Webhook chưa xác thực API key**: `sepay_api_key` có trong Branch config nhưng
  `sepay_webhook()` không kiểm tra header/khóa nào. Endpoint là `allow_guest`.
- **`payment_status` lệch giá trị**: `generate_qr_for_invoice` ghi `"Chưa thanh toán"`,
  trong khi `pos_api.cancel_draft_order` và `Orders.tsx` (tag "Chờ QR", chặn hủy khi
  chưa `force`) kiểm tra `"Đang chờ"`. Options của Custom Field có cả hai giá trị.
- `update_sepay_payment_log()` còn trong file nhưng webhook không gọi (webhook tự ghi log).

## 6. Fixtures

- Custom Field `POS Invoice.payment_code`, `payment_status`, `transaction_ref`,
  `sepay_payment_log` nằm trong `fixtures/custom_field.json` (filter `dt = POS Invoice` trong `hooks.py`).
