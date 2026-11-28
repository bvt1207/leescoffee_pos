# Module Rules: SePay Integration — MYPOS

> Paths: `mypos/mypos/doctype/sepay/sepay.py`,
> helper ở `mypos/mypos/doctype/branch_config/branch_config.py`.
> Đã đối chiếu với code ngày 2026-10-27; §1 xác thực webhook đổi sang HMAC-SHA256 ngày 2026-11-28.

## 1. Quản lý cấu hình SePay

- **Chỉ ở `Branch`** (Custom Field, fixtures): `sepay_enabled` (Check), `sepay_webhook_secret` (Password),
  `sepay_va_account` (Data), `sepay_bank_code` (Data).
- **Mỗi chi nhánh/doanh nghiệp một bộ riêng**: một secret webhook, một VA, một mã ngân hàng (nhiều chi nhánh dùng chung một webhook
  SePay → điền cùng một secret ở mọi Branch đó).
  Chi nhánh lấy từ `POS Invoice.pos_profile` → `POS Profile.branch`.

### Xác thực webhook: HMAC-SHA256 (từ 0.2.0, 2026-11-28)

- `sepay_webhook` là `allow_guest=True` (SePay gọi không có phiên ERPNext) → phải tự xác thực request đến từ SePay.
- **Chỉ dùng kiểu "HMAC-SHA256" trên SePay.** Các kiểu gửi header `Authorization` (API Key, OAuth 2.0) bị Frappe trả 401 trước khi vào
  hàm (`auth.py::validate_auth` 16.61, dòng 645–657: chỉ nhận Bearer của OAuth Frappe / Basic / token của User). mypos không dùng
  `auth_hooks` / `before_request`, không đổi user khi xác thực.
- **Kiểu SePay "HMAC-SHA256"**: SePay gửi `X-SePay-Timestamp` (unix giây) + `X-SePay-Signature: sha256=<hex>`, chữ ký =
  HMAC-SHA256(secret, `"{timestamp}." + raw_body`). Không có header `Authorization` → Frappe để request đi tiếp dưới Guest.
- Code (`sepay.py`):
  1. `_check_signature_headers()` — ĐẦU webhook, TRƯỚC khi đọc DB: thiếu header / timestamp không phải số / lệch giờ server >
     `SIGNATURE_TOLERANCE_SECONDS = 300` / chữ ký đã xử lý thành công (chống phát lại) → 403.
  2. Tìm đơn theo `payment_code` (như cũ) → `_verify_sepay_signature(invoice, signed)`: secret = `Branch.sepay_webhook_secret` của
     Branch của POS Profile của đơn; tính lại trên **raw body** `frappe.request.get_data()` (werkzeug cache body, vẫn đúng bytes sau khi
     Frappe `make_form_dict` đã đọc — selfcheck H6); so `hmac.compare_digest`. Hợp lệ → `_remember_signature`.
  3. Chống phát lại: khóa Redis `mypos_sepay_sig:<sha256(chữ ký)>` TTL 600 giây, đặt **sau commit** (`frappe.db.after_commit`;
     rollback xóa hàng đợi → request lỗi gửi lại được). Gửi lại đúng request đã thành công → 403 "phát lại". Lớp 2 vẫn là
     chống trùng theo `transaction_ref` (request ký mới cùng giao dịch → `already_processed`).
     [Unverified] SePay khi retry ký lại hay dùng lại chữ ký cũ: nếu dùng lại sau một lần đã thành công (mất phản hồi) → nhận 403;
     đơn vẫn đúng (quyết định Van 2026-11-28).
- 403 (`PermissionError` không bị bọc) + Error Log đúng lý do: "SePay webhook: thiếu chữ ký HMAC" / "… timestamp không hợp lệ" /
  "… timestamp quá hạn" / "… chữ ký đã dùng (phát lại)" / "… đơn không có POS Profile" / "… POS Profile thiếu Branch" /
  "… Branch chưa cấu hình secret webhook" / "… chữ ký sai". Thông báo trả bên gọi luôn chung "Webhook SePay không hợp lệ.".
- Đồng hồ server phải đúng (NTP): lệch > 5 phút → mọi webhook bị từ chối. SePay phải gửi **JSON** (mypos chỉ đọc JSON).
- Kiểm: `selfcheck/sepay_hmac_check.py` (H1–H8); request giả ký sẵn: `selfcheck/sepay_sign.py`; lệnh curl: `docs/checklist.md` §C.

### Cấu hình bên SePay

1. my.sepay.vn → Webhooks → thêm / sửa webhook: URL `https://<domain>/api/method/mypos.mypos.doctype.sepay.sepay.sepay_webhook`,
   kiểu gửi JSON, tài khoản nhận tiền = VA của chi nhánh.
2. Bước **Bảo mật** → chọn **HMAC-SHA256** → nhập hoặc bấm tạo Secret Key → **copy ngay** (mở lại chỉ thấy 4 ký tự cuối).
3. ERPNext → Branch của chi nhánh → "Secret webhook SePay (HMAC)" → dán secret → Save. Nhiều chi nhánh dùng chung webhook → dán cùng
   secret vào từng Branch.
4. Thử bằng `curl` ký sẵn (`docs/checklist.md` §C) hoặc nút gửi thử của SePay; xem Error Log nếu 403.
- **Chỉ đọc Branch** cho SePay config (branding cũng chỉ đọc Branch — xem `branch.md`).
- **Không dùng** `merchant_code`, `secret_key`, `env`, `callback_url` (đã loại bỏ).

Helper trong `branch_config.py`:

- `get_sepay_config(branch_name=None)` → `{enabled, va_account, bank_code}` (không trả secret webhook).
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

- 2026-11-28: trước khi lưu, dòng thanh toán của đơn = mode **Bank** của POS Profile của đơn (`_set_bank_mode`, `pos_profile.md` §1b);
  profile thiếu mode Bank -> lỗi rõ. Nhánh idempotent (đã có `payment_code`) không đổi.

## 3. Webhook `sepay_webhook()` (`allow_guest=True`)

Payload theo format SePay: `content`/`code`, `transferAmount`, `id`/`referenceCode`,
`transferType`, `gateway`, `transactionDate`.

1. Thiếu JSON / thiếu `content` / `transferAmount <= 0` → ném lỗi.
2. `transferType` có giá trị khác `"in"` → trả `{success: False}` (bỏ qua giao dịch tiền ra).
3. Tìm đơn `docstatus` 0, 1 **hoặc 2** (`_find_invoice_by_code`, thêm 2 từ 2026-11-23): (a) `payment_code = content` khớp chính xác
   (cột có `search_index`, fixture 2026-11-14); (b) dự phòng: so mã chuẩn hóa bằng SQL (bỏ `- . / _` và
   khoảng trắng, viết hoa) chỉ trong đơn tạo 30 ngày gần nhất, `LIMIT 2`; khớp ≥ 2 đơn → log, coi như không thấy.
0. (2026-11-28) Kiểm 2 header HMAC + hạn timestamp + chống phát lại (`_check_signature_headers`) TRƯỚC mọi bước dưới (§1).
4. Không khớp → `log_error` + ném lỗi. Khớp → **xác thực chữ ký HMAC** (`_verify_sepay_signature`) TRƯỚC mọi nhánh sau.
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
7. Mode of Payment = mode **Bank** của POS Profile của đơn (`_set_bank_mode`, 2026-11-28; trước đây lấy từ `invoice.payments`).
   Đặt 1 dòng thanh toán với đúng số tiền. Profile thiếu mode Bank -> lỗi + Error Log (tiền đã về: đối soát tay).
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
