import frappe
from frappe import _
import secrets
from datetime import datetime
import json as _json
from frappe.utils import flt

# Import helper functions from branch_config module
from ..branch_config.branch_config import (
    get_default_branch,
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

        # 3. Tìm POS Invoice Draft theo payment_code
        invoices = frappe.get_all(
            "POS Invoice",
            filters={
                "payment_code": ["is", "set"],
                "docstatus": 0,
            },
            fields=[
                "name",
                "payment_code",
                "grand_total",
                "rounded_total",
                "status",
                "docstatus",
                "payment_status",
            ],
            order_by="creation desc",
        )

        matched_invoice = None

        for row in invoices:
            if normalize_code(row.payment_code) == normalized_content:
                matched_invoice = row
                break

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

        # 8. Lưu và submit POS Invoice
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

    except Exception as e:
        frappe.log_error(
            title="SePay POS Webhook Error",
            message=f"{str(e)}\n{frappe.get_traceback()}",
        )
        frappe.throw(
            _("Lỗi xử lý webhook SePay: {0}").format(str(e))
        )


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


