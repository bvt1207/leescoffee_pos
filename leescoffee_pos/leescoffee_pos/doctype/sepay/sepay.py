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
    """Receive SePay webhook callback for payment verification.

    This endpoint is called by SePay after a customer completes a bank transfer.
    It verifies the API key, matches payment_code and amount, and creates a
    Payment Entry in ERPNext to mark the POS Invoice as "Paid".

    Expected POST JSON payload:
    {
        "payment_code": "POS-INV-00001-20241201-abc123",
        "amount": 50000,
        "status": "success",
        "transaction_id": "SEPAY-TX-20241201-xyz789",
        "api_key": "..."
    }

    Returns:
        dict: Response with success status and message.
    """
    try:
        # Parse JSON payload from request
        if not frappe.request.data:
            frappe.throw(_("Không có dữ liệu POST"))

        # Try to parse JSON - handle both bytes and string
        try:
            payload_str = frappe.request.data.decode('utf-8') if isinstance(frappe.request.data, bytes) else frappe.request.data
            payload = _json.loads(payload_str)
        except:
            # If parsing fails, try frappe.request.get_json()
            payload = frappe.request.get_json()
            if not payload:
                frappe.throw(_("Không thể parse JSON từ request"))

        payment_code = payload.get("payment_code", "")
        amount = payload.get("amount", 0)
        sepay_status = payload.get("status", "")
        transaction_id = payload.get("transaction_id", "")
        api_key_from_payload = payload.get("api_key", "")

        # Also check header for API key
        api_key_from_header = None
        if frappe.request.headers.get("X-Api-Key"):
            api_key_from_header = frappe.request.headers.get("X-Api-Key")

        # Determine which API key to use for verification
        # Priority: payload api_key > header api_key > Branch config > Settings
        verified_api_key = None

        # 1. If api_key in payload, use it
        if api_key_from_payload:
            verified_api_key = api_key_from_payload
        # 2. Check header api_key
        elif api_key_from_header:
            verified_api_key = api_key_from_header
        else:
            # 3. Check Branch config (default branch)
            branch_name = get_default_branch()
            if branch_name:
                branch = frappe.get_doc("Branch", branch_name)
                if branch.sepay_api_key:
                    verified_api_key = branch.sepay_api_key
            if not verified_api_key:
                # 4. Fallback to Settings
                settings = frappe.get_single("Leescoffee POS Settings")
                if settings.sepay_api_key:
                    verified_api_key = settings.sepay_api_key

        # Verify API Key
        if not verified_api_key:
            frappe.log_error(
                title="SePay Webhook Missing API Key",
                message="No API key found in payload or headers",
            )
            frappe.throw(_("API Key không được cung cấp"))

        # Check if API key matches Branch config (primary source)
        branch_name = get_default_branch()
        expected_api_key = None

        if branch_name:
            branch = frappe.get_doc("Branch", branch_name)
            expected_api_key = branch.sepay_api_key if branch.sepay_api_key else None
        else:
            expected_api_key = None

        if not expected_api_key:
            settings = frappe.get_single("Leescoffee POS Settings")
            expected_api_key = settings.sepay_api_key or ""

        if verified_api_key != expected_api_key:
            frappe.log_error(
                title="SePay Webhook API Key Mismatch",
                message=f"Expected: {expected_api_key}, Got: {verified_api_key}",
            )
            frappe.throw(_("API Key không hợp lệ. Vui lòng kiểm tra cấu hình Branch/Settings."))

        # Find POS Invoice by payment_code
        invoice_name = frappe.db.get_value(
            "POS Invoice",
            {"payment_code": payment_code},
            "name",
        )
        if not invoice_name:
            frappe.log_error(
                title="SePay Webhook Invoice Not Found",
                message=f"Payment code '{payment_code}' not found in any POS Invoice",
            )
            frappe.throw(_("Mã thanh toán không khớp với bất kỳ đơn nào. Vui lòng kiểm tra lại."))

        invoice = frappe.get_doc("POS Invoice", invoice_name)

        # Idempotency check: if already processed
        if invoice.payment_status in ("Đã thanh toán", "Hủy"):
            return {
                "success": True,
                "message": "Đã xử lý trước đó",
                "invoice_name": invoice.name,
                "already_processed": True,
            }

        # Amount verification
        # Use tolerance for floating point comparison
        amount_tolerance = 0.01
        try:
            amount_float = float(amount)
            grand_total_float = float(invoice.grand_total)
            if abs(amount_float - grand_total_float) > amount_tolerance:
                frappe.log_error(
                    title="SePay Webhook Amount Mismatch",
                    message=f"Expected: {invoice.grand_total}, Got: {amount}",
                )
                frappe.throw(_("Số tiền không khớp. Vui lòng kiểm tra lại amount thanh toán."))
        except:
            frappe.throw(_("Giá trị amount không hợp lệ."))

        # Update invoice payment info
        update_sepay_payment_log(invoice.name, _json.dumps({
            "payment_code": payment_code,
            "transaction_id": transaction_id,
            "amount": amount,
            "status": sepay_status,
            "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "already_processed": False,
        }))
        # Reload invoice to avoid optimistic locking conflict after update_sepay_payment_log saved it
        invoice = frappe.get_doc("POS Invoice", invoice.name)

        # Determine Mode of Payment from invoice.payments (payment method thực tế của đơn)
        if not invoice.get("payments"):
            frappe.throw(_("POS Invoice has no payment methods. Please set the payment method when creating the invoice."))

        mode_of_payment = None
        for payment in invoice.payments:
            if flt(payment.amount) == flt(amount):
                mode_of_payment = payment.mode_of_payment
                break
        if not mode_of_payment and invoice.payments:
            mode_of_payment = invoice.payments[0].mode_of_payment

        if not mode_of_payment:
            frappe.throw(_("Cannot determine Mode of Payment from POS Invoice payments."))

        # Append payment method + amount to invoice.payments
        invoice.append("payments", {
            "mode_of_payment": mode_of_payment,
            "amount": flt(amount),
        })

        # Update invoice payment status
        invoice.payment_status = "Đã thanh toán"
        invoice.save(ignore_permissions=True)

        # Submit invoice → ERPNext auto-marks as Paid → on_submit hook sets custom_kitchen_status
        invoice.submit()

        return {
            "success": True,
            "message": "Xác nhận thanh toán thành công",
            "invoice_name": invoice.name,
            "payment_code": payment_code,
            "amount": amount,
            "transaction_id": transaction_id,
        }

    except Exception as e:
        frappe.log_error(
            title="SePay Webhook Error",
            message=f"{str(e)}\n{frappe.get_traceback()}",
        )
        frappe.throw(_("Lỗi xử lý webhook SePay: {0}").format(str(e)))


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


