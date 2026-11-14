import frappe
from frappe import _
import secrets
from datetime import datetime
import json as _json
from contextlib import contextmanager
from frappe.utils import flt

# Import helper functions from branch_config module
from ..branch_config.branch_config import (
    get_va_bank_config,
    get_sepay_qr_url,
)

@frappe.whitelist()
def generate_qr_for_invoice(invoice_name):
    """Generate VietQR dynamic code for a POS Invoice.

    This method creates a unique payment_code and VietQR URL for the invoice.
    The invoice status remains Draft until payment is confirmed via webhook.

    Args:
        invoice_name (str): Name of the POS Invoice document.

    Returns:
        dict: Dictionary containing invoice details and payment info:
            - invoice_name: The invoice document name
            - payment_code: Unique payment reference code
            - qr_url: VietQR image URL for display
            - amount: Invoice grand total amount
            - payment_status: Current payment status ("Chưa thanh toán")

    Logic:
        1. Validates invoice exists and doesn't already have a payment_code
        2. Retrieves VA account and bank code from Branch (fallback to Settings)
        3. Generates unique payment_code using invoice name + timestamp + hash
        4. Builds VietQR URL using the VietQR API format
        5. Saves payment_code and status to the invoice
        6. Returns all information for frontend display
    """
    try:
        invoice = frappe.get_doc("POS Invoice", invoice_name)

        # Check if invoice already has a payment_code (idempotent)
        if invoice.payment_code:
            return {
                "invoice_name": invoice_name,
                "payment_code": invoice.payment_code,
                "qr_url": _get_existing_qr_url(invoice.payment_code, invoice),
                "amount": invoice.grand_total,
                "payment_status": invoice.payment_status or "Chưa thanh toán",
                "idempotent": True,
            }

        # Get VA and bank config for this invoice's branch
        va_config = get_va_bank_config(invoice_name)
        va_account = va_config.get("va_account", "")
        bank_code = va_config.get("bank_code", "")

        # Generate unique payment code
        # Format: POS-{invoice_name}-{YYYYMMDD}-{hash}
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_hash = secrets.token_hex(3).upper()
        payment_code = f"POS-{invoice_name}-{timestamp}-{unique_hash}"

        # Build VietQR URL
        qr_url = get_sepay_qr_url(va_account, bank_code, invoice.grand_total, payment_code)

        # Update invoice with payment info (status still Draft)
        invoice.payment_code = payment_code
        invoice.payment_status = "Chưa thanh toán"
        # transaction_ref cleared for new payment
        if invoice.transaction_ref:
            invoice.transaction_ref = ""
        # Clear payment log for new payment
        invoice.sepay_payment_log = ""

        # Invoice đã tồn tại → chỉ save, không insert lại
        invoice.save(ignore_permissions=True)

        return {
            "invoice_name": invoice_name,
            "payment_code": payment_code,
            "qr_url": qr_url,
            "amount": invoice.grand_total,
            "payment_status": "Chưa thanh toán",
            "idempotent": False,
        }

    except Exception as e:
        frappe.log_error(
            title="SePay Generate QR Error",
            message=f"{str(e)}\n{frappe.get_traceback()}",
        )
        frappe.throw(_("Lỗi khi tạo mã QR thanh toán: {0}").format(str(e)))


def _get_existing_qr_url(payment_code, invoice):
    """Get existing QR URL for an invoice that already has a payment_code.

    Args:
        payment_code (str): Payment code of the invoice
        invoice (doc): POS Invoice document

    Returns:
        str: VietQR URL
    """
    # Get VA and bank config for this invoice's branch
    va_config = get_va_bank_config(invoice.name)
    va_account = va_config.get("va_account", "")
    bank_code = va_config.get("bank_code", "")

    return get_sepay_qr_url(va_account, bank_code, invoice.grand_total, payment_code)


