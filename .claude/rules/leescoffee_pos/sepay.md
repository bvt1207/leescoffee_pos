# Module Rules: SePay Integration — Leescoffee POS

> Paths: `leescoffee_pos/leescoffee_pos/doctype/sepay/`

## 1. Quản lý cấu hình SePay

- **Chỉ ở `Branch`**: `sepay_enabled`, `sepay_api_key`, `sepay_va_account`, `sepay_bank_code`.
- **Không fallback Settings** cho SePay config.
- **Không dùng** `merchant_code`, `secret_key`, `env`, `callback_url` trong config mới (đã được loại bỏ).

### `get_sepay_config(branch_name=None)`
Trả về dict:
```python
{
    "enabled": int,
    "api_key": str,
    "va_account": str,
    "bank_code": str,
}
```

## 2. generate_qr_for_invoice()

`leescoffee_pos/leescoffee_pos/doctype/sepay/sepay.py::generate_qr_for_invoice()`

- Đầu vào: `invoice_name` (string)
- Output: `invoice_name`, `payment_code`, `qr_url`, `amount`, `payment_status`
- Xử lý:
  1. Kiểm tra invoice tồn tại + chưa có `payment_code`
  2. Lấy `sepay_va_account` + `sepay_bank_code` từ Branch (via `get_va_bank_config()`)
  3. Tạo `payment_code` duy nhất
  4. Build VietQR URL
  5. Lưu `payment_code` + `payment_status = "Đang chờ"` vào POS Invoice (status vẫn Draft)
  6. Idempotent: nếu đã có `payment_code` → trả về code cũ

## 3. Webhook: `sepay_webhook()`

`leescoffee_pos/leescoffee_pos/doctype/sepay/sepay.py::sepay_webhook()`

- `@frappe.whitelist(allow_guest=True)`, nhận POST JSON
- Payload: `payment_code`, `amount`, `status`, `transaction_id`, `api_key`
- Verify API Key: `branch.sepay_api_key`
- Idempotent: quét `sepay_payment_log` tránh xử lý trùng
- Kiểm tra amount: `fabs(amount - invoice.grand_total) < 0.01`
- Tạo Payment Entry (payment_type=Receive) → submit → ERPNext tự set POS Invoice.status = "Paid"

## 4. Fixtures

- Custom Field `POS Invoice.payment_code`, `payment_status`, `transaction_ref`, `sepay_payment_log` trong `fixtures` của `hooks.py`.