@frappe.whitelist(allow_guest=True)
def sepay_webhook():
    """Receive SePay webhook and update POS Invoice payment."""

    try:
        # 1. Đọc JSON theo format SePay
        payload = frappe.request.get_json(silent=True) or {}

        if not payload:
            frappe.throw(_("Không có dữ liệu JSON từ SePay"))

        content = str(
            payload.get("content") or payload.get("code") or ""
        ).strip()

        amount = flt(payload.get("transferAmount") or 0)

        transaction_id = str(
            payload.get("id") or payload.get("referenceCode") or ""
        ).strip()

        transfer_type = str(
            payload.get("transferType") or ""
        ).strip().lower()

        if not content:
            frappe.throw(_("SePay không gửi mã nội dung chuyển khoản"))

        if amount <= 0:
            frappe.throw(_("Số tiền chuyển khoản không hợp lệ"))

        # Chỉ nhận giao dịch chuyển tiền vào
        if transfer_type and transfer_type != "in":
            return {
                "success": False,
                "message": "Không phải giao dịch chuyển tiền vào",
            }

        # 2. Chuẩn hóa mã để bỏ qua dấu gạch ngang, khoảng trắng
        def normalize_code(value):
            return "".join(
                char
                for char in str(value or "").upper()
                if char.isalnum()
            )

        normalized_content = normalize_code(content)

        # 3. Tìm POS Invoice theo payment_code (Draft HOẶC đã submit, để retry của SePay
        #    nhận được phản hồi idempotent). Không quét toàn bảng: xem _find_invoice_by_code.
        matched_invoice = _find_invoice_by_code(content, normalized_content)

        if not matched_invoice:
            frappe.log_error(
                title="SePay POS Invoice Not Found",
                message=(
                    f"content={content}\n"
                    f"normalized_content={normalized_content}"
                ),
            )
            frappe.throw(
                _("Không tìm thấy POS Invoice có payment_code khớp với nội dung SePay")
            )

        invoice = frappe.get_doc(
            "POS Invoice", matched_invoice.name
        )

        # 3b. Xác thực webhook đến từ SePay (API key của Branch của đơn).
        #     Mọi nhánh bên dưới (kể cả phản hồi idempotent) chỉ chạy SAU bước này.
        _verify_sepay_key(invoice)

        # 3b'. Đơn đã submit: không bao giờ xác nhận lại.
        if invoice.docstatus == 1:
            if (invoice.transaction_ref or "") == transaction_id:
                # SePay retry đúng giao dịch đã xử lý -> thành công idempotent.
                return {
                    "success": True,
                    "message": "Giao dịch đã được xử lý trước đó",
                    "invoice_name": invoice.name,
                    "already_processed": True,
                }
            # Giao dịch THỨ HAI cho cùng mã (khách chuyển 2 lần...): ghi log để đối soát/hoàn
            # tiền thủ công. Trả success để SePay không retry mãi; không trả dữ liệu đơn/khách.
            frappe.log_error(
                title="SePay: giao dịch thứ hai cho mã đã thanh toán",
                message=(
                    f"invoice={invoice.name}\n"
                    f"transaction_ref_da_luu={invoice.transaction_ref}\n"
                    f"transaction_id_moi={transaction_id}\n"
                    f"amount={amount}\ncontent={content}\n"
                    f"gateway={payload.get('gateway')}\n"
                    f"transactionDate={payload.get('transactionDate')}"
                ),
            )
            return {
                "success": True,
                "already_processed": True,
                "needs_review": True,
                "message": "Mã thanh toán đã được sử dụng; giao dịch được ghi nhận để đối soát.",
            }

        # 3c. Cùng mã giao dịch SePay đã submit một đơn khác -> không xử lý lại.
        if transaction_id and frappe.db.exists(
            "POS Invoice",
            {"transaction_ref": transaction_id, "docstatus": 1, "name": ["!=", invoice.name]},
        ):
            return {
                "success": True,
                "message": "Giao dịch đã được xử lý trước đó",
                "invoice_name": invoice.name,
                "already_processed": True,
            }

        # 4. Chống xử lý lại giao dịch
        if invoice.payment_status == "Đã thanh toán":
            return {
                "success": True,
                "message": "Giao dịch đã được xử lý trước đó",
                "invoice_name": invoice.name,
                "already_processed": True,
            }

        if invoice.payment_status == "Hủy":
            frappe.throw(_("Giao dịch thuộc POS Invoice đã bị hủy"))

        if invoice.docstatus != 0:
            frappe.throw(_("POS Invoice không còn ở trạng thái Draft"))

        # 5. Kiểm tra số tiền
        expected_amount = flt(
            invoice.rounded_total or invoice.grand_total
        )

        if abs(amount - expected_amount) > 0.01:
            frappe.log_error(
                title="SePay POS Amount Mismatch",
                message=(
                    f"Invoice={invoice.name}\n"
                    f"Expected={expected_amount}\n"
                    f"Received={amount}"
                ),
            )
            frappe.throw(
                _("Số tiền không khớp. Cần {0}, nhận được {1}").format(
                    expected_amount, amount
                )
            )

        # 6. Lấy Mode of Payment từ POS Invoice hiện tại
        payments = invoice.get("payments") or []

        if not payments:
            frappe.throw(
                _("POS Invoice chưa có phương thức thanh toán")
            )

        matched_payment = next(
            (
                payment for payment in payments
                if payment.mode_of_payment
                and abs(flt(payment.amount) - expected_amount) <= 0.01
            ),
            None,
        )

        # Nếu không có dòng khớp số tiền, lấy dòng đầu tiên có phương thức
        if not matched_payment:
            matched_payment = next(
                (
                    payment for payment in payments
                    if payment.mode_of_payment
                ),
                None,
            )

        if not matched_payment:
            frappe.throw(
                _("Không xác định được Mode of Payment từ POS Invoice")
            )

        mode_of_payment = matched_payment.mode_of_payment

        # Thay payment rows hiện tại bằng dòng thanh toán đã xác định
        invoice.set("payments", [])
        invoice.append("payments", {
            "mode_of_payment": mode_of_payment,
            "amount": expected_amount,
        })

        # 7. Cập nhật thông tin giao dịch SePay
        invoice.payment_status = "Đã thanh toán"
        invoice.transaction_ref = transaction_id

        log_entry = {
            "content": content,
            "transaction_id": transaction_id,
            "referenceCode": payload.get("referenceCode"),
            "transferAmount": amount,
            "gateway": payload.get("gateway"),
            "transactionDate": payload.get("transactionDate"),
            "received_at": frappe.utils.now_datetime().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

        existing_log = []

        if invoice.sepay_payment_log:
            try:
                existing_log = _json.loads(
                    invoice.sepay_payment_log
                )
                if not isinstance(existing_log, list):
                    existing_log = [existing_log]
            except (ValueError, TypeError):
                existing_log = []

        existing_log.append(log_entry)

        invoice.sepay_payment_log = _json.dumps(
            existing_log[-50:],
            ensure_ascii=False,
        )

        # 8. Lưu và submit POS Invoice.
        # Webhook là allow_guest (user Guest). save/submit của ERPNext gọi
        # get_party_account -> account_perm_check, không bị ignore_permissions bỏ qua.
        # Vì vậy CHỈ bước này (đã qua xác thực API key, khớp đơn, khớp số tiền) chạy dưới
        # user hệ thống; hook on_submit (kitchen status, buzzer, Loyalty Point Entry,
        # đổi điểm) chạy trong cùng phạm vi. Không cấp quyền Account cho Guest/role nào.
        with _as_system_user():
            invoice.save(ignore_permissions=True)
            invoice.submit()
        invoice.reload()

        return {
            "success": True,
            "message": "Xác nhận thanh toán SePay thành công",
            "invoice_name": invoice.name,
            "payment_code": invoice.payment_code,
            "transaction_id": transaction_id,
            "amount": amount,
            "mode_of_payment": mode_of_payment,
            "invoice_status": invoice.status,
            "docstatus": invoice.docstatus,
            "payment_status": invoice.payment_status,
        }

    except frappe.PermissionError:
        # Sai/thiếu API key: trả 403 nguyên trạng, không bọc thành lỗi chung.
        raise

    except Exception as e:
        frappe.log_error(
            title="SePay POS Webhook Error",
            message=f"{str(e)}\n{frappe.get_traceback()}",
        )
        frappe.throw(
            _("Lỗi xử lý webhook SePay: {0}").format(str(e))
        )


# Ký tự bỏ đi khi chuẩn hóa payment_code ở SQL (mã sinh ra chỉ gồm chữ, số, "-").
_CODE_STRIP_CHARS = ("-", " ", ".", "/", "_")
# Giới hạn quét của đường dự phòng (nội dung chuyển khoản bị ngân hàng bỏ dấu "-").
_FALLBACK_LOOKUP_DAYS = 30
_LOOKUP_FIELDS = ["name", "docstatus", "creation"]


def _find_invoice_by_code(content, normalized_content):
    """POS Invoice (docstatus 0 hoặc 1) có payment_code khớp nội dung chuyển khoản.

    1. Khớp chính xác `payment_code = content` -> dùng index của cột payment_code.
    2. Dự phòng (ngân hàng bỏ "-", đổi hoa/thường): so mã đã chuẩn hóa bằng SQL, chỉ
       trong các đơn tạo trong _FALLBACK_LOOKUP_DAYS ngày gần nhất, LIMIT 2.
    Có >= 2 đơn khớp ở bước 2 -> log, không đoán (trả None).
    """
    if not normalized_content:
        return None

    exact = frappe.get_all(
        "POS Invoice",
        filters={"payment_code": content.strip(), "docstatus": ["in", [0, 1]]},
        fields=_LOOKUP_FIELDS,
        order_by="creation desc",
        limit=1,
    )
    if exact:
        return exact[0]

    expr = "UPPER(`payment_code`)"
    for ch in _CODE_STRIP_CHARS:
        expr = f"REPLACE({expr}, '{ch}', '')"
    since = frappe.utils.add_days(frappe.utils.now_datetime(), -_FALLBACK_LOOKUP_DAYS)
    rows = frappe.db.sql(
        f"""
        SELECT `name`, `docstatus`, `creation`
        FROM `tabPOS Invoice`
        WHERE `docstatus` IN (0, 1)
          AND `creation` >= %(since)s
          AND IFNULL(`payment_code`, '') != ''
          AND {expr} = %(code)s
        ORDER BY `creation` DESC
        LIMIT 2
        """,
        {"since": since, "code": normalized_content},
        as_dict=True,
    )
    if len(rows) > 1:
        frappe.log_error(
            title="SePay: nhiều POS Invoice khớp cùng mã",
            message=f"normalized_content={normalized_content}\ninvoices={[r.name for r in rows]}",
        )
        return None
    return rows[0] if rows else None


@contextmanager
def _as_system_user():
    """Tạm chạy dưới Administrator trong phạm vi hẹp, luôn trả lại user cũ (Guest với webhook).

    Chỉ dùng SAU khi webhook đã được xác thực (_verify_sepay_key) và đã khớp đơn + số tiền.
    """
    prev = frappe.session.user
    frappe.set_user("Administrator")
    try:
        yield
    finally:
        frappe.set_user(prev)


def _received_sepay_key():
    """API key SePay gửi kèm webhook.

    Nhận 1 trong 2 cách (cấu hình bên SePay):
    - Header `Authorization: Apikey <key>` (kiểu chứng thực "API Key" của SePay).
    - Tham số `?key=<key>` trên URL webhook (dùng khi Frappe chặn header Authorization
      có scheme lạ trước khi vào hàm — xem rules/leescoffee_pos/sepay.md).
    """
    header = str(frappe.get_request_header("Authorization") or "").strip()
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "apikey":
        return parts[1].strip()

    args = getattr(frappe.request, "args", None) or {}
    return str(args.get("key") or "").strip()


def verify_sepay_key_for_branch(branch_name, received):
    """True nếu `received` khớp Branch.sepay_api_key (so sánh thời gian hằng)."""
    import hmac

    from frappe.utils.password import get_decrypted_password

    if not branch_name or not received:
        return False
    expected = get_decrypted_password(
        "Branch", branch_name, "sepay_api_key", raise_exception=False
    ) or ""
    if not expected:
        return False
    return hmac.compare_digest(received.encode(), str(expected).encode())


def _verify_sepay_key(invoice):
    """Chặn webhook giả: key gửi kèm phải khớp sepay_api_key của Branch của đơn."""
    branch_name = (
        frappe.db.get_value("POS Profile", invoice.pos_profile, "branch")
        if invoice.pos_profile
        else None
    )
    if not verify_sepay_key_for_branch(branch_name, _received_sepay_key()):
        frappe.log_error(
            title="SePay webhook: sai hoặc thiếu API key",
            message=f"invoice={invoice.name}\nbranch={branch_name}\nip={getattr(frappe.local, 'request_ip', None)}",
        )
        raise frappe.PermissionError(_("Webhook SePay không hợp lệ."))


def update_sepay_payment_log(invoice_name, log_entry):
    """Append a new log entry to the invoice's sepay_payment_log field.

    Args:
        invoice_name (str): Name of the POS Invoice.
        log_entry (str): JSON string to append.
    """
    invoice = frappe.get_doc("POS Invoice", invoice_name)

    # Get existing log
    existing_log = invoice.sepay_payment_log or "[]"

    try:
        log_list = _json.loads(existing_log)
    except _json.JSONDecodeError:
        log_list = []

    # Append new entry
    try:
        log_entry_dict = _json.loads(log_entry)
        log_list.append(log_entry_dict)
    except _json.JSONDecodeError:
        log_list.append({"log_entry": log_entry})

    # Keep only last 50 entries to avoid field size issues
    if len(log_list) > 50:
        log_list = log_list[-50:]

    # Save back
    invoice.sepay_payment_log = _json.dumps(log_list, ensure_ascii=False, indent=2)
    invoice.save(ignore_permissions=True)


